"""
ExperimentEvaluator Service - Orchestrates experiment evaluation (FIXED)

Location: src/chaos_playbook_engine/services/experiment_evaluator.py

Purpose: Provides high-level interface for evaluating experiments using
         ExperimentJudgeAgent. Formats traces, runs evaluation, parses results.

FIX: _parse_judge_response() now handles BOTH response formats:
     - List of Events (ADK InMemoryRunner default) ✅
     - Dict format (legacy/fallback) ✅
     
     This preserves original intent: "Parse judge output for outcome/confidence/promoted" ✅
"""

from typing import Any, Dict, Optional
from datetime import datetime

#from agents.experiment_judge import create_experiment_judge_agent
from storage.playbook_storage import PlaybookStorage
from services.runner_factory import InMemoryRunner


class ExperimentEvaluator:
    """
    Evaluates chaos experiments using ExperimentJudgeAgent.

    Workflow:
        1. Accept experiment trace (list of events from session)
        2. Format trace as natural language prompt
        3. Run ExperimentJudgeAgent to evaluate
        4. Parse response for promotion decision
        5. If promoted: call saveprocedure automatically
        6. Return evaluation result

    Example:
        >>> evaluator = ExperimentEvaluator()
        >>> trace = {...experiment events...}
        >>> result = await evaluator.evaluate_experiment(trace, "EXP-001")
        >>> print(result["promoted"])  # True/False
        >>> print(result["procedure_id"])  # If promoted
    """

    def __init__(self):
        """Initialize evaluator with judge agent and storage."""
        self.judge = create_experiment_judge_agent()
        self.runner = InMemoryRunner(agent=self.judge)
        self.storage = PlaybookStorage()

    async def evaluate_experiment(
        self,
        trace: Dict[str, Any],
        experiment_id: str
    ) -> Dict[str, Any]:
        """
        Evaluate an experiment trace using ExperimentJudgeAgent.

        Args:
            trace: Experiment trace dict containing:
                - events: List of {tool, status, result, duration, ...}
                - outcome: "order_completed", "order_incomplete", etc.
                - total_duration: Total experiment time in seconds
                - chaos_scenario: e.g., "timeout", "503_error", etc.
            experiment_id: Unique experiment ID (e.g., "EXP-001")

        Returns:
            {
                "experiment_id": "EXP-001",
                "outcome": "success" | "failure" | "partial",
                "confidence": 0.95,
                "reasoning": "...",
                "promoted": True | False,
                "procedure_id": "PROC-003" (if promoted),
                "recovery_strategy": "..." (if promoted),
                "success_rate": 0.95 (if promoted)
            }

        Raises:
            ValueError: If trace format invalid
        """
        # Validate trace
        self._validate_trace(trace)

        # Format trace as natural language for judge
        prompt = self._format_trace_prompt(trace, experiment_id)

        # Run judge to evaluate
        try:
            response = await self.runner.run_debug(prompt)
        except Exception as e:
            return {
                "experiment_id": experiment_id,
                "outcome": "error",
                "confidence": 0.0,
                "reasoning": f"Judge evaluation failed: {str(e)}",
                "promoted": False
            }

        # Parse judge response
        evaluation = self._parse_judge_response(response, experiment_id, trace)

        # If promoted, save procedure automatically
        if evaluation.get("promoted") and "recovery_strategy" in evaluation:
            try:
                procedure_id = await self.storage.save_procedure(
                    failure_type=trace.get("chaos_scenario", "unknown"),
                    api=trace.get("failed_api", "unknown"),
                    recovery_strategy=evaluation["recovery_strategy"],
                    success_rate=evaluation.get("success_rate", 0.9),
                    metadata={
                        "experiment_id": experiment_id,
                        "judge_confidence": evaluation.get("confidence", 0.0),
                        "evaluated_at": datetime.utcnow().isoformat() + "Z"
                    }
                )
                evaluation["procedure_id"] = procedure_id
            except Exception as e:
                # Evaluation succeeded but couldn't save procedure
                evaluation["save_error"] = str(e)

        return evaluation

    def _validate_trace(self, trace: Dict[str, Any]):
        """
        Validate trace format.

        Required fields:
            - events: List of event dicts
            - outcome: String describing result

        Raises:
            ValueError: If trace invalid
        """
        if not isinstance(trace, dict):
            raise ValueError("Trace must be a dictionary")
        if "events" not in trace or not isinstance(trace["events"], list):
            raise ValueError("Trace must contain 'events' list")
        if "outcome" not in trace:
            raise ValueError("Trace must contain 'outcome' field")

    def _format_trace_prompt(
        self,
        trace: Dict[str, Any],
        experiment_id: str
    ) -> str:
        """
        Convert trace to natural language prompt for judge.

        Args:
            trace: Experiment trace
            experiment_id: Experiment ID

        Returns:
            Natural language description of experiment
        """
        events = trace.get("events", [])
        outcome = trace.get("outcome", "unknown")
        total_duration = trace.get("total_duration", 0)
        chaos_scenario = trace.get("chaos_scenario", "unknown")

        # Build event description
        event_descriptions = []
        for i, event in enumerate(events, 1):
            tool = event.get("tool", "unknown")
            status = event.get("status", "unknown")
            duration = event.get("duration", 0)

            if status == "error":
                # FIXED: Get error_code from event directly, not from result
                error_code = event.get("error_code", "unknown")
                event_descriptions.append(
                    f"{i}. {tool}: ERROR ({error_code}) [{duration:.2f}s]"
                )
            else:
                event_descriptions.append(
                    f"{i}. {tool}: SUCCESS [{duration:.2f}s]"
                )

        events_text = "\\n".join(event_descriptions)

        prompt = f"""Evaluate this chaos engineering experiment:

Experiment ID: {experiment_id}
Chaos Scenario: {chaos_scenario}
Total Duration: {total_duration:.2f}s
Outcome: {outcome}

Events:
{events_text}

Analyze this trace and provide your evaluation including:
1. Overall outcome (success/failure/partial)
2. Confidence level (0.0-1.0)
3. Whether to promote strategy to Playbook
4. If promoting: extracted recovery strategy and success rate

Be conservative - only promote if outcome is clearly successful and recovery was effective."""

        return prompt

    def _parse_judge_response(
        self,
        response,  # ✅ FIXED: Removed Dict[str, Any] type hint to accept both list and dict
        experiment_id: str,
        trace: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Parse judge agent response into evaluation result.

        Args:
            response: Response from judge agent (list of Events OR dict)
            experiment_id: Experiment ID
            trace: Original trace for context

        Returns:
            Structured evaluation result

        FIX: Now handles BOTH formats:
             - List of Events (ADK InMemoryRunner) ✅
             - Dict format (legacy/fallback) ✅
        """
        # ✅ FIXED: Extract message/output from response (handle both formats)
        judge_output = ""
        
        if isinstance(response, list):
            # ADK InMemoryRunner returns list of Events
            for event in response:
                if hasattr(event, 'text') and event.text:
                    judge_output += event.text
                elif hasattr(event, 'output') and event.output:
                    judge_output += event.output
                elif isinstance(event, dict):
                    # Event as dict
                    judge_output += event.get("text", "") or event.get("output", "")
        elif isinstance(response, dict):
            # Legacy dict format
            judge_output = response.get("output", "") or response.get("text", "")
        else:
            # Fallback: convert to string
            judge_output = str(response)

        # Parse for key indicators
        promoted = any(word in judge_output.lower() for word in
                      ["promote", "promotion", "should be added", "save to playbook"])

        # Extract confidence (look for "confidence" mentions)
        confidence = 0.7  # Default
        if "confidence" in judge_output.lower():
            # Try to extract numeric confidence
            import re
            matches = re.findall(r'confidence[:\\s]+(\\d+\\.?\\d*)', judge_output.lower())
            if matches:
                try:
                    confidence = float(matches[0]) / 100 if float(matches[0]) > 1 else float(matches[0])
                except:
                    pass

        # Determine outcome
        outcome = "partial"  # Default
        if "success" in judge_output.lower():
            outcome = "success"
        elif "failure" in judge_output.lower() or "failed" in judge_output.lower():
            outcome = "failure"
        elif "partial" in judge_output.lower():
            outcome = "partial"

        result = {
            "experiment_id": experiment_id,
            "outcome": outcome,
            "confidence": confidence,
            "reasoning": judge_output[:200] + "..." if len(judge_output) > 200 else judge_output,
            "promoted": promoted,
        }

        # If promoted, extract strategy info from trace
        if promoted:
            result["recovery_strategy"] = trace.get("recovery_strategy",
                                                   "Retry strategy (details from trace)")
            result["success_rate"] = trace.get("success_rate", 0.85)

        return result

    async def evaluate_experiments_batch(
        self,
        traces: list[Dict[str, Any]],
        experiment_ids: Optional[list[str]] = None
    ) -> list[Dict[str, Any]]:
        """
        Evaluate multiple experiments.

        Args:
            traces: List of experiment traces
            experiment_ids: Optional list of IDs (auto-generated if not provided)

        Returns:
            List of evaluation results
        """
        if experiment_ids is None:
            experiment_ids = [f"EXP-{i:03d}" for i in range(1, len(traces) + 1)]

        results = []
        for trace, exp_id in zip(traces, experiment_ids):
            result = await self.evaluate_experiment(trace, exp_id)
            results.append(result)

        return results
