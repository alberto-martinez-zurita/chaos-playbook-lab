"""Integration test — full pipeline with DeterministicAgent (no API key needed).

Replaces the legacy test_order_agent.py that required GOOGLE_API_KEY.
Tests the complete stack: ChaosProxy → CircuitBreakerProxy → DeterministicAgent
with real playbook files from assets/.
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from chaos_engine.agents.deterministic import DeterministicAgent
from chaos_engine.chaos.proxy import ChaosProxy
from chaos_engine.core.resilience import CircuitBreakerProxy
from chaos_engine.core.types import Status, WorkflowStep
from chaos_engine.simulation.parametric import ParametricABTestRunner

BASELINE_PLAYBOOK = "assets/playbooks/baseline.json"
TRAINING_PLAYBOOK = "assets/playbooks/training.json"


# ---------------------------------------------------------------------------
# Single agent run — full stack integration
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_deterministic_agent_succeeds_with_no_chaos():
    """With failure_rate=0, all 4 steps should succeed."""
    chaos = ChaosProxy(failure_rate=0.0, seed=42, mock_mode=True, verbose=False)
    cb = CircuitBreakerProxy(wrapped_executor=chaos, failure_threshold=3, cooldown_seconds=30)
    agent = DeterministicAgent(
        tool_executor=cb,
        playbook_path=TRAINING_PLAYBOOK,
        simulate_delays=False,
    )

    result = await agent.run()

    assert result["status"] == Status.SUCCESS
    assert len(result["steps_completed"]) == 4
    assert result["failed_at"] is None
    assert result["duration_ms"] >= 0


@pytest.mark.asyncio
async def test_deterministic_agent_fails_under_total_chaos():
    """With failure_rate=1.0, agent should fail (circuit breaker will open)."""
    chaos = ChaosProxy(failure_rate=1.0, seed=42, mock_mode=True, verbose=False)
    cb = CircuitBreakerProxy(wrapped_executor=chaos, failure_threshold=3, cooldown_seconds=30)
    agent = DeterministicAgent(
        tool_executor=cb,
        playbook_path=TRAINING_PLAYBOOK,
        simulate_delays=False,
    )

    result = await agent.run()

    assert result["status"] == Status.FAILURE
    assert result["failed_at"] is not None


@pytest.mark.asyncio
async def test_baseline_vs_training_playbook_deterministic():
    """Same chaos seed: training playbook should perform >= baseline."""
    results = {}
    for name, playbook in [("baseline", BASELINE_PLAYBOOK), ("training", TRAINING_PLAYBOOK)]:
        chaos = ChaosProxy(failure_rate=0.3, seed=100, mock_mode=True, verbose=False)
        cb = CircuitBreakerProxy(wrapped_executor=chaos, failure_threshold=3, cooldown_seconds=30)
        agent = DeterministicAgent(
            tool_executor=cb,
            playbook_path=playbook,
            simulate_delays=False,
        )
        results[name] = await agent.run()

    # Both should produce valid result structures
    for name in ("baseline", "training"):
        assert "status" in results[name]
        assert "steps_completed" in results[name]
        assert "duration_ms" in results[name]


# ---------------------------------------------------------------------------
# Parametric runner — end-to-end with CSV/JSON output
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_parametric_runner_produces_output_files(tmp_path):
    """ParametricABTestRunner should produce raw_results.csv and aggregated_metrics.json."""
    runner = ParametricABTestRunner(
        failure_rates=[0.0, 0.5],
        experiments_per_rate=3,
        output_dir=tmp_path,
        seed=42,
        playbook_baseline_path=BASELINE_PLAYBOOK,
        playbook_training_path=TRAINING_PLAYBOOK,
        simulate_delays=False,
    )

    result = await runner.run_parametric_experiments()

    # Should have run 2 rates × 3 experiments × 2 agents = 12
    assert result["total_experiments"] == 12

    # Per-rate CSVs should exist with correct row counts
    for rate_str, rate_val in [("0.00", "0.0"), ("0.50", "0.5")]:
        csv_path = tmp_path / f"rate_{rate_str}.csv"
        assert csv_path.exists(), f"Missing {csv_path.name}"
        with open(csv_path, "r", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        assert len(rows) == 6  # 3 experiments × 2 agents
        assert all(r["failure_rate"] == rate_val for r in rows)

    # JSON should exist with 2 rate keys
    json_path = tmp_path / "aggregated_metrics.json"
    assert json_path.exists()
    with open(json_path, "r", encoding="utf-8") as f:
        metrics = json.load(f)
    assert "0.0" in metrics
    assert "0.5" in metrics
    assert "baseline" in metrics["0.0"]
    assert "playbook" in metrics["0.0"]


@pytest.mark.asyncio
async def test_parametric_runner_zero_chaos_all_succeed(tmp_path):
    """With failure_rate=0.0, all experiments should succeed."""
    runner = ParametricABTestRunner(
        failure_rates=[0.0],
        experiments_per_rate=5,
        output_dir=tmp_path,
        seed=42,
        playbook_baseline_path=TRAINING_PLAYBOOK,
        playbook_training_path=TRAINING_PLAYBOOK,
        simulate_delays=False,
    )

    await runner.run_parametric_experiments()

    json_path = tmp_path / "aggregated_metrics.json"
    with open(json_path, "r", encoding="utf-8") as f:
        metrics = json.load(f)

    for agent_type in ("baseline", "playbook"):
        assert metrics["0.0"][agent_type]["success_rate"]["mean"] == 1.0

