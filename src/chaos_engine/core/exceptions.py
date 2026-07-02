"""Custom exception hierarchy for the Chaos Playbook Engine."""
from __future__ import annotations


class ChaosEngineError(Exception):
    """Base exception for all Chaos Playbook Engine errors."""


class PlaybookError(ChaosEngineError):
    """Error loading, parsing, or applying a playbook."""


class ChaosInjectionError(ChaosEngineError):
    """Error during chaos fault injection."""


class CircuitBreakerOpenError(ChaosEngineError):
    """Raised when the circuit breaker blocks a request."""


class ExperimentError(ChaosEngineError):
    """Error during experiment execution or orchestration."""


class ConfigError(ChaosEngineError):
    """Error in configuration loading or validation."""
