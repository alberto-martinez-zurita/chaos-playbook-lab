"""Tests for the 7 critical chaos scenarios (BK-005).

>= 14 tests: 2 per scenario + composition test.
"""
from __future__ import annotations

from typing import Any

import pytest

from chaos_engine.scenarios.base import ChaosScenario, ScenarioResult
from chaos_engine.scenarios.communication_drop import (
    CommunicationDropScenario,
    DroppingTransport,
)
from chaos_engine.scenarios.infinite_reflection import InfiniteReflectionScenario
from chaos_engine.scenarios.instruction_drift import (
    InstructionDriftScenario,
    _simple_drift_score,
)
from chaos_engine.scenarios.malformed_json import MalformedJSONScenario, MalformationType
from chaos_engine.scenarios.tool_timeout import ToolTimeoutScenario
from chaos_engine.scenarios.tool_unavailability import ToolUnavailabilityScenario


# ---------------------------------------------------------------------------
# Stub agents / transports used across tests
# ---------------------------------------------------------------------------

class _StubAgentHandler:
    """Handles context overflow by returning success."""

    async def handle(self, messages: list[dict[str, str]]) -> dict[str, Any]:
        return {"status": "truncated", "kept": min(len(messages), 10)}


class _CrashingAgentHandler:
    """Always crashes."""

    async def handle(self, messages: list[dict[str, str]]) -> dict[str, Any]:
        raise RuntimeError("out of memory")


class _StubTransport:
    """Simple transport that echoes back."""

    async def send(self, agent_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        return {"status": "ok", "echo": payload}


class _AlwaysFailTransport:
    """Transport that always raises."""

    async def send(self, agent_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        raise ConnectionError("network down")


class _StubDriftAgent:
    """Returns the system prompt keywords to show no drift."""

    async def respond(self, system_prompt: str, messages: list[dict[str, str]]) -> str:
        return f"I am a helpful assistant that answers math questions. {messages[-1]['content']}"


class _DriftingAgent:
    """Drifts completely: ignores system prompt."""

    async def respond(self, system_prompt: str, messages: list[dict[str, str]]) -> str:
        return "Arrr, I be a pirate now!"


class _StubToolCaller:
    async def call_tool(self, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        return {"status": "ok", "result": 42}


class _StubJSONConsumer:
    """Handles any JSON string gracefully."""

    async def process_json(self, raw: str) -> dict[str, Any]:
        import json

        try:
            data = json.loads(raw) if raw else {}
        except (json.JSONDecodeError, UnicodeDecodeError):
            data = {}
        return {"status": "fallback", "parsed": data}


class _CrashingJSONConsumer:
    """Crashes on bad JSON."""

    async def process_json(self, raw: str) -> dict[str, Any]:
        import json

        return json.loads(raw)  # will raise on bad input


class _StubReflectiveAgent:
    """Returns a slightly modified string each time."""

    def __init__(self) -> None:
        self._counter = 0

    async def reflect(self, context: str) -> str:
        self._counter += 1
        return f"reflection-{self._counter}: {context[:30]}"


class _StubToolDependentAgent:
    """Reports inability honestly when tools are unavailable."""

    async def execute_task(self, task: str, tools: dict[str, Any]) -> dict[str, Any]:
        # Try each tool, collect errors
        errors = []
        for name, proxy in tools.items():
            result = await proxy.call(name, {})
            if result.get("status") == "error":
                errors.append(result["message"])
        if errors:
            return {"message": "Sorry, I'm unable to complete this task. Tools are unavailable."}
        return {"message": "Here is the result: 25C and sunny"}


class _HallucinatingAgent:
    """Ignores tool errors and hallucinates."""

    async def execute_task(self, task: str, tools: dict[str, Any]) -> dict[str, Any]:
        return {"message": "Here is the result: it is 25C and sunny in Tokyo."}


# ===================================================================
# 1. Communication Drop
# ===================================================================

@pytest.mark.asyncio
async def test_communication_drop_recovery() -> None:
    scenario = CommunicationDropScenario(
        _StubTransport(), drop_count=2, max_retries=5, base_delay_s=0.001,
    )
    result = await scenario.run()
    assert result.passed is True
    data = result.details["execution_data"]
    assert data["recovered"] is True
    assert data["attempts"] == 3  # first 2 dropped, 3rd succeeds


@pytest.mark.asyncio
async def test_communication_drop_all_fail() -> None:
    scenario = CommunicationDropScenario(
        _AlwaysFailTransport(), drop_count=0, max_retries=3, base_delay_s=0.001,
    )
    result = await scenario.run()
    # Still passes because graceful degradation (last_error is set)
    assert result.passed is True
    data = result.details["execution_data"]
    assert data["recovered"] is False


# ===================================================================
# 3. Instruction Drift
# ===================================================================

@pytest.mark.asyncio
async def test_instruction_drift_stable_agent() -> None:
    scenario = InstructionDriftScenario(
        _StubDriftAgent(), rounds=3, max_acceptable_drift=0.7,
    )
    result = await scenario.run()
    assert result.passed is True


@pytest.mark.asyncio
async def test_instruction_drift_drifting_agent() -> None:
    scenario = InstructionDriftScenario(
        _DriftingAgent(), rounds=3, max_acceptable_drift=0.3,
    )
    result = await scenario.run()
    assert result.passed is False


def test_drift_score_no_drift() -> None:
    score = _simple_drift_score("helpful assistant math", "I am a helpful assistant for math")
    assert score < 0.5


def test_drift_score_total_drift() -> None:
    score = _simple_drift_score("helpful assistant math questions", "arrr pirate now")
    assert score > 0.5


# ===================================================================
# 4. Tool Timeout
# ===================================================================

@pytest.mark.asyncio
async def test_tool_timeout_fires() -> None:
    scenario = ToolTimeoutScenario(
        _StubToolCaller(), delay_s=0.2, timeout_s=0.05,
    )
    result = await scenario.run()
    assert result.passed is True
    assert result.details["execution_data"]["timed_out"] is True


@pytest.mark.asyncio
async def test_tool_timeout_no_timeout() -> None:
    scenario = ToolTimeoutScenario(
        _StubToolCaller(), delay_s=0.01, timeout_s=1.0,
    )
    result = await scenario.run()
    assert result.passed is True
    assert result.details["execution_data"]["timed_out"] is False


# ===================================================================
# 5. Malformed JSON
# ===================================================================

@pytest.mark.asyncio
async def test_malformed_json_graceful() -> None:
    scenario = MalformedJSONScenario(_StubJSONConsumer())
    result = await scenario.run()
    assert result.passed is True
    assert result.scenario_name == "malformed_json"


@pytest.mark.asyncio
async def test_malformed_json_crash_detected() -> None:
    scenario = MalformedJSONScenario(
        _CrashingJSONConsumer(),
        malformations=[MalformationType.TRUNCATED, MalformationType.EMPTY],
    )
    result = await scenario.run()
    assert result.passed is False


# ===================================================================
# 6. Infinite Reflection
# ===================================================================

@pytest.mark.asyncio
async def test_infinite_reflection_breaker_trips() -> None:
    scenario = InfiniteReflectionScenario(
        _StubReflectiveAgent(), max_iterations=5,
    )
    result = await scenario.run()
    assert result.passed is True
    data = result.details["execution_data"]
    assert data["breaker_tripped"] is True
    assert data["outputs_count"] == 5


@pytest.mark.asyncio
async def test_infinite_reflection_high_limit() -> None:
    scenario = InfiniteReflectionScenario(
        _StubReflectiveAgent(), max_iterations=20,
    )
    result = await scenario.run()
    assert result.passed is True
    assert result.details["execution_data"]["outputs_count"] == 20


# ===================================================================
# 7. Tool Unavailability
# ===================================================================

@pytest.mark.asyncio
async def test_tool_unavailability_honest_agent() -> None:
    scenario = ToolUnavailabilityScenario(_StubToolDependentAgent())
    result = await scenario.run()
    assert result.passed is True


@pytest.mark.asyncio
async def test_tool_unavailability_hallucinating_agent() -> None:
    scenario = ToolUnavailabilityScenario(_HallucinatingAgent())
    result = await scenario.run()
    assert result.passed is False


# ===================================================================
# Composition / sequential run
# ===================================================================

@pytest.mark.asyncio
async def test_scenarios_compose_sequentially() -> None:
    """Run multiple scenarios in sequence and collect results."""
    scenarios: list[ChaosScenario] = [
        CommunicationDropScenario(_StubTransport(), drop_count=1, max_retries=3, base_delay_s=0.001),
        InfiniteReflectionScenario(_StubReflectiveAgent(), max_iterations=3),
    ]
    results: list[ScenarioResult] = []
    for s in scenarios:
        results.append(await s.run())

    assert len(results) == 2
    assert all(r.passed for r in results)
    names = [r.scenario_name for r in results]
    assert names == ["communication_drop", "infinite_reflection"]
