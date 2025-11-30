# 🏛️ Chaos Playbook Engine: Architectural Wiki

> **Living Documentation of Resilience Engineering**
> *Based on CLEAR Framework Level 5 (Elite) Standards*

Welcome to the project's digital brain. This wiki breaks down the architecture, design patterns, and internal logic of the Chaos Engine. It is designed to provide a deep understanding of *why* the system is robust, modular, and efficient.

-----

## 📑 Navigation Index

1.  [Territory Map (Structure)](https://www.google.com/search?q=%231-territory-map-structure)
2.  [Data Flow (Architecture)](https://www.google.com/search?q=%232-data-flow-architecture)
3.  [Core Component Catalog](https://www.google.com/search?q=%233-core-component-catalog)
      * [Agents: PetstoreAgent](https://www.google.com/search?q=%23class-petstoreagent)
      * [Chaos: ChaosProxy](https://www.google.com/search?q=%23class-chaosproxy)
      * [Resilience: CircuitBreakerProxy](https://www.google.com/search?q=%23class-circuitbreakerproxy)
      * [Simulation: ParametricABTestRunner](https://www.google.com/search?q=%23class-parametricabtestrunner)
      * [Memory: PlaybookStorage](https://www.google.com/search?q=%23class-playbookstorage)
4.  [Extension Guide (Future-Proofing)](https://www.google.com/search?q=%234-extension-guide-future-proofing)

-----

## 1\. Territory Map (Structure)

The project strictly follows the `src-layout` pattern to ensure business logic is decoupled from execution scripts and data assets.

```text
chaos-playbook-engine/
├── assets/                  # 💾 DATA (Immutable)
│   ├── knowledge_base/      # Source documents for RAG
│   ├── playbooks/           # Recovery strategies (JSON)
│   └── scenarios/           # Chaos definitions
├── cli/                     # 🎮 EXECUTION (Entry Points)
│   ├── run_simulation.py    # Main script for massive parametric experiments
│   └── run_comparison.py    # Script to compare Agent A vs B
├── config/                  # ⚙️ CONFIGURATION (12-Factor App)
│   ├── dev.yaml             # Local environment config
│   └── prod.yaml            # Production config
├── src/                     # 🧠 LOGIC (The Core)
│   └── chaos_engine/
│       ├── agents/          # Agent implementations (LlmAgent)
│       ├── chaos/           # Failure injection (Proxy)
│       ├── core/            # Infrastructure (Logging, Resilience)
│       ├── reporting/       # Dashboard generation (Plotly)
│       └── simulation/      # Parametric execution engine
└── tests/                   # 🛡️ GUARDRAILS (Pytest)
```

-----

## 2\. Data Flow (Architecture)

The system operates as a **Hybrid Laboratory**: a deterministic execution core wraps a probabilistic brain (LLM).

```mermaid
graph TD
    Runner[ParametricRunner] -->|1. Init Experiment| Chaos[ChaosProxy]
    
    subgraph "Resilience Core (Dependency Injection)"
    Chaos -->|2. Intercept & Fail (503)| CB[CircuitBreaker]
    CB -->|3. Pass Call| Agent[PetstoreAgent]
    end
    
    Agent -->|4. Detect Error| Memory[PlaybookStorage]
    Memory -->|5. Return Strategy (RAG)| Agent
    
    Agent -->|6. Execute Strategy (Jittered Retry)| Chaos
    Chaos -->|7. Success| Runner
    
    Runner -->|8. Stream Results| CSV[Raw CSV]
```

-----

## 3\. Core Component Catalog

Below is the engineering detail behind the critical classes in `src/chaos_engine`.

### Class: `PetstoreAgent`

**Location:** `src/chaos_engine/agents/petstore.py`

**Purpose:**
Acts as the workflow orchestrator. It is a hybrid agent that uses an LLM to reason about errors but follows a deterministic "happy path" for tool execution.

**Signature and Key Methods:**

| Method | Arguments | Return | Description |
| :--- | :--- | :--- | :--- |
| `__init__` | `tool_executor: ToolExecutor` | `None` | Constructor with **Dependency Injection**. |
| `run` | `objective: str` | `Dict[str, Any]` | Executes the OODA loop (Observe-Orient-Decide-Act). |
| `_execute_tool_safely` | `tool_name: str`, `args: Dict` | `ToolResult` | Defensive wrapper with exception handling. |

> **💎 CLEAR DNA (Quality):**
>
>   * **🧱 Pillar III (Modularity):** The agent **does not** instantiate tools or HTTP clients internally. It receives a `tool_executor` in the constructor. This allows injecting the `ChaosProxy` or mocks during tests without touching the agent code.
>   * **🧠 Pillar I (Cognitive):** The system prompt (`SYSTEM_PROMPT`) is structured using the **DIRECTOR** method (Delimiters, Instruction, Role), reducing ambiguity for the LLM.

-----

### Class: `ChaosProxy`

**Location:** `src/chaos_engine/chaos/proxy.py`

**Purpose:**
Middleware that intercepts tool calls and injects simulated failures (503, 429, Timeout) based on a configured failure rate and a deterministic seed.

**Signature and Key Methods:**

| Method | Arguments | Return | Description |
| :--- | :--- | :--- | :--- |
| `execute` | `tool_name: str`, `params: Dict` | `Dict` | Executes the real tool or raises a simulated exception. |
| `_should_fail` | `rate: float` | `bool` | Deterministically decides whether to fail using `random.Random(seed)`. |
| `calculate_jittered_backoff`| `attempt: int` | `float` | Calculates exponential wait time with random noise. |

> **💎 CLEAR DNA (Quality):**
>
>   * **🛡️ Pillar IV (SRE):** Implements **Jittered Backoff**. Instead of waiting fixed times, it adds randomness to prevent the "Thundering Herd" problem (synchronized retry avalanches) in distributed systems.
>   * **🛡️ Pillar V (Security):** Performs **Zero Trust** input validation, ensuring critical parameters (like IDs) are of the correct type before processing.

-----

### Class: `CircuitBreakerProxy`

**Location:** `src/chaos_engine/core/resilience.py`

**Purpose:**
Wraps the `ChaosProxy` to add stability. If it detects too many consecutive failures, it "opens the circuit" and rejects traffic immediately to allow the downstream system to recover.

**Key Methods:**

  * `execute(...)`: Checks the circuit state (`CLOSED`, `OPEN`, `HALF_OPEN`) before allowing execution.

> **💎 CLEAR DNA (Quality):**
>
>   * **🛡️ Pillar IV (SRE):** Canonical implementation of the **Circuit Breaker** pattern. Essential for preventing cascading failures in microservices architectures.

-----

### Class: `ParametricABTestRunner`

**Location:** `src/chaos_engine/simulation/parametric.py`

**Purpose:**
The laboratory engine. Executes thousands of experiments varying parameters (failure rate) and logging results.

**Signature and Key Methods:**

| Method | Arguments | Return | Description |
| :--- | :--- | :--- | :--- |
| `run_parametric_experiments`| `failure_rates: List[float]`, `n: int` | `None` | Orchestrates the massive simulation. |
| `_experiment_generator` | `None` | `Generator` | **Yields** results one by one. |

> **💎 CLEAR DNA (Quality):**
>
>   * **🍃 Pillar VI (GreenOps):** Uses **Python Generators (`yield`)** to process experiments. This allows running 14,000 tests while maintaining **O(1)** (constant) RAM consumption, instead of loading a giant list.
>   * **⚠️ Transparency Note:** The audit detected that while CSV writing is streamed, an `all_results_buffer` exists that accumulates metrics for the final report. *Optimization Opportunity:* Implement streaming aggregation to eliminate this buffer in simulations \>1M events.

-----

### Class: `PlaybookStorage`

**Location:** `src/chaos_engine/core/playbook_storage.py`

**Purpose:**
The RAG (Retrieval-Augmented Generation) component. Loads recovery strategies from JSON and serves them to the agent when a specific error occurs.

**Key Methods:**

  * `get_best_procedure(error_type: str)`: Searches for the most relevant strategy by keyword.

> **💎 CLEAR DNA (Quality):**
>
>   * **🧠 Pillar I (Cognitivo):** Decouples **recovery logic** (JSON data) from **execution logic** (Python code). This allows updating resilience strategies without redeploying the agent code.

-----

## 4\. Extension Guide (Future-Proofing)

The code is designed to be extended, not modified. Here is how to grow the system.

### A. Adding a New Tool

1.  Define the interface in `src/chaos_engine/agents/types.py` (using `TypedDict` for inputs/outputs).
2.  Implement the real logic in a class that adheres to the `ToolExecutor` protocol.
3.  Register the tool in `PetstoreAgent`.
4.  *Automatically*, `ChaosProxy` will be able to inject failures into it without additional changes.

### B. Implementing a New Chaos Strategy

1.  Edit `src/chaos_engine/chaos/types.py` to add the new error type (e.g., `HighLatency`).
2.  In `ChaosProxy`, add the logic in `_simulate_failure`.
3.  Update the Playbook JSON in `assets/playbooks/` with the corresponding countermeasure.
