# 🏛️ Architecture Decision Records (ADRs)

> **Documenting the Engineering Journey of the Chaos Playbook Engine**
> *Decisions made to balance Reliability, Scalability, and Scientific Rigor.*

-----

## ADR-001: The Hybrid Engine Strategy (Deterministic Core vs LLM Brain)

  * **Status:** ✅ Accepted & Validated
  * **Context:**
    We needed to build an agent system that could be **scientifically validated** (N=1000 experiments) but also capable of **complex reasoning** in production.
      * *Problem:* Pure LLM agents are non-deterministic, slow, and expensive to test at scale. Pure script-based agents are brittle and cannot adapt to novel errors.
  * **Decision:**
    Adopt a **Hybrid Architecture**.
    1.  **Deterministic Core (`src/chaos_engine/simulation`):** Python-based orchestration for the "Happy Path" and Chaos Injection.
    2.  **Probabilistic Brain (`src/chaos_engine/agents`):** LLM (Gemini 2.0) is invoked *only* for reasoning about errors and retrieving recovery strategies.
  * **Rejected Alternatives:**
      * ❌ **Full LLM Loop:** Using the LLM for every step (including chaos injection). *Reason:* Too slow (5s/op), costly, and impossible to reproduce errors deterministically for A/B testing.
  * **Consequences:**
      * 🟢 **Positive Impact:** Enabled running 14,000 experiments in \<10 hours with 100% reproducibility.
      * 🟠 **Trade-off/Cost:** Increases code complexity by requiring a strict interface between the Python Core and the LLM Agent.
  * **Compliance:** Hybrid Deterministic + Probabilistic Architecture

-----

## ADR-002: `src-layout` & Dependency Injection

  * **Status:** ✅ Accepted & Validated
  * **Context:**
    To support massive parametric testing, we needed to swap real network calls with simulated chaos proxies seamlessly.
      * *Problem:* Standard import patterns often lead to coupled code where `Agent` classes instantiate `HTTPClient` directly, making mocking difficult.
  * **Decision:**
    1.  Enforce **`src-layout`** project structure to isolate logic from execution.
    2.  Use strict **Dependency Injection (DI)**. The `PetstoreAgent` accepts a `tool_executor` protocol in its constructor.
  * **Rejected Alternatives:**
      * ❌ **Global Singletons:** Using a global `API_CLIENT` variable. *Reason:* Prevents running parallel tests with different chaos configurations.
      * ❌ **Monkeypatching:** Patching imports at runtime. *Reason:* Fragile and breaks type checking.
  * **Consequences:**
      * 🟢 **Positive Impact:** Allowed us to wrap the `ChaosProxy` inside a `CircuitBreakerProxy` and inject the stack into the Agent without changing Agent code.
      * 🟠 **Trade-off/Cost:** Requires more boilerplate code in the entry points (`cli/run_comparison.py`) to wire up the dependencies.
  * **Standard:** Separation of Concerns (SoC)

-----

## ADR-003: Resilience-as-Middleware (The Proxy Pattern)

  * **Status:** ✅ Accepted & Validated
  * **Context:**
    Agents need to be resilient, but polluting business logic with `try/except` blocks makes code unreadable and hard to maintain.
  * **Decision:**
    Implement resilience patterns (Chaos Injection, Circuit Breaking) as **Middleware Proxies** that wrap the tool execution interface.
  * **Rejected Alternatives:**
      * ❌ **In-Agent Retry Logic:** Writing retry loops inside `PetstoreAgent`. *Reason:* Violates Single Responsibility Principle. Hard to reuse across different agents.
      * ❌ **Decorator-based Retries:** Using `@retry` decorators. *Reason:* Static configuration doesn't allow dynamic chaos injection or adaptive backoff strategies.
  * **Consequences:**
      * 🟢 **Positive Impact:** Achieved **Resilience Best Practice**. Circuit Breakers protect downstream services automatically.
      * 🟠 **Trade-off/Cost:** Debugging stack traces involves traversing multiple proxy layers.
  * **Standard:** SRE & Reliability

-----

## ADR-004: GreenOps Streaming Aggregation

  * **Status:** ✅ Accepted & Validated
  * **Context:**
    Running parametric tests involves thousands of iterations. Loading 14,000 result objects into memory to calculate a mean causes OOM (Out of Memory) errors on standard hardware.
  * **Decision:**
    Use **Python Generators (`yield`)** and **Streaming Aggregation**. Results are written to CSV line-by-line, and metrics are updated incrementally.
  * **Rejected Alternatives:**
      * ❌ **Pandas DataFrames:** Loading the full dataset into Pandas. *Reason:* Memory footprint grows linearly with experiment count ($O(N)$).
      * ❌ **Database Logging:** Writing to SQLite. *Reason:* Adds unnecessary I/O overhead for a CLI tool.
  * **Consequences:**
      * 🟢 **Positive Impact:** Memory usage remains **O(1)** (constant) even when scaling from 1,000 to 1,000,000 experiments.
      * 🟠 **Trade-off/Cost:** Implementing streaming variance/standard deviation algorithms (Welford's algorithm) is more complex than `numpy.std()`.
  * **Standard:** Resource Efficiency (GreenOps)

-----

## ADR-005: JSON-Based RAG (The "Boring Solution")

  * **Status:** ✅ Accepted & Validated
  * **Context:**
    We needed a way for the Agent to retrieve recovery strategies based on error types (e.g., "503 Service Unavailable").
  * **Decision:**
    Use a **Local JSON Key-Value Store** (`assets/playbooks/training.json`) as the initial RAG implementation.
  * **Rejected Alternatives:**
      * ❌ **Vector Databases (Pinecone/Chroma):** *Reason:* Massive overkill for \<100 recovery rules. Introduces network latency and deployment complexity incompatible with a standalone CLI.
      * ❌ **Hardcoded Dicts:** *Reason:* Strategy updates would require code deploys. JSON allows hot-swapping strategies.
  * **Consequences:**
      * 🟢 **Positive Impact:** Ultra-low latency retrieval (\<10ms) essential for high-throughput simulation. Zero external dependencies.
      * 🟠 **Trade-off/Cost:** Limited to keyword matching. Cannot handle semantic nuance (e.g., "Connection Reset" vs "Network Error") without manual aliases. (Addressed in Phase 8 Roadmap).
  * **Compliance:** PlaybookStorage Implementation

-----

## ADR-006: Parametric Testing Methodology

  * **Status:** ✅ Accepted & Validated
  * **Context:**
    "It works on my machine" is not acceptable for enterprise software. We needed statistical proof of reliability.
  * **Decision:**
    Implement a **Parametric Sweep** methodology. Fix a `seed`, then sweep failure rates from 0.0 to 0.3 in 0.05 increments, running 100 experiments at each step.
  * **Rejected Alternatives:**
      * ❌ **Unit Testing:** *Reason:* Deterministic tests cannot verify behavior under stochastic failure conditions.
      * ❌ **Random Chaos:** *Reason:* Without seed control, results are not reproducible, making it impossible to prove improvement between versions.
  * **Consequences:**
      * 🟢 **Positive Impact:** Generated the datasets required for the **Scientific Report**, proving statistical significance ($p < 0.01$).
      * 🟠 **Trade-off/Cost:** High compute time (approx. 55 mins for full suite). Mitigated by `InMemoryRunner` speed.
  * **Compliance:** Scientific Report Methodology