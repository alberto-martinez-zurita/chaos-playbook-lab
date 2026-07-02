"""
DeterministicAgent - LLM-free workflow engine for parametric simulation.

Executes the same 4-step Petstore workflow as PetstoreAgent but replaces
LLM reasoning with deterministic strategy execution. Uses the real
infrastructure stack: ChaosProxy, CircuitBreakerProxy, and playbook lookup.
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Any, Dict, Final, Optional, Tuple

from chaos_engine.core.fixtures import ORDER_ID, PRODUCT_ID
from chaos_engine.core.protocols import Executor
from chaos_engine.core.types import (
    ApiResponse,
    ExperimentResult,
    RetryStrategy,
    Status,
    WorkflowStep,
)


# Step definition: (step_name, playbook_tool_name, http_method, endpoint, params, json_body)
# Unified order workflow matching LLM agents.
WORKFLOW_STEPS: Final[tuple[
    tuple[str, str, str, str, Optional[Dict], Optional[Dict]], ...
]] = (
    (WorkflowStep.FIND_PRODUCT, WorkflowStep.FIND_PRODUCT, "GET", "/product/find", {"status": "available"}, None),
    (WorkflowStep.CHECK_INVENTORY, WorkflowStep.CHECK_INVENTORY, "GET", "/store/inventory", {"productId": PRODUCT_ID}, None),
    (WorkflowStep.PLACE_ORDER, WorkflowStep.PLACE_ORDER, "POST", "/store/order",
     None, {"productId": PRODUCT_ID, "quantity": 1}),
    (WorkflowStep.CONFIRM_ORDER, WorkflowStep.CONFIRM_ORDER, "PUT", "/order/confirm",
     None, {"orderId": ORDER_ID}),
)


class DeterministicAgent:
    """
    Deterministic workflow engine that mirrors PetstoreAgent behavior
    without LLM calls. Uses real ChaosProxy + CircuitBreakerProxy + playbook.
    """

    def __init__(
        self,
        tool_executor: Executor,
        playbook_path: str,
        verbose: bool = False,
        simulate_delays: bool = False,
    ):
        self.executor = tool_executor
        self.playbook_data = self._load_playbook(playbook_path)
        self.verbose = verbose
        self.simulate_delays = simulate_delays
        self.logger = logging.getLogger("DeterministicAgent")

    @staticmethod
    def _load_playbook(path: str) -> Dict:
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            logging.getLogger("DeterministicAgent").warning("Error loading playbook %s", path, exc_info=True)
            return {}

    async def run(self) -> ExperimentResult:
        """Execute the 4-step workflow. Returns result compatible with ABTestRunner."""
        start_time = time.time()
        steps_completed: list[str] = []
        failed_at: str | None = None
        total_retries = 0
        total_simulated_delay = 0.0
        # Data chaining: store response data from previous steps for real API mode
        step_data: Dict[str, Any] = {}

        for step_name, tool_name, method, endpoint, params, json_body in WORKFLOW_STEPS:
            # Build dynamic body using data from previous steps
            actual_body = self._build_step_body(step_name, json_body, step_data)

            result, retries, simulated_delay = await self._execute_step(
                tool_name, method, endpoint, params, actual_body
            )
            total_retries += retries
            total_simulated_delay += simulated_delay

            if result.get("status") == Status.SUCCESS:
                steps_completed.append(step_name)
                step_data[step_name] = result.get("data", {})
            else:
                failed_at = step_name
                break

        duration_s = time.time() - start_time
        duration_ms = duration_s * 1000
        status = Status.SUCCESS if failed_at is None else Status.FAILURE

        from chaos_engine.core.metrics import EXPERIMENT_DURATION, RETRIES_TOTAL
        EXPERIMENT_DURATION.labels(agent_type="deterministic").observe(duration_s)
        if total_retries > 0:
            RETRIES_TOTAL.labels(agent_type="deterministic").inc(total_retries)

        return ExperimentResult(
            status=status,
            steps_completed=steps_completed,
            failed_at=failed_at,
            duration_ms=duration_ms,
            retries=total_retries,
            simulated_delay_s=round(total_simulated_delay, 3),
            outcome=status,
            agent_type="",
        )

    @staticmethod
    def _build_step_body(
        step_name: str,
        template_body: Optional[Dict],
        step_data: Dict[str, Any],
    ) -> Optional[Dict]:
        """Build request body using data from previous workflow steps.

        In mock mode, step_data values match the hardcoded mock responses
        so this is a no-op. In real API mode, it chains actual response data
        (e.g. real productId from find_product into place_order and confirm_order).
        """
        if template_body is None:
            return None

        body = dict(template_body)

        # Extract product ID from find_product response
        products_data = step_data.get(WorkflowStep.FIND_PRODUCT)
        if products_data and isinstance(products_data, list) and len(products_data) > 0:
            product_id = products_data[0].get("id", PRODUCT_ID)
        else:
            product_id = PRODUCT_ID

        # Extract order ID from place_order response
        order_data = step_data.get(WorkflowStep.PLACE_ORDER)
        order_id = order_data.get("orderId", ORDER_ID) if order_data else ORDER_ID

        if step_name == WorkflowStep.PLACE_ORDER:
            body["productId"] = product_id
        elif step_name == WorkflowStep.CONFIRM_ORDER:
            body["orderId"] = order_id

        return body

    async def _execute_step(
        self, tool_name: str, method: str, endpoint: str,
        params: Optional[Dict], json_body: Optional[Dict],
    ) -> Tuple[Dict, int, float]:
        """Execute a single step with playbook-driven recovery. Returns (result, retries, simulated_delay)."""

        result = await self.executor.send_request(method, endpoint, params, json_body)

        if result.get("status") == Status.SUCCESS:
            return result, 0, 0.0

        # Error path — consult playbook
        error_code = str(result.get("code", 500))
        strategy_entry = self._resolve_strategy(tool_name, error_code)
        strategy = strategy_entry.get("strategy", RetryStrategy.FAIL_FAST)
        config = strategy_entry.get("config", {})

        from chaos_engine.core.metrics import STRATEGY_USED
        STRATEGY_USED.labels(strategy=strategy).inc()

        if self.verbose:
            self.logger.info(
                "  [%s] Error %s -> strategy: %s", tool_name, error_code, strategy
            )

        if strategy in (RetryStrategy.FAIL_FAST, RetryStrategy.ESCALATE_TO_HUMAN):
            return result, 0, 0.0

        return await self._retry_with_strategy(
            strategy, config, method, endpoint, params, json_body
        )

    def _resolve_strategy(self, tool_name: str, error_code: str) -> Dict[str, Any]:
        """Lookup playbook by tool_name + error_code, fallback to default."""
        tool_config = self.playbook_data.get(tool_name, {})
        entry = tool_config.get(error_code)
        if entry:
            return entry
        default = self.playbook_data.get("default")
        if default:
            return default
        return {"strategy": RetryStrategy.FAIL_FAST, "config": {}}

    async def _retry_with_strategy(
        self, strategy: str, config: Dict,
        method: str, endpoint: str,
        params: Optional[Dict], json_body: Optional[Dict],
    ) -> Tuple[Dict, int, float]:
        """Execute retry strategy. Returns (final_result, retries_used, simulated_delay)."""

        max_retries = config.get("max_retries", 3)
        total_delay = 0.0

        for attempt in range(1, max_retries + 1):
            delay = self._calculate_delay(strategy, config, attempt)
            jittered = self.executor.calculate_jittered_backoff(delay)
            total_delay += jittered

            if self.simulate_delays:
                await asyncio.sleep(jittered)

            result = await self.executor.send_request(method, endpoint, params, json_body)

            if result.get("status") == Status.SUCCESS:
                return result, attempt, total_delay

        # All retries exhausted
        return result, max_retries, total_delay

    @staticmethod
    def _calculate_delay(strategy: str, config: Dict, attempt: int) -> float:
        """Calculate base delay before jitter, based on strategy type."""
        if strategy == RetryStrategy.RETRY_LINEAR:
            return config.get("delay", 1.0) * attempt

        if strategy == RetryStrategy.WAIT_AND_RETRY:
            return config.get("wait_seconds", 5.0)

        if strategy == RetryStrategy.RETRY_EXPONENTIAL:
            base = config.get("base_delay", 1.0)
            return base * (2 ** (attempt - 1))

        return 1.0
