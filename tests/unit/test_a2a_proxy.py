"""Tests for A2AChaosProxy — Agent-to-Agent communication chaos injection."""
import pytest

from chaos_engine.chaos.a2a_proxy import A2AChaosProxy
from chaos_engine.core.protocols import A2AExecutor
from chaos_engine.core.types import A2AFailureType, Status


# ---------------------------------------------------------------------------
# Protocol conformance
# ---------------------------------------------------------------------------

def test_a2a_proxy_satisfies_protocol():
    proxy = A2AChaosProxy(failure_rate=0.0, seed=1)
    assert isinstance(proxy, A2AExecutor)


# ---------------------------------------------------------------------------
# Seed determinism
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_a2a_proxy_determinism():
    """Two proxies with the same seed produce identical sequences."""
    p1 = A2AChaosProxy(failure_rate=0.5, seed=42, mock_mode=True)
    p2 = A2AChaosProxy(failure_rate=0.5, seed=42, mock_mode=True)

    task = {"instruction": "summarize document"}
    results1 = [await p1.send_task("agent-b", task) for _ in range(10)]
    results2 = [await p2.send_task("agent-b", task) for _ in range(10)]

    assert results1 == results2


# ---------------------------------------------------------------------------
# Chaos injection
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_a2a_proxy_always_injects_at_rate_1():
    proxy = A2AChaosProxy(failure_rate=1.0, seed=1, mock_mode=True)
    result = await proxy.send_task("agent-b", {"instruction": "test"})

    assert result["status"] == Status.ERROR
    assert result["error_type"] in [ft.value for ft in A2AFailureType]
    assert result["agent_id"] == "agent-b"
    assert "task_id" in result


@pytest.mark.asyncio
async def test_a2a_proxy_never_injects_at_rate_0():
    proxy = A2AChaosProxy(failure_rate=0.0, seed=1, mock_mode=True)
    for _ in range(20):
        result = await proxy.send_task("agent-x", {"instruction": "work"})
        assert result["status"] == Status.SUCCESS


@pytest.mark.asyncio
async def test_a2a_proxy_specific_failure_type():
    proxy = A2AChaosProxy(
        failure_rate=1.0, seed=1, mock_mode=True,
        failure_types=[A2AFailureType.TIMEOUT],
    )
    result = await proxy.send_task("agent-slow", {"instruction": "heavy task"})
    assert result["error_type"] == A2AFailureType.TIMEOUT


# ---------------------------------------------------------------------------
# Corrupt response
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_a2a_corrupt_response_includes_mangled_data():
    proxy = A2AChaosProxy(
        failure_rate=1.0, seed=1, mock_mode=True,
        failure_types=[A2AFailureType.CORRUPT_RESPONSE],
    )
    result = await proxy.send_task("agent-corrupt", {"instruction": "test"})
    assert result["error_type"] == A2AFailureType.CORRUPT_RESPONSE
    assert "data" in result
    assert result["data"]["truncated"] is True


# ---------------------------------------------------------------------------
# Partial failure
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_a2a_partial_failure_includes_progress():
    proxy = A2AChaosProxy(
        failure_rate=1.0, seed=1, mock_mode=True,
        failure_types=[A2AFailureType.PARTIAL_FAILURE],
    )
    result = await proxy.send_task("agent-partial", {"instruction": "test"})
    assert result["error_type"] == A2AFailureType.PARTIAL_FAILURE
    assert 0.0 < result["partial_data"]["progress"] < 1.0


# ---------------------------------------------------------------------------
# Latency injection
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_a2a_latency_injection():
    proxy = A2AChaosProxy(
        failure_rate=1.0, seed=1, mock_mode=True,
        latency_range_ms=(100, 5000),
    )
    result = await proxy.send_task("agent-b", {"instruction": "test"})
    assert 100 <= result["injected_latency_ms"] <= 5000


# ---------------------------------------------------------------------------
# Mock mode
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_a2a_mock_returns_data():
    proxy = A2AChaosProxy(failure_rate=0.0, seed=1, mock_mode=True)
    task = {"instruction": "analyze data"}
    result = await proxy.send_task("agent-analyst", task)

    assert result["status"] == Status.SUCCESS
    assert result["agent_id"] == "agent-analyst"
    assert result["task_status"] == "completed"
    assert isinstance(result["data"], dict)


# ---------------------------------------------------------------------------
# query_status
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_a2a_query_status_for_known_task():
    proxy = A2AChaosProxy(failure_rate=0.0, seed=1, mock_mode=True)
    send_result = await proxy.send_task("agent-b", {"instruction": "work"})
    task_id = send_result["task_id"]

    status_result = await proxy.query_status("agent-b", task_id)
    assert status_result["status"] == Status.SUCCESS
    assert status_result["task_id"] == task_id


@pytest.mark.asyncio
async def test_a2a_query_status_for_unknown_task():
    proxy = A2AChaosProxy(failure_rate=0.0, seed=1, mock_mode=True)
    result = await proxy.query_status("agent-b", "nonexistent-task-id")
    assert result["status"] == Status.ERROR
    assert result["error_type"] == "task_not_found"


@pytest.mark.asyncio
async def test_a2a_query_status_chaos_injection():
    proxy = A2AChaosProxy(failure_rate=1.0, seed=1, mock_mode=True)
    result = await proxy.query_status("agent-b", "some-task")
    assert result["status"] == Status.ERROR
    assert result["error_type"] in [ft.value for ft in A2AFailureType]


# ---------------------------------------------------------------------------
# Error message formatting
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_a2a_error_message_includes_agent_id():
    proxy = A2AChaosProxy(
        failure_rate=1.0, seed=1, mock_mode=True,
        failure_types=[A2AFailureType.AGENT_NOT_FOUND],
    )
    result = await proxy.send_task("agent-xyz-123", {"instruction": "test"})
    assert "agent-xyz-123" in result["message"]
