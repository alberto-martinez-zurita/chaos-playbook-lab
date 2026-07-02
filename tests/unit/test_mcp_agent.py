"""Unit tests for MCPBaselineAgent and MCPLLMAgent."""
from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

import pytest

from chaos_engine.agents.mcp_agent import (
    MCPBaselineAgent,
    MCPLLMAgent,
    MCP_WORKFLOW_STEPS,
    _MCP_SYSTEM_PROMPT,
)
from chaos_engine.core.types import MCPFailureType, Status


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------

class FakeMCPExecutor:
    """Fake MCPToolExecutor with configurable responses."""

    def __init__(
        self,
        tool_responses: dict[str, dict[str, Any]] | None = None,
        list_tools_result: list[dict] | None = None,
        call_sequence: list[dict[str, Any]] | None = None,
    ) -> None:
        self._tool_responses = tool_responses or {}
        self._list_tools_result = list_tools_result if list_tools_result is not None else [
            {"name": "find_product", "description": "Search products"},
            {"name": "check_inventory", "description": "Check stock"},
            {"name": "place_order", "description": "Create order"},
            {"name": "confirm_order", "description": "Finalize order"},
        ]
        self._call_sequence = list(call_sequence) if call_sequence else None
        self._call_index = 0
        self.calls: list[tuple[str, Optional[dict]]] = []

    async def call_tool(
        self, tool_name: str, arguments: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        self.calls.append((tool_name, arguments))
        if self._call_sequence is not None:
            if self._call_index < len(self._call_sequence):
                resp = self._call_sequence[self._call_index]
                self._call_index += 1
                return resp
            return {"status": Status.SUCCESS, "data": {}}
        if tool_name in self._tool_responses:
            return self._tool_responses[tool_name]
        return {"status": Status.SUCCESS, "tool_name": tool_name, "data": {"result": "ok"}}

    async def list_tools(self) -> List[Dict[str, Any]]:
        return self._list_tools_result


def _mcp_action(
    action: str,
    tool_name: str = "",
    arguments: Any = None,
) -> str:
    """Build a JSON action string as the LLM would return for MCP."""
    if action == "call_tool":
        return json.dumps({
            "action": "call_tool",
            "tool_name": tool_name,
            "arguments": arguments,
        })
    return json.dumps({"action": action})


class SequentialLLM:
    """Fake LLM that returns a pre-configured sequence of responses."""

    def __init__(self, responses: list[str]) -> None:
        self._responses = list(responses)
        self._index = 0
        self.calls: list[tuple[str, str]] = []

    def chat(
        self, system_prompt: str, user_message: str,
        temperature: float | None = None,
    ) -> str:
        self.calls.append((system_prompt, user_message))
        if self._index < len(self._responses):
            resp = self._responses[self._index]
            self._index += 1
            return resp
        return _mcp_action("abort")


# ---------------------------------------------------------------------------
# MCPBaselineAgent tests
# ---------------------------------------------------------------------------

class TestMCPBaselineAgent:
    @pytest.mark.asyncio
    async def test_all_steps_succeed(self):
        executor = FakeMCPExecutor()
        agent = MCPBaselineAgent(tool_executor=executor)
        result = await agent.run()

        assert result["status"] == Status.SUCCESS
        assert len(result["steps_completed"]) == 4
        assert result["failed_at"] is None

    @pytest.mark.asyncio
    async def test_first_tool_error_stops_workflow(self):
        executor = FakeMCPExecutor(tool_responses={
            "find_product": {"status": Status.ERROR, "error_type": MCPFailureType.TIMEOUT},
        })
        agent = MCPBaselineAgent(tool_executor=executor)
        result = await agent.run()

        assert result["status"] == Status.FAILURE
        assert result["failed_at"] == "find_product"
        assert result["steps_completed"] == []

    @pytest.mark.asyncio
    async def test_second_tool_error(self):
        executor = FakeMCPExecutor(tool_responses={
            "check_inventory": {"status": Status.ERROR, "error_type": MCPFailureType.RATE_LIMITED},
        })
        agent = MCPBaselineAgent(tool_executor=executor)
        result = await agent.run()

        assert result["status"] == Status.FAILURE
        assert result["failed_at"] == "check_inventory"
        assert result["steps_completed"] == ["find_product"]

    @pytest.mark.asyncio
    async def test_zero_retries(self):
        executor = FakeMCPExecutor(tool_responses={
            "find_product": {"status": Status.ERROR, "error_type": MCPFailureType.TIMEOUT},
        })
        agent = MCPBaselineAgent(tool_executor=executor)
        result = await agent.run()

        assert result["retries"] == 0


# ---------------------------------------------------------------------------
# MCPLLMAgent tests
# ---------------------------------------------------------------------------

class TestMCPLLMAgent:
    @pytest.mark.asyncio
    async def test_all_steps_succeed(self):
        """LLM orchestrates 4 MCP steps, all succeed, then signals complete."""
        llm_responses = [
            _mcp_action("call_tool", "find_product", {"status": "available"}),
            _mcp_action("call_tool", "check_inventory", {"productId": "SKU-1234"}),
            _mcp_action("call_tool", "place_order",
                        {"productId": "SKU-1234", "quantity": 1}),
            _mcp_action("call_tool", "confirm_order", {"orderId": "ORD-2026-001"}),
            _mcp_action("complete"),
        ]
        executor = FakeMCPExecutor()
        llm = SequentialLLM(llm_responses)
        agent = MCPLLMAgent(tool_executor=executor, llm_client=llm)

        result = await agent.run()

        assert result["status"] == Status.SUCCESS
        assert result["steps_completed"] == [
            "find_product", "check_inventory", "place_order", "confirm_order",
        ]
        assert result["failed_at"] is None
        # LLM called 5 times: 4 actions + 1 complete
        assert len(llm.calls) == 5

    @pytest.mark.asyncio
    async def test_failure_and_abort(self):
        """LLM aborts after a tool call failure."""
        llm_responses = [
            _mcp_action("call_tool", "find_product", {"status": "available"}),
            _mcp_action("abort"),
        ]
        executor = FakeMCPExecutor(tool_responses={
            "find_product": {
                "status": Status.ERROR,
                "error_type": MCPFailureType.TIMEOUT,
            },
        })
        llm = SequentialLLM(llm_responses)
        agent = MCPLLMAgent(tool_executor=executor, llm_client=llm)

        result = await agent.run()

        assert result["status"] == Status.FAILURE
        assert result["failed_at"] == "find_product"
        assert result["steps_completed"] == []
        assert len(llm.calls) == 2

    @pytest.mark.asyncio
    async def test_retry_on_failure(self):
        """LLM retries a failed tool call and succeeds on second attempt."""
        llm_responses = [
            _mcp_action("call_tool", "find_product", {"status": "available"}),
            # After failure, LLM retries the same tool
            _mcp_action("call_tool", "find_product", {"status": "available"}),
            _mcp_action("call_tool", "check_inventory", {"productId": "SKU-1234"}),
            _mcp_action("call_tool", "place_order",
                        {"productId": "SKU-1234", "quantity": 1}),
            _mcp_action("call_tool", "confirm_order", {"orderId": "ORD-2026-001"}),
            _mcp_action("complete"),
        ]
        executor = FakeMCPExecutor(call_sequence=[
            # find_product first attempt fails
            {"status": Status.ERROR, "error_type": MCPFailureType.TIMEOUT},
            # find_product retry succeeds
            {"status": Status.SUCCESS, "data": {"products": []}},
            # check_inventory succeeds
            {"status": Status.SUCCESS, "data": {"available": 100}},
            # place_order succeeds
            {"status": Status.SUCCESS, "data": {"orderId": "ORD-2026-001"}},
            # confirm_order succeeds
            {"status": Status.SUCCESS, "data": {"confirmed": True}},
        ])
        llm = SequentialLLM(llm_responses)
        agent = MCPLLMAgent(tool_executor=executor, llm_client=llm)

        result = await agent.run()

        assert result["status"] == Status.SUCCESS
        assert result["steps_completed"] == [
            "find_product", "check_inventory", "place_order", "confirm_order",
        ]
        assert result["retries"] == 1
        assert len(llm.calls) == 6

    @pytest.mark.asyncio
    async def test_max_turns_exceeded(self):
        """Agent stops after max turns with FAILURE."""
        # LLM keeps retrying find_product forever
        llm_responses = [
            _mcp_action("call_tool", "find_product", {"status": "available"})
            for _ in range(20)
        ]
        executor = FakeMCPExecutor(call_sequence=[
            {"status": Status.ERROR, "error_type": MCPFailureType.TIMEOUT}
            for _ in range(20)
        ])
        llm = SequentialLLM(llm_responses)
        agent = MCPLLMAgent(tool_executor=executor, llm_client=llm)

        result = await agent.run()

        assert result["status"] == Status.FAILURE
        assert result["failed_at"] == "find_product"
        # Should have used exactly 12 turns (max)
        assert len(llm.calls) == 12

    @pytest.mark.asyncio
    async def test_llm_parse_error_aborts(self):
        """When LLM returns unparseable text, agent aborts with failure."""
        llm = SequentialLLM(["this is not json"])
        executor = FakeMCPExecutor()
        agent = MCPLLMAgent(tool_executor=executor, llm_client=llm)

        result = await agent.run()

        assert result["status"] == Status.FAILURE
        assert result["failed_at"] == "find_product"

    @pytest.mark.asyncio
    async def test_llm_exception_aborts(self):
        """When LLM client raises, agent aborts."""
        from unittest.mock import MagicMock

        llm = SequentialLLM([])
        llm.chat = MagicMock(side_effect=RuntimeError("API down"))
        executor = FakeMCPExecutor()
        agent = MCPLLMAgent(tool_executor=executor, llm_client=llm)

        result = await agent.run()

        assert result["status"] == Status.FAILURE
        assert result["retries"] == 0

    @pytest.mark.asyncio
    async def test_system_prompt_is_sent(self):
        """Every LLM call receives the MCP system prompt."""
        llm_responses = [_mcp_action("complete")]
        llm = SequentialLLM(llm_responses)
        executor = FakeMCPExecutor()
        agent = MCPLLMAgent(tool_executor=executor, llm_client=llm)

        await agent.run()

        assert len(llm.calls) == 1
        assert llm.calls[0][0] == _MCP_SYSTEM_PROMPT

    @pytest.mark.asyncio
    async def test_state_message_after_call_tool_success(self):
        """After a successful call_tool, user message includes step info."""
        llm_responses = [
            _mcp_action("call_tool", "find_product", {"status": "available"}),
            _mcp_action("complete"),
        ]
        executor = FakeMCPExecutor()
        llm = SequentialLLM(llm_responses)
        agent = MCPLLMAgent(tool_executor=executor, llm_client=llm)

        await agent.run()

        # Second LLM call should mention the successful step
        second_msg = llm.calls[1][1]
        assert "find_product" in second_msg
        assert "success" in second_msg

    @pytest.mark.asyncio
    async def test_state_message_after_call_tool_error(self):
        """After a call_tool failure, user message includes error info."""
        llm_responses = [
            _mcp_action("call_tool", "find_product", {"status": "available"}),
            _mcp_action("abort"),
        ]
        executor = FakeMCPExecutor(tool_responses={
            "find_product": {
                "status": Status.ERROR,
                "error_type": MCPFailureType.TIMEOUT,
            },
        })
        llm = SequentialLLM(llm_responses)
        agent = MCPLLMAgent(tool_executor=executor, llm_client=llm)

        await agent.run()

        # Second LLM call should mention the error
        second_msg = llm.calls[1][1]
        assert "error" in second_msg
        assert "timeout" in second_msg

    @pytest.mark.asyncio
    async def test_unknown_action_aborts(self):
        """Unknown action type from LLM causes abort."""
        llm_responses = [json.dumps({"action": "fly_to_moon"})]
        llm = SequentialLLM(llm_responses)
        executor = FakeMCPExecutor()
        agent = MCPLLMAgent(tool_executor=executor, llm_client=llm)

        result = await agent.run()

        assert result["status"] == Status.FAILURE
        assert result["failed_at"] == "find_product"

    @pytest.mark.asyncio
    async def test_markdown_fenced_action(self):
        """LLM response wrapped in markdown code fences is parsed correctly."""
        llm_responses = [
            '```json\n{"action": "call_tool", "tool_name": "find_product", "arguments": {"status": "available"}}\n```',
            _mcp_action("complete"),
        ]
        executor = FakeMCPExecutor()
        llm = SequentialLLM(llm_responses)
        agent = MCPLLMAgent(tool_executor=executor, llm_client=llm)

        result = await agent.run()

        # Markdown fences are parsed correctly (find_product step runs)
        assert "find_product" in result["steps_completed"]
        # But LLM claimed complete with only 1/4 steps done -> failure
        assert result["status"] == Status.FAILURE
        assert result["failed_at"] == "check_inventory"

    @pytest.mark.asyncio
    async def test_simulated_delay_is_zero(self):
        """Orchestration mode always reports simulated_delay_s=0."""
        llm_responses = [_mcp_action("complete")]
        llm = SequentialLLM(llm_responses)
        executor = FakeMCPExecutor()
        agent = MCPLLMAgent(tool_executor=executor, llm_client=llm)

        result = await agent.run()

        assert result["simulated_delay_s"] == 0.0


# ---------------------------------------------------------------------------
# MCPLLMAgent._parse_action tests
# ---------------------------------------------------------------------------

class TestMCPParseAction:
    def test_valid_call_tool(self):
        raw = '{"action": "call_tool", "tool_name": "find_product", "arguments": {"status": "available"}}'
        result = MCPLLMAgent._parse_action(raw)
        assert result["action"] == "call_tool"
        assert result["tool_name"] == "find_product"

    def test_complete(self):
        result = MCPLLMAgent._parse_action('{"action": "complete"}')
        assert result["action"] == "complete"

    def test_abort(self):
        result = MCPLLMAgent._parse_action('{"action": "abort"}')
        assert result["action"] == "abort"

    def test_markdown_fenced(self):
        raw = '```json\n{"action": "complete"}\n```'
        result = MCPLLMAgent._parse_action(raw)
        assert result["action"] == "complete"

    def test_invalid_json_raises(self):
        with pytest.raises((json.JSONDecodeError, ValueError)):
            MCPLLMAgent._parse_action("not json at all")
