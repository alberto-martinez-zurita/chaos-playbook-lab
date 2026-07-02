"""
Chaos Playbook Storage Module.

Provides JSON-based storage for chaos recovery strategy matrix.
Thread-safe operations with asyncio.Lock.
Supports hot-reload via file modification monitoring.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class PlaybookStorage:
    """
    JSON-based storage for chaos recovery strategy matrix.

    Supports HTTP, MCP, and A2A failure types using a unified
    ``operation → failure_key → strategy`` schema.

    Schema::

        {
            "get_inventory": {
                "500": {"strategy": "retry_exponential_backoff", "config": {...}}
            },
            "call_tool": {
                "tool_not_found": {"strategy": "fail_fast"},
                "context_overflow": {"strategy": "escalate_to_human"}
            },
            "send_task": {
                "agent_not_found": {"strategy": "fail_fast"},
                "timeout": {"strategy": "retry_exponential_backoff", "config": {"base_delay": 2.0}}
            },
            "default": {"strategy": "escalate_to_human", "config": {}}
        }
    """

    def __init__(self, file_path: str = "data/chaos_playbook.json", watch: bool = False):
        self.file_path = Path(file_path)
        self._lock = asyncio.Lock()
        self._cache: Dict[str, Any] | None = None
        self._last_mtime: float = 0.0
        self._watch = watch
        self._watch_task: asyncio.Task | None = None
        self._ensure_storage_exists()

    def _ensure_storage_exists(self):
        """Ensure data directory and file exist."""
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.file_path.exists():
            with open(self.file_path, "w") as f:
                json.dump({}, f, indent=2)

     
    def _read_playbook_unlocked(self) -> dict:
        """Read playbook from disk without locking (caller must hold lock)."""
        if not self.file_path.exists() or self.file_path.stat().st_size == 0:
            return {}
        try:
            with open(self.file_path, 'r') as f:
                return json.load(f)
        except json.JSONDecodeError:
            return {}

    def _write_playbook_unlocked(self, data: Dict[str, Any]) -> None:
        """Write playbook to disk without locking (caller must hold lock)."""
        with open(self.file_path, "w") as f:
            json.dump(data, f, indent=2)

    async def _read_playbook(self) -> dict:
        async with self._lock:
            return self._read_playbook_unlocked()

    async def _write_playbook(self, data: Dict[str, Any]) -> None:
        async with self._lock:
            self._write_playbook_unlocked(data)

    # ---------------------------------------------------------
    # Public API
    # ---------------------------------------------------------

    async def load_playbook(self) -> Dict[str, Any]:
        """Return full strategy matrix."""
        return await self._read_playbook()

    async def save_playbook(self, playbook: Dict[str, Any]) -> None:
        """Replace entire playbook."""
        await self._write_playbook(playbook)

    async def add_or_update_strategy(
        self,
        operation: str,
        failure_key: str,
        strategy: str,
        reasoning: str = "",
        config: Optional[Dict[str, Any]] = None
    ) -> None:
        """Add or update strategy rule for operation + failure_key.

        Uses a single lock acquisition for the read-modify-write cycle
        to prevent TOCTOU race conditions.
        """
        if config is None:
            config = {}

        async with self._lock:
            playbook = self._read_playbook_unlocked()

            if operation not in playbook:
                playbook[operation] = {}

            playbook[operation][str(failure_key)] = {
                "strategy": strategy,
                "reasoning": reasoning,
                "config": config
            }

            self._write_playbook_unlocked(playbook)

    async def remove_strategy(
        self,
        operation: str,
        failure_key: str,
    ) -> None:
        """Remove a strategy rule (atomic read-modify-write)."""
        async with self._lock:
            playbook = self._read_playbook_unlocked()
            if operation in playbook and str(failure_key) in playbook[operation]:
                del playbook[operation][str(failure_key)]
            self._write_playbook_unlocked(playbook)

    async def set_default_strategy(
        self,
        strategy: str,
        reasoning: str = "",
        config: Optional[Dict[str, Any]] = None
    ) -> None:
        """Set default fallback strategy (atomic read-modify-write)."""
        if config is None:
            config = {}

        async with self._lock:
            playbook = self._read_playbook_unlocked()
            playbook["default"] = {
                "strategy": strategy,
                "reasoning": reasoning,
                "config": config
            }
            self._write_playbook_unlocked(playbook)

    async def resolve_strategy(
        self,
        operation: str,
        failure_key: str,
    ) -> Optional[Dict[str, Any]]:
        """Resolve strategy for a given operation and failure key.

        Works with any failure key format:
        - HTTP status codes: ``"500"``, ``"429"``
        - MCP failure types: ``"tool_not_found"``, ``"context_overflow"``
        - A2A failure types: ``"agent_not_found"``, ``"timeout"``

        Falls back to ``"default"`` entry if no specific match found.
        """

        playbook = await self._read_playbook()

        op_rules = playbook.get(operation, {})
        if str(failure_key) in op_rules:
            return op_rules[str(failure_key)]

        return playbook.get("default")

    # ---------------------------------------------------------
    # Hot-reload (E.2)
    # ---------------------------------------------------------

    def _file_changed(self) -> bool:
        """Check if the playbook file has been modified since last read."""
        try:
            mtime = os.path.getmtime(self.file_path)
            return mtime > self._last_mtime
        except OSError:
            return False

    async def _reload_if_changed(self) -> None:
        """Reload the playbook from disk if the file has been modified."""
        if self._file_changed():
            self._cache = await self._read_playbook()
            self._last_mtime = os.path.getmtime(self.file_path)
            logger.info("Playbook hot-reloaded from %s", self.file_path)

    async def get_cached_playbook(self) -> Dict[str, Any]:
        """Return the playbook, reloading from disk if the file changed.

        This is the preferred read path for long-running processes that
        want to pick up playbook changes without restarting.
        """
        if self._cache is None or self._file_changed():
            await self._reload_if_changed()
        return self._cache or {}

    async def start_watching(self, poll_interval: float = 2.0) -> None:
        """Start a background task that polls for playbook file changes."""
        if self._watch_task is not None:
            return

        async def _poll() -> None:
            while True:
                await asyncio.sleep(poll_interval)
                await self._reload_if_changed()

        self._watch_task = asyncio.create_task(_poll())
        logger.info("Started playbook file watcher (interval=%.1fs)", poll_interval)

    async def stop_watching(self) -> None:
        """Stop the background file watcher."""
        if self._watch_task is not None:
            self._watch_task.cancel()
            try:
                await self._watch_task
            except asyncio.CancelledError:
                pass
            self._watch_task = None
            logger.info("Stopped playbook file watcher")