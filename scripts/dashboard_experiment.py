"""Generic experiment dashboard — works with any experiments/ directory.

Reads the unified experiment structure (experiment.yaml + rate_*.csv + trace.jsonl)
and serves a live-updating HTML dashboard.

Usage:
    # Auto-detect all experiments
    python scripts/dashboard_experiment.py

    # Specific experiment
    python scripts/dashboard_experiment.py --experiment gemma4_e4b

    # Custom port
    python scripts/dashboard_experiment.py --port 8060
"""
from __future__ import annotations

import csv
import json
import math
import os
import re
import time
import webbrowser
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from typing import Any
import argparse

import yaml

_ROOT = Path(__file__).resolve().parent.parent
EXPERIMENTS_DIR = _ROOT / "experiments"


def _safe_int(v: Any) -> int:
    try:
        return int(float(v))
    except (ValueError, TypeError):
        return 0


def _safe_float(v: Any) -> float:
    try:
        return float(v)
    except (ValueError, TypeError):
        return 0.0


_PARAM_UNIT_MULT = {"K": 1e-6, "M": 1e-3, "B": 1.0, "T": 1e3}


def _params_to_b(s: Any) -> float | None:
    """Parse '5.4B', '~2B', '355B', '3.6B active' → float in B (billions). None if unparseable."""
    if s is None:
        return None
    raw = str(s).strip()
    if not raw:
        return None
    raw = raw.lstrip("~").strip()
    m = re.match(r"^([0-9]*\.?[0-9]+)\s*([KMBT])?", raw, flags=re.IGNORECASE)
    if not m:
        return None
    val = float(m.group(1))
    unit = (m.group(2) or "B").upper()
    return val * _PARAM_UNIT_MULT.get(unit, 1.0)


def _wilson_ci(k: int, n: int, z: float = 1.959963984540054) -> tuple[float, float]:
    """Wilson score 95% CI for proportion. Returns (low, high) in [0,1]."""
    if n <= 0:
        return (0.0, 0.0)
    p = k / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return (max(0.0, centre - half), min(1.0, centre + half))


def _load_yaml(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        return data if isinstance(data, dict) else {}
    except yaml.YAMLError:
        return {}


def discover_experiments() -> list[str]:
    if not EXPERIMENTS_DIR.exists():
        return []
    return sorted(
        d.name for d in EXPERIMENTS_DIR.iterdir()
        if d.is_dir() and (d / "experiment.yaml").exists()
    )


def _parse_yaml_plan(yaml_text: str) -> dict:
    """Extract planned rates, experiments_per_rate, protocols, model from yaml (regex, no pyyaml)."""
    plan: dict[str, Any] = {}

    # failure_rates: [0.0, 0.05, 0.10, 0.20, 0.30]
    m = re.search(r"failure_rates:\s*\[([^\]]+)\]", yaml_text)
    if m:
        plan["failure_rates"] = [float(x.strip()) for x in m.group(1).split(",")]

    # experiments_per_rate: 100
    m = re.search(r"experiments_per_rate:\s*(\d+)", yaml_text)
    if m:
        plan["experiments_per_rate"] = int(m.group(1))

    # protocols: [http, mcp, a2a]
    m = re.search(r"protocols:\s*\[([^\]]+)\]", yaml_text)
    if m:
        plan["protocols"] = [x.strip() for x in m.group(1).split(",")]

    # model id
    m = re.search(r"id:\s*(.+)", yaml_text)
    if m:
        plan["model_id"] = m.group(1).strip()

    # trace
    m = re.search(r"^trace:\s*(true|false)", yaml_text, re.MULTILINE)
    if m:
        plan["trace"] = m.group(1) == "true"

    # name
    m = re.search(r"^name:\s*(.+)", yaml_text, re.MULTILINE)
    if m:
        plan["name"] = m.group(1).strip()

    # created
    m = re.search(r"^created:\s*(.+)", yaml_text, re.MULTILINE)
    if m:
        plan["created"] = m.group(1).strip()

    # generation
    m = re.search(r"^generation:\s*(.+)", yaml_text, re.MULTILINE)
    if m:
        plan["generation"] = m.group(1).strip()

    return plan


def _get_timing(exp_dir: Path) -> dict:
    """Get experiment timing from CSV creation/modification times."""
    timing: dict[str, Any] = {}

    earliest_mtime = float("inf")
    latest_mtime = 0.0
    for model_dir in exp_dir.iterdir():
        if not model_dir.is_dir() or model_dir.name in ("playbooks", "logs", "reports"):
            continue
        for proto_dir in model_dir.iterdir():
            if not proto_dir.is_dir():
                continue
            for csv_file in proto_dir.glob("rate_*.csv"):
                mt = os.path.getmtime(csv_file)
                ct = os.path.getctime(csv_file)
                if ct < earliest_mtime:
                    earliest_mtime = ct
                if mt > latest_mtime:
                    latest_mtime = mt

    if earliest_mtime < float("inf"):
        timing["start"] = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(earliest_mtime))
        timing["start_ts"] = earliest_mtime
    if latest_mtime > 0:
        timing["last_activity"] = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(latest_mtime))
        timing["last_activity_ts"] = latest_mtime

    return timing


def scan_experiment(exp_name: str) -> dict:
    exp_dir = EXPERIMENTS_DIR / exp_name
    if not exp_dir.exists():
        return {"name": exp_name, "error": "not found"}

    yaml_path = exp_dir / "experiment.yaml"
    yaml_text = yaml_path.read_text(encoding="utf-8") if yaml_path.exists() else ""

    plan = _parse_yaml_plan(yaml_text)
    timing = _get_timing(exp_dir)

    combos: list[dict] = []
    all_rates: set[float] = set()
    all_agents: set[str] = set()

    for model_dir in sorted(exp_dir.iterdir()):
        if not model_dir.is_dir() or model_dir.name in ("playbooks", "logs", "reports"):
            continue
        model_tag = model_dir.name
        for proto_dir in sorted(model_dir.iterdir()):
            if not proto_dir.is_dir():
                continue
            protocol = proto_dir.name

            rate_data: dict[str, dict] = {}
            total_rows = 0
            trace_lines = 0
            trace_path = proto_dir / "trace.jsonl"
            if trace_path.exists():
                with open(trace_path, "r", encoding="utf-8") as f:
                    trace_lines = sum(1 for _ in f)

            body_total = 0
            body_diffs = 0
            step_stats: dict[str, dict] = {}

            if trace_path.exists():
                with open(trace_path, "r", encoding="utf-8") as f:
                    for line in f:
                        try:
                            t = json.loads(line)
                        except json.JSONDecodeError:
                            continue
                        bb = t.get("body_before_enrich")
                        step = t.get("step_name") or "unknown"
                        if bb is not None:
                            body_total += 1
                            if step not in step_stats:
                                step_stats[step] = {"total": 0, "diffs": 0}
                            step_stats[step]["total"] += 1
                            ba = t.get("body_after_enrich")
                            if bb != ba:
                                body_diffs += 1
                                step_stats[step]["diffs"] += 1

            for csv_file in sorted(proto_dir.glob("rate_*.csv")):
                rate_str = csv_file.stem.replace("rate_", "")
                try:
                    rate_val = float(rate_str)
                except ValueError:
                    continue
                all_rates.add(rate_val)

                agents: dict[str, dict] = {}
                with open(csv_file, "r", encoding="utf-8") as f:
                    for row in csv.DictReader(f):
                        total_rows += 1
                        agent = row.get("agent_type") or "unknown"
                        all_agents.add(agent)
                        if agent not in agents:
                            agents[agent] = {
                                "n": 0, "ok": 0, "fail": 0,
                                "dur_ms": 0.0, "retries": 0,
                                "llm_calls": 0, "ptok": 0, "ctok": 0,
                                "inc": 0,
                            }
                        a = agents[agent]
                        a["n"] += 1
                        if row.get("outcome") == "success":
                            a["ok"] += 1
                        else:
                            a["fail"] += 1
                        a["dur_ms"] += _safe_float(row.get("duration_ms", 0))
                        a["retries"] += _safe_int(row.get("retries", 0))
                        a["llm_calls"] += _safe_int(row.get("llm_calls", 0))
                        a["ptok"] += _safe_int(row.get("prompt_tokens", 0))
                        a["ctok"] += _safe_int(row.get("completion_tokens", 0))
                        a["inc"] += _safe_int(row.get("inconsistencies_count", 0))

                rate_data[rate_str] = agents

            combos.append({
                "model": model_tag,
                "protocol": protocol,
                "total_rows": total_rows,
                "rate_data": rate_data,
                "trace_lines": trace_lines,
                "body_total": body_total,
                "body_diffs": body_diffs,
                "step_stats": step_stats,
            })

    # Compute per-rate status for rate progress panel.
    # yaml's `experiments_per_rate` is often a stale seed value (e.g. 50) while
    # actual data scales beyond it via progressive top-ups (N=50 → 100 → 200).
    # Use max(yaml, observed_max_per_agent) so the headline planned-count
    # reflects the de-facto target rather than the stale seed.
    planned_rates = plan.get("failure_rates", [])
    n_per_rate_yaml = plan.get("experiments_per_rate", 0)
    n_agents = len(all_agents) if all_agents else 2
    max_observed_per_agent = max(
        (a.get("n", 0) for c in combos for ad in c["rate_data"].values() for a in ad.values()),
        default=0,
    )
    n_per_rate = max(n_per_rate_yaml, max_observed_per_agent)
    planned_per_rate = n_per_rate * n_agents
    total_planned = planned_per_rate * len(planned_rates) if planned_rates else 0

    rate_status: list[dict] = []
    for pr in planned_rates:
        rk = f"{pr:.2f}"
        actual = 0
        for c in combos:
            agents_at_rate = c["rate_data"].get(rk, {})
            actual += sum(a["n"] for a in agents_at_rate.values())
        status = "done" if actual >= planned_per_rate else ("progress" if actual > 0 else "pending")
        rate_status.append({
            "rate": pr,
            "actual": actual,
            "planned": planned_per_rate,
            "status": status,
        })

    total_done = sum(c["total_rows"] for c in combos)

    return {
        "name": exp_name,
        "yaml_preview": yaml_text[:_YAML_PREVIEW_LIMIT],
        "rates": sorted(all_rates),
        "agents": sorted(all_agents),
        "combos": combos,
        "total_experiments": total_done,
        "total_planned": total_planned,
        "total_traces": sum(c["trace_lines"] for c in combos),
        "plan": plan,
        "timing": timing,
        "rate_status": rate_status,
    }


def aggregate_for_compare(exp_name: str) -> dict | None:
    """Compact aggregate for cross-model comparison.

    Returns one entry per (agent, rate) with:
      n, ok, sr, ci_low, ci_high, dur_ms_mean, tokens_total_mean, retries_mean
    Plus the experiment's tags + roles (from experiment.yaml).
    """
    exp_dir = EXPERIMENTS_DIR / exp_name
    yaml_path = exp_dir / "experiment.yaml"
    if not yaml_path.exists():
        return None

    raw = _load_yaml(yaml_path)
    tags_raw = raw.get("tags", {}) if isinstance(raw.get("tags"), dict) else {}
    roles = raw.get("roles", []) if isinstance(raw.get("roles"), list) else []

    tags = {
        "family": tags_raw.get("family"),
        "architecture": tags_raw.get("architecture"),
        "total_params": tags_raw.get("total_params"),
        "active_params": tags_raw.get("active_params"),
        "total_params_b": _params_to_b(tags_raw.get("total_params")),
        "active_params_b": _params_to_b(tags_raw.get("active_params")),
        "reasoning": tags_raw.get("reasoning"),
        "provider": tags_raw.get("provider"),
        "region": tags_raw.get("region"),
        "runtime": tags_raw.get("runtime"),
    }

    model_block = raw.get("model", {}) if isinstance(raw.get("model"), dict) else {}
    model_id = model_block.get("id", "")
    model_tag = model_block.get("tag", "")

    agents_data: dict[str, dict] = {}
    rates_seen: set[float] = set()
    protocols_seen: set[str] = set()

    for model_dir in exp_dir.iterdir():
        if not model_dir.is_dir() or model_dir.name.startswith("_") \
                or model_dir.name in ("playbooks", "logs", "reports"):
            continue
        for proto_dir in model_dir.iterdir():
            if not proto_dir.is_dir():
                continue
            protocol = proto_dir.name.split("_")[0]
            protocols_seen.add(protocol)

            for csv_file in proto_dir.glob("rate_*.csv"):
                rate_str = csv_file.stem.replace("rate_", "")
                try:
                    rate_val = round(float(rate_str), 4)
                except ValueError:
                    continue
                rates_seen.add(rate_val)

                with open(csv_file, "r", encoding="utf-8") as f:
                    for row in csv.DictReader(f):
                        agent = row.get("agent_type") or "unknown"
                        if agent not in agents_data:
                            agents_data[agent] = {}
                        if rate_val not in agents_data[agent]:
                            agents_data[agent][rate_val] = {
                                "n": 0, "ok": 0,
                                "dur_ms_sum": 0.0, "tok_total_sum": 0,
                                "retries_sum": 0,
                            }
                        bucket = agents_data[agent][rate_val]
                        bucket["n"] += 1
                        if row.get("outcome") == "success":
                            bucket["ok"] += 1
                        bucket["dur_ms_sum"] += _safe_float(row.get("duration_ms", 0))
                        ptok = _safe_int(row.get("prompt_tokens", 0))
                        ctok = _safe_int(row.get("completion_tokens", 0))
                        bucket["tok_total_sum"] += ptok + ctok
                        bucket["retries_sum"] += _safe_int(row.get("retries", 0))

    # Finalize: compute SR, CI, means
    agents_out: dict[str, dict] = {}
    for agent, by_rate in agents_data.items():
        rates_list = []
        for rate in sorted(by_rate):
            b = by_rate[rate]
            n = b["n"]
            ok = b["ok"]
            sr = ok / n if n else 0.0
            lo, hi = _wilson_ci(ok, n)
            rates_list.append({
                "rate": rate,
                "n": n, "ok": ok,
                "sr": sr, "ci_low": lo, "ci_high": hi,
                "dur_ms_mean": (b["dur_ms_sum"] / n) if n else 0.0,
                "tok_total_mean": (b["tok_total_sum"] / n) if n else 0.0,
                "retries_mean": (b["retries_sum"] / n) if n else 0.0,
            })
        agents_out[agent] = {"rates": rates_list}

    return {
        "name": exp_name,
        "model_id": model_id,
        "model_tag": model_tag,
        "tags": tags,
        "roles": roles,
        "rates": sorted(rates_seen),
        "protocols": sorted(protocols_seen),
        "agents": agents_out,
    }


def build_compare_payload() -> dict:
    """Aggregate all experiments for cross-model comparison view."""
    out = []
    for exp_name in discover_experiments():
        agg = aggregate_for_compare(exp_name)
        if agg is not None and agg["agents"]:
            out.append(agg)
    return {"experiments": out, "count": len(out)}


def _snapshot_path(exp_name: str) -> Path:
    return EXPERIMENTS_DIR / exp_name / "snapshot.json"


def save_snapshot(exp_name: str) -> dict:
    """Scan experiment live, save to snapshot.json, return data."""
    data = scan_experiment(exp_name)
    path = _snapshot_path(exp_name)
    path.write_text(json.dumps(data, default=str, ensure_ascii=False), encoding="utf-8")
    return data


def load_snapshot(exp_name: str) -> dict | None:
    """Load cached snapshot.json if it exists."""
    path = _snapshot_path(exp_name)
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return None


_SELECTED_EXPERIMENT: str | None = None
_REFRESH_INTERVAL_MS: int = 15000
_YAML_PREVIEW_LIMIT: int = 2000


def build_html() -> str:
    experiments = discover_experiments()
    selected = _SELECTED_EXPERIMENT or (experiments[0] if experiments else "")
    # Initial load uses snapshot (offline) if available
    data = None
    if selected:
        data = load_snapshot(selected)
    if data is None:
        data = scan_experiment(selected) if selected else {}
    has_snapshot = _snapshot_path(selected).exists() if selected else False
    all_data = {
        "experiments": experiments,
        "selected": selected,
        "data": data,
        "has_snapshot": has_snapshot,
    }
    data_json = json.dumps(all_data, default=str)

    return ("""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Chaos Experiments Dashboard</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.7/dist/chart.umd.min.js"></script>
<style>
* { margin:0; padding:0; box-sizing:border-box; }
body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
       background:#0f1117; color:#e0e0e0; padding:20px; }
h1 { color:#fff; font-size:1.4em; margin-bottom:2px; }
.sub { color:#888; font-size:.85em; margin-bottom:16px; }
.clock { color:#555; font-size:.75em; }
.top-bar { display:flex; align-items:center; justify-content:space-between;
           flex-wrap:wrap; gap:8px; margin-bottom:12px; }

select { background:#1a1d27; color:#7dd3fc; border:1px solid #333; padding:6px 12px;
         border-radius:6px; font-size:.9em; cursor:pointer; }
select:hover { border-color:#7dd3fc; }

.summary { display:flex; flex-wrap:wrap; gap:12px 20px; margin-bottom:16px; padding:10px 14px;
           background:#1a1d27; border-radius:8px; }
.summary .s { text-align:center; min-width:80px; }
.summary .n { font-size:1.3em; font-weight:700; color:#fff; }
.summary .l { font-size:.7em; color:#888; }

.card { background:#1a1d27; border-radius:8px; padding:14px 16px; margin-bottom:16px; }
.card h2 { font-size:.85em; color:#aaa; text-transform:uppercase;
            letter-spacing:.05em; margin-bottom:10px; }
.card-full { grid-column:1/-1; }

.grid { display:grid; grid-template-columns:1fr 1fr; gap:16px; margin-bottom:16px; }
.grid-main { display:grid; grid-template-columns:1fr 400px; gap:16px; margin-bottom:20px; align-items:stretch; }
.grid-main > .card { width:100%; display:flex; flex-direction:column; }
.grid-main .card-chart { grid-column:1; }
.grid-main .card-yaml  { grid-column:2; min-height:0; }
.grid-main .card-yaml .yaml { flex:1; overflow-y:auto; margin:0; min-height:0; }
@media (max-width:1000px) { .grid { grid-template-columns:1fr; } }

/* thinking / model badges */
.badge { display:inline-block; padding:1px 5px; border-radius:3px; font-size:.65em;
         font-weight:600; letter-spacing:.03em; margin-left:4px; vertical-align:middle; }
.badge-think { background:#0e7490; color:#cffafe; }
.badge-nothink { background:#78350f; color:#fde68a; }
.badge-pb { background:#166534; color:#bbf7d0; }
.badge-nopb { background:#581c87; color:#e9d5ff; }

.axes-bar { display:flex; flex-wrap:wrap; gap:18px 24px; align-items:center; }
.axis-group { display:flex; align-items:center; gap:6px; }
.axis-label { font-size:.68em; color:#666; text-transform:uppercase; letter-spacing:.06em; margin-right:4px; }
.axis-btn { background:#1a1d27; color:#94a3b8; border:1px solid #2a2d3a; padding:4px 10px;
            border-radius:4px; font-size:.72em; font-weight:600; letter-spacing:.03em; cursor:pointer; }
.axis-btn:hover:not(.disabled):not(.forced) { border-color:#7dd3fc; color:#7dd3fc; }
.axis-btn.active { background:#0e4a6b; color:#7dd3fc; border-color:#0369a1; }
.axis-btn.forced { background:#1f2937; color:#9ca3af; border-color:#374151; cursor:default;
                    opacity:.85; box-shadow:inset 0 0 0 1px #4b5563; }
.axis-btn.disabled { background:#0f1117; color:#3a3f4b; border-color:#1a1d27;
                     cursor:not-allowed; opacity:.5; text-decoration:line-through; }

/* experiment header panel */
.exp-header { display:grid; grid-template-columns:1fr 1fr; gap:12px; margin-bottom:16px; }
@media (max-width:1000px) { .exp-header { grid-template-columns:1fr; } }
.exp-info { background:#1a1d27; border-radius:8px; padding:12px 16px; }
.exp-info h3 { font-size:.78em; color:#666; text-transform:uppercase; letter-spacing:.04em; margin-bottom:8px; }
.exp-meta { display:flex; flex-wrap:wrap; gap:4px 16px; font-size:.82em; }
.exp-meta .mk { color:#666; } .exp-meta .mv { color:#e0e0e0; font-weight:600; }
.exp-meta .mv.on { color:#22c55e; } .exp-meta .mv.off { color:#ef4444; }

/* progress bar */
.progress-wrap { margin:6px 0; }
.progress-bar { height:6px; background:#252836; border-radius:3px; overflow:hidden; }
.progress-fill { height:100%; border-radius:3px; transition:width .3s; }
.progress-fill.green { background:linear-gradient(90deg,#22c55e,#16a34a); }
.progress-fill.blue { background:linear-gradient(90deg,#60a5fa,#3b82f6); }
.progress-fill.amber { background:linear-gradient(90deg,#fbbf24,#f59e0b); }
.progress-label { font-size:.72em; color:#888; margin-top:2px; display:flex; justify-content:space-between; }

/* rate pills */
.rate-pills { display:flex; flex-wrap:wrap; gap:4px; margin-top:6px; }
.rate-pill { padding:3px 8px; border-radius:4px; font-size:.72em; font-weight:600;
             border:1px solid transparent; min-width:60px; text-align:center; }
.rate-pill.done { background:#052e16; color:#22c55e; border-color:#166534; }
.rate-pill.progress { background:#1c1917; color:#fbbf24; border-color:#78350f; animation:pulse-border 2s infinite; }
.rate-pill.pending { background:#1a1d27; color:#555; border-color:#252836; }
.rate-pill.deselected { background:#12141c; color:#444; border-color:#1e2030; opacity:.5; }
.rate-pill:hover { filter:brightness(1.3); }
@keyframes pulse-border { 0%,100%{border-color:#78350f} 50%{border-color:#fbbf24} }

.chart-wrap { background:#0f1117; border-radius:8px; padding:10px; }

/* agent legend checkboxes */
.legend-bar { display:flex; flex-wrap:wrap; gap:4px 12px; margin-bottom:8px; }
.legend-item { display:flex; align-items:center; gap:4px; font-size:.78em; cursor:pointer;
               padding:2px 6px; border-radius:4px; user-select:none; }
.legend-item:hover { background:#252836; }
.legend-item input { accent-color:var(--c); width:12px; height:12px; }
.legend-item .swatch { width:10px; height:10px; border-radius:2px; }
.legend-item.off { opacity:.4; }
.legend-group { font-size:.7em; color:#666; text-transform:uppercase; letter-spacing:.05em;
                margin-right:4px; padding:2px 0; }

/* table */
table { width:100%; border-collapse:collapse; font-size:.78em; }
th { text-align:right; padding:4px 6px; color:#888; border-bottom:2px solid #2a2d3a;
     font-size:.72em; text-transform:uppercase; white-space:nowrap; }
th:first-child { text-align:left; }
td { padding:3px 6px; border-bottom:1px solid #1e2130; text-align:right; white-space:nowrap; }
td:first-child { text-align:left; }
tr:hover { background:#252836; }
.sr { font-weight:600; }
.sr.good { color:#22c55e; }
.sr.bad  { color:#ef4444; }
.sr.mid  { color:#fbbf24; }
.timing { color:#94a3b8; }
.tokens { color:#c084fc; }
.retries-col { color:#f97316; }
.llm-col { color:#7dd3fc; }
.delta { color:#60a5fa; font-weight:600; }
.delta.neg { color:#ef4444; }

.trace-ok { color:#22c55e; font-weight:600; }
.trace-warn { color:#fbbf24; font-weight:600; }
.step-row { display:flex; justify-content:space-between; padding:3px 0;
            border-bottom:1px solid #1e2130; font-size:.85em; }

.yaml { background:#0f1117; border-radius:6px; padding:10px; font-family:'Fira Code',monospace;
        font-size:.7em; color:#888; overflow-y:auto; white-space:pre-wrap; }

.btn { background:#1a1d27; border:1px solid #333; color:#7dd3fc; padding:5px 12px;
       border-radius:6px; cursor:pointer; font-size:.78em; font-weight:600; transition:all .15s; }
.btn:hover { background:#2a2d3a; border-color:#7dd3fc; }
.btn.active { background:#0c4a6e; border-color:#7dd3fc; color:#fff; }
.btn.warn { color:#fbbf24; border-color:#78350f; }
.btn.warn.active { background:#78350f; color:#fbbf24; }

/* print / PDF */
@media print {
  body { background:#fff; color:#111; padding:10px; }
  .top-bar, .btn, .legend-item input, .yaml, .no-print { display:none !important; }
  .card { background:#f8f8f8; border:1px solid #ddd; break-inside:avoid; }
  .summary { background:#f0f0f0; }
  .summary .n { color:#111; }
  th, td { color:#333; border-color:#ccc; }
  .sr.good { color:#16a34a; } .sr.bad { color:#dc2626; } .sr.mid { color:#ca8a04; }
  .delta { color:#2563eb; } .delta.neg { color:#dc2626; }
  .timing { color:#475569; } .tokens { color:#7c3aed; }
  h1 { color:#111; } h2 { color:#555; }
  .chart-wrap { background:#fff; border:1px solid #ddd; }
}

/* compare view */
.cmp-grid { display:grid; grid-template-columns: 280px 1fr; gap:12px; align-items:start; }
@media (max-width:1100px) { .cmp-grid { grid-template-columns:1fr; } }
.cmp-sidebar { background:#1a1d27; border-radius:8px; padding:12px; max-height:88vh; overflow-y:auto; position:sticky; top:10px; }
.cmp-section { margin-bottom:12px; padding-bottom:10px; border-bottom:1px solid #252836; }
.cmp-section:last-child { border-bottom:0; }
.cmp-section h3 { font-size:.7em; color:#888; text-transform:uppercase; margin-bottom:6px; letter-spacing:.05em; }
.cmp-tags { display:flex; flex-wrap:wrap; gap:3px; }
.cmp-tag { background:#0f1117; color:#94a3b8; border:1px solid #252836; padding:3px 8px;
           border-radius:3px; font-size:.7em; font-weight:600; cursor:pointer; }
.cmp-tag:hover { border-color:#7dd3fc; color:#7dd3fc; }
.cmp-tag.on { background:#0c4a6e; color:#7dd3fc; border-color:#0369a1; }
.cmp-range { display:flex; gap:6px; align-items:center; }
.cmp-range input { background:#0f1117; color:#e0e0e0; border:1px solid #252836; padding:4px 6px;
                   border-radius:3px; font-size:.78em; width:75px; }
.cmp-main { display:flex; flex-direction:column; gap:12px; }
.cmp-toolbar { background:#1a1d27; border-radius:8px; padding:10px; display:flex; gap:6px; flex-wrap:wrap; }
.cmp-scenario { background:#1a1d27; border-radius:8px; padding:10px; display:flex; gap:6px; flex-wrap:wrap; align-items:center; }
.cmp-sl { font-size:.68em; color:#666; text-transform:uppercase; letter-spacing:.05em; margin-right:2px; padding-left:4px; }
.cmp-plot-wrap { background:#1a1d27; border-radius:8px; padding:14px; height:520px; }
.cmp-plot-wrap canvas { width:100% !important; height:100% !important; }
.cmp-table-wrap { background:#1a1d27; border-radius:8px; padding:12px; overflow-x:auto; }
.cmp-table-wrap h3 { font-size:.78em; color:#888; text-transform:uppercase; margin-bottom:8px; letter-spacing:.05em; }
.cmp-export { display:flex; gap:6px; }
</style>
</head>
<body>
<div class="top-bar">
  <div>
    <h1>Chaos Experiments Dashboard</h1>
    <p class="sub">Unified experiment monitoring</p>
  </div>
  <div style="display:flex;gap:6px;align-items:center;flex-wrap:wrap">
    <div style="display:inline-flex;border:1px solid #333;border-radius:6px;overflow:hidden;margin-right:6px">
      <button class="btn active" id="btn-view-single" onclick="setViewMode('single')" style="border:none;border-radius:0">Single</button>
      <button class="btn" id="btn-view-compare" onclick="setViewMode('compare')" style="border:none;border-radius:0;border-left:1px solid #333">Compare</button>
    </div>
    <select id="exp-select" onchange="switchExperiment()" class="single-only"></select>
    <button class="btn active single-only" id="btn-offline" onclick="setDashMode('offline')">Offline</button>
    <button class="btn single-only" id="btn-live" onclick="setDashMode('live')">Live</button>
    <button class="btn single-only" onclick="generateSnapshot()" title="Save current data to snapshot.json">Save snapshot</button>
    <button class="btn single-only" id="refresh-btn" onclick="toggleRefresh()">Auto-refresh: OFF</button>
    <button class="btn compare-only" onclick="reloadCompare()" style="display:none" title="Re-aggregate all experiments">Reload data</button>
    <button class="btn" onclick="window.print()">Export PDF</button>
    <span class="clock" id="clock"></span>
  </div>
</div>
<div id="app">Loading...</div>
<div id="compare-app" style="display:none">Loading compare data...</div>

<script>
let ALL = """ + data_json + """;
const REFRESH_MS = """ + str(_REFRESH_INTERVAL_MS) + """;
let autoRefresh = false;
let refreshTimer = null;
let srChart = null;
let hiddenAgents = new Set();
let dashMode = 'offline';
let hiddenRates = new Set(); // rate keys like "0.10" that are hidden from chart+table
let chartType = 'line'; // line, bar, radar, scatter
// Per-axis exclusion: { axis: Set(values) } — an agent whose axis value is here is hidden
let hiddenAxis = { proto: new Set(), model: new Set(), playbook: new Set(), thinking: new Set() };

function setChartType(t) { chartType = t; render(); }

function toggleRate(rateStr) {
  if (hiddenRates.has(rateStr)) hiddenRates.delete(rateStr);
  else hiddenRates.add(rateStr);
  render();
}

function switchExperiment() {
  hiddenRates = new Set();
  window.location.href = '/?experiment=' + encodeURIComponent(document.getElementById('exp-select').value);
}

function setDashMode(mode) {
  dashMode = mode;
  document.getElementById('btn-offline').classList.toggle('active', mode === 'offline');
  document.getElementById('btn-live').classList.toggle('active', mode === 'live');
  if (mode === 'live') {
    autoRefresh = true;
    document.getElementById('refresh-btn').textContent = 'Auto-refresh: ON';
    document.getElementById('refresh-btn').classList.add('active');
    startRefresh();
  } else {
    autoRefresh = false;
    document.getElementById('refresh-btn').textContent = 'Auto-refresh: OFF';
    document.getElementById('refresh-btn').classList.remove('active');
    stopRefresh();
  }
  reloadData();
}

function reloadData() {
  const modeParam = dashMode === 'offline' ? 'offline' : 'live';
  fetch('/?json=1&mode=' + modeParam + '&experiment=' + encodeURIComponent(ALL.selected))
    .then(r => r.json()).then(d => { ALL = d; render(); }).catch(() => {});
}

function generateSnapshot() {
  fetch('/?json=1&mode=snapshot&experiment=' + encodeURIComponent(ALL.selected))
    .then(r => r.json()).then(d => { ALL = d; render(); alert('Snapshot saved'); }).catch(() => {});
}

function toggleRefresh() {
  autoRefresh = !autoRefresh;
  const btn = document.getElementById('refresh-btn');
  btn.textContent = 'Auto-refresh: ' + (autoRefresh ? 'ON' : 'OFF');
  btn.classList.toggle('active', autoRefresh);
  if (autoRefresh) startRefresh(); else stopRefresh();
}

function startRefresh() {
  stopRefresh();
  refreshTimer = setInterval(() => {
    fetch('/?json=1&mode=live&experiment='+encodeURIComponent(ALL.selected))
      .then(r => r.json()).then(d => { ALL = d; render(); }).catch(() => {});
  }, REFRESH_MS);
}
function stopRefresh() { if (refreshTimer) { clearInterval(refreshTimer); refreshTimer=null; } }

function srClass(pct) {
  if (pct >= 80) return 'good';
  if (pct >= 50) return 'mid';
  return 'bad';
}

function fmtK(n) { return n >= 10000 ? (n/1000).toFixed(1)+'k' : n.toLocaleString(); }

// Parse agent name into structured parts
function parseAgent(a) {
  // Examples:  "http-glm45-think-pb", "http-glm45-nothink-nopb"
  //            "http-glm45-nopb" (think implicit), "http-glm45_nothink-nopb"
  const parts = a.split('-');
  const proto = parts[0] || 'other';
  let modelRaw = parts[1] || '';
  let reasoning = null;
  // Detect suffix on the model token (G3 style): glm45_nothink, glm45_think
  if (modelRaw.endsWith('_nothink')) {
    reasoning = 'nothink';
    modelRaw = modelRaw.slice(0, -'_nothink'.length);
  } else if (modelRaw.endsWith('_think')) {
    reasoning = 'think';
    modelRaw = modelRaw.slice(0, -'_think'.length);
  }
  const model = modelRaw;
  // Dash-delimited tokens (G7 style)
  if (!reasoning) {
    if (a.includes('-nothink-') || a.endsWith('-nothink')) reasoning = 'nothink';
    else if (a.includes('-think-') || a.endsWith('-think')) reasoning = 'think';
  }
  // Default: glm45 without explicit marker is think (native reasoning mode)
  if (!reasoning && model === 'glm45') reasoning = 'think';
  const rest = parts.slice(2).join('-');
  const playbook = a.endsWith('-pb') && !a.endsWith('-nopb') ? 'pb' : 'nopb';
  // Keep `thinking` key name for backward compat with existing callers
  return { proto, model, thinking: reasoning, playbook, rest };
}

// Group agents by protocol + model for legend
function agentGroups(agents) {
  const groups = {};
  agents.forEach(a => {
    const p = parseAgent(a);
    const key = p.proto + (p.model ? ' / ' + p.model : '');
    if (!groups[key]) groups[key] = [];
    groups[key].push(a);
  });
  return groups;
}

// Full human-readable label: "HTTP · GLM45 · REASONING · PB" (plain text, used in chart legend)
function fullAgentLabel(a) {
  const p = parseAgent(a);
  const parts = [];
  if (p.proto)    parts.push(p.proto.toUpperCase());
  if (p.model)    parts.push(p.model.toUpperCase());
  if (p.thinking === 'think')    parts.push('REASONING');
  else if (p.thinking === 'nothink') parts.push('NO-REASONING');
  if (p.playbook === 'pb')       parts.push('PB');
  else if (p.playbook === 'nopb') parts.push('NO-PB');
  return parts.join(' · ');
}

function chartLabel(a) {
  const p = parseAgent(a);
  const parts = [];
  if (p.proto) parts.push(p.proto.toUpperCase());
  if (p.thinking === 'think')    parts.push('THINK');
  else if (p.thinking === 'nothink') parts.push('NO-THINK');
  if (p.playbook === 'pb')       parts.push('PLAYBOOK');
  else if (p.playbook === 'nopb') parts.push('NO-PB');
  return parts.join(' · ');
}

function shortAgent(a) {
  const parts = a.split('-');
  if (parts.length <= 2) return a;
  // Drop mode tokens (shown as badges) to avoid duplication
  const MODE_TOKENS = new Set(['think','nothink','pb','nopb']);
  const kept = parts.slice(2).filter(p => !MODE_TOKENS.has(p));
  return kept.join('-');
}

function agentBadges(a) {
  const p = parseAgent(a);
  let h = '';
  if (p.thinking === 'think')   h += '<span class="badge badge-think">REASONING</span>';
  if (p.thinking === 'nothink') h += '<span class="badge badge-nothink">NO-REASONING</span>';
  if (p.playbook === 'pb')      h += '<span class="badge badge-pb">PB</span>';
  if (p.playbook === 'nopb')    h += '<span class="badge badge-nopb">NO-PB</span>';
  return h;
}

function toggleAgent(agent) {
  if (hiddenAgents.has(agent)) hiddenAgents.delete(agent);
  else hiddenAgents.add(agent);
  render();
}

function toggleAxis(axis, value) {
  const s = hiddenAxis[axis];
  if (s.has(value)) s.delete(value); else s.add(value);
  render();
}

// Agent matches current axis filters?
function agentMatchesAxes(a) {
  const p = parseAgent(a);
  if (hiddenAxis.proto.has(p.proto)) return false;
  if (hiddenAxis.model.has(p.model)) return false;
  if (p.playbook && hiddenAxis.playbook.has(p.playbook)) return false;
  if (p.thinking && hiddenAxis.thinking.has(p.thinking)) return false;
  return true;
}

const COLORS = ['#ef4444','#22c55e','#60a5fa','#fbbf24','#a78bfa','#f97316',
                '#ec4899','#14b8a6','#f43f5e','#84cc16','#06b6d4','#e879f9'];

function render() {
  const app = document.getElementById('app');
  document.getElementById('clock').textContent = new Date().toLocaleTimeString();

  const sel = document.getElementById('exp-select');
  sel.innerHTML = ALL.experiments.map(e =>
    `<option value="${e}" ${e===ALL.selected?'selected':''}>${e}</option>`
  ).join('');

  const d = ALL.data;
  if (!d || d.error) { app.innerHTML = '<p>No experiment data found.</p>'; return; }

  const combos = d.combos || [];
  const visibleAgents = d.agents.filter(a => !hiddenAgents.has(a) && agentMatchesAxes(a));

  // Totals
  let totalExp=0, totalDur=0, totalPtok=0, totalCtok=0, totalOk=0, totalRetries=0, totalLLM=0;
  combos.forEach(c => { Object.values(c.rate_data).forEach(agents => {
    Object.values(agents).forEach(a => {
      totalExp+=a.n; totalDur+=a.dur_ms; totalPtok+=a.ptok; totalCtok+=a.ctok;
      totalOk+=a.ok; totalRetries+=a.retries; totalLLM+=a.llm_calls;
    });
  });});
  const totalTok = totalPtok + totalCtok;
  const avgDurS = totalExp ? (totalDur/totalExp/1000).toFixed(1) : '-';
  const avgTok = totalExp ? Math.round(totalTok/totalExp) : '-';

  let bodyTotal=0, bodyDiffs=0;
  combos.forEach(c => { bodyTotal+=c.body_total; bodyDiffs+=c.body_diffs; });

  // ── Enhanced header ──
  const plan = d.plan || {};
  const timing = d.timing || {};
  const rateStatus = d.rate_status || [];
  const totalPlanned = d.total_planned || 0;
  const pctDone = totalPlanned ? Math.round(100*totalExp/totalPlanned) : (totalExp ? 100 : 0);
  const overallSR = totalExp ? Math.round(100*totalOk/totalExp) : 0;

  // Elapsed time — sum of experiment durations (actual inference time, excludes pauses)
  let elapsedStr = '-', etaStr = '-', throughput = '-';
  if (totalDur > 0) {
    const elapsedS = totalDur / 1000;
    const elapsedH = Math.floor(elapsedS/3600);
    const elapsedM = Math.floor((elapsedS%3600)/60);
    elapsedStr = elapsedH > 0 ? elapsedH+'h '+elapsedM+'m' : elapsedM+'m';
    if (totalExp > 0) {
      const expPerMin = totalExp / (elapsedS/60);
      throughput = expPerMin.toFixed(1) + ' exp/min';
      if (totalPlanned > totalExp) {
        const remaining = totalPlanned - totalExp;
        const etaS = remaining / expPerMin * 60;
        const etaH = Math.floor(etaS/3600);
        const etaM = Math.floor((etaS%3600)/60);
        etaStr = etaH > 0 ? '~'+etaH+'h '+etaM+'m' : '~'+etaM+'m';
      } else {
        etaStr = 'Done';
      }
    }
  }

  let html = '<div class="exp-header">';

  // Left: Experiment info + progress
  html += '<div class="exp-info"><h3>Experiment</h3>';
  html += '<div class="exp-meta">';
  html += `<div><span class="mk">Gen:</span> <span class="mv">${plan.generation||'-'}</span></div>`;
  html += `<div><span class="mk">Model:</span> <span class="mv">${plan.model_id||'-'}</span></div>`;
  html += `<div><span class="mk">Protocols:</span> <span class="mv">${(plan.protocols||[]).join(', ')||'-'}</span></div>`;
  html += `<div><span class="mk">Trace:</span> <span class="mv ${plan.trace===true?'on':''}">${plan.trace===true?'ON':plan.trace===false?'OFF':'-'}</span></div>`;
  html += `<div><span class="mk">Created:</span> <span class="mv">${plan.created||'-'}</span></div>`;
  html += '</div>';

  // Progress bar
  html += '<div class="progress-wrap">';
  html += `<div class="progress-bar"><div class="progress-fill ${pctDone>=100?'green':pctDone>0?'blue':'amber'}" style="width:${Math.min(pctDone,100)}%"></div></div>`;
  html += `<div class="progress-label"><span>${totalExp.toLocaleString()} / ${totalPlanned?totalPlanned.toLocaleString():'?'} experiments (${pctDone}%)</span><span>SR: <span class="sr ${srClass(overallSR)}">${overallSR}%</span></span></div>`;
  html += '</div>';

  // Timing row
  html += '<div class="exp-meta" style="margin-top:6px">';
  html += `<div><span class="mk">Elapsed:</span> <span class="mv">${elapsedStr}</span></div>`;
  html += `<div><span class="mk">Throughput:</span> <span class="mv">${throughput}</span></div>`;
  html += `<div><span class="mk">ETA:</span> <span class="mv">${etaStr}</span></div>`;
  html += `<div><span class="mk">Avg dur:</span> <span class="mv">${avgDurS}s</span></div>`;
  html += `<div><span class="mk">Avg tok:</span> <span class="mv">${avgTok}</span></div>`;
  html += `<div><span class="mk">Traces:</span> <span class="mv">${d.total_traces.toLocaleString()}</span></div>`;
  html += `<div><span class="mk">Body diffs:</span> <span class="mv ${bodyDiffs?'trace-warn':'trace-ok'}">${bodyDiffs}/${bodyTotal}</span></div>`;
  html += '</div></div>';

  // Right: Rate progress panel
  html += '<div class="exp-info"><h3>Rate Progress</h3>';
  if (rateStatus.length) {
    html += '<div class="rate-pills">';
    rateStatus.forEach(rs => {
      const label = Math.round(rs.rate*100)+'%';
      const sub = rs.actual+'/'+rs.planned;
      html += `<div class="rate-pill ${rs.status}"><div>${label}</div><div style="font-size:.85em;font-weight:400;margin-top:1px">${sub}</div></div>`;
    });
    html += '</div>';

    // Mini summary under pills
    const doneRates = rateStatus.filter(r=>r.status==='done').length;
    const progRates = rateStatus.filter(r=>r.status==='progress').length;
    const totalR = rateStatus.length;
    html += `<div style="margin-top:8px;font-size:.75em;color:#666">${doneRates} done, ${progRates} in progress, ${totalR-doneRates-progRates} pending</div>`;
  } else {
    html += '<div style="color:#555;font-size:.82em">No planned rates found in experiment.yaml</div>';
  }

  // Token summary
  html += '<div style="margin-top:10px;border-top:1px solid #252836;padding-top:8px">';
  html += '<div class="exp-meta">';
  html += `<div><span class="mk">Total tokens:</span> <span class="mv tokens">${fmtK(totalTok)}</span></div>`;
  html += `<div><span class="mk">Prompt:</span> <span class="mv tokens">${fmtK(totalPtok)}</span></div>`;
  html += `<div><span class="mk">Completion:</span> <span class="mv tokens">${fmtK(totalCtok)}</span></div>`;
  html += `<div><span class="mk">Retries:</span> <span class="mv retries-col">${totalRetries.toLocaleString()}</span></div>`;
  html += `<div><span class="mk">LLM calls:</span> <span class="mv llm-col">${totalLLM.toLocaleString()}</span></div>`;
  html += '</div></div>';

  html += '</div>';
  html += '</div>'; // close exp-header

  // ── Axis-based filters ──
  // Canonical axis definitions: full catalogue of possible values
  const AXES = [
    { key:'proto',    label:'Protocol', values:['http','mcp','a2a'] },
    { key:'model',    label:'Model',    values:null },          // dynamic
    { key:'playbook', label:'Playbook', values:['pb','nopb'] },
    { key:'thinking', label:'Reasoning', values:['think','nothink'] },
  ];
  // Which values are observed in this experiment, per axis
  const observed = { proto:new Set(), model:new Set(), playbook:new Set(), thinking:new Set() };
  d.agents.forEach(a => {
    const p = parseAgent(a);
    if (p.proto)    observed.proto.add(p.proto);
    if (p.model)    observed.model.add(p.model);
    if (p.playbook) observed.playbook.add(p.playbook);
    if (p.thinking) observed.thinking.add(p.thinking);
  });

  html += '<div class="card no-print"><h2>Filters</h2><div class="axes-bar">';
  AXES.forEach(ax => {
    const obs = observed[ax.key];
    const vals = ax.values || Array.from(obs).sort();
    if (vals.length === 0) return;
    html += `<div class="axis-group"><span class="axis-label">${ax.label}</span>`;
    vals.forEach(v => {
      const isObserved = obs.has(v);
      const onlyOne = isObserved && obs.size === 1;                 // forced on
      const active  = isObserved && !hiddenAxis[ax.key].has(v);
      const cls = !isObserved ? 'axis-btn disabled'
                : onlyOne     ? 'axis-btn active forced'
                : active      ? 'axis-btn active'
                :               'axis-btn';
      const click = (isObserved && !onlyOne) ? `onclick="toggleAxis('${ax.key}','${v}')"` : '';
      const title = !isObserved ? 'No data for this value in this experiment'
                  : onlyOne     ? 'Only value present — forced on'
                  :               'Click to toggle';
      const VALUE_LABELS = { think:'YES', nothink:'NO', pb:'YES', nopb:'NO' };
      const displayLabel = VALUE_LABELS[v] !== undefined ? VALUE_LABELS[v] : v.toUpperCase();
      html += `<button type="button" class="${cls}" ${click} title="${title}">${displayLabel}</button>`;
    });
    html += '</div>';
  });

  // Rate filter buttons
  html += '<div class="axis-group"><span class="axis-label">Rate</span>';
  d.rates.forEach(r => {
    const rk = r.toFixed(2);
    const label = Math.round(r*100)+'%';
    const active = !hiddenRates.has(rk);
    const cls = active ? 'axis-btn active' : 'axis-btn';
    html += `<button type="button" class="${cls}" onclick="toggleRate('${rk}')" title="Click to toggle">${label}</button>`;
  });
  html += '</div>';

  html += '</div></div>';

  // ── Grid: chart (left) + yaml (right) ──
  html += '<div class="grid-main">';

  // Left: Chart
  html += '<div class="card card-chart">';
  html += '<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px">';
  html += '<h2 style="margin:0">Success Rate by Failure Rate</h2>';
  html += '<div class="axis-group" style="margin:0">';
  ['line','bar','radar','scatter'].forEach(t => {
    const cls = chartType === t ? 'axis-btn active' : 'axis-btn';
    const icons = {line:'\u2571',bar:'\u2587',radar:'\u25CE',scatter:'\u2022\u2022'};
    html += `<button type="button" class="${cls}" onclick="setChartType('${t}')" title="${t}">${icons[t]} ${t[0].toUpperCase()+t.slice(1)}</button>`;
  });
  html += '</div></div>';
  html += '<div class="chart-wrap"><canvas id="sr-chart" height="70"></canvas></div></div>';

  // Right: experiment.yaml
  html += '<div class="card card-yaml"><h2>experiment.yaml</h2>';
  html += `<pre class="yaml">${(d.yaml_preview||'').replace(/</g,'&lt;')}</pre></div>`;

  html += '</div>'; // close grid-main

  // ── Rate table (full width) ──
  // Helper to aggregate agent data across combos for a given rate
  function rateAgentData(rate) {
    const rk = rate.toFixed(2);
    const totals = {};
    d.agents.forEach(a => { totals[a] = {ok:0,n:0,dur:0,ptok:0,ctok:0,retries:0,llm:0,inc:0}; });
    combos.forEach(c => {
      const agents = c.rate_data[rk] || {};
      Object.entries(agents).forEach(([a, v]) => {
        if (!totals[a]) totals[a] = {ok:0,n:0,dur:0,ptok:0,ctok:0,retries:0,llm:0,inc:0};
        totals[a].ok+=v.ok; totals[a].n+=v.n; totals[a].dur+=v.dur_ms;
        totals[a].ptok+=v.ptok; totals[a].ctok+=v.ctok;
        totals[a].retries+=v.retries; totals[a].llm+=v.llm_calls; totals[a].inc+=v.inc;
      });
    });
    return totals;
  }

  // Split agents into pairs for responsive tables (2 agents per table = fits without scroll)
  const AGENTS_PER_TABLE = 2;
  const agentChunks = [];
  for (let i = 0; i < visibleAgents.length; i += AGENTS_PER_TABLE) {
    agentChunks.push(visibleAgents.slice(i, i + AGENTS_PER_TABLE));
  }

  const visibleRates = d.rates.filter(r => !hiddenRates.has(r.toFixed(2)));

  agentChunks.forEach((chunk, chunkIdx) => {
    const agentSep = 'border-left:2px solid #3a3d4a;';
    const showDelta = chunk.length >= 2;
    const title = agentChunks.length > 1 ? `Rate Breakdown (${chunkIdx+1}/${agentChunks.length})` : 'Rate Breakdown';
    html += `<div class="card"><h2>${title}</h2>`;
    html += '<table>';

    // Agent header row — bold the parts that differ between the pair
    const chunkLabels = chunk.map(a => fullAgentLabel(a).split(' \u00b7 '));
    const diffIndices = new Set();
    if (chunk.length === 2) {
      const [p0, p1] = chunkLabels;
      const maxLen = Math.max(p0.length, p1.length);
      for (let k = 0; k < maxLen; k++) {
        if ((p0[k] || '') !== (p1[k] || '')) diffIndices.add(k);
      }
    }
    html += '<tr><th></th>';
    chunk.forEach((a, i) => {
      const sep = i > 0 ? agentSep : '';
      const label = chunkLabels[i].map((part, k) =>
        diffIndices.has(k) ? `<strong style="color:#fff">${part}</strong>` : part
      ).join(' \u00b7 ');
      html += `<th colspan="6" style="text-align:center;border-bottom:1px solid #2a2d3a;padding-bottom:6px;font-size:.78em;${sep}">${label}</th>`;
    });
    if (showDelta) html += '<th></th>';
    html += '</tr>';

    // Metric header row
    html += '<tr><th style="text-align:left">Rate</th>';
    chunk.forEach((_, i) => {
      const sep = i > 0 ? ` style="${agentSep}"` : '';
      html += `<th${sep}>SR</th><th>N</th><th>Dur</th><th>Tok</th><th>Ret</th><th>LLM</th>`;
    });
    if (showDelta) html += '<th>Delta SR</th>';
    html += '</tr>';

    // Data rows
    visibleRates.forEach(r => {
      const totals = rateAgentData(r);
      html += `<tr><td style="color:#7dd3fc;font-weight:600;text-align:left">${Math.round(r*100)}%</td>`;
      let srs = [];
      chunk.forEach((a,i) => {
        const t = totals[a];
        const sr = t.n ? Math.round(100*t.ok/t.n) : null;
        srs.push(sr);
        const avgS = t.n ? (t.dur/t.n/1000).toFixed(1) : '-';
        const avgTk = t.n ? Math.round((t.ptok+t.ctok)/t.n) : '-';
        const avgRet = t.n ? (t.retries/t.n).toFixed(1) : '-';
        const avgLLM = t.n ? (t.llm/t.n).toFixed(1) : '-';
        const sep = i > 0 ? ` style="${agentSep}"` : '';
        html += `<td${sep}><span class="sr ${sr!==null?srClass(sr):''}">${sr!==null?sr+'%':'-'}</span></td>`;
        html += `<td style="color:#555">${t.n||'-'}</td>`;
        html += `<td class="timing">${avgS}s</td>`;
        html += `<td class="tokens">${avgTk}</td>`;
        html += `<td class="retries-col">${avgRet}</td>`;
        html += `<td class="llm-col">${avgLLM}</td>`;
      });
      if (showDelta) {
        const delta = (srs[0]!==null && srs[1]!==null) ? srs[1]-srs[0] : null;
        const ds = delta!==null ? ((delta>=0?'+':'')+delta+'pp') : '-';
        html += `<td class="delta ${delta!==null&&delta<0?'neg':''}">${ds}</td>`;
      }
      html += '</tr>';
    });

    // Totals row
    html += '<tr style="border-top:2px solid #2a2d3a;font-weight:600"><td style="text-align:left">TOTAL</td>';
    chunk.forEach((a,i) => {
      let tOk=0,tN=0,tDur=0,tPtok=0,tCtok=0,tRet=0,tLLM=0;
      visibleRates.forEach(r => {
        const t = rateAgentData(r)[a];
        tOk+=t.ok; tN+=t.n; tDur+=t.dur; tPtok+=t.ptok; tCtok+=t.ctok; tRet+=t.retries; tLLM+=t.llm;
      });
      const sr = tN ? Math.round(100*tOk/tN) : null;
      const avgS = tN ? (tDur/tN/1000).toFixed(1) : '-';
      const avgTk = tN ? Math.round((tPtok+tCtok)/tN) : '-';
      const sep = i > 0 ? ` style="${agentSep}"` : '';
      html += `<td${sep}><span class="sr ${sr!==null?srClass(sr):''}">${sr!==null?sr+'%':'-'}</span></td>`;
      html += `<td style="color:#555">${tN}</td>`;
      html += `<td class="timing">${avgS}s</td>`;
      html += `<td class="tokens">${avgTk}</td>`;
      html += `<td class="retries-col">${tN?(tRet/tN).toFixed(1):'-'}</td>`;
      html += `<td class="llm-col">${tN?(tLLM/tN).toFixed(1):'-'}</td>`;
    });
    if (showDelta) html += '<td></td>';
    html += '</tr>';

    html += '</table></div>';
  }); // end agentChunks.forEach

  app.innerHTML = html;

  // ── Draw chart ──
  if (srChart) { srChart.destroy(); srChart = null; }
  const canvas = document.getElementById('sr-chart');
  if (canvas && visibleRates.length > 0) {
    const labels = visibleRates.map(r => Math.round(r*100)+'%');

    // Compute SR points and duration per agent per rate
    const agentStats = visibleAgents.map(agent => {
      const i = d.agents.indexOf(agent);
      const color = COLORS[i % COLORS.length];
      const srPoints = [];
      const durPoints = [];
      visibleRates.forEach(r => {
        const rk = r.toFixed(2);
        let ok=0, n=0, dur=0;
        combos.forEach(c => {
          const ag = (c.rate_data[rk]||{})[agent];
          if (ag) { ok+=ag.ok; n+=ag.n; dur+=ag.dur_ms||0; }
        });
        srPoints.push(n ? Math.round(100*ok/n) : null);
        durPoints.push(n ? dur/n/1000 : null);
      });
      return { agent, i, color, srPoints, durPoints, label: chartLabel(agent) };
    });

    // Auto-scale Y axis
    let yMin = 100;
    agentStats.forEach(a => a.srPoints.forEach(v => { if (v !== null && v < yMin) yMin = v; }));
    yMin = Math.max(0, Math.floor(yMin / 10) * 10 - 5);

    const legendGapPlugin = {
      id:'legendGap',
      beforeInit(chart){
        const origFit = chart.legend.fit;
        chart.legend.fit = function(){ origFit.call(this); this.width += 40; };
      }
    };

    const legendOpts = { display:true, position:'right', align:'center',
      labels:{ color:'#ccc', font:{size:11}, usePointStyle:true, pointStyle:'rect', boxWidth:12, padding:10 } };

    if (chartType === 'scatter') {
      // Scatter: X = avg duration (s), Y = SR (%)
      const datasets = agentStats.map(a => ({
        label: a.label,
        data: a.srPoints.map((sr, j) => sr !== null && a.durPoints[j] !== null ? {x: a.durPoints[j], y: sr} : null).filter(Boolean),
        borderColor: a.color,
        backgroundColor: a.color + '66',
        pointRadius: 5, pointHoverRadius: 7,
      }));
      srChart = new Chart(canvas, {
        type:'scatter',
        data:{ datasets },
        plugins:[legendGapPlugin],
        options:{
          responsive:true, maintainAspectRatio:true, aspectRatio:1.5,
          layout:{ padding:{ top:12, bottom:8, left:8, right:8 } },
          plugins:{ legend:legendOpts },
          scales:{
            x:{ title:{display:true,text:'Avg Duration (s)',color:'#666',font:{size:11}}, ticks:{color:'#666',font:{size:10}}, grid:{color:'#1a1d27'} },
            y:{ title:{display:true,text:'Success Rate (%)',color:'#666',font:{size:11}}, ticks:{color:'#666',font:{size:10}}, grid:{color:'#1a1d27'},
                min:yMin, max:105 },
          }
        }
      });
    } else if (chartType === 'radar') {
      const datasets = agentStats.map(a => ({
        label: a.label,
        data: a.srPoints.map(v => v !== null ? v : 0),
        borderColor: a.color,
        backgroundColor: a.color + '22',
        borderWidth: 2, pointRadius: 3,
      }));
      srChart = new Chart(canvas, {
        type:'radar',
        data:{ labels, datasets },
        plugins:[legendGapPlugin],
        options:{
          responsive:true, maintainAspectRatio:true, aspectRatio:1.5,
          layout:{ padding:{ top:12, bottom:8, left:8, right:8 } },
          plugins:{ legend:legendOpts },
          scales:{
            r:{ min:yMin, max:105, ticks:{color:'#666',font:{size:9},backdropColor:'transparent'},
                pointLabels:{color:'#ccc',font:{size:10}}, grid:{color:'#1a1d27'}, angleLines:{color:'#1a1d27'} }
          }
        }
      });
    } else {
      // Line or Bar
      const datasets = agentStats.map(a => ({
        label: a.label,
        data: a.srPoints,
        borderColor: a.color,
        backgroundColor: chartType === 'bar' ? a.color + '88' : a.color + '18',
        fill: chartType === 'line', tension:.3, pointRadius: chartType === 'line' ? 3 : 0, borderWidth:2,
      }));
      srChart = new Chart(canvas, {
        type: chartType,
        data:{ labels, datasets },
        plugins:[legendGapPlugin],
        options:{
          responsive:true, maintainAspectRatio:true, aspectRatio:1.5,
          layout:{ padding:{ top:12, bottom:8, left:8, right:8 } },
          plugins:{ legend:legendOpts },
          scales:{
            x:{ title:{display:true,text:'Failure Rate',color:'#666',font:{size:11}}, ticks:{color:'#666',font:{size:10}}, grid:{color:'#1a1d27'} },
            y:{ title:{display:true,text:'Success Rate (%)',color:'#666',font:{size:11}}, ticks:{color:'#666',font:{size:10}}, grid:{color:'#1a1d27'},
                min:yMin, max:105 },
          }
        }
      });
    }
  }
}

// ── Compare view ─────────────────────────────────────────────────────────────
let viewMode = 'single';
let COMPARE = null;
let compareLoaded = false;
let compareChart = null;
let comparePlotType = 'cross';

const compareFilter = {
  architecture: new Set(),
  family: new Set(),
  reasoning: new Set(),
  region: new Set(),
  runtime: new Set(),
  totalParamsRange: null,
  activeParamsRange: null,
  roles: new Set(),
  protocol: 'http',
  playbook: 'all',
  thinking: 'any',
  fixedRate: 0.10,
};

const ARCH_COLORS = { dense:'#22c55e', moe:'#a78bfa', matformer:'#fbbf24', default:'#94a3b8' };
function archColor(a) { return ARCH_COLORS[a] || ARCH_COLORS.default; }

function setViewMode(mode) {
  viewMode = mode;
  document.getElementById('btn-view-single').classList.toggle('active', mode === 'single');
  document.getElementById('btn-view-compare').classList.toggle('active', mode === 'compare');
  document.getElementById('app').style.display = mode === 'single' ? '' : 'none';
  document.getElementById('compare-app').style.display = mode === 'compare' ? '' : 'none';
  document.querySelectorAll('.single-only').forEach(el => { el.style.display = mode==='single' ? '' : 'none'; });
  document.querySelectorAll('.compare-only').forEach(el => { el.style.display = mode==='compare' ? '' : 'none'; });
  if (mode === 'compare') {
    if (!compareLoaded) loadCompareData();
    else renderCompare();
  } else {
    render();
  }
}

function loadCompareData() {
  const root = document.getElementById('compare-app');
  root.innerHTML = '<div style="padding:40px;color:#666">Aggregating all experiments…</div>';
  fetch('/?json=1&view=compare')
    .then(r => r.json())
    .then(d => {
      COMPARE = d;
      compareLoaded = true;
      const totals = d.experiments.map(e => e.tags.total_params_b).filter(v => v != null);
      const actives = d.experiments.map(e => e.tags.active_params_b).filter(v => v != null);
      if (totals.length) compareFilter.totalParamsRange = [Math.min(...totals), Math.max(...totals)];
      if (actives.length) compareFilter.activeParamsRange = [Math.min(...actives), Math.max(...actives)];
      renderCompare();
    })
    .catch(err => {
      root.innerHTML = '<div style="padding:20px;color:#ef4444">Error: ' + err + '</div>';
    });
}

function reloadCompare() { compareLoaded = false; loadCompareData(); }

function applyFiltersToExperiments() {
  if (!COMPARE) return [];
  return COMPARE.experiments.filter(e => {
    const t = e.tags, f = compareFilter;
    if (f.architecture.size && !f.architecture.has(t.architecture)) return false;
    if (f.family.size && !f.family.has(t.family)) return false;
    if (f.reasoning.size && !f.reasoning.has(String(t.reasoning))) return false;
    if (f.region.size && !f.region.has(t.region)) return false;
    if (f.runtime.size && !f.runtime.has(t.runtime)) return false;
    if (f.totalParamsRange && t.total_params_b != null) {
      if (t.total_params_b < f.totalParamsRange[0] || t.total_params_b > f.totalParamsRange[1]) return false;
    }
    if (f.activeParamsRange && t.active_params_b != null) {
      if (t.active_params_b < f.activeParamsRange[0] || t.active_params_b > f.activeParamsRange[1]) return false;
    }
    if (f.roles.size) {
      const overlap = (e.roles||[]).some(r => f.roles.has(r));
      if (!overlap) return false;
    }
    return true;
  });
}

function agentMatchesScenario(agentName) {
  const p = parseAgent(agentName);
  if (compareFilter.protocol !== 'any' && p.proto !== compareFilter.protocol) return false;
  if (compareFilter.playbook !== 'all' && p.playbook !== compareFilter.playbook) return false;
  if (compareFilter.thinking !== 'any' && p.thinking && p.thinking !== compareFilter.thinking) return false;
  return true;
}

function getMatchedAgents(exp) { return Object.keys(exp.agents).filter(agentMatchesScenario); }

function rateAt(rates, target) { return rates.find(r => Math.abs(r.rate - target) < 1e-6) || null; }

function applyPreset(name) {
  ['architecture','family','reasoning','region','runtime','roles'].forEach(k => compareFilter[k] = new Set());
  if (name === 'cross')  { comparePlotType='cross';  compareFilter.protocol='http'; compareFilter.playbook='all';  compareFilter.thinking='any'; }
  if (name === 'hump')   { comparePlotType='hump';   compareFilter.protocol='http'; compareFilter.playbook='all';  compareFilter.thinking='any'; compareFilter.fixedRate=0.10; }
  if (name === 'ht')     { comparePlotType='ht';     compareFilter.protocol='http'; compareFilter.playbook='pb';   compareFilter.thinking='any'; compareFilter.fixedRate=0.10; }
  if (name === 'roster') { comparePlotType='roster'; }
  renderCompare();
}

function setComparePlotType(t) { comparePlotType = t; renderCompare(); }
function toggleCompareFilter(key, value) { const s = compareFilter[key]; if (s.has(value)) s.delete(value); else s.add(value); renderCompare(); }
function setComparePart(key, value) { compareFilter[key] = value; renderCompare(); }

function renderCompare() {
  const root = document.getElementById('compare-app');
  if (!COMPARE) { root.textContent = 'No data'; return; }
  let html = '<div class="cmp-grid">';
  html += '<aside class="cmp-sidebar">' + renderFiltersSidebar() + '</aside>';
  html += '<main class="cmp-main">' + renderCompareMain() + '</main>';
  html += '</div>';
  root.innerHTML = html;
  drawCurrentPlot();
}

function renderFiltersSidebar() {
  const archs = new Set(), fams = new Set(), reasoning = new Set(),
        regions = new Set(), runtimes = new Set(), roles = new Set();
  COMPARE.experiments.forEach(e => {
    if (e.tags.architecture) archs.add(e.tags.architecture);
    if (e.tags.family) fams.add(e.tags.family);
    if (e.tags.reasoning != null) reasoning.add(String(e.tags.reasoning));
    if (e.tags.region) regions.add(e.tags.region);
    if (e.tags.runtime) runtimes.add(e.tags.runtime);
    (e.roles||[]).forEach(r => roles.add(r));
  });

  let h = '<div class="cmp-section"><h3>Presets</h3><div style="display:flex;flex-wrap:wrap;gap:4px">';
  h += '<button class="btn" onclick="applyPreset(\\'cross\\')" title="Cross-model SR vs failure rate">Cross-model</button>';
  h += '<button class="btn" onclick="applyPreset(\\'hump\\')" title="Hump-shape: gap pb-nopb vs capability">Hump-shape</button>';
  h += '<button class="btn" onclick="applyPreset(\\'ht\\')" title="Hare & Tortoise: latency vs SR">Hare &amp; Tortoise</button>';
  h += '<button class="btn" onclick="applyPreset(\\'roster\\')" title="Tag roster">Roster</button>';
  h += '</div></div>';

  function tagSection(label, key, vals) {
    let s = '<div class="cmp-section"><h3>' + label + '</h3><div class="cmp-tags">';
    Array.from(vals).sort().forEach(v => {
      const active = compareFilter[key].has(v);
      s += '<button class="cmp-tag ' + (active?'on':'') + '" onclick="toggleCompareFilter(\\'' + key + '\\',\\'' + v + '\\')">' + v + '</button>';
    });
    s += '</div></div>';
    return s;
  }
  h += tagSection('Architecture', 'architecture', archs);
  h += tagSection('Family', 'family', fams);
  h += tagSection('Reasoning', 'reasoning', reasoning);
  h += tagSection('Region', 'region', regions);
  h += tagSection('Runtime', 'runtime', runtimes);
  h += tagSection('Roles', 'roles', roles);

  if (compareFilter.totalParamsRange) {
    const r = compareFilter.totalParamsRange;
    h += '<div class="cmp-section"><h3>Total params (B)</h3><div class="cmp-range">'+
      '<input type="number" id="tprm-min" value="'+r[0]+'" step="0.1" onchange="syncSlider(\\'total\\')">'+
      '<input type="number" id="tprm-max" value="'+r[1]+'" step="0.1" onchange="syncSlider(\\'total\\')"></div></div>';
  }
  if (compareFilter.activeParamsRange) {
    const r = compareFilter.activeParamsRange;
    h += '<div class="cmp-section"><h3>Active params (B)</h3><div class="cmp-range">'+
      '<input type="number" id="aprm-min" value="'+r[0]+'" step="0.1" onchange="syncSlider(\\'active\\')">'+
      '<input type="number" id="aprm-max" value="'+r[1]+'" step="0.1" onchange="syncSlider(\\'active\\')"></div></div>';
  }
  return h;
}

function syncSlider(which) {
  if (which === 'total') {
    const a = parseFloat(document.getElementById('tprm-min').value);
    const b = parseFloat(document.getElementById('tprm-max').value);
    if (!isNaN(a) && !isNaN(b)) compareFilter.totalParamsRange = [Math.min(a,b), Math.max(a,b)];
  } else {
    const a = parseFloat(document.getElementById('aprm-min').value);
    const b = parseFloat(document.getElementById('aprm-max').value);
    if (!isNaN(a) && !isNaN(b)) compareFilter.activeParamsRange = [Math.min(a,b), Math.max(a,b)];
  }
  renderCompare();
}

function renderCompareMain() {
  let h = '<div class="cmp-toolbar">';
  const labels = {cross:'Cross-model SR', hump:'Hump-shape', ht:'Hare & Tortoise', roster:'Roster'};
  ['cross','hump','ht','roster'].forEach(t => {
    const cls = comparePlotType === t ? 'btn active' : 'btn';
    h += '<button class="' + cls + '" onclick="setComparePlotType(\\'' + t + '\\')">' + labels[t] + '</button>';
  });
  h += '</div>';

  h += '<div class="cmp-scenario">';
  h += '<span class="cmp-sl">Protocol</span>';
  ['http','mcp','a2a','any'].forEach(p => {
    const cls = compareFilter.protocol === p ? 'cmp-tag on' : 'cmp-tag';
    h += '<button class="' + cls + '" onclick="setComparePart(\\'protocol\\',\\'' + p + '\\')">' + p + '</button>';
  });
  h += '<span class="cmp-sl">Playbook</span>';
  ['pb','nopb','all'].forEach(p => {
    const cls = compareFilter.playbook === p ? 'cmp-tag on' : 'cmp-tag';
    h += '<button class="' + cls + '" onclick="setComparePart(\\'playbook\\',\\'' + p + '\\')">' + p + '</button>';
  });
  h += '<span class="cmp-sl">Thinking</span>';
  ['think','nothink','any'].forEach(t => {
    const cls = compareFilter.thinking === t ? 'cmp-tag on' : 'cmp-tag';
    h += '<button class="' + cls + '" onclick="setComparePart(\\'thinking\\',\\'' + t + '\\')">' + t + '</button>';
  });
  if (comparePlotType === 'hump' || comparePlotType === 'ht' || comparePlotType === 'roster') {
    h += '<span class="cmp-sl">Fixed rate</span>';
    [0.0,0.05,0.10,0.20,0.30].forEach(r => {
      const cls = Math.abs(compareFilter.fixedRate - r) < 1e-6 ? 'cmp-tag on' : 'cmp-tag';
      h += '<button class="' + cls + '" onclick="setComparePart(\\'fixedRate\\',' + r + ')">' + (r*100).toFixed(0) + '%</button>';
    });
  }
  h += '</div>';

  h += '<div class="cmp-plot-wrap">';
  if (comparePlotType !== 'roster') h += '<canvas id="cmp-canvas"></canvas>';
  else h += '<div id="cmp-roster" style="height:100%;overflow-y:auto"></div>';
  h += '</div>';

  h += '<div class="cmp-table-wrap"><h3>Selected experiments</h3><div id="cmp-table"></div></div>';
  h += '<div class="cmp-export">';
  h += '<button class="btn" onclick="exportComparePNG()">Export PNG</button>';
  h += '<button class="btn" onclick="exportCompareCSV()">Export CSV</button>';
  h += '</div>';
  return h;
}

function drawCurrentPlot() {
  if (compareChart) { compareChart.destroy(); compareChart = null; }
  if (comparePlotType === 'roster') {
    const r = document.getElementById('cmp-roster');
    if (r) r.innerHTML = renderRosterTable();
    document.getElementById('cmp-table').innerHTML = '';
    return;
  }
  const cvs = document.getElementById('cmp-canvas');
  if (!cvs) return;
  if (comparePlotType === 'cross') compareChart = drawCrossModel(cvs);
  if (comparePlotType === 'hump')  compareChart = drawHumpShape(cvs);
  if (comparePlotType === 'ht')    compareChart = drawHareTortoise(cvs);
  document.getElementById('cmp-table').innerHTML = renderCompareTable();
}

function drawCrossModel(cvs) {
  const exps = applyFiltersToExperiments();
  const datasets = [];
  exps.forEach(e => {
    const arch = e.tags.architecture || 'default';
    const baseColor = archColor(arch);
    getMatchedAgents(e).forEach(agentName => {
      const p = parseAgent(agentName);
      const pts = e.agents[agentName].rates.map(r => ({
        x: r.rate*100, y: r.sr*100,
        ci_low: r.ci_low*100, ci_high: r.ci_high*100, n: r.n,
      }));
      const lbl = e.name + (p.playbook?' '+p.playbook:'') + (p.thinking?' '+p.thinking:'');
      const dash = p.playbook === 'nopb' ? [4,4] : [];
      datasets.push({
        label: lbl, data: pts, borderColor: baseColor, backgroundColor: baseColor + '22',
        borderWidth: 1.6, borderDash: dash, fill:false, tension:0.2, pointRadius:2,
      });
    });
  });
  return new Chart(cvs, {
    type: 'line',
    data: { datasets },
    options: {
      responsive:true, maintainAspectRatio:false, parsing:false,
      plugins: {
        legend: { position:'right', labels:{ color:'#aaa', font:{size:9}, boxWidth:14 } },
        tooltip: { callbacks: { label: ctx => {
          const d = ctx.raw;
          return ctx.dataset.label + ': SR=' + d.y.toFixed(1) + '% [' + d.ci_low.toFixed(1) + ',' + d.ci_high.toFixed(1) + '] n=' + d.n;
        }}},
      },
      scales: {
        x: { type:'linear', title:{display:true,text:'Failure rate (%)',color:'#888'}, ticks:{color:'#888'}, grid:{color:'#1a1d27'}, min:0 },
        y: { title:{display:true,text:'Success rate (%)',color:'#888'}, ticks:{color:'#888'}, grid:{color:'#1a1d27'}, min:0, max:105 },
      }
    }
  });
}

function drawHumpShape(cvs) {
  const exps = applyFiltersToExperiments();
  const points = [];
  exps.forEach(e => {
    const groups = {};
    Object.keys(e.agents).forEach(a => {
      const p = parseAgent(a);
      if (compareFilter.protocol !== 'any' && p.proto !== compareFilter.protocol) return;
      if (compareFilter.thinking !== 'any' && p.thinking && p.thinking !== compareFilter.thinking) return;
      const key = p.proto + '|' + (p.thinking||'');
      if (!groups[key]) groups[key] = {};
      groups[key][p.playbook] = a;
    });
    Object.entries(groups).forEach(([gkey, grp]) => {
      if (!grp.nopb || !grp.pb) return;
      const baseline = rateAt(e.agents[grp.nopb].rates, 0.0);
      const tgN = rateAt(e.agents[grp.nopb].rates, compareFilter.fixedRate);
      const tgP = rateAt(e.agents[grp.pb].rates, compareFilter.fixedRate);
      if (!baseline || !tgN || !tgP) return;
      points.push({
        x: baseline.sr * 100, y: (tgP.sr - tgN.sr) * 100,
        n_pb: tgP.n, n_nopb: tgN.n, label: e.name + ' (' + gkey + ')',
        arch: e.tags.architecture || 'default',
      });
    });
  });
  const byArch = {};
  points.forEach(p => { (byArch[p.arch] = byArch[p.arch] || []).push(p); });
  const datasets = Object.entries(byArch).map(([arch, pts]) => ({
    label: arch, data: pts, backgroundColor: archColor(arch), borderColor: archColor(arch),
    pointRadius: 6, pointHoverRadius: 8,
  }));
  return new Chart(cvs, {
    type: 'scatter', data: { datasets },
    options: {
      responsive:true, maintainAspectRatio:false,
      plugins: {
        legend: { position:'right', labels:{ color:'#aaa', font:{size:10} } },
        tooltip: { callbacks: { label: ctx => {
          const d = ctx.raw;
          return d.label + ': capability=' + d.x.toFixed(1) + '%, gap=' + d.y.toFixed(1) + 'pp';
        }}},
      },
      scales: {
        x: { title:{display:true,text:'Capability — nopb SR @ rate=0 (%)',color:'#888'}, ticks:{color:'#888'}, grid:{color:'#1a1d27'}, min:0, max:105 },
        y: { title:{display:true,text:'Gap = SR(pb) − SR(nopb) @ rate=' + (compareFilter.fixedRate*100).toFixed(0) + '% (pp)', color:'#888'}, ticks:{color:'#888'}, grid:{color:'#1a1d27'} },
      }
    }
  });
}

function drawHareTortoise(cvs) {
  const exps = applyFiltersToExperiments();
  const byArch = {};
  exps.forEach(e => {
    getMatchedAgents(e).forEach(a => {
      const r = rateAt(e.agents[a].rates, compareFilter.fixedRate);
      if (!r) return;
      const arch = e.tags.architecture || 'default';
      const p = parseAgent(a);
      const point = {
        x: r.dur_ms_mean / 1000, y: r.sr * 100,
        label: e.name + ' ' + (p.playbook||'') + ' ' + (p.thinking||''), n: r.n,
      };
      (byArch[arch] = byArch[arch] || []).push(point);
    });
  });
  const datasets = Object.entries(byArch).map(([arch, pts]) => ({
    label: arch, data: pts, backgroundColor: archColor(arch), borderColor: archColor(arch),
    pointRadius: 5, pointHoverRadius: 7,
  }));
  return new Chart(cvs, {
    type: 'scatter', data: { datasets },
    options: {
      responsive:true, maintainAspectRatio:false,
      plugins: {
        legend: { position:'right', labels:{ color:'#aaa', font:{size:10} } },
        tooltip: { callbacks: { label: ctx => {
          const d = ctx.raw;
          return d.label + ': ' + d.x.toFixed(1) + 's, SR=' + d.y.toFixed(1) + '% n=' + d.n;
        }}},
      },
      scales: {
        x: { title:{display:true,text:'Mean duration (s)',color:'#888'}, ticks:{color:'#888'}, grid:{color:'#1a1d27'}, min:0 },
        y: { title:{display:true,text:'Success rate @ rate=' + (compareFilter.fixedRate*100).toFixed(0) + '% (%)', color:'#888'}, ticks:{color:'#888'}, grid:{color:'#1a1d27'}, min:0, max:105 },
      }
    }
  });
}

function renderCompareTable() {
  const exps = applyFiltersToExperiments();
  const rows = [];
  exps.forEach(e => {
    getMatchedAgents(e).forEach(a => {
      const r = rateAt(e.agents[a].rates, compareFilter.fixedRate);
      if (!r) return;
      const p = parseAgent(a);
      rows.push({
        exp: e.name, arch: e.tags.architecture, family: e.tags.family,
        total: e.tags.total_params, active: e.tags.active_params, reasoning: String(e.tags.reasoning),
        proto: p.proto, playbook: p.playbook, thinking: p.thinking || '-',
        sr: (r.sr*100).toFixed(1),
        ci: '[' + (r.ci_low*100).toFixed(1) + ',' + (r.ci_high*100).toFixed(1) + ']',
        n: r.n, dur: (r.dur_ms_mean/1000).toFixed(1),
      });
    });
  });
  if (!rows.length) return '<p style="color:#666">No data matches filters.</p>';
  let h = '<table><thead><tr><th>Experiment</th><th>Arch</th><th>Family</th><th>Total</th><th>Active</th><th>Reason</th><th>Proto</th><th>PB</th><th>Think</th><th>SR @ ' + (compareFilter.fixedRate*100).toFixed(0) + '%</th><th>CI95</th><th>n</th><th>Dur (s)</th></tr></thead><tbody>';
  rows.forEach(r => {
    h += '<tr><td>' + r.exp + '</td><td>' + (r.arch||'') + '</td><td>' + (r.family||'') + '</td><td>' + (r.total||'') + '</td><td>' + (r.active||'') + '</td><td>' + r.reasoning + '</td><td>' + r.proto + '</td><td>' + r.playbook + '</td><td>' + r.thinking + '</td><td class="sr ' + srClass(parseFloat(r.sr)) + '">' + r.sr + '%</td><td>' + r.ci + '</td><td>' + r.n + '</td><td>' + r.dur + '</td></tr>';
  });
  h += '</tbody></table>';
  return h;
}

function renderRosterTable() {
  const exps = applyFiltersToExperiments();
  let h = '<table><thead><tr><th>Experiment</th><th>Family</th><th>Arch</th><th>Total</th><th>Active</th><th>Reasoning</th><th>Provider</th><th>Region</th><th>Runtime</th><th>Roles</th><th>Protocols</th></tr></thead><tbody>';
  exps.forEach(e => {
    const t = e.tags;
    h += '<tr><td>' + e.name + '</td><td>' + (t.family||'') + '</td><td>' + (t.architecture||'') + '</td><td>' + (t.total_params||'') + '</td><td>' + (t.active_params||'') + '</td><td>' + (t.reasoning||'') + '</td><td>' + (t.provider||'') + '</td><td>' + (t.region||'') + '</td><td>' + (t.runtime||'') + '</td><td style="font-size:.78em">' + (e.roles||[]).join(', ') + '</td><td>' + (e.protocols||[]).join(',') + '</td></tr>';
  });
  h += '</tbody></table>';
  return h;
}

function exportComparePNG() {
  if (!compareChart) { alert('No chart to export — switch to a plot type first'); return; }
  const url = compareChart.toBase64Image('image/png', 1.0);
  const a = document.createElement('a');
  a.href = url; a.download = 'compare_' + comparePlotType + '_' + Date.now() + '.png';
  a.click();
}

function exportCompareCSV() {
  const exps = applyFiltersToExperiments();
  const rows = [['experiment','agent','architecture','family','total_params','active_params','reasoning','protocol','playbook','thinking','rate','n','ok','sr','ci_low','ci_high','dur_ms_mean']];
  exps.forEach(e => {
    getMatchedAgents(e).forEach(a => {
      const p = parseAgent(a);
      e.agents[a].rates.forEach(r => {
        rows.push([e.name, a, e.tags.architecture||'', e.tags.family||'', e.tags.total_params||'', e.tags.active_params||'',
                   e.tags.reasoning||'', p.proto, p.playbook||'', p.thinking||'',
                   r.rate, r.n, r.ok, r.sr, r.ci_low, r.ci_high, r.dur_ms_mean]);
      });
    });
  });
  const csv = rows.map(r => r.map(v => '"' + v + '"').join(',')).join('\\n');
  const blob = new Blob([csv], { type:'text/csv' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url; a.download = 'compare_' + comparePlotType + '_' + Date.now() + '.csv';
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

render();
</script>
</body>
</html>""")


class Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        # Wrap the entire response in a try/except so a client disconnect
        # (e.g. tab closed, refresh, browser timeout) doesn't kill the
        # server process via uncaught ConnectionAbortedError on Windows.
        try:
            return self._do_GET()
        except (ConnectionAbortedError, ConnectionResetError, BrokenPipeError):
            return  # client closed early; nothing to do

    def _do_GET(self) -> None:
        from urllib.parse import urlparse, parse_qs
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)

        global _SELECTED_EXPERIMENT
        if "experiment" in params:
            _SELECTED_EXPERIMENT = params["experiment"][0]

        if "json" in params:
            view = params.get("view", ["single"])[0]

            if view == "compare":
                payload = json.dumps(build_compare_payload(), default=str)
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(payload.encode())
                return

            experiments = discover_experiments()
            selected = _SELECTED_EXPERIMENT or (experiments[0] if experiments else "")
            mode = params.get("mode", ["live"])[0]

            if mode == "offline" and selected:
                data = load_snapshot(selected)
                if data is None:
                    data = save_snapshot(selected)
            elif mode == "snapshot" and selected:
                data = save_snapshot(selected)
            else:
                data = scan_experiment(selected) if selected else {}

            has_snapshot = _snapshot_path(selected).exists() if selected else False
            payload = json.dumps({
                "experiments": experiments,
                "selected": selected,
                "data": data,
                "has_snapshot": has_snapshot,
            }, default=str)
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(payload.encode())
        else:
            html = build_html()
            payload = html.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

    def log_message(self, fmt: str, *args: Any) -> None:
        pass


def main() -> None:
    global _SELECTED_EXPERIMENT, _REFRESH_INTERVAL_MS, _YAML_PREVIEW_LIMIT
    parser = argparse.ArgumentParser(description="Experiment dashboard")
    parser.add_argument("--experiment", type=str, default=None,
                        help="Experiment to show initially")
    parser.add_argument("--port", type=int, default=8060)
    parser.add_argument("--refresh-interval", type=int, default=15000,
                        help="Auto-refresh interval in ms (default 15000)")
    parser.add_argument("--yaml-preview-limit", type=int, default=2000,
                        help="Max characters for YAML preview (0=unlimited)")
    args = parser.parse_args()

    _SELECTED_EXPERIMENT = args.experiment
    _REFRESH_INTERVAL_MS = args.refresh_interval
    _YAML_PREVIEW_LIMIT = args.yaml_preview_limit or 999999
    port = args.port

    server = HTTPServer(("", port), Handler)
    url = f"http://localhost:{port}"
    if _SELECTED_EXPERIMENT:
        url += f"?experiment={_SELECTED_EXPERIMENT}"
    print(f"Dashboard: {url}")
    webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    server.server_close()


if __name__ == "__main__":
    main()
