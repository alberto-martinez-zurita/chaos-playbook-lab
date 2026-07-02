"""Experiment dashboard — local web server with planned experiment matrix.

The dashboard knows the full experiment plan (models, protocols, rates,
experiments_per_rate) and shows progress against it.  Empty cells appear
as "pending" — when you add more models or rates later, existing data
is preserved and new cells appear automatically.

Usage:
    python scripts/dashboard.py
    python scripts/dashboard.py --models glm-4.5 glm-4.5-flash glm-5
    python scripts/dashboard.py --rates 0.0 0.01 0.05 0.10
    python scripts/dashboard.py --per-rate 50
"""
from __future__ import annotations

import argparse
import csv
import json
import webbrowser
from collections import defaultdict
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
REPORTS_DIR = _ROOT / "reports" / "parametric_experiments"


def model_tag(model: str) -> str:
    """Convert model name to directory tag.

    Handles special suffixes like '_nothink' that use underscores in
    directory names but hyphens in CLI model names.
    """
    # Separate known suffixes before tag conversion
    suffix = ""
    for s in ("_nothink", "_think"):
        hyphen_s = s.replace("_", "-")
        if model.endswith(hyphen_s):
            model = model[: -len(hyphen_s)]
            suffix = s
            break
    return model.replace(".", "").replace("-", "") + suffix


def _safe_int(v) -> int:
    try:
        return int(float(v))
    except (ValueError, TypeError):
        return 0


def _safe_float(v) -> float:
    try:
        return float(v)
    except (ValueError, TypeError):
        return 0.0


def scan_data(models: list[str], protocols: list[str],
              rates: list[float], per_rate: int) -> dict:
    """Build the full experiment matrix with progress from disk."""
    matrix = []

    for model in models:
        mtag = model_tag(model)
        for proto in protocols:
            dirname = f"run_paper_{proto}_{mtag}"
            csv_path = REPORTS_DIR / dirname / "raw_results.csv"

            # Per-rate buckets
            rate_data = {}
            for r in rates:
                rate_data[f"{r:.4g}"] = {
                    "nopb": 0, "pb": 0,
                    "nopb_ok": 0, "pb_ok": 0,
                    "nopb_fail": 0, "pb_fail": 0,
                    "nopb_inc": 0, "pb_inc": 0,
                    "nopb_dur": 0.0, "pb_dur": 0.0,
                    "nopb_chars": 0, "pb_chars": 0,
                    "nopb_ptok": 0, "pb_ptok": 0,
                    "nopb_ctok": 0, "pb_ctok": 0,
                }

            # Read data from per-rate CSVs (rate_X.XX.csv) and legacy raw_results.csv
            total_rows = 0
            data_dir = REPORTS_DIR / dirname
            csv_files = sorted(data_dir.glob("rate_*.csv")) if data_dir.exists() else []
            # Fallback: also read legacy raw_results.csv
            legacy_csv = data_dir / "raw_results.csv"
            if legacy_csv.exists():
                csv_files.append(legacy_csv)

            for csv_file in csv_files:
                if not csv_file.exists():
                    continue
                with open(csv_file, "r", encoding="utf-8") as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        total_rows += 1
                        rkey_raw = row.get("failure_rate")
                        if not rkey_raw:
                            continue
                        try:
                            rkey = f"{float(rkey_raw):.4g}"
                        except (ValueError, TypeError):
                            continue
                        if rkey not in rate_data:
                            rate_data[rkey] = {
                                "nopb": 0, "pb": 0,
                                "nopb_ok": 0, "pb_ok": 0,
                                "nopb_fail": 0, "pb_fail": 0,
                                "nopb_inc": 0, "pb_inc": 0,
                                "nopb_dur": 0.0, "pb_dur": 0.0,
                                "nopb_chars": 0, "pb_chars": 0,
                                "nopb_ptok": 0, "pb_ptok": 0,
                                "nopb_ctok": 0, "pb_ctok": 0,
                            }
                        bucket = rate_data[rkey]
                        agent = row.get("agent_type", "")
                        outcome = row.get("outcome", "")
                        is_nopb = "nopb" in agent
                        prefix = "nopb" if is_nopb else "pb"
                        bucket[prefix] += 1
                        if outcome == "success":
                            bucket[f"{prefix}_ok"] += 1
                        else:
                            bucket[f"{prefix}_fail"] += 1
                        inc = _safe_int(row.get("inconsistencies_count", 0))
                        if inc > 0:
                            bucket[f"{prefix}_inc"] += 1
                        bucket[f"{prefix}_dur"] += _safe_float(row.get("duration_ms", 0))
                        in_c = _safe_int(row.get("input_chars", 0))
                        out_c = _safe_int(row.get("output_chars", 0))
                        bucket[f"{prefix}_chars"] += in_c + out_c
                        bucket[f"{prefix}_ptok"] += _safe_int(row.get("prompt_tokens", 0))
                        bucket[f"{prefix}_ctok"] += _safe_int(row.get("completion_tokens", 0))

            expected = len(rates) * per_rate * 2
            done = total_rows
            status = "done" if done >= expected and done > 0 else (
                "partial" if done > 0 else "pending")

            matrix.append({
                "model": model,
                "protocol": proto,
                "dir": dirname,
                "total_rows": total_rows,
                "expected": expected,
                "per_rate": per_rate,
                "rates": rate_data,
                "status": status,
                "relaunch": (
                    f"python scripts/run_paper_multimodel.py "
                    f"--model {model} --protocol {proto} "
                    f"--experiments-per-rate {per_rate}"
                ),
            })

    return {
        "models": models,
        "protocols": protocols,
        "rates": rates,
        "per_rate": per_rate,
        "matrix": matrix,
        "total_planned": len(models) * len(protocols) * len(rates) * per_rate * 2,
    }


# ── Shared config (set by main, read by handler) ──────────────────────────
_CFG: dict = {}


def build_html() -> str:
    data = scan_data(**_CFG)
    data_json = json.dumps(data)

    return """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Chaos Playbook Engine</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.7/dist/chart.umd.min.js"></script>
<style>
* { margin:0; padding:0; box-sizing:border-box; }
body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
       background:#0f1117; color:#e0e0e0; padding:20px; }
h1 { color:#fff; font-size:1.4em; margin-bottom:2px; }
.sub { color:#888; font-size:.85em; margin-bottom:16px; }
.clock { color:#555; font-size:.75em; }
.top-bar { display:flex; align-items:center; justify-content:space-between;
           flex-wrap:wrap; gap:8px; margin-bottom:4px; }

/* ── summary bar ──────────────────────────────────────────── */
.summary { display:flex; flex-wrap:wrap; gap:16px 24px; margin-bottom:20px; padding:12px 16px;
           background:#1a1d27; border-radius:8px; }
.summary .s { text-align:center; min-width:100px; }
.summary .n { font-size:1.6em; font-weight:700; color:#fff; }
.summary .l { font-size:.75em; color:#888; }

/* ── matrix grid ──────────────────────────────────────────── */
.matrix { display:grid; gap:12px; margin-bottom:24px; }
@media (max-width:1200px) { .matrix { grid-template-columns:repeat(2,1fr) !important; } }
@media (max-width:800px)  { .matrix { grid-template-columns:1fr !important; } }
.cell { background:#1a1d27; border-radius:8px; padding:12px 14px;
        border-left:4px solid #333; transition:border-color .3s; }
.cell.done    { border-left-color:#34d399; }
.cell.partial { border-left-color:#fbbf24; }
.cell.pending { border-left-color:#333; opacity:.6; }
.cell-head { display:flex; justify-content:space-between; align-items:center;
             cursor:pointer; user-select:none; flex-wrap:wrap; gap:4px; }
.cell-title { font-weight:600; font-size:.95em; }
.cell-title .proto { color:#7dd3fc; }
.cell-title .proto.http { color:#f97316; }
.cell-title .proto.a2a  { color:#a78bfa; }
.cell-agg { font-size:.75em; color:#aaa; margin-left:auto; margin-right:12px; }
.cell-badge { font-size:.75em; padding:2px 8px; border-radius:4px; font-weight:600; }
.cell-badge.done    { background:#064e3b; color:#6ee7b7; }
.cell-badge.partial { background:#78350f; color:#fbbf24; }
.cell-badge.pending { background:#1e2130; color:#555; }
.cell-progress { margin-top:6px; }
.pbar { background:#0f1117; border-radius:4px; height:18px; position:relative; overflow:hidden; }
.pfill { height:100%; border-radius:4px; transition:width .5s; max-width:100%; }
.pfill.done    { background:linear-gradient(90deg,#059669,#34d399); }
.pfill.partial { background:linear-gradient(90deg,#d97706,#fbbf24); }
.ptxt { position:absolute; inset:0; display:flex; align-items:center;
        justify-content:center; font-size:.7em; font-weight:600; }

/* ── rate detail ──────────────────────────────────────────── */
.rates { display:none; margin-top:10px; }
.rates.open { display:block; }
.rate-row { display:grid; grid-template-columns:70px 1fr 1fr; gap:8px;
            padding:4px 0; border-bottom:1px solid #1e2130; font-size:.8em; }
@media (max-width:600px) { .rate-row { grid-template-columns:50px 1fr; } }
.rate-row.header { color:#888; font-weight:600; border-bottom:2px solid #2a2d3a; }
.rate-label { color:#7dd3fc; font-weight:600; }
.agent-cell { display:flex; flex-direction:column; gap:2px; }
.agent-top { display:flex; align-items:center; gap:6px; width:100%; }
.mini-bar { flex:1; background:#0f1117; border-radius:3px; height:12px; position:relative; overflow:hidden; }
.mini-fill { height:100%; border-radius:3px; max-width:100%; }
.mini-fill.nopb { background:#ef4444; }
.mini-fill.pb   { background:#22c55e; }
.agent-count { font-size:.85em; white-space:nowrap; min-width:55px; text-align:right; }
.agent-detail { font-size:.8em; display:flex; flex-wrap:wrap; justify-content:flex-end; gap:2px 6px; }
.agent-detail .col-sr  { min-width:40px; text-align:right; }
.agent-detail .col-t   { min-width:32px; text-align:right; }
.agent-detail .col-tok { min-width:38px; text-align:right; }
.agent-detail .col-inc { min-width:26px; text-align:right; }
.sr { font-weight:600; }
.sr.nopb { color:#ef4444; }
.sr.pb   { color:#22c55e; }
.sr.high { color:#6ee7b7; }
.inc { color:#fbbf24; font-weight:600; font-size:.9em; }
.inc.zero { color:#555; font-weight:400; }
.timing { color:#94a3b8; font-size:.9em; }
.tokens { color:#c084fc; font-size:.9em; }

.cmd { font-family:'Fira Code','Consolas',monospace; font-size:.7em;
       background:#0f1117; padding:4px 8px; border-radius:4px; color:#fbbf24;
       cursor:pointer; display:inline-block; margin-top:6px; word-break:break-all; }
.cmd:hover { background:#2a2d37; }
.cmd.copied { color:#22c55e; }

/* ── breakdown sections ───────────────────────────────────── */
.breakdowns { display:grid; grid-template-columns:1fr 1fr; gap:16px; margin-bottom:20px; }
@media (max-width:900px) { .breakdowns { grid-template-columns:1fr; } }
.bd-left { display:flex; flex-direction:column; gap:16px; }
.breakdown { background:#1a1d27; border-radius:8px; padding:14px 16px; }
.breakdown h2 { font-size:.85em; color:#aaa; text-transform:uppercase;
                letter-spacing:.05em; margin-bottom:10px; }
.bd-row { display:grid; grid-template-columns:70px 1fr; gap:8px; padding:5px 0;
          border-bottom:1px solid #1e2130; align-items:center; cursor:pointer;
          transition:background .15s; border-radius:4px; }
.bd-row:hover { background:#252836; }
.bd-metrics { display:flex; flex-wrap:wrap; gap:6px 12px; margin-top:4px; font-size:.8em; color:#aaa; }
.bd-metrics strong { color:#e0e0e0; }
.bd-label { font-weight:600; font-size:.85em; }
.bd-label.http { color:#f97316; }
.bd-label.mcp  { color:#7dd3fc; }
.bd-label.a2a  { color:#a78bfa; }
.bd-label.rate { color:#7dd3fc; }
.bd-bar { flex:1; background:#0f1117; border-radius:4px; height:16px; position:relative; overflow:hidden; }
.bd-fill { height:100%; border-radius:4px; max-width:100%; }
.bd-fill.http { background:linear-gradient(90deg,#c2410c,#f97316); }
.bd-fill.mcp  { background:linear-gradient(90deg,#0369a1,#7dd3fc); }
.bd-fill.a2a  { background:linear-gradient(90deg,#6d28d9,#a78bfa); }
.bd-fill.rate { background:linear-gradient(90deg,#0369a1,#7dd3fc); }
.bd-fill.think  { background:linear-gradient(90deg,#b45309,#fbbf24); }
.bd-fill.nothink { background:linear-gradient(90deg,#0d9488,#5eead4); }
.bd-label.think  { color:#fbbf24; }
.bd-label.nothink { color:#5eead4; }

/* ── buttons ─────────────────────────────────────────────── */
.export-btn { background:#1a1d27; border:1px solid #333; color:#7dd3fc; padding:6px 14px;
              border-radius:6px; cursor:pointer; font-size:.8em; font-weight:600;
              transition:all .2s; }
.export-btn:hover { background:#2a2d3a; border-color:#7dd3fc; }

/* ── detail overlay ──────────────────────────────────────── */
.detail-overlay { position:fixed; inset:0; background:rgba(0,0,0,.7); z-index:100;
                  display:flex; align-items:center; justify-content:center;
                  animation:fadeIn .15s; }
@keyframes fadeIn { from{opacity:0} to{opacity:1} }
.detail-panel { background:#1a1d27; border-radius:12px; padding:24px; width:90vw;
                max-width:900px; max-height:90vh; overflow-y:auto; position:relative; }
.detail-panel h2 { color:#fff; font-size:1.2em; margin-bottom:4px; }
.detail-panel .detail-sub { color:#888; font-size:.8em; margin-bottom:16px; }
.detail-close { position:absolute; top:12px; right:16px; background:none; border:none;
                color:#888; font-size:1.4em; cursor:pointer; }
.detail-close:hover { color:#fff; }
.detail-chart-wrap { background:#0f1117; border-radius:8px; padding:16px; margin-bottom:16px; }
.detail-table { width:100%; border-collapse:collapse; font-size:.82em; margin-top:12px; }
.detail-table th { text-align:left; padding:5px 8px; color:#888; border-bottom:2px solid #2a2d3a;
                   font-size:.8em; text-transform:uppercase; }
.detail-table td { padding:4px 8px; border-bottom:1px solid #1e2130; }
.detail-table tr:hover { background:#252836; }
</style>
</head>
<body>
<div class="top-bar">
<div><h1>Chaos Playbook Engine</h1>
<p class="sub">Experiment Dashboard &mdash; 4 steps, 10 rates &times; 3 protocols &times; 2 thinking modes &times; 500/rate</p></div>
<div style="display:flex;gap:8px;align-items:center">
<button class="export-btn" onclick="exportReport()">Export PDF</button>
<span class="clock" id="clock"></span></div>
</div>

<div id="app">Loading...</div>
<div id="detail-root"></div>

<script>
let DATA = """ + data_json + """;
let openCells = null;

function rk(r) {
  if (r === 0) return "0";
  let s = r.toPrecision(4);
  if (s.includes('.')) s = s.replace(/0+$/, '').replace(/\\.$/, '');
  return s;
}

// ── Aggregation helpers ──────────────────────────────────────
function aggCells(cells, rates) {
  // Returns per-rate {nopb_ok, nopb_n, pb_ok, pb_n, ...} for given cells
  const byRate = {};
  rates.forEach(r => {
    const k = rk(r);
    let nt=0,no=0,pt=0,po=0,dur=0,tok=0,ni=0,pi=0;
    cells.forEach(c => {
      const rd = c.rates[k];
      if (!rd) return;
      nt+=rd.nopb; no+=rd.nopb_ok; pt+=rd.pb; po+=rd.pb_ok;
      dur+=(rd.nopb_dur||0)+(rd.pb_dur||0);
      tok+=(rd.nopb_ptok||0)+(rd.pb_ptok||0)+(rd.nopb_ctok||0)+(rd.pb_ctok||0);
      ni+=(rd.nopb_inc||0); pi+=(rd.pb_inc||0);
    });
    byRate[k] = {nopb_n:nt, nopb_ok:no, pb_n:pt, pb_ok:po, dur, tok, nopb_inc:ni, pb_inc:pi};
  });
  return byRate;
}

function srPct(ok,n) { return n ? (100*ok/n) : null; }
function fmtSR(ok,n) { return n ? Math.round(100*ok/n)+'%' : '-'; }

// ── Detail view ──────────────────────────────────────────────
let activeChart = null;

function showDetail(title, subtitle, cells) {
  const m = DATA;
  const byRate = aggCells(cells, m.rates);
  const root = document.getElementById('detail-root');

  const labels = m.rates.map(r => Math.round(r*100)+'%');
  const nopbData = m.rates.map(r => { const d=byRate[rk(r)]; return srPct(d.nopb_ok,d.nopb_n); });
  const pbData = m.rates.map(r => { const d=byRate[rk(r)]; return srPct(d.pb_ok,d.pb_n); });

  // Table rows
  let tableRows = '';
  m.rates.forEach(r => {
    const k = rk(r);
    const d = byRate[k];
    const nsr = fmtSR(d.nopb_ok,d.nopb_n);
    const psr = fmtSR(d.pb_ok,d.pb_n);
    const delta = (d.nopb_n && d.pb_n) ?
      (v => (v>=0?'+':'')+v.toFixed(1)+'pp')(100*d.pb_ok/d.pb_n - 100*d.nopb_ok/d.nopb_n) : '-';
    const avgS = (d.nopb_n+d.pb_n) ? (d.dur/(d.nopb_n+d.pb_n)/1000).toFixed(1)+'s' : '-';
    const avgTok = (d.nopb_n+d.pb_n) ? Math.round(d.tok/(d.nopb_n+d.pb_n)).toLocaleString() : '-';
    tableRows += `<tr>
      <td>${Math.round(r*100)}%</td>
      <td>${d.nopb_n+d.pb_n}</td>
      <td><span class="sr nopb">${nsr}</span></td>
      <td><span class="sr pb">${psr}</span></td>
      <td style="color:#60a5fa;font-weight:600">${delta}</td>
      <td class="timing">${avgS}</td>
      <td class="tokens">${avgTok}</td>
      <td><span class="inc${(d.nopb_inc+d.pb_inc)?'':' zero'}">${d.nopb_inc+d.pb_inc}</span></td>
    </tr>`;
  });

  root.innerHTML = `<div class="detail-overlay" onclick="if(event.target===this)closeDetail()">
    <div class="detail-panel">
      <button class="detail-close" onclick="closeDetail()">&times;</button>
      <h2>${title}</h2>
      <div class="detail-sub">${subtitle}</div>
      <div class="detail-chart-wrap"><canvas id="detail-chart" height="260"></canvas></div>
      <table class="detail-table">
        <tr><th>Rate</th><th>N</th><th>nopb SR</th><th>pb SR</th><th>Delta</th><th>Avg time</th><th>Avg tok</th><th>Inc</th></tr>
        ${tableRows}
      </table>
    </div>
  </div>`;

  // Draw chart
  if (activeChart) { activeChart.destroy(); activeChart=null; }
  const ctx = document.getElementById('detail-chart').getContext('2d');
  activeChart = new Chart(ctx, {
    type: 'line',
    data: {
      labels,
      datasets: [
        { label:'No Playbook (nopb)', data:nopbData, borderColor:'#ef4444', backgroundColor:'rgba(239,68,68,.15)',
          fill:true, tension:.3, pointRadius:4, borderWidth:2 },
        { label:'Playbook (pb)', data:pbData, borderColor:'#22c55e', backgroundColor:'rgba(34,197,94,.15)',
          fill:true, tension:.3, pointRadius:4, borderWidth:2 },
      ]
    },
    options: {
      responsive:true,
      plugins: {
        legend: { labels: { color:'#ccc', font:{size:12} } },
        title: { display:true, text:'Success Rate vs Failure Rate', color:'#aaa', font:{size:13} },
      },
      scales: {
        x: { title:{display:true,text:'Failure Rate',color:'#888'}, ticks:{color:'#888'}, grid:{color:'#1e2130'} },
        y: { title:{display:true,text:'Success Rate (%)',color:'#888'}, ticks:{color:'#888'}, grid:{color:'#1e2130'},
             min:0, max:105 },
      }
    }
  });
}

function closeDetail() {
  if (activeChart) { activeChart.destroy(); activeChart=null; }
  document.getElementById('detail-root').innerHTML = '';
}

// ── Main render ──────────────────────────────────────────────
function render() {
  const app = document.getElementById('app');
  document.getElementById('clock').textContent = new Date().toLocaleTimeString();

  const m = DATA;
  const totalDone = m.matrix.reduce((s,c) => s + c.total_rows, 0);
  const totalPlanned = m.total_planned;
  const pct = totalPlanned ? Math.round(100*totalDone/totalPlanned) : 0;
  const combosTotal = m.matrix.length;
  const combosDone = m.matrix.filter(c => c.status==='done').length;

  let totalDurMs=0, totalPtok=0, totalCtok=0;
  m.matrix.forEach(c => { Object.values(c.rates).forEach(rd => {
    totalDurMs += (rd.nopb_dur||0) + (rd.pb_dur||0);
    totalPtok += (rd.nopb_ptok||0) + (rd.pb_ptok||0);
    totalCtok += (rd.nopb_ctok||0) + (rd.pb_ctok||0);
  })});
  const totalDurMin = (totalDurMs/1000/60).toFixed(1);
  const avgDurS = totalDone ? (totalDurMs/totalDone/1000).toFixed(1) : '-';
  const totalTok = totalPtok + totalCtok;
  const avgTok = totalDone ? Math.round(totalTok/totalDone) : '-';

  let html = `<div class="summary">
    <div class="s"><div class="n">${totalDone.toLocaleString()} / ${totalPlanned.toLocaleString()}</div><div class="l">Experiments (${pct}%)</div></div>
    <div class="s"><div class="n">${combosDone} / ${combosTotal}</div><div class="l">Combos complete</div></div>
    <div class="s"><div class="n">${totalDurMin} min</div><div class="l">Total time</div></div>
    <div class="s"><div class="n">${avgDurS}s</div><div class="l">Avg / experiment</div></div>
    <div class="s"><div class="n">${totalTok.toLocaleString()}</div><div class="l">Total tokens</div></div>
    <div class="s"><div class="n">${typeof avgTok==='number'?avgTok.toLocaleString():avgTok}</div><div class="l">Avg tok / exp</div></div>
  </div>`;

  // ── Breakdowns ──────────────────────────────────────────────
  function bdRow(label, cls, done, planned, nSR, pSR, avgS, avgTok, onclick) {
    const p = planned ? Math.round(100*done/planned) : 0;
    return `<div class="bd-row" onclick="${onclick||''}">
      <div class="bd-label ${cls}">${label}</div>
      <div>
        <div class="bd-bar"><div class="bd-fill ${cls}" style="width:${p}%"></div></div>
        <div class="bd-metrics">
          <span><strong>${done.toLocaleString()}/${planned.toLocaleString()}</strong> (${p}%)</span>
          <span>nopb:<span class="sr nopb">${nSR}%</span></span>
          <span>pb:<span class="sr pb">${pSR}%</span></span>
          <span class="timing">${avgS}s/exp</span>
          <span class="tokens">${avgTok}tok/exp</span>
        </div>
      </div>
    </div>`;
  }

  html += `<div class="breakdowns">`;
  html += `<div class="bd-left">`;

  // By Protocol
  html += `<div class="breakdown"><h2>By Protocol</h2>`;
  m.protocols.forEach(proto => {
    const cells = m.matrix.filter(c => c.protocol===proto);
    const done = cells.reduce((s,c) => s + c.total_rows, 0);
    const planned = cells.reduce((s,c) => s + c.expected, 0);
    let nt=0,no=0,pt=0,po=0,dur=0,tok=0;
    cells.forEach(c => { Object.values(c.rates).forEach(rd => {
      nt+=rd.nopb; no+=rd.nopb_ok; pt+=rd.pb; po+=rd.pb_ok;
      dur+=(rd.nopb_dur||0)+(rd.pb_dur||0);
      tok+=(rd.nopb_ptok||0)+(rd.pb_ptok||0)+(rd.nopb_ctok||0)+(rd.pb_ctok||0);
    })});
    const nSR = nt ? Math.round(100*no/nt) : '-';
    const pSR = pt ? Math.round(100*po/pt) : '-';
    const avgS = done ? (dur/done/1000).toFixed(1) : '-';
    const avgT = done ? Math.round(tok/done) : '-';
    const onclick = `showDetail('${proto.toUpperCase()}','Protocol: ${proto.toUpperCase()} &mdash; all thinking modes',DATA.matrix.filter(c=>c.protocol==='${proto}'))`;
    html += bdRow(proto.toUpperCase(), proto, done, planned, nSR, pSR, avgS, avgT, onclick);
  });
  html += `<div style="font-size:.7em;color:#555;margin-top:6px">SR: <span class="sr nopb">nopb</span> / <span class="sr pb">pb</span> &mdash; click for detail</div>`;
  html += `</div>`;

  // Think vs No-think
  html += `<div class="breakdown"><h2>Think vs No-think</h2>`;
  const thinkModes = [
    { label:'think', cls:'think', filter:'!c.model.includes("nothink")' },
    { label:'no-think', cls:'nothink', filter:'c.model.includes("nothink")' },
  ];
  thinkModes.forEach(tm => {
    const cells = m.matrix.filter(tm.label==='think' ? c=>!c.model.includes('nothink') : c=>c.model.includes('nothink'));
    const done = cells.reduce((s,c) => s + c.total_rows, 0);
    const planned = cells.reduce((s,c) => s + c.expected, 0);
    let nt=0,no=0,pt=0,po=0,dur=0,tok=0;
    cells.forEach(c => { Object.values(c.rates).forEach(rd => {
      nt+=rd.nopb; no+=rd.nopb_ok; pt+=rd.pb; po+=rd.pb_ok;
      dur+=(rd.nopb_dur||0)+(rd.pb_dur||0);
      tok+=(rd.nopb_ptok||0)+(rd.pb_ptok||0)+(rd.nopb_ctok||0)+(rd.pb_ctok||0);
    })});
    const nSR = nt ? Math.round(100*no/nt) : '-';
    const pSR = pt ? Math.round(100*po/pt) : '-';
    const avgS = done ? (dur/done/1000).toFixed(1) : '-';
    const avgT = done ? Math.round(tok/done) : '-';
    const onclick = `showDetail('${tm.label}','Thinking mode: ${tm.label} &mdash; all protocols',DATA.matrix.filter(c=>${tm.filter}))`;
    html += bdRow(tm.label, tm.cls, done, planned, nSR, pSR, avgS, avgT, onclick);
  });
  html += `<div style="font-size:.7em;color:#555;margin-top:6px">SR: <span class="sr nopb">nopb</span> / <span class="sr pb">pb</span> &mdash; click for detail</div>`;
  html += `</div>`;

  html += `</div>`; // bd-left

  // By Failure Rate
  html += `<div class="breakdown"><h2>By Failure Rate</h2>`;
  m.rates.forEach(rate => {
    const rKey = rk(rate);
    let done=0,planned=0,nt=0,no=0,pt=0,po=0,dur=0,tok=0;
    m.matrix.forEach(c => {
      planned += c.per_rate * 2;
      const rd = c.rates[rKey];
      if (rd) {
        done+=rd.nopb+rd.pb; nt+=rd.nopb; no+=rd.nopb_ok; pt+=rd.pb; po+=rd.pb_ok;
        dur+=(rd.nopb_dur||0)+(rd.pb_dur||0);
        tok+=(rd.nopb_ptok||0)+(rd.pb_ptok||0)+(rd.nopb_ctok||0)+(rd.pb_ctok||0);
      }
    });
    const nSR = nt ? Math.round(100*no/nt) : '-';
    const pSR = pt ? Math.round(100*po/pt) : '-';
    const avgS = done ? (dur/done/1000).toFixed(1) : '-';
    const avgT = done ? Math.round(tok/done) : '-';
    html += bdRow(Math.round(rate*100)+'%', 'rate', done, planned, nSR, pSR, avgS, avgT, '');
  });
  html += `<div style="font-size:.7em;color:#555;margin-top:6px">SR: <span class="sr nopb">nopb</span> / <span class="sr pb">pb</span></div>`;
  html += `</div></div>`;

  // ── Matrix grid ─────────────────────────────────────────
  const cols = m.protocols.length;
  html += `<div class="matrix" style="grid-template-columns:repeat(${cols},1fr)">`;

  m.models.forEach(model => {
    m.protocols.forEach(proto => {
      const cell = m.matrix.find(c => c.model===model && c.protocol===proto);
      if (!cell) return;
      const cellId = `${model}-${proto}`;
      const isOpen = openCells === null || openCells.has(cellId);
      const pct = cell.expected ? Math.min(100, Math.round(100*cell.total_rows/cell.expected)) : 0;

      let cNopb=0,cNopbOk=0,cPb=0,cPbOk=0,cDur=0,cTok=0,cInc=0;
      Object.values(cell.rates).forEach(rd => {
        cNopb+=rd.nopb; cNopbOk+=rd.nopb_ok; cPb+=rd.pb; cPbOk+=rd.pb_ok;
        cDur+=(rd.nopb_dur||0)+(rd.pb_dur||0);
        cTok+=(rd.nopb_ptok||0)+(rd.pb_ptok||0)+(rd.nopb_ctok||0)+(rd.pb_ctok||0);
        cInc+=(rd.nopb_inc||0)+(rd.pb_inc||0);
      });
      const cNSR = cNopb ? Math.round(100*cNopbOk/cNopb) : '-';
      const cPSR = cPb ? Math.round(100*cPbOk/cPb) : '-';
      const cAvgS = cell.total_rows ? (cDur/cell.total_rows/1000).toFixed(1) : '-';
      const cAvgTok = cell.total_rows ? Math.round(cTok/cell.total_rows) : '-';

      html += `<div class="cell ${cell.status}">
        <div class="cell-head" onclick="toggleCell('${cellId}')">
          <span class="cell-title"><strong>${model}</strong> <span class="proto ${proto}">${proto.toUpperCase()}</span></span>
          <span class="cell-agg">SR:<span class="sr nopb">${cNSR}%</span> <span class="sr pb">${cPSR}%</span> <span class="timing">${cAvgS}s</span> <span class="tokens">${cAvgTok}tok</span> <span class="inc${cInc?'':' zero'}">${cInc}inc</span></span>
          <span class="cell-badge ${cell.status}">${cell.total_rows}/${cell.expected}</span>
        </div>
        <div class="cell-progress">
          <div class="pbar"><div class="pfill ${cell.status}" style="width:${Math.min(pct,100)}%"></div>
            <div class="ptxt">${pct}%</div></div>
        </div>
        <div class="rates ${isOpen?'open':''}" id="rates-${cellId}">`;

      html += `<div class="rate-row header">
        <div>Rate</div><div>No Playbook (n / SR / time / tok / inc)</div><div>Playbook (n / SR / time / tok / inc)</div></div>`;

      const allRateKeys = m.rates.map(r => rk(r));
      Object.keys(cell.rates).forEach(k => { if (!allRateKeys.includes(k)) allRateKeys.push(k); });

      allRateKeys.forEach(rKey => {
        const rd = cell.rates[rKey] || {nopb:0,pb:0,nopb_ok:0,pb_ok:0,nopb_fail:0,pb_fail:0,nopb_inc:0,pb_inc:0,nopb_dur:0,pb_dur:0,nopb_chars:0,pb_chars:0,nopb_ptok:0,pb_ptok:0,nopb_ctok:0,pb_ctok:0};
        const pr = cell.per_rate;
        const nPct = pr ? Math.min(100, Math.round(100*rd.nopb/pr)) : 0;
        const pPct = pr ? Math.min(100, Math.round(100*rd.pb/pr)) : 0;
        const nSR = rd.nopb ? Math.round(100*rd.nopb_ok/rd.nopb) : '-';
        const pSR = rd.pb ? Math.round(100*rd.pb_ok/rd.pb) : '-';
        const nInc = rd.nopb_inc || 0;
        const pInc = rd.pb_inc || 0;
        const nAvg = rd.nopb ? (rd.nopb_dur/rd.nopb/1000).toFixed(1) : '-';
        const pAvg = rd.pb ? (rd.pb_dur/rd.pb/1000).toFixed(1) : '-';
        const nTok = rd.nopb ? Math.round((rd.nopb_ptok+rd.nopb_ctok)/rd.nopb) : '-';
        const pTok = rd.pb ? Math.round((rd.pb_ptok+rd.pb_ctok)/rd.pb) : '-';

        html += `<div class="rate-row">
          <div class="rate-label">${Math.round(parseFloat(rKey)*100)}%</div>
          <div class="agent-cell">
            <div class="agent-top">
              <div class="mini-bar"><div class="mini-fill nopb" style="width:${nPct}%"></div></div>
              <div class="agent-count">${rd.nopb}/${pr}</div>
            </div>
            <div class="agent-detail">
              <span class="col-sr">SR:<span class="sr nopb ${nSR!=='-'&&nSR>=90?'high':''}">${nSR}%</span></span>
              <span class="col-t"><span class="timing">${nAvg}s</span></span>
              <span class="col-tok"><span class="tokens">${nTok}tok</span></span>
              <span class="col-inc"><span class="inc${nInc?'':' zero'}">${nInc}inc</span></span>
            </div>
          </div>
          <div class="agent-cell">
            <div class="agent-top">
              <div class="mini-bar"><div class="mini-fill pb" style="width:${pPct}%"></div></div>
              <div class="agent-count">${rd.pb}/${pr}</div>
            </div>
            <div class="agent-detail">
              <span class="col-sr">SR:<span class="sr pb ${pSR!=='-'&&pSR>=90?'high':''}">${pSR}%</span></span>
              <span class="col-t"><span class="timing">${pAvg}s</span></span>
              <span class="col-tok"><span class="tokens">${pTok}tok</span></span>
              <span class="col-inc"><span class="inc${pInc?'':' zero'}">${pInc}inc</span></span>
            </div>
          </div>
        </div>`;
      });

      if (cell.status !== 'done') {
        html += `<div class="cmd" onclick="copyCmd(this)">${cell.relaunch}</div>`;
      }
      html += `</div></div>`;
    });
  });

  html += '</div>';
  app.innerHTML = html;
}

function toggleCell(id) {
  if (openCells === null) {
    openCells = new Set(DATA.models.flatMap(m => DATA.protocols.map(p => m+'-'+p)));
    openCells.delete(id);
  } else {
    if (openCells.has(id)) openCells.delete(id); else openCells.add(id);
  }
  render();
}

function copyCmd(el) {
  navigator.clipboard.writeText(el.textContent);
  el.classList.add('copied');
  setTimeout(() => el.classList.remove('copied'), 800);
}

function refresh() {
  fetch('/api/data').then(r=>r.json()).then(d => { DATA=d; render(); });
}

function exportReport() {
  window.open('/api/report', '_blank');
}

render();
setInterval(refresh, 10000);
</script>
</body>
</html>"""


def build_report_pdf() -> bytes:
    """Generate a native PDF report using fpdf2."""
    from datetime import datetime
    from fpdf import FPDF

    data = scan_data(**_CFG)
    m = data
    total_done = sum(c["total_rows"] for c in m["matrix"])
    total_planned = m["total_planned"]
    combos_done = sum(1 for c in m["matrix"] if c["status"] == "done")
    combos_total = len(m["matrix"])
    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    # Aggregate totals
    total_dur_ms = total_ptok = total_ctok = 0
    for c in m["matrix"]:
        for rd in c["rates"].values():
            total_dur_ms += (rd.get("nopb_dur", 0) or 0) + (rd.get("pb_dur", 0) or 0)
            total_ptok += (rd.get("nopb_ptok", 0) or 0) + (rd.get("pb_ptok", 0) or 0)
            total_ctok += (rd.get("nopb_ctok", 0) or 0) + (rd.get("pb_ctok", 0) or 0)
    total_dur_min = total_dur_ms / 1000 / 60
    total_tok = total_ptok + total_ctok
    avg_dur_s = total_dur_ms / total_done / 1000 if total_done else 0
    avg_tok = total_tok // total_done if total_done else 0

    def _sr(ok: int, n: int) -> str:
        return f"{100 * ok / n:.1f}%" if n else "-"

    def _delta(nopb_ok: int, nopb_t: int, pb_ok: int, pb_t: int) -> str:
        if nopb_t and pb_t:
            d = 100 * pb_ok / pb_t - 100 * nopb_ok / nopb_t
            return f"+{d:.1f}pp" if d >= 0 else f"{d:.1f}pp"
        return "-"

    # ── Colors ──
    CLR_TITLE = (30, 58, 138)    # dark blue
    CLR_HEADER = (51, 65, 85)    # slate
    CLR_HEADER_BG = (226, 232, 240)
    CLR_NOPB = (220, 38, 38)     # red
    CLR_PB = (22, 163, 74)       # green
    CLR_DELTA = (37, 99, 235)    # blue
    CLR_GRAY = (100, 116, 139)
    CLR_ROW_ALT = (248, 250, 252)
    CLR_BLACK = (0, 0, 0)
    CLR_WHITE = (255, 255, 255)

    pdf = FPDF(orientation="P", unit="mm", format="A4")
    pdf.set_auto_page_break(auto=True, margin=18)
    pdf.add_page()

    # ── Title ──
    pdf.set_font("Helvetica", "B", 16)
    pdf.set_text_color(*CLR_TITLE)
    pdf.cell(0, 10, "Chaos Playbook Engine - Experiment Report", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(*CLR_GRAY)
    pdf.cell(0, 5, f"Generated {now}  |  GLM 4.5  |  3 protocols  |  10 failure rates  |  500/rate  |  think + no-think", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(3)

    # ── Summary cards ──
    cards = [
        (f"{total_done:,} / {total_planned:,}", "Experiments"),
        (f"{combos_done} / {combos_total}", "Combos complete"),
        (f"{total_dur_min:,.0f} min", "Total time"),
        (f"{avg_dur_s:.1f}s", "Avg / experiment"),
        (f"{total_tok:,}", "Total tokens"),
        (f"{avg_tok:,}", "Avg tok / exp"),
    ]
    card_w = (210 - 20 - 5 * 3) / 3  # A4P width, 3 cards per row
    y0 = pdf.get_y()
    cols_per_row = 3
    for i, (val, label) in enumerate(cards):
        row_i = i // cols_per_row
        col_i = i % cols_per_row
        x = 10 + col_i * (card_w + 5)
        y = y0 + row_i * 16
        pdf.set_fill_color(241, 245, 249)
        pdf.rect(x, y, card_w, 14, style="F")
        pdf.set_draw_color(203, 213, 225)
        pdf.rect(x, y, card_w, 14, style="D")
        pdf.set_xy(x, y + 1)
        pdf.set_font("Helvetica", "B", 10)
        pdf.set_text_color(*CLR_BLACK)
        pdf.cell(card_w, 6, val, align="C")
        pdf.set_xy(x, y + 7)
        pdf.set_font("Helvetica", "", 7)
        pdf.set_text_color(*CLR_GRAY)
        pdf.cell(card_w, 5, label, align="C")
    total_rows = (len(cards) + cols_per_row - 1) // cols_per_row
    pdf.set_y(y0 + total_rows * 16 + 4)

    # ── Helper: draw a table ──
    def draw_table(title: str, headers: list[str], widths: list[float],
                   rows: list[list[str]], colors: list[tuple | None] | None = None):
        """Draw a table. colors[col] = RGB tuple or None for black."""
        # Scale widths to fill page width (210 - 2*10 margins = 190mm)
        usable_w = 190
        raw_total = sum(widths)
        scale = usable_w / raw_total
        widths = [w * scale for w in widths]

        # Check page break
        needed = 8 + 6 + len(rows) * 5.5 + 4
        if pdf.get_y() + needed > 275:
            pdf.add_page()

        pdf.set_font("Helvetica", "B", 10)
        pdf.set_text_color(*CLR_TITLE)
        pdf.cell(0, 8, title, new_x="LMARGIN", new_y="NEXT")
        # Header
        pdf.set_font("Helvetica", "B", 7.5)
        pdf.set_fill_color(*CLR_HEADER_BG)
        pdf.set_text_color(*CLR_HEADER)
        for j, (h, w) in enumerate(zip(headers, widths)):
            last = j == len(headers) - 1
            pdf.cell(w, 6, h, border="B", fill=True, align="C",
                     new_x="LMARGIN" if last else "RIGHT",
                     new_y="NEXT" if last else "TOP")
        # Rows
        pdf.set_font("Helvetica", "", 7.5)
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
                pdf.cell(w, 5.5, cell, fill=True, align=align,
                         new_x="LMARGIN" if last else "RIGHT",
                         new_y="NEXT" if last else "TOP")
        pdf.ln(4)

    # ── Table 1: By Protocol ──
    proto_data = []
    for proto in m["protocols"]:
        cells = [c for c in m["matrix"] if c["protocol"] == proto]
        done = sum(c["total_rows"] for c in cells)
        nt = no = pt = po = pd_ = pk = 0
        for c in cells:
            for rd in c["rates"].values():
                nt += rd["nopb"]; no += rd["nopb_ok"]
                pt += rd["pb"]; po += rd["pb_ok"]
                pd_ += (rd.get("nopb_dur", 0) or 0) + (rd.get("pb_dur", 0) or 0)
                pk += (rd.get("nopb_ptok", 0) or 0) + (rd.get("pb_ptok", 0) or 0) + \
                      (rd.get("nopb_ctok", 0) or 0) + (rd.get("pb_ctok", 0) or 0)
        avg_s = f"{pd_ / done / 1000:.1f}s" if done else "-"
        avg_t = f"{pk // done:,}" if done else "-"
        proto_data.append([proto.upper(), f"{done:,}", _sr(no, nt), _sr(po, pt),
                           _delta(no, nt, po, pt), avg_s, avg_t])
    draw_table("By Protocol",
               ["Protocol", "Experiments", "nopb SR", "pb SR", "Delta", "Avg time", "Avg tok"],
               [22, 28, 22, 22, 22, 22, 22],
               proto_data,
               [None, None, CLR_NOPB, CLR_PB, CLR_DELTA, CLR_GRAY, CLR_GRAY])

    # ── Table 2: Thinking vs No-Thinking ──
    think_data = []
    for label, filt in [("think", lambda c: "nothink" not in c["model"]),
                        ("no-think", lambda c: "nothink" in c["model"])]:
        cells = [c for c in m["matrix"] if filt(c)]
        done = sum(c["total_rows"] for c in cells)
        nt = no = pt = po = td_ = tk = 0
        for c in cells:
            for rd in c["rates"].values():
                nt += rd["nopb"]; no += rd["nopb_ok"]
                pt += rd["pb"]; po += rd["pb_ok"]
                td_ += (rd.get("nopb_dur", 0) or 0) + (rd.get("pb_dur", 0) or 0)
                tk += (rd.get("nopb_ptok", 0) or 0) + (rd.get("pb_ptok", 0) or 0) + \
                      (rd.get("nopb_ctok", 0) or 0) + (rd.get("pb_ctok", 0) or 0)
        avg_s = f"{td_ / done / 1000:.1f}s" if done else "-"
        avg_t = f"{tk // done:,}" if done else "-"
        think_data.append([label, f"{done:,}", _sr(no, nt), _sr(po, pt),
                           _delta(no, nt, po, pt), avg_s, avg_t])
    draw_table("Think vs No-think",
               ["Mode", "Experiments", "nopb SR", "pb SR", "Delta", "Avg time", "Avg tok"],
               [28, 28, 22, 22, 22, 22, 22],
               think_data,
               [None, None, CLR_NOPB, CLR_PB, CLR_DELTA, CLR_GRAY, CLR_GRAY])

    # ── Table 3: By Failure Rate ──
    rate_data = []
    for rate in m["rates"]:
        rkey = f"{rate:.4g}" if rate != 0 else "0"
        nt = no = pt = po = rd_ = rk_ = 0
        for c in m["matrix"]:
            rd = c["rates"].get(rkey, {})
            nt += rd.get("nopb", 0); no += rd.get("nopb_ok", 0)
            pt += rd.get("pb", 0); po += rd.get("pb_ok", 0)
            rd_ += (rd.get("nopb_dur", 0) or 0) + (rd.get("pb_dur", 0) or 0)
            rk_ += (rd.get("nopb_ptok", 0) or 0) + (rd.get("pb_ptok", 0) or 0) + \
                   (rd.get("nopb_ctok", 0) or 0) + (rd.get("pb_ctok", 0) or 0)
        done = nt + pt
        avg_s = f"{rd_ / done / 1000:.1f}s" if done else "-"
        avg_t = f"{rk_ // done:,}" if done else "-"
        rate_data.append([f"{round(rate * 100)}%", f"{done:,}", _sr(no, nt), _sr(po, pt),
                          _delta(no, nt, po, pt), avg_s, avg_t])
    draw_table("By Failure Rate",
               ["Rate", "Experiments", "nopb SR", "pb SR", "Delta (pb-nopb)", "Avg time", "Avg tok"],
               [18, 28, 22, 22, 30, 22, 22],
               rate_data,
               [None, None, CLR_NOPB, CLR_PB, CLR_DELTA, CLR_GRAY, CLR_GRAY])

    # ── Table 4: Per-Combo Detail ──
    combo_data = []
    for c in m["matrix"]:
        nt = no = pt = po = cd = ck = ci = 0
        for rd in c["rates"].values():
            nt += rd["nopb"]; no += rd["nopb_ok"]
            pt += rd["pb"]; po += rd["pb_ok"]
            cd += (rd.get("nopb_dur", 0) or 0) + (rd.get("pb_dur", 0) or 0)
            ck += (rd.get("nopb_ptok", 0) or 0) + (rd.get("pb_ptok", 0) or 0) + \
                  (rd.get("nopb_ctok", 0) or 0) + (rd.get("pb_ctok", 0) or 0)
            ci += (rd.get("nopb_inc", 0) or 0) + (rd.get("pb_inc", 0) or 0)
        avg_s = f"{cd / c['total_rows'] / 1000:.1f}s" if c["total_rows"] else "-"
        avg_t = f"{ck // c['total_rows']:,}" if c["total_rows"] else "-"
        pct = min(100, round(100 * c["total_rows"] / c["expected"])) if c["expected"] else 0
        combo_data.append([c["model"], c["protocol"].upper(),
                           f"{c['total_rows']}/{c['expected']} ({pct}%)",
                           _sr(no, nt), _sr(po, pt), _delta(no, nt, po, pt),
                           avg_s, avg_t, str(ci)])
    draw_table("Per-Combo Detail",
               ["Model", "Protocol", "Progress", "nopb SR", "pb SR", "Delta", "Avg time", "Avg tok", "Inc"],
               [24, 16, 28, 20, 20, 22, 20, 22, 14],
               combo_data,
               [None, None, None, CLR_NOPB, CLR_PB, CLR_DELTA, CLR_GRAY, CLR_GRAY, (180, 130, 0)])

    # ── Table 5: Per-Combo x Rate (full detail matrix) ──
    for c in m["matrix"]:
        label = f"{c['model']} / {c['protocol'].upper()}"
        detail_rows = []
        all_rate_keys = [f"{r:.4g}" if r != 0 else "0" for r in m["rates"]]
        for rkey in all_rate_keys:
            rd = c["rates"].get(rkey, {})
            n_n = rd.get("nopb", 0); n_ok = rd.get("nopb_ok", 0)
            p_n = rd.get("pb", 0); p_ok = rd.get("pb_ok", 0)
            n_avg = f"{rd.get('nopb_dur', 0) / n_n / 1000:.1f}s" if n_n else "-"
            p_avg = f"{rd.get('pb_dur', 0) / p_n / 1000:.1f}s" if p_n else "-"
            n_tok = f"{(rd.get('nopb_ptok', 0) + rd.get('nopb_ctok', 0)) // n_n:,}" if n_n else "-"
            p_tok = f"{(rd.get('pb_ptok', 0) + rd.get('pb_ctok', 0)) // p_n:,}" if p_n else "-"
            n_inc = str(rd.get("nopb_inc", 0))
            p_inc = str(rd.get("pb_inc", 0))
            detail_rows.append([
                f"{round(float(rkey) * 100)}%",
                f"{n_n}", _sr(n_ok, n_n), n_avg, n_tok, n_inc,
                f"{p_n}", _sr(p_ok, p_n), p_avg, p_tok, p_inc,
            ])
        draw_table(label,
                   ["Rate", "nopb N", "nopb SR", "nopb t", "nopb tok", "nopb inc",
                    "pb N", "pb SR", "pb t", "pb tok", "pb inc"],
                   [14, 14, 16, 14, 18, 14, 14, 16, 14, 18, 14],
                   detail_rows,
                   [None, None, CLR_NOPB, CLR_GRAY, CLR_GRAY, (180, 130, 0),
                    None, CLR_PB, CLR_GRAY, CLR_GRAY, (180, 130, 0)])

    # Disable auto page break before footer to prevent trailing blank page
    pdf.set_auto_page_break(auto=False)

    # ── Footer on every page ──
    page_count = pdf.page_no()
    pdf.set_font("Helvetica", "I", 7)
    pdf.set_text_color(*CLR_GRAY)
    footer_text = f"Chaos Playbook Engine  |  Chaos Playbook Lab  |  SR = Success Rate  |  nopb = No Playbook  |  pb = Playbook  |  {now}"
    for i in range(1, page_count + 1):
        pdf.page = i
        pdf.set_y(-12)
        pdf.cell(0, 5, f"{footer_text}  |  Page {i}/{page_count}", align="C")

    return pdf.output()


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/api/data":
            data = scan_data(**_CFG)
            body = json.dumps(data).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif self.path == "/api/report":
            from generate_comparison_report import build_report_bytes
            body = build_report_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "application/pdf")
            self.send_header("Content-Disposition",
                             "inline; filename=comparison-report.pdf")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            body = build_html().encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    def log_message(self, format, *args):
        pass


def main():
    parser = argparse.ArgumentParser(description="Experiment dashboard")
    parser.add_argument("--port", type=int, default=8050)
    parser.add_argument("--no-open", action="store_true")
    parser.add_argument("--models", nargs="+",
                        default=["glm-4.5", "glm-4.5-nothink"],
                        help="Models to track")
    parser.add_argument("--protocols", nargs="+",
                        default=["http", "mcp", "a2a"],
                        help="Protocols to track")
    parser.add_argument("--rates", nargs="+", type=float,
                        default=[0.0, 0.01, 0.02, 0.03, 0.05, 0.10, 0.15, 0.20, 0.25, 0.30],
                        help="Failure rates")
    parser.add_argument("--per-rate", type=int, default=500,
                        help="Experiments per rate per agent")
    args = parser.parse_args()

    global _CFG
    _CFG = {
        "models": args.models,
        "protocols": args.protocols,
        "rates": args.rates,
        "per_rate": args.per_rate,
    }

    server = HTTPServer(("127.0.0.1", args.port), Handler)
    url = f"http://localhost:{args.port}"
    print(f"Dashboard: {url}")
    print(f"Config: {len(args.models)} models x {len(args.protocols)} protocols "
          f"x {len(args.rates)} rates x {args.per_rate}/rate "
          f"= {len(args.models)*len(args.protocols)*len(args.rates)*args.per_rate*2} experiments")
    if not args.no_open:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")


if __name__ == "__main__":
    main()
