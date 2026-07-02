"""Metrics Aggregator — core calculation and comparison logic.

Calculates success rates, consistency rates, latency statistics,
and comparative improvements between baseline and playbook agents.
"""
from __future__ import annotations

import math
from typing import Any, Dict, List

from chaos_engine.reporting.types import ExperimentResult


class MetricsAggregator:
    """Aggregate and analyze A/B test results.

    Calculates:
    - Success rates with confidence intervals
    - Consistency rates (inverse of inconsistency)
    - Latency statistics (mean, median, p95, p99)
    - Comparative improvements with validation criteria
    """

    def calculate_success_rate(
        self,
        results: List[ExperimentResult],
    ) -> Dict[str, Any]:
        """Calculate success rate with 95% confidence intervals.

        Returns dict with mean, std, confidence_interval_95, sample_size,
        successes, failures, inconsistent counts.
        """
        if not results:
            return {
                "mean": 0.0, "std": 0.0,
                "confidence_interval_95": (0.0, 0.0),
                "sample_size": 0, "successes": 0,
                "failures": 0, "inconsistent": 0,
            }

        successes = sum(1 for r in results if r.outcome == "success")
        failures = sum(1 for r in results if r.outcome == "failure")
        inconsistent = sum(1 for r in results if r.inconsistencies)

        n = len(results)
        success_rate = successes / n if n > 0 else 0.0

        std = math.sqrt(success_rate * (1 - success_rate) / n) if n > 0 else 0.0

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
            "inconsistent": inconsistent,
        }

    def calculate_consistency_rate(
        self,
        results: List[ExperimentResult],
    ) -> Dict[str, Any]:
        """Calculate consistency rate (1 - inconsistency_rate).

        Higher is better — aligns with success rate direction.
        """
        if not results:
            return {
                "consistency_rate": 0.0, "inconsistency_rate": 0.0,
                "consistent_count": 0, "inconsistent_count": 0,
                "sample_size": 0, "inconsistency_types": {},
            }

        n = len(results)
        inconsistent_count = sum(1 for r in results if r.inconsistencies)
        consistent_count = n - inconsistent_count

        inconsistency_rate = inconsistent_count / n if n > 0 else 0.0
        consistency_rate = 1.0 - inconsistency_rate

        inconsistency_types: Dict[str, int] = {}
        for result in results:
            for inc_type in result.inconsistencies:
                inconsistency_types[inc_type] = inconsistency_types.get(inc_type, 0) + 1

        return {
            "consistency_rate": round(consistency_rate, 4),
            "inconsistency_rate": round(inconsistency_rate, 4),
            "consistent_count": consistent_count,
            "inconsistent_count": inconsistent_count,
            "sample_size": n,
            "inconsistency_types": inconsistency_types,
        }

    def calculate_latency_stats(
        self,
        results: List[ExperimentResult],
    ) -> Dict[str, Any]:
        """Calculate latency statistics (mean, median, p95, p99, min, max, std)."""
        if not results:
            return {
                "mean_latency_s": 0.0, "median_latency_s": 0.0,
                "p95_latency_s": 0.0, "p99_latency_s": 0.0,
                "min_latency_s": 0.0, "max_latency_s": 0.0,
                "std_latency_s": 0.0,
            }

        durations = [r.total_duration_s for r in results]
        durations_sorted = sorted(durations)
        n = len(durations)

        mean_latency = sum(durations) / n

        if n % 2 == 0:
            median_latency = (durations_sorted[n // 2 - 1] + durations_sorted[n // 2]) / 2
        else:
            median_latency = durations_sorted[n // 2]

        p95_index = int(n * 0.95)
        p99_index = int(n * 0.99)
        p95_latency = durations_sorted[p95_index] if p95_index < n else durations_sorted[-1]
        p99_latency = durations_sorted[p99_index] if p99_index < n else durations_sorted[-1]

        min_latency = durations_sorted[0]
        max_latency = durations_sorted[-1]

        variance = sum((d - mean_latency) ** 2 for d in durations) / n
        std_latency = math.sqrt(variance)

        return {
            "mean_latency_s": round(mean_latency, 2),
            "median_latency_s": round(median_latency, 2),
            "p95_latency_s": round(p95_latency, 2),
            "p99_latency_s": round(p99_latency, 2),
            "min_latency_s": round(min_latency, 2),
            "max_latency_s": round(max_latency, 2),
            "std_latency_s": round(std_latency, 2),
        }

    def compare_baseline_vs_playbook(
        self,
        baseline_results: List[ExperimentResult],
        playbook_results: List[ExperimentResult],
    ) -> Dict[str, Any]:
        """Compare baseline vs playbook performance.

        Returns metrics for both agents, improvements, and validation criteria:
        - Metric-001: Success rate improvement >= 20%
        - Metric-002: Consistency >= baseline
        - Metric-003: Latency overhead <= 200%
        """
        baseline_success = self.calculate_success_rate(baseline_results)
        playbook_success = self.calculate_success_rate(playbook_results)

        baseline_consistency = self.calculate_consistency_rate(baseline_results)
        playbook_consistency = self.calculate_consistency_rate(playbook_results)

        baseline_latency = self.calculate_latency_stats(baseline_results)
        playbook_latency = self.calculate_latency_stats(playbook_results)

        baseline_sr = baseline_success["mean"]
        playbook_sr = playbook_success["mean"]

        baseline_cr = baseline_consistency["consistency_rate"]
        playbook_cr = playbook_consistency["consistency_rate"]

        baseline_lat = baseline_latency["mean_latency_s"]
        playbook_lat = playbook_latency["mean_latency_s"]

        # Success rate improvement
        if baseline_sr > 0:
            success_rate_improvement = (playbook_sr - baseline_sr) / baseline_sr
        else:
            success_rate_improvement = playbook_sr - baseline_sr

        # Consistency improvement
        if baseline_cr < 1.0:
            consistency_improvement = (playbook_cr - baseline_cr) / (1.0 - baseline_cr)
        else:
            consistency_improvement = playbook_cr - baseline_cr

        # Latency overhead
        if baseline_lat > 0:
            latency_overhead_pct = (playbook_lat - baseline_lat) / baseline_lat * 100
        else:
            latency_overhead_pct = 0.0

        # Strategies used
        strategies_used = []
        for result in playbook_results:
            strategies_used.extend(result.playbook_strategies_used)
        unique_strategies = len(set(strategies_used))

        # Validation criteria
        metric_001_pass = success_rate_improvement >= 0.20
        metric_002_pass = playbook_cr >= baseline_cr
        metric_003_pass = latency_overhead_pct <= 200.0

        return {
            "baseline": {
                "success_rate": baseline_success,
                "consistency": baseline_consistency,
                "latency": baseline_latency,
            },
            "playbook": {
                "success_rate": playbook_success,
                "consistency": playbook_consistency,
                "latency": playbook_latency,
                "unique_strategies_used": unique_strategies,
                "total_strategy_uses": len(strategies_used),
            },
            "improvements": {
                "success_rate_improvement": round(success_rate_improvement, 4),
                "success_rate_improvement_pct": round(success_rate_improvement * 100, 2),
                "consistency_improvement": round(consistency_improvement, 4),
                "consistency_improvement_pct": round(consistency_improvement * 100, 2),
                "latency_overhead_pct": round(latency_overhead_pct, 2),
            },
            "validation": {
                "metric_001_success_rate_20pct": metric_001_pass,
                "metric_002_consistency_maintained": metric_002_pass,
                "metric_003_latency_200pct": metric_003_pass,
            },
        }
