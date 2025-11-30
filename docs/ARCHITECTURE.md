# 🏗️ System Architecture: Chaos Playbook Engine

> **Architecting for Resilience: A Hybrid Deterministic/Probabilistic Engine**

**Version:** 4.0 (Phase 5 Validated)
**Date:** November 24, 2025
**Status:** Production-Ready (SRC-Layout Compliant)

-----

## 1\. High-Level Design: The Hybrid Engine Strategy

The Chaos Playbook Engine solves the fundamental tension in Agentic AI: **Reasoning (LLMs) is probabilistic, but Reliability (SRE) must be deterministic.**

We architected a **Hybrid Engine** that decouples these concerns into two distinct layers:

1.  **The Deterministic Core (`src/chaos_engine/simulation`)**: A mathematically rigorous laboratory that executes chaos experiments. It uses seed-controlled randomness to ensure 100% reproducibility.
2.  **The Probabilistic Brain (`src/chaos_engine/agents`)**: An LLM-based reasoning layer (Google Gemini 2.0 Flash) that consults the playbook. It does *not* invent recovery strategies; it *retrieves* them.

### System Data Flow

```mermaid
graph TD
    User[CLI User] -->|1. Run Simulation| CLI[CLI Entrypoint]
    CLI -->|2. Instantiate| Runner[Parametric Runner]
    
    subgraph "Deterministic Core (The Lab)"
    Runner -->|3. Generate Chaos| Proxy[Chaos Proxy (Middleware)]
    Proxy -->|4. Inject Failure (503/429)| Agent[Petstore Agent]
    end
    
    subgraph "Resilience Layer"
    Agent -->|5. Fails?| CB[Circuit Breaker]
    CB -->|6. Consult| RAG[Playbook Storage (JSON)]
    RAG -->|7. Return Strategy| Agent
    end
    
    Agent -->|8. Retry with Jitter| Proxy
    Proxy -->|9. Success| Metrics[Streaming Aggregator]
```

-----

## 2\. Directory Structure Strategy: The `src-layout`

We adopted the Python **`src-layout` standard** to enforce a strict separation between **Application Logic**, **Execution Contexts**, and **Data Assets**. This prevents import side-effects and ensures the engine is packaged as a reusable library (`pip install chaos-engine`), not just a collection of scripts.

| Layer | Path | Responsibility | Architectural Driver |
| :--- | :--- | :--- | :--- |
| **Logic** | `src/chaos_engine/` | Pure Python package. Contains domain logic, agents, and core infrastructure. | **Reusability**: Can be imported by other projects. |
| **Interface** | `cli/` | Executable scripts (`run_simulation.py`, `run_comparison.py`). | **Isolation**: CLI concerns do not pollute domain logic. |
| **Data** | `assets/` | JSON Playbooks, OpenAPI specs, Knowledge Base. | **Immutability**: Code and configuration are separated. |
| **Config** | `config/` | Environment-specific YAMLs (`dev.yaml`, `prod.yaml`). | **12-Factor App**: Config varies by deployment. |

-----

## 3\. Design Patterns & Engineering Excellence

This architecture was built to withstand the rigors of 14,000 continuous experiments. We prioritized stability and observability over complexity.

### A. Dependency Injection (Decoupling)

We completely decoupled the Agent from the Network layer. The `PetstoreAgent` does not instantiate `ChaosProxy` internally.

  * **Implementation:** In `cli/run_comparison.py` , we instantiate the `tool_executor` (the network layer) and inject it into the Agent's constructor.
  * **Why it matters:** This allows us to swap the Real API for a Mock, or a standard HTTP client for a Circuit Breaker, without changing a single line of the Agent's code. This is essential for unit testing and deterministic simulation.

### B. Resilience Layer (SRE Best Practices)

We implemented reliability patterns directly into the infrastructure code (`src/chaos_engine/core/resilience.py`), treating reliability as a cross-cutting concern.

1.  **Circuit Breaker Proxy:** Wraps the network calls. If the downstream service fails 3 times consecutively, the breaker **Opens**, rejecting traffic immediately to prevent cascading failures and allow the system to recover .
2.  **Jittered Backoff:** Retries are not static. We calculate a randomized "jitter" (`base_delay + random_offset`) to desynchronize retry attempts . This prevents the "Thundering Herd" problem in distributed systems.

### C. GreenOps: Memory-Efficient Streaming

Running 10,000+ experiments can exhaust RAM if results are stored in memory.

  * **Implementation:** The `ParametricABTestRunner` uses **Python Generators (`yield`)** to process experiments one by one .
  * **Result:** Data is streamed directly to disk (`raw_results.csv`) immediately after execution. The memory footprint remains **O(1)** regardless of whether we run 10 or 10 million experiments.

### D. Cognitive Simplicity

We enforce **Cognitive Complexity \< 8** for all critical functions.

  * **Technique:** Heavy use of **Guard Clauses** (returning early) to avoid deep nesting `if/else` blocks.
  * **Typing:** 100% strict type hints using `Protocol` and `TypedDict`. We do not use `Any`. This turns runtime errors into build-time errors.

-----

## 4\. Google ADK Native Integration

We utilize the **Agent Development Kit (ADK)** idiomatically, avoiding "wrapper hell."

  * **`InMemoryRunner`:** Used for the simulation loop. Its lightweight nature allows us to spin up and tear down agents in milliseconds , enabling high-throughput testing.
  * **`AgentEvaluator`:** We use the ADK's native evaluation capabilities. By patching the network layer dynamically , we feed "Golden Datasets" to the evaluator to score agent trajectories automatically.
  * **`LlmAgent`:** The core unit of reasoning. We configure it with a strict system prompt ("DETERMINISTIC WORKFLOW ENGINE") to constrain LLM hallucinations during critical phases .

-----

**Status:** Validated Architecture.
**Evidence:** 1000 parametric experiments executed successfully without memory leaks or race conditions.