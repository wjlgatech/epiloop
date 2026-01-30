#!/bin/bash
# Continuous Claude-Loop Execution Script
# Runs until 14:40 PST with automatic restart on completion

set -euo pipefail

END_TIME="14:40"
LOG_DIR="$HOME/.clawdbot/logs/claude-loop"
EXECUTION_LOG="./continuous-execution.log"

mkdir -p "$LOG_DIR"

echo "=== Claude-Loop Continuous Execution ===" | tee -a "$EXECUTION_LOG"
echo "Started: $(date)" | tee -a "$EXECUTION_LOG"
echo "Target End: Today at $END_TIME PST" | tee -a "$EXECUTION_LOG"
echo "" | tee -a "$EXECUTION_LOG"

# Function to check if we should continue
should_continue() {
    CURRENT_TIME=$(date +%H:%M)
    if [[ "$CURRENT_TIME" < "$END_TIME" ]]; then
        return 0
    else
        return 1
    fi
}

# Main execution loop
ITERATION=1
while should_continue; do
    echo "=== Iteration $ITERATION at $(date) ===" | tee -a "$EXECUTION_LOG"

    # Check PRD status
    COMPLETED=$(grep -c '"passes": true' prds/active/claude-loop-integration/prd.json 2>/dev/null || echo "0")
    echo "Stories completed: $COMPLETED/15" | tee -a "$EXECUTION_LOG"

    # If all stories complete, we're done
    if [ "$COMPLETED" -eq 15 ]; then
        echo "✅ ALL STORIES COMPLETE!" | tee -a "$EXECUTION_LOG"
        echo "Integration finished at $(date)" | tee -a "$EXECUTION_LOG"
        exit 0
    fi

    # Run claude-loop
    echo "Starting claude-loop execution..." | tee -a "$EXECUTION_LOG"
    ./claude-loop.sh \
        --prd prds/active/claude-loop-integration/prd.json \
        --verbose \
        --max-iterations 5 \
        2>&1 | tee -a "$LOG_DIR/iteration-$ITERATION.log"

    EXIT_CODE=$?
    echo "Exit code: $EXIT_CODE" | tee -a "$EXECUTION_LOG"

    # Log completion
    COMPLETED_AFTER=$(grep -c '"passes": true' prds/active/claude-loop-integration/prd.json 2>/dev/null || echo "0")
    echo "Stories completed after iteration: $COMPLETED_AFTER/15" | tee -a "$EXECUTION_LOG"

    # Short delay before next iteration
    sleep 5

    ITERATION=$((ITERATION + 1))
done

echo "" | tee -a "$EXECUTION_LOG"
echo "=== Execution window closed at $(date) ===" | tee -a "$EXECUTION_LOG"
FINAL_COMPLETED=$(grep -c '"passes": true' prds/active/claude-loop-integration/prd.json 2>/dev/null || echo "0")
echo "Final status: $FINAL_COMPLETED/15 stories completed" | tee -a "$EXECUTION_LOG"
