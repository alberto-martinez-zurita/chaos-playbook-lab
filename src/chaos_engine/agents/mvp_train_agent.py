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
from core.chaos_proxy import ChaosProxy
from core.playbook_manager import PlaybookManager
from dotenv import load_dotenv
  
load_dotenv()


chaos_proxy = ChaosProxy(failure_rate=0.6,mock_mode=True) 
 

 
 #load previous playbook to resume
playbook = PlaybookManager("data/playbook_training.json")
 
#define the opration to get playbooks and addend a new case used during the training.
 
def get_playbook():
    return playbook.get_all()
 
def add_scenario_to_playbook(operation: str, status_code: str,strategy: str, reasoning: str,config: Optional[Dict[str, Any]] = None):
    playbook.add_operation_or_response(
        operation=operation,
        status_code=status_code,
        strategy=strategy,
        reasoning=reasoning,
        config=config
    )
       
 

 
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
 
 
async def train_agent():
    #agents definition to be moved in a separete file
   
    orderAgent = LlmAgent(
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
        Your mission is to complete the pet purchase process reliably, even under failures and API instability.
 
        ==========================
        PRIMARY OBJECTIVE
        ==========================
        Complete the PURCHASE FLOW:
 
        1. Check the inventory → (get_inventory)
        2. Look for an available pet → (find_pets_by_status)
           - Must select ONE valid pet ID from the results.
        3. Purchase that pet → (place_order)
        4. Mark the pet as sold → (update_pet_status)
 
        If all four steps succeed, the purchase is complete.
 
        ==========================
        MANDATORY REPORTING FORMAT
        ==========================
        For EVERY tool call you make, you MUST produce a structured log entry in this format:
 
        [STEP <n>]
        TOOL: <tool_name>
        PARAMS: <json>
        RESULT: <raw tool output | raw error>
        STRATEGY_DECISION: <what you decided and why>
 
        At the end, produce a final section:
 
        [FINAL_STATE]
        {
        "selected_pet_id": <id or null>,
        "retry_counters": { "<tool>": <number> },
        "last_error": <string or null>,
        "completed": true|false
        }
 
        ==========================
        STATE REQUIREMENTS
        ==========================
        You MUST track:
 
        - selected_pet_id
        - retry counters per tool
        - last_error
        - last_playbook_strategy
 
        Include these in the final output (steps_performed).
 
        ==========================
        FAILURE PROTOCOL (CRITICAL)
        ==========================
        If a tool call fails in ANY way (HTTP error, timeout, malformed response, null data):
 
        1. IMMEDIATELY call get_playbook
        2. When the playbook responds with a strategy:
            - DO NOT ask the user.
            - EXECUTE THE STRATEGY IMMEDIATELY.
 
 
        ==========================
        GENERAL RULES
        ==========================
        - Always follow the purchase flow strictly in order.
        - Never select a pet ID that does not appear in the results.
        - Never skip a failing step unless the playbook explicitly instructs it.
        - Never hallucinate successful results.
        - Your success metric is FINISHING THE PURCHASE UNASSISTED despite failures.
        - In case the strategy suggested is escalate_to_human, you have to stop the execution and return a message to let the human complete or correct the order procedure
    """,
    output_key="steps_performed",
    tools=[get_inventory, find_pets_by_status, place_order, update_pet_status, wait_seconds, get_playbook]
)
    playbookCreatorAgent = LlmAgent(
        name="PlaybookCreatorAgent",
        model=Gemini(
        model="gemini-2.5-flash-lite",
        retry_options=types.HttpRetryOptions(
        attempts=5,  # Maximum retry attempts
        exp_base=7,  # Delay multiplier
        initial_delay=1,
        http_status_codes=[429, 500, 503, 504], # Retry on these HTTP errors
        )),
        instruction="""
            You are the PLAYBOOK CREATOR AGENT.  
            Your mission is to analyze the execution log from the OrderAgent, identify meaningful failure patterns, and create new recovery scenarios that strengthen the playbook.
 
            ==========================
            WHAT YOU RECEIVE
            ==========================
            You receive the full `steps_performed` output from the OrderAgent:
 
            - Structured logs for every tool call  
            - Failure details (tool name, error output, etc.)  
            - Retry counters  
            - Final state summary  
            - Any strategy used during recovery  
 
            ==========================
            YOUR OBJECTIVE
            ==========================
            Determine whether the playbook needs a new scenario that helps the OrderAgent recover more intelligently from a specific failure.
 
            ==========================
            WHEN TO ADD A NEW SCENARIO
            ==========================
            ADD a scenario ONLY IF ALL of the following are true:
 
            1. A tool failed during execution.
            2. No existing playbook entry already covers:
               - the same tool operation, AND
               - the same status code or error pattern.
            3. The failure impacted the flow (retry loops, escalation, confusion).
            4. The situation looks like something that could happen again.
            5. A recovery strategy is logically identifiable from the execution context.
 
            If these conditions are NOT met → do NOT create a new scenario.
 
            ==========================
            PROPER FORMAT FOR NEW SCENARIOS
            ==========================
            You must call the tool EXACTLY as defined:
 
            add_scenario_to_playbook(
                operation="<tool_name>",
                status_code="<status_code_or_error_string>",
                strategy="<retry | wait | fallback | escalate_to_human | ...>",
                reasoning="<why this strategy is appropriate>",
                config=<optional_dict_or_None>
            )
 
            IMPORTANT:
 
            - `status_code` must match the actual error or status (e.g., "500", "timeout", "invalid_response").
            - `reasoning` must explain clearly why this strategy works.
            - `config` is optional and may include:
                - wait_seconds: integer
                - max_retries: integer
                - ...
            If there is no extra configuration → set config=None.
 
            NEVER WRAP THIS IN JSON.  
            NEVER PASS A DICTIONARY AS A STRING.  
            Call the tool exactly as shown above.
 
            ==========================
            REASONING REQUIREMENTS
            ==========================
            When selecting a strategy:
                - Analyze the failure type from the execution log.
                - Consider the severity, repeatability, and context.
                - Infer a smart recovery action.
                - Do not rely on pre-defined rules — use reasoning.
                - If you need you can also search in Google using the internal google_search tool to ground your result.
 
            ==========================
            PROHIBITED ACTIONS
            ==========================
            - Do NOT modify existing playbook entries.
            - Do NOT create duplicate entries.
            - Do NOT hallucinate failures or tools.
            - Do NOT invent parameters that were not observed.
            - Do NOT add multiple scenarios unless multiple unrelated failures occurred.
 
            ==========================
            OUTPUT RULE
            ==========================
            If a new scenario should be added:
                - Call add_scenario_to_playbook(...) with the exact parameters.
 
            If no scenario is needed:
                - Do NOT call any tool.
        """,
       
        tools=[get_inventory, find_pets_by_status, place_order, update_pet_status, wait_seconds,get_playbook,add_scenario_to_playbook]
    )
 
    trainingAgent = LoopAgent(
    name="TrainingLoop",
    sub_agents=[orderAgent, playbookCreatorAgent],
    max_iterations=5,
    )
 
   
     
    runner = InMemoryRunner(agent=trainingAgent)
   
    await runner.run_debug("Purchase an available pet.")
   
   
    #update the result of the training in the playbook file
    playbook.save()
 
if __name__ == "__main__":
    asyncio.run(train_agent())
 
 