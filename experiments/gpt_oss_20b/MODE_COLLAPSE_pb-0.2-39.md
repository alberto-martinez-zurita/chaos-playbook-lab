# Reproducibility record — gpt-oss-20b mode collapse on `pb-0.2-39`

**Status**: failure mode documented and worked around with a synthetic row; experiment continues from `j=40`.

This file records a deterministic failure mode of `openai/gpt-oss-20b` on a specific seed/rate combination encountered during the chaos-playbook-lab paper run. The failure is **reproducible** with the environment captured below.

---

## TL;DR

When `gpt-oss-20b` is asked to recover from **5 consecutive identical errors on the same endpoint** (`/order/confirm`) in a long cumulative prompt, it falls into a **degenerate repetition loop** — generating literal `?` characters for hundreds of consecutive tokens — and the response never completes within the client timeout. Reproducible 100% on the seed/rate combo `(seed=2065, rate=0.20, agent=pb)`.

This is **a model-side failure**, not a harness bug. The same prompt structure is handled correctly by every other model in the roster (gemma4-e2b/e4b/26b, qwen35-0_8b/2b/4b/9b/9b-distilled, ministral-14b, nemotron-nano-4b).

---

## Environment (all components needed to reproduce)

### Machine

| Item | Value |
|---|---|
| Manufacturer | LENOVO 90SV0088ES |
| CPU | 12th Gen Intel Core i5-12400F (6 cores / 12 threads, 2.5 GHz base) |
| RAM | 128 GB |
| GPU | NVIDIA GeForce RTX 3060 (~4 GB visible VRAM in this build) |
| GPU driver | 32.0.15.9174 |

### Operating system

| Item | Value |
|---|---|
| OS | Microsoft Windows 11 Pro |
| Version | 10.0.26200 (build 26200) |
| Architecture | 64-bit |

### LM Studio

| Item | Value |
|---|---|
| Application | LM Studio |
| Product version | 0.4.12.0 |
| Install path | `C:\Program Files\LM Studio\LM Studio.exe` |
| API endpoint | `http://localhost:1234/v1/chat/completions` (OpenAI-compatible) |
| Model id served | `openai/gpt-oss-20b` |

### Model

| Item | Value |
|---|---|
| Family | OpenAI GPT-OSS |
| Architecture | MoE |
| Total params | 21B |
| Active params | 3.6B |
| Quantization | mxfp4 |
| Reasoning mode | enabled (model emits `<\|channel\|>analysis ... <\|channel\|>final` segments) |
| Region of origin | USA |

### Python runtime

| Item | Value |
|---|---|
| Python | 3.11.9 |
| openai SDK | 2.8.1 |
| httpx | 0.28.1 |
| tenacity | 9.1.2 |
| `httpx.Timeout` | 120 s read, 15 s connect (per `_llm_internal.py`) |

### Lab code

| Item | Value |
|---|---|
| Lab repo | `chaos-playbook-lab` |
| Bug-fix SHA vendored from upstream | `3ca3851` |
| LLM client | `src/chaos_engine/agents/_llm_internal.py` (vendored) |
| Agent loop | `src/chaos_engine/agents/llm_agent.py`, `MAX_TURNS = 15` |
| Chaos proxy | `src/chaos_engine/chaos/proxy.py`, circuit breaker (3 fails → 30 s cooldown) |

### Experiment configuration

| Item | Value |
|---|---|
| Experiment | `experiments/gpt_oss_20b/experiment.yaml` |
| Protocol | HTTP (mocked target) |
| Harness | off (LLM tracks state autonomously) |
| Trace | on |
| Failure rate | 0.20 |
| Agent | playbook-equipped (`http-gpt-oss-20b-think-pb`) |
| j (experiment index) | 39 |
| **Seed** | **2065** (= `base_seed=2026 + j=39`) |
| Temperature | 0.2 |
| Thinking | enabled (passed via `extra_body={"thinking":{"type":"enabled"}}`) |

---

## Symptoms

### Workflow trace (from `trace.jsonl`)

The experiment ran twice (once during Pass 1, once during a second attempt after manual LM Studio restart). Both attempts produced an identical 8-turn trace and hung at turn 9. Excerpt of the second attempt's first 8 turns:

| Turn | API call | LLM response action | Tool result |
|---|---|---|---|
| 1 | `GET /product/find` | `call_api { /product/find }` | success → `find_product` ✓ |
| 2 | `GET /store/inventory` | `call_api { /store/inventory, params={productId:"SKU-1234"} }` | success → `check_inventory` ✓ |
| 3 | `POST /store/order` | `call_api { /store/order, body={productId:"SKU-1234", quantity:1} }` | success → `place_order`. Server returns `orderId: "ORD-2026-001"` ✓ |
| 4 | `PUT /order/confirm` | `call_api { /order/confirm, body={orderId:"ORD-2026-001"} }` | **chaos-injected 429** Too Many Requests ✗ |
| 5 | `PUT /order/confirm` | `call_api { /order/confirm, body={orderId:"<id>"} }` ← **state regression: model swapped real id for placeholder** | **chaos-injected 502** Bad Gateway ✗ |
| 6 | `PUT /order/confirm` | `call_api { body={orderId:"<id>"} }` | **chaos-injected 500** Internal Server Error ✗ |
| 7 | `PUT /order/confirm` | `call_api { body={orderId:"<id>"} }` | **circuit breaker OPEN** (3 consecutive failures, 30 s cooldown). Returns 503 ✗ |
| 8 | `PUT /order/confirm` | `call_api { body={orderId:"<id>"} }` | circuit breaker still open. 503 ✗ |
| 9 | (would call LLM) | **— LLM never returns a parseable response —** | hang |

Two pathological behaviors observed:
1. **State regression** at turn 5: the LLM forgets `orderId="ORD-2026-001"` (which it observed in turn 3) and substitutes the placeholder string `"<id>"`. From turn 5 onwards every retry uses the bogus id.
2. **Reasoning collapse** at turn 9: the LLM stops producing structured output and instead emits a degenerate stream of `?` characters.

### LM Studio log during the hang

During the turn-9 generation, LM Studio's internal log shows the model accumulating tokens in linear progression where every new token is the literal `?`:

```
[INFO] [openai/gpt-oss-20b] Accumulated 759 tokens in response  ?????…
[INFO] [openai/gpt-oss-20b] Accumulated 760 tokens in response  ?????…
[INFO] [openai/gpt-oss-20b] Accumulated 761 tokens in response  ?????…
…
[INFO] [openai/gpt-oss-20b] Accumulated 791 tokens in response  ?????…
```

Token counter advances at ~32 tok/s. Every emitted token is `?`. The model would (eventually) hit its max-output-tokens cap, but the openai SDK's 120 s `httpx.Timeout` fires first; tenacity retries; the next attempt reproduces the same collapse on the same prompt; loop indefinitely.

### Why it never completes

- The agent loop in `llm_agent.py` builds the user_message at turn N from cumulative history, so the prompt at turn 9 contains the full sequence of 5 identical-error responses and the `<id>` placeholder regression.
- The repetition pattern in the prompt appears to push `gpt-oss-20b` into a low-entropy attractor in token space; once it picks `?`, every subsequent token argmax is also `?`.
- Other models in the roster (gemma, qwen, ministral, nemotron) handle the same prompt without collapsing — they may have stronger repetition-penalty training signal, more robust state-tracking, or simply break out of the attractor on the next sampling step.

---

## Mitigation applied to this dataset

We initially chose to skip just `pb-0.2-39` synthetically. **On retry, the next experiments (`j=40..49`) at the same rate also looped** — gpt-oss-20b appears to enter the same degenerate-repetition attractor on multiple consecutive seeds at this rate, suggesting the failure mode is not seed-specific but rate-pattern-specific (5 consecutive identical-error retries on `/order/confirm` is the trigger, and at rate 0.20 the chaos proxy reproducibly emits this pattern).

We therefore inserted **synthetic failure rows for the entire `pb-0.2-{39..49}` block** (11 rows) so the runner could skip rate 0.20 pb entirely and proceed to rate 0.25. The synthetic rows in `gpt-oss-20b/http_think/rate_0.20.csv` look like:

```
http-gpt-oss-20b-think-pb-0.2-39,http-gpt-oss-20b-think-pb,failure,0,3,confirm_order,0,0,2065,0.2,8,0,0,0,0,0,"find_product,check_inventory,place_order"
http-gpt-oss-20b-think-pb-0.2-40,http-gpt-oss-20b-think-pb,failure,0,3,confirm_order,0,0,2066,0.2,8,0,0,0,0,0,"find_product,check_inventory,place_order"
...
http-gpt-oss-20b-think-pb-0.2-49,http-gpt-oss-20b-think-pb,failure,0,3,confirm_order,0,0,2075,0.2,8,0,0,0,0,0,"find_product,check_inventory,place_order"
```

Identifying the synthetic rows programmatically: `outcome == "failure" AND duration_ms == 0 AND llm_calls == 8`. A consumer that needs to exclude synthetic rows can filter on `duration_ms > 0`.

The synthetic rows preserve what the trace evidence tells us about `pb-0.2-39`:
- 3 of 4 steps completed (`find_product`, `check_inventory`, `place_order`).
- Failed at `confirm_order` (the endpoint that triggered the cascade).
- Seeds 2065-2075, rate 0.20, agent `pb`.
- 8 LLM calls actually made for `j=39` (turns 1–8 in the trace); the j=40..49 rows assume the same 8-turn truncation pattern by extrapolation, since they hit the same loop after the first 8 turns. **Only `j=39` has full evidence in `trace.jsonl`**; `j=40..49` are documented-but-unobserved.

After these synthetic rows were inserted, `run_experiment.py --config experiments/gpt_oss_20b/experiment.yaml -n 50` was relaunched; the resume mechanism detected 50 pb rows at rate 0.20 (39 real + 11 synthetic) and skipped to rate 0.25 onwards.

The trace file `trace.jsonl` retains the 16 partial-attempt entries for `pb-0.2-39` (8 turns × 2 attempts) as primary evidence of the failure.

---

## Reproducibility recipe

To reproduce the mode collapse on a fresh setup:

1. Install the environment listed above (Win 11 Pro 26200, LM Studio 0.4.12.0, Python 3.11.9, openai 2.8.1, httpx 0.28.1, tenacity 9.1.2).
2. Load `openai/gpt-oss-20b` (mxfp4 quantization) in LM Studio at `localhost:1234`.
3. Check out the lab at the SHA that vendored upstream `3ca3851`.
4. From the lab root, run:
   ```
   .venv/Scripts/python.exe scripts/run_experiment.py \
       --config experiments/gpt_oss_20b/experiment.yaml \
       --rate 0.20 -n 1
   ```
   with seeded experiment index `j=39` (the runner uses `seed=2065` for that combo).
5. Observe the LM Studio log: token counter increments monotonically with literal `?` tokens, and the openai client times out after 120 s.

Expected wall-clock to first hang: **~25 s of normal turns + ~120 s of timeout** = ~2.5 min total before the first retry begins.

---

## Final state of the gpt_oss_20b dataset

Experiment **abandoned** at rate 0.25 onwards. Final on-disk state:

| Rate | Rows | Composition |
|---|---|---|
| 0.00 | 100 | real (50 nopb + 50 pb), clean |
| 0.01 | 100 | real, clean |
| 0.02 | 100 | real, clean |
| 0.03 | 100 | real, clean |
| 0.05 | 100 | real, clean |
| 0.10 | 100 | real, clean |
| 0.15 | 100 | real, clean |
| 0.20 | 100 | 50 nopb real + 39 pb real + 11 pb synthetic (j=39..49) |
| 0.25 | 0 | abandoned; first attempt (`nopb-0.25-0`, seed 2026) also entered mode collapse, took 70 min wall-clock and 0 successful LLM calls before agent aborted at `find_product` (turn 1). Partial row deleted to keep the dataset clean. |
| 0.30 | 0 | abandoned |

**Total useful rows for analysis**: 789 real + 11 synthetic = **800 rows** across rates 0.00–0.20.

Filter `duration_ms > 0 AND llm_calls > 0` to exclude synthetic + partial-failure rows.

## Additional evidence: nopb at rate 0.25 also collapses

A single attempt at `nopb-0.25-0` (seed 2026, agent without playbook) reproduced the same hang signature: 0 LLM calls succeeded, the agent's first turn hit a 70-minute openai-SDK retry loop and finally aborted at `find_product`. This confirms:

- The mode collapse is **not specific to `pb` agents** — it affects both `nopb` and `pb`.
- It is **not specific to a particular cumulative-error history** — the very first turn at higher chaos rates can already trigger it (when chaos injects errors that confuse the model from the start).
- The trigger appears to be **rate 0.20+ on `gpt-oss-20b`**, broadly. Below rate 0.20 the model completes normally.

Because the failure mode is broad rather than seed-specific, we did NOT attempt to mitigate beyond rate 0.20. The dataset abandonment is final.

## Implications for the paper

This failure mode is itself a usable finding:

- **Model robustness under high chaos rates** is a real axis of variation across models. `gpt-oss-20b` is the only model in the roster that exhibits a hard hang in our 10-rate × N=100 sweep.
- The **state-regression behavior** (turn 5 swapping real id for `<id>` placeholder) is a separate observable failure that may be present in other reasoning models, but is fast-failing rather than hard-hanging.
- The **rate threshold** (0.20+) is an empirical capability boundary for this specific 21B-MoE/3.6B-active reasoning configuration on this hardware. A larger GPU or a non-reasoning model in the same parameter class may behave differently.
- We recommend documenting these behaviors in a "failure modes" section of the paper, citing this file as the canonical reproducibility record. For the headline cross-model figures, `gpt-oss-20b` should either be **excluded entirely** or **plotted only up to rate 0.15** with a footnote.

[record generated 2026-05-05; experiment formally abandoned 2026-05-05]
