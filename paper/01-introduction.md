# 1 Introduction

## 1.1 Why chaos, why now

Agentic large language model (LLM) stacks—a model orchestrating a sequence of tool calls against external systems—are no longer a research curiosity. They underpin retrieval-augmented assistants, integrated development environment (IDE) copilots, customer-support bots, extract-transform-load (ETL) repair jobs and a growing class of business-process automation. Yet the deployment story for these stacks still rests on two implicit assumptions:

1. The model is *good enough* to recover from the kind of imperfect tool behaviour that real production environments exhibit (timeouts, malformed JSON, half-applied writes, race conditions, transient HTTP 5xx).
2. Standard benchmarks (GSM8K [20], MMLU [19], HumanEval [21], agentic suites such as τ-Bench [18] or SWE-Bench [13]) are *informative enough* about that recovery behaviour to inform model-selection and architecture decisions.

We argue that neither assumption holds in practice. Standard benchmarks measure an agent's behaviour on a happy path. Reliability under chaos—partial failures, redelivery, drift between protocol layers—is a qualitatively different surface. It determines whether a deployed agent compounds errors silently or recovers gracefully, and it is the surface that a site reliability engineer (SRE) actually watches.

Two terms are used throughout. **Operational chaos** is the phenomenon: the transient failures an agent meets in production when its tools are slow, rate-limited or briefly unavailable. **Chaos engineering** [1, 3] is the practice, originating at Netflix, of injecting such failures deliberately and under control to observe how a system behaves. Our contribution is to **treat chaos engineering as a scientific instrument**, not a production-hardening tool, and to use it to expose the reliability landscape of LLM agents.

The question also has a regulatory side. The EU AI Act [33] requires providers of high-risk AI systems to ensure accuracy, robustness and cybersecurity (Art. 15), including resilience to "errors, faults or inconsistencies" arising from interaction with other systems (Art. 15(4)), and asks for the development of "benchmarks and measurement methodologies" (Art. 15(2)) without prescribing them. Evidence of how an agent behaves when its tools misbehave is exactly that kind of measurement, and it is largely absent from current practice (§2.4, §5.7).

## 1.2 The instrument

We build a transparent, seeded chaos rig (released as `chaos-engine`) that injects a controlled rate of faults into the path between the LLM agent and its tools. It re-architects an earlier prototype into a protocol-agnostic A/B rig (see Acknowledgements). The faults are intentionally simple and explicitly signalled—HTTP error codes (5xx, 408/504 timeouts, 429), typed MCP errors (`timeout`, `rate_limited`, `internal_error`) and typed A2A errors (`timeout`, `task_rejected`, `partial_failure`)—and the injection mechanism is the same for all protocols: each tool call is replaced by a fault with probability *p*, and the fault type is drawn uniformly from the rig's set. A single knob—the **failure rate** *p*—goes from 0 % to 30 % per tool call. Around the rig we run a fixed multi-step task and an A/B comparison between two agents:

- **`nopb` (unguided)**: the model is told what tools exist and asked to complete the task. It receives no recovery instructions.
- **`pb` (playbook)**: the model also receives a short structured **recovery playbook** that we designed for this study—a 69-word instruction block (HTTP version) stating, for each error type the rig can inject, whether and how to retry and when to give up.

Both arms run on the *same model*, the *same prompt skeleton* and the *same seed for each run index*. Differences in success rate, token cost and wall time are therefore attributable to the playbook and to the retries it elicits.

## 1.3 What this paper claims

We apply this instrument to **eleven LLMs** spanning nearly three orders of magnitude (0.8 B to 355 B total parameters), four architecture types (dense, Per-Layer-Embedding, hybrid Mamba2–Transformer and Mixture-of-Experts), one think/nothink toggle (GLM 4.5) plus two models that reason by default, and three transport protocols (HTTP, MCP, A2A). The full dataset is **128,000 active agent runs** (plus 800 appendix runs from an excluded model, §3.6), all released as raw CSVs alongside this paper.

Four contributions:

1. **An open, reproducible instrument and dataset.** A seeded chaos rig, a recovery playbook per protocol and a 128,800-run dataset from which every figure and table in this paper can be regenerated.
2. **The playbook closes most of the chaos-induced gap.** Over the **functioning roster** (n = 9: the active roster minus the capacity-floor qwen3.5 0.8 B and the structural-rescue qwen3.5 2 B, §5.3), the median improvement at 30 % chaos is **+43.5 pp**; across the full active roster the range is +0 pp (qwen3.5 0.8 B) to +67 pp (Ministral 14 B). In paired exact tests with multiple-comparison correction the effect is significant in every functioning-roster HTTP cell at failure rates of 5 % and above, and no model is harmed at any rate under the transient faults we inject. A large part of the gain comes from inducing retries in models that otherwise rarely retry (§5.5 xi).
3. **The benefit depends on capability and on the chaos rate.** At 30 % chaos the mid-range models gain the most (largest at 14 B) and the 355 B frontier model gains less because its unguided baseline is already high; at 10 % chaos the gain is not monotonic in model size. We characterise this pattern and its limits rather than claiming a formal law.
4. **The cost is bounded and predictable.** The playbook adds 13 %–69 % more tokens per run (mean ≈ 42 %) and +0.57 LLM calls on average (range +0.25 to +0.98). Wall time is model-dependent: some models run *faster* with the playbook (qwen3.5 4 B: −20 %; GLM 4.5 nothink: −7 %), others moderately slower (Ministral 14 B: +27 %; Gemma 4 26 B: +43 %).

Two negative findings deserve attention:

- A **capacity floor**: qwen3.5 0.8 B fails the task at 0 % chaos in both arms. The playbook cannot rescue a model that cannot follow the original instructions.
- A **structural-rescue artefact**: qwen3.5 2 B's `nopb` arm scores 0 % at chaos = 0 % because the model cannot emit valid structured output for the task without explicit guidance. Its +56.5 pp gap at chaos = 10 % is largely the playbook fixing a *format* problem rather than a *chaos* problem. We discuss this caveat in §5.3.

A twelfth model (`gpt-oss-20b`) is excluded from comparative analysis because of a decoder-level failure at high chaos rates; details and rationale in §3.6.

## 1.4 Roadmap

§2 places the work in context. §3 describes the task, the playbook, the chaos rig and the model roster. §4 is the empirical core (Figs 1–8). §5 discusses caveats, threats to validity and practical implications. §6 closes with future directions. All figures and tables can be regenerated from the released data by running `python scripts/generate_paper_figures.py`.
