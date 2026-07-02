"""Multi-provider LLM client — thin wrapper over the vendored call path.

Maintains the same public API (``LLMClient.chat()``) for backward compatibility
with ``llm_agent.py`` and ``parametric.py``. The underlying request shape,
response parsing, and retry semantics are vendored verbatim from the prior
provider abstraction so re-runs against z.ai / OpenAI produce the same
per-call output as before.
"""
from __future__ import annotations

import logging
from typing import Optional

from chaos_engine.agents import _llm_internal
from chaos_engine.core.settings import DEFAULT_LLM_PROVIDER, TimeoutSettings

logger = logging.getLogger(__name__)

_TIMEOUTS = TimeoutSettings()


class LLMClient:
    """Multi-provider LLM client.

    Tracks cumulative input/output characters and tokens across all calls
    via instance counters.  Agents read these after a run to populate
    cost/efficiency columns in the experiment CSV.
    """

    def __init__(
        self,
        provider: str = DEFAULT_LLM_PROVIDER,
        model: Optional[str] = None,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        temperature: float = 0.2,
        max_retries: int = 10,
        thinking: Optional[bool] = None,
        seed: Optional[int] = None,
    ) -> None:
        self.provider = provider
        resolved = _llm_internal.get_config().default_models.get(provider)
        if not model and not resolved:
            raise ValueError(
                f"No model specified and no default for provider '{provider}'. "
                "Pass model= explicitly."
            )
        self.model = model or resolved
        self.temperature = temperature
        self.thinking = thinking
        self.seed = seed

        # Cumulative counters — reset per experiment via reset_counters()
        self.total_input_chars: int = 0
        self.total_output_chars: int = 0
        self.total_prompt_tokens: int = 0
        self.total_completion_tokens: int = 0
        self.total_reasoning_tokens: int = 0

        # Aggressive retry for z.ai 429s — provider rate-limits must never
        # contaminate experiment data (those are API-layer errors, not
        # chaos-injected faults).
        cfg = _llm_internal.get_config()
        cfg.max_retries = max_retries
        cfg.retry_min_wait = _TIMEOUTS.llm_retry_min_wait_s
        cfg.retry_max_wait = _TIMEOUTS.llm_retry_max_wait_s

        logger.info(
            "LLMClient initialized: provider=%s model=%s",
            provider, self.model,
        )

    def chat(
        self,
        system_prompt: str,
        user_message: str,
        temperature: Optional[float] = None,
        seed: Optional[int] = None,
    ) -> str:
        """Send a chat completion request. Returns the response text.

        Side-effect: accumulates chars and tokens in instance counters.
        """
        temp = temperature if temperature is not None else self.temperature
        effective_seed = seed if seed is not None else self.seed
        extra: dict[str, object] = {}
        if effective_seed is not None:
            extra["seed"] = effective_seed
        resp = _llm_internal.chat_raw(
            system_prompt=system_prompt,
            user_message=user_message,
            provider=self.provider,
            model=self.model,
            temperature=temp,
            thinking=self.thinking,
            **extra,
        )
        self.total_input_chars += resp.input_chars
        self.total_output_chars += resp.output_chars
        self.total_prompt_tokens += getattr(resp, 'prompt_tokens', 0)
        self.total_completion_tokens += getattr(resp, 'completion_tokens', 0)
        self.total_reasoning_tokens += getattr(resp, 'reasoning_tokens', 0)
        return resp.text

    def reset_counters(self) -> None:
        """Reset all counters — call before each experiment run."""
        self.total_input_chars = 0
        self.total_output_chars = 0
        self.total_prompt_tokens = 0
        self.total_completion_tokens = 0
        self.total_reasoning_tokens = 0
