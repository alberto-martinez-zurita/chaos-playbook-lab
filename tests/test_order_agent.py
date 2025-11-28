import pytest
from google.adk.evaluation.agent_evaluator import AgentEvaluator
from dotenv import load_dotenv

load_dotenv()

@pytest.mark.asyncio
async def test_agent_evaluation():
    result = await AgentEvaluator.evaluate(
        agent_module="agents.order_agent",   # module containing `agent`
        eval_dataset_file_path_or_dir="tests/test_cases.json",
        
    )

    print("\n=== Evaluation Result ===")
    print(result)

    # Assert that the evaluation ran and produced behavior results
    assert result is not None
    assert "evaluation_summary" in result or "metrics" in result or "runs" in result
