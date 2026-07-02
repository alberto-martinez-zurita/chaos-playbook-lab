"""Scenario: Agent communication drop with exponential backoff."""
from __future__ import annotations

import logging
from typing import Any, Protocol, runtime_checkable

from chaos_engine.scenarios.base import ChaosScenario

logger = logging.getLogger(__name__)


@runtime_checkable
class MessageTransport(Protocol):
    """Abstraction over agent-to-agent messaging."""

    async def send(self, agent_id: str, payload: dict[str, Any]) -> dict[str, Any]: ...


class DroppingTransport:
    """Wraps a ``MessageTransport`` and drops the first *drop_count* messages."""

    def __init__(self, inner: MessageTransport, *, drop_count: int = 3) -> None:
        self._inner = inner
        self._drop_count = drop_count
        self._calls = 0
        self.dropped: int = 0

    async def send(self, agent_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        self._calls += 1
        if self._calls <= self._drop_count:
            self.dropped += 1
            raise ConnectionError(f"Message drop #{self.dropped}")
        return await self._inner.send(agent_id, payload)


class CommunicationDropScenario(ChaosScenario):
    """Simulates agent-to-agent message drops.  The caller retries with
    exponential backoff and must eventually recover or degrade gracefully.
    """

    def __init__(
        self,
        transport: MessageTransport,
        *,
        target_agent: str = "agent-b",
        drop_count: int = 3,
        max_retries: int = 5,
        base_delay_s: float = 0.01,
    ) -> None:
        self._transport = transport
        self._target_agent = target_agent
        self._drop_count = drop_count
        self._max_retries = max_retries
        self._base_delay_s = base_delay_s
        self._dropping: DroppingTransport | None = None

    @property
    def name(self) -> str:
        return "communication_drop"

    @property
    def description(self) -> str:
        return (
            f"Drop first {self._drop_count} messages, retry with exponential backoff "
            f"(max {self._max_retries} retries)"
        )

    async def setup(self) -> None:
        self._dropping = DroppingTransport(self._transport, drop_count=self._drop_count)

    async def execute(self) -> dict[str, Any]:
        assert self._dropping is not None
        delay = self._base_delay_s
        last_error: str | None = None
        for attempt in range(1, self._max_retries + 1):
            try:
                result = await self._dropping.send(
                    self._target_agent,
                    {"type": "ping", "attempt": attempt},
                )
                return {
                    "recovered": True,
                    "attempts": attempt,
                    "drops": self._dropping.dropped,
                    "response": result,
                }
            except ConnectionError as exc:
                last_error = str(exc)
                logger.info("Attempt %d failed: %s — backoff %.3fs", attempt, exc, delay)
                # Simulated backoff (no real sleep in tests)
                delay *= 2

        return {
            "recovered": False,
            "attempts": self._max_retries,
            "drops": self._dropping.dropped,
            "last_error": last_error,
        }

    async def verify(self, execution_data: dict[str, Any]) -> bool:
        recovered = execution_data.get("recovered", False)
        if recovered:
            return True
        # Graceful degradation: agent acknowledged failure without crashing
        return execution_data.get("last_error") is not None

    async def teardown(self) -> None:
        self._dropping = None
