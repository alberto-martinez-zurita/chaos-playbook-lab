# 🤝 Join the Chaos Playbook Engine Lab

> **"Help us build the immune system for the Agentic Web."**

Welcome to the frontier of **Automated AI Resilience**. We aren't just building a tool; we are pioneering a new scientific discipline: **Prompt Science & Chaos Engineering**.

This project proves that **reliability is not an accident**—it is a measurable, optimizable property of AI systems. If you care about building robust agents that don't crash when APIs timeout, you belong here.

-----

## 🚀 The Vision: Why Contribute?

Most AI development is "Happy Path" engineering. We are the opposite. We build for the **20% of the time when everything breaks**.

By contributing, you are helping to solve the hardest problem in Agentic AI: **Reliability at Scale**.

  * **We don't guess; we test.** We use brute-force parametric experimentation to find truth.
  * **We don't patch; we synthesize.** We use LLMs to write their own recovery playbooks.
  * **We don't hack; we engineer.** We adhere to Elite Engineering Standards (SRE, FinOps, Cognitive Simplicity).

-----

## ⚡ Development Setup

We use a modern, standards-compliant Python stack. You can be up and running in **2 minutes**.

### Prerequisites

  * Python 3.11+
  * Poetry (Dependency Management)
  * Google Cloud API Key (for Gemini models)

### Quick Start

```bash
# 1. Clone the Lab
git clone https://github.com/alberto-martinez-zurita/chaos-playbook-engine.git
cd chaos-playbook-engine

# 2. Install Dependencies (Poetry handles virtualenvs automatically)
poetry install

# 3. Configure Environment
# Copy the example env and add your key
cp .env.example .env
# Edit .env to add GOOGLE_API_KEY=...

# 4. Run the Chaos Simulation
poetry run python cli/run_simulation.py \
  --failure-rates 0.0 0.1 \
  --experiments-per-rate 5 \
  --verbose

# 5. Run the Chaos Experiment
poetry run python cli/run_comparison.py \
  --failure-rates 0.0 0.1 \
  --experiments-per-rate 5 \
  --verbose
```

> **Note:** The simulation and comparison runs in `Mock Mode` by default. For simulation no API key is required. For comparison API Key is required.

-----

## 🗺️ Architecture Map: Where Things Live

We follow the strict `src-layout` pattern to separate **Logic** from **Execution** and **Data**.

| Directory | Purpose | Key Files |
| :--- | :--- | :--- |
| **`src/chaos_engine/`** | **The Brain.** Core logic, agents, and simulation engine. | `agents/petstore.py`, `chaos/proxy.py` |
| **`cli/`** | **The Hands.** Executable scripts and entry points. | `run_simulation.py`, `run_comparison.py` |
| **`assets/`** | **The Knowledge.** Data, playbooks, and scenarios. | `playbooks/training.json`, `knowledge_base/` |
| **`config/`** | **The Controls.** Environment settings. | `dev.yaml`, `prod.yaml` |
| **`tests/`** | **The Guardrails.** Pytest suites. | `unit/`, `integration/` |
| **`docs/`** | **The Documentation.** Arquitecture, ADRs and User Guide. | `docs/` |
-----

## 🛡️ Quality Standards (The Elite Code)

To maintain our **1000-experiment reliability** , we enforce strict engineering standards.

### 1\. 100% Type Safety

We do not use `Any`. We use **Protocols** and **TypedDicts** to define interfaces.

  * **Bad:** `def run(agent):`
  * **Good:** `def run(agent: ToolExecutor) -> Dict[str, Any]:`

### 2\. Resilience Injection

New tools must not make direct HTTP calls. They must use the injected `tool_executor` (which wraps `ChaosProxy` and `CircuitBreakerProxy`).

  * **Why:** This allows us to inject failures deterministically during testing .

### 3\. Determinism & Seeding

All stochastic processes (chaos injection, random choices) must accept a `seed` parameter.

  * **Rule:** `run_simulation.py --seed 42` must produce the *exact same* result on your machine as it does on CI/CD .

-----

## 🔭 Help Wanted: The Innovation Roadmap

We have ambitious plans (See `INNOVATION.md`). Pick a Horizon and start building\!

### 🧪 For Prompt Engineers: **"Horizon 1 - Prompt Science"**

  * **The Mission:** Use our `ParametricABTestRunner` to scientifically prove which system prompts yield higher reliability.
  * **The Task:** Extend `src/chaos_engine/simulation/parametric.py` to accept a list of `prompts` instead of `failure_rates`. Run 1000 experiments to find the "Perfect Prompt".

### ⚙️ For SREs & DevOps: **"Horizon 4 - Digital Twin"**

  * **The Mission:** Import real production logs to replay outages in the lab.
  * **The Task:** Build a log ingestor that converts Cloud Logging JSON into `assets/scenarios/production_replay.json` format for the `ChaosProxy` to consume.

### 🏗️ For Architects: **"Horizon 5 - Infrastructure as Product"**

  * **The Mission:** Turn our Python Proxy into a standalone API Gateway.
  * **The Task:** Containerize `src/chaos_engine/chaos/proxy.py` into a lightweight FastAPI service that sits in front of any agent, injecting chaos as a sidecar.

-----

## 📝 How to Submit a PR

1.  **Fork & Branch:** `git checkout -b feat/my-awesome-feature`.
2.  **Test:** Ensure `poetry run pytest` passes (20+ tests).
3.  **Validate:** Run a small simulation (`cli/run_simulation.py`) to ensure no regression in resilience.
4.  **Document:** Update `README.md` or `INNOVATION.md` if you changed the architecture.

**Join us. Let's build software that learns from failure.**