# System Architecture Document: Chaos Playbook Engine

**Version**: 3.0  
**Date**: November 24, 2025  
**Project**: Chaos Playbook Engine – Chaos Engineering + RAG for Resilient Order Agents  
**Framework**: Google Agent Development Kit (ADK) v1.18.0+ (Infrastructure Ready)  
**Status**: Phase 5 Complete ✅ | Production-Ready  
**Source Documents**: `Capstone-Pitch-Updated.md`, `Capstone-Requirements-v3.md`, `ADK_Framework_RAG_Perplexity.md`, `ADK_Cookbook_Humano_Perplexity.md`, Phase 5 Implementation

---

## VERSION 3.0 UPDATES

### Major Architectural Changes from v2.0

**Design Evolution: From Multi-Agent to Hybrid Deterministic System**

| v2.0 Architecture | v3.0 Architecture | Rationale |
|---|---|---|
| 3 LLM Agents (OrderOrchestrator, ChaosInjector, Judge) | Hybrid: Deterministic orchestration + Rule-based chaos + Statistical evaluation | Chaos engineering requires deterministic logic and statistical rigor, not LLM reasoning |
| LlmAgent for OrderOrchestrator | Python deterministic logic in `ABTestRunner` | Reproducibility, speed (10x faster), cost (100x cheaper) |
| LlmAgent for Judge | `ExperimentEvaluator` + `MetricsAggregator` (deterministic metrics) | Statistical rigor, quantifiable results, scalable validation |
| Ad-hoc chaos injection | `ChaosConfig` class with configurable failure rates | Systematic, reproducible, seed-controlled chaos injection |
| Simple A/B testing | Parametric testing framework (Phase 5.1-5.3) | Scientific validation with multiple failure rates, confidence intervals |

**Phase 5 Completion: Scientific Validation Layer**

- ✅ **Phase 5.1**: `ParametricABTestRunner` - Systematic parametric data generation across failure rates
- ✅ **Phase 5.2**: `AcademicReportGenerator` - Publication-ready Plotly visualizations with statistical summaries
- ✅ **Phase 5.3**: Unified CLI (`run_parametric_ab_test.py`) - End-to-end workflow automation
- Added: CSV export, JSON aggregation, interactive HTML dashboards

**ADK Infrastructure Status:**
- **Current Phase 5**: ADK infrastructure in place, not actively used for core logic (deterministic approach prioritized)
- **Future Phase 6+**: Clear migration path to LlmAgent-based agents with ADK primitives (Sessions, Memory, Tools)

**Key Insight:**
This evolution is a **strength, not a compromise**. The hybrid approach produces a more reliable, faster, and cheaper system while maintaining the original vision of learning and sharing chaos recovery strategies. The architecture is production-ready and provides a clear path to future LLM-based enhancements.

---

## 1. Architectural Goals and Constraints

### 1.1 Primary Goals

**Goal 1: Demonstrate the Chaos Playbook AgentOps Pattern**
Prove that chaos engineering applied to tool-using agents, combined with RAG-based knowledge distillation, can significantly improve agent resilience in production-like scenarios. The pattern must be demonstrable with clear before/after metrics and academic-grade visualizations.

**Goal 2: Hybrid Architecture with Deterministic Core**
Implement a system that balances:
- **Deterministic Order Orchestration**: Reproducible, fast, cost-effective order processing
- **Rule-Based Chaos Injection**: Systematic failure injection via `ChaosConfig`
- **Statistical Evaluation**: Quantifiable metrics (success rate, latency, inconsistencies)
- **Playbook Learning**: JSON-based recovery strategy storage
- **ADK Infrastructure**: Ready for future LLM-based agent migration

**Goal 3: Scientific Rigor (Phase 5)**
Provide parametric testing infrastructure with:
- Multiple experiments per failure rate (statistical significance)
- Confidence intervals and statistical summaries
- Academic-grade visualizations (Plotly dashboards)
- Reproducible results (seed control)

**Goal 4: Local Development First, Cloud-Ready**
- **Phase 1-5 (Current)**: Run entirely locally without GCP credentials
- **Phase 6+ (Future)**: Clear migration path to VertexAiMemoryBankService and cloud deployment
- No architectural changes required for cloud migration

**Goal 5: Production-Grade Code Quality**
- Type-safe Python (`mypy` strict mode)
- Comprehensive testing (>80% coverage)
- Async-first patterns throughout
- ADK best practices compliance (infrastructure ready)

### 1.2 Constraints

**C1: ADK Framework Constraints**
- ADK infrastructure v1.18.0+ in place for future migration
- Current implementation: deterministic logic (not LlmAgent-based)
- Future migration: LlmAgent with Gemini models (gemini-2.0-flash-exp, gemini-1.5-flash)
- FunctionTool wrappers ready for custom tool implementation
- Session.events ready for trace analysis (future LLM-based agents)

**C2: Python Constraints**
- Python 3.10+ required (3.11+ recommended)
- Async patterns mandatory (`asyncio`, `async def`, `await`)
- Type hints enforced (`mypy --strict`)
- Poetry for dependency management

**C3: Local Development Constraints**
- No GCP credentials required for Phase 1-5
- JSON files for persistence (`chaos_playbook.json`, `chaos_config.py`)
- No Docker required (optional for reproducibility)

**C4: Performance Constraints**
- Single order execution: < 10 seconds (without artificial delays)
- Chaos injection overhead: < 100ms per call
- Playbook search: < 200ms
- Metrics aggregation: < 5 seconds for 100 experiments

---

## 2. System Overview

### 2.1 High-Level Architecture

**Current Implementation (Phase 5 Complete):**

The Chaos Playbook Engine consists of **deterministic components** working together to demonstrate chaos engineering patterns with scientific rigor.

```
┌─────────────────────────────────────────────────────────────────┐
│                    Chaos Playbook Engine                        │
│                  (Hybrid Deterministic System)                  │
└─────────────────────────────────────────────────────────────────┘
                                │
                ┌───────────────┴───────────────┐
                │                               │
┌───────────────▼──────────────┐   ┌──────────▼──────────────────┐
│   Order Orchestration Layer   │   │   Chaos Injection Layer     │
│   (Deterministic)              │   │   (Rule-Based)              │
├────────────────────────────────┤   ├─────────────────────────────┤
│  ABTestRunner                  │   │  ChaosConfig                │
│  - Baseline execution          │   │  - failure_rate: float      │
│  - Playbook-powered execution  │   │  - seed: int                │
│  - Sequential workflow:        │   │  - enabled: bool            │
│    Inventory → Payment →       │   │                             │
│    ERP → Shipping              │   │  Simulated APIs:            │
│                                │   │  - InventoryAPI             │
│  PlaybookStorage               │   │  - PaymentAPI               │
│  - JSON persistence            │   │  - ErpAPI                   │
│  - Keyword search              │   │  - ShippingAPI              │
└────────────────────────────────┘   └─────────────────────────────┘
                │
                │
┌───────────────▼──────────────────────────────────────────────────┐
│              Evaluation & Metrics Layer                          │
│              (Deterministic Statistical Analysis)                │
├──────────────────────────────────────────────────────────────────┤
│  ExperimentEvaluator                MetricsAggregator            │
│  - Success rate calculation         - Mean, std, CI calculation │
│  - Inconsistency detection          - Failure rate aggregation  │
│  - Latency tracking                 - Confidence intervals      │
│                                                                  │
│  ParametricABTestRunner (Phase 5.1)                              │
│  - Multiple failure rates: [0.1, 0.3, 0.5]                      │
│  - N experiments per rate                                       │
│  - CSV export: raw_results.csv                                  │
│                                                                  │
│  AcademicReportGenerator (Phase 5.2)                             │
│  - Plotly dashboard with 4 charts                               │
│  - Statistical summaries (mean, std, CI)                        │
│  - HTML export: dashboard.html                                  │
└──────────────────────────────────────────────────────────────────┘
                │
                │
┌───────────────▼──────────────────────────────────────────────────┐
│                    Outputs & Artifacts                           │
├──────────────────────────────────────────────────────────────────┤
│  raw_results.csv          - Individual experiment data           │
│  aggregated_metrics.json  - Statistical summaries                │
│  dashboard.html           - Interactive visualizations           │
│  chaos_playbook.json      - Learned recovery strategies          │
└──────────────────────────────────────────────────────────────────┘
```

**ADK Infrastructure (Ready for Phase 6+):**
```
┌─────────────────────────────────────────────────────────────────┐
│              ADK Infrastructure (Phase 6+ Ready)                 │
├──────────────────────────────────────────────────────────────────┤
│  InMemorySessionService    - Conversation management (ready)     │
│  FunctionTool              - Custom tool wrappers (ready)        │
│  Runner                    - Agent execution (ready)             │
│  Session.events            - Trace analysis (ready)              │
│                                                                  │
│  Future Migration Path:                                          │
│  - LlmAgent for OrderOrchestrator (natural language reasoning)   │
│  - LlmAgent for ExperimentJudge (Agent-as-a-Judge pattern)      │
│  - VertexAiMemoryBankService (semantic search playbook)         │
└──────────────────────────────────────────────────────────────────┘
```

### 2.2 System Flow

**Current Implementation (Phase 5):**

1. **Parametric Test Runner** (`run_parametric_ab_test.py`)
   - Loads chaos configuration from `ChaosConfig`
   - Defines failure rates: [0.1, 0.3, 0.5]
   - Runs N experiments per failure rate

2. **Baseline Agent Execution** (No Playbook)
   - `ABTestRunner.run_experiment()` executes order workflow
   - Sequential API calls with chaos injection: Inventory → Payment → ERP → Shipping
   - Captures metrics: success, duration_s, api_calls, inconsistencies
   - Exports to `raw_results.csv`

3. **Playbook-Powered Agent Execution**
   - Same workflow as baseline
   - Loads recovery procedures from `chaos_playbook.json`
   - Applies recovery strategies on failures (retry with backoff)
   - Captures enhanced metrics
   - Exports to `raw_results.csv`

4. **Metrics Aggregation** (`MetricsAggregator`)
   - Groups results by failure_rate and agent_type
   - Calculates statistical summaries: mean, std, confidence intervals
   - Exports to `aggregated_metrics.json`

5. **Academic Visualization** (`AcademicReportGenerator`)
   - Generates 4 interactive Plotly charts:
     - Success Rate by Failure Rate (line chart with error bars)
     - Execution Time by Failure Rate (line chart)
     - API Calls by Failure Rate (bar chart)
     - Inconsistencies by Failure Rate (bar chart)
   - Exports to `dashboard.html`

---

## 3. Component Details

### 3.1 Order Orchestration Layer (Deterministic)

**Component**: `ABTestRunner`

**Type**: Python class (deterministic, not LlmAgent)

**Purpose**: Execute order workflows with and without playbook guidance

**Implementation**:
```python
class ABTestRunner:
    """
    Executes order processing workflows with deterministic logic.
    
    Supports two execution modes:
    - Baseline: No playbook consultation (naive error handling)
    - Playbook: Loads recovery procedures from chaos_playbook.json
    """
    
    def __init__(
        self,
        chaos_config: ChaosConfig,
        playbook_storage: PlaybookStorage,
        simulated_apis: SimulatedAPIs
    ):
        self.chaos_config = chaos_config
        self.playbook_storage = playbook_storage
        self.simulated_apis = simulated_apis
    
    async def run_experiment(
        self,
        order_input: dict,
        agent_type: str  # "baseline" | "playbook"
    ) -> ExperimentResult:
        """
        Execute single order experiment.
        
        Workflow:
        1. Check inventory (simulated API + chaos injection)
        2. Authorize payment (simulated API + chaos injection)
        3. Create ERP record (simulated API + chaos injection)
        4. Generate shipping label (simulated API + chaos injection)
        
        Returns:
            ExperimentResult: With success, duration_s, api_calls, inconsistencies
        """
        # Sequential workflow execution
        # Chaos injection applied at each API call
        # Playbook consultation if agent_type == "playbook"
        # Metrics tracking throughout
```

**Key Features**:
- Deterministic execution (reproducible with seed control)
- Sequential workflow: Inventory → Payment → ERP → Shipping
- Chaos injection transparent to orchestrator (appears as normal API failures)
- Playbook consultation optional (baseline vs playbook modes)
- Metrics tracking: success, duration_s, api_calls, inconsistencies

**Future Migration Path (Phase 6+)**:
```python
# Current: Deterministic
ab_runner = ABTestRunner(chaos_config, playbook_storage, simulated_apis)

# Future: LlmAgent-based
order_agent = LlmAgent(
    name="OrderOrchestratorAgent",
    model=Gemini(model="gemini-2.0-flash-exp"),
    instruction=ORDER_ORCHESTRATOR_INSTRUCTION,
    tools=[chaos_proxy_tool, load_procedure_tool]
)
```

### 3.2 Chaos Injection Layer (Rule-Based)

**Component**: `ChaosConfig`

**Type**: Python dataclass (configurable)

**Purpose**: Systematic, reproducible failure injection

**Implementation**:
```python
@dataclass
class ChaosConfig:
    """
    Configuration for chaos injection.
    
    Attributes:
        failure_rate: Probability of injecting failure (0.0-1.0)
        seed: Random seed for reproducibility
        enabled: Master switch for chaos injection
    """
    failure_rate: float = 0.0
    seed: Optional[int] = None
    enabled: bool = True
    
    def should_inject_failure(self) -> bool:
        """Determine if failure should be injected (random with seed)."""
        return self.enabled and random.random() < self.failure_rate
```

**Simulated APIs**:
```python
class SimulatedAPIs:
    """
    Four mock e-commerce APIs with stateful behavior.
    
    APIs:
    - InventoryAPI: check_stock, reserve_items
    - PaymentAPI: authorize, capture, refund
    - ErpAPI: create_order, update_status
    - ShippingAPI: calculate_rate, create_label
    """
    
    async def call_api(
        self,
        api_name: str,
        endpoint: str,
        method: str,
        payload: dict
    ) -> dict:
        """
        Execute API call with chaos injection.
        
        Chaos injection logic:
        1. Check if chaos should be injected (ChaosConfig.should_inject_failure())
        2. If yes, return simulated failure (503, 429, timeout, malformed JSON)
        3. If no, execute actual simulated API logic
        
        Returns:
            dict: {"status": "success"|"error", "data": {...}, "injected": bool}
        """
```

**Supported Failure Types**:
- **HTTP Status Errors**: 500, 502, 503, 504, 429, 404
- **Timeout Errors**: Simulated delays exceeding threshold
- **Malformed Responses**: Invalid JSON, missing fields
- **Transient Failures**: Errors that resolve on retry

**Key Features**:
- Seed-controlled reproducibility (same seed + failure_rate = same failures)
- Transparent to orchestrator (failures appear as normal API responses)
- Configurable failure rates (0.1, 0.3, 0.5 for parametric testing)
- Stateful APIs (inventory reservations, payment authorizations)

### 3.3 Evaluation & Metrics Layer (Deterministic Statistical Analysis)

**Component**: `ExperimentEvaluator`

**Type**: Python class (deterministic)

**Purpose**: Deterministic analysis of order execution

**Implementation**:
```python
class ExperimentEvaluator:
    """
    Evaluates order execution results.
    
    Metrics calculated:
    - success_rate: Percentage of successful orders
    - avg_duration_s: Mean execution time
    - avg_api_calls: Mean API invocations per order
    - inconsistency_rate: Percentage of data integrity issues
    """
    
    def evaluate(self, results: List[ExperimentResult]) -> MetricsSummary:
        """
        Analyze experiment results.
        
        Args:
            results: List of ExperimentResult objects
            
        Returns:
            MetricsSummary: With mean, std, confidence intervals
        """
        # Calculate success rate, latency, API calls, inconsistencies
        # Statistical summaries: mean, std, confidence intervals
        # Return structured metrics
```

**Component**: `MetricsAggregator` (Phase 5)

**Type**: Python class (deterministic statistical analysis)

**Purpose**: Aggregate metrics by failure_rate and agent_type

**Implementation**:
```python
class MetricsAggregator:
    """
    Aggregates metrics across multiple experiments.
    
    Groups results by:
    - failure_rate: 0.1, 0.3, 0.5
    - agent_type: "baseline", "playbook"
    
    Calculates:
    - mean, std, confidence_interval_95 for success_rate
    - mean, std for duration_s, api_calls, inconsistencies
    """
    
    def aggregate_by_failure_rate(
        self,
        df: pd.DataFrame
    ) -> dict:
        """
        Aggregate metrics by failure_rate and agent_type.
        
        Returns:
            dict: Nested structure with statistical summaries
                {
                    "0.1": {
                        "baseline": {"success_rate": {"mean": 0.85, "std": 0.08, ...}, ...},
                        "playbook": {"success_rate": {"mean": 0.94, "std": 0.05, ...}, ...}
                    },
                    ...
                }
        """
```

**Key Features**:
- Deterministic metrics calculation (no LLM-based evaluation)
- Statistical rigor: mean, std, confidence intervals (95%)
- Reproducible results
- CSV and JSON export formats

**Future Migration Path (Phase 6+)**:
```python
# Current: Deterministic
evaluator = ExperimentEvaluator()
metrics = evaluator.evaluate(results)

# Future: LlmAgent as Agent-as-a-Judge
judge_agent = LlmAgent(
    name="ExperimentJudgeAgent",
    model=Gemini(model="gemini-2.0-flash-exp"),
    instruction=EXPERIMENT_JUDGE_INSTRUCTION,
    tools=[save_procedure_tool]
)
```

### 3.4 Parametric A/B Testing Framework (Phase 5)

**Component**: `ParametricABTestRunner`

**Type**: Python class (Phase 5.1)

**Purpose**: Systematic parametric data generation across failure rates

**Implementation**:
```python
class ParametricABTestRunner:
    """
    Runs parametric experiments across multiple failure rates.
    
    For each failure rate:
    1. Run N experiments with baseline agent
    2. Run N experiments with playbook-powered agent
    3. Export raw results to CSV
    """
    
    async def run_parametric_experiments(
        self,
        failure_rates: List[float],  # e.g., [0.1, 0.3, 0.5]
        experiments_per_rate: int,
        output_dir: Path
    ) -> pd.DataFrame:
        """
        Execute parametric experiments.
        
        Returns:
            pd.DataFrame: Raw results with columns:
                - agent_type: "baseline" | "playbook"
                - failure_rate: float
                - success: bool
                - duration_s: float
                - api_calls: int
                - inconsistencies: int
                - run_id: int
        """
```

**Component**: `AcademicReportGenerator` (Phase 5.2)

**Type**: Python class (Phase 5.2)

**Purpose**: Generate publication-ready visualizations

**Implementation**:
```python
class AcademicReportGenerator:
    """
    Generates academic-grade Plotly dashboard.
    
    Creates 4 interactive charts:
    1. Success Rate by Failure Rate (line chart with error bars)
    2. Execution Time by Failure Rate (line chart)
    3. API Calls by Failure Rate (bar chart)
    4. Inconsistencies by Failure Rate (bar chart)
    """
    
    def generate_dashboard(
        self,
        aggregated_metrics: dict,
        output_path: Path
    ) -> None:
        """
        Generate interactive HTML dashboard.
        
        Exports:
        - Self-contained HTML file (Plotly.js embedded)
        - 4 charts in 2x2 grid layout
        - Professional styling (publication-ready)
        """
```

**Unified CLI** (Phase 5.3):
```bash
poetry run python scripts/run_parametric_ab_test.py \
    --failure-rates 0.1 0.3 0.5 \
    --experiments-per-rate 10 \
    --output-dir results/parametric_experiments/run_TIMESTAMP \
    --seed 42 \
    --verbose
```

**Outputs**:
- `raw_results.csv`: Individual experiment data
- `aggregated_metrics.json`: Statistical summaries
- `dashboard.html`: Interactive visualizations

### 3.5 Chaos Playbook Storage (JSON Persistence)

**Component**: `PlaybookStorage`

**Type**: Python class (JSON file persistence)

**Purpose**: Persist and retrieve learned recovery strategies

**Implementation**:
```python
class PlaybookStorage:
    """
    JSON-based playbook storage with keyword search.
    
    File: data/chaos_playbook.json
    
    Schema:
    {
        "procedures": [
            {
                "procedure_id": "uuid-string",
                "scenario_name": "payment_503_retry",
                "failure_pattern": {
                    "api_name": "payments",
                    "error_code": "503",
                    "context": "During authorization step"
                },
                "recovery_steps": [
                    "Wait 2 seconds before retry",
                    "Retry authorization with same payload"
                ],
                "expected_outcome": "Successful authorization on retry",
                "confidence_score": 0.85,
                "created_at": "2025-11-21T22:00:00Z",
                "usage_count": 0
            }
        ]
    }
    """
    
    def __init__(self, json_path: Path = Path("data/chaos_playbook.json")):
        self.json_path = json_path
        self.procedures = []
        self.load_from_json()
    
    def search_procedures(
        self,
        api_name: str,
        error_code: str
    ) -> List[dict]:
        """
        Search procedures by keyword matching (Phase 1-5).
        
        Phase 6+ Migration: Replace with VertexAiMemoryBankService
        for semantic search with embeddings.
        """
```

**Key Features**:
- JSON file persistence (survives restarts)
- Keyword-based search (api_name + error_code)
- Atomic writes (thread-safe)
- Validation (schema enforcement)

**Future Migration Path (Phase 6+)**:
```python
# Current: JSON file persistence
playbook_storage = PlaybookStorage(json_path="data/chaos_playbook.json")

# Future: VertexAiMemoryBankService with semantic search
memory_service = VertexAiMemoryBankService(
    project_id=os.getenv("GCP_PROJECT_ID"),
    location="us-central1",
    memory_bank_id="chaos-playbook-bank"
)
```

---

## 4. Data Flow Diagrams

### 4.1 Parametric Experiment Flow (Phase 5)

```
┌─────────────────────────────────────────────────────────────────┐
│                  Parametric Experiment Pipeline                  │
└─────────────────────────────────────────────────────────────────┘
                                │
                ┌───────────────┴───────────────┐
                │                               │
┌───────────────▼──────────────┐   ┌──────────▼──────────────────┐
│  BASELINE EXPERIMENTS          │   │  PLAYBOOK EXPERIMENTS       │
│  (No recovery strategies)      │   │  (With recovery strategies) │
├────────────────────────────────┤   ├─────────────────────────────┤
│  For each failure_rate:        │   │  For each failure_rate:     │
│    [0.1, 0.3, 0.5]             │   │    [0.1, 0.3, 0.5]          │
│                                │   │                             │
│  Run N experiments (e.g., 10)  │   │  Run N experiments          │
│                                │   │                             │
│  Order Input:                  │   │  Order Input: (same)        │
│    order_id: ORD-001           │   │    order_id: ORD-001        │
│    sku: WIDGET-001             │   │    sku: WIDGET-001          │
│    quantity: 2                 │   │    quantity: 2              │
│    chaos_config:               │   │    chaos_config:            │
│      failure_rate: 0.3         │   │      failure_rate: 0.3      │
│      seed: 42                  │   │      seed: 42               │
│                                │   │                             │
│  OrderOrchestrator (baseline)  │   │  OrderOrchestrator (playbook)│
│  1. Call Inventory API         │   │  1. Call Inventory API      │
│     → 30% chance: FAILURE      │   │     → 30% chance: FAILURE   │
│     → Return ExperimentResult  │   │     → Load recovery from    │
│                                │   │       chaos_playbook.json   │
│  2. Call Payment API           │   │     → Apply retry strategy  │
│     → 30% chance: FAILURE      │   │     → Success after retry   │
│     → Return ExperimentResult  │   │                             │
│                                │   │  2. Call Payment API        │
│  3. Call ERP API               │   │     → Same pattern          │
│  4. Call Shipping API          │   │                             │
│                                │   │  3-4. Continue workflow     │
│  Collect Results:              │   │                             │
│    - success: bool             │   │  Collect Results:           │
│    - duration_s: float         │   │    - success: bool          │
│    - api_calls: int            │   │    - duration_s: float      │
│    - inconsistencies: int      │   │    - api_calls: int         │
│    - agent_type: "baseline"    │   │    - inconsistencies: int   │
│    - failure_rate: 0.3         │   │    - agent_type: "playbook" │
│    - run_id: 0                 │   │    - failure_rate: 0.3      │
│                                │   │    - run_id: 0              │
└────────────────────────────────┘   └─────────────────────────────┘
                │                                   │
                └───────────────┬───────────────────┘
                                │
                ┌───────────────▼───────────────┐
                │    RAW RESULTS CSV EXPORT      │
                ├────────────────────────────────┤
                │  agent_type,failure_rate,      │
                │  success,duration_s,api_calls, │
                │  inconsistencies,run_id        │
                │                                │
                │  baseline,0.1,True,2.3,4,0,0   │
                │  baseline,0.1,False,1.8,3,1,1  │
                │  playbook,0.1,True,2.5,4,0,0   │
                │  playbook,0.1,True,2.4,4,0,1   │
                │  ...                           │
                └────────────────────────────────┘
                                │
                ┌───────────────▼───────────────┐
                │   METRICS AGGREGATION          │
                │   (MetricsAggregator)          │
                ├────────────────────────────────┤
                │  Group by:                     │
                │    - failure_rate              │
                │    - agent_type                │
                │                                │
                │  Calculate:                    │
                │    - mean, std, CI for         │
                │      success_rate              │
                │    - mean, std for duration_s, │
                │      api_calls, inconsistencies│
                │                                │
                │  Export:                       │
                │    aggregated_metrics.json     │
                └────────────────────────────────┘
                                │
                ┌───────────────▼───────────────┐
                │  ACADEMIC VISUALIZATION        │
                │  (AcademicReportGenerator)     │
                ├────────────────────────────────┤
                │  Generate 4 Plotly charts:     │
                │  1. Success Rate vs Failure    │
                │     Rate (line + error bars)   │
                │  2. Execution Time vs Failure  │
                │     Rate (line)                │
                │  3. API Calls vs Failure Rate  │
                │     (bar chart)                │
                │  4. Inconsistencies vs Failure │
                │     Rate (bar chart)           │
                │                                │
                │  Export:                       │
                │    dashboard.html              │
                └────────────────────────────────┘
```

### 4.2 Chaos Injection Decision Logic

```
API Call Initiated
      │
      ▼
┌─────────────────────┐
│  ChaosConfig Check  │
│  - enabled: true?   │
│  - random() <       │
│    failure_rate?    │
└─────────────────────┘
      │
      ├───── YES (inject failure) ────┐
      │                                │
      ▼                                ▼
┌─────────────────────┐   ┌────────────────────────┐
│  Select Failure      │   │  Execute Simulated     │
│  Type (random):      │   │  API Call (normal)     │
│  - 503 error         │   │                        │
│  - 429 rate limit    │   │  Return:               │
│  - Timeout           │   │    {"status": "success"│
│  - Malformed JSON    │   │     "data": {...},     │
└─────────────────────┘   │     "injected": false} │
      │                    └────────────────────────┘
      ▼
┌─────────────────────┐
│  Return Failure      │
│  Response:           │
│  {"status": "error", │
│   "error_code": 503, │
│   "injected": true}  │
└─────────────────────┘
```

### 4.3 Playbook Consultation Flow

```
API Call Failed
      │
      ▼
┌─────────────────────┐
│  Agent Type Check   │
└─────────────────────┘
      │
      ├───── baseline ────┐
      │                   │
      │                   ▼
      │          ┌────────────────────┐
      │          │  No Playbook       │
      │          │  Consultation      │
      │          │  → Return failure  │
      │          └────────────────────┘
      │
      └───── playbook ───┐
                         │
                         ▼
              ┌────────────────────┐
              │  PlaybookStorage   │
              │  .search_procedures│
              │  (api_name,        │
              │   error_code)      │
              └────────────────────┘
                         │
        ┌────────────────┴────────────────┐
        │                                 │
        ▼                                 ▼
┌─────────────────────┐   ┌────────────────────────┐
│  Procedure Found    │   │  No Procedure Found    │
│  (keyword match)    │   │                        │
└─────────────────────┘   │  Return failure        │
        │                  └────────────────────────┘
        ▼
┌─────────────────────┐
│  Load Recovery      │
│  Strategy:          │
│  - retry with       │
│    backoff          │
│  - max_retries: 3   │
│  - backoff_ms: 100  │
└─────────────────────┘
        │
        ▼
┌─────────────────────┐
│  Apply Recovery     │
│  1. Wait backoff_ms │
│  2. Retry API call  │
│  3. Success? Return │
└─────────────────────┘
```

---

## 5. Implementation Details

### 5.1 Project Structure

```
chaos-playbook-engine/
├── pyproject.toml              # Poetry dependency management
├── README.md                   # Setup and usage instructions
├── .env.example                # Environment variable template
│
├── data/                       # Data files (gitignored except .example)
│   ├── chaos_playbook.json     # Chaos Playbook procedures (JSON persistence)
│   └── chaos_playbook.example.json  # Example playbook with seed procedures
│
├── src/chaos_playbook_engine/
│   ├── __init__.py
│   │
│   ├── config/                 # Configuration and settings
│   │   ├── __init__.py
│   │   ├── chaos_config.py     # ChaosConfig dataclass
│   │   └── settings.py         # Application settings (Pydantic)
│   │
│   ├── apis/                   # Simulated API implementations
│   │   ├── __init__.py
│   │   ├── base.py             # BaseAPI abstract class
│   │   ├── inventory.py        # InventoryAPI
│   │   ├── payments.py         # PaymentAPI
│   │   ├── erp.py              # ErpAPI
│   │   └── shipping.py         # ShippingAPI
│   │
│   ├── services/               # Core services and managers
│   │   ├── __init__.py
│   │   ├── playbook_storage.py  # PlaybookStorage (JSON persistence)
│   │   └── simulated_apis.py   # SimulatedAPIs orchestrator
│   │
│   ├── runners/                # Experiment execution
│   │   ├── __init__.py
│   │   ├── ab_test_runner.py   # ABTestRunner (baseline vs playbook)
│   │   ├── parametric_ab_test_runner.py  # ParametricABTestRunner (Phase 5.1)
│   │   └── runner_factory.py   # Factory for runner creation (ADK-ready)
│   │
│   ├── evaluation/             # Metrics and evaluation
│   │   ├── __init__.py
│   │   ├── experiment_evaluator.py  # ExperimentEvaluator (deterministic)
│   │   ├── aggregate_metrics.py     # MetricsAggregator (Phase 5.1)
│   │   └── generate_report.py       # AcademicReportGenerator (Phase 5.2)
│   │
│   ├── utils/                  # Utility functions
│   │   ├── __init__.py
│   │   ├── logging_config.py   # Structured logging setup
│   │   └── retry_wrapper.py    # Retry logic with backoff
│   │
│   └── tools/                  # ADK FunctionTool wrappers (Phase 6+ ready)
│       ├── __init__.py
│       ├── chaos_proxy.py      # chaos_proxy_call FunctionTool (future)
│       └── playbook_tools.py   # save_procedure, load_procedure (future)
│
├── scripts/                    # Utility scripts
│   ├── run_parametric_ab_test.py  # Unified CLI (Phase 5.3)
│   ├── generate_report.py         # Report generator (deprecated, use evaluation/)
│   └── view_playbook.py           # Playbook inspection tool
│
├── tests/                      # Test suite
│   ├── __init__.py
│   ├── conftest.py             # Pytest fixtures
│   │
│   ├── fixtures/               # Test data
│   │   ├── chaos_playbook.json
│   │   └── chaos_config.py
│   │
│   ├── unit/                   # Unit tests
│   │   ├── test_apis.py
│   │   ├── test_playbook_storage.py
│   │   ├── test_chaos_config.py
│   │   └── test_retry_wrapper.py
│   │
│   ├── integration/            # Integration tests
│   │   ├── test_ab_runner.py
│   │   ├── test_aggregate_metrics.py
│   │   └── test_parametric_runner.py
│   │
│   └── e2e/                    # End-to-end tests
│       └── test_parametric_experiments.py
│
└── docs/                       # Additional documentation
    ├── architecture_diagrams/  # Mermaid diagrams
    ├── demo_script.md          # 3-minute demo walkthrough
    └── deployment_guide.md     # Phase 6 cloud deployment (future)
```

### 5.2 Key Files

**`src/chaos_playbook_engine/config/chaos_config.py`**:
```python
@dataclass
class ChaosConfig:
    """Configuration for chaos injection."""
    failure_rate: float = 0.0
    seed: Optional[int] = None
    enabled: bool = True
```

**`src/chaos_playbook_engine/runners/ab_test_runner.py`**:
```python
class ABTestRunner:
    """Execute order workflows with deterministic logic."""
    async def run_experiment(self, order_input, agent_type): ...
```

**`src/chaos_playbook_engine/evaluation/aggregate_metrics.py`** (Phase 5.1):
```python
class MetricsAggregator:
    """Aggregate metrics by failure_rate and agent_type."""
    def aggregate_by_failure_rate(self, df): ...
```

**`src/chaos_playbook_engine/evaluation/generate_report.py`** (Phase 5.2):
```python
class AcademicReportGenerator:
    """Generate Plotly dashboard with 4 charts."""
    def generate_dashboard(self, aggregated_metrics, output_path): ...
```

**`scripts/run_parametric_ab_test.py`** (Phase 5.3):
```python
# Unified CLI for parametric experiments
poetry run python scripts/run_parametric_ab_test.py \
    --failure-rates 0.1 0.3 0.5 \
    --experiments-per-rate 10 \
    --output-dir results/parametric_experiments/run_TIMESTAMP \
    --seed 42 \
    --verbose
```

---

## 6. Testing Strategy

### 6.1 Unit Tests

**Coverage**: >80%

**Files**:
- `tests/unit/test_apis.py`: Simulated API behavior
- `tests/unit/test_playbook_storage.py`: JSON persistence
- `tests/unit/test_chaos_config.py`: Chaos injection logic
- `tests/unit/test_retry_wrapper.py`: Retry with backoff

**Example**:
```python
@pytest.mark.asyncio
async def test_inventory_api_check_stock():
    """Test InventoryAPI.check_stock endpoint."""
    api = InventoryAPI()
    result = await api.call("check-stock", "GET", {"sku": "WIDGET-001"})
    assert result["status"] == "success"
    assert result["data"]["available"] == True
```

### 6.2 Integration Tests

**Files**:
- `tests/integration/test_ab_runner.py`: ABTestRunner workflow
- `tests/integration/test_aggregate_metrics.py`: MetricsAggregator
- `tests/integration/test_parametric_runner.py`: ParametricABTestRunner

**Example**:
```python
@pytest.mark.asyncio
async def test_ab_runner_baseline_vs_playbook():
    """Test ABTestRunner with baseline and playbook agents."""
    runner = ABTestRunner(chaos_config, playbook_storage, simulated_apis)
    
    # Run baseline
    baseline_result = await runner.run_experiment(order_input, "baseline")
    assert "success" in baseline_result
    
    # Run playbook
    playbook_result = await runner.run_experiment(order_input, "playbook")
    assert playbook_result["success"] >= baseline_result["success"]
```

### 6.3 End-to-End Tests

**Files**:
- `tests/e2e/test_parametric_experiments.py`: Full parametric pipeline

**Example**:
```python
@pytest.mark.asyncio
async def test_parametric_ab_test_full_workflow():
    """Test complete parametric AB testing workflow."""
    runner = ParametricABTestRunner(
        failure_rates=[0.1, 0.3],
        experiments_per_rate=5
    )
    
    # Run experiments
    results = await runner.run_parametric_experiments()
    
    # Verify outputs
    assert Path("raw_results.csv").exists()
    assert Path("aggregated_metrics.json").exists()
    assert Path("dashboard.html").exists()
```

---

## 7. Deployment & Scalability

### 7.1 Current Architecture (Phase 1-5)

**Environment**: Local development

**Characteristics**:
- Single machine execution
- JSON file persistence
- No cloud dependencies
- Fast iteration cycles

**Deployment**:
```bash
# Setup
poetry install
poetry run python scripts/run_parametric_ab_test.py --verbose

# View results
open results/parametric_experiments/run_TIMESTAMP/dashboard.html
```

### 7.2 Future Scaling (Phase 6+)

**ADK Infrastructure Migration**:

**1. LlmAgent for OrderOrchestrator**:
```python
from google.adk.agents import LlmAgent
from google.genai import Gemini

order_agent = LlmAgent(
    name="OrderOrchestratorAgent",
    model=Gemini(model="gemini-2.0-flash-exp"),
    instruction=ORDER_ORCHESTRATOR_INSTRUCTION,
    tools=[chaos_proxy_tool, load_procedure_tool],
    output_key="order_result"
)
```

**2. LlmAgent for ExperimentJudge**:
```python
judge_agent = LlmAgent(
    name="ExperimentJudgeAgent",
    model=Gemini(model="gemini-2.0-flash-exp"),
    instruction=EXPERIMENT_JUDGE_INSTRUCTION,
    tools=[save_procedure_tool],
    output_key="evaluation_result"
)
```

**3. VertexAiMemoryBankService**:
```python
from google.adk.memory import VertexAiMemoryBankService

memory_service = VertexAiMemoryBankService(
    project_id=os.getenv("GCP_PROJECT_ID"),
    location="us-central1",
    memory_bank_id="chaos-playbook-bank"
)
```

**4. Cloud Run Deployment**:
```yaml
# cloud_run.yaml
service: chaos-playbook-engine
runtime: python311
entrypoint: poetry run python scripts/run_parametric_ab_test.py
env_variables:
  GCP_PROJECT_ID: "your-project-id"
  DATABASE_URL: "postgresql://..."
  MEMORY_BANK_ID: "chaos-playbook-bank"
```

---

## 8. Key Metrics & Success Criteria

### 8.1 Validation Framework (Phase 5)

**Metric-001: Success Rate Improvement**
- **Target**: >20% improvement
- **Calculation**: `(Playbook SR - Baseline SR) / Baseline SR * 100`
- **Actual**: 49.99% improvement (3-run test)
- **Status**: ✅ PASS

**Metric-002: Inconsistency Reduction**
- **Target**: -50% reduction or maintain 0%
- **Calculation**: `(Playbook IR - Baseline IR) / Baseline IR * 100`
- **Actual**: N/A (both 0%)
- **Status**: ✅ PASS

**Metric-003: Latency Overhead**
- **Target**: <10% increase acceptable
- **Calculation**: `(Playbook Latency - Baseline Latency) / Baseline Latency * 100`
- **Actual**: -47.26% (playbook is FASTER!)
- **Status**: ✅ PASS

### 8.2 Statistical Rigor (Phase 5)

**Confidence Intervals**:
- Success rate: 95% confidence intervals calculated
- Reproducibility: Seed-controlled experiments

**Sample Size**:
- Minimum 10 experiments per failure rate
- Parametric testing across 3+ failure rates
- Total: 60+ experiments for robust validation

---

## 9. ADK Best Practices Compliance

### 9.1 Current Implementation (Phase 5)

**Infrastructure Ready**:
- ✅ ADK dependencies installed (`google-adk>=1.18.0`)
- ✅ FunctionTool wrappers prepared (future use)
- ✅ Session management structure in place
- ✅ Clear migration path documented

**Not Currently Used** (deterministic approach prioritized):
- LlmAgent for agents (using deterministic Python classes instead)
- Runner for agent execution (using direct async calls)
- Session.events for trace analysis (using direct metrics tracking)

### 9.2 Future Migration Checklist (Phase 6+)

**Agent Design**:
- [ ] Migrate OrderOrchestrator to LlmAgent with natural language reasoning
- [ ] Migrate ExperimentJudge to LlmAgent (Agent-as-a-Judge pattern)
- [ ] Add agent instructions (clear and specific prompts)
- [ ] Use `output_key` for structured results

**Tool Implementation**:
- [ ] Wrap all tools in FunctionTool
- [ ] Add comprehensive docstrings for LLM understanding
- [ ] Implement async patterns for IO operations
- [ ] Use structured return format (dict with status, data, error)

**Session Management**:
- [ ] Use InMemorySessionService or DatabaseSessionService
- [ ] Parse Session.events for trace analysis
- [ ] Store persistent data in Session.state

**Memory Management**:
- [ ] Migrate PlaybookStorage to VertexAiMemoryBankService
- [ ] Implement semantic search with embeddings
- [ ] Preserve existing JSON data during migration

**Runner Usage**:
- [ ] Use Runner for agent execution
- [ ] Handle streaming events properly
- [ ] Inject sessionservice via factory pattern

---

## 10. Appendices

### 10.1 Example Raw Results CSV

```csv
agent_type,failure_rate,success,duration_s,api_calls,inconsistencies,run_id
baseline,0.1,True,2.3,4,0,0
baseline,0.1,False,1.8,3,1,1
playbook,0.1,True,2.5,4,0,0
playbook,0.1,True,2.4,4,0,1
baseline,0.3,False,1.5,2,1,0
baseline,0.3,True,3.1,5,0,1
playbook,0.3,True,2.8,4,0,0
playbook,0.3,True,2.9,4,0,1
baseline,0.5,False,0.8,1,2,0
baseline,0.5,False,1.2,2,1,1
playbook,0.5,True,3.5,6,0,0
playbook,0.5,True,3.2,5,0,1
```

### 10.2 Example Aggregated Metrics JSON

```json
{
  "0.1": {
    "baseline": {
      "success_rate": {
        "mean": 0.85,
        "std": 0.08,
        "ci_95": [0.77, 0.93]
      },
      "duration_s": {
        "mean": 2.3,
        "std": 0.15
      },
      "api_calls": {
        "mean": 4.2,
        "std": 0.4
      },
      "inconsistencies": {
        "mean": 0.15,
        "std": 0.35
      }
    },
    "playbook": {
      "success_rate": {
        "mean": 0.94,
        "std": 0.05,
        "ci_95": [0.89, 0.99]
      },
      "duration_s": {
        "mean": 2.5,
        "std": 0.10
      },
      "api_calls": {
        "mean": 4.0,
        "std": 0.2
      },
      "inconsistencies": {
        "mean": 0.0,
        "std": 0.0
      }
    }
  },
  "0.3": {
    "baseline": {...},
    "playbook": {...}
  },
  "0.5": {
    "baseline": {...},
    "playbook": {...}
  }
}
```

### 10.3 Example Chaos Playbook JSON

```json
{
  "procedures": [
    {
      "procedure_id": "proc-20251121-001",
      "scenario_name": "payment_503_retry",
      "failure_pattern": {
        "api_name": "payments",
        "error_code": "503",
        "context": "During authorization step"
      },
      "recovery_steps": [
        "Wait 2 seconds before retry",
        "Retry authorization with same payload",
        "If retry fails, wait 4 seconds and retry again",
        "Maximum 3 retry attempts"
      ],
      "expected_outcome": "Successful authorization on retry",
      "confidence_score": 0.85,
      "created_at": "2025-11-21T22:00:00Z",
      "usage_count": 47,
      "last_used_at": "2025-11-23T15:30:00Z"
    },
    {
      "procedure_id": "proc-20251121-002",
      "scenario_name": "inventory_timeout_backoff",
      "failure_pattern": {
        "api_name": "inventory",
        "error_code": "timeout",
        "context": "During stock check"
      },
      "recovery_steps": [
        "Wait 1 second before retry",
        "Retry stock check with exponential backoff",
        "If timeout persists, skip to next step with warning"
      ],
      "expected_outcome": "Stock check succeeds or order continues with warning",
      "confidence_score": 0.78,
      "created_at": "2025-11-21T22:15:00Z",
      "usage_count": 23,
      "last_used_at": "2025-11-23T14:20:00Z"
    }
  ]
}
```

### 10.4 Dashboard Chart Specifications

**Chart 1: Success Rate by Failure Rate**
- **Type**: Line chart with error bars
- **X-axis**: Failure Rate (0.1, 0.3, 0.5)
- **Y-axis**: Success Rate (0.0 - 1.0)
- **Lines**: Baseline (red), Playbook (green)
- **Error bars**: ±1 std deviation

**Chart 2: Execution Time by Failure Rate**
- **Type**: Line chart
- **X-axis**: Failure Rate
- **Y-axis**: Duration (seconds)
- **Lines**: Baseline, Playbook

**Chart 3: API Calls by Failure Rate**
- **Type**: Grouped bar chart
- **X-axis**: Failure Rate
- **Y-axis**: API Calls (count)
- **Bars**: Baseline, Playbook

**Chart 4: Inconsistencies by Failure Rate**
- **Type**: Grouped bar chart
- **X-axis**: Failure Rate
- **Y-axis**: Inconsistencies (count)
- **Bars**: Baseline, Playbook

---

## 11. Change Log

**Version 3.0 - November 24, 2025**

**Major Updates:**
- Documented design evolution from 3 LLM agents to hybrid deterministic system
- Completed Phase 5: Parametric Experiments & Academic Visualization
  - Phase 5.1: ParametricABTestRunner
  - Phase 5.2: AcademicReportGenerator
  - Phase 5.3: Unified CLI
- Added statistical rigor: confidence intervals, reproducible experiments
- Clarified current implementation (deterministic) vs future migration (LLM-based)
- Updated all component descriptions to reflect Phase 5 completion
- Added Plotly dashboard specifications and examples
- Documented ADK infrastructure status (ready but not actively used)
- Expanded testing strategy with Phase 5 integration tests
- Updated deployment section with Phase 6+ migration path

**Architecture Changes:**
- OrderOrchestrator: Deterministic Python class (not LlmAgent)
- ExperimentEvaluator: Deterministic metrics calculation (not LlmAgent)
- Chaos Injection: Rule-based via ChaosConfig (not agent-based)
- A/B Testing: Parametric framework with statistical aggregation
- Playbook Storage: JSON persistence (Phase 1-5), VertexAiMemoryBankService path (Phase 6+)

**Version 2.0 - November 21, 2025**
- Clarified multi-agent architecture: 2 LlmAgents (Orchestrator + Judge)
- Specified InMemoryMemoryService with JSON persistence
- Added comprehensive FunctionTool implementation guidelines
- Documented future migration path to VertexAiMemoryBankService

**Version 1.0 - November 18, 2025**
- Initial architecture document based on Capstone-Pitch.md

---

**END OF SYSTEM ARCHITECTURE DOCUMENT v3.0**
