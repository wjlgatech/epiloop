#!/bin/bash
# Final RG-TDD Execution - Until 14:40 PST
# RG-TDD enforced via config files

set -euo pipefail

echo "╔════════════════════════════════════════════════════════════════╗"
echo "║       Claude-Loop with RG-TDD - Final Execution               ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""
date
echo "Target End: 14:40 PST"
echo ""

# Ensure RG-TDD config exists
if [ ! -f "prds/active/claude-loop-integration/.rg-tdd-config.yaml" ]; then
    echo "⚠️  RG-TDD config not found, creating..."
    cat > prds/active/claude-loop-integration/.rg-tdd-config.yaml <<'EOF'
enabled: true
ironLawEnforcement: true
layers:
  foundation:
    enabled: true
    minCoverage: 75
  challenge:
    enabled: true
  reality:
    enabled: false
qualityGates:
  - name: "Unit Tests"
    required: true
  - name: "Type Checking"
    required: true
  - name: "Linting"
    required: true
  - name: "Security Scan"
    required: true
EOF
fi

# Update PRD to include TDD requirements in each story
python3 - <<'PYTHON'
import json
import sys

prd_path = "prds/active/claude-loop-integration/prd.json"
with open(prd_path) as f:
    prd = json.load(f)

# Add TDD note to each story's acceptance criteria
for story in prd["userStories"]:
    # Ensure TDD requirement is mentioned
    tdd_criterion = "Tests written FIRST (RED phase), then minimal implementation (GREEN phase), following TDD Iron Law"
    if tdd_criterion not in story.get("acceptanceCriteria", []):
        if "acceptanceCriteria" not in story:
            story["acceptanceCriteria"] = []
        story["acceptanceCriteria"].insert(0, tdd_criterion)

# Save updated PRD
with open(prd_path, 'w') as f:
    json.dump(prd, f, indent=2)

print("✅ PRD updated with TDD requirements")
PYTHON

echo ""
echo "RG-TDD Quality Configuration:"
echo "  ✅ Layer 1 (Foundation): Tests, types, lint, security"
echo "  ✅ Layer 2 (Challenge): Edge cases, stress tests"
echo "  ✅ TDD Iron Law: RED → GREEN → REFACTOR"
echo "  ✅ Coverage Required: >= 75%"
echo ""
echo "Starting execution..."
echo ""

# Start with all quality features
nohup ./claude-loop.sh \
    --prd prds/active/claude-loop-integration/prd.json \
    --verbose \
    --max-iterations 50 \
    > execution-final.log 2>&1 &

PID=$!
echo $PID > .execution-pid

echo "✅ Started with PID: $PID"
echo ""
echo "Monitor: tail -f execution-final.log"
echo "Progress: ./WATCH_PROGRESS.sh"
echo ""
