"""Unit tests for LLMClient and LLMAgent with mocked LLM responses.

The LLMAgent now orchestrates every step via LLM calls (not just recovery),
so these tests verify the turn-based orchestration loop.
"""
from __future__ import annotations

import json
from typing import Any, Optional
from unittest.mock import MagicMock

import pytest

from chaos_engine.agents.llm_agent import LLMAgent, _SYSTEM_PROMPT
from chaos_engine.core.types import Status, WorkflowStep


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class FakeExecutor:
    """Minimal Executor that returns configurable responses per call."""

    def __init__(self, responses: list[dict[str, Any]]) -> None:
        self._responses = list(responses)
        self._call_index = 0
        self.calls: list[tuple[str, str, Any, Any]] = []

    async def send_request(
        self, method: str, endpoint: str,
        params: Optional[dict] = None, json_body: Optional[dict] = None,
    ) -> dict[str, Any]:
        self.calls.append((method, endpoint, params, json_body))
        if self._call_index < len(self._responses):
            resp = self._responses[self._call_index]
            self._call_index += 1
            return resp
        return {"status": Status.SUCCESS, "data": {}}

    def calculate_jittered_backoff(self, delay: float) -> float:
        return 0.0


def _action(action: str, method: str = "", endpoint: str = "",
            params: Any = None, body: Any = None) -> str:
    """Build a JSON action string as the LLM would return."""
    if action == "call_api":
        return json.dumps({
            "action": "call_api",
            "method": method,
            "endpoint": endpoint,
            "params": params,
            "body": body,
        })
    return json.dumps({"action": action})


class SequentialLLM:
    """Fake LLM that returns a pre-configured sequence of responses."""

    def __init__(self, responses: list[str]) -> None:
        self._responses = list(responses)
        self._index = 0
        self.calls: list[tuple[str, str]] = []

    def chat(self, system_prompt: str, user_message: str,
             temperature: float | None = None) -> str:
        self.calls.append((system_prompt, user_message))
        if self._index < len(self._responses):
            resp = self._responses[self._index]
            self._index += 1
            return resp
        return _action("abort")


# ---------------------------------------------------------------------------
# _parse_action tests
# ---------------------------------------------------------------------------

class TestParseAction:
    def test_valid_call_api(self) -> None:
        raw = '{"action": "call_api", "method": "GET", "endpoint": "/store/inventory"}'
        result = LLMAgent._parse_action(raw)
        assert result["action"] == "call_api"
        assert result["method"] == "GET"

    def test_complete(self) -> None:
        result = LLMAgent._parse_action('{"action": "complete"}')
        assert result["action"] == "complete"

    def test_abort(self) -> None:
        result = LLMAgent._parse_action('{"action": "abort"}')
        assert result["action"] == "abort"

    def test_markdown_fenced(self) -> None:
        raw = '```json\n{"action": "complete"}\n```'
        result = LLMAgent._parse_action(raw)
        assert result["action"] == "complete"

    def test_invalid_json_raises(self) -> None:
        with pytest.raises(ValueError, match="No JSON object found"):
            LLMAgent._parse_action("not json at all")


# ---------------------------------------------------------------------------
# LLMAgent.run() integration tests (with fakes)
# ---------------------------------------------------------------------------

class TestLLMAgentRun:
    @pytest.mark.asyncio
    async def test_all_steps_succeed(self) -> None:
        """LLM orchestrates 4 steps, all succeed, then signals complete."""
        llm_responses = [
            _action("call_api", "GET", "/product/find", params={"status": "available"}),
            _action("call_api", "GET", "/store/inventory", params={"productId": "SKU-1234"}),
            _action("call_api", "POST", "/store/order",
                    body={"productId": "SKU-1234", "quantity": 1}),
            _action("call_api", "PUT", "/order/confirm",
                    body={"orderId": "ORD-2026-001"}),
            _action("complete"),
        ]
        api_responses = [
            {"status": Status.SUCCESS, "code": 200, "data": [
                {"id": "SKU-1234", "name": "Widget Pro", "price": 29.99, "status": "available"},
            ]},
            {"status": Status.SUCCESS, "code": 200, "data": {
                "SKU-1234": {"available": 100, "reserved": 5},
            }},
            {"status": Status.SUCCESS, "code": 200, "data": {
                "orderId": "ORD-2026-001", "productId": "SKU-1234", "quantity": 1, "status": "placed",
            }},
            {"status": Status.SUCCESS, "code": 200, "data": {
                "orderId": "ORD-2026-001", "status": "confirmed", "complete": True,
            }},
        ]
        executor = FakeExecutor(api_responses)
        llm = SequentialLLM(llm_responses)
        agent = LLMAgent(tool_executor=executor, llm_client=llm)

        result = await agent.run()

        assert result["status"] == Status.SUCCESS
        assert len(result["steps_completed"]) == 4
        assert result["failed_at"] is None
        # LLM called 5 times: 4 actions + 1 complete
        assert len(llm.calls) == 5

    @pytest.mark.asyncio
    async def test_llm_signals_abort(self) -> None:
        """LLM aborts after a failure instead of retrying."""
        llm_responses = [
            _action("call_api", "GET", "/product/find", params={"status": "available"}),
            _action("abort"),
        ]
        api_responses = [
            {"status": Status.FAILURE, "code": 500, "message": "Internal Server Error"},
        ]
        executor = FakeExecutor(api_responses)
        llm = SequentialLLM(llm_responses)
        agent = LLMAgent(tool_executor=executor, llm_client=llm)

        result = await agent.run()

        assert result["status"] == Status.FAILURE
        assert result["failed_at"] == WorkflowStep.FIND_PRODUCT
        assert WorkflowStep.FIND_PRODUCT not in result["steps_completed"]

    @pytest.mark.asyncio
    async def test_retry_succeeds_on_second_attempt(self) -> None:
        """LLM retries a failed step and succeeds."""
        llm_responses = [
            _action("call_api", "GET", "/product/find", params={"status": "available"}),
            # After failure, LLM retries the same endpoint
            _action("call_api", "GET", "/product/find", params={"status": "available"}),
            _action("call_api", "GET", "/store/inventory", params={"productId": "SKU-1234"}),
            _action("call_api", "POST", "/store/order",
                    body={"productId": "SKU-1234", "quantity": 1}),
            _action("call_api", "PUT", "/order/confirm",
                    body={"orderId": "ORD-2026-001"}),
            _action("complete"),
        ]
        api_responses = [
            {"status": Status.FAILURE, "code": 503, "message": "Service Unavailable"},
            {"status": Status.SUCCESS, "code": 200, "data": [
                {"id": "SKU-1234", "name": "Widget Pro", "status": "available"},
            ]},
            {"status": Status.SUCCESS, "code": 200, "data": {"SKU-1234": {"available": 50}}},
            {"status": Status.SUCCESS, "code": 200, "data": {"orderId": "ORD-2026-001"}},
            {"status": Status.SUCCESS, "code": 200, "data": {"status": "confirmed"}},
        ]
        executor = FakeExecutor(api_responses)
        llm = SequentialLLM(llm_responses)
        agent = LLMAgent(tool_executor=executor, llm_client=llm)

        result = await agent.run()

        assert result["status"] == Status.SUCCESS
        assert len(result["steps_completed"]) == 4
        assert result["retries"] == 1

    @pytest.mark.asyncio
    async def test_llm_parse_error_aborts(self) -> None:
        """When LLM returns unparseable text, agent aborts with failure."""
        llm = SequentialLLM(["this is not json"])
        executor = FakeExecutor([])
        agent = LLMAgent(tool_executor=executor, llm_client=llm)

        result = await agent.run()

        assert result["status"] == Status.FAILURE
        assert result["failed_at"] == WorkflowStep.FIND_PRODUCT

    @pytest.mark.asyncio
    async def test_llm_exception_aborts(self) -> None:
        """When LLM client raises, agent aborts."""
        llm = SequentialLLM([])
        llm.chat = MagicMock(side_effect=RuntimeError("API down"))
        executor = FakeExecutor([])
        agent = LLMAgent(tool_executor=executor, llm_client=llm)

        result = await agent.run()

        assert result["status"] == Status.FAILURE
        assert result["retries"] == 0

    @pytest.mark.asyncio
    async def test_max_turns_reached(self) -> None:
        """Agent stops after max turns with FAILURE."""
        # LLM keeps calling the same endpoint forever
        llm_responses = [
            _action("call_api", "GET", "/product/find", params={"status": "available"})
            for _ in range(20)
        ]
        api_responses = [
            {"status": Status.FAILURE, "code": 503, "message": "Service Unavailable"}
            for _ in range(20)
        ]
        executor = FakeExecutor(api_responses)
        llm = SequentialLLM(llm_responses)
        agent = LLMAgent(tool_executor=executor, llm_client=llm)

        result = await agent.run()

        assert result["status"] == Status.FAILURE
        assert result["failed_at"] is not None

    @pytest.mark.asyncio
    async def test_build_step_body_enriches_order(self) -> None:
        """Place-order body gets productId from find_product data."""
        llm_responses = [
            _action("call_api", "GET", "/product/find", params={"status": "available"}),
            _action("call_api", "GET", "/store/inventory", params={"productId": "SKU-1234"}),
            _action("call_api", "POST", "/store/order",
                    body={"productId": "SKU-1234", "quantity": 1}),
            _action("call_api", "PUT", "/order/confirm",
                    body={"orderId": "ORD-2026-001"}),
            _action("complete"),
        ]
        api_responses = [
            {"status": Status.SUCCESS, "code": 200,
             "data": [{"id": "SKU-9999", "name": "Premium Widget", "status": "available"}]},
            {"status": Status.SUCCESS, "code": 200,
             "data": {"SKU-9999": {"available": 42}}},
            {"status": Status.SUCCESS, "code": 200,
             "data": {"orderId": "ORD-2026-002", "productId": "SKU-9999", "quantity": 1}},
            {"status": Status.SUCCESS, "code": 200,
             "data": {"orderId": "ORD-2026-002", "status": "confirmed"}},
        ]
        executor = FakeExecutor(api_responses)
        llm = SequentialLLM(llm_responses)
        agent = LLMAgent(tool_executor=executor, llm_client=llm)

        result = await agent.run()

        assert result["status"] == Status.SUCCESS
        # Verify the order body was enriched with productId from find_product
        order_call = executor.calls[2]  # 3rd API call = place_order
        assert order_call[3]["productId"] == "SKU-9999"
        # Verify the confirm body was enriched with orderId from place_order
        confirm_call = executor.calls[3]
        assert confirm_call[3]["orderId"] == "ORD-2026-002"

    @pytest.mark.asyncio
    async def test_simulated_delay_is_zero(self) -> None:
        """Orchestration mode always reports simulated_delay_s=0."""
        llm_responses = [
            _action("call_api", "GET", "/product/find", params={"status": "available"}),
            _action("complete"),
        ]
        api_responses = [
            {"status": Status.SUCCESS, "code": 200, "data": {}},
        ]
        executor = FakeExecutor(api_responses)
        llm = SequentialLLM(llm_responses)
        agent = LLMAgent(tool_executor=executor, llm_client=llm)

        result = await agent.run()

        assert result["simulated_delay_s"] == 0.0

    @pytest.mark.asyncio
    async def test_system_prompt_is_sent(self) -> None:
        """Every LLM call receives the system prompt."""
        llm_responses = [_action("complete")]
        llm = SequentialLLM(llm_responses)
        executor = FakeExecutor([])
        agent = LLMAgent(tool_executor=executor, llm_client=llm)

        await agent.run()

        assert len(llm.calls) == 1
        assert llm.calls[0][0] == _SYSTEM_PROMPT


# ---------------------------------------------------------------------------
# LLMClient tests (with mocked openai)
# ---------------------------------------------------------------------------

class TestLLMClientInit:
    def test_init_defaults(self) -> None:
        from chaos_engine.agents.llm_client import LLMClient

        client = LLMClient(provider="zhipuai")
        assert client.provider == "zhipuai"
        assert client.model == "glm-4.5"

    def test_openai_provider(self) -> None:
        from chaos_engine.agents.llm_client import LLMClient

        client = LLMClient(provider="openai")
        assert client.model == "gpt-4o"

    def test_custom_model(self) -> None:
        from chaos_engine.agents.llm_client import LLMClient

        client = LLMClient(provider="openai", model="gpt-4o-mini")
        assert client.model == "gpt-4o-mini"
