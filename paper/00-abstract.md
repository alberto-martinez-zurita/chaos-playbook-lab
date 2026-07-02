<hr />

# Mapping LLM-agent reliability under chaos: a cross-architecture study of structured recovery playbooks

<p class="subtitle">Chaos Playbook Lab — Working Paper 1</p>

<hr />

<div class="sidestamp">Chaos Playbook Lab &middot; Working Paper 1 &middot; v1.0 &middot; 2 July 2026</div>

<p class="author">Alberto Martínez Zurita &middot; Alessandro Russo</p>

<p class="affil">Chaos Playbook Lab</p>

<p class="date">First version: 19 May 2026 &nbsp;·&nbsp; This version: 2 July 2026 (v1.0)</p>

<p class="availability">Code, dataset and figures: <a href="https://github.com/alberto-martinez-zurita/chaos-playbook-lab">github.com/alberto-martinez-zurita/chaos-playbook-lab</a></p>

---

# Abstract

LLM-driven agents are increasingly deployed as autonomous executors of multi-step business workflows, yet their reliability under realistic operational chaos — flaky tool calls, timeouts, transient server errors — remains poorly characterised. We treat **chaos engineering as a scientific instrument** for exposing this reliability surface, and report a controlled study across **eleven open and frontier LLMs** (0.8 B → 355 B parameters; dense, MoE and MatFormer architectures), three agent transport protocols (HTTP, MCP, A2A) and ten injected failure rates from 0 % to 30 %.

For each model we run an A/B comparison between an unguided agent (`nopb`) and the same model executing under a small structured **recovery playbook** (`pb`), totalling 128.0 K active agent runs. Three findings emerge. **(i)** The playbook closes the chaos-induced failure gap across the active roster: over the **functioning roster** (n = 9 — i.e. the active roster minus the qwen3.5 0.8 B capacity-floor case and the qwen3.5 2 B structural-rescue caveat), median Δ(pb−nopb) at 30 % chaos is **+43.5 percentage points** (bootstrap 95 % CI [40.0, 55.0]), with no model harmed by the playbook at any rate we tested. **(ii)** The benefit is *not* monotonic in capability — we observe a **hump** most cleanly at high chaos: 4 B–26 B dense and MoE models gain the most at chaos = 30 % (+36 to +67 pp, peak at 14 B), the 0.8 B floor cannot follow either arm (capacity floor), and a frontier 355 B/32 B-active model saturates earlier (+40 pp at 30 % chaos but only +14 pp at 10 %). **(iii)** Operational cost is modest and predictable — the playbook adds 13 %–69 % more tokens per run (mean ≈ 42 %) and +0.57 extra LLM calls on average; wall time is model-dependent (faster for two models, up to +43 % for the most reasoning-intensive cells).

We also document a *capacity floor* (qwen3.5 0.8 B fails the task at 0 % chaos in both arms) and a *structural-rescue artefact* (qwen3.5 2 B has nopb = 0 % at chaos = 0 % because it cannot emit valid structured output without the playbook). The chaos rig and playbook spec are released as open source.

**Keywords**: chaos engineering, LLM agents, reliability, recovery playbook, MCP, A2A.
