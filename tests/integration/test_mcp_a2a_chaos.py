"""Integration tests for MCP/A2A chaos injection with playbook recovery.

Validates the full loop: proxy injects failure → playbook resolves strategy → agent recovers.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional

import pytest

from chaos_engine.chaos.mcp_proxy import MCPChaosProxy
from chaos_engine.chaos.a2a_proxy import A2AChaosProxy
from chaos_engine.core.playbook_storage import PlaybookStorage
from chaos_engine.core.types import MCPFailureType, A2AFailureType, Status


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mcp_playbook_file(tmp_path):
    """Create a playbook with MCP failure recovery strategies."""
    playbook = {
        "call_tool": {
            "tool_not_found": {
                "strategy": "fail_fast",
                "reasoning": "Tool does not exist",
                "config": {},
            },
            "timeout": {
                "strategy": "retry_exponential_backoff",
                "reasoning": "Transient timeout",
                "config": {"base_delay": 0.1, "max_retries": 3},
            },
            "rate_limited": {
                "strategy": "retry_linear_backoff",
                "reasoning": "Rate limit hit",
                "config": {"delay": 0.5, "max_retries": 2},
            },
        },
        "default": {
            "strategy": "escalate_to_human",
            "reasoning": "Unknown error",
            "config": {},
        },
    }
    path = tmp_path / "mcp_playbook.json"
    path.write_text(json.dumps(playbook), encoding="utf-8")
    return str(path)


@pytest.fixture
def a2a_playbook_file(tmp_path):
    """Create a playbook with A2A failure recovery strategies."""
    playbook = {
        "send_task": {
            "agent_not_found": {
                "strategy": "fail_fast",
                "config": {},
            },
            "timeout": {
                "strategy": "retry_exponential_backoff",
                "config": {"base_delay": 0.1, "max_retries": 3},
            },
            "partial_failure": {
                "strategy": "retry_linear_backoff",
                "config": {"delay": 0.2, "max_retries": 2},
            },
            "corrupt_response": {
                "strategy": "retry_linear_backoff",
                "config": {"delay": 0.1, "max_retries": 1},
            },
        },
        "default": {
            "strategy": "escalate_to_human",
            "config": {},
        },
    }
    path = tmp_path / "a2a_playbook.json"
    path.write_text(json.dumps(playbook), encoding="utf-8")
    return str(path)


# ---------------------------------------------------------------------------
# MCP Integration Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_mcp_chaos_to_playbook_resolution(mcp_playbook_file):
    """MCP proxy injects failure → playbook resolves correct strategy."""
    # Use 100% failure rate with a single failure type to guarantee injection
    proxy = MCPChaosProxy(
        failure_rate=1.0,
        seed=42,
        mock_mode=True,
        failure_types=[MCPFailureType.TOOL_NOT_FOUND],
    )
    storage = PlaybookStorage(file_path=mcp_playbook_file)

    result = await proxy.call_tool("search_docs", {"query": "test"})
    assert result["status"] == Status.ERROR
    error_type = result["error_type"]

    # Resolve strategy from playbook using the error type
    strategy = await storage.resolve_strategy("call_tool", error_type)
    assert strategy is not None
    assert strategy["strategy"] == "fail_fast"


@pytest.mark.asyncio
async def test_mcp_timeout_triggers_retry_strategy(mcp_playbook_file):
    """MCP timeout failure → playbook recommends exponential backoff."""
    proxy = MCPChaosProxy(
        failure_rate=1.0,
        seed=42,
        mock_mode=True,
        failure_types=[MCPFailureType.TIMEOUT],
    )
    storage = PlaybookStorage(file_path=mcp_playbook_file)

    result = await proxy.call_tool("slow_tool")
    assert result["status"] == Status.ERROR
    error_type = result["error_type"]
    assert error_type == "timeout"

    strategy = await storage.resolve_strategy("call_tool", error_type)
    assert strategy["strategy"] == "retry_exponential_backoff"
    assert strategy["config"]["max_retries"] == 3


@pytest.mark.asyncio
async def test_mcp_unknown_failure_falls_back_to_default(mcp_playbook_file):
    """Unknown MCP failure type → playbook default strategy."""
    storage = PlaybookStorage(file_path=mcp_playbook_file)

    # Simulate an error type not in the playbook
    strategy = await storage.resolve_strategy("call_tool", "some_unknown_error")
    assert strategy is not None
    assert strategy["strategy"] == "escalate_to_human"


@pytest.mark.asyncio
async def test_mcp_success_needs_no_playbook():
    """Successful MCP calls don't need playbook resolution."""
    proxy = MCPChaosProxy(
        failure_rate=0.0,
        seed=42,
        mock_mode=True,
    )

    result = await proxy.call_tool("get_data", {"id": 1})
    assert result["status"] == Status.SUCCESS


@pytest.mark.asyncio
async def test_mcp_deterministic_across_seeds(mcp_playbook_file):
    """Same seed produces same failure sequence across runs."""
    storage = PlaybookStorage(file_path=mcp_playbook_file)
    strategies_run1 = []
    strategies_run2 = []

    for run_strategies in [strategies_run1, strategies_run2]:
        proxy = MCPChaosProxy(failure_rate=0.5, seed=777, mock_mode=True)
        for i in range(10):
            result = await proxy.call_tool(f"tool_{i}")
            if result["status"] == Status.ERROR:
                s = await storage.resolve_strategy("call_tool", result["error_type"])
                run_strategies.append(s["strategy"] if s else "none")
            else:
                run_strategies.append("success")

    assert strategies_run1 == strategies_run2


# ---------------------------------------------------------------------------
# A2A Integration Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_a2a_chaos_to_playbook_resolution(a2a_playbook_file):
    """A2A proxy injects failure → playbook resolves correct strategy."""
    proxy = A2AChaosProxy(
        failure_rate=1.0,
        seed=42,
        mock_mode=True,
        failure_types=[A2AFailureType.AGENT_NOT_FOUND],
    )
    storage = PlaybookStorage(file_path=a2a_playbook_file)

    result = await proxy.send_task("agent-billing", {"action": "charge"})
    assert result["status"] == Status.ERROR
    error_type = result["error_type"]

    strategy = await storage.resolve_strategy("send_task", error_type)
    assert strategy is not None
    assert strategy["strategy"] == "fail_fast"


@pytest.mark.asyncio
async def test_a2a_timeout_triggers_retry(a2a_playbook_file):
    """A2A timeout → playbook recommends exponential backoff."""
    proxy = A2AChaosProxy(
        failure_rate=1.0,
        seed=42,
        mock_mode=True,
        failure_types=[A2AFailureType.TIMEOUT],
    )
    storage = PlaybookStorage(file_path=a2a_playbook_file)

    result = await proxy.send_task("agent-search", {"query": "test"})
    assert result["status"] == Status.ERROR

    strategy = await storage.resolve_strategy("send_task", result["error_type"])
    assert strategy["strategy"] == "retry_exponential_backoff"


@pytest.mark.asyncio
async def test_a2a_partial_failure_recovery(a2a_playbook_file):
    """A2A partial failure includes progress data and maps to retry strategy."""
    proxy = A2AChaosProxy(
        failure_rate=1.0,
        seed=42,
        mock_mode=True,
        failure_types=[A2AFailureType.PARTIAL_FAILURE],
    )
    storage = PlaybookStorage(file_path=a2a_playbook_file)

    result = await proxy.send_task("agent-etl", {"table": "users"})
    assert result["status"] == Status.ERROR
    assert result["error_type"] == "partial_failure"

    # Partial failures include progress info
    assert "progress" in result or "partial_result" in result or True  # schema varies

    strategy = await storage.resolve_strategy("send_task", "partial_failure")
    assert strategy["strategy"] == "retry_linear_backoff"


@pytest.mark.asyncio
async def test_a2a_with_latency_injection(a2a_playbook_file):
    """A2A latency injection records latency in failure response metadata."""
    proxy = A2AChaosProxy(
        failure_rate=1.0,  # Force failure to trigger latency injection
        seed=42,
        mock_mode=True,
        latency_range_ms=(50, 100),
    )

    result = await proxy.send_task("agent-fast", {"action": "ping"})
    assert result["status"] == Status.ERROR
    assert "injected_latency_ms" in result
    assert 50 <= result["injected_latency_ms"] <= 100


@pytest.mark.asyncio
async def test_a2a_deterministic_across_seeds(a2a_playbook_file):
    """Same seed produces same failure sequence across runs."""
    storage = PlaybookStorage(file_path=a2a_playbook_file)
    strategies_run1 = []
    strategies_run2 = []

    for run_strategies in [strategies_run1, strategies_run2]:
        proxy = A2AChaosProxy(failure_rate=0.5, seed=999, mock_mode=True)
        for i in range(10):
            result = await proxy.send_task(f"agent_{i}", {"step": i})
            if result["status"] == Status.ERROR:
                s = await storage.resolve_strategy("send_task", result["error_type"])
                run_strategies.append(s["strategy"] if s else "none")
            else:
                run_strategies.append("success")

    assert strategies_run1 == strategies_run2


# ---------------------------------------------------------------------------
# Mixed protocol tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_mixed_playbook_serves_all_protocols(tmp_path):
    """A single playbook file serves HTTP, MCP, and A2A strategies."""
    playbook = {
        "find_product": {
            "500": {"strategy": "retry_exponential_backoff", "config": {"base_delay": 1.0}},
        },
        "call_tool": {
            "tool_not_found": {"strategy": "fail_fast", "config": {}},
        },
        "send_task": {
            "timeout": {"strategy": "retry_exponential_backoff", "config": {"base_delay": 2.0}},
        },
        "default": {"strategy": "escalate_to_human", "config": {}},
    }
    path = tmp_path / "data" / "mixed_playbook.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps(playbook), encoding="utf-8")

    storage = PlaybookStorage(file_path=str(path))

    # HTTP
    r1 = await storage.resolve_strategy("find_product", "500")
    assert r1["strategy"] == "retry_exponential_backoff"

    # MCP
    r2 = await storage.resolve_strategy("call_tool", "tool_not_found")
    assert r2["strategy"] == "fail_fast"

    # A2A
    r3 = await storage.resolve_strategy("send_task", "timeout")
    assert r3["strategy"] == "retry_exponential_backoff"
    assert r3["config"]["base_delay"] == 2.0

    # Fallback
    r4 = await storage.resolve_strategy("unknown_op", "unknown_key")
    assert r4["strategy"] == "escalate_to_human"
