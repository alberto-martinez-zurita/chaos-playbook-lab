"""
CLI Script for running Parametric A/B Test Experiments

Location: scripts/run_parametric_experiments.py

Purpose: Execute parametric experiments across multiple failure rates

Usage:
  # Basic usage (2 rates, 5 experiments each)
  poetry run python scripts/run_parametric_experiments.py

  # Custom configuration
  poetry run python scripts/run_parametric_experiments.py \
    --failure-rates 0.0 0.1 0.2 0.3 \
    --experiments-per-rate 10

  # Larger study
  poetry run python scripts/run_parametric_experiments.py \
    --failure-rates 0.0 0.1 0.2 0.3 0.5 \
    --experiments-per-rate 20

Features:
- Runs experiments across multiple failure rates
- Compares baseline vs playbook for each rate
- Generates aggregated metrics with mean ± std
- Exports raw results (CSV) and aggregated metrics (JSON)
"""

import argparse
import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from chaos_playbook_engine.experiments.parametric_runner import (
    ParametricConfig,
    ParametricABTestRunner
)


def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Run Parametric A/B Test Experiments across multiple failure rates",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Minimal test (2 rates × 2 experiments = 4 total)
  poetry run python scripts/run_parametric_experiments.py \\
    --failure-rates 0.0 0.1 \\
    --experiments-per-rate 2

  # Medium test (3 rates × 5 experiments = 15 total)
  poetry run python scripts/run_parametric_experiments.py \\
    --failure-rates 0.0 0.1 0.2 \\
    --experiments-per-rate 5

  # Full study (5 rates × 10 experiments = 50 total)
  poetry run python scripts/run_parametric_experiments.py \\
    --failure-rates 0.0 0.1 0.2 0.3 0.5 \\
    --experiments-per-rate 10
"""
    )

    parser.add_argument(
        "--failure-rates",
        type=float,
        nargs="+",
        default=[0.0, 0.1],
        help="List of failure rates to test (default: 0.0 0.1)"
    )

    parser.add_argument(
        "--experiments-per-rate",
        type=int,
        default=5,
        help="Number of experiment pairs per rate (default: 5)"
    )

    parser.add_argument(
        "--project-root",
        type=str,
        default=None,
        help="Project root directory (default: current directory)"
    )

    return parser.parse_args()


def display_configuration(config: ParametricConfig, runner: ParametricABTestRunner):
    """Display experiment configuration."""
    total_experiments = len(config.failure_rates) * config.experiments_per_rate
    total_runs = total_experiments * 2  # baseline + playbook

    print("\n" + "=" * 70)
    print("PARAMETRIC EXPERIMENT CONFIGURATION")
    print("=" * 70)
    print(f"Failure Rates: {config.failure_rates}")
    print(f"Experiments per rate: {config.experiments_per_rate}")
    print(f"Total experiments: {total_experiments} ({total_runs} runs)")
    print(f"Estimated time: ~{total_runs * 1.5:.0f} seconds")
    print(f"Output directory: {runner.run_dir}")
    print("=" * 70 + "\n")


async def run_parametric_experiments(args):
    """Execute parametric experiments."""
    
    # Create config
    print("\n[1/5] Creating configuration...")
    
    project_root = Path(args.project_root) if args.project_root else Path.cwd()
    
    config = ParametricConfig(
        failure_rates=args.failure_rates,
        experiments_per_rate=args.experiments_per_rate,
        project_root=project_root
    )
    
    # Initialize runner
    print("[2/5] Initializing Parametric Runner...")
    runner = ParametricABTestRunner(config)
    
    # Display configuration
    display_configuration(config, runner)
    
    # Run experiments
    print("[3/5] Running parametric experiments...")
    print(f"  Testing {len(config.failure_rates)} failure rates")
    print(f"  {config.experiments_per_rate} experiments per rate")
    print(f"  Total: {len(config.failure_rates) * config.experiments_per_rate * 2} runs\n")
    
    # Execute experiments
    summary = await runner.run_parametric_experiments()
    
    print(f"\n✅ Completed all experiments")
    print(f"   Total results collected: {len(runner.all_results)}\n")
    
    # Display summary
    print("[4/5] Displaying summary...")
    runner.display_summary()
    
    # Final message
    print("\n" + "=" * 70)
    print("PARAMETRIC EXPERIMENTS COMPLETED SUCCESSFULLY")
    print("=" * 70)
    print(f"\nResults saved to: {runner.run_dir}")
    print(f"\nFiles generated:")
    print(f"  - raw_results.csv: All individual experiment results")
    print(f"  - aggregated_metrics.json: Metrics aggregated by failure rate")
    print(f"\nNext steps:")
    print(f"  1. Review raw data:")
    print(f"     cat {runner.run_dir / 'raw_results.csv'}")
    print(f"  2. Analyze metrics:")
    print(f"     cat {runner.run_dir / 'aggregated_metrics.json'}")
    print(f"  3. Generate plots (if available):")
    print(f"     poetry run python scripts/plot_parametric_results.py --run-dir {runner.run_dir.name}")
    print()


def main():
    """Main entry point."""
    args = parse_arguments()
    
    # Validate arguments
    if args.experiments_per_rate < 1:
        print("ERROR: --experiments-per-rate must be at least 1")
        sys.exit(1)
    
    if len(args.failure_rates) < 1:
        print("ERROR: Must specify at least one failure rate")
        sys.exit(1)
    
    for rate in args.failure_rates:
        if not (0.0 <= rate <= 1.0):
            print(f"ERROR: Failure rate {rate} must be between 0.0 and 1.0")
            sys.exit(1)
    
    # Run experiments
    try:
        asyncio.run(run_parametric_experiments(args))
    except KeyboardInterrupt:
        print("\n\n⚠️  Experiments interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
