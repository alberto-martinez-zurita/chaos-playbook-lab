"""Output formatters for metrics summaries."""
from __future__ import annotations

import json
import logging
from typing import Any, Dict

logger = logging.getLogger(__name__)


def export_summary_json(
    comparison: Dict[str, Any],
    filename: str = "metrics_summary.json",
) -> None:
    """Export comparison summary to JSON file."""
    with open(filename, "w") as f:
        json.dump(comparison, f, indent=2)


def print_summary(comparison: Dict[str, Any]) -> None:
    """Print human-readable A/B test summary to log."""
    baseline = comparison["baseline"]
    playbook = comparison["playbook"]
    improvements = comparison["improvements"]
    validation = comparison["validation"]

    lines = [
        "",
        "=" * 60,
        "A/B TEST RESULTS SUMMARY",
        "=" * 60,
        "",
        "BASELINE AGENT:",
        f"  Success Rate: {baseline['success_rate']['mean']:.2%} ± {baseline['success_rate']['std']:.4f}",
        f"  Consistency Rate: {baseline['consistency']['consistency_rate']:.2%}",
        f"  Mean Latency: {baseline['latency']['mean_latency_s']:.2f}s",
        "",
        "PLAYBOOK AGENT:",
        f"  Success Rate: {playbook['success_rate']['mean']:.2%} ± {playbook['success_rate']['std']:.4f}",
        f"  Consistency Rate: {playbook['consistency']['consistency_rate']:.2%}",
        f"  Mean Latency: {playbook['latency']['mean_latency_s']:.2f}s",
        f"  Strategies Used: {playbook['unique_strategies_used']} unique, {playbook['total_strategy_uses']} total",
        "",
        "IMPROVEMENTS:",
        f"  Success Rate: +{improvements['success_rate_improvement_pct']:.2f}%",
        f"  Consistency: +{improvements['consistency_improvement_pct']:.2f}%",
        f"  Latency Overhead: +{improvements['latency_overhead_pct']:.2f}%",
        "",
        "SUCCESS CRITERIA:",
        f"  Metric-001 (Success +20%): {'PASS' if validation['metric_001_success_rate_20pct'] else 'FAIL'}",
        f"  Metric-002 (Consistency >=baseline): {'PASS' if validation['metric_002_consistency_maintained'] else 'FAIL'}",
        f"  Metric-003 (Latency <200%): {'PASS' if validation['metric_003_latency_200pct'] else 'FAIL'}",
        "=" * 60,
    ]
    logger.info("\n".join(lines))
