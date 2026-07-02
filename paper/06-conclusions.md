# 6 Conclusions

## 6.1 What we showed

We treated chaos engineering as a scientific instrument and used it to map the reliability surface of LLM agents across **eleven open and frontier models** (0.8 B → 355 B), three architecture families (dense, MoE, MatFormer), three transport protocols (HTTP, MCP, A2A), two reasoning toggles (think / nothink) and ten failure rates from 0 % to 30 %, totalling **128.0 K active agent runs**. For each model we ran a paired A/B comparison between an unguided agent and the same agent under a small structured **recovery playbook**.

Three findings stand:

1. **The playbook helps and never harms.** Median Δ(pb − nopb) over the **functioning roster** (n = 9, excluding the capacity-floor and structural-rescue cases) is +24 pp at chaos = 10 % and +43.5 pp at chaos = 30 %; the `pb` arm of the upper active roster (qwen3.5 4 B and above) clusters between 86 % and 99 % at every chaos rate we tested.
2. **The benefit is non-monotonic in capability — the hump.** A 0.8 B model is at the capacity floor (cannot follow the task at all), 4 B–14 B models gain the most, the frontier saturates earlier as the unguided model approaches the playbook's ceiling.
3. **The cost is bounded and predictable** — about +42 % tokens on average and less than one extra LLM turn (≈ +0.57 calls per run), with comparable wall time. There is no model in the roster where the playbook is the wrong choice.

We also documented two qwen caveats (a capacity floor at qwen3.5 0.8 B and a structural-rescue artefact at qwen3.5 2 B) and showed that the playbook generalises across HTTP / MCP / A2A.

## 6.2 What we did not show

To set expectations:

- We did not measure *task generalisation* beyond the four-step structured-tool-use workflow. Other task families (long-horizon planning, retrieval-heavy QA, tool composition under ambiguity) may exhibit different shapes.
- We did not vary the **content** of the playbook. We do not yet know how much of the gap is attributable to the specific recovery rules vs the act of providing any recovery scaffolding.
- We did not test **bursty** or **correlated** chaos. The rig is uniform-random per call.
- We did not inject **silently corrupted payloads** (dropped fields, swapped types, truncated JSON). Every fault in this campaign was explicitly signalled to the agent; robustness to quiet corruption — an axis the engine's payload-corruption library supports — is left unexercised here.
- We did not run **multi-agent collusion** or **adversarial-environment** scenarios, which sit on a separate axis from the operational chaos studied here.

## 6.3 What we recommend doing next

The experimental campaign behind this paper is closed: ten local-roster cells are at *N* = 200 and the frontier cell (GLM 4.5) at *N* = 600, giving Wilson 95 % CIs in the figures we publish. The directions below are *follow-up work*, framed as separate studies rather than open tasks of this paper; we list them in rough order of value-per-effort.

1. **A "schema-only" control arm** to disentangle structural rescue from chaos rescue at the small-model end (qwen3.5 2 B and below). Same model, same task, same prompt skeleton, plus an explicit JSON schema. Closes the §5.3 caveat numerically.
2. **A "bad playbook" control arm** to measure how much of the gap is content-driven. The hypothesis is that a deliberately misleading playbook should hurt and a content-free recovery template should help less than the real one. If neither holds, the contribution narrative shifts toward "any recovery scaffolding works".
3. **More reasoning-toggle pairs.** GLM 4.5 is a single data point. Adding qwen3.5 14 B (think/nothink) and a Mistral reasoning-pair would let us replicate Fig 5 across families.
4. **A targeted distillation ablation.** The community-distilled qwen3.5 9 B is uniformly above the original on `nopb` across every chaos rate in our sweep (§4.6), but the distilled variant emits zero `reasoning_tokens` per turn, so we cannot attribute the gain to inherited deliberation. A controlled pair with matched compute budgets and matched system-prompt shapes would identify the mechanism. Extending the small-model cells (0.8 B / 2 B) to MCP and A2A would also test whether the structural-rescue artefact (§5.3) is protocol-specific.
5. **Burst-mode chaos.** Add a Poisson-burst fault scheduler to the rig and re-sweep the active roster at a single chaos rate. Hypothesis: the playbook helps more under burstiness because it makes recovery deterministic rather than emergent.
6. **A paired hardware-cost analysis** (joules per run, GPU-seconds per run) to complement the token/wall-time accounting in §4.7.
7. **Public dashboard.** All paper figures should be served live from the released CSVs so a reader can reslice the data interactively. This is a project-side deliverable rather than a paper one.

## 6.4 Closing remark

The result we find most interesting is not that the playbook works — it is that the *shape* of where it works is non-trivial. Recovery scaffolding extracts the most reliability from the band of models *just below* the frontier, not from the largest models money can buy. For a practitioner who does not have a research budget, this is the band where the playbook is worth measuring.

The chaos rig and the playbook prompts are released as open source under the same repository as this paper. The 128.0 K-run dataset is released as raw CSVs under `experiments/` (plus 800 appendix traces from the excluded model, see §3.6). Reproducing every figure in this paper from those CSVs is one shell command. We hope the rig is useful, the dataset is more useful, and the methodology is the most useful of the three.
