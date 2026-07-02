# 1 Introduction

## 1.1 Why chaos, why now

Agentic LLM stacks — a model orchestrating a sequence of tool calls against external systems — are no longer a research curiosity. They underpin retrieval-augmented assistants, IDE copilots, customer-support bots, ETL repairers and a growing class of business-process automation. Yet the deployment story for these stacks still rests on two implicit assumptions:

1. The model is *good enough* to recover from the kind of imperfect tool behaviour that real production environments exhibit (timeouts, malformed JSON, half-applied writes, race conditions, transient HTTP 5xx).
2. Standard benchmarks (GSM8K [20], MMLU [19], HumanEval [21], agentic suites such as τ-Bench [18] or SWE-Bench [13]) are *informative enough* about that recovery behaviour to inform model-selection and architecture decisions.

We argue both assumptions are weak. Standard benchmarks measure an agent's behaviour on a happy path. Reliability under chaos — partial failures, redelivery, drift between protocol layers — is qualitatively a different surface. It is the surface that determines whether a deployed agent compounds errors silently or recovers gracefully, and it is the surface that an SRE actually watches.

Chaos engineering [1, 3], in the Netflix / Principles-of-Chaos sense, was built precisely to probe this surface for distributed systems. Our contribution here is to **treat chaos engineering as a scientific instrument**, not a production hardening tool, and use it to expose the reliability landscape of LLM agents.

## 1.2 The instrument

We build a transparent, deterministic chaos rig (open-sourced as `chaos-engine`) that injects a controlled rate of fault into the path between the LLM agent and its tools. The faults are intentionally simple and explicitly signalled — HTTP error codes (5xx, 408/504 timeouts, 429), typed MCP errors (`timeout`, `rate_limited`, `internal_error`) and typed A2A errors (`timeout`, `task_rejected`, `partial_failure`) — and the injection mechanism is protocol-agnostic: the same seed-controlled rig design applies whether the agent talks HTTP, MCP or A2A. A single knob — the **failure rate** — sweeps from 0 % to 30 % per tool call. Around the rig we run a fixed multi-step task and an A/B comparison between two agents:

- **`nopb` (unguided)**: the model is told what tools exist and asked to complete the task. It receives no recovery instructions.
- **`pb` (playbook)**: the model is given a small structured **recovery playbook** — a few hundred tokens describing how to recognise tool failures, how to retry, how to verify, and how to give up gracefully.

Both arms run on the *same model*, the *same prompt skeleton* and the *same chaos seed schedule*. Differences in success rate, token cost and wall time are therefore attributable to the playbook itself.

## 1.3 What this paper claims

We sweep this instrument across **eleven LLMs** spanning three orders of magnitude (0.8 B → 355 B total parameters), three architecture families (dense, Mixture-of-Experts, MatFormer), two providers' reasoning modes (think / nothink toggle), and three transport protocols (HTTP, MCP, A2A). The full dataset is **128.0 K active agent runs** (plus 800 appendix runs from an excluded model, §3.6), all released as raw CSVs alongside this paper.

Three concrete contributions:

1. **The playbook generalises.** Across every active model we measure, the structured recovery playbook closes the chaos-induced failure gap. The improvement at 30 % chaos, over the **functioning roster** (n = 9 — i.e. the active roster minus the capacity-floor qwen3.5 0.8 B and the structural-rescue qwen3.5 2 B documented in §5.3), has median **+43.5 pp**; including the two caveat cases the full active-roster range is +0 pp (qwen3.5 0.8 B, capacity floor) to +67 pp (Ministral 14 B). No model is harmed by the playbook at any rate we tested.
2. **The benefit is non-monotonic in capability.** The Δ(pb − nopb) traces a hump: a 0.8 B model is below the floor (cannot follow the task at all), 4 B–26 B models gain the most, and a 355 B-parameter frontier model saturates earlier. We characterise the shape and discuss its implications for model selection.
3. **The cost is bounded and predictable.** The playbook adds 13 %–69 % more tokens per run (mean ≈ 42 %) and +0.57 extra LLM calls on average (range +0.25 to +0.98 calls / run). Wall time is broadly comparable but model-dependent — some models run *faster* with the playbook (qwen3.5 4 B: −20 %; GLM 4.5 nothink: −7 %), others moderately slower (Ministral 14 B: +27 %, Gemma 4 26 B: +43 %). This makes the playbook a reasonable default for any deployed agent that values reliability over a single-digit percentage of inference cost.

Two negative findings deserve attention:

- A **capacity floor**: qwen3.5 0.8 B fails the task at 0 % chaos in both arms. The playbook cannot rescue a model that cannot follow the original instructions.
- A **structural-rescue artefact**: qwen3.5 2 B's nopb arm scores 0 % at chaos = 0 % because the model cannot emit valid structured output for the task without explicit guidance. The +56 pp gap at chaos = 10 % is largely the playbook fixing a *format* problem rather than a *chaos* problem. We surface this caveat in §5.

A third model (`gpt-oss-20b`) is excluded from comparative analysis because it enters a `?????`-loop mode collapse at chaos ≥ 0.25; details and rationale in §3.6.

## 1.4 Roadmap

§2 places the work in context. §3 describes the task, the playbook spec, the chaos rig and the model roster. §4 is the empirical core (Figs 2–9). §5 discusses caveats, threats to validity and what the hump means for practitioners. §6 closes with future directions. All figures and tables are auto-generated from `experiments/` by `scripts/generate_paper_figures.py`; regenerating the paper graphics is one shell command.
