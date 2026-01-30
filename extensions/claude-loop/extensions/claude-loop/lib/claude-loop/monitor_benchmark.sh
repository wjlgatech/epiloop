#!/bin/bash
# Real-time benchmark progress monitor

RESULTS_FILE="/Users/jialiang.wu/Documents/Projects/benchmark-results/benchmark_parallel_incremental.json"
OUTPUT_FILE="/private/tmp/claude/-Users-jialiang-wu-Documents-Projects/tasks/bd36b30.output"

echo "=========================================="
echo "BENCHMARK PROGRESS MONITOR"
echo "=========================================="
echo ""

while true; do
    clear
    echo "=========================================="
    echo "BENCHMARK PROGRESS MONITOR"
    echo "Timestamp: $(date '+%Y-%m-%d %H:%M:%S')"
    echo "=========================================="
    echo ""

    # Check if results file exists
    if [ -f "$RESULTS_FILE" ]; then
        COMPLETED=$(jq -r '.progress.completed' "$RESULTS_FILE" 2>/dev/null || echo "0")
        TOTAL=$(jq -r '.progress.total' "$RESULTS_FILE" 2>/dev/null || echo "50")

        SUCCESSES=$(jq '[.results[] | select(.success == true)] | length' "$RESULTS_FILE" 2>/dev/null || echo "0")

        PERCENT=$(echo "scale=1; ($COMPLETED * 100) / $TOTAL" | bc 2>/dev/null || echo "0.0")
        SUCCESS_RATE=$(echo "scale=1; ($SUCCESSES * 100) / $COMPLETED" | bc 2>/dev/null || echo "0.0")

        echo "Progress: $COMPLETED / $TOTAL runs ($PERCENT%)"
        echo "Success Rate: $SUCCESSES / $COMPLETED ($SUCCESS_RATE%)"
        echo ""

        # Show last 5 completed tasks
        echo "Recent completions:"
        jq -r '.results[-5:] | .[] | "  [\(.task_id) Run \(.run)] \(if .success then "✅ PASS" else "❌ FAIL" end) | \(.elapsed_time | tonumber | round)s"' "$RESULTS_FILE" 2>/dev/null

    else
        echo "Waiting for benchmark to start..."
        echo "(Results file not found yet)"
    fi

    echo ""
    echo "=========================================="
    echo "Recent output (last 10 lines):"
    echo "=========================================="
    tail -10 "$OUTPUT_FILE" 2>/dev/null || echo "No output yet"

    echo ""
    echo "Press Ctrl+C to exit monitor"
    echo "Refreshing in 10 seconds..."

    sleep 10
done
