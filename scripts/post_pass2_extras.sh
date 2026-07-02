#!/usr/bin/env bash
# Post-Pass-2 extras: 3 models that need extra runs after the main Pass 2 finishes.
# - gpt_oss_20b: Phase B regen — fills 250 holes (rate 0.20 pb + rates 0.25 + 0.30)
#                left after the GPU-contention contamination cleanup. -n 50 is correct
#                because all complete rates already have 50/agent; resume detects holes.
# - qwen35_0_8b: bring up from N=50 (already 100/rate) to N=100 (target 200/rate)
# - qwen35_2b: same as qwen35_0_8b
#
# Sequential per model — no LM Studio contention.

set -u

ROSTER=(
  "experiments/gpt_oss_20b/experiment.yaml:50"
  "experiments/qwen35_0_8b/experiment.yaml:100"
  "experiments/qwen35_2b/experiment.yaml:100"
)

PYTHON=".venv/Scripts/python"
START=$(date +%s)

for entry in "${ROSTER[@]}"; do
  cfg="${entry%%:*}"
  n="${entry##*:}"
  name=$(basename $(dirname "$cfg"))
  echo ""
  echo "================================================================"
  echo ">>> N=$n RERUN: $name — $(date '+%H:%M:%S')"
  echo "================================================================"
  $PYTHON scripts/run_experiment.py --config "$cfg" -n "$n" --sleep-between-rates 5
  rc=$?
  if [ $rc -ne 0 ]; then
    echo "WARN: $name exited with code $rc — continuing with next model"
  fi
done

ELAPSED=$(( $(date +%s) - START ))
echo ""
echo "================================================================"
echo ">>> POST-PASS-2 EXTRAS COMPLETE — total elapsed: $((ELAPSED/60)) min"
echo "================================================================"
