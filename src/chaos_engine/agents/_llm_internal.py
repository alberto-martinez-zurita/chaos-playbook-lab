"""Vendored LLM call path — preserves bit-for-bit equivalence with the prior
provider abstraction so re-runs against z.ai / OpenAI produce the same per-call
output (same request shape, same response parsing, same retry semantics).

Public surface (intentionally minimal):
- ``LLMResponse``   — unified response dataclass.
- ``LLMConfig``     — retry + provider tuning, mutable singleton via ``get_config()``.
- ``chat_raw(...)`` — the only call entry-point used by the lab.

Stripped from the upstream surface to keep this file self-contained and the
reproducibility package free of unrelated concerns: tracing, accounting,
fallback chains, transparency / compliance metadata, and the Anthropic
provider (the paper does not exercise it).

Configuration is read from environment variables with no other config source:
- z.ai (zhipuai):  ``ZHIPUAI_API_KEY``, ``ZHIPUAI_BASE_URL``
                   (default https://api.z.ai/api/coding/paas/v4)
- OpenAI:          ``OPENAI_API_KEY``
- Local OpenAI-compatible: ``LOCAL_API_KEY``, ``LOCAL_BASE_URL``
                            (default http://localhost:1234/v1)

Retry tuning is read from ``LLMConfig`` (mutable at runtime — the lab's
``LLMClient.__init__`` overrides ``max_retries``, ``retry_min_wait``,
``retry_max_wait`` per instance, matching the previous behaviour).
"""

from __future__ import annotations

import logging
import os
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

import httpx
from openai import OpenAI
from tenacity import (
    RetryCallState,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

logger = logging.getLogger(__name__)


# ── response dataclass ──────────────────────────────────────────────────────

@dataclass(frozen=True)
class LLMResponse:
    """Unified response from any provider."""

    text: str
    input_chars: int
    output_chars: int
    provider: str
    model: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    reasoning_tokens: int = 0


# ── configuration ───────────────────────────────────────────────────────────

@dataclass
class LLMConfig:
    """Retry + provider tuning. Singleton accessed via ``get_config()``."""

    # Retry — overridden per LLMClient instance.
    max_retries: int = 5
    retry_min_wait: float = 5.0
    retry_max_wait: float = 60.0
    retry_multiplier: float = 2.0

    # ZhipuAI / z.ai serialization.
    zhipu_cooldown: float = 2.0
    zhipu_timeout: float = 300.0

    default_models: dict[str, str] = field(default_factory=lambda: {
        "openai": "gpt-4o",
        "zhipuai": "glm-4.5",
        "local": "local-model",
    })


_config: Optional[LLMConfig] = None


def get_config() -> LLMConfig:
    global _config
    if _config is None:
        _config = LLMConfig()
    return _config


# ── retry wrapper ───────────────────────────────────────────────────────────

def _log_retry(retry_state: RetryCallState) -> None:
    exc = retry_state.outcome.exception() if retry_state.outcome else None
    logger.warning(
        "LLM call attempt %d failed: %s — retrying…",
        retry_state.attempt_number, exc,
    )


def with_retry(fn: Callable[..., object]) -> Callable[..., object]:
    """Wrap *fn* with tenacity retry using current ``LLMConfig`` values."""
    cfg = get_config()
    return retry(
        stop=stop_after_attempt(cfg.max_retries),
        wait=wait_exponential(
            multiplier=cfg.retry_multiplier,
            min=cfg.retry_min_wait,
            max=cfg.retry_max_wait,
        ),
        retry=retry_if_exception_type(Exception),
        before_sleep=_log_retry,
        reraise=True,
    )(fn)


# ── OpenAI-compatible provider ──────────────────────────────────────────────

# Provider presets: (env_key_for_api_key, env_key_for_base_url, default_base_url)
_PRESETS: dict[str, tuple[str, Optional[str], Optional[str]]] = {
    "openai": ("OPENAI_API_KEY", None, None),
    "zhipuai": ("ZHIPUAI_API_KEY", "ZHIPUAI_BASE_URL", "https://api.z.ai/api/coding/paas/v4"),
    "local": ("LOCAL_API_KEY", "LOCAL_BASE_URL", "http://localhost:1234/v1"),
}

_zhipu_lock = threading.Lock()


class OpenAICompatProvider:
    """Wraps any OpenAI-compatible API."""

    def __init__(
        self,
        name: str,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
    ) -> None:
        self.name = name
        preset = _PRESETS.get(name)

        if api_key is None and preset:
            api_key = os.environ.get(preset[0], "")
        self._api_key = api_key or ""

        if base_url is None and preset:
            env_key = preset[1]
            base_url = os.environ.get(env_key, preset[2]) if env_key else preset[2]
        self._base_url = base_url

        cfg = get_config()
        timeout = cfg.zhipu_timeout if name == "zhipuai" else 120.0

        kwargs: dict[str, Any] = {
            "api_key": self._api_key,
            "timeout": httpx.Timeout(timeout, connect=15.0),
        }
        if self._base_url:
            kwargs["base_url"] = self._base_url
        self._client = OpenAI(**kwargs)

    def call(
        self,
        system_prompt: str,
        user_message: str,
        model: str,
        temperature: float = 0.2,
        thinking: Optional[bool] = None,
        **extra_params: object,
    ) -> LLMResponse:
        cfg = get_config()
        messages: list[dict[str, str]] = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ]

        if self.name == "zhipuai":
            with _zhipu_lock:
                response = self._do_call(messages, model, temperature, thinking=thinking, **extra_params)
                if cfg.zhipu_cooldown > 0:
                    time.sleep(cfg.zhipu_cooldown)
                return response
        return self._do_call(messages, model, temperature, thinking=thinking, **extra_params)

    def _do_call(
        self,
        messages: list[dict[str, str]],
        model: str,
        temperature: float,
        *,
        thinking: Optional[bool] = None,
        **extra_params: object,
    ) -> LLMResponse:
        kwargs: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
        }
        for k, v in extra_params.items():
            if v is not None:
                kwargs[k] = v
        if thinking is not None:
            kwargs["extra_body"] = {"thinking": {"type": "enabled" if thinking else "disabled"}}

        resp = self._client.chat.completions.create(**kwargs)
        text = resp.choices[0].message.content or ""
        input_chars = sum(len(m["content"]) for m in messages)
        usage = resp.usage
        reasoning_tokens = 0
        if usage and hasattr(usage, "completion_tokens_details") and usage.completion_tokens_details:
            reasoning_tokens = getattr(usage.completion_tokens_details, "reasoning_tokens", 0) or 0
        return LLMResponse(
            text=text,
            input_chars=input_chars,
            output_chars=len(text),
            provider=self.name,
            model=model,
            prompt_tokens=usage.prompt_tokens if usage else 0,
            completion_tokens=usage.completion_tokens if usage else 0,
            total_tokens=usage.total_tokens if usage else 0,
            reasoning_tokens=reasoning_tokens,
        )


# ── provider registry (lazy, per-name singleton) ────────────────────────────

_providers: dict[str, OpenAICompatProvider] = {}
_providers_lock = threading.Lock()


def _get_provider(name: str) -> OpenAICompatProvider:
    if name in _providers:
        return _providers[name]
    with _providers_lock:
        if name in _providers:
            return _providers[name]
        if name not in _PRESETS:
            raise ValueError(
                f"Provider '{name}' not registered. Available: {list(_PRESETS)}"
            )
        instance = OpenAICompatProvider(name)
        _providers[name] = instance
        return instance


# ── public entry point ──────────────────────────────────────────────────────

def chat_raw(
    system_prompt: str,
    user_message: str,
    provider: str = "openai",
    model: Optional[str] = None,
    temperature: float = 0.2,
    thinking: Optional[bool] = None,
    **extra_params: object,
) -> LLMResponse:
    """Execute a chat completion with retry. Returns the full ``LLMResponse``.

    Args:
        thinking: ``True`` enables reasoning mode, ``False`` disables it,
            ``None`` (default) lets the provider/model decide.
        **extra_params: Forwarded verbatim to the underlying API call
            (e.g. ``seed=2026``).
    """
    cfg = get_config()
    resolved_model = model or cfg.default_models.get(provider, "gpt-4o")
    prov = _get_provider(provider)

    def _make_call() -> LLMResponse:
        return prov.call(
            system_prompt, user_message, resolved_model, temperature,
            thinking=thinking, **extra_params,
        )

    retried = with_retry(_make_call)
    result = retried()
    assert isinstance(result, LLMResponse)
    return result
