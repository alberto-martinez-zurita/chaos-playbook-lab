# 4 Results

This section reports the empirical findings, illustrated by eight figures (Figs 1–8; files `paper/figures/fig2_*` to `fig9_*`) and computed from the per-cell CSVs (`experiments/<model>/<alias>/<protocol>/rate_<R>.csv`). Every number quoted below can be recomputed from those CSVs with `scripts/check_paper_numbers.py`.

## 4.1 The playbook closes the chaos-induced gap

**Fig 1—Hare and tortoise** (`paper/figures/fig2_hare_tortoise.svg`). Per-model success rates at a single high-chaos operating point (HTTP, chaos = 20 %), plotted against mean run duration (log scale). Hollow markers are `nopb`, filled markers are `pb`, and each arrow is one model's playbook lift; the numbered side legend maps each number to a model, ordered by `pb` success rate (descending).

![Fig 1—Hare and tortoise (HTTP, chaos = 20 %)](figures/fig2_hare_tortoise.png)

| Model | `nopb` SR | `pb` SR | Δ (pp) |
|---|---:|---:|---:|
| qwen3.5 0.8 B | 0.0 | 0.0 | 0.0 |
| qwen3.5 2 B | 4.0 | 31.5 | +27.5 |
| Gemma 4 E2B | 19.0 | 71.5 | +52.5 |
| Gemma 4 E4B | 69.0 | 98.5 | +29.5 |
| qwen3.5 4 B | 71.5 | 97.0 | +25.5 |
| Nemotron Nano 4 B | 43.5 | 90.5 | +47.0 |
| qwen3.5 9 B | 53.0 | 89.5 | +36.5 |
| qwen3.5 9 B (distilled) | 59.5 | 98.0 | +38.5 |
| Ministral 14 B | 41.0 | 98.0 | +57.0 |
| Gemma 4 26 B (MoE) | 55.0 | 97.5 | +42.5 |
| GLM 4.5 (think) | 71.7 | 98.3 | +26.7 |

**Headline**: every active model above the capacity floor benefits from the playbook, and at 20 % chaos the `pb` arm lies between **89 % and 99 %** for the upper-roster models (qwen3.5 9 B and above): the playbook *flattens* the success-rate distribution at the top, regardless of where the model started. No model has a negative Δ at any rate.

The design is paired—run *i* uses the same seed and task instance in both arms—so the effect can be tested on matched pairs. Table 4 counts, for each functioning-roster model, the runs that succeed only with the playbook and only without it, and reports the exact McNemar test with Holm correction over the 81 functioning-roster HTTP cells with *p* > 0. The playbook effect is significant in 68 of the 81 cells; the 13 non-significant cells are all at failure rates of 1 %–3 %, where few calls fail and there is little to recover. At 10 % and 30 % chaos every model is significant (Holm-adjusted *p* < 10⁻⁴), and runs that succeed only *without* the playbook are rare (0–9 of 200; 0–1 of 600 for GLM 4.5).

**Table 4—Paired comparison (HTTP).** Runs that succeed only with the playbook / only without it, out of *N* = 200 pairs (GLM 4.5: 600).

| Model | 10 % chaos | 30 % chaos |
|---|---:|---:|
| Gemma 4 E2B | 107 / 6 | 92 / 9 |
| qwen3.5 4 B | 29 / 2 | 76 / 3 |
| Gemma 4 E4B | 28 / 0 | 82 / 0 |
| Nemotron Nano 4 B | 71 / 9 | 109 / 4 |
| Gemma 4 26 B (MoE) | 54 / 0 | 110 / 0 |
| qwen3.5 9 B | 48 / 0 | 100 / 0 |
| qwen3.5 9 B (distilled) | 36 / 0 | 88 / 1 |
| Ministral 14 B | 68 / 0 | 134 / 0 |
| GLM 4.5 (think) | 87 / 1 | 240 / 0 |


The qwen3.5 0.8 B row is the **capacity floor**: the model cannot complete the task even without chaos, and the playbook cannot rescue it. We discuss this in §5. The qwen3.5 2 B row is a **structural rescue** rather than a chaos rescue (its `nopb` baseline is 0 % at chaos = 0 %); it is shown here for completeness and revisited in §5.

## 4.2 Where the playbook helps most

**Fig 2—Δ vs active parameters at chaos = 10 % and chaos = 30 %** (`paper/figures/fig3_hump.svg`). Two panels on a shared *y*-axis: *x* is model active parameters (log scale, B); *y* is Δ(pb − nopb). Architecture encoded by colour, error bars are 95 % CIs on the difference of two proportions. The left panel shows a moderate chaos rate; the right panel shows the highest rate tested.

![Fig 2—Δ(pb − nopb) vs active parameters at chaos = 10 % and chaos = 30 %](figures/fig3_hump.png)

The relation between Δ and model size **depends on the chaos rate**. At chaos = 30 % the largest gain is at 14 B (Ministral, +67 pp); the ~4 B–9 B models gain +36.5 to +55 pp, the ~2 B PLE model +41.5 pp and the frontier model +40 pp (32 B active). At chaos = 10 % there is no such pattern: the largest gain is the smallest functioning model (Gemma 4 E2B, ~2.3 B effective, +50.5 pp), whose `nopb` baseline is already weak, and the ~4 B models range from +13.5 to +31 pp. A quadratic fit of Δ on log(active parameters) over the functioning roster is concave at 30 % (peak near 10 B) and convex at 10 %, and neither curvature is statistically significant at n = 9 (§5.5 viii). Values at 10 % chaos (the qwen3.5 0.8 B floor and the qwen3.5 2 B structural-rescue case are omitted):

| Active params (B) | Model | Δ at 10 % chaos |
|---|---|---:|
| ~2.3 | Gemma 4 E2B | +50.5 |
| 4 | qwen3.5 4 B | +13.5 |
| ~4.5 | Gemma 4 E4B | +14.0 |
| 4 | Nemotron Nano 4 B | +31.0 |
| 9 | qwen3.5 9 B | +24.0 |
| 9 | qwen3.5 9 B (distilled) | +18.0 |
| 14 | Ministral 14 B | +34.0 |
| ~4 (active, MoE) | Gemma 4 26 B | +27.0 |
| 32 (active, MoE) | GLM 4.5 (think) | +14.3 |

Two observations.

**(a) Saturation when `nopb` is already high.** GLM 4.5 (`nopb` SR at chaos = 10 % is 85.2 %, `pb` SR is 99.5 %) extracts a +14.3 pp gain—comparable to the 4 B-class dense models, and smaller than every model in the 9 B–26 B band. The mechanism is not specifically *frontier* saturation: qwen 3.5 4 B (`nopb` = 85.5 %, Δ = +13.5 pp) and Gemma 4 E4B (`nopb` = 86.0 %, Δ = +14.0 pp) sit at the same operating point within Wilson 95 % CIs at *N* = 200 / 600. What controls Δ at saturation is **proximity of the `nopb` baseline to the playbook ceiling**, not parameter count. The frontier model has a higher *floor at extreme chaos* (it does not break the way smaller models do—its `nopb` at chaos = 30 % is 57.0 %, comparable to qwen 4 B's 57.5 % within CIs), but at the canonical operating rates where `nopb` is already in the 80–90 % band the marginal value of the playbook is bounded by how much headroom remains. The same inverted-U pattern has been independently observed for *prompting strategies* on math reasoning [40]: a recent "Prompting Inversion" study finds a sophisticated prompting method peaks on gpt-4o and collapses to parity on gpt-5, via what the authors term a "Guardrail-to-Handcuff transition"—the constraint helpful for the mid-tier model becomes neutral or counterproductive for the frontier. Our hump finding on chaos recovery is consistent with this independent observation on a different axis.

**(b) A mid-range maximum at high chaos only.** At chaos = 30 % the largest gain is Ministral 14 B (+67 pp); at chaos = 10 % Gemma 4 E2B (+50.5 pp) leads because its `nopb` baseline is already weak (it gains partly from the structure the playbook prompt adds, a milder version of the qwen3.5 2 B structural-rescue case), and Ministral (+34 pp) is second. "Mid-range models gain the most" therefore describes the high-chaos regime, not the moderate one. See Fig 3 panel C.

At chaos = 30 % the gap profile is:

| Model | Δ at 30 % chaos |
|---|---:|
| qwen3.5 4 B | +36.5 |
| Gemma 4 E4B | +41.0 |
| Nemotron Nano 4 B | +52.5 |
| qwen3.5 9 B | +50.0 |
| qwen3.5 9 B (distilled) | +43.5 |
| Ministral 14 B | **+67.0** |
| Gemma 4 26 B (MoE) | +55.0 |
| GLM 4.5 (think) | +40.0 |

The gap at chaos = 30 % is larger than at chaos = 10 % for every functioning model except Gemma 4 E2B (+50.5 → +41.5 pp): within the band where the model can follow the task at all, the playbook's value grows with environmental hostility.

## 4.3 The full sweep, by capability bucket

**Fig 3—Cross-model SR vs chaos rate** (`paper/figures/fig4_cross_model.svg`). A 2×2 grid splitting the active roster into four capability brackets. Colour encodes vendor (Alibaba blue, Google yellow, NVIDIA green, Mistral violet, Zhipu pink, the community-distilled model grey); within a panel, marker shape distinguishes models of the same vendor. Solid lines are `pb`, dashed lines are `nopb`.

![Fig 3—Cross-model SR vs chaos rate, 4 capability brackets](figures/fig4_cross_model.png)

| Panel | Bucket | Models |
|---|---|---|
| A | Sub-2B—capacity floor / structural rescue | qwen3.5 0.8 B, qwen3.5 2 B, Gemma 4 E2B |
| B | ~4 B class—similar active compute, different architectures | qwen3.5 4 B, Gemma 4 E4B, Nemotron Nano 4 B |
| C | 9 B–26 B total—middle and upper roster | qwen3.5 9 B, qwen3.5 9 B distilled, Ministral 14 B, Gemma 4 26 B |
| D | Frontier (cloud) | GLM 4.5 |

Each panel plots success rate vs failure rate for both arms, with Wilson 95 % bands. Three takeaways:

- **Panel A** (Sub-2B): qwen3.5 0.8 B is flat at zero in both arms (capacity floor). qwen3.5 2 B's `nopb` arm is at the floor at every rate (0 % to ~4 %); the `pb` arm starts at 100 % at chaos = 0 % and degrades to 17 % at chaos = 30 %. Gemma 4 E2B is the most informative member of this bucket—both arms function and the playbook gap widens with chaos, mirroring the larger models.
- **Panel B** (~4 B class): the two non-reasoning models (qwen3.5 4 B dense, Gemma 4 E4B PLE) stay within 3 pp of each other on the `nopb` arm at every rate; the reasoning hybrid Mamba2–Transformer model (Nemotron 3 Nano 4 B) sits 12–26 pp below them. The `pb` arm is essentially saturated for qwen3.5 4 B and Gemma 4 E4B (≥ 94 % at chaos = 30 %) and slightly behind for Nemotron Nano 4 B (86.5 % at 30 %). Nemotron has the *lowest* `nopb` of the three at chaos = 0 % (85 %) and the *largest* `pb − nopb` gap at chaos = 30 % (+52.5 pp). We cannot disentangle two confounded effects in this panel: reasoning-by-default introducing self-induced drift (consistent with the §4.4 think/nothink evidence on GLM 4.5 under MCP/A2A) versus the hybrid Mamba2–Transformer architecture itself. Running Nemotron with its reasoning toggle off would separate them; we did not vary it in this campaign.
- **Panel C** (9 B–26 B): all four models reach `pb` ≥ 86 % at chaos = 30 %. The MoE model (Gemma 4 26 B, ~4 B active) behaves like the dense 9 B–14 B models on both arms. The community-distilled qwen3.5 9 B is *uniformly above* the original on `nopb` across every chaos rate (gap +1 pp at chaos = 0 % widening to +13 pp at chaos = 30 %), and on `pb` it saturates at 100 % up to chaos = 10 % and stays 1–7 pp above the original at every higher rate. Distillation preserves—and at high chaos, modestly improves—chaos resilience at the 9 B point in our roster.
- **Panel D** (Frontier): GLM 4.5 (think mode, 32 B active of 355 B) maintains a `nopb` floor of 57.0 % at chaos = 30 %—among the highest in the HTTP roster, statistically indistinguishable from qwen3.5 4 B (57.5 %) within Wilson 95 % CIs (GLM at *N* = 600 has Wilson half-width ≈ 4.0 pp vs qwen3.5 4 B at *N* = 200 with ≈ 6.8 pp)—and reaches `pb` = 97.0 % there. The arms are visibly closer than for any other model in the roster, which is the saturation signature: the unguided model is already close to the playbook ceiling.

## 4.4 Thinking helps on flat tools—and hurts on structured-error protocols

**Fig 4—Think vs nothink across protocols** (`paper/figures/fig5_thinking.svg`). Three panels, one per protocol (HTTP, MCP, A2A). Each panel plots GLM 4.5 for both arms. Encoding follows Fig 5 (pastel green = `pb`, pastel red = `nopb`; solid = `pb`, dashed = `nopb`), with marker shape distinguishing think (○) from nothink (△).

![Fig 4—GLM 4.5 think vs nothink across HTTP/MCP/A2A](figures/fig5_thinking.png)

The effect of the think toggle is **asymmetric across protocols**. On **HTTP** the think and nothink `nopb` curves are within Wilson 95 % CIs at every chaos rate (maximum observed difference +5.5 pp at chaos = 15 %; at chaos = 30 %: think 57.0 % vs nothink 55.0 %, Δ = +2.0 pp ± 5.6)—explicit reasoning has no detectable effect with flat HTTP tools. On **MCP** and **A2A**, however, think actively *hurts* the unguided arm well outside CIs: at chaos = 30 % MCP, `nopb` drops from 56.7 % (nothink) to 39.2 % (think); on A2A from 65.2 % to 51.5 %. We hypothesise that the typed error semantics of MCP/A2A (`timeout`, `rate_limited`, `task_rejected`) invite over-deliberation—the model reasons about the error type instead of treating it as a recoverable signal—and the longer reasoning chains drift off-task more often than a single HTTP status code would. This hypothesis is consistent with the aggregate `nopb` SRs but not directly supported by trace-level inspection in this paper (§5.5 ix).

The `pb` arm is mostly saturated near 100 % under nothink, and the playbook absorbs the would-be reasoning benefit on HTTP and A2A (chaos = 30 % `pb`: HTTP think 97.0 vs nothink 91.3; A2A think 99.5 vs nothink 98.8). The exception is **MCP under think**, where `pb` drops to 88.3 % at chaos = 30 % (vs 99.2 % under nothink): the same over-deliberation that hurts MCP `nopb` leaks through the playbook, attenuated but visible. Constructive observation for deployers: the playbook recovers most of the recovery benefit of explicit reasoning at a fraction of the inference cost (see §4.7), and on structured-error protocols it is actively safer to *disable* explicit thinking unless a downstream task requires it.

## 4.5 The playbook generalises across protocols

**Fig 5—Cross-protocol** (`paper/figures/fig6_cross_protocol.svg`). The three models with full protocol coverage—Ministral 14 B (HTTP/MCP/A2A think), Gemma 4 26 B (HTTP/MCP/A2A) and GLM 4.5 (HTTP/MCP/A2A, think + nothink)—are plotted side-by-side. Markers encode protocol (○ HTTP, ▢ MCP, △ A2A); colour encodes arm (pastel green = pb, pastel red = nopb); line style separates pb (solid) from nopb (dashed).

![Fig 5—Cross-protocol generalisation (HTTP/MCP/A2A)](figures/fig6_cross_protocol.png)

Two observations:

- The `pb` arm **mostly generalises across protocols**: at chaos = 30 % it lies between 88 % and 100 % for the three models, except Ministral 14 B on MCP (79.5 %). The same recovery instructions, adapted to each protocol's error vocabulary, produce comparable success on HTTP, MCP and A2A. The one consistent dip is MCP under think mode (Ministral 14 B: MCP `pb` 79.5 % vs HTTP 94.5 % / A2A 93.5 %; GLM 4.5 think: MCP `pb` 88.3 % vs HTTP 97.0 % / A2A 99.5 %), the same pattern surfaced in §4.4: explicit reasoning interferes with structured-error recovery even when the playbook is active.
- The `nopb` curve has more cross-protocol spread, and **the direction of the spread is model-dependent**. For **Ministral 14 B** and **Gemma 4 26 B**, A2A is the *most forgiving* environment (chaos = 30 % `nopb`: Ministral A2A 87.5 % vs HTTP 27.5 %, a +60 pp gap; Gemma 26 B A2A 86.5 % vs HTTP 38.5 %, +48 pp). For **GLM 4.5 in think mode** the pattern flips—HTTP is best (57.0 %), MCP worst (39.2 %), A2A in the middle (51.5 %). In **GLM 4.5 nothink** mode, A2A is best again (65.2 %), echoing the mid-roster pattern.

The constructive interpretation has two parts. First, **the playbook brings most protocol/model combinations up to a similar ceiling** (90–100 % at chaos = 30 %), with **MCP under reasoning the documented exception**—both Ministral 14 B (MCP `pb` = 79.5 %) and GLM 4.5 think (MCP `pb` = 88.3 %) sit visibly below their HTTP/A2A `pb`. We do *not* claim the playbook fully equalises across protocols; on this single recovered case the protocol-specific structural disadvantage of MCP under reasoning leaks through. Second, the protocol-specific *floor*—i.e. what the unguided model achieves—is shaped by how much **structural scaffolding** the protocol gives the model for free. A2A delegates each step to a sub-agent with a focused scope and wraps chaos in typed error semantics (`task_rejected`, `timeout`) that are easier to recover from than a bare HTTP 503; this is consistent with the structural help that mid-sized models (Ministral, Gemma 26 B) appear to absorb. The frontier model (GLM 4.5 think) does not benefit from this envelope—its own reasoning chain already maintains state—and on MCP/A2A the extra structure even costs `nopb` performance (§4.4). The playbook is the partial equaliser: it removes most of the protocol-specific structural advantage on the `pb` arm, while leaving the MCP-under-reasoning floor as a stubborn residual. We mark this as a hypothesis pending trace-level evidence (§5.5).

## 4.6 Does community distillation preserve chaos resilience?

**Fig 7—Distillation pair** (`paper/figures/fig8_distillation.svg`). Two panels comparing qwen3.5 9 B (original) and a community-distilled 9 B variant (DeepSeek-V4-Flash teacher) under identical HTTP chaos sweeps, *N* = 200 per cell.

![Fig 7—qwen3.5 9 B vanilla vs community-distilled (HTTP, N = 200)](figures/fig8_distillation.png)

The distilled variant is **uniformly above the original on the `nopb` arm** across every chaos rate, with the gap widening as chaos increases:

| Chaos rate | Vanilla nopb (%) | Distilled nopb (%) | Δ (pp) | 95 % CI on Δ (pp) |
|---:|---:|---:|---:|---:|
| 0 % | 99.0 | 100.0 | +1.0 | ± 1.4 (not individually sig.) |
| 5 % | 86.5 | 90.0 | +3.5 | ± 6.3 (not individually sig.) |
| 10 % | 73.0 | 82.0 | **+9.0** | ± 8.0 (marginally sig.) |
| 20 % | 53.0 | 59.5 | +6.5 | ± 9.7 (not individually sig.) |
| 30 % | 36.5 | 49.5 | **+13.0** | ± 9.6 (sig.) |

The strength of the distillation finding is **not the size of any single Δ**—most individual rates are within Wilson 95 % CIs at *N* = 200—but the **uniformity across rates**: distilled ≥ vanilla on `nopb` at 10/10 rates (sign test, *p* = 0.002, two-sided binomial). On the `pb` arm the distilled variant sits 0–8.5 pp above the original at every rate; the playbook saturates both lines near 100 % up to chaos = 10 %.

This result inverts the direction of a preliminary internal observation made on an *N* = 5 distilled pilot (April 2026), which suggested the opposite—distilled appearing *more* fragile than vanilla. The pilot's apparent gap was within sampling noise; the *N* = 200 sweep settles it cleanly. Two empirical implications:

1. **Community distillation preserves—and modestly improves—chaos resilience at the 9 B point in our roster.** The unguided distilled model is more robust to flaky tools than the unguided original at every chaos rate we tested. We do not interpret this as a general claim about distillation; it is one model pair, one task family. But it falsifies the conservative prior ("distillation can only lose") for this configuration.
2. **The playbook benefit does not depend on the distillation step.** Both variants saturate near 100 % at low chaos and stay above 86 % at chaos = 30 %; the playbook gain travels with the underlying capability bracket (§4.2) rather than with the training recipe.

Caveat: we deliberately do *not* claim a mechanism. The distilled variant emits zero `reasoning_tokens` per turn (the teacher's reasoning traces were not directly transferred), so we cannot attribute the gain to inherited deliberation pattern. A targeted ablation—pair vanilla vs distilled with matched compute budgets and matched system-prompt shapes—would be needed to identify the mechanism. We flag this as item 4 in §6.3 (the targeted distillation ablation).

Historical context: the closest prior art is from the image-classification adversarial literature, where Papernot et al. [43] showed that defensive distillation can transfer robustness to perturbations. Our finding extends the "distillation can preserve / improve robustness" axis from image-classification adversarial inputs to LLM-agent chaos at the tool boundary—a different axis entirely, but consistent with the conservative prior.

## 4.7 Cost is bounded and predictable

**Fig 6—Cost of the playbook** (`paper/figures/fig7_cost_of_playbook.svg`). Three panels at chaos = 10 % HTTP: tokens per run (prompt + completion, mean), wall time per run (s, mean), LLM calls per run (mean). For each panel, two bars per model—`nopb` (pastel red) and `pb` (pastel green).

![Fig 6—Cost of the playbook (tokens, wall time, LLM calls per run)](figures/fig7_cost_of_playbook.png)

Numbers (per run, mean, at chaos = 10 % HTTP):

| Model | `nopb` tokens | `pb` tokens | Δ tokens (%) | `nopb` calls | `pb` calls | `nopb` time (s) | `pb` time (s) |
|---|---:|---:|---:|---:|---:|---:|---:|
| qwen3.5 4 B | 3 224 | 3 663 | +13.6 % | 5.2 | 5.4 | 23.3 | 18.6 |
| Gemma 4 E4B | 2 941 | 3 846 | +30.8 % | 5.0 | 5.4 | 19.8 | 20.3 |
| Nemotron Nano 4 B | 2 709 | 3 702 | +36.7 % | 5.5 | 6.1 | 12.4 | 12.6 |
| qwen3.5 9 B | 2 597 | 3 644 | +40.3 % | 4.8 | 5.4 | 23.5 | 26.7 |
| Ministral 14 B | 1 581 | 2 664 | +68.5 % | 4.5 | 5.4 | 15.4 | 19.6 |
| Gemma 4 26 B | 1 750 | 2 791 | +59.5 % | 4.7 | 5.4 | 14.8 | 21.2 |
| GLM 4.5 (nothink) | 1 680 | 2 472 | +47.1 % | 5.0 | 5.4 | 14.5 | 13.4 |

- **Tokens**: the playbook adds 13 %–69 % (mean ≈ 42 %). The *absolute* cost is the playbook prompt itself (a few hundred tokens) plus the extra retry turns it elicits. Reasoning-heavy models (Nemotron Nano with thinking, Ministral 14 B) sit in the upper half of the range because their retry chains include reasoning tokens.
- **LLM calls**: the playbook adds **+0.57 calls per run on average** (range +0.25 to +0.98 calls / run; mean across the seven cells in the table above). This is the empirical signature of the retry loop the playbook authorises.
- **Wall time**: model-dependent. Two cells run *faster* with the playbook (qwen3.5 4 B: −20 %; GLM 4.5 nothink: −7 %), two are essentially unchanged (Gemma 4 E4B, Nemotron Nano 4 B), and three run moderately slower (qwen3.5 9 B: +14 %; Ministral 14 B: +27 %; Gemma 4 26 B: +43 %). Faster runs come from the playbook abandoning long chaos-induced hallucination loops earlier; slower runs come from the extra retry latency dominating.

The combined picture: a small fixed-shape token tax (~ +42 % per run on average, bounded above by ~ +69 % for the most reasoning-intensive models in the roster) buys the reliability gains documented in Figs 1–3. There is no free lunch but the lunch is cheap.

## 4.8 The full corpus at a glance

**Fig 8—Δ(pb − nopb) heatmap across (model, chaos rate)** (`paper/figures/fig9_heatmap.svg`). Rows are models sorted by active parameters (low → high); columns are the ten chaos rates (0 % → 30 %). Each cell is the per-rate Δ; the colour scale runs from red (Δ ≤ 0) through yellow (Δ ≈ 30 pp) to green (Δ ≥ 60 pp).

![Fig 8—Δ heatmap, HTTP full sweep](figures/fig9_heatmap.png)

Four patterns are visible without reading any single curve:

1. **The capacity floor (qwen3.5 0.8 B, top row) is red across the entire grid**: the playbook cannot rescue what cannot follow the task.
2. **The structural-rescue band (qwen3.5 2 B, second row) is bright green at low chaos and fades to yellow at high chaos**: the playbook adds *structural* scaffolding that helps overwhelmingly at chaos = 0 % and progressively less as the underlying task becomes too hard for the 2 B model.
3. **The mid-roster (Gemma E4B / qwen 4 B / Nemotron / Gemma 26 B / qwen 9 B / Ministral) green band intensifies as chaos rises**: the playbook gain scales with environmental hostility for models that can already follow the task, with Ministral the brightest column at chaos = 30 %.
4. **The frontier row (GLM 4.5, bottom) is red-yellow at low chaos and yellow at high chaos**: the unguided model already approaches the playbook ceiling so the marginal value of the playbook is bounded.

## 4.9 Summary of the empirical map

Combining the eight figures and the paired tests:

1. **Across all functioning models the playbook helps and never harms**, with a median Δ of **+24 pp** at chaos = 10 % (bootstrap 95 % CI over models: [14.0, 34.0]) and **+43.5 pp** at chaos = 30 % (bootstrap 95 % CI: [40.0, 55.0]) over the functioning roster (n = 9; the qwen3.5 0.8 B floor and the qwen3.5 2 B structural-rescue case are excluded, §5.3). In paired exact tests with Holm correction the effect is significant in every functioning-roster HTTP cell at failure rates of 5 % and above (Table 4).
2. **The marginal value of the playbook depends on capability and on the chaos rate.** At 30 % chaos it is largest in the mid-range (maximum at 14 B) and smaller for the frontier model, whose unguided baseline is already close to the playbook's ceiling; at 10 % chaos it is not monotonic in size. This is an observed pattern, not a formally tested law (§5.5 viii).
3. **The playbook generalises across protocols** (HTTP/MCP/A2A) and across reasoning toggles (think/nothink), with **MCP under reasoning** as the one documented exception, where the `pb` arm sits about 9–15 pp below its HTTP/A2A counterparts at 30 % chaos (§4.5).
4. **Capacity floor**: a 0.8 B model cannot use the playbook because it cannot follow the task. A 2 B model gains a +100 pp Δ at chaos = 0 % because the playbook supplies missing structural scaffolding.
5. **The cost of the playbook is bounded** (~ +42 % tokens on average; +0.57 extra LLM calls on average; wall time model-dependent—see §4.7).

These findings feed §5 (caveats and threats to validity) and §6 (what we recommend doing next).
