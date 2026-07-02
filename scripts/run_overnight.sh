#!/usr/bin/env bash
# Overnight run: 10 parallel experiments, 500 nopb + 500 pb per rate.
# Resume-safe: the runner skips experiment_ids already in the CSV.
#
# Usage: bash scripts/run_overnight.sh

set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

PYTHON="$ROOT/.venv/Scripts/python"
SCRIPT="$ROOT/scripts/run_paper_multimodel.py"
LOG_DIR="$ROOT/reports/paper"
PER_RATE=500
DELAY=15

mkdir -p "$LOG_DIR"

launch() {
    local label="$1"; shift
    local log="$LOG_DIR/overnight_${label}.log"

    echo "[$(date +%H:%M:%S)] Launching: $label"
    echo "  cmd: PYTHONPATH=src $PYTHON $SCRIPT $* --experiments-per-rate $PER_RATE"

    PYTHONPATH=src $PYTHON "$SCRIPT" "$@" --experiments-per-rate $PER_RATE \
        > "$log" 2>&1 &
    local pid=$!
    echo "  PID: $pid -> $log"

    # Wait and verify no 429s
    sleep $DELAY
    local err429=$(grep -c "HTTP/1.1 429" "$log" 2>/dev/null || echo 0)
    local err500=$(grep -c "HTTP/1.1 500" "$log" 2>/dev/null || echo 0)
    local lines=$(wc -l < "$log" 2>/dev/null || echo 0)

    if [ "$err429" -gt 0 ]; then
        echo "  WARNING: $err429 x 429 errors detected!"
    elif [ "$err500" -gt 0 ]; then
        echo "  WARNING: $err500 x 500 errors detected!"
    elif [ "$lines" -lt 3 ]; then
        echo "  WARNING: log has only $lines lines — may not have started"
    else
        echo "  OK ($lines log lines, 0 errors)"
    fi
    echo ""
}

echo "============================================================"
echo "  OVERNIGHT RUN — $(date)"
echo "  Target: 500 nopb + 500 pb per rate (1000 total per rate)"
echo "  10 parallel processes, ${DELAY}s delay between launches"
echo "============================================================"
echo ""

# --- GLM 4.5 thinking: HTTP split into 2 groups ---
launch "think_http_low" \
    --model glm-4.5 --protocol http \
    --failure-rates "0.0,0.01,0.02,0.03"

launch "think_http_mid" \
    --model glm-4.5 --protocol http \
    --failure-rates "0.05,0.10"

launch "think_http_high" \
    --model glm-4.5 --protocol http \
    --failure-rates "0.15,0.20"

# --- GLM 4.5 thinking: MCP split into 2 groups ---
launch "think_mcp_low" \
    --model glm-4.5 --protocol mcp \
    --failure-rates "0.0,0.01,0.02,0.03"

launch "think_mcp_high" \
    --model glm-4.5 --protocol mcp \
    --failure-rates "0.05,0.10,0.15,0.20"

# --- GLM 4.5 thinking: A2A split into 2 groups ---
launch "think_a2a_low" \
    --model glm-4.5 --protocol a2a \
    --failure-rates "0.0,0.01,0.02,0.03"

launch "think_a2a_high" \
    --model glm-4.5 --protocol a2a \
    --failure-rates "0.05,0.10,0.15,0.20"

# --- GLM 4.5 no-thinking: 1 process per protocol, all 8 rates ---
launch "nothink_http" \
    --model glm-4.5 --protocol http --no-thinking

launch "nothink_mcp" \
    --model glm-4.5 --protocol mcp --no-thinking

launch "nothink_a2a" \
    --model glm-4.5 --protocol a2a --no-thinking

echo "============================================================"
echo "  ALL 10 LAUNCHED — $(date)"
echo "  Logs: $LOG_DIR/overnight_*.log"
echo "============================================================"
echo ""
echo "Waiting for all to finish..."
wait
echo ""
echo "============================================================"
echo "  ALL DONE — $(date)"
echo "============================================================"
