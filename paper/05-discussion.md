# 5 Discussion

## 5.1 What the hump means

The headline empirical finding — a non-monotonic shape of Δ(pb − nopb) vs active parameters, peaking at 4 B–14 B and shrinking at the frontier — is consistent with two intuitions that meet in the middle.

**(a) Below 4 B, the model lacks the capacity to *use* the playbook.** qwen3.5 0.8 B is the demonstration: it cannot follow the four-step task at chaos = 0 %, and the playbook is just more text it does not act on. qwen3.5 2 B is a softer version of the same story — it cannot emit valid structured output without the playbook providing format scaffolding, so the +100 pp gap at chaos = 0 % is overwhelmingly *structural rescue* rather than chaos rescue (§4.1, §5.3). These two points define the **capacity floor** of the instrument.

**(b) At the frontier, the model partly *invents* the playbook.** GLM 4.5 (32 B active of 355 B total) reaches `nopb` SR = 85.2 % at chaos = 10 % and 57.0 % at chaos = 30 % — among the highest `nopb` arms in the HTTP roster, statistically indistinguishable from qwen3.5 4 B and Gemma 4 E4B within Wilson 95 % CIs at several rates (GLM at *N* = 600 vs the local roster at *N* = 200). Adding the playbook still helps (+14.3 pp at 10 %, +40.0 pp at 30 %), but the unguided model is already doing some of the recovery the playbook codifies. The marginal value of the playbook shrinks because the baseline is close to the playbook ceiling.

The middle band — 4 B to 14 B active parameters — is the regime where the model has enough capability to *follow* recovery instructions but not enough capability to *invent* them on its own. This is the band where the playbook is most leveraged.

The practical implication is opposite to the naïve "use the smallest model that works" heuristic: **the smallest model that benefits most from a recovery playbook is the same model an SRE should deploy with one**. Smaller than that, the playbook cannot rescue the agent. Larger than that, the playbook is still net-positive but spendier as a proportion of inference cost.

## 5.2 Architecture, not parameter count

The 4 B-active iso-comparison (qwen3.5 4 B dense, Gemma 4 E4B MatFormer, Nemotron 3 Nano 4 B hybrid Mamba2-Transformer with reasoning) shows the two **non-reasoning Transformer** architectures (qwen3.5 4 B and Gemma 4 E4B) within ~5 pp of each other on `nopb` at every rate, and the `pb` arm of all three within ~9 pp. The reasoning hybrid-architecture model (Nemotron) is the spread driver: it sits 15–25 pp below the non-reasoning pair on `nopb` at every rate but joins them on `pb` (within ~9 pp). The MoE point in our roster (Gemma 4 26 B = 4 B active) tracks the dense 9 B–14 B band rather than the dense 26 B band. Taken together, **active parameters predict the playbook-corrected ceiling** (the `pb` arm clusters by active count, not by architecture), but the `nopb` floor is additionally modulated by *some* combination of reasoning-by-default and the hybrid Mamba2-Transformer architecture — the Nemotron data alone cannot separate those two factors (§4.3 panel B caveat).

A speculative observation: the reasoning model in the 4 B class (Nemotron Nano 4 B) has the lowest `nopb` baseline at chaos = 0 % and the largest `pb` − `nopb` gap at high chaos. We hypothesise (without definitive evidence in the current dataset) that internal reasoning introduces its own *self-induced* failure mode — long chains of thought that eventually drift off-task — and that the playbook absorbs both chaos-induced and reasoning-induced failures. The evidence is **protocol-specific**: the effect is visible in the Nemotron 4 B class (HTTP), and well outside CIs on **GLM 4.5 under MCP and A2A** (−17.5 pp on MCP, −13.7 pp on A2A at chaos = 30 % for think vs nothink, well outside Wilson 95 % CIs on the difference). On **GLM 4.5 under HTTP** the think/nothink difference is within sampling noise at every rate (§4.4) — i.e. reasoning is approximately neutral on flat tools, harmful on structured-error protocols. We mark the broader "reasoning trades baseline reliability" reading as a hypothesis pending more reasoning-toggle pairs (§5.5 vi) and trace-level inspection (§5.5 ix).

## 5.3 Two caveats that must travel with the data

**Capacity floor (qwen3.5 0.8 B).** The model is in the comparative figures so the floor is visible, but the row should be read as "playbook cannot rescue what cannot follow instructions". It is a useful empirical anchor (we now know where the floor is) and should not be cited as evidence that the playbook ever harms a model.

**Structural rescue (qwen3.5 2 B).** The +100 pp Δ at chaos = 0 % is the playbook fixing a *format* problem (the model cannot emit valid JSON without explicit guidance) rather than a *chaos* problem. A reader who quotes the qwen3.5 2 B numbers without this caveat will misread the rest of the paper. We retain the row because the *shape* of the gap profile is informative: Δ decreases monotonically from +100 pp at chaos = 0 % through +56 pp at chaos = 10 % to +13 pp at chaos = 30 %, showing the playbook's chaos-rescue contribution shrinks as the absolute task becomes too hard for the underlying model.

In future work we will add a "structured-output baseline" arm — same model, same task, same prompt skeleton, plus an explicit JSON schema — to disentangle structural rescue from chaos rescue numerically.

## 5.4 Excluded: the mode-collapse model

We exclude `gpt_oss_20b` from comparative analysis because at chaos ≥ 0.25 it enters a `?????`-loop mode collapse — a *language-model-level* decoder failure qualitatively distinct from the trajectory failures of the active roster (cf. "policy collapse" reported in adversarial-input studies, e.g. [35], but elicited here by entirely benign chaos at the tool boundary). Rates 0.00–0.20 are preserved as appendix evidence (§3.6, `experiments/gpt_oss_20b/`); the finding is flagged for follow-up but not analysed further here.

## 5.5 Threats to validity

**(i) Single task family.** The Petstore-style four-step workflow is representative of the structured-tool-use class but not of all agent tasks. A task with longer reasoning chains, ambiguous tool semantics or open-ended state would stress the playbook differently. The cross-protocol generalisation (Fig 6) provides a partial defence — the playbook works the same across HTTP, MCP and A2A *for this task* — but cross-task generalisation is future work.

**(ii) Chaos schedule is uniform random.** Our chaos rate is a marginal probability over independent calls. Real production failures are bursty, correlated and sometimes systemic (one downstream service is degraded for the next 30 s). A burst-mode chaos rig would likely change the shape of the curves; we expect the playbook to help *more*, not less, but this should be measured.

**(iii) Sample sizes by cell.** All local-roster cells are *N* = 200 per arm (qwen3.5 family, Gemma 4 family including the 26 B MoE, Nemotron Nano 4 B, Ministral 14 B); the cloud frontier model (GLM 4.5) is *N* = 600 per arm so that think × nothink × HTTP/MCP/A2A is well powered. All headline differences in §4 are well outside Wilson 95 % CIs at the cells where they are quoted. The released CSVs include the `seed` column for exact replication.

**(iv) One playbook per protocol.** We did not sweep playbook variants. The HTTP playbook is 69 words; we have not measured how much of the gap is attributable to the playbook *content* versus the act of giving the model *any* recovery instruction. A control arm with a deliberately bad playbook would tell us. We anticipated negative results would have to be reported here; positive — i.e. the content matters — would be a stronger contribution.

**(v) Local runtime variance.** Most models in our roster ran on LM Studio (localhost). Throughput varies between machines and between runtime versions; wall-time numbers in §4.7 should be read as relative comparisons, not absolute deployment estimates. The token and call counts are runtime-independent.

**(vi) Vendor reasoning toggle is single-model.** Only GLM 4.5 in the roster exposes a clean think/nothink toggle. Generalising the §4.4 findings beyond GLM 4.5 requires more reasoning-toggle pairs.

**(vii) Single seed (`seed = 2026`).** All cells share the same chaos schedule per `(rate, model)` pair, so cross-arm comparisons within a cell are well controlled, but our error bars capture *binomial* sampling variance only — not seed-driven variance in *which* calls within a run get faulted. Two cells at the same `(model, rate)` with different seeds would draw different chaos sequences and could land on slightly different success rates. We do not claim to have measured that variance; a follow-up replication with 3–5 alternative seeds on a roster subset would close this gap.

**(viii) No multiple-comparisons correction; hump shape not formally tested.** The paper reports many pairwise differences across an 11-model × 10-rate × 2-arm grid. We rely on the magnitude of the headline differences (well outside Wilson 95 % CIs at the cells where they are quoted) rather than on family-wise α control. We also do not formally test the *shape* of the hump: a quadratic regression of Δ on log(active parameters) over the n = 9 functioning roster yields a negative concavity coefficient at chaos = 30 % (consistent with a peak around ~10 B active parameters, in agreement with the visual peak at Ministral 14 B) but the coefficient is not statistically significant at n = 9 (*t* ≈ −1.1). The hump is therefore best read as a *visual* and *bootstrap-supported* pattern (the median +43.5 pp at chaos = 30 % is bracketed by a 95 % bootstrap CI of [40.0, 55.0]) rather than as a formally tested non-monotonicity. Inferences drawn from individual fine-grained comparisons should be read accordingly; the structural claims of the paper (hump shape, frontier saturation, MCP-under-reasoning dip) each rest on multiple consistent points rather than on a single comparison.

**(ix) Mechanistic claims pending trace-level evidence.** The hypotheses in §4.4 (over-deliberation drives MCP/A2A drift) and §4.5 (structural scaffolding from A2A's typed errors helps mid-sized models) are consistent with the aggregate `nopb` SRs we report but are *not* directly supported by trace-level inspection in this paper. Both hypotheses are falsifiable from the released CSVs (which include `reasoning_tokens` per turn and per-step `failed_at` markers) and we flag the trace-level study as immediate follow-up rather than as a settled finding here.

**(x) Runtime under-specification.** Local cells were served by LM Studio; specific runtime / driver / quantisation choices per model are recorded in the released `experiments/<model>/experiment.yaml` artefacts rather than transcribed into this paper. Headline SR differences are large relative to plausible runtime-driven variance, but wall-time numbers in §4.7 should be read as ordinal comparisons within this study, not as absolute deployment estimates.

## 5.6 What does this mean for an SRE?

Three concrete recommendations for someone deploying an LLM agent today:

1. **Always add a recovery playbook.** The cost is bounded (~ +42 % tokens, ~ +1 LLM call) and the benefit is large (median +24 pp at chaos = 10 %, +43.5 pp at chaos = 30 %), and there is no model in our roster where the playbook hurts.
2. **Pick the model in the *middle of the hump***, not the smallest one that "passes the benchmark". A 4 B–14 B model with a playbook tends to outperform a smaller model with or without one, on chaos-load reliability — which is what the SRE actually pages on.
3. **Run a chaos sweep before production**, not after the first incident. The methodology in §3 is reproducible in a few hours on a single GPU; the released `chaos-engine` rig is open source. The marginal value of even one chaos sweep is large because failure modes (especially mode collapse, see §5.4) are easy to miss on clean benchmarks and hard to debug in production.

## 5.7 Compliance evidence (EU AI Act)

The chaos rig and the released CSVs are intentionally structured to serve as compliance evidence under EU AI Act Articles 9 (risk-management system) and 15 (accuracy, robustness and cybersecurity). Each row in the CSVs records the seed, the chaos rate, the protocol, the agent identity and the outcome — i.e. an auditable provenance chain from a deployed agent to the chaos sweep that exercised it. We do not claim this discharges Art 15 by itself; we do claim it is a candidate template for the kind of robustness evidence the regulation asks for and which the LLM-agent literature does not yet routinely produce.
