# 2 Related work

This paper draws on three research communities: chaos engineering and fault injection for distributed systems (§2.1), LLM-agent benchmarking and robustness (§2.2), and the study of how capability changes with model scale, distillation and reasoning (§2.3). A fourth thread, regulatory requirements for robustness evidence, motivates the work (§2.4).

## 2.1 Chaos engineering and fault injection for distributed systems

*Community: site reliability engineering and distributed-systems research.* Chaos engineering originated as a production-hardening practice at Netflix with Chaos Monkey [2] and was formalised in the *Principles of Chaos Engineering* [3] and the IEEE Software treatment [1]. Subsequent work generalised the approach to controlled fault injection in production-grade platforms [6, 7, 8] and to formal models of failure such as Lineage-Driven Fault Injection [4] and its industrial application [5]. The standard target is *infrastructure*: kill a pod, throttle a network link, pause a process, return 5xx with probability *p*.

Our work inherits the philosophy—*inject controlled faults and observe*—and the methodological discipline (seeded injection, paired control runs, bounded blast radius). It departs in the *target*: we inject at the **agent ↔ tool boundary** of an LLM stack, not at the infrastructure level. The fault model is consequently different: transient failures surfaced through the tool-call channel itself—HTTP 5xx and timeout codes, typed MCP/A2A errors such as `rate_limited` or `task_rejected`—the failure modes a real LLM agent encounters when its tools are flaky.

A small set of **concurrent** works explores this direction: ReliabilityBench [37] injects timeouts, rate limits, partial responses and schema drift at the tool boundary across two frontier APIs (Gemini 2.0 Flash, GPT-4o) over 1,280 episodes; Hell or High Water [38] benchmarks agent recovery when functions disappear or fail mid-trajectory; AgentNoiseBench [39] categorises noise into user-noise and tool-noise in an automated pipeline. Our contribution differs on four axes: (i) **scale** (128,000 runs vs 1,280 episodes in ReliabilityBench), (ii) **roster breadth** (eleven models spanning 0.8 B to 355 B vs two frontier APIs), (iii) **an explicit A/B comparison with a structured recovery playbook** (a methodological lever absent in the concurrent works), and (iv) **cross-protocol coverage** (HTTP/MCP/A2A).

## 2.2 LLM-agent benchmarks and robustness

*Community: machine-learning evaluation and agent research.* The LLM-agent literature has produced an expanding family of benchmarks: **SWE-Bench** [13] (software engineering), **AgentBench** [14], **WebArena** [15], **OSWorld** [17], **τ-Bench** [18] (multi-turn business-process completion) and **GAIA** [16]. These suites measure end-to-end task success on golden trajectories in deterministic environments. They have driven real progress in tool use and planning, but by construction they say little about behaviour under *operational* chaos: the environments are clean, the tools always work, and the only source of failure is the model itself.

A second strand examines *robustness* to perturbed or adversarial inputs, such as jailbreak red-teaming and prompt-injection attacks [34]. These manipulate the *input* the model receives, mimicking a careless or malicious user or a poisoned document. Our axis is complementary: we keep prompts fixed and inject faults into the *tool responses* the agent receives mid-trajectory. This mimics what production infrastructure does to an agent—an API that times out, a rate limiter that pushes back, a service that is briefly down—failures that are frequent, benign in intent and invisible to input-side robustness tests.

A third strand adds model-side recovery behaviour: ReAct [9] interleaves reasoning and acting, and Reflexion [10] adds verbal self-reflection between attempts; relatedly, Tree of Thoughts [11] performs deliberate search with self-evaluation and backtracking. These works make the *model* invent recovery behaviour. We ask the complementary question: given a fixed model, how much of the recovery gap can a *short, externally provided* recovery playbook close? Because the model is held fixed in each comparison, the effect is comparable across architectures.

## 2.3 Scale, distillation and reasoning

*Community: language-model scaling and training research.* A large body of work studies how capability changes with scale and architecture—compute-optimal training [22], knowledge distillation [23], sparse Mixture-of-Experts models such as Mixtral [24]—and the literature on inference-time reasoning (chain-of-thought [12], deliberation and "thinking" toggles in current model families [25, 26, 27]). These findings are established on *clean* benchmarks.

We vary the same axes—total and active parameters, architecture, distilled vs original, think vs nothink—under chaos, and find a different picture:

- The playbook's benefit is not monotonic in scale: at high chaos the mid-range models gain the most and the frontier model gains less, whereas capability on clean benchmarks usually grows with scale. A similar inverted-U has been reported for prompting strategies on reasoning tasks [40].
- In our **distillation pair** (qwen3.5 9 B vs a community-distilled 9 B variant), the distilled model is above the original on the unguided arm at every chaos rate, with the gap widening from +1 pp at chaos = 0 % to +13 pp at chaos = 30 %.
- The think/nothink toggle on GLM 4.5 has little effect on flat HTTP tools but lowers unguided success on protocols with typed errors (MCP, A2A).

We treat these as empirical observations, not as theory.

## 2.4 Regulatory requirements for robustness evidence

The EU AI Act [33] requires *providers* of high-risk AI systems to comply with requirements on risk management (Art. 9), data governance (Art. 10), human oversight (Art. 14) and accuracy, robustness and cybersecurity (Art. 15). Article 15(4) asks that such systems be "as resilient as possible regarding errors, faults or inconsistencies" arising from their interaction with natural persons or other systems; providers of general-purpose AI models *with systemic risk* must additionally perform model evaluation including adversarial testing (Art. 55(1)(a)). The Act encourages the development of "benchmarks and measurement methodologies" (Art. 15(2)) without prescribing them, a gap analysed in [42]. Proposed assurance frameworks focus on documentation rather than active testing (e.g. the ontology and assurance-case approach of [41]). Evidence of *what an agent does when its tools misbehave* is largely absent from both guidance and practice. We present the rig and the released dataset as a candidate measurement methodology for that gap (§5.7).

## 2.5 What this paper is *not*

This is **not** a paper about a new model, a new training recipe or a new agent framework. The agent framework is deliberately minimal. The contribution is the *measurement methodology* and the *empirical map* it produces; the instrument and the data are the artefact.
