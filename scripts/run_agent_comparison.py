"""
run_agent_comparison.py - Agent Comparison with Phase 5 Dashboard Integration
=============================================================================

**FINAL VERSION v5 - COMPLETE FORMAT FIX**
Fixed: Both CSV and JSON formats now match Phase 5 exactly

**CSV Format**:
experiment_id,agent_type,outcome,duration_s,inconsistencies_count,strategies_used,seed,failure_rate

**JSON Format**:
{
  "0.0": {
    "failure_rate": 0.0,
    "n_experiments": 100,
    "baseline": {"n_runs": 100, ...},
    "playbook": {"n_runs": 100, ...}
  }
}

**Usage**:
    poetry run python scripts/run_agent_comparison.py \
        --agent-a playbook_simulated \
        --agent-b order_agent_llm \
        --failure-rates 0.0 0.10 0.20 \
        --experiments-per-rate 100
    
    python scripts/generate_dashboard.py --latest
"""

from pathlib import Path
import json
import csv
import asyncio
import sys
import argparse
from datetime import datetime
from typing import List, Dict, Literal, Optional
from collections import defaultdict

# Add src to path
src_path = Path(__file__).parent.parent / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

# Phase 6 agent
from chaos_playbook_engine.agents.order_agent_llm import (
    initialize_order_agent_llm,
    process_order_simple,
    PlaybookStorage
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
# AGENT IMPLEMENTATIONS
# ================================

class BaselineAgent:
    """Phase 5 baseline agent - no retries."""
    
    def __init__(self, playbook_path: Optional[str] = None):
        pass
    
    async def process_order(
        self,
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
                seed=seed + i
            )
            
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


class PlaybookSimulatedAgent:
    """Phase 5 playbook agent - hardcoded retries."""
    
    def __init__(self, playbook_path: Optional[str] = None, max_retries: int = 2):
        self.max_retries = max_retries
    
    async def process_order(
        self,
        order_id: str,
        failure_rate: float,
        seed: int
    ) -> Dict:
        """Process order WITH hardcoded retries."""
        steps = ["inventory", "payment", "shipment", "erp"]
        steps_completed = []
        
        for step_idx, step in enumerate(steps):
            success = False
            
            for attempt in range(self.max_retries + 1):
                chaos_config = ChaosConfig(
                    enabled=True,
                    failure_rate=failure_rate,
                    failure_type="timeout",
                    max_delay_seconds=2,
                    seed=seed + step_idx + attempt * 1000
                )
                
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
                
                if attempt < self.max_retries:
                    await asyncio.sleep(0.5)
            
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


class OrderAgentLLMWrapper:
    """Phase 6 OrderAgentLLM wrapper."""
    
    def __init__(self, playbook_path: str = "data/playbook_phase6.json"):
        self.playbook_path = playbook_path
        from chaos_playbook_engine.agents import order_agent_llm
        order_agent_llm.playbook_storage = PlaybookStorage(path=playbook_path)
        print(f"  OrderAgentLLM using: {playbook_path}")
    
    async def process_order(
        self,
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
# AGENT FACTORY
# ================================

def create_agent(
    agent_type: Literal["baseline", "playbook_simulated", "order_agent_llm"],
    playbook_path: Optional[str] = None
):
    """Create agent instance."""
    if agent_type == "baseline":
        return BaselineAgent()
    elif agent_type == "playbook_simulated":
        return PlaybookSimulatedAgent()
    else:  # order_agent_llm
        if playbook_path is None:
            playbook_path = "data/playbook_phase6.json"
        return OrderAgentLLMWrapper(playbook_path=playbook_path)


# ================================
# EXPERIMENT EXECUTION
# ================================

async def run_experiment(
    experiment_id: str,
    agent: any,
    agent_name: str,
    failure_rate: float,
    seed: int
) -> Dict:
    """Run single experiment."""
    import time
    start_time = time.time()
    
    result = await agent.process_order(
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
# PHASE 5 FORMAT CONVERSION
# ================================

def save_phase5_format(
    experiments: List[Dict],
    output_dir: Path,
    agent_names: Dict[str, str]
) -> None:
    """Save results in Phase 5 format matching generate_dashboard.py expectations."""
    
    # 1. Save raw_results.csv with EXACT format from Phase 5
    csv_path = output_dir / "raw_results.csv"
    with open(csv_path, "w", newline="") as f:
        fieldnames = [
            "experiment_id",
            "agent_type",
            "outcome",
            "duration_s",
            "inconsistencies_count",
            "strategies_used",
            "seed",
            "failure_rate"
        ]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        
        for exp in experiments:
            agent_type = agent_names.get(exp["agent"], exp["agent"])
            prefix = "BASE" if agent_type == "baseline" else "PLAY"
            exp_id = f"{prefix}-{exp['seed']}"
            
            writer.writerow({
                "experiment_id": exp_id,
                "agent_type": agent_type,
                "outcome": exp["outcome"],
                "duration_s": round(exp["duration_ms"] / 1000, 2),
                "inconsistencies_count": 0,
                "strategies_used": "",
                "seed": exp["seed"],
                "failure_rate": exp["failure_rate"]
            })
    
    # 2. Calculate aggregated metrics with CORRECT STRUCTURE
    # Structure: {
    #   "0.0": {
    #     "failure_rate": 0.0,
    #     "n_experiments": 100,
    #     "baseline": {"n_runs": 100, ...},
    #     "playbook": {"n_runs": 100, ...}
    #   }
    # }
    by_rate = defaultdict(lambda: {
        "failure_rate": None,
        "n_experiments": 0,
        "baseline": None,
        "playbook": None
    })
    
    # Group experiments by failure_rate
    rate_groups = defaultdict(list)
    for exp in experiments:
        rate_groups[exp["failure_rate"]].append(exp)
    
    for rate, rate_exps in rate_groups.items():
        rate_str = str(rate)
        
        # Set failure_rate and n_experiments at rate level
        by_rate[rate_str]["failure_rate"] = rate
        by_rate[rate_str]["n_experiments"] = len(rate_exps)
        
        # Group by agent within this rate
        agent_groups = defaultdict(list)
        for exp in rate_exps:
            agent_phase5 = agent_names.get(exp["agent"], exp["agent"])
            agent_groups[agent_phase5].append(exp)
        
        # Calculate metrics for each agent
        for agent_name, agent_exps in agent_groups.items():
            successes = sum(1 for e in agent_exps if e["outcome"] == "success")
            latencies = [float(e["duration_ms"]) for e in agent_exps]
            
            by_rate[rate_str][agent_name] = {
                "n_runs": len(agent_exps),  # CORRECT: "n_runs" not "total_experiments"
                "success_rate": {
                    "mean": successes / len(agent_exps),
                    "std": 0.0
                },
                "duration_s": {
                    "mean": sum(latencies) / len(latencies) / 1000,
                    "std": 0.0
                },
                "inconsistencies": {
                    "mean": 0,
                    "std": 0.0
                }
            }
    
    # 3. Save aggregated_metrics.json
    json_path = output_dir / "aggregated_metrics.json"
    phase5_json = dict(by_rate)
    
    with open(json_path, "w") as f:
        json.dump(phase5_json, f, indent=2)
    
    print(f"\n✅ Phase 5 format files created:")
    print(f"  - {csv_path}")
    print(f"  - {json_path}")
    print(f"\n📋 JSON Structure (matching Phase 5):")
    print(f"  {{")
    print(f"    \"0.0\": {{")
    print(f"      \"failure_rate\": 0.0,")
    print(f"      \"n_experiments\": 100,")
    print(f"      \"baseline\": {{\"n_runs\": 100, ...}},")
    print(f"      \"playbook\": {{\"n_runs\": 100, ...}}")
    print(f"    }}")
    print(f"  }}")


# ================================
# MAIN COMPARISON LOGIC
# ================================

async def run_comparison(args) -> bool:
    """Run agent comparison experiments."""
    print("\n" + "="*70)
    print("AGENT COMPARISON - PARAMETRIC EXPERIMENTS")
    print("="*70)
    
    print(f"\nConfiguration:")
    print(f"  Agent A: {args.agent_a}")
    if args.playbook_a:
        print(f"    Playbook: {args.playbook_a}")
    print(f"  Agent B: {args.agent_b}")
    if args.playbook_b:
        print(f"    Playbook: {args.playbook_b}")
    print(f"  Failure rates: {args.failure_rates}")
    print(f"  Experiments per rate: {args.experiments_per_rate}")
    print(f"  Total experiments: {len(args.failure_rates) * args.experiments_per_rate * 2}")
    
    print("\n[1/4] Initializing agents...")
    try:
        agent_a = create_agent(args.agent_a, args.playbook_a)
        agent_b = create_agent(args.agent_b, args.playbook_b)
    except Exception as e:
        print(f"❌ Agent initialization failed: {e}")
        return False
    
    print("\n[2/4] Running experiments...")
    print("-" * 70)
    
    all_results = []
    base_seed = 42
    
    for rate in args.failure_rates:
        print(f"\n📊 Failure rate: {rate:.0%}")
        print("-" * 70)
        
        print(f"\n  Agent A ({args.agent_a}):")
        for i in range(args.experiments_per_rate):
            seed = base_seed + i
            exp_id = f"A-{rate:.2f}-{i+1:03d}"
            
            result = await run_experiment(exp_id, agent_a, args.agent_a, rate, seed)
            all_results.append(result)
            
            if (i + 1) % 10 == 0 or (i + 1) == args.experiments_per_rate:
                successes = sum(1 for r in all_results[-10:] if r["outcome"] == "success")
                print(f"    Progress: {i+1}/{args.experiments_per_rate} ({successes}/10 recent success)")
        
        print(f"\n  Agent B ({args.agent_b}):")
        for i in range(args.experiments_per_rate):
            seed = base_seed + i
            exp_id = f"B-{rate:.2f}-{i+1:03d}"
            
            result = await run_experiment(exp_id, agent_b, args.agent_b, rate, seed)
            all_results.append(result)
            
            if (i + 1) % 10 == 0 or (i + 1) == args.experiments_per_rate:
                successes = sum(1 for r in all_results[-10:] if r["outcome"] == "success")
                print(f"    Progress: {i+1}/{args.experiments_per_rate} ({successes}/10 recent success)")
        
        base_seed += args.experiments_per_rate
    
    print("\n[3/4] Calculating success rates...")
    print("-" * 70)
    
    success_rates = {args.agent_a: {}, args.agent_b: {}}
    
    for agent_name in [args.agent_a, args.agent_b]:
        for rate in args.failure_rates:
            agent_rate_results = [
                r for r in all_results 
                if r["agent"] == agent_name and r["failure_rate"] == rate
            ]
            successes = sum(1 for r in agent_rate_results if r["outcome"] == "success")
            success_rates[agent_name][rate] = successes / len(agent_rate_results)
    
    print("\n" + "="*70)
    print("SUCCESS RATES COMPARISON")
    print("="*70)
    print(f"\n{'Failure Rate':<15} | {args.agent_a[:20]:>20} | {args.agent_b[:20]:>20} | {'Delta':>10}")
    print("-" * 70)
    
    for rate in args.failure_rates:
        rate_a = success_rates[args.agent_a][rate]
        rate_b = success_rates[args.agent_b][rate]
        delta = rate_b - rate_a
        
        print(f"{rate:>13.0%} | {rate_a:>19.1%} | {rate_b:>19.1%} | {delta:>+9.1%}")
    
    output_dir = Path("results") / "parametric_experiments" / f"run_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    print("\n[4/4] Saving results...")
    
    agent_names = {
        args.agent_a: "baseline",
        args.agent_b: "playbook"
    }
    
    save_phase5_format(all_results, output_dir, agent_names)
    
    print("\n" + "="*70)
    print("FILES SAVED")
    print("="*70)
    print(f"  Location: {output_dir}")
    print(f"  - raw_results.csv (Phase 5 format)")
    print(f"  - aggregated_metrics.json (Phase 5 format - COMPLETE STRUCTURE)")
    
    print("\n" + "="*70)
    print("✅ AGENT COMPARISON COMPLETED")
    print("="*70)
    
    print("\n📋 Next step:")
    print("  python scripts/generate_dashboard.py --latest")
    
    return True


# ================================
# CLI ARGUMENT PARSING
# ================================

def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Compare 2 agents with configurable chaos parameters"
    )
    
    parser.add_argument(
        "--agent-a",
        type=str,
        required=True,
        choices=["baseline", "playbook_simulated", "order_agent_llm"],
        help="First agent to compare"
    )
    
    parser.add_argument(
        "--agent-b",
        type=str,
        required=True,
        choices=["baseline", "playbook_simulated", "order_agent_llm"],
        help="Second agent to compare"
    )
    
    parser.add_argument(
        "--playbook-a",
        type=str,
        default=None,
        help="Playbook path for agent A (only for order_agent_llm)"
    )
    
    parser.add_argument(
        "--playbook-b",
        type=str,
        default=None,
        help="Playbook path for agent B (only for order_agent_llm)"
    )
    
    parser.add_argument(
        "--failure-rates",
        type=float,
        nargs="+",
        required=True,
        help="List of failure rates to test (e.g., 0.0 0.10 0.20)"
    )
    
    parser.add_argument(
        "--experiments-per-rate",
        type=int,
        default=100,
        help="Number of experiments per failure rate (default: 100)"
    )
    
    return parser.parse_args()


# ================================
# MAIN ENTRY POINT
# ================================

if __name__ == "__main__":
    args = parse_args()
    success = asyncio.run(run_comparison(args))
    exit(0 if success else 1)
