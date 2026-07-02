#!/usr/bin/env bash
# Pass 2: N=100 sequential rerun. Skips gpt_oss_20b (LM Studio hang post-circuit-breaker).
# gpt_oss_120b was never in the roster (status: on_hold per chaos satellite).
# Resume detects existing N=50 → adds 50 more per agent per rate.
# - Sequential porque solo 1 GPU disponible
# - Order: smallest first (rapid feedback) → largest last
# - Each model: 10 rates × 50 new × 2 agents = 1000 nuevos runs

set -u

ROSTER=(
  "experiments/gemma4_e2b/experiment.yaml"           # ~2B  — fastest
  "experiments/gemma4_e4b/experiment.yaml"           # ~4B
  "experiments/qwen35_4b/experiment.yaml"            # 4B
  "experiments/nemotron_nano_4b/experiment.yaml"     # 4B
  "experiments/qwen35_9b/experiment.yaml"            # 9B
  "experiments/qwen35_9b_distilled/experiment.yaml"  # 9B distilled
  "experiments/ministral_14b/experiment.yaml"        # 14B
  "experiments/gemma4_26b/experiment.yaml"           # 26B MoE
)

PYTHON=".venv/Scripts/python"
START=$(date +%s)

for cfg in "${ROSTER[@]}"; do
  name=$(basename $(dirname "$cfg"))
  echo ""
  echo "================================================================"
  echo ">>> N=100 RERUN: $name — $(date '+%H:%M:%S')"
  echo "================================================================"
  $PYTHON scripts/run_experiment.py --config "$cfg" -n 100 --sleep-between-rates 5
  rc=$?
  if [ $rc -ne 0 ]; then
    echo "WARN: $name exited with code $rc — continuing with next model"
  fi
done

ELAPSED=$(( $(date +%s) - START ))
echo ""
echo "================================================================"
echo ">>> ALL 8 MODELS N=100 COMPLETE — total elapsed: $((ELAPSED/60)) min"
echo "================================================================"
