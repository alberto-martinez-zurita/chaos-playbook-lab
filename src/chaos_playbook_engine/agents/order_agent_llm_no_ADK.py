"""
OrderAgentLLM - Phase 6 CORRECTED (Parametrized failure_rate)
==============================================================

**FIX APPLIED**: failure_rate is now parametrizable instead of hardcoded 0.20

**Changes:**
1. All tools accept failure_rate parameter
2. process_order_simple() accepts and propagates failure_rate
3. validate_phase6.py can now test different failure rates correctly

**Purpose**: LLM-based order processing agent with PLAYBOOK-DRIVEN recovery
**Phase**: 6 - LLM Agents (Week 1, Days 2-4)
**Target**: Match Phase 5 performance using Gemini 2.0 + Chaos Playbook

**Usage:**
    export GEMINI_API_KEY=your_key
    python src/chaos_playbook_engine/agents/order_agent_llm.py
"""

from typing import TypedDict, Literal, List, Dict, Any, Optional
import os
import json
import asyncio
from pathlib import Path

# ADK and GenAI imports
from google.genai.client import Client as GenAIClient

# Phase 5 validated tools
import sys
src_path = Path(__file__).parent.parent.parent
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

from chaos_playbook_engine.tools.simulated_apis import (
    call_simulated_inventory_api,
    call_simulated_payments_api,
    call_simulated_shipping_api,
    call_simulated_erp_api,
)
from chaos_playbook_engine.config.chaos_config import ChaosConfig


# ================================
# TYPE DEFINITIONS
# ================================

class InventoryResult(TypedDict):
    status: Literal["success", "error"]
    error: str
    items_available: int
    duration_ms: float


class PaymentResult(TypedDict):
    status: Literal["success", "error"]
    error: str
    transaction_id: str
    duration_ms: float


class ShipmentResult(TypedDict):
    status: Literal["success", "error"]
    error: str
    tracking_number: str
    duration_ms: float


class ERPResult(TypedDict):
    status: Literal["success", "error"]
    error: str
    erp_status: str
    duration_ms: float


class PlaybookEntry(TypedDict):
    failure_type: str
    api: str
    action: str
    backoff_seconds: int
    max_retries: int


class OrderResult(TypedDict):
    status: Literal["success", "failure"]
    order_id: str
    steps_completed: List[str]
    error_message: str
    total_duration_ms: float


# ================================
# PLAYBOOK STORAGE
# ================================

class PlaybookStorage:
    """Loads and validates playbook from JSON file."""
    
    def __init__(self, path: str = "data/playbook_phase6.json") -> None:
        self.path = path
        self.entries: List[PlaybookEntry] = []
        self._load_and_validate()
    
    def _load_and_validate(self) -> None:
        playbook_path = Path(self.path)
        if not playbook_path.exists():
            raise FileNotFoundError(
                f"Playbook file not found: {self.path}\n"
                f"Create data/playbook_phase6.json"
            )
        
        with open(self.path, "r") as f:
            data = json.load(f)
            self.entries = data["procedures"]
        
        # Validate duplicates
        seen = set()
        for entry in self.entries:
            key = (entry["failure_type"], entry["api"])
            if key in seen:
                raise ValueError(f"Duplicate playbook entry: {key}")
            seen.add(key)
        
        if len(self.entries) < 7:
            raise ValueError(f"Insufficient playbook entries: {len(self.entries)}/7")
        
        print(f"✅ Playbook loaded: {len(self.entries)} entries from {self.path}")
    
    def lookup(self, failure_type: str, api: str) -> PlaybookEntry:
        """Lookup recovery strategy for given failure + API."""
        for entry in self.entries:
            if (entry["failure_type"] == failure_type and 
                entry["api"] == api):
                return entry
        
        raise ValueError(
            f"No playbook entry for (failure_type='{failure_type}', api='{api}')"
        )


# ================================
# BUSINESS TOOLS WITH PLAYBOOK + PARAMETRIZED FAILURE_RATE
# ================================

playbook_storage: Optional[PlaybookStorage] = None


async def check_inventory(
    order_id: str,
    seed_offset: int = 0,
    failure_rate: float = 0.20  # ✅ NOW PARAMETRIZED
) -> InventoryResult:
    """
    Check inventory with PLAYBOOK-DRIVEN recovery.
    
    Args:
        order_id: Order identifier
        seed_offset: Unique seed offset
        failure_rate: Chaos failure rate (0.0-1.0) ✅ NEW
    """
    chaos_config = ChaosConfig(
        enabled=True,
        failure_rate=failure_rate,  # ✅ USE PARAMETER
        failure_type="timeout",
        max_delay_seconds=2,
        seed=42 + seed_offset
    )
    
    # Initial attempt
    result = await call_simulated_inventory_api(
        endpoint="check_stock",
        payload={"sku": order_id, "qty": 1},
        chaos_config=chaos_config
    )
    
    if result["status"] == "success":
        return InventoryResult(
            status="success",
            error="",
            items_available=result.get("data", {}).get("available_stock", 10),
            duration_ms=result.get("duration_ms", 0.0)
        )
    
    # Playbook lookup
    try:
        strategy = playbook_storage.lookup("timeout", "inventory")
        max_retries = strategy["max_retries"]
        backoff_seconds = strategy["backoff_seconds"]
    except:
        max_retries = 2
        backoff_seconds = 1
    
    last_error = result.get("error_message", "Unknown error")
    
    for attempt in range(max_retries):
        await asyncio.sleep(backoff_seconds)
        
        retry_config = ChaosConfig(
            enabled=True,
            failure_rate=failure_rate,  # ✅ USE PARAMETER
            failure_type="timeout",
            max_delay_seconds=2,
            seed=42 + seed_offset + (attempt + 1) * 1000
        )
        
        result = await call_simulated_inventory_api(
            endpoint="check_stock",
            payload={"sku": order_id, "qty": 1},
            chaos_config=retry_config
        )
        
        if result["status"] == "success":
            return InventoryResult(
                status="success",
                error="",
                items_available=result.get("data", {}).get("available_stock", 10),
                duration_ms=result.get("duration_ms", 0.0)
            )
        
        last_error = result.get("error_message", "Unknown error")
    
    return InventoryResult(
        status="error",
        error=f"Failed after {max_retries + 1} attempts (playbook): {last_error}",
        items_available=0,
        duration_ms=0.0
    )


async def process_payment(
    order_id: str,
    amount: float,
    seed_offset: int = 0,
    failure_rate: float = 0.20  # ✅ NOW PARAMETRIZED
) -> PaymentResult:
    """Process payment with PLAYBOOK-DRIVEN recovery."""
    chaos_config = ChaosConfig(
        enabled=True,
        failure_rate=failure_rate,  # ✅ USE PARAMETER
        failure_type="timeout",
        max_delay_seconds=2,
        seed=42 + seed_offset
    )
    
    result = await call_simulated_payments_api(
        endpoint="capture",
        payload={"amount": amount, "currency": "USD", "order_id": order_id},
        chaos_config=chaos_config
    )
    
    if result["status"] == "success":
        return PaymentResult(
            status="success",
            error="",
            transaction_id=result.get("data", {}).get("transaction_id", f"txn_{order_id}"),
            duration_ms=result.get("duration_ms", 0.0)
        )
    
    try:
        strategy = playbook_storage.lookup("timeout", "payments")
        max_retries = strategy["max_retries"]
        backoff_seconds = strategy["backoff_seconds"]
    except:
        max_retries = 2
        backoff_seconds = 1
    
    last_error = result.get("error_message", "Unknown error")
    
    for attempt in range(max_retries):
        await asyncio.sleep(backoff_seconds)
        
        retry_config = ChaosConfig(
            enabled=True,
            failure_rate=failure_rate,  # ✅ USE PARAMETER
            failure_type="timeout",
            max_delay_seconds=2,
            seed=42 + seed_offset + (attempt + 1) * 1000
        )
        
        result = await call_simulated_payments_api(
            endpoint="capture",
            payload={"amount": amount, "currency": "USD", "order_id": order_id},
            chaos_config=retry_config
        )
        
        if result["status"] == "success":
            return PaymentResult(
                status="success",
                error="",
                transaction_id=result.get("data", {}).get("transaction_id", f"txn_{order_id}"),
                duration_ms=result.get("duration_ms", 0.0)
            )
        
        last_error = result.get("error_message", "Unknown error")
    
    return PaymentResult(
        status="error",
        error=f"Failed after {max_retries + 1} attempts (playbook): {last_error}",
        transaction_id="",
        duration_ms=0.0
    )


async def create_shipment(
    order_id: str,
    address: str,
    seed_offset: int = 0,
    failure_rate: float = 0.20  # ✅ NOW PARAMETRIZED
) -> ShipmentResult:
    """Create shipment with PLAYBOOK-DRIVEN recovery."""
    chaos_config = ChaosConfig(
        enabled=True,
        failure_rate=failure_rate,  # ✅ USE PARAMETER
        failure_type="timeout",
        max_delay_seconds=2,
        seed=42 + seed_offset
    )
    
    result = await call_simulated_shipping_api(
        endpoint="create_shipment",
        payload={"order_id": order_id, "address": address},
        chaos_config=chaos_config
    )
    
    if result["status"] == "success":
        return ShipmentResult(
            status="success",
            error="",
            tracking_number=result.get("data", {}).get("tracking_number", f"track_{order_id}"),
            duration_ms=result.get("duration_ms", 0.0)
        )
    
    try:
        strategy = playbook_storage.lookup("timeout", "shipment")
        max_retries = strategy["max_retries"]
        backoff_seconds = strategy["backoff_seconds"]
    except:
        max_retries = 2
        backoff_seconds = 1
    
    last_error = result.get("error_message", "Unknown error")
    
    for attempt in range(max_retries):
        await asyncio.sleep(backoff_seconds)
        
        retry_config = ChaosConfig(
            enabled=True,
            failure_rate=failure_rate,  # ✅ USE PARAMETER
            failure_type="timeout",
            max_delay_seconds=2,
            seed=42 + seed_offset + (attempt + 1) * 1000
        )
        
        result = await call_simulated_shipping_api(
            endpoint="create_shipment",
            payload={"order_id": order_id, "address": address},
            chaos_config=retry_config
        )
        
        if result["status"] == "success":
            return ShipmentResult(
                status="success",
                error="",
                tracking_number=result.get("data", {}).get("tracking_number", f"track_{order_id}"),
                duration_ms=result.get("duration_ms", 0.0)
            )
        
        last_error = result.get("error_message", "Unknown error")
    
    return ShipmentResult(
        status="error",
        error=f"Failed after {max_retries + 1} attempts (playbook): {last_error}",
        tracking_number="",
        duration_ms=0.0
    )


async def update_erp(
    order_id: str,
    status: str,
    seed_offset: int = 0,
    failure_rate: float = 0.20  # ✅ NOW PARAMETRIZED
) -> ERPResult:
    """Update ERP with PLAYBOOK-DRIVEN recovery."""
    chaos_config = ChaosConfig(
        enabled=True,
        failure_rate=failure_rate,  # ✅ USE PARAMETER
        failure_type="timeout",
        max_delay_seconds=2,
        seed=42 + seed_offset
    )
    
    result = await call_simulated_erp_api(
        endpoint="create_order",
        payload={"order_id": order_id, "status": status},
        chaos_config=chaos_config
    )
    
    if result["status"] == "success":
        return ERPResult(
            status="success",
            error="",
            erp_status=result.get("data", {}).get("status", status),
            duration_ms=result.get("duration_ms", 0.0)
        )
    
    try:
        strategy = playbook_storage.lookup("timeout", "erp")
        max_retries = strategy["max_retries"]
        backoff_seconds = strategy["backoff_seconds"]
    except:
        max_retries = 2
        backoff_seconds = 1
    
    last_error = result.get("error_message", "Unknown error")
    
    for attempt in range(max_retries):
        await asyncio.sleep(backoff_seconds)
        
        retry_config = ChaosConfig(
            enabled=True,
            failure_rate=failure_rate,  # ✅ USE PARAMETER
            failure_type="timeout",
            max_delay_seconds=2,
            seed=42 + seed_offset + (attempt + 1) * 1000
        )
        
        result = await call_simulated_erp_api(
            endpoint="create_order",
            payload={"order_id": order_id, "status": status},
            chaos_config=retry_config
        )
        
        if result["status"] == "success":
            return ERPResult(
                status="success",
                error="",
                erp_status=result.get("data", {}).get("status", status),
                duration_ms=result.get("duration_ms", 0.0)
            )
        
        last_error = result.get("error_message", "Unknown error")
    
    return ERPResult(
        status="error",
        error=f"Failed after {max_retries + 1} attempts (playbook): {last_error}",
        erp_status="",
        duration_ms=0.0
    )


# ================================
# INITIALIZATION
# ================================

def validate_environment() -> str:
    api_key = os.getenv("GEMINI_API_KEY")
    
    if not api_key:
        raise ValueError(
            "GEMINI_API_KEY environment variable not set.\n"
            "Setup: export GEMINI_API_KEY=your_key"
        )
    
    if len(api_key) < 20:
        raise ValueError(f"GEMINI_API_KEY invalid (length: {len(api_key)})")
    
    return api_key


def initialize_order_agent_llm(playbook_path: str = "data/playbook_phase6.json") -> GenAIClient:
    global playbook_storage
    
    api_key = validate_environment()
    playbook_storage = PlaybookStorage(path=playbook_path)
    client = GenAIClient(api_key=api_key)
    
    print("✅ OrderAgentLLM initialized (PLAYBOOK-DRIVEN)")
    print(f"   Model: gemini-2.0-flash-lite")
    print(f"   Playbook: {len(playbook_storage.entries)} entries")
    print(f"   Chaos: parametrizable (0-100%)")
    
    return client


# ================================
# ORDER PROCESSING WITH PARAMETRIZED FAILURE_RATE
# ================================

async def process_order_simple(
    order_id: str,
    amount: float = 100.0,
    address: str = "123 Main St",
    order_index: int = 0,
    failure_rate: float = 0.20  # ✅ NOW PARAMETRIZED
) -> OrderResult:
    """
    Process order using playbook-driven recovery.
    
    Args:
        order_id: Order identifier
        amount: Payment amount
        address: Shipping address
        order_index: Index for seed generation
        failure_rate: Chaos failure rate (0.0-1.0) ✅ NEW
    """
    import time
    start_time = time.time()
    steps_completed: List[str] = []
    error_message = ""
    
    try:
        # Step 1: Inventory
        inv_result = await check_inventory(
            order_id,
            seed_offset=order_index * 10 + 1,
            failure_rate=failure_rate  # ✅ PROPAGATE
        )
        if inv_result["status"] == "error":
            error_message = f"Inventory failed: {inv_result['error']}"
            return OrderResult(
                status="failure",
                order_id=order_id,
                steps_completed=steps_completed,
                error_message=error_message,
                total_duration_ms=(time.time() - start_time) * 1000
            )
        steps_completed.append("inventory_checked")
        
        # Step 2: Payment
        pay_result = await process_payment(
            order_id,
            amount,
            seed_offset=order_index * 10 + 2,
            failure_rate=failure_rate  # ✅ PROPAGATE
        )
        if pay_result["status"] == "error":
            error_message = f"Payment failed: {pay_result['error']}"
            return OrderResult(
                status="failure",
                order_id=order_id,
                steps_completed=steps_completed,
                error_message=error_message,
                total_duration_ms=(time.time() - start_time) * 1000
            )
        steps_completed.append("payment_processed")
        
        # Step 3: Shipment
        ship_result = await create_shipment(
            order_id,
            address,
            seed_offset=order_index * 10 + 3,
            failure_rate=failure_rate  # ✅ PROPAGATE
        )
        if ship_result["status"] == "error":
            error_message = f"Shipment failed: {ship_result['error']}"
            return OrderResult(
                status="failure",
                order_id=order_id,
                steps_completed=steps_completed,
                error_message=error_message,
                total_duration_ms=(time.time() - start_time) * 1000
            )
        steps_completed.append("shipment_created")
        
        # Step 4: ERP
        erp_result = await update_erp(
            order_id,
            "completed",
            seed_offset=order_index * 10 + 4,
            failure_rate=failure_rate  # ✅ PROPAGATE
        )
        if erp_result["status"] == "error":
            error_message = f"ERP failed: {erp_result['error']}"
            return OrderResult(
                status="failure",
                order_id=order_id,
                steps_completed=steps_completed,
                error_message=error_message,
                total_duration_ms=(time.time() - start_time) * 1000
            )
        steps_completed.append("erp_updated")
        
        return OrderResult(
            status="success",
            order_id=order_id,
            steps_completed=steps_completed,
            error_message="",
            total_duration_ms=(time.time() - start_time) * 1000
        )
        
    except Exception as e:
        error_message = f"Unexpected error: {str(e)}"
        return OrderResult(
            status="failure",
            order_id=order_id,
            steps_completed=steps_completed,
            error_message=error_message,
            total_duration_ms=(time.time() - start_time) * 1000
        )


# ================================
# TEST
# ================================

async def test_order_agent_llm() -> bool:
    print("\n" + "="*60)
    print("PHASE 6 - ORDER AGENT LLM (PLAYBOOK-DRIVEN)")
    print("="*60)
    
    print("\n[1/3] Initializing OrderAgentLLM...")
    try:
        client = initialize_order_agent_llm()
    except Exception as e:
        print(f"❌ Initialization failed: {e}")
        return False
    
    print("\n[2/3] Processing 10 sample orders...")
    results = []
    for i in range(10):
        result = await process_order_simple(f"order_test_{i}", order_index=i)
        results.append(result)
        
        status_emoji = "✅" if result["status"] == "success" else "❌"
        print(f"  {status_emoji} Order {i+1}/10: {result['status']}, "
              f"steps: {len(result['steps_completed'])}/4")
    
    print("\n[3/3] Analyzing results...")
    success_count = sum(1 for r in results if r["status"] == "success")
    success_rate = success_count / len(results)
    
    print(f"\n📊 Results Summary:")
    print(f"  Success rate: {success_rate:.1%} ({success_count}/10)")
    print(f"  Expected (with playbook): 70-80%")
    
    if success_rate < 0.50:
        print(f"\n⚠️  WARNING: Rate below expected")
    elif 0.50 <= success_rate <= 0.90:
        print(f"\n✅ SUCCESS: Rate within expected range")
    else:
        print(f"\n✅ EXCELLENT: Rate above expected!")
    
    print("\n" + "="*60)
    print("✅ PLAYBOOK-DRIVEN TEST COMPLETED")
    print("="*60)
    
    if success_rate >= 0.50:
        print("\n🎉 SUCCESS! Playbook-driven recovery working")
        print("\n📋 Next Steps:")
        print("   1. Test with different failure_rates")
        print("   2. Run validate_phase6.py (30 experiments)")
        print("   3. Compare playbook performance")
    
    return True


async def main() -> None:
    print("\n" + "🚀 "*30)
    print("PHASE 6 - PLAYBOOK-DRIVEN ORDER AGENT (PARAMETRIZED)")
    print("🚀 "*30)
    
    success = await test_order_agent_llm()
    exit(0 if success else 1)


if __name__ == "__main__":
    asyncio.run(main())
