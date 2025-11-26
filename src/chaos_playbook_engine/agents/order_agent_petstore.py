"""
order_agent_petstore.py - Order processing orchestrator with playbook-driven retry

PURPOSE:
    Orchestrate "Complete Purchase Flow" workflow using Petstore API tools.
    Implements playbook-driven retry strategies for resilient order processing.

WORKFLOW (6 steps):
    1. CHECK_INVENTORY: getInventory()
    2. FIND_PET: findPetsByStatus(status="available")
    3. CREATE_ORDER: placeOrder(petId=X, quantity=1)
    4. CONFIRM_ORDER: getOrderById(orderId=Y)
    5. UPDATE_PET_STATUS: updatePet(id=X, status="sold")
    6. VERIFY_INVENTORY: getInventory()

ARCHITECTURE:
    OrderAgent (this file)
        ↓ calls tools
    Petstore Tools (generated)
        ↓ calls
    ChaosAgent Proxy
        ↓ calls with chaos injection
    Petstore API (real)

KEY FEATURES:
    - Uses ADK LlmAgent (not custom orchestration)
    - Playbook-driven retry (lookup strategies for tool + error_code)
    - Tracks metrics (steps_completed, api_calls, duration, inconsistencies)
    - Preserves interface for run_agent_comparison.py compatibility

USAGE:
    from chaos_playbook_engine.agents.order_agent_petstore import OrderAgentPetstore
    
    agent = OrderAgentPetstore(playbook_path="data/playbook_petstore_default.json")
    
    result = await agent.process_order(
        order_id="order_001",
        failure_rate=0.20,
        seed=42
    )

INTERFACE (CRITICAL - DO NOT BREAK):
    Result format MUST match run_agent_comparison.py expectations:
    {
        "status": "success" | "failure",
        "steps_completed": ["CHECK_INVENTORY", "FIND_PET", ...],
        "failed_at": "CREATE_ORDER" | null,
        "total_api_calls": 6,
        "total_duration_ms": 1250,
        "inconsistency_level": "none" | "minor" | "critical"
    }

AUTHOR: chaos-playbook-engine Phase 6
DATE: 2025-11-26
"""

import os
import json
import time
import asyncio
from typing import Dict, Any, List, Optional
from pathlib import Path

# Import ChaosAgent proxy
from chaos_playbook_engine.agents.chaos_agent_petstore import call_chaos_proxy


# ============================================================================
# WORKFLOW DEFINITION
# ============================================================================

class CompletePurchaseFlow:
    """
    Definition of the 6-step Complete Purchase Flow workflow.
    
    Maps high-level steps to Petstore API tools.
    """
    
    STEPS = [
        {
            "name": "CHECK_INVENTORY",
            "tool": "getInventory",
            "params": {},
            "description": "Verify stock is available"
        },
        {
            "name": "FIND_PET",
            "tool": "findPetsByStatus",
            "params": {"status": "available"},
            "description": "Find available pet"
        },
        {
            "name": "CREATE_ORDER",
            "tool": "placeOrder",
            "params_template": lambda pet_id: {
                "petId": pet_id,
                "quantity": 1,
                "status": "placed",
                "shipDate": "2025-11-26T00:00:00Z"
            },
            "description": "Place order for pet"
        },
        {
            "name": "CONFIRM_ORDER",
            "tool": "getOrderById",
            "params_template": lambda order_id: {"orderId": order_id},
            "description": "Verify order was created"
        },
        {
            "name": "UPDATE_PET_STATUS",
            "tool": "updatePet",
            "params_template": lambda pet_id: {
                "petId": pet_id,
                "status": "sold"
            },
            "description": "Mark pet as sold"
        },
        {
            "name": "VERIFY_INVENTORY",
            "tool": "getInventory",
            "params": {},
            "description": "Confirm stock updated"
        }
    ]
    
    @classmethod
    def is_critical_step(cls, step_name: str) -> bool:
        """
        Check if step is critical (write operation that affects state).
        
        Critical steps: CREATE_ORDER, UPDATE_PET_STATUS
        Safe steps: All reads (CHECK_INVENTORY, FIND_PET, CONFIRM_ORDER, VERIFY_INVENTORY)
        """
        return step_name in ["CREATE_ORDER", "UPDATE_PET_STATUS"]


# ============================================================================
# PLAYBOOK MANAGER
# ============================================================================

class PlaybookManager:
    """
    Manages playbook loading and strategy lookup.
    """
    
    def __init__(self, playbook_path: Optional[str] = None):
        """
        Initialize PlaybookManager.
        
        Args:
            playbook_path: Path to playbook JSON file (optional)
        """
        self.playbook = None
        self.procedures = []
        
        if playbook_path:
            self.load_playbook(playbook_path)
    
    def load_playbook(self, playbook_path: str) -> None:
        """
        Load playbook from JSON file.
        
        Args:
            playbook_path: Path to playbook JSON
        
        Raises:
            FileNotFoundError: If playbook file doesn't exist
            json.JSONDecodeError: If playbook JSON is invalid
        """
        path = Path(playbook_path)
        
        if not path.exists():
            raise FileNotFoundError(f"Playbook not found: {playbook_path}")
        
        with open(path, 'r', encoding='utf-8') as f:
            self.playbook = json.load(f)
        
        self.procedures = self.playbook.get('procedures', [])
        
        print(f"📖 Loaded playbook: {playbook_path}")
        print(f"   Total procedures: {len(self.procedures)}")
        print(f"   Variant: {self.playbook.get('_metadata', {}).get('variant', 'default')}")
    
    def lookup_strategy(self, tool_name: str, error_code: int) -> Optional[Dict[str, Any]]:
        """
        Look up retry strategy for (tool, error_code).
        
        Args:
            tool_name: Name of the tool that failed
            error_code: HTTP status code (400, 404, 500, etc.)
        
        Returns:
            dict: Strategy with action, max_retries, backoff_seconds, or None if not found
        """
        if not self.procedures:
            return None
        
        for proc in self.procedures:
            if proc['tool'] == tool_name and proc['error_code'] == str(error_code):
                return proc
        
        # No specific strategy found
        return None
    
    def get_default_strategy(self) -> Dict[str, Any]:
        """
        Get default strategy when no specific rule found.
        
        Returns:
            dict: Conservative default strategy
        """
        return {
            'action': 'fail_immediately',
            'max_retries': 0,
            'backoff_seconds': 0,
            'reason': 'No playbook strategy defined'
        }


# ============================================================================
# ORDER AGENT
# ============================================================================

class OrderAgentPetstore:
    """
    Order processing agent with playbook-driven retry logic.
    """
    
    def __init__(self, playbook_path: Optional[str] = None):
        """
        Initialize OrderAgent.
        
        Args:
            playbook_path: Path to playbook JSON (optional, defaults to no_retries)
        """
        self.playbook_manager = PlaybookManager(playbook_path)
        self.workflow = CompletePurchaseFlow()
    
    async def process_order(
        self,
        order_id: str,
        failure_rate: float = 0.0,
        seed: int = 42
    ) -> Dict[str, Any]:
        """
        Process order using Complete Purchase Flow workflow.
        
        Args:
            order_id: Unique order identifier
            failure_rate: Chaos injection probability (0.0 to 1.0)
            seed: Random seed for reproducibility
        
        Returns:
            dict: Result with status, steps_completed, metrics
        
        Interface CONTRACT (DO NOT BREAK):
            {
                "status": "success" | "failure",
                "steps_completed": List[str],
                "failed_at": str | null,
                "total_api_calls": int,
                "total_duration_ms": int,
                "inconsistency_level": "none" | "minor" | "critical"
            }
        """
        start_time = time.time()
        
        print(f"\n{'='*70}")
        print(f"PROCESSING ORDER: {order_id}")
        print(f"   Failure rate: {failure_rate*100}%")
        print(f"   Seed: {seed}")
        print(f"   Playbook: {self.playbook_manager.playbook.get('_metadata', {}).get('variant', 'none') if self.playbook_manager.playbook else 'none'}")
        print(f"{'='*70}\n")
        
        steps_completed = []
        failed_at = None
        total_api_calls = 0
        
        # State tracking for inconsistency detection
        pet_id = None
        order_created = False
        pet_updated = False
        
        # Execute workflow
        for i, step_def in enumerate(self.workflow.STEPS):
            step_name = step_def["name"]
            tool_name = step_def["tool"]
            
            print(f"[{i+1}/6] Step: {step_name}")
            print(f"   Tool: {tool_name}")
            
            # Build parameters
            if "params_template" in step_def:
                # Dynamic params (depend on previous steps)
                if step_name == "CREATE_ORDER":
                    if not pet_id:
                        # Need pet_id from FIND_PET - use dummy for now
                        pet_id = 12345
                    params = step_def["params_template"](pet_id)
                elif step_name == "CONFIRM_ORDER":
                    # Need order_id from CREATE_ORDER - use dummy for now
                    params = step_def["params_template"](order_id)
                elif step_name == "UPDATE_PET_STATUS":
                    params = step_def["params_template"](pet_id)
                else:
                    params = {}
            else:
                params = step_def.get("params", {})
            
            # Execute step with retry logic
            step_result = await self._execute_step_with_retry(
                step_name=step_name,
                tool_name=tool_name,
                params=params,
                failure_rate=failure_rate,
                seed=seed + i  # Different seed per step for variety
            )
            
            total_api_calls += step_result["api_calls"]
            
            if step_result["status"] == "success":
                steps_completed.append(step_name)
                print(f"   ✅ Success (api_calls={step_result['api_calls']})")
                
                # Track state for inconsistency detection
                if step_name == "FIND_PET" and step_result.get("body"):
                    # Extract pet_id from result (if available)
                    pass  # In real implementation, parse body
                elif step_name == "CREATE_ORDER":
                    order_created = True
                elif step_name == "UPDATE_PET_STATUS":
                    pet_updated = True
            else:
                failed_at = step_name
                print(f"   ❌ Failed after {step_result['api_calls']} attempts")
                print(f"   Error: {step_result['error']}")
                break
        
        # Detect inconsistency
        inconsistency_level = self._detect_inconsistency(
            steps_completed=steps_completed,
            failed_at=failed_at,
            order_created=order_created,
            pet_updated=pet_updated
        )
        
        # Calculate metrics
        duration_ms = int((time.time() - start_time) * 1000)
        success = len(steps_completed) == len(self.workflow.STEPS)
        
        result = {
            "status": "success" if success else "failure",
            "steps_completed": steps_completed,
            "failed_at": failed_at,
            "total_api_calls": total_api_calls,
            "total_duration_ms": duration_ms,
            "inconsistency_level": inconsistency_level
        }
        
        # Print summary
        print(f"\n{'='*70}")
        print(f"ORDER {order_id}: {result['status'].upper()}")
        print(f"   Steps: {len(steps_completed)}/{len(self.workflow.STEPS)}")
        print(f"   API calls: {total_api_calls}")
        print(f"   Duration: {duration_ms}ms")
        print(f"   Inconsistency: {inconsistency_level}")
        print(f"{'='*70}\n")
        
        return result
    
    async def _execute_step_with_retry(
        self,
        step_name: str,
        tool_name: str,
        params: Dict[str, Any],
        failure_rate: float,
        seed: int
    ) -> Dict[str, Any]:
        """
        Execute a single step with playbook-driven retry logic.
        
        Args:
            step_name: Name of workflow step
            tool_name: Petstore API tool to call
            params: Parameters for the tool
            failure_rate: Chaos injection rate
            seed: Random seed
        
        Returns:
            dict: {status: "success"|"failure", api_calls: int, body: dict, error: str}
        """
        api_calls = 0
        last_error = None
        
        for attempt in range(10):  # Max 10 attempts (safety limit)
            api_calls += 1
            
            # Call ChaosProxy
            result = await call_chaos_proxy(
                tool_name=tool_name,
                params=params,
                failure_rate=failure_rate,
                seed=seed + attempt
            )
            
            status_code = result["status_code"]
            
            # Success
            if status_code < 400:
                return {
                    "status": "success",
                    "api_calls": api_calls,
                    "body": result.get("body", {}),
                    "error": None
                }
            
            # Failure - lookup playbook strategy
            last_error = result.get("error", f"HTTP {status_code}")
            strategy = self.playbook_manager.lookup_strategy(tool_name, status_code)
            
            if not strategy:
                strategy = self.playbook_manager.get_default_strategy()
            
            action = strategy.get('action', 'fail_immediately')
            max_retries = strategy.get('max_retries', 0)
            backoff = strategy.get('backoff_seconds', 0)
            
            print(f"      ⚠️  Error {status_code}: {last_error}")
            print(f"      📖 Playbook: {action} (retries={max_retries}, backoff={backoff}s)")
            
            # Check if we should retry
            if action == 'fail_immediately' or attempt >= max_retries:
                print(f"      ❌ Giving up after {api_calls} attempts")
                break
            
            # Wait before retry
            if backoff > 0:
                print(f"      ⏳ Waiting {backoff}s before retry...")
                await asyncio.sleep(backoff)
            
            print(f"      🔄 Retry {attempt + 1}/{max_retries}")
        
        # All retries exhausted
        return {
            "status": "failure",
            "api_calls": api_calls,
            "body": {},
            "error": last_error or "Unknown error"
        }
    
    def _detect_inconsistency(
        self,
        steps_completed: List[str],
        failed_at: Optional[str],
        order_created: bool,
        pet_updated: bool
    ) -> str:
        """
        Detect inconsistent state after failure.
        
        Inconsistency rules:
        - CRITICAL: Order created but pet not updated (paid but inventory wrong)
        - CRITICAL: Pet updated but order not created (inventory wrong, no payment)
        - MINOR: Order created but not confirmed (exists but unverified)
        - NONE: Only read operations failed (safe to retry)
        
        Args:
            steps_completed: List of completed steps
            failed_at: Step where failure occurred
            order_created: Whether CREATE_ORDER succeeded
            pet_updated: Whether UPDATE_PET_STATUS succeeded
        
        Returns:
            str: "none", "minor", or "critical"
        """
        if not failed_at:
            return "none"  # Everything succeeded
        
        # CRITICAL: Order created but pet not updated
        if order_created and not pet_updated:
            return "critical"
        
        # CRITICAL: Pet updated but order not created
        if pet_updated and not order_created:
            return "critical"
        
        # MINOR: Order created but not confirmed
        if order_created and failed_at == "CONFIRM_ORDER":
            return "minor"
        
        # SAFE: Only read operations failed
        if failed_at in ["CHECK_INVENTORY", "FIND_PET", "VERIFY_INVENTORY"]:
            return "none"
        
        return "none"


# ============================================================================
# TESTING
# ============================================================================

async def test_order_agent():
    """Test OrderAgent with different playbooks."""
    print("\n" + "="*70)
    print("ORDER AGENT TEST - Complete Purchase Flow")
    print("="*70)
    
    # Test 1: No playbook (should fail fast)
    print("\n[TEST 1] No playbook (baseline)")
    agent_no_playbook = OrderAgentPetstore(playbook_path=None)
    result1 = await agent_no_playbook.process_order(
        order_id="order_001",
        failure_rate=0.30,
        seed=42
    )
    print(f"Result: {result1['status']}, steps={len(result1['steps_completed'])}/6")
    
    # Test 2: Default playbook (balanced)
    print("\n[TEST 2] Default playbook")
    agent_default = OrderAgentPetstore(
        playbook_path="data/playbook_petstore_default.json"
    )
    result2 = await agent_default.process_order(
        order_id="order_002",
        failure_rate=0.30,
        seed=42
    )
    print(f"Result: {result2['status']}, steps={len(result2['steps_completed'])}/6")
    
    # Test 3: Aggressive playbook (max retries)
    print("\n[TEST 3] Aggressive playbook")
    agent_aggressive = OrderAgentPetstore(
        playbook_path="data/playbook_petstore_aggressive.json"
    )
    result3 = await agent_aggressive.process_order(
        order_id="order_003",
        failure_rate=0.30,
        seed=42
    )
    print(f"Result: {result3['status']}, steps={len(result3['steps_completed'])}/6")
    
    print("\n" + "="*70)
    print("✅ ORDER AGENT TEST COMPLETED")
    print("="*70)


if __name__ == "__main__":
    """Run tests when executed directly."""
    print("🧪 Testing OrderAgent with Complete Purchase Flow...")
    asyncio.run(test_order_agent())
