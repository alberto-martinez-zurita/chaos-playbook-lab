"""Experiment trace writer for --trace-llm mode.

Writes one JSONL file per experiment directory, where each line captures a
single LLM turn with full request/response data and harness enrichment info.
"""
from __future__ import annotations

import hashlib
import json
import logging
import threading
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class TraceTurn:
    """One LLM interaction within an experiment."""

    experiment_id: str
    turn: int
    timestamp: float
    # LLM request
    system_prompt_hash: str
    user_message: str
    # LLM response
    raw_response: str
    parsed_action: Optional[dict] = None
    parse_error: Optional[str] = None
    # Harness enrichment (HTTP agent only)
    body_before_enrich: Optional[dict] = None
    body_after_enrich: Optional[dict] = None
    # Tool execution result
    tool_status: Optional[str] = None
    tool_status_code: Optional[int] = None
    tool_message: Optional[str] = None
    step_name: Optional[str] = None


class ExperimentTracer:
    """Thread-safe JSONL trace writer.

    Usage::

        tracer = ExperimentTracer(Path("reports/.../run_paper_http_gemma/"))
        tracer.log_turn(TraceTurn(...))
        tracer.flush()
    """

    def __init__(self, output_dir: Path) -> None:
        self._path = output_dir / "trace.jsonl"
        self._lock = threading.Lock()
        output_dir.mkdir(parents=True, exist_ok=True)
        self._file = open(self._path, "a", encoding="utf-8")
        logger.info("Trace writer opened: %s", self._path)

    def log_turn(self, turn: TraceTurn) -> None:
        line = json.dumps(asdict(turn), default=str, ensure_ascii=False)
        with self._lock:
            self._file.write(line + "\n")
            self._file.flush()

    def close(self) -> None:
        with self._lock:
            self._file.close()

    def __enter__(self) -> "ExperimentTracer":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()


def prompt_hash(prompt: str) -> str:
    """SHA-256 truncated to 12 hex chars — enough to identify prompt variants."""
    return hashlib.sha256(prompt.encode()).hexdigest()[:12]
