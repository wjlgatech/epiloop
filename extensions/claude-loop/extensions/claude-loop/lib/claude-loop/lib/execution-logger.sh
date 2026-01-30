#!/bin/bash
#
# execution-logger.sh - Structured Execution Logging for claude-loop
#
# Provides detailed execution logging for every story attempt, enabling
# gap analysis, pattern detection, and autonomous self-improvement.
#
# Log Format: JSONL (one JSON object per line)
# Storage: .claude-loop/execution_log.jsonl
#
# Usage:
#   source lib/execution-logger.sh
#   log_execution_start "SI-001" "story title"
#   log_action "Read" '{"file_path": "/path/to/file"}'
#   log_execution_end "success" "" ""
#
# Error Types:
#   timeout     - Execution exceeded time limit
#   not_found   - File, resource, or tool not found
#   permission  - Permission denied errors
#   parse       - JSON/syntax parsing errors
#   network     - Network/API connection errors
#   validation  - Test or validation failures
#   unknown     - Unclassified errors

# ============================================================================
# Configuration
# ============================================================================

# Log file location
EXECUTION_LOG_DIR=".claude-loop"
EXECUTION_LOG_FILE="${EXECUTION_LOG_DIR}/execution_log.jsonl"

# Current execution state (populated by log_execution_start)
EXEC_LOG_STORY_ID=""
EXEC_LOG_STORY_TITLE=""
EXEC_LOG_START_TIME=""
EXEC_LOG_START_ISO=""
EXEC_LOG_ACTIONS=""         # JSON array of actions
EXEC_LOG_TOOLS_USED=""      # Comma-separated list of tools
EXEC_LOG_FILE_TYPES=""      # Comma-separated list of file types
EXEC_LOG_RETRY_COUNT=0
EXEC_LOG_FALLBACK_COUNT=0
EXEC_LOG_CONTEXT=""         # JSON object with additional context

# Colors for output (match monitoring.sh)
EXEC_CYAN='\033[0;36m'
EXEC_GREEN='\033[0;32m'
EXEC_YELLOW='\033[1;33m'
EXEC_RED='\033[0;31m'
EXEC_NC='\033[0m'

# ============================================================================
# Helper Functions
# ============================================================================

# Get current timestamp in milliseconds
exec_get_timestamp_ms() {
    if [[ "$OSTYPE" == "darwin"* ]]; then
        perl -MTime::HiRes=time -e 'printf "%.0f\n", time * 1000'
    else
        echo $(($(date +%s%N) / 1000000))
    fi
}

# Get current timestamp as ISO string
exec_get_timestamp_iso() {
    date -u +"%Y-%m-%dT%H:%M:%SZ"
}

# Escape special characters for JSON strings
exec_json_escape() {
    local str="${1:-}"
    # Escape backslashes, double quotes, and newlines
    str="${str//\\/\\\\}"
    str="${str//\"/\\\"}"
    str="${str//$'\n'/\\n}"
    str="${str//$'\r'/\\r}"
    str="${str//$'\t'/\\t}"
    echo "$str"
}

# Ensure log directory exists
exec_ensure_log_dir() {
    if [ ! -d "$EXECUTION_LOG_DIR" ]; then
        mkdir -p "$EXECUTION_LOG_DIR"
    fi
}

# Get exit code meaning
get_exit_code_meaning() {
    local exit_code="$1"

    case "$exit_code" in
        0)   echo "Success" ;;
        1)   echo "General error" ;;
        2)   echo "Misuse of shell builtin" ;;
        124) echo "Command timed out" ;;
        125) echo "Command itself failed" ;;
        126) echo "Command invoked cannot execute" ;;
        127) echo "Command not found" ;;
        128) echo "Invalid argument to exit" ;;
        130) echo "Script terminated by Ctrl+C" ;;
        137) echo "Process killed (SIGKILL)" ;;
        143) echo "Process terminated (SIGTERM)" ;;
        *)   echo "Exit code $exit_code" ;;
    esac
}

# Get actionable suggestion for error
# Returns a helpful suggestion for fixing the error
get_error_suggestion() {
    local error_msg="$1"
    local exit_code="${2:-1}"
    local error_type="$3"

    # Convert to lowercase for matching
    local lower_msg
    lower_msg=$(echo "$error_msg" | tr '[:upper:]' '[:lower:]')

    # Command not found (exit 127)
    if [ "$exit_code" -eq 127 ] || echo "$lower_msg" | grep -qE "command not found"; then
        echo "→ Install the missing command or check if it's in your PATH"
        echo "→ Verify the command name is spelled correctly"
        return
    fi

    # Permission denied (exit 126)
    if [ "$exit_code" -eq 126 ] || echo "$lower_msg" | grep -qE "permission denied"; then
        echo "→ Check file permissions: chmod +x <file>"
        echo "→ Run with elevated privileges: sudo <command>"
        echo "→ Verify you own the file: ls -la <file>"
        return
    fi

    # Timeout (exit 124)
    if [ "$exit_code" -eq 124 ] || echo "$lower_msg" | grep -qE "(timeout|timed out)"; then
        echo "→ Increase the timeout value: --timeout <seconds>"
        echo "→ Check if the process is stuck in an infinite loop"
        echo "→ Verify network connectivity if accessing remote resources"
        return
    fi

    # File not found
    if echo "$lower_msg" | grep -qE "no such file"; then
        # Extract file path if present
        local file_path=$(echo "$error_msg" | grep -oE "(/[^:]+|[a-zA-Z0-9_./\-]+\.(txt|json|sh|py|js|ts))" | head -1)
        echo "→ Verify the file path exists: ls $file_path"
        echo "→ Check for typos in the file path"
        echo "→ Ensure you're in the correct working directory: pwd"
        return
    fi

    # Network/connection errors
    if echo "$lower_msg" | grep -qE "(network|connection|econnrefused|etimedout|dns|unreachable)"; then
        echo "→ Check network connectivity: ping <host>"
        echo "→ Verify the service is running: curl <url>"
        echo "→ Check firewall rules and proxy settings"
        echo "→ Retry the operation after a brief delay"
        return
    fi

    # API rate limit
    if echo "$lower_msg" | grep -qE "rate limit"; then
        echo "→ Wait before retrying (typically 1-60 minutes)"
        echo "→ Check API rate limit documentation"
        echo "→ Use exponential backoff for retries"
        return
    fi

    # Parse/syntax errors
    if echo "$lower_msg" | grep -qE "(parse error|syntax error|invalid json)"; then
        echo "→ Validate JSON syntax: jq . <file>"
        echo "→ Check for missing commas, braces, or quotes"
        echo "→ Use a linter to identify syntax issues"
        return
    fi

    # Test failures
    if echo "$lower_msg" | grep -qE "test failed|assertion"; then
        echo "→ Review test output for specific failure details"
        echo "→ Run tests with verbose mode: pytest -v or npm test -- --verbose"
        echo "→ Check if test data or fixtures need updating"
        return
    fi

    # Type errors
    if echo "$lower_msg" | grep -qE "type error"; then
        echo "→ Run type checker: mypy <file> or tsc --noEmit"
        echo "→ Review type annotations and interfaces"
        echo "→ Check for null/undefined values"
        return
    fi

    # Generic suggestions based on error type
    case "$error_type" in
        validation)
            echo "→ Review validation rules and test data"
            echo "→ Run tests individually to isolate the failure"
            ;;
        unknown)
            echo "→ Search for the error message online"
            echo "→ Check project documentation and logs"
            echo "→ Review recent code changes"
            ;;
        *)
            echo "→ Review error details above"
            echo "→ Check relevant documentation"
            ;;
    esac
}

# Classify error type from error message
classify_error_type() {
    local error_msg="$1"
    local exit_code="${2:-1}"

    # Convert to lowercase for matching
    local lower_msg
    lower_msg=$(echo "$error_msg" | tr '[:upper:]' '[:lower:]')

    # Exit code 127 is always command not found
    if [ "$exit_code" -eq 127 ]; then
        echo "not_found"
        return
    fi

    # Exit code 126 is permission/execution error
    if [ "$exit_code" -eq 126 ]; then
        echo "permission"
        return
    fi

    # Exit code 124 is timeout
    if [ "$exit_code" -eq 124 ]; then
        echo "timeout"
        return
    fi

    # Timeout errors
    if echo "$lower_msg" | grep -qE "(timeout|timed out|exceeded.*limit|deadline)"; then
        echo "timeout"
        return
    fi

    # Not found errors
    if echo "$lower_msg" | grep -qE "(not found|no such file|does not exist|cannot find|missing|undefined|unresolved)"; then
        echo "not_found"
        return
    fi

    # Permission errors
    if echo "$lower_msg" | grep -qE "(permission denied|access denied|forbidden|unauthorized|not permitted|eacces)"; then
        echo "permission"
        return
    fi

    # Parse errors
    if echo "$lower_msg" | grep -qE "(parse error|syntax error|invalid json|unexpected token|malformed|invalid syntax)"; then
        echo "parse"
        return
    fi

    # Network errors
    if echo "$lower_msg" | grep -qE "(network|connection|socket|econnrefused|etimedout|dns|unreachable|api error|rate limit)"; then
        echo "network"
        return
    fi

    # Validation/test errors
    if echo "$lower_msg" | grep -qE "(test failed|assertion|validation failed|type error|lint error|check failed)"; then
        echo "validation"
        return
    fi

    # Unknown if no pattern matched
    echo "unknown"
}

# Extract file extension/type from file path
get_file_type() {
    local file_path="$1"
    local ext
    ext="${file_path##*.}"

    # Normalize common extensions
    case "$ext" in
        ts|tsx)  echo "typescript" ;;
        js|jsx)  echo "javascript" ;;
        py)      echo "python" ;;
        sh)      echo "shell" ;;
        md)      echo "markdown" ;;
        json)    echo "json" ;;
        yaml|yml) echo "yaml" ;;
        html)    echo "html" ;;
        css|scss|sass) echo "css" ;;
        *)       echo "$ext" ;;
    esac
}

# Add a file type to the tracked list
add_file_type() {
    local file_type="$1"

    if [ -z "$file_type" ]; then
        return
    fi

    if [ -z "$EXEC_LOG_FILE_TYPES" ]; then
        EXEC_LOG_FILE_TYPES="$file_type"
    elif ! echo ",$EXEC_LOG_FILE_TYPES," | grep -q ",$file_type,"; then
        EXEC_LOG_FILE_TYPES="${EXEC_LOG_FILE_TYPES},$file_type"
    fi
}

# Add a tool to the tracked list
add_tool_used() {
    local tool="$1"

    if [ -z "$tool" ]; then
        return
    fi

    if [ -z "$EXEC_LOG_TOOLS_USED" ]; then
        EXEC_LOG_TOOLS_USED="$tool"
    elif ! echo ",$EXEC_LOG_TOOLS_USED," | grep -q ",$tool,"; then
        EXEC_LOG_TOOLS_USED="${EXEC_LOG_TOOLS_USED},$tool"
    fi
}

# Convert comma-separated list to JSON array
list_to_json_array() {
    local list="$1"

    if [ -z "$list" ]; then
        echo "[]"
        return
    fi

    local json_array="["
    local first=true

    IFS=',' read -ra items <<< "$list"
    for item in "${items[@]}"; do
        if [ -n "$item" ]; then
            if [ "$first" = true ]; then
                first=false
            else
                json_array+=", "
            fi
            json_array+="\"$(exec_json_escape "$item")\""
        fi
    done

    json_array+="]"
    echo "$json_array"
}

# ============================================================================
# Core Logging Functions
# ============================================================================

# Initialize logging for a story execution
# Usage: log_execution_start "SI-001" "Story Title" '{"extra": "context"}'
log_execution_start() {
    local story_id="$1"
    local story_title="${2:-}"
    local context="${3:-{}}"

    # Reset state
    EXEC_LOG_STORY_ID="$story_id"
    EXEC_LOG_STORY_TITLE="$story_title"
    EXEC_LOG_START_TIME=$(exec_get_timestamp_ms)
    EXEC_LOG_START_ISO=$(exec_get_timestamp_iso)
    EXEC_LOG_ACTIONS="[]"
    EXEC_LOG_TOOLS_USED=""
    EXEC_LOG_FILE_TYPES=""
    EXEC_LOG_RETRY_COUNT=0
    EXEC_LOG_FALLBACK_COUNT=0
    EXEC_LOG_CONTEXT="$context"

    # Ensure log directory exists
    exec_ensure_log_dir

    echo -e "${EXEC_CYAN}[EXEC-LOG]${EXEC_NC} Started: $story_id - $story_title"
}

# Log an action (tool invocation)
# Usage: log_action "Read" '{"file_path": "/path/to/file.ts"}' "success" ""
log_action() {
    local tool_name="$1"
    local parameters="$2"
    if [ -z "$parameters" ]; then
        parameters="{}"
    fi
    local action_status="${3:-pending}"
    local error_msg="${4:-}"

    # Track tool usage
    add_tool_used "$tool_name"

    # Extract file type if parameters contain a file path
    local file_path
    file_path=$(echo "$parameters" | jq -r '.file_path // .path // ""' 2>/dev/null || echo "")
    if [ -n "$file_path" ]; then
        local file_type
        file_type=$(get_file_type "$file_path")
        add_file_type "$file_type"
    fi

    # Build action JSON - use printf to avoid heredoc issues
    local escaped_tool
    escaped_tool=$(exec_json_escape "$tool_name")
    local escaped_error
    escaped_error=$(exec_json_escape "$error_msg")
    local timestamp
    timestamp=$(exec_get_timestamp_iso)

    local action_json
    action_json="{\"tool\": \"$escaped_tool\", \"parameters\": $parameters, \"status\": \"$action_status\", \"error\": \"$escaped_error\", \"timestamp\": \"$timestamp\"}"

    # Append to actions array
    if [ "$EXEC_LOG_ACTIONS" = "[]" ]; then
        EXEC_LOG_ACTIONS="[$action_json]"
    else
        EXEC_LOG_ACTIONS="${EXEC_LOG_ACTIONS%]}, $action_json]"
    fi
}

# Increment retry count
log_retry() {
    EXEC_LOG_RETRY_COUNT=$((EXEC_LOG_RETRY_COUNT + 1))
    echo -e "${EXEC_YELLOW}[EXEC-LOG]${EXEC_NC} Retry #$EXEC_LOG_RETRY_COUNT for $EXEC_LOG_STORY_ID"
}

# Increment fallback count
log_fallback() {
    local fallback_reason="${1:-}"
    EXEC_LOG_FALLBACK_COUNT=$((EXEC_LOG_FALLBACK_COUNT + 1))
    echo -e "${EXEC_YELLOW}[EXEC-LOG]${EXEC_NC} Fallback #$EXEC_LOG_FALLBACK_COUNT: $fallback_reason"
}

# Set additional context
# Usage: set_execution_context '{"application": "web", "runtime": "node"}'
set_execution_context() {
    local context="$1"
    EXEC_LOG_CONTEXT="$context"
}

# Merge additional context (instead of replacing)
# Usage: add_execution_context "key" "value"
add_execution_context() {
    local key="$1"
    local value="$2"

    if command -v jq &> /dev/null; then
        EXEC_LOG_CONTEXT=$(echo "$EXEC_LOG_CONTEXT" | jq --arg k "$key" --arg v "$value" '. + {($k): $v}')
    fi
}

# Save error details to dedicated error log
# Usage: save_error_to_log "story_id" "error_msg" "exit_code" "stderr" "stdout"
save_error_to_log() {
    local story_id="$1"
    local error_msg="$2"
    local exit_code="$3"
    local stderr="${4:-}"
    local stdout="${5:-}"

    # Create logs directory if it doesn't exist
    local error_log_dir=".claude-loop/logs"
    mkdir -p "$error_log_dir"

    local error_log_file="${error_log_dir}/error.log"
    local timestamp
    timestamp=$(exec_get_timestamp_iso)

    local exit_meaning
    exit_meaning=$(get_exit_code_meaning "$exit_code")
    local error_type
    error_type=$(classify_error_type "$error_msg" "$exit_code")

    # Get actionable suggestions
    local suggestions
    suggestions=$(get_error_suggestion "$error_msg" "$exit_code" "$error_type")

    # Get last 20 lines of stdout
    local stdout_excerpt=""
    if [ -n "$stdout" ]; then
        stdout_excerpt=$(echo "$stdout" | tail -n 20)
    fi

    # Build detailed error entry using echo (avoid heredoc issues with set -euo pipefail)
    {
        echo ""
        echo "================================================================================"
        echo "Timestamp: $timestamp"
        echo "Story ID:  $story_id"
        echo "Exit Code: $exit_code ($exit_meaning)"
        echo "Error Type: $error_type"
        echo "Error Message:"
        echo "$error_msg"
        echo ""
        echo "--- ACTIONABLE SUGGESTIONS ---"
        echo "$suggestions"
        echo ""
        echo "--- STDERR ---"
        echo "$stderr"
        echo ""
        echo "--- STDOUT (last 20 lines) ---"
        echo "$stdout_excerpt"
        echo "================================================================================"
        echo ""
    } >> "$error_log_file"
}

# Complete logging for a story execution
# Usage: log_execution_end "success" "" "" "" ""
# Usage: log_execution_end "failure" "Test failed: expected 5 but got 3" "2" "stderr content" "stdout content"
log_execution_end() {
    local exec_status="${1:-unknown}"
    local error_msg="${2:-}"
    local exit_code="${3:-0}"
    local stderr="${4:-}"
    local stdout="${5:-}"

    # Calculate duration
    local end_time
    end_time=$(exec_get_timestamp_ms)
    local duration_ms=$((end_time - EXEC_LOG_START_TIME))

    # Classify error if present
    local error_type=""
    if [ -n "$error_msg" ] && [ "$exec_status" != "success" ]; then
        error_type=$(classify_error_type "$error_msg" "$exit_code")
    fi

    # Save detailed error log if execution failed
    if [ "$exec_status" != "success" ] && [ -n "$error_msg" ]; then
        save_error_to_log "$EXEC_LOG_STORY_ID" "$error_msg" "$exit_code" "$stderr" "$stdout"
    fi

    # Build tools and file types JSON arrays
    local tools_json
    tools_json=$(list_to_json_array "$EXEC_LOG_TOOLS_USED")
    local file_types_json
    file_types_json=$(list_to_json_array "$EXEC_LOG_FILE_TYPES")

    # Build the complete log entry
    local log_entry
    log_entry=$(cat << EOF
{
  "story_id": "$(exec_json_escape "$EXEC_LOG_STORY_ID")",
  "story_title": "$(exec_json_escape "$EXEC_LOG_STORY_TITLE")",
  "timestamp_start": "$EXEC_LOG_START_ISO",
  "timestamp_end": "$(exec_get_timestamp_iso)",
  "duration_ms": $duration_ms,
  "status": "$exec_status",
  "exit_code": $exit_code,
  "exit_code_meaning": "$(get_exit_code_meaning "$exit_code")",
  "error_type": "$error_type",
  "error_message": "$(exec_json_escape "$error_msg")",
  "retry_count": $EXEC_LOG_RETRY_COUNT,
  "fallback_count": $EXEC_LOG_FALLBACK_COUNT,
  "attempted_actions": $EXEC_LOG_ACTIONS,
  "tools_used": $tools_json,
  "file_types": $file_types_json,
  "context": $EXEC_LOG_CONTEXT
}
EOF
)

    # Minify JSON (remove newlines and extra whitespace) for JSONL format
    local minified_entry
    if command -v jq &> /dev/null; then
        # Try jq first, fallback to simple minification if it fails
        minified_entry=$(echo "$log_entry" | jq -c '.' 2>/dev/null)
        if [ -z "$minified_entry" ]; then
            # jq failed, use simple minification
            minified_entry=$(echo "$log_entry" | tr -d '\n' | tr -s ' ')
        fi
    else
        # Fallback: simple minification
        minified_entry=$(echo "$log_entry" | tr -d '\n' | tr -s ' ')
    fi

    # Append to log file
    echo "$minified_entry" >> "$EXECUTION_LOG_FILE"

    # Display summary
    if [ "$exec_status" = "success" ]; then
        echo -e "${EXEC_GREEN}[EXEC-LOG]${EXEC_NC} Completed: $EXEC_LOG_STORY_ID (${duration_ms}ms)"
    else
        echo -e "${EXEC_RED}[EXEC-LOG]${EXEC_NC} Failed: $EXEC_LOG_STORY_ID - $error_type: $error_msg (exit $exit_code: $(get_exit_code_meaning "$exit_code"))"
    fi

    # Reset state
    EXEC_LOG_STORY_ID=""
    EXEC_LOG_STORY_TITLE=""
    EXEC_LOG_START_TIME=""
    EXEC_LOG_ACTIONS="[]"
}

# ============================================================================
# Query Functions
# ============================================================================

# Get total execution count
get_execution_count() {
    if [ -f "$EXECUTION_LOG_FILE" ]; then
        wc -l < "$EXECUTION_LOG_FILE" | tr -d ' '
    else
        echo "0"
    fi
}

# Get recent executions as JSON array
# Usage: get_recent_executions 10
get_recent_executions() {
    local count="${1:-10}"

    if [ ! -f "$EXECUTION_LOG_FILE" ]; then
        echo "[]"
        return
    fi

    if command -v jq &> /dev/null; then
        tail -n "$count" "$EXECUTION_LOG_FILE" | jq -s '.'
    else
        echo "["
        tail -n "$count" "$EXECUTION_LOG_FILE" | head -c -1
        echo "]"
    fi
}

# Get executions for a specific story
# Usage: get_story_executions "SI-001"
get_story_executions() {
    local story_id="$1"

    if [ ! -f "$EXECUTION_LOG_FILE" ]; then
        echo "[]"
        return
    fi

    if command -v jq &> /dev/null; then
        grep "\"story_id\":\"$story_id\"" "$EXECUTION_LOG_FILE" | jq -s '.'
    else
        grep "\"story_id\":\"$story_id\"" "$EXECUTION_LOG_FILE"
    fi
}

# Get failure count by error type
# Usage: get_failure_counts
get_failure_counts() {
    if [ ! -f "$EXECUTION_LOG_FILE" ]; then
        echo "{}"
        return
    fi

    if command -v jq &> /dev/null; then
        jq -s '
          [.[] | select(.status != "success")] |
          group_by(.error_type) |
          map({key: .[0].error_type, value: length}) |
          from_entries
        ' "$EXECUTION_LOG_FILE"
    else
        echo "{}"
    fi
}

# Get executions since a specific date
# Usage: get_executions_since "2026-01-01T00:00:00Z"
get_executions_since() {
    local since_date="$1"

    if [ ! -f "$EXECUTION_LOG_FILE" ]; then
        echo "[]"
        return
    fi

    if command -v jq &> /dev/null; then
        jq -s --arg since "$since_date" '
          [.[] | select(.timestamp_start >= $since)]
        ' "$EXECUTION_LOG_FILE"
    else
        echo "[]"
    fi
}

# Get summary statistics
get_execution_stats() {
    if [ ! -f "$EXECUTION_LOG_FILE" ]; then
        cat << EOF
{
  "total_executions": 0,
  "success_count": 0,
  "failure_count": 0,
  "success_rate": 0,
  "avg_duration_ms": 0,
  "total_retries": 0,
  "error_types": {}
}
EOF
        return
    fi

    if command -v jq &> /dev/null; then
        jq -s '
          {
            total_executions: length,
            success_count: ([.[] | select(.status == "success")] | length),
            failure_count: ([.[] | select(.status != "success")] | length),
            success_rate: (([.[] | select(.status == "success")] | length) / (length | if . == 0 then 1 else . end) * 100 | floor),
            avg_duration_ms: (([.[] | .duration_ms] | add) / (length | if . == 0 then 1 else . end) | floor),
            total_retries: ([.[] | .retry_count] | add),
            error_types: (
              [.[] | select(.status != "success")] |
              group_by(.error_type) |
              map({key: .[0].error_type, value: length}) |
              from_entries
            )
          }
        ' "$EXECUTION_LOG_FILE"
    else
        local total
        total=$(wc -l < "$EXECUTION_LOG_FILE" | tr -d ' ')
        echo "{\"total_executions\": $total}"
    fi
}

# ============================================================================
# CLI Interface
# ============================================================================

# Main CLI handler when script is run directly
exec_logger_cli() {
    local command="${1:-help}"
    shift || true

    case "$command" in
        stats)
            get_execution_stats
            ;;
        recent)
            local count="${1:-10}"
            get_recent_executions "$count"
            ;;
        story)
            local story_id="$1"
            if [ -z "$story_id" ]; then
                echo "Usage: execution-logger.sh story <story_id>"
                exit 1
            fi
            get_story_executions "$story_id"
            ;;
        failures)
            get_failure_counts
            ;;
        since)
            local date="$1"
            if [ -z "$date" ]; then
                echo "Usage: execution-logger.sh since <ISO_DATE>"
                exit 1
            fi
            get_executions_since "$date"
            ;;
        count)
            get_execution_count
            ;;
        tail)
            local count="${1:-20}"
            if [ -f "$EXECUTION_LOG_FILE" ]; then
                tail -n "$count" "$EXECUTION_LOG_FILE" | jq '.'
            else
                echo "No log file found"
            fi
            ;;
        help|--help|-h)
            cat << EOF
execution-logger.sh - Query and manage execution logs

USAGE:
    ./lib/execution-logger.sh <command> [options]

COMMANDS:
    stats           Show summary statistics
    recent [N]      Show last N executions (default: 10)
    story <ID>      Show executions for a specific story
    failures        Show failure counts by error type
    since <DATE>    Show executions since ISO date
    count           Show total execution count
    tail [N]        Show last N log entries (default: 20)
    help            Show this help message

EXAMPLES:
    ./lib/execution-logger.sh stats
    ./lib/execution-logger.sh recent 5
    ./lib/execution-logger.sh story SI-001
    ./lib/execution-logger.sh since 2026-01-10T00:00:00Z

LOG FILE:
    $EXECUTION_LOG_FILE

EOF
            ;;
        *)
            echo "Unknown command: $command"
            echo "Run './lib/execution-logger.sh help' for usage"
            exit 1
            ;;
    esac
}

# ============================================================================
# Export Functions for Sourcing
# ============================================================================

export -f exec_get_timestamp_ms
export -f exec_get_timestamp_iso
export -f exec_json_escape
export -f exec_ensure_log_dir
export -f get_exit_code_meaning
export -f get_error_suggestion
export -f classify_error_type
export -f get_file_type
export -f save_error_to_log
export -f log_execution_start
export -f log_action
export -f log_retry
export -f log_fallback
export -f set_execution_context
export -f add_execution_context
export -f log_execution_end
export -f get_execution_count
export -f get_recent_executions
export -f get_story_executions
export -f get_failure_counts
export -f get_executions_since
export -f get_execution_stats

# Run CLI if script is executed directly (not sourced)
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    exec_logger_cli "$@"
fi
