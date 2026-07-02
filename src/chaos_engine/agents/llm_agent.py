"""LLM-orchestrated workflow agent for chaos engineering experiments.

Unlike the DeterministicAgent (which follows a hardcoded playbook), this agent
delegates every orchestration decision to the LLM.  At each turn the LLM
receives the current workflow state and responds with a JSON action — even when
nothing has failed.  This means the LLM is invoked ~4 times at 0 % failure
rate, producing a realistic token-cost and latency baseline for comparison.
"""
from __future__ import annotations

import json
import logging
import time
from typing import Any, Dict, Final, Optional

from chaos_engine.agents.llm_client import LLMClient
from chaos_engine.agents.trace import ExperimentTracer, TraceTurn, prompt_hash
from chaos_engine.core.fixtures import ORDER_ID, PRODUCT_ID
from chaos_engine.core.prompts import load_prompt
from chaos_engine.core.protocols import Executor
from chaos_engine.core.types import (
    ExperimentResult,
    RetryStrategy,
    Status,
    WorkflowStep,
)

logger = logging.getLogger(__name__)

# ── constants ────────────────────────────────────────────────────────────────

_MAX_TURNS: Final[int] = 15

_ENDPOINT_TO_STEP: Final[Dict[str, str]] = {
    "/product/find": WorkflowStep.FIND_PRODUCT,
    "/store/inventory": WorkflowStep.CHECK_INVENTORY,
    "/store/order": WorkflowStep.PLACE_ORDER,
    "/order/confirm": WorkflowStep.CONFIRM_ORDER,
}

_SYSTEM_PROMPT: Final[str] = load_prompt("http_system")
HTTP_PLAYBOOK_GUIDANCE: Final[str] = load_prompt("http_playbook_guidance")
HTTP_PLAYBOOK_GUIDANCE_V2: Final[str] = load_prompt("http_playbook_guidance_v2")


class LLMAgent:
    """Workflow agent where the LLM orchestrates every step."""

    def __init__(
        self,
        tool_executor: Executor,
        llm_client: LLMClient,
        simulate_delays: bool = False,
        playbook_guidance: str | None = None,
        system_prompt: str | None = None,
        all_steps: list[str] | None = None,
        tracer: "ExperimentTracer | None" = None,
        experiment_id: str = "",
        enable_harness: bool = True,
    ) -> None:
        self.executor = tool_executor
        self.llm = llm_client
        self.simulate_delays = simulate_delays
        self._playbook_guidance = playbook_guidance
        self._system_prompt = system_prompt or _SYSTEM_PROMPT
        self._tracer = tracer
        self._experiment_id = experiment_id
        self._enable_harness = enable_harness
        self._all_steps = all_steps or [
            WorkflowStep.FIND_PRODUCT,
            WorkflowStep.CHECK_INVENTORY,
            WorkflowStep.PLACE_ORDER,
            WorkflowStep.CONFIRM_ORDER,
        ]

    # ── public API ───────────────────────────────────────────────────────

    async def run(self) -> ExperimentResult:
        """Execute the LLM-orchestrated workflow loop."""
        start_time = time.time()

        effective_prompt = self._system_prompt
        if self._playbook_guidance is not None:
            effective_prompt = self._system_prompt + self._playbook_guidance

        if hasattr(self.llm, 'reset_counters'):
            self.llm.reset_counters()

        steps_completed: list[str] = []
        failed_at: Optional[str] = None
        retries = 0
        llm_calls = 0
        step_data: Dict[str, Any] = {}
        last_endpoint: Optional[str] = None

        # First turn message
        user_message = (
            "Workflow started. No steps completed yet. "
            "What is your first action?"
        )

        sys_hash = prompt_hash(effective_prompt) if self._tracer else ""

        for turn in range(1, _MAX_TURNS + 1):
            # 1. Ask the LLM
            try:
                raw_response = self.llm.chat(effective_prompt, user_message)
                llm_calls += 1
                action = self._parse_action(raw_response)
            except Exception as exc:
                logger.warning(
                    "LLM response could not be parsed on turn %d: %s. Aborting.",
                    turn,
                    exc,
                )
                if self._tracer:
                    self._tracer.log_turn(TraceTurn(
                        experiment_id=self._experiment_id, turn=turn,
                        timestamp=time.time(),
                        system_prompt_hash=sys_hash,
                        user_message=user_message,
                        raw_response=str(exc),
                        parse_error=str(exc),
                    ))
                failed_at = self._resolve_next_step(steps_completed)
                break

            action_type = action.get("action")

            # 2. Handle terminal actions
            if action_type == "complete":
                logger.info("LLM signalled completion on turn %d.", turn)
                if self._tracer:
                    self._tracer.log_turn(TraceTurn(
                        experiment_id=self._experiment_id, turn=turn,
                        timestamp=time.time(),
                        system_prompt_hash=sys_hash,
                        user_message=user_message,
                        raw_response=raw_response,
                        parsed_action=action,
                    ))
                if len(steps_completed) < len(self._all_steps):
                    missing = self._resolve_next_step(steps_completed)
                    logger.warning(
                        "LLM claimed complete but step '%s' not done. Marking failure.",
                        missing,
                    )
                    failed_at = missing
                break

            if action_type == "abort":
                logger.info("LLM signalled abort on turn %d.", turn)
                if self._tracer:
                    self._tracer.log_turn(TraceTurn(
                        experiment_id=self._experiment_id, turn=turn,
                        timestamp=time.time(),
                        system_prompt_hash=sys_hash,
                        user_message=user_message,
                        raw_response=raw_response,
                        parsed_action=action,
                    ))
                failed_at = self._resolve_next_step(steps_completed)
                break

            if action_type != "call_api":
                logger.warning("Unknown action '%s' on turn %d. Aborting.", action_type, turn)
                if self._tracer:
                    self._tracer.log_turn(TraceTurn(
                        experiment_id=self._experiment_id, turn=turn,
                        timestamp=time.time(),
                        system_prompt_hash=sys_hash,
                        user_message=user_message,
                        raw_response=raw_response,
                        parsed_action=action,
                    ))
                failed_at = self._resolve_next_step(steps_completed)
                break

            # 3. Execute the API call
            method: str = action.get("method", "GET")
            endpoint: str = action.get("endpoint", "")
            params: Optional[Dict] = action.get("params")
            body: Optional[Dict] = action.get("body")

            step_name = self._endpoint_to_step(endpoint)

            # Capture body BEFORE harness enrichment (for trace)
            body_before = dict(body) if body else None

            # Enrich body with data gathered from previous steps
            if self._enable_harness:
                body = self._build_step_body(step_name, body, step_data)

            body_after = dict(body) if body else None

            # Track retries (repeated call to the same endpoint)
            if endpoint == last_endpoint:
                retries += 1
                from chaos_engine.core.metrics import RETRIES_TOTAL
                RETRIES_TOTAL.labels(agent_type="llm").inc()
            last_endpoint = endpoint

            result = await self.executor.send_request(
                method, endpoint, params, body,
            )

            # 4. Build next user message based on outcome
            status_code = result.get("code", 0)
            if result.get("status") == Status.SUCCESS:
                data = result.get("data", {})
                if step_name and step_name not in steps_completed:
                    steps_completed.append(step_name)
                    step_data[step_name] = data
                user_message = (
                    f"{method} {endpoint} → {status_code} OK. "
                    f"Data: {json.dumps(data, default=str)[:512]}. "
                    f"Steps completed: {[str(s) for s in steps_completed]}. Next action?"
                )
            else:
                message = result.get("message", "Unknown error")
                user_message = (
                    f"{method} {endpoint} → HTTP {status_code} {message}. "
                    f"Steps completed: {[str(s) for s in steps_completed]}. Next action?"
                )
                from chaos_engine.core.metrics import STRATEGY_USED
                STRATEGY_USED.labels(strategy="llm_orchestrated").inc()

            # 5. Log trace turn (after tool result is known)
            if self._tracer:
                self._tracer.log_turn(TraceTurn(
                    experiment_id=self._experiment_id, turn=turn,
                    timestamp=time.time(),
                    system_prompt_hash=sys_hash,
                    user_message=user_message,
                    raw_response=raw_response,
                    parsed_action=action,
                    body_before_enrich=body_before,
                    body_after_enrich=body_after,
                    tool_status=str(result.get("status", "")),
                    tool_status_code=status_code,
                    tool_message=result.get("message", ""),
                    step_name=step_name,
                ))
        else:
            # Exhausted all turns without complete/abort
            logger.warning("LLM agent hit max turns (%d). Marking as failure.", _MAX_TURNS)
            failed_at = self._resolve_next_step(steps_completed)

        # ── build result ─────────────────────────────────────────────────
        duration_s = time.time() - start_time
        duration_ms = duration_s * 1000
        status = Status.SUCCESS if failed_at is None else Status.FAILURE

        from chaos_engine.core.metrics import EXPERIMENT_DURATION
        EXPERIMENT_DURATION.labels(agent_type="llm").observe(duration_s)

        result = ExperimentResult(
            status=status,
            steps_completed=steps_completed,
            failed_at=failed_at,
            duration_ms=duration_ms,
            retries=retries,
            simulated_delay_s=0.0,
            outcome=status,
            agent_type="",
        )
        result["llm_calls"] = llm_calls
        result["steps_completed_list"] = ",".join(steps_completed)
        if hasattr(self.llm, 'total_input_chars'):
            result["input_chars"] = self.llm.total_input_chars
            result["output_chars"] = self.llm.total_output_chars
            result["prompt_tokens"] = self.llm.total_prompt_tokens
            result["completion_tokens"] = self.llm.total_completion_tokens
            result["reasoning_tokens"] = getattr(self.llm, 'total_reasoning_tokens', 0)
        return result

    # ── helpers ──────────────────────────────────────────────────────────

    @staticmethod
    def _parse_action(raw: str) -> Dict[str, Any]:
        """Parse a JSON action from the LLM response.

        Strips optional markdown code fences and trailing text after the
        JSON object (common with smaller/flash models).
        """
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            lines = cleaned.split("\n")
            lines = [line for line in lines if not line.strip().startswith("```")]
            cleaned = "\n".join(lines).strip()
        # Extract first JSON object — tolerates trailing text
        start = cleaned.find("{")
        if start == -1:
            raise ValueError("No JSON object found in response")
        depth = 0
        in_string = False
        escape = False
        for i, ch in enumerate(cleaned[start:], start):
            if escape:
                escape = False
                continue
            if ch == "\\":
                escape = True
                continue
            if ch == '"' and not escape:
                in_string = not in_string
                continue
            if in_string:
                continue
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    return json.loads(cleaned[start:i + 1])
        return json.loads(cleaned[start:])

    @staticmethod
    def _endpoint_to_step(endpoint: str) -> Optional[str]:
        """Map an endpoint path to its canonical WorkflowStep name."""
        for prefix, step in _ENDPOINT_TO_STEP.items():
            if endpoint.startswith(prefix):
                return step
        return None

    def _resolve_next_step(self, steps_completed: list[str]) -> str:
        """Return the step name where progress stopped."""
        for step in self._all_steps:
            if step not in steps_completed:
                return step
        return self._all_steps[-1]

    @staticmethod
    def _build_step_body(
        step_name: Optional[str],
        body: Optional[Dict],
        step_data: Dict[str, Any],
    ) -> Optional[Dict]:
        """Enrich a request body with data gathered from earlier steps.

        The LLM may provide placeholder values.  This method fills in real
        ids obtained from prior API responses.
        """
        if body is None or step_name is None:
            return body

        body = dict(body)
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
