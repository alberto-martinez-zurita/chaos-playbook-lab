#!/usr/bin/env bash
# GLM-4.5 top-up to 600/variant/rate (72K target).
# Launches 4 blocks in parallel, staggered 5 min apart.
# Resume-safe: skips already-completed rows.

set -uo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

PYTHON="$ROOT/.venv/Scripts/python"
SCRIPT="$ROOT/scripts/run_experiment.py"
CONFIG="$ROOT/experiments/glm45"
LOG_DIR="$ROOT/experiments/glm45/logs"
STAGGER=300

mkdir -p "$LOG_DIR"

launch() {
    local label="$1"; local protocol="$2"; local mode="$3"
    local stamp; stamp=$(date +%Y%m%d_%H%M%S)
    local log="$LOG_DIR/topup_${label}_${stamp}.log"

    echo "[$(date +%H:%M:%S)] Launching $label (protocol=$protocol mode=$mode) -> $log"
    PYTHONPATH=src "$PYTHON" "$SCRIPT" \
        --config "$CONFIG" \
        --protocol "$protocol" \
        --thinking-mode "$mode" \
        > "$log" 2>&1 &
    local pid=$!
    echo "  PID: $pid"
}

echo "============================================================"
echo "  GLM-4.5 top-up 600/variant/rate  ($(date))"
echo "  4 blocks, staggered ${STAGGER}s"
echo "============================================================"

launch "http_think"   http  think
sleep $STAGGER

launch "mcp_think"    mcp   think
sleep $STAGGER

launch "a2a_think"    a2a   think
sleep $STAGGER

launch "http_nothink" http  nothink

echo "============================================================"
echo "  ALL 4 LAUNCHED  ($(date))"
echo "  Waiting for completion..."
echo "============================================================"
wait
echo "[$(date +%H:%M:%S)] ALL DONE"
