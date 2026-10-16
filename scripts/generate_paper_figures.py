"""Generate paper figures + tables from the lab's experiment data.

Reads the canonical lab dataset (default ``../chaos-playbook-lab/experiments``)
and produces:

  Fig 2 — Hare & Tortoise (mean latency vs success rate at rate=0)
  Fig 3 — Hump-shape (gap pb-nopb vs active params)
  Fig 4 — Cross-model SR curves (SR vs failure rate, line per model)
  Fig 5 — Thinking trade-off (GLM 4.5 think vs nothink)
  Fig 6 — Cross-protocol (HTTP/MCP/A2A panels for 3 multi-protocol models)
  Fig 8 — Distillation pair (qwen3.5 9B vanilla vs community-distilled, HTTP)
  Table 1 — Active model roster
  Table 2 — Excluded / partial models

Output: ``paper/figures/<name>.{svg,png}`` and ``paper/tables/<name>.md``.

Usage:
  python scripts/generate_paper_figures.py
  python scripts/generate_paper_figures.py --figure 3
  python scripts/generate_paper_figures.py --root <path-to-experiments-dir>
"""
from __future__ import annotations

import argparse
import csv
import logging
import math
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

import matplotlib.pyplot as plt
import numpy as np
import yaml
from adjustText import adjust_text

logger = logging.getLogger(__name__)


# ── Configuration ─────────────────────────────────────────────────────────────

DEFAULT_LAB_ROOT = Path("experiments")  # local copy in this repo (was ../chaos-playbook-lab/experiments)
PAPER_DIR = Path("paper")

ARCH_COLORS = {
    "dense": "#22c55e",
    "moe": "#a78bfa",
    "matformer": "#fbbf24",
    "ple": "#fbbf24",  # Per-Layer Embeddings (Gemma 4 E2B/E4B), see METADATA_CORRECTIONS
    "hybrid_mamba2_transformer": "#ef4444",  # red — Nemotron family
    "default": "#94a3b8",
}

# Descriptive-metadata corrections applied at figure-generation time (paper v1.1, Oct 2026).
# The experiment.yaml files are kept exactly as used during the campaign; their `tags` block is
# not read by the experiment runner (src/chaos_engine/experiments/config.py) and only feeds the
# figures and tables. The official Gemma 4 Technical Report (arXiv:2607.02770) describes E2B/E4B
# as Per-Layer-Embedding models with 2.3B / 4.5B effective parameters of 5B / 8B total, not as
# MatFormer models. No run, CSV or metric is affected.
METADATA_CORRECTIONS = {
    "gemma4_e2b": {"architecture": "ple", "total_params": "5B", "active_params": "~2.3B"},
    "gemma4_e4b": {"architecture": "ple", "total_params": "8B", "active_params": "~4.5B"},
}

MODEL_PRETTY_ORDER = [
    "qwen35_0_8b", "qwen35_2b", "gemma4_e2b", "gemma4_e4b", "qwen35_4b",
    "nemotron_nano_4b", "qwen35_9b", "qwen35_9b_distilled", "ministral_14b",
    "gpt_oss_20b", "gemma4_26b", "glm45",
]

# Models excluded from main comparative figures (Figs 1–3). They still appear
# in Table 2 (excluded / partial) with their failure-mode annotation.
EXCLUDED_FROM_MAIN = {
    "gpt_oss_20b": (
        "Reproducible degenerate decoding loop ('?' tokens) at rate 0.20 (§3.6); rates 0.00–0.20 "
        "preserved as qualitative evidence of high-chaos breakdown but not "
        "comparable with the rest of the roster (different N + truncated rates)."
    ),
}

MAIN_ROSTER = [n for n in MODEL_PRETTY_ORDER if n not in EXCLUDED_FROM_MAIN]

# Compact model labels for crowded scatter plots (Fig 2, Fig 3).
SHORT_LABELS = {
    "qwen35_0_8b": "qwen 0.8b",
    "qwen35_2b": "qwen 2b",
    "qwen35_4b": "qwen 4b",
    "qwen35_9b": "qwen 9b",
    "qwen35_9b_distilled": "qwen 9b-dist",
    "gemma4_e2b": "gemma E2b",
    "gemma4_e4b": "gemma E4b",
    "gemma4_26b": "gemma 26b",
    "ministral_14b": "ministral 14b",
    "nemotron_nano_4b": "nemotron 4b",
    "glm45": "glm-4.5",
    "gpt_oss_20b": "gpt-oss 20b",
    "gpt_oss_120b": "gpt-oss 120b",
}


def short_label(name: str) -> str:
    return SHORT_LABELS.get(name, name.replace("_", " "))

# Failure rates — all 10 in the canonical paper plan.
RATES_ALL = [0.0, 0.01, 0.02, 0.03, 0.05, 0.10, 0.15, 0.20, 0.25, 0.30]


# ── Stats ─────────────────────────────────────────────────────────────────────

def wilson_ci(k: int, n: int, z: float = 1.959963984540054) -> tuple[float, float]:
    if n <= 0:
        return (0.0, 0.0)
    p = k / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return (max(0.0, centre - half), min(1.0, centre + half))


def params_to_b(s) -> float | None:
    if s is None:
        return None
    raw = str(s).strip().lstrip("~")
    m = re.match(r"^([0-9]*\.?[0-9]+)\s*([KMBT])?", raw, flags=re.IGNORECASE)
    if not m:
        return None
    val = float(m.group(1))
    unit = (m.group(2) or "B").upper()
    return val * {"K": 1e-6, "M": 1e-3, "B": 1.0, "T": 1e3}.get(unit, 1.0)


# ── Data loading ──────────────────────────────────────────────────────────────

@dataclass
class CellStats:
    """Aggregate stats for one (model, protocol, agent, rate) cell."""
    n: int = 0
    ok: int = 0
    dur_ms_sum: float = 0.0
    tokens_sum: int = 0
    retries_sum: int = 0
    llm_calls_sum: int = 0

    def add(self, row: dict) -> None:
        self.n += 1
        if row.get("outcome") == "success":
            self.ok += 1
        try: self.dur_ms_sum += float(row.get("duration_ms", 0) or 0)
        except (TypeError, ValueError): pass
        try: self.tokens_sum += int(float(row.get("prompt_tokens", 0) or 0))
        except (TypeError, ValueError): pass
        try: self.tokens_sum += int(float(row.get("completion_tokens", 0) or 0))
        except (TypeError, ValueError): pass
        try: self.retries_sum += int(float(row.get("retries", 0) or 0))
        except (TypeError, ValueError): pass
        try: self.llm_calls_sum += int(float(row.get("llm_calls", 0) or 0))
        except (TypeError, ValueError): pass

    @property
    def sr(self) -> float:
        return self.ok / self.n if self.n else 0.0

    @property
    def ci(self) -> tuple[float, float]:
        return wilson_ci(self.ok, self.n)

    @property
    def dur_ms_mean(self) -> float:
        return self.dur_ms_sum / self.n if self.n else 0.0

    @property
    def tokens_mean(self) -> float:
        return self.tokens_sum / self.n if self.n else 0.0


@dataclass
class ModelData:
    name: str                            # dir name (e.g. "qwen35_4b")
    tag: str                             # data subdir (e.g. "qwen35-4b")
    tags: dict = field(default_factory=dict)
    roles: list = field(default_factory=list)
    cells: dict = field(default_factory=dict)  # (protocol, thinking, agent, rate) -> CellStats

    @property
    def architecture(self) -> str:
        return str(self.tags.get("architecture", "default")).lower()

    @property
    def family(self) -> str:
        return str(self.tags.get("family", "")).lower()

    @property
    def total_params_b(self) -> float | None:
        return params_to_b(self.tags.get("total_params"))

    @property
    def active_params_b(self) -> float | None:
        return params_to_b(self.tags.get("active_params"))

    @property
    def reasoning(self) -> str:
        return str(self.tags.get("reasoning", "")).lower()


def parse_protocol_dir(name: str) -> tuple[str, str | None]:
    """'http_think' -> ('http', 'think'); 'mcp' -> ('mcp', None)."""
    if "_" in name:
        proto, thinking = name.split("_", 1)
        return proto, thinking if thinking in ("think", "nothink") else None
    return name, None


def parse_agent(agent_name: str) -> dict:
    """Parse agent_type into structured parts."""
    parts = agent_name.split("-")
    proto = parts[0] if parts else "?"
    playbook = "pb" if agent_name.endswith("-pb") and not agent_name.endswith("-nopb") else "nopb"
    thinking = None
    if "-think-" in agent_name or agent_name.endswith("-think"): thinking = "think"
    elif "-nothink-" in agent_name or agent_name.endswith("-nothink"): thinking = "nothink"
    return {"protocol": proto, "playbook": playbook, "thinking": thinking}


def load_models(root: Path) -> dict[str, ModelData]:
    """Discover and load all models under root."""
    models: dict[str, ModelData] = {}
    if not root.exists():
        raise FileNotFoundError(f"experiments root not found: {root}")

    for model_dir in sorted(root.iterdir()):
        if not model_dir.is_dir() or model_dir.name.startswith("_"):
            continue
        yaml_path = model_dir / "experiment.yaml"
        if not yaml_path.exists():
            continue

        with open(yaml_path, "r", encoding="utf-8") as f:
            cfg = yaml.safe_load(f) or {}
        tags = cfg.get("tags", {}) if isinstance(cfg.get("tags"), dict) else {}
        tags = {**tags, **METADATA_CORRECTIONS.get(model_dir.name, {})}
        roles = cfg.get("roles", []) if isinstance(cfg.get("roles"), list) else []

        # Find the data subdir (== model.tag)
        tag_dir = None
        for sub in model_dir.iterdir():
            if not sub.is_dir() or sub.name in ("logs", "playbooks", "reports") \
               or sub.name.startswith("_"):
                continue
            tag_dir = sub
            break
        if tag_dir is None:
            logger.info("no data subdir for model %s — skipping", model_dir.name)
            continue

        m = ModelData(name=model_dir.name, tag=tag_dir.name, tags=tags, roles=list(roles))

        # Walk protocol subdirs
        for proto_dir in sorted(tag_dir.iterdir()):
            if not proto_dir.is_dir():
                continue
            proto, thinking = parse_protocol_dir(proto_dir.name)
            for csv_path in sorted(proto_dir.glob("rate_*.csv")):
                try:
                    rate = round(float(csv_path.stem.replace("rate_", "")), 4)
                except ValueError:
                    continue
                with open(csv_path, "r", encoding="utf-8") as f:
                    for row in csv.DictReader(f):
                        agent = row.get("agent_type") or "unknown"
                        ap = parse_agent(agent)
                        key = (proto, thinking, ap["playbook"], rate)
                        cell = m.cells.setdefault(key, CellStats())
                        cell.add(row)
        models[m.name] = m

    return models


# ── Output helpers ────────────────────────────────────────────────────────────

def save_fig(fig: plt.Figure, name: str) -> None:
    figdir = PAPER_DIR / "figures"
    figdir.mkdir(parents=True, exist_ok=True)
    for ext in ("svg", "png"):
        path = figdir / f"{name}.{ext}"
        fig.savefig(path, dpi=200, bbox_inches="tight")
        logger.info("wrote %s", path)
    plt.close(fig)


def save_table(name: str, content: str) -> None:
    tabdir = PAPER_DIR / "tables"
    tabdir.mkdir(parents=True, exist_ok=True)
    path = tabdir / f"{name}.md"
    path.write_text(content, encoding="utf-8")
    logger.info("wrote %s", path)


# ── Plot helpers ──────────────────────────────────────────────────────────────

def setup_axes(ax: plt.Axes) -> None:
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.grid(True, alpha=0.25, linewidth=0.5)


def model_label(m: ModelData) -> str:
    p = m.tags.get("total_params") or "?"
    return f"{m.name} ({p})"


def model_color(m: ModelData, palette_idx: int = 0) -> str:
    return ARCH_COLORS.get(m.architecture, ARCH_COLORS["default"])


def get_curve(m: ModelData, protocol: str, thinking: str | None,
              playbook: str) -> tuple[list[float], list[float], list[float], list[float]]:
    """Return (rates, sr_pct, ci_low_pct, ci_high_pct) for a curve."""
    rates, sr, lo, hi = [], [], [], []
    for r in RATES_ALL:
        c = m.cells.get((protocol, thinking, playbook, r))
        if c is None or c.n == 0:
            continue
        l, h = c.ci
        rates.append(r * 100)
        sr.append(c.sr * 100)
        lo.append(l * 100)
        hi.append(h * 100)
    return rates, sr, lo, hi


# ── Figure 4: Cross-model SR curves (split small/large) ───────────────────────

def plot_fig4_cross_model(models: dict[str, ModelData], protocol: str = "http") -> None:
    """Four panels by capability bracket. Distinct color per model in each panel.
    Solid line = pb, dashed = nopb. Bracket boundaries chosen for paper clarity:
      Sub-2B   — capacity-floor / structural-rescue zone (3 models)
      4B       — iso-active-compute architecture comparison (3 models)
      9–26B    — middle and upper of the hump (4 models)
      Frontier — cloud-scale baseline (glm45 alone)
    """
    selected = set(n for n in MAIN_ROSTER if n in models
                   and any(k[0] == protocol for k in models[n].cells))

    BUCKETS = [
        ("Sub-2B  — capacity floor / structural rescue",
         ["qwen35_0_8b", "qwen35_2b", "gemma4_e2b"]),
        ("4B class — iso-active architecture",
         ["qwen35_4b", "gemma4_e4b", "nemotron_nano_4b"]),
        ("9–26B  — middle and upper roster",
         ["qwen35_9b", "qwen35_9b_distilled", "ministral_14b", "gemma4_26b"]),
        ("Frontier (cloud)",
         ["glm45"]),
    ]

    # Vendor-keyed palette so models from the same provider share a hue.
    # Differentiation between same-vendor models within a panel is by line
    # style (pb solid vs nopb dashed) and by marker — never two same-vendor
    # models on the same arm in the same panel of the BUCKETS layout.
    VENDOR_COLOR = {
        "qwen35_0_8b":         "#3b82f6",  # alibaba — blue
        "qwen35_2b":           "#3b82f6",
        "qwen35_4b":           "#3b82f6",
        "qwen35_9b":           "#3b82f6",
        "qwen35_9b_distilled": "#64748b",  # community distill — slate (visibly different)
        "gemma4_e2b":          "#f59e0b",  # google — amber
        "gemma4_e4b":          "#f59e0b",
        "gemma4_26b":          "#f59e0b",
        "nemotron_nano_4b":    "#10b981",  # nvidia — emerald
        "ministral_14b":       "#a855f7",  # mistral — violet
        "glm45":               "#ec4899",  # zhipu — pink
    }

    fig, axes = plt.subplots(2, 2, figsize=(14, 10), sharey=True,
                              gridspec_kw={"hspace": 0.32, "wspace": 0.08})
    axes_flat = axes.flatten()

    # Within a panel, distinguish same-vendor models by marker.
    PANEL_MARKERS = ["o", "s", "^", "D", "v", "P"]

    for ax, (title, names) in zip(axes_flat, BUCKETS):
        setup_axes(ax)
        present = [n for n in names if n in selected]
        for idx, name in enumerate(present):
            color = VENDOR_COLOR.get(name, "#374151")
            marker = PANEL_MARKERS[idx % len(PANEL_MARKERS)]
            m = models[name]
            thinkings = {k[1] for k in m.cells if k[0] == protocol}
            thinking = "think" if "think" in thinkings else \
                       (None if None in thinkings else "nothink")
            for pb in ("nopb", "pb"):
                r, sr, lo, hi = get_curve(m, protocol, thinking, pb)
                if not r: continue
                ls = "-" if pb == "pb" else (0, (3, 3))
                label = name if pb == "pb" else None
                ax.plot(r, sr, color=color, linewidth=1.8, marker=marker, markersize=4.0,
                        linestyle=ls, label=label, alpha=0.95)
                ax.fill_between(r, lo, hi, color=color, alpha=0.10)
        ax.set_xlabel("Failure rate (%)", fontsize=10)
        ax.set_title(title, fontsize=10.5, pad=6)
        ax.set_xlim(-1, 31)
        ax.set_ylim(0, 105)
        ax.legend(loc="lower left", fontsize=8, frameon=False,
                   title="(solid=pb, dashed=nopb)")

    axes[0, 0].set_ylabel("Success rate (%)", fontsize=11)
    axes[1, 0].set_ylabel("Success rate (%)", fontsize=11)
    fig.suptitle(f"Cross-model SR — {protocol.upper()} (4 capability brackets)",
                 fontsize=12, y=1.00)
    fig.tight_layout()
    save_fig(fig, "fig4_cross_model")


# ── Figure 3: Hump-shape (gap pb-nopb vs capability) ──────────────────────────

def plot_fig3_hump(models: dict[str, ModelData], protocol: str = "http",
                   fixed_rate: float = 0.10) -> None:
    """Two-panel figure: hump shape at the canonical operating rate
    (chaos = 10 %, left) and at the high-chaos rate (chaos = 30 %, right).

    The hump is more pronounced at higher chaos rates; showing both panels
    makes the rate-dependence visible and avoids cherry-picking a single rate.
    """
    rates = [fixed_rate, 0.30]
    fig, axes = plt.subplots(1, 2, figsize=(14, 6), sharey=True)

    for ax, rate in zip(axes, rates):
        setup_axes(ax)
        grouped: dict[str, list[tuple[ModelData, float, float, float, float]]] = {}
        for name in MAIN_ROSTER:
            m = models.get(name)
            if not m: continue
            thinkings = {k[1] for k in m.cells if k[0] == protocol}
            thinking = "think" if "think" in thinkings else (None if None in thinkings else "nothink")

            nopb = m.cells.get((protocol, thinking, "nopb", rate))
            pb = m.cells.get((protocol, thinking, "pb", rate))
            if not nopb or not pb or nopb.n == 0 or pb.n == 0:
                continue

            x = m.active_params_b
            if x is None:
                continue

            gap = (pb.sr - nopb.sr) * 100
            nopb_lo, nopb_hi = nopb.ci
            pb_lo, pb_hi = pb.ci
            sigma_nopb = (nopb_hi - nopb_lo) / (2 * 1.96)
            sigma_pb = (pb_hi - pb_lo) / (2 * 1.96)
            sigma_gap = math.sqrt(sigma_pb ** 2 + sigma_nopb ** 2)
            lo = gap - 1.96 * sigma_gap * 100
            hi = gap + 1.96 * sigma_gap * 100

            arch = m.architecture
            grouped.setdefault(arch, []).append((m, x, gap, lo, hi))

        all_texts = []
        all_x: list[float] = []
        all_y: list[float] = []
        for arch, rows in grouped.items():
            rows.sort(key=lambda r: r[1])
            xs = [r[1] for r in rows]
            ys = [r[2] for r in rows]
            los = [r[3] for r in rows]
            his = [r[4] for r in rows]
            c = ARCH_COLORS.get(arch, ARCH_COLORS["default"])
            ax.errorbar(xs, ys, yerr=[[y - l for y, l in zip(ys, los)],
                                      [h - y for y, h in zip(ys, his)]],
                        fmt="o", markersize=8, color=c, ecolor=c, elinewidth=1.2,
                        capsize=3, label=arch, alpha=0.9)
            for m, x, gap, _, _ in rows:
                all_texts.append(ax.text(x, gap, short_label(m.name),
                                          fontsize=8, color="#222", zorder=5))
                all_x.append(x)
                all_y.append(gap)

        adjust_text(
            all_texts, x=all_x, y=all_y, ax=ax,
            arrowprops=dict(arrowstyle="-", color="#888", lw=0.6, alpha=0.7),
            expand=(1.3, 1.6),
            force_text=(0.4, 0.6),
        )

        ax.axhline(0, color="#888", linewidth=0.7, linestyle=":")
        ax.set_xscale("log")
        ax.set_xlabel("Active params (B, log scale)", fontsize=11)
        ax.set_ylabel(f"Gap = SR(pb) − SR(nopb) (pp)", fontsize=11)
        ax.set_title(f"chaos = {rate*100:.0f}%", fontsize=12, pad=8)
        ax.legend(loc="lower right", fontsize=9, frameon=False)

    fig.suptitle("Playbook gain vs model capability (depends on the chaos rate)",
                 fontsize=13, y=1.02)
    fig.tight_layout()
    save_fig(fig, "fig3_hump")


# ── Figure 2: Hare & Tortoise (latency vs SR with arrows) ─────────────────────

def plot_fig2_hare_tortoise(models: dict[str, ModelData], protocol: str = "http",
                            rate: float = 0.20) -> None:
    """Numbered scatter with side legend. Each model gets a number 1..N inside
    its filled (pb) marker. Arrow connects nopb (hollow) → pb (filled). The
    number ↔ model mapping lives in a side legend on the right. This avoids
    label overlap when 5+ models converge to ~97% SR with playbook."""
    fig, ax = plt.subplots(figsize=(11, 7))
    setup_axes(ax)

    rows: list[tuple[ModelData, float, float, float, float]] = []
    for name in MAIN_ROSTER:
        m = models.get(name)
        if not m: continue
        thinkings = {k[1] for k in m.cells if k[0] == protocol}
        thinking = "think" if "think" in thinkings else \
                   (None if None in thinkings else "nothink")
        nopb = m.cells.get((protocol, thinking, "nopb", rate))
        pb = m.cells.get((protocol, thinking, "pb", rate))
        if not nopb or not pb or nopb.n == 0 or pb.n == 0:
            continue
        x_nopb, y_nopb = nopb.dur_ms_mean / 1000, nopb.sr * 100
        x_pb, y_pb = pb.dur_ms_mean / 1000, pb.sr * 100
        rows.append((m, x_pb, y_pb, x_nopb, y_nopb))

    # Sort by pb SR descending, then by duration ascending — gives reading order
    rows.sort(key=lambda r: (-r[2], r[1]))

    arch_seen: set[str] = set()
    for idx, (m, x_pb, y_pb, x_nopb, y_nopb) in enumerate(rows, start=1):
        col = ARCH_COLORS.get(m.architecture, ARCH_COLORS["default"])
        ax.annotate("", xy=(x_pb, y_pb), xytext=(x_nopb, y_nopb),
                    arrowprops=dict(arrowstyle="->", color=col, lw=1.2, alpha=0.55,
                                    shrinkA=8, shrinkB=8))
        ax.scatter(x_nopb, y_nopb, s=120, edgecolor=col, facecolor="white",
                   linewidth=1.6, zorder=3)
        lbl = m.architecture if m.architecture not in arch_seen else None
        ax.scatter(x_pb, y_pb, s=180, color=col, edgecolor=col,
                   linewidth=0.5, zorder=4, label=lbl)
        # Number inside the filled pb marker
        ax.text(x_pb, y_pb, str(idx), ha="center", va="center", fontsize=8,
                fontweight="bold", color="white", zorder=6)
        arch_seen.add(m.architecture)

    ax.set_xlabel("Mean run duration (s, log scale)", fontsize=11)
    ax.set_ylabel(f"Success rate at chaos {rate*100:.0f}% (%)", fontsize=11)
    ax.set_xscale("log")
    ax.set_title(f"Hare & Tortoise at chaos {rate*100:.0f}% — "
                 f"hollow=no playbook, filled=playbook, arrow=playbook lift",
                 fontsize=11, pad=10)
    ax.set_ylim(-5, 110)

    # Side legend: number → model (sorted by SR desc)
    legend_lines = [f"{idx}. {short_label(m.name)}" for idx, (m, *_) in enumerate(rows, 1)]
    legend_text = "\n".join(legend_lines)
    ax.text(1.02, 0.99, legend_text, transform=ax.transAxes,
            fontsize=8.5, verticalalignment="top",
            family="monospace", color="#222",
            bbox=dict(boxstyle="round,pad=0.5", facecolor="#f5f5f5",
                      edgecolor="#aaa", linewidth=0.5))
    ax.legend(loc="lower right", fontsize=9, frameon=False, title="Architecture")
    plt.subplots_adjust(right=0.78)
    save_fig(fig, "fig2_hare_tortoise")


# ── Figure 5: Thinking trade-off (GLM 4.5) ────────────────────────────────────

def plot_fig5_thinking(models: dict[str, ModelData]) -> None:
    """GLM 4.5 thinking vs no-thinking, one panel per protocol (HTTP, MCP, A2A).
    Shows whether the 'thinking is modest insurance at high chaos' claim holds
    across all three transports."""
    glm = models.get("glm45")
    if glm is None:
        logger.warning("glm45 not found; skipping fig5")
        return

    # Same color convention as Fig 6: color encodes arm (pb = pastel green,
    # nopb = pastel red), linestyle reinforces it (solid = pb, dashed = nopb).
    # The reasoning axis is encoded by marker shape: ○ think, △ nothink.
    color_pb = "#86efac"    # pastel green
    color_nopb = "#fca5a5"  # pastel red
    marker_think = "o"
    marker_nothink = "^"
    protocols = ("http", "mcp", "a2a")

    fig, axes = plt.subplots(1, 3, figsize=(16, 5.5), sharey=True,
                              gridspec_kw={"wspace": 0.10})

    for ax, proto in zip(axes, protocols):
        setup_axes(ax)
        any_data = False
        for thinking, marker in (("think", marker_think), ("nothink", marker_nothink)):
            for pb in ("nopb", "pb"):
                r, sr, lo, hi = get_curve(glm, proto, thinking, pb)
                if not r: continue
                any_data = True
                color = color_pb if pb == "pb" else color_nopb
                ls = "-" if pb == "pb" else (0, (3, 3))
                ax.plot(r, sr, color=color, linestyle=ls, marker=marker, markersize=5,
                        linewidth=1.7, label=f"{thinking} {pb}", alpha=0.95)
                ax.fill_between(r, lo, hi, color=color, alpha=0.10)
        ax.set_xlabel("Failure rate (%)", fontsize=11)
        ax.set_title(f"{proto.upper()}", fontsize=11, pad=8)
        ax.set_xlim(-1, 31)
        ax.set_ylim(0, 105)
        if not any_data:
            ax.text(0.5, 0.5, "no data", transform=ax.transAxes,
                    ha="center", color="#888")

    axes[0].set_ylabel("Success rate (%)", fontsize=11)
    # Single shared legend on the right
    handles, labels = axes[-1].get_legend_handles_labels()
    if handles:
        fig.legend(handles, labels, loc="center right", fontsize=10,
                   frameon=False, title="Mode × playbook")
        plt.subplots_adjust(right=0.88)

    fig.suptitle("GLM 4.5 — thinking vs no-thinking across protocols",
                 fontsize=12, y=1.02)
    save_fig(fig, "fig5_thinking")


# ── Figure 6: Cross-protocol panels ───────────────────────────────────────────

def plot_fig6_cross_protocol(models: dict[str, ModelData]) -> None:
    """Three panels (one per multi-protocol model). Single shared legend on the
    right. Legend column 1 = nopb, column 2 = pb (so the playbook effect reads
    visually left-to-right per row)."""
    multi = []
    for name in ("glm45", "ministral_14b", "gemma4_26b"):
        m = models.get(name)
        if not m: continue
        protos = {k[0] for k in m.cells}
        if {"http", "mcp", "a2a"}.issubset(protos):
            multi.append(m)
    if not multi:
        logger.warning("no multi-protocol models found; skipping fig6")
        return

    fig, axes = plt.subplots(1, len(multi), figsize=(5 * len(multi) + 2.5, 5),
                              sharey=True, squeeze=False)
    axes = axes[0]
    color_pb = "#86efac"   # pastel green
    color_nopb = "#fca5a5"  # pastel red

    proto_marker = {"http": "o", "mcp": "s", "a2a": "^"}

    for ax, m in zip(axes, multi):
        setup_axes(ax)
        for proto in ("http", "mcp", "a2a"):
            thinkings = {k[1] for k in m.cells if k[0] == proto}
            thinking = "think" if "think" in thinkings else \
                       (None if None in thinkings else "nothink")
            for pb in ("nopb", "pb"):
                r, sr, lo, hi = get_curve(m, proto, thinking, pb)
                if not r: continue
                col = color_pb if pb == "pb" else color_nopb
                ls = "-" if pb == "pb" else (0, (3, 3))
                ax.plot(r, sr, color=col, marker=proto_marker[proto], markersize=5,
                        linewidth=1.4, linestyle=ls, alpha=0.9)
                ax.fill_between(r, lo, hi, color=col, alpha=0.08)
        ax.set_xlabel("Failure rate (%)")
        ax.set_title(m.name, fontsize=11)
        ax.set_xlim(-1, 31)
        ax.set_ylim(0, 105)

    axes[0].set_ylabel("Success rate (%)", fontsize=11)

    # Build a single shared legend with the requested layout:
    #   Column 1 (nopb) | Column 2 (pb)
    #   HTTP nopb       | HTTP pb
    #   MCP nopb        | MCP pb
    #   A2A nopb        | A2A pb
    # matplotlib fills legends column-major, so we provide the items in the
    # order that the column-major fill produces the row layout above:
    #   col 1 = nopb of (http, mcp, a2a), col 2 = pb of (http, mcp, a2a)
    from matplotlib.lines import Line2D
    handles, labels = [], []
    for pb in ("nopb", "pb"):  # outer = column
        for proto in ("http", "mcp", "a2a"):  # inner = row within column
            col = color_pb if pb == "pb" else color_nopb
            ls = "-" if pb == "pb" else (0, (3, 3))
            handles.append(Line2D([], [], color=col, marker=proto_marker[proto],
                                   linestyle=ls, markersize=6, linewidth=1.6))
            labels.append(f"{proto.upper()} {pb}")
    fig.legend(handles, labels, loc="center right", fontsize=10, frameon=False,
               ncol=2, columnspacing=1.4, handletextpad=0.6,
               title="Protocol × playbook")
    plt.subplots_adjust(right=0.83)

    fig.suptitle("Cross-protocol — playbook generalizes to HTTP/MCP/A2A",
                 fontsize=12, y=1.02)
    save_fig(fig, "fig6_cross_protocol")


# ── Figure 7: Cost of the playbook (tokens, time, calls) ─────────────────────

def plot_fig7_cost(models: dict[str, ModelData], protocol: str = "http",
                   rate: float = 0.10) -> None:
    """Three panels showing the operational cost of the playbook per model:
      A — Tokens per run (prompt + completion, mean)
      B — Wall time per run (seconds, mean)
      C — LLM calls per run (turns, mean)
    Two bars per model (nopb vs pb) at fixed chaos rate. Models ordered as
    in MAIN_ROSTER (small → large)."""
    rows = []
    for name in MAIN_ROSTER:
        m = models.get(name)
        if not m: continue
        thinkings = {k[1] for k in m.cells if k[0] == protocol}
        thinking = "think" if "think" in thinkings else \
                   (None if None in thinkings else "nothink")
        nopb = m.cells.get((protocol, thinking, "nopb", rate))
        pb = m.cells.get((protocol, thinking, "pb", rate))
        if not nopb or not pb or nopb.n == 0 or pb.n == 0:
            continue
        rows.append({
            "name": name, "short": short_label(m.name),
            "tok_nopb": nopb.tokens_mean, "tok_pb": pb.tokens_mean,
            "dur_nopb": nopb.dur_ms_mean / 1000, "dur_pb": pb.dur_ms_mean / 1000,
            "calls_nopb": nopb.llm_calls_sum / nopb.n,
            "calls_pb": pb.llm_calls_sum / pb.n,
        })
    if not rows:
        logger.warning("plot_fig7_cost: no rows")
        return

    fig, axes = plt.subplots(1, 3, figsize=(17, 6))
    color_nopb = "#fca5a5"  # pastel red
    color_pb = "#86efac"    # pastel green
    labels = [r["short"] for r in rows]
    x = np.arange(len(rows))
    bw = 0.38

    panels = [
        (axes[0], "Tokens / run (prompt + completion)", "tok_nopb", "tok_pb", ""),
        (axes[1], f"Wall time / run (s) at chaos {rate*100:.0f}%", "dur_nopb", "dur_pb", ""),
        (axes[2], "LLM calls / run (turns)", "calls_nopb", "calls_pb", ""),
    ]
    for ax, title, k_nopb, k_pb, _ in panels:
        setup_axes(ax)
        nopb_vals = [r[k_nopb] for r in rows]
        pb_vals = [r[k_pb] for r in rows]
        ax.bar(x - bw/2, nopb_vals, bw, color=color_nopb, label="nopb",
               edgecolor="#b91c1c", linewidth=0.4)
        ax.bar(x + bw/2, pb_vals, bw, color=color_pb, label="pb",
               edgecolor="#166534", linewidth=0.4)
        ax.set_xticks(x)
        ax.set_xticklabels(labels, rotation=40, ha="right", fontsize=8)
        ax.set_title(title, fontsize=10.5, pad=8)
        ax.legend(loc="upper left", fontsize=9, frameon=False)

    fig.suptitle(
        f"Cost of the playbook — {protocol.upper()} at chaos {rate*100:.0f}% "
        f"(mean per run, nopb vs pb)",
        fontsize=12, y=1.00,
    )
    fig.tight_layout()
    save_fig(fig, "fig7_cost_of_playbook")


# ── Figure 8: Distillation pair (qwen3.5 9B vanilla vs community-distilled) ──

def plot_fig8_distillation(models: dict[str, ModelData], protocol: str = "http") -> None:
    """Side-by-side comparison of qwen3.5 9B vanilla vs community-distilled.

    Two panels: left = `nopb` arm, right = `pb` arm. Both panels show SR vs
    failure rate with Wilson 95 % bands. Goal: surface that the distilled
    variant is uniformly above the original on `nopb` (gap widens with
    chaos) and modestly above on `pb`, against the N = 5 pilot snapshot
    which suggested the opposite direction (see bitácora 2026-04-29 and
    the SUPERSEDED notice + 2026-05-11 entry).
    """
    vanilla = models.get("qwen35_9b")
    distilled = models.get("qwen35_9b_distilled")
    if vanilla is None or distilled is None:
        logger.warning("plot_fig8_distillation: missing qwen35_9b or qwen35_9b_distilled")
        return

    fig, axes = plt.subplots(1, 2, figsize=(14, 5.5), sharey=True,
                              gridspec_kw={"wspace": 0.08})

    COLOR_VANILLA = "#3b82f6"    # alibaba — blue
    COLOR_DISTILLED = "#64748b"  # community distill — slate

    for ax, arm, title in (
        (axes[0], "nopb", "Unguided arm (`nopb`)"),
        (axes[1], "pb", "Playbook arm (`pb`)"),
    ):
        setup_axes(ax)
        for m, color, label in (
            (vanilla, COLOR_VANILLA, "qwen3.5 9 B (vanilla)"),
            (distilled, COLOR_DISTILLED, "qwen3.5 9 B (distilled)"),
        ):
            r, sr, lo, hi = get_curve(m, protocol, None, arm)
            if not r:
                continue
            ax.plot(r, sr, color=color, linewidth=2.0, marker="o", markersize=4.5,
                    linestyle="-", label=label)
            ax.fill_between(r, lo, hi, color=color, alpha=0.13)
        ax.set_xlabel("Failure rate (%)", fontsize=10)
        ax.set_title(title, fontsize=10.5, pad=6)
        ax.set_xlim(-1, 31)
        ax.set_ylim(0, 105)
        ax.legend(loc="lower left", fontsize=9, frameon=False)

    axes[0].set_ylabel("Success rate (%)", fontsize=11)
    fig.suptitle(
        f"Distillation pair — qwen3.5 9 B vanilla vs community-distilled ({protocol.upper()}, N = 200/cell)",
        fontsize=12, y=1.00,
    )
    fig.tight_layout()
    save_fig(fig, "fig8_distillation")


# ── Figure 9: Heatmap of Δ across (model, chaos rate) ─────────────────────────

def plot_fig9_heatmap(models: dict[str, ModelData], protocol: str = "http") -> None:
    """Δ(pb − nopb) as a heatmap with one row per model and one column per rate.

    Visual summary of the full corpus: makes the rate-dependent pattern of the
    playbook gain visible at a glance, without forcing the reader through 11
    panels. Models ordered by active parameters; rates ordered low → high.
    """
    rates = [0.0, 0.01, 0.02, 0.03, 0.05, 0.10, 0.15, 0.20, 0.25, 0.30]

    # Pick a single canonical (protocol, thinking) cell per model
    rows_data = []
    for name in MAIN_ROSTER:
        m = models.get(name)
        if not m: continue
        thinkings = {k[1] for k in m.cells if k[0] == protocol}
        thinking = "think" if "think" in thinkings else (None if None in thinkings else "nothink")
        deltas = []
        for r in rates:
            nopb = m.cells.get((protocol, thinking, "nopb", r))
            pb = m.cells.get((protocol, thinking, "pb", r))
            if not nopb or not pb or nopb.n == 0 or pb.n == 0:
                deltas.append(float("nan"))
            else:
                deltas.append((pb.sr - nopb.sr) * 100)
        if m.active_params_b is None:
            continue
        rows_data.append((m.active_params_b, name, deltas))

    rows_data.sort(key=lambda r: r[0])
    labels = [f"{short_label(name)} ({ap:.1f}B act)" for ap, name, _ in rows_data]
    matrix = np.array([d for _, _, d in rows_data])

    fig, ax = plt.subplots(figsize=(11, 6.5))
    cmap = plt.get_cmap("RdYlGn")
    im = ax.imshow(matrix, aspect="auto", cmap=cmap, vmin=-10, vmax=100,
                   interpolation="nearest")

    ax.set_xticks(range(len(rates)))
    ax.set_xticklabels([f"{int(r*100)}%" for r in rates], fontsize=9)
    ax.set_yticks(range(len(labels)))
    ax.set_yticklabels(labels, fontsize=9)
    ax.set_xlabel("Chaos failure rate", fontsize=10)
    ax.set_ylabel("Model (sorted by active parameters)", fontsize=10)
    ax.set_title(f"Δ(pb − nopb) per (model, chaos rate) — {protocol.upper()}, full sweep",
                 fontsize=11.5, pad=8)

    # Annotate each cell with the numeric Δ
    for i in range(matrix.shape[0]):
        for j in range(matrix.shape[1]):
            v = matrix[i, j]
            if math.isnan(v): continue
            txt_color = "#111" if 0 <= v <= 65 else "#fff"
            ax.text(j, i, f"{v:+.0f}", ha="center", va="center",
                    fontsize=8, color=txt_color)

    cbar = fig.colorbar(im, ax=ax, shrink=0.85, pad=0.02)
    cbar.set_label("Δ (pp)", fontsize=10)
    fig.tight_layout()
    save_fig(fig, "fig9_heatmap")


# ── Tables ────────────────────────────────────────────────────────────────────

def table_roster(models: dict[str, ModelData]) -> str:
    # Roles and region columns dropped: roles are experiment-harness metadata
    # (cross_model, iso_4b_active, …) and region is implied by provider.
    rows = ["| Model | Architecture | Total | Active | Reasoning | Provider | Runtime |",
            "|---|---|---|---|---|---|---|"]
    for name in MAIN_ROSTER:
        m = models.get(name)
        if not m: continue
        t = m.tags
        rows.append(f"| {m.name} | {t.get('architecture','')} "
                    f"| {t.get('total_params','')} | {t.get('active_params','')} "
                    f"| {t.get('reasoning','')} | {t.get('provider','')} "
                    f"| {t.get('runtime','')} |")
    return "**Table 1 — Active model roster.**\n\n" + "\n".join(rows) + "\n"


def table_excluded(models: dict[str, ModelData]) -> str:
    """Models excluded from main comparative figures, with failure-mode notes."""
    rows = ["| Model | Total params | Active | Reason for exclusion |",
            "|---|---|---|---|"]
    for name, reason in EXCLUDED_FROM_MAIN.items():
        m = models.get(name)
        if not m: continue
        t = m.tags
        rows.append(f"| {name} | {t.get('total_params','')} | {t.get('active_params','')} "
                    f"| {reason} |")
    return ("**Table 3 — Excluded / partial models.**\n\n"
            "These models appear in the dataset but are excluded from the main "
            "comparative figures (Figs 1–3) because their coverage or failure "
            "mode is qualitatively different from the active roster. Listed "
            "here as appendix evidence.\n\n" + "\n".join(rows) + "\n")


def _bucket_total_params(b: float | None) -> str:
    if b is None: return "unknown"
    if b < 2:   return "sub-2B"
    if b < 5:   return "2–4B"
    if b < 30:  return "5–26B"
    return "frontier (≥30B)"


def table_runs_summary(models: dict[str, ModelData]) -> str:
    """Per-model + per-axis run counts. Verifiable totals from any direction.

    Includes excluded models (e.g. gpt_oss_20b) so totals match the on-disk
    dataset. The grand total at the top is the sum of all rows in all
    rate_*.csv files we ingested.
    """
    grand_total = sum(c.n for m in models.values() for c in m.cells.values())

    # ── Per-model rows ──
    per_model = ["| Model | Protocols | Agent groups | Rates seen | Total rows | Min n/cell | Max n/cell |",
                 "|---|---|---|---|---|---|---|"]
    for name in MODEL_PRETTY_ORDER:
        m = models.get(name)
        if not m: continue
        protos = sorted({k[0] for k in m.cells})
        agents = sorted({(k[1], k[2]) for k in m.cells})  # (thinking, playbook)
        rates = sorted({k[3] for k in m.cells})
        ns = [c.n for c in m.cells.values() if c.n > 0]
        total = sum(ns)
        flag = " *" if name in EXCLUDED_FROM_MAIN else ""
        per_model.append(f"| {m.name}{flag} | {', '.join(protos)} | {len(agents)} "
                         f"| {len(rates)} | {total} | {min(ns) if ns else 0} | {max(ns) if ns else 0} |")

    # ── Aggregations ──
    def axis_table(title: str, header_label: str, key_fn) -> list[str]:
        agg: dict[str, int] = {}
        for m in models.values():
            for k, c in m.cells.items():
                if c.n == 0: continue
                bucket = key_fn(m, k)
                if bucket is None: continue
                agg[bucket] = agg.get(bucket, 0) + c.n
        if not agg:
            return [f"\n## {title}\n", "_(no data)_\n"]
        rows = [f"\n## {title}\n",
                f"| {header_label} | Runs | % |", "|---|---:|---:|"]
        for k in sorted(agg, key=lambda x: -agg[x]):
            v = agg[k]
            pct = 100 * v / grand_total if grand_total else 0
            rows.append(f"| {k} | {v:,} | {pct:.1f}% |")
        rows.append(f"| **Total** | **{sum(agg.values()):,}** | 100.0% |")
        return rows

    out: list[str] = [
        "**Runs summary (rows in CSVs).**",
        "",
        f"**Grand total: {grand_total:,} runs** across {sum(1 for m in models.values() for c in m.cells.values() if c.n > 0)} non-empty cells.",
        "",
        "_Models marked with `*` are excluded from main comparative figures (Table 3)._",
        "",
        "## Per model",
        "",
        *per_model,
    ]

    out += axis_table(
        "By protocol",
        "Protocol",
        lambda m, k: k[0].upper(),
    )

    out += axis_table(
        "By reasoning mode (in protocol directory)",
        "Reasoning",
        lambda m, k: k[1] or "n/a",
    )

    out += axis_table(
        "By playbook arm",
        "Arm",
        lambda m, k: k[2],  # 'pb' or 'nopb'
    )

    out += axis_table(
        "By family",
        "Family",
        lambda m, k: m.family or "unknown",
    )

    out += axis_table(
        "By architecture",
        "Architecture",
        lambda m, k: m.architecture,
    )

    out += axis_table(
        "By total-params bucket",
        "Total params",
        lambda m, k: _bucket_total_params(m.total_params_b),
    )

    return "\n".join(out) + "\n"


# ── Main ──────────────────────────────────────────────────────────────────────

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--root", type=Path, default=DEFAULT_LAB_ROOT,
                        help=f"Experiments root (default {DEFAULT_LAB_ROOT})")
    parser.add_argument("--figure", type=str, default="all",
                        help="Which figure(s) to generate: 2,3,4,5,6 or 'all'")
    parser.add_argument("--rate", type=float, default=0.10,
                        help="Fixed rate for hump (Fig 3) — default 0.10")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(message)s")
    logger.info("Loading lab dataset from %s ...", args.root.resolve())
    models = load_models(args.root.resolve())
    logger.info("Loaded %d models: %s", len(models), ", ".join(sorted(models)))

    figures = args.figure.split(",") if args.figure != "all" else ["2", "3", "4", "5", "6", "7", "8", "9"]
    figures = [f.strip() for f in figures]

    if "4" in figures: plot_fig4_cross_model(models, "http")
    if "3" in figures: plot_fig3_hump(models, "http", fixed_rate=args.rate)
    if "2" in figures: plot_fig2_hare_tortoise(models, "http", rate=0.20)
    if "5" in figures: plot_fig5_thinking(models)
    if "6" in figures: plot_fig6_cross_protocol(models)
    if "7" in figures: plot_fig7_cost(models, "http", rate=0.10)
    if "8" in figures: plot_fig8_distillation(models, "http")
    if "9" in figures: plot_fig9_heatmap(models, "http")

    save_table("table1_roster", table_roster(models))
    save_table("table2_excluded", table_excluded(models))
    save_table("table_runs_summary", table_runs_summary(models))

    logger.info("Done — output in %s", PAPER_DIR.resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
