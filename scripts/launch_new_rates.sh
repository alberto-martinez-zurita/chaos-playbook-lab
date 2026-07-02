#!/usr/bin/env bash
# Launch 0.15/0.20 rates for combos as soon as their base run finishes.
# Watches CSV row counts and fires when a combo hits its target.

set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

PYTHON="$ROOT/.venv/Scripts/python"

# Combos to extend with new rates (target = 1600 = 8 rates × 100 × 2 agents)
declare -A COMBOS=(
    ["mcp_glm45_nothink"]="--model glm-4.5 --protocol mcp --no-thinking"
    ["a2a_glm45_nothink"]="--model glm-4.5 --protocol a2a --no-thinking"
    ["http_glm45_nothink"]="--model glm-4.5 --protocol http --no-thinking"
    ["mcp_glm45"]="--model glm-4.5 --protocol mcp"
    ["http_glm45"]="--model glm-4.5 --protocol http"
)

TARGET_BASE=1200   # rows needed before launching new rates
TARGET_FINAL=1600  # rows after adding 0.15/0.20

declare -A LAUNCHED=()

count_rows() {
    local csv="$ROOT/reports/parametric_experiments/run_paper_$1/raw_results.csv"
    if [[ -f "$csv" ]]; then
        echo $(( $(wc -l < "$csv") - 1 ))
    else
        echo 0
    fi
}

echo "=== Watcher: waiting for base runs to complete, then launching 0.15/0.20 ==="
echo "=== Target: ${TARGET_BASE} rows base → launch → ${TARGET_FINAL} rows final ==="

while true; do
    all_done=true
    for combo in "${!COMBOS[@]}"; do
        rows=$(count_rows "$combo")

        # Already launched new rates for this combo
        if [[ -n "${LAUNCHED[$combo]:-}" ]]; then
            if (( rows >= TARGET_FINAL )); then
                echo "[$(date +%H:%M:%S)] ✓ $combo COMPLETE: $rows/$TARGET_FINAL"
            fi
            continue
        fi

        # Base run not done yet
        if (( rows < TARGET_BASE )); then
            echo "[$(date +%H:%M:%S)]   $combo: $rows/$TARGET_BASE (waiting)"
            all_done=false
            continue
        fi

        # Base run done — launch new rates!
        echo "[$(date +%H:%M:%S)] → $combo: $rows rows — LAUNCHING 0.15/0.20"
        PYTHONPATH=src $PYTHON scripts/run_paper_multimodel.py \
            ${COMBOS[$combo]} \
            --experiments-per-rate 100 \
            > "$ROOT/reports/paper/launch_${combo}_newrates.log" 2>&1 &
        LAUNCHED[$combo]=$!
        echo "[$(date +%H:%M:%S)]   PID: ${LAUNCHED[$combo]}"
    done

    # Check if all launched combos are also complete
    remaining=0
    for combo in "${!COMBOS[@]}"; do
        rows=$(count_rows "$combo")
        if (( rows < TARGET_FINAL )); then
            remaining=$(( remaining + 1 ))
        fi
    done

    if (( remaining == 0 )); then
        echo ""
        echo "=== ALL COMBOS COMPLETE ==="
        break
    fi

    sleep 30
done
