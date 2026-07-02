"""
MCP Chaos Proxy - Failure injection for Model Context Protocol tool calls.

Wraps an MCP server connection and injects configurable failures
(tool not found, context overflow, schema errors, timeouts, rate limits)
using seed-controlled randomness for deterministic chaos scenarios.
"""
from __future__ import annotations

import logging
import random
from typing import Any, Dict, List, Optional

from chaos_engine.core.fixtures import MOCK_DATA_BY_ACTION
from chaos_engine.core.types import MCPFailureType, Status


# Default tool catalog for mock mode — unified order workflow
_MOCK_TOOLS: List[Dict[str, Any]] = [
    {
        "name": "find_product",
        "description": "Search available products",
        "inputSchema": {
            "type": "object",
            "properties": {"status": {"type": "string"}},
            "required": ["status"],
        },
    },
    {
        "name": "check_inventory",
        "description": "Check stock for a product",
        "inputSchema": {
            "type": "object",
            "properties": {"productId": {"type": "string"}},
            "required": ["productId"],
        },
    },
    {
        "name": "place_order",
        "description": "Create an order",
        "inputSchema": {
            "type": "object",
            "properties": {"productId": {"type": "string"}, "quantity": {"type": "integer"}},
            "required": ["productId", "quantity"],
        },
    },
    {
        "name": "confirm_order",
        "description": "Finalize and confirm the order",
        "inputSchema": {
            "type": "object",
            "properties": {"orderId": {"type": "string"}},
            "required": ["orderId"],
        },
    },
]

# Error messages per failure type
_MCP_ERROR_MESSAGES: Dict[str, str] = {
    MCPFailureType.TOOL_NOT_FOUND: "Tool '{tool_name}' not found on MCP server",
    MCPFailureType.INVALID_PARAMS: "Schema validation failed for tool '{tool_name}': invalid arguments",
    MCPFailureType.CONTEXT_OVERFLOW: "Context window exceeded: request too large for tool '{tool_name}'",
    MCPFailureType.TIMEOUT: "MCP server timeout: tool '{tool_name}' did not respond within deadline",
    MCPFailureType.RATE_LIMITED: "Rate limit exceeded for MCP server: retry after backoff",
    MCPFailureType.INTERNAL_ERROR: "MCP server internal error while executing tool '{tool_name}'",
}


class MCPChaosProxy:
    """Chaos-injecting proxy for MCP tool calls.

    Sits between an MCP client and server, intercepting ``call_tool`` and
    ``list_tools`` requests.  When the RNG (seed-controlled) triggers a
    failure, it returns a realistic MCP error instead of forwarding the
    request.

    Satisfies the ``MCPToolExecutor`` protocol.
    """

    def __init__(
        self,
        failure_rate: float,
        seed: int,
        mock_mode: bool = False,
        failure_types: List[MCPFailureType] | None = None,
        tool_catalog: List[Dict[str, Any]] | None = None,
    ) -> None:
        self.failure_rate = failure_rate
        self.rng = random.Random(seed)
        self.mock_mode = mock_mode
        # Only transient errors — tool_not_found, invalid_params, and
        # context_overflow are permanent and shouldn't resolve on retry.
        self.failure_types = failure_types or [
            MCPFailureType.TIMEOUT,
            MCPFailureType.RATE_LIMITED,
            MCPFailureType.INTERNAL_ERROR,
        ]
        self.tool_catalog = tool_catalog or list(_MOCK_TOOLS)
        self.logger = logging.getLogger("MCPChaosProxy")

    def should_inject(self) -> bool:
        """Return True if chaos should be injected on this call."""
        return self.rng.random() < self.failure_rate

    # ------------------------------------------------------------------
    # MCPToolExecutor protocol
    # ------------------------------------------------------------------

    async def call_tool(
        self,
        tool_name: str,
        arguments: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Call an MCP tool, with possible chaos injection."""

        # 1. Chaos check
        if self.should_inject():
            failure = self.rng.choice(self.failure_types)
            msg = _MCP_ERROR_MESSAGES.get(
                failure, "Unknown MCP error"
            ).format(tool_name=tool_name)
            self.logger.info(
                "MCP CHAOS INJECTED: %s on tool '%s'", failure, tool_name,
            )
            return {
                "status": Status.ERROR,
                "error_type": str(failure),
                "message": msg,
                "tool_name": tool_name,
            }

        # 2. Mock mode
        if self.mock_mode:
            self.logger.info("MCP MOCK CALL: tool '%s'", tool_name)
            return self._mock_tool_result(tool_name, arguments)

        # 3. Real call (delegate to wrapped client — not yet wired)
        self.logger.warning(
            "MCPChaosProxy: real MCP forwarding not implemented; "
            "returning mock result for tool '%s'",
            tool_name,
        )
        return self._mock_tool_result(tool_name, arguments)

    async def list_tools(self) -> List[Dict[str, Any]]:
        """List available MCP tools (chaos may inject empty list)."""
        if self.should_inject():
            self.logger.info("MCP CHAOS INJECTED: returning empty tool list")
            return []
        return list(self.tool_catalog)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _mock_tool_result(
        self, tool_name: str, arguments: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        data = MOCK_DATA_BY_ACTION.get(tool_name, {"result": f"Mock result for {tool_name}"})
        return {
            "status": Status.SUCCESS,
            "tool_name": tool_name,
            "data": data,
        }
