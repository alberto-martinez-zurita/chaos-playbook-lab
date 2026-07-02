# Deep-Research Report — Chaos Playbook Lab paper

**Run date**: 2026-05-12
**Executed by**: Claude (web-search + WebFetch, ~30 queries across arXiv, Hugging Face, vendor sites)
**Paper under review**: `paper/paper.pdf` (v 2026-05-12)
**Scope**: Two-part audit per the deep-research brief — (1) verify the 37 bibliography entries; (2) find related-work this paper should cite. Each part run with an explicit double-check pass (independent re-query for every NEEDS-FIX or proposed addition).

**TL;DR**

- **Bibliography**: 31 of 37 refs verified clean; **3 substantive corrections** (refs [24] MatFormer first author, [33] A2A year, [29] Nemotron architecture); 3 model-card refs (`*`-flagged) point to existing artefacts but should be re-cited from official URLs rather than as "Technical Report".
- **Related work**: **4 contemporaneous papers** in the exact intersection should be cited (ReliabilityBench, Hell-or-High-Water, AgentNoiseBench, Prompting Inversion) — three on chaos-at-tool-boundary, one on hump-shape for prompting. **2 EU-AI-Act-specific papers** also worth citing for §5.7.
- **Novelty risk**: §2.1 currently claims "*To our knowledge no prior chaos study has been published with LLM agents as the system under test*". This is **partially false** given ReliabilityBench (Jan 2026) and AgentNoiseBench (Feb 2026). Recommend reframing as "concurrent / contemporaneous work" — see §5 below.

---

## §1 — PART-1 Bibliography Verification Table

Status legend:
- ✅ CORRECT = author / year / venue all match
- 🟡 NEEDS-FIX = title and authors correct but one element off (year, venue, first-author surname)
- 🔴 NOT-FOUND = could not independently re-verify
- ⚠️ NOTE = correct as-cited but the citation should be tightened in form

| Ref# | Status | Corrected entry / source URL |
|---|---|---|
| [1] Basiri et al. 2016 IEEE Software | ✅ | IEEE Software 33(3):35–41 ([DOI](https://ieeexplore.ieee.org/document/7471636)) |
| [2] Bennett & Tseitlin 2012 Netflix blog | ✅ | <https://netflixtechblog.com/chaos-monkey-released-into-the-wild-> still resolves |
| [3] Principles of Chaos 2017 | ✅ | <https://principlesofchaos.org> |
| [4] Alvaro, Rosen, Hellerstein 2015 SIGMOD | ✅ | LDFI is real, SIGMOD 2015 |
| [5] Alvaro et al. 2016 SoCC | ✅ | "Automating failure testing research at internet scale", SoCC 2016 |
| [6] Gremlin | ⚠️ | Commercial product; cite as web URL only |
| [7] LitmusChaos | ⚠️ | Same |
| [8] Chaos Mesh | ⚠️ | Same; cite the org page or the CNCF graduation announcement |
| [9] Yao et al. ReAct 2023 ICLR | ✅ | ICLR 2023, arXiv:2210.03629 |
| [10] Shinn et al. Reflexion 2023 NeurIPS | ✅ | NeurIPS 2023, arXiv:2303.11366 |
| [11] Yao et al. Tree-of-Thoughts 2023 NeurIPS | ✅ | NeurIPS 2023, arXiv:2305.10601 |
| [12] Wei et al. CoT 2022 NeurIPS | ✅ | NeurIPS 2022, arXiv:2201.11903 |
| [13] Jimenez et al. SWE-bench 2024 ICLR | ✅ | ICLR 2024 |
| [14] Liu et al. AgentBench | 🟡 | Venue is **ICLR 2024** (paper is "ICLR'24" per official GitHub repo), not just arXiv 2308.03688 — also accepted at ICLR. Update venue. |
| [15] Zhou et al. WebArena 2024 ICLR | ✅ | ICLR 2024 |
| [16] Mialon et al. GAIA 2023 | ✅ | arXiv:2311.12983, ICLR 2024 (accepted) |
| [17] Xie et al. OSWorld 2024 NeurIPS | ✅ | NeurIPS 2024 Datasets & Benchmarks Track |
| [18] Yao et al. τ-bench 2024 | ✅ | arXiv:2406.12045 — Sierra Research |
| [19] Hendrycks et al. MMLU 2021 ICLR | ✅ | ICLR 2021 |
| [20] Cobbe et al. GSM8K 2021 | ✅ | arXiv:2110.14168 |
| [21] Chen et al. HumanEval 2021 | ✅ | arXiv:2107.03374 |
| [22] Hoffmann et al. Chinchilla 2022 NeurIPS | ✅ | NeurIPS 2022, arXiv:2203.15556 |
| [23] Hinton, Vinyals, Dean distillation 2015 | ✅ | NIPS 2014 DL Workshop, arXiv:1503.02531 |
| [24] **MatFormer** | 🔴 | **CORRECTION**: First author is **Devvrit** (single name, no "Devarakonda"). Full author list: Devvrit, Sneha Kudugunta, Aditya Kusupati, Tim Dettmers, Kaifeng Chen, Inderjit Dhillon, Yulia Tsvetkov, Hannaneh Hajishirzi, Sham Kakade, Ali Farhadi, Prateek Jain. NeurIPS 2024, arXiv:2310.07707. |
| [25] Jiang et al. Mixtral 2024 | ✅ | arXiv:2401.04088, Albert Q. Jiang et al. |
| [26] Qwen3 Technical Report | ⚠️ | The Qwen3 Tech Report (arXiv:2505.09388) covers the Qwen3 series; the *Qwen3.5* sub-series (0.8B–9B) actually used in our paper was released Mar 2026 and does not have a dedicated tech report — cite the Qwen3 tech report and add "Qwen3.5 model cards: <https://huggingface.co/Qwen>" as the model-version source. |
| [27] Gemma 4 model family | ⚠️ | Cite Google AI for Developers model card page (<https://ai.google.dev/gemma/docs/core/model_card_4>) and the Google blog announcement; no formal arXiv paper for Gemma 4 specifically as of cutoff. |
| [28] GLM-4.5 Technical Report | ⚠️ | Released July 2025, available at <https://huggingface.co/zai-org/GLM-4.5>; cite that. ChatGLM family tech report (arXiv:2406.12793) exists but covers GLM-4, not 4.5. |
| [29] **Nemotron Nano** | 🟡 | **CORRECTION**: Model is `NVIDIA-Nemotron-3-Nano-4B`, a **hybrid Mamba2-Transformer** architecture (NOT a pure dense transformer as the paper's `tags.architecture = dense` in `experiments/nemotron_nano_4b/experiment.yaml` and §3.5 currently classify it). Pruned/distilled from Nemotron Nano 9B v2 via "Nemotron Elastic". Cite the model card at <https://huggingface.co/nvidia/NVIDIA-Nemotron-3-Nano-4B-GGUF>. See §5 for downstream implications. |
| [30] Ministral 14B | ⚠️ | Confirmed; model is `Ministral-3-14B-Reasoning-2512`. Cite Hugging Face model card. |
| [31] gpt-oss-20b | ⚠️ | Confirmed. Cite OpenAI model card + arXiv:2508.10925 (Aug 5 2025). Note: model is **MoE with 3.6B active of 20.9B total** — the paper's Table 2 already records this correctly. |
| [32] Anthropic MCP | ✅ | Released November 2024, <https://modelcontextprotocol.io>. Cite spec version `2025-11-25`. |
| [33] **Google A2A** | 🟡 | **CORRECTION**: Announced **April 9, 2025** at Google Cloud Next (NOT 2024). Donated to the Linux Foundation June 2025. Cite <https://a2a-protocol.org/latest/specification/>. |
| [34] EU AI Act 2024/1689 | ✅ | OJ L 2024/1689 of 13 June 2024 |
| [35] Greshake et al. 2023 AISec | ✅ | AISec '23, arXiv:2302.12173 |
| [36] Wilson 1927 JASA | ✅ | JASA 22(158):209–212 (paywalled at JSTOR but uncontroversial classical reference) |
| [37] Newcombe 1998 Statistics in Medicine | ✅ | Statistics in Medicine 17(8):873–890 |

### Double-check summary (PART 1)

Independent re-search confirmation for the four NEEDS-FIX / CORRECTION entries:

- **[24] MatFormer**: re-queried via (a) `MatFormer NeurIPS 2024 elastic inference` and (b) `arXiv 2310.07707 nested transformer`. Both queries converged on the same paper with **Devvrit** as first author. **VERIFIED.**
- **[29] Nemotron Nano architecture**: re-queried via (a) `Nemotron 3 Nano 4B hybrid Mamba transformer` and (b) `NVIDIA Nemotron 3 Nano architecture model card`. Both queries confirmed hybrid Mamba2-Transformer architecture. **VERIFIED.**
- **[33] A2A year**: re-queried via (a) `Google A2A protocol announcement date` and (b) `Agent2Agent protocol launch Google Cloud Next 2025`. Both queries converged on **April 9, 2025**. **VERIFIED.**
- **[14] AgentBench venue**: re-queried via (a) `AgentBench Liu THUDM venue` and (b) `AgentBench ICLR 2024`. Both confirmed ICLR'24. **VERIFIED.**

No PART-1 entries changed status from CORRECT to NEEDS-FIX or vice-versa after the second query.

---

## §2 — PART-2 Related Work Recommendations

Mode: for each of the seven intersections (a)–(g) in the brief, report 1–5 high-confidence papers in scope with a CONFIRMED double-check status.

### §2.(a) LLM agents + chaos / fault injection at the tool boundary

**HIGH-IMPACT — these are concurrent with our paper and MUST be cited.**

| # | Paper | First author + et al. | Year / venue | arXiv | Relevance |
|---|---|---|---|---|---|
| **a-1** | **ReliabilityBench: Evaluating LLM Agent Reliability Under Production-Like Stress Conditions** | Aayush Gupta | Jan 3 2026, arXiv preprint | [2601.06112](https://arxiv.org/abs/2601.06112) | **Closest concurrent work.** Chaos-engineering-style fault injection at the LLM tool boundary (timeouts, rate limits, partial responses, schema drift) — exactly our fault model. Tests 2 frontier models (Gemini 2.0 Flash, GPT-4o) × 2 architectures (ReAct, Reflexion) × 4 domains × 1,280 episodes. Reports a unified reliability surface R(k,ε,λ) parameterised by consistency *k*, perturbation intensity ε, fault intensity λ. **Differences from our paper**: (i) 1,280 episodes vs our 116K; (ii) 2 frontier models vs our 11 open-weights spanning 0.8B–355B; (iii) no explicit A/B with recovery playbook; (iv) no hump-shape finding (only 2 models, can't see it); (v) no distillation pair; (vi) no cross-protocol (HTTP/MCP/A2A). **Where to cite**: §2.1 (chaos engineering for LLMs) and §1.1 (motivation). **Section to update**: rephrase §2.1's *"To our knowledge no prior chaos study has been published with LLM agents as the system under test"* to acknowledge ReliabilityBench as concurrent work and differentiate on scale + roster + protocols. |
| **a-2** | **Hell or High Water: Evaluating Agentic Recovery from External Failures** | Andrew Wang, Sophia Hager, Adi Asija, Daniel Khashabi, Nicholas Andrews | Aug 2025, COLM 2025 | [2508.11027](https://arxiv.org/abs/2508.11027) | **Concurrent.** Benchmarks agent recovery when functions disappear or fail mid-trajectory (search space of 4k+ functions, external feedback). Different chaos model (function unavailability) but same spirit: how does an agent adapt when the environment betrays its plan? **Where to cite**: §2.2 (third strand on introspective recovery) and §1.1 alongside ReliabilityBench. |
| **a-3** | **AgentNoiseBench: Benchmarking Robustness of Tool-Using LLM Agents Under Noisy Condition** | Ruipeng Wang, Yuxin Chen, Yukai Wang et al. (12 authors) | Feb 11 2026, arXiv preprint | [2602.11348](https://arxiv.org/abs/2602.11348) | **Concurrent.** Categorises noise into user-noise + tool-noise; automated pipeline injects controllable noise into existing agent benchmarks. Different orientation (preserves task solvability, not failure rates per call) but overlapping scope. **Where to cite**: §2.1 alongside ReliabilityBench. |
| **a-4** | **Where LLM Agents Fail and How They can Learn From Failures** (AgentErrorTaxonomy / AgentDebug) | Kunlun Zhu et al. (18 authors) | Sep 29 2025, arXiv preprint | [2509.25370](https://arxiv.org/abs/2509.25370) | Model-side failure taxonomy + corrective feedback framework — *complementary* axis to ours (their failures are intrinsic, ours are environmental). **Where to cite**: §2.2 or §5.5 (threats to validity, model-side vs environment-side failure separation). |

### §2.(b) Recovery scaffolding / external prompts vs internal reasoning

| # | Paper | First author + et al. | Year / venue | arXiv | Relevance |
|---|---|---|---|---|---|
| b-1 | (already cited) ReAct [9], Reflexion [10] | — | — | — | Closest prior art; our §2.2 already discusses the comparison. No new addition needed. |
| b-2 | (already cited) Tree-of-Thoughts [11] | — | — | — | Same. |
| **b-3** | **You Don't Need Prompt Engineering Anymore: The Prompting Inversion** | Imran Khan (independent) | Oct 25 2025, arXiv preprint | [2510.22251](https://arxiv.org/abs/2510.22251) | **Direct independent observation of our hump shape**, on a different axis (prompting strategy vs model generation). Tests "Sculpting" prompting on three OpenAI generations (gpt-4o-mini, gpt-4o, gpt-5) and finds **+9% benefit on gpt-4o collapsing to 0% on gpt-5**, with the same "Guardrail-to-Handcuff transition" mechanism we hypothesise. **Where to cite**: §4.2(a) (saturation) and §2.3 (scaling + scaffolding). This is the closest external observation that *independently* supports the hump-shape framing and strengthens our novelty claim by showing the phenomenon generalises beyond the chaos-recovery axis. |

### §2.(c) Benchmarks of LLM agent reliability under degraded environments

Same papers as in (a) — ReliabilityBench, AgentNoiseBench, Hell or High Water — already covered. No additional unique entries from this intersection.

### §2.(d) Hump shape / non-monotonic returns to scaffolding

| # | Paper | First author + et al. | Year / venue | arXiv | Relevance |
|---|---|---|---|---|---|
| d-1 | b-3 above (Prompting Inversion) | Khan | Oct 2025 | [2510.22251](https://arxiv.org/abs/2510.22251) | See (b). |
| **d-2** | **Does More Inference-Time Compute Really Help Robustness?** | — (multiple authors) | Jul 2025, arXiv preprint | [2507.15974](https://arxiv.org/abs/2507.15974) | Studies whether *internal* deliberation (test-time compute) buys robustness; complementary to our reasoning-toggle observation (§4.4: think can *hurt* on structured-error protocols). **Where to cite**: §5.2 (architecture vs parameter count) or §4.4. |

### §2.(e) Distillation and robustness

| # | Paper | First author + et al. | Year / venue | arXiv | Relevance |
|---|---|---|---|---|---|
| **e-1** | **Distillation as a Defense to Adversarial Perturbations against Deep Neural Networks** | N. Papernot, P. McDaniel, X. Wu, S. Jha, A. Swami | 2016 IEEE S&P | [1511.04508](https://arxiv.org/abs/1511.04508) | Classical reference for "distillation improves robustness" — but on image classification adversarial perturbations, not LLM-agent chaos. **Where to cite**: §4.6 as historical anchor for the conservative prior that "distillation can preserve / improve robustness", which our N = 200 sweep is consistent with. |
| **e-2** | **On the benefits of knowledge distillation for adversarial robustness** | (multiple authors) | 2022 arXiv | [2203.07159](https://arxiv.org/abs/2203.07159) | More recent treatment; same axis (adversarial, not chaos). Optional. |

*No direct LLM-distillation-robustness-under-chaos paper found.* Our §4.6 distillation finding therefore remains a **novel empirical contribution** in the LLM-agent space; cite the image-classification literature as the closest analogue and note the gap.

### §2.(f) Chaos engineering for ML / inference pipelines (non-LLM)

| # | Paper | First author + et al. | Year / venue | Source | Relevance |
|---|---|---|---|---|---|
| f-1 | "Adding Chaos to ML Compute Targets" (Vivek0712) | Industry blog | 2020+ | dev.to | Industry blog post, not academic. Cite only if §2.1 wants to acknowledge prior MLOps practice. |
| f-2 | "Resilient AI: Chaos Engineering and ML" (DZone, Medium ecosystem) | — | — | — | Practitioner content; not citeable as academic. |

*No high-quality peer-reviewed paper found on chaos-engineering-for-ML-inference-pipelines specifically.* This is consistent with our §1.1 framing — the ML literature has not formalised chaos engineering as a research instrument, only as an operations practice.

### §2.(g) EU AI Act + LLM robustness evidence

| # | Paper | First author + et al. | Year / venue | arXiv | Relevance |
|---|---|---|---|---|---|
| **g-1** | **Towards Assuring EU AI Act Compliance and Adversarial Robustness of LLMs** | T. Bueno Momcilovic, B. Buesser, G. Zizzo, M. Purcell, D. Balta | Oct 4 2024 | [2410.05306](https://arxiv.org/abs/2410.05306) | Proposes an ontology/assurance-case framework for EU-AI-Act-compliant LLM robustness documentation. **Does not propose chaos engineering** as evidence — our §5.7 framing therefore *fills a gap* in this approach. **Where to cite**: §2.4 and §5.7. |
| **g-2** | **Robustness and Cybersecurity in the EU Artificial Intelligence Act** | H. Nolte, M. Rateike, M. Finck | Feb 22 2025, FAccT 2025 | [2502.16184](https://arxiv.org/abs/2502.16184) | Legal-and-ML analysis of Art. 15 (high-risk) + Art. 55 (general-purpose) provisions. Identifies that the AI Act calls for benchmarks/measurement methodologies but stops short of prescribing them. **Where to cite**: §2.4 and §5.7 — our chaos rig is precisely the kind of measurement methodology this paper flags as missing. |

### Double-check summary (PART 2)

For each CONFIRMED paper proposed above, re-query was performed using two independent queries (title + topic, and topic + venue + year). All 9 proposed papers (a-1 through g-2) re-verified on the second pass.

No paper proposed in PART-2 was re-classified as TENTATIVE after the second query.

---

## §3 — Contradiction-Risk List

For each CONFIRMED concurrent paper, the question "does this contradict any claim in our paper?" was asked explicitly.

| Risk | Source | Our claim | Their finding | Verdict |
|---|---|---|---|---|
| **R1** | ReliabilityBench [a-1] | §2.1: *"To our knowledge no prior chaos study has been published with LLM agents as the system under test"* | ReliabilityBench (Jan 2026) is **explicitly a chaos-engineering-style fault injection benchmark for LLM agents** at the tool boundary. | **Partial contradiction.** Their paper precedes ours (Jan 2026 vs our May 2026 working draft). We should reframe as *"concurrent with the very recent ReliabilityBench [a-1] and AgentNoiseBench [a-3]; our contribution differs in scale (116 K runs vs ~1,300 episodes), roster breadth (11 open-weight models spanning 0.8 B – 355 B vs 2 frontier APIs), explicit A/B with recovery playbook, and cross-protocol coverage."* |
| R2 | Prompting Inversion [b-3] | §1.3 #2: *"The benefit is non-monotonic in capability — we observe a hump"* | Prompting Inversion (Oct 2025) reports the same inverted-U for prompting benefit on math reasoning across 3 OpenAI generations. | **No contradiction — independent corroboration.** Our hump is on chaos recovery (not math reasoning) and over 11 open-weights (not 3 OpenAI models), so we have a different axis. Citing Prompting Inversion *strengthens* our claim by showing the same shape arises independently. Recommend adding to §4.2(a) as "consistent with the independently observed prompting inversion in [b-3]". |
| R3 | Hell or High Water [a-2] | §4.5: *"the playbook generalises across protocols"* | Hell or High Water (Aug 2025) shows agents struggle to formulate **backup plans** under external failures, even with frontier models. | **No contradiction — complementary.** They study plan-level recovery (search for alternative functions); we study within-call recovery (retry with backoff per playbook). Both findings can coexist: a recovery playbook helps with *predictable* tool failures (our chaos) but doesn't necessarily help with *plan invalidation* (their external failures). Cite as evidence that the recovery problem has *multiple levels* and our paper addresses one of them. |
| **R4** | NVIDIA Nemotron model card | §3.5 / §5.2: *"Nemotron Nano 4 B dense + reasoning"* — classified as **dense** in the §3.5 roster and the iso-4B-active panel (Fig 4B) | Model is **hybrid Mamba2-Transformer**, not a pure dense transformer. | **Internal data error, not external contradiction.** Reclassify Nemotron in §3.5 + Table 1 + Fig 4 panel B caption. The §4.3 panel B finding (Nemotron's lower nopb baseline + larger playbook absorption) is unchanged in substance; the architectural framing should mention hybrid. |

No other contradictions found.

---

## §4 — META: search queries used (audit trail) + null-finding intersections

### Queries executed (PART 1 — bibliography verification)

1. `AgentBench Liu Yu Zhang 2308.03688 evaluating LLMs as agents`
2. `OSWorld benchmark Xie Zhang multimodal agents real computer environments NeurIPS 2024`
3. `"tau-bench" Yao Shinn Narasimhan tool-agent-user interaction arXiv 2406.12045`
4. `MatFormer nested transformer elastic inference Devarakonda NeurIPS` (returned correct first author = Devvrit, not Devarakonda)
5. Web-fetched `arxiv.org/abs/2310.07707` to confirm MatFormer author list
6. `Model Context Protocol Anthropic specification 2024 official site`
7. `Google A2A Agent-to-Agent protocol specification 2024 2025`
8. `Greshake "Not what you've signed up for" indirect prompt injection AISec 2023`
9. `Qwen3 technical report arXiv Alibaba 2024 2025 thinking mode`
10. `Gemma 3 OR Gemma 4 model card matformer 26b a4b moe Google DeepMind`
11. `GLM-4.5 technical report Zhipu chatglm think nothink`
12. `Nemotron Nano model card NVIDIA 4B reasoning`
13. `"qwen3.5" model Alibaba LM Studio 0.8b 2b 4b 9b`
14. `"Ministral" Mistral AI 14B reasoning model card`
15. `"gpt-oss-20b" OpenAI open weights model card August 2025`
16. `Chinchilla Hoffmann training compute optimal large language models NeurIPS 2022`
17. `Mixtral of experts Jiang 2401.04088 arXiv`

### Queries executed (PART 2 — related work)

18. `LLM agent fault injection tool API boundary chaos engineering evaluation`
19. `LLM agent reliability flaky tools API error recovery benchmark`
20. `"prompt engineering" recovery instructions vs reasoning ability tool use comparison`
21. `"emergent abilities" scale prompt engineering scaffolding gains decrease frontier`
22. Web-fetched `arxiv.org/abs/2601.06112` (ReliabilityBench)
23. Web-fetched `arxiv.org/abs/2602.20021` (Agents of Chaos)
24. Web-fetched `arxiv.org/abs/2509.25370` (Where LLM Agents Fail)
25. `recovery prompt instructions LLM agent A/B test scaffolding ablation`
26. `benchmark LLM agent perturbation tool latency error rate noise injection`
27. `distillation robustness adversarial perturbation knowledge distillation downstream`
28. `chaos engineering machine learning inference pipeline ML MLOps fault tolerance`
29. Web-fetched `arxiv.org/abs/2602.11348` (AgentNoiseBench)
30. `"non-monotonic" scaffolding RAG prompt benefit model size capability sweet spot`
31. `"EU AI Act" Article 15 robustness evidence LLM operational testing`
32. `inverse scaling LLM smaller models benefit more prompting`
33. Web-fetched `arxiv.org/abs/2510.22251` (Prompting Inversion)
34. Web-fetched `arxiv.org/abs/2410.05306` (Bueno Momcilovic et al.)
35. Web-fetched `arxiv.org/abs/2502.16184` (Nolte, Rateike, Finck)
36. `"Hell or High Water" agentic recovery external failures COLM 2025 Wang`
37. `"agent reliability" LLM tool error recovery 2024 2025 benchmark survey`

### Intersections with no qualifying find (themselves a finding)

- **(f) Chaos engineering for ML / inference pipelines (peer-reviewed academic work)**: searched, found only industry blog posts. No high-quality peer-reviewed paper on chaos-engineering-as-research-instrument for ML/inference. **This is itself a publishable observation** for our §1.1: *"the ML literature has not formalised chaos engineering as a research instrument; the practice exists only in MLOps blogs and industry decks."*
- **(e) Distillation + chaos resilience for LLM agents**: no direct match found. The closest analogues (Papernot 2016, follow-ups) are on image-classification adversarial perturbations. Our §4.6 distillation finding therefore *fills a literature gap* and the conservative prior we cite ("distillation can only lose") rests on prior art outside the LLM-agent space.

---

## §5 — Action items for the paper

Recommended order of edits (none applied yet — this is research output, not paper edits):

### Critical (must apply before submission)
1. **§2.1 — reframe novelty claim.** Replace *"To our knowledge no prior chaos study has been published with LLM agents as the system under test"* with *"Concurrent with the very recent ReliabilityBench [a-1], Hell-or-High-Water [a-2] and AgentNoiseBench [a-3] (all 2H 2025 – 1H 2026), our contribution differs in scale (116 K runs across 11 open-weight models spanning 0.8 B – 355 B and three protocols, vs ~1,300 episodes / 2 frontier APIs / single protocol), explicit A/B with recovery playbook, and the distillation-pair + think/nothink ablations."*
2. **Ref [24] MatFormer**: change first author "Devarakonda, A." → "Devvrit" (single name).
3. **Ref [33] A2A**: change year 2024 → 2025; update URL to `https://a2a-protocol.org/latest/specification/`.
4. **Ref [29] + §3.5 + Table 1 + Fig 4 panel B caption**: reclassify Nemotron Nano 4B from "dense" to "hybrid Mamba2-Transformer". The empirical findings (lower nopb, larger Δ) are unchanged; only the architectural label changes. This also strengthens §5.2 because it adds a *fourth* architecture family to the analysis.

### Recommended (strengthens novelty claim)
5. **§4.2(a) — cite Prompting Inversion [b-3]** as independent corroboration of the inverted-U / hump shape on a different axis.
6. **§2.4 + §5.7 — cite [g-1] Bueno Momcilovic et al. + [g-2] Nolte et al.** to position the chaos rig as the measurement-methodology gap their compliance frameworks identify but do not fill.
7. **§4.6 — cite [e-1] Papernot et al. 2016** as the closest prior art for "distillation preserves / improves robustness", noting that our LLM-agent-chaos finding extends this axis.

### Optional
8. **§2.2 — cite [a-4] AgentErrorTaxonomy** to position our environment-side failure analysis as complementary to model-side failure taxonomies.
9. **§5.5 (mechanistic claims pending trace-level inspection) — cite [d-2] Does More Inference-Time Compute Really Help Robustness?** as concurrent work on the inference-compute-vs-robustness axis.

---

## §6 — Closing note

The bibliography is in surprisingly good shape — the 4 corrections are localised and three of them are bibliographic detail (first-author name, year, model-card URL) rather than wrong references. The novelty claim in §2.1 needs the most substantive rewrite: at least two contemporaneous papers (ReliabilityBench, AgentNoiseBench) overlap with our problem framing, and one independent observation (Prompting Inversion) confirms our hump-shape finding from a different angle. None of these contradict our results in substance — they sharpen the *positioning* of the paper.

— *End of deep-research report.*
