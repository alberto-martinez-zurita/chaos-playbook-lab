"""Prometheus metrics for the Chaos Playbook Engine.

Exposes counters, histograms, and gauges that Prometheus scrapes via /metrics.
"""
from __future__ import annotations

from prometheus_client import Counter, Gauge, Histogram, Summary

# ---------------------------------------------------------------------------
# Experiment metrics
# ---------------------------------------------------------------------------

EXPERIMENTS_TOTAL = Counter(
    "chaos_experiments_total",
    "Total experiments executed",
    ["agent_type", "failure_rate"],
)

EXPERIMENTS_SUCCESS = Counter(
    "chaos_experiments_success_total",
    "Successful experiments",
    ["agent_type", "failure_rate"],
)

EXPERIMENTS_FAILED = Counter(
    "chaos_experiments_failed_total",
    "Failed experiments",
    ["agent_type", "failure_rate"],
)

EXPERIMENT_DURATION = Histogram(
    "chaos_experiment_duration_seconds",
    "Experiment duration in seconds",
    ["agent_type"],
    buckets=(0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1.0, 5.0, 10.0),
)

# ---------------------------------------------------------------------------
# Chaos injection metrics
# ---------------------------------------------------------------------------

CHAOS_INJECTIONS = Counter(
    "chaos_injections_total",
    "Total chaos failures injected",
    ["error_code"],
)

# ---------------------------------------------------------------------------
# Playbook / strategy metrics
# ---------------------------------------------------------------------------

STRATEGY_USED = Counter(
    "chaos_strategy_used_total",
    "Recovery strategies applied",
    ["strategy"],
)

RETRIES_TOTAL = Counter(
    "chaos_retries_total",
    "Total retries performed across all experiments",
    ["agent_type"],
)

# ---------------------------------------------------------------------------
# Circuit breaker metrics
# ---------------------------------------------------------------------------

CIRCUIT_STATE = Gauge(
    "chaos_circuit_breaker_state",
    "Circuit breaker state (0=closed, 1=open, 2=half-open)",
)

# ---------------------------------------------------------------------------
# Run-level metrics
# ---------------------------------------------------------------------------

CURRENT_FAILURE_RATE = Gauge(
    "chaos_current_failure_rate",
    "Current failure rate being tested",
)

SUCCESS_RATE = Gauge(
    "chaos_success_rate",
    "Latest computed success rate",
    ["agent_type"],
)

CONSISTENCY_RATE = Gauge(
    "chaos_consistency_rate",
    "Latest computed consistency rate",
    ["agent_type"],
)
