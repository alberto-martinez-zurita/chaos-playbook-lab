"""
Test Suite for Aggregate Metrics (v4.0 - Consistency-First) - FIXED IMPORTS

Location: tests/experiments/test_aggregate_metrics.py

Purpose: Validate MetricsAggregator functionality with CORRECT ExperimentResult structure:
- chaos_config: Dict[str, Any]
- api_calls: List[Dict[str, Any]]

ONLY CHANGES FROM ORIGINAL:
1. Line 21: Fixed import to use chaos_playbook_engine.experiments
2. Line 256: Changed 'success' to 'success_rate' (actual key in return dict)
3. Line 310: Changed 'metric_001_success_improvement' to 'metric_001_success_rate_20pct' (actual key)

Run:
poetry run pytest tests/experiments/test_aggregate_metrics.py -v
"""

import pytest
from typing import List, Dict, Any
from chaos_playbook_engine.experiments.aggregate_metrics import MetricsAggregator
from chaos_playbook_engine.experiments.ab_test_runner import ExperimentResult

# ============================================================================
# FIXTURES
# ============================================================================

def create_experiment_result(
    experiment_id: str,
    agent_type: str,
    outcome: str,
    total_duration_s: float,
    inconsistencies: List[str] = None,
    playbook_strategies_used: List[str] = None,
    seed: int = 42
) -> ExperimentResult:
    """Helper to create ExperimentResult with all required fields."""
    return ExperimentResult(
        experiment_id=experiment_id,
        agent_type=agent_type,
        chaos_config={
            "failure_rate": 0.3,
            "seed": seed,
            "max_delay": 2.0
        },
        outcome=outcome,
        total_duration_s=total_duration_s,
        api_calls=[
            {
                "api": "inventory",
                "status": "success" if outcome == "success" else "failure",
                "duration": 0.5
            }
        ],
        playbook_strategies_used=playbook_strategies_used or [],
        inconsistencies=inconsistencies or []
    )

@pytest.fixture
def sample_baseline_results() -> List[ExperimentResult]:
    """
    Baseline results: 70% success, 0% inconsistency, ~4s latency.
    Simulates simple agent without retries:
    - Lower success rate
    - No inconsistencies (fails fast)
    - Lower latency
    """
    results = []
    # 70 successes
    for i in range(70):
        results.append(create_experiment_result(
            experiment_id=f"baseline_{i:03d}",
            agent_type="baseline",
            outcome="success",
            total_duration_s=4.0 + (i % 10) * 0.1,  # 4.0-4.9s
            seed=42 + i
        ))
    # 30 failures
    for i in range(30):
        results.append(create_experiment_result(
            experiment_id=f"baseline_{i+70:03d}",
            agent_type="baseline",
            outcome="failure",
            total_duration_s=4.0 + (i % 10) * 0.1,
            seed=42 + i + 70
        ))
    return results

@pytest.fixture
def sample_playbook_results() -> List[ExperimentResult]:
    """
    Playbook results: 98% success, 0% inconsistency, ~6.7s latency.
    Simulates sophisticated agent with retries:
    - Higher success rate
    - No inconsistencies (maintains consistency)
    - Higher latency (cost of retries)
    """
    results = []
    # 98 successes (with strategy uses)
    for i in range(98):
        strategies = ["Retry with 0.5s backoff"] if i % 3 == 0 else []
        results.append(create_experiment_result(
            experiment_id=f"playbook_{i:03d}",
            agent_type="playbook",
            outcome="success",
            total_duration_s=6.5 + (i % 10) * 0.1,  # 6.5-7.4s
            playbook_strategies_used=strategies,
            seed=42 + i
        ))
    # 2 failures
    for i in range(2):
        results.append(create_experiment_result(
            experiment_id=f"playbook_{i+98:03d}",
            agent_type="playbook",
            outcome="failure",
            total_duration_s=8.0,
            seed=42 + i + 98
        ))
    return results

@pytest.fixture
def baseline_with_inconsistencies() -> List[ExperimentResult]:
    """Baseline with 10% inconsistency (fails without cleanup)."""
    results = []
    # 70 successes
    for i in range(70):
        results.append(create_experiment_result(
            experiment_id=f"baseline_inc_{i:03d}",
            agent_type="baseline",
            outcome="success",
            total_duration_s=4.0,
            seed=42 + i
        ))
    # 10 inconsistent states
    for i in range(10):
        results.append(create_experiment_result(
            experiment_id=f"baseline_inc_{i+70:03d}",
            agent_type="baseline",
            outcome="inconsistent",
            total_duration_s=4.0,
            inconsistencies=["payment_without_order"],
            seed=42 + i + 70
        ))
    # 20 failures
    for i in range(20):
        results.append(create_experiment_result(
            experiment_id=f"baseline_inc_{i+80:03d}",
            agent_type="baseline",
            outcome="failure",
            total_duration_s=4.0,
            seed=42 + i + 80
        ))
    return results

# ============================================================================
# TESTS
# ============================================================================

class TestMetricsAggregatorSuccess:
    """Test success rate calculation."""
    
    @pytest.fixture
    def aggregator(self):
        return MetricsAggregator()
    
    def test_baseline_success_rate(self, aggregator, sample_baseline_results):
        """Baseline: 70/100 = 70% success rate."""
        metrics = aggregator.calculate_success_rate(sample_baseline_results)
        assert metrics['mean'] == pytest.approx(0.70, rel=0.01)
        assert metrics['sample_size'] == 100
        assert metrics['successes'] == 70
        assert metrics['failures'] == 30
    
    def test_playbook_success_rate(self, aggregator, sample_playbook_results):
        """Playbook: 98/100 = 98% success rate."""
        metrics = aggregator.calculate_success_rate(sample_playbook_results)
        assert metrics['mean'] == pytest.approx(0.98, rel=0.01)
        assert metrics['sample_size'] == 100
        assert metrics['successes'] == 98
        assert metrics['failures'] == 2


class TestMetricsAggregatorConsistency:
    """Test consistency metrics (v4.0 - consistency-first)."""
    
    @pytest.fixture
    def aggregator(self):
        return MetricsAggregator()
    
    def test_baseline_perfect_consistency(self, aggregator, sample_baseline_results):
        """Baseline (no retries): 100% consistency (0 inconsistent states)."""
        metrics = aggregator.calculate_consistency_rate(sample_baseline_results)
        assert metrics['consistency_rate'] == pytest.approx(1.0, rel=0.01)
        assert metrics['inconsistent_count'] == 0
        assert metrics['consistent_count'] == 100
    
    def test_playbook_perfect_consistency(self, aggregator, sample_playbook_results):
        """Playbook: 100% consistency (maintains consistency via strategies)."""
        metrics = aggregator.calculate_consistency_rate(sample_playbook_results)
        assert metrics['consistency_rate'] == pytest.approx(1.0, rel=0.01)
        assert metrics['inconsistent_count'] == 0
        assert metrics['consistent_count'] == 100
    
    def test_baseline_with_inconsistencies(self, aggregator, baseline_with_inconsistencies):
        """Baseline with 10% inconsistency."""
        metrics = aggregator.calculate_consistency_rate(baseline_with_inconsistencies)
        assert metrics['consistency_rate'] == pytest.approx(0.90, rel=0.01)
        assert metrics['inconsistent_count'] == 10
        assert metrics['consistent_count'] == 90
        assert 'inconsistency_types' in metrics
        assert metrics['inconsistency_types']['payment_without_order'] == 10


class TestMetricsAggregatorLatency:
    """Test latency metrics."""
    
    @pytest.fixture
    def aggregator(self):
        return MetricsAggregator()
    
    def test_baseline_latency(self, aggregator, sample_baseline_results):
        """Baseline: ~4.5s avg latency."""
        metrics = aggregator.calculate_latency_stats(sample_baseline_results)
        assert metrics['mean_latency_s'] == pytest.approx(4.45, rel=0.01)
        assert metrics['min_latency_s'] == pytest.approx(4.0, rel=0.01)
        assert metrics['max_latency_s'] == pytest.approx(4.9, rel=0.01)
    
    def test_playbook_latency(self, aggregator, sample_playbook_results):
        """Playbook: ~6.8s avg latency (higher due to retries)."""
        metrics = aggregator.calculate_latency_stats(sample_playbook_results)
        assert metrics['mean_latency_s'] > 6.0  # Higher than baseline
        assert metrics['min_latency_s'] == pytest.approx(6.5, rel=0.01)


class TestMetricsAggregatorComparison:
    """Test baseline vs playbook comparison (INTEGRATION LEVEL)."""
    
    @pytest.fixture
    def aggregator(self):
        return MetricsAggregator()
    
    def test_comparison_structure(self, aggregator, sample_baseline_results, sample_playbook_results):
        """Test comparison output structure."""
        comparison = aggregator.compare_baseline_vs_playbook(
            sample_baseline_results,
            sample_playbook_results
        )
        
        # Check top-level structure
        assert 'baseline' in comparison
        assert 'playbook' in comparison
        assert 'improvements' in comparison
        assert 'validation' in comparison
        
        # Check baseline metrics - FIXED: 'success_rate' not 'success'
        assert 'success_rate' in comparison['baseline']
        assert 'consistency' in comparison['baseline']
        assert 'latency' in comparison['baseline']
        
        # Check playbook metrics
        assert 'success_rate' in comparison['playbook']
        assert 'consistency' in comparison['playbook']
        assert 'latency' in comparison['playbook']
        
        # Check improvements
        assert 'success_rate_improvement' in comparison['improvements']
        assert 'consistency_improvement' in comparison['improvements']
        assert 'latency_overhead_pct' in comparison['improvements']
    
    def test_success_improvement(self, aggregator, sample_baseline_results, sample_playbook_results):
        """Playbook should improve success rate from 70% to 98% (+40%)."""
        comparison = aggregator.compare_baseline_vs_playbook(
            sample_baseline_results,
            sample_playbook_results
        )
        
        # Success rate improvement
        improvement = comparison['improvements']['success_rate_improvement']
        assert improvement == pytest.approx(0.40, rel=0.01)  # +40% (0.98 - 0.70 = 0.28, relative: 0.28/0.70 = 0.40)
    
    def test_consistency_maintained(self, aggregator, sample_baseline_results, sample_playbook_results):
        """Both maintain 100% consistency."""
        comparison = aggregator.compare_baseline_vs_playbook(
            sample_baseline_results,
            sample_playbook_results
        )
        
        assert comparison['baseline']['consistency']['consistency_rate'] == pytest.approx(1.0)
        assert comparison['playbook']['consistency']['consistency_rate'] == pytest.approx(1.0)
    
    def test_latency_overhead(self, aggregator, sample_baseline_results, sample_playbook_results):
        """Playbook should have higher latency than baseline."""
        comparison = aggregator.compare_baseline_vs_playbook(
            sample_baseline_results,
            sample_playbook_results
        )
        
        # Latency overhead should be positive (playbook is slower)
        latency_overhead = comparison['improvements']['latency_overhead_pct']
        assert latency_overhead > 0  # Playbook takes longer
    
    def test_validation_checks(self, aggregator, sample_baseline_results, sample_playbook_results):
        """Test that validation checks are present."""
        comparison = aggregator.compare_baseline_vs_playbook(
            sample_baseline_results,
            sample_playbook_results
        )
        
        # Check validation flags exist - FIXED: correct key names
        assert 'metric_001_success_rate_20pct' in comparison['validation']
        assert 'metric_002_consistency_maintained' in comparison['validation']
        assert 'metric_003_latency_200pct' in comparison['validation']
