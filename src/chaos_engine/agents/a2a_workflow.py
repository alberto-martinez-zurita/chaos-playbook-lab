"""A2A multi-agent workflow for chaos experiments.

Two variants compete in parametric experiments:
- A2ABaselineAgent: fail_fast on any A2A communication error
- A2ALLMAgent: uses LLM (z.ai / GLM 4.5) to decide recovery strategy

Simulates a 2-agent order processing workflow (unified across protocols):
  Agent A (Coordinator) delegates subtasks to Agent B (Worker) via A2AChaosProxy.

Workflow steps:
1. send_task("worker-b", find_product) — search available products
2. send_task("worker-b", check_inventory) — verify stock
3. send_task("worker-b", place_order) — create the order
4. send_task("worker-b", confirm_order) — finalize

Satisfies WorkflowAgent protocol.
"""
from __future__ import annotations

import json
import logging
import time
from typing import Any, Dict, Final, Optional

from chaos_engine.agents.trace import ExperimentTracer, TraceTurn, prompt_hash
from chaos_engine.core.fixtures import ORDER_ID, PRODUCT_ID
from chaos_engine.core.prompts import load_prompt
from chaos_engine.core.protocols import A2AExecutor
from chaos_engine.core.types import A2AFailureType, ExperimentResult, Status

logger = logging.getLogger(__name__)

WORKER_AGENT_ID: Final[str] = "worker-b"

# A2A workflow steps: (step_name, task_payload)
# Unified order workflow — same business logic as HTTP and MCP
A2A_WORKFLOW_STEPS: Final[tuple[tuple[str, Dict[str, Any]], ...]] = (
    ("find_product", {"action": "find_product", "status": "available"}),
    ("check_inventory", {"action": "check_inventory", "productId": PRODUCT_ID}),
    ("place_order", {"action": "place_order", "productId": PRODUCT_ID, "quantity": 1}),
    ("confirm_order", {"action": "confirm_order", "orderId": ORDER_ID}),
)

_MAX_TURNS: Final[int] = 12

A2A_PLAYBOOK_GUIDANCE: Final[str] = load_prompt("a2a_playbook_guidance")

_ALL_STEPS: Final[list[str]] = ["find_product", "check_inventory", "place_order", "confirm_order"]

_A2A_SYSTEM_PROMPT: Final[str] = load_prompt("a2a_system")

# Map task action names to workflow step names
_TASK_TO_STEP: Final[dict[str, str]] = {
    "find_product": "find_product",
    "check_inventory": "check_inventory",
    "place_order": "place_order",
    "confirm_order": "confirm_order",
}


class A2ABaselineAgent:
    """A2A coordinator with no resilience — fail_fast on any error."""

    def __init__(
        self,
        a2a_executor: A2AExecutor,
        workflow_steps: tuple | None = None,
    ) -> None:
        self.executor = a2a_executor
        self._workflow_steps = workflow_steps or A2A_WORKFLOW_STEPS

    async def run(self) -> ExperimentResult:
        start_time = time.time()
        steps_completed: list[str] = []
        failed_at: str | None = None

        for step_name, task_payload in self._workflow_steps:
            result = await self.executor.send_task(WORKER_AGENT_ID, task_payload)

            if result.get("status") == Status.SUCCESS:
                steps_completed.append(step_name)
            else:
                failed_at = step_name
                break

        duration_ms = (time.time() - start_time) * 1000
        status = Status.SUCCESS if failed_at is None else Status.FAILURE

        result = ExperimentResult(
            status=status,
            steps_completed=steps_completed,
            failed_at=failed_at,
            duration_ms=duration_ms,
            retries=0,
            simulated_delay_s=0.0,
            outcome=status,
            agent_type="",
        )
        result["llm_calls"] = 0
        result["steps_completed_list"] = ",".join(steps_completed)
        return result


class A2ALLMAgent:
    """A2A coordinator where the LLM orchestrates every step.

    At each turn the LLM receives the current workflow state and responds with
    a JSON action — even when nothing has failed.  The LLM decides which task
    to delegate, when to retry, and when to signal completion or abort.
    """

    def __init__(
        self,
        a2a_executor: A2AExecutor,
        llm_client: Any,
        playbook_guidance: str | None = None,
        system_prompt: str | None = None,
        all_steps: list[str] | None = None,
        tracer: ExperimentTracer | None = None,
        experiment_id: str = "",
    ) -> None:
        self.executor = a2a_executor
        self.llm = llm_client
        self._playbook_guidance = playbook_guidance
        self._system_prompt = system_prompt or _A2A_SYSTEM_PROMPT
        self._all_steps = all_steps or _ALL_STEPS
        self._tracer = tracer
        self._experiment_id = experiment_id

    # ── public API ───────────────────────────────────────────────────────

    async def run(self) -> ExperimentResult:
        """Execute the LLM-orchestrated A2A workflow loop."""
        start_time = time.time()

        effective_prompt = self._system_prompt
        if self._playbook_guidance:
            effective_prompt = self._system_prompt + self._playbook_guidance

        if hasattr(self.llm, 'reset_counters'):
            self.llm.reset_counters()

        steps_completed: list[str] = []
        failed_at: Optional[str] = None
        retries = 0
        llm_calls = 0
        last_action_key: Optional[str] = None

        user_message = (
            "Order processing started. Worker agent 'worker-b' available. "
            "No tasks completed. What's your first delegation?"
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
                    turn, exc,
                )
                if self._tracer:
                    self._tracer.log_turn(TraceTurn(
                        experiment_id=self._experiment_id, turn=turn,
                        timestamp=time.time(), system_prompt_hash=sys_hash,
                        user_message=user_message, raw_response=str(exc),
                        parse_error=str(exc),
                    ))
                failed_at = self._resolve_next_step(steps_completed)
                break

            action_type = action.get("action")

            # 2. Handle terminal actions
            if action_type == "complete":
                logger.info("LLM signalled completion on turn %d.", turn)
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
                failed_at = self._resolve_next_step(steps_completed)
                break

            # 3. Execute the A2A delegation
            if action_type == "send_task":
                agent_id: str = action.get("agent_id", WORKER_AGENT_ID)
                task: Dict[str, Any] = action.get("task", {})
                task_action: str = task.get("action", "")
                step_name = _TASK_TO_STEP.get(task_action, task_action)

                # Track retries (repeated delegation of the same task)
                action_key = f"send_task:{task_action}"
                if action_key == last_action_key:
                    retries += 1
                last_action_key = action_key

                result = await self.executor.send_task(agent_id, task)

                # 4. Build next user message based on outcome
                if result.get("status") == Status.SUCCESS:
                    data = result.get("data", {})
                    if step_name not in steps_completed:
                        steps_completed.append(step_name)
                    data_summary = json.dumps(data, default=str)[:512]
                    user_message = (
                        f"send_task('{agent_id}', {task_action}) -> "
                        f"completed successfully. Data: {data_summary}. "
                        f"Steps completed: {steps_completed}. Next?"
                    )
                else:
                    error = result.get(
                        "error_type", result.get("message", "unknown"),
                    )
                    user_message = (
                        f"send_task('{agent_id}', {task_action}) -> "
                        f"error: {error}. "
                        f"Steps completed: {steps_completed}. Next?"
                    )

                # 5. Log trace turn
                if self._tracer:
                    self._tracer.log_turn(TraceTurn(
                        experiment_id=self._experiment_id, turn=turn,
                        timestamp=time.time(), system_prompt_hash=sys_hash,
                        user_message=user_message, raw_response=raw_response,
                        parsed_action=action,
                        tool_status=str(result.get("status", "")),
                        tool_message=result.get("error_type", result.get("message", "")),
                        step_name=step_name,
                    ))
            else:
                logger.warning(
                    "Unknown action '%s' on turn %d. Aborting.",
                    action_type, turn,
                )
                if self._tracer:
                    self._tracer.log_turn(TraceTurn(
                        experiment_id=self._experiment_id, turn=turn,
                        timestamp=time.time(), system_prompt_hash=sys_hash,
                        user_message=user_message, raw_response=raw_response,
                        parsed_action=action,
                    ))
                failed_at = self._resolve_next_step(steps_completed)
                break
        else:
            # Exhausted all turns without complete/abort
            logger.warning(
                "A2A LLM agent hit max turns (%d). Marking as failure.",
                _MAX_TURNS,
            )
            failed_at = self._resolve_next_step(steps_completed)

        # ── build result ─────────────────────────────────────────────────
        duration_ms = (time.time() - start_time) * 1000
        status = Status.SUCCESS if failed_at is None else Status.FAILURE

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

    def _resolve_next_step(self, steps_completed: list[str]) -> str:
        """Return the step name where progress stopped."""
        for step in self._all_steps:
            if step not in steps_completed:
                return step
        return self._all_steps[-1]
