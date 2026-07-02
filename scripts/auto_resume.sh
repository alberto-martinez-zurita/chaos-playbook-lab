#!/usr/bin/env bash
# Auto-resume wrapper — relaunches run_experiment.py on python crashes.
# The lab's resume mechanism picks up from existing CSVs, so each
# restart costs ~30s of overhead at most.
#
# Usage: bash scripts/auto_resume.sh <experiment.yaml> [-n N] [other args...]

set -u

CONFIG="$1"
shift

PYTHON=".venv/Scripts/python"
MAX_RESTARTS=20
RESTART_COUNT=0

while [ $RESTART_COUNT -lt $MAX_RESTARTS ]; do
    echo ""
    echo "================================================================"
    echo ">>> [auto_resume] launch #$((RESTART_COUNT + 1)) at $(date '+%H:%M:%S')"
    echo "================================================================"
    $PYTHON scripts/run_experiment.py --config "$CONFIG" "$@"
    rc=$?
    if [ $rc -eq 0 ]; then
        echo ">>> [auto_resume] python exited cleanly (rc=0). Done."
        exit 0
    fi
    echo ">>> [auto_resume] python exited rc=$rc. Sleeping 10s and restarting..."
    sleep 10
    RESTART_COUNT=$((RESTART_COUNT + 1))
done

echo ">>> [auto_resume] gave up after $MAX_RESTARTS restarts."
exit 1
