from google.adk.agents import LlmAgent, LoopAgent
from google.adk.models.google_llm import Gemini
from google.adk.runners import InMemoryRunner
import os
import httpx
import random
import json
from pathlib import Path
import asyncio
from typing import Any, Dict, Optional
from google.adk.models.google_llm import Gemini
from google.genai import types
from chaos_engine.chaos.proxy import ChaosProxy 
from chaos_engine.core.playbook_manager import PlaybookManager
from dotenv import load_dotenv

load_dotenv()

chaos_proxy = ChaosProxy(failure_rate=0.1, seed=42, mock_mode=False)
 
#load previous playbook to resume
playbook = PlaybookManager("data/playbook_training.json")
 
#define the opration to get playbooks and addend a new case used during the training.
def get_playbook():
    return playbook.get_all()

# Tool 1: GET /store/inventory
async def get_inventory() -> dict:
    """Returns a map of status codes to quantities from the store."""
    return await chaos_proxy.send_request("GET", "/store/inventory")
 
# Tool 2: GET /pet/findByStatus
async def find_pets_by_status(status: str = "available") -> dict:
    """Finds Pets by status.
   
    Args:
        status: Status values that need to be considered for filter (available, pending, sold).
    """
    return await chaos_proxy.send_request("GET", "/pet/findByStatus", params={"status": status})
 
# Tool 3: POST /store/order
async def place_order(pet_id: int, quantity: int) -> dict:
    """Place an order for a pet.
   
    Args:
        pet_id: ID of the pet that needs to be ordered.
        quantity: Quantity of the pet to order.
    """
    body = {
        "petId": pet_id,
        "quantity": quantity,
        "status": "placed",
        "complete": False
    }
    return await chaos_proxy.send_request("POST", "/store/order", json_body=body)
 
# Tool 4: PUT /pet (Update an existing pet)
async def update_pet_status(pet_id: int, name: str, status: str) -> dict:
    """Update an existing pet status.
   
    Args:
        pet_id: ID of the pet.
        name: Name of the pet (required by API).
        status: New status (available, pending, sold).
    """
    body = {
        "id": pet_id,
        "name": name,
        "status": status,
        "photoUrls": [] # Required by schema
    }
    return await chaos_proxy.send_request("PUT", "/pet", json_body=body)
 
async def wait_seconds(seconds: float) -> dict:
    """Pauses execution for a specified number of seconds.
   
    Use this when a playbook strategy recommends waiting or backing off
    before retrying an operation.
    """
    print(f"⏳ AGENT WAITING: {seconds}s (Executing Backoff Strategy)...")
    await asyncio.sleep(seconds)
    return {"status": "success", "message": f"Waited {seconds} seconds"}

agent=root_agennt= LlmAgent(
    name="OrderAgent",
    model=Gemini(
        model="gemini-2.5-flash-lite",
        retry_options=types.HttpRetryOptions(
            attempts=5,
            exp_base=7,
            initial_delay=1,
            http_status_codes=[429, 500, 503, 504],
        )
    ),
    instruction="""
You are the ORDER AGENT.

Your mission is to reliably complete the pet purchase process using the available tools and the recovery playbook.

==========================
PRIMARY OBJECTIVE
==========================
Execute the PURCHASE FLOW in this exact order unless the playbook instructs otherwise:

1. Retrieve the inventory → (get_inventory)
2. Search for available pets → (find_pets_by_status)
   - Select EXACTLY ONE valid pet ID returned by the tool.
3. Purchase the selected pet → (place_order)
4. Mark the pet as sold → (update_pet_status)

The purchase is successful only when all four steps complete correctly.

==========================
FAILURE & RECOVERY PROTOCOL
==========================
If ANY tool call fails (HTTP error, timeout, null/invalid data, malformed response):

1. Immediately call → get_playbook
2. When the playbook returns a strategy:
   - Do NOT ask the user.
   - Execute the strategy exactly as provided.
   - If the strategy instructs a retry, perform that retry.
   - If the strategy instructs waiting, call wait_seconds with the provided duration.
   - If the strategy instructs skipping or altering steps, follow it exactly.
   - If the strategy is "escalate_to_human", stop execution and return a message explaining that human intervention is required.

==========================
EXECUTION RULES
==========================
- Respect the purchase flow strictly unless the playbook overrides it.
- Never invent or assume data not returned by tools.
- Never select a pet ID that is not present in the tool result.
- The selected pet ID must remain the same for the entire flow.
- After a failure, never proceed until the playbook instructs you how.
- If the playbook loops or gives conflicting instructions, escalate to human.

==========================
FINAL OUTPUT REQUIREMENTS
==========================
At the end, return a simple JSON summary with:

{
  "selected_pet_id": <id or null>,
  "completed": true|false,
  "error": <null or string>
}

If escalation occurs, set "completed" to false and include a human-readable explanation in "error".
    """,
    tools=[get_inventory, find_pets_by_status, place_order, update_pet_status, wait_seconds, get_playbook]
)
 