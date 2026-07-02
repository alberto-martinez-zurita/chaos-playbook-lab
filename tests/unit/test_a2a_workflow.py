"""Unit tests for A2ABaselineAgent and A2ALLMAgent."""
from __future__ import annotations

import json
from typing import Any, Dict, Optional

import pytest

from chaos_engine.agents.a2a_workflow import (
    A2ABaselineAgent,
    A2ALLMAgent,
    A2A_WORKFLOW_STEPS,
    WORKER_AGENT_ID,
)
from chaos_engine.core.types import A2AFailureType, Status


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------

class FakeA2AExecutor:
    """Fake A2AExecutor with configurable responses."""

    def __init__(
        self,
        call_sequence: list[dict[str, Any]] | None = None,
    ) -> None:
        self._call_sequence = list(call_sequence) if call_sequence else None
        self._call_index = 0
        self.calls: list[tuple[str, dict]] = []

    async def send_task(
        self, agent_id: str, task: Dict[str, Any],
    ) -> Dict[str, Any]:
        self.calls.append((agent_id, task))
        if self._call_sequence is not None:
            if self._call_index < len(self._call_sequence):
                resp = self._call_sequence[self._call_index]
                self._call_index += 1
                return resp
        return {"status": Status.SUCCESS, "data": {"result": "ok"}}

    async def query_status(
        self, agent_id: str, task_id: str,
    ) -> Dict[str, Any]:
        return {"status": Status.SUCCESS}


def _a2a_action(
    action: str,
    agent_id: str = "worker-b",
    task: dict[str, Any] | None = None,
) -> str:
    """Build a JSON action string as the LLM would return for A2A."""
    if action == "send_task":
        return json.dumps({
            "action": "send_task",
            "agent_id": agent_id,
            "task": task,
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
        return _a2a_action("abort")


# ---------------------------------------------------------------------------
# A2ABaselineAgent tests
# ---------------------------------------------------------------------------

class TestA2ABaselineAgent:
    @pytest.mark.asyncio
    async def test_all_steps_succeed(self):
        executor = FakeA2AExecutor()
        agent = A2ABaselineAgent(a2a_executor=executor)
        result = await agent.run()

        assert result["status"] == Status.SUCCESS
        assert len(result["steps_completed"]) == 4
        assert result["failed_at"] is None

    @pytest.mark.asyncio
    async def test_first_step_fails(self):
        executor = FakeA2AExecutor(call_sequence=[
            {"status": Status.ERROR, "error_type": A2AFailureType.AGENT_NOT_FOUND},
        ])
        agent = A2ABaselineAgent(a2a_executor=executor)
        result = await agent.run()

        assert result["status"] == Status.FAILURE
        assert result["failed_at"] == "find_product"
        assert result["steps_completed"] == []

    @pytest.mark.asyncio
    async def test_second_step_fails(self):
        executor = FakeA2AExecutor(call_sequence=[
            {"status": Status.SUCCESS, "data": {"products": [{"id": "SKU-1234"}]}},
            {"status": Status.ERROR, "error_type": A2AFailureType.TASK_REJECTED},
        ])
        agent = A2ABaselineAgent(a2a_executor=executor)
        result = await agent.run()

        assert result["status"] == Status.FAILURE
        assert result["failed_at"] == "check_inventory"
        assert result["steps_completed"] == ["find_product"]

    @pytest.mark.asyncio
    async def test_third_step_fails(self):
        executor = FakeA2AExecutor(call_sequence=[
            {"status": Status.SUCCESS, "data": {}},
            {"status": Status.SUCCESS, "data": {}},
            {"status": Status.ERROR, "error_type": A2AFailureType.TIMEOUT},
        ])
        agent = A2ABaselineAgent(a2a_executor=executor)
        result = await agent.run()

        assert result["status"] == Status.FAILURE
        assert result["failed_at"] == "place_order"
        assert len(result["steps_completed"]) == 2

    @pytest.mark.asyncio
    async def test_fourth_step_fails(self):
        executor = FakeA2AExecutor(call_sequence=[
            {"status": Status.SUCCESS, "data": {}},
            {"status": Status.SUCCESS, "data": {}},
            {"status": Status.SUCCESS, "data": {}},
            {"status": Status.ERROR, "error_type": A2AFailureType.TIMEOUT},
        ])
        agent = A2ABaselineAgent(a2a_executor=executor)
        result = await agent.run()

        assert result["status"] == Status.FAILURE
        assert result["failed_at"] == "confirm_order"
        assert len(result["steps_completed"]) == 3

    @pytest.mark.asyncio
    async def test_sends_to_correct_agent(self):
        executor = FakeA2AExecutor()
        agent = A2ABaselineAgent(a2a_executor=executor)
        await agent.run()

        assert all(agent_id == WORKER_AGENT_ID for agent_id, _ in executor.calls)
        assert len(executor.calls) == 4

    @pytest.mark.asyncio
    async def test_zero_retries(self):
        executor = FakeA2AExecutor(call_sequence=[
            {"status": Status.ERROR, "error_type": A2AFailureType.TIMEOUT},
        ])
        agent = A2ABaselineAgent(a2a_executor=executor)
        result = await agent.run()

        assert result["retries"] == 0


# ---------------------------------------------------------------------------
# A2ALLMAgent tests
# ---------------------------------------------------------------------------

class TestA2ALLMAgent:
    @pytest.mark.asyncio
    async def test_all_steps_succeed(self):
        """LLM orchestrates 4 delegations, all succeed, then signals complete."""
        llm_responses = [
            _a2a_action("send_task", task={
                "action": "find_product", "status": "available",
            }),
            _a2a_action("send_task", task={
                "action": "check_inventory", "productId": "SKU-1234",
            }),
            _a2a_action("send_task", task={
                "action": "place_order", "productId": "SKU-1234", "quantity": 1,
            }),
            _a2a_action("send_task", task={
                "action": "confirm_order", "orderId": "ORD-2026-001",
            }),
            _a2a_action("complete"),
        ]
        executor = FakeA2AExecutor()
        llm = SequentialLLM(llm_responses)
        agent = A2ALLMAgent(a2a_executor=executor, llm_client=llm)

        result = await agent.run()

        assert result["status"] == Status.SUCCESS
        assert result["steps_completed"] == [
            "find_product", "check_inventory", "place_order", "confirm_order",
        ]
        assert result["failed_at"] is None
        # LLM called 5 times: 4 delegations + 1 complete
        assert len(llm.calls) == 5

    @pytest.mark.asyncio
    async def test_failure_and_abort(self):
        """LLM aborts after a delegation failure."""
        llm_responses = [
            _a2a_action("send_task", task={
                "action": "find_product", "status": "available",
            }),
            _a2a_action("abort"),
        ]
        executor = FakeA2AExecutor(call_sequence=[
            {"status": Status.ERROR, "error_type": A2AFailureType.TIMEOUT},
        ])
        llm = SequentialLLM(llm_responses)
        agent = A2ALLMAgent(a2a_executor=executor, llm_client=llm)

        result = await agent.run()

        assert result["status"] == Status.FAILURE
        assert result["failed_at"] == "find_product"
        assert result["steps_completed"] == []
        assert len(llm.calls) == 2

    @pytest.mark.asyncio
    async def test_retry_on_failure(self):
        """LLM retries a failed delegation and succeeds."""
        llm_responses = [
            _a2a_action("send_task", task={
                "action": "find_product", "status": "available",
            }),
            # First attempt fails, LLM retries same task
            _a2a_action("send_task", task={
                "action": "find_product", "status": "available",
            }),
            _a2a_action("send_task", task={
                "action": "check_inventory", "productId": "SKU-1234",
            }),
            _a2a_action("send_task", task={
                "action": "place_order", "productId": "SKU-1234", "quantity": 1,
            }),
            _a2a_action("send_task", task={
                "action": "confirm_order", "orderId": "ORD-2026-001",
            }),
            _a2a_action("complete"),
        ]
        executor = FakeA2AExecutor(call_sequence=[
            {"status": Status.ERROR, "error_type": A2AFailureType.TIMEOUT},
            {"status": Status.SUCCESS, "data": {"available": True}},
            {"status": Status.SUCCESS, "data": {"in_stock": True}},
            {"status": Status.SUCCESS, "data": {"placed": True}},
            {"status": Status.SUCCESS, "data": {"confirmed": True}},
        ])
        llm = SequentialLLM(llm_responses)
        agent = A2ALLMAgent(a2a_executor=executor, llm_client=llm)

        result = await agent.run()

        assert result["status"] == Status.SUCCESS
        assert result["steps_completed"] == [
            "find_product", "check_inventory", "place_order", "confirm_order",
        ]
        assert result["retries"] == 1
        assert len(llm.calls) == 6

    @pytest.mark.asyncio
    async def test_max_turns_exceeded(self):
        """LLM never signals complete -- hits max turns."""
        # Build 12 identical send_task actions (agent keeps retrying same task)
        llm_responses = [
            _a2a_action("send_task", task={
                "action": "find_product", "status": "available",
            })
            for _ in range(12)
        ]
        # All calls fail
        executor = FakeA2AExecutor(call_sequence=[
            {"status": Status.ERROR, "error_type": A2AFailureType.TIMEOUT}
            for _ in range(12)
        ])
        llm = SequentialLLM(llm_responses)
        agent = A2ALLMAgent(a2a_executor=executor, llm_client=llm)

        result = await agent.run()

        assert result["status"] == Status.FAILURE
        assert result["failed_at"] == "find_product"
        assert len(llm.calls) == 12

    @pytest.mark.asyncio
    async def test_sends_to_worker_b(self):
        """Executor receives the correct agent_id and task payloads."""
        llm_responses = [
            _a2a_action("send_task", task={
                "action": "find_product", "status": "available",
            }),
            _a2a_action("complete"),
        ]
        executor = FakeA2AExecutor()
        llm = SequentialLLM(llm_responses)
        agent = A2ALLMAgent(a2a_executor=executor, llm_client=llm)

        await agent.run()

        assert len(executor.calls) == 1
        agent_id, task = executor.calls[0]
        assert agent_id == "worker-b"
        assert task["action"] == "find_product"

    @pytest.mark.asyncio
    async def test_parse_error_aborts(self):
        """Unparseable LLM response causes immediate failure."""
        llm = SequentialLLM(["this is not json"])
        executor = FakeA2AExecutor()
        agent = A2ALLMAgent(a2a_executor=executor, llm_client=llm)

        result = await agent.run()

        assert result["status"] == Status.FAILURE
        assert result["failed_at"] == "find_product"
        assert len(executor.calls) == 0


# ---------------------------------------------------------------------------
# A2ALLMAgent._parse_action tests
# ---------------------------------------------------------------------------

class TestA2AParseAction:
    def test_valid_json(self):
        raw = '{"action": "send_task", "agent_id": "worker-b", "task": {"action": "find_product"}}'
        result = A2ALLMAgent._parse_action(raw)
        assert result["action"] == "send_task"
        assert result["agent_id"] == "worker-b"

    def test_markdown_fenced(self):
        raw = '```json\n{"action": "complete"}\n```'
        result = A2ALLMAgent._parse_action(raw)
        assert result["action"] == "complete"

    def test_abort_action(self):
        raw = '{"action": "abort"}'
        result = A2ALLMAgent._parse_action(raw)
        assert result["action"] == "abort"

    def test_invalid_json_raises(self):
        with pytest.raises(Exception):
            A2ALLMAgent._parse_action("not json at all")
