#!/bin/bash
# Monitor the parallel execution fix PRD

echo "=== Monitoring Fix PRD (PID: 5466) ==="
echo ""

while true; do
    clear
    echo "╔════════════════════════════════════════════════════════════╗"
    echo "║  Parallel Execution Fix - Live Monitor                     ║"
    echo "╚════════════════════════════════════════════════════════════╝"
    echo ""

    # Check if process is still running
    if ps -p 5466 > /dev/null 2>&1; then
        echo "✅ Status: RUNNING (PID: 5466)"
    else
        echo "❌ Status: STOPPED"
        echo ""
        echo "Final log tail:"
        tail -30 .claude-loop/fix-execution.log
        exit 0
    fi

    echo ""
    echo "--- Latest Progress (last 20 lines) ---"
    tail -20 .claude-loop/fix-execution.log | grep -E "INFO|SUCCESS|ERROR|Story|US-" || echo "No progress updates yet..."

    echo ""
    echo "--- Completed Stories ---"
    grep -E "passes.*true|Story.*complete" prds/fix-parallel-execution-logging.json 2>/dev/null | wc -l | xargs echo "Stories marked complete:"

    echo ""
    echo "Press Ctrl+C to stop monitoring (process will continue)"
    echo "Refreshing in 10 seconds..."

    sleep 10
done
