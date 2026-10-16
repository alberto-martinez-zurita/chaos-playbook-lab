<hr />

# Mapping LLM-agent reliability under chaos: a cross-architecture study of structured recovery playbooks

<p class="subtitle">Chaos Playbook Lab — Working Paper 1</p>

<hr />

<div class="sidestamp">Chaos Playbook Lab &middot; Working Paper 1 &middot; v1.1 &middot; October 2026</div>

<p class="author">Alberto Martínez Zurita &middot; Alessandro Russo</p>

<p class="affil">Chaos Playbook Lab</p>

<p class="date">First version: 19 May 2026 &nbsp;·&nbsp; This version: October 2026 (v1.1)</p>

<p class="availability">Code, dataset and figures: <a href="https://github.com/alberto-martinez-zurita/chaos-playbook-lab">github.com/alberto-martinez-zurita/chaos-playbook-lab</a></p>

---

# Abstract

Large language model (LLM) agents are increasingly used as autonomous executors of multi-step business workflows, yet their reliability under *operational chaos*—transient tool failures such as timeouts, rate limits and server errors—remains poorly characterised. This matters beyond engineering: the EU AI Act requires high-risk AI systems to be resilient to "errors, faults or inconsistencies" arising from their interaction with other systems (Art. 15(4)), but prescribes no method to measure it. We use **chaos engineering as a scientific instrument**—controlled, seeded fault injection at the agent–tool boundary—and report a controlled study across **eleven open and frontier LLMs** (0.8 B to 355 B parameters; dense, Per-Layer-Embedding, hybrid Mamba2–Transformer and Mixture-of-Experts architectures), three agent transport protocols (HTTP, MCP, A2A) and ten injected failure rates *p* (the per-call probability that a tool call is replaced by an explicit, transient error) from 0 % to 30 %.

For each model we run a paired A/B comparison between an unguided agent (`nopb`) and the same model executing under a short structured **recovery playbook** (`pb`) that we designed for this study (69 words for HTTP), totalling 128,000 active agent runs. The primary outcome is the **success rate** (SR, the fraction of runs that complete the four-step workflow) and its difference Δ(pb−nopb) in percentage points; secondary outcomes are tokens, LLM calls and wall time per run. Three findings emerge. **(i)** The playbook closes most of the chaos-induced failure gap: over the **functioning roster** (n = 9 models, excluding a capacity-floor model and a structural-rescue case), the median Δ at 30 % chaos is **+43.5 percentage points** (bootstrap 95 % CI over models [40.0, 55.0]); in paired exact McNemar tests with Holm correction the effect is significant in every functioning-roster HTTP cell at failure rates of 5 % and above, and no model is harmed at any rate. **(ii)** The benefit depends on capability and on the chaos rate: at 30 % chaos the mid-range models gain the most (+36.5 to +67 pp, largest at 14 B) and the frontier model gains less (+40 pp), while at 10 % chaos the gain is not monotonic in model size. We report this as an observed pattern, not a formally tested non-monotonicity. **(iii)** The cost is modest: 13 %–69 % more tokens per run (mean ≈ 42 %) and +0.57 LLM calls on average; wall time is model-dependent (−20 % to +43 %).

We also document a *capacity floor* (qwen3.5 0.8 B fails the task at 0 % chaos in both arms) and a *structural-rescue artefact* (qwen3.5 2 B succeeds at 0 % chaos only with the playbook, which supplies missing output structure). The chaos rig, playbook, the 128,800-run dataset and the analysis scripts are released as open source.

**Keywords**: chaos engineering, LLM agents, reliability, recovery playbook, MCP, A2A.
