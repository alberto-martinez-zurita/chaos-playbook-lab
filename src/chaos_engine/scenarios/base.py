"""Base classes for chaos scenarios."""
from __future__ import annotations

import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class ScenarioResult:
    """Result of executing a chaos scenario."""

    scenario_name: str
    passed: bool
    details: dict[str, Any] = field(default_factory=dict)
    duration_ms: float = 0.0


class ChaosScenario(ABC):
    """Abstract base class for all chaos scenarios.

    Subclasses implement the four lifecycle methods: setup, execute, verify,
    teardown.  The ``run`` convenience method orchestrates them and returns a
    ``ScenarioResult``.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable scenario identifier."""
        ...

    @property
    @abstractmethod
    def description(self) -> str:
        """One-line description of what this scenario tests."""
        ...

    @abstractmethod
    async def setup(self) -> None:
        """Prepare environment / inject faults."""
        ...

    @abstractmethod
    async def execute(self) -> dict[str, Any]:
        """Run the scenario and return raw output data."""
        ...

    @abstractmethod
    async def verify(self, execution_data: dict[str, Any]) -> bool:
        """Return True when the agent handled the scenario correctly."""
        ...

    @abstractmethod
    async def teardown(self) -> None:
        """Clean up after the scenario."""
        ...

    # ------------------------------------------------------------------
    async def run(self) -> ScenarioResult:
        """Orchestrate the full scenario lifecycle."""
        start = time.monotonic()
        details: dict[str, Any] = {}
        passed = False
        try:
            await self.setup()
            execution_data = await self.execute()
            details["execution_data"] = execution_data
            passed = await self.verify(execution_data)
        except Exception as exc:  # noqa: BLE001
            logger.exception("Scenario %s failed with exception", self.name)
            details["error"] = str(exc)
            passed = False
        finally:
            try:
                await self.teardown()
            except Exception:  # noqa: BLE001
                logger.exception("Teardown error for %s", self.name)
        duration_ms = (time.monotonic() - start) * 1000
        return ScenarioResult(
            scenario_name=self.name,
            passed=passed,
            details=details,
            duration_ms=duration_ms,
        )
