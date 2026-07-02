"""Tests for the unified experiment configuration loader."""
from __future__ import annotations

import textwrap
from pathlib import Path

import pytest
import yaml

from chaos_engine.experiments.config import (
    ExperimentConfig,
    ModelConfig,
    PerRequestParams,
    PROTOCOL_AGENT_KINDS,
)


@pytest.fixture
def minimal_yaml(tmp_path: Path) -> Path:
    data = {
        "name": "test_exp",
        "description": "A test experiment",
        "generation": "T1",
        "model": {"id": "test-model-7b", "provider": "local"},
        "protocols": ["http"],
        "failure_rates": [0.0, 0.10],
        "experiments_per_rate": 10,
        "seed": 42,
    }
    p = tmp_path / "experiment.yaml"
    p.write_text(yaml.dump(data), encoding="utf-8")
    return p


@pytest.fixture
def full_yaml(tmp_path: Path) -> Path:
    data = {
        "name": "full_exp",
        "description": "Full config test",
        "generation": "G99",
        "model": {
            "id": "vendor/big-model-70b",
            "tag": "big70b",
            "provider": "zhipuai",
            "runtime": "cloud",
            "base_url": "https://api.example.com/v1",
            "has_thinking": True,
            "sleep_between_rates_s": 5,
        },
        "per_request_params": {
            "temperature": 0.3,
            "seed": 999,
            "thinking": [True, False],
        },
        "protocols": ["http", "mcp", "a2a"],
        "failure_rates": [0.0, 0.05, 0.10, 0.20],
        "experiments_per_rate": 200,
        "seed": 999,
        "harness": True,
        "trace": True,
        "simulate_delays": False,
        "sleep_between_rates_s": 10,
        "sleep_between_protocols_s": 60,
    }
    p = tmp_path / "experiment.yaml"
    p.write_text(yaml.dump(data), encoding="utf-8")
    return p


class TestModelConfig:
    def test_from_dict_minimal(self):
        mc = ModelConfig.from_dict({"id": "my-model"})
        assert mc.id == "my-model"
        assert mc.provider == "local"
        assert mc.tag == ""
        assert mc.has_thinking is False
        assert mc.sleep_between_rates_s == 30

    def test_from_dict_full(self):
        mc = ModelConfig.from_dict({
            "id": "glm-4.5",
            "tag": "glm45",
            "provider": "zhipuai",
            "has_thinking": True,
            "sleep_between_rates_s": 5,
        })
        assert mc.tag == "glm45"
        assert mc.provider == "zhipuai"
        assert mc.has_thinking is True
        assert mc.sleep_between_rates_s == 5


class TestPerRequestParams:
    def test_from_none(self):
        p = PerRequestParams.from_dict(None)
        assert p.temperature == 0.2
        assert p.thinking is None

    def test_thinking_list(self):
        p = PerRequestParams.from_dict({"thinking": [True, False]})
        assert p.thinking == [True, False]

    def test_thinking_scalar(self):
        p = PerRequestParams.from_dict({"thinking": True})
        assert p.thinking == [True]

    def test_no_thinking(self):
        p = PerRequestParams.from_dict({"temperature": 0.5})
        assert p.thinking is None
        assert p.temperature == 0.5


class TestExperimentConfig:
    def test_load_minimal(self, minimal_yaml: Path):
        cfg = ExperimentConfig.load(minimal_yaml)
        assert cfg.name == "test_exp"
        assert cfg.model.id == "test-model-7b"
        assert cfg.protocols == ["http"]
        assert cfg.failure_rates == [0.0, 0.10]
        assert cfg.experiments_per_rate == 10
        assert cfg.seed == 42
        assert cfg.harness is False
        assert cfg.trace is False

    def test_load_from_directory(self, minimal_yaml: Path):
        cfg = ExperimentConfig.load(minimal_yaml.parent)
        assert cfg.name == "test_exp"

    def test_load_full(self, full_yaml: Path):
        cfg = ExperimentConfig.load(full_yaml)
        assert cfg.name == "full_exp"
        assert cfg.model.tag == "big70b"
        assert cfg.model.has_thinking is True
        assert cfg.harness is True
        assert cfg.trace is True
        assert cfg.sleep_between_rates_s == 10
        assert cfg.sleep_between_protocols_s == 60

    def test_experiment_dir(self, minimal_yaml: Path):
        cfg = ExperimentConfig.load(minimal_yaml)
        assert cfg.experiment_dir == minimal_yaml.parent

    def test_model_tag_from_tag_field(self, full_yaml: Path):
        cfg = ExperimentConfig.load(full_yaml)
        assert cfg._model_tag() == "big70b"

    def test_model_tag_auto_generated(self, minimal_yaml: Path):
        cfg = ExperimentConfig.load(minimal_yaml)
        assert cfg._model_tag() == "test-model-7b"

    def test_thinking_modes_from_per_request(self, full_yaml: Path):
        cfg = ExperimentConfig.load(full_yaml)
        assert cfg.thinking_modes() == [True, False]

    def test_thinking_modes_from_has_thinking(self, minimal_yaml: Path):
        cfg = ExperimentConfig.load(minimal_yaml)
        cfg.model.has_thinking = True
        cfg.per_request_params.thinking = None
        assert cfg.thinking_modes() == [True]

    def test_thinking_modes_none(self, minimal_yaml: Path):
        cfg = ExperimentConfig.load(minimal_yaml)
        assert cfg.thinking_modes() == [None]

    def test_effective_sleep_override(self, full_yaml: Path):
        cfg = ExperimentConfig.load(full_yaml)
        assert cfg.effective_sleep_between_rates == 10

    def test_effective_sleep_from_model(self, minimal_yaml: Path):
        cfg = ExperimentConfig.load(minimal_yaml)
        assert cfg.effective_sleep_between_rates == 30

    def test_output_dir_no_thinking(self, minimal_yaml: Path):
        cfg = ExperimentConfig.load(minimal_yaml)
        out = cfg.output_dir("http", None)
        assert out == cfg.experiment_dir / "test-model-7b" / "http"

    def test_output_dir_with_thinking(self, full_yaml: Path):
        cfg = ExperimentConfig.load(full_yaml)
        out = cfg.output_dir("mcp", True)
        assert out == cfg.experiment_dir / "big70b" / "mcp_think"

    def test_output_dir_custom_tag(self, minimal_yaml: Path):
        cfg = ExperimentConfig.load(minimal_yaml)
        out = cfg.output_dir("http", None, model_tag="custom")
        assert out == cfg.experiment_dir / "custom" / "http"

    def test_build_agent_names(self, full_yaml: Path):
        cfg = ExperimentConfig.load(full_yaml)
        nopb, pb = cfg.build_agent_names("http", True)
        assert nopb == "http-big70b-think-nopb"
        assert pb == "http-big70b-think-pb"

    def test_build_agent_names_no_thinking(self, minimal_yaml: Path):
        cfg = ExperimentConfig.load(minimal_yaml)
        nopb, pb = cfg.build_agent_names("mcp", None)
        assert nopb == "mcp-test-model-7b-nopb"
        assert pb == "mcp-test-model-7b-pb"

    def test_file_not_found(self, tmp_path: Path):
        with pytest.raises(FileNotFoundError):
            ExperimentConfig.load(tmp_path / "nonexistent.yaml")


class TestProtocolAgentKinds:
    def test_all_protocols_present(self):
        assert set(PROTOCOL_AGENT_KINDS.keys()) == {"http", "mcp", "a2a"}

    def test_each_has_nopb_and_pb(self):
        for proto, kinds in PROTOCOL_AGENT_KINDS.items():
            assert "nopb" in kinds, f"{proto} missing nopb"
            assert "pb" in kinds, f"{proto} missing pb"
