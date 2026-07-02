#!/usr/bin/env bash
# Auto-resume wrapper for the dashboard. Restarts on crash (the http.server
# stdlib occasionally dies on Windows when a client closes mid-response).
# Usage: bash scripts/auto_dashboard.sh [--port 8061]

set -u

PYTHON=".venv/Scripts/python"
MAX_RESTARTS=50
RESTART_COUNT=0

while [ $RESTART_COUNT -lt $MAX_RESTARTS ]; do
    echo ">>> [auto_dashboard] launch #$((RESTART_COUNT + 1)) at $(date '+%H:%M:%S')"
    $PYTHON scripts/dashboard_experiment.py "$@"
    rc=$?
    if [ $rc -eq 0 ]; then
        echo ">>> [auto_dashboard] dashboard exited cleanly. Done."
        exit 0
    fi
    echo ">>> [auto_dashboard] dashboard rc=$rc. Restarting in 5s..."
    sleep 5
    RESTART_COUNT=$((RESTART_COUNT + 1))
done

echo ">>> [auto_dashboard] gave up after $MAX_RESTARTS restarts."
exit 1
