#!/usr/bin/env bash
#
# parallel.sh - Parallel Group Executor for Claude-Loop
#
# Executes groups of independent stories in parallel using worker processes.
# Each worker runs in isolation and results are aggregated after completion.
#
# Features:
#   - Launch workers as background processes
#   - Wait for all workers in a group to complete
#   - Collect and aggregate results from all workers
#   - Support --max-workers to limit parallelism
#   - Display parallel execution progress in terminal
#
# Usage:
#   source lib/parallel.sh
#   execute_parallel_group "story1,story2,story3" [options]
#
# Options:
#   --max-workers N       Maximum parallel workers (default: 3)
#   --prd FILE           Path to prd.json (default: ./prd.json)
#   --model-strategy STR  Model selection strategy (default: auto)
#   --verbose            Enable verbose output
#

set -euo pipefail

# ============================================================================
# Configuration
# ============================================================================

PARALLEL_SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PARALLEL_PARENT_DIR="$(dirname "$PARALLEL_SCRIPT_DIR")"

# Default values
PARALLEL_MAX_WORKERS=3
PARALLEL_PRD_FILE="./prd.json"
PARALLEL_MODEL_STRATEGY="auto"
PARALLEL_VERBOSE=false

# Worker tracking (using file-based storage for bash 3.x compatibility)
# Stores story_id:pid:worker_dir:result_file, one per line
PARALLEL_WORKER_TRACKING_FILE=""
PARALLEL_ACTIVE_WORKERS=""  # Space-separated list of story_ids

# Group execution state
PARALLEL_GROUP_ID=""
PARALLEL_GROUP_START_TIME=""
PARALLEL_GROUP_RESULTS=()

# Colors for output
PAR_RED='\033[0;31m'
PAR_GREEN='\033[0;32m'
PAR_YELLOW='\033[1;33m'
PAR_BLUE='\033[0;34m'
PAR_CYAN='\033[0;36m'
PAR_MAGENTA='\033[0;35m'
PAR_NC='\033[0m' # No Color

# ============================================================================
# Helper Functions
# ============================================================================

par_log_info() {
    echo -e "${PAR_BLUE}[PARALLEL]${PAR_NC} $1"
}

par_log_success() {
    echo -e "${PAR_GREEN}[PARALLEL]${PAR_NC} $1"
}

par_log_warn() {
    echo -e "${PAR_YELLOW}[PARALLEL]${PAR_NC} $1"
}

par_log_error() {
    echo -e "${PAR_RED}[PARALLEL]${PAR_NC} $1"
}

par_log_progress() {
    echo -e "${PAR_CYAN}[PARALLEL]${PAR_NC} $1"
}

par_log_debug() {
    if $PARALLEL_VERBOSE; then
        echo -e "${PAR_MAGENTA}[DEBUG]${PAR_NC} $1"
    fi
}

# Get timestamp in milliseconds (macOS compatible)
par_get_timestamp_ms() {
    if [[ "$OSTYPE" == "darwin"* ]]; then
        perl -MTime::HiRes=time -e 'printf "%.0f\n", time * 1000'
    else
        echo $(($(date +%s%N) / 1000000))
    fi
}

# Get ISO timestamp
par_get_timestamp_iso() {
    date -u +"%Y-%m-%dT%H:%M:%SZ"
}

# Format duration for display
par_format_duration() {
    local duration_ms="$1"
    local duration_s=$((duration_ms / 1000))

    if [ "$duration_s" -lt 60 ]; then
        echo "${duration_s}s"
    else
        local mins=$((duration_s / 60))
        local secs=$((duration_s % 60))
        echo "${mins}m ${secs}s"
    fi
}

# ============================================================================
# Worker Tracking Functions (bash 3.x compatible)
# ============================================================================

# Initialize worker tracking
init_worker_tracking() {
    PARALLEL_WORKER_TRACKING_FILE=".claude-loop/workers/.tracking_${PARALLEL_GROUP_ID}"
    mkdir -p "$(dirname "$PARALLEL_WORKER_TRACKING_FILE")"
    : > "$PARALLEL_WORKER_TRACKING_FILE"
    PARALLEL_ACTIVE_WORKERS=""
}

# Add worker to tracking
# Usage: add_worker_tracking "story_id" "pid" "worker_dir" "result_file"
add_worker_tracking() {
    local story_id="$1"
    local pid="$2"
    local worker_dir="$3"
    local result_file="$4"

    echo "${story_id}:${pid}:${worker_dir}:${result_file}" >> "$PARALLEL_WORKER_TRACKING_FILE"
    PARALLEL_ACTIVE_WORKERS="$PARALLEL_ACTIVE_WORKERS $story_id"
}

# Get worker info by story_id
# Returns: pid worker_dir result_file
get_worker_info() {
    local story_id="$1"
    grep "^${story_id}:" "$PARALLEL_WORKER_TRACKING_FILE" | head -1 | cut -d: -f2-
}

# Get worker PID
get_worker_pid() {
    local story_id="$1"
    grep "^${story_id}:" "$PARALLEL_WORKER_TRACKING_FILE" | head -1 | cut -d: -f2
}

# Get worker directory
get_worker_dir() {
    local story_id="$1"
    grep "^${story_id}:" "$PARALLEL_WORKER_TRACKING_FILE" | head -1 | cut -d: -f3
}

# Get worker result file
get_worker_result_file() {
    local story_id="$1"
    grep "^${story_id}:" "$PARALLEL_WORKER_TRACKING_FILE" | head -1 | cut -d: -f4
}

# Remove worker from active list
remove_from_active() {
    local story_id="$1"
    PARALLEL_ACTIVE_WORKERS=$(echo "$PARALLEL_ACTIVE_WORKERS" | sed "s/ ${story_id}//" | sed "s/${story_id} //")
}

# Get list of active worker story IDs
get_active_workers() {
    echo "$PARALLEL_ACTIVE_WORKERS" | tr ' ' '\n' | grep -v '^$'
}

# ============================================================================
# Worker Management Functions
# ============================================================================

# Launch a single worker for a story as a background process
# Usage: launch_worker "story_id" [model]
launch_worker() {
    local story_id="$1"
    local model="${2:-}"

    local worker_script="${PARALLEL_SCRIPT_DIR}/worker.sh"

    if [ ! -f "$worker_script" ]; then
        par_log_error "Worker script not found: $worker_script"
        return 1
    fi

    # Get model for story if not provided
    if [ -z "$model" ]; then
        local model_selector="${PARALLEL_SCRIPT_DIR}/model-selector.py"
        if [ -f "$model_selector" ]; then
            model=$(python3 "$model_selector" select "$story_id" "$PARALLEL_PRD_FILE" --strategy "$PARALLEL_MODEL_STRATEGY" --json 2>/dev/null | jq -r '.selected_model // "sonnet"') || model="sonnet"
        else
            model="sonnet"
        fi
    fi

    # Create unique working directory for this worker
    local timestamp
    timestamp=$(date +%Y%m%d_%H%M%S)
    local worker_dir=".claude-loop/workers/${story_id}_${timestamp}"
    mkdir -p "$worker_dir/logs"
    local result_file="$worker_dir/result.json"

    par_log_progress "Launching worker for $story_id (model: $model)"
    par_log_debug "  Worker dir: $worker_dir"

    # Launch worker in background
    # Worker will write JSON result to its directory
    (
        "$worker_script" "$story_id" \
            --prd "$PARALLEL_PRD_FILE" \
            --model "$model" \
            --work-dir "$worker_dir" \
            --json > "$result_file" 2> "$worker_dir/logs/worker_stderr.log"
        echo $? > "$worker_dir/exit_code"
    ) &

    local pid=$!

    # Track this worker
    add_worker_tracking "$story_id" "$pid" "$worker_dir" "$result_file"

    par_log_debug "  Worker PID: $pid"

    return 0
}

# Wait for a specific worker to complete
# Returns the worker's result JSON
wait_for_worker() {
    local story_id="$1"
    local pid
    pid=$(get_worker_pid "$story_id")

    if [ -z "$pid" ]; then
        par_log_error "No worker found for $story_id"
        return 1
    fi

    # Wait for the process
    local exit_code=0
    wait "$pid" 2>/dev/null || exit_code=$?

    # Read the exit code from file (more reliable than wait)
    local worker_dir
    worker_dir=$(get_worker_dir "$story_id")
    if [ -f "$worker_dir/exit_code" ]; then
        exit_code=$(cat "$worker_dir/exit_code")
    fi

    # Read and return result
    local result_file
    result_file=$(get_worker_result_file "$story_id")
    if [ -f "$result_file" ]; then
        cat "$result_file"
    else
        # Return error result
        cat << EOF
{
  "story_id": "$story_id",
  "success": false,
  "exit_code": $exit_code,
  "error": "Worker did not produce result file",
  "timestamp": "$(par_get_timestamp_iso)"
}
EOF
    fi

    return $exit_code
}

# Check if a worker is still running
worker_is_running() {
    local story_id="$1"
    local pid
    pid=$(get_worker_pid "$story_id")

    if [ -z "$pid" ]; then
        return 1
    fi

    kill -0 "$pid" 2>/dev/null
}

# Kill a specific worker
kill_worker() {
    local story_id="$1"
    local pid
    pid=$(get_worker_pid "$story_id")

    if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
        par_log_warn "Killing worker for $story_id (PID: $pid)"
        kill -TERM "$pid" 2>/dev/null || true
        sleep 1
        kill -KILL "$pid" 2>/dev/null || true
    fi
}

# Kill all running workers
kill_all_workers() {
    par_log_warn "Killing all workers..."
    for story_id in $(get_active_workers); do
        kill_worker "$story_id"
    done
}

# ============================================================================
# Progress Display Functions
# ============================================================================

# Display progress bar for parallel execution
display_parallel_progress() {
    local total="$1"
    local completed="$2"
    local running="$3"
    local pending="$4"
    local elapsed_ms="$5"

    local bar_width=30
    local filled=$((completed * bar_width / total))
    local active=$((running * bar_width / total))
    local empty=$((bar_width - filled - active))

    # Build progress bar
    local bar=""
    for ((i=0; i<filled; i++)); do bar+="█"; done
    for ((i=0; i<active; i++)); do bar+="▓"; done
    for ((i=0; i<empty; i++)); do bar+="░"; done

    local elapsed_fmt
    elapsed_fmt=$(par_format_duration "$elapsed_ms")

    # Print progress line (carriage return for updating)
    printf "\r${PAR_CYAN}[PARALLEL]${PAR_NC} [%s] %d/%d complete | %d running | %d pending | %s    " \
        "$bar" "$completed" "$total" "$running" "$pending" "$elapsed_fmt"
}

# Display worker status for all workers
display_worker_status() {
    echo ""
    echo -e "${PAR_CYAN}═══════════════════════════════════════════════════════════════${PAR_NC}"
    echo -e "${PAR_CYAN}                    PARALLEL EXECUTION STATUS${PAR_NC}"
    echo -e "${PAR_CYAN}═══════════════════════════════════════════════════════════════${PAR_NC}"
    echo ""

    if [ -z "$PARALLEL_WORKER_TRACKING_FILE" ] || [ ! -f "$PARALLEL_WORKER_TRACKING_FILE" ]; then
        echo "  No workers tracked"
        echo ""
        return
    fi

    while IFS=':' read -r story_id pid worker_dir result_file; do
        local status
        if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
            status="${PAR_YELLOW}RUNNING${PAR_NC}"
        else
            if [ -f "$result_file" ]; then
                local success
                success=$(jq -r '.success // false' "$result_file" 2>/dev/null || echo "false")
                if [ "$success" = "true" ]; then
                    status="${PAR_GREEN}SUCCESS${PAR_NC}"
                else
                    status="${PAR_RED}FAILED${PAR_NC}"
                fi
            else
                status="${PAR_RED}NO RESULT${PAR_NC}"
            fi
        fi
        echo -e "  $story_id: $status (PID: $pid)"
    done < "$PARALLEL_WORKER_TRACKING_FILE"
    echo ""
}

# ============================================================================
# Group Execution Functions
# ============================================================================

# Execute a group of stories in parallel
# Usage: execute_parallel_group "story1,story2,story3" [--max-workers N]
execute_parallel_group() {
    local stories_str="$1"
    shift

    # Parse additional arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            --max-workers)
                PARALLEL_MAX_WORKERS="$2"
                shift 2
                ;;
            --prd)
                PARALLEL_PRD_FILE="$2"
                shift 2
                ;;
            --model-strategy)
                PARALLEL_MODEL_STRATEGY="$2"
                shift 2
                ;;
            --verbose)
                PARALLEL_VERBOSE=true
                shift
                ;;
            *)
                par_log_error "Unknown option: $1"
                return 1
                ;;
        esac
    done

    # Convert comma-separated stories to array
    IFS=',' read -ra stories <<< "$stories_str"
    local total_stories=${#stories[@]}

    if [ "$total_stories" -eq 0 ]; then
        par_log_warn "No stories to execute"
        return 0
    fi

    # Initialize tracking
    PARALLEL_GROUP_ID=$(date +%Y%m%d_%H%M%S)
    PARALLEL_GROUP_START_TIME=$(par_get_timestamp_ms)
    PARALLEL_GROUP_RESULTS=()
    init_worker_tracking

    par_log_info "Executing group $PARALLEL_GROUP_ID with $total_stories stories (max workers: $PARALLEL_MAX_WORKERS)"
    echo ""

    # Track execution state
    local completed=0
    local running=0
    local pending=$total_stories
    local next_story_idx=0

    # Set up signal handler for cleanup
    trap 'kill_all_workers; exit 1' SIGINT SIGTERM

    # Main execution loop
    while [ $completed -lt $total_stories ]; do
        # Launch new workers up to max
        while [ $running -lt $PARALLEL_MAX_WORKERS ] && [ $next_story_idx -lt $total_stories ]; do
            local story_id="${stories[$next_story_idx]}"
            if launch_worker "$story_id"; then
                ((running++))
                ((pending--))
            fi
            ((next_story_idx++))
        done

        # Display progress
        local elapsed=$(($(par_get_timestamp_ms) - PARALLEL_GROUP_START_TIME))
        display_parallel_progress "$total_stories" "$completed" "$running" "$pending" "$elapsed"

        # Check for completed workers
        local workers_to_remove=""
        for story_id in $(get_active_workers); do
            if ! worker_is_running "$story_id"; then
                workers_to_remove="$workers_to_remove $story_id"
            fi
        done

        # Process completed workers
        for story_id in $workers_to_remove; do
            [ -z "$story_id" ] && continue

            # Collect result
            local result
            result=$(wait_for_worker "$story_id")
            PARALLEL_GROUP_RESULTS+=("$result")

            # Check success
            local success
            success=$(echo "$result" | jq -r '.success // false')

            # Update display
            echo ""  # New line after progress bar
            if [ "$success" = "true" ]; then
                par_log_success "Worker completed: $story_id"
            else
                local error
                error=$(echo "$result" | jq -r '.error // "Unknown error"')
                par_log_error "Worker failed: $story_id - $error"
            fi

            # Remove from active tracking
            remove_from_active "$story_id"

            ((completed++))
            ((running--))
        done

        # Small sleep to avoid busy waiting
        if [ $running -gt 0 ]; then
            sleep 1
        fi
    done

    # Clear progress line
    echo ""

    # Calculate final timing
    local end_time
    end_time=$(par_get_timestamp_ms)
    local total_duration=$((end_time - PARALLEL_GROUP_START_TIME))

    # Display summary
    display_group_summary "$total_stories" "$total_duration"

    # Reset signal handler
    trap - SIGINT SIGTERM

    return 0
}

# Display summary of group execution
display_group_summary() {
    local total="$1"
    local duration_ms="$2"

    local successful=0
    local failed=0
    local total_tokens_in=0
    local total_tokens_out=0

    # Aggregate results
    for result in "${PARALLEL_GROUP_RESULTS[@]}"; do
        local success
        success=$(echo "$result" | jq -r '.success // false')
        if [ "$success" = "true" ]; then
            ((successful++))
        else
            ((failed++))
        fi

        local tokens_in tokens_out
        tokens_in=$(echo "$result" | jq -r '.tokens_in // 0')
        tokens_out=$(echo "$result" | jq -r '.tokens_out // 0')
        total_tokens_in=$((total_tokens_in + tokens_in))
        total_tokens_out=$((total_tokens_out + tokens_out))
    done

    echo ""
    echo -e "${PAR_CYAN}═══════════════════════════════════════════════════════════════${PAR_NC}"
    echo -e "${PAR_CYAN}                    PARALLEL GROUP SUMMARY${PAR_NC}"
    echo -e "${PAR_CYAN}═══════════════════════════════════════════════════════════════${PAR_NC}"
    echo ""
    echo -e "  ${PAR_BLUE}Group ID:${PAR_NC}      $PARALLEL_GROUP_ID"
    echo -e "  ${PAR_BLUE}Stories:${PAR_NC}       $total total"
    echo -e "    ${PAR_GREEN}Successful:${PAR_NC}  $successful"
    if [ $failed -gt 0 ]; then
        echo -e "    ${PAR_RED}Failed:${PAR_NC}      $failed"
    fi
    echo ""
    echo -e "  ${PAR_BLUE}Duration:${PAR_NC}      $(par_format_duration $duration_ms)"
    echo -e "  ${PAR_BLUE}Avg per story:${PAR_NC} $(par_format_duration $((duration_ms / total)))"
    echo ""
    echo -e "  ${PAR_BLUE}Tokens:${PAR_NC}"
    echo -e "    Input:       $total_tokens_in"
    echo -e "    Output:      $total_tokens_out"
    echo ""
    echo -e "${PAR_CYAN}═══════════════════════════════════════════════════════════════${PAR_NC}"
    echo ""
}

# Get aggregated results from last group execution as JSON
get_group_results_json() {
    local results="["
    local first=true

    for result in "${PARALLEL_GROUP_RESULTS[@]}"; do
        if [ "$first" = true ]; then
            first=false
        else
            results+=","
        fi
        results+="$result"
    done

    results+="]"
    echo "$results"
}

# Check if all workers in last group succeeded
all_workers_succeeded() {
    for result in "${PARALLEL_GROUP_RESULTS[@]}"; do
        local success
        success=$(echo "$result" | jq -r '.success // false')
        if [ "$success" != "true" ]; then
            return 1
        fi
    done
    return 0
}

# Get list of failed story IDs from last group
get_failed_stories() {
    local failed=()
    for result in "${PARALLEL_GROUP_RESULTS[@]}"; do
        local success
        success=$(echo "$result" | jq -r '.success // false')
        if [ "$success" != "true" ]; then
            local story_id
            story_id=$(echo "$result" | jq -r '.story_id')
            failed+=("$story_id")
        fi
    done
    echo "${failed[*]}"
}

# ============================================================================
# Integration Functions (for claude-loop.sh)
# ============================================================================

# Execute all parallel batches from execution plan
# Usage: execute_all_parallel_batches [options]
execute_all_parallel_batches() {
    local prd_file="${1:-$PARALLEL_PRD_FILE}"
    shift || true

    local dep_graph="${PARALLEL_SCRIPT_DIR}/dependency-graph.py"

    if [ ! -f "$dep_graph" ]; then
        par_log_error "Dependency graph not found: $dep_graph"
        return 1
    fi

    # Get batches from dependency graph
    local batches_json
    batches_json=$(python3 "$dep_graph" batches "$prd_file" --incomplete-only 2>/dev/null)

    if [ -z "$batches_json" ] || [ "$batches_json" = "[]" ]; then
        par_log_info "No incomplete stories to execute"
        return 0
    fi

    # Parse batches
    local num_batches
    num_batches=$(echo "$batches_json" | jq 'length')

    par_log_info "Executing $num_batches sequential batches"
    echo ""

    local batch_num=1
    for batch in $(echo "$batches_json" | jq -c '.[]'); do
        local stories
        stories=$(echo "$batch" | jq -r 'join(",")')
        local batch_size
        batch_size=$(echo "$batch" | jq 'length')

        echo ""
        echo -e "${PAR_MAGENTA}═══════════════════════════════════════════════════════════════${PAR_NC}"
        echo -e "${PAR_MAGENTA}                      BATCH $batch_num of $num_batches${PAR_NC}"
        echo -e "${PAR_MAGENTA}       Stories: $stories${PAR_NC}"
        echo -e "${PAR_MAGENTA}═══════════════════════════════════════════════════════════════${PAR_NC}"
        echo ""

        # Execute this batch in parallel
        if ! execute_parallel_group "$stories" --prd "$prd_file" "$@"; then
            par_log_error "Batch $batch_num failed"
            return 1
        fi

        # Check if all workers succeeded
        if ! all_workers_succeeded; then
            local failed
            failed=$(get_failed_stories)
            par_log_error "Some stories failed in batch $batch_num: $failed"
            par_log_warn "Stopping execution due to failures"
            return 1
        fi

        ((batch_num++))
    done

    par_log_success "All batches completed successfully!"
    return 0
}

# ============================================================================
# CLI Mode
# ============================================================================

show_parallel_help() {
    cat << EOF
parallel.sh - Parallel Group Executor for Claude-Loop

USAGE:
    source lib/parallel.sh
    execute_parallel_group "story1,story2,story3" [OPTIONS]

    # Or run directly:
    ./lib/parallel.sh execute "US-001,US-002,US-003" [OPTIONS]
    ./lib/parallel.sh all [OPTIONS]

COMMANDS:
    execute STORIES    Execute specified stories in parallel
    all                Execute all batches from execution plan

OPTIONS:
    --max-workers N       Maximum parallel workers (default: 3)
    --prd FILE           Path to prd.json (default: ./prd.json)
    --model-strategy STR  Model selection strategy (default: auto)
    --verbose            Enable verbose output
    -h, --help           Show this help message

DESCRIPTION:
    Executes multiple stories in parallel using isolated worker processes.
    Each worker runs independently and results are collected after completion.

    The execute command takes a comma-separated list of story IDs and runs
    them in parallel (up to --max-workers at a time).

    The all command gets the execution plan from dependency-graph.py and
    executes each batch in sequence, with stories within each batch running
    in parallel.

EXAMPLES:
    # Execute three stories in parallel
    ./lib/parallel.sh execute "US-001,US-002,US-003"

    # Execute with max 5 parallel workers
    ./lib/parallel.sh execute "US-001,US-002,US-003" --max-workers 5

    # Execute all remaining batches
    ./lib/parallel.sh all --max-workers 4 --verbose

    # Source and use in script
    source lib/parallel.sh
    execute_parallel_group "US-001,US-002" --max-workers 2

EOF
}

# Main entry point for CLI usage
parallel_main() {
    if [ $# -eq 0 ] || [ "$1" = "-h" ] || [ "$1" = "--help" ]; then
        show_parallel_help
        exit 0
    fi

    local command="$1"
    shift

    case "$command" in
        execute)
            if [ $# -eq 0 ]; then
                par_log_error "Stories required for execute command"
                echo "Usage: ./lib/parallel.sh execute 'US-001,US-002' [options]"
                exit 1
            fi
            local stories="$1"
            shift
            execute_parallel_group "$stories" "$@"
            ;;
        all)
            execute_all_parallel_batches "./prd.json" "$@"
            ;;
        *)
            par_log_error "Unknown command: $command"
            show_parallel_help
            exit 1
            ;;
    esac
}

# Run main if executed directly (not sourced)
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    parallel_main "$@"
fi
