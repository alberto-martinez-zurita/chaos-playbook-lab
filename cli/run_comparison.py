"""
run_agent_comparison.py - Agent Comparison with Phase 5 Dashboard Integration
=============================================================================
FINAL VERSION v5.5 - Fresh Agent Instantiation per Experiment (Fixes State Pollution)
"""

import sys
import asyncio
import argparse
import asyncio
import json
import csv
import time
from pathlib import Path
from typing import List, Dict, Literal, Optional
from collections import defaultdict
from datetime import datetime

from chaos_engine.core.logging import setup_logger
from chaos_engine.agents.petstore import PetstoreAgent
from chaos_engine.chaos.config import ChaosConfig
from chaos_engine.core.config import load_config

# ================================
# AGENT FACTORY
# ================================

def create_petstore_agent(playbook_path: str, verbose: bool) -> PetstoreAgent:
    """Instancia un PetstoreAgent con un playbook específico."""
    return PetstoreAgent(playbook_path=playbook_path, mock_mode=True, verbose=verbose)

# ================================
# EXPERIMENT EXECUTION
# ================================

async def run_experiment_safe(
    experiment_id: str,
    playbook_path: str,  # ✅ CHANGE: Pass playbook path instead of agent instance
    agent_label: str,
    failure_rate: float,
    seed: int,
    verbose: bool,
    logger
) -> Dict:
    """Run single LLM experiment with FRESH agent instance."""
    import time
    start_time = time.time()
    
    try:
        # ✅ CRITICAL FIX: Create FRESH agent for every single experiment
        # This eliminates any state pollution between runs (A vs B, or Exp 1 vs Exp 2)
        agent = create_petstore_agent(playbook_path, verbose)
        
        result = await agent.process_order(
            order_id=f"exp_{experiment_id}",
            failure_rate=failure_rate,
            seed=seed
        )
        
        outcome = result["status"]
        steps = len(result["steps_completed"])
        failed_at = result.get("failed_at", "")
        
        logger.debug(f"  Exp {experiment_id}: Outcome={outcome}, Steps={steps}, Time={result['duration_ms']:.0f}ms")
        
    except Exception as e:
        logger.error(f"  🔥 CRASH {experiment_id}: {str(e)[:100]}...")
        outcome = "failure"
        steps = 0
        failed_at = "runner_crash"
        
        if "429" in str(e) or "quota" in str(e).lower():
            logger.warning("  ⏳ Quota exceeded. Cooling down for 60s...")
            await asyncio.sleep(60)

    duration_ms = (time.time() - start_time) * 1000
    
    return {
        "experiment_id": experiment_id,
        "agent": agent_label,
        "failure_rate": failure_rate,
        "seed": seed,
        "outcome": outcome,
        "steps_completed": steps,
        "failed_at": failed_at,
        "duration_ms": round(duration_ms, 2)
    }

# ================================
# DATA SAVING
# ================================

def calculate_inconsistency(exp: Dict) -> int:
    if exp["outcome"] == "success": return 0
    steps = exp.get("steps_completed", 0)
    if steps == 3: return 1
    return 0

def save_phase5_format(experiments: List[Dict], output_dir: Path, agent_labels: Dict[str, str], logger) -> None:
    csv_path = output_dir / "raw_results.csv"
    with open(csv_path, "w", newline="") as f:
        fieldnames = ["experiment_id", "agent_type", "outcome", "duration_s", "inconsistencies_count", "strategies_used", "seed", "failure_rate"]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for exp in experiments:
            if exp["experiment_id"].startswith("A-"): atype = "baseline"
            elif exp["experiment_id"].startswith("B-"): atype = "playbook"
            else: atype = "unknown"
            
            writer.writerow({
                "experiment_id": f"{atype.upper()}-{exp['seed']}",
                "agent_type": atype,
                "outcome": exp["outcome"],
                "duration_s": round(exp["duration_ms"] / 1000, 2),
                "inconsistencies_count": calculate_inconsistency(exp),
                "strategies_used": "",
                "seed": exp["seed"],
                "failure_rate": exp["failure_rate"]
            })
            
    by_rate = defaultdict(lambda: {"failure_rate": None, "n_experiments": 0, "baseline": None, "playbook": None})
    rate_groups = defaultdict(list)
    for exp in experiments: rate_groups[exp["failure_rate"]].append(exp)
    
    for rate, rate_exps in rate_groups.items():
        rate_str = str(rate)
        by_rate[rate_str]["failure_rate"] = rate
        by_rate[rate_str]["n_experiments"] = len(rate_exps) // 2
        
        exps_a = [e for e in rate_exps if e["experiment_id"].startswith("A-")]
        exps_b = [e for e in rate_exps if e["experiment_id"].startswith("B-")]
        
        groups = {"baseline": exps_a, "playbook": exps_b}
        for key, exps in groups.items():
            if not exps:
                by_rate[rate_str][key] = {"n_runs": 0, "success_rate": {"mean": 0.0, "std": 0.0}, "duration_s": {"mean": 0.0, "std": 0.0}, "inconsistencies": {"mean": 0.0, "std": 0.0}}
                continue
            successes = sum(1 for e in exps if e["outcome"] == "success")
            latencies = [e["duration_ms"] for e in exps]
            inconsistencies = [calculate_inconsistency(e) for e in exps]
            avg_dur = sum(latencies)/len(latencies)/1000 if latencies else 0
            avg_inc = sum(inconsistencies)/len(inconsistencies) if inconsistencies else 0
            by_rate[rate_str][key] = {"n_runs": len(exps), "success_rate": {"mean": successes/len(exps), "std": 0.0}, "duration_s": {"mean": avg_dur, "std": 0.0}, "inconsistencies": {"mean": avg_inc, "std": 0.0}}
            
    json_path = output_dir / "aggregated_metrics.json"
    with open(json_path, "w") as f: json.dump(dict(by_rate), f, indent=2)
    logger.info(f"✅ Results saved to {output_dir}")

# ================================
# MAIN LOGIC
# ================================

async def run_comparison(args) -> bool:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = (Path("reports") / "parametric_experiments" / f"run_{timestamp}").resolve()
    logger = setup_logger("agent_comparison", verbose=args.verbose, log_dir=str(output_dir))
    
    logger.info("="*70)
    logger.info("🤖 PETSTORE AGENT COMPARISON (Phase 6 - Fresh Instances)")
    logger.info("="*70)
    
    config = load_config()
    base_seed = args.seed if args.seed is not None else config.get('experiment', {}).get('default_seed', 42)
    
    all_results = []
    SAFE_DELAY_SECONDS = 10
    
    for rate in args.failure_rates:
        logger.info(f"\n📊 Chaos Level: {rate:.0%}")
        
        # --- RUN AGENT A ---
        logger.info(f"  👉 Agent A ({args.agent_a_label})...")
        for i in range(args.experiments_per_rate):
            seed = base_seed + i
            # ✅ Change: Pass playbook path string, not instance
            res = await run_experiment_safe(f"A-{rate:.2f}-{i+1:03d}", args.playbook_a, args.agent_a_label, rate, seed, args.verbose, logger)
            all_results.append(res)
            if args.verbose: print(f"    Run {i+1}: {'✅' if res['outcome']=='success' else '❌'}")
            if i < args.experiments_per_rate - 1: await asyncio.sleep(SAFE_DELAY_SECONDS)
            
        await asyncio.sleep(SAFE_DELAY_SECONDS)

        # --- RUN AGENT B ---
        logger.info(f"  👉 Agent B ({args.agent_b_label})...")
        for i in range(args.experiments_per_rate):
            seed = base_seed + i
            # ✅ Change: Pass playbook path string, not instance
            res = await run_experiment_safe(f"B-{rate:.2f}-{i+1:03d}", args.playbook_b, args.agent_b_label, rate, seed, args.verbose, logger)
            all_results.append(res)
            if args.verbose: print(f"    Run {i+1}: {'✅' if res['outcome']=='success' else '❌'}")
            if i < args.experiments_per_rate - 1: await asyncio.sleep(SAFE_DELAY_SECONDS)
            
        base_seed += args.experiments_per_rate
        await asyncio.sleep(SAFE_DELAY_SECONDS)
    
    logger.info("\n[4/4] Saving results...")
    output_dir.mkdir(parents=True, exist_ok=True)
    labels_map = {"A": "baseline", "B": "playbook"}
    save_phase5_format(all_results, output_dir, labels_map, logger)
    
    return True

def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--agent-a-label", type=str, default="Weak Agent")
    parser.add_argument("--playbook-a", type=str, required=True)
    parser.add_argument("--agent-b-label", type=str, default="Strong Agent")
    parser.add_argument("--playbook-b", type=str, required=True)
    parser.add_argument("--failure-rates", type=float, nargs="+", required=True)
    parser.add_argument("--experiments-per-rate", type=int, default=5)
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument("--verbose", action="store_true")
    return parser.parse_args()

if __name__ == "__main__":
    args = parse_args()
    asyncio.run(run_comparison(args))