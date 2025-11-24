"""
ExperimentJudgeAgent - LLM-based evaluation of chaos experiments.

Location: src/chaos_playbook_engine/agents/experiment_judge.py

Purpose: Evaluates experiment traces and decides which recovery strategies
should be promoted to the Chaos Playbook. Implements ADR-004 (Agent-as-Judge).

The judge analyzes:
1. Experiment outcome (success, failure, partial)
2. Recovery strategies used
3. Whether to promote strategy to Playbook

Promotion criteria:
- Strategy resulted in SUCCESS
- Success rate > 70%
- Recovery time reasonable (<30s total)
- No data inconsistencies
"""

from typing import Any, Dict, Optional
from google.adk.agents import LlmAgent
from google.adk.models.google_llm import Gemini

# Import Playbook tools for promotion/rejection
from ..tools.playbook_tools import recordfailure


MODEL_NAME = "gemini-2.5-flash-lite"


# ============================================================================
# HELPER TOOLS FOR JUDGE
# ============================================================================

async def recordfailure(
    failure_reason: str,
    experiment_id: str
) -> Dict[str, Any]:
    """
    Record experiment failure for analysis.
    
    Use this tool when rejecting a strategy that didn't work.
    
    Args:
        failure_reason: Why the strategy failed or was rejected
        experiment_id: Unique experiment ID
    
    Returns:
        {"status": "recorded", "experiment_id": experiment_id}
    """
    return {
        "status": "recorded",
        "experiment_id": experiment_id,
        "failure_reason": failure_reason
    }


# ============================================================================
# EXPERIMENTJUDGEAGENT FACTORY
# ============================================================================

def create_experiment_judge_agent() -> LlmAgent:
    """
    Create ExperimentJudgeAgent for evaluating chaos experiments.
    
    The agent analyzes experiment traces and determines:
    1. Outcome: success, failure, or partial
    2. Confidence in the assessment
    3. Whether strategy should be promoted to Playbook
    
    Returns:
        Configured LlmAgent with judge capabilities
    
    Example:
        >>> judge = create_experiment_judge_agent()
        >>> runner = InMemoryRunner(agent=judge)
        >>> result = await runner.run_debug(experiment_trace)
    """
    instruction = """You are an Experiment Judge Agent that evaluates chaos engineering experiments.

Your Role:
Analyze experiment traces (session events) and determine:
1. Outcome: success, failure, or partial
2. Effectiveness of recovery strategy
3. Recommendation: promote to Playbook or reject

**Evaluation Criteria:**

SUCCESS:
- Order processing completed
- All 4 APIs called successfully (inventory → payments → erp → shipping)
- No payment without order, no order without payment (consistency)
- Recovery strategy was effective

FAILURE:
- Order did not complete
- Inconsistent states detected (e.g., payment captured but no order created)
- Recovery strategy ineffective

PARTIAL:
- Order completed but with issues
- Recovery took excessive time (>30s total)
- Strategy worked but suboptimal

**Promotion Decision:**

PROMOTE to Playbook if:
✅ Strategy resulted in SUCCESS
✅ Success rate > 70% (if multiple attempts tracked)
✅ Recovery time reasonable (<30s from failure to resolution)
✅ No data inconsistencies
✅ Confidence level > 0.8

DO NOT PROMOTE if:
❌ Strategy resulted in FAILURE
❌ Success rate < 70%
❌ Recovery time excessive (>30s)
❌ Data inconsistencies detected
❌ Confidence < 0.7

**Output Format:**

For PROMOTION, analyze trace and describe:
{
    "outcome": "success",
    "confidence": 0.95,
    "reasoning": "Clear progression through all 4 APIs, retry was effective, completed in 8s",
    "recovery_strategy": "Retried 3x with exponential backoff (2s, 4s, 8s)",
    "success_rate": 0.95,
    "recommendation": "PROMOTE"
}

For REJECTION, use recordfailure tool and explain:
{
    "outcome": "failure",
    "confidence": 0.9,
    "reasoning": "Order not completed after retries, payment inconsistency detected",
    "recommendation": "REJECT"
}

**Analysis Approach:**

1. Parse trace events chronologically
2. Identify failure points and recovery attempts
3. Measure recovery time
4. Check for data consistency
5. Rate strategy effectiveness
6. Make promotion decision

Always provide clear reasoning for your decision. Be conservative with promotions - 
only promote strategies with high confidence and clear success.

**Tools Available:**
- recordfailure (record rejected strategies)

**Important:** Your evaluation will inform future retry strategies, so accuracy is critical."""

    # Define judge with tools
    return LlmAgent(
        name="ExperimentJudgeAgent",
        model=Gemini(model=MODEL_NAME),
        instruction=instruction,
        tools=[recordfailure]
    )
