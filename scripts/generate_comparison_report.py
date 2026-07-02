"""Generate a comprehensive PDF comparison report with charts.

Covers all 18 unique comparisons from the experiment analysis matrix:
  - Cross-protocol (nopb and harm pb, think and nothink)
  - Think vs nothink per protocol (nopb and harm pb)
  - pb vs nopb per protocol x think mode
  - harm vs cons (HTTP only)

Uses matplotlib for charts embedded in fpdf2 PDF.

Usage:
    python scripts/generate_comparison_report.py
    python scripts/generate_comparison_report.py --output reports/paper/comparison-report.pdf
"""
from __future__ import annotations

import argparse
import csv
import io
import tempfile
from datetime import datetime
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from fpdf import FPDF

_ROOT = Path(__file__).resolve().parent.parent
REPORTS_DIR = _ROOT / "reports" / "parametric_experiments"
RATES = [0.0, 0.01, 0.02, 0.03, 0.05, 0.10, 0.15, 0.20, 0.25, 0.30]
RATE_LABELS = ["0%", "1%", "2%", "3%", "5%", "10%", "15%", "20%", "25%", "30%"]


# ── Data loading ─────────────────────────────────────────────────────────────

def load_dir(dirname: str) -> dict:
    dp = REPORTS_DIR / dirname
    data = {}
    for r in RATES:
        rkey = f"{r:.4g}"
        data[rkey] = {
            "nopb_n": 0, "nopb_ok": 0, "pb_n": 0, "pb_ok": 0,
            "nopb_dur": 0.0, "pb_dur": 0.0,
            "nopb_retries": 0, "pb_retries": 0,
            "nopb_llm": 0, "pb_llm": 0,
            "nopb_ptok": 0, "pb_ptok": 0, "nopb_ctok": 0, "pb_ctok": 0,
            "nopb_inc": 0, "pb_inc": 0,
        }
    for csv_file in sorted(dp.glob("rate_*.csv")):
        with open(csv_file, encoding="utf-8") as f:
            for row in csv.DictReader(f):
                fr = row.get("failure_rate", "")
                try:
                    rkey = f"{float(fr):.4g}"
                except (ValueError, TypeError):
                    continue
                if rkey not in data:
                    continue
                is_nopb = "nopb" in row.get("agent_type", "")
                pfx = "nopb" if is_nopb else "pb"
                data[rkey][f"{pfx}_n"] += 1
                if row.get("outcome") == "success":
                    data[rkey][f"{pfx}_ok"] += 1
                data[rkey][f"{pfx}_dur"] += float(row.get("duration_ms", 0))
                data[rkey][f"{pfx}_retries"] += int(float(row.get("retries", 0)))
                data[rkey][f"{pfx}_llm"] += int(float(row.get("llm_calls", 0)))
                data[rkey][f"{pfx}_ptok"] += int(float(row.get("prompt_tokens", 0)))
                data[rkey][f"{pfx}_ctok"] += int(float(row.get("completion_tokens", 0)))
                data[rkey][f"{pfx}_inc"] += int(float(row.get("inconsistencies_count", 0)))
    return data


def sr(ok: int, n: int) -> float | None:
    return 100 * ok / n if n else None


def sr_series(data: dict, variant: str) -> list[float | None]:
    """Extract SR series for a variant ('nopb' or 'pb')."""
    result = []
    for r in RATES:
        rkey = f"{r:.4g}"
        d = data[rkey]
        result.append(sr(d[f"{variant}_ok"], d[f"{variant}_n"]))
    return result


def agg_sr(data: dict, variant: str) -> float | None:
    total_n = sum(data[f"{r:.4g}"][f"{variant}_n"] for r in RATES)
    total_ok = sum(data[f"{r:.4g}"][f"{variant}_ok"] for r in RATES)
    return sr(total_ok, total_n)


# ── Chart generation ─────────────────────────────────────────────────────────

COLORS = {
    "HTTP": "#3b82f6",
    "MCP": "#f97316",
    "A2A": "#22c55e",
    "nopb": "#ef4444",
    "harm": "#22c55e",
    "cons": "#f97316",
    "think": "#6366f1",
    "nothink": "#ec4899",
    "pb": "#22c55e",
}

DASH_STYLES = {
    "solid": "-",
    "dashed": "--",
    "dotted": ":",
}


def _make_chart(
    title: str,
    series: list[tuple[str, list[float | None], str, str]],
    ylabel: str = "SR (%)",
    ylim: tuple[float, float] = (0, 105),
    figsize: tuple[float, float] = (7, 3.2),
) -> bytes:
    """Create a line chart and return PNG bytes.

    series: list of (label, values, color, linestyle)
    """
    fig, ax = plt.subplots(figsize=figsize)
    for label, values, color, ls in series:
        valid_x = [i for i, v in enumerate(values) if v is not None]
        valid_y = [values[i] for i in valid_x]
        valid_labels = [RATE_LABELS[i] for i in valid_x]
        ax.plot(valid_x, valid_y, label=label, color=color, linestyle=ls,
                linewidth=2, marker="o", markersize=4)
    ax.set_xticks(range(len(RATE_LABELS)))
    ax.set_xticklabels(RATE_LABELS, fontsize=8)
    ax.set_xlabel("Failure Rate", fontsize=9)
    ax.set_ylabel(ylabel, fontsize=9)
    ax.set_ylim(*ylim)
    ax.set_title(title, fontsize=10, fontweight="bold")
    ax.legend(fontsize=8, loc="lower left")
    ax.grid(True, alpha=0.3)
    fig.tight_layout()

    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=150)
    plt.close(fig)
    buf.seek(0)
    return buf.read()


# ── PDF generation ───────────────────────────────────────────────────────────

def build_report(output_path: Path) -> None:
    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    # Load all experiment data
    experiments = {
        "HTTP harm T": load_dir("run_paper_http_glm45"),
        "HTTP harm N": load_dir("run_paper_http_glm45_nothink"),
        "HTTP cons T": load_dir("run_paper_http_glm45_v2"),
        "HTTP cons N": load_dir("run_paper_http_glm45_nothink_v2"),
        "MCP T": load_dir("run_paper_mcp_glm45"),
        "MCP N": load_dir("run_paper_mcp_glm45_nothink"),
        "A2A T": load_dir("run_paper_a2a_glm45"),
        "A2A N": load_dir("run_paper_a2a_glm45_nothink"),
    }

    # Colors
    CLR_TITLE = (30, 58, 138)
    CLR_HEADER = (51, 65, 85)
    CLR_HEADER_BG = (226, 232, 240)
    CLR_GRAY = (100, 116, 139)
    CLR_BLACK = (0, 0, 0)
    CLR_WHITE = (255, 255, 255)
    CLR_ROW_ALT = (248, 250, 252)

    pdf = FPDF(orientation="P", unit="mm", format="A4")
    pdf.set_auto_page_break(auto=True, margin=18)

    def _safe(s: str) -> str:
        return s.replace("\u2014", "-").replace("\u2013", "-").replace("\u2192", "->")

    def add_chart(png_bytes: bytes):
        """Add a chart image to the PDF."""
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            tmp.write(png_bytes)
            tmp_path = tmp.name
        # Calculate width to fill page (190mm usable)
        pdf.image(tmp_path, x=10, w=190)
        pdf.ln(4)
        Path(tmp_path).unlink(missing_ok=True)

    def draw_table(title: str, headers: list[str], widths: list[float],
                   rows: list[list[str]], colors: list[tuple | None] | None = None):
        usable_w = 190
        raw_total = sum(widths)
        scale = usable_w / raw_total
        widths = [w * scale for w in widths]

        needed = 8 + 6 + len(rows) * 5.5 + 4
        if pdf.get_y() + needed > 275:
            pdf.add_page()

        pdf.set_font("Helvetica", "B", 10)
        pdf.set_text_color(*CLR_TITLE)
        pdf.cell(0, 8, _safe(title), new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", "B", 7)
        pdf.set_fill_color(*CLR_HEADER_BG)
        pdf.set_text_color(*CLR_HEADER)
        for j, (h, w) in enumerate(zip(headers, widths)):
            last = j == len(headers) - 1
            pdf.cell(w, 5.5, _safe(h), border="B", fill=True, align="C",
                     new_x="LMARGIN" if last else "RIGHT",
                     new_y="NEXT" if last else "TOP")
        pdf.set_font("Helvetica", "", 7)
        for i, row in enumerate(rows):
            if i % 2 == 1:
                pdf.set_fill_color(*CLR_ROW_ALT)
            else:
                pdf.set_fill_color(*CLR_WHITE)
            for j, (cell, w) in enumerate(zip(row, widths)):
                clr = (colors[j] if colors and j < len(colors) else None) or CLR_BLACK
                pdf.set_text_color(*clr)
                last = j == len(row) - 1
                align = "L" if j == 0 else "C"
                pdf.cell(w, 5.5, _safe(cell), fill=True, align=align,
                         new_x="LMARGIN" if last else "RIGHT",
                         new_y="NEXT" if last else "TOP")
        pdf.ln(3)

    def fmt_sr(ok, n):
        return f"{100*ok/n:.1f}%" if n else "-"

    def fmt_delta(a_ok, a_n, b_ok, b_n):
        if a_n and b_n:
            d = 100*b_ok/b_n - 100*a_ok/a_n
            return f"+{d:.1f}pp" if d >= 0 else f"{d:.1f}pp"
        return "-"

    # ════════════════════════════════════════════════════════════════════════
    # PAGE 1: Title + Overview
    # ════════════════════════════════════════════════════════════════════════
    pdf.add_page()

    pdf.set_font("Helvetica", "B", 18)
    pdf.set_text_color(*CLR_TITLE)
    pdf.cell(0, 12, "Chaos Playbook Engine", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "B", 14)
    pdf.cell(0, 8, "Full Comparison Report - 18 Scenarios", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(*CLR_GRAY)
    pdf.cell(0, 5, f"Generated {now}  |  GLM 4.5  |  3 protocols  |  10 failure rates  |  500/rate  |  80,000 experiments",
             new_x="LMARGIN", new_y="NEXT")
    pdf.ln(6)

    # Aggregate table
    agg_rows = []
    for label, key in [
        ("HTTP think (harm)", "HTTP harm T"), ("HTTP nothink (harm)", "HTTP harm N"),
        ("HTTP think (cons)", "HTTP cons T"), ("HTTP nothink (cons)", "HTTP cons N"),
        ("MCP think", "MCP T"), ("MCP nothink", "MCP N"),
        ("A2A think", "A2A T"), ("A2A nothink", "A2A N"),
    ]:
        d = experiments[key]
        n_sr = agg_sr(d, "nopb")
        p_sr = agg_sr(d, "pb")
        delta = p_sr - n_sr if n_sr is not None and p_sr is not None else 0
        sign = "+" if delta >= 0 else ""
        agg_rows.append([label,
                         f"{n_sr:.1f}%" if n_sr else "-",
                         f"{p_sr:.1f}%" if p_sr else "-",
                         f"{sign}{delta:.1f}pp"])
    draw_table("Aggregate SR - All 8 Experiments",
               ["Experiment", "nopb SR", "pb SR", "Delta"],
               [50, 25, 25, 25],
               agg_rows,
               [None, (220, 38, 38), (22, 163, 74), (37, 99, 235)])

    # ════════════════════════════════════════════════════════════════════════
    # COMPARISONS 1-2: Cross-protocol, nopb
    # ════════════════════════════════════════════════════════════════════════
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 12)
    pdf.set_text_color(*CLR_TITLE)
    pdf.cell(0, 8, "A. Cross-Protocol Comparison (no playbook)", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(2)

    # Chart: 3 protocols nopb, think + nothink
    chart = _make_chart(
        "#1-2: Protocol comparison - nopb (think solid, nothink dashed)",
        [
            ("HTTP think", sr_series(experiments["HTTP harm T"], "nopb"), COLORS["HTTP"], "-"),
            ("HTTP nothink", sr_series(experiments["HTTP harm N"], "nopb"), COLORS["HTTP"], "--"),
            ("MCP think", sr_series(experiments["MCP T"], "nopb"), COLORS["MCP"], "-"),
            ("MCP nothink", sr_series(experiments["MCP N"], "nopb"), COLORS["MCP"], "--"),
            ("A2A think", sr_series(experiments["A2A T"], "nopb"), COLORS["A2A"], "-"),
            ("A2A nothink", sr_series(experiments["A2A N"], "nopb"), COLORS["A2A"], "--"),
        ],
        ylim=(30, 105),
    )
    add_chart(chart)

    # Table
    rows = []
    for r in RATES:
        rkey = f"{r:.4g}"
        vals = [f"{round(r*100)}%"]
        for key in ["HTTP harm T", "MCP T", "A2A T", "HTTP harm N", "MCP N", "A2A N"]:
            d = experiments[key][rkey]
            vals.append(fmt_sr(d["nopb_ok"], d["nopb_n"]))
        rows.append(vals)
    draw_table("#1-2: nopb SR by rate",
               ["Rate", "HTTP(T)", "MCP(T)", "A2A(T)", "HTTP(N)", "MCP(N)", "A2A(N)"],
               [14, 18, 18, 18, 18, 18, 18],
               rows,
               [None, (59,130,246), (249,115,22), (34,197,94), (59,130,246), (249,115,22), (34,197,94)])

    # ════════════════════════════════════════════════════════════════════════
    # COMPARISONS 3-5: Think vs nothink per protocol, nopb
    # ════════════════════════════════════════════════════════════════════════
    chart = _make_chart(
        "#3-5: Think vs Nothink per protocol (nopb)",
        [
            ("HTTP think", sr_series(experiments["HTTP harm T"], "nopb"), COLORS["HTTP"], "-"),
            ("HTTP nothink", sr_series(experiments["HTTP harm N"], "nopb"), COLORS["HTTP"], "--"),
            ("MCP think", sr_series(experiments["MCP T"], "nopb"), COLORS["MCP"], "-"),
            ("MCP nothink", sr_series(experiments["MCP N"], "nopb"), COLORS["MCP"], "--"),
            ("A2A think", sr_series(experiments["A2A T"], "nopb"), COLORS["A2A"], "-"),
            ("A2A nothink", sr_series(experiments["A2A N"], "nopb"), COLORS["A2A"], "--"),
        ],
        ylim=(30, 105),
    )
    # Same chart as above — skip duplicate, reference it
    pdf.set_font("Helvetica", "I", 8)
    pdf.set_text_color(*CLR_GRAY)
    pdf.cell(0, 5, "#3-5: Think vs Nothink (nopb) - see chart above. Think penalizes MCP (-10pp) and A2A (-7pp), neutral for HTTP.",
             new_x="LMARGIN", new_y="NEXT")
    pdf.ln(2)

    # ════════════════════════════════════════════════════════════════════════
    # COMPARISONS 6-7: Cross-protocol, harm pb
    # ════════════════════════════════════════════════════════════════════════
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 12)
    pdf.set_text_color(*CLR_TITLE)
    pdf.cell(0, 8, "B. Cross-Protocol Comparison (harmonized playbook)", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(2)

    chart = _make_chart(
        "#6-7: Protocol comparison - harm pb (think solid, nothink dashed)",
        [
            ("HTTP think", sr_series(experiments["HTTP harm T"], "pb"), COLORS["HTTP"], "-"),
            ("HTTP nothink", sr_series(experiments["HTTP harm N"], "pb"), COLORS["HTTP"], "--"),
            ("MCP think", sr_series(experiments["MCP T"], "pb"), COLORS["MCP"], "-"),
            ("MCP nothink", sr_series(experiments["MCP N"], "pb"), COLORS["MCP"], "--"),
            ("A2A think", sr_series(experiments["A2A T"], "pb"), COLORS["A2A"], "-"),
            ("A2A nothink", sr_series(experiments["A2A N"], "pb"), COLORS["A2A"], "--"),
        ],
        ylim=(82, 101),
    )
    add_chart(chart)

    rows = []
    for r in RATES:
        rkey = f"{r:.4g}"
        vals = [f"{round(r*100)}%"]
        for key in ["HTTP harm T", "MCP T", "A2A T", "HTTP harm N", "MCP N", "A2A N"]:
            d = experiments[key][rkey]
            vals.append(fmt_sr(d["pb_ok"], d["pb_n"]))
        rows.append(vals)
    draw_table("#6-7: harm pb SR by rate",
               ["Rate", "HTTP(T)", "MCP(T)", "A2A(T)", "HTTP(N)", "MCP(N)", "A2A(N)"],
               [14, 18, 18, 18, 18, 18, 18],
               rows,
               [None, (59,130,246), (249,115,22), (34,197,94), (59,130,246), (249,115,22), (34,197,94)])

    # COMPARISONS 8-10: Think vs nothink per protocol, harm pb
    pdf.set_font("Helvetica", "I", 8)
    pdf.set_text_color(*CLR_GRAY)
    pdf.cell(0, 5, "#8-10: Think vs Nothink (harm pb) - see chart above. Think hurts MCP (-5.2pp), neutral for HTTP/A2A.",
             new_x="LMARGIN", new_y="NEXT")
    pdf.ln(2)

    # ════════════════════════════════════════════════════════════════════════
    # COMPARISONS 11-16: pb vs nopb (6 combos)
    # ════════════════════════════════════════════════════════════════════════
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 12)
    pdf.set_text_color(*CLR_TITLE)
    pdf.cell(0, 8, "C. Playbook vs No Playbook (per protocol x thinking mode)", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(2)

    # Chart: 6 subplots (3 protocols x 2 think modes) showing nopb vs pb
    fig, axes = plt.subplots(2, 3, figsize=(10, 5.5), sharey=True)
    combos = [
        ("HTTP think", "HTTP harm T", 0, 0),
        ("MCP think", "MCP T", 0, 1),
        ("A2A think", "A2A T", 0, 2),
        ("HTTP nothink", "HTTP harm N", 1, 0),
        ("MCP nothink", "MCP N", 1, 1),
        ("A2A nothink", "A2A N", 1, 2),
    ]
    for label, key, row_i, col_i in combos:
        ax = axes[row_i][col_i]
        nopb_vals = sr_series(experiments[key], "nopb")
        pb_vals = sr_series(experiments[key], "pb")
        x = range(len(RATES))
        ax.plot(x, nopb_vals, label="nopb", color="#ef4444", linewidth=1.5, marker="o", markersize=3)
        ax.plot(x, pb_vals, label="pb", color="#22c55e", linewidth=1.5, marker="s", markersize=3)
        # Delta fill
        nv = [v or 0 for v in nopb_vals]
        pv = [v or 0 for v in pb_vals]
        ax.fill_between(x, nv, pv, alpha=0.15, color="#22c55e")
        ax.set_title(f"#{11 + row_i*3 + col_i}: {label}", fontsize=9, fontweight="bold")
        ax.set_xticks(x)
        ax.set_xticklabels(RATE_LABELS, fontsize=6, rotation=45)
        ax.set_ylim(30, 105)
        ax.grid(True, alpha=0.3)
        if col_i == 0:
            ax.set_ylabel("SR (%)", fontsize=8)
        if row_i == 0 and col_i == 0:
            ax.legend(fontsize=7, loc="lower left")
    fig.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=150)
    plt.close(fig)
    buf.seek(0)
    add_chart(buf.read())

    # Delta table
    rows = []
    for r in RATES:
        rkey = f"{r:.4g}"
        vals = [f"{round(r*100)}%"]
        for key in ["HTTP harm T", "HTTP harm N", "MCP T", "MCP N", "A2A T", "A2A N"]:
            d = experiments[key][rkey]
            vals.append(fmt_delta(d["nopb_ok"], d["nopb_n"], d["pb_ok"], d["pb_n"]))
        rows.append(vals)
    draw_table("#11-16: Playbook delta (pb - nopb) in pp",
               ["Rate", "HTTP(T)", "HTTP(N)", "MCP(T)", "MCP(N)", "A2A(T)", "A2A(N)"],
               [14, 18, 18, 18, 18, 18, 18],
               rows,
               [None, (37,99,235), (37,99,235), (37,99,235), (37,99,235), (37,99,235), (37,99,235)])

    # ════════════════════════════════════════════════════════════════════════
    # COMPARISONS 17-18: harm vs cons (HTTP only)
    # ════════════════════════════════════════════════════════════════════════
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 12)
    pdf.set_text_color(*CLR_TITLE)
    pdf.cell(0, 8, "D. Playbook Wording: Harmonized vs Conservative (HTTP only)", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(2)

    # Chart: harm vs cons for think and nothink
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(10, 3.5), sharey=True)

    for ax, mode, hkey, ckey, title_num in [
        (ax1, "think", "HTTP harm T", "HTTP cons T", 17),
        (ax2, "nothink", "HTTP harm N", "HTTP cons N", 18),
    ]:
        nopb_vals = sr_series(experiments[hkey], "nopb")
        harm_vals = sr_series(experiments[hkey], "pb")
        cons_vals = sr_series(experiments[ckey], "pb")
        x = range(len(RATES))
        ax.plot(x, nopb_vals, label="nopb", color="#ef4444", linewidth=1.5, marker="o", markersize=3)
        ax.plot(x, harm_vals, label="harm pb", color="#22c55e", linewidth=2, marker="s", markersize=3)
        ax.plot(x, cons_vals, label="cons pb", color="#f97316", linewidth=2, marker="^", markersize=3, linestyle="--")
        ax.set_title(f"#{title_num}: HTTP {mode}", fontsize=10, fontweight="bold")
        ax.set_xticks(x)
        ax.set_xticklabels(RATE_LABELS, fontsize=7, rotation=45)
        ax.set_ylim(40, 101)
        ax.set_ylabel("SR (%)", fontsize=8)
        ax.grid(True, alpha=0.3)
        ax.legend(fontsize=7, loc="lower left")
    fig.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=150)
    plt.close(fig)
    buf.seek(0)
    add_chart(buf.read())

    # Table
    rows = []
    for r in RATES:
        rkey = f"{r:.4g}"
        ht = experiments["HTTP harm T"][rkey]
        ct = experiments["HTTP cons T"][rkey]
        hn = experiments["HTTP harm N"][rkey]
        cn = experiments["HTTP cons N"][rkey]
        ht_sr = sr(ht["pb_ok"], ht["pb_n"])
        ct_sr = sr(ct["pb_ok"], ct["pb_n"])
        hn_sr = sr(hn["pb_ok"], hn["pb_n"])
        cn_sr = sr(cn["pb_ok"], cn["pb_n"])
        dt = ht_sr - ct_sr if ht_sr and ct_sr else 0
        dn = hn_sr - cn_sr if hn_sr and cn_sr else 0
        st = "+" if dt >= 0 else ""
        sn = "+" if dn >= 0 else ""
        rows.append([
            f"{round(r*100)}%",
            f"{ht_sr:.1f}%" if ht_sr else "-",
            f"{ct_sr:.1f}%" if ct_sr else "-",
            f"{st}{dt:.1f}pp",
            f"{hn_sr:.1f}%" if hn_sr else "-",
            f"{cn_sr:.1f}%" if cn_sr else "-",
            f"{sn}{dn:.1f}pp",
        ])
    draw_table("#17-18: Harmonized vs Conservative (HTTP)",
               ["Rate", "harm(T)", "cons(T)", "H-C(T)", "harm(N)", "cons(N)", "H-C(N)"],
               [14, 18, 18, 22, 18, 18, 22],
               rows,
               [None, (34,197,94), (249,115,22), (37,99,235), (34,197,94), (249,115,22), (37,99,235)])

    # ════════════════════════════════════════════════════════════════════════
    # SUMMARY: Coherence Assessment
    # ════════════════════════════════════════════════════════════════════════
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 12)
    pdf.set_text_color(*CLR_TITLE)
    pdf.cell(0, 8, "E. Coherence Assessment", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(2)

    coh_rows = [
        ["#1-2", "Cross-protocol nopb", "Ranking inverts T/N", "Interaction effect", "REAL"],
        ["#3", "HTTP T vs N nopb", "+1.4pp think", "Neutral", "OK"],
        ["#4", "MCP T vs N nopb", "-10.1pp think", "Think penalizes", "REAL"],
        ["#5", "A2A T vs N nopb", "-7.4pp think", "Think penalizes", "REAL"],
        ["#6-7", "Cross-protocol harm", "MCP think outlier", "Tool call complexity", "REAL"],
        ["#8", "HTTP T vs N harm", "+0.9pp think", "Neutral", "OK"],
        ["#9", "MCP T vs N harm", "-5.2pp think", "Penalty persists", "REAL"],
        ["#10", "A2A T vs N harm", "+0.1pp", "pb neutralizes", "OK"],
        ["#11-16", "pb vs nopb (all 6)", "+12 to +20pp", "Consistent", "OK"],
        ["#17", "harm vs cons think", "+0.9pp harm", "Marginal", "NOISE?"],
        ["#18", "harm vs cons nothink", "-0.2pp harm", "Sign flip", "NOISE?"],
    ]
    draw_table("Coherence summary",
               ["#", "Comparison", "Result", "Interpretation", "Status"],
               [12, 42, 30, 38, 16],
               coh_rows,
               [CLR_GRAY, None, None, None, None])

    # Key findings text
    pdf.set_font("Helvetica", "B", 10)
    pdf.set_text_color(*CLR_TITLE)
    pdf.cell(0, 8, "Key Findings", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 8)
    pdf.set_text_color(*CLR_BLACK)
    findings = [
        "1. Playbook >> no playbook: +12 to +20pp aggregate, +43-50pp at 30% rate. Robust across all 6 combos.",
        "2. Thinking x Protocol interaction: think helps HTTP (+0.9pp), hurts MCP (-5.2pp), neutral A2A with pb.",
        "3. Playbook wording (harm vs cons) has negligible effect for HTTP (0-3pp). Fault injector only produces known errors.",
        "4. A2A achieves near-perfect resilience (99.6-100%) regardless of thinking mode when using playbook.",
        "5. MCP think is the outlier: 94.7% aggregate vs 99%+ for all other combos. Even fails at 0% rate (99.4%).",
        "6. No-think mode is 3.5x faster (13s vs 45s) with similar or better SR in most conditions.",
    ]
    for f in findings:
        pdf.cell(0, 5, _safe(f), new_x="LMARGIN", new_y="NEXT")

    # ── Footer ──
    pdf.set_auto_page_break(auto=False)
    page_count = pdf.page_no()
    pdf.set_font("Helvetica", "I", 7)
    pdf.set_text_color(*CLR_GRAY)
    footer = f"Chaos Playbook Engine - Full Comparison Report  |  Chaos Playbook Lab  |  {now}"
    for i in range(1, page_count + 1):
        pdf.page = i
        pdf.set_y(-12)
        pdf.cell(0, 5, f"{footer}  |  Page {i}/{page_count}", align="C")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    pdf.output(str(output_path))
    print(f"Report saved: {output_path} ({output_path.stat().st_size / 1024:.1f} KB)")


def build_report_bytes() -> bytes:
    """Generate the comparison PDF and return raw bytes (for dashboard integration)."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    # Reuse build_report logic but return bytes instead of writing to file
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp_path = Path(tmp.name)
    build_report(tmp_path)
    data = tmp_path.read_bytes()
    tmp_path.unlink(missing_ok=True)
    return data


def main():
    parser = argparse.ArgumentParser(description="Generate comparison PDF report")
    parser.add_argument("--output", type=str,
                        default="reports/paper/comparison-report.pdf")
    args = parser.parse_args()
    build_report(Path(args.output))


if __name__ == "__main__":
    main()
