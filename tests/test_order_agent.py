import pytest
from unittest.mock import AsyncMock, patch
from google.adk.evaluation.agent_evaluator import AgentEvaluator
from dotenv import load_dotenv

load_dotenv()

@pytest.mark.asyncio
@patch('agents.order_agent.chaos_proxy.send_request')
async def test_agent_evaluation(mock_send_request):
    """Mock ChaosProxy.send_request → 100% success"""
    
    async def mock_success(*args, **kwargs):
        endpoint = args[1] if len(args) > 1 else ""
        
        
        if "inventory" in endpoint:
            return {"status": "success", "code": 200, "data": {"pets": [{"id": 12345, "name": "Fluffy", "status": "available"}]}}
        elif "findByStatus" in endpoint:
            return {"status": "success", "code": 200, "data": [{"id": 12345, "name": "Fluffy", "status": "available"}]}
        elif "order" in endpoint:
            return {"status": "success", "code": 200, "data": {"id": "abc123", "status": "placed"}}
        elif "/pet" in endpoint:
            return {"status": "success", "code": 200, "data": {"id": 12345, "status": "sold"}}
        return {"status": "success", "code": 200, "data": {}}
    
  
    mock_send_request.side_effect = mock_success

    result = await AgentEvaluator.evaluate(
        agent_module="agents.order_agent",
        eval_dataset_file_path_or_dir="tests/test_cases.json"
    )

    
    
   
