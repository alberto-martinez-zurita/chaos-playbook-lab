"""Shared fixtures for unit tests."""
from __future__ import annotations

import json
from typing import Any, Dict, Optional
from unittest.mock import AsyncMock

import pytest

from chaos_engine.core.types import Status


# ---------------------------------------------------------------------------
# Executor fixtures (for CircuitBreaker and PetstoreAgent tests)
# ---------------------------------------------------------------------------

class _MockSuccessExecutor:
    async def send_request(
        self, method: str, endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        json_body: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        return {"status": Status.SUCCESS, "code": 200, "data": {"id": 123, "name": "MockPet"}}

    def calculate_jittered_backoff(self, seconds: float) -> float:
        return seconds


class _MockFailingExecutor:
    async def send_request(
        self, method: str, endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        json_body: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        return {"status": Status.ERROR, "code": 500, "message": "Simulated failure"}

    def calculate_jittered_backoff(self, seconds: float) -> float:
        return seconds


@pytest.fixture
def mock_executor():
    return _MockSuccessExecutor()


@pytest.fixture
def mock_failing_executor():
    return _MockFailingExecutor()


# ---------------------------------------------------------------------------
# PetstoreAgent fixtures
# ---------------------------------------------------------------------------

class _MockLLMConstructor:
    def __init__(self, *args, **kwargs):
        pass


@pytest.fixture
def mock_llm_constructor():
    return _MockLLMConstructor


@pytest.fixture
def temp_playbook_file(tmp_path):
    playbook = {
        "find_product": {
            "500": {"strategy": "retry_exponential_backoff", "reasoning": "Server error", "config": {"base_delay": 1.0, "max_retries": 3}}
        },
        "default": {"strategy": "escalate_to_human", "reasoning": "Unknown error", "config": {}}
    }
    path = tmp_path / "test_playbook.json"
    path.write_text(json.dumps(playbook), encoding="utf-8")
    return str(path)
