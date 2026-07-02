"""Shared type definitions for the Chaos Playbook Engine."""
from __future__ import annotations

from enum import StrEnum
from typing import Any, TypedDict


# ---------------------------------------------------------------------------
# A.9 — Domain enumerations replacing magic strings
# ---------------------------------------------------------------------------

class Status(StrEnum):
    """Outcome status for API responses and experiment results."""
    SUCCESS = "success"
    FAILURE = "failure"
    ERROR = "error"


class WorkflowStep(StrEnum):
    """Canonical names for the unified 4-step order workflow.

    Shared across HTTP, MCP, and A2A protocols for fair comparison.
    """
    FIND_PRODUCT = "find_product"
    CHECK_INVENTORY = "check_inventory"
    PLACE_ORDER = "place_order"
    CONFIRM_ORDER = "confirm_order"


class RetryStrategy(StrEnum):
    """Playbook retry strategies supported by DeterministicAgent."""
    FAIL_FAST = "fail_fast"
    ESCALATE_TO_HUMAN = "escalate_to_human"
    RETRY_LINEAR = "retry_linear_backoff"
    RETRY_EXPONENTIAL = "retry_exponential_backoff"
    WAIT_AND_RETRY = "wait_and_retry"


class MCPFailureType(StrEnum):
    """Failure types for MCP tool call chaos injection."""
    TOOL_NOT_FOUND = "tool_not_found"
    INVALID_PARAMS = "invalid_params"
    CONTEXT_OVERFLOW = "context_overflow"
    TIMEOUT = "timeout"
    RATE_LIMITED = "rate_limited"
    INTERNAL_ERROR = "internal_error"


class A2AFailureType(StrEnum):
    """Failure types for Agent-to-Agent communication chaos injection."""
    AGENT_NOT_FOUND = "agent_not_found"
    TASK_REJECTED = "task_rejected"
    TIMEOUT = "timeout"
    CORRUPT_RESPONSE = "corrupt_response"
    PARTIAL_FAILURE = "partial_failure"
    AUTH_ERROR = "authentication_error"


# ---------------------------------------------------------------------------
# A.8 — Typed dictionaries for public return types
# ---------------------------------------------------------------------------

class ApiResponse(TypedDict, total=False):
    """Return type for ChaosProxy.send_request and CircuitBreakerProxy.send_request."""
    status: str
    code: int
    data: dict[str, Any] | None
    message: str | None


class ExperimentResult(TypedDict, total=False):
    """Return type for DeterministicAgent.run() and ABTestRunner.run_experiment()."""
    status: str
    steps_completed: list[str]
    failed_at: str | None
    duration_ms: float
    retries: int
    simulated_delay_s: float
    outcome: str
    agent_type: str
    # Added by ParametricABTestRunner
    experiment_id: str
    failure_rate: float
    seed: int
    inconsistencies_count: int
