"""Regenerate aggregated_metrics.json from rate_*.csv files.

Background: the unified runner (`scripts/run_experiment.py`) calls the
parametric runner once per rate. Each call writes `aggregated_metrics.json`
in mode "w", so only the LAST rate processed survives. The CSVs are the
source of truth; this script rebuilds the JSON from them.

Output format matches `_StreamingAggregator.build_metrics()` byte-for-byte
so existing tooling and dashboards keep working.

Usage:
    # All experiment subdirs that contain at least one rate_*.csv
    python scripts/reaggregate_metrics.py

    # Specific experiment dir
    python scripts/reaggregate_metrics.py --experiment G8_gemma4_e4b

    # Dry run — print what would be written
    python scripts/reaggregate_metrics.py --dry-run
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import re
from collections import defaultdict
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parent.parent
_EXPERIMENTS_DIR = _ROOT / "experiments"

# Only canonical rate files. Skips `rate_0.02.original_*.csv`,
# `rate_0.00.retired_*.csv`, and any other tagged variant left in the dir.
_RATE_FILE_RE = re.compile(r"^rate_\d+\.\d+\.csv$")


def _build_metrics_for_dir(rate_dir: Path) -> dict[str, Any]:
    """Compute the aggregated metrics dict for one experiment subdir.

    Replicates _StreamingAggregator.build_metrics() in
    src/chaos_engine/simulation/parametric.py (_StreamingAggregator) so we stay format-compatible.
    """
    # buckets[(rate, agent_type)] -> running stats
    buckets: dict[tuple[float, str], dict[str, float]] = defaultdict(
        lambda: {"n": 0, "successes": 0, "dur_sum": 0.0, "dur_sq_sum": 0.0,
                 "inc_sum": 0.0, "inc_sq_sum": 0.0}
    )
    agent_names_seen: list[str] = []
    seen_set: set[str] = set()

    for csv_path in sorted(rate_dir.glob("rate_*.csv")):
        if not _RATE_FILE_RE.match(csv_path.name):
            continue
        with open(csv_path, "r", encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                rate = float(row["failure_rate"])
                agent = row["agent_type"]
                if agent not in seen_set:
                    agent_names_seen.append(agent)
                    seen_set.add(agent)
                b = buckets[(rate, agent)]
                b["n"] += 1
                if row["outcome"] == "success":
                    b["successes"] += 1
                dur = float(row["duration_ms"] or 0)
                inc = float(row.get("inconsistencies_count") or 0)
                b["dur_sum"] += dur
                b["dur_sq_sum"] += dur * dur
                b["inc_sum"] += inc
                b["inc_sq_sum"] += inc * inc

    # Group by rate, format like _StreamingAggregator.build_metrics()
    rates_grouped: dict[float, dict[str, dict[str, Any]]] = defaultdict(dict)
    for (rate, agent), b in buckets.items():
        n = int(b["n"])
        if n == 0:
            continue
        succ = int(b["successes"])
        dur_mean = b["dur_sum"] / n
        dur_var = (b["dur_sq_sum"] / n) - dur_mean * dur_mean
        std_dur = math.sqrt(max(dur_var, 0.0)) if n > 1 else 0.0

        inc_mean = b["inc_sum"] / n
        inc_var = (b["inc_sq_sum"] / n) - inc_mean * inc_mean
        std_inc = math.sqrt(max(inc_var, 0.0)) if n > 1 else 0.0

        success_rate = succ / n
        std_sr = math.sqrt(success_rate * (1 - success_rate) / n) if n else 0.0

        rates_grouped[rate][agent] = {
            "n_runs": n,
            "success_rate": {"mean": success_rate, "std": round(std_sr, 6)},
            "duration_s": {
                "mean": dur_mean / 1000.0,
                "std": round(std_dur / 1000.0, 6),
            },
            "inconsistencies": {
                "mean": inc_mean,
                "std": round(std_inc, 6),
            },
        }

    n_agents = len(agent_names_seen)
    metrics: dict[str, Any] = {}
    for rate in sorted(rates_grouped):
        rate_key = str(rate)
        group = rates_grouped[rate]
        total = sum(v["n_runs"] for v in group.values())
        entry: dict[str, Any] = {
            "failure_rate": rate,
            "n_experiments": total // n_agents if n_agents else 0,
        }
        for agent_name in agent_names_seen:
            entry[agent_name] = group.get(agent_name, {})
        metrics[rate_key] = entry
    return metrics


def _find_target_dirs(only_experiment: str | None) -> list[Path]:
    """Find every leaf dir that contains rate_*.csv files."""
    if only_experiment:
        roots = [_EXPERIMENTS_DIR / only_experiment]
        if not roots[0].exists():
            raise FileNotFoundError(f"Experiment dir not found: {roots[0]}")
    else:
        roots = [d for d in _EXPERIMENTS_DIR.iterdir()
                 if d.is_dir() and not d.name.startswith("_")]
    targets: list[Path] = []
    for root in roots:
        for csv_path in root.rglob("rate_0.00.csv"):
            targets.append(csv_path.parent)
    return sorted(set(targets))


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Regenerate aggregated_metrics.json from rate_*.csv files",
    )
    parser.add_argument("--experiment", default=None,
                        help="Only process this experiment dir (e.g. G8_ministral14b)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print summary, don't write anything")
    args = parser.parse_args()

    targets = _find_target_dirs(args.experiment)
    if not targets:
        print("No rate_*.csv directories found.")
        return

    print(f"Reaggregating {len(targets)} experiment dirs\n")
    n_written = 0
    n_skipped = 0
    for tdir in targets:
        rel = tdir.relative_to(_ROOT)
        try:
            metrics = _build_metrics_for_dir(tdir)
        except Exception as e:
            print(f"  [error] {rel}: {e}")
            n_skipped += 1
            continue

        out_path = tdir / "aggregated_metrics.json"
        old_keys: list[str] = []
        if out_path.exists():
            try:
                with open(out_path, "r", encoding="utf-8") as f:
                    old = json.load(f)
                if isinstance(old, dict):
                    old_keys = sorted(old.keys())
            except Exception:
                pass

        new_keys = sorted(metrics.keys())
        delta = ""
        if old_keys != new_keys:
            delta = f" (was: [{','.join(old_keys) or '-'}] -> now: [{','.join(new_keys)}])"

        if args.dry_run:
            print(f"  [dry] {rel} — {len(metrics)} rates{delta}")
        else:
            with open(out_path, "w", encoding="utf-8") as f:
                json.dump(metrics, f, indent=2)
            print(f"  [ok ] {rel} — {len(metrics)} rates{delta}")
            n_written += 1

    print(f"\nDone. {n_written} JSON files written, {n_skipped} skipped.")


if __name__ == "__main__":
    main()
