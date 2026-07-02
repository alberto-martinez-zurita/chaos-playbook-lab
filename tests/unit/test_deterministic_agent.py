from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

import pytest

from chaos_engine.agents.deterministic import DeterministicAgent


# ---------------------------------------------------------------------------
# Inline mock — no external fixtures, no mocks.py import
# ---------------------------------------------------------------------------

class MockExecutor:
    """Test double for the Executor protocol."""

    def __init__(self, responses: List[Dict[str, Any]]):
        self.responses = list(responses)
        self.call_count = 0

    async def send_request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict] = None,
        json_body: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        self.call_count += 1
        if self.responses:
            return self.responses.pop(0)
        return {"status": "success", "code": 200, "data": {}}

    def calculate_jittered_backoff(self, seconds: float) -> float:
        return seconds  # No jitter in tests


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

SUCCESS = {"status": "success", "code": 200, "data": {}}
FAILURE_500 = {"status": "error", "code": 500, "message": "Server Error"}
FAILURE_429 = {"status": "error", "code": 429, "message": "Rate Limited"}
FAILURE_408 = {"status": "error", "code": 408, "message": "Timeout"}


def _write_playbook(tmp_path, content: dict) -> str:
    """Write a JSON playbook to a temp file and return the path string."""
    p = tmp_path / "playbook.json"
    p.write_text(json.dumps(content), encoding="utf-8")
    return str(p)


# ---------------------------------------------------------------------------
# 1. Successful 4-step workflow
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_all_steps_succeed(tmp_path):
    """All 4 steps succeed → status=success, steps_completed has all 4 names."""
    playbook_path = _write_playbook(tmp_path, {})
    executor = MockExecutor([SUCCESS, SUCCESS, SUCCESS, SUCCESS])
    agent = DeterministicAgent(tool_executor=executor, playbook_path=playbook_path)

    result = await agent.run()

    assert result["status"] == "success"
    assert result["failed_at"] is None
    assert result["steps_completed"] == [
        "find_product",
        "check_inventory",
        "place_order",
        "confirm_order",
    ]
    assert executor.call_count == 4
    assert result["retries"] == 0


# ---------------------------------------------------------------------------
# 2. Failure at each individual step (parametrized)
# ---------------------------------------------------------------------------

_ALL_STEPS = ["find_product", "check_inventory", "place_order", "confirm_order"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "responses, expected_failed_at, expected_steps_completed",
    [
        pytest.param(
            [FAILURE_500],
            "find_product",
            [],
            id="failure_at_find_product",
        ),
        pytest.param(
            [SUCCESS, FAILURE_500],
            "check_inventory",
            ["find_product"],
            id="failure_at_check_inventory",
        ),
        pytest.param(
            [SUCCESS, SUCCESS, FAILURE_500],
            "place_order",
            ["find_product", "check_inventory"],
            id="failure_at_place_order",
        ),
        pytest.param(
            [SUCCESS, SUCCESS, SUCCESS, FAILURE_500],
            "confirm_order",
            ["find_product", "check_inventory", "place_order"],
            id="failure_at_confirm_order",
        ),
    ],
)
async def test_failure_at_step(
    tmp_path, responses, expected_failed_at, expected_steps_completed
):
    """Failing at step N → failed_at is that step, prior steps are completed."""
    playbook_path = _write_playbook(tmp_path, {})
    executor = MockExecutor(responses)
    agent = DeterministicAgent(tool_executor=executor, playbook_path=playbook_path)

    result = await agent.run()

    assert result["status"] == "failure"
    assert result["failed_at"] == expected_failed_at
    assert result["steps_completed"] == expected_steps_completed


# ---------------------------------------------------------------------------
# 3. Retry strategies
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_retry_linear_backoff_succeeds_on_second_attempt(tmp_path):
    """linear_backoff strategy: initial failure then success on retry."""
    playbook = {
        "find_product": {
            "408": {
                "strategy": "retry_linear_backoff",
                "config": {"delay": 1.0, "max_retries": 3},
            }
        }
    }
    playbook_path = _write_playbook(tmp_path, playbook)
    # First call fails with 408, second call succeeds
    executor = MockExecutor([FAILURE_408, SUCCESS, SUCCESS, SUCCESS])
    agent = DeterministicAgent(tool_executor=executor, playbook_path=playbook_path)

    result = await agent.run()

    assert result["status"] == "success"
    assert result["retries"] == 1
    # The jitter-free delay for attempt=1 with delay=1.0 is 1.0
    assert result["simulated_delay_s"] == 1.0


@pytest.mark.asyncio
async def test_retry_exponential_backoff_succeeds_on_third_attempt(tmp_path):
    """exponential_backoff strategy: two failures then success."""
    playbook = {
        "find_product": {
            "500": {
                "strategy": "retry_exponential_backoff",
                "config": {"base_delay": 1.0, "max_retries": 3},
            }
        }
    }
    playbook_path = _write_playbook(tmp_path, playbook)
    # Initial fail, retry 1 fail, retry 2 succeed
    executor = MockExecutor([FAILURE_500, FAILURE_500, SUCCESS, SUCCESS, SUCCESS, SUCCESS])
    agent = DeterministicAgent(tool_executor=executor, playbook_path=playbook_path)

    result = await agent.run()

    assert result["status"] == "success"
    assert result["retries"] == 2
    # Delays: attempt1 → 1.0*(2**0)=1.0, attempt2 → 1.0*(2**1)=2.0  total=3.0
    assert result["simulated_delay_s"] == pytest.approx(3.0)


@pytest.mark.asyncio
async def test_retry_wait_and_retry_succeeds(tmp_path):
    """wait_and_retry strategy: constant wait between retries."""
    playbook = {
        "find_product": {
            "429": {
                "strategy": "wait_and_retry",
                "config": {"wait_seconds": 5.0, "max_retries": 3},
            }
        }
    }
    playbook_path = _write_playbook(tmp_path, playbook)
    # Initial fail with 429, then success on first retry
    executor = MockExecutor([FAILURE_429, SUCCESS, SUCCESS, SUCCESS, SUCCESS])
    agent = DeterministicAgent(tool_executor=executor, playbook_path=playbook_path)

    result = await agent.run()

    assert result["status"] == "success"
    assert result["retries"] == 1
    assert result["simulated_delay_s"] == pytest.approx(5.0)


@pytest.mark.asyncio
async def test_retry_exhausted_reports_failure(tmp_path):
    """All retries exhausted → status=failure, retries equals max_retries."""
    max_retries = 3
    playbook = {
        "find_product": {
            "500": {
                "strategy": "retry_exponential_backoff",
                "config": {"base_delay": 1.0, "max_retries": max_retries},
            }
        }
    }
    playbook_path = _write_playbook(tmp_path, playbook)
    # Initial + 3 retries = 4 total failures
    executor = MockExecutor([FAILURE_500] * (1 + max_retries))
    agent = DeterministicAgent(tool_executor=executor, playbook_path=playbook_path)

    result = await agent.run()

    assert result["status"] == "failure"
    assert result["failed_at"] == "find_product"
    assert result["retries"] == max_retries


# ---------------------------------------------------------------------------
# 4. Playbook fallback to "default" entry
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_fallback_to_default_playbook_strategy(tmp_path):
    """When tool-specific entry is missing, use the 'default' entry."""
    playbook = {
        "default": {
            "strategy": "retry_linear_backoff",
            "config": {"delay": 2.0, "max_retries": 2},
        }
    }
    playbook_path = _write_playbook(tmp_path, playbook)
    # Unknown error code 503 not in find_product block → falls to default
    failure_503 = {"status": "error", "code": 503, "message": "Unavailable"}
    executor = MockExecutor([failure_503, SUCCESS, SUCCESS, SUCCESS, SUCCESS])
    agent = DeterministicAgent(tool_executor=executor, playbook_path=playbook_path)

    result = await agent.run()

    assert result["status"] == "success"
    assert result["retries"] == 1
    # delay=2.0 * attempt=1 = 2.0
    assert result["simulated_delay_s"] == pytest.approx(2.0)


# ---------------------------------------------------------------------------
# 5. Empty playbook → fail_fast default
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_empty_playbook_uses_fail_fast(tmp_path):
    """Empty playbook dict → _resolve_strategy returns fail_fast → no retries."""
    playbook_path = _write_playbook(tmp_path, {})
    executor = MockExecutor([FAILURE_500])
    agent = DeterministicAgent(tool_executor=executor, playbook_path=playbook_path)

    result = await agent.run()

    assert result["status"] == "failure"
    assert result["retries"] == 0
    assert result["failed_at"] == "find_product"
    # Only the single initial request should have been made
    assert executor.call_count == 1


# ---------------------------------------------------------------------------
# 6. Result shape — required keys always present
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_result_contains_required_keys(tmp_path):
    """Successful run must return all keys expected by ABTestRunner."""
    playbook_path = _write_playbook(tmp_path, {})
    executor = MockExecutor([SUCCESS, SUCCESS, SUCCESS, SUCCESS])
    agent = DeterministicAgent(tool_executor=executor, playbook_path=playbook_path)

    result = await agent.run()

    required_keys = {
        "status",
        "steps_completed",
        "failed_at",
        "duration_ms",
        "retries",
        "simulated_delay_s",
        "outcome",
        "agent_type",
    }
    assert required_keys.issubset(result.keys())


# ---------------------------------------------------------------------------
# 7-8. Non-retry strategies (fail_fast, escalate_to_human)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@pytest.mark.parametrize(
    "playbook_content",
    [
        pytest.param(
            {"find_product": {"500": {"strategy": "fail_fast", "config": {}}}},
            id="fail_fast",
        ),
        pytest.param(
            {"default": {"strategy": "escalate_to_human", "config": {}}},
            id="escalate_to_human",
        ),
    ],
)
async def test_non_retry_strategy_no_retry(tmp_path, playbook_content):
    """Non-retry strategies must not trigger any retry attempts."""
    playbook_path = _write_playbook(tmp_path, playbook_content)
    executor = MockExecutor([FAILURE_500])
    agent = DeterministicAgent(tool_executor=executor, playbook_path=playbook_path)

    result = await agent.run()

    assert result["status"] == "failure"
    assert result["retries"] == 0
    assert executor.call_count == 1


# ---------------------------------------------------------------------------
# 9. duration_ms is always a positive number
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_duration_ms_is_positive(tmp_path):
    """duration_ms must be a non-negative float regardless of outcome."""
    playbook_path = _write_playbook(tmp_path, {})
    executor = MockExecutor([FAILURE_500])
    agent = DeterministicAgent(tool_executor=executor, playbook_path=playbook_path)

    result = await agent.run()

    assert isinstance(result["duration_ms"], float)
    assert result["duration_ms"] >= 0.0


# ---------------------------------------------------------------------------
# 10. Bad/missing playbook file → falls back to empty dict (fail_fast)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_missing_playbook_file_fails_gracefully(tmp_path):
    """A non-existent playbook path produces an empty dict → fail_fast behaviour."""
    missing_path = str(tmp_path / "does_not_exist.json")
    executor = MockExecutor([FAILURE_500])
    agent = DeterministicAgent(tool_executor=executor, playbook_path=missing_path)

    result = await agent.run()

    # Should not raise; fail_fast applies because playbook_data is {}
    assert result["status"] == "failure"
    assert result["retries"] == 0
