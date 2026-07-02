"""Prompt loader — reads system prompts and playbook guidance from assets/prompts/.

Prompts are loaded once and cached for the process lifetime.
"""
from __future__ import annotations

import functools
from pathlib import Path

_PROMPTS_DIR = Path(__file__).resolve().parent.parent.parent.parent / "assets" / "prompts"


@functools.lru_cache(maxsize=32)
def load_prompt(name: str) -> str:
    """Load a prompt file by name (without extension).

    >>> load_prompt("http_system")
    'You are an AI agent executing an order workflow via HTTP APIs.\\n...'
    """
    path = _PROMPTS_DIR / f"{name}.txt"
    if not path.exists():
        raise FileNotFoundError(f"Prompt not found: {path}")
    return path.read_text(encoding="utf-8")
