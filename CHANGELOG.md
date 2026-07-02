# Changelog

All notable changes to the Chaos Playbook Engine are documented in this file.

---

## [2.1.0] - 2026-04-18

### Sprint 14: Real LLM Experiments & Quality Pass

### Added

- **G8 Ministral 14B experiment** (n=200, HTTP think, 10 failure rates 0.00–0.30): 4,000 runs completed in ~13.7h on local LM Studio.
- **Experiment tracing** (`trace.jsonl`): Per-turn LLM interaction logs for full auditability. Available for G6, G7, G8 experiments. G3 and G5 lack traces — they ran on remote providers (ZhipuAI) before the tracing feature was implemented.

### Changed

- **`ExperimentConfig.thinking_modes()`**: `has_thinking: true` now defaults to `[True]` (think-only). Previously defaulted to `[True, False]`, silently doubling experiment runs. Use explicit `thinking: [true, false]` in `per_request_params` for both modes.
- **Dashboard elapsed time** (`dashboard_experiment.py`): Fixed two bugs inflating elapsed time — start now uses earliest CSV creation time (not unrelated log files), end uses latest CSV modification time (not wall clock).

### Fixed

- `test_thinking_modes_from_has_thinking`: Updated assertion to match new `[True]` default.

---

## [2.0.0] - 2026-03-14

### Phase 10: Evolution & Unified CLI

**57/53 backlog items resolved across 8 sprints. 126 automated tests passing.**

### Added

- **Unified CLI** (`__main__.py`): Single entry point with subcommands (`simulate`, `judge`, `evolve`, `leaderboard`, `registry`). Accessible via `python -m chaos_engine` or `chaos-engine` after `poetry install`.
- **PlaybookWriterAgent** (`agents/playbook_writer.py`): Autonomous playbook synthesis from experiment CSV data. Heuristic-based strategy selection (no LLM required).
- **PlaybookEvolver** (`simulation/mutation.py`): Genetic algorithm for playbook optimization — mutate strategies, evaluate variants via parametric experiments, select the best per generation.
- **N-Agent Comparison** (`reporting/comparison.py`): Dynamic agent name extraction, composite scoring (`success*100 - inconsistencies*50 - duration*2`), cross-run trend analysis, ASCII leaderboard.
- **Protocol abstractions** (`core/protocols.py`): Unified `Executor`, `AgentRunner`, and `WorkflowAgent` protocols. Single source of truth, replacing 3 duplicate definitions.
- **CircuitBreakerSettings** (`core/settings.py`): Pydantic model centralizing circuit breaker magic numbers.
- **Custom exception hierarchy** (`core/exceptions.py`): `ChaosEngineError`, `PlaybookError`, `CircuitBreakerOpenError`, etc.
- **ExperimentResult TypedDict** (`core/types.py`): Strict return types replacing `Dict[str, Any]`.
- **Status/WorkflowStep StrEnums** (`core/types.py`): Replacing magic strings throughout.
- **Property-based tests** (8 tests): Hypothesis tests for `ChaosConfig`, `DeterministicAgent`, `WelfordAggregator`.
- **Integration tests** (6 tests): End-to-end pipeline with `DeterministicAgent` (no API key required).
- **GitHub Actions CI**: `poetry install` → `ruff check` → `pytest --cov` → `pip-audit` → integration tests.
- **Signal handlers**: SIGINT/SIGTERM graceful shutdown in CLI.
- **Poetry script entry point**: `chaos-engine = "chaos_engine.__main__:main"`.

### Changed

- **StreamingAggregator**: Replaced O(N) `all_results_buffer` with Welford's algorithm for O(1) streaming mean/variance.
- **ChaosProxy**: Reusable `httpx.AsyncClient` via `_get_client()` pattern (replaces per-request client creation). Added `close()` for cleanup. Added DELETE/PATCH HTTP method support.
- **CircuitBreakerProxy**: Added HALF-OPEN single-probe limit. Configurable via `CircuitBreakerSettings`.
- **DeterministicAgent**: `simulate_delays` flag to skip `asyncio.sleep()` in test mode. `WORKFLOW_STEPS` as immutable tuple.
- **PetstoreAgent**: Added `simulate_delays` parameter. Fixed file handle leak (context manager).
- **PlaybookStorage**: Updated to strategy-matrix API (`add_or_update_strategy`, `resolve_strategy`). Hot-reload detection.
- **Logging**: Replaced 34 `print()` calls with `logger.info()`/`logger.debug()`. Fixed f-strings in logging calls to use lazy `%s` formatting.
- **Exception handling**: Added `raise X from exc` for causality chain. Added `logger.exception()` in except blocks.
- **All modules**: Added `from __future__ import annotations` (PEP 563). Added `__all__` to all `__init__.py` files.
- **`pyproject.toml`**: Added `httpx`, `hypothesis`, `pip-audit` dependencies. Added Poetry scripts entry point.
- **Test suite**: Grew from ~20 to 126 tests (120 unit + 6 integration).

### Fixed

- `ChaosConfig.should_inject_failure()` respecting `enabled` flag
- `std: 0.0` hardcoded in aggregated metrics (now computes actual standard deviation)
- `sys.path` manipulation workarounds removed
- `playbook_tools.py` bypassing `PlaybookStorage` async lock
- `_enrich_with_env_vars()` mutating input dict (now returns new dict)
- Race condition in `PetstoreAgent.successful_steps` (now local to method)
- API key copied to config dict (security fix)

---

## [1.0.0] - 2025-12-01

### Phases 1-6: Foundation through Reasoning

- Initial release: Chaos Playbook Engine with Hybrid Deterministic/Probabilistic architecture
- Google ADK integration with Gemini 2.5 Flash Lite
- 18,000 parametric experiments validating +60% success rate improvement
- ChaosProxy with seed-controlled failure injection
- CircuitBreakerProxy (SRE pattern)
- PlaybookStorage (JSON-based RAG)
- Interactive Plotly dashboards
- Winner of Google Agentic AI Hackathon (Dec 2025)
