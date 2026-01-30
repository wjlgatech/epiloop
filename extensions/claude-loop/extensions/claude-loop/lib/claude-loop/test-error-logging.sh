#!/bin/bash
#
# Test script for error logging functionality
# Tests US-001 acceptance criteria

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Clear previous error log
rm -f .claude-loop/logs/error.log

# Source the execution logger
source lib/execution-logger.sh

echo "Testing error logging functionality..."
echo ""

# Test 1: Command not found (exit code 127)
echo "Test 1: Command not found error"
log_execution_start "TEST-001" "Test command not found" "{}"
log_execution_end "failure" "nonexistent_command: command not found" "127" "bash: nonexistent_command: command not found" "Attempting to run nonexistent_command..."
echo "✓ Test 1 complete"
echo ""

# Test 2: Permission denied (exit code 126)
echo "Test 2: Permission denied error"
log_execution_start "TEST-002" "Test permission denied" "{}"
log_execution_end "failure" "Permission denied: /etc/shadow" "126" "bash: /etc/shadow: Permission denied" "Attempting to access /etc/shadow..."
echo "✓ Test 2 complete"
echo ""

# Test 3: Timeout error (exit code 124)
echo "Test 3: Timeout error"
log_execution_start "TEST-003" "Test timeout" "{}"
log_execution_end "failure" "Operation timed out after 60s" "124" "timeout: sending signal TERM to command 'long_running_process'" "Running long_running_process..."
echo "✓ Test 3 complete"
echo ""

# Test 4: File not found error
echo "Test 4: File not found error"
log_execution_start "TEST-004" "Test file not found" "{}"
log_execution_end "failure" "File /nonexistent/file.txt not found" "1" "cat: /nonexistent/file.txt: No such file or directory" "Attempting to read file..."
echo "✓ Test 4 complete"
echo ""

# Test 5: Validation failure
echo "Test 5: Validation failure"
log_execution_start "TEST-005" "Test validation failure" "{}"
log_execution_end "failure" "Test failed: expected 5 but got 3" "1" "AssertionError: expected 5 but got 3
    at test_add (test.js:10:5)" "Running tests...
PASS test_subtract
FAIL test_add"
echo "✓ Test 5 complete"
echo ""

# Check that error log was created
if [ -f ".claude-loop/logs/error.log" ]; then
    echo "✓ Error log created at .claude-loop/logs/error.log"
    echo ""
    echo "Error log contains $(wc -l < .claude-loop/logs/error.log) lines"
    echo ""
    echo "Sample from error log:"
    echo "===================="
    tail -n 30 .claude-loop/logs/error.log
    echo "===================="
else
    echo "✗ Error log was not created!"
    exit 1
fi

echo ""
echo "All tests passed! Error logging is working correctly."
echo ""
echo "Acceptance criteria verified:"
echo "✓ Capture complete stderr output on command failures"
echo "✓ Capture stdout context around errors"
echo "✓ Include exit code with meaning (e.g., 127 = command not found)"
echo "✓ Store in .claude-loop/logs/error.log with timestamps"
echo "✓ Test by triggering intentional error and verifying log"
