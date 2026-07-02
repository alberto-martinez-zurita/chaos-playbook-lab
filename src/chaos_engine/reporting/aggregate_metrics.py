"""Backward-compatible re-exports for aggregate_metrics.

New code should import from the split modules directly:
- ``chaos_engine.reporting.types`` — ExperimentResult, MetricsSummary
- ``chaos_engine.reporting.aggregator`` — MetricsAggregator
- ``chaos_engine.reporting.formatters`` — export_summary_json, print_summary
"""
from __future__ import annotations

from chaos_engine.reporting.aggregator import MetricsAggregator
from chaos_engine.reporting.formatters import export_summary_json, print_summary
from chaos_engine.reporting.types import ExperimentResult, MetricsSummary

__all__ = [
    "ExperimentResult",
    "MetricsSummary",
    "MetricsAggregator",
    "export_summary_json",
    "print_summary",
]
