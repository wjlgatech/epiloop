#!/bin/bash
# Quick progress check script

echo "=== Claude-Loop Integration Progress ==="
echo "$(date)"
echo ""

# Worker status
if [ -f ".claude-loop/workers/claude-loop-integration/status.json" ]; then
    echo "Worker Status:"
    cat .claude-loop/workers/claude-loop-integration/status.json | jq '.'
    echo ""
fi

# PRD progress
if [ -f "prds/active/claude-loop-integration/prd.json" ]; then
    COMPLETED=$(grep -c '"passes": true' prds/active/claude-loop-integration/prd.json || echo "0")
    echo "Stories Completed: $COMPLETED/15"
    echo ""

    echo "Completed Stories:"
    cat prds/active/claude-loop-integration/prd.json | jq -r '.userStories[] | select(.passes == true) | "  ✅ \(.id): \(.title)"'
    echo ""

    echo "In Progress Stories:"
    cat prds/active/claude-loop-integration/prd.json | jq -r '.userStories[] | select(.passes == false) | "  ⏳ \(.id): \(.title)"' | head -5
fi

echo ""
echo "Worker Process:"
ps aux | grep "claude-loop.*claude-loop-integration" | grep -v grep || echo "  Not found (may have completed)"

echo ""
echo "To monitor live: tail -f .claude-loop/workers/claude-loop-integration/worker.log"
