"""Dashboard Generator — pure data preparation.

Table rendering is handled client-side by JavaScript in templates/dashboard.html.
Charts rendered via Plotly.js.
"""
from __future__ import annotations

import argparse
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


def _extract_chart_data(metrics: Dict) -> Dict[str, List]:
    """Extract data arrays for plotting."""
    data: Dict[str, List] = {k: [] for k in [
        'failure_rates', 'baseline_success', 'playbook_success',
        'latency_overhead_pct', 'baseline_consistency', 'playbook_consistency',
        'effectiveness_improvement', 'consistency_improvement',
    ]}

    for rate_str in sorted(metrics.keys(), key=float):
        m = metrics[rate_str]
        data['failure_rates'].append(m['failure_rate'])

        b_succ = m['baseline']['success_rate']['mean']
        p_succ = m['playbook']['success_rate']['mean']
        data['baseline_success'].append(b_succ)
        data['playbook_success'].append(p_succ)

        b_dur = m['baseline']['duration_s']['mean']
        p_dur = m['playbook']['duration_s']['mean']
        overhead = ((p_dur / b_dur) - 1) * 100 if b_dur > 0 else 0
        data['latency_overhead_pct'].append(overhead)

        b_inc = m['baseline'].get('inconsistencies', {}).get('mean', 0.0)
        p_inc = m['playbook'].get('inconsistencies', {}).get('mean', 0.0)
        b_cons = (1.0 - b_inc) * 100
        p_cons = (1.0 - p_inc) * 100
        data['baseline_consistency'].append(b_cons)
        data['playbook_consistency'].append(p_cons)

        data['effectiveness_improvement'].append((p_succ - b_succ) * 100)
        data['consistency_improvement'].append(p_cons - b_cons)

    return data


def _calculate_summary_stats(metrics: Dict) -> Dict[str, Any]:
    """Calculate aggregate statistics for KPI cards."""
    max_improvement = 0
    total_b_dur = 0
    total_p_dur = 0
    total_p_cons = 0
    n = len(metrics)

    for rate_str in metrics.keys():
        m = metrics[rate_str]

        imp = m['playbook']['success_rate']['mean'] - m['baseline']['success_rate']['mean']
        if abs(imp) > abs(max_improvement):
            max_improvement = imp

        total_b_dur += m['baseline']['duration_s']['mean']
        total_p_dur += m['playbook']['duration_s']['mean']

        p_inc = m['playbook'].get('inconsistencies', {}).get('mean', 0.0)
        total_p_cons += (1.0 - p_inc)

    return {
        'max_improvement': max_improvement * 100,
        'improvement_class': "positive" if max_improvement > 0 else "negative",
        'avg_duration_baseline': total_b_dur / n if n > 0 else 0,
        'avg_duration_playbook': total_p_dur / n if n > 0 else 0,
        'avg_consistency_playbook': (total_p_cons / n * 100) if n > 0 else 0,
    }


def _load_template() -> str:
    """Load the dashboard HTML template."""
    paths = [
        Path(__file__).parent / "templates" / "dashboard.html",
        Path("src/chaos_engine/reporting/templates/dashboard.html"),
        Path("reporting/templates/dashboard.html"),
    ]
    for p in paths:
        if p.exists():
            return p.read_text(encoding="utf-8")
    raise FileNotFoundError("Template dashboard.html not found")


def generate_dashboard(metrics_path: Path, output_path: Path) -> None:
    """Generate an interactive HTML dashboard from aggregated metrics."""
    logger.info("Generating dashboard from: %s", metrics_path)
    with open(metrics_path, 'r') as f:
        metrics = json.load(f)

    chart = _extract_chart_data(metrics)
    stats = _calculate_summary_stats(metrics)

    context = {
        "generated_time": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        "run_name": metrics_path.parent.name,
        "failure_rates": ', '.join([f"{r*100:.0f}%" for r in chart['failure_rates']]),
        "total_runs": len(metrics) * 200,
        "improvement": stats['max_improvement'],
        "improvement_class": stats['improvement_class'],
        "avg_duration_baseline": stats['avg_duration_baseline'],
        "avg_duration_playbook": stats['avg_duration_playbook'],
        "avg_consistency_playbook": stats['avg_consistency_playbook'],

        # Raw metrics for client-side table rendering
        "metrics_json": json.dumps(metrics),

        # Chart data arrays
        "failure_rates_json": json.dumps(chart['failure_rates']),
        "failure_rates_label_json": json.dumps([f"{r*100:.0f}%" for r in chart['failure_rates']]),
        "baseline_success_json": json.dumps(chart['baseline_success']),
        "playbook_success_json": json.dumps(chart['playbook_success']),
        "latency_overhead_json": json.dumps(chart['latency_overhead_pct']),
        "baseline_consistency_json": json.dumps(chart['baseline_consistency']),
        "playbook_consistency_json": json.dumps(chart['playbook_consistency']),
        "effectiveness_improvement_json": json.dumps(chart['effectiveness_improvement']),
        "consistency_improvement_json": json.dumps(chart['consistency_improvement']),
    }

    try:
        template = _load_template()
        html = template.format(**context)
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(html)
        logger.info("Dashboard saved to: %s", output_path)
    except Exception as e:
        logger.error("Render failed: %s", e)
        raise


def main() -> None:
    """CLI entry point for standalone dashboard generation."""
    parser = argparse.ArgumentParser()
    parser.add_argument('--run-dir', type=str)
    parser.add_argument('--latest', action='store_true')
    parser.add_argument('--output', type=str)
    args = parser.parse_args()

    base_dir = Path("reports/parametric_experiments")
    if args.latest:
        runs = sorted([d for d in base_dir.iterdir() if d.is_dir()])
        if not runs:
            return
        run_dir = runs[-1]
    elif args.run_dir:
        run_dir = base_dir / args.run_dir
    else:
        logger.error("Use --latest or --run-dir")
        return

    metrics_path = run_dir / "aggregated_metrics.json"
    output_path = Path(args.output) if args.output else run_dir / "dashboard.html"

    if metrics_path.exists():
        generate_dashboard(metrics_path, output_path)
    else:
        logger.error("Metrics not found: %s", metrics_path)


if __name__ == "__main__":
    main()
