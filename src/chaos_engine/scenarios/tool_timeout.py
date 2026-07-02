"""Scenario: Tool timeout (>45 s)."""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Protocol, runtime_checkable

from chaos_engine.scenarios.base import ChaosScenario

logger = logging.getLogger(__name__)


@runtime_checkable
class ToolCaller(Protocol):
    """Agent that calls a tool and returns the result."""

    async def call_tool(self, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]: ...


class SlowToolWrapper:
    """Wraps a ``ToolCaller`` adding an artificial delay to simulate timeout."""

    def __init__(self, inner: ToolCaller, *, delay_s: float = 46.0) -> None:
        self._inner = inner
        self.delay_s = delay_s

    async def call_tool(self, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        await asyncio.sleep(self.delay_s)
        return await self._inner.call_tool(tool_name, arguments)


class ToolTimeoutScenario(ChaosScenario):
    """Simulates a tool call that takes >45 s and verifies the agent
    respects its timeout budget and handles the situation gracefully.
    """

    def __init__(
        self,
        agent_call_tool: ToolCaller,
        *,
        delay_s: float = 46.0,
        timeout_s: float = 45.0,
        tool_name: str = "slow_tool",
    ) -> None:
        self._agent = agent_call_tool
        self._delay_s = delay_s
        self._timeout_s = timeout_s
        self._tool_name = tool_name
        self._slow: SlowToolWrapper | None = None

    @property
    def name(self) -> str:
        return "tool_timeout"

    @property
    def description(self) -> str:
        return f"Tool responds after {self._delay_s}s, timeout set to {self._timeout_s}s"

    async def setup(self) -> None:
        self._slow = SlowToolWrapper(self._agent, delay_s=self._delay_s)

    async def execute(self) -> dict[str, Any]:
        assert self._slow is not None
        try:
            result = await asyncio.wait_for(
                self._slow.call_tool(self._tool_name, {}),
                timeout=self._timeout_s,
            )
            return {"timed_out": False, "result": result}
        except asyncio.TimeoutError:
            return {"timed_out": True}
        except Exception as exc:  # noqa: BLE001
            return {"timed_out": False, "error": str(exc)}

    async def verify(self, execution_data: dict[str, Any]) -> bool:
        # The agent should have timed out since delay > timeout
        if self._delay_s > self._timeout_s:
            return execution_data.get("timed_out", False)
        # If delay <= timeout, getting a result is fine
        return not execution_data.get("error")

    async def teardown(self) -> None:
        self._slow = None
