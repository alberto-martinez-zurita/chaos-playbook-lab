"""
validate_3_agents.py - Phase 5 + Phase 6 Integration
=====================================================

**Purpose**: Compare 3 agents with same chaos injection:
  1. Baseline (no retries) - Phase 5
  2. Playbook Simulated (hardcoded retries) - Phase 5
  3. OrderAgentLLM (playbook-driven retries) - Phase 6

**Usage**:
    python scripts/validate_3_agents.py

**Output**:
    - CSV with all experiments
    - JSON with aggregated results
    - Comparison table (3 agents × 3 failure rates)
"""

from pathlib import Path
import json
import csv
import asyncio
import sys
from datetime import datetime
from typing import List, Dict, Literal

# Add src to path
src_path = Path(__file__).parent.parent / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

# Phase 6 agent
from chaos_playbook_engine.agents.order_agent_llm import (
    initialize_order_agent_llm,
    process_order_simple
)

# Shared chaos injection
from chaos_playbook_engine.tools.simulated_apis import (
    call_simulated_inventory_api,
    call_simulated_payments_api,
    call_simulated_shipping_api,
    call_simulated_erp_api,
)
from chaos_playbook_engine.config.chaos_config import ChaosConfig


# ================================
# AGENT 1: BASELINE (NO RETRIES)
# ================================

class BaselineAgent:
    """Phase 5 baseline agent - no retries."""
    
    @staticmethod
    async def process_order(
        order_id: str,
        failure_rate: float,
        seed: int
    ) -> Dict:
        """Process order WITHOUT retries."""
        steps = ["inventory", "payment", "shipment", "erp"]
        steps_completed = []
        
        for i, step in enumerate(steps):
            chaos_config = ChaosConfig(
                enabled=True,
                failure_rate=failure_rate,
                failure_type="timeout",
                max_delay_seconds=2,
                seed=42 + seed + i
            )
            
            # Call API without retry
            if step == "inventory":
                result = await call_simulated_inventory_api(
                    "check_stock",
                    {"sku": order_id, "qty": 1},
                    chaos_config
                )
            elif step == "payment":
                result = await call_simulated_payments_api(
                    "capture",
                    {"amount": 100.0, "currency": "USD"},
                    chaos_config
                )
            elif step == "shipment":
                result = await call_simulated_shipping_api(
                    "create_shipment",
                    {"order_id": order_id, "address": "123 Main St"},
                    chaos_config
                )
            else:  # erp
                result = await call_simulated_erp_api(
                    "create_order",
                    {"order_id": order_id, "status": "completed"},
                    chaos_config
                )
            
            # Fail immediately if error
            if result["status"] == "error":
                return {
                    "status": "failure",
                    "steps_completed": steps_completed,
                    "failed_at": step
                }
            
            steps_completed.append(step)
        
        return {
            "status": "success",
            "steps_completed": steps_completed,
            "failed_at": None
        }


# ================================
# AGENT 2: PLAYBOOK SIMULATED (HARDCODED RETRIES)
# ================================

class PlaybookSimulatedAgent:
    """Phase 5 playbook agent - hardcoded retries."""
    
    @staticmethod
    async def process_order(
        order_id: str,
        failure_rate: float,
        seed: int
    ) -> Dict:
        """Process order WITH hardcoded retries (max_retries=2)."""
        steps = ["inventory", "payment", "shipment", "erp"]
        steps_completed = []
        max_retries = 2
        
        for step_idx, step in enumerate(steps):
            success = False
            
            # Try initial + retries
            for attempt in range(max_retries + 1):
                chaos_config = ChaosConfig(
                    enabled=True,
                    failure_rate=failure_rate,
                    failure_type="timeout",
                    max_delay_seconds=2,
                    seed=42 + seed + step_idx + attempt * 1000
                )
                
                # Call API
                if step == "inventory":
                    result = await call_simulated_inventory_api(
                        "check_stock",
                        {"sku": order_id, "qty": 1},
                        chaos_config
                    )
                elif step == "payment":
                    result = await call_simulated_payments_api(
                        "capture",
                        {"amount": 100.0, "currency": "USD"},
                        chaos_config
                    )
                elif step == "shipment":
                    result = await call_simulated_shipping_api(
                        "create_shipment",
                        {"order_id": order_id, "address": "123 Main St"},
                        chaos_config
                    )
                else:  # erp
                    result = await call_simulated_erp_api(
                        "create_order",
                        {"order_id": order_id, "status": "completed"},
                        chaos_config
                    )
                
                if result["status"] == "success":
                    success = True
                    break
                
                # Wait before retry
                if attempt < max_retries:
                    await asyncio.sleep(0.5)
            
            # If all retries exhausted
            if not success:
                return {
                    "status": "failure",
                    "steps_completed": steps_completed,
                    "failed_at": step
                }
            
            steps_completed.append(step)
        
        return {
            "status": "success",
            "steps_completed": steps_completed,
            "failed_at": None
        }


# ================================
# AGENT 3: ORDER AGENT LLM (PHASE 6)
# ================================

class OrderAgentLLMWrapper:
    """Phase 6 OrderAgentLLM wrapper."""
    
    @staticmethod
    async def process_order(
        order_id: str,
        failure_rate: float,
        seed: int
    ) -> Dict:
        """Process order with playbook-driven retries."""
        result = await process_order_simple(
            order_id=order_id,
            order_index=seed,
            failure_rate=failure_rate
        )
        
        return {
            "status": result["status"],
            "steps_completed": result["steps_completed"],
            "failed_at": None if result["status"] == "success" else "unknown"
        }


# ================================
# EXPERIMENT EXECUTION
# ================================

async def run_experiment(
    experiment_id: str,
    agent_name: Literal["baseline", "playbook_simulated", "order_agent_llm"],
    failure_rate: float,
    seed: int
) -> Dict:
    """Run single experiment with specified agent."""
    import time
    start_time = time.time()
    
    # Select agent
    if agent_name == "baseline":
        result = await BaselineAgent.process_order(
            order_id=f"exp_{experiment_id}",
            failure_rate=failure_rate,
            seed=seed
        )
    elif agent_name == "playbook_simulated":
        result = await PlaybookSimulatedAgent.process_order(
            order_id=f"exp_{experiment_id}",
            failure_rate=failure_rate,
            seed=seed
        )
    else:  # order_agent_llm
        result = await OrderAgentLLMWrapper.process_order(
            order_id=f"exp_{experiment_id}",
            failure_rate=failure_rate,
            seed=seed
        )
    
    duration_ms = (time.time() - start_time) * 1000
    
    return {
        "experiment_id": experiment_id,
        "agent": agent_name,
        "failure_rate": failure_rate,
        "seed": seed,
        "outcome": result["status"],
        "steps_completed": len(result["steps_completed"]),
        "failed_at": result.get("failed_at", ""),
        "duration_ms": round(duration_ms, 2)
    }


# ================================
# VALIDATION LOGIC
# ================================

async def run_validation() -> bool:
    """Run experiments with 3 agents and compare results."""
    print("\n" + "="*70)
    print("PHASE 5+6 INTEGRATION - 3 AGENTS COMPARISON")
    print("="*70)
    
    # Initialize Phase 6 agent
    print("\n[1/5] Initializing OrderAgentLLM (Phase 6)...")
    try:
        client = initialize_order_agent_llm()
    except Exception as e:
        print(f"❌ OrderAgentLLM initialization failed: {e}")
        return False
    
    # Configuration
    agents = ["baseline", "playbook_simulated", "order_agent_llm"]
    failure_rates = [0.0, 0.10, 0.20]
    experiments_per_agent_per_rate = 10  # 3 agents × 3 rates × 10 = 90 total
    base_seed = 2000
    
    all_results = []
    
    # Run experiments
    print("\n[2/5] Running 90 experiments (3 agents × 3 rates × 10)...")
    print("-" * 70)
    
    for agent in agents:
        print(f"\n🤖 Agent: {agent.upper()}")
        print("-" * 70)
        
        for rate in failure_rates:
            print(f"\n  {rate:.0%} chaos: Running {experiments_per_agent_per_rate} experiments...")
            
            for i in range(experiments_per_agent_per_rate):
                exp_id = f"{agent}-{rate:.2f}-{i+1:02d}"
                seed = base_seed + hash(agent) % 1000 + int(rate * 100) + i
                
                result = await run_experiment(exp_id, agent, rate, seed)
                all_results.append(result)
                
                status = "✅" if result["outcome"] == "success" else "❌"
                print(f"    {status} Exp {i+1}/{experiments_per_agent_per_rate}: {result['outcome']}")
    
    # Calculate success rates
    print("\n[3/5] Calculating success rates...")
    print("-" * 70)
    
    success_rates = {}
    for agent in agents:
        success_rates[agent] = {}
        for rate in failure_rates:
            agent_rate_results = [
                r for r in all_results 
                if r["agent"] == agent and r["failure_rate"] == rate
            ]
            successes = sum(1 for r in agent_rate_results if r["outcome"] == "success")
            success_rates[agent][rate] = successes / len(agent_rate_results)
    
    # Display comparison table
    print("\n[4/5] Comparison table...")
    print("="*70)
    print("SUCCESS RATES COMPARISON (3 AGENTS)")
    print("="*70)
    print(f"\n{'Agent':<25} | {'0% chaos':>10} | {'10% chaos':>10} | {'20% chaos':>10}")
    print("-" * 70)
    
    for agent in agents:
        rates_str = " | ".join([
            f"{success_rates[agent][rate]:>9.1%}"
            for rate in failure_rates
        ])
        print(f"{agent:<25} | {rates_str}")
    
    # Save results
    output_dir = Path("results/phase56_integration")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # CSV
    csv_path = output_dir / f"3agents_comparison_{timestamp}.csv"
    with open(csv_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=all_results[0].keys())
        writer.writeheader()
        writer.writerows(all_results)
    
    # JSON
    json_path = output_dir / f"3agents_comparison_{timestamp}.json"
    with open(json_path, "w") as f:
        json.dump({
            "success_rates": {
                agent: {str(k): v for k, v in rates.items()}
                for agent, rates in success_rates.items()
            },
            "experiments": all_results
        }, f, indent=2)
    
    # Print summary
    print("\n" + "="*70)
    print("FILES SAVED")
    print("="*70)
    print(f"  CSV:  {csv_path}")
    print(f"  JSON: {json_path}")
    
    # Analysis
    print("\n[5/5] Analysis...")
    print("="*70)
    print("KEY FINDINGS")
    print("="*70)
    
    # Compare OrderAgentLLM vs Playbook Simulated
    for rate in failure_rates:
        llm_rate = success_rates["order_agent_llm"][rate]
        sim_rate = success_rates["playbook_simulated"][rate]
        base_rate = success_rates["baseline"][rate]
        
        delta_llm_sim = llm_rate - sim_rate
        delta_llm_base = llm_rate - base_rate
        
        print(f"\n{rate:.0%} chaos:")
        print(f"  Baseline:           {base_rate:>6.1%}")
        print(f"  Playbook Simulated: {sim_rate:>6.1%}")
        print(f"  OrderAgentLLM:      {llm_rate:>6.1%}")
        print(f"  LLM vs Simulated:   {delta_llm_sim:>+6.1%}")
        print(f"  LLM vs Baseline:    {delta_llm_base:>+6.1%}")
    
    print("\n" + "="*70)
    print("✅ 3-AGENT COMPARISON COMPLETED")
    print("="*70)
    
    return True


# ================================
# MAIN ENTRY POINT
# ================================

if __name__ == "__main__":
    success = asyncio.run(run_validation())
    exit(0 if success else 1)
