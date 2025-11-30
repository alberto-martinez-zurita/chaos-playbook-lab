"""
ParametricABTestRunner - Orchestrator for multi-rate experiments.
Updated with DEBUGGING for Inconsistency Calculation.
REFACTORED: Streaming/Generator pattern for GreenOps compliance.
"""

import asyncio
import csv
import json
import time
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional, AsyncGenerator
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
        
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Prepare CSV Streaming (GreenOps: Low Memory Footprint)
        csv_path = self.output_dir / "raw_results.csv"
        csv_keys = [
            "experiment_id", "agent_type", "outcome", "duration_ms", 
            "steps_completed", "failed_at", "inconsistencies_count",
            "retries", "seed", "failure_rate"
        ]

        # Accumulator for aggregation (Metrics still need full context)
        # Note: Ideally aggregation would also be streaming, but this fixes the I/O bottleneck first.
        all_results_buffer = []

        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=csv_keys)
            writer.writeheader()
            
            # Consume the generator
            async for result in self._experiment_generator():
                # 1. Enrich result (Inconsistency Calc)
                incons = self._calculate_inconsistency(result)
                result["inconsistencies_count"] = incons
                
                # 2. Write to Disk Immediately (Streaming)
                row = self._flatten_result_for_csv(result)
                writer.writerow(row)
                
                # 3. Buffer for Aggregation & UX
                all_results_buffer.append(result)
                print("." if incons == 0 else "!", end="", flush=True)

        self.logger.info(f"\n\n💾 Raw results streamed to {csv_path}")
        
        # Generate Aggregated Metrics
        self._save_aggregated_metrics(all_results_buffer)
        
        return {"total_experiments": len(all_results_buffer)}

    async def _experiment_generator(self) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Generator that yields experiment results one by one.
        Reduces cognitive complexity of the main runner and enables streaming.
        """
        for i, rate in enumerate(self.failure_rates):
            self.logger.info(f"\n[{i+1}/{len(self.failure_rates)}] Testing failure_rate={rate:.2f}")
            print(f"\n[{i+1}/{len(self.failure_rates)}] Testing failure_rate={rate:.2f}")
            
            # 1. Baseline Experiments
            self.logger.info(f"  Running {self.experiments_per_rate} Baseline experiments...")
            for j in range(self.experiments_per_rate):
                seed = self.base_seed + (i * 1000) + j
                
                result = await self.ab_runner.run_experiment(
                    agent_type="baseline",
                    failure_rate=rate,
                    seed=seed
                )
                
                # Enrich identity
                result["experiment_id"] = f"BASE-{rate}-{j}"
                result["failure_rate"] = rate
                result["seed"] = seed
                
                if j % 5 == 0: 
                    self.logger.debug(f"    Baseline run {j} completed")
                
                yield result

            # 2. Playbook Experiments
            self.logger.info(f"  Running {self.experiments_per_rate} Playbook experiments...")
            print(f"  Running {self.experiments_per_rate} Playbook experiments...")
            for j in range(self.experiments_per_rate):
                seed = self.base_seed + (i * 1000) + j 
                
                result = await self.ab_runner.run_experiment(
                    agent_type="playbook",
                    failure_rate=rate,
                    seed=seed
                )
                
                # Enrich identity
                result["experiment_id"] = f"PLAY-{rate}-{j}"
                result["failure_rate"] = rate
                result["seed"] = seed
                
                if j % 5 == 0:
                    self.logger.debug(f"    Playbook run {j} completed")
                
                yield result
            
            self.logger.info(f"   ✅ Completed batch for rate {rate}")

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

    def _flatten_result_for_csv(self, res: Dict) -> Dict:
        """Helper to flatten result dictionary for CSV writing."""
        return {
            "experiment_id": res["experiment_id"],
            "agent_type": res["agent_type"],
            "outcome": res["status"],
            "duration_ms": res["duration_ms"],
            "steps_completed": len(res["steps_completed"]),
            "failed_at": res.get("failed_at", ""),
            "inconsistencies_count": res.get("inconsistencies_count", 0),
            "retries": res.get("retries", 0),
            "seed": res["seed"],
            "failure_rate": res["failure_rate"]
        }

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