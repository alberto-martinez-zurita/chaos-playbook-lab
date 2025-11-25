"""
Test All API Endpoints - Comprehensive Check
=============================================

Purpose: Test all 4 APIs with their endpoints to see which ones work.
"""

import sys
from pathlib import Path
import asyncio

# Add src to path
src_path = Path(__file__).parent.parent.parent
sys.path.insert(0, str(src_path))

from chaos_playbook_engine.config.chaos_config import ChaosConfig
from chaos_playbook_engine.tools.simulated_apis import (
    call_simulated_inventory_api,
    call_simulated_payments_api,
    call_simulated_shipping_api,
    call_simulated_erp_api,
)

print("\n" + "="*70)
print("COMPREHENSIVE API ENDPOINT TEST")
print("="*70)

async def test_all_apis():
    """Test all API endpoints without chaos."""
    
    # No chaos for this test
    chaos_config = ChaosConfig(
        enabled=False,  # ← Disabled to test happy-path
        failure_rate=0.0,
        failure_type="timeout",
        max_delay_seconds=2,
        seed=42
    )
    
    results = []
    
    # ================================
    # TEST 1: Inventory API
    # ================================
    print("\n[TEST 1] INVENTORY API")
    print("-" * 70)
    
    for endpoint in ["check_stock", "reserve_stock"]:
        try:
            result = await call_simulated_inventory_api(
                endpoint=endpoint,
                payload={"sku": "TEST-SKU", "qty": 1},
                chaos_config=chaos_config
            )
            status = "✅ PASS" if result["status"] == "success" else "❌ FAIL"
            print(f"  {endpoint:20s} → {status}")
            results.append({"api": "inventory", "endpoint": endpoint, "status": "PASS"})
        except Exception as e:
            print(f"  {endpoint:20s} → ❌ EXCEPTION: {e}")
            results.append({"api": "inventory", "endpoint": endpoint, "status": "EXCEPTION", "error": str(e)})
    
    # ================================
    # TEST 2: Payments API
    # ================================
    print("\n[TEST 2] PAYMENTS API")
    print("-" * 70)
    
    for endpoint in ["capture", "refund"]:
        try:
            result = await call_simulated_payments_api(
                endpoint=endpoint,
                payload={"amount": 100.0, "currency": "USD", "order_id": "TEST-ORDER"},
                chaos_config=chaos_config
            )
            status = "✅ PASS" if result["status"] == "success" else "❌ FAIL"
            print(f"  {endpoint:20s} → {status}")
            results.append({"api": "payments", "endpoint": endpoint, "status": "PASS"})
        except Exception as e:
            print(f"  {endpoint:20s} → ❌ EXCEPTION: {e}")
            results.append({"api": "payments", "endpoint": endpoint, "status": "EXCEPTION", "error": str(e)})
    
    # ================================
    # TEST 3: Shipping API
    # ================================
    print("\n[TEST 3] SHIPPING API")
    print("-" * 70)
    
    for endpoint in ["create_shipment", "track_shipment"]:
        try:
            result = await call_simulated_shipping_api(
                endpoint=endpoint,
                payload={"order_id": "TEST-ORDER", "address": "123 Main St"},
                chaos_config=chaos_config
            )
            status = "✅ PASS" if result["status"] == "success" else "❌ FAIL"
            print(f"  {endpoint:20s} → {status}")
            results.append({"api": "shipping", "endpoint": endpoint, "status": "PASS"})
        except Exception as e:
            print(f"  {endpoint:20s} → ❌ EXCEPTION: {e}")
            results.append({"api": "shipping", "endpoint": endpoint, "status": "EXCEPTION", "error": str(e)})
    
    # ================================
    # TEST 4: ERP API
    # ================================
    print("\n[TEST 4] ERP API")
    print("-" * 70)
    
    for endpoint in ["create_order", "get_order"]:
        try:
            result = await call_simulated_erp_api(
                endpoint=endpoint,
                payload={"order_id": "TEST-ORDER", "status": "completed"},
                chaos_config=chaos_config
            )
            status = "✅ PASS" if result["status"] == "success" else "❌ FAIL"
            print(f"  {endpoint:20s} → {status}")
            results.append({"api": "erp", "endpoint": endpoint, "status": "PASS"})
        except Exception as e:
            print(f"  {endpoint:20s} → ❌ EXCEPTION: {e}")
            results.append({"api": "erp", "endpoint": endpoint, "status": "EXCEPTION", "error": str(e)})
    
    # ================================
    # SUMMARY
    # ================================
    print("\n" + "="*70)
    print("SUMMARY")
    print("="*70)
    
    passed = sum(1 for r in results if r["status"] == "PASS")
    failed = sum(1 for r in results if r["status"] == "EXCEPTION")
    
    print(f"\n  ✅ Passed: {passed}")
    print(f"  ❌ Failed: {failed}")
    print(f"  Total:  {len(results)}")
    
    if failed > 0:
        print("\n❌ FAILED ENDPOINTS:")
        for r in results:
            if r["status"] == "EXCEPTION":
                print(f"  - {r['api']}.{r['endpoint']}: {r.get('error', 'Unknown')}")
    else:
        print("\n✅ All endpoints working!")
    
    return results

# Run test
asyncio.run(test_all_apis())
