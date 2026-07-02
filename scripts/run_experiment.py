"""Unified experiment runner — replaces run_g6/g7/g8/paper_* scripts.

Reads an experiment.yaml and runs all specified protocol × thinking mode
combinations with resume support.

Usage:
    # Run full experiment from YAML config
    python scripts/run_experiment.py --config experiments/G8_ministral14b/experiment.yaml

    # Single protocol override
    python scripts/run_experiment.py --config experiments/G8_ministral14b --protocol http

    # Override N and single rate for quick testing
    python scripts/run_experiment.py --config experiments/G8_ministral14b -n 10 --rate 0.05

    # Custom model tag (when YAML model.id doesn't produce a clean tag)
    python scripts/run_experiment.py --config experiments/G8_ministral14b --model-tag ministral-14b

    # Override sleep between rates
    python scripts/run_experiment.py --config experiments/GEMMA26B --sleep-between-rates 120
"""
from __future__ import annotations

import argparse
import asyncio
import csv as _csv
import logging
import sys
import time
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT / "src"))

from dotenv import load_dotenv
load_dotenv(_ROOT / ".env")

from chaos_engine.experiments.config import ExperimentConfig, PROTOCOL_AGENT_KINDS
from chaos_engine.simulation.parametric import AgentConfig, ParametricABTestRunner


def _build_agents(
    cfg: ExperimentConfig,
    protocol: str,
    thinking: bool | None,
    model_tag: str,
    agent_filter: str = "both",
) -> list[AgentConfig]:
    kinds = PROTOCOL_AGENT_KINDS[protocol]
    nopb_name, pb_name = cfg.build_agent_names(protocol, thinking, model_tag)

    pb_kind = kinds["pb"]
    # Defensive getattr — `playbook_variant` is a chaos-side field that may
    # not exist on this lab's `ExperimentConfig` (which is locked at SHA 3ca3851
    # per the self-containment thread; no source code edits in `src/chaos_engine/`).
    if getattr(cfg, "playbook_variant", None) == "v2":
        if protocol != "http":
            raise ValueError(
                f"playbook_variant=v2 only implemented for http, got protocol={protocol}"
            )
        pb_kind = "llm_playbook_v2"

    nopb_cfg = AgentConfig(
        name=nopb_name,
        playbook_path="",
        kind=kinds["nopb"],
        llm_provider=cfg.model.provider,
        llm_model=cfg.model.id,
        thinking=thinking,
        harness=cfg.harness,
    )
    pb_cfg = AgentConfig(
        name=pb_name,
        playbook_path="",
        kind=pb_kind,
        llm_provider=cfg.model.provider,
        llm_model=cfg.model.id,
        thinking=thinking,
        harness=cfg.harness,
    )

    if agent_filter == "nopb":
        return [nopb_cfg]
    if agent_filter == "pb":
        return [pb_cfg]
    return [nopb_cfg, pb_cfg]


def _setup_logging(log_path: Path, logger_name: str) -> logging.Logger:
    for handler in logging.root.handlers[:]:
        logging.root.removeHandler(handler)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(log_path),
        ],
    )
    return logging.getLogger(logger_name)


def _count_csv_rows(csv_path: Path) -> int:
    if not csv_path.exists():
        return 0
    with open(csv_path, "r", encoding="utf-8") as f:
        return sum(1 for _ in _csv.DictReader(f))


def run_block(
    cfg: ExperimentConfig,
    protocol: str,
    thinking: bool | None,
    rate_plan: list[tuple[float, int]],
    model_tag: str,
    agent_filter: str = "both",
) -> int:
    think_label = "default" if thinking is None else ("THINK" if thinking else "NOTHINK")
    out = cfg.output_dir(protocol, thinking, model_tag)
    agents = _build_agents(cfg, protocol, thinking, model_tag, agent_filter=agent_filter)
    total = sum(n for _, n in rate_plan) * len(agents)
    sleep_s = cfg.effective_sleep_between_rates

    log_dir = cfg.experiment_dir / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / f"{model_tag}_{protocol}_{think_label.lower()}.log"
    log = _setup_logging(log_path, f"{cfg.name}-{protocol}-{think_label}")

    plan_str = ", ".join(f"{r:.2f}@n={n}" for r, n in rate_plan)
    log.info("=" * 60)
    log.info("Experiment: %s — %s %s %s", cfg.name, model_tag, protocol.upper(), think_label)
    log.info("  Model:    %s (%s)", cfg.model.id, cfg.model.provider)
    log.info("  Thinking: %s", think_label)
    log.info("  Trace:    %s", "ON" if cfg.trace else "OFF")
    log.info("  Plan:     %s", plan_str)
    log.info("  Total:    %d experiments (x%d agents)", total, len(agents))
    log.info("  Output:   %s", out)
    log.info("=" * 60)

    start = time.time()
    done = 0

    for idx, (rate, n) in enumerate(rate_plan):
        expected = n * len(agents)
        csv_path = out / ParametricABTestRunner.rate_csv_name(rate)
        existing = _count_csv_rows(csv_path)

        if existing >= expected:
            log.info(
                "--- rate %.2f @ n=%d (%d/%d) SKIP (already %d/%d) ---",
                rate, n, idx + 1, len(rate_plan), existing, expected,
            )
            done += existing
            continue

        log.info("--- rate %.2f @ n=%d (%d/%d) ---", rate, n, idx + 1, len(rate_plan))
        runner = ParametricABTestRunner(
            failure_rates=[rate],
            experiments_per_rate=n,
            output_dir=out,
            agents=agents,
            seed=cfg.seed,
            simulate_delays=cfg.simulate_delays,
            trace=cfg.trace,
        )
        result = asyncio.run(runner.run_parametric_experiments())
        done += result["total_experiments"]

        if sleep_s > 0 and idx < len(rate_plan) - 1:
            log.info("Cooldown: sleeping %d s before next rate", sleep_s)
            time.sleep(sleep_s)

    elapsed = (time.time() - start) / 60
    log.info(
        "Done %s %s %s! %d experiments in %.1f min",
        model_tag, protocol.upper(), think_label, done, elapsed,
    )
    return done


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Unified experiment runner — reads experiment.yaml",
    )
    parser.add_argument(
        "--config", required=True,
        help="Path to experiment.yaml (or directory containing one)",
    )
    parser.add_argument(
        "--model-tag", default=None,
        help="Override model tag for output dirs/agent names",
    )
    parser.add_argument(
        "--protocol", choices=["http", "mcp", "a2a"], default=None,
        help="Run a single protocol (default: all from config)",
    )
    parser.add_argument(
        "-n", "--experiments-per-rate", type=int, default=None,
        help="Override experiments per rate per agent",
    )
    parser.add_argument(
        "--rate", type=float, default=None,
        help="Run a single failure rate",
    )
    parser.add_argument(
        "--failure-rates", type=str, default=None,
        help="Override rates (comma-separated, e.g. '0.0,0.05,0.10')",
    )
    parser.add_argument(
        "--thinking-mode", choices=["think", "nothink", "both", "none"],
        default=None,
        help="Override thinking mode (default: from config/model)",
    )
    parser.add_argument(
        "--sleep-between-rates", type=int, default=None,
        help="Override cooldown seconds between rates",
    )
    parser.add_argument(
        "--sleep-between-protocols", type=int, default=None,
        help="Override cooldown seconds between protocol blocks",
    )
    parser.add_argument(
        "--trace", action="store_true", default=None,
        help="Force trace on (overrides config)",
    )
    parser.add_argument(
        "--no-trace", action="store_true", default=False,
        help="Force trace off (overrides config)",
    )
    parser.add_argument(
        "--agent", choices=["nopb", "pb", "both"], default="both",
        help="Restrict to one agent (for parallel runs splitting pb/nopb)",
    )
    args = parser.parse_args()

    # ── Load config ──────────────────────────────────────────────────────────
    cfg = ExperimentConfig.load(args.config)

    # ── Apply CLI overrides ──────────────────────────────────────────────────
    model_tag = args.model_tag or cfg._model_tag()

    if args.experiments_per_rate is not None:
        cfg.experiments_per_rate = args.experiments_per_rate
    if args.sleep_between_rates is not None:
        cfg.sleep_between_rates_s = args.sleep_between_rates
    if args.sleep_between_protocols is not None:
        cfg.sleep_between_protocols_s = args.sleep_between_protocols
    if args.trace is True:
        cfg.trace = True
    if args.no_trace:
        cfg.trace = False

    # ── Build rate plan ──────────────────────────────────────────────────────
    n = cfg.experiments_per_rate
    if args.rate is not None:
        rate_plan = [(args.rate, n)]
    elif args.failure_rates:
        rates = [float(x.strip()) for x in args.failure_rates.split(",")]
        rate_plan = [(r, n) for r in rates]
    else:
        rate_plan = [(r, n) for r in cfg.failure_rates]

    # ── Determine combos ─────────────────────────────────────────────────────
    protocols = [args.protocol] if args.protocol else cfg.protocols
    if args.thinking_mode == "both":
        modes: list[bool | None] = [True, False]
    elif args.thinking_mode == "think":
        modes = [True]
    elif args.thinking_mode == "nothink":
        modes = [False]
    elif args.thinking_mode == "none":
        modes = [None]
    else:
        modes = cfg.thinking_modes()

    n_agents = 1 if args.agent in ("nopb", "pb") else 2
    per_block = sum(n for _, n in rate_plan) * n_agents
    total = per_block * len(modes) * len(protocols)
    plan_str = ", ".join(f"{r:.2f}@n={n}" for r, n in rate_plan)

    print(f"=== {cfg.name}: {model_tag} ===")
    print(f"    Model:     {cfg.model.id} ({cfg.model.provider})")
    print(f"    Protocols: {protocols}")
    print(f"    Modes:     {[_think_label(m) for m in modes]}")
    print(f"    Trace:     {'ON' if cfg.trace else 'OFF'}")
    print(f"    Plan:      {plan_str}")
    print(f"    Total:     {total} experiments")
    print(f"    Output:    {cfg.experiment_dir / model_tag}")
    print()

    # ── Run ──────────────────────────────────────────────────────────────────
    grand_total = 0
    sleep_proto = cfg.sleep_between_protocols_s
    proto_count = len(protocols) * len(modes)
    combo_idx = 0

    for proto in protocols:
        for thinking in modes:
            label = _think_label(thinking)
            print(f"\n--- Starting {proto.upper()} {label} ({per_block} experiments) ---")
            done = run_block(cfg, proto, thinking, rate_plan, model_tag, agent_filter=args.agent)
            grand_total += done
            combo_idx += 1

            if sleep_proto > 0 and combo_idx < proto_count:
                print(f"\n>>> Cooldown between blocks: sleeping {sleep_proto}s <<<\n")
                time.sleep(sleep_proto)

    print(f"\n=== {cfg.name} DONE: {grand_total} experiments ===")


def _think_label(thinking: bool | None) -> str:
    if thinking is None:
        return "DEFAULT"
    return "THINK" if thinking else "NOTHINK"


if __name__ == "__main__":
    main()
