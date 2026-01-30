#!/bin/bash
#
# worker.sh - Single-Story Worker for Parallel Execution
#
# Executes a single user story in an isolated environment for parallel execution.
# Each worker:
#   - Runs in its own isolated working directory
#   - Uses the selected model (haiku/sonnet/opus)
#   - Captures stdout/stderr to worker-specific logs
#   - Returns structured results (success/failure, files changed, tokens)
#   - Handles timeouts gracefully
#
# Usage:
#   ./lib/worker.sh <story_id> [options]
#
# Options:
#   --prd FILE              Path to prd.json (default: ./prd.json)
#   --model MODEL           Model to use: haiku|sonnet|opus (default: sonnet)
#   --work-dir DIR          Base working directory (default: .claude-loop/workers)
#   --timeout SECONDS       Timeout in seconds (default: 600)
#   --log-dir DIR           Log output directory (default: .claude-loop/workers/<story_id>)
#   --prompt-file FILE      Path to prompt.md (default: ./prompt.md)
#   --json                  Output result as JSON
#   --verbose               Enable verbose output
#   -h, --help              Show this help message
#
# Output (JSON):
#   {
#     "story_id": "US-001",
#     "success": true|false,
#     "exit_code": 0,
#     "duration_ms": 12345,
#     "tokens_in": 5000,
#     "tokens_out": 2000,
#     "files_changed": ["path/to/file.ts"],
#     "model": "sonnet",
#     "log_file": ".claude-loop/workers/US-001/output.log",
#     "error": null
#   }

set -euo pipefail

# Source hidden intelligence layer (silent - no user-facing output)
WORKER_SCRIPT_DIR_EARLY="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [[ -f "${WORKER_SCRIPT_DIR_EARLY}/hidden-intelligence.sh" ]]; then
    source "${WORKER_SCRIPT_DIR_EARLY}/hidden-intelligence.sh" 2>/dev/null || true
fi

# ============================================================================
# Configuration
# ============================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PARENT_DIR="$(dirname "$SCRIPT_DIR")"

# Default values
PRD_FILE="./prd.json"
PROMPT_FILE="${PARENT_DIR}/prompt.md"
MODEL="sonnet"
BASE_WORK_DIR=".claude-loop/workers"
TIMEOUT_SECONDS=600
LOG_DIR=""
JSON_OUTPUT=false
VERBOSE=false
SANITIZE_OUTPUT="${SANITIZE_OUTPUT:-true}"  # Enable output sanitization by default
SANITIZE_MAX_CHARS="${SANITIZE_MAX_CHARS:-30000}"  # Max chars before truncation

# Delegation support
DELEGATION_DEPTH="${DELEGATION_DEPTH:-0}"
MAX_DELEGATION_DEPTH="${MAX_DELEGATION_DEPTH:-2}"

# Worker state
WORKER_PID=""
WORKER_START_TIME=""
WORKER_STORY_ID=""
WORKER_DIR=""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# ============================================================================
# Helper Functions
# ============================================================================

# Sanitize tool output to prevent context overflow
# Uses tool_sanitizer.py if available, otherwise passes through unchanged
sanitize_output() {
    local input="$1"
    local max_chars="${2:-8000}"

    # Check if tool_sanitizer.py is available
    if [ -f "$SCRIPT_DIR/tool_sanitizer.py" ]; then
        echo "$input" | python3 "$SCRIPT_DIR/tool_sanitizer.py" - "$max_chars" 2>/dev/null || echo "$input"
    else
        echo "$input"
    fi
}

log_info() {
    if ! $JSON_OUTPUT; then
        echo -e "${BLUE}[WORKER]${NC} $1" >&2
    fi
}

log_success() {
    if ! $JSON_OUTPUT; then
        echo -e "${GREEN}[WORKER]${NC} $1" >&2
    fi
}

log_warn() {
    if ! $JSON_OUTPUT; then
        echo -e "${YELLOW}[WORKER]${NC} $1" >&2
    fi
}

log_error() {
    if ! $JSON_OUTPUT; then
        echo -e "${RED}[WORKER]${NC} $1" >&2
    fi
}

log_debug() {
    if $VERBOSE && ! $JSON_OUTPUT; then
        echo -e "${CYAN}[DEBUG]${NC} $1" >&2
    fi
}

show_help() {
    cat << EOF
worker.sh - Single-Story Worker for Parallel Execution

USAGE:
    ./lib/worker.sh <story_id> [OPTIONS]

OPTIONS:
    --prd FILE              Path to prd.json (default: ./prd.json)
    --model MODEL           Model to use: haiku|sonnet|opus (default: sonnet)
    --work-dir DIR          Base working directory (default: .claude-loop/workers)
    --timeout SECONDS       Timeout in seconds (default: 600)
    --log-dir DIR           Log output directory (default: .claude-loop/workers/<story_id>)
    --prompt-file FILE      Path to prompt.md (default: ./prompt.md)
    --json                  Output result as JSON
    --verbose               Enable verbose output
    -h, --help              Show this help message

DESCRIPTION:
    Executes a single user story in an isolated environment. Designed to be
    called by the parallel executor for concurrent story execution.

    Each worker:
    - Creates an isolated working directory
    - Uses the specified model for Claude invocation
    - Captures all output to worker-specific logs
    - Returns structured results on completion
    - Cleans up on timeout or error

DELEGATION SUPPORT:
    Set DELEGATION_DEPTH environment variable for hierarchical delegation:
        DELEGATION_DEPTH=0  Root level (default)
        DELEGATION_DEPTH=1  First-level subordinate
        DELEGATION_DEPTH=2  Second-level subordinate (max)

    Example:
        DELEGATION_DEPTH=1 ./lib/worker.sh US-007-DEL-001

EXAMPLES:
    # Execute a story with default settings
    ./lib/worker.sh US-001

    # Execute with specific model and timeout
    ./lib/worker.sh US-002 --model opus --timeout 300

    # Get JSON output for scripting
    ./lib/worker.sh US-003 --json

    # Verbose mode for debugging
    ./lib/worker.sh US-004 --verbose

EOF
}

# Get timestamp in milliseconds (macOS compatible)
get_timestamp_ms() {
    if [[ "$OSTYPE" == "darwin"* ]]; then
        perl -MTime::HiRes=time -e 'printf "%.0f\n", time * 1000'
    else
        echo $(($(date +%s%N) / 1000000))
    fi
}

# Get ISO timestamp
get_timestamp_iso() {
    date -u +"%Y-%m-%dT%H:%M:%SZ"
}

# ============================================================================
# Story Data Functions
# ============================================================================

# Get story data from prd.json
get_story_data() {
    local story_id="$1"
    jq -r --arg id "$story_id" '.userStories[] | select(.id == $id)' "$PRD_FILE"
}

# Get story title
get_story_title() {
    local story_id="$1"
    jq -r --arg id "$story_id" '.userStories[] | select(.id == $id) | .title' "$PRD_FILE"
}

# Get story description
get_story_description() {
    local story_id="$1"
    jq -r --arg id "$story_id" '.userStories[] | select(.id == $id) | .description' "$PRD_FILE"
}

# Get story acceptance criteria as a list
get_story_criteria() {
    local story_id="$1"
    jq -r --arg id "$story_id" '.userStories[] | select(.id == $id) | .acceptanceCriteria[]' "$PRD_FILE"
}

# Get story file scope
get_story_file_scope() {
    local story_id="$1"
    jq -r --arg id "$story_id" '.userStories[] | select(.id == $id) | .fileScope // [] | .[]' "$PRD_FILE"
}

# Check if story exists
story_exists() {
    local story_id="$1"
    local count
    count=$(jq -r --arg id "$story_id" '[.userStories[] | select(.id == $id)] | length' "$PRD_FILE")
    [ "$count" -gt 0 ]
}

# Check if story is already complete
story_is_complete() {
    local story_id="$1"
    local passes
    passes=$(jq -r --arg id "$story_id" '.userStories[] | select(.id == $id) | .passes' "$PRD_FILE")
    [ "$passes" = "true" ]
}

# ============================================================================
# Worker Isolation Functions
# ============================================================================

# Create isolated working directory for worker
# Sets global WORKER_DIR and LOG_DIR variables
create_worker_directory() {
    local story_id="$1"
    local timestamp
    timestamp=$(date +%Y%m%d_%H%M%S)

    WORKER_DIR="${BASE_WORK_DIR}/${story_id}_${timestamp}"

    # Create directory structure
    mkdir -p "$WORKER_DIR"
    mkdir -p "$WORKER_DIR/logs"

    # Set log directory if not specified
    if [ -z "$LOG_DIR" ]; then
        LOG_DIR="$WORKER_DIR/logs"
    fi

    log_debug "Worker directory: $WORKER_DIR"
    log_debug "Log directory: $LOG_DIR"
}

# Clean up worker directory on exit
cleanup_worker() {
    local exit_code=${1:-0}

    if [ -n "$WORKER_PID" ] && kill -0 "$WORKER_PID" 2>/dev/null; then
        log_warn "Killing worker process $WORKER_PID"
        kill -TERM "$WORKER_PID" 2>/dev/null || true
        sleep 1
        kill -KILL "$WORKER_PID" 2>/dev/null || true
    fi

    # Don't clean up logs if there was an error
    if [ "$exit_code" -eq 0 ] && [ -n "$WORKER_DIR" ] && [ -d "$WORKER_DIR" ]; then
        # Keep logs, but clean up temp files
        find "$WORKER_DIR" -type f -name "*.tmp" -delete 2>/dev/null || true
    fi
}

# Set up signal handlers for cleanup
setup_signal_handlers() {
    trap 'cleanup_worker 1' SIGINT SIGTERM
    trap 'cleanup_worker $?' EXIT

    # Hidden intelligence: Stop heartbeat on exit
    trap 'stop_worker_heartbeat "$worker_id" 2>/dev/null || true' EXIT
}

# ============================================================================
# Prompt Building Functions
# ============================================================================

# Build the worker-specific prompt
build_worker_prompt() {
    local story_id="$1"

    # Read base prompt
    local prompt
    prompt=$(cat "$PROMPT_FILE")

    # Add worker-specific context
    local story_title
    story_title=$(get_story_title "$story_id")
    local story_description
    story_description=$(get_story_description "$story_id")

    # Get file scope if available
    local file_scope
    file_scope=$(get_story_file_scope "$story_id" | paste -sd ',' -)

    # Build focused prompt for this specific story
    local worker_header="
# Worker Execution Context

You are executing as a parallel worker for story **${story_id}**: ${story_title}

## Story Details
- **ID**: ${story_id}
- **Title**: ${story_title}
- **Description**: ${story_description}
"

    if [ -n "$file_scope" ]; then
        worker_header+="- **File Scope**: ${file_scope}
"
    fi

    worker_header+="
## Worker Instructions

1. Focus ONLY on this specific story (${story_id})
2. Do NOT modify files outside the story's file scope
3. Complete all acceptance criteria for this story
4. Output progress as you work
5. End with either:
   - 'WORKER_SUCCESS: ${story_id}' if all criteria are met
   - 'WORKER_FAILURE: ${story_id}: <reason>' if unable to complete

---

"

    # Combine header with base prompt
    echo "${worker_header}${prompt}"
}

# ============================================================================
# Execution Functions
# ============================================================================

# Get the timeout command (macOS uses gtimeout from coreutils)
get_timeout_cmd() {
    if command -v timeout &> /dev/null; then
        echo "timeout"
    elif command -v gtimeout &> /dev/null; then
        echo "gtimeout"
    else
        echo ""
    fi
}

# Execute Claude with the worker prompt
# Returns exit code from Claude execution
# Creates JSON response file at ${output_file}.json with token usage
execute_worker() {
    local story_id="$1"
    local prompt="$2"
    local output_file="$3"
    local error_file="$4"

    log_info "Starting execution for $story_id (model: $MODEL)"

    # Build Claude command with model selection and JSON output
    local claude_cmd="claude --print --dangerously-skip-permissions --model $MODEL --output-format json"

    log_debug "Executing: $claude_cmd"

    # Get timeout command (macOS compatibility)
    local timeout_cmd
    timeout_cmd=$(get_timeout_cmd)

    # Execute Claude and capture JSON output
    local json_output_file="${output_file}.json"
    local exit_code=0
    if [ -n "$timeout_cmd" ]; then
        echo "$prompt" | $timeout_cmd "$TIMEOUT_SECONDS" $claude_cmd > "$json_output_file" 2> "$error_file" || exit_code=$?
    else
        # Fallback: run without timeout but log a warning
        log_warn "No timeout command available - running without timeout"
        echo "$prompt" | $claude_cmd > "$json_output_file" 2> "$error_file" || exit_code=$?
    fi

    # Extract text content from JSON response for backward compatibility
    # The JSON format has: {"content": [{"type": "text", "text": "..."}], "usage": {...}}
    if [ -f "$json_output_file" ] && [ -s "$json_output_file" ]; then
        # Extract text content using jq
        if command -v jq >/dev/null 2>&1; then
            local extracted_text
            extracted_text=$(jq -r '.content[]? | select(.type == "text") | .text' "$json_output_file" 2>/dev/null || {
                # Fallback: if jq fails, use raw JSON
                log_warn "Failed to extract text from JSON response, using raw output"
                cat "$json_output_file"
            })

            # Apply sanitization if enabled
            if [ "$SANITIZE_OUTPUT" = "true" ]; then
                echo "$extracted_text" | sanitize_output - "$SANITIZE_MAX_CHARS" > "$output_file"
            else
                echo "$extracted_text" > "$output_file"
            fi
        else
            # No jq available - copy entire JSON
            log_warn "jq not available, using raw JSON output"
            if [ "$SANITIZE_OUTPUT" = "true" ]; then
                sanitize_output "$(cat "$json_output_file")" "$SANITIZE_MAX_CHARS" > "$output_file"
            else
                cat "$json_output_file" > "$output_file"
            fi
        fi
    else
        # No JSON output - create empty output file
        touch "$output_file"
    fi

    return $exit_code
}

# Check worker result for success/failure markers
# Supports both JSON format and legacy sigil format
check_worker_result() {
    local output_file="$1"
    local story_id="$2"

    # Try JSON format first (if present)
    # Look for JSON blocks with "action" field
    if grep -q '"action"' "$output_file"; then
        # Try to extract JSON block
        local json_block=""

        # Try to find JSON code block first (```json ... ```)
        if grep -q '```json' "$output_file"; then
            json_block=$(sed -n '/```json/,/```/p' "$output_file" | sed '1d;$d')
        fi

        # If no code block, try to find JSON object
        if [ -z "$json_block" ]; then
            json_block=$(grep -E '^\s*\{.*"action"' "$output_file" | head -1)
        fi

        # Parse action from JSON
        if [ -n "$json_block" ]; then
            local action
            action=$(echo "$json_block" | jq -r '.action // empty' 2>/dev/null)

            case "$action" in
                complete|commit)
                    return 0
                    ;;
                skip|delegate)
                    return 1
                    ;;
            esac
        fi
    fi

    # Fallback to sigil-based detection (backward compatibility)
    if grep -q "WORKER_SUCCESS: $story_id" "$output_file"; then
        return 0
    elif grep -q "WORKER_FAILURE: $story_id" "$output_file"; then
        return 1
    elif grep -q "<loop>COMPLETE</loop>" "$output_file"; then
        # Also accept the standard completion signal
        return 0
    else
        # No explicit marker - check for error patterns
        if grep -qi "error\|failed\|exception" "$output_file"; then
            return 1
        fi
        # Assume success if no error patterns found
        return 0
    fi
}

# Count files changed (basic git-based detection)
get_files_changed() {
    # Get list of modified files since worker started
    git diff --name-only HEAD 2>/dev/null || echo ""
}

# Estimate tokens from text length (fallback method)
estimate_tokens() {
    local text="$1"
    local char_count=${#text}
    echo $((char_count / 4))
}

# Extract token usage from Claude JSON response
# Usage: extract_token_usage <json_file> <input|output|cache_read|cache_creation>
# Returns token count or 0 if not found
extract_token_usage() {
    local json_file="$1"
    local token_type="$2"

    if [ ! -f "$json_file" ]; then
        echo "0"
        return
    fi

    if ! command -v jq >/dev/null 2>&1; then
        echo "0"
        return
    fi

    local tokens
    case "$token_type" in
        input)
            # Get input_tokens, including cache_read_input_tokens
            tokens=$(jq -r '(.usage.input_tokens // 0) + (.usage.cache_read_input_tokens // 0)' "$json_file" 2>/dev/null || echo "0")
            ;;
        output)
            tokens=$(jq -r '.usage.output_tokens // 0' "$json_file" 2>/dev/null || echo "0")
            ;;
        cache_read)
            tokens=$(jq -r '.usage.cache_read_input_tokens // 0' "$json_file" 2>/dev/null || echo "0")
            ;;
        cache_creation)
            tokens=$(jq -r '.usage.cache_creation_input_tokens // 0' "$json_file" 2>/dev/null || echo "0")
            ;;
        *)
            echo "0"
            return
            ;;
    esac

    # Ensure numeric output
    if ! [[ "$tokens" =~ ^[0-9]+$ ]]; then
        echo "0"
    else
        echo "$tokens"
    fi
}

# ============================================================================
# Result Functions
# ============================================================================

# Output result as JSON
output_result_json() {
    local story_id="$1"
    local success="$2"
    local exit_code="$3"
    local duration_ms="$4"
    local tokens_in="$5"
    local tokens_out="$6"
    local model="$7"
    local log_file="$8"
    local error="${9:-null}"
    local files_changed="${10:-[]}"

    # Escape error message for JSON
    if [ "$error" != "null" ]; then
        error="\"$(echo "$error" | sed 's/"/\\"/g' | tr '\n' ' ')\""
    fi

    cat << EOF
{
  "story_id": "$story_id",
  "success": $success,
  "exit_code": $exit_code,
  "duration_ms": $duration_ms,
  "tokens_in": $tokens_in,
  "tokens_out": $tokens_out,
  "model": "$model",
  "log_file": "$log_file",
  "error": $error,
  "files_changed": $files_changed,
  "delegation_depth": $DELEGATION_DEPTH,
  "timestamp": "$(get_timestamp_iso)"
}
EOF
}

# Output result as human-readable text
output_result_text() {
    local story_id="$1"
    local success="$2"
    local exit_code="$3"
    local duration_ms="$4"
    local tokens_in="$5"
    local tokens_out="$6"
    local model="$7"
    local log_file="$8"
    local error="${9:-}"

    local duration_s=$((duration_ms / 1000))

    if [ "$success" = "true" ]; then
        log_success "Story $story_id completed successfully"
    else
        log_error "Story $story_id failed"
        if [ -n "$error" ]; then
            log_error "Error: $error"
        fi
    fi

    echo ""
    echo "Worker Result:"
    echo "  Story:      $story_id"
    echo "  Success:    $success"
    echo "  Exit Code:  $exit_code"
    echo "  Duration:   ${duration_s}s"
    echo "  Tokens:     $tokens_in in / $tokens_out out"
    echo "  Model:      $model"
    echo "  Log:        $log_file"
}

# ============================================================================
# Main Worker Function
# ============================================================================

run_worker() {
    local story_id="$1"

    # Hidden intelligence: Start heartbeat (background, silent)
    local worker_id="worker-${story_id}-$$"
    local prd_id=$(basename "$(dirname "$PRD_FILE")" 2>/dev/null || echo "unknown")
    start_worker_heartbeat "$worker_id" "$prd_id" "$story_id" 2>/dev/null || true

    # Validate delegation depth
    if (( DELEGATION_DEPTH > MAX_DELEGATION_DEPTH )); then
        log_error "Delegation depth limit exceeded"
        log_error "Current depth: $DELEGATION_DEPTH"
        log_error "Maximum allowed: $MAX_DELEGATION_DEPTH"

        # Hidden intelligence: Log failure
        log_failure_silent "$prd_id" "logic_error" "Delegation depth limit exceeded" 1 "$story_id" "$worker_id" 2>/dev/null || true
        exit 1
    fi

    if (( DELEGATION_DEPTH > 0 )); then
        log_info "Running as subordinate agent (depth: $DELEGATION_DEPTH)"
    fi

    # Validate inputs
    if ! [ -f "$PRD_FILE" ]; then
        log_error "PRD file not found: $PRD_FILE"
        exit 1
    fi

    if ! [ -f "$PROMPT_FILE" ]; then
        log_error "Prompt file not found: $PROMPT_FILE"
        exit 1
    fi

    if ! story_exists "$story_id"; then
        log_error "Story not found: $story_id"
        exit 1
    fi

    if story_is_complete "$story_id"; then
        log_warn "Story $story_id is already complete"
        if $JSON_OUTPUT; then
            output_result_json "$story_id" "true" 0 0 0 0 "$MODEL" "" "Story already complete" "[]"
        fi
        exit 0
    fi

    # Record start time
    WORKER_START_TIME=$(get_timestamp_ms)
    WORKER_STORY_ID="$story_id"

    # Create isolated working directory (sets WORKER_DIR and LOG_DIR)
    create_worker_directory "$story_id"
    local output_file="${LOG_DIR}/output.log"
    local error_file="${LOG_DIR}/error.log"
    local combined_log="${LOG_DIR}/combined.log"

    log_info "Story: $story_id"
    log_info "Model: $MODEL"
    log_info "Timeout: ${TIMEOUT_SECONDS}s"
    log_info "Work Dir: $WORKER_DIR"

    # Clone source repository if specified in PRD
    if [ -f "$SCRIPT_DIR/workspace-manager.sh" ]; then
        source "$SCRIPT_DIR/workspace-manager.sh"

        # Get source_project from PRD
        local source_project
        source_project=$(get_source_project_from_prd "$PRD_FILE")

        if [ -n "$source_project" ] && [ "$source_project" != "null" ]; then
            log_info "Cloning source project: $source_project"
            clone_source_to_workspace "$source_project" "$WORKER_DIR"
        fi
    fi

    # Build prompt
    log_debug "Building worker prompt..."
    local prompt
    prompt=$(build_worker_prompt "$story_id")
    log_debug "Prompt built successfully"

    # Save prompt for debugging
    echo "$prompt" > "${LOG_DIR}/prompt.txt"

    # Execute worker (creates JSON response at ${output_file}.json)
    local exit_code=0
    execute_worker "$story_id" "$prompt" "$output_file" "$error_file" || exit_code=$?

    # Calculate duration
    local end_time
    end_time=$(get_timestamp_ms)
    local duration_ms=$((end_time - WORKER_START_TIME))

    # Extract actual token usage from JSON response
    local json_response="${output_file}.json"
    local tokens_in=0
    local tokens_out=0
    local cache_read_tokens=0
    local cache_creation_tokens=0

    if [ -f "$json_response" ]; then
        tokens_in=$(extract_token_usage "$json_response" "input")
        tokens_out=$(extract_token_usage "$json_response" "output")
        cache_read_tokens=$(extract_token_usage "$json_response" "cache_read")
        cache_creation_tokens=$(extract_token_usage "$json_response" "cache_creation")
        log_debug "Token usage from API: input=$tokens_in output=$tokens_out cache_read=$cache_read_tokens cache_creation=$cache_creation_tokens"
    else
        # Fallback to estimates if JSON not available
        log_warn "JSON response not found, falling back to token estimation"
        tokens_in=$(estimate_tokens "$prompt")
        local output_content
        output_content=$(cat "$output_file" 2>/dev/null || echo "")
        tokens_out=$(estimate_tokens "$output_content")
    fi

    # Read stdout and stderr content for logging
    local stdout_content=""
    local stderr_content=""
    if [ -f "$output_file" ]; then
        stdout_content=$(cat "$output_file")
    fi
    if [ -f "$error_file" ]; then
        stderr_content=$(cat "$error_file")
    fi

    # Combine logs
    {
        echo "=== STDOUT ==="
        cat "$output_file"
        echo ""
        echo "=== STDERR ==="
        cat "$error_file"
    } > "$combined_log"

    # Determine success/failure
    local success="false"
    local error=""

    if [ $exit_code -eq 0 ]; then
        if check_worker_result "$output_file" "$story_id"; then
            success="true"
        else
            error="Worker completed but story criteria not met"
        fi
    elif [ $exit_code -eq 124 ]; then
        # Timeout exit code
        error="Worker timed out after ${TIMEOUT_SECONDS}s"
    else
        error="Worker exited with code $exit_code"
        # Check error file for more details
        if [ -s "$error_file" ]; then
            local error_content
            error_content=$(head -n 5 "$error_file" | tr '\n' ' ')
            error="$error: $error_content"
        fi
    fi

    # Log execution end with full stderr/stdout if available and execution failed
    if [ -f "$SCRIPT_DIR/execution-logger.sh" ] && [ "$success" = "false" ]; then
        source "$SCRIPT_DIR/execution-logger.sh"
        log_execution_start "$story_id" "$(get_story_title "$story_id")" "{}"
        log_execution_end "failure" "$error" "$exit_code" "$stderr_content" "$stdout_content"
    fi

    # Save checkpoint after iteration (US-001: checkpoint after every iteration)
    # Get current iteration count from PRD or default to 1
    local current_iteration=1
    if [ -f "$SCRIPT_DIR/session-state.sh" ]; then
        source "$SCRIPT_DIR/session-state.sh"

        # Get PRD state for checkpoint
        local prd_state="{}"
        if [ -f "$PRD_FILE" ]; then
            prd_state=$(cat "$PRD_FILE")
        fi

        # Save checkpoint (silently, don't fail if it errors)
        save_checkpoint "$story_id" "$current_iteration" "$prd_state" 2>/dev/null || true
    fi

    # Get files changed
    local files_changed
    files_changed=$(get_files_changed | jq -R -s 'split("\n") | map(select(length > 0))' 2>/dev/null || echo "[]")

    # Output result
    if $JSON_OUTPUT; then
        output_result_json "$story_id" "$success" "$exit_code" "$duration_ms" \
            "$tokens_in" "$tokens_out" "$MODEL" "$combined_log" "$error" "$files_changed"
    else
        output_result_text "$story_id" "$success" "$exit_code" "$duration_ms" \
            "$tokens_in" "$tokens_out" "$MODEL" "$combined_log" "$error"
    fi

    # Return appropriate exit code
    if [ "$success" = "true" ]; then
        exit 0
    else
        exit 1
    fi
}

# ============================================================================
# Main Entry Point
# ============================================================================

main() {
    # Parse command line arguments
    local story_id=""

    while [[ $# -gt 0 ]]; do
        case $1 in
            --prd)
                PRD_FILE="$2"
                shift 2
                ;;
            --model)
                MODEL="$2"
                shift 2
                ;;
            --work-dir)
                BASE_WORK_DIR="$2"
                shift 2
                ;;
            --timeout)
                TIMEOUT_SECONDS="$2"
                shift 2
                ;;
            --log-dir)
                LOG_DIR="$2"
                shift 2
                ;;
            --prompt-file)
                PROMPT_FILE="$2"
                shift 2
                ;;
            --json)
                JSON_OUTPUT=true
                shift
                ;;
            --verbose)
                VERBOSE=true
                shift
                ;;
            -h|--help)
                show_help
                exit 0
                ;;
            -*)
                log_error "Unknown option: $1"
                show_help
                exit 1
                ;;
            *)
                if [ -z "$story_id" ]; then
                    story_id="$1"
                else
                    log_error "Unexpected argument: $1"
                    show_help
                    exit 1
                fi
                shift
                ;;
        esac
    done

    # Validate story ID
    if [ -z "$story_id" ]; then
        log_error "Story ID required"
        show_help
        exit 1
    fi

    # Validate model
    case "$MODEL" in
        haiku|sonnet|opus)
            ;;
        *)
            log_error "Invalid model: $MODEL (must be haiku, sonnet, or opus)"
            exit 1
            ;;
    esac

    # Set up cleanup handlers
    setup_signal_handlers

    # Run the worker
    run_worker "$story_id"
}

# Run main
main "$@"
