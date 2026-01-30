#!/bin/bash
# Start 2-hour continuous Claude-Loop execution
# Target: Complete by 14:40 PST

set -euo pipefail

echo "=== Starting Claude-Loop Continuous Execution ==="
echo "Start Time: $(date)"
echo "Target End: 14:40 PST"
echo "PRD: prds/active/claude-loop-integration/prd.json"
echo ""

# Create log directory
mkdir -p ~/.clawdbot/logs/claude-loop

# Start execution with high iteration count
nohup ./claude-loop.sh \
    --prd prds/active/claude-loop-integration/prd.json \
    --verbose \
    --max-iterations 50 \
    > execution-main.log 2>&1 &

PID=$!
echo $PID > .execution-pid

echo "✅ Execution started with PID: $PID"
echo ""
echo "Monitor commands:"
echo "  tail -f execution-main.log"
echo "  ./PROGRESS_CHECK.sh"
echo "  grep -c '\"passes\": true' prds/active/claude-loop-integration/prd.json"
echo ""
echo "Stop execution:"
echo "  kill \$(cat .execution-pid)"
