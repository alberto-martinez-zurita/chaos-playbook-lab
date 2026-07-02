"""
Tools for interacting with the Chaos Playbook.

This module centralizes all functions related to reading from and writing to
the playbook, using the asynchronous PlaybookStorage.

Matrix-style schema:
{
  "api_name": {
    "status_code": {
      "strategy": "...",
      "reasoning": "...",
      "config": {...}
    }
  }
}
"""
from __future__ import annotations

from typing import Dict, TypedDict

from ..core.playbook_storage import PlaybookStorage


# ============================================================
# Response type
# ============================================================

class AddScenarioResponse(TypedDict):
    message: str


# ============================================================
# Playbook functions
# ============================================================

async def get_playbook(storage: PlaybookStorage) -> Dict:
    """
    Returns the full chaos playbook in matrix format:
    { "api_name": { "status_code": { "strategy": ..., "reasoning": ..., "config": {...} } } }
    """
    return await storage.load_playbook()


async def add_scenario_to_playbook(
    storage: PlaybookStorage,
    api: str,
    status_code: int,
    strategy_payload: Dict[str, object]
) -> AddScenarioResponse:
    """
    Adds a new scenario to the matrix-style playbook.

    Args:
        storage: PlaybookStorage instance
        api: API name, e.g., "get_inventory"
        status_code: HTTP status code or internal error code
        strategy_payload: Full structured dict:
            { "strategy": "...", "reasoning": "...", "config": {...} }

    Returns:
        AddScenarioResponse with confirmation message
    """
    # Load existing playbook
    playbook = await storage.load_playbook()

    # Ensure API entry exists
    if api not in playbook:
        playbook[api] = {}

    # Save scenario under the status code as string
    playbook[api][str(status_code)] = strategy_payload

    # Save via storage (respects asyncio.Lock)
    await storage.save_playbook(playbook)

    return {"message": f"Scenario added for {api} [{status_code}]"}


# ============================================================
# Optional helper for default scenario
# ============================================================

async def add_default_scenario(
    storage: PlaybookStorage,
    api: str
) -> AddScenarioResponse:
    """
    Adds a default escalation strategy for unknown errors.
    """
    default_payload = {
        "strategy": "escalate_to_human",
        "reasoning": "Unknown error scenario.",
        "config": {}
    }

    return await add_scenario_to_playbook(
        storage=storage,
        api=api,
        status_code="default",
        strategy_payload=default_payload
    )