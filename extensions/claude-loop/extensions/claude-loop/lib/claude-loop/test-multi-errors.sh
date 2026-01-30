#!/bin/bash
source lib/execution-logger.sh

rm -f .claude-loop/logs/error.log

# Test permission error
log_execution_start "TEST-PERM" "Test permission" "{}"
log_execution_end "failure" "Permission denied: /etc/shadow" "126" "bash: /etc/shadow: Permission denied" "cat /etc/shadow"

# Test network error
log_execution_start "TEST-NET" "Test network" "{}"
log_execution_end "failure" "Connection refused to api.example.com" "1" "curl: (7) Failed to connect" "curl api.example.com"

# Test file not found
log_execution_start "TEST-FILE" "Test file" "{}"
log_execution_end "failure" "cat: /nonexistent/data.json: No such file or directory" "1" "cat: /nonexistent/data.json: No such file or directory" "cat /nonexistent/data.json"

# Test JSON parse error
log_execution_start "TEST-JSON" "Test json" "{}"
log_execution_end "failure" "JSON parse error: unexpected token at line 5" "1" "parse error: Invalid numeric literal at line 5" "jq . bad.json"

# Test rate limit
log_execution_start "TEST-RATE" "Test rate limit" "{}"
log_execution_end "failure" "API rate limit exceeded" "1" "429 Too Many Requests" "curl -H 'Authorization: Bearer token' api.example.com"

cat .claude-loop/logs/error.log
