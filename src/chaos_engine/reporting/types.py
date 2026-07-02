"""Data models for metrics aggregation."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List


@dataclass
class ExperimentResult:
    """Result of a single chaos experiment.

    Defined locally to avoid circular dependencies with simulation modules.
    """

    outcome: str
    total_duration_s: float
    inconsistencies: List[str] = field(default_factory=list)
    playbook_strategies_used: List[str] = field(default_factory=list)


@dataclass
class MetricsSummary:
    """Summary statistics for a set of experiments."""

    mean: float
    std: float
    confidence_interval_95: tuple
    sample_size: int
