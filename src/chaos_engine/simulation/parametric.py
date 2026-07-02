"""ParametricABTestRunner — orchestrator for multi-rate chaos experiments."""
from __future__ import annotations

import csv
import json
import logging
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from collections.abc import AsyncGenerator
from typing import Any

from chaos_engine.agents.deterministic import DeterministicAgent
from chaos_engine.agents.trace import ExperimentTracer
from chaos_engine.chaos.proxy import ChaosProxy
from chaos_engine.core.metrics import (
    EXPERIMENTS_FAILED,
    EXPERIMENTS_SUCCESS,
    EXPERIMENTS_TOTAL,
)
from chaos_engine.core.resilience import CircuitBreakerProxy
from chaos_engine.core.settings import DEFAULT_LLM_PROVIDER, CircuitBreakerSettings, PlaybookPaths
from chaos_engine.core.types import Status, WorkflowStep

# Default circuit breaker configuration (A.31: centralized constants)
_DEFAULT_CB = CircuitBreakerSettings()

logger = logging.getLogger(__name__)


@dataclass
class AgentConfig:
    """Configuration for a single agent type in parametric experiments."""
    name: str          # e.g. "baseline", "aggressive", "conservative"
    playbook_path: str  # path to playbook JSON
    kind: str = "deterministic"  # "deterministic", "llm", "mcp_baseline", "mcp_llm", "a2a_baseline", "a2a_llm"
    llm_provider: str = DEFAULT_LLM_PROVIDER
    llm_model: str | None = None
    thinking: bool | None = None  # None=provider default, True=force on, False=force off
    harness: bool = True  # Enable _build_step_body enrichment (False for ablation experiments)


class _StreamingAggregator:
    """Online aggregator using Welford's algorithm for mean and variance.

    Processes one result at a time — O(1) memory per rate/agent_type bucket.
    Replaces the old ``all_results_buffer`` list that required O(N) memory.
    """

    def __init__(self, agent_names: list[str]) -> None:
        # key: (failure_rate, agent_type) -> stats accumulator
        self._buckets: dict[tuple[float, str], dict[str, Any]] = {}
        self._agent_names = agent_names

    def _ensure_bucket(self, key: tuple[float, str]) -> dict[str, Any]:
        if key not in self._buckets:
            self._buckets[key] = {
                "n": 0,
                "successes": 0,
                # Welford accumulators for duration
                "dur_mean": 0.0,
                "dur_m2": 0.0,
                # Welford accumulators for inconsistencies
                "inc_mean": 0.0,
                "inc_m2": 0.0,
            }
        return self._buckets[key]

    def process(self, result: dict[str, Any]) -> None:
        """Ingest a single experiment result (O(1) memory)."""
        key = (result["failure_rate"], result["agent_type"])
        b = self._ensure_bucket(key)

        b["n"] += 1
        n = b["n"]

        if result["status"] == Status.SUCCESS:
            b["successes"] += 1

        # Welford online update — duration_ms
        dur = result["duration_ms"]
        delta = dur - b["dur_mean"]
        b["dur_mean"] += delta / n
        delta2 = dur - b["dur_mean"]
        b["dur_m2"] += delta * delta2

        # Welford online update — inconsistencies
        inc = result.get("inconsistencies_count", 0)
        delta_i = inc - b["inc_mean"]
        b["inc_mean"] += delta_i / n
        delta_i2 = inc - b["inc_mean"]
        b["inc_m2"] += delta_i * delta_i2

    def build_metrics(self) -> dict[str, Any]:
        """Produce the aggregated_metrics.json-compatible dict."""
        import math

        # Group by failure_rate
        rates: dict[float, dict[str, dict[str, Any]]] = defaultdict(dict)
        for (rate, agent_type), b in self._buckets.items():
            n = b["n"]
            std_dur = math.sqrt(b["dur_m2"] / n) if n > 1 else 0.0
            std_inc = math.sqrt(b["inc_m2"] / n) if n > 1 else 0.0
            success_rate = b["successes"] / n if n else 0.0
            std_sr = math.sqrt(success_rate * (1 - success_rate) / n) if n else 0.0

            rates[rate][agent_type] = {
                "n_runs": n,
                "success_rate": {"mean": success_rate, "std": round(std_sr, 6)},
                "duration_s": {
                    "mean": (b["dur_mean"] / 1000) if n else 0,
                    "std": round(std_dur / 1000, 6),
                },
                "inconsistencies": {
                    "mean": b["inc_mean"],
                    "std": round(std_inc, 6),
                },
            }

        n_agents = len(self._agent_names)
        metrics: dict[str, Any] = {}
        for rate in sorted(rates):
            rate_key = str(rate)
            group = rates[rate]
            total = sum(v["n_runs"] for v in group.values())
            entry: dict[str, Any] = {
                "failure_rate": rate,
                "n_experiments": total // n_agents,
            }
            for agent_name in self._agent_names:
                entry[agent_name] = group.get(agent_name, {})
            metrics[rate_key] = entry
        return metrics


class ParametricABTestRunner:
    def __init__(
        self,
        failure_rates: list[float],
        experiments_per_rate: int,
        output_dir: Path,
        seed: int = 42,
        logger: logging.Logger | None = None,
        playbook_baseline_path: str = PlaybookPaths().baseline,
        playbook_training_path: str = PlaybookPaths().training,
        simulate_delays: bool = False,
        agents: list[AgentConfig] | None = None,
        base_url: str | None = None,
        seed_range: tuple[int, int] | None = None,
        trace: bool = False,
    ):
        self.failure_rates = failure_rates
        self.experiments_per_rate = experiments_per_rate
        self.output_dir = output_dir
        self.base_seed = seed
        self.simulate_delays = simulate_delays
        self.base_url = base_url
        # seed_range = (start, end) limits j to [start, end) for parallel blocks
        self.seed_range = seed_range
        self.trace = trace
        self.logger = logger or logging.getLogger(__name__)

        # Build agent list: use explicit agents if provided, otherwise
        # fall back to the legacy two-agent baseline/playbook setup.
        if agents is not None:
            self.agents = agents
        else:
            self.agents = [
                AgentConfig(name="baseline", playbook_path=playbook_baseline_path),
                AgentConfig(name="playbook", playbook_path=playbook_training_path),
            ]

    @classmethod
    def from_ab_config(
        cls,
        failure_rates: list[float],
        experiments_per_rate: int,
        output_dir: Path,
        playbook_baseline_path: str = PlaybookPaths().baseline,
        playbook_training_path: str = PlaybookPaths().training,
        seed: int = 42,
        simulate_delays: bool = False,
        logger: logging.Logger | None = None,
    ) -> "ParametricABTestRunner":
        """Factory method preserving the original two-agent A/B test interface."""
        return cls(
            failure_rates=failure_rates,
            experiments_per_rate=experiments_per_rate,
            output_dir=output_dir,
            seed=seed,
            logger=logger,
            playbook_baseline_path=playbook_baseline_path,
            playbook_training_path=playbook_training_path,
            simulate_delays=simulate_delays,
        )

    def _load_completed_ids(self, csv_path: Path) -> set[str]:
        """Load experiment IDs already written to CSV (for resume support)."""
        completed: set[str] = set()
        if not csv_path.exists():
            return completed
        with open(csv_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                completed.add(row["experiment_id"])
        self.logger.info("Resume: found %d completed experiments in %s", len(completed), csv_path)
        return completed

    _CSV_KEYS = [
        "experiment_id", "agent_type", "outcome", "duration_ms",
        "steps_completed", "failed_at", "inconsistencies_count",
        "retries", "seed", "failure_rate",
        "llm_calls", "input_chars", "output_chars",
        "prompt_tokens", "completion_tokens", "reasoning_tokens",
        "steps_completed_list",
    ]

    @staticmethod
    def rate_csv_name(rate: float) -> str:
        """Canonical CSV filename for a given failure rate."""
        return f"rate_{rate:.2f}.csv"

    async def run_parametric_experiments(self) -> dict[str, Any]:
        """Run experiments writing one CSV per failure rate.

        Each rate writes to ``rate_X.XX.csv`` inside *output_dir*, allowing
        multiple processes to run different rates in parallel without file
        contention.  Resume support is per-file via experiment_id tracking.
        """
        self.logger.info("Starting parametric experiments...")
        self.logger.info("Failure rates: %s", self.failure_rates)
        j_start = self.seed_range[0] if self.seed_range else 0
        j_end = self.seed_range[1] if self.seed_range else self.experiments_per_rate
        block_size = j_end - j_start
        n_agents = len(self.agents)
        total_planned = len(self.failure_rates) * block_size * n_agents
        self.logger.info("Experiments per rate: %d (block: %d)", self.experiments_per_rate, block_size)
        self.logger.info("Total: %d runs (%d agent types)", total_planned, n_agents)

        self.output_dir.mkdir(parents=True, exist_ok=True)

        agent_names = [a.name for a in self.agents]
        aggregator = _StreamingAggregator(agent_names)
        grand_count = 0

        for i, rate in enumerate(self.failure_rates):
            csv_path = self.output_dir / self.rate_csv_name(rate)
            completed_ids = self._load_completed_ids(csv_path)
            resuming = len(completed_ids) > 0

            # Replay completed into aggregator
            rate_count = 0
            if resuming:
                with open(csv_path, "r", encoding="utf-8") as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        aggregator.process({
                            "failure_rate": float(row["failure_rate"]),
                            "agent_type": row["agent_type"],
                            "status": row["outcome"],  # CSV "outcome" → internal "status"
                            "duration_ms": float(row["duration_ms"]),
                            "inconsistencies_count": int(row.get("inconsistencies_count", 0)),
                        })
                        rate_count += 1
                self.logger.info("Resume rate %.2f: replayed %d results", rate, rate_count)

            # Check if this rate is already complete
            expected_for_rate = block_size * n_agents
            if rate_count >= expected_for_rate:
                self.logger.info("SKIP rate %.2f: already complete (%d/%d)", rate, rate_count, expected_for_rate)
                grand_count += rate_count
                continue

            open_mode = "a" if resuming else "w"
            with open(csv_path, open_mode, newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=self._CSV_KEYS)
                if not resuming:
                    writer.writeheader()

                async for result in self._single_rate_generator(i, rate, skip_ids=completed_ids):
                    result["inconsistencies_count"] = self._calculate_inconsistency(result)

                    writer.writerow(self._flatten_result_for_csv(result))
                    f.flush()
                    aggregator.process(result)
                    rate_count += 1

                    fr_label = str(result["failure_rate"])
                    at_label = result["agent_type"]
                    EXPERIMENTS_TOTAL.labels(agent_type=at_label, failure_rate=fr_label).inc()
                    if result["status"] == Status.SUCCESS:
                        EXPERIMENTS_SUCCESS.labels(agent_type=at_label, failure_rate=fr_label).inc()
                    else:
                        EXPERIMENTS_FAILED.labels(agent_type=at_label, failure_rate=fr_label).inc()

            self.logger.info("Rate %.2f: %d experiments -> %s", rate, rate_count, csv_path.name)
            grand_count += rate_count

        self.logger.info("All rates done: %d total experiments", grand_count)

        # Save aggregated metrics
        json_path = self.output_dir / "aggregated_metrics.json"
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(aggregator.build_metrics(), f, indent=2)

        return {"total_experiments": grand_count}

    async def _run_single_experiment(
        self, agent_cfg: AgentConfig, failure_rate: float, seed: int,
        tracer: ExperimentTracer | None = None, experiment_id: str = "",
    ) -> dict[str, Any]:
        """Run a single experiment with fresh infrastructure for any agent type."""
        kind = agent_cfg.kind

        # --- MCP protocol agents ---
        if kind.startswith("mcp_"):
            return await self._run_mcp_experiment(agent_cfg, failure_rate, seed, tracer=tracer, experiment_id=experiment_id)

        # --- A2A protocol agents ---
        if kind.startswith("a2a_"):
            return await self._run_a2a_experiment(agent_cfg, failure_rate, seed, tracer=tracer, experiment_id=experiment_id)

        # --- HTTP protocol agents (original) ---
        mock_mode = self.base_url is None
        chaos_proxy = ChaosProxy(
            failure_rate=failure_rate,
            seed=seed,
            mock_mode=mock_mode,
            verbose=False,
            base_url=self.base_url or "",
        )
        circuit_breaker = CircuitBreakerProxy(
            wrapped_executor=chaos_proxy,
            failure_threshold=_DEFAULT_CB.failure_threshold,
            cooldown_seconds=_DEFAULT_CB.cooldown_seconds,
        )

        if kind in ("llm", "llm_playbook", "llm_playbook_v2"):
            from chaos_engine.agents.llm_agent import HTTP_PLAYBOOK_GUIDANCE, HTTP_PLAYBOOK_GUIDANCE_V2, LLMAgent
            from chaos_engine.agents.llm_client import LLMClient

            llm_client = LLMClient(
                provider=agent_cfg.llm_provider,
                model=agent_cfg.llm_model,
                thinking=agent_cfg.thinking,
                seed=seed,
            )
            playbook = (
                HTTP_PLAYBOOK_GUIDANCE_V2 if kind == "llm_playbook_v2"
                else HTTP_PLAYBOOK_GUIDANCE if kind == "llm_playbook"
                else None
            )
            agent = LLMAgent(
                tool_executor=circuit_breaker,
                llm_client=llm_client,
                simulate_delays=self.simulate_delays,
                playbook_guidance=playbook,
                tracer=tracer,
                experiment_id=experiment_id,
                enable_harness=agent_cfg.harness,
            )
        else:
            agent = DeterministicAgent(
                tool_executor=circuit_breaker,
                playbook_path=agent_cfg.playbook_path,
                simulate_delays=self.simulate_delays,
            )

        result = await agent.run()
        result["agent_type"] = agent_cfg.name
        return result

    async def _run_mcp_experiment(
        self, agent_cfg: AgentConfig, failure_rate: float, seed: int,
        tracer: ExperimentTracer | None = None, experiment_id: str = "",
    ) -> dict[str, Any]:
        """Run a single MCP protocol experiment."""
        from chaos_engine.agents.mcp_agent import MCP_PLAYBOOK_GUIDANCE, MCPBaselineAgent, MCPLLMAgent
        from chaos_engine.chaos.mcp_proxy import MCPChaosProxy

        proxy = MCPChaosProxy(
            failure_rate=failure_rate,
            seed=seed,
            mock_mode=True,
        )

        if agent_cfg.kind in ("mcp_llm", "mcp_llm_playbook"):
            from chaos_engine.agents.llm_client import LLMClient
            llm_client = LLMClient(
                provider=agent_cfg.llm_provider,
                model=agent_cfg.llm_model,
                thinking=agent_cfg.thinking,
                seed=seed,
            )
            playbook = MCP_PLAYBOOK_GUIDANCE if agent_cfg.kind == "mcp_llm_playbook" else None
            agent = MCPLLMAgent(tool_executor=proxy, llm_client=llm_client, playbook_guidance=playbook,
                                tracer=tracer, experiment_id=experiment_id)
        else:
            agent = MCPBaselineAgent(tool_executor=proxy)

        result = await agent.run()
        result["agent_type"] = agent_cfg.name
        return result

    async def _run_a2a_experiment(
        self, agent_cfg: AgentConfig, failure_rate: float, seed: int,
        tracer: ExperimentTracer | None = None, experiment_id: str = "",
    ) -> dict[str, Any]:
        """Run a single A2A protocol experiment."""
        from chaos_engine.agents.a2a_workflow import A2A_PLAYBOOK_GUIDANCE, A2ABaselineAgent, A2ALLMAgent
        from chaos_engine.chaos.a2a_proxy import A2AChaosProxy

        proxy = A2AChaosProxy(
            failure_rate=failure_rate,
            seed=seed,
            mock_mode=True,
        )

        if agent_cfg.kind in ("a2a_llm", "a2a_llm_playbook"):
            from chaos_engine.agents.llm_client import LLMClient
            llm_client = LLMClient(
                provider=agent_cfg.llm_provider,
                model=agent_cfg.llm_model,
                thinking=agent_cfg.thinking,
                seed=seed,
            )
            playbook = A2A_PLAYBOOK_GUIDANCE if agent_cfg.kind == "a2a_llm_playbook" else None
            agent = A2ALLMAgent(a2a_executor=proxy, llm_client=llm_client, playbook_guidance=playbook,
                                tracer=tracer, experiment_id=experiment_id)
        else:
            agent = A2ABaselineAgent(a2a_executor=proxy)

        result = await agent.run()
        result["agent_type"] = agent_cfg.name
        return result

    async def _single_rate_generator(
        self, rate_index: int, rate: float,
        skip_ids: set[str] | None = None,
    ) -> AsyncGenerator[dict[str, Any], None]:
        """Yield experiment results for a single failure rate."""
        _skip = skip_ids or set()
        j_start = self.seed_range[0] if self.seed_range else 0
        j_end = self.seed_range[1] if self.seed_range else self.experiments_per_rate
        block_size = j_end - j_start

        # Open tracer for this rate (if trace mode is on)
        tracer: ExperimentTracer | None = None
        if self.trace:
            tracer = ExperimentTracer(self.output_dir)

        self.logger.info("[rate %.2f] j=%d..%d (%d per agent)",
                         rate, j_start, j_end - 1, block_size)

        try:
            for agent_cfg in self.agents:
                agent_name = agent_cfg.name
                self.logger.info("  Running %d %s experiments...", block_size, agent_name)

                for j in range(j_start, j_end):
                    seed = self.base_seed + (rate_index * 1000) + j
                    exp_id = f"{agent_name}-{rate}-{j}"

                    if exp_id in _skip:
                        continue

                    result = await self._run_single_experiment(
                        agent_cfg, rate, seed, tracer=tracer, experiment_id=exp_id,
                    )
                    result["experiment_id"] = exp_id
                    result["failure_rate"] = rate
                    result["seed"] = seed

                    if (j - j_start) % 50 == 0:
                        self.logger.info("    %s run %d/%d completed", agent_name, j - j_start, block_size)

                    yield result
        finally:
            if tracer:
                tracer.close()

        self.logger.info("  Completed rate %.2f", rate)

    async def _experiment_generator(
        self, skip_ids: set[str] | None = None,
    ) -> AsyncGenerator[dict[str, Any], None]:
        """Yield experiment results for all rates (legacy compatibility)."""
        for i, rate in enumerate(self.failure_rates):
            async for result in self._single_rate_generator(i, rate, skip_ids=skip_ids):
                yield result

    def _calculate_inconsistency(self, result: dict[str, Any]) -> int:
        """Detect data inconsistencies from partial workflow completion."""
        if result["status"] == Status.SUCCESS:
            return 0

        failed_at = result.get("failed_at")

        if not failed_at and result["status"] == Status.FAILURE:
            self.logger.warning("Result marked failure but failed_at is empty: %s", result)

        # Unified workflow inconsistency: order placed but not confirmed,
        # or inventory checked but order failed — data inconsistency risk.
        # Applies to all protocols (HTTP, MCP, A2A) equally.
        if failed_at in (WorkflowStep.PLACE_ORDER, WorkflowStep.CONFIRM_ORDER):
            return 1

        return 0

    def _flatten_result_for_csv(self, res: dict[str, Any]) -> dict[str, Any]:
        """Helper to flatten result dictionary for CSV writing."""
        return {
            "experiment_id": res["experiment_id"],
            "agent_type": res["agent_type"],
            "outcome": res["status"],
            "duration_ms": res["duration_ms"],
            "steps_completed": len(res["steps_completed"]),
            "failed_at": res.get("failed_at", ""),
            "inconsistencies_count": res.get("inconsistencies_count", 0),
            "retries": res.get("retries", 0),
            "seed": res["seed"],
            "failure_rate": res["failure_rate"],
            "llm_calls": res.get("llm_calls", 0),
            "input_chars": res.get("input_chars", 0),
            "output_chars": res.get("output_chars", 0),
            "prompt_tokens": res.get("prompt_tokens", 0),
            "completion_tokens": res.get("completion_tokens", 0),
            "reasoning_tokens": res.get("reasoning_tokens", 0),
            "steps_completed_list": res.get("steps_completed_list", ""),
        }
