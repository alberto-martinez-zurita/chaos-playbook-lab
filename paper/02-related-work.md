# 2 Related work

This paper sits at the intersection of three communities. We summarise each line briefly and explain how this work differs.

## 2.1 Chaos engineering for distributed systems

Chaos engineering originated as a production-hardening practice at Netflix in the early 2010s with Chaos Monkey [2] and was formalised in the *Principles of Chaos Engineering* [3] and the IEEE Software treatment [1]. Subsequent work generalised the approach to controlled fault injection in production-grade platforms [6, 7, 8], to formal models of failure modes such as Lineage-Driven Fault Injection [4, 5], and to safety arguments around blast-radius control. The standard target is *infrastructure*: kill a pod, throttle a network link, pause a process, return 5xx with probability *p*.

Our work inherits the philosophy — *inject controlled fault and observe* — and the methodological discipline (deterministic seeding, paired control runs, bounded blast radius). It departs in the *target*: we inject at the **agent ↔ tool boundary** of an LLM stack, not at the infrastructure level. The fault model is consequently different: transient failures surfaced through the tool-call channel itself — HTTP 5xx and timeout codes, typed MCP/A2A errors such as `rate_limited` or `task_rejected` — the failure modes a real LLM agent encounters when its tools are flaky.

A small set of **concurrent** works has begun exploring this direction in the past nine months: ReliabilityBench [38] (Jan 2026) injects timeouts, rate limits, partial responses and schema drift at the tool boundary across two frontier APIs (Gemini 2.0 Flash, GPT-4o) over 1,280 episodes; Hell or High Water [39] (Aug 2025, COLM) benchmarks agent recovery when functions disappear or fail mid-trajectory; AgentNoiseBench [40] (Feb 2026) categorises noise into user-noise and tool-noise on an automated pipeline. Our contribution differs on four axes: (i) **scale** (128 K runs vs ~1,300 episodes in ReliabilityBench), (ii) **roster breadth** (11 open-weight models spanning 0.8 B – 355 B vs 2 frontier APIs), (iii) **explicit A/B with a structured recovery playbook** (a methodological lever absent in the concurrent works), and (iv) **cross-protocol coverage** (HTTP/MCP/A2A). The hump-shape, frontier-saturation, MCP-under-reasoning and distillation-pair findings (§4) follow from those four levers and have, to our knowledge, no parallel in the concurrent literature.

## 2.2 LLM agent reliability and benchmarks

The LLM-agent literature has produced an expanding family of benchmarks: **SWE-Bench** [13] (software engineering), **AgentBench** [14], **WebArena** [15], **OSWorld** [17], **τ-Bench** [18] (multi-turn business-process completion), **GAIA** [16], and so on. These suites measure end-to-end task success on a set of golden trajectories with deterministic environments. They have driven real progress in tool-use and planning ability, but by construction they say very little about behaviour under *operational* chaos: the environments are clean, tools always work, and a single failure mode (the model itself) is varied.

A second strand examines *robustness* via prompt perturbations or adversarial inputs (e.g. red-team studies of jailbreaks, prompt-injection benchmarks [35]). These adversarially manipulate the *input* to the model. Our axis is orthogonal: we keep prompts fixed and adversarially manipulate the *tool responses* the agent receives mid-trajectory.

A third strand, closest in spirit, instruments single agents with introspective recovery loops (ReAct [9], Reflexion [10], Tree-of-Thoughts variants for agents [11]). Those works *invent* recovery behaviour by adding model-side reasoning. Our work asks the complementary question: given a fixed model, how much of the recovery gap can we close with a *small, externally provided* recovery playbook? The playbook is a few hundred tokens; the experiment is comparable across architectures because the model is held fixed.

## 2.3 Scaling, distillation and reasoning

A large body of work studies how capability emerges with scale — Chinchilla compute-optimality [22], distillation studies [23], elastic-inference architectures such as MatFormer [24] and sparse-MoE architectures such as Mixtral [25], and the recent literature on inference-time reasoning (chain-of-thought [12], deliberation, "thinking" toggles in Qwen 3.5 [26], GLM 4.5 [28], Gemma 4 [27]). These findings live in the world of *clean* benchmarks.

We sweep the same axes — total parameters, active parameters, dense vs MoE vs MatFormer, distilled vs original, think vs nothink — under chaos. The result is a different empirical picture than the clean-benchmark literature suggests. Notably:

- The **hump** we observe (4 B–26 B benefits most from the playbook, frontier saturates) does not appear on clean benchmarks where capability is monotonic in scale.
- A **distillation pair** in our roster (qwen3.5 9 B vs a community-distilled 9 B variant) shows the distilled variant *uniformly above* the original on the `nopb` arm, with the gap widening from +1 pp at chaos = 0 % to +13 pp at chaos = 30 %. Distillation preserves chaos resilience at the 9 B point and, modestly, improves it at high chaos.
- A **think/nothink** toggle on the same frontier model (GLM 4.5) does not change the playbook's marginal value as much as one might expect.

We treat these as empirical contributions to the scaling-laws literature, not as definitive theory.

## 2.4 EU AI Act and operational evidence

A pragmatic motivation: the EU AI Act [34] (Articles 9, 10, 14, 15) requires deployers of high-risk AI systems to provide evidence of robustness, risk-management procedures and human oversight. Two recent legal-and-ML analyses [42, 43] examine how Articles 15 (high-risk) and 55 (general-purpose AI) should be operationalised and explicitly identify that the Act calls for "benchmarks and measurement methodologies" without prescribing them. Existing practice for LLM systems leans heavily on output-quality evaluations and red-teaming reports; chaos evidence — *what does the agent do when its tools misbehave?* — is conspicuously absent from both prescriptive guidance and proposed assurance frameworks (e.g. ontology + assurance-case approaches [42] focus on documentation rather than active testing). We frame the rig and the released CSV dataset as a candidate template for the measurement-methodology gap. §5.7 returns to this.

## 2.5 What this paper is *not*

To set expectations: this is **not** a paper about a new model, a new training recipe, or a new agent framework. The framework is deliberately minimal. The contribution is the *measurement methodology* and the *empirical map* it produces. The instrument and the data are the artefact.
