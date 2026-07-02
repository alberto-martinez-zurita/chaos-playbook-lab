"""Tests for MCPChaosProxy — MCP tool call chaos injection."""
import pytest

from chaos_engine.chaos.mcp_proxy import MCPChaosProxy
from chaos_engine.core.protocols import MCPToolExecutor
from chaos_engine.core.types import MCPFailureType, Status


# ---------------------------------------------------------------------------
# Protocol conformance
# ---------------------------------------------------------------------------

def test_mcp_proxy_satisfies_protocol():
    proxy = MCPChaosProxy(failure_rate=0.0, seed=1)
    assert isinstance(proxy, MCPToolExecutor)


# ---------------------------------------------------------------------------
# Seed determinism
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_mcp_proxy_determinism():
    """Two proxies with the same seed produce identical sequences."""
    p1 = MCPChaosProxy(failure_rate=0.5, seed=42, mock_mode=True)
    p2 = MCPChaosProxy(failure_rate=0.5, seed=42, mock_mode=True)

    results1 = [await p1.call_tool("find_product", {"status": "available"}) for _ in range(10)]
    results2 = [await p2.call_tool("find_product", {"status": "available"}) for _ in range(10)]

    assert results1 == results2


# ---------------------------------------------------------------------------
# Chaos injection
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_mcp_proxy_always_injects_at_rate_1():
    proxy = MCPChaosProxy(failure_rate=1.0, seed=1, mock_mode=True)
    result = await proxy.call_tool("check_inventory", {"productId": "SKU-1234"})

    assert result["status"] == Status.ERROR
    assert result["error_type"] in [ft.value for ft in MCPFailureType]
    assert result["tool_name"] == "check_inventory"


@pytest.mark.asyncio
async def test_mcp_proxy_never_injects_at_rate_0():
    proxy = MCPChaosProxy(failure_rate=0.0, seed=1, mock_mode=True)
    for _ in range(20):
        result = await proxy.call_tool("find_product", {"status": "available"})
        assert result["status"] == Status.SUCCESS


@pytest.mark.asyncio
async def test_mcp_proxy_specific_failure_types():
    """When restricted to one failure type, only that type is injected."""
    proxy = MCPChaosProxy(
        failure_rate=1.0,
        seed=1,
        mock_mode=True,
        failure_types=[MCPFailureType.CONTEXT_OVERFLOW],
    )
    result = await proxy.call_tool("check_inventory")
    assert result["error_type"] == MCPFailureType.CONTEXT_OVERFLOW


# ---------------------------------------------------------------------------
# Mock mode
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_mcp_proxy_mock_returns_data():
    proxy = MCPChaosProxy(failure_rate=0.0, seed=1, mock_mode=True)
    result = await proxy.call_tool("find_product", {"status": "available"})

    assert result["status"] == Status.SUCCESS
    assert result["tool_name"] == "find_product"
    assert isinstance(result["data"], list)
    assert result["data"][0]["id"] == "SKU-1234"


# ---------------------------------------------------------------------------
# list_tools
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_mcp_list_tools_normal():
    proxy = MCPChaosProxy(failure_rate=0.0, seed=1)
    tools = await proxy.list_tools()
    assert len(tools) == 4
    assert tools[0]["name"] == "find_product"
    assert tools[3]["name"] == "confirm_order"


@pytest.mark.asyncio
async def test_mcp_list_tools_chaos_returns_empty():
    proxy = MCPChaosProxy(failure_rate=1.0, seed=1)
    tools = await proxy.list_tools()
    assert tools == []


# ---------------------------------------------------------------------------
# Error message formatting
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_mcp_error_message_includes_tool_name():
    proxy = MCPChaosProxy(
        failure_rate=1.0, seed=1, mock_mode=True,
        failure_types=[MCPFailureType.TOOL_NOT_FOUND],
    )
    result = await proxy.call_tool("my_custom_tool")
    assert "my_custom_tool" in result["message"]
