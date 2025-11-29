"""
CLI script to run parametric experiments.
Updated for Phase 5 Refactor (Correct Path Setup & Logging).
"""
import sys
import asyncio
import argparse
from pathlib import Path
from datetime import datetime
from chaos_engine.core.logging import setup_logger  # ✅ NEW
from chaos_engine.simulation.parametric import ParametricABTestRunner

def main():
    parser = argparse.ArgumentParser(description="Run parametric chaos experiments")
    
    parser.add_argument("--failure-rates", type=float, nargs="+", required=True)
    parser.add_argument("--experiments-per-rate", type=int, default=5)
    parser.add_argument("--seed", type=int, default=42, help="Base seed for reproducibility (default: 42)")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose logging to console") # ✅ NEW
    
    args = parser.parse_args()
    
# 1. PREPARAR DIRECTORIO
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    # Usar resolve() para obtener ruta absoluta
    output_dir = (Path("reports") / "parametric_experiments" / f"run_{timestamp}").resolve()
    
    # 2. INICIALIZAR LOGGING
    logger = setup_logger("Experiment_log_", verbose=args.verbose, log_dir=str(output_dir))

    logger.info("="*70)
    logger.info("PARAMETRIC EXPERIMENT CONFIGURATION")
    logger.info("="*70)
    logger.info(f"Failure Rates: {args.failure_rates}")
    logger.info(f"Experiments per rate: {args.experiments_per_rate}")
    logger.info(f"Total experiments: {len(args.failure_rates) * args.experiments_per_rate * 2} (Baseline + Playbook)")
    logger.info(f"Output directory: {output_dir}")
    logger.info("="*70 + "\n")

    print("="*70)
    print("PARAMETRIC EXPERIMENT CONFIGURATION")
    print("="*70)
    print(f"Failure Rates: {args.failure_rates}")
    print(f"Experiments per rate: {args.experiments_per_rate}")
    print(f"Total experiments: {len(args.failure_rates) * args.experiments_per_rate * 2} (Baseline + Playbook)")
    print(f"Output directory: {output_dir}")
    print("="*70 + "\n")

    runner = ParametricABTestRunner(
        failure_rates=args.failure_rates,
        experiments_per_rate=args.experiments_per_rate,
        output_dir=output_dir,
        seed=args.seed,
        logger=logger
    )
    
    # Ejecutar
    asyncio.run(runner.run_parametric_experiments())

if __name__ == "__main__":
    main()