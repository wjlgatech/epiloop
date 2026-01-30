#!/bin/bash
source lib/execution-logger.sh
log_execution_start "TEST-001" "Test" "{}"
log_execution_end "failure" "test error" "127" "stderr content" "stdout content"
echo "Test complete"
ls -la .claude-loop/logs/error.log 2>&1 | head -n 5
