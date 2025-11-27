"""OrderOrchestratorAgent - Phase 1+3 Implementation with Chaos Playbook.

This agent orchestrates e-commerce order processing through a 4-step workflow:

1. Check inventory availability
2. Capture payment
3. Create order in ERP system
4. Initiate shipping

Phase 3 Addition: Chaos Playbook integration with saveprocedure and loadprocedure tools.

Implementation uses InMemoryRunner pattern from ADK labs for reliable tool execution.

Key learnings from Phase 1:
- InMemoryRunner provides reliable tool execution vs. Runner + App pattern
- Tools must be defined in same scope as agent for proper ADK registration
- run_debug() simplifies testing with automatic session management

Phase 3 Enhancement:
- saveprocedure tool enables agent to record successful recovery strategies
- loadprocedure tool enables agent to query Chaos Playbook for known solutions
- PlaybookStorage provides JSON-based persistence for chaos procedures
"""

import asyncio
from datetime import datetime
from typing import Any, Dict

from google.adk.agents import LlmAgent
from google.adk.models.google_llm import Gemini

# Import simulated APIs from project tools
from tools.simulated_apis import (
    call_simulated_erp_api,
    call_simulated_inventory_api,
    call_simulated_payments_api,
    call_simulated_shipping_api,
)

# Phase 3: Import PlaybookStorage for Chaos Playbook tools
from storage.playbook_storage import PlaybookStorage


MODEL_NAME = "gemini-2.5-flash-lite"

# ============================================================================
# TOOL WRAPPERS - Adapt simulated APIs to match ADK tool signatures
# ============================================================================

# NOTE: Tools must be defined inline with agent for proper ADK registration.
# These wrappers adapt the generic simulated_apis to specific tool signatures
# that the LLM can call directly.

async def call_inventory_api(sku: str, qty: int) -> Dict[str, Any]:
    """
    Check inventory stock availability.
    
    Args:
        sku: Product SKU to check
        qty: Quantity needed
    
    Returns:
        Dict with status, sku, available quantity, and reserved amount
    """
    return await call_simulated_inventory_api("check_stock", {"sku": sku, "qty": qty})


async def call_payments_api(amount: float, currency: str) -> Dict[str, Any]:
    """
    Capture payment for order.
    
    Args:
        amount: Payment amount
        currency: Currency code (e.g., 'USD')
    
    Returns:
        Dict with status, transaction_id, amount, and currency
    """
    return await call_simulated_payments_api("capture", {"amount": amount, "currency": currency})


async def call_erp_api(user_id: str, items: str) -> Dict[str, Any]:
    """
    Create order record in ERP system.
    
    The LLM provides items as a string, but simulated_erp_api expects a list.
    This wrapper adapts the format.
    """
    # Adapt string items to expected list format
    items_list = [
        {
            "sku": items,  # LLM provides SKU string
            "qty": 1,      # Default qty (already validated in inventory step)
            "price": 0.0   # Price not critical for Phase 1 happy-path
        }
    ]
    return await call_simulated_erp_api("create_order", {"user_id": user_id, "items": items_list})


async def call_shipping_api(order_id: str, address: str) -> Dict[str, Any]:
    """
    Create shipment for order.
    
    Args:
        order_id: ERP order ID to ship
        address: Shipping address (can be string or structured)
    
    Returns:
        Dict with status, shipment_id, and tracking number
    """
    return await call_simulated_shipping_api(
        "create_shipment",
        {"order_id": order_id, "address": address}
    )


# ============================================================================
# PHASE 3: CHAOS PLAYBOOK TOOLS
# ============================================================================

async def saveprocedure(
    failure_type: str,
    api: str,
    recovery_strategy: str,
    success_rate: float = 1.0
) -> Dict[str, Any]:
    """
    Save successful recovery procedure to Chaos Playbook.
    
    Use this tool when you successfully recover from a failure
    and want to record the strategy for future reference.
    
    Args:
        failure_type: Type of failure (timeout, service_unavailable, 
                     rate_limit_exceeded, invalid_request, network_error)
        api: API that failed (inventory, payments, erp, shipping)
        recovery_strategy: Description of recovery strategy used
        success_rate: Success rate of strategy (0.0-1.0, default 1.0)
    
    Returns:
        {
            "status": "success",
            "procedure_id": "PROC-001",
            "message": "Procedure saved to Chaos Playbook"
        }
        
        Or on error:
        {
            "status": "error",
            "message": "Error description"
        }
    
    Example:
        saveprocedure(
            failure_type="timeout",
            api="inventory",
            recovery_strategy="Retried 3 times with exponential backoff (2s, 4s, 8s)",
            success_rate=1.0
        )
    """
    try:
        storage = PlaybookStorage()
        
        procedure_id = await storage.save_procedure(
            failure_type=failure_type,
            api=api,
            recovery_strategy=recovery_strategy,
            success_rate=success_rate,
            metadata={
                "agent": "OrderOrchestratorAgent",
                "saved_at": datetime.utcnow().isoformat() + "Z"
            }
        )
        
        return {
            "status": "success",
            "procedure_id": procedure_id,
            "message": f"Procedure {procedure_id} saved to Chaos Playbook"
        }
    
    except ValueError as e:
        return {
            "status": "error",
            "message": f"Validation error: {str(e)}"
        }
    
    except Exception as e:
        return {
            "status": "error",
            "message": f"Failed to save procedure: {str(e)}"
        }


async def loadprocedure(
    failure_type: str,
    api: str
) -> Dict[str, Any]:
    """
    Load best recovery procedure from Chaos Playbook.
    
    Use this tool when you encounter a failure and want to check
    if there's a known successful recovery strategy.
    
    Args:
        failure_type: Type of failure (timeout, service_unavailable, 
                     rate_limit_exceeded, invalid_request, network_error)
        api: API that failed (inventory, payments, erp, shipping)
    
    Returns:
        If procedure found:
        {
            "status": "success",
            "procedure_id": "PROC-001",
            "recovery_strategy": "Retry 3x with exponential backoff (2s, 4s, 8s)",
            "success_rate": 0.9,
            "recommendation": "This strategy has 90% success rate"
        }
        
        If not found:
        {
            "status": "not_found",
            "message": "No recovery procedure found for timeout in inventory API",
            "recommendation": "Try standard retry or escalate"
        }
    
    Example:
        result = loadprocedure(
            failure_type="timeout",
            api="inventory"
        )
        # Use result["recovery_strategy"] to guide retry logic
    """
    try:
        storage = PlaybookStorage()
        
        procedure = await storage.get_best_procedure(
            failure_type=failure_type,
            api=api
        )
        
        if procedure:
            return {
                "status": "success",
                "procedure_id": procedure["id"],
                "recovery_strategy": procedure["recovery_strategy"],
                "success_rate": procedure["success_rate"],
                "recommendation": f"This strategy has {procedure['success_rate']*100:.0f}% success rate"
            }
        else:
            return {
                "status": "not_found",
                "message": f"No recovery procedure found for {failure_type} in {api} API",
                "recommendation": "Try standard retry or escalate"
            }
    
    except Exception as e:
        return {
            "status": "error",
            "message": f"Failed to load procedure: {str(e)}"
        }


# ============================================================================
# AGENT FACTORY
# ============================================================================

def create_order_orchestrator_agent(mode: str = "basic") -> LlmAgent:
    """
    Create OrderOrchestratorAgent for e-commerce order processing.
    
    The agent uses tools to orchestrate the complete order workflow.
    In Phase 1, operates in 'basic' mode (happy-path, no chaos injection).
    In Phase 3, adds Chaos Playbook tools (saveprocedure, loadprocedure).
    
    Args:
        mode: Agent mode ('basic' for Phase 1 happy-path)
    
    Returns:
        Configured LlmAgent with tools registered
    
    Example:
        >>> agent = create_order_orchestrator_agent(mode="basic")
        >>> runner = InMemoryRunner(agent=agent)
        >>> await runner.run_debug("Process order: sku=WIDGET-A, qty=5...")
    """
    instruction = """You are an Order Orchestrator Agent for e-commerce order processing.

Your task: Execute a complete order workflow by calling these tools in sequence:

1. **Check Inventory**: Call call_inventory_api with the product sku and quantity
2. **Capture Payment**: Call call_payments_api with the order amount and currency
3. **Create ERP Order**: Call call_erp_api with the user_id and items information
4. **Create Shipment**: Call call_shipping_api with the order_id and shipping address

After completing all 4 steps successfully, provide a summary of the order processing results including key IDs and status from each step.

**Chaos Recovery Pattern (Phase 3):**

When a tool call fails:
1. Check error response for 'retryable' flag
2. If retryable=True:
   a. Call loadprocedure(failure_type, api) to check Chaos Playbook
   b. If procedure found: Follow recommended recovery_strategy
   c. If not found: Use standard retry (3 attempts, exponential backoff)
3. If retry succeeds: Call saveprocedure to record strategy
4. If retryable=False: Report error immediately, don't retry

**Tools Available:**
- call_inventory_api (check stock)
- call_payments_api (capture payment)
- call_erp_api (create order)
- call_shipping_api (create shipment)
- saveprocedure (record successful recovery - Phase 3)
- loadprocedure (query Chaos Playbook - Phase 3)

Important: Execute ALL 4 steps in order before responding with the summary."""

    # CRITICAL: Tools defined inline in same scope as agent
    # This ensures proper ADK registration and tool execution
    return LlmAgent(
        name="OrderOrchestratorAgent",
        model=Gemini(model=MODEL_NAME),
        instruction=instruction,
        tools=[
            call_inventory_api,
            call_payments_api,
            call_erp_api,
            call_shipping_api,
            saveprocedure,   # Phase 3: Save recovery procedures
            loadprocedure    # Phase 3: Load recovery procedures
        ]
    )
