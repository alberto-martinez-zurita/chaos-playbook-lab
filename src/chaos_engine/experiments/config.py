"""Unified experiment configuration loader.

Reads experiment.yaml files and produces typed configuration objects
that the unified runner (and dashboard) can consume directly.
"""
from __future__ import annotations

import functools
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Final

import yaml

logger = logging.getLogger(__name__)

_REGISTRY_PATH: Final[Path] = (
    Path(__file__).resolve().parents[3] / "assets" / "models" / "registry.yaml"
)


@functools.lru_cache(maxsize=1)
def _load_registry() -> dict[str, dict[str, Any]]:
    if not _REGISTRY_PATH.exists():
        logger.warning("Model registry not found: %s", _REGISTRY_PATH)
        return {}
    with open(_REGISTRY_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}

PROTOCOL_AGENT_KINDS: dict[str, dict[str, str]] = {
    "http": {"nopb": "llm", "pb": "llm_playbook"},
    "mcp": {"nopb": "mcp_llm", "pb": "mcp_llm_playbook"},
    "a2a": {"nopb": "a2a_llm", "pb": "a2a_llm_playbook"},
}


@dataclass
class ModelConfig:
    id: str
    tag: str = ""
    provider: str = "local"
    runtime: str = ""
    base_url: str | None = None
    notes: str = ""
    has_thinking: bool = False
    sleep_between_rates_s: int = 30

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ModelConfig:
        return cls(
            id=data["id"],
            tag=data.get("tag", ""),
            provider=data.get("provider", "local"),
            runtime=data.get("runtime", ""),
            base_url=data.get("base_url"),
            notes=data.get("notes", ""),
            has_thinking=data.get("has_thinking", False),
            sleep_between_rates_s=data.get("sleep_between_rates_s", 30),
        )

    @classmethod
    def from_registry(cls, key: str, overrides: dict[str, Any] | None = None) -> ModelConfig:
        """Load a model from the registry YAML by its tag key."""
        registry = _load_registry()
        if key not in registry:
            raise KeyError(f"Model '{key}' not found in registry. Available: {list(registry)}")
        data = dict(registry[key])
        data.setdefault("tag", key)
        if overrides:
            data.update(overrides)
        return cls.from_dict(data)


@dataclass
class PerRequestParams:
    temperature: float = 0.2
    seed: int | None = None
    thinking: list[bool] | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> PerRequestParams:
        if not data:
            return cls()
        thinking_raw = data.get("thinking")
        thinking: list[bool] | None = None
        if isinstance(thinking_raw, list):
            thinking = [bool(t) for t in thinking_raw]
        elif isinstance(thinking_raw, bool):
            thinking = [thinking_raw]
        return cls(
            temperature=data.get("temperature", 0.2),
            seed=data.get("seed"),
            thinking=thinking,
        )


@dataclass
class ExperimentConfig:
    """Typed configuration loaded from an experiment.yaml file."""

    name: str
    description: str
    generation: str
    config_path: Path

    model: ModelConfig
    per_request_params: PerRequestParams

    protocols: list[str]
    failure_rates: list[float]
    experiments_per_rate: int

    seed: int = 2026
    harness: bool = False
    trace: bool = False
    simulate_delays: bool = False

    sleep_between_rates_s: int | None = None
    sleep_between_protocols_s: int = 0

    @property
    def experiment_dir(self) -> Path:
        return self.config_path.parent

    @property
    def effective_sleep_between_rates(self) -> int:
        if self.sleep_between_rates_s is not None:
            return self.sleep_between_rates_s
        return self.model.sleep_between_rates_s

    def thinking_modes(self) -> list[bool | None]:
        if self.per_request_params.thinking:
            return [bool(t) for t in self.per_request_params.thinking]
        if self.model.has_thinking:
            return [True]
        return [None]

    def output_dir(
        self, protocol: str, thinking: bool | None, model_tag: str | None = None,
    ) -> Path:
        tag = model_tag or self._model_tag()
        base = self.experiment_dir / tag
        if thinking is None:
            return base / protocol
        think_tag = "think" if thinking else "nothink"
        return base / f"{protocol}_{think_tag}"

    def _model_tag(self) -> str:
        if self.model.tag:
            return self.model.tag
        raw = self.model.id
        return raw.replace("/", "-").replace(".", "").replace(" ", "")

    def build_agent_names(
        self, protocol: str, thinking: bool | None, model_tag: str | None = None,
    ) -> tuple[str, str]:
        tag = model_tag or self._model_tag()
        think_suffix = ""
        if thinking is not None:
            think_suffix = "-think" if thinking else "-nothink"
        nopb_name = f"{protocol}-{tag}{think_suffix}-nopb"
        pb_name = f"{protocol}-{tag}{think_suffix}-pb"
        return nopb_name, pb_name

    @classmethod
    def load(cls, path: str | Path) -> ExperimentConfig:
        path = Path(path).resolve()
        if path.is_dir():
            path = path / "experiment.yaml"
        if not path.exists():
            raise FileNotFoundError(f"Experiment config not found: {path}")

        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        model_raw = data.get("model", {})
        if isinstance(model_raw, str):
            model = ModelConfig.from_registry(model_raw)
        else:
            model = ModelConfig.from_dict(model_raw)
        per_request = PerRequestParams.from_dict(data.get("per_request_params"))

        cfg = cls(
            name=data["name"],
            description=data.get("description", ""),
            generation=data.get("generation", ""),
            config_path=path,
            model=model,
            per_request_params=per_request,
            protocols=data.get("protocols", ["http"]),
            failure_rates=data.get("failure_rates", [0.0, 0.05, 0.10, 0.20, 0.30]),
            experiments_per_rate=data.get("experiments_per_rate", 100),
            seed=data.get("seed", 2026),
            harness=data.get("harness", False),
            trace=data.get("trace", False),
            simulate_delays=data.get("simulate_delays", False),
            sleep_between_rates_s=data.get("sleep_between_rates_s"),
            sleep_between_protocols_s=data.get("sleep_between_protocols_s", 0),
        )

        logger.info(
            "Loaded experiment %r (%s) — %d protocols, %d rates, N=%d",
            cfg.name, cfg.model.id, len(cfg.protocols), len(cfg.failure_rates),
            cfg.experiments_per_rate,
        )
        return cfg
