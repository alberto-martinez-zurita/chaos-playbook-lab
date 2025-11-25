"""
validate_phase6.py - Phase 6 Validation Script (FIXED)
=======================================================

**FIX APPLIED**: Now passes failure_rate to process_order_simple()

**Purpose**: Run 30 deterministic experiments to validate OrderAgentLLM
             matches Phase 5 baseline (±5% tolerance).

**Requirements**: AC-PHASE6-001
- 30 experiments (3 rates × 10 experiments)
- Failure rates: 0.0, 0.10, 0.20
- Deterministic: Same seed → same results
- Output: CSV + JSON + Pass/Fail report

**Usage**:
    python scripts/validate_phase6.py

**Expected Output**:
    PHASE 6 VALIDATION PASSED ✅
    Success rates within ±5% tolerance for all 3 rates
"""

from pathlib import Path
import json
import csv
import asyncio
import sys
from datetime import datetime
from typing import List, Dict

# Add src to path
src_path = Path(__file__).parent.parent / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

# Import OrderAgentLLM
from chaos_playbook_engine.agents.order_agent_llm import (
    initialize_order_agent_llm,
    process_order_simple
)

# ================================
# PHASE 5 BASELINE (from parametric results)
# ================================

PHASE5_BASELINE = {
    0.0: 1.00,   # 100% success
    0.10: 0.80,  # 80% success
    0.20: 0.49   # 49% success
}

TOLERANCE = 0.05  # ±5%


# ================================
# EXPERIMENT EXECUTION
# ================================

async def run_experiment(
    experiment_id: str,
    failure_rate: float,
    seed: int
) -> Dict:
    """
    Run single experiment with OrderAgentLLM.
    
    Args:
        experiment_id: Unique experiment identifier
        failure_rate: Chaos failure rate (0.0, 0.10, 0.20)
        seed: Deterministic seed for reproducibility
    
    Returns:
        Dict with experiment_id, failure_rate, seed, outcome, duration_ms
    """
    import time
    start_time = time.time()
    
    # ✅ FIX: Now passing failure_rate parameter
    result = await process_order_simple(
        order_id=f"exp_{experiment_id}",
        order_index=seed,
        failure_rate=failure_rate  # ✅ ADDED
    )
    
    duration_ms = (time.time() - start_time) * 1000
    
    return {
        "experiment_id": experiment_id,
        "failure_rate": failure_rate,
        "seed": seed,
        "outcome": result["status"],  # "success" or "failure"
        "steps_completed": len(result["steps_completed"]),
        "error_message": result.get("error_message", ""),
        "duration_ms": round(duration_ms, 2)
    }


# ================================
# VALIDATION LOGIC
# ================================

async def run_validation() -> bool:
    """
    Run 30 experiments and validate against Phase 5 baseline.
    
    Returns:
        True if all acceptance criteria met, False otherwise
    """
    print("\n" + "="*60)
    print("PHASE 6 - VALIDATION (30 EXPERIMENTS - FIXED)")
    print("="*60)
    
    # Initialize OrderAgentLLM
    print("\n[1/4] Initializing OrderAgentLLM...")
    try:
        client = initialize_order_agent_llm()
    except Exception as e:
        print(f"❌ Initialization failed: {e}")
        return False
    
    # Configuration
    failure_rates = [0.0, 0.10, 0.20]
    experiments_per_rate = 10
    base_seed = 1000
    
    all_results = []
    
    # Run experiments
    print("\n[2/4] Running 30 experiments...")
    print("-" * 60)
    
    for rate in failure_rates:
        print(f"\n{rate:.0%} chaos: Running {experiments_per_rate} experiments...")
        
        for i in range(experiments_per_rate):
            exp_id = f"PHASE6-{rate:.2f}-{i+1:02d}"
            seed = base_seed + int(rate * 100) + i
            
            result = await run_experiment(exp_id, rate, seed)
            all_results.append(result)
            
            status = "✅" if result["outcome"] == "success" else "❌"
            print(f"  {status} Exp {i+1}/{experiments_per_rate}: {result['outcome']}")
    
    # Calculate success rates
    print("\n[3/4] Calculating success rates...")
    print("-" * 60)
    
    success_rates = {}
    for rate in failure_rates:
        rate_results = [r for r in all_results if r["failure_rate"] == rate]
        successes = sum(1 for r in rate_results if r["outcome"] == "success")
        success_rates[rate] = successes / len(rate_results)
    
    # Validate against baseline
    print("\n[4/4] Validating against Phase 5 baseline...")
    print("="*60)
    print("VALIDATION RESULTS")
    print("="*60)
    
    all_passed = True
    for rate in failure_rates:
        phase6_rate = success_rates[rate]
        phase5_rate = PHASE5_BASELINE[rate]
        delta = phase6_rate - phase5_rate
        
        lower_bound = phase5_rate - TOLERANCE
        upper_bound = phase5_rate + TOLERANCE
        passed = lower_bound <= phase6_rate <= upper_bound
        
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"\n{rate:.0%} chaos:")
        print(f"  Phase 5 baseline: {phase5_rate:.1%}")
        print(f"  Phase 6 result:   {phase6_rate:.1%}")
        print(f"  Delta:            {delta:+.1%}")
        print(f"  Tolerance:        ±{TOLERANCE:.0%}")
        print(f"  Status:           {status}")
        
        if not passed:
            all_passed = False
    
    # Save results
    output_dir = Path("results/phase6_validation")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # CSV
    csv_path = output_dir / f"validation_{timestamp}.csv"
    with open(csv_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=all_results[0].keys())
        writer.writeheader()
        writer.writerows(all_results)
    
    # JSON
    json_path = output_dir / f"validation_{timestamp}.json"
    with open(json_path, "w") as f:
        json.dump({
            "success_rates": {str(k): v for k, v in success_rates.items()},
            "baseline": {str(k): v for k, v in PHASE5_BASELINE.items()},
            "tolerance": TOLERANCE,
            "passed": all_passed,
            "experiments": all_results
        }, f, indent=2)
    
    # Print summary
    print("\n" + "="*60)
    print("FILES SAVED")
    print("="*60)
    print(f"  CSV:  {csv_path}")
    print(f"  JSON: {json_path}")
    
    print("\n" + "="*60)
    if all_passed:
        print("✅ PHASE 6 VALIDATION PASSED")
        print("="*60)
        print("\n🎉 SUCCESS! OrderAgentLLM matches Phase 5 baseline (±5%)")
        print("\n📋 Next Steps:")
        print("   1. Review validation results in CSV/JSON")
        print("   2. Proceed to PROMPT 3: test_order_agent_llm.py (unit tests)")
        print("   3. Proceed to Phase 7: Playbook Validation")
    else:
        print("❌ PHASE 6 VALIDATION FAILED")
        print("="*60)
        print("\n⚠️  OrderAgentLLM does NOT match Phase 5 baseline")
        print("\n🔍 Debug Steps:")
        print("   1. Review failure_rate configuration")
        print("   2. Check chaos injection is working")
        print("   3. Verify playbook lookup integration")
        print("   4. Check seed generation logic")
        print("\n💡 NOTE: If Phase 6 EXCEEDS baseline significantly,")
        print("   that may be SUCCESS (playbook improves resilience).")
        print("   Consider adjusting expectations if consistent.")
    
    return all_passed


# ================================
# MAIN ENTRY POINT
# ================================

if __name__ == "__main__":
    success = asyncio.run(run_validation())
    exit(0 if success else 1)
