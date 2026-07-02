"""Multi-run and N-agent comparison utilities (H.2).

Provides:
- N-agent metric extraction from aggregated_metrics.json
- Cross-run trend analysis (compare multiple experiment runs)
- Leaderboard ranking by composite score
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class AgentScore:
    """Scored result for a single agent across all failure rates."""
    name: str
    avg_success_rate: float = 0.0
    avg_duration_s: float = 0.0
    avg_inconsistencies: float = 0.0
    n_rates: int = 0

    @property
    def composite_score(self) -> float:
        """Higher is better: success * 100 - inconsistencies * 50 - duration * 2."""
        return self.avg_success_rate * 100 - self.avg_inconsistencies * 50 - self.avg_duration_s * 2


def extract_agent_names(metrics: dict[str, Any]) -> list[str]:
    """Discover agent names from metrics JSON (works for N agents)."""
    agents: set[str] = set()
    for rate_data in metrics.values():
        for key in rate_data:
            if key not in ("failure_rate", "n_experiments"):
                agents.add(key)
    return sorted(agents)


def extract_n_agent_data(metrics: dict[str, Any]) -> dict[str, Any]:
    """Extract chart-ready data for N agents.

    Returns::

        {
            "failure_rates": [0.0, 0.1, 0.3],
            "agents": {
                "baseline": {"success": [...], "duration": [...], "inconsistencies": [...]},
                "playbook": {"success": [...], "duration": [...], "inconsistencies": [...]},
                "aggressive": {...},
            }
        }
    """
    agent_names = extract_agent_names(metrics)
    result: dict[str, Any] = {
        "failure_rates": [],
        "agents": {name: {"success": [], "duration": [], "inconsistencies": []} for name in agent_names},
    }

    for rate_str in sorted(metrics.keys(), key=float):
        rate_data = metrics[rate_str]
        result["failure_rates"].append(rate_data.get("failure_rate", float(rate_str)))

        for name in agent_names:
            agent_data = rate_data.get(name, {})
            result["agents"][name]["success"].append(
                agent_data.get("success_rate", {}).get("mean", 0.0)
            )
            result["agents"][name]["duration"].append(
                agent_data.get("duration_s", {}).get("mean", 0.0)
            )
            result["agents"][name]["inconsistencies"].append(
                agent_data.get("inconsistencies", {}).get("mean", 0.0)
            )

    return result


def build_leaderboard(metrics: dict[str, Any]) -> list[AgentScore]:
    """Rank agents by composite score across all failure rates.

    Returns a sorted list (best first).
    """
    data = extract_n_agent_data(metrics)
    scores: list[AgentScore] = []

    for name, agent_data in data["agents"].items():
        n = len(agent_data["success"])
        if n == 0:
            continue
        scores.append(AgentScore(
            name=name,
            avg_success_rate=sum(agent_data["success"]) / n,
            avg_duration_s=sum(agent_data["duration"]) / n,
            avg_inconsistencies=sum(agent_data["inconsistencies"]) / n,
            n_rates=n,
        ))

    return sorted(scores, key=lambda s: s.composite_score, reverse=True)


@dataclass
class RunSummary:
    """Summary of a single experiment run for trend comparison."""
    run_id: str
    timestamp: str
    failure_rates: list[float] = field(default_factory=list)
    leaderboard: list[AgentScore] = field(default_factory=list)


def compare_runs(run_dirs: list[str | Path]) -> list[RunSummary]:
    """Compare multiple experiment runs for trend analysis.

    Args:
        run_dirs: List of paths to experiment run directories,
                  each containing aggregated_metrics.json.

    Returns:
        List of RunSummary objects sorted by timestamp.
    """
    summaries: list[RunSummary] = []

    for run_dir in run_dirs:
        run_dir = Path(run_dir)
        metrics_path = run_dir / "aggregated_metrics.json"
        if not metrics_path.exists():
            logger.warning("Skipping %s: no aggregated_metrics.json", run_dir)
            continue

        with open(metrics_path, "r", encoding="utf-8") as f:
            metrics = json.load(f)

        data = extract_n_agent_data(metrics)
        leaderboard = build_leaderboard(metrics)

        # Extract timestamp from dir name (e.g., run_20260314_153000)
        timestamp = run_dir.name.replace("run_", "")

        summaries.append(RunSummary(
            run_id=run_dir.name,
            timestamp=timestamp,
            failure_rates=data["failure_rates"],
            leaderboard=leaderboard,
        ))

    return sorted(summaries, key=lambda s: s.timestamp)


def print_leaderboard(metrics: dict[str, Any]) -> str:
    """Format a leaderboard as a text table."""
    board = build_leaderboard(metrics)
    lines = [
        f"{'Rank':<6}{'Agent':<20}{'Success%':<12}{'Incons':<10}{'Duration':<12}{'Score':<10}",
        "-" * 70,
    ]
    for i, s in enumerate(board, 1):
        lines.append(
            f"{i:<6}{s.name:<20}{s.avg_success_rate:>8.1%}   "
            f"{s.avg_inconsistencies:>7.3f}   {s.avg_duration_s:>8.3f}s   "
            f"{s.composite_score:>7.2f}"
        )
    return "\n".join(lines)
