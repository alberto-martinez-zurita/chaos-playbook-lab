# Chaos Playbook Lab — Paper draft

Working draft of the paper *"Chaos Playbook Lab — probing LLM-agent reliability across architectures with a structured recovery playbook"* by Alberto Martínez Zurita & Alessandro Russo (target: ISSRE / ICST 2027).

## Status (2026-05-10)

The *N* = 200 top-up sweep is complete across the local roster. All eleven active models are at their final *N*:

| Model | Status |
|---|---|
| qwen3.5 0.8 B | ✓ *N* = 200 (HTTP) |
| qwen3.5 2 B   | ✓ *N* = 200 (HTTP) |
| qwen3.5 4 B   | ✓ *N* = 200 (HTTP) |
| Gemma 4 E2B   | ✓ *N* = 200 (HTTP) |
| Gemma 4 E4B   | ✓ *N* = 200 (HTTP) |
| Nemotron Nano 4 B | ✓ *N* = 200 (HTTP think) |
| qwen3.5 9 B   | ✓ *N* = 200 (HTTP) |
| qwen3.5 9 B distilled | ✓ *N* = 200 (HTTP) |
| Ministral 14 B | ✓ *N* = 200 (HTTP/MCP/A2A think) |
| Gemma 4 26 B  | ✓ *N* = 100 (HTTP/MCP/A2A) |
| GLM 4.5       | ✓ *N* = 500 (HTTP/MCP/A2A think+nothink, cloud) |

Grand total: **110,800 active runs** across 416 non-empty cells.

The paper is split into one Markdown file per section so we can iterate independently. Build the camera-ready PDF later (LaTeX or pandoc) once the prose is stable.

## Sections

| # | File | Status |
|---|---|---|
| 0 | [00-abstract.md](00-abstract.md) | draft |
| 1 | [01-introduction.md](01-introduction.md) | draft |
| 2 | [02-related-work.md](02-related-work.md) | draft |
| 3 | [03-methodology.md](03-methodology.md) | draft |
| 4 | [04-results.md](04-results.md) | draft |
| 5 | [05-discussion.md](05-discussion.md) | draft |
| 6 | [06-conclusions.md](06-conclusions.md) | draft |

## Figures

All figures live in [`figures/`](figures/) as paired SVG + PNG. They are regenerated from raw CSVs in `experiments/` by [`scripts/generate_paper_figures.py`](../scripts/generate_paper_figures.py).

| ID | File | What it shows |
|---|---|---|
| 2 | `figures/fig2_hare_tortoise.svg` | Per-model success rate (pb vs nopb) at chaos = 20 %. Shows the playbook closes the failure gap regardless of size. |
| 3 | `figures/fig3_hump.svg` | Δ (pb − nopb) at chaos = 10 % vs active parameters. Surfaces a hump: 4 B–14 B benefits most, 0.8 B is a capacity floor, frontier saturates. |
| 4 | `figures/fig4_cross_model.svg` | 2×2 grid by capability bucket (Sub-2B / 4B / 9–26B / Frontier). Each panel: SR vs chaos rate, pb vs nopb. |
| 5 | `figures/fig5_thinking.svg` | GLM 4.5 think vs nothink across HTTP / MCP / A2A. Probes whether explicit reasoning helps under chaos. |
| 6 | `figures/fig6_cross_protocol.svg` | Models with full coverage (Ministral, Gemma4-26B, GLM 4.5) across the three protocols. Tests playbook generalisation. |
| 7 | `figures/fig7_cost_of_playbook.svg` | Operational cost: tokens, wall time and LLM calls per run, nopb vs pb at chaos = 10 %. |

## Tables

Tables live in [`tables/`](tables/) as Markdown. Same regeneration pipeline.

| ID | File | What it lists |
|---|---|---|
| 1 | `tables/table1_roster.md` | Active model roster — 11 models in the comparative figures. |
| 2 | `tables/table2_excluded.md` | Excluded / partial models — appendix evidence (currently `gpt_oss_20b`). |
| — | `tables/table_runs_summary.md` | Per-model row counts in the released CSVs. |

## Data layout

The paper draws from `experiments/<model>/<model_alias>/<protocol>[_<thinking>]/rate_<R>.csv` where:
- `<model>` ∈ Table 1 / Table 2.
- `<protocol>` ∈ {`http`, `mcp`, `a2a`}.
- `<thinking>` ∈ {`think`, `nothink`} when the model exposes that toggle.
- `rate_<R>.csv` covers chaos rates `0.00, 0.01, 0.02, 0.03, 0.05, 0.10, 0.15, 0.20, 0.25, 0.30`.

Each row is one run with: `experiment_id`, `agent_type`, `outcome` ∈ {success, failure}, `duration_ms`, `steps_completed`, `failed_at`, `inconsistencies_count`, `retries`, `seed`, `failure_rate`, `llm_calls`, `input_chars`, `output_chars`, `prompt_tokens`, `completion_tokens`, `reasoning_tokens`, `steps_completed_list`.

`agent_type` encodes `<protocol>-<model>-[<thinking>-]<pb|nopb>` so the same CSV holds both arms of the A/B test.

## Regeneration

```
python scripts/generate_paper_figures.py                  # all figures + tables
python scripts/generate_paper_figures.py --figure 6,7     # subset
```
