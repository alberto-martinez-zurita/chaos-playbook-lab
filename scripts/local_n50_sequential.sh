#!/usr/bin/env bash
# Sequential rerun of all 9 local models at N=50 with bug fix applied.
# - Sequential porque solo 1 GPU disponible
# - Order: smallest first (rapid feedback) → largest last
# - Resume: reuses N=5 from smoke test → adds 95 nuevos por agente por rate
# - Each model: 10 rates × 95 new × 2 agents = 1900 nuevos runs

set -u

ROSTER=(
  "experiments/gemma4_e2b/experiment.yaml"           # ~2B  — fastest
  "experiments/gemma4_e4b/experiment.yaml"           # ~4B
  "experiments/qwen35_4b/experiment.yaml"            # 4B
  "experiments/nemotron_nano_4b/experiment.yaml"     # 4B
  "experiments/qwen35_9b/experiment.yaml"            # 9B
  "experiments/qwen35_9b_distilled/experiment.yaml"  # 9B distilled
  "experiments/ministral_14b/experiment.yaml"        # 14B
  "experiments/gpt_oss_20b/experiment.yaml"          # 20B reasoning
  "experiments/gemma4_26b/experiment.yaml"           # 26B MoE
)

PYTHON=".venv/Scripts/python"
START=$(date +%s)

for cfg in "${ROSTER[@]}"; do
  name=$(basename $(dirname "$cfg"))
  echo ""
  echo "================================================================"
  echo ">>> N=50 RERUN: $name — $(date '+%H:%M:%S')"
  echo "================================================================"
  $PYTHON scripts/run_experiment.py --config "$cfg" -n 50 --sleep-between-rates 5
  rc=$?
  if [ $rc -ne 0 ]; then
    echo "WARN: $name exited with code $rc — continuing with next model"
  fi
done

ELAPSED=$(( $(date +%s) - START ))
echo ""
echo "================================================================"
echo ">>> ALL 9 MODELS N=50 COMPLETE — total elapsed: $((ELAPSED/60)) min"
echo "================================================================"
