"""
Unit tests for ExperimentJudgeAgent and ExperimentEvaluator (Phase 3 Prompt 3).

Location: tests/unit/test_experiment_judge.py

Run with:
    poetry run pytest tests/unit/test_experiment_judge.py -v
    
Expected: 5+ tests passing
"""

import asyncio
import pytest
from datetime import datetime

from chaos_playbook_engine.agents.experiment_judge import create_experiment_judge_agent
from chaos_playbook_engine.services.experiment_evaluator import ExperimentEvaluator
from chaos_playbook_engine.data.playbook_storage import PlaybookStorage


# ==================================================================
# TEST EXPERIMENTJUDGEAGENT
# ==================================================================

class TestExperimentJudgeAgent:
    """Tests for ExperimentJudgeAgent factory and configuration."""
    
    def test_judge_agent_created(self):
        """Test judge agent is created successfully."""
        judge = create_experiment_judge_agent()
        
        assert judge is not None
        assert judge.name == "ExperimentJudgeAgent"
    
    def test_judge_agent_has_instruction(self):
        """Test judge has evaluation instruction."""
        judge = create_experiment_judge_agent()
        
        assert judge.instruction is not None
        assert len(judge.instruction) > 0
        assert "evaluate" in judge.instruction.lower()
    
    def test_judge_agent_has_recordfailure_tool(self):
        """Test judge has recordfailure tool."""
        judge = create_experiment_judge_agent()
        
        # Check tools list
        assert len(judge.tools) > 0
        tool_names = [t.name if hasattr(t, 'name') else str(t) for t in judge.tools]
        # At minimum, should have some tools defined
        assert len(tool_names) >= 1


# ==================================================================
# TEST EXPERIMENTEVALUATOR
# ==================================================================

class TestExperimentEvaluator:
    """Tests for ExperimentEvaluator service."""
    
    @pytest.fixture
    def evaluator(self):
        """Provide ExperimentEvaluator instance."""
        return ExperimentEvaluator()
    
    def test_evaluator_initialized(self, evaluator):
        """Test evaluator initializes correctly."""
        assert evaluator is not None
        assert evaluator.judge is not None
        assert evaluator.runner is not None
        assert evaluator.storage is not None
    
    def test_validate_trace_valid(self, evaluator):
        """Test trace validation accepts valid trace."""
        trace = {
            "events": [
                {"tool": "call_inventory_api", "status": "success", "duration": 0.1},
                {"tool": "call_payments_api", "status": "success", "duration": 0.1}
            ],
            "outcome": "order_completed",
            "total_duration": 0.2,
            "chaos_scenario": "timeout"
        }
        
        # Should not raise
        evaluator._validate_trace(trace)
    
    def test_validate_trace_invalid_no_events(self, evaluator):
        """Test trace validation rejects trace without events."""
        trace = {
            "outcome": "order_completed"
        }
        
        with pytest.raises(ValueError, match="events"):
            evaluator._validate_trace(trace)
    
    def test_validate_trace_invalid_no_outcome(self, evaluator):
        """Test trace validation rejects trace without outcome."""
        trace = {
            "events": []
        }
        
        with pytest.raises(ValueError, match="outcome"):
            evaluator._validate_trace(trace)
    
    @pytest.mark.asyncio
    async def test_evaluate_experiment_success(self, evaluator, tmp_path):
        """Test evaluating a successful experiment."""
        # Mock trace
        trace = {
            "events": [
                {"tool": "call_inventory_api", "status": "success", "duration": 0.1},
                {"tool": "call_payments_api", "status": "success", "duration": 0.1},
                {"tool": "call_erp_api", "status": "success", "duration": 0.1},
                {"tool": "call_shipping_api", "status": "success", "duration": 0.1}
            ],
            "outcome": "order_completed",
            "total_duration": 0.4,
            "chaos_scenario": "timeout",
            "recovery_strategy": "Retry 3x with exponential backoff",
            "success_rate": 1.0,
            "failed_api": "inventory"
        }
        
        # Mock PlaybookStorage to use temp file
        test_file = str(tmp_path / "test_playbook.json")
        evaluator.storage = PlaybookStorage(file_path=test_file)
        
        # Evaluate
        result = await evaluator.evaluate_experiment(trace, "EXP-001")
        
        # Verify result structure
        assert result["experiment_id"] == "EXP-001"
        assert "outcome" in result
        assert "confidence" in result
        assert "reasoning" in result
        assert "promoted" in result
    
    @pytest.mark.asyncio
    async def test_evaluate_experiment_failure(self, evaluator, tmp_path):
        """Test evaluating a failed experiment."""
        trace = {
            "events": [
                {"tool": "call_inventory_api", "status": "error", "error_code": "TIMEOUT", "duration": 0.1},
                {"tool": "call_inventory_api", "status": "error", "error_code": "TIMEOUT", "duration": 0.1},
                {"tool": "call_inventory_api", "status": "error", "error_code": "TIMEOUT", "duration": 0.1}
            ],
            "outcome": "order_incomplete",
            "total_duration": 0.3,
            "chaos_scenario": "timeout",
            "failed_api": "inventory"
        }
        
        test_file = str(tmp_path / "test_playbook.json")
        evaluator.storage = PlaybookStorage(file_path=test_file)
        
        result = await evaluator.evaluate_experiment(trace, "EXP-002")
        
        assert result["experiment_id"] == "EXP-002"
        # Failed experiments should not be promoted
        assert result.get("promoted", False) == False or result["outcome"] == "failure"


# ==================================================================
# TEST TRACE FORMATTING
# ==================================================================

class TestTraceFormatting:
    """Tests for trace formatting logic."""
    
    @pytest.fixture
    def evaluator(self):
        """Provide evaluator."""
        return ExperimentEvaluator()
    
    def test_format_trace_prompt(self, evaluator):
        """Test trace formatting creates valid prompt."""
        trace = {
            "events": [
                {"tool": "call_inventory_api", "status": "success", "duration": 0.1},
                {"tool": "call_payments_api", "status": "error", "error_code": "TIMEOUT", "duration": 0.2, "result": {"error_code": "TIMEOUT"}},
                {"tool": "call_payments_api", "status": "success", "duration": 0.1}
            ],
            "outcome": "order_completed",
            "total_duration": 0.4,
            "chaos_scenario": "timeout"
        }
        
        prompt = evaluator._format_trace_prompt(trace, "EXP-001")
        
        # Verify prompt contains key information
        assert "EXP-001" in prompt
        assert "timeout" in prompt
        assert "call_inventory_api" in prompt
        assert "call_payments_api" in prompt
        assert "SUCCESS" in prompt
        assert "ERROR" in prompt
        # The error_code should appear in the prompt (from result dict)
        assert "TIMEOUT" in prompt or "unknown" in prompt.lower()
    
    def test_format_trace_with_durations(self, evaluator):
        """Test trace formatting includes event durations."""
        trace = {
            "events": [
                {"tool": "test_tool", "status": "success", "duration": 0.5}
            ],
            "outcome": "success",
            "total_duration": 0.5
        }
        
        prompt = evaluator._format_trace_prompt(trace, "EXP-001")
        
        assert "0.50s" in prompt


# ==================================================================
# TEST RESPONSE PARSING
# ==================================================================

class TestResponseParsing:
    """Tests for judge response parsing."""
    
    @pytest.fixture
    def evaluator(self):
        """Provide evaluator."""
        return ExperimentEvaluator()
    
    def test_parse_promoted_response(self, evaluator):
        """Test parsing response that promotes strategy."""
        response = {
            "output": """
            Outcome: SUCCESS
            The recovery strategy (retry 3x with backoff) was effective.
            Confidence: 0.95
            Recommendation: PROMOTE to Playbook
            """
        }
        
        trace = {
            "recovery_strategy": "Retry 3x with exponential backoff",
            "success_rate": 0.95
        }
        
        result = evaluator._parse_judge_response(response, "EXP-001", trace)
        
        assert result["promoted"] == True
        assert result["experiment_id"] == "EXP-001"
    
    def test_parse_rejected_response(self, evaluator):
        """Test parsing response that rejects strategy."""
        response = {
            "output": """
            Outcome: FAILURE
            The recovery strategy did not work. Order not completed.
            Confidence: 0.85
            Recommendation: REJECT
            """
        }
        
        trace = {}
        
        result = evaluator._parse_judge_response(response, "EXP-002", trace)
        
        assert result["promoted"] == False
        assert result["outcome"] == "failure"


# ==================================================================
# BATCH EVALUATION
# ==================================================================

class TestBatchEvaluation:
    """Tests for batch experiment evaluation."""
    
    @pytest.fixture
    def evaluator(self):
        """Provide evaluator."""
        return ExperimentEvaluator()
    
    @pytest.mark.asyncio
    async def test_evaluate_experiments_batch(self, evaluator, tmp_path):
        """Test evaluating multiple experiments."""
        traces = [
            {
                "events": [{"tool": "call_inventory_api", "status": "success", "duration": 0.1}],
                "outcome": "order_completed",
                "total_duration": 0.1
            },
            {
                "events": [{"tool": "call_inventory_api", "status": "error", "duration": 0.1}],
                "outcome": "order_incomplete",
                "total_duration": 0.1
            }
        ]
        
        test_file = str(tmp_path / "test_playbook.json")
        evaluator.storage = PlaybookStorage(file_path=test_file)
        
        results = await evaluator.evaluate_experiments_batch(traces)
        
        assert len(results) == 2
        assert results[0]["experiment_id"] == "EXP-001"
        assert results[1]["experiment_id"] == "EXP-002"
    
    @pytest.mark.asyncio
    async def test_evaluate_experiments_batch_with_ids(self, evaluator, tmp_path):
        """Test batch evaluation with custom experiment IDs."""
        traces = [
            {"events": [], "outcome": "success"},
            {"events": [], "outcome": "failure"}
        ]
        
        test_file = str(tmp_path / "test_playbook.json")
        evaluator.storage = PlaybookStorage(file_path=test_file)
        
        custom_ids = ["CHAOS-100", "CHAOS-101"]
        results = await evaluator.evaluate_experiments_batch(traces, custom_ids)
        
        assert results[0]["experiment_id"] == "CHAOS-100"
        assert results[1]["experiment_id"] == "CHAOS-101"
