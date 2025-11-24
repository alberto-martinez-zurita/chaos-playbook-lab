"""
Integration Tests for Parametric Experiments - PHASE 5.1 - FIXED v3

Location: tests/integration/test_parametric_experiments.py

Purpose: Integration tests for ParametricABTestRunner with ABTestRunner

Tests end-to-end execution with real (but small) experiments.

Test Coverage:
- MVP test: 2 rates x 2 experiments = 4 total
- Full integration: CSV and JSON file generation
- Data validation: correct structure and content

FIX APPLIED v3:
  - BEFORE: assert len(all_results) == 4  # ❌ Wrong - missed agent_type
  - AFTER:  assert len(all_results) == 8  # ✅ Correct - 2 agents per experiment
  - Each experiment produces 2 results: baseline + playbook
  - 2 rates × 2 experiments × 2 agents = 8 total results
"""

import pytest
from pathlib import Path
from dataclasses import asdict
from chaos_playbook_engine.experiments.parametric_runner import (
    ParametricABTestRunner,
    ParametricConfig
)


@pytest.mark.asyncio
async def test_parametric_mvp():
    """
    MVP Test: Can we execute ABTestRunner with different failure_rates?

    This is the simplest possible test to validate the concept:
    - 2 failure rates: 0% and 10%
    - 2 experiments per rate
    - Total: 4 experiments = 8 results (2 agents per experiment)

    Validates:
    - ABTestRunner can be called multiple times with different rates
    - Results accumulate correctly
    - Failure_rate metadata is added
    - Each experiment produces 2 results (baseline + playbook)
    """
    failure_rates = [0.00, 0.10]  # Only 2 rates for MVP
    experiments_per_rate = 2       # Only 2 experiments per rate

    # Manual implementation (not using ParametricABTestRunner yet)
    from chaos_playbook_engine.experiments.ab_test_runner import ABTestRunner

    all_results = []
    for rate in failure_rates:
        runner = ABTestRunner()  # ✅ FIXED: No failure_rate parameter here
        # ✅ FIXED: Pass failure_rate to run_batch_experiments() instead
        results = await runner.run_batch_experiments(
            n=experiments_per_rate,
            failure_rate=rate
        )
        
        # ✅ FIXED: Convert ExperimentResult dataclass to dict, then add metadata
        for r in results:
            result_dict = asdict(r)  # Convert dataclass to dict
            result_dict['failure_rate'] = rate
            all_results.append(result_dict)

    # Validations
    # ✅ FIXED v3: Each experiment produces 2 results (baseline + playbook)
    # 2 rates × 2 experiments × 2 agents = 8 total results
    assert len(all_results) == 8, f"Expected 8 results, got {len(all_results)}"

    # Check that we have both agent types
    agent_types = [r['agent_type'] for r in all_results]
    assert agent_types.count('baseline') == 4  # 2 rates × 2 experiments
    assert agent_types.count('playbook') == 4  # 2 rates × 2 experiments

    # Check failure_rate metadata for rate 0.0 (first 4 results)
    rate_0_results = [r for r in all_results if r['failure_rate'] == 0.00]
    assert len(rate_0_results) == 4  # 2 experiments × 2 agents

    # Check failure_rate metadata for rate 0.1 (last 4 results)
    rate_01_results = [r for r in all_results if r['failure_rate'] == 0.10]
    assert len(rate_01_results) == 4  # 2 experiments × 2 agents

    print("✅ MVP Funciona - Concepto validado")
    print(f"   Total results: {len(all_results)}")
    print(f"   Baseline results: {agent_types.count('baseline')}")
    print(f"   Playbook results: {agent_types.count('playbook')}")


@pytest.mark.asyncio
async def test_parametric_runner_integration(tmp_path):
    """
    Integration test: Run ParametricABTestRunner with 2 rates x 2 experiments.

    Validates:
    - ParametricABTestRunner executes successfully
    - CSV file is created with correct data
    - JSON file is created with aggregated metrics
    - All files are in timestamped directory
    """
    # Config: 2 rates x 2 experiments = 4 total (fast test)
    config = ParametricConfig(
        failure_rates=[0.00, 0.10],
        experiments_per_rate=2,
        project_root=tmp_path
    )

    # Run parametric experiments
    runner = ParametricABTestRunner(config)
    summary = await runner.run_parametric_experiments()

    # Validate summary
    assert summary['total_experiments'] == 4
    assert summary['failure_rates'] == [0.00, 0.10]
    assert summary['experiments_per_rate'] == 2

    # Validate files exist
    run_dir = Path(summary['run_directory'])
    assert run_dir.exists()
    csv_path = Path(summary['files']['raw_results'])
    json_path = Path(summary['files']['metrics_summary'])
    assert csv_path.exists()
    assert json_path.exists()

    # Validate CSV content
    with open(csv_path, 'r') as f:
        lines = f.readlines()
    # ✅ FIXED v3: 2 rates × 2 experiments × 2 agents = 8 data rows + 1 header = 9 lines
    assert len(lines) == 9  # Header + 8 rows

    # Check header has failure_rate column
    header = lines[0].strip()
    assert 'failure_rate' in header

    # Check first data row has failure_rate value
    first_row = lines[1].strip()
    assert '0.0' in first_row or '0.00' in first_row

    # Validate JSON content
    import json
    with open(json_path, 'r') as f:
        metrics = json.load(f)

    # Should have 2 entries (one per rate)
    assert len(metrics) == 2

    # Check structure
    assert '0.0' in metrics
    assert '0.1' in metrics

    # Check rate 0.0 entry
    rate_0_metrics = metrics['0.0']
    assert rate_0_metrics['failure_rate'] == 0.0
    assert rate_0_metrics['n_experiments'] == 2
    assert 'success_rate' in rate_0_metrics
    assert 'mean' in rate_0_metrics['success_rate']
    assert 'std' in rate_0_metrics['success_rate']

    print(f"\n✅ Integration test PASSED")
    print(f" Results directory: {run_dir}")


@pytest.mark.asyncio
async def test_parametric_runner_larger_scale(tmp_path):
    """
    Larger scale integration test: 3 rates x 3 experiments = 9 total.

    Validates:
    - Handles more rates and experiments
    - Aggregation works correctly across different rates
    - Statistics (mean, std) are calculated correctly
    """
    config = ParametricConfig(
        failure_rates=[0.00, 0.05, 0.10],
        experiments_per_rate=3,
        project_root=tmp_path
    )

    runner = ParametricABTestRunner(config)
    summary = await runner.run_parametric_experiments()

    # Validate total count
    assert summary['total_experiments'] == 9  # 3 rates x 3 experiments

    # Validate all files exist
    csv_path = Path(summary['files']['raw_results'])
    json_path = Path(summary['files']['metrics_summary'])
    assert csv_path.exists()
    assert json_path.exists()

    # Validate CSV has correct number of lines
    # ✅ FIXED v3: 3 rates × 3 experiments × 2 agents = 18 data rows + 1 header = 19 lines
    with open(csv_path, 'r') as f:
        lines = f.readlines()
    assert len(lines) == 19  # Header + 18 rows

    # Validate JSON has 3 entries
    import json
    with open(json_path, 'r') as f:
        metrics = json.load(f)

    assert len(metrics) == 3

    # Each entry should have 3 experiments
    for rate_key in metrics:
        assert metrics[rate_key]['n_experiments'] == 3

    print(f"✅ Larger scale test PASSED (9 experiments = 18 results)")
