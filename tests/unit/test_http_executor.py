from __future__ import annotations

import pytest

from chaos_engine.infrastructure.http_executor import HttpExecutor


def test_implements_executor_protocol():
    """HttpExecutor must satisfy the Executor protocol."""
    from chaos_engine.core.protocols import Executor

    executor = HttpExecutor(base_url="http://localhost")
    assert isinstance(executor, Executor)


def test_jittered_backoff_is_deterministic():
    """Same seed should produce same jitter."""
    a = HttpExecutor(seed=42)
    b = HttpExecutor(seed=42)
    assert a.calculate_jittered_backoff(5.0) == b.calculate_jittered_backoff(5.0)


def test_jittered_backoff_adds_positive_jitter():
    """Backoff should always be >= the input seconds."""
    executor = HttpExecutor(seed=1)
    for _ in range(20):
        result = executor.calculate_jittered_backoff(3.0)
        assert result >= 3.0
        assert result <= 3.0 * 1.5  # max jitter is 50%


@pytest.mark.asyncio
async def test_send_request_timeout_returns_408():
    """Requests to unreachable host should return a 408 timeout."""
    executor = HttpExecutor(base_url="http://10.255.255.1", timeout=0.1)
    result = await executor.send_request("GET", "/test")
    assert result["status"] == "error"
    assert result["code"] in (408, 500)  # timeout or connection error
    await executor.close()
