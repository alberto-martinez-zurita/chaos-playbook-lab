"""
Plotting Script for Parametric Experiment Results - PHASE 5.2.1

Location: scripts/generate_parametric_plots.py

Purpose: Generate publication-quality plots from parametric experiment results

Usage:
    # Plot from specific run directory
    poetry run python scripts/generate_parametric_plots.py --run-dir run_20251123_214412
    
    # Plot from latest run
    poetry run python scripts/generate_parametric_plots.py --latest
    
    # Custom output directory
    poetry run python scripts/generate_parametric_plots.py --run-dir run_20251123_214412 --output-dir custom_plots

Features:
- Success rate vs failure rate comparison
- Duration vs failure rate with error bars
- Inconsistencies analysis
- Side-by-side agent comparison
- Export as PNG (high-resolution)
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, List, Tuple

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import seaborn as sns
import numpy as np

# Configure plotting style
sns.set_style("whitegrid")
sns.set_context("paper", font_scale=1.3)
plt.rcParams['figure.figsize'] = (12, 8)
plt.rcParams['font.family'] = 'sans-serif'
plt.rcParams['axes.labelsize'] = 12
plt.rcParams['axes.titlesize'] = 14
plt.rcParams['xtick.labelsize'] = 10
plt.rcParams['ytick.labelsize'] = 10
plt.rcParams['legend.fontsize'] = 11


def load_metrics(json_path: Path) -> Dict:
    """Load aggregated metrics from JSON file."""
    with open(json_path, 'r') as f:
        return json.load(f)


def extract_data(metrics: Dict) -> Tuple[List, List, List, List, List, List]:
    """Extract plotting data from metrics dictionary.
    
    Returns:
        failure_rates, baseline_success, playbook_success,
        baseline_duration, playbook_duration,
        baseline_inconsistencies, playbook_inconsistencies
    """
    failure_rates = []
    baseline_success = []
    playbook_success = []
    baseline_duration = []
    baseline_duration_std = []
    playbook_duration = []
    playbook_duration_std = []
    baseline_inconsistencies = []
    playbook_inconsistencies = []
    
    for rate_str in sorted(metrics.keys(), key=float):
        data = metrics[rate_str]
        failure_rates.append(data['failure_rate'])
        
        baseline_success.append(data['baseline']['success_rate']['mean'])
        playbook_success.append(data['playbook']['success_rate']['mean'])
        
        baseline_duration.append(data['baseline']['duration_s']['mean'])
        baseline_duration_std.append(data['baseline']['duration_s']['std'])
        playbook_duration.append(data['playbook']['duration_s']['mean'])
        playbook_duration_std.append(data['playbook']['duration_s']['std'])
        
        baseline_inconsistencies.append(data['baseline']['inconsistencies']['mean'])
        playbook_inconsistencies.append(data['playbook']['inconsistencies']['mean'])
    
    return (
        failure_rates,
        baseline_success,
        playbook_success,
        baseline_duration,
        baseline_duration_std,
        playbook_duration,
        playbook_duration_std,
        baseline_inconsistencies,
        playbook_inconsistencies
    )


def plot_success_rate(failure_rates: List, baseline: List, playbook: List, output_dir: Path):
    """Plot success rate comparison."""
    fig, ax = plt.subplots(figsize=(10, 6))
    
    # Convert to percentages
    failure_rates_pct = [r * 100 for r in failure_rates]
    baseline_pct = [s * 100 for s in baseline]
    playbook_pct = [s * 100 for s in playbook]
    
    # Plot lines with markers
    ax.plot(failure_rates_pct, baseline_pct, 
            marker='o', linewidth=2, markersize=8, 
            label='Baseline Agent', color='#FF6B6B', alpha=0.8)
    ax.plot(failure_rates_pct, playbook_pct, 
            marker='s', linewidth=2, markersize=8, 
            label='Playbook Agent', color='#4ECDC4', alpha=0.8)
    
    # Styling
    ax.set_xlabel('Failure Rate (%)', fontweight='bold')
    ax.set_ylabel('Success Rate (%)', fontweight='bold')
    ax.set_title('Success Rate vs Failure Rate: Baseline vs Playbook', 
                 fontweight='bold', pad=20)
    ax.legend(loc='best', frameon=True, shadow=True)
    ax.grid(True, alpha=0.3)
    ax.set_ylim([0, 105])
    
    # Add horizontal reference line at 100%
    ax.axhline(y=100, color='gray', linestyle='--', alpha=0.5, linewidth=1)
    
    plt.tight_layout()
    plt.savefig(output_dir / 'success_rate_comparison.png', dpi=300, bbox_inches='tight')
    plt.close()
    
    print(f"  ✅ Generated: success_rate_comparison.png")


def plot_duration(failure_rates: List, 
                  baseline: List, baseline_std: List,
                  playbook: List, playbook_std: List,
                  output_dir: Path):
    """Plot duration comparison with error bars."""
    fig, ax = plt.subplots(figsize=(10, 6))
    
    failure_rates_pct = [r * 100 for r in failure_rates]
    
    # Plot with error bars
    ax.errorbar(failure_rates_pct, baseline, yerr=baseline_std,
                marker='o', linewidth=2, markersize=8, capsize=5, capthick=2,
                label='Baseline Agent', color='#FF6B6B', alpha=0.8)
    ax.errorbar(failure_rates_pct, playbook, yerr=playbook_std,
                marker='s', linewidth=2, markersize=8, capsize=5, capthick=2,
                label='Playbook Agent', color='#4ECDC4', alpha=0.8)
    
    # Styling
    ax.set_xlabel('Failure Rate (%)', fontweight='bold')
    ax.set_ylabel('Average Duration (seconds)', fontweight='bold')
    ax.set_title('Execution Duration vs Failure Rate (with std dev)', 
                 fontweight='bold', pad=20)
    ax.legend(loc='best', frameon=True, shadow=True)
    ax.grid(True, alpha=0.3)
    
    plt.tight_layout()
    plt.savefig(output_dir / 'duration_comparison.png', dpi=300, bbox_inches='tight')
    plt.close()
    
    print(f"  ✅ Generated: duration_comparison.png")


def plot_inconsistencies(failure_rates: List, baseline: List, playbook: List, 
                         output_dir: Path):
    """Plot inconsistencies comparison."""
    fig, ax = plt.subplots(figsize=(10, 6))
    
    failure_rates_pct = [r * 100 for r in failure_rates]
    
    # Plot lines with markers
    ax.plot(failure_rates_pct, baseline, 
            marker='o', linewidth=2, markersize=8, 
            label='Baseline Agent', color='#FF6B6B', alpha=0.8)
    ax.plot(failure_rates_pct, playbook, 
            marker='s', linewidth=2, markersize=8, 
            label='Playbook Agent', color='#4ECDC4', alpha=0.8)
    
    # Styling
    ax.set_xlabel('Failure Rate (%)', fontweight='bold')
    ax.set_ylabel('Average Inconsistencies Count', fontweight='bold')
    ax.set_title('Data Inconsistencies vs Failure Rate', 
                 fontweight='bold', pad=20)
    ax.legend(loc='best', frameon=True, shadow=True)
    ax.grid(True, alpha=0.3)
    
    # Add horizontal reference line at 0
    ax.axhline(y=0, color='gray', linestyle='--', alpha=0.5, linewidth=1)
    
    plt.tight_layout()
    plt.savefig(output_dir / 'inconsistencies_comparison.png', dpi=300, bbox_inches='tight')
    plt.close()
    
    print(f"  ✅ Generated: inconsistencies_comparison.png")


def plot_agent_comparison(failure_rates: List,
                          baseline_success: List, playbook_success: List,
                          output_dir: Path):
    """Plot side-by-side agent comparison."""
    fig, ax = plt.subplots(figsize=(12, 6))
    
    failure_rates_pct = [r * 100 for r in failure_rates]
    baseline_success_pct = [s * 100 for s in baseline_success]
    playbook_success_pct = [s * 100 for s in playbook_success]
    
    x = np.arange(len(failure_rates))
    width = 0.35
    
    # Create bars
    bars1 = ax.bar(x - width/2, baseline_success_pct, width, 
                   label='Baseline Agent', color='#FF6B6B', alpha=0.8)
    bars2 = ax.bar(x + width/2, playbook_success_pct, width, 
                   label='Playbook Agent', color='#4ECDC4', alpha=0.8)
    
    # Add value labels on bars
    for bars in [bars1, bars2]:
        for bar in bars:
            height = bar.get_height()
            ax.text(bar.get_x() + bar.get_width()/2., height,
                   f'{height:.0f}%',
                   ha='center', va='bottom', fontsize=10, fontweight='bold')
    
    # Styling
    ax.set_xlabel('Failure Rate (%)', fontweight='bold')
    ax.set_ylabel('Success Rate (%)', fontweight='bold')
    ax.set_title('Agent Success Rate Comparison Across Failure Rates', 
                 fontweight='bold', pad=20)
    ax.set_xticks(x)
    ax.set_xticklabels([f'{r:.0f}%' for r in failure_rates_pct])
    ax.legend(loc='best', frameon=True, shadow=True)
    ax.grid(True, alpha=0.3, axis='y')
    ax.set_ylim([0, 110])
    
    # Add horizontal reference line at 100%
    ax.axhline(y=100, color='gray', linestyle='--', alpha=0.5, linewidth=1)
    
    plt.tight_layout()
    plt.savefig(output_dir / 'agent_comparison_bars.png', dpi=300, bbox_inches='tight')
    plt.close()
    
    print(f"  ✅ Generated: agent_comparison_bars.png")


def generate_all_plots(metrics_path: Path, output_dir: Path):
    """Generate all plots from metrics file."""
    print(f"\n📊 Generating plots from: {metrics_path}")
    print(f"   Output directory: {output_dir}\n")
    
    # Create output directory
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Load metrics
    metrics = load_metrics(metrics_path)
    
    # Extract data
    (failure_rates, baseline_success, playbook_success,
     baseline_duration, baseline_duration_std,
     playbook_duration, playbook_duration_std,
     baseline_inconsistencies, playbook_inconsistencies) = extract_data(metrics)
    
    # Generate plots
    print("Generating plots...")
    plot_success_rate(failure_rates, baseline_success, playbook_success, output_dir)
    plot_duration(failure_rates, 
                  baseline_duration, baseline_duration_std,
                  playbook_duration, playbook_duration_std,
                  output_dir)
    plot_inconsistencies(failure_rates, 
                        baseline_inconsistencies, playbook_inconsistencies, 
                        output_dir)
    plot_agent_comparison(failure_rates, 
                         baseline_success, playbook_success, 
                         output_dir)
    
    print(f"\n✅ All plots generated successfully!")
    print(f"   Location: {output_dir}")


def find_latest_run(results_dir: Path) -> Path:
    """Find the most recent run directory."""
    run_dirs = sorted([d for d in results_dir.iterdir() if d.is_dir() and d.name.startswith('run_')])
    if not run_dirs:
        raise FileNotFoundError("No run directories found")
    return run_dirs[-1]


def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Generate plots from parametric experiment results",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument(
        '--run-dir',
        type=str,
        help='Specific run directory name (e.g., run_20251123_214412)'
    )
    
    parser.add_argument(
        '--latest',
        action='store_true',
        help='Use the latest run directory'
    )
    
    parser.add_argument(
        '--output-dir',
        type=str,
        default=None,
        help='Custom output directory for plots (default: <run_dir>/plots)'
    )
    
    return parser.parse_args()


def main():
    """Main entry point."""
    args = parse_arguments()
    
    # Determine run directory
    results_base = Path.cwd() / "reports" / "parametric_experiments"
    
    if args.latest:
        run_dir = find_latest_run(results_base)
        print(f"Using latest run: {run_dir.name}")
    elif args.run_dir:
        run_dir = results_base / args.run_dir
        if not run_dir.exists():
            print(f"ERROR: Run directory not found: {run_dir}")
            sys.exit(1)
    else:
        print("ERROR: Must specify --run-dir or --latest")
        sys.exit(1)
    
    # Find metrics file
    metrics_path = run_dir / "aggregated_metrics.json"
    if not metrics_path.exists():
        print(f"ERROR: Metrics file not found: {metrics_path}")
        sys.exit(1)
    
    # Determine output directory
    if args.output_dir:
        output_dir = Path(args.output_dir)
    else:
        output_dir = run_dir / "plots"
    
    # Generate plots
    try:
        generate_all_plots(metrics_path, output_dir)
    except Exception as e:
        print(f"\n❌ ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
