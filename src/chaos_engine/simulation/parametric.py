"""
ParametricABTestRunner - Orchestrator for multi-rate experiments.
Updated with DEBUGGING for Inconsistency Calculation.
"""

import asyncio
import csv
import json
import time
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
from collections import defaultdict
from datetime import datetime

try:
    from chaos_engine.simulation.runner import ABTestRunner
except ImportError:
    import sys
    sys.path.append(str(Path(__file__).parent.parent))
    from chaos_engine.simulation.runner import ABTestRunner

class ParametricABTestRunner:
    def __init__(
        self, 
        failure_rates: List[float], 
        experiments_per_rate: int, 
        output_dir: Path,
        seed: int = 42,
        logger: Optional[logging.Logger] = None
    ):
        self.failure_rates = failure_rates
        self.experiments_per_rate = experiments_per_rate
        self.output_dir = output_dir
        self.base_seed = seed
        self.ab_runner = ABTestRunner()
        self.logger = logger or logging.getLogger(__name__)

    async def run_parametric_experiments(self) -> Dict[str, Any]:
        self.logger.info(f"\n🚀 Starting parametric experiments...")
        print(f"\n🚀 Starting parametric experiments...")
        print(f"   Failure rates: {self.failure_rates}")
        print(f"   Experiments per rate: {self.experiments_per_rate}")
        print(f"   Total: {len(self.failure_rates) * self.experiments_per_rate * 2} runs")
        
        all_results = []
        self.output_dir.mkdir(parents=True, exist_ok=True)

        for i, rate in enumerate(self.failure_rates):
            self.logger.info(f"\n[{i+1}/{len(self.failure_rates)}] Testing failure_rate={rate:.2f}")
            print(f"\n[{i+1}/{len(self.failure_rates)}] Testing failure_rate={rate:.2f}")
            # --- BUCLE BATCH MANUAL ---
            
            # 1. Baseline Experiments
            self.logger.info(f"  Running {self.experiments_per_rate} Baseline experiments...")
            for j in range(self.experiments_per_rate):
                seed = base_seed + (i * 1000) + j
                
                result = await self.ab_runner.run_experiment(
                    agent_type="baseline",
                    failure_rate=rate,
                    seed=seed
                )
                
                result["experiment_id"] = f"BASE-{rate}-{j}"
                result["failure_rate"] = rate
                result["seed"] = seed
                
                # ✅ CALCULAR INCONSISTENCIA AL VUELO
                incons = self._calculate_inconsistency(result)
                result["inconsistencies_count"] = incons
                
                all_results.append(result)
                print("." if incons == 0 else ".", end="", flush=True) # ! significa inconsistencia detectada
                if j % 5 == 0: 
                    self.logger.debug(f"    Baseline run {j} completed")

            # 2. Playbook Experiments
            self.logger.info(f"  Running {self.experiments_per_rate} Playbook experiments...")
            print(f"  Running {self.experiments_per_rate} Playbook experiments...")
            for j in range(self.experiments_per_rate):
                seed = base_seed + (i * 1000) + j 
                
                result = await self.ab_runner.run_experiment(
                    agent_type="playbook",
                    failure_rate=rate,
                    seed=seed
                )
                
                result["experiment_id"] = f"PLAY-{rate}-{j}"
                result["failure_rate"] = rate
                result["seed"] = seed
                
                # ✅ CALCULAR INCONSISTENCIA
                incons = self._calculate_inconsistency(result)
                result["inconsistencies_count"] = incons
                
                all_results.append(result)
                print(".", end="", flush=True)
                if j % 5 == 0:
                    self.logger.debug(f"    Playbook run {j} completed")
            
            self.logger.info(f"   ✅ Completed batch for rate {rate}")
            print(f"   ✅ Completed {self.experiments_per_rate*2} runs")

        self._save_raw_results(all_results)
        self._save_aggregated_metrics(all_results)
        return {"total_experiments": len(all_results)}

    def _calculate_inconsistency(self, result: Dict) -> int:
        """
        Calcula si hubo inconsistencia de datos.
        Regla: Si falló en ERP o Shipping, es inconsistente (se cobró pero no se entregó).
        """
        if result["status"] == "success":
            return 0
            
        failed_at = result.get("failed_at")
        
        # Debug visual si falla la detección
        if not failed_at and result["status"] == "failure":
            self.logger.warning(f"⚠️ Result marked failure but failed_at is empty: {result}")

        # Lógica de negocio: 
        # Inventory/Payment fail -> Safe (0)
        # ERP/Shipping fail -> Unsafe (1)
        if failed_at in ["erp", "shipping"]:
            return 1
            
        return 0

    def _save_raw_results(self, results: List[Dict]):
        csv_path = self.output_dir / "raw_results.csv"
        keys = [
            "experiment_id", "agent_type", "outcome", "duration_ms", 
            "steps_completed", "failed_at", "inconsistencies_count", # ✅ Key correcta
            "retries", "seed", "failure_rate"
        ]
        
        with open(csv_path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=keys)
            writer.writeheader()
            for res in results:
                row = {
                    "experiment_id": res["experiment_id"],
                    "agent_type": res["agent_type"],
                    "outcome": res["status"],
                    "duration_ms": res["duration_ms"],
                    "steps_completed": len(res["steps_completed"]),
                    "failed_at": res.get("failed_at", ""),
                    "inconsistencies_count": res.get("inconsistencies_count", 0), # ✅ Usar el calculado
                    "retries": res.get("retries", 0),
                    "seed": res["seed"],
                    "failure_rate": res["failure_rate"]
                }
                writer.writerow(row)
        self.logger.info(f"\n💾 Saved raw results to {csv_path}")

    def _save_aggregated_metrics(self, results: List[Dict]):
        metrics = {}
        by_rate = defaultdict(list)
        for r in results: by_rate[r["failure_rate"]].append(r)
            
        for rate, group in by_rate.items():
            rate_key = str(rate)
            baseline_runs = [r for r in group if r["agent_type"] == "baseline"]
            playbook_runs = [r for r in group if r["agent_type"] == "playbook"]
            
            def calc_stats(runs):
                if not runs: return {}
                successes = sum(1 for r in runs if r["status"] == "success")
                latencies = [r["duration_ms"] for r in runs]
                # ✅ Usar el valor pre-calculado
                inconsistencies = [r.get("inconsistencies_count", 0) for r in runs]
                
                mean_incons = sum(inconsistencies) / len(runs) if runs else 0.0
                
                return {
                    "n_runs": len(runs),
                    "success_rate": {"mean": successes / len(runs), "std": 0.0},
                    "duration_s": {"mean": (sum(latencies)/len(latencies))/1000 if latencies else 0, "std": 0.0},
                    "inconsistencies": {"mean": mean_incons, "std": 0.0}
                }

            metrics[rate_key] = {
                "failure_rate": rate,
                "n_experiments": len(group) // 2,
                "baseline": calc_stats(baseline_runs),
                "playbook": calc_stats(playbook_runs)
            }
            
        json_path = self.output_dir / "aggregated_metrics.json"
        with open(json_path, "w") as f:
            json.dump(metrics, f, indent=2)
        self.logger.info(f"💾 Saved aggregated metrics to {json_path}")