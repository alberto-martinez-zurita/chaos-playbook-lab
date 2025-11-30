"""
Dashboard Generator - Logic Controller (Refactored & Polished v3).
Updates:
- Section renaming (Graphical Data, Summary Data).
- CSS improvements for compact tables (no scrollbars).
- Professional UI enhancements.
"""
import json
import argparse
import sys
import logging
from pathlib import Path
from typing import Dict, List, Any
from datetime import datetime

logger = logging.getLogger(__name__)

# --- 1. LÓGICA DE NEGOCIO (Igual que antes) ---

def extract_chart_data(metrics: Dict) -> Dict[str, List]:
    """Extract data arrays for plotting."""
    data = {k: [] for k in [
        'failure_rates', 'baseline_success', 'playbook_success', 
        'latency_overhead_pct', 'baseline_consistency', 'playbook_consistency',
        'effectiveness_improvement', 'consistency_improvement'
    ]}
    
    for rate_str in sorted(metrics.keys(), key=float):
        m = metrics[rate_str]
        data['failure_rates'].append(m['failure_rate'])
        
        # Success
        b_succ = m['baseline']['success_rate']['mean']
        p_succ = m['playbook']['success_rate']['mean']
        data['baseline_success'].append(b_succ)
        data['playbook_success'].append(p_succ)
        
        # Latency Overhead
        b_dur = m['baseline']['duration_s']['mean']
        p_dur = m['playbook']['duration_s']['mean']
        overhead = ((p_dur / b_dur) - 1) * 100 if b_dur > 0 else 0
        data['latency_overhead_pct'].append(overhead)
        
        # Consistency
        b_inc = m['baseline'].get('inconsistencies', {}).get('mean', 0.0)
        p_inc = m['playbook'].get('inconsistencies', {}).get('mean', 0.0)
        
        b_cons = (1.0 - b_inc) * 100
        p_cons = (1.0 - p_inc) * 100
        data['baseline_consistency'].append(b_cons)
        data['playbook_consistency'].append(p_cons)
        
        # Improvements
        data['effectiveness_improvement'].append((p_succ - b_succ) * 100)
        data['consistency_improvement'].append(p_cons - b_cons)
        
    return data

def calculate_summary_stats(metrics: Dict) -> Dict[str, Any]:
    """Calculate aggregate statistics."""
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

# --- 2. GENERADORES DE FRAGMENTOS HTML ---

def generate_summary_tables(metrics: Dict) -> str:
    """Generate compact summary tables."""
    failure_rates = sorted([float(k) for k in metrics.keys()])
    
    # Helper para headers compactos (quitar el % para ahorrar espacio si es necesario, pero lo dejamos por claridad)
    def make_header():
        h = "<tr><th>Agent</th>"
        for r in failure_rates: h += f"<th>{r*100:.0f}%</th>"
        return h + "</tr>"

    # --- Table 1: Success Rate ---
    t1 = f'<div class="table-container"><h3>Success Rate</h3><table>{make_header()}'
    for ag_key, label in [('baseline', 'Baseline'), ('playbook', 'Playbook')]:
        t1 += f"<tr><td><strong>{label}</strong></td>"
        for r in failure_rates:
            val = metrics[str(r)][ag_key]['success_rate']['mean'] * 100
            t1 += f"<td>{val:.0f}%</td>" # Reducido a 0 decimales para ahorrar espacio
        t1 += "</tr>"
    t1 += "<tr><td><strong>Delta</strong></td>"
    for r in failure_rates:
        d = metrics[str(r)]
        delta = (d['playbook']['success_rate']['mean'] - d['baseline']['success_rate']['mean']) * 100
        css = 'neutral' if abs(delta) < 0.05 else ('positive' if delta > 0 else 'negative')
        t1 += f"<td class=\"{css}\">{delta:+.0f}%</td>"
    t1 += "</tr></table></div>"

    # --- Table 2: Latency ---
    t2 = f'<div class="table-container"><h3>Latency Overhead</h3><table>{make_header()}'
    for ag_key, label in [('baseline', 'Baseline'), ('playbook', 'Playbook')]:
        t2 += f"<tr><td><strong>{label}</strong></td>"
        for r in failure_rates:
            val = metrics[str(r)][ag_key]['duration_s']['mean']
            t2 += f"<td>{val:.2f}s</td>"
        t2 += "</tr>"
    t2 += "<tr><td><strong>Overhead</strong></td>"
    for r in failure_rates:
        d = metrics[str(r)]
        b_val = d['baseline']['duration_s']['mean']
        p_val = d['playbook']['duration_s']['mean']
        ov = ((p_val / b_val) - 1) * 100 if b_val > 0 else 0.0
        css = 'negative' if ov > 10 else 'neutral'
        t2 += f"<td class=\"{css}\">+{ov:.0f}%</td>"
    t2 += "</tr></table></div>"

    # --- Table 3: Consistency ---
    t3 = f'<div class="table-container"><h3>Consistency Rate</h3><table>{make_header()}'
    for ag_key, label in [('baseline', 'Baseline'), ('playbook', 'Playbook')]:
        t3 += f"<tr><td><strong>{label}</strong></td>"
        for r in failure_rates:
            inc = metrics[str(r)][ag_key].get('inconsistencies', {}).get('mean', 0.0)
            val = (1.0 - inc) * 100
            t3 += f"<td>{val:.0f}%</td>"
        t3 += "</tr>"
    t3 += "<tr><td><strong>Delta</strong></td>"
    for r in failure_rates:
        d = metrics[str(r)]
        b_inc = d['baseline'].get('inconsistencies', {}).get('mean', 0.0)
        p_inc = d['playbook'].get('inconsistencies', {}).get('mean', 0.0)
        delta = ((1.0 - p_inc) - (1.0 - b_inc)) * 100
        css = 'neutral' if abs(delta) < 0.05 else ('positive' if delta > 0 else 'negative')
        t3 += f"<td class=\"{css}\">{delta:+.0f}%</td>"
    t3 += "</tr></table></div>"

    return f'<div class="summary-tables">{t1}{t2}{t3}</div>'

def generate_detailed_tables(metrics: Dict) -> str:
    """Generate detailed HTML tables."""
    html = '<div class="summary-tables detailed-grid">' # Clase extra para grid más denso
    for rate_str in sorted(metrics.keys(), key=float):
        data = metrics[rate_str]
        rate = data['failure_rate']
        n_exp = data['n_experiments']
        base = data['baseline']
        play = data['playbook']
        
        b_succ = base['success_rate']['mean'] * 100
        p_succ = play['success_rate']['mean'] * 100
        succ_delta = p_succ - b_succ
        
        b_dur = base['duration_s']['mean']
        p_dur = play['duration_s']['mean']
        lat_over = ((p_dur/b_dur)-1)*100 if b_dur > 0 else 0
        
        b_cons = (1.0 - base.get('inconsistencies', {}).get('mean', 0.0)) * 100
        p_cons = (1.0 - play.get('inconsistencies', {}).get('mean', 0.0)) * 100
        cons_delta = p_cons - b_cons
        
        s_css = 'positive' if succ_delta > 0 else ('negative' if succ_delta < 0 else 'neutral')
        l_css = 'negative' if lat_over > 0 else 'positive'
        c_css = 'positive' if cons_delta > 0 else 'neutral'
        
        html += f"""
        <div class="table-container detailed-card">
            <div class="card-header">
                <h3>Chaos Level: {rate*100:.0f}%</h3>
                <span class="badge">{n_exp} runs</span>
            </div>
            <table>
                <tr><th>Metric</th><th>Base</th><th>Playbook</th><th>Delta</th></tr>
                <tr>
                    <td>Success</td>
                    <td>{b_succ:.0f}%</td><td>{p_succ:.0f}%</td>
                    <td class="{s_css}">{succ_delta:+.0f}%</td>
                </tr>
                <tr>
                    <td>Latency</td>
                    <td>{b_dur:.2f}s</td><td>{p_dur:.2f}s</td>
                    <td class="{l_css}">+{lat_over:.0f}%</td>
                </tr>
                <tr>
                    <td>Consistency</td>
                    <td>{b_cons:.0f}%</td><td>{p_cons:.0f}%</td>
                    <td class="{c_css}">{cons_delta:+.0f}%</td>
                </tr>
            </table>
        </div>
        """
    html += '</div>'
    return html

# --- 3. INFRAESTRUCTURA ---

def load_template() -> str:
    paths = [
        Path(__file__).parent / "templates" / "dashboard.html",
        Path("src/chaos_engine/reporting/templates/dashboard.html"),
        Path("reporting/templates/dashboard.html")
    ]
    for p in paths:
        if p.exists(): return p.read_text(encoding="utf-8")
    raise FileNotFoundError("Template dashboard.html not found")

def generate_dashboard(metrics_path: Path, output_path: Path):
    print(f"\n🎨 Generating dashboard from: {metrics_path}")
    with open(metrics_path, 'r') as f: metrics = json.load(f)
        
    chart = extract_chart_data(metrics)
    stats = calculate_summary_stats(metrics)
    
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
        
        "summary_tables": generate_summary_tables(metrics),
        "detailed_tables": generate_detailed_tables(metrics),
        
        # JSON Data
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
        template = load_template()
        html = template.format(**context)
        with open(output_path, 'w', encoding='utf-8') as f: f.write(html)
        print(f"✅ Dashboard saved to: {output_path}")
    except Exception as e:
        logger.error(f"Render failed: {e}")
        raise

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--run-dir', type=str)
    parser.add_argument('--latest', action='store_true')
    parser.add_argument('--output', type=str)
    args = parser.parse_args()
    
    base_dir = Path("reports/parametric_experiments")
    if args.latest:
        runs = sorted([d for d in base_dir.iterdir() if d.is_dir()])
        if not runs: return
        run_dir = runs[-1]
    elif args.run_dir:
        run_dir = base_dir / args.run_dir
    else:
        print("Use --latest or --run-dir")
        return

    metrics_path = run_dir / "aggregated_metrics.json"
    output_path = Path(args.output) if args.output else run_dir / "dashboard.html"
    
    if metrics_path.exists():
        generate_dashboard(metrics_path, output_path)
    else:
        print(f"Metrics not found: {metrics_path}")

if __name__ == "__main__":
    main()