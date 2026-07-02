"""Pydantic-based configuration models with validation.

Replaces raw dict-based config access with typed, validated models.
Supports loading from YAML files and environment variables.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Final, Optional

from pydantic import BaseModel, Field, field_validator


# ── Named failure-rate profiles ─────────────────────────────────────────
RATES_PAPER: Final[list[float]] = [
    0.0, 0.01, 0.02, 0.04, 0.06, 0.08, 0.10, 0.15, 0.20, 0.25, 0.30,
]
RATES_ABLATION: Final[list[float]] = [0.0, 0.05, 0.10, 0.20, 0.30]
RATES_QUICK: Final[list[float]] = [0.1, 0.3, 0.5]


# ── Playbook path resolution ────────────────────────────────────────────
_PROJECT_ROOT: Final[Path] = Path(__file__).resolve().parents[3]


class PlaybookPaths(BaseModel):
    """Playbook file paths, resolved relative to project root."""
    baseline: str = "assets/playbooks/baseline.json"
    training: str = "assets/playbooks/training.json"
    candidate: str = "assets/playbooks/candidate.json"

    def resolve(self, relative: str) -> Path:
        """Resolve a playbook path relative to the project root."""
        return _PROJECT_ROOT / relative

    @property
    def baseline_abs(self) -> Path:
        return self.resolve(self.baseline)

    @property
    def training_abs(self) -> Path:
        return self.resolve(self.training)

    @property
    def candidate_abs(self) -> Path:
        return self.resolve(self.candidate)


# ── Service defaults ─────────────────────────────────────────────────────
DEFAULT_API_BASE_URL: Final[str] = "https://petstore3.swagger.io/api/v3"
DEFAULT_LLM_PROVIDER: Final[str] = "zhipuai"
DEFAULT_PROMETHEUS_URL: Final[str] = "http://localhost:9090"
DEFAULT_METRICS_PORT: Final[int] = 8000
DEFAULT_SERVE_INTERVAL_S: Final[int] = 60


class TimeoutSettings(BaseModel):
    """Centralized timeout and retry defaults."""
    http_timeout_s: float = Field(default=10.0, gt=0)
    llm_retry_min_wait_s: float = Field(default=8.0, gt=0)
    llm_retry_max_wait_s: float = Field(default=120.0, gt=0)
    default_max_retries: int = Field(default=3, ge=1)
    default_retry_delay_s: float = Field(default=1.0, ge=0)
    jitter_factor: float = Field(default=0.5, ge=0, le=1)


class AgentSettings(BaseModel):
    """LLM agent configuration."""
    model: str = ""


class ExperimentSettings(BaseModel):
    """Experiment defaults."""
    default_seed: int = Field(default=42, ge=0)


class CircuitBreakerSettings(BaseModel):
    """Circuit breaker configuration constants."""
    failure_threshold: int = Field(default=3, ge=1)
    cooldown_seconds: int = Field(default=30, ge=1)


class SimulationSettings(BaseModel):
    """Parametric simulation configuration."""
    failure_rates: list[float] = Field(default_factory=lambda: list(RATES_ABLATION))
    experiments_per_rate: int = Field(default=50, ge=1)
    seed: int = Field(default=42, ge=0)
    playbooks: PlaybookPaths = Field(default_factory=PlaybookPaths)
    simulate_delays: bool = False
    circuit_breaker: CircuitBreakerSettings = Field(default_factory=CircuitBreakerSettings)

    @property
    def playbook_baseline(self) -> str:
        return self.playbooks.baseline

    @property
    def playbook_training(self) -> str:
        return self.playbooks.training

    @field_validator("failure_rates", mode="before")
    @classmethod
    def _validate_rates(cls, v: Any) -> list[float]:
        if isinstance(v, (int, float)):
            v = [v]
        for rate in v:
            if not 0.0 <= rate <= 1.0:
                raise ValueError(f"failure_rate must be in [0, 1], got {rate}")
        return v


class AppSettings(BaseModel):
    """Top-level application settings.

    Can be constructed from a raw config dict (e.g. YAML) via::

        settings = AppSettings.from_yaml_dict(config)
    """
    environment: str = "dev"
    agent: AgentSettings = Field(default_factory=AgentSettings)
    experiment: ExperimentSettings = Field(default_factory=ExperimentSettings)
    simulation: SimulationSettings = Field(default_factory=SimulationSettings)
    runner_type: str = "InMemoryRunner"
    mock_mode: bool = False
    use_vertex_ai: bool = False

    @classmethod
    def from_yaml_dict(cls, data: dict[str, Any]) -> AppSettings:
        """Build settings from a raw YAML-loaded dict, tolerating missing keys."""
        runner_type = data.get("runner", {}).get("type", "InMemoryRunner")
        sim_data = data.get("simulation", {})
        if sim_data:
            # Migrate legacy flat playbook keys into nested playbooks dict
            if "playbook_baseline" in sim_data or "playbook_training" in sim_data:
                pb = sim_data.pop("playbooks", {})
                if "playbook_baseline" in sim_data:
                    pb["baseline"] = sim_data.pop("playbook_baseline")
                if "playbook_training" in sim_data:
                    pb["training"] = sim_data.pop("playbook_training")
                sim_data["playbooks"] = pb
        return cls(
            environment=data.get("environment", "dev"),
            agent=AgentSettings(**data["agent"]) if "agent" in data else AgentSettings(),
            experiment=ExperimentSettings(**data["experiment"]) if "experiment" in data else ExperimentSettings(),
            simulation=SimulationSettings(**sim_data) if sim_data else SimulationSettings(),
            runner_type=runner_type,
            mock_mode=data.get("mock_mode", False),
            use_vertex_ai=data.get("use_vertex_ai", False),
        )
