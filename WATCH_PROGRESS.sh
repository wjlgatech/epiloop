#!/bin/bash
# Real-time progress watcher
# Updates every 30 seconds until 14:40 PST

echo "=== Claude-Loop Integration Progress Watcher ==="
echo "Started: $(date)"
echo "Will run until: 14:40 PST"
echo ""

while true; do
    CURRENT_TIME=$(date +%H:%M)

    # Stop at 14:40
    if [[ "$CURRENT_TIME" > "14:40" ]]; then
        echo ""
        echo "=== Execution window closed at $(date) ==="
        break
    fi

    clear
    echo "╔════════════════════════════════════════════════════════════════╗"
    echo "║     Claude-Loop Integration - Live Progress                   ║"
    echo "╚════════════════════════════════════════════════════════════════╝"
    echo ""
    echo "Time: $(date '+%H:%M:%S PST') | Target End: 14:40 PST"
    echo ""

    # Check if process is still running
    if [ -f ".execution-pid" ] && ps -p $(cat .execution-pid) > /dev/null 2>&1; then
        echo "Status: 🟢 RUNNING (PID: $(cat .execution-pid))"
    else
        echo "Status: 🔴 STOPPED"
        echo ""
        echo "Restart with: ./START_EXECUTION.sh"
        sleep 30
        continue
    fi

    echo ""

    # Count completed stories
    if [ -f "prds/active/claude-loop-integration/prd.json" ]; then
        COMPLETED=$(grep -c '"passes": true' prds/active/claude-loop-integration/prd.json 2>/dev/null || echo "0")
        PERCENT=$((COMPLETED * 100 / 15))

        # Progress bar
        FILLED=$((COMPLETED * 30 / 15))
        EMPTY=$((30 - FILLED))
        BAR=$(printf '▓%.0s' $(seq 1 $FILLED))$(printf '░%.0s' $(seq 1 $EMPTY))

        echo "Progress: [$BAR] $PERCENT% ($COMPLETED/15 stories)"
        echo ""

        # Show completed stories
        if [ "$COMPLETED" -gt 0 ]; then
            echo "✅ Completed Stories:"
            cat prds/active/claude-loop-integration/prd.json | \
                jq -r '.userStories[] | select(.passes == true) | "  ✓ \(.id): \(.title)"' 2>/dev/null | head -5
            if [ "$COMPLETED" -gt 5 ]; then
                echo "  ... and $((COMPLETED - 5)) more"
            fi
            echo ""
        fi

        # Show current story
        CURRENT=$(cat prds/active/claude-loop-integration/prd.json | \
            jq -r '.userStories[] | select(.passes == false) | "\(.id): \(.title)"' 2>/dev/null | head -1)
        if [ -n "$CURRENT" ]; then
            echo "🔄 Current Story:"
            echo "  $CURRENT"
        fi
    else
        echo "Progress: Initializing..."
    fi

    echo ""
    echo "─────────────────────────────────────────────────────────────────"
    echo ""

    # Show last few lines of execution log
    echo "Recent Activity:"
    tail -5 execution-main.log 2>/dev/null | sed 's/\x1b\[[0-9;]*m//g' | tail -3

    echo ""
    echo "─────────────────────────────────────────────────────────────────"
    echo "Press Ctrl+C to stop watching (execution continues in background)"
    echo "Refreshing in 30 seconds..."

    sleep 30
done

# Final status
echo ""
FINAL_COMPLETED=$(grep -c '"passes": true' prds/active/claude-loop-integration/prd.json 2>/dev/null || echo "0")
echo "Final Status: $FINAL_COMPLETED/15 stories completed"
echo ""
echo "View full log: cat execution-main.log"
