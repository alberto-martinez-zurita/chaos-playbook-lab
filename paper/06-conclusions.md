# 6 Conclusions

## 6.1 What we showed

We treated chaos engineering as a scientific instrument and used it to map the reliability surface of LLM agents across **eleven open and frontier models** (0.8 B to 355 B), four architecture types (dense, Per-Layer-Embedding, hybrid Mamba2–Transformer, MoE), three transport protocols (HTTP, MCP, A2A), a think/nothink toggle and ten failure rates from 0 % to 30 %, totalling **128,000 active agent runs**. For each model we ran a paired A/B comparison between an unguided agent and the same agent under a small structured **recovery playbook**.

Three findings stand:

1. **The playbook helps and never harms.** Median Δ(pb − nopb) over the **functioning roster** (n = 9, excluding the capacity-floor and structural-rescue cases) is +24 pp at chaos = 10 % and +43.5 pp at chaos = 30 %, significant in paired exact tests in every functioning-roster HTTP cell at failure rates of 5 % and above; the `pb` arm of the models from qwen3.5 4 B upwards stays between 86 % and 100 % at every chaos rate we tested.
2. **The benefit depends on capability and on the chaos rate.** A 0.8 B model is at the capacity floor; at 30 % chaos the mid-range models gain the most and the frontier model gains less, as its unguided baseline approaches the playbook's ceiling; at 10 % chaos the gain is not monotonic in size. This pattern is observed, not formally tested.
3. **The cost is bounded and predictable**: about +42 % tokens on average and less than one extra LLM call per run (≈ +0.57), with model-dependent wall time (−20 % to +43 %). There is no model in the roster where the playbook lowers the success rate.

We also documented two qwen caveats (a capacity floor at qwen3.5 0.8 B and a structural-rescue artefact at qwen3.5 2 B) and showed that the playbook generalises across HTTP / MCP / A2A.

## 6.2 What we did not show

To set expectations:

- We did not measure *task generalisation* beyond the four-step structured-tool-use workflow. Other task families (long-horizon planning, retrieval-heavy QA, tool composition under ambiguity) may exhibit different shapes.
- We did not vary the **content** of the playbook. We do not yet know how much of the gap is attributable to the specific recovery rules vs the act of providing any recovery scaffolding.
- We did not test **bursty** or **correlated** chaos. The rig is uniform-random per call.
- We did not inject **silently corrupted payloads** (dropped fields, swapped types, truncated JSON). Every fault in this campaign was explicitly signalled to the agent; robustness to quiet corruption—an axis the engine's payload-corruption library supports—is left unexercised here.
- We did not run **multi-agent collusion** or **adversarial-environment** scenarios, which sit on a separate axis from the operational chaos studied here.

## 6.3 What we recommend doing next

The experimental campaign behind this paper is closed: ten local-roster cells are at *N* = 200 and the frontier cell (GLM 4.5) at *N* = 600, giving Wilson 95 % CIs in the figures we publish. The directions below are *follow-up work*, framed as separate studies rather than open tasks of this paper; we list them in rough order of value-per-effort.

1. **A seed-replication study**: repeat a subset of the local roster at two or three failure rates with 3–5 alternative seed bases, to measure seed-set variance directly (§5.5 vii).
2. **A "schema-only" control arm** to disentangle structural rescue from chaos rescue at the small-model end (qwen3.5 2 B and below). Same model, same task, same prompt skeleton, plus an explicit JSON schema. Closes the §5.3 caveat numerically.
3. **A "bad playbook" control arm** to measure how much of the gap is content-driven. The hypothesis is that a deliberately misleading playbook should hurt and a content-free recovery template should help less than the real one. If neither holds, the contribution narrative shifts toward "any recovery scaffolding works".
4. **More reasoning-toggle pairs.** GLM 4.5 is a single data point. Running Nemotron 3 Nano 4 B with its reasoning toggle off, and adding further think/nothink pairs, would let us replicate Fig 4 across families and separate reasoning from architecture in the ~4 B class.
5. **A targeted distillation ablation.** The community-distilled qwen3.5 9 B is uniformly above the original on `nopb` across every chaos rate in our sweep (§4.6), but the distilled variant emits zero `reasoning_tokens` per turn, so we cannot attribute the gain to inherited deliberation. A controlled pair with matched compute budgets and matched system-prompt shapes would identify the mechanism. Extending the small-model cells (0.8 B / 2 B) to MCP and A2A would also test whether the structural-rescue artefact (§5.3) is protocol-specific.
6. **Burst-mode chaos.** Add a Poisson-burst fault scheduler to the rig and re-sweep the active roster at a single chaos rate. Hypothesis: the playbook helps more under burstiness because it makes recovery deterministic rather than emergent.
7. **A paired hardware-cost analysis** (joules per run, GPU-seconds per run) to complement the token/wall-time accounting in §4.7.
8. **Public dashboard.** All paper figures should be served live from the released CSVs so a reader can reslice the data interactively. This is a project-side deliverable rather than a paper one.

## 6.4 Closing remark

At 30 % chaos, a 69-word recovery playbook raised the success rate of the functioning models from 14.5 %–57.5 % to 56 %–97 % (86 %–97 % for all but the smallest of them), at a modest and predictable cost, and in our roster it never lowered an agent's success rate. Because each run is seeded and recorded, the same sweep that measures this also produces auditable evidence of how an agent behaves when its tools fail—the kind of evidence that both reliability engineering and the EU AI Act call for and that is rarely collected today. The rig, the playbooks and the 128,800-run dataset are released so that others can rerun, extend or refute these results.

## Acknowledgements

An earlier prototype of this instrument—the *Chaos Playbook Engine*—won **first place in the Enterprise Agents track** of the Google × Kaggle *AI Agents Intensive* capstone competition (December 2025; 4,477 entries in the track among 11,500+ submissions overall). The prototype is open source at <https://github.com/alberto-martinez-zurita/chaos-playbook-engine>. The present study re-architected that prototype into the deterministic, protocol-agnostic A/B rig described in §3 and ran an entirely new experimental campaign; no result from the prototype is reused in this paper.
