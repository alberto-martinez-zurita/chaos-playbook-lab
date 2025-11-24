"""
Report Generator for A/B Test Results (FIXED - v2 compatibility)

Location: scripts/generate_report.py

FIX: Updated to use "consistency" key instead of "inconsistency" (v2 metrics format)
     Backward compatible with both v1 (inconsistency) and v2 (consistency) formats

Usage:
    # Generate report for specific test
    poetry run python scripts/generate_report.py --test-id n05

    # Generate report for latest test
    poetry run python scripts/generate_report.py --latest

    # Display in terminal (don't save)
    poetry run python scripts/generate_report.py --latest --display-only
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional


def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Generate Markdown report from A/B test results",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Generate report for specific test
    poetry run python scripts/generate_report.py --test-id test_20251122_220000

    # Generate report for latest test
    poetry run python scripts/generate_report.py --latest

    # Display only (don't save)
    poetry run python scripts/generate_report.py --latest --display-only
"""
    )

    parser.add_argument(
        "--test-id",
        type=str,
        default=None,
        help="Test ID (directory name in results/)"
    )

    parser.add_argument(
        "--latest",
        action="store_true",
        help="Use latest test results"
    )

    parser.add_argument(
        "--display-only",
        action="store_true",
        help="Display report in terminal without saving"
    )

    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Custom output path (default: results/{test_id}/report.md)"
    )

    return parser.parse_args()


def find_latest_test() -> Optional[Path]:
    """Find the latest test directory in results/."""
    results_dir = Path("results")
    if not results_dir.exists():
        return None

    # Get all test directories (both test_* and n* formats)
    test_dirs = [d for d in results_dir.iterdir() if d.is_dir()]
    if not test_dirs:
        return None

    # Sort by creation time (newest first)
    test_dirs.sort(key=lambda d: d.stat().st_mtime, reverse=True)
    return test_dirs[0]


def load_metrics(test_dir: Path) -> Dict[str, Any]:
    """Load metrics_summary.json from test directory."""
    metrics_file = test_dir / "metrics_summary.json"
    if not metrics_file.exists():
        raise FileNotFoundError(f"Metrics file not found: {metrics_file}")

    with open(metrics_file, "r") as f:
        return json.load(f)


def format_percentage(value: float) -> str:
    """Format value as percentage."""
    return f"{value * 100:.1f}%"


def format_number(value: float, decimals: int = 2) -> str:
    """Format number with decimals."""
    return f"{value:.{decimals}f}"


def generate_report(metrics: Dict[str, Any], test_id: str) -> str:
    """Generate Markdown report from metrics."""
    baseline = metrics["baseline"]
    playbook = metrics["playbook"]
    improvements = metrics["improvements"]
    validation = metrics["validation"]

    # Extract key metrics
    baseline_sr = baseline["success_rate"]
    playbook_sr = playbook["success_rate"]
    
    # ✅ FIXED: Handle both v1 (inconsistency) and v2 (consistency) formats
    if "consistency" in baseline:
        # v2 format (new)
        baseline_ir = baseline["consistency"]
        playbook_ir = playbook["consistency"]
    else:
        # v1 format (legacy)
        baseline_ir = baseline["inconsistency"]
        playbook_ir = playbook["inconsistency"]
    
    baseline_lat = baseline["latency"]
    playbook_lat = playbook["latency"]

    # Build report
    report = []

    # Header
    report.append("# A/B Test Report")
    report.append("")
    report.append(f"**Test ID:** `{test_id}`")
    report.append(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    report.append(f"**Sample Size:** {baseline_sr['sample_size']} experiments per agent")
    report.append("")
    report.append("---")
    report.append("")

    # Executive Summary
    report.append("## Executive Summary")
    report.append("")

    # Determine overall result
    success_improved = improvements["success_rate_improvement"] > 0
    
    # ✅ FIXED: Use consistency_improvement (v2) or inconsistency_reduction (v1)
    if "consistency_improvement" in improvements:
        consistency_improved = improvements["consistency_improvement"] >= 0
    else:
        consistency_improved = improvements["inconsistency_reduction"] >= 0
    
    latency_acceptable = improvements["latency_overhead_pct"] < 20  # Within 20% overhead

    if success_improved and consistency_improved and latency_acceptable:
        report.append("✅ **Playbook agent significantly outperforms Baseline**")
    elif success_improved:
        report.append("⚠️ **Playbook agent shows improvement but with trade-offs**")
    else:
        report.append("❌ **Playbook agent does not show improvement over Baseline**")

    report.append("")
    report.append("**Key Findings:**")
    report.append("")

    # Success Rate
    if success_improved:
        report.append(f"- ✅ **Success Rate:** Playbook improved by **{format_percentage(improvements['success_rate_improvement'])}** "
                     f"({format_percentage(baseline_sr['mean'])} → {format_percentage(playbook_sr['mean'])})")
    else:
        report.append(f"- ❌ **Success Rate:** No improvement ({format_percentage(baseline_sr['mean'])} → {format_percentage(playbook_sr['mean'])})")

    # Consistency/Inconsistency
    if "consistency_improvement" in improvements:
        # v2 format: consistency_improvement
        if improvements["consistency_improvement"] > 0:
            report.append(f"- ✅ **Consistency:** Improved by **{format_percentage(improvements['consistency_improvement'])}** "
                         f"({format_percentage(baseline_ir['consistency_rate'])} → {format_percentage(playbook_ir['consistency_rate'])})")
        elif baseline_ir['inconsistency_rate'] == 0 and playbook_ir['inconsistency_rate'] == 0:
            report.append(f"- ✅ **Consistency:** Both agents have 0% inconsistency rate")
        else:
            report.append(f"- ⚠️ **Consistency:** No significant improvement")
    else:
        # v1 format: inconsistency_reduction
        if improvements["inconsistency_reduction"] > 0:
            report.append(f"- ✅ **Inconsistency:** Reduced by **{format_percentage(improvements['inconsistency_reduction'])}** "
                         f"({format_percentage(baseline_ir['inconsistency_rate'])} → {format_percentage(playbook_ir['inconsistency_rate'])})")
        elif baseline_ir['inconsistency_rate'] == 0 and playbook_ir['inconsistency_rate'] == 0:
            report.append(f"- ✅ **Inconsistency:** Both agents have 0% inconsistency rate")
        else:
            report.append(f"- ⚠️ **Inconsistency:** No significant reduction")

    # Latency
    overhead = improvements["latency_overhead_pct"]
    if overhead < 100:
        report.append(f"- ✅ **Latency:** Minimal overhead ({overhead:.1f}%, {format_number(baseline_lat['mean_latency_s'])}s → {format_number(playbook_lat['mean_latency_s'])}s)")
    elif overhead < 200:
        report.append(f"- ⚠️ **Latency:** Moderate overhead ({overhead:.1f}%, {format_number(baseline_lat['mean_latency_s'])}s → {format_number(playbook_lat['mean_latency_s'])}s)")
    else:
        report.append(f"- ❌ **Latency:** High overhead ({overhead:.1f}%, {format_number(baseline_lat['mean_latency_s'])}s → {format_number(playbook_lat['mean_latency_s'])}s)")

    report.append("")
    report.append("---")
    report.append("")

    # Detailed Metrics Comparison
    report.append("## Detailed Metrics Comparison")
    report.append("")

    # Success Rate Table
    report.append("### Success Rate")
    report.append("")
    report.append("| Metric | Baseline | Playbook | Improvement |")
    report.append("|--------|----------|----------|-------------|")
    report.append(f"| **Success Rate** | {format_percentage(baseline_sr['mean'])} | {format_percentage(playbook_sr['mean'])} | {format_percentage(improvements['success_rate_improvement'])} |")
    report.append(f"| Successes | {baseline_sr['successes']} | {playbook_sr['successes']} | +{playbook_sr['successes'] - baseline_sr['successes']} |")
    report.append(f"| Failures | {baseline_sr['failures']} | {playbook_sr['failures']} | {playbook_sr['failures'] - baseline_sr['failures']:+d} |")
    report.append(f"| Inconsistent | {baseline_sr['inconsistent']} | {playbook_sr['inconsistent']} | {playbook_sr['inconsistent'] - baseline_sr['inconsistent']:+d} |")
    report.append(f"| Sample Size | {baseline_sr['sample_size']} | {playbook_sr['sample_size']} | - |")
    report.append("")

    # Consistency/Inconsistency Table
    report.append("### Consistency Analysis")
    report.append("")
    report.append("| Metric | Baseline | Playbook | Change |")
    report.append("|--------|----------|----------|--------|")
    
    # ✅ FIXED: Display appropriate metrics based on format version
    if "consistency_rate" in baseline_ir:
        # v2 format
        report.append(f"| **Consistency Rate** | {format_percentage(baseline_ir['consistency_rate'])} | {format_percentage(playbook_ir['consistency_rate'])} | {format_percentage(improvements.get('consistency_improvement', 0))} |")
    
    report.append(f"| **Inconsistency Rate** | {format_percentage(baseline_ir['inconsistency_rate'])} | {format_percentage(playbook_ir['inconsistency_rate'])} | {format_percentage(improvements.get('inconsistency_reduction', 0))} |")
    report.append(f"| Total Inconsistencies | {baseline_ir.get('inconsistent_count', 0)} | {playbook_ir.get('inconsistent_count', 0)} | {playbook_ir.get('inconsistent_count', 0) - baseline_ir.get('inconsistent_count', 0):+d} |")
    report.append("")

    # Latency Table
    report.append("### Latency Statistics")
    report.append("")
    report.append("| Metric | Baseline | Playbook | Overhead |")
    report.append("|--------|----------|----------|----------|")
    report.append(f"| **Mean Latency** | {format_number(baseline_lat['mean_latency_s'])}s | {format_number(playbook_lat['mean_latency_s'])}s | {overhead:+.1f}% |")
    report.append(f"| Median Latency | {format_number(baseline_lat['median_latency_s'])}s | {format_number(playbook_lat['median_latency_s'])}s | - |")
    report.append(f"| P95 Latency | {format_number(baseline_lat['p95_latency_s'])}s | {format_number(playbook_lat['p95_latency_s'])}s | - |")
    report.append(f"| Min Latency | {format_number(baseline_lat['min_latency_s'])}s | {format_number(playbook_lat['min_latency_s'])}s | - |")
    report.append(f"| Max Latency | {format_number(baseline_lat['max_latency_s'])}s | {format_number(playbook_lat['max_latency_s'])}s | - |")
    report.append("")

    report.append("---")
    report.append("")

    # Validation Results
    report.append("## Validation Results")
    report.append("")
    for metric_id, passes in validation.items():
        status_icon = "✅" if passes else "❌"
        status_text = "PASS" if passes else "FAIL"
        report.append(f"**{metric_id}:** {status_icon} {status_text}")
    report.append("")

    report.append("---")
    report.append("")

    # Statistical Summary
    report.append("## Statistical Summary")
    report.append("")
    report.append(f"**Baseline Agent:**")
    report.append(f"- Success Rate: {format_percentage(baseline_sr['mean'])} (95% CI: [{format_percentage(baseline_sr['confidence_interval_95'][0])}, {format_percentage(baseline_sr['confidence_interval_95'][1])}])")
    report.append(f"- Mean Latency: {format_number(baseline_lat['mean_latency_s'])}s (±{format_number(baseline_lat['std_latency_s'])}s)")
    report.append("")
    report.append(f"**Playbook Agent:**")
    report.append(f"- Success Rate: {format_percentage(playbook_sr['mean'])} (95% CI: [{format_percentage(playbook_sr['confidence_interval_95'][0])}, {format_percentage(playbook_sr['confidence_interval_95'][1])}])")
    report.append(f"- Mean Latency: {format_number(playbook_lat['mean_latency_s'])}s (±{format_number(playbook_lat['std_latency_s'])}s)")
    report.append("")

    # Playbook Strategies
    if "strategies_used" in playbook:
        report.append("---")
        report.append("")
        report.append("## Playbook Strategies Used")
        report.append("")
        strategies = playbook.get("strategies_used", [])
        if strategies:
            for strategy in strategies:
                report.append(f"- `{strategy}`")
            report.append("")
        else:
            report.append("*No Playbook strategies were used in this test*")
            report.append("")

    # Footer
    report.append("---")
    report.append("")
    report.append("*Generated by Chaos Playbook Engine - A/B Test Report Generator*")
    report.append("")

    return "\n".join(report)


def main():
    """Main entry point."""
    args = parse_arguments()

    # Determine test directory
    if args.latest:
        test_dir = find_latest_test()
        if not test_dir:
            print("ERROR: No test results found in results/")
            sys.exit(1)
        test_id = test_dir.name
        print(f"Using latest test: {test_id}")
    elif args.test_id:
        test_dir = Path("results") / args.test_id
        test_id = args.test_id
        if not test_dir.exists():
            print(f"ERROR: Test directory not found: {test_dir}")
            sys.exit(1)
    else:
        print("ERROR: Must specify either --test-id or --latest")
        sys.exit(1)

    # Load metrics
    print(f"Loading metrics from {test_dir}...")
    try:
        metrics = load_metrics(test_dir)
    except FileNotFoundError as e:
        print(f"ERROR: {e}")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"ERROR: Invalid JSON in metrics file: {e}")
        sys.exit(1)

    # Generate report
    print("Generating report...")
    report_content = generate_report(metrics, test_id)

    # Display or save
    if args.display_only:
        print("\n" + "=" * 70)
        print(report_content)
        print("=" * 70)
    else:
        # Determine output path
        if args.output:
            output_path = Path(args.output)
        else:
            output_path = test_dir / "report.md"

        # Save report with UTF-8 encoding (for emoji support on Windows)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(report_content)

        print(f"✅ Report saved to: {output_path}")
        print(f"\nView with:")
        print(f"  cat {output_path}")
        print(f"  code {output_path}")


if __name__ == "__main__":
    main()
