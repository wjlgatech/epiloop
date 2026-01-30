#!/bin/bash
# Real-time monitoring script for claude-loop integration

echo "=== Claude-Loop Integration Monitor ==="
echo "Task ID: bf0b931"
echo "Started: $(date)"
echo ""

# Function to count completed stories
count_completed() {
    if [ -f "prds/active/claude-loop-integration/prd.json" ]; then
        grep -c '"passes": true' prds/active/claude-loop-integration/prd.json 2>/dev/null || echo "0"
    else
        echo "0"
    fi
}

# Function to show worker status
show_workers() {
    if [ -d ".claude-loop/workers" ]; then
        echo "Active Workers:"
        ls -la .claude-loop/workers/ 2>/dev/null | grep -v "^total" | grep -v "^d" || echo "  None yet"
    fi
}

# Function to tail logs
tail_logs() {
    echo ""
    echo "=== Latest Execution Output ==="
    tail -30 /private/tmp/claude/-Users-jialiang-wu-Documents-Projects/tasks/bf0b931.output 2>/dev/null
}

# Main monitoring loop
while true; do
    clear
    echo "=== Claude-Loop Integration Monitor ==="
    echo "Task ID: bf0b931"
    echo "Time: $(date '+%Y-%m-%d %H:%M:%S')"
    echo ""

    COMPLETED=$(count_completed)
    echo "Progress: $COMPLETED/15 stories completed"
    echo ""

    show_workers

    tail_logs

    echo ""
    echo "=== Press Ctrl+C to exit monitoring ==="
    echo "=== Refreshing in 30 seconds... ==="

    sleep 30
done
