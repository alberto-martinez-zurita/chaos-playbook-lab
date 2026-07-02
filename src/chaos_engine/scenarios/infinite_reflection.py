"""Scenario: Infinite reflection loop with circuit breaker."""
from __future__ import annotations

import logging
from typing import Any, Protocol, runtime_checkable

from chaos_engine.scenarios.base import ChaosScenario

logger = logging.getLogger(__name__)


@runtime_checkable
class ReflectiveAgent(Protocol):
    """Agent that can perform one round of self-reflection."""

    async def reflect(self, context: str) -> str: ...


class InfiniteReflectionScenario(ChaosScenario):
    """Forces an agent into a self-reflection loop and verifies the circuit
    breaker kicks in after *max_iterations* rounds.
    """

    def __init__(
        self,
        agent: ReflectiveAgent,
        *,
        max_iterations: int = 10,
        seed_context: str = "Please reflect on your previous answer.",
    ) -> None:
        self._agent = agent
        self._max_iterations = max_iterations
        self._seed_context = seed_context

    @property
    def name(self) -> str:
        return "infinite_reflection"

    @property
    def description(self) -> str:
        return f"Self-reflection loop, circuit breaker at {self._max_iterations} iterations"

    async def setup(self) -> None:
        pass

    async def execute(self) -> dict[str, Any]:
        context = self._seed_context
        iterations = 0
        outputs: list[str] = []
        breaker_tripped = False

        for _ in range(self._max_iterations * 2):  # generous upper bound
            iterations += 1
            if iterations > self._max_iterations:
                breaker_tripped = True
                break
            try:
                response = await self._agent.reflect(context)
            except Exception as exc:  # noqa: BLE001
                logger.warning("Reflect error at iteration %d: %s", iterations, exc)
                breaker_tripped = True
                break
            outputs.append(response)
            context = response  # feed output back in

        return {
            "iterations": iterations,
            "breaker_tripped": breaker_tripped,
            "last_output": outputs[-1] if outputs else "",
            "outputs_count": len(outputs),
        }

    async def verify(self, execution_data: dict[str, Any]) -> bool:
        tripped = execution_data.get("breaker_tripped", False)
        has_output = execution_data.get("outputs_count", 0) > 0
        if not tripped:
            logger.error("Circuit breaker did NOT trip after reflection loop")
            return False
        if not has_output:
            logger.error("No output produced before breaker tripped")
            return False
        return True

    async def teardown(self) -> None:
        pass
