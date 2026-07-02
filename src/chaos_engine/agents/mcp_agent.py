"""MCP workflow agents for chaos experiments.

Two variants compete in parametric experiments:
- MCPBaselineAgent: fail_fast on any MCP tool error (no resilience)
- MCPLLMAgent: LLM orchestrates every step via MCP tool calls

Both execute a 4-step MCP tool workflow via MCPChaosProxy (unified order flow):
1. call_tool("find_product") — search available products
2. call_tool("check_inventory") — verify stock
3. call_tool("place_order") — create the order
4. call_tool("confirm_order") — finalize

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
from chaos_engine.core.protocols import MCPToolExecutor
from chaos_engine.core.types import ExperimentResult, MCPFailureType, Status

logger = logging.getLogger(__name__)

# MCP workflow steps: (step_name, tool_name, arguments)
# Unified order workflow — same business logic as HTTP and A2A
MCP_WORKFLOW_STEPS: Final[tuple[tuple[str, str, Optional[Dict[str, Any]]], ...]] = (
    ("find_product", "find_product", {"status": "available"}),
    ("check_inventory", "check_inventory", {"productId": PRODUCT_ID}),
    ("place_order", "place_order", {"productId": PRODUCT_ID, "quantity": 1}),
    ("confirm_order", "confirm_order", {"orderId": ORDER_ID}),
)

# Recovery strategies for MCP errors (used by MCPBaselineAgent)
_MCP_STRATEGIES: Final[dict[str, str]] = {
    MCPFailureType.TOOL_NOT_FOUND: "fail_fast",
    MCPFailureType.INVALID_PARAMS: "fail_fast",
    MCPFailureType.CONTEXT_OVERFLOW: "retry_with_reduction",
    MCPFailureType.TIMEOUT: "retry_linear_backoff",
    MCPFailureType.RATE_LIMITED: "wait_and_retry",
    MCPFailureType.INTERNAL_ERROR: "retry_exponential_backoff",
}

# ── constants for MCPLLMAgent ───────────────────────────────────────────────

_MAX_TURNS: Final[int] = 12

_ALL_STEPS: Final[list[str]] = ["find_product", "check_inventory", "place_order", "confirm_order"]

MCP_PLAYBOOK_GUIDANCE: Final[str] = load_prompt("mcp_playbook_guidance")
_MCP_SYSTEM_PROMPT: Final[str] = load_prompt("mcp_system")


class MCPBaselineAgent:
    """MCP agent with no resilience — fail_fast on any error."""

    def __init__(
        self,
        tool_executor: MCPToolExecutor,
        workflow_steps: tuple | None = None,
    ) -> None:
        self.executor = tool_executor
        self._workflow_steps = workflow_steps or MCP_WORKFLOW_STEPS

    async def run(self) -> ExperimentResult:
        start_time = time.time()
        steps_completed: list[str] = []
        failed_at: str | None = None

        for step_name, tool_name, arguments in self._workflow_steps:
            result = await self._execute_step(step_name, tool_name, arguments)

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

    async def _execute_step(
        self, step_name: str, tool_name: str, arguments: Optional[Dict],
    ) -> Dict[str, Any]:
        return await self.executor.call_tool(tool_name, arguments)


class MCPLLMAgent:
    """MCP agent where the LLM orchestrates every step via MCP tool calls.

    At each turn the LLM receives the current workflow state and responds with
    a JSON action — even when nothing has failed.  The LLM decides which MCP
    tool to call, when to retry, and when to signal completion or abort.
    """

    def __init__(
        self,
        tool_executor: MCPToolExecutor,
        llm_client: Any,
        playbook_guidance: str | None = None,
        system_prompt: str | None = None,
        all_steps: list[str] | None = None,
        tracer: ExperimentTracer | None = None,
        experiment_id: str = "",
    ) -> None:
        self.executor = tool_executor
        self.llm = llm_client
        self._playbook_guidance = playbook_guidance
        self._system_prompt = system_prompt or _MCP_SYSTEM_PROMPT
        self._all_steps = all_steps or _ALL_STEPS
        self._tracer = tracer
        self._experiment_id = experiment_id

    # ── public API ───────────────────────────────────────────────────────

    async def run(self) -> ExperimentResult:
        """Execute the LLM-orchestrated MCP workflow loop."""
        start_time = time.time()

        if hasattr(self.llm, 'reset_counters'):
            self.llm.reset_counters()

        steps_completed: list[str] = []
        failed_at: Optional[str] = None
        retries = 0
        llm_calls = 0
        last_action_key: Optional[str] = None

        effective_prompt = self._system_prompt
        if self._playbook_guidance is not None:
            effective_prompt = self._system_prompt + self._playbook_guidance

        user_message = (
            "Order workflow started via MCP. No steps completed yet. "
            "What's your first action?"
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
                # Validate all steps are done before accepting completion
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

            # 3. Execute the MCP action
            action_key = self._action_key(action)

            # Track retries (repeated call to the same action)
            if action_key == last_action_key:
                retries += 1
            last_action_key = action_key

            if action_type == "call_tool":
                tool_name: str = action.get("tool_name", "")
                arguments: Optional[Dict] = action.get("arguments")
                step_name = tool_name  # tool_name maps directly to step name
                result = await self._exec_call_tool(tool_name, arguments)
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

            # 4. Build next user message based on outcome
            if result.get("status") == Status.SUCCESS:
                data = result.get("data", {})
                if step_name not in steps_completed:
                    steps_completed.append(step_name)
                data_summary = json.dumps(data, default=str)[:512]
                user_message = (
                    f"call_tool('{tool_name}') -> success. "
                    f"Data: {data_summary}. "
                    f"Steps completed: {steps_completed}. Next?"
                )
            else:
                error = result.get("error_type", result.get("message", "unknown"))
                user_message = (
                    f"call_tool('{tool_name}') -> error: {error}. "
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
            # Exhausted all turns without complete/abort
            logger.warning(
                "MCP LLM agent hit max turns (%d). Marking as failure.",
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

    async def _exec_call_tool(
        self, tool_name: str, arguments: Optional[Dict],
    ) -> Dict[str, Any]:
        """Execute call_tool on the MCP server."""
        return await self.executor.call_tool(tool_name, arguments)

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
    def _action_key(action: Dict[str, Any]) -> str:
        """Return a string key identifying the action for retry detection."""
        action_type = action.get("action", "")
        if action_type == "call_tool":
            return f"call_tool:{action.get('tool_name', '')}"
        return action_type

    def _resolve_next_step(self, steps_completed: list[str]) -> str:
        """Return the step name where progress stopped."""
        for step in self._all_steps:
            if step not in steps_completed:
                return step
        return self._all_steps[-1]
