# 📘 User Guide: Chaos Playbook Engine

**Welcome to the Laboratory.** This guide explains how to operate the Chaos Playbook Engine, run parametric simulations, and interpret the results.

---

## 1. Quick Start (The "Happy Path")

If you just want to verify the system works, run the standard simulation suite.

```bash
# Activate your environment (if not using Poetry directly)
source venv/bin/activate  # or .\venv\Scripts\Activate.ps1

# Run the unified simulation
python cli/run_simulation.py --failure-rates 0.0 0.1 0.2 --experiments-per-rate 5
````

**What happens?**

1.  The engine initializes the `OrderOrchestratorAgent`.
2.  It runs 5 baseline tests (no playbook) and 5 playbook tests for *each* failure rate (0%, 10%, 20%).
3.  It generates a report in `reports/parametric_experiments/run_TIMESTAMP/`.

-----

## 2\. Running Parametric Experiments

The `run_simulation.py` CLI is the heart of the scientific validation.

### Command Syntax

```bash
python cli/run_simulation.py [OPTIONS]
```

### Options Reference

| Argument | Description | Default | Example |
| :--- | :--- | :--- | :--- |
| `--failure-rates` | List of chaos probabilities (0.0 to 1.0) | Required | `0.0 0.05 0.1 0.2` |
| `--experiments-per-rate` | Number of runs per configuration | `5` | `100` (for rigor) |
| `--seed` | Integer seed for reproducibility | `42` | `1234` |
| `--verbose` | Enable detailed logs in console | `False` | `--verbose` |

### Example: The "Stress Test"

To replicate our scientific report (High confidence):

```bash
python cli/run_simulation.py \
  --failure-rates 0.0 0.1 0.2 0.3 \
  --experiments-per-rate 50 \
  --seed 42 \
  --verbose
```

-----

## 3\. Comparing Agents (A/B Testing)

Use `run_comparison.py` when you want to pit two specific agent configurations against each other (e.g., GPT-4 vs Gemini, or Strong Playbook vs Weak Playbook).

```bash
python cli/run_comparison.py \
  --agent-a-label "Baseline (No RAG)" \
  --playbook-a assets/playbooks/baseline.json \
  --agent-b-label "Pro (With RAG)" \
  --playbook-b assets/playbooks/training.json \
  --failure-rates 0.2 \
  --experiments-per-rate 10
```
-----

Aquí tienes la versión revisada y corregida de la sección **"4. Visualizing Results"** para tu `USER_GUIDE.md`.

Me he asegurado de que explique con precisión las responsabilidades de los tres scripts de reporte (`generate_report.py`, `generate_plots.py`, `generate_dashboard.py`) tal como se detalla en tu `EXPERIMENTS_GUIDE.md`, en lugar de la versión simplificada anterior.

-----

## 4\. Visualizing Results (The Dashboard)

Once you have raw data from your experiments, the Chaos Playbook Engine offers a suite of reporting tools to transform CSV logs into actionable insights. These scripts are located in `cli/` and handle different aspects of data visualization.

### A. Creating Custom Plots (`generate_plots.py`)

If you need specific charts for a presentation or paper (e.g., just the "Success Rate" curve without the rest), use this script. It uses Plotly to generate interactive HTML files for individual metrics.

**Use this when:** You want to customize or regenerate specific charts without re-calculating statistics.

```bash
# Generate all standard plots for a run
python cli/generate_plots.py --run-dir reports/parametric_experiments/run_20251129_144331

# Generate only the Success Rate chart
python cli/generate_plots.py --run-dir ... --plot-type success_rate
```

**Key Charts Produced:**

  * `plot_success_rate.png`: The resilience curve (Baseline vs. Playbook).
  * `plot_latency.png`: Execution time analysis with error bars.
  * `plot_consistency.png`: Data integrity violation rates.


### B. Generating a Full Scientific Report (`generate_report.py`)

This is the master script for end-to-end reporting. It orchestrates data aggregation, statistical analysis, and visualization in one go.

**Use this when:** You have just finished a large simulation and want the complete "Scientific Report" package.

```bash
# Generate report for the most recent run
python cli/generate_report.py --latest

# Generate report for a specific run directory
python cli/generate_report.py --run-dir reports/parametric_experiments/run_20251129_144331
```

**What it does:**

1.  **Aggregates Data:** Reads `raw_results.csv` and computes mean, standard deviation, and confidence intervals for every failure rate.
2.  **Generates JSON:** Saves statistical summaries to `aggregated_metrics.json`.
3.  **Creates Visuals:** Calls the plotting engine to generate the HTML dashboard.


### C. Building the Interactive Dashboard (`generate_dashboard.py`)

This script assembles all generated plots and metrics into a single, self-contained HTML file (`dashboard.html`). It creates the "Control Center" view that you see in the README.

**Use this when:** You have the plots and JSON metrics but need to bundle them into a shareable artifact.

```bash
python cli/generate_dashboard.py --run-dir reports/parametric_experiments/run_20251129_144331
```

**The Output:**

  * A single file: `dashboard.html`.
  * Contains embedded interactive charts (zoom, pan, hover).
  * Includes summary tables of the "Killer Metrics" (ROI, Consistency Improvement).
  * **Zero-dependency:** You can email this file to a stakeholder, and it will open in any browser.

-----

**Summary of Workflow:**
Typically, you only need to run `run_simulation.py` (which auto-triggers reporting) or `generate_report.py` (to manually rebuild). The other scripts (`generate_plots`, `generate_dashboard`) are modular components available for advanced users who need granular control over the visualization pipeline.

-----

## 5\. Configuration (Advanced)

The engine behavior is controlled by YAML files in `config/`.

### `config/dev.yaml`

Use this to tweak the agent model or session backend.

```yaml
environment: dev
agent:
  model: gemini-2.5-flash-lite  # Change LLM here
runner:
  type: InMemoryRunner         # Best for simulations
```

### `assets/playbooks/`

This is the "Brain" of the agent. You can edit `training.json` to add new recovery strategies.

```json
"503": {
  "strategy": "wait",
  "reasoning": "Service Unavailable usually clears in seconds.",
  "config": {
    "wait_seconds": 5,
    "max_retries": 3
  }
}
```