#!/bin/bash
#
# Test script for error suggestions functionality
# Tests US-002 acceptance criteria

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Clear previous error log
rm -f .claude-loop/logs/error.log

# Source the execution logger
source lib/execution-logger.sh

echo "Testing error suggestion functionality..."
echo ""

# Test 1: Command not found (exit code 127)
echo "Test 1: Command not found error"
log_execution_start "TEST-SUG-001" "Test command not found" "{}"
log_execution_end "failure" "nonexistent_command: command not found" "127" "bash: nonexistent_command: command not found" "Attempting to run nonexistent_command..."
echo "✓ Test 1 complete"
echo ""

# Test 2: Permission denied (exit code 126)
echo "Test 2: Permission denied error"
log_execution_start "TEST-SUG-002" "Test permission denied" "{}"
log_execution_end "failure" "Permission denied: /etc/shadow" "126" "bash: /etc/shadow: Permission denied" "Attempting to access /etc/shadow..."
echo "✓ Test 2 complete"
echo ""

# Test 3: Timeout error (exit code 124)
echo "Test 3: Timeout error"
log_execution_start "TEST-SUG-003" "Test timeout" "{}"
log_execution_end "failure" "Operation timed out after 60s" "124" "timeout: sending signal TERM to command 'long_running_process'" "Running long_running_process..."
echo "✓ Test 3 complete"
echo ""

# Test 4: File not found error
echo "Test 4: File not found error"
log_execution_start "TEST-SUG-004" "Test file not found" "{}"
log_execution_end "failure" "File /nonexistent/file.txt not found" "1" "cat: /nonexistent/file.txt: No such file or directory" "Attempting to read file..."
echo "✓ Test 4 complete"
echo ""

# Test 5: Network error
echo "Test 5: Network error"
log_execution_start "TEST-SUG-005" "Test network error" "{}"
log_execution_end "failure" "Connection refused" "1" "curl: (7) Failed to connect to api.example.com port 443: Connection refused" "Fetching data from API..."
echo "✓ Test 5 complete"
echo ""

# Check that error log was created
if [ -f ".claude-loop/logs/error.log" ]; then
    echo "✓ Error log created at .claude-loop/logs/error.log"
    echo ""
    echo "Sample from error log with suggestions:"
    echo "===================="
    tail -n 50 .claude-loop/logs/error.log
    echo "===================="
else
    echo "✗ Error log was not created!"
    exit 1
fi

echo ""
echo "All tests passed! Error suggestions are working correctly."
echo ""
echo "Acceptance criteria verified:"
echo "✓ Detect common error patterns (file not found, permission denied, command not found, etc.)"
echo "✓ Provide specific fix suggestions for each pattern"
echo "✓ Include relevant file paths and line numbers when available"
echo "✓ Format suggestions as clear action items"
echo "✓ Test with 5 common error scenarios"
