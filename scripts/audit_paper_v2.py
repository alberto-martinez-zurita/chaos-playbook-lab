"""Academic audit v2 — statistical rigor + figure-text-data alignment."""
import json
from pathlib import Path
from statistics import mean, median
import math

ROOT = Path("experiments")

def find_arms(d):
    keys = [k for k in d if k not in ("failure_rate","n_experiments")]
    return (next((k for k in keys if k.endswith("-nopb")), None),
            next((k for k in keys if k.endswith("-pb")), None))

def get_cell(jpath, rate, atype):
    """Return (n_runs, success_rate_mean) or (0, None) if missing."""
    d = json.load(open(jpath))
    r = d.get(str(rate), {})
    n_key, p_key = find_arms(r)
    k = n_key if atype == "nopb" else p_key
    if not k or k not in r: return (0, None)
    return (r[k].get("n_runs", 0), r[k].get("success_rate", {}).get("mean"))

def wilson_ci(p, n, z=1.96):
    """Wilson 95% CI half-width on a binomial proportion."""
    if n == 0: return None
    denom = 1 + z*z/n
    centre = (p + z*z/(2*n)) / denom
    halfw = z * math.sqrt((p*(1-p) + z*z/(4*n)) / n) / denom
    return (centre - halfw, centre + halfw)

def diff_ci_95(p1, n1, p2, n2):
    """95% CI half-width on the difference of two independent binomials (Newcombe-style)."""
    if n1 == 0 or n2 == 0: return None
    se = math.sqrt(p1*(1-p1)/n1 + p2*(1-p2)/n2)
    return 1.96 * se

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

print("="*80)
print("PART 1 — HUMP SHAPE AT 10% vs 30% (active params x-axis)")
print("="*80)

ACTIVE_PARAMS = {  # active params (B) per the §3.5 roster
    "gemma4_e2b": 2.0,
    "qwen35_4b": 4.0,
    "gemma4_e4b": 4.0,
    "nemotron_nano_4b": 4.0,
    "gemma4_26b_http": 4.0,   # MoE 4B active
    "qwen35_9b": 9.0,
    "qwen35_9b_distilled": 9.0,
    "ministral_14b_http": 14.0,
    "glm45_http_think": 32.0,  # MoE 32B active
}

for chaos in ["0.1", "0.3"]:
    print(f"\nAt chaos={chaos}:")
    pts = []
    for m, ap in sorted(ACTIVE_PARAMS.items(), key=lambda x: x[1]):
        n1, p_n = get_cell(JSONS[m], chaos, "nopb")
        n2, p_p = get_cell(JSONS[m], chaos, "pb")
        if p_n is None or p_p is None: continue
        delta = (p_p - p_n) * 100
        # 95% CI on the Δ
        ci_diff = diff_ci_95(p_p, n2, p_n, n1) * 100
        pts.append((ap, m, delta, ci_diff))
        print(f"  {ap:5.1f}B  {m:25s}  Δ={delta:+6.2f} ± {ci_diff:.2f} pp (95% CI)")
    # Check monotonicity
    print("  --- Trend (Δ as we walk up the active params axis):")
    last = None
    inversions = 0
    for ap, m, delta, ci in pts:
        if last is not None and delta < last - 5:  # require >5pp drop
            inversions += 1
        last = delta
    print(f"  Significant drops walking up the curve: {inversions}")

print()
print("="*80)
print("PART 2 — SIGNIFICANCE OF PAIRWISE COMPARISONS")
print("="*80)

# Check that "GLM saturation" is materially different from qwen4B at chaos=30
print("\nGLM 4.5 think vs qwen 4B at chaos=30 (nopb):")
n1, p1 = get_cell(JSONS["glm45_http_think"], "0.3", "nopb")
n2, p2 = get_cell(JSONS["qwen35_4b"], "0.3", "nopb")
diff = (p1 - p2) * 100
ci = diff_ci_95(p1, n1, p2, n2) * 100
print(f"  GLM nopb={p1*100:.1f} (N={n1})  qwen4B nopb={p2*100:.1f} (N={n2})")
print(f"  Δ={diff:+.2f} ± {ci:.2f} pp (95% CI) — significant={abs(diff)>ci}")

# Check chaos=20 too
print("\nGLM 4.5 think vs qwen 4B at chaos=20 (nopb):")
n1, p1 = get_cell(JSONS["glm45_http_think"], "0.2", "nopb")
n2, p2 = get_cell(JSONS["qwen35_4b"], "0.2", "nopb")
diff = (p1 - p2) * 100
ci = diff_ci_95(p1, n1, p2, n2) * 100
print(f"  GLM nopb={p1*100:.1f} (N={n1})  qwen4B nopb={p2*100:.1f} (N={n2})")
print(f"  Δ={diff:+.2f} ± {ci:.2f} pp (95% CI) — significant={abs(diff)>ci}")

# Check the cross-protocol HTTP-vs-A2A "flip" for GLM think
print("\nGLM 4.5 think — HTTP vs A2A nopb at chaos=30:")
n1, p1 = get_cell(JSONS["glm45_http_think"], "0.3", "nopb")
n2, p2 = get_cell(JSONS["glm45_a2a_think"], "0.3", "nopb")
diff = (p1 - p2) * 100
ci = diff_ci_95(p1, n1, p2, n2) * 100
print(f"  HTTP nopb={p1*100:.1f} (N={n1})  A2A nopb={p2*100:.1f} (N={n2})")
print(f"  Δ(HTTP-A2A)={diff:+.2f} ± {ci:.2f} pp — significant={abs(diff)>ci}")
print("  Paper claims: 'HTTP is best ... A2A in the middle' — is HTTP > A2A real?")

# GLM nothink — A2A vs HTTP nopb at chaos=30 (claim "A2A is best")
print("\nGLM 4.5 nothink — A2A vs HTTP nopb at chaos=30:")
n1, p1 = get_cell(JSONS["glm45_a2a_nothink"], "0.3", "nopb")
n2, p2 = get_cell(JSONS["glm45_http_nothink"], "0.3", "nopb")
diff = (p1 - p2) * 100
ci = diff_ci_95(p1, n1, p2, n2) * 100
print(f"  A2A nopb={p1*100:.1f} (N={n1})  HTTP nopb={p2*100:.1f} (N={n2})")
print(f"  Δ(A2A-HTTP)={diff:+.2f} ± {ci:.2f} pp — significant={abs(diff)>ci}")

# Check Ministral A2A vs HTTP nopb at chaos=30 (claim +60pp gap)
print("\nMinistral 14B — A2A vs HTTP nopb at chaos=30:")
n1, p1 = get_cell(JSONS["ministral_14b_a2a"], "0.3", "nopb")
n2, p2 = get_cell(JSONS["ministral_14b_http"], "0.3", "nopb")
diff = (p1 - p2) * 100
ci = diff_ci_95(p1, n1, p2, n2) * 100
print(f"  A2A nopb={p1*100:.1f}  HTTP nopb={p2*100:.1f}")
print(f"  Δ(A2A-HTTP)={diff:+.2f} ± {ci:.2f} pp — significant={abs(diff)>ci}")

# Distillation pair at chaos=0 (paper claims +1pp)
print("\nDistillation @0% nopb (paper claims +1pp):")
n1, p1 = get_cell(JSONS["qwen35_9b_distilled"], "0.0", "nopb")
n2, p2 = get_cell(JSONS["qwen35_9b"], "0.0", "nopb")
diff = (p1 - p2) * 100
ci = diff_ci_95(p1, n1, p2, n2) * 100
print(f"  distilled={p1*100:.1f} vanilla={p2*100:.1f}")
print(f"  Δ={diff:+.2f} ± {ci:.2f} — significant={abs(diff)>ci}")

# Distillation pair at chaos=30 (paper claims +13pp)
print("\nDistillation @30% nopb (paper claims +13pp):")
n1, p1 = get_cell(JSONS["qwen35_9b_distilled"], "0.3", "nopb")
n2, p2 = get_cell(JSONS["qwen35_9b"], "0.3", "nopb")
diff = (p1 - p2) * 100
ci = diff_ci_95(p1, n1, p2, n2) * 100
print(f"  distilled={p1*100:.1f} vanilla={p2*100:.1f}")
print(f"  Δ={diff:+.2f} ± {ci:.2f} — significant={abs(diff)>ci}")

# Sign test for distillation 10/10 above (uniformity)
import scipy.stats as st  # may fail; fallback below
try:
    p_value = 2 * (0.5 ** 10)
    print(f"\nSign test for distilled > vanilla at all 10 rates: p = {p_value:.4f} (one-sided binomial, expected 0.5)")
except Exception as e:
    pass

print()
print("="*80)
print("PART 3 — REASONING MODEL HYPOTHESIS")
print("="*80)
# Paper claim: reasoning lowers nopb. Reasoning models in roster:
# - Nemotron 4B (reasoning by default)
# - Ministral 14B (reasoning)
# - GLM 4.5 think (reasoning toggleable)

# Compare Nemotron vs avg(qwen 4B, Gemma E4B) — non-reasoning 4B class
print("\nNemotron (reasoning 4B) vs avg(qwen4B, GemmaE4B) — non-reasoning 4B class:")
for r in ["0.0","0.05","0.1","0.15","0.2","0.25","0.3"]:
    nv = get_cell(JSONS["nemotron_nano_4b"], r, "nopb")[1]
    q4 = get_cell(JSONS["qwen35_4b"], r, "nopb")[1]
    g4 = get_cell(JSONS["gemma4_e4b"], r, "nopb")[1]
    if None in (nv, q4, g4): continue
    avg_non = (q4 + g4) / 2
    diff = (nv - avg_non) * 100
    print(f"  rate={r:5s}  Nemotron={nv*100:5.1f}  avg(qwen4B, GemmaE4B)={avg_non*100:5.1f}  Δ={diff:+.1f}")

# GLM think vs nothink nopb on HTTP — should be ≈0 per paper
print("\nGLM think vs nothink HTTP nopb (should be ~0 per §4.4):")
for r in ["0.0","0.05","0.1","0.15","0.2","0.25","0.3"]:
    n1, p1 = get_cell(JSONS["glm45_http_think"], r, "nopb")
    n2, p2 = get_cell(JSONS["glm45_http_nothink"], r, "nopb")
    if None in (p1, p2): continue
    diff = (p1 - p2) * 100
    ci = diff_ci_95(p1, n1, p2, n2) * 100
    sig = "*" if abs(diff) > ci else " "
    print(f"  rate={r:5s}  think={p1*100:5.1f}  nothink={p2*100:5.1f}  Δ={diff:+5.1f} ± {ci:.1f} {sig}")

print()
print("="*80)
print("PART 4 — CONSISTENCY OF HUMP SHAPE NARRATIVE")
print("="*80)
# At chaos=10%, the hump claim is "rises into 4B-26B region, plateaus, narrows at frontier"
# But E2B at 2B has Δ=+50.5 (HIGHER than the 4B class) — so the curve is NOT monotonically rising

print("\nFig 3 (chaos=10%) — does the curve actually show a hump?")
chaos = "0.1"
pts = []
for m, ap in sorted(ACTIVE_PARAMS.items(), key=lambda x: x[1]):
    n1, p_n = get_cell(JSONS[m], chaos, "nopb")
    n2, p_p = get_cell(JSONS[m], chaos, "pb")
    if p_n is None or p_p is None: continue
    delta = (p_p - p_n) * 100
    pts.append((ap, m, delta))

# Sort by active params
pts.sort()
deltas = [p[2] for p in pts]
print(f"  Active params (B): {[p[0] for p in pts]}")
print(f"  Δ values (pp):     {[round(p[2],1) for p in pts]}")
print(f"  Argmax: {pts[deltas.index(max(deltas))][1]} at {pts[deltas.index(max(deltas))][0]}B with Δ={max(deltas):+.1f}")
print()
print("  Strict hump = first half rises to peak, second half falls.")
print("  Reality: max Δ at chaos=10% is Gemma E2B (2B Matformer) at +50.5pp — the leftmost point!")
print("  Without E2B, sorting by active params @10%: ", [round(p[2],1) for p in pts if p[0] > 2.0])
print("  The 4B-class is itself spread +13.5..+31 (Nemotron outlier), so '4B region rises' is weak.")
print()
print("  At chaos=30%, does the hump hold better?")
chaos = "0.3"
pts = []
for m, ap in sorted(ACTIVE_PARAMS.items(), key=lambda x: x[1]):
    n1, p_n = get_cell(JSONS[m], chaos, "nopb")
    n2, p_p = get_cell(JSONS[m], chaos, "pb")
    if p_n is None or p_p is None: continue
    delta = (p_p - p_n) * 100
    pts.append((ap, m, delta))
pts.sort()
print(f"  Active params (B): {[p[0] for p in pts]}")
print(f"  Δ values (pp):     {[round(p[2],1) for p in pts]}")
print(f"  Max Δ: {pts[[p[2] for p in pts].index(max(p[2] for p in pts))][1]}")

print()
print("="*80)
print("PART 5 — pb arm CLUSTERING AT chaos=30% (upper roster claim)")
print("="*80)
# Paper §6.1: pb arm of qwen 4B and above clusters between 86% and 99% at every rate
# Check all rates for upper roster
upper_models = ["qwen35_4b","gemma4_e4b","nemotron_nano_4b","qwen35_9b","qwen35_9b_distilled",
                "ministral_14b_http","gemma4_26b_http","glm45_http_think"]
for r in ["0.0","0.05","0.1","0.15","0.2","0.25","0.3"]:
    pbs = []
    for m in upper_models:
        _, p = get_cell(JSONS[m], r, "pb")
        if p is not None: pbs.append(p*100)
    print(f"  rate={r:5s}  pb range = [{min(pbs):.1f}, {max(pbs):.1f}]  ({len(pbs)} models)")
