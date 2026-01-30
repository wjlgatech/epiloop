#!/bin/bash
# Start Claude-Loop with Reality-Grounded TDD Enabled
# 2-hour continuous execution until 14:40 PST

set -euo pipefail

echo "╔════════════════════════════════════════════════════════════════╗"
echo "║  Starting Claude-Loop with RG-TDD (Reality-Grounded TDD)      ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""
echo "Start Time: $(date)"
echo "Target End: 14:40 PST"
echo ""
echo "RG-TDD Features Enabled:"
echo "  ✅ Layer 1 (Foundation): Unit tests, integration, type checks, lint"
echo "  ✅ Layer 2 (Challenge): Edge cases, stress tests, baselines"
echo "  ✅ Layer 3 (Reality): Will enable after basic implementation"
echo "  ✅ Iron Law: Tests must fail before implementation"
echo "  ✅ TDD Enforcer: Verifies RED phase before GREEN"
echo ""

# Create necessary directories
mkdir -p ~/.clawdbot/logs/claude-loop
mkdir -p ~/.clawdbot/claude-loop/experience-store
mkdir -p prds/active/claude-loop-integration/test-reports

# Copy RG-TDD config to PRD directory
if [ ! -f "prds/active/claude-loop-integration/.rg-tdd-config.yaml" ]; then
    cp .rg-tdd-config.yaml prds/active/claude-loop-integration/ 2>/dev/null || true
fi

# Start execution with RG-TDD
echo "Starting execution..."
nohup ./claude-loop.sh \
    --prd prds/active/claude-loop-integration/prd.json \
    --verbose \
    --max-iterations 50 \
    --enable-tdd \
    > execution-rgtdd.log 2>&1 &

PID=$!
echo $PID > .execution-pid

echo ""
echo "✅ Execution started with PID: $PID"
echo ""
echo "RG-TDD Quality Gates Active:"
echo "  1. TDD Iron Law Verification"
echo "  2. Unit Tests (>= 75% coverage)"
echo "  3. Integration Tests"
echo "  4. Type Checking (strict TypeScript)"
echo "  5. Linting (oxlint)"
echo "  6. Security Scan"
echo ""
echo "Monitor commands:"
echo "  tail -f execution-rgtdd.log"
echo "  ./PROGRESS_CHECK.sh"
echo "  ./WATCH_PROGRESS.sh"
echo ""
echo "TDD Reports will be in:"
echo "  prds/active/claude-loop-integration/test-reports/"
echo ""
