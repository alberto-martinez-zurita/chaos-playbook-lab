# 🚀 Chaos Playbook Engine: The Resilience Laboratory
> **"Don't just survive the storm. Learn from it."**

[![Status](https://img.shields.io/badge/Status-Phase%206%20Complete%20✅-brightgreen)](https://github.com/google/adk-python)
[![Google ADK](https://img.shields.io/badge/Framework-Google%20ADK%20-blue)](https://google.github.io/adk-docs/)
[![Quality](https://img.shields.io/badge/Code%20Quality-CLEAR%20Level%205%20(Elite)-purple)](https://github.com/google/adk-samples)
[![Coverage](https://img.shields.io/badge/Test%20Coverage-92%25-green)](https://github.com/google/adk-python)
[![Experiments](https://img.shields.io/badge/Validated%20Runs-14%2C000-orange)](https://github.com/google/adk-samples)

<img src="chaos_playbook_engine.png" style="max-width: 800px; height: auto;">

**Chaos Playbook Engine** is an **AgentOps Laboratory** that systematically injects chaos into AI agents to discover failure modes and synthesize **RAG-based recovery playbooks**.

We moved beyond "prompt engineering" to **Parametric Engineering**. By running **1,000 controlled experiments** across 9 failure rates, we proved that agents equipped with our Playbook Engine achieve **98% reliability** in simulated agentic flows where standard agents fail.

---

## 📊 The "Killer" Metric: 100K ROI

We didn't just build an agent; we proved a thesis. Under realistic production chaos (20% API failure rate), the difference is catastrophic:

| Metric | Baseline Agent | Playbook Agent | Improvement |
| :--- | :--- | :--- | :--- |
| **Success Rate** | 37% (Fails 2/3 times) | **98% (Bulletproof)** | **+60%** 🚀 |
| **Data Consistency** | 26% inconsistent state | **2% inconsistent state** | **98% Safer** 🛡️ |
| **Revenue Impact** | Loss: $1,000 / 100 orders | **Full Recovery** | **100K ROI** 💰 |

> *Data Source: [`reports/parametric_experiments/run_20251129_144331`](./reports/parametric_experiments/run_20251129_144331/report.md) (14,000 total simulated agent ops).*<br>
> *Data Source: [`reports/parametric_experiments/run_20251129_231224`](./reports/parametric_experiments/run_20251129_231224/report.md) (280 total real agent ops with random mock api).*

---
## 📚 Documentation & Evidence

We believe in transparency and rigor. Explore the full project details:

  * 📖 **[Project Narrative (The Pitch)](./docs/CAPSTONE_NARRATIVE.md)**: The business case, ROI analysis, and problem statement.
  * 🏗️ **[System Architecture](./docs/ARCHITECTURE.md)**: Deep dive into the Hybrid Deterministic/Probabilistic engine, source layout, and design patterns.
  * 🏛️ **[Decision Records (ADRs)](./docs/ADR.md)**: The engineering trade-offs behind our architecture (Why JSON? Why Streaming Aggregation?).
  * 🔬 **[Scientific Report](./docs/SCIENTIFIC_REPORT.md)**: The empirical evidence from 14,000 parametric experiments (p \< 0.01).
  * 🔮 **[Innovation Roadmap](./docs/INNOVATION.md)**: Our vision for Prompt Science, PlaybookOps, and Digital Twins.
  * 📘 **[User Guide](./docs/USER_GUIDE.md)**: Detailed instructions for configuring chaos scenarios and interpreting dashboards.
  * 🛡️ **[CLEAR Audit Report](./docs/PROJECT_REPORT.md)**: A detailed audit of the code quality, SRE practices, and GreenOps compliance (Level 5 Elite).
  * 💻 **[Code Wiki](./docs/CODE_WIKI.md)**: A developer-centric guide to the codebase structure, classes, and extension points.

-----

## ⚡ Quick Start

Run the full parametric simulation in under 2 minutes. No Cloud credentials required (Mock Mode).

### 1. Installation
```bash
# Clone and enter
git clone [https://github.com/alberto-martinez-zurita/chaos-playbook-lab.git](https://github.com/alberto-martinez-zurita/chaos-playbook-lab)
cd chaos-playbook-engine

# Install dependencies (Poetry or Pip)
pip install -r requirements.txt
````

### 2\. Run the Laboratory

Execute 100 experiments across varying chaos levels (0% to 30%) with a single command:

```bash
# Run the Unified CLI
python cli/run_simulation.py \
  --failure-rates 0.0 0.1 0.2 \
  --experiments-per-rate 10 \
  --verbose
```

### 3\. View the Evidence

The engine generates a publication-ready HTML dashboard using Plotly and a report in markdown with the data.

```bash
# Open the interactive report
open .reports/parametric_experiments/run_*/report.md

# Open the interactive dashboard
open reports/parametric_experiments/run_*/dashboard.html
```

-----



## 🏗️ Architecture: Hybrid Deterministic + Probabilistic

We solve the "Hallucination vs. Reliability" dilemma by decoupling **Reasoning** (LLM) from **Recovery** (Playbook).

```mermaid
sequenceDiagram
    autonumber
    %% Definición de participantes con iconos para claridad
    actor Agent as 🤖 Order Agent
    participant Proxy as 💥 Chaos Proxy
    participant Strategy as 🧠 Strategy/RAG
    participant API as ☁️ Real API / Mock

    %% Step 1: El intento fallido
    Note over Agent, Proxy: 🛑 Phase 1: Chaos Injection
    Agent->>Proxy: Execute Tool (Request)
    activate Proxy
    Proxy--xAgent: Failure 503/429 (Simulated)
    deactivate Proxy

    %% Step 2: La recuperación (Reasoning)
    Note right of Agent: ⚠️ Agent error detection
    
    Agent->>Strategy: Retrieve Recovery Strategy
    activate Strategy
    Strategy-->>Agent: Return: "Apply Jittered Backoff"
    deactivate Strategy

    %% Step 3: Aplicación de la estrategia
    Note over Agent: ⏳ Waiting (Jittered Backoff)

    %% Step 4: El intento exitoso
    Note over Agent, Proxy: ✅ Phase 2: Recovery
    Agent->>Proxy: Retry Tool (New Request)
    activate Proxy
    Proxy->>API: Forward Request
    activate API
    API-->>Proxy: Success (200 OK)
    deactivate API
    Proxy-->>Agent: Return Data
    deactivate Proxy

```
<br>

  * **`src/chaos_engine/agents`**: The actors. Uses **Google ADK `LlmAgent`** for reasoning over complex failures .
  * **`src/chaos_engine/chaos`**: The adversary. A **Chaos Proxy** that injects failures deterministically (Seed-controlled) .
  * **`assets/playbooks`**: The knowledge. A JSON-based RAG layer containing proven recovery strategies .

-----

## 🛡️ Engineering Excellence (CLEAR Level 5)

This codebase follows the **CLEAR Framework** for Elite Software Quality, audited for the Enterprise Track judges.

### 🧠 Pillar I: Cognitive Maintainability

  * **Type Safety:** 100% strictly typed Python (`Protocol`, `TypedDict`). No `Any`.
  * **Flat Structure:** Logic flows are linear. Cognitive Complexity is strictly \< 8 per function.

### 🧱 Pillar II: Modularity & DI

  * **Dependency Injection:** The `PetstoreAgent` never instantiates its dependencies. We inject `CircuitBreakerProxy` and `ChaosProxy` at runtime , making the system 100% testable without mocking the universe.

### 🔧 Pillar III: SRE & Reliability

  * **Circuit Breakers:** Implemented in `core/resilience.py`. Opens after 3 failures to protect downstream services .
  * **Jittered Backoff:** Retries utilize randomized jitter to prevent "thundering herd" attacks on APIs .

-----

## 🗺️ Roadmap: From Lab to Auto-Evolution

We are currently at **Phase 6 (Validated)**. Here is where we are going:

| Phase | Goal | Key Innovation | Status |
| :--- | :--- | :--- | :--- |
| **Phase 5** | **Evidence Base** | **"Parametric Testing"** (1000 runs) | ✅ **Done** |
| **Phase 6** | **Reasoning** | **"Google Gemini 2.5"** Flash Lite Integration and **"Real Comparison Test"** | ✅ **Done** |
| **Phase 7** | **Production** | **"Cloud Run + Real APIs"** (Stripe/Google) | 🚀 Posible evolution |
| **Phase 8** | **Evolution** | **"Playbook As A Software"**, playbook lifecycle until production | 🚀 Posible evolution |
| **Phase 8** | **Evolution** | **"Triple-Agent Comparison Lab"**, training in an adversay way | 🚀 Posible evolution |
| **Phase 9** | **Evolution** | **"Agent Judge"**: Auto-writes Playbooks from production observability| 🚀 Posible evolution |
| **Phase 10** | **Evolution** | **"Prompt Engineering Playbooks for Agents"**, an engine to test prompts with same philosophy | 🚀 Posible evolution |

-----

## 🏆 Why We Win

1.  **We have the Data:** Not a demo; a scientific study with **14,000 data points**.
2.  **We have the Code:** Enterprise-grade architecture compliant with **Google ADK** and **Quality Standards**.
3.  **We have the Vision:** We aren't just handling errors; we are automating the creation of resilient software. <BR>
- Chaos Playbook strategy of procedural RAG can be applied for **"A2A integration"**<BR>
- Test agents with diferents **"prompts enabling evaluation"**
- Deploy **"Procedural RAG As A Software"** to enhancement production agents without stop the agent in runtime, adding tested new procedures in live mode
<BR><BR>
```
Chaos Playbook Engine. Built using Google Agent Development Kit.
