**Table 2 — Model runtime details.**

Per-model model identifier, runtime, protocols swept, and sample size. Quantisation for local models follows LM Studio's default at the time of the experiment (typically `GGUF Q4_K_M` for ≤14 B models and `GGUF Q4_0` for larger MoE checkpoints); the exact per-model quantisation is recorded in each `experiments/<model>/experiment.yaml` artefact alongside the LM Studio model identifier.

| Model (paper) | Vendor model ID | Runtime | Protocols | N / arm | Reasoning |
|---|---|---|---|---:|---|
| qwen3.5 0.8 B | `qwen3.5-0.8b` | LM&nbsp;Studio&nbsp;(local) | HTTP | 200 | — |
| qwen3.5 2 B | `qwen3.5-2b` | LM&nbsp;Studio&nbsp;(local) | HTTP | 200 | — |
| Gemma 4 E2B | `google/gemma-4-e2b` | LM&nbsp;Studio&nbsp;(local) | HTTP | 200 | — |
| Gemma 4 E4B | `google/gemma-4-e4b` | LM&nbsp;Studio&nbsp;(local) | HTTP | 200 | — |
| qwen3.5 4 B | `qwen3.5-4b` | LM&nbsp;Studio&nbsp;(local) | HTTP | 200 | — |
| Nemotron 3 Nano 4 B (hybrid Mamba2-Transformer) | `nvidia/nemotron-3-nano-4b` | LM&nbsp;Studio&nbsp;(local) | HTTP | 200 | think (default) |
| qwen3.5 9 B | `qwen/qwen3.5-9b` | LM&nbsp;Studio&nbsp;(local) | HTTP | 200 | — |
| qwen3.5 9 B distilled | `flipradio/qwen3.5-9b-distill`¹ | LM&nbsp;Studio&nbsp;(local) | HTTP | 200 | inherited (teacher) |
| Ministral 14 B | `mistralai/ministral-3-14b-reasoning` | LM&nbsp;Studio&nbsp;(local) | HTTP, MCP, A2A | 200 | think (default) |
| Gemma 4 26 B (MoE) | `gemma-4-26b-a4b-it` | LM&nbsp;Studio&nbsp;(local) | HTTP, MCP, A2A | 200 | — |
| GLM 4.5 | `glm-4.5` | cloud (z.ai API) | HTTP, MCP, A2A × think/nothink | 600 | toggleable |
| gpt-oss-20b (excluded) | `openai/gpt-oss-20b` | LM&nbsp;Studio&nbsp;(local) | HTTP | 50 | think (default) |

¹ Full LM Studio identifier: `flipradio_qwen_3.5_9b_deepseek_v4_flash_distillation` (community distillation of qwen3.5 9 B with DeepSeek-V4-Flash as teacher; abbreviated in the table for readability).

**Sampling parameters (all cells)**: `temperature = 0.2`; per-run seed 2026 + 1000·*k* + *j* (§3.2), used by the chaos proxy and passed to the model API as its sampling seed; recorded per row.

**Local hardware**: LM Studio served from a Windows 11 / Intel Core i5-12400F (12 threads) / 128 GB RAM / NVIDIA RTX 3060 (~4 GB visible VRAM) workstation. Wall-time numbers in §4.7 should be read as comparisons within this study, not as absolute deployment estimates.

**Cloud cell (GLM 4.5)**: served via z.ai API, `glm-4.5` endpoint, same `temperature = 0.2` and per-run seed. Reasoning toggled via the API's `thinking_mode` parameter.
