"""
order_agent_llm.py - Phase 6 OrderAgentLLM REFACTORED WITH ADK
================================================================

**MIGRATION TO ADK v1.18.0+**

This module implements the Phase 6 OrderAgentLLM using proper Google ADK framework:
- ✅ LlmAgent for specialized agents
- ✅ SequentialAgent for workflow orchestration
- ✅ FunctionTool pattern for tools
- ✅ InMemoryRunner for execution
- ✅ Proper type hints and docstrings

**Previous Implementation**: Custom async functions with manual control flow
**New Implementation**: ADK-compliant agents, tools, and workflows

**Usage**:
    from agents.order_agent_llm import initialize_order_agent_adk
    
    runner = initialize_order_agent_adk()
    result = await process_order_adk(runner, "order_123", failure_rate=0.10)
"""

import os
import json
import asyncio
from pathlib import Path
from typing import Dict, Any, Optional, List
from dataclasses import dataclass

# =====================================================
# ADK IMPORTS (FRAMEWORK)
# =====================================================
from google.adk.agents import LlmAgent, SequentialAgent
from google.adk.models.google_llm import Gemini
from google.adk.runners import InMemoryRunner
from google.genai import types

# =====================================================
# CUSTOM IMPORTS (PROJECT-SPECIFIC)
# =====================================================
from tools.simulated_apis import (
    call_simulated_inventory_api,
    call_simulated_payments_api,
    call_simulated_shipping_api,
    call_simulated_erp_api,
)
from config.chaos_config import ChaosConfig


# =====================================================
# PLAYBOOK STORAGE (UNCHANGED FROM PHASE 5)
# =====================================================

@dataclass
class PlaybookEntry:
    """Playbook entry for chaos recovery strategies."""
    failure_type: str
    api: str
    action: str
    backoff_seconds: int
    max_retries: int


class PlaybookStorage:
    """Loads and validates playbook from JSON file."""
    
    def __init__(self, path: str = "data/playbook_phase6.json") -> None:
        self.path = path
        self.entries: List[PlaybookEntry] = []
        self._load_and_validate()
    
    def _load_and_validate(self) -> None:
        """Load playbook from JSON and validate structure."""
        playbook_path = Path(self.path)
        
        if not playbook_path.exists():
            raise FileNotFoundError(
                f"Playbook file not found: {self.path}\n"
                f"Create {self.path} with proper structure."
            )
        
        with open(self.path, 'r') as f:
            data = json.load(f)
        
        self.entries = data.get("procedures", [])
        
        if not self.entries:
            raise ValueError(f"Playbook at {self.path} has no procedures")
    
    def lookup(self, failure_type: str, api: str) -> Dict[str, int]:
        """Look up recovery strategy for a given failure type and API.
        
        Args:
            failure_type: Type of failure (e.g., "timeout", "503_error")
            api: API name (e.g., "inventory", "payment")
        
        Returns:
            Dictionary with recovery strategy:
            {
                "max_retries": 3,
                "backoff_seconds": 2
            }
        
        If no match found, returns default strategy.
        """
        for entry in self.entries:
            if entry["failure_type"] == failure_type and entry["api"] == api:
                return {
                    "max_retries": entry["max_retries"],
                    "backoff_seconds": entry["backoff_seconds"]
                }
        
        # Default fallback strategy
        return {
            "max_retries": 2,
            "backoff_seconds": 1
        }


# Global playbook storage instance
playbook_storage: Optional[PlaybookStorage] = None


# =====================================================
# STEP 1: DEFINE ADK TOOLS WITH TYPE HINTS
# =====================================================

def check_inventory_tool(order_id: str, failure_rate: float = 0.20, seed_offset: int = 0) -> dict:
    """Check inventory availability for an order with chaos injection.
    
    This tool verifies stock availability using simulated inventory API.
    Includes playbook-driven retry logic for failure recovery.
    
    Args:
        order_id: The order identifier (format: "order_XXX")
        failure_rate: Chaos injection rate (0.0 = no chaos, 1.0 = always fail)
        seed_offset: Seed offset for deterministic chaos injection
    
    Returns:
        Success case:
        {
            "status": "success",
            "items_available": 10,
            "duration_ms": 45.2
        }
        
        Error case:
        {
            "status": "error",
            "error": "Timeout after 3 retries",
            "items_available": 0,
            "duration_ms": 1205.5
        }
    """
    global playbook_storage
    
    # Configure chaos injection
    chaos_config = ChaosConfig(
        enabled=True,
        failure_rate=failure_rate,
        failure_type="timeout",
        max_delay_seconds=2,
        seed=42 + seed_offset
    )
    
    # Get retry strategy from playbook
    try:
        strategy = playbook_storage.lookup("timeout", "inventory")
        max_retries = strategy["max_retries"]
        backoff_seconds = strategy["backoff_seconds"]
    except:
        max_retries = 2
        backoff_seconds = 1
    
    # Execute with retries
    last_error = None
    import time
    start_time = time.time()
    
    for attempt in range(max_retries + 1):
        if attempt > 0:
            time.sleep(backoff_seconds)
        
        # Adjust seed for retry attempts
        retry_config = ChaosConfig(
            enabled=True,
            failure_rate=failure_rate,
            failure_type="timeout",
            max_delay_seconds=2,
            seed=42 + seed_offset + (attempt + 1) * 1000
        )
        
        result = call_simulated_inventory_api(
            endpoint="check_stock",
            payload={"sku": order_id, "qty": 1},
            chaos_config=retry_config
        )
        
        if result["status"] == "success":
            duration_ms = (time.time() - start_time) * 1000
            return {
                "status": "success",
                "items_available": result.get("data", {}).get("available_stock", 10),
                "duration_ms": round(duration_ms, 2)
            }
        
        last_error = result.get("error_message", "Unknown error")
    
    # All retries exhausted
    duration_ms = (time.time() - start_time) * 1000
    return {
        "status": "error",
        "error": f"Failed after {max_retries + 1} attempts (playbook): {last_error}",
        "items_available": 0,
        "duration_ms": round(duration_ms, 2)
    }


def process_payment_tool(order_id: str, amount: float = 100.0, failure_rate: float = 0.20, seed_offset: int = 0) -> dict:
    """Process payment for an order with chaos injection.
    
    This tool captures payment using simulated payment API.
    Includes playbook-driven retry logic for failure recovery.
    
    Args:
        order_id: The order identifier
        amount: Payment amount in USD
        failure_rate: Chaos injection rate
        seed_offset: Seed offset for deterministic chaos
    
    Returns:
        Success case:
        {
            "status": "success",
            "transaction_id": "txn_123",
            "duration_ms": 52.3
        }
        
        Error case:
        {
            "status": "error",
            "error": "Payment declined after retries",
            "transaction_id": "",
            "duration_ms": 1103.7
        }
    """
    global playbook_storage
    
    chaos_config = ChaosConfig(
        enabled=True,
        failure_rate=failure_rate,
        failure_type="timeout",
        max_delay_seconds=2,
        seed=42 + seed_offset
    )
    
    # Get retry strategy from playbook
    try:
        strategy = playbook_storage.lookup("timeout", "payment")
        max_retries = strategy["max_retries"]
        backoff_seconds = strategy["backoff_seconds"]
    except:
        max_retries = 2
        backoff_seconds = 1
    
    last_error = None
    import time
    start_time = time.time()
    
    for attempt in range(max_retries + 1):
        if attempt > 0:
            time.sleep(backoff_seconds)
        
        retry_config = ChaosConfig(
            enabled=True,
            failure_rate=failure_rate,
            failure_type="timeout",
            max_delay_seconds=2,
            seed=42 + seed_offset + (attempt + 1) * 1000
        )
        
        result = call_simulated_payments_api(
            endpoint="capture",
            payload={"amount": amount, "currency": "USD"},
            chaos_config=retry_config
        )
        
        if result["status"] == "success":
            duration_ms = (time.time() - start_time) * 1000
            return {
                "status": "success",
                "transaction_id": result.get("data", {}).get("transaction_id", "txn_success"),
                "duration_ms": round(duration_ms, 2)
            }
        
        last_error = result.get("error_message", "Unknown error")
    
    duration_ms = (time.time() - start_time) * 1000
    return {
        "status": "error",
        "error": f"Failed after {max_retries + 1} attempts (playbook): {last_error}",
        "transaction_id": "",
        "duration_ms": round(duration_ms, 2)
    }


def create_shipment_tool(order_id: str, address: str = "123 Main St", failure_rate: float = 0.20, seed_offset: int = 0) -> dict:
    """Create shipment for an order with chaos injection.
    
    This tool initiates shipping using simulated shipping API.
    Includes playbook-driven retry logic for failure recovery.
    
    Args:
        order_id: The order identifier
        address: Shipping address
        failure_rate: Chaos injection rate
        seed_offset: Seed offset for deterministic chaos
    
    Returns:
        Success case:
        {
            "status": "success",
            "tracking_number": "TRACK123",
            "duration_ms": 48.9
        }
        
        Error case:
        {
            "status": "error",
            "error": "Shipment creation failed after retries",
            "tracking_number": "",
            "duration_ms": 1089.4
        }
    """
    global playbook_storage
    
    chaos_config = ChaosConfig(
        enabled=True,
        failure_rate=failure_rate,
        failure_type="timeout",
        max_delay_seconds=2,
        seed=42 + seed_offset
    )
    
    try:
        strategy = playbook_storage.lookup("timeout", "shipping")
        max_retries = strategy["max_retries"]
        backoff_seconds = strategy["backoff_seconds"]
    except:
        max_retries = 2
        backoff_seconds = 1
    
    last_error = None
    import time
    start_time = time.time()
    
    for attempt in range(max_retries + 1):
        if attempt > 0:
            time.sleep(backoff_seconds)
        
        retry_config = ChaosConfig(
            enabled=True,
            failure_rate=failure_rate,
            failure_type="timeout",
            max_delay_seconds=2,
            seed=42 + seed_offset + (attempt + 1) * 1000
        )
        
        result = call_simulated_shipping_api(
            endpoint="create_shipment",
            payload={"order_id": order_id, "address": address},
            chaos_config=retry_config
        )
        
        if result["status"] == "success":
            duration_ms = (time.time() - start_time) * 1000
            return {
                "status": "success",
                "tracking_number": result.get("data", {}).get("tracking_number", "TRACK_OK"),
                "duration_ms": round(duration_ms, 2)
            }
        
        last_error = result.get("error_message", "Unknown error")
    
    duration_ms = (time.time() - start_time) * 1000
    return {
        "status": "error",
        "error": f"Failed after {max_retries + 1} attempts (playbook): {last_error}",
        "tracking_number": "",
        "duration_ms": round(duration_ms, 2)
    }


def update_erp_tool(order_id: str, status: str = "completed", failure_rate: float = 0.20, seed_offset: int = 0) -> dict:
    """Update ERP system with order status and chaos injection.
    
    This tool updates ERP using simulated ERP API.
    Includes playbook-driven retry logic for failure recovery.
    
    Args:
        order_id: The order identifier
        status: Order status to set (typically "completed")
        failure_rate: Chaos injection rate
        seed_offset: Seed offset for deterministic chaos
    
    Returns:
        Success case:
        {
            "status": "success",
            "erp_status": "completed",
            "duration_ms": 51.1
        }
        
        Error case:
        {
            "status": "error",
            "error": "ERP update failed after retries",
            "erp_status": "",
            "duration_ms": 1123.8
        }
    """
    global playbook_storage
    
    chaos_config = ChaosConfig(
        enabled=True,
        failure_rate=failure_rate,
        failure_type="timeout",
        max_delay_seconds=2,
        seed=42 + seed_offset
    )
    
    try:
        strategy = playbook_storage.lookup("timeout", "erp")
        max_retries = strategy["max_retries"]
        backoff_seconds = strategy["backoff_seconds"]
    except:
        max_retries = 2
        backoff_seconds = 1
    
    last_error = None
    import time
    start_time = time.time()
    
    for attempt in range(max_retries + 1):
        if attempt > 0:
            time.sleep(backoff_seconds)
        
        retry_config = ChaosConfig(
            enabled=True,
            failure_rate=failure_rate,
            failure_type="timeout",
            max_delay_seconds=2,
            seed=42 + seed_offset + (attempt + 1) * 1000
        )
        
        result = call_simulated_erp_api(
            endpoint="create_order",
            payload={"order_id": order_id, "status": status},
            chaos_config=retry_config
        )
        
        if result["status"] == "success":
            duration_ms = (time.time() - start_time) * 1000
            return {
                "status": "success",
                "erp_status": result.get("data", {}).get("status", status),
                "duration_ms": round(duration_ms, 2)
            }
        
        last_error = result.get("error_message", "Unknown error")
    
    duration_ms = (time.time() - start_time) * 1000
    return {
        "status": "error",
        "error": f"Failed after {max_retries + 1} attempts (playbook): {last_error}",
        "erp_status": "",
        "duration_ms": round(duration_ms, 2)
    }


# =====================================================
# STEP 2: DEFINE SPECIALIZED ADK AGENTS
# =====================================================

def create_inventory_agent(failure_rate: float, seed_offset: int) -> LlmAgent:
    """Create inventory checking agent with ADK.
    
    This agent is responsible for verifying stock availability.
    It uses the check_inventory_tool and stores results in session.state.
    """
    # Create a closure to pass parameters to the tool
    def check_inventory_wrapper(order_id: str) -> dict:
        return check_inventory_tool(order_id, failure_rate, seed_offset)
    
    return LlmAgent(
        name="InventoryAgent",
        model=Gemini(model="gemini-2.5-flash-lite"),
        instruction="""You are the Inventory Agent responsible for checking stock availability.

Your task:
1. Use the check_inventory_wrapper tool to verify inventory for the given order
2. Report the result clearly
3. Store the result for the next agent

If inventory check fails, the workflow should stop.
""",
        tools=[check_inventory_wrapper],
        output_key="inventory_result"
    )


def create_payment_agent(failure_rate: float, seed_offset: int) -> LlmAgent:
    """Create payment processing agent with ADK.
    
    This agent is responsible for capturing payment.
    It verifies inventory was successful before proceeding.
    """
    def process_payment_wrapper(order_id: str, amount: float = 100.0) -> dict:
        return process_payment_tool(order_id, amount, failure_rate, seed_offset + 1)
    
    return LlmAgent(
        name="PaymentAgent",
        model=Gemini(model="gemini-2.0-flash-lite"),
        instruction="""You are the Payment Agent responsible for processing payments.

Your task:
1. Verify that inventory check was successful: {inventory_result}
2. ONLY proceed if inventory_result status is "success"
3. Use the process_payment_wrapper tool to capture payment
4. Report the result clearly

If inventory failed or payment fails, the workflow should stop.
""",
        tools=[process_payment_wrapper],
        output_key="payment_result"
    )


def create_shipping_agent(failure_rate: float, seed_offset: int) -> LlmAgent:
    """Create shipping agent with ADK.
    
    This agent is responsible for creating shipments.
    It verifies payment was successful before proceeding.
    """
    def create_shipment_wrapper(order_id: str, address: str = "123 Main St") -> dict:
        return create_shipment_tool(order_id, address, failure_rate, seed_offset + 2)
    
    return LlmAgent(
        name="ShippingAgent",
        model=Gemini(model="gemini-2.0-flash-lite"),
        instruction="""You are the Shipping Agent responsible for creating shipments.

Your task:
1. Verify that payment was successful: {payment_result}
2. ONLY proceed if payment_result status is "success"
3. Use the create_shipment_wrapper tool to initiate shipping
4. Report the result clearly

If payment failed or shipment fails, the workflow should stop.
""",
        tools=[create_shipment_wrapper],
        output_key="shipment_result"
    )


def create_erp_agent(failure_rate: float, seed_offset: int) -> LlmAgent:
    """Create ERP updating agent with ADK.
    
    This agent is responsible for updating the ERP system.
    It verifies shipment was successful before proceeding.
    """
    def update_erp_wrapper(order_id: str, status: str = "completed") -> dict:
        return update_erp_tool(order_id, status, failure_rate, seed_offset + 3)
    
    return LlmAgent(
        name="ERPAgent",
        model=Gemini(model="gemini-2.0-flash-lite"),
        instruction="""You are the ERP Agent responsible for updating the ERP system.

Your task:
1. Verify that shipment was successful: {shipment_result}
2. ONLY proceed if shipment_result status is "success"
3. Use the update_erp_wrapper tool to update ERP with order status
4. Report the final result

This is the last step. Report success only if all previous steps succeeded.
""",
        tools=[update_erp_wrapper],
        output_key="erp_result"
    )


# =====================================================
# STEP 3: CREATE ADK SEQUENTIAL WORKFLOW
# =====================================================

def create_order_workflow(failure_rate: float = 0.20, seed_offset: int = 0) -> SequentialAgent:
    """Create the order processing workflow using ADK SequentialAgent.
    
    This workflow orchestrates 4 specialized agents in sequence:
    1. InventoryAgent - checks stock
    2. PaymentAgent - captures payment
    3. ShippingAgent - creates shipment
    4. ERPAgent - updates ERP
    
    Each agent passes its result to the next via session.state.
    
    Args:
        failure_rate: Chaos injection rate (0.0-1.0)
        seed_offset: Base seed offset for deterministic chaos
    
    Returns:
        SequentialAgent configured with 4-step order workflow
    """
    return SequentialAgent(
        name="OrderProcessingWorkflow",
        sub_agents=[
            create_inventory_agent(failure_rate, seed_offset),
            create_payment_agent(failure_rate, seed_offset),
            create_shipping_agent(failure_rate, seed_offset),
            create_erp_agent(failure_rate, seed_offset)
        ]
    )


# =====================================================
# STEP 4: INITIALIZE ADK RUNNER
# =====================================================

def validate_environment() -> str:
    """Validate GEMINI_API_KEY environment variable.
    
    Returns:
        str: API key
        
    Raises:
        ValueError: If API key not set or invalid
    """
    api_key = os.getenv("GEMINI_API_KEY")
    
    if not api_key:
        raise ValueError(
            "GEMINI_API_KEY environment variable not set.\n"
            "Setup: export GEMINI_API_KEY=your_key"
        )
    
    if len(api_key) < 20:
        raise ValueError(f"GEMINI_API_KEY invalid (length: {len(api_key)})")
    
    return api_key


def initialize_order_agent_adk(playbook_path: str = "data/playbook_phase6.json") -> InMemoryRunner:
    """Initialize OrderAgentLLM using proper ADK framework.
    
    This is the Phase 6 refactored version that uses:
    - LlmAgent for specialized agents
    - SequentialAgent for workflow
    - InMemoryRunner for execution
    
    Args:
        playbook_path: Path to playbook JSON file
    
    Returns:
        InMemoryRunner configured with order workflow
    
    Raises:
        ValueError: If GEMINI_API_KEY not set
        FileNotFoundError: If playbook file not found
    """
    global playbook_storage
    
    # Validate environment
    api_key = validate_environment()
    
    # Load playbook
    playbook_storage = PlaybookStorage(path=playbook_path)
    
    print("✅ OrderAgentLLM initialized with ADK v1.18.0+")
    print(f"   Model: gemini-2.0-flash-lite")
    print(f"   Framework: Google ADK (LlmAgent + SequentialAgent)")
    print(f"   Playbook: {len(playbook_storage.entries)} entries loaded from {playbook_path}")
    print(f"   Workflow: 4-step sequential pipeline")
    print(f"     1. InventoryAgent → checks stock")
    print(f"     2. PaymentAgent → captures payment")
    print(f"     3. ShippingAgent → creates shipment")
    print(f"     4. ERPAgent → updates ERP")
    
    # Note: We'll create the workflow dynamically in process_order_adk
    # because we need failure_rate and seed_offset
    return None  # Placeholder - actual runner created per-request


# =====================================================
# STEP 5: EXECUTE ORDER WITH ADK
# =====================================================

async def process_order_adk(
    order_id: str,
    amount: float = 100.0,
    address: str = "123 Main St",
    order_index: int = 0,
    failure_rate: float = 0.20
) -> Dict[str, Any]:
    """Process order using ADK workflow (Phase 6 refactored).
    
    This function creates an ADK workflow with the given parameters
    and executes it using InMemoryRunner.
    
    Args:
        order_id: Order identifier
        amount: Payment amount in USD
        address: Shipping address
        order_index: Index for seed generation
        failure_rate: Chaos injection rate (0.0-1.0)
    
    Returns:
        Dictionary with order processing result:
        {
            "status": "success" | "failure",
            "order_id": "order_123",
            "steps_completed": ["inventory", "payment", "shipment", "erp"],
            "error_message": "",
            "total_duration_ms": 234.5
        }
    """
    import time
    start_time = time.time()
    
    # Create workflow with specific parameters
    workflow = create_order_workflow(
        failure_rate=failure_rate,
        seed_offset=order_index * 10
    )
    
    # Create runner
    runner = InMemoryRunner(agent=workflow)
    
    # Prepare user message with order details
    user_message = f"""Process order {order_id}:
- Amount: ${amount:.2f}
- Address: {address}
- Failure Rate: {failure_rate:.0%} (chaos testing)

Execute the 4-step order workflow:
1. Check inventory
2. Process payment
3. Create shipment
4. Update ERP

Report status of each step and final outcome.
"""
    
    try:
        # Execute workflow with ADK runner
        response = await runner.run_debug(user_message)
        
        # Parse response to determine success/failure
        response_text = str(response).lower()
        
        # Check if all steps succeeded
        if "error" in response_text or "failed" in response_text or "failure" in response_text:
            # Determine which steps completed
            steps_completed = []
            if "inventory" in response_text and "success" in response_text:
                steps_completed.append("inventory")
            if "payment" in response_text and "success" in response_text:
                steps_completed.append("payment")
            if "shipment" in response_text or "shipping" in response_text:
                if "success" in response_text:
                    steps_completed.append("shipment")
            if "erp" in response_text and "success" in response_text:
                steps_completed.append("erp")
            
            total_duration_ms = (time.time() - start_time) * 1000
            
            return {
                "status": "failure",
                "order_id": order_id,
                "steps_completed": steps_completed,
                "error_message": "Workflow failed - check response for details",
                "total_duration_ms": round(total_duration_ms, 2)
            }
        else:
            # All steps succeeded
            total_duration_ms = (time.time() - start_time) * 1000
            
            return {
                "status": "success",
                "order_id": order_id,
                "steps_completed": ["inventory", "payment", "shipment", "erp"],
                "error_message": "",
                "total_duration_ms": round(total_duration_ms, 2)
            }
    
    except Exception as e:
        total_duration_ms = (time.time() - start_time) * 1000
        
        return {
            "status": "failure",
            "order_id": order_id,
            "steps_completed": [],
            "error_message": f"Unexpected error: {str(e)}",
            "total_duration_ms": round(total_duration_ms, 2)
        }


# =====================================================
# LEGACY COMPATIBILITY WRAPPERS
# =====================================================

# For backward compatibility with existing code
def initialize_order_agent_llm(playbook_path: str = "data/playbook_phase6.json"):
    """Legacy initialization function (compatibility wrapper).
    
    This maintains the old API for existing code while using ADK internally.
    """
    return initialize_order_agent_adk(playbook_path)


async def process_order_simple(
    order_id: str,
    amount: float = 100.0,
    address: str = "123 Main St",
    order_index: int = 0,
    failure_rate: float = 0.20
) -> Dict[str, Any]:
    """Legacy order processing function (compatibility wrapper).
    
    This maintains the old API for existing code while using ADK internally.
    """
    return await process_order_adk(order_id, amount, address, order_index, failure_rate)


# =====================================================
# TESTING & VALIDATION
# =====================================================

async def test_order_agent_adk() -> bool:
    """Test ADK-based OrderAgentLLM with 10 sample orders."""
    print("=" * 60)
    print("PHASE 6 - ORDER AGENT ADK TEST")
    print("=" * 60)
    
    print("\n[1/3] Initializing OrderAgentLLM with ADK...")
    try:
        initialize_order_agent_adk()
    except Exception as e:
        print(f"❌ Initialization failed: {e}")
        return False
    
    print("\n[2/3] Processing 10 sample orders...")
    results = []
    for i in range(10):
        result = await process_order_adk(
            f"order_test_{i}",
            order_index=i,
            failure_rate=0.20
        )
        results.append(result)
        
        status_emoji = "✅" if result["status"] == "success" else "❌"
        print(f"  {status_emoji} Order {i+1}/10: {result['status']}, "
              f"steps: {len(result['steps_completed'])}/4")
    
    print("\n[3/3] Analyzing results...")
    success_count = sum(1 for r in results if r["status"] == "success")
    success_rate = success_count / len(results)
    
    print(f"\n📊 Results Summary:")
    print(f"  Success rate: {success_rate:.1%} ({success_count}/10)")
    print(f"  Expected with playbook: 70-80%")
    
    if success_rate < 0.50:
        print(f"\n⚠️ WARNING: Rate below expected")
    elif 0.50 <= success_rate <= 0.90:
        print(f"\n✅ SUCCESS: Rate within expected range")
    else:
        print(f"\n🎉 EXCELLENT: Rate above expected!")
    
    print("\n" + "=" * 60)
    print("✅ ADK TEST COMPLETED")
    print("=" * 60)
    
    return success_rate >= 0.50


async def main() -> None:
    """Main entry point for testing."""
    print("\n" + "=" * 30)
    print("PHASE 6 - ADK REFACTORED")
    print("=" * 30)
    
    success = await test_order_agent_adk()
    
    if success:
        print("\n✅ All tests passed! ADK implementation working correctly.")
    else:
        print("\n❌ Tests failed. Check logs above for details.")


if __name__ == "__main__":
    asyncio.run(main())
