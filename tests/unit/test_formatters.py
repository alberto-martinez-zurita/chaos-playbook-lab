"""Tests for reporting formatters — export_summary_json and print_summary."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict

import pytest

from chaos_engine.reporting.formatters import export_summary_json, print_summary


# ---------------------------------------------------------------------------
# Fixture: a realistic comparison dict matching aggregator output
# ---------------------------------------------------------------------------

@pytest.fixture()
def comparison() -> Dict[str, Any]:
    return {
        "baseline": {
            "success_rate": {"mean": 0.45, "std": 0.0702},
            "consistency": {"consistency_rate": 0.90},
            "latency": {"mean_latency_s": 0.15},
        },
        "playbook": {
            "success_rate": {"mean": 0.82, "std": 0.0543},
            "consistency": {"consistency_rate": 0.95},
            "latency": {"mean_latency_s": 0.28},
            "unique_strategies_used": 4,
            "total_strategy_uses": 120,
        },
        "improvements": {
            "success_rate_improvement_pct": 82.22,
            "consistency_improvement_pct": 50.00,
            "latency_overhead_pct": 86.67,
        },
        "validation": {
            "metric_001_success_rate_20pct": True,
            "metric_002_consistency_maintained": True,
            "metric_003_latency_200pct": True,
        },
    }


# ---------------------------------------------------------------------------
# export_summary_json
# ---------------------------------------------------------------------------

class TestExportSummaryJson:
    def test_creates_file(self, tmp_path: Path, comparison: dict):
        filepath = str(tmp_path / "summary.json")
        export_summary_json(comparison, filepath)
        assert Path(filepath).exists()

    def test_file_is_valid_json(self, tmp_path: Path, comparison: dict):
        filepath = str(tmp_path / "summary.json")
        export_summary_json(comparison, filepath)
        with open(filepath) as f:
            data = json.load(f)
        assert isinstance(data, dict)

    def test_file_content_matches_input(self, tmp_path: Path, comparison: dict):
        filepath = str(tmp_path / "summary.json")
        export_summary_json(comparison, filepath)
        with open(filepath) as f:
            data = json.load(f)
        assert data["baseline"]["success_rate"]["mean"] == 0.45
        assert data["validation"]["metric_001_success_rate_20pct"] is True

    def test_default_filename(self, tmp_path: Path, comparison: dict, monkeypatch):
        monkeypatch.chdir(tmp_path)
        export_summary_json(comparison)
        assert (tmp_path / "metrics_summary.json").exists()

    def test_pretty_printed(self, tmp_path: Path, comparison: dict):
        filepath = str(tmp_path / "summary.json")
        export_summary_json(comparison, filepath)
        content = Path(filepath).read_text()
        # indent=2 means newlines and spaces
        assert "\n" in content
        assert "  " in content

    def test_empty_comparison(self, tmp_path: Path):
        filepath = str(tmp_path / "empty.json")
        export_summary_json({}, filepath)
        with open(filepath) as f:
            data = json.load(f)
        assert data == {}


# ---------------------------------------------------------------------------
# print_summary
# ---------------------------------------------------------------------------

class TestPrintSummary:
    def test_logs_summary(self, comparison: dict, caplog):
        with caplog.at_level(logging.INFO, logger="chaos_engine.reporting.formatters"):
            print_summary(comparison)
        assert "A/B TEST RESULTS SUMMARY" in caplog.text

    def test_logs_baseline_stats(self, comparison: dict, caplog):
        with caplog.at_level(logging.INFO, logger="chaos_engine.reporting.formatters"):
            print_summary(comparison)
        assert "BASELINE AGENT" in caplog.text
        assert "45.00%" in caplog.text  # 0.45 formatted as percent

    def test_logs_playbook_stats(self, comparison: dict, caplog):
        with caplog.at_level(logging.INFO, logger="chaos_engine.reporting.formatters"):
            print_summary(comparison)
        assert "PLAYBOOK AGENT" in caplog.text
        assert "82.00%" in caplog.text

    def test_logs_improvements(self, comparison: dict, caplog):
        with caplog.at_level(logging.INFO, logger="chaos_engine.reporting.formatters"):
            print_summary(comparison)
        assert "IMPROVEMENTS" in caplog.text
        assert "82.22%" in caplog.text

    def test_logs_validation_pass(self, comparison: dict, caplog):
        with caplog.at_level(logging.INFO, logger="chaos_engine.reporting.formatters"):
            print_summary(comparison)
        assert "PASS" in caplog.text

    def test_logs_validation_fail(self, comparison: dict, caplog):
        comparison["validation"]["metric_001_success_rate_20pct"] = False
        with caplog.at_level(logging.INFO, logger="chaos_engine.reporting.formatters"):
            print_summary(comparison)
        assert "FAIL" in caplog.text

    def test_logs_strategy_counts(self, comparison: dict, caplog):
        with caplog.at_level(logging.INFO, logger="chaos_engine.reporting.formatters"):
            print_summary(comparison)
        assert "4 unique" in caplog.text
        assert "120 total" in caplog.text

    def test_logs_latency(self, comparison: dict, caplog):
        with caplog.at_level(logging.INFO, logger="chaos_engine.reporting.formatters"):
            print_summary(comparison)
        assert "0.15s" in caplog.text  # baseline latency
        assert "0.28s" in caplog.text  # playbook latency

    def test_zero_values(self, caplog):
        comparison = {
            "baseline": {
                "success_rate": {"mean": 0.0, "std": 0.0},
                "consistency": {"consistency_rate": 0.0},
                "latency": {"mean_latency_s": 0.0},
            },
            "playbook": {
                "success_rate": {"mean": 0.0, "std": 0.0},
                "consistency": {"consistency_rate": 0.0},
                "latency": {"mean_latency_s": 0.0},
                "unique_strategies_used": 0,
                "total_strategy_uses": 0,
            },
            "improvements": {
                "success_rate_improvement_pct": 0.0,
                "consistency_improvement_pct": 0.0,
                "latency_overhead_pct": 0.0,
            },
            "validation": {
                "metric_001_success_rate_20pct": False,
                "metric_002_consistency_maintained": True,
                "metric_003_latency_200pct": True,
            },
        }
        with caplog.at_level(logging.INFO, logger="chaos_engine.reporting.formatters"):
            print_summary(comparison)
        assert "0.00%" in caplog.text

    def test_perfect_scores(self, caplog):
        comparison = {
            "baseline": {
                "success_rate": {"mean": 1.0, "std": 0.0},
                "consistency": {"consistency_rate": 1.0},
                "latency": {"mean_latency_s": 0.01},
            },
            "playbook": {
                "success_rate": {"mean": 1.0, "std": 0.0},
                "consistency": {"consistency_rate": 1.0},
                "latency": {"mean_latency_s": 0.01},
                "unique_strategies_used": 5,
                "total_strategy_uses": 500,
            },
            "improvements": {
                "success_rate_improvement_pct": 0.0,
                "consistency_improvement_pct": 0.0,
                "latency_overhead_pct": 0.0,
            },
            "validation": {
                "metric_001_success_rate_20pct": False,
                "metric_002_consistency_maintained": True,
                "metric_003_latency_200pct": True,
            },
        }
        with caplog.at_level(logging.INFO, logger="chaos_engine.reporting.formatters"):
            print_summary(comparison)
        assert "100.00%" in caplog.text
