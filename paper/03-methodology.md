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

A run is **successful** if and only if the agent completes all four steps in order — each call returning a non-error response — within the run's turn budget. Anything else — an injected fault the agent never recovers from, an explicit abort, an unparseable action, or an exhausted turn budget — is recorded as `failure`, together with the exact step at which the run failed (`failed_at`) and the steps completed before that (`steps_completed`). Success therefore measures **trajectory completion under chaos**: the oracle validates the call choreography, not the semantic consistency of every field the agent carries between steps. Parameter-chaining fidelity (e.g. reusing the `order_id` from step 3 in step 4) is instructed by the prompt and recorded in the released per-turn traces, but is not part of the success predicate; per-field state-tracking accuracy is flagged as trace-level follow-up (§5.5 ix). Both arms face the same oracle, so the A/B contrast is unaffected by this choice.

## 3.2 The chaos rig

A small chaos proxy sits between the agent and the tool endpoints. For each tool call it draws a uniform random number against the configured **failure rate** *p* and, when triggered, replaces the tool response with an explicit, typed fault. Two design decisions shape the fault model of this campaign. First, every injected fault is **visible**: the agent receives an error status plus a protocol-appropriate error message, never a silently corrupted payload — the study therefore measures *recovery from detectable failures*, not *detection of corrupted data*. Second, every injected fault is **transient by design** — a fault class for which retrying is a sensible strategy. The per-rig fault sets are:

- **HTTP rig**: the response is replaced by an error whose status code is drawn uniformly from {408, 429, 500, 502, 503, 504}, with a generic error body.
- **MCP rig** (`MCPFailureType` in the released code): `timeout`, `rate_limited`, `internal_error`.
- **A2A rig** (`A2AFailureType`): `timeout`, `task_rejected`, `partial_failure`.

The released engine defines a broader catalog — six MCP-typed and six A2A-typed faults (including permanent classes such as `tool_not_found`, `invalid_params`, `context_overflow`, `agent_not_found` and `authentication_error`) plus a payload-corruption library (drop a required field, swap a field's type, truncate the payload, return an empty body) — but this campaign deliberately injects only the transient subset above. Permanent faults would contaminate the A/B comparison with unrecoverable cells, and silently corrupted payloads test detection rather than recovery; we flag silent-corruption chaos as future work (§6.2).

The proxy is fully deterministic: a single `seed = 2026` (recorded per row) and the chaos rate at the time of the call uniquely determine which calls within a run get faulted and how. Reproducing a run with the same seed and rate produces the same fault sequence. Three protocol-specific implementations of the rig exist:

- **HTTP**: classic JSON-over-HTTP REST endpoints. The proxy wraps the test Petstore.
- **MCP** (Model Context Protocol [32]): tools exposed as MCP server methods; faults are injected at the MCP envelope layer using the MCP-typed set above.
- **A2A** (Agent-to-Agent [33]): the four steps split across cooperating agents communicating over a structured message protocol; faults are injected at the inter-agent message layer using the A2A-typed set above.

All three rigs share the same injection mechanism — a seed-controlled uniform draw per tool call — the same seed schedule, and the same transient-and-explicit fault design, so cross-protocol comparisons (Fig 6) compare like with like: in every rig the agent faces a visible, retryable error at the same schedule points. The fault *vocabularies* are intrinsic to each rig (you cannot inject a 504 timeout in A2A or a `task_rejected` in HTTP) and are documented as part of each rig's catalog rather than equated across protocols.

**Playbook–rig coverage note.** The HTTP playbook in §3.3 lists exactly the six status codes the HTTP rig can inject — 408, 429, 500, 502, 503, 504 — each present in the rig's fault catalog (`assets/knowledge_base/http_error_codes.json` in the released code). The MCP and A2A playbooks likewise cover exactly the typed faults their rigs inject (§3.2). Rig and playbook are therefore fully aligned on the recoverable fault set; no abort-only ("400/401/403"-style) rules appear in either, by design — the experiments inject only recoverable faults so that A/B differences attributable to the playbook reflect *recovery behaviour*, not *fail-fast routing*. See threats to validity (§5.5 iv) for the implication of having a single playbook content.

## 3.3 The two arms

For each `(model, protocol[, thinking-mode])` cell we evaluate two agents on identical inputs:

- **`nopb` (control)**: the model receives a system prompt that names the four steps and the available tools, plus the task instance. No further guidance.
- **`pb` (treatment)**: the same prompt prefix plus a structured **recovery playbook**. The HTTP playbook fits in 69 words and is reproduced verbatim below from `assets/prompts/http_playbook_guidance.txt`; MCP and A2A variants exist with comparable length:

```
Recovery playbook — when a step fails, apply these strategies:
  - HTTP 408, 504 → retry with linear backoff (max 3 retries, 2s delay)
  - HTTP 429 → wait 5s then retry (max 3 retries)
  - HTTP 500, 502, 503 → retry with exponential backoff (max 3, 1s base)
All errors are transient — always retry before giving up.
Always retry the exact same endpoint that failed.
Only abort after exhausting all retries for a given step.
```

The playbook lists exactly the status codes the rig can inject (cf. §3.2: 408, 429, 500, 502, 503, 504) and does *not* invent recovery semantics beyond what HTTP status conventions already imply. It is a forcing function: it asks the model to recognise standard signals and respond in a standard way.

## 3.4 Sweep

For every `(model, protocol[, thinking])` cell we sweep ten failure rates:

```
0.00, 0.01, 0.02, 0.03, 0.05, 0.10, 0.15, 0.20, 0.25, 0.30
```

At each rate we run *N* paired runs per arm (the same task instances, the same seed schedule). All local-roster cells are *N* = 200 (eight dense and MatFormer models, Ministral 14 B, and Gemma 4 26 B across HTTP/MCP/A2A); the cloud frontier model (GLM 4.5) is *N* = 600 — a clean 3 × multiplier over the local-roster *N* — so that think × nothink × HTTP/MCP/A2A is well powered. Total sample: **128.0 K active runs**. Per-cell counts:

<!-- include: tables/table_runs_summary.md -->

## 3.5 Model roster

The active roster comprises eleven models spanning three orders of magnitude in total parameters and three architecture families.

<!-- include: tables/table1_roster.md -->

In short:

- **Dense Transformer**: qwen3.5 0.8 B, qwen3.5 2 B, qwen3.5 4 B, qwen3.5 9 B, a community-distilled qwen3.5 9 B variant, Ministral 14 B (with reasoning).
- **Hybrid Mamba2-Transformer**: NVIDIA Nemotron 3 Nano 4 B (with reasoning by default) — pruned and distilled from Nemotron Nano 9 B v2 via the Nemotron Elastic framework [29].
- **MatFormer**: Gemma 4 E2B (~2 B active of 5.4 B total) and Gemma 4 E4B (~4 B active of 7.5 B total).
- **MoE**: Gemma 4 26 B (4 B active of 26 B total) and GLM 4.5 (32 B active of 355 B total).

The roster intentionally repeats the 4 B active-parameter point with **four different architectures** (qwen3.5 4 B dense, Gemma 4 E4B MatFormer, Nemotron 3 Nano 4 B hybrid Mamba2-Transformer + reasoning, Gemma 4 26 B MoE with 4 B active) to support the iso-active-compute architecture comparison in Fig 4 panel B.

The roster also includes a **distillation pair** at the 9 B point and a **think/nothink toggle pair** on GLM 4.5.

### 3.5.1 Runtime and per-model identifiers

::: {.table-runtime}

<!-- include: tables/table_runtime.md -->

:::

## 3.6 Caveats and excluded model

**Capacity floor (qwen3.5 0.8 B).** This model stays in the roster (so the figures show the floor) but its `nopb` and `pb` arms both score 0 % at all rates — it cannot follow the task at chaos = 0 %. We treat it as the empirical capacity floor and discuss the implications in §5.

**Structural rescue (qwen3.5 2 B).** Its `nopb` arm scores 0 % at chaos = 0 % because the model cannot emit valid structured output without the playbook prompt. The +56 pp gap at chaos = 10 % therefore reflects a *structural rescue* (the playbook supplies missing format scaffolding) rather than purely *chaos rescue*. We retain the data point because the gap profile across rates is still informative, but flag the caveat throughout.

**Excluded model (`gpt_oss_20b`).** At chaos ≥ 0.25 the model enters a `?????`-loop mode collapse — a language-model-level decoder failure qualitatively distinct from the trajectory failures of the active roster. Rates 0.00–0.20 (800 runs) are preserved as appendix evidence under `experiments/gpt_oss_20b/`; we do not analyse this model further:

::: {.table-excluded}

<!-- include: tables/table2_excluded.md -->

:::

## 3.7 Metrics

We report:

- **Success rate (SR)**: fraction of runs that complete the four steps with semantically valid responses. CIs are Wilson 95 % [36].
- **Δ (pb − nopb)**: paired difference in success rate at a fixed rate. CIs on the difference of two independent binomials use the standard normal approximation (`diff_ci_95` in `scripts/audit_paper_v2.py`); see Newcombe [37] for exact alternatives.
- **Tokens / run**: prompt + completion tokens per run, mean. The playbook prompt itself is amortised across the run, so the per-run number captures both the larger system prompt and any extra retry turns.
- **Wall time / run**: end-to-end seconds per run, mean. Includes any retry latency the playbook introduces.
- **LLM calls / run**: number of model invocations per run, mean. Useful as a proxy for retry behaviour.
- **`steps_completed`** and **`failed_at`** (stored per row, not aggregated in the headline figures): used in §5 to characterise *where* in the trajectory each arm fails.

Every number quoted in the prose is regeneratable from the released CSVs. The figures (Figs 2–9) and the top-level tables (Table 1 — roster; Table 3 — excluded models; the runs-summary table) are auto-generated by `scripts/generate_paper_figures.py`; the headline medians and the pairwise significance checks are reproduced by `scripts/audit_paper.py` and `scripts/audit_paper_v2.py`. Table 2 (runtime details) and the inline summary tables in §4 (the per-model Δ rows at fixed chaos rates) are hand-curated from the released `experiment.yaml` artefacts and the same CSVs, traceable to the auto-generated aggregates; we do not introduce human-curated *aggregates* without a CSV-traceable source.

## 3.8 What we held constant

To make the cross-model comparison clean:

- Same seed (`2026`) and same chaos schedule per `(rate, model)` pair.
- Same per-request sampling parameters (temperature 0.2; deterministic decode where the runtime supports it).
- Same task instances (identical product / inventory queries across arms).
- Same prompt skeleton and identical playbook text per protocol; only the playbook ON/OFF flag differs between arms.
- Same trace plumbing — every run emits an identical schema row.

Variance between arms is therefore attributable to (a) the playbook prompt, (b) any retry behaviour the playbook elicits and (c) the resulting differences in the chaos schedule encountered (because retries re-roll the chaos die).
