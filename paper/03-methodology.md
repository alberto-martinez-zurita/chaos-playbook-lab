# 3 Methodology

## 3.1 The task

The system under test is an LLM agent executing a deterministic four-step business workflow modelled on the OpenAPI Petstore reference:

| # | Step | Endpoint (HTTP) | Purpose |
|---|---|---|---|
| 1 | `FIND_PRODUCT`   | `GET  /product/find`     | Resolve a product by query string. |
| 2 | `CHECK_INVENTORY`| `GET  /store/inventory`  | Confirm stock for the resolved product. |
| 3 | `PLACE_ORDER`    | `POST /store/order`      | Place the order, receive an order id. |
| 4 | `CONFIRM_ORDER`  | `PUT  /order/confirm`    | Verify the order was committed. |

The four-step shape is intentionally minimal but realistic: each step depends on the previous one (the `order_id` from step 3 is a parameter to step 4), so a failed intermediate call derails the rest of the trajectory unless the agent recognises the failure and recovers before moving on.

A run is **successful** if and only if the agent completes all four steps in order—each call returning a non-error response—within the run's turn budget. Anything else—an injected fault the agent never recovers from, an explicit abort, an unparseable action, or an exhausted turn budget—is recorded as `failure`, together with the exact step at which the run failed (`failed_at`) and the steps completed before that (`steps_completed`). Success therefore measures **trajectory completion under chaos**: the oracle validates the call choreography, not the semantic consistency of every field the agent carries between steps. Parameter-chaining fidelity (e.g. reusing the `order_id` from step 3 in step 4) is instructed by the prompt and recorded in the released per-turn traces, but is not part of the success predicate; per-field state-tracking accuracy is flagged as trace-level follow-up (§5.5 ix). Both arms face the same oracle, so the A/B contrast is unaffected by this choice.

**The agent loop.** At each turn the model receives the system prompt (task description, available tools and, in the `pb` arm, the playbook) and a single harness-generated message summarising the previous step: the call made, its status (the tool result or the injected error) and the list of steps completed so far. The model does not see the earlier conversation; the workflow state is carried by this summary. The model answers with one action: a tool call, `complete` or `abort`. A retry is the model re-issuing the call that failed; it is counted in the `retries` column. The agent has no wait action, so the backoff delays mentioned in the playbook are not executed: retries are immediate. Each run has a turn budget of 15 turns (HTTP) or 12 turns (MCP and A2A); a run that exhausts it is a failure. The released repository also contains an LLM-free deterministic agent (`agents/deterministic.py`) that executes the workflow with a fixed retry strategy; it was not run as a baseline arm in this campaign (§5.5 xi).

## 3.2 The chaos rig

A small chaos proxy sits between the agent and the tool endpoints. Each tool call is faulted with probability *p* (the configured **failure rate**), independently of other calls; when a fault is triggered, the proxy replaces the tool response with an explicit, typed fault whose type is drawn uniformly at random from the rig's fault set. Two design decisions shape the fault model of this campaign. First, every injected fault is **visible**: the agent receives an error status plus a protocol-appropriate error message, never a silently corrupted payload—the study therefore measures *recovery from detectable failures*, not *detection of corrupted data*. Second, every injected fault is **transient by design**—a fault class for which retrying is a sensible strategy. The per-rig fault sets are:

- **HTTP rig**: the response is replaced by an error whose status code is drawn uniformly from {408, 429, 500, 502, 503, 504}, with a generic error body (`chaos/proxy.py`).
- **MCP rig** (`MCPFailureType` in the released code): `timeout`, `rate_limited`, `internal_error`, drawn uniformly (`chaos/mcp_proxy.py`).
- **A2A rig** (`A2AFailureType`): `timeout`, `task_rejected`, `partial_failure`, drawn uniformly (`chaos/a2a_proxy.py`).

The released engine defines a broader catalog—six MCP-typed and six A2A-typed faults (including permanent classes such as `tool_not_found`, `invalid_params`, `context_overflow`, `agent_not_found` and `authentication_error`) plus a payload-corruption library (drop a required field, swap a field's type, truncate the payload, return an empty body)—but this campaign deliberately injects only the transient subset above. Permanent faults would contaminate the A/B comparison with unrecoverable cells, and silently corrupted payloads test detection rather than recovery; we flag silent-corruption chaos as future work (§6.2).

The proxy's random number generator is seeded per run with seed = 2026 + 1000·*k* + *j*, where *j* is the run index and *k* the position of the failure rate in the list of rates of a given launch of the runner. Both arms of a pair are launched together, so they share the seed and start from the same fault schedule; the seed is recorded in every CSV row and the same per-run seed is passed to the model API as its sampling seed. Most cells were launched one rate at a time (*k* = 0, seeds 2026 + *j*); some GLM 4.5 and Gemma 4 26 B MCP/A2A runs were collected in launches covering several rates, which gave them seed offsets of 1000·*k* (3026 + *j*, 5026 + *j*, …), and in a few of those cells the two arms were not launched together, so they are not paired run by run for every index. The paired tests of §3.7 therefore use only the HTTP cells, which are fully paired, and §5.5 (vii) uses the different offsets as a seed-robustness check. For a given seed, failure rate and sequence of tool calls, the fault sequence is reproducible. Two caveats apply. First, the *model's* output is not deterministic (sampling at temperature 0.2, §3.8, and runtime-dependent numerics), so re-running a cell on another machine reproduces the fault schedule but not necessarily every trajectory. Second, a retry is a new tool call that consumes a new random draw, so once the two arms take different actions their fault sequences diverge (§3.8). The three rigs are emulated in-process: no network transport and no official protocol SDK is involved. Three protocol-specific implementations of the rig exist:

- **HTTP**: REST-style calls (method, endpoint, parameters) answered by a mock Petstore inside the proxy, with HTTP status codes. In the HTTP rig the proxy is additionally wrapped by a **circuit breaker** that opens after three consecutive failed calls and, for the next 30 seconds of wall-clock time, answers every call with `503 Circuit Breaker Open`, then lets one probe call through; its state is reset at the start of each run. It is not present in the MCP and A2A rigs (see §5.5 xii).
- **MCP** (Model Context Protocol [31]): an emulated MCP tool interface—a tool catalogue with JSON input schemas and MCP-style results—with faults returned as the MCP-typed errors above.
- **A2A** (Agent-to-Agent [32]): each step is phrased as a task delegated to an emulated remote agent, with A2A-style task messages, and faults are returned as the A2A-typed errors above.

All three rigs share the same injection mechanism—a seeded Bernoulli draw per tool call—the same seed schedule, and the same transient-and-explicit fault design, so cross-protocol comparisons (Fig 5) share the fault mechanism: in every rig the agent faces a visible, retryable error at the same schedule points. The rigs still differ in error vocabulary, in the HTTP-only circuit breaker and in the turn budget (§5.5 xii). The fault *vocabularies* are intrinsic to each rig (you cannot inject a 504 timeout in A2A or a `task_rejected` in HTTP) and are documented as part of each rig's catalog rather than equated across protocols.

**Playbook–rig coverage note.** The HTTP playbook in §3.3 lists exactly the six status codes the HTTP rig can inject—408, 429, 500, 502, 503, 504—each present in the rig's fault catalog (`assets/knowledge_base/http_error_codes.json` in the released code). The MCP and A2A playbooks likewise cover exactly the typed faults their rigs inject (§3.2). Rig and playbook are therefore fully aligned on the recoverable fault set; no abort-only ("400/401/403"-style) rules appear in either, by design—the experiments inject only recoverable faults so that A/B differences attributable to the playbook reflect *recovery behaviour*, not *fail-fast routing*. See threats to validity (§5.5 iv) for the implication of having a single playbook content.

## 3.3 The two arms

For each `(model, protocol[, thinking-mode])` cell we evaluate two agents on identical inputs:

- **`nopb` (control)**: the model receives a system prompt that names the four steps and the available tools, plus the task instance. No further guidance.
- **`pb` (treatment)**: the same prompt prefix plus a structured **recovery playbook**, designed by the authors for this study. The HTTP playbook has 69 words and is reproduced verbatim below from `assets/prompts/http_playbook_guidance.txt`; MCP and A2A variants of comparable length use each protocol's error vocabulary:

```
Recovery playbook—when a step fails, apply these strategies:
  - HTTP 408, 504 → retry with linear backoff (max 3 retries, 2s delay)
  - HTTP 429 → wait 5s then retry (max 3 retries)
  - HTTP 500, 502, 503 → retry with exponential backoff (max 3, 1s base)
All errors are transient—always retry before giving up.
Always retry the exact same endpoint that failed.
Only abort after exhausting all retries for a given step.
```

The playbook lists exactly the status codes the rig can inject (cf. §3.2: 408, 429, 500, 502, 503, 504) and does *not* invent recovery semantics beyond what HTTP status conventions already imply. It is a forcing function: it asks the model to recognise standard signals and respond in a standard way.

The MCP and A2A playbooks (`assets/prompts/mcp_playbook_guidance.txt` and `assets/prompts/a2a_playbook_guidance.txt`) read:

```
Recovery playbook — when a tool call fails, apply these strategies:
  - timeout → retry same tool call with linear backoff (max 3 retries, 2s delay)
  - rate_limited → wait 5s then retry (max 3 retries)
  - internal_error → retry with exponential backoff (max 3, 1s base)
All errors are transient — always retry before giving up.
Always retry the exact same tool call that failed.
Only abort after exhausting all retries for a given step.
```

```
Recovery playbook — when a task delegation fails, apply these strategies:
  - timeout → retry with linear backoff (max 3 retries, 2s delay)
  - task_rejected → retry with exponential backoff (max 3, 1s base)
  - partial_failure → retry with linear backoff (max 3, 2s delay)
All errors are transient — always retry before giving up.
Always retry the exact same task delegation that failed.
Only abort after exhausting all retries for a given step.
```

## 3.4 Failure-rate sweep

We call a *sweep* the series of experiments that runs one `(model, protocol[, thinking])` configuration at each of ten failure rates:

```
0.00, 0.01, 0.02, 0.03, 0.05, 0.10, 0.15, 0.20, 0.25, 0.30
```

At each rate we run *N* paired runs per arm (the same task instance, the same seed per run index). All local-roster cells are *N* = 200 (ten models: the five qwen3.5 models, Gemma 4 E2B and E4B, Nemotron 3 Nano 4 B, Ministral 14 B across HTTP/MCP/A2A and Gemma 4 26 B across HTTP/MCP/A2A); the cloud frontier model (GLM 4.5) is *N* = 600 per arm, three times the local *N*, so that its six think/nothink × protocol cells are well powered. Total sample: **128,000 active runs**. Per-cell counts:

<!-- include: tables/table_runs_summary.md -->

## 3.5 Model roster

The active roster comprises eleven models spanning nearly three orders of magnitude in total parameters and four architecture types.

<!-- include: tables/table1_roster.md -->

In short:

- **Dense** (non-MoE): the qwen3.5 0.8 B, 2 B, 4 B and 9 B models [25] and a community-distilled qwen3.5 9 B variant, whose layers combine Gated DeltaNet linear attention with standard gated attention in a 3:1 ratio; and Ministral 14 B, a Transformer with reasoning [29].
- **Hybrid Mamba2–Transformer**: NVIDIA Nemotron 3 Nano 4 B (reasoning enabled by default; its reasoning toggle was not varied in this study), pruned and distilled from Nemotron Nano 9 B v2 via the Nemotron Elastic framework [28].
- **Per-Layer Embeddings (PLE)**: Gemma 4 E2B (~2.3 B effective of 5 B total) and Gemma 4 E4B (~4.5 B effective of 8 B total) [26]; each decoder layer has its own small token embedding, so the effective (compute) size is smaller than the total.
- **MoE**: Gemma 4 26 B (4 B active of 26 B total) and GLM 4.5 (32 B active of 355 B total).

The roster intentionally repeats the ~4 B active-parameter point with **four different architectures** (qwen3.5 4 B dense, Gemma 4 E4B PLE, Nemotron 3 Nano 4 B hybrid Mamba2–Transformer with reasoning, Gemma 4 26 B MoE with ~4 B active) to support the comparison at similar active compute in Fig 3 panel B and §5.2.

The roster also includes a **distillation pair** at the 9 B point and a **think/nothink toggle pair** on GLM 4.5.

### 3.5.1 Runtime and per-model identifiers

::: {.table-runtime}

<!-- include: tables/table_runtime.md -->

:::

## 3.6 Caveats and excluded model

**Capacity floor (qwen3.5 0.8 B).** This model stays in the roster (so the figures show the floor) but its `nopb` and `pb` arms both score 0 % at all rates—it cannot follow the task at chaos = 0 %. We treat it as the empirical capacity floor and discuss the implications in §5.

**Structural rescue (qwen3.5 2 B).** Its `nopb` arm scores 0 % at chaos = 0 % because the model cannot emit valid structured output without the playbook prompt. The +56.5 pp gap at chaos = 10 % therefore reflects a *structural rescue* (the playbook supplies missing format scaffolding) rather than purely *chaos rescue*. We retain the data point because the gap profile across rates is still informative, but flag the caveat throughout.

**Excluded model (`gpt_oss_20b`) [30].** At chaos = 0.20 the model entered a reproducible degenerate decoding loop (hundreds of consecutive `?` tokens after five identical errors on the same endpoint; seed 2065, `pb` arm), a language-model-level failure qualitatively distinct from the trajectory failures of the active roster. The case is documented with its environment in `experiments/gpt_oss_20b/MODE_COLLAPSE_pb-0.2-39.md`; that run is recorded as a synthetic failure row, and the sweep was not extended beyond 0.20. Rates 0.00–0.20 (800 runs) are preserved as appendix evidence under `experiments/gpt_oss_20b/`; we do not analyse this model further:

::: {.table-excluded}

<!-- include: tables/table2_excluded.md -->

:::

## 3.7 Metrics

We report:

- **Success rate (SR)**: fraction of runs that complete the four steps in order with non-error responses (the oracle of §3.1). CIs are Wilson 95 % [35].
- **Δ (pb − nopb)**: difference in success rate, in percentage points, between the two arms at a fixed rate. Reported CIs on Δ use the normal approximation for the difference of two proportions (`diff_ci_95` in `scripts/audit_paper_v2.py`); this treats the arms as independent and is therefore conservative for our paired design, and it can be inaccurate near 0 % or 100 %, where score-based intervals are preferable [36].
- **Paired significance**: because run *i* uses the same seed and task instance in both arms, each cell yields 200 (or 600) matched pairs. We test Δ ≠ 0 with the exact McNemar test on the discordant pairs (runs that succeed in only one arm) and control the family-wise error rate with the Holm procedure over the 81 functioning-roster HTTP cells with *p* > 0 (`scripts/paired_analysis.py`). GLM 4.5 enters this family in think mode; its nothink HTTP cells give the same picture (no run succeeds only without the playbook, and every cell from 2 % upwards is significant even under a Bonferroni bound over 81 tests).
- **Tokens / run**: prompt + completion tokens per run, mean. The playbook prompt itself is amortised across the run, so the per-run number captures both the larger system prompt and any extra retry turns.
- **Wall time / run**: end-to-end seconds per run, mean. Includes any retry latency the playbook introduces.
- **LLM calls / run**: number of model invocations per run, mean. Useful as a proxy for retry behaviour.
- **`steps_completed`** and **`failed_at`** (stored per row, not aggregated in the headline figures): used in §5 to characterise *where* in the trajectory each arm fails.

Every number quoted in the text can be recomputed from the released CSVs. The figures (Figs 1–8) and the generated tables (Table 1, roster; Table 3, excluded model; the runs-summary table) are produced by `scripts/generate_paper_figures.py`. The inline tables of §4 and the numbers quoted in the text are checked against the CSVs by `scripts/check_paper_numbers.py`, and the paired tests by `scripts/paired_analysis.py`. Table 2 (runtime details) is transcribed from the released `experiment.yaml` files.

## 3.8 What we held constant

To make the cross-model comparison clean:

- Same seed per run index in both arms (seed 2026 + 1000·*k* + *j*, §3.2), hence the same initial fault schedule.
- Same per-request sampling parameters (temperature 0.2). Decoding is therefore not deterministic: a retried call can return a different model action, and the retried tool call draws a new fault decision.
- Same task instance: every run of every cell uses one fixed task (product `SKU-1234`), so run-to-run variation comes only from the fault schedule and from model sampling; variance across task instances is not measured.
- Same prompt skeleton and identical playbook text per protocol; only the playbook ON/OFF flag differs between arms.
- Same trace plumbing—every run emits an identical schema row.

Variance between arms is therefore attributable to (a) the playbook prompt, (b) any retry behaviour the playbook elicits and (c) the resulting differences in the chaos schedule encountered (because retries re-roll the chaos die).
