"""
Dashboard HTML Generator for Parametric Experiments - PHASE 5.2.4 - FINAL v5

Location: scripts/generate_dashboard.py

Purpose: Generate interactive HTML dashboard from parametric experiment results

Features:
- Interactive Plotly charts (zoom, pan, hover)
- Summary statistics cards with updated metrics
- Responsive design
- Export functionality (PNG, SVG)
- Real-time filtering

Updates v5:
- Chart 1: Agent Effectiveness (bars) with % labels
- Chart 2: Latency Overhead (%) with dynamic X-axis
- Chart 3: Data Consistency (%)
- Chart 4: Combined Trends
- Summary Results tables (2 per row - same width as charts)
- Detailed Results tables (2 per row - same width as charts)
- Delta values with 0.0% in black (neutral class)
- Updated table labels and delta format
"""

import json
import argparse
import sys
from pathlib import Path
from typing import Dict, List
from datetime import datetime


HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Chaos Playbook Engine - Parametric Experiment Dashboard</title>
    <script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }}
        
        .container {{
            max-width: 1400px;
            margin: 0 auto;
            background: white;
            border-radius: 12px;
            box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
            overflow: hidden;
        }}
        
        .header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 40px;
            text-align: center;
        }}
        
        .header h1 {{
            font-size: 2.5em;
            margin-bottom: 10px;
            font-weight: 700;
        }}
        
        .header p {{
            font-size: 1.1em;
            opacity: 0.9;
        }}
        
        .metadata {{
            background: #f8f9fa;
            padding: 20px 40px;
            border-bottom: 1px solid #e0e0e0;
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            font-size: 0.9em;
        }}
        
        .metadata-item {{
            display: flex;
            flex-direction: column;
        }}
        
        .metadata-label {{
            font-weight: 600;
            color: #667eea;
            margin-bottom: 5px;
        }}
        
        .metadata-value {{
            color: #555;
        }}
        
        .content {{
            padding: 40px;
        }}
        
        .section {{
            margin-bottom: 60px;
        }}
        
        .section h2 {{
            color: #333;
            font-size: 1.8em;
            margin-bottom: 30px;
            padding-bottom: 15px;
            border-bottom: 3px solid #667eea;
        }}
        
        .summary-cards {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 20px;
            margin-bottom: 40px;
        }}
        
        .summary-card {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 25px;
            border-radius: 8px;
            box-shadow: 0 4px 15px rgba(102, 126, 234, 0.3);
            text-align: center;
            transition: transform 0.3s ease, box-shadow 0.3s ease;
        }}
        
        .summary-card:hover {{
            transform: translateY(-5px);
            box-shadow: 0 8px 25px rgba(102, 126, 234, 0.4);
        }}
        
        .summary-card-value {{
            font-size: 2.5em;
            font-weight: 700;
            margin: 10px 0;
            font-variant-numeric: tabular-nums;
        }}
        
        .summary-card-label {{
            font-size: 0.95em;
            opacity: 0.9;
        }}
        
        .charts-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(600px, 1fr));
            gap: 30px;
        }}
        
        .chart-container {{
            background: #f8f9fa;
            border: 1px solid #e0e0e0;
            border-radius: 8px;
            padding: 20px;
            box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
        }}
        
        .chart-title {{
            font-size: 1.2em;
            font-weight: 600;
            color: #333;
            margin-bottom: 15px;
            padding-bottom: 10px;
            border-bottom: 2px solid #667eea;
        }}
        
        .chart {{
            width: 100%;
            height: 400px;
        }}
        
        .summary-tables {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(600px, 1fr));
            gap: 30px;
            margin-top: 30px;
        }}
        
        .table-container {{
            background: #f8f9fa;
            border: 1px solid #e0e0e0;
            border-radius: 8px;
            padding: 20px;
            overflow-x: auto;
        }}
        
        table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 0.9em;
        }}
        
        th {{
            background: #667eea;
            color: white;
            padding: 12px;
            text-align: left;
            font-weight: 600;
        }}
        
        td {{
            padding: 10px 12px;
            border-bottom: 1px solid #ddd;
        }}
        
        tr:hover {{
            background: white;
        }}
        
        .positive {{
            color: #28a745;
            font-weight: 600;
        }}
        
        .negative {{
            color: #dc3545;
            font-weight: 600;
        }}
        
        .neutral {{
            color: #333;
            font-weight: 600;
        }}
        
        .footer {{
            background: #f8f9fa;
            padding: 30px 40px;
            border-top: 1px solid #e0e0e0;
            text-align: center;
            color: #666;
            font-size: 0.9em;
        }}
        
        @media (max-width: 768px) {{
            .header h1 {{
                font-size: 1.8em;
            }}
            
            .metadata {{
                grid-template-columns: 1fr;
            }}
            
            .charts-grid {{
                grid-template-columns: 1fr;
            }}
            
            .summary-cards {{
                grid-template-columns: 1fr;
            }}
            
            .summary-tables {{
                grid-template-columns: 1fr;
            }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🔬 Chaos Playbook Engine</h1>
            <p>Parametric Experiment Dashboard</p>
        </div>
        
        <div class="metadata">
            <div class="metadata-item">
                <span class="metadata-label">Generated</span>
                <span class="metadata-value">{generated_time}</span>
            </div>
            <div class="metadata-item">
                <span class="metadata-label">Experiment Run</span>
                <span class="metadata-value">{run_name}</span>
            </div>
            <div class="metadata-item">
                <span class="metadata-label">Failure Rates Tested</span>
                <span class="metadata-value">{failure_rates}</span>
            </div>
            <div class="metadata-item">
                <span class="metadata-label">Total Runs</span>
                <span class="metadata-value">{total_runs}</span>
            </div>
        </div>
        
        <div class="content">
            <!-- SUMMARY SECTION -->
            <div class="section">
                <h2>📊 Executive Summary</h2>
                <div class="summary-cards">
                    <div class="summary-card">
                        <div class="summary-card-label">Max Effectiveness Gain</div>
                        <div class="summary-card-value {improvement_class}">{improvement:+.0f}%</div>
                    </div>
                    <div class="summary-card">
                        <div class="summary-card-label">Avg Latency (Baseline)</div>
                        <div class="summary-card-value">{avg_duration_baseline:.2f}s</div>
                    </div>
                    <div class="summary-card">
                        <div class="summary-card-label">Avg Latency (Playbook)</div>
                        <div class="summary-card-value">{avg_duration_playbook:.2f}s</div>
                    </div>
                    <div class="summary-card">
                        <div class="summary-card-label">Avg Consistency (Playbook)</div>
                        <div class="summary-card-value">{avg_consistency_playbook:.0f}%</div>
                    </div>
                </div>
            </div>
            
            <!-- CHARTS SECTION -->
            <div class="section">
                <h2>📈 Comparative Analysis</h2>
                <div class="charts-grid">
                    <div class="chart-container">
                        <div class="chart-title">Agent Effectiveness</div>
                        <div id="effectiveness-chart" class="chart"></div>
                    </div>
                    <div class="chart-container">
                        <div class="chart-title">Latency Overhead (%)</div>
                        <div id="latency-chart" class="chart"></div>
                    </div>
                    <div class="chart-container">
                        <div class="chart-title">Data Consistency (%)</div>
                        <div id="consistency-chart" class="chart"></div>
                    </div>
                    <div class="chart-container">
                        <div class="chart-title">Combined Performance Trends</div>
                        <div id="combined-chart" class="chart"></div>
                    </div>
                </div>
            </div>
            
            <!-- SUMMARY RESULTS SECTION -->
            <div class="section">
                <h2>📊 Summary Results</h2>
                {summary_tables}
            </div>
            
            <!-- DETAILED RESULTS SECTION -->
            <div class="section">
                <h2>📋 Detailed Results by Failure Rate</h2>
                {detailed_tables}
            </div>
        </div>
        
        <div class="footer">
            <p>Generated by Chaos Playbook Engine v2.0 | Parametric Experiment Analysis</p>
            <p>For questions or support, contact the development team.</p>
        </div>
    </div>
    
    <script>
        // Chart 1: Agent Effectiveness (Bar Chart) - FIRST
        var effectivenessTrace1 = {{
            x: {failure_rates_label_json},
            y: {baseline_success_json},
            name: 'Baseline Agent',
            type: 'bar',
            marker: {{color: '#FF6B6B'}},
            hovertemplate: '<b>Baseline</b><br>Failure Rate: %{{x}}<br>Success Rate: %{{y:.1%}}<extra></extra>'
        }};
        
        var effectivenessTrace2 = {{
            x: {failure_rates_label_json},
            y: {playbook_success_json},
            name: 'Playbook Agent',
            type: 'bar',
            marker: {{color: '#4ECDC4'}},
            hovertemplate: '<b>Playbook</b><br>Failure Rate: %{{x}}<br>Success Rate: %{{y:.1%}}<extra></extra>'
        }};
        
        var effectivenessLayout = {{
            title: 'Agent Effectiveness Comparison',
            xaxis: {{title: 'Failure Rate (%)'}},
            yaxis: {{title: 'Success Rate (%)', tickformat: '.0%'}},
            barmode: 'group',
            plot_bgcolor: '#f8f9fa',
            paper_bgcolor: 'white',
            font: {{family: 'Segoe UI, Tahoma, Geneva, Verdana, sans-serif'}}
        }};
        
        Plotly.newPlot('effectiveness-chart', [effectivenessTrace1, effectivenessTrace2], effectivenessLayout, {{responsive: true}});
        
        // Chart 2: Latency Overhead (%)
        var latencyTrace = {{
            x: {failure_rates_json},
            y: {latency_overhead_json},
            name: 'Latency Overhead',
            mode: 'lines+markers',
            line: {{color: '#FF6B6B', width: 3}},
            marker: {{size: 10}},
            hovertemplate: '<b>Latency Overhead</b><br>Failure Rate: %{{x:.0%}}<br>Overhead: %{{y:.1f}}%<extra></extra>'
        }};
        
        var maxFailureRate = Math.max(...{failure_rates_json});
        
        var latencyLayout = {{
            title: 'Playbook Latency Overhead vs Baseline',
            xaxis: {{title: 'Failure Rate (%)', tickformat: ',.0%', range: [0, maxFailureRate * 1.1]}},
            yaxis: {{title: 'Latency Overhead (%)'}},
            hovermode: 'x unified',
            plot_bgcolor: '#f8f9fa',
            paper_bgcolor: 'white',
            font: {{family: 'Segoe UI, Tahoma, Geneva, Verdana, sans-serif'}},
            shapes: [{{
                type: 'line',
                x0: 0,
                x1: maxFailureRate,
                y0: 0,
                y1: 0,
                line: {{
                    color: 'rgba(0,0,0,0.3)',
                    width: 1,
                    dash: 'dash'
                }}
            }}]
        }};
        
        Plotly.newPlot('latency-chart', [latencyTrace], latencyLayout, {{responsive: true}});
        
        // Chart 3: Data Consistency (%)
        var consistencyTrace1 = {{
            x: {failure_rates_json},
            y: {baseline_consistency_json},
            name: 'Baseline Agent',
            mode: 'lines+markers',
            line: {{color: '#FF6B6B', width: 3}},
            marker: {{size: 10}},
            hovertemplate: '<b>Baseline</b><br>Failure Rate: %{{x:.0%}}<br>Consistency: %{{y:.1f}}%<extra></extra>'
        }};
        
        var consistencyTrace2 = {{
            x: {failure_rates_json},
            y: {playbook_consistency_json},
            name: 'Playbook Agent',
            mode: 'lines+markers',
            line: {{color: '#4ECDC4', width: 3}},
            marker: {{size: 10}},
            hovertemplate: '<b>Playbook</b><br>Failure Rate: %{{x:.0%}}<br>Consistency: %{{y:.1f}}%<extra></extra>'
        }};
        
        var consistencyLayout = {{
            title: 'Data Consistency',
            xaxis: {{title: 'Failure Rate (%)', tickformat: ',.0%'}},
            yaxis: {{title: 'Consistency (%)', range: [0, 100]}},
            hovermode: 'x unified',
            plot_bgcolor: '#f8f9fa',
            paper_bgcolor: 'white',
            font: {{family: 'Segoe UI, Tahoma, Geneva, Verdana, sans-serif'}}
        }};
        
        Plotly.newPlot('consistency-chart', [consistencyTrace1, consistencyTrace2], consistencyLayout, {{responsive: true}});
        
        // Chart 4: Combined Performance Trends (NEW)
        var combinedTrace1 = {{
            x: {failure_rates_json},
            y: {effectiveness_improvement_json},
            name: 'Effectiveness Improvement',
            mode: 'lines+markers',
            line: {{color: '#4ECDC4', width: 3}},
            marker: {{size: 10}},
            hovertemplate: '<b>Effectiveness Improvement</b><br>Failure Rate: %{{x:.0%}}<br>Change: %{{y:.1f}}%<extra></extra>'
        }};
        
        var combinedTrace2 = {{
            x: {failure_rates_json},
            y: {latency_overhead_json},
            name: 'Latency Overhead',
            mode: 'lines+markers',
            line: {{color: '#FF6B6B', width: 3}},
            marker: {{size: 10}},
            yaxis: 'y2',
            hovertemplate: '<b>Latency Overhead</b><br>Failure Rate: %{{x:.0%}}<br>Change: %{{y:.1f}}%<extra></extra>'
        }};
        
        var combinedTrace3 = {{
            x: {failure_rates_json},
            y: {consistency_improvement_json},
            name: 'Consistency Improvement',
            mode: 'lines+markers',
            line: {{color: '#95E1D3', width: 3}},
            marker: {{size: 10}},
            hovertemplate: '<b>Consistency Improvement</b><br>Failure Rate: %{{x:.0%}}<br>Change: %{{y:.1f}}%<extra></extra>'
        }};
        
        var combinedLayout = {{
            title: 'Combined Performance Trends',
            xaxis: {{title: 'Failure Rate (%)', tickformat: ',.0%'}},
            yaxis: {{title: 'Improvement (%)', side: 'left'}},
            yaxis2: {{
                title: 'Overhead (%)',
                overlaying: 'y',
                side: 'right'
            }},
            hovermode: 'x unified',
            plot_bgcolor: '#f8f9fa',
            paper_bgcolor: 'white',
            font: {{family: 'Segoe UI, Tahoma, Geneva, Verdana, sans-serif'}},
            legend: {{x: 0.1, y: 1.1, orientation: 'h'}}
        }};
        
        Plotly.newPlot('combined-chart', [combinedTrace1, combinedTrace3, combinedTrace2], combinedLayout, {{responsive: true}});
    </script>
</body>
</html>
"""


def load_metrics(json_path: Path) -> Dict:
    """Load aggregated metrics from JSON file."""
    with open(json_path, 'r') as f:
        return json.load(f)


def generate_summary_tables(metrics: Dict) -> str:
    """Generate summary tables for each metric across all failure rates."""
    # Collect data
    failure_rates = sorted([float(k) for k in metrics.keys()])
    
    # Success Rate table
    success_html = """
    <div class="table-container">
        <h3>Success Rate Summary</h3>
        <table>
            <tr>
                <th>Agent</th>
"""
    for rate in failure_rates:
        success_html += f"                <th>{rate*100:.0f}%</th>\n"
    success_html += "            </tr>\n"
    
    # Baseline row
    success_html += "            <tr>\n                <td><strong>Baseline Agent</strong></td>\n"
    for rate in failure_rates:
        data = metrics[str(rate)]
        val = data['baseline']['success_rate']['mean'] * 100
        success_html += f"                <td>{val:.1f}%</td>\n"
    success_html += "            </tr>\n"
    
    # Playbook row
    success_html += "            <tr>\n                <td><strong>Playbook Agent</strong></td>\n"
    for rate in failure_rates:
        data = metrics[str(rate)]
        val = data['playbook']['success_rate']['mean'] * 100
        success_html += f"                <td>{val:.1f}%</td>\n"
    success_html += "            </tr>\n"
    
    # Delta row
    success_html += "            <tr>\n                <td><strong>Delta</strong></td>\n"
    for rate in failure_rates:
        data = metrics[str(rate)]
        baseline_val = data['baseline']['success_rate']['mean'] * 100
        playbook_val = data['playbook']['success_rate']['mean'] * 100
        delta = playbook_val - baseline_val
        if abs(delta) < 0.05:  # Less than 0.05% is neutral
            css_class = 'neutral'
        else:
            css_class = 'positive' if delta > 0 else 'negative'
        success_html += f"                <td class=\"{css_class}\">{delta:+.1f}%</td>\n"
    success_html += "            </tr>\n"
    success_html += "        </table>\n    </div>\n"
    
    # Latency table
    latency_html = """
    <div class="table-container">
        <h3>Latency Overhead Rate Summary</h3>
        <table>
            <tr>
                <th>Agent</th>
"""
    for rate in failure_rates:
        latency_html += f"                <th>{rate*100:.0f}%</th>\n"
    latency_html += "            </tr>\n"
    
    # Baseline row
    latency_html += "            <tr>\n                <td><strong>Baseline Agent</strong></td>\n"
    for rate in failure_rates:
        data = metrics[str(rate)]
        val = data['baseline']['duration_s']['mean']
        latency_html += f"                <td>{val:.2f}s</td>\n"
    latency_html += "            </tr>\n"
    
    # Playbook row
    latency_html += "            <tr>\n                <td><strong>Playbook Agent</strong></td>\n"
    for rate in failure_rates:
        data = metrics[str(rate)]
        val = data['playbook']['duration_s']['mean']
        latency_html += f"                <td>{val:.2f}s</td>\n"
    latency_html += "            </tr>\n"
    
    # Delta row (overhead %)
    latency_html += "            <tr>\n                <td><strong>Delta</strong></td>\n"
    for rate in failure_rates:
        data = metrics[str(rate)]
        baseline_val = data['baseline']['duration_s']['mean']
        playbook_val = data['playbook']['duration_s']['mean']
        if baseline_val > 0:
            overhead = ((playbook_val / baseline_val) - 1) * 100
        else:
            overhead = 0
        if abs(overhead) < 0.05:  # Less than 0.05% is neutral
            css_class = 'neutral'
        else:
            css_class = 'negative' if overhead > 0 else 'positive'
        latency_html += f"                <td class=\"{css_class}\">{overhead:+.1f}%</td>\n"
    latency_html += "            </tr>\n"
    latency_html += "        </table>\n    </div>\n"
    
    # Consistency table
    consistency_html = """
    <div class="table-container">
        <h3>Consistency Rate Summary</h3>
        <table>
            <tr>
                <th>Agent</th>
"""
    for rate in failure_rates:
        consistency_html += f"                <th>{rate*100:.0f}%</th>\n"
    consistency_html += "            </tr>\n"
    
    # Baseline row
    consistency_html += "            <tr>\n                <td><strong>Baseline Agent</strong></td>\n"
    for rate in failure_rates:
        data = metrics[str(rate)]
        val = (1.0 - data['baseline']['inconsistencies']['mean']) * 100
        consistency_html += f"                <td>{val:.1f}%</td>\n"
    consistency_html += "            </tr>\n"
    
    # Playbook row
    consistency_html += "            <tr>\n                <td><strong>Playbook Agent</strong></td>\n"
    for rate in failure_rates:
        data = metrics[str(rate)]
        val = (1.0 - data['playbook']['inconsistencies']['mean']) * 100
        consistency_html += f"                <td>{val:.1f}%</td>\n"
    consistency_html += "            </tr>\n"
    
    # Delta row
    consistency_html += "            <tr>\n                <td><strong>Delta</strong></td>\n"
    for rate in failure_rates:
        data = metrics[str(rate)]
        baseline_val = (1.0 - data['baseline']['inconsistencies']['mean']) * 100
        playbook_val = (1.0 - data['playbook']['inconsistencies']['mean']) * 100
        delta = playbook_val - baseline_val
        if abs(delta) < 0.05:  # Less than 0.05% is neutral
            css_class = 'neutral'
        else:
            css_class = 'positive' if delta > 0 else 'negative'
        consistency_html += f"                <td class=\"{css_class}\">{delta:+.1f}%</td>\n"
    consistency_html += "            </tr>\n"
    consistency_html += "        </table>\n    </div>\n"
    
    return f'<div class="summary-tables_2">\n{success_html}\n{latency_html}\n{consistency_html}\n</div>'


def generate_detailed_tables(metrics: Dict) -> str:
    """Generate detailed HTML tables for each failure rate."""
    html = '<div class="summary-tables">\n'
    
    for rate_str in sorted(metrics.keys(), key=float):
        data = metrics[rate_str]
        rate = data['failure_rate']
        n_exp = data['n_experiments']
        
        baseline = data['baseline']
        playbook = data['playbook']
        
        # Calculate metrics
        baseline_consistency = (1.0 - baseline['inconsistencies']['mean']) * 100
        playbook_consistency = (1.0 - playbook['inconsistencies']['mean']) * 100
        consistency_delta = playbook_consistency - baseline_consistency
        
        # Calculate latency overhead
        if baseline['duration_s']['mean'] > 0:
            latency_overhead = ((playbook['duration_s']['mean'] / baseline['duration_s']['mean']) - 1) * 100
        else:
            latency_overhead = 0
        
        # Calculate success rate delta
        success_delta = (playbook['success_rate']['mean'] - baseline['success_rate']['mean']) * 100
        
        # Determine CSS classes with neutral handling
        if abs(success_delta) < 0.05:
            success_css_class = 'neutral'
        else:
            success_css_class = 'positive' if success_delta > 0 else 'negative'
        
        if abs(latency_overhead) < 0.05:
            latency_css_class = 'neutral'
        else:
            latency_css_class = 'negative' if latency_overhead > 0 else 'positive'
        
        if abs(consistency_delta) < 0.05:
            consistency_css_class = 'neutral'
        else:
            consistency_css_class = 'positive' if consistency_delta > 0 else 'negative'
        
        html += f"""
        <div class="table-container">
            <h3>Failure Rate: {rate*100:.0f}% ({n_exp} experiments)</h3>
            <table>
                <tr>
                    <th>Metric</th>
                    <th>Baseline Agent</th>
                    <th>Playbook Agent</th>
                    <th>Delta</th>
                </tr>
                <tr>
                    <td><strong>Success Rate</strong></td>
                    <td>{baseline['success_rate']['mean']*100:.1f}%</td>
                    <td>{playbook['success_rate']['mean']*100:.1f}%</td>
                    <td class="{success_css_class}">
                        {success_delta:+.1f}%
                    </td>
                </tr>
                <tr>
                    <td><strong>Latency Overhead Rate</strong></td>
                    <td>{baseline['duration_s']['mean']:.2f}s ± {baseline['duration_s']['std']:.2f}s</td>
                    <td>{playbook['duration_s']['mean']:.2f}s ± {playbook['duration_s']['std']:.2f}s</td>
                    <td class="{latency_css_class}">
                        {latency_overhead:+.1f}%
                    </td>
                </tr>
                <tr>
                    <td><strong>Consistency Rate</strong></td>
                    <td>{baseline_consistency:.1f}%</td>
                    <td>{playbook_consistency:.1f}%</td>
                    <td class="{consistency_css_class}">
                        {consistency_delta:+.1f}%
                    </td>
                </tr>
            </table>
        </div>
        """
    
    html += '</div>'
    return html


def extract_chart_data(metrics: Dict):
    """Extract data for charts."""
    failure_rates = []
    baseline_success = []
    playbook_success = []
    latency_overhead_pct = []
    baseline_consistency = []
    playbook_consistency = []
    effectiveness_improvement = []
    consistency_improvement = []
    
    for rate_str in sorted(metrics.keys(), key=float):
        data = metrics[rate_str]
        failure_rates.append(data['failure_rate'])
        
        baseline_success.append(data['baseline']['success_rate']['mean'])
        playbook_success.append(data['playbook']['success_rate']['mean'])
        
        # Calculate latency overhead percentage
        baseline_dur = data['baseline']['duration_s']['mean']
        playbook_dur = data['playbook']['duration_s']['mean']
        if baseline_dur > 0:
            overhead = ((playbook_dur / baseline_dur) - 1) * 100
        else:
            overhead = 0
        latency_overhead_pct.append(overhead)
        
        # Calculate consistency (1 - inconsistencies) as percentage
        baseline_cons = (1.0 - data['baseline']['inconsistencies']['mean']) * 100
        playbook_cons = (1.0 - data['playbook']['inconsistencies']['mean']) * 100
        baseline_consistency.append(baseline_cons)
        playbook_consistency.append(playbook_cons)
        
        # Calculate improvements for combined chart
        effectiveness_improvement.append((data['playbook']['success_rate']['mean'] - data['baseline']['success_rate']['mean']) * 100)
        consistency_improvement.append(playbook_cons - baseline_cons)
    
    return {
        'failure_rates': failure_rates,
        'baseline_success': baseline_success,
        'playbook_success': playbook_success,
        'latency_overhead_pct': latency_overhead_pct,
        'baseline_consistency': baseline_consistency,
        'playbook_consistency': playbook_consistency,
        'effectiveness_improvement': effectiveness_improvement,
        'consistency_improvement': consistency_improvement,
    }


def calculate_summary_stats(metrics: Dict):
    """Calculate summary statistics."""
    max_improvement = 0
    avg_duration_baseline = 0
    avg_duration_playbook = 0
    avg_consistency_playbook = 0
    
    n_rates = len(metrics)
    
    for rate_str in metrics.keys():
        data = metrics[rate_str]
        baseline = data['baseline']
        playbook = data['playbook']
        
        # Calculate improvement
        b_success = baseline['success_rate']['mean']
        p_success = playbook['success_rate']['mean']
        improvement = p_success - b_success
        
        if abs(improvement) > abs(max_improvement):
            max_improvement = improvement
        
        avg_duration_baseline += baseline['duration_s']['mean']
        avg_duration_playbook += playbook['duration_s']['mean']
        avg_consistency_playbook += (1.0 - playbook['inconsistencies']['mean'])
    
    avg_duration_baseline /= n_rates
    avg_duration_playbook /= n_rates
    avg_consistency_playbook = (avg_consistency_playbook / n_rates) * 100
    
    improvement_class = "positive" if max_improvement > 0 else "negative"
    
    return {
        'max_improvement': max_improvement * 100,
        'improvement_class': improvement_class,
        'avg_duration_baseline': avg_duration_baseline,
        'avg_duration_playbook': avg_duration_playbook,
        'avg_consistency_playbook': avg_consistency_playbook,
    }


def generate_dashboard(metrics_path: Path, output_path: Path):
    """Generate complete HTML dashboard."""
    print(f"\n🎨 Generating dashboard from: {metrics_path}")
    print(f"   Output: {output_path}\n")
    
    # Load metrics
    metrics = load_metrics(metrics_path)
    
    # Extract data
    chart_data = extract_chart_data(metrics)
    summary_stats = calculate_summary_stats(metrics)
    
    # Generate tables
    summary_tables = generate_summary_tables(metrics)
    detailed_tables = generate_detailed_tables(metrics)
    
    # Prepare JSON for charts
    failure_rates_json = json.dumps(chart_data['failure_rates'])
    failure_rates_label_json = json.dumps([f"{r*100:.0f}%" for r in chart_data['failure_rates']])
    baseline_success_json = json.dumps(chart_data['baseline_success'])
    playbook_success_json = json.dumps(chart_data['playbook_success'])
    latency_overhead_json = json.dumps(chart_data['latency_overhead_pct'])
    baseline_consistency_json = json.dumps(chart_data['baseline_consistency'])
    playbook_consistency_json = json.dumps(chart_data['playbook_consistency'])
    effectiveness_improvement_json = json.dumps(chart_data['effectiveness_improvement'])
    consistency_improvement_json = json.dumps(chart_data['consistency_improvement'])
    
    # Format HTML
    html = HTML_TEMPLATE.format(
        generated_time=datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        run_name=metrics_path.parent.name,
        failure_rates=', '.join([f"{r*100:.0f}%" for r in chart_data['failure_rates']]),
        total_runs=len(chart_data['failure_rates']) * 2 * 2,  # rates × agents × experiments approx
        improvement_class=summary_stats['improvement_class'],
        improvement=summary_stats['max_improvement'],
        avg_duration_baseline=summary_stats['avg_duration_baseline'],
        avg_duration_playbook=summary_stats['avg_duration_playbook'],
        avg_consistency_playbook=summary_stats['avg_consistency_playbook'],
        summary_tables=summary_tables,
        detailed_tables=detailed_tables,
        failure_rates_json=failure_rates_json,
        failure_rates_label_json=failure_rates_label_json,
        baseline_success_json=baseline_success_json,
        playbook_success_json=playbook_success_json,
        latency_overhead_json=latency_overhead_json,
        baseline_consistency_json=baseline_consistency_json,
        playbook_consistency_json=playbook_consistency_json,
        effectiveness_improvement_json=effectiveness_improvement_json,
        consistency_improvement_json=consistency_improvement_json,
    )
    
    # Write dashboard
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html)
    
    print(f"✅ Dashboard generated successfully!")
    print(f"   Location: {output_path}")
    print(f"   Size: {output_path.stat().st_size / 1024:.1f} KB\n")
    print(f"🌐 Open in browser: file:///{output_path.resolve()}\n")


def find_latest_run(results_dir: Path) -> Path:
    """Find the most recent run directory."""
    run_dirs = sorted([d for d in results_dir.iterdir() if d.is_dir() and d.name.startswith('run_')])
    if not run_dirs:
        raise FileNotFoundError("No run directories found")
    return run_dirs[-1]


def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Generate interactive HTML dashboard from parametric experiment results",
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
        '--output',
        type=str,
        default=None,
        help='Custom output path for dashboard (default: <run_dir>/dashboard.html)'
    )
    
    return parser.parse_args()


def main():
    """Main entry point."""
    args = parse_arguments()
    
    # Determine run directory
    results_base = Path.cwd() / "results" / "parametric_experiments"
    
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
    
    # Determine output path
    if args.output:
        output_path = Path(args.output)
    else:
        output_path = run_dir / "dashboard.html"
    
    # Generate dashboard
    try:
        generate_dashboard(metrics_path, output_path)
    except Exception as e:
        print(f"\n❌ ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
