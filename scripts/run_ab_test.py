"""
CLI Script for running A/B Tests

Location: scripts/run_ab_test.py

Usage:
    # Basic usage
    poetry run python scripts/run_ab_test.py --runs 100

    # Advanced usage
    poetry run python scripts/run_ab_test.py \
        --runs 50 \
        --failure-rate 0.4 \
        --failure-type timeout \
        --output results/my_test \
        --verbose

Features:
- Executes ABTestRunner batch experiments
- Generates metrics comparison (baseline vs playbook)
- Exports results to CSV and JSON
- Displays formatted summary in terminal
- Optional verbose mode for chaos debugging

"""

import argparse
import asyncio
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from experiments.ab_test_runner import ABTestRunner
from experiments.aggregate_metrics import MetricsAggregator
from chaos_playbook_engine.config.chaos_config import ChaosConfig


def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Run A/B Testing experiments (Baseline vs Playbook agents)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run 100 experiments (50 baseline + 50 playbook)
  poetry run python scripts/run_ab_test.py --runs 100

  # Custom chaos config
  poetry run python scripts/run_ab_test.py \
      --runs 50 \
      --failure-rate 0.4 \
      --failure-type service_unavailable

  # Save to custom directory
  poetry run python scripts/run_ab_test.py --runs 20 --output results/my_experiment
"""
    )

    parser.add_argument(
        "--runs",
        type=int,
        default=10,
        help="Number of experiment pairs to run (default: 10)"
    )

    parser.add_argument(
        "--failure-rate",
        type=float,
        default=0.3,
        help="Chaos failure rate (0.0 to 1.0, default: 0.3)"
    )

    parser.add_argument(
        "--failure-type",
        type=str,
        default="timeout",
        choices=["timeout", "service_unavailable", "rate_limit_exceeded", "invalid_request", "network_error"],
        help="Type of failure to inject (default: timeout)"
    )

    parser.add_argument(
        "--max-delay",
        type=int,
        default=2,  # V3: 3 → 2s
        help="Maximum delay for timeout failures in seconds (default: 2)"
    )

    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Output directory (default: results/test_{timestamp})"
    )

    # ✅ VERBOSE FLAG AÑADIDO
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose chaos logging for debugging (default: False)"
    )

    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed for reproducibility (default: 42)"
    )

    return parser.parse_args()


def create_output_directory(custom_path: Optional[str] = None) -> Path:
    """Create output directory for test results."""
    if custom_path:
        output_dir = Path(custom_path)
    else:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_dir = Path(f"results/test_{timestamp}")

    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir


def display_configuration(args, output_dir: Path):
    """Display test configuration."""
    print("\n" + "="*70)
    print("A/B TEST CONFIGURATION")
    print("="*70)
    print(f"Experiments: {args.runs} pairs ({args.runs} baseline + {args.runs} playbook)")
    print(f"Failure Rate: {args.failure_rate * 100:.1f}%")
    print(f"Failure Type: {args.failure_type}")
    print(f"Max Delay: {args.max_delay}s")
    print(f"Random Seed: {args.seed}")
    print(f"Verbose Mode: {args.verbose}")  # ✅ AÑADIDO
    print(f"Output Dir: {output_dir}")
    print("="*70 + "\n")


async def run_experiments(args):
    """Execute A/B test experiments."""
    # Create output directory
    output_dir = create_output_directory(args.output)

    # Display configuration
    display_configuration(args, output_dir)

    # Initialize runner
    print("[1/4] Initializing AB Test Runner...")
    runner = ABTestRunner()

    # Run experiments
    print(f"[2/4] Running {args.runs} experiment pairs...")
    print(f"     This will execute {args.runs * 2} total experiments")
    print(f"     (Estimated time: ~{args.runs * 3} seconds)\n")

    # ✅ PRESERVADO: Pasar parámetros individuales + verbose añadido
    results = await runner.run_batch_experiments(
        n=args.runs,
        failure_rate=args.failure_rate,
        failure_type=args.failure_type,
        max_delay_seconds=args.max_delay,
        verbose=args.verbose  # ✅ NUEVO: Pasar verbose flag
    )

    print(f"\n✅ Completed {len(results)} experiments\n")

    # Export raw results to CSV
    print("[3/4] Exporting results...")
    csv_path = output_dir / "raw_results.csv"
    runner.export_results_csv(results, str(csv_path))
    print(f"✅ Exported {len(results)} results to {csv_path}")
    print(f"     ✅ CSV exported to {csv_path}")

    # Calculate metrics
    print("[4/4] Calculating aggregate metrics...")
    aggregator = MetricsAggregator()

    # Separate baseline and playbook results
    baseline_results = [r for r in results if r.agent_type == "baseline"]
    playbook_results = [r for r in results if r.agent_type == "playbook"]

    # Generate comparison
    comparison = aggregator.compare_baseline_vs_playbook(baseline_results, playbook_results)

    # Export metrics JSON
    json_path = output_dir / "metrics_summary.json"
    aggregator.export_summary_json(comparison, str(json_path))
    print(f"     ✅ Metrics JSON exported to {json_path}\n")

    # Display summary
    print("="*70)
    print("RESULTS SUMMARY")
    print("="*70)
    aggregator.print_summary(comparison)

    # Final message
    print("\n" + "="*70)
    print("TEST COMPLETED SUCCESSFULLY")
    print("="*70)
    print(f"\nResults saved to: {output_dir}")
    print(f"\nNext steps:")
    print(f"  1. Review metrics: cat {json_path}")
    print(f"  2. Generate report: poetry run python scripts/generate_report.py --test-id {output_dir.name}")
    print()


def main():
    """Main entry point."""
    args = parse_arguments()

    # Validate arguments
    if args.runs < 1:
        print("ERROR: --runs must be at least 1")
        sys.exit(1)

    if not (0.0 <= args.failure_rate <= 1.0):
        print("ERROR: --failure-rate must be between 0.0 and 1.0")
        sys.exit(1)

    # Run experiments
    try:
        asyncio.run(run_experiments(args))
    except KeyboardInterrupt:
        print("\n\n⚠️  Test interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
