#!/usr/bin/env python3
"""
FASE 5.3: Integrated Parametric AB Test Runner with Report Generation

Complete end-to-end script for running parametric experiments and generating
academic reports in a single command.

Workflow:
1. ParametricABTestRunner: Generate data (5.1)
2. AcademicReportGenerator: Create visualizations (5.2)
3. Report: Save results with metadata (5.3)

Usage:
    poetry run python scripts/run_parametric_ab_test.py
    poetry run python scripts/run_parametric_ab_test.py --experiments-per-rate 50
    poetry run python scripts/run_parametric_ab_test.py --failure-rates 0.0 0.1 0.3
    poetry run python scripts/run_parametric_ab_test.py --skip-visualization
"""

import argparse
import logging
import sys
from pathlib import Path
from typing import List, Optional

# Import from chaos_playbook_engine package
from chaos_playbook_engine.experiments.parametric_ab_test_runner import ParametricABTestRunner
from chaos_playbook_engine.experiments.academic_report_generator import AcademicReportGenerator


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def main():
    """Main entry point for parametric AB testing."""
    
    parser = argparse.ArgumentParser(
        description="Chaos Playbook Engine - Parametric A/B Test Runner",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Default: 5 experiments per rate, failure rates [0.1, 0.3, 0.5]
  poetry run python scripts/run_parametric_ab_test.py
  
  # Custom: 50 experiments per rate
  poetry run python scripts/run_parametric_ab_test.py --experiments-per-rate 50
  
  # Custom failure rates
  poetry run python scripts/run_parametric_ab_test.py --failure-rates 0.0 0.1 0.2 0.3
  
  # Skip visualization (data only)
  poetry run python scripts/run_parametric_ab_test.py --skip-visualization
        """
    )
    
    parser.add_argument(
        '--failure-rates',
        nargs='+',
        type=float,
        default=[0.1, 0.3, 0.5],
        help='Failure rates to test (default: 0.1 0.3 0.5)'
    )
    
    parser.add_argument(
        '--experiments-per-rate',
        type=int,
        default=5,
        help='Number of experiments per failure rate (default: 5)'
    )
    
    parser.add_argument(
        '--timeout',
        type=int,
        default=60,
        help='Timeout in seconds per experiment (default: 60)'
    )
    
    parser.add_argument(
        '--output-dir',
        type=str,
        default='results/parametric_experiments',
        help='Output directory for results (default: results/parametric_experiments)'
    )
    
    parser.add_argument(
        '--skip-visualization',
        action='store_true',
        help='Skip dashboard generation (data only)'
    )
    
    parser.add_argument(
        '--seed',
        type=int,
        default=42,
        help='Random seed for reproducibility (default: 42)'
    )
    
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Verbose output'
    )
    
    args = parser.parse_args()
    
    # Validate failure rates
    for rate in args.failure_rates:
        if not (0.0 <= rate <= 1.0):
            print(f"❌ Error: Failure rates must be between 0.0 and 1.0, got {rate}")
            sys.exit(1)
    
    # Print configuration
    if args.verbose:
        print("🚀 PHASE 5.3: PARAMETRIC AB TEST RUNNER")
        print("━" * 60)
        print("Configuration:")
        print(f"  • Failure Rates: {args.failure_rates}")
        print(f"  • Experiments per Rate: {args.experiments_per_rate}")
        print(f"  • Timeout: {args.timeout}s")
        print(f"  • Output Dir: {args.output_dir}")
        print(f"  • Random Seed: {args.seed}")
        print(f"  • Skip Visualization: {args.skip_visualization}")
        print()
    
    # STEP 1: Run parametric experiments (5.1 - Data Generation)
    print("📊 STEP 1: Parametric A/B Testing (Data Generation)")
    print("━" * 60)
    
    try:
        runner = ParametricABTestRunner(
            failure_rates=args.failure_rates,
            n_experiments=args.experiments_per_rate,
            timeout=args.timeout,
            output_dir=args.output_dir,
            seed=args.seed
        )
        
        experiment_result = runner.run_experiments(verbose=args.verbose)
        
        print(f"✅ Experiments Complete!")
        print(f"   • Run ID: {experiment_result['run_id']}")
        print(f"   • Results Dir: {experiment_result['run_dir']}")
        print(f"   • Total Experiments: {experiment_result['n_experiments']}")
        print(f"   • CSV: {experiment_result['csv_path']}")
        print(f"   • Metrics: {experiment_result['metrics_path']}")
        print()
        
    except Exception as e:
        print(f"❌ Experiment Failed: {e}")
        logger.exception("Full traceback:")
        sys.exit(1)
    
    # STEP 2: Generate academic report (5.2 - Visualization)
    if not args.skip_visualization:
        print("📈 STEP 2: Academic Report Generation (Visualization)")
        print("━" * 60)
        
        try:
            metrics_path = experiment_result['metrics_path']
            dashboard_path = Path(experiment_result['run_dir']) / 'dashboard.html'
            
            generator = AcademicReportGenerator(
                metrics_path=metrics_path,
                output_path=str(dashboard_path)
            )
            
            output = generator.generate(verbose=args.verbose)
            
            print(f"✅ Report Generated!")
            print(f"   • Dashboard: {output}")
            print()
            
        except Exception as e:
            print(f"❌ Report Generation Failed: {e}")
            logger.exception("Full traceback:")
            sys.exit(1)
    
    # STEP 3: Summary and next steps
    print("✨ PHASE 5.3 COMPLETE")
    print("━" * 60)
    print(f"📁 Results Location: {experiment_result['run_dir']}")
    print()
    print("Files Generated:")
    print(f"  ✓ raw_results.csv - Raw experimental data")
    print(f"  ✓ aggregated_metrics.json - Aggregated statistics")
    if not args.skip_visualization:
        print(f"  ✓ dashboard.html - Interactive dashboard")
    print()
    print("Next Steps:")
    if not args.skip_visualization:
        dashboard_abs = Path(dashboard_path).absolute()
        print(f"  1. Open dashboard in browser:")
        print(f"     → file:///{dashboard_abs}")
    else:
        print(f"  1. Generate dashboard later:")
        print(f"     → poetry run python scripts/generate_dashboard.py --run-dir {experiment_result['run_id']}")
    print(f"  2. Analyze results in: {experiment_result['run_dir']}")
    print()


if __name__ == "__main__":
    main()
