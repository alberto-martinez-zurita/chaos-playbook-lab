"""Tests for N-agent comparison and leaderboard (H.2)."""
from __future__ import annotations

import json

import pytest

from chaos_engine.reporting.comparison import (
    AgentScore,
    RunSummary,
    build_leaderboard,
    compare_runs,
    extract_agent_names,
    extract_n_agent_data,
    print_leaderboard,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _two_agent_metrics() -> dict:
    return {
        "0.0": {
            "failure_rate": 0.0,
            "n_experiments": 5,
            "baseline": {
                "n_runs": 5,
                "success_rate": {"mean": 1.0, "std": 0.0},
                "duration_s": {"mean": 0.01, "std": 0.001},
                "inconsistencies": {"mean": 0.0, "std": 0.0},
            },
            "playbook": {
                "n_runs": 5,
                "success_rate": {"mean": 1.0, "std": 0.0},
                "duration_s": {"mean": 0.02, "std": 0.001},
                "inconsistencies": {"mean": 0.0, "std": 0.0},
            },
        },
        "0.5": {
            "failure_rate": 0.5,
            "n_experiments": 5,
            "baseline": {
                "n_runs": 5,
                "success_rate": {"mean": 0.4, "std": 0.1},
                "duration_s": {"mean": 0.05, "std": 0.01},
                "inconsistencies": {"mean": 0.2, "std": 0.1},
            },
            "playbook": {
                "n_runs": 5,
                "success_rate": {"mean": 0.8, "std": 0.05},
                "duration_s": {"mean": 0.08, "std": 0.02},
                "inconsistencies": {"mean": 0.0, "std": 0.0},
            },
        },
    }


def _three_agent_metrics() -> dict:
    m = _two_agent_metrics()
    for rate_key in m:
        m[rate_key]["aggressive"] = {
            "n_runs": 5,
            "success_rate": {"mean": 0.6, "std": 0.1},
            "duration_s": {"mean": 0.03, "std": 0.005},
            "inconsistencies": {"mean": 0.1, "std": 0.05},
        }
    return m


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_extract_agent_names_two():
    names = extract_agent_names(_two_agent_metrics())
    assert names == ["baseline", "playbook"]


def test_extract_agent_names_three():
    names = extract_agent_names(_three_agent_metrics())
    assert sorted(names) == ["aggressive", "baseline", "playbook"]


def test_extract_n_agent_data_structure():
    data = extract_n_agent_data(_two_agent_metrics())
    assert data["failure_rates"] == [0.0, 0.5]
    assert "baseline" in data["agents"]
    assert "playbook" in data["agents"]
    assert len(data["agents"]["baseline"]["success"]) == 2


def test_extract_n_agent_data_values():
    data = extract_n_agent_data(_two_agent_metrics())
    assert data["agents"]["baseline"]["success"][0] == 1.0
    assert data["agents"]["playbook"]["success"][1] == 0.8


def test_build_leaderboard_ordering():
    board = build_leaderboard(_two_agent_metrics())
    assert len(board) == 2
    # Playbook should rank higher (better success at 0.5 rate)
    assert board[0].name == "playbook"
    assert board[0].composite_score > board[1].composite_score


def test_build_leaderboard_three_agents():
    board = build_leaderboard(_three_agent_metrics())
    assert len(board) == 3
    names = [s.name for s in board]
    assert names[0] == "playbook"  # Best overall


def test_agent_score_composite():
    s = AgentScore(name="test", avg_success_rate=0.9, avg_duration_s=0.5, avg_inconsistencies=0.1)
    # 0.9*100 - 0.1*50 - 0.5*2 = 90 - 5 - 1 = 84
    assert s.composite_score == pytest.approx(84.0)


def test_print_leaderboard_format():
    output = print_leaderboard(_two_agent_metrics())
    assert "Rank" in output
    assert "baseline" in output
    assert "playbook" in output


def test_compare_runs(tmp_path):
    # Create two fake run directories
    for i, name in enumerate(["run_20260314_100000", "run_20260314_110000"]):
        run_dir = tmp_path / name
        run_dir.mkdir()
        metrics = _two_agent_metrics()
        # Slightly different data for second run
        if i == 1:
            metrics["0.5"]["playbook"]["success_rate"]["mean"] = 0.9
        with open(run_dir / "aggregated_metrics.json", "w") as f:
            json.dump(metrics, f)

    summaries = compare_runs([tmp_path / "run_20260314_100000", tmp_path / "run_20260314_110000"])
    assert len(summaries) == 2
    assert summaries[0].timestamp < summaries[1].timestamp
    # Second run should have higher playbook score
    assert summaries[1].leaderboard[0].avg_success_rate > summaries[0].leaderboard[0].avg_success_rate


def test_compare_runs_skips_missing(tmp_path):
    empty_dir = tmp_path / "run_empty"
    empty_dir.mkdir()
    summaries = compare_runs([empty_dir])
    assert len(summaries) == 0
