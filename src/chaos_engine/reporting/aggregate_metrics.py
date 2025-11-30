"""
Metrics Aggregator for A/B Test Results - v4.0 (Consistency-First Design)

Location: experiments/aggregate_metrics.py

Purpose: Calculate and compare metrics between Baseline and Playbook agents.

V4 CHANGES:
- Migrated from "Inconsistency Reduction" to "Consistency Improvement" 
- More intuitive metric direction (all improvements are positive increases)
- Mathematically equivalent validation logic
- All existing tests remain compatible (consistency = 1 - inconsistency)

Rationale:
With consistency metric, ALL KPIs move in same direction:
- Success Rate: ↑ better
- Consistency Rate: ↑ better  
- Latency: managed overhead

Usage:
    aggregator = MetricsAggregator()
    baseline_metrics = aggregator.calculate_success_rate(baseline_results)
    playbook_metrics = aggregator.calculate_success_rate(playbook_results)
    comparison = aggregator.compare_baseline_vs_playbook(baseline_results, playbook_results)
    aggregator.export_summary_json(comparison, "metrics_summary.json")
"""

import json
import math
from typing import Any, Dict, List
from dataclasses import dataclass, field

@dataclass
class ExperimentResult:
    """
    Estructura de datos para representar el resultado de un experimento.
    Definida localmente para evitar dependencias circulares o rutas rotas.
    """
    outcome: str
    total_duration_s: float
    inconsistencies: List[str] = field(default_factory=list)
    playbook_strategies_used: List[str] = field(default_factory=list)

# -------------------------------------------------------------------------
@dataclass
class MetricsSummary:
    """Summary statistics for a set of experiments."""
    mean: float
    std: float
    confidence_interval_95: tuple
    sample_size: int


class MetricsAggregator:
    """
    Aggregate and analyze A/B test results.

    Calculates:
    - Success rates with confidence intervals
    - Consistency rates (NEW: inverse of inconsistency)
    - Latency statistics
    - Comparative improvements
    """

    def calculate_success_rate(
        self,
        results: List[ExperimentResult]
    ) -> Dict[str, Any]:
        """
        Calculate success rate with confidence intervals.

        Args:
            results: List of ExperimentResult

        Returns:
            {
                "mean": 0.85,
                "std": 0.357,
                "confidence_interval_95": (0.78, 0.92),
                "sample_size": 50,
                "successes": 42,
                "failures": 5,
                "inconsistent": 3
            }
        """
        if not results:
            return {
                "mean": 0.0,
                "std": 0.0,
                "confidence_interval_95": (0.0, 0.0),
                "sample_size": 0,
                "successes": 0,
                "failures": 0,
                "inconsistent": 0
            }

        # Count outcomes
        successes = sum(1 for r in results if r.outcome == "success")
        failures = sum(1 for r in results if r.outcome == "failure")
        inconsistent = sum(1 for r in results if r.outcome == "inconsistent")

        n = len(results)
        success_rate = successes / n if n > 0 else 0.0

        # Calculate standard deviation (for binomial: sqrt(p(1-p)/n))
        std = math.sqrt(success_rate * (1 - success_rate) / n) if n > 0 else 0.0

        # Calculate 95% confidence interval (z=1.96 for 95% CI)
        margin = 1.96 * std
        ci_lower = max(0.0, success_rate - margin)
        ci_upper = min(1.0, success_rate + margin)

        return {
            "mean": round(success_rate, 4),
            "std": round(std, 4),
            "confidence_interval_95": (round(ci_lower, 4), round(ci_upper, 4)),
            "sample_size": n,
            "successes": successes,
            "failures": failures,
            "inconsistent": inconsistent
        }

    def calculate_consistency_rate(
        self,
        results: List[ExperimentResult]
    ) -> Dict[str, Any]:
        """
        Calculate consistency rate (NEW: inverse of inconsistency).

        Consistency = transactions WITHOUT inconsistent states.
        This metric is MORE INTUITIVE than inconsistency because:
        - Higher is better (aligns with success rate direction)
        - Positive framing ("maintain consistency" vs "reduce inconsistency")

        Args:
            results: List of ExperimentResult

        Returns:
            {
                "consistency_rate": 0.94,  # 1 - inconsistency_rate
                "inconsistency_rate": 0.06,  # For backward compat
                "consistent_count": 47,
                "inconsistent_count": 3,
                "sample_size": 50,
                "inconsistency_types": {
                    "payment_without_order": 2,
                    "order_without_payment": 1
                }
            }
        """
        if not results:
            return {
                "consistency_rate": 0.0,
                "inconsistency_rate": 0.0,
                "consistent_count": 0,
                "inconsistent_count": 0,
                "sample_size": 0,
                "inconsistency_types": {}
            }

        n = len(results)
        inconsistent_count = sum(1 for r in results if r.outcome == "inconsistent")
        consistent_count = n - inconsistent_count

        inconsistency_rate = inconsistent_count / n if n > 0 else 0.0
        consistency_rate = 1.0 - inconsistency_rate  # NEW: Positive metric

        # Count inconsistency types (for debugging)
        inconsistency_types = {}
        for result in results:
            for inc_type in result.inconsistencies:
                inconsistency_types[inc_type] = inconsistency_types.get(inc_type, 0) + 1

        return {
            "consistency_rate": round(consistency_rate, 4),  # NEW: Primary metric
            "inconsistency_rate": round(inconsistency_rate, 4),  # Keep for backward compat
            "consistent_count": consistent_count,
            "inconsistent_count": inconsistent_count,
            "sample_size": n,
            "inconsistency_types": inconsistency_types
        }

    def calculate_latency_stats(
        self,
        results: List[ExperimentResult]
    ) -> Dict[str, Any]:
        """
        Calculate latency statistics.

        Args:
            results: List of ExperimentResult

        Returns:
            {
                "mean_latency_s": 5.2,
                "median_latency_s": 4.8,
                "p95_latency_s": 8.5,
                "p99_latency_s": 12.1,
                "min_latency_s": 2.1,
                "max_latency_s": 15.3,
                "std_latency_s": 2.4
            }
        """
        if not results:
            return {
                "mean_latency_s": 0.0,
                "median_latency_s": 0.0,
                "p95_latency_s": 0.0,
                "p99_latency_s": 0.0,
                "min_latency_s": 0.0,
                "max_latency_s": 0.0,
                "std_latency_s": 0.0
            }

        durations = [r.total_duration_s for r in results]
        durations_sorted = sorted(durations)
        n = len(durations)

        # Mean
        mean_latency = sum(durations) / n

        # Median
        if n % 2 == 0:
            median_latency = (durations_sorted[n//2 - 1] + durations_sorted[n//2]) / 2
        else:
            median_latency = durations_sorted[n//2]

        # Percentiles
        p95_index = int(n * 0.95)
        p99_index = int(n * 0.99)
        p95_latency = durations_sorted[p95_index] if p95_index < n else durations_sorted[-1]
        p99_latency = durations_sorted[p99_index] if p99_index < n else durations_sorted[-1]

        # Min/Max
        min_latency = durations_sorted[0]
        max_latency = durations_sorted[-1]

        # Standard deviation
        variance = sum((d - mean_latency) ** 2 for d in durations) / n
        std_latency = math.sqrt(variance)

        return {
            "mean_latency_s": round(mean_latency, 2),
            "median_latency_s": round(median_latency, 2),
            "p95_latency_s": round(p95_latency, 2),
            "p99_latency_s": round(p99_latency, 2),
            "min_latency_s": round(min_latency, 2),
            "max_latency_s": round(max_latency, 2),
            "std_latency_s": round(std_latency, 2)
        }

    def compare_baseline_vs_playbook(
        self,
        baseline_results: List[ExperimentResult],
        playbook_results: List[ExperimentResult]
    ) -> Dict[str, Any]:
        """
        Compare Baseline vs Playbook performance.

        Args:
            baseline_results: Baseline experiment results
            playbook_results: Playbook experiment results

        Returns:
            {
                "baseline": {...},
                "playbook": {...},
                "improvements": {
                    "success_rate_improvement": 0.23,
                    "consistency_improvement": 0.05,  # NEW: Positive metric
                    "latency_overhead_pct": 67.5
                },
                "validation": {
                    "metric_001_success_rate_20pct": True/False,
                    "metric_002_consistency_maintained": True/False,  # NEW
                    "metric_003_latency_200pct": True/False
                }
            }
        """
        # Calculate metrics for each
        baseline_success = self.calculate_success_rate(baseline_results)
        playbook_success = self.calculate_success_rate(playbook_results)

        baseline_consistency = self.calculate_consistency_rate(baseline_results)  # NEW
        playbook_consistency = self.calculate_consistency_rate(playbook_results)  # NEW

        baseline_latency = self.calculate_latency_stats(baseline_results)
        playbook_latency = self.calculate_latency_stats(playbook_results)

        # Extract values
        baseline_sr = baseline_success["mean"]
        playbook_sr = playbook_success["mean"]

        baseline_cr = baseline_consistency["consistency_rate"]  # NEW
        playbook_cr = playbook_consistency["consistency_rate"]  # NEW

        baseline_lat = baseline_latency["mean_latency_s"]
        playbook_lat = playbook_latency["mean_latency_s"]

        # ============ SUCCESS RATE IMPROVEMENT ============
        if baseline_sr > 0:
            success_rate_improvement = (playbook_sr - baseline_sr) / baseline_sr
        else:
            # If baseline = 0%, absolute difference is the improvement
            success_rate_improvement = playbook_sr - baseline_sr

        # ============ CONSISTENCY IMPROVEMENT (NEW) ============
        # Positive metric: higher consistency = better
        # Mathematically equivalent to inconsistency reduction but MORE INTUITIVE
        if baseline_cr < 1.0:  # If baseline has room for improvement
            # Calculate relative improvement in consistency
            consistency_improvement = (playbook_cr - baseline_cr) / (1.0 - baseline_cr)
        else:
            # Baseline is already 100% consistent
            # Playbook MUST maintain it
            consistency_improvement = playbook_cr - baseline_cr  # 1.0 - 1.0 = 0 (NEUTRAL)

        # ============ LATENCY OVERHEAD ============
        if baseline_lat > 0:
            latency_overhead_pct = ((playbook_lat - baseline_lat) / baseline_lat * 100)
        else:
            latency_overhead_pct = 0.0  # Can't calculate without baseline latency

        # Count Playbook strategies used
        strategies_used = []
        for result in playbook_results:
            strategies_used.extend(result.playbook_strategies_used)
        unique_strategies = len(set(strategies_used))

        # ============ VALIDATION CRITERIA ============
        # Metric-001: Success rate must improve by ≥20%
        metric_001_pass = success_rate_improvement >= 0.20

        # Metric-002: Consistency must be maintained or improved (NEW)
        # Simpler logic: playbook consistency >= baseline consistency
        metric_002_pass = playbook_cr >= baseline_cr

        # Metric-003: Latency overhead must be ≤200%
        metric_003_pass = latency_overhead_pct <= 200.0

        return {
            "baseline": {
                "success_rate": baseline_success,
                "consistency": baseline_consistency,  # NEW key name
                "latency": baseline_latency
            },
            "playbook": {
                "success_rate": playbook_success,
                "consistency": playbook_consistency,  # NEW key name
                "latency": playbook_latency,
                "unique_strategies_used": unique_strategies,
                "total_strategy_uses": len(strategies_used)
            },
            "improvements": {
                "success_rate_improvement": round(success_rate_improvement, 4),
                "success_rate_improvement_pct": round(success_rate_improvement * 100, 2),
                "consistency_improvement": round(consistency_improvement, 4),  # NEW
                "consistency_improvement_pct": round(consistency_improvement * 100, 2),  # NEW
                "latency_overhead_pct": round(latency_overhead_pct, 2)
            },
            "validation": {
                "metric_001_success_rate_20pct": metric_001_pass,
                "metric_002_consistency_maintained": metric_002_pass,  # NEW name
                "metric_003_latency_200pct": metric_003_pass
            }
        }

    def export_summary_json(
        self,
        comparison: Dict[str, Any],
        filename: str = "metrics_summary.json"
    ):
        """
        Export comparison summary to JSON file.

        Args:
            comparison: Result from compare_baseline_vs_playbook()
            filename: Output JSON filename
        """
        with open(filename, 'w') as f:
            json.dump(comparison, f, indent=2)

    def print_summary(
        self,
        comparison: Dict[str, Any]
    ):
        """
        Print human-readable summary to console.

        Args:
            comparison: Result from compare_baseline_vs_playbook()
        """
        print("\n" + "="*60)
        print("A/B TEST RESULTS SUMMARY")
        print("="*60)

        # Baseline metrics
        baseline = comparison["baseline"]
        print(f"\nBASELINE AGENT:")
        print(f"  Success Rate: {baseline['success_rate']['mean']:.2%} ± {baseline['success_rate']['std']:.4f}")
        print(f"  Consistency Rate: {baseline['consistency']['consistency_rate']:.2%}")  # NEW
        print(f"  Mean Latency: {baseline['latency']['mean_latency_s']:.2f}s")

        # Playbook metrics
        playbook = comparison["playbook"]
        print(f"\nPLAYBOOK AGENT:")
        print(f"  Success Rate: {playbook['success_rate']['mean']:.2%} ± {playbook['success_rate']['std']:.4f}")
        print(f"  Consistency Rate: {playbook['consistency']['consistency_rate']:.2%}")  # NEW
        print(f"  Mean Latency: {playbook['latency']['mean_latency_s']:.2f}s")
        print(f"  Strategies Used: {playbook['unique_strategies_used']} unique, {playbook['total_strategy_uses']} total")

        # Improvements
        improvements = comparison["improvements"]
        print(f"\nIMPROVEMENTS:")
        print(f"  Success Rate: +{improvements['success_rate_improvement_pct']:.2f}%")
        print(f"  Consistency: +{improvements['consistency_improvement_pct']:.2f}%")  # NEW
        print(f"  Latency Overhead: +{improvements['latency_overhead_pct']:.2f}%")

        # Validation
        validation = comparison["validation"]
        print(f"\nSUCCESS CRITERIA:")
        print(f"  Metric-001 (Success +20%): {'✓ PASS' if validation['metric_001_success_rate_20pct'] else '✗ FAIL'}")
        print(f"  Metric-002 (Consistency ≥baseline): {'✓ PASS' if validation['metric_002_consistency_maintained'] else '✗ FAIL'}")  # NEW
        print(f"  Metric-003 (Latency <200%): {'✓ PASS' if validation['metric_003_latency_200pct'] else '✗ FAIL'}")
        print("="*60 + "\n")
