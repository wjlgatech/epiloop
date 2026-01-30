#!/bin/bash
# Quick Task Mode Demo Script
# Demonstrates Cowork-style natural language task execution

echo "==================================="
echo "  QUICK TASK MODE DEMO"
echo "==================================="
echo ""
echo "Feature: Execute tasks with natural language, no PRD required"
echo ""
echo "Example Command:"
echo '  ./claude-loop.sh quick "Add a timestamp to README.md"'
echo ""
echo "What happens:"
echo "  1. Task parsing - understands your intent"
echo "  2. Plan generation - creates 5-step execution plan"
echo "  3. Cost estimation - shows token cost ($0.05-0.10 typical)"
echo "  4. Approval checkpoint - you review and approve/reject"
echo "  5. Isolated execution - runs in workspace sandbox"
echo "  6. Auto-commit - creates git commit if --commit flag used"
echo ""
echo "Advanced Features:"
echo "  - Complexity detection (0-100 scale)"
echo "  - Auto-escalation to full PRD if complexity > 60"
echo "  - Task templates for common patterns"
echo "  - Audit trail in .claude-loop/quick-tasks.jsonl"
echo ""
echo "Try it yourself:"
echo '  ./claude-loop.sh quick "Create DEMO.txt with Phase 2 features list" --workspace ./'
echo ""
