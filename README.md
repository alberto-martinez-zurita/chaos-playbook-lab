# Chaos Playbook Lab

> **Reproducibility package** for the paper *"Mapping LLM-agent reliability under chaos: a cross-architecture study of structured recovery playbooks"* (Working Paper 1, 2026). Paper, dataset, chaos rig and every script needed to regenerate every figure and table — in one repository.

We treat **chaos engineering as a scientific instrument**: a deterministic, seed-controlled proxy injects transient faults at the agent ↔ tool boundary while an LLM agent executes a four-step business workflow. For each of **11 models** (0.8 B → 355 B parameters), **3 transport protocols** (HTTP, MCP, A2A) and **10 failure rates** (0 % → 30 %), we run a paired A/B comparison between an unguided agent (`nopb`) and the same agent given a ~69-word structured **recovery playbook** (`pb`) — **128,000 active runs** (plus 800 appendix runs from an excluded model).

## Headline findings

1. **The playbook helps and never harms.** Median Δ(pb − nopb) over the functioning roster (n = 9) is **+24 pp** at 10 % chaos and **+43.5 pp** at 30 % chaos; no model is harmed at any rate tested.
2. **The benefit is non-monotonic in capability — the hump.** 4 B–14 B-active models gain the most; a 0.8 B model sits below the capacity floor; the 355 B frontier model saturates early because its unguided arm already approaches the playbook ceiling.
3. **The cost is bounded and predictable.** ≈ +42 % tokens per run on average, ≈ +0.57 extra LLM calls, model-dependent wall time.

## The paper

| Artifact | Path |
|---|---|
| Sections (Markdown sources) | [`paper/00-abstract.md`](paper/00-abstract.md) … [`paper/07-references.md`](paper/07-references.md) |
| Single-file HTML (self-contained) | `paper/mapping-llm-agent-reliability-under-chaos.html` |
| PDF | [`paper/mapping-llm-agent-reliability-under-chaos.pdf`](paper/mapping-llm-agent-reliability-under-chaos.pdf) |
| Figures (SVG + PNG) | `paper/figures/` |
| Tables (generated Markdown) | `paper/tables/` |

## Reproduce everything

Requires Python 3.11+.

```bash
pip install -r requirements.txt          # or: poetry install

# 1. Regenerate ALL paper figures (Figs 2–9) and tables from the raw CSVs — one command:
python scripts/generate_paper_figures.py

# 2. Verify the headline statistics quoted in the prose (medians, Δ CIs, sign test):
python scripts/audit_paper.py
python scripts/audit_paper_v2.py

# 3. Rebuild the paper itself (combined Markdown → HTML → PDF).
#    Needs pandoc and Chrome/Edge on PATH:
python scripts/build_paper_pdf.py
```

Every number quoted in the paper is regeneratable from the released CSVs. Figures and top-level tables are produced by `generate_paper_figures.py`; the statistical spot-checks live in the two `audit_paper*.py` scripts.

## The dataset

```
experiments/<model>/<model-tag>/<protocol>[_think|_nothink]/rate_<R>.csv
```

- **128,800 rows** across 416 non-empty cells: 12 models (11 active + `gpt_oss_20b`, excluded for mode collapse and kept as appendix evidence), N = 200 runs/arm for local models, N = 600 for the cloud frontier model (GLM 4.5).
- One row per agent run. Columns: `experiment_id, agent_type, outcome, duration_ms, steps_completed, failed_at, inconsistencies_count, retries, seed, failure_rate, llm_calls, input_chars, output_chars, prompt_tokens, completion_tokens, reasoning_tokens, steps_completed_list`.
- **Determinism**: base seed `2026`; the per-run seed is recorded in every row. `temperature = 0.2` for all cells.
- Per-turn JSONL traces (`trace.jsonl`) accompany the cells that were run with tracing enabled.
- `experiments/<model>/experiment.yaml` records the model identifier, runtime, protocols, rates and sample sizes for each cell.
- `lmstudio-logs-zips/` contains the zipped LM Studio server logs for the local-runtime campaign days.
- The whole dataset is ~30 MB of plain CSV.

## The chaos rig

`src/chaos_engine/` — the released rig (`chaos-engine`). A seed-controlled proxy draws a uniform random number per tool call and, at the configured rate, replaces the tool response with an **explicit, transient, typed fault**:

| Rig | Injected fault set |
|---|---|
| HTTP (`chaos/proxy.py`) | error status drawn uniformly from {408, 429, 500, 502, 503, 504} |
| MCP (`chaos/mcp_proxy.py`) | `timeout`, `rate_limited`, `internal_error` |
| A2A (`chaos/a2a_proxy.py`) | `timeout`, `task_rejected`, `partial_failure` |

The two arms differ **only** in whether the recovery playbook (`assets/prompts/*_playbook_guidance.txt`) is appended to the system prompt. Paired runs share the same seed schedule, so Δ(pb − nopb) is attributable to the playbook.

## Repository layout

```
paper/            # the paper: sections, combined build, HTML, PDF, figures, tables
experiments/      # raw dataset: one dir per model, one CSV per (protocol, rate)
src/chaos_engine/ # the rig: chaos proxies, agents, runner, metrics
scripts/          # figure/table generation, stats audit, paper build, experiment runner
assets/           # prompts (system + playbooks), fault catalog, model registry, OpenAPI spec
config/           # engine settings presets
tests/            # unit + integration tests (pytest)
```

## Run new experiments (optional)

The sweep runner reads an `experiment.yaml` and executes all protocol × thinking-mode combinations with resume support:

```bash
python scripts/run_experiment.py --config experiments/qwen35_9b            # full sweep
python scripts/run_experiment.py --config experiments/qwen35_9b -n 10 --rate 0.05   # quick test
```

Local models are served via LM Studio (`localhost:1234`); the cloud cell used the z.ai API (set `ZHIPUAI_API_KEY` — see `.env.template`).

## Tests

```bash
pytest tests/
```

## License

[Apache-2.0](LICENSE.md). Copyright 2026 Alberto Martínez Zurita.

## Citation

```bibtex
@techreport{martinez2026chaosplaybook,
  title  = {Mapping LLM-agent reliability under chaos: a cross-architecture
            study of structured recovery playbooks},
  author = {Mart{\'i}nez Zurita, Alberto and Russo, Alessandro},
  year   = {2026},
  type   = {Working Paper},
  number = {1},
  institution = {Chaos Playbook Lab}
}
```
