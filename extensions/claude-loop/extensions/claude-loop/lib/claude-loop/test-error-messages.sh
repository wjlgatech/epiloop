#!/bin/bash
cd /tmp

# Source the claude-loop file to test error messages
source /Users/jialiang.wu/Documents/Projects/claude-loop/claude-loop.sh

echo "===== Testing git error message ====="
check_git_repo 2>&1 || echo "Git check failed (expected)"

echo ""
echo "===== Testing PRD not found error ====="
PRD_FILE="nonexistent.json"
check_prd_exists 2>&1 || echo "PRD check failed (expected)"
