"""
Diagnostic Script - Phase 6 Chaos Debugging
============================================

Purpose: Understand why ALL orders are failing at step 0.

This script will:
1. Test ChaosConfig.should_inject_failure() behavior
2. Validate seed distribution
3. Simulate 10 orders with detailed logging
4. Identify the root cause
"""

import sys
from pathlib import Path
import asyncio
import random

# Add src to path
src_path = Path(__file__).parent.parent.parent
sys.path.insert(0, str(src_path))

from chaos_playbook_engine.config.chaos_config import ChaosConfig
from chaos_playbook_engine.tools.simulated_apis import call_simulated_inventory_api

print("\n" + "="*70)
print("DIAGNOSTIC SCRIPT - CHAOS BEHAVIOR ANALYSIS")
print("="*70)

# ================================
# TEST 1: ChaosConfig.should_inject_failure() behavior
# ================================

print("\n[TEST 1] ChaosConfig.should_inject_failure() with different seeds")
print("-" * 70)

seeds_to_test = [42, 43, 44, 45, 46, 47, 48, 49, 50, 51, 52]

for seed in seeds_to_test:
    config = ChaosConfig(
        enabled=True,
        failure_rate=0.20,
        failure_type="timeout",
        max_delay_seconds=2,
        seed=seed
    )
    
    # Call should_inject_failure() 5 times with same config
    results = [config.should_inject_failure() for _ in range(5)]
    
    print(f"  seed={seed:3d}: {results} → inject={results[0]}")

print("\n📊 Analysis:")
print("   If ALL first values are True → That's the bug")
print("   If mixed True/False → Seed distribution is working")

# ================================
# TEST 2: Actual random.random() values
# ================================

print("\n[TEST 2] Raw random.random() values with seeds")
print("-" * 70)

print("  seed | random.random() | < 0.20?")
print("  " + "-"*40)

for seed in seeds_to_test[:10]:
    random.seed(seed)
    value = random.random()
    inject = value < 0.20
    symbol = "❌ FAIL" if inject else "✅ PASS"
    print(f"  {seed:3d}  | {value:.6f}       | {inject}  {symbol}")

print("\n📊 Analysis:")
print("   Expected: ~20% should be < 0.20 (2 out of 10)")
print("   If ALL are < 0.20 → Seed sequence is broken")

# ================================
# TEST 3: Simulate actual API calls
# ================================

print("\n[TEST 3] Simulate 10 inventory checks (like order_agent_llm.py)")
print("-" * 70)

async def test_inventory_calls():
    """Simulate 10 inventory checks with unique seeds."""
    results = []
    
    for i in range(10):
        seed_offset = i * 10 + 1  # Same as order_agent_llm.py
        
        config = ChaosConfig(
            enabled=True,
            failure_rate=0.20,
            failure_type="timeout",
            max_delay_seconds=2,
            seed=42 + seed_offset
        )
        
        # Check if failure would be injected
        will_inject = config.should_inject_failure()
        
        # Actually call the API
        try:
            result = await call_simulated_inventory_api(
                endpoint="checkstock",
                payload={"sku": f"order_test_{i}", "qty": 1},
                chaos_config=config
            )
            
            status = result["status"]
            results.append({
                "order": i,
                "seed": 42 + seed_offset,
                "will_inject": will_inject,
                "actual_status": status,
                "match": (will_inject and status == "error") or (not will_inject and status == "success")
            })
            
        except Exception as e:
            results.append({
                "order": i,
                "seed": 42 + seed_offset,
                "will_inject": will_inject,
                "actual_status": "EXCEPTION",
                "error": str(e),
                "match": False
            })
    
    return results

# Run test
results = asyncio.run(test_inventory_calls())

print("  Order | Seed | Predicted | Actual  | Match")
print("  " + "-"*60)

for r in results:
    pred = "FAIL" if r["will_inject"] else "PASS"
    actual = "FAIL" if r["actual_status"] == "error" else ("EXCEPTION" if r["actual_status"] == "EXCEPTION" else "PASS")
    match = "✅" if r["match"] else "❌"
    
    print(f"  {r['order']:5d} | {r['seed']:4d} | {pred:9s} | {actual:7s} | {match}")
    
    if r["actual_status"] == "EXCEPTION":
        print(f"        ERROR: {r.get('error', 'Unknown')}")

# Calculate success rate
successes = sum(1 for r in results if r["actual_status"] == "success")
success_rate = successes / len(results)

print(f"\n📊 Results:")
print(f"   Success rate: {success_rate:.1%} ({successes}/{len(results)})")
print(f"   Expected: 60-80% (accounting for 20% chaos + multi-step failures)")
print(f"   Actual: {success_rate:.1%}")

if success_rate == 0.0:
    print("\n❌ CRITICAL: 0% success rate confirms the bug")
    print("   → Look at 'Match' column to see if predictions match actual behavior")
    print("   → If matches are all ❌, then ChaosConfig.should_inject_failure() is broken")
    print("   → If matches are ✅ but all fail, then problem is in simulated_apis.py")
elif success_rate < 0.50:
    print("\n⚠️  WARNING: Success rate too low")
else:
    print("\n✅ SUCCESS: Chaos distribution is working correctly")

# ================================
# TEST 4: Check ChaosConfig implementation
# ================================

print("\n[TEST 4] Inspecting ChaosConfig.should_inject_failure() implementation")
print("-" * 70)

import inspect

# Get source code of should_inject_failure
try:
    source = inspect.getsource(ChaosConfig.should_inject_failure)
    print(source)
except Exception as e:
    print(f"❌ Could not inspect source: {e}")

print("\n" + "="*70)
print("DIAGNOSTIC COMPLETE")
print("="*70)
print("\n📋 Next Steps:")
print("   1. Review TEST 1 results - are first values all True?")
print("   2. Review TEST 2 results - are raw random values distributed correctly?")
print("   3. Review TEST 3 results - does predicted behavior match actual?")
print("   4. Review TEST 4 - what is the actual implementation of should_inject_failure()?")
print("\nShare ALL output with me to diagnose the issue.")
