"""
A2A Chaos Proxy - Failure injection for Agent-to-Agent communication.

Wraps inter-agent messaging and injects configurable failures
(agent unavailable, task rejected, timeout, corrupt response, auth errors)
using seed-controlled randomness for deterministic chaos scenarios.
"""
from __future__ import annotations

import logging
import random
import uuid
from typing import Any, Dict, List, Optional

from chaos_engine.core.fixtures import MOCK_DATA_BY_ACTION
from chaos_engine.core.types import A2AFailureType, Status


# Error messages per failure type
_A2A_ERROR_MESSAGES: Dict[str, str] = {
    A2AFailureType.AGENT_NOT_FOUND: "Agent '{agent_id}' is not reachable or does not exist",
    A2AFailureType.TASK_REJECTED: "Agent '{agent_id}' rejected the task: capacity exceeded",
    A2AFailureType.TIMEOUT: "Agent '{agent_id}' did not respond within deadline",
    A2AFailureType.CORRUPT_RESPONSE: "Corrupt payload received from agent '{agent_id}'",
    A2AFailureType.PARTIAL_FAILURE: "Agent '{agent_id}' returned partial results before disconnecting",
    A2AFailureType.AUTH_ERROR: "Authentication failed for agent '{agent_id}': invalid credentials",
}

# Task statuses for A2A protocol
_TASK_STATUSES = ["submitted", "working", "completed", "failed", "canceled"]


class A2AChaosProxy:
    """Chaos-injecting proxy for Agent-to-Agent communication.

    Intercepts ``send_task`` and ``query_status`` calls between agents,
    injecting realistic failures based on seed-controlled randomness.

    Satisfies the ``A2AExecutor`` protocol.
    """

    def __init__(
        self,
        failure_rate: float,
        seed: int,
        mock_mode: bool = False,
        failure_types: List[A2AFailureType] | None = None,
        latency_range_ms: tuple[int, int] = (0, 0),
    ) -> None:
        self.failure_rate = failure_rate
        self.rng = random.Random(seed)
        self.mock_mode = mock_mode
        # Only transient errors — agent_not_found, authentication_error, and
        # corrupt_response are permanent and shouldn't resolve on retry.
        self.failure_types = failure_types or [
            A2AFailureType.TIMEOUT,
            A2AFailureType.TASK_REJECTED,
            A2AFailureType.PARTIAL_FAILURE,
        ]
        self.latency_range_ms = latency_range_ms
        self.logger = logging.getLogger("A2AChaosProxy")
        self._task_store: Dict[str, Dict[str, Any]] = {}

    def should_inject(self) -> bool:
        """Return True if chaos should be injected on this call."""
        return self.rng.random() < self.failure_rate

    # ------------------------------------------------------------------
    # A2AExecutor protocol
    # ------------------------------------------------------------------

    async def send_task(
        self,
        agent_id: str,
        task: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Send a task to a remote agent, with possible chaos injection."""

        task_id = str(uuid.UUID(int=self.rng.getrandbits(128), version=4))

        # 1. Chaos check
        if self.should_inject():
            failure = self.rng.choice(self.failure_types)
            msg = _A2A_ERROR_MESSAGES.get(
                failure, "Unknown A2A error"
            ).format(agent_id=agent_id)
            self.logger.info(
                "A2A CHAOS INJECTED: %s on agent '%s'", failure, agent_id,
            )

            response: Dict[str, Any] = {
                "status": Status.ERROR,
                "error_type": str(failure),
                "message": msg,
                "agent_id": agent_id,
                "task_id": task_id,
            }

            # Corrupt response: return mangled data instead of clean error
            if failure == A2AFailureType.CORRUPT_RESPONSE:
                response["data"] = self._generate_corrupt_payload()

            # Partial failure: return truncated results
            if failure == A2AFailureType.PARTIAL_FAILURE:
                response["partial_data"] = {"progress": self.rng.uniform(0.1, 0.9)}

            # Simulated latency (stored, not actually slept — for determinism)
            if self.latency_range_ms != (0, 0):
                response["injected_latency_ms"] = self.rng.randint(*self.latency_range_ms)

            return response

        # 2. Mock mode
        if self.mock_mode:
            self.logger.info("A2A MOCK CALL: task to agent '%s'", agent_id)
            result = self._mock_task_response(agent_id, task_id, task)
            self._task_store[task_id] = result
            return result

        # 3. Real call (delegate to wrapped transport — not yet wired)
        self.logger.warning(
            "A2AChaosProxy: real A2A forwarding not implemented; "
            "returning mock result for agent '%s'",
            agent_id,
        )
        result = self._mock_task_response(agent_id, task_id, task)
        self._task_store[task_id] = result
        return result

    async def query_status(
        self,
        agent_id: str,
        task_id: str,
    ) -> Dict[str, Any]:
        """Query status of a previously sent task, with possible chaos injection."""

        # Chaos check
        if self.should_inject():
            failure = self.rng.choice(self.failure_types)
            msg = _A2A_ERROR_MESSAGES.get(
                failure, "Unknown A2A error"
            ).format(agent_id=agent_id)
            self.logger.info(
                "A2A CHAOS INJECTED on query_status: %s for agent '%s'",
                failure, agent_id,
            )
            return {
                "status": Status.ERROR,
                "error_type": str(failure),
                "message": msg,
                "agent_id": agent_id,
                "task_id": task_id,
            }

        # Return stored task status or unknown
        if task_id in self._task_store:
            return self._task_store[task_id]

        return {
            "status": Status.ERROR,
            "error_type": "task_not_found",
            "message": f"Task '{task_id}' not found for agent '{agent_id}'",
            "agent_id": agent_id,
            "task_id": task_id,
        }

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _mock_task_response(
        self, agent_id: str, task_id: str, task: Dict[str, Any],
    ) -> Dict[str, Any]:
        action = task.get("action", "")
        data = MOCK_DATA_BY_ACTION.get(action, {"result": f"Mock response from agent {agent_id}"})
        return {
            "status": Status.SUCCESS,
            "agent_id": agent_id,
            "task_id": task_id,
            "task_status": "completed",
            "data": data,
        }

    def _generate_corrupt_payload(self) -> Dict[str, Any]:
        """Generate a realistically corrupted JSON payload."""
        return {
            "status": None,
            "data": "\\x00\\xff" * self.rng.randint(1, 5),
            "truncated": True,
            "bytes_received": self.rng.randint(0, 256),
        }
