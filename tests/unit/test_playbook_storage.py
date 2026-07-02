"""Tests for PlaybookStorage — JSON strategy matrix with hot-reload."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from chaos_engine.core.playbook_storage import PlaybookStorage


# --- FIXTURES ---

@pytest.fixture
def temp_storage_file(tmp_path):
    """Create a temporary path for the playbook JSON file."""
    d = tmp_path / "data"
    d.mkdir()
    return str(d / "test_chaos_playbook.json")


# --- TESTS ---

@pytest.mark.asyncio
async def test_storage_initialization_creates_file(temp_storage_file):
    """Verify that if the file doesn't exist, an empty JSON object is created."""
    storage = PlaybookStorage(file_path=temp_storage_file)

    assert Path(temp_storage_file).exists()

    with open(temp_storage_file, "r") as f:
        data = json.load(f)
        assert data == {}


@pytest.mark.asyncio
async def test_add_and_resolve_strategy(temp_storage_file):
    """Verify adding a strategy and resolving it by api + status_code."""
    storage = PlaybookStorage(file_path=temp_storage_file)

    await storage.add_or_update_strategy(
        operation="find_product",
        failure_key="500",
        strategy="retry_exponential_backoff",
        reasoning="Server error, safe to retry",
        config={"base_delay": 1.0, "max_retries": 3},
    )

    resolved = await storage.resolve_strategy("find_product", "500")
    assert resolved is not None
    assert resolved["strategy"] == "retry_exponential_backoff"
    assert resolved["config"]["base_delay"] == 1.0


@pytest.mark.asyncio
async def test_resolve_falls_back_to_default(temp_storage_file):
    """Verify fallback to default strategy when specific rule not found."""
    storage = PlaybookStorage(file_path=temp_storage_file)

    await storage.set_default_strategy(
        strategy="escalate_to_human",
        reasoning="Unknown scenario",
    )

    resolved = await storage.resolve_strategy("unknown_api", "999")
    assert resolved is not None
    assert resolved["strategy"] == "escalate_to_human"


@pytest.mark.asyncio
async def test_resolve_returns_none_when_no_match(temp_storage_file):
    """Verify None returned when no strategy matches and no default set."""
    storage = PlaybookStorage(file_path=temp_storage_file)

    resolved = await storage.resolve_strategy("unknown_api", "500")
    assert resolved is None


@pytest.mark.asyncio
async def test_remove_strategy(temp_storage_file):
    """Verify strategy removal."""
    storage = PlaybookStorage(file_path=temp_storage_file)

    await storage.add_or_update_strategy(
        operation="place_order", failure_key="429",
        strategy="wait_and_retry", config={"wait_seconds": 5},
    )
    await storage.remove_strategy("place_order", "429")

    resolved = await storage.resolve_strategy("place_order", "429")
    assert resolved is None


@pytest.mark.asyncio
async def test_save_and_load_full_playbook(temp_storage_file):
    """Verify full playbook save/load round trip."""
    storage = PlaybookStorage(file_path=temp_storage_file)

    playbook = {
        "find_product": {
            "500": {"strategy": "retry_exponential_backoff", "config": {"base_delay": 1.0}},
        },
        "default": {"strategy": "fail_fast", "config": {}},
    }

    await storage.save_playbook(playbook)
    loaded = await storage.load_playbook()

    assert loaded["find_product"]["500"]["strategy"] == "retry_exponential_backoff"
    assert loaded["default"]["strategy"] == "fail_fast"


@pytest.mark.asyncio
async def test_hot_reload_detects_file_change(temp_storage_file):
    """Verify get_cached_playbook picks up external file changes."""
    storage = PlaybookStorage(file_path=temp_storage_file)

    # Prime the cache
    await storage.get_cached_playbook()

    # External write simulating another process updating the file
    new_data = {"external_update": {"200": {"strategy": "fail_fast"}}}
    with open(temp_storage_file, "w") as f:
        json.dump(new_data, f)

    # Force mtime change detection
    import os
    import time
    # Touch file to ensure mtime differs
    os.utime(temp_storage_file, (time.time() + 1, time.time() + 1))

    cached = await storage.get_cached_playbook()
    assert "external_update" in cached


# --- MCP/A2A PLAYBOOK RESOLUTION ---

@pytest.mark.asyncio
async def test_resolve_mcp_failure_type(temp_storage_file):
    """Playbook resolves MCP failure types (string keys, not HTTP codes)."""
    storage = PlaybookStorage(file_path=temp_storage_file)

    await storage.add_or_update_strategy(
        operation="call_tool",
        failure_key="tool_not_found",
        strategy="fail_fast",
        reasoning="Tool does not exist on server",
    )
    await storage.add_or_update_strategy(
        operation="call_tool",
        failure_key="context_overflow",
        strategy="escalate_to_human",
        reasoning="Context window exceeded",
    )

    resolved = await storage.resolve_strategy("call_tool", "tool_not_found")
    assert resolved is not None
    assert resolved["strategy"] == "fail_fast"

    resolved2 = await storage.resolve_strategy("call_tool", "context_overflow")
    assert resolved2["strategy"] == "escalate_to_human"


@pytest.mark.asyncio
async def test_resolve_a2a_failure_type(temp_storage_file):
    """Playbook resolves A2A failure types."""
    storage = PlaybookStorage(file_path=temp_storage_file)

    await storage.add_or_update_strategy(
        operation="send_task",
        failure_key="agent_not_found",
        strategy="fail_fast",
    )
    await storage.add_or_update_strategy(
        operation="send_task",
        failure_key="timeout",
        strategy="retry_exponential_backoff",
        config={"base_delay": 2.0, "max_retries": 3},
    )

    resolved = await storage.resolve_strategy("send_task", "timeout")
    assert resolved is not None
    assert resolved["strategy"] == "retry_exponential_backoff"
    assert resolved["config"]["base_delay"] == 2.0


@pytest.mark.asyncio
async def test_mixed_http_mcp_a2a_playbook(temp_storage_file):
    """A single playbook can contain HTTP, MCP, and A2A entries."""
    storage = PlaybookStorage(file_path=temp_storage_file)

    playbook = {
        "find_product": {
            "500": {"strategy": "retry_exponential_backoff", "config": {"base_delay": 1.0}},
        },
        "call_tool": {
            "rate_limited": {"strategy": "retry_linear_backoff", "config": {"delay": 5.0}},
        },
        "send_task": {
            "partial_failure": {"strategy": "retry_linear_backoff", "config": {"delay": 1.0}},
        },
        "default": {"strategy": "escalate_to_human", "config": {}},
    }
    await storage.save_playbook(playbook)

    # HTTP
    r1 = await storage.resolve_strategy("find_product", "500")
    assert r1["strategy"] == "retry_exponential_backoff"

    # MCP
    r2 = await storage.resolve_strategy("call_tool", "rate_limited")
    assert r2["strategy"] == "retry_linear_backoff"

    # A2A
    r3 = await storage.resolve_strategy("send_task", "partial_failure")
    assert r3["strategy"] == "retry_linear_backoff"

    # Unknown → default
    r4 = await storage.resolve_strategy("query_status", "unknown_error")
    assert r4["strategy"] == "escalate_to_human"
