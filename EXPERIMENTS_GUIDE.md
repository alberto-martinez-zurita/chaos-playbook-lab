# Experimentation Framework Documentation

This guide outlines the usage of the Python scripts designed to run simulated experiments, compare agents, and generate analysis reports. All scripts should be executed via `poetry run`.

-----

## 1\. Simulated Experiments

Use this script to run parametric experiments across various failure rates to test system robustness.

### Usage

```bash
poetry run python scripts/run_parametric_experiments.py \
  --failure-rates 0.0 0.01 0.03 0.05 0.10 0.15 0.20 0.25 0.30 \
  --experiments-per-rate 100
```

### Parameters

  * **`--failure-rates`**: A space-separated list of float values representing the probability of failure to simulate (e.g., `0.10` is a 10% failure rate).
  * **`--experiments-per-rate`**: The integer number of iterations to run for each defined failure rate.

### Outputs

The script creates a timestamped directory (e.g., `run_20251126_143430`) containing:

  * `aggregated_metrics.json`: High-level summary statistics of the run.
  * `raw_results.csv`: Detailed data for every single iteration.

-----

## 2\. Agent Experiments

Use this script to perform A/B testing between two specific agent configurations (e.g., a simulated playbook vs. an LLM-based agent).

### Usage

```bash
poetry run python scripts/run_agent_comparison.py \
  --agent-a petstore_agent \
  --playbook-a data/playbook_petstore_strong.json \
  --agent-b petstore_agent \
  --playbook-b data/playbook_petstore_weak.json \
  --failure-rates 0.10 \
  --experiments-per-rate 5 \
  --seed 42
```

### Parameters

  * **`--agent-a`**: The identifier for the first agent/strategy.
  * **`--agent-b`**: The identifier for the second agent/strategy.
  * **`--playbook-a`**: The playbook for the first agent/strategy.
  * **`--playbook-b`**: The playbook for the second agent/strategy.
  * **`--failure-rates`**: The specific failure rate(s) under which to compare the agents.
  * **`--experiments-per-rate`**: How many trials to run per agent per failure rate.
  * **`--seed`**: The seed for the random experiment.
  
### Outputs

Files are saved in a new timestamped directory:

  * `aggregated_metrics.json`
  * `raw_results.csv`

-----

## 3\. Experiment Dashboard (.HTML)

Generate an interactive HTML dashboard to visualize the results of either parametric experiments or agent comparisons.

### Usage

**Option A: Visualize the most recent run**

```bash
poetry run python scripts/generate_dashboard.py --latest
```

**Option B: Visualize a specific run**

```bash
poetry run python scripts/generate_dashboard.py --run-dir run_YYYYMMDD_HHMMSS
```

### Output

  * `dashboard.html`: An interactive file located inside the specific run directory. Open this file in any web browser.

-----

## 4\. Static Reporting (.MD)

Generate static assets (plots) and a Markdown summary report for documentation. This is a two-step process.

### Step A: Generate Plots

Create visualization graphs from the raw data.

**For the latest run:**

```bash
poetry run python scripts/generate_parametric_plots.py --latest
```

**For a specific run:**

```bash
poetry run python scripts/generate_parametric_plots.py --run-dir run_20251126_143430
```

  * **Output:** A `\plots` subdirectory containing `.png` visualizations.

### Step B: Generate Markdown Report

Compile metrics and plots into a readable report.

**For the latest run:**

```bash
poetry run python scripts/generate_parametric_report.py --latest
```

**For a specific run:**

```bash
poetry run python scripts/generate_parametric_report.py --run-dir run_20251126_143430
```

  * **Output:** `report.md` located in the run directory.

-----

### Summary of Directory Structure

After running the full pipeline, your results folder will look like this:

```text
results/
└── parametric_experiments/
    └── run_YYYYMMDD_HHMMSS/
        ├── raw_results.csv
        ├── aggregated_metrics.json
        ├── dashboard.html
        ├── report.md
        └── plots/
            ├── agent_comparison_bars.png
            ├── duration_comparison.png
            ├── inconsistencies_comparison.png
            └── success_rate_comparison.png
```
