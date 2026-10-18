**Runs summary (rows in CSVs).**

**Grand total: 128,800 runs** across 416 non-empty cells.

_Models marked with `*` are excluded from main comparative figures (Table 3)._

## Per model

| Model | Protocols | Agent groups | Rates seen | Total rows | Min n/cell | Max n/cell |
|---|---|---|---|---|---|---|
| qwen35_0_8b | http | 2 | 10 | 4000 | 200 | 200 |
| qwen35_2b | http | 2 | 10 | 4000 | 200 | 200 |
| gemma4_e2b | http | 2 | 10 | 4000 | 200 | 200 |
| gemma4_e4b | http | 2 | 10 | 4000 | 200 | 200 |
| qwen35_4b | http | 2 | 10 | 4000 | 200 | 200 |
| nemotron_nano_4b | http | 2 | 10 | 4000 | 200 | 200 |
| qwen35_9b | http | 2 | 10 | 4000 | 200 | 200 |
| qwen35_9b_distilled | http | 2 | 10 | 4000 | 200 | 200 |
| ministral_14b | a2a, http, mcp | 2 | 10 | 12000 | 200 | 200 |
| gpt_oss_20b * | http | 2 | 8 | 800 | 50 | 50 |
| gemma4_26b | a2a, http, mcp | 2 | 10 | 12000 | 200 | 200 |
| glm45 | a2a, http, mcp | 4 | 10 | 72000 | 600 | 600 |

## By protocol

| Protocol | Runs | % |
|---|---:|---:|
| HTTP | 64,800 | 50.3% |
| A2A | 32,000 | 24.8% |
| MCP | 32,000 | 24.8% |
| **Total** | **128,800** | 100.0% |

## By reasoning mode (in protocol directory)

| Reasoning | Runs | % |
|---|---:|---:|
| think | 52,800 | 41.0% |
| n/a | 40,000 | 31.1% |
| nothink | 36,000 | 28.0% |
| **Total** | **128,800** | 100.0% |

## By playbook arm

| Arm | Runs | % |
|---|---:|---:|
| nopb | 64,400 | 50.0% |
| pb | 64,400 | 50.0% |
| **Total** | **128,800** | 100.0% |

## By family

| Family | Runs | % |
|---|---:|---:|
| glm4 | 72,000 | 55.9% |
| gemma4 | 20,000 | 15.5% |
| qwen3.5 | 20,000 | 15.5% |
| ministral3 | 12,000 | 9.3% |
| nemotron3 | 4,000 | 3.1% |
| gpt-oss | 800 | 0.6% |
| **Total** | **128,800** | 100.0% |

## By architecture

| Architecture | Runs | % |
|---|---:|---:|
| moe | 84,800 | 65.8% |
| dense | 32,000 | 24.8% |
| ple | 8,000 | 6.2% |
| hybrid_mamba2_transformer | 4,000 | 3.1% |
| **Total** | **128,800** | 100.0% |

## By total-params bucket

| Total params | Runs | % |
|---|---:|---:|
| frontier (≥30B) | 72,000 | 55.9% |
| 5–26B | 40,800 | 31.7% |
| 2–4B | 12,000 | 9.3% |
| sub-2B | 4,000 | 3.1% |
| **Total** | **128,800** | 100.0% |
