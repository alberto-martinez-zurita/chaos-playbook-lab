"""
run_agent_comparison_NEW.py
===========================
Phase 6: A/B Testing powered by Google ADK Agent Evaluator.

Combines parametric chaos testing with ADK's formal evaluation metrics.
- Replaces manual execution with AgentEvaluator.evaluate().
- Uses dynamic patching to inject Chaos/Playbook configurations per run.
- Generates standard CSV/JSON for the existing Dashboard.

Usage:
    poetry run python cli/run_agent_comparison_NEW.py \
      --agent-a-label "Agent (Weak)" \
      --playbook-a assets/playbooks/baseline.json \
      --agent-b-label "Agent (Strong)" \
      --playbook-b assets/playbooks/training.json \
      --failure-rates 0.0 0.2 \
      --experiments-per-rate 1 \
      --seed 42
"""

import sys
import argparse
import asyncio
import csv
import json
import logging
import time
import tempfile
import os
from pathlib import Path
from collections import defaultdict
from datetime import datetime
from unittest.mock import patch

# 1. Setup Environment
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root / "src"))

from chaos_engine.core.logging import setup_logger
from chaos_engine.core.config import load_config

# ADK Imports
from google.adk.evaluation.agent_evaluator import AgentEvaluator

# Module to test
import chaos_engine.agents.order_agent as order_agent_module
from chaos_engine.core.playbook_manager import PlaybookManager
from chaos_engine.chaos.proxy import ChaosProxy

# ==============================================================================
# CONFIGURATION & CONSTANTS
# ==============================================================================

# Definimos el "Camino de Oro" EXACTO.
# El agente DEBE replicar estos argumentos letra por letra.
EXPECTED_TOOL_USE = [
    {
        "tool_name": "get_inventory", 
        "tool_input": {}
    },
    {
        "tool_name": "find_pets_by_status", 
        "tool_input": {"status": "available"} # Prompt forzará este argumento explícito
    },
    {
        "tool_name": "place_order", 
        "tool_input": {"pet_id": 12345, "quantity": 1} # Prompt forzará quantity=1
    },
    {
        "tool_name": "update_pet_status", 
        "tool_input": {
            "pet_id": 12345, 
            "status": "sold", 
            "name": "MockPet" # Coincide con lo que devuelve el MockProxy
        }
    }
]

# ==============================================================================
# HELPERS
# ==============================================================================

async def run_single_eval_case(
    run_id: str,
    playbook_path: str,
    failure_rate: float,
    seed: int,
    verbose: bool
):
    """
    Ejecuta UNA evaluación usando ADK, inyectando la configuración específica.
    """
    
    # 1. PREPARACIÓN DEL CASO DE PRUEBA (PROMPT BLINDADO)
    # 🔥 FIX: Instrucciones explícitas para eliminar ambigüedad en los argumentos
    prompt_text = (
        f"Start a pet purchase session (Run: {run_id}).\n"
        "1. Check inventory.\n"
        "2. Find pets explicitly with status='available'.\n" # Fuerza el argumento status
        "3. Buy 1 unit of pet 12345.\n"                     # Fuerza quantity=1 y ID
        "4. Update its status to 'sold' (use name='MockPet')." # Fuerza nombre correcto
    )

    case_data = [
        {
            "query": prompt_text,
            "expected_tool_use": EXPECTED_TOOL_USE,
            "reference": "{\"selected_pet_id\": 12345, \"completed\": true, \"error\": null}"
        }
    ]
    
    # Crear archivo temporal
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False, encoding='utf-8') as tmp:
        json.dump(case_data, tmp)
        tmp_path = tmp.name

    # 2. INYECCIÓN DE DEPENDENCIAS
    scoped_proxy = ChaosProxy(
        failure_rate=failure_rate, 
        seed=seed, 
        mock_mode=True, 
        verbose=verbose
    )
    
    pb_path_obj = Path(playbook_path)
    if not pb_path_obj.exists():
        pb_path_obj = project_root / playbook_path
        
    scoped_playbook = PlaybookManager(str(pb_path_obj))

    # 3. EJECUCIÓN DEL EVALUADOR
    start_time = time.time()
    outcome = "failure"
    tool_score = 0.0
    inconsistency = 0
    
    try:
        with patch.object(order_agent_module, 'chaos_proxy', scoped_proxy), \
             patch.object(order_agent_module, 'playbook', scoped_playbook), \
             patch('google.adk.evaluation.agent_evaluator.NUM_RUNS', 1):
            
            if verbose:
                print(f"   ⚡ ADK Eval: Rate={failure_rate:.2f}, PB={pb_path_obj.name}")

            result = await AgentEvaluator.evaluate(
                agent_module="chaos_engine.agents.order_agent",
                eval_dataset_file_path_or_dir=tmp_path
            )
            
            if result:
                results_list = result.eval_results if hasattr(result, 'eval_results') else result
                
                if results_list and len(results_list) > 0:
                    metrics = results_list[0].metrics if hasattr(results_list[0], 'metrics') else results_list[0]
                    
                    # Extraer scores
                    tool_score = metrics.get('tool_trajectory_avg_score') or metrics.get('tool_use_match', 0)
                    
                    # Si tool_score es 1.0, es perfecto. Si es >= 0.4, es aceptable.
                    outcome = "success" if tool_score >= 0.4 else "failure"
                    
                    # Inconsistencia: Pasos parciales correctos pero flujo incompleto
                    inconsistency = 1 if (0.0 < tool_score < 0.4) else 0

    except Exception as e:
        print(f"   ❌ Error: {e}")
    finally:
        if os.path.exists(tmp_path):
            try: os.remove(tmp_path)
            except: pass

    duration_ms = (time.time() - start_time) * 1000
    
    return {
        "experiment_id": run_id,
        "outcome": outcome,
        "duration_ms": duration_ms,
        "inconsistencies_count": inconsistency,
        "adk_score": tool_score,
        "seed": seed,
        "failure_rate": failure_rate
    }

# ... (El resto del archivo run_comparison y save_results se mantienen igual) ...
# ==============================================================================
# MAIN LOOP & REPORTING
# ==============================================================================

async def run_comparison(args) -> bool:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = (Path("reports") / "parametric_experiments" / f"run_{timestamp}").resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    
    logger = setup_logger("adk_comparison", verbose=args.verbose, log_dir=str(output_dir))
    
    logger.info("="*80)
    logger.info("🤖 ADK-POWERED AGENT COMPARISON")
    logger.info("="*80)
    
    all_results = []
    
    for rate in args.failure_rates:
        logger.info(f"\n📊 Chaos Rate: {rate:.0%}")
        
        # Agent A
        logger.info(f"  👉 Testing Agent A: {args.agent_a_label}")
        for i in range(args.experiments_per_rate):
            seed = (args.seed or 42) + i
            res = await run_single_eval_case(f"A-{rate:.2f}-{i+1:03d}", args.playbook_a, rate, seed, args.verbose)
            res["agent_type"] = "baseline"
            all_results.append(res)
            print(f"     Run {i+1}: {res['outcome'].upper()} (Score: {res['adk_score']:.2f})")

        # Agent B
        logger.info(f"  👉 Testing Agent B: {args.agent_b_label}")
        for i in range(args.experiments_per_rate):
            seed = (args.seed or 42) + i
            res = await run_single_eval_case(f"B-{rate:.2f}-{i+1:03d}", args.playbook_b, rate, seed, args.verbose)
            res["agent_type"] = "playbook"
            all_results.append(res)
            print(f"     Run {i+1}: {res['outcome'].upper()} (Score: {res['adk_score']:.2f})")

    save_results(all_results, output_dir, logger)
    return True

def save_results(results, output_dir, logger):
    csv_path = output_dir / "raw_results.csv"
    with open(csv_path, "w", newline="") as f:
        fieldnames = ["experiment_id", "agent_type", "outcome", "duration_s", "inconsistencies_count", "adk_score", "seed", "failure_rate"]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in results:
            writer.writerow({
                "experiment_id": r["experiment_id"],
                "agent_type": r["agent_type"],
                "outcome": r["outcome"],
                "duration_s": round(r["duration_ms"] / 1000, 2),
                "inconsistencies_count": r["inconsistencies_count"],
                "adk_score": r["adk_score"],
                "seed": r["seed"],
                "failure_rate": r["failure_rate"]
            })

    # Basic JSON aggregation
    json_path = output_dir / "aggregated_metrics.json"
    agg_data = {str(r["failure_rate"]): {"baseline": {}, "playbook": {}} for r in results} # Placeholder structure
    with open(json_path, "w") as f:
        json.dump(agg_data, f, indent=2)

    logger.info(f"\n✅ Results saved to: {output_dir}")

def parse_args():
    parser = argparse.ArgumentParser(description="Run comparison using ADK Evaluator")
    parser.add_argument("--agent-a-label", type=str, default="Baseline")
    parser.add_argument("--playbook-a", type=str, required=True)
    parser.add_argument("--agent-b-label", type=str, default="Playbook")
    parser.add_argument("--playbook-b", type=str, required=True)
    parser.add_argument("--failure-rates", type=float, nargs="+", required=True)
    parser.add_argument("--experiments-per-rate", type=int, default=1)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--verbose", action="store_true")
    return parser.parse_args()

if __name__ == "__main__":
    args = parse_args()
    asyncio.run(run_comparison(args))