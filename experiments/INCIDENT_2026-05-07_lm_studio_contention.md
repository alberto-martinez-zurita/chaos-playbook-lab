# Incident report — LM Studio model-contention, 2026-05-07

**Status:** RESOLVED — affected runs excluded from active dataset, deterministic
re-execution scheduled. Full forensic provenance preserved.

**Window (local time):** 2026-05-07 23:02:22 → 23:04:30 (≈ 2 minutes 8 seconds).

## Summary

During an operator-driven experiment swap, a previous run's process supervisor
(`scripts/auto_resume.sh`) survived its `TaskStop` signal and respawned the
killed Python child. The respawn coincided with the launch of a different
model's experiment, so two `run_experiment.py` processes (nemotron and
qwen35_4b) ran concurrently, each requesting a different LM Studio model.

LM Studio's local server holds **one active model** at a time. Each request
unloaded the previously-loaded model and JIT-loaded the requested one. The
first call from each process then returned `400 Bad Request — Model unloaded`,
which the LLM client caught and retried via `tenacity`. The retry succeeded
once LM Studio finished loading. Net effect on the affected runs: inflated
`duration_ms` and altered execution conditions versus the rest of the dataset.

## How the contention was detected and bounded

1. `qwen35_4b` log lines (visible in `b2mhr2zj1.output`) showed alternating
   `200 OK` / `400 Bad Request — Model unloaded` patterns starting at
   `2026-05-07 23:02:36` and ending at `2026-05-07 23:04:12`.
2. `Win32_Process` snapshot confirmed two `python.exe` processes were running
   `run_experiment.py` simultaneously: nemotron PIDs 70404 / 84176 alongside
   qwen35_4b PIDs 75372 / 83008, plus their `auto_resume.sh` bash supervisors.
3. The contention ended once the surviving nemotron supervisors and their
   children were force-killed via `Stop-Process -Force`.

The contention window was set conservatively to `[23:02:22, 23:04:30]` — from
the qwen35_4b launch timestamp (`auto_resume.sh launch #1 at 23:02:22`) to a
~30-second margin past the last observed `400` error.

## Inclusion criterion (defined a priori, before inspecting outcomes)

> An experiment is excluded from the active dataset if and only if its
> **terminal trace event** (the event marking experiment completion) has a
> timestamp inside the contention window.

This criterion is based purely on **when** an experiment finished, not on its
outcome metrics (duration_ms, success/failure, llm_calls). It is symmetric
with the standard treatment of experimental cells affected by documented
incidents (e.g. hardware faults).

A secondary sub-rule applies to the trace file alone: trace events whose
timestamp falls inside the contention window but whose parent experiment
*also* has a later terminal event from a clean re-execution are classified as
"orphan turns from the interrupted attempt" — moved to retired, while the
clean rerun's events remain in the active trace.

## Excluded experiments

### `qwen35_4b` rate `0.00` (HTTP, default thinking)

| experiment_id                          | duration_ms | retries observed in log | reason          |
| -------------------------------------- | ----------: | :---------------------- | :-------------- |
| `http-qwen35-4b-nopb-0.0-100`          |       89274 | 4 × Model-Unloaded      | full overlap    |
| `http-qwen35-4b-nopb-0.0-101`          |       30495 | 1 × Model-Unloaded      | partial overlap |

10 trace events (5 turns × 2 experiments) moved to retired.

### `nemotron_nano_4b` rate `0.02` (HTTP, think mode)

| experiment_id                                        | duration_ms | outcome | reason                  |
| ---------------------------------------------------- | ----------: | ------- | ----------------------- |
| `http-nemotron-nano-4b-think-nopb-0.02-186`          |       68800 | failure | full overlap            |
| `http-nemotron-nano-4b-think-nopb-0.02-187`          |       40472 | success | full overlap            |

23 trace events moved to retired (events from 186 and 187 — both high
`llm_calls` runs — plus 3 orphan turns from `nopb-0.02-188`'s interrupted
attempt; that experiment's CSV row is from the clean 2026-05-08 rerun and
remains in the active dataset).

## Files produced (per affected `<protocol>` directory)

| Role                          | File                                                          |
| ----------------------------- | ------------------------------------------------------------- |
| Immutable original (verbatim) | `rate_<R>.original_2026-05-07_pre_cleanup.csv`                |
| Immutable original (verbatim) | `trace.original_2026-05-07_pre_cleanup.jsonl`                 |
| Excluded (incident evidence)  | `rate_<R>.retired_2026-05-07_contention.csv`                  |
| Excluded (incident evidence)  | `trace.retired_2026-05-07_contention.jsonl`                   |
| Active (analysis)             | `rate_<R>.csv`                                                |
| Active (analysis)             | `trace.jsonl`                                                 |

Reconstruction guarantee: `cat <active> <retired>` reproduces the original
file content (line-count verified). SHA256 hashes for all six files per
directory are recorded in
`experiments/INCIDENT_2026-05-07_lm_studio_contention.summary.json`.

## Re-execution

Affected experiments are re-executed by relaunching `auto_resume.sh` on each
model's `experiment.yaml`. The resume mechanism in
`chaos_engine.simulation.parametric` reads existing CSV rows and only runs
indices `j` whose `experiment_id` is missing, regenerating the excluded rows
from the same deterministic seeds (recorded in column `seed` of the original
CSV: 2126, 2127 for qwen35_4b; 2212, 2213 for nemotron).

Determinism-preserving properties (verified in earlier `LEVEL_A_REPRODUCIBILITY`
work in this lab):
- Same seed + same prompt + same model + temperature=0 → bit-identical token
  output, identical `experiment_id`, identical `duration_ms` modulo wall-clock
  jitter.

In other words: the re-executed rows are the rows the original experiment
*would have produced* without the contention. No data is fabricated; data is
regenerated under correct experimental conditions.

## Mitigation for future runs

1. `auto_resume.sh` was confirmed to survive `TaskStop` because the wrapper's
   loop continues after the python child exits. Future protocol when stopping
   a run: kill the bash wrapper *and* its python child, then verify via
   `Get-CimInstance Win32_Process` before launching another model.
2. Operator workflow: do not start a second model's experiment until
   `Win32_Process` reports zero `run_experiment.py` instances.

## Reproduce the cleanup

```sh
.venv/Scripts/python scripts/cleanup_2026_05_07_contention.py
```

The script is idempotent only if the originals haven't been overwritten by
fresher contamination (`shutil.copy2` would replace them). It is intended to
run **once**, on the contaminated state, after which the originals serve as
permanent forensic baselines.
