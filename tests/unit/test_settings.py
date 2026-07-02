from __future__ import annotations

import pytest
from pydantic import ValidationError

from chaos_engine.core.settings import AppSettings, SimulationSettings


def test_default_settings():
    """AppSettings with no args should use sensible defaults."""
    s = AppSettings()
    assert s.environment == "dev"
    assert s.agent.model == ""
    assert s.experiment.default_seed == 42
    assert s.mock_mode is False


def test_from_yaml_dict_minimal():
    """from_yaml_dict should work with a minimal config."""
    data = {"environment": "prod", "agent": {"model": "gemini-2.5-pro"}}
    s = AppSettings.from_yaml_dict(data)
    assert s.environment == "prod"
    assert s.agent.model == "gemini-2.5-pro"
    assert s.experiment.default_seed == 42  # default


def test_from_yaml_dict_with_runner():
    """Runner type should be extracted from nested dict."""
    data = {"agent": {"model": "x"}, "runner": {"type": "CustomRunner"}}
    s = AppSettings.from_yaml_dict(data)
    assert s.runner_type == "CustomRunner"


def test_failure_rate_validation_rejects_out_of_range():
    """failure_rates outside [0, 1] should raise ValidationError."""
    with pytest.raises(ValidationError):
        SimulationSettings(failure_rates=[0.5, 1.5])


def test_failure_rate_validation_accepts_valid():
    """Valid failure rates should pass."""
    s = SimulationSettings(failure_rates=[0.0, 0.5, 1.0])
    assert s.failure_rates == [0.0, 0.5, 1.0]


def test_failure_rate_scalar_coerced_to_list():
    """A single float should be coerced to a list."""
    s = SimulationSettings(failure_rates=0.3)
    assert s.failure_rates == [0.3]


def test_experiments_per_rate_must_be_positive():
    """experiments_per_rate < 1 should raise ValidationError."""
    with pytest.raises(ValidationError):
        SimulationSettings(experiments_per_rate=0)
