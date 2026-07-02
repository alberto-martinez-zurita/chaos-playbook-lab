"""
Resilience Utilities - Circuit Breaker Implementation.
"""
from __future__ import annotations

import logging
import time
from typing import Any, Dict, Optional

from chaos_engine.core.protocols import Executor
from chaos_engine.core.types import Status


class CircuitBreakerProxy:
    """
    Implements the Circuit Breaker pattern to protect the downstream service.

    If the number of consecutive failures exceeds the threshold, the circuit opens.
    """

    def __init__(self, wrapped_executor: Executor, failure_threshold: int = 5, cooldown_seconds: int = 60):
        self._executor = wrapped_executor
        self._failure_threshold = failure_threshold
        self._cooldown_seconds = cooldown_seconds

        # Circuit state
        self._failures = 0
        self._is_open = False
        self._half_open = False
        self._opened_timestamp = 0.0
        self.logger = logging.getLogger("CircuitBreaker")

    def calculate_jittered_backoff(self, seconds: float) -> float:
        """Delegates the jitter calculation to the wrapped executor (e.g., ChaosProxy)."""
        if hasattr(self._executor, "calculate_jittered_backoff"):
            return self._executor.calculate_jittered_backoff(seconds)
        # Fallback if the wrapped executor does not have the method.
        return seconds

    async def send_request(self, method: str, endpoint: str, params: Optional[Dict] = None, json_body: Optional[Dict] = None) -> Dict[str, Any]:

        # 1. OPEN STATE (Protection)
        if self._is_open:
            if time.time() < self._opened_timestamp + self._cooldown_seconds:
                self.logger.warning("CIRCUIT OPEN: Request to %s blocked (Cooldown active).", endpoint)
                return {"status": Status.ERROR, "code": 503, "message": "Circuit Breaker Open: Service is down."}
            else:
                # Transition to Half-Open: allow exactly one probe request.
                self._half_open = True
                self._is_open = False
                self.logger.info("CIRCUIT HALF-OPEN: Allowing one probe request.")
                from chaos_engine.core.metrics import CIRCUIT_STATE
                CIRCUIT_STATE.set(2)  # half-open

        # 1b. HALF-OPEN guard: only one request allowed
        if self._half_open:
            response = await self._executor.send_request(method, endpoint, params, json_body)
            if response.get("status") == Status.ERROR:
                # Probe failed — reopen with fresh cooldown
                self._half_open = False
                self._is_open = True
                self._opened_timestamp = time.time()
                self.logger.warning("CIRCUIT RE-OPENED: Probe request failed on %s.", endpoint)
                from chaos_engine.core.metrics import CIRCUIT_STATE
                CIRCUIT_STATE.set(1)  # open
            else:
                # Probe succeeded — fully close
                self._half_open = False
                self._failures = 0
                self.logger.info("CIRCUIT CLOSED: Probe request succeeded.")
                from chaos_engine.core.metrics import CIRCUIT_STATE
                CIRCUIT_STATE.set(0)  # closed
            return response

        # 2. CLOSED STATE: Normal request execution
        response = await self._executor.send_request(method, endpoint, params, json_body)

        # 3. State Handling
        if response.get("status") == Status.ERROR:
            self._handle_failure()
        else:
            self._handle_success()

        return response

    def _handle_failure(self) -> None:
        self._failures += 1
        self.logger.debug("Failure count: %d/%d", self._failures, self._failure_threshold)
        if self._failures >= self._failure_threshold:
            self._is_open = True
            self._opened_timestamp = time.time()
            from chaos_engine.core.metrics import CIRCUIT_STATE
            CIRCUIT_STATE.set(1)  # open
            self.logger.critical(
                "CIRCUIT OPENED: %d consecutive failures. Cooldown for %ds.",
                self._failure_threshold,
                self._cooldown_seconds,
            )

    def _handle_success(self) -> None:
        if self._failures > 0:
            self.logger.info("CIRCUIT RESET: Successful request.")
            self._failures = 0
            self._is_open = False