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

## 4\. Visualizing Results (The Dashboard)

Every simulation generates a self-contained HTML dashboard. You don't need a server to view it.

### Finding the Dashboard

Navigate to the `reports/` directory. Each run has its own folder:
`reports/parametric_experiments/run_YYYYMMDD_HHMMSS/dashboard.html`

### Interpreting the Charts

1.  **Success Rate Curve:** Look for the gap between the red line (Baseline) and green line (Playbook). A widening gap indicates higher resilience value.
2.  **Latency Overhead:** This shows the "cost" of resilience. Expect the Playbook line to be higher (retries take time).
3.  **Consistency:** Bars show data corruption events. The Playbook bars should be near zero.

### Regenerating Reports

If you need to re-generate the HTML from existing data:

```bash
python cli/generate_report.py --latest
# OR
python cli/generate_report.py --run-dir run_20251129_144331
```

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
session_service:
  type: DatabaseSessionService # Persist logs if needed
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