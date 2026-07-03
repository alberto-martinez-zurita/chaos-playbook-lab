"""Comprehensive audit: verify every specific numeric claim in the paper."""
import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import json, csv
from pathlib import Path
from statistics import mean, median
ROOT = Path("experiments")

def find_arms(d):
    keys = [k for k in d if k not in ("failure_rate","n_experiments")]
    n = next((k for k in keys if k.endswith("-nopb")), None)
    p = next((k for k in keys if k.endswith("-pb")), None)
    return n, p

def sr(jpath, rate, atype):
    d = json.load(open(jpath))
    r = d.get(str(rate), {})
    n, p = find_arms(r)
    k = n if atype == "nopb" else p
    if not k: return None
    return r.get(k, {}).get("success_rate", {}).get("mean", None)

JSONS = {
    "qwen35_0_8b": ROOT/"qwen35_0_8b"/"qwen35-0_8b"/"http"/"aggregated_metrics.json",
    "qwen35_2b": ROOT/"qwen35_2b"/"qwen35-2b"/"http"/"aggregated_metrics.json",
    "gemma4_e2b": ROOT/"gemma4_e2b"/"gemma4-e2b"/"http"/"aggregated_metrics.json",
    "gemma4_e4b": ROOT/"gemma4_e4b"/"gemma4-e4b"/"http"/"aggregated_metrics.json",
    "qwen35_4b": ROOT/"qwen35_4b"/"qwen35-4b"/"http"/"aggregated_metrics.json",
    "nemotron_nano_4b": ROOT/"nemotron_nano_4b"/"nemotron-nano-4b"/"http_think"/"aggregated_metrics.json",
    "qwen35_9b": ROOT/"qwen35_9b"/"qwen35-9b"/"http"/"aggregated_metrics.json",
    "qwen35_9b_distilled": ROOT/"qwen35_9b_distilled"/"qwen35-9b-distilled"/"http"/"aggregated_metrics.json",
    "ministral_14b_http": ROOT/"ministral_14b"/"ministral-14b"/"http_think"/"aggregated_metrics.json",
    "ministral_14b_a2a": ROOT/"ministral_14b"/"ministral-14b"/"a2a_think"/"aggregated_metrics.json",
    "ministral_14b_mcp": ROOT/"ministral_14b"/"ministral-14b"/"mcp_think"/"aggregated_metrics.json",
    "gemma4_26b_http": ROOT/"gemma4_26b"/"gemma426ba4b"/"http"/"aggregated_metrics.json",
    "gemma4_26b_a2a": ROOT/"gemma4_26b"/"gemma426ba4b"/"a2a"/"aggregated_metrics.json",
    "gemma4_26b_mcp": ROOT/"gemma4_26b"/"gemma426ba4b"/"mcp"/"aggregated_metrics.json",
    "glm45_http_think": ROOT/"glm45"/"glm45"/"http_think"/"aggregated_metrics.json",
    "glm45_http_nothink": ROOT/"glm45"/"glm45"/"http_nothink"/"aggregated_metrics.json",
    "glm45_mcp_think": ROOT/"glm45"/"glm45"/"mcp_think"/"aggregated_metrics.json",
    "glm45_mcp_nothink": ROOT/"glm45"/"glm45"/"mcp_nothink"/"aggregated_metrics.json",
    "glm45_a2a_think": ROOT/"glm45"/"glm45"/"a2a_think"/"aggregated_metrics.json",
    "glm45_a2a_nothink": ROOT/"glm45"/"glm45"/"a2a_nothink"/"aggregated_metrics.json",
}

# ============================================================
# CLAIM §5.3: qwen 2B "stable around +56 pp at chaos = 10 %"
# ============================================================
print("=== CLAIM §5.3: qwen35_2b 'stable around +56 pp at chaos=10%, drops to +13 at 30%' ===")
for r in ["0.0","0.01","0.02","0.03","0.05","0.1","0.15","0.2","0.25","0.3"]:
    nn = sr(JSONS["qwen35_2b"], r, "nopb")*100
    pp = sr(JSONS["qwen35_2b"], r, "pb")*100
    print(f"  qwen35_2b @{r:5s}: nopb={nn:5.1f} pb={pp:5.1f} d={pp-nn:+6.1f}")
print()

# CLAIM §5.5(iii)
print("=== CLAIM §5.5(iii): 'Most cells are N=100' ===")
print("  STALE — all local cells now N=200, GLM N=500")
print()

# CLAIM §4.1 pb cluster
print("=== CLAIM §4.1 prose: 'pb arm clusters between 90% and 99%' for upper roster @chaos=0.20 ===")
upper = ["qwen35_9b","qwen35_9b_distilled","ministral_14b_http","gemma4_26b_http","glm45_http_think"]
for m in upper:
    p20 = sr(JSONS[m], "0.2", "pb")*100
    flag = " ← OUT of 90-99 range" if p20 < 90 or p20 > 99 else ""
    print(f"  {m:25s} pb@20% = {p20:5.1f}{flag}")
print()

# CLAIM: no model harmed at any rate
print("=== CLAIM §4.1, §5.6: 'no model harmed at any rate' ===")
violations = []
for m, j in JSONS.items():
    d = json.load(open(j))
    for rate_key in d:
        r = d[rate_key]
        if not isinstance(r, dict): continue
        n, p = find_arms(r)
        if not (n and p): continue
        srn = r.get(n, {}).get("success_rate", {}).get("mean")
        srp = r.get(p, {}).get("success_rate", {}).get("mean")
        if srn is None or srp is None: continue
        delta = (srp - srn) * 100
        if delta < -0.001:
            violations.append((m, rate_key, srn*100, srp*100, delta))
if violations:
    print("  VIOLATIONS:")
    for v in violations:
        print(f"    {v[0]:25s} @{v[1]:5s} nopb={v[2]:5.1f} pb={v[3]:5.1f} d={v[4]:+5.2f}")
else:
    print("  OK no negative Δ anywhere")
print()

# CLAIM §4.2(a)
print("=== CLAIM §4.2(a): GLM Δ@10 (+13.8) 'smaller than every model in the 9B-26B band' ===")
glm_d10 = (sr(JSONS["glm45_http_think"],"0.1","pb")-sr(JSONS["glm45_http_think"],"0.1","nopb"))*100
print(f"  glm45 Δ@10 = {glm_d10:+5.1f}")
band = ["qwen35_9b","qwen35_9b_distilled","ministral_14b_http","gemma4_26b_http"]
for m in band:
    d = (sr(JSONS[m],"0.1","pb")-sr(JSONS[m],"0.1","nopb"))*100
    flag = "  ← VIOLATION" if d <= glm_d10 else ""
    print(f"  {m:25s} Δ@10 = {d:+5.1f}{flag}")
print()

# CLAIM §5.2: -18.6 pp MCP and -15.6 pp A2A (think hurts nopb)
print("=== CLAIM §5.2: '-18.6 pp on MCP, -15.6 pp on A2A' for nopb (think - nothink) @30% ===")
for proto in ["mcp","a2a"]:
    nt = sr(JSONS[f"glm45_{proto}_think"],"0.3","nopb")*100
    nn = sr(JSONS[f"glm45_{proto}_nothink"],"0.3","nopb")*100
    pt = sr(JSONS[f"glm45_{proto}_think"],"0.3","pb")*100
    pn = sr(JSONS[f"glm45_{proto}_nothink"],"0.3","pb")*100
    d_nopb = nt - nn
    d_pb = pt - pn
    print(f"  {proto:6s} nopb think-nothink = {d_nopb:+5.1f}  pb think-nothink = {d_pb:+5.1f}")
print("  Claim hold mcp: -18.6, a2a: -15.6 — see numbers above")
print()

# CLAIM §4.7: mean ~42%, range 13%-69%
print("=== CLAIM §4.7: tokens overhead range 13%-69%, mean ~42% ===")
cells = [
    ("qwen35_4b", ROOT/"qwen35_4b"/"qwen35-4b"/"http"/"rate_0.10.csv"),
    ("gemma4_e4b", ROOT/"gemma4_e4b"/"gemma4-e4b"/"http"/"rate_0.10.csv"),
    ("nemotron_nano_4b", ROOT/"nemotron_nano_4b"/"nemotron-nano-4b"/"http_think"/"rate_0.10.csv"),
    ("qwen35_9b", ROOT/"qwen35_9b"/"qwen35-9b"/"http"/"rate_0.10.csv"),
    ("ministral_14b", ROOT/"ministral_14b"/"ministral-14b"/"http_think"/"rate_0.10.csv"),
    ("gemma4_26b", ROOT/"gemma4_26b"/"gemma426ba4b"/"http"/"rate_0.10.csv"),
    ("glm45_nothink", ROOT/"glm45"/"glm45"/"http_nothink"/"rate_0.10.csv"),
]
overheads, calls_delta = [], []
for name, p in cells:
    by_arm = {"nopb": {"tokens": [], "calls": []}, "pb": {"tokens": [], "calls": []}}
    with open(p, newline="") as f:
        for row in csv.DictReader(f):
            at = "pb" if row["agent_type"].endswith("-pb") else "nopb" if row["agent_type"].endswith("-nopb") else None
            if at is None: continue
            t = float(row.get("prompt_tokens",0) or 0) + float(row.get("completion_tokens",0) or 0)
            c = float(row.get("llm_calls",0) or 0)
            by_arm[at]["tokens"].append(t)
            by_arm[at]["calls"].append(c)
    tn = mean(by_arm["nopb"]["tokens"]); tp = mean(by_arm["pb"]["tokens"])
    cn = mean(by_arm["nopb"]["calls"]); cp = mean(by_arm["pb"]["calls"])
    ov = (tp-tn)/tn*100
    overheads.append(ov); calls_delta.append(cp-cn)
    print(f"  {name:25s} nopb_tokens={tn:6.0f} pb_tokens={tp:6.0f} overhead={ov:+5.1f}% d_calls={cp-cn:+.2f}")
print(f"  Mean overhead = {mean(overheads):+.1f}%  (claim ~42%)")
print(f"  Range = {min(overheads):+.1f}% .. {max(overheads):+.1f}% (claim 13-69)")
print(f"  Mean d_calls = +{mean(calls_delta):.2f} (claim ~+1)")
print()

# CLAIM §6.1: median Δ
print("=== CLAIM §6.1, §4.8: median Δ functioning roster = +24 @ 10%, +43.5 @ 30% ===")
funcset = ["gemma4_e2b","gemma4_e4b","qwen35_4b","nemotron_nano_4b","qwen35_9b",
           "qwen35_9b_distilled","ministral_14b_http","gemma4_26b_http","glm45_http_think"]
d10s, d30s = [], []
for m in funcset:
    d10 = (sr(JSONS[m],"0.1","pb")-sr(JSONS[m],"0.1","nopb"))*100
    d30 = (sr(JSONS[m],"0.3","pb")-sr(JSONS[m],"0.3","nopb"))*100
    d10s.append(d10); d30s.append(d30)
print(f"  Δ@10 median = {median(d10s):+.2f}")
print(f"  Δ@30 median = {median(d30s):+.2f}")
print()

# CLAIM §5.2 iso-4B: within ~10 pp nopb, ~5 pp pb
print("=== CLAIM §5.2: 3 archs within ~10pp nopb, ~5pp pb at every rate ===")
iso = ["qwen35_4b","gemma4_e4b","nemotron_nano_4b"]
print("  rate    nopb_spread  pb_spread")
violators = []
for r in ["0.0","0.05","0.1","0.15","0.2","0.25","0.3"]:
    nopbs = [sr(JSONS[m],r,"nopb")*100 for m in iso]
    pbs   = [sr(JSONS[m],r,"pb")*100 for m in iso]
    spr_n = max(nopbs) - min(nopbs)
    spr_p = max(pbs) - min(pbs)
    flag = ""
    if spr_n > 10.5: flag += " NOPB>10!"
    if spr_p > 5.5: flag += " PB>5!"
    print(f"  {r:6s}  {spr_n:5.1f}        {spr_p:5.1f}{flag}")
print()

# CLAIM §4.3 panel C: distilled uniformly above original on nopb
print("=== CLAIM §4.3 panel C: distilled uniformly above original on nopb at every rate ===")
v_count = 0
for r in ["0.0","0.01","0.02","0.03","0.05","0.1","0.15","0.2","0.25","0.3"]:
    v = sr(JSONS["qwen35_9b"], r, "nopb")
    dst = sr(JSONS["qwen35_9b_distilled"], r, "nopb")
    if v is None or dst is None: continue
    diff = (dst - v) * 100
    flag = " ← VIOLATION" if diff < 0 else ""
    if diff < 0: v_count += 1
    print(f"  rate={r:5s}  vanilla={v*100:5.1f}  distilled={dst*100:5.1f}  d={diff:+5.1f}{flag}")
print(f"  Violations: {v_count}")
print()

# CLAIM §4.3 panel C: distilled on pb "saturates 100% up to chaos=10% and 1-7pp above original at every higher rate"
print("=== CLAIM §4.3 panel C pb arm distilled 'saturates 100% up to chaos=10%, 1-7pp above at every higher' ===")
for r in ["0.0","0.01","0.02","0.03","0.05","0.1","0.15","0.2","0.25","0.3"]:
    v = sr(JSONS["qwen35_9b"], r, "pb")
    dst = sr(JSONS["qwen35_9b_distilled"], r, "pb")
    if v is None or dst is None: continue
    diff = (dst - v) * 100
    print(f"  rate={r:5s}  vanilla_pb={v*100:5.1f}  distilled_pb={dst*100:5.1f}  d={diff:+5.1f}")
print()

# Spot-check §4.1 row vs claims
print("=== Spot-check §4.1 table @ chaos=0.20 ===")
ALL_4_1 = ["qwen35_0_8b","qwen35_2b","gemma4_e2b","gemma4_e4b","qwen35_4b",
           "nemotron_nano_4b","qwen35_9b","qwen35_9b_distilled","ministral_14b_http",
           "gemma4_26b_http","glm45_http_think"]
for m in ALL_4_1:
    n = sr(JSONS[m],"0.2","nopb")*100
    p = sr(JSONS[m],"0.2","pb")*100
    print(f"  {m:25s} nopb={n:5.1f} pb={p:5.1f} d={p-n:+5.1f}")
print()

# CLAIM §4.4: "GLM 4.5 (nopb SR at chaos = 10% is 85.8%, pb SR is 99.6%)"
print("=== CLAIM §4.4: GLM 4.5 think nopb@10=85.8 pb@10=99.6, +13.8 ===")
n = sr(JSONS["glm45_http_think"],"0.1","nopb")*100
p = sr(JSONS["glm45_http_think"],"0.1","pb")*100
print(f"  nopb@10 = {n:.1f}, pb@10 = {p:.1f}, delta = {p-n:+.1f}")
print()

# CLAIM §4.5: Ministral A2A 87.5 vs HTTP 27.5 = +60pp gap; Gemma 26B A2A 86.5 vs HTTP 38.5 = +48pp
print("=== CLAIM §4.5: cross-protocol gaps @30% nopb ===")
mh = sr(JSONS["ministral_14b_http"],"0.3","nopb")*100
ma = sr(JSONS["ministral_14b_a2a"],"0.3","nopb")*100
mm = sr(JSONS["ministral_14b_mcp"],"0.3","nopb")*100
gh = sr(JSONS["gemma4_26b_http"],"0.3","nopb")*100
ga = sr(JSONS["gemma4_26b_a2a"],"0.3","nopb")*100
gm = sr(JSONS["gemma4_26b_mcp"],"0.3","nopb")*100
print(f"  Ministral A2A={ma:.1f} HTTP={mh:.1f} MCP={mm:.1f}  gap A2A-HTTP={ma-mh:+.1f}pp")
print(f"  Gemma26B  A2A={ga:.1f} HTTP={gh:.1f} MCP={gm:.1f}  gap A2A-HTTP={ga-gh:+.1f}pp")
print()

# CLAIM §4.6 distillation table - 5 rates
print("=== CLAIM §4.6 distillation table (5 rates: 0%, 5%, 10%, 20%, 30%) ===")
for r in ["0.0","0.05","0.1","0.2","0.3"]:
    v = sr(JSONS["qwen35_9b"], r, "nopb")*100
    dst = sr(JSONS["qwen35_9b_distilled"], r, "nopb")*100
    print(f"  rate={r:5s}  V={v:.1f}  D={dst:.1f}  d={dst-v:+.1f}")
print()
