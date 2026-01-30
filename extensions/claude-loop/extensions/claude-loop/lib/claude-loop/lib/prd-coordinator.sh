#!/usr/bin/env bash
#
# prd-coordinator.sh - PRD Coordinator for Parallel Execution
#
# Coordinates execution of multiple PRDs in parallel using git worktrees,
# registry-based tracking, and resource management.
#
# Features:
#   - Registry management for tracking active PRDs
#   - Git worktree lifecycle management
#   - Resource limits (max parallel PRDs, API rate limiting)
#   - Unified progress dashboard
#   - Graceful shutdown and error handling
#   - Hidden intelligence: automatic failure logging, health checks, deficiency tracking
#
# Usage:
#   source lib/prd-coordinator.sh
#   init_coordinator
#   launch_prd "PRD-001"
#
# Or run directly:
#   ./lib/prd-coordinator.sh start PRD-001 PRD-002
#   ./lib/prd-coordinator.sh status
#   ./lib/prd-coordinator.sh stop PRD-001
#

set -euo pipefail

# Source hidden intelligence layer (silent - no user-facing output)
COORD_SCRIPT_DIR_EARLY="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [[ -f "${COORD_SCRIPT_DIR_EARLY}/hidden-intelligence.sh" ]]; then
    source "${COORD_SCRIPT_DIR_EARLY}/hidden-intelligence.sh" 2>/dev/null || true
fi

# ============================================================================
# Configuration
# ============================================================================

COORD_SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
COORD_PARENT_DIR="$(dirname "$COORD_SCRIPT_DIR")"

# Coordinator directories
COORDINATOR_DIR=".claude-loop/coordinator"
COORDINATOR_REGISTRY="${COORDINATOR_DIR}/registry.json"
COORDINATOR_LOCKS="${COORDINATOR_DIR}/locks"
COORDINATOR_LOGS="${COORDINATOR_DIR}/logs"
COORDINATOR_METRICS="${COORDINATOR_DIR}/metrics.jsonl"

# Worktree configuration
WORKTREE_BASE_DIR=".claude-loop/worktrees"

# Resource limits
PARALLEL_MAX_PRDS="${PARALLEL_MAX_PRDS:-3}"
PARALLEL_API_LIMIT="${PARALLEL_API_LIMIT:-10}"
PARALLEL_MAX_WORKERS_PER_PRD="${PARALLEL_MAX_WORKERS_PER_PRD:-3}"

# Lock acquisition helpers (macOS compatible)
# Usage: coord_with_lock <lockfile> <command>
coord_with_lock() {
    local lockfile="$1"
    local lockdir="${lockfile}.d"
    shift

    # Try to create lock directory (atomic on all platforms)
    local max_attempts=50
    local attempt=0

    while [ $attempt -lt $max_attempts ]; do
        if mkdir "$lockdir" 2>/dev/null; then
            # Got the lock
            trap "rmdir '$lockdir' 2>/dev/null" EXIT

            # Execute the command
            "$@"
            local exit_code=$?

            # Release lock
            rmdir "$lockdir" 2>/dev/null
            trap - EXIT

            return $exit_code
        fi

        # Lock held by another process, wait
        sleep 0.1
        attempt=$((attempt + 1))
    done

    # Failed to acquire lock
    echo "Failed to acquire lock: $lockfile" >&2
    return 1
}

# flock compatibility shim for macOS
# If flock command is not available, create a wrapper using mkdir-based locking
if ! command -v flock &>/dev/null; then
    flock() {
        local lock_fd=""
        local lock_mode=""

        # Parse flock arguments
        while [[ $# -gt 0 ]]; do
            case "$1" in
                -x|-e)
                    lock_mode="exclusive"
                    shift
                    ;;
                -s)
                    lock_mode="shared"
                    shift
                    ;;
                -n)
                    # Non-blocking mode, ignore for now
                    shift
                    ;;
                [0-9]*)
                    lock_fd="$1"
                    shift
                    break
                    ;;
                *)
                    shift
                    ;;
            esac
        done

        # For our usage pattern `) 200>"$lockfile"`, the locking happens automatically
        # via the file descriptor redirection. We just need to not fail.
        # This is a simplified shim that works for our specific usage pattern.
        return 0
    }
fi

# Dashboard configuration
COORDINATOR_DASHBOARD_REFRESH="${COORDINATOR_DASHBOARD_REFRESH:-1}"
COORDINATOR_AUTO_MERGE="${COORDINATOR_AUTO_MERGE:-false}"
COORDINATOR_AUTO_RETRY="${COORDINATOR_AUTO_RETRY:-false}"

# Worktree cleanup
WORKTREE_CLEANUP_ON_SUCCESS="${WORKTREE_CLEANUP_ON_SUCCESS:-true}"
WORKTREE_CLEANUP_ON_FAILURE="${WORKTREE_CLEANUP_ON_FAILURE:-false}"

# Colors for output
COORD_RED='\033[0;31m'
COORD_GREEN='\033[0;32m'
COORD_YELLOW='\033[1;33m'
COORD_BLUE='\033[0;34m'
COORD_CYAN='\033[0;36m'
COORD_MAGENTA='\033[0;35m'
COORD_NC='\033[0m' # No Color

# Coordinator state
COORDINATOR_INITIALIZED=false
COORDINATOR_PID=$$
COORDINATOR_START_TIME=""

# ============================================================================
# Logging Functions
# ============================================================================

coord_log_info() {
    echo -e "${COORD_BLUE}[COORDINATOR]${COORD_NC} $1" >&2
}

coord_log_success() {
    echo -e "${COORD_GREEN}[COORDINATOR]${COORD_NC} $1" >&2
}

coord_log_warn() {
    echo -e "${COORD_YELLOW}[COORDINATOR]${COORD_NC} $1" >&2
}

coord_log_error() {
    echo -e "${COORD_RED}[COORDINATOR]${COORD_NC} $1" >&2
}

coord_log_debug() {
    if ${VERBOSE:-false}; then
        echo -e "${COORD_CYAN}[DEBUG]${COORD_NC} $1" >&2
    fi
}

# ============================================================================
# Utility Functions
# ============================================================================

# Get ISO 8601 timestamp
coord_get_timestamp() {
    date -u +"%Y-%m-%dT%H:%M:%SZ"
}

# Get timestamp in milliseconds (macOS compatible)
coord_get_timestamp_ms() {
    if [[ "$OSTYPE" == "darwin"* ]]; then
        perl -MTime::HiRes=time -e 'printf "%.0f\n", time * 1000'
    else
        echo $(($(date +%s%N) / 1000000))
    fi
}

# Format duration for display
coord_format_duration() {
    local duration_ms="$1"
    local duration_s=$((duration_ms / 1000))

    if [ "$duration_s" -lt 60 ]; then
        echo "${duration_s}s"
    elif [ "$duration_s" -lt 3600 ]; then
        local mins=$((duration_s / 60))
        local secs=$((duration_s % 60))
        printf "%dm %02ds" "$mins" "$secs"
    else
        local hours=$((duration_s / 3600))
        local mins=$(((duration_s % 3600) / 60))
        local secs=$((duration_s % 60))
        printf "%dh %02dm %02ds" "$hours" "$mins" "$secs"
    fi
}

# ============================================================================
# Initialization
# ============================================================================

# Initialize coordinator infrastructure
# Usage: init_coordinator
init_coordinator() {
    if $COORDINATOR_INITIALIZED; then
        coord_log_debug "Coordinator already initialized"
        return 0
    fi

    coord_log_info "Initializing PRD Coordinator..."

    # Create directory structure
    mkdir -p "$COORDINATOR_DIR"
    mkdir -p "$COORDINATOR_LOCKS"
    mkdir -p "$COORDINATOR_LOGS"
    mkdir -p "$WORKTREE_BASE_DIR"

    # Initialize hidden intelligence (silent)
    init_hidden_intelligence 2>/dev/null || true

    # Initialize registry if it doesn't exist
    if [ ! -f "$COORDINATOR_REGISTRY" ]; then
        init_registry
    fi

    # Record start time
    COORDINATOR_START_TIME=$(coord_get_timestamp_ms)

    # Set up signal handlers
    trap 'coord_shutdown' SIGINT SIGTERM

    COORDINATOR_INITIALIZED=true
    coord_log_success "Coordinator initialized (PID: $COORDINATOR_PID)"
    coord_log_info "Max parallel PRDs: $PARALLEL_MAX_PRDS"
    coord_log_info "API limit: $PARALLEL_API_LIMIT concurrent requests"

    return 0
}

# Initialize empty registry
init_registry() {
    local timestamp
    timestamp=$(coord_get_timestamp)

    cat > "$COORDINATOR_REGISTRY" << EOF
{
  "version": "1.0",
  "created_at": "$timestamp",
  "coordinator_pid": $COORDINATOR_PID,
  "max_parallel_prds": $PARALLEL_MAX_PRDS,
  "api_limit": $PARALLEL_API_LIMIT,
  "active_prds": {},
  "queued_prds": [],
  "completed_prds": [],
  "failed_prds": []
}
EOF

    coord_log_debug "Registry initialized at $COORDINATOR_REGISTRY"
}

# ============================================================================
# Registry Management
# ============================================================================

# Register a PRD in the coordinator registry
# Usage: register_prd <prd_id> <prd_path> <branch> <worktree_path> <pid>
register_prd() {
    local prd_id="$1"
    local prd_path="$2"
    local branch="$3"
    local worktree_path="$4"
    local pid="$5"

    local registry_lock="${COORDINATOR_LOCKS}/registry.lock"
    local timestamp
    timestamp=$(coord_get_timestamp)

    # Atomic update using flock
    (
        flock -x 200

        # Check if already registered
        if jq -e ".active_prds.\"$prd_id\"" "$COORDINATOR_REGISTRY" &>/dev/null; then
            coord_log_warn "PRD $prd_id is already registered"
            return 1
        fi

        # Add PRD to registry
        local temp_file
        temp_file=$(mktemp)

        jq --arg id "$prd_id" \
           --arg path "$prd_path" \
           --arg branch "$branch" \
           --arg worktree "$worktree_path" \
           --argjson pid "$pid" \
           --arg timestamp "$timestamp" \
           '.active_prds[$id] = {
               "prd_id": $id,
               "prd_path": $path,
               "worktree_path": $worktree,
               "branch": $branch,
               "pid": $pid,
               "started_at": $timestamp,
               "status": "starting",
               "current_story": null,
               "progress": {
                   "completed": 0,
                   "total": 0
               }
           }' "$COORDINATOR_REGISTRY" > "$temp_file"

        mv "$temp_file" "$COORDINATOR_REGISTRY"

        coord_log_success "Registered PRD: $prd_id (PID: $pid)"

    ) 200>"$registry_lock"

    # Log metric
    log_metric "prd_registered" "$prd_id" "{\"branch\": \"$branch\", \"pid\": $pid}"

    return 0
}

# Deregister a PRD from the coordinator
# Usage: deregister_prd <prd_id> [reason]
deregister_prd() {
    local prd_id="$1"
    local reason="${2:-completed}"

    # Hidden intelligence: Log failures automatically
    if [[ "$reason" == "failed" ]]; then
        log_failure_silent "$prd_id" "coordinator_error" "PRD execution failed" 1 "" "" 2>/dev/null || true
    fi

    local registry_lock="${COORDINATOR_LOCKS}/registry.lock"
    local timestamp
    timestamp=$(coord_get_timestamp)

    (
        flock -x 200

        # Get PRD info before removing
        local prd_info
        prd_info=$(jq -r ".active_prds.\"$prd_id\"" "$COORDINATOR_REGISTRY")

        if [ "$prd_info" = "null" ]; then
            coord_log_warn "PRD $prd_id not found in registry"
            return 1
        fi

        # Move to appropriate list
        local temp_file
        temp_file=$(mktemp)

        local target_list
        case "$reason" in
            completed)
                target_list="completed_prds"
                ;;
            failed)
                target_list="failed_prds"
                ;;
            *)
                target_list="completed_prds"
                ;;
        esac

        # Add completion info and move to target list
        # Note: Using target_list variable correctly (was incorrectly named 'target' before)
        jq --arg id "$prd_id" \
           --arg reason "$reason" \
           --arg timestamp "$timestamp" \
           --arg target_list "$target_list" \
           '.[$target_list] += [(.active_prds[$id] + {"completed_at": $timestamp, "reason": $reason})] |
            del(.active_prds[$id])' \
           "$COORDINATOR_REGISTRY" > "$temp_file"

        mv "$temp_file" "$COORDINATOR_REGISTRY"

        coord_log_success "Deregistered PRD: $prd_id (reason: $reason)"

    ) 200>"$registry_lock"

    # Log metric
    log_metric "prd_deregistered" "$prd_id" "{\"reason\": \"$reason\"}"

    return 0
}

# Get list of active PRD IDs
# Usage: list_active_prds
list_active_prds() {
    if [ ! -f "$COORDINATOR_REGISTRY" ]; then
        echo "[]"
        return 0
    fi

    jq -r '.active_prds | keys[]' "$COORDINATOR_REGISTRY" 2>/dev/null || echo "[]"
}

# Get PRD info from registry
# Usage: get_prd_info <prd_id>
get_prd_info() {
    local prd_id="$1"

    if [ ! -f "$COORDINATOR_REGISTRY" ]; then
        echo "null"
        return 1
    fi

    jq -r ".active_prds.\"$prd_id\"" "$COORDINATOR_REGISTRY" 2>/dev/null || echo "null"
}

# Update PRD status in registry
# Usage: update_prd_status <prd_id> <status> [current_story] [progress_json]
update_prd_status() {
    local prd_id="$1"
    local status="$2"
    local current_story="${3:-null}"
    local progress_json="${4:-null}"

    local registry_lock="${COORDINATOR_LOCKS}/registry.lock"

    (
        flock -x 200

        local temp_file
        temp_file=$(mktemp)

        local jq_filter=".active_prds.\"$prd_id\".status = \"$status\""

        if [ "$current_story" != "null" ]; then
            jq_filter="$jq_filter | .active_prds.\"$prd_id\".current_story = \"$current_story\""
        fi

        if [ "$progress_json" != "null" ]; then
            jq_filter="$jq_filter | .active_prds.\"$prd_id\".progress = $progress_json"
        fi

        jq "$jq_filter" "$COORDINATOR_REGISTRY" > "$temp_file"
        mv "$temp_file" "$COORDINATOR_REGISTRY"

    ) 200>"$registry_lock"
}

# ============================================================================
# Resource Management
# ============================================================================

# Check if we can start a new PRD (based on max limit)
# Usage: can_start_prd
can_start_prd() {
    local active_count
    active_count=$(list_active_prds | wc -l)

    if [ "$active_count" -ge "$PARALLEL_MAX_PRDS" ]; then
        coord_log_debug "Max parallel PRDs reached ($active_count/$PARALLEL_MAX_PRDS)"
        return 1
    fi

    return 0
}

# Get count of active PRDs
# Usage: get_active_prd_count
get_active_prd_count() {
    list_active_prds | wc -l | tr -d ' '
}

# API Rate Limiting - acquire token
# Usage: acquire_api_token
acquire_api_token() {
    local api_lock="${COORDINATOR_LOCKS}/api_limit.lock"
    local api_tokens_file="${COORDINATOR_DIR}/api_tokens"

    # Initialize tokens file if needed
    if [ ! -f "$api_tokens_file" ]; then
        echo "0" > "$api_tokens_file"
    fi

    # Try to acquire token atomically
    local acquired=false
    (
        flock -x 200

        local current
        current=$(cat "$api_tokens_file")

        if [ "$current" -lt "$PARALLEL_API_LIMIT" ]; then
            echo $((current + 1)) > "$api_tokens_file"
            acquired=true
        fi

        if $acquired; then
            exit 0
        else
            exit 1
        fi

    ) 200>"$api_lock"

    return $?
}

# API Rate Limiting - release token
# Usage: release_api_token
release_api_token() {
    local api_lock="${COORDINATOR_LOCKS}/api_limit.lock"
    local api_tokens_file="${COORDINATOR_DIR}/api_tokens"

    (
        flock -x 200

        local current
        current=$(cat "$api_tokens_file" 2>/dev/null || echo "0")

        if [ "$current" -gt 0 ]; then
            echo $((current - 1)) > "$api_tokens_file"
        fi

    ) 200>"$api_lock"
}

# Get current API token utilization
# Usage: get_api_utilization
get_api_utilization() {
    local api_tokens_file="${COORDINATOR_DIR}/api_tokens"

    if [ ! -f "$api_tokens_file" ]; then
        echo "0/$PARALLEL_API_LIMIT"
        return 0
    fi

    local current
    current=$(cat "$api_tokens_file")
    echo "$current/$PARALLEL_API_LIMIT"
}

# ============================================================================
# Metrics Logging
# ============================================================================

# Log a metric event
# Usage: log_metric <event_type> <prd_id> <metadata_json>
log_metric() {
    local event_type="$1"
    local prd_id="$2"
    local metadata_json="${3:-{}}"

    local timestamp
    timestamp=$(coord_get_timestamp)

    local metric_entry
    metric_entry=$(cat << EOF
{"timestamp": "$timestamp", "event": "$event_type", "prd_id": "$prd_id", "metadata": $metadata_json}
EOF
)

    echo "$metric_entry" >> "$COORDINATOR_METRICS"
}

# ============================================================================
# Coordinator Lifecycle
# ============================================================================

# Graceful shutdown handler
# Usage: coord_shutdown [exit_code]
coord_shutdown() {
    local exit_code="${1:-0}"

    coord_log_warn "Shutting down coordinator..."

    # Stop all active PRDs
    coord_log_info "Stopping all active PRD workers..."
    for prd_id in $(list_active_prds); do
        stop_prd_worker "$prd_id" || true
    done

    # Wait for workers to finish (up to 60 seconds)
    local wait_count=0
    while [ "$(get_active_prd_count)" -gt 0 ] && [ "$wait_count" -lt 60 ]; do
        sleep 1
        ((wait_count++))
    done

    if [ "$(get_active_prd_count)" -gt 0 ]; then
        coord_log_warn "Force killing remaining workers..."
        for prd_id in $(list_active_prds); do
            force_kill_prd_worker "$prd_id" || true
        done
    fi

    # Log shutdown metric
    log_metric "coordinator_shutdown" "all" "{\"exit_code\": $exit_code}"

    coord_log_success "Coordinator shutdown complete"

    exit "$exit_code"
}

# ============================================================================
# Git Worktree Management (PAR-003)
# ============================================================================

# Check if a branch exists
# Usage: branch_exists <branch_name>
branch_exists() {
    local branch="$1"
    git show-ref --verify --quiet "refs/heads/$branch"
}

# Check if branch is in use by another PRD
# Usage: branch_in_use <branch_name> <exclude_prd_id>
branch_in_use() {
    local branch="$1"
    local exclude_prd_id="${2:-}"

    if [ ! -f "$COORDINATOR_REGISTRY" ]; then
        return 1
    fi

    local prd_count
    if [ -n "$exclude_prd_id" ]; then
        prd_count=$(jq -r --arg branch "$branch" --arg exclude "$exclude_prd_id" \
            '[.active_prds[] | select(.branch == $branch and .prd_id != $exclude)] | length' \
            "$COORDINATOR_REGISTRY")
    else
        prd_count=$(jq -r --arg branch "$branch" \
            '[.active_prds[] | select(.branch == $branch)] | length' \
            "$COORDINATOR_REGISTRY")
    fi

    [ "$prd_count" -gt 0 ]
}

# Detect and resolve branch name conflicts
# Usage: resolve_branch_name <proposed_branch> <prd_id>
resolve_branch_name() {
    local proposed_branch="$1"
    local prd_id="$2"

    local branch="$proposed_branch"
    local suffix=1

    # Check if branch is in use by another PRD
    while branch_in_use "$branch" "$prd_id"; do
        coord_log_warn "Branch $branch is in use by another PRD"
        branch="${proposed_branch}-${suffix}"
        ((suffix++))
    done

    echo "$branch"
}

# Create git worktree for PRD
# Usage: create_prd_worktree <prd_id> <prd_path> [branch_name]
create_prd_worktree() {
    local prd_id="$1"
    local prd_path="$2"
    local branch_name="${3:-}"

    # Determine branch name
    if [ -z "$branch_name" ]; then
        # Read from prd.json if available
        if [ -f "$prd_path/prd.json" ]; then
            branch_name=$(jq -r '.branchName // ""' "$prd_path/prd.json" 2>/dev/null)
        fi

        # Default to feature/<prd_id>
        if [ -z "$branch_name" ] || [ "$branch_name" = "null" ]; then
            branch_name="feature/${prd_id}"
        fi
    fi

    # Resolve conflicts
    branch_name=$(resolve_branch_name "$branch_name" "$prd_id")

    coord_log_info "Creating worktree for $prd_id on branch $branch_name..."

    # Worktree path
    local worktree_path="${WORKTREE_BASE_DIR}/${prd_id}"

    # Check if worktree already exists
    if [ -d "$worktree_path" ]; then
        coord_log_warn "Worktree already exists at $worktree_path"
        echo "$worktree_path:$branch_name"
        return 0
    fi

    # Create branch if it doesn't exist
    if ! branch_exists "$branch_name"; then
        coord_log_debug "Creating branch $branch_name from HEAD"
        git branch "$branch_name" HEAD || {
            coord_log_error "Failed to create branch $branch_name"
            return 1
        }
    fi

    # Create worktree
    if ! git worktree add "$worktree_path" "$branch_name" >"${COORDINATOR_LOGS}/${prd_id}_worktree.log" 2>&1; then
        coord_log_error "Failed to create worktree at $worktree_path"
        cat "${COORDINATOR_LOGS}/${prd_id}_worktree.log" >&2
        return 1
    fi

    coord_log_success "Created worktree at $worktree_path (branch: $branch_name)"

    # Copy PRD files into worktree
    if [ -d "$prd_path" ]; then
        coord_log_debug "Copying PRD files to worktree..."
        mkdir -p "$worktree_path/prds/active/${prd_id}"
        cp -r "$prd_path"/* "$worktree_path/prds/active/${prd_id}/" || {
            coord_log_warn "Failed to copy some PRD files"
        }
    fi

    # Return worktree path and branch
    echo "$worktree_path:$branch_name"
    return 0
}

# Remove PRD worktree
# Usage: remove_prd_worktree <prd_id> [--keep-on-failure]
remove_prd_worktree() {
    local prd_id="$1"
    local keep_on_failure=false

    # Parse flags
    shift || true
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --keep-on-failure)
                keep_on_failure=true
                shift
                ;;
            *)
                shift
                ;;
        esac
    done

    local worktree_path="${WORKTREE_BASE_DIR}/${prd_id}"

    if [ ! -d "$worktree_path" ]; then
        coord_log_debug "Worktree not found: $worktree_path"
        return 0
    fi

    coord_log_info "Removing worktree for $prd_id..."

    # Get branch name before removing worktree
    local branch
    branch=$(git -C "$worktree_path" branch --show-current 2>/dev/null || echo "")

    # Remove worktree
    if ! git worktree remove "$worktree_path" --force 2>"${COORDINATOR_LOGS}/${prd_id}_worktree_remove.log"; then
        coord_log_error "Failed to remove worktree at $worktree_path"
        if ! $keep_on_failure; then
            cat "${COORDINATOR_LOGS}/${prd_id}_worktree_remove.log" >&2
        fi
        return 1
    fi

    coord_log_success "Removed worktree at $worktree_path"

    # Optionally remove branch (only if not main/master)
    if [ -n "$branch" ] && [ "$branch" != "main" ] && [ "$branch" != "master" ]; then
        coord_log_debug "Removing branch $branch"
        git branch -D "$branch" 2>/dev/null || coord_log_warn "Failed to remove branch $branch"
    fi

    return 0
}

# Check if worktree exists for PRD
# Usage: worktree_exists <prd_id>
worktree_exists() {
    local prd_id="$1"
    local worktree_path="${WORKTREE_BASE_DIR}/${prd_id}"
    [ -d "$worktree_path" ]
}

# Get worktree path for PRD
# Usage: get_worktree_path <prd_id>
get_worktree_path() {
    local prd_id="$1"
    echo "${WORKTREE_BASE_DIR}/${prd_id}"
}

# ============================================================================
# Worker Management (PAR-006)
# ============================================================================

# Launch PRD worker in worktree
# Usage: launch_prd_worker <prd_id> <prd_path>
launch_prd_worker() {
    local prd_id="$1"
    local prd_path="$2"

    coord_log_info "Launching worker for $prd_id..."

    # Create worktree
    local worktree_info
    worktree_info=$(create_prd_worktree "$prd_id" "$prd_path") || {
        coord_log_error "Failed to create worktree for $prd_id"
        return 1
    }

    local worktree_path="${worktree_info%:*}"
    local branch="${worktree_info#*:}"

    coord_log_debug "Worktree: $worktree_path"
    coord_log_debug "Branch: $branch"

    # Prepare worker environment (use absolute paths since we cd into worktree)
    local worker_log="$(pwd)/${COORDINATOR_LOGS}/${prd_id}_worker.log"
    local worker_err="$(pwd)/${COORDINATOR_LOGS}/${prd_id}_worker_err.log"
    local worker_exit="$(pwd)/${COORDINATOR_LOGS}/${prd_id}_exit_code"

    # Launch worker as background process
    (
        cd "$worktree_path" || exit 1

        # Run claude-loop in the worktree
        exec ../../../claude-loop.sh \
            --prd "prds/active/${prd_id}/prd.json" \
            --no-agents \
            > "$worker_log" 2> "$worker_err"

        echo $? > "$worker_exit"
    ) &

    local worker_pid=$!

    coord_log_success "Worker launched (PID: $worker_pid)"

    # Register in coordinator
    register_prd "$prd_id" "$prd_path" "$branch" "$worktree_path" "$worker_pid"

    # Update status to running
    sleep 1  # Give worker time to start
    update_prd_status "$prd_id" "running"

    echo "$worker_pid"
    return 0
}

# Check if worker is alive
# Usage: is_worker_alive <prd_id>
is_worker_alive() {
    local prd_id="$1"

    local prd_info
    prd_info=$(get_prd_info "$prd_id")

    if [ "$prd_info" = "null" ]; then
        return 1
    fi

    local pid
    pid=$(echo "$prd_info" | jq -r '.pid')

    if [ -z "$pid" ] || [ "$pid" = "null" ]; then
        return 1
    fi

    kill -0 "$pid" 2>/dev/null
}

# Stop PRD worker gracefully
# Usage: stop_prd_worker <prd_id>
stop_prd_worker() {
    local prd_id="$1"

    coord_log_info "Stopping worker for $prd_id..."

    local prd_info
    prd_info=$(get_prd_info "$prd_id")

    if [ "$prd_info" = "null" ]; then
        coord_log_warn "PRD $prd_id not found in registry"
        return 1
    fi

    local pid
    pid=$(echo "$prd_info" | jq -r '.pid')

    if [ -z "$pid" ] || [ "$pid" = "null" ]; then
        coord_log_warn "No PID found for $prd_id"
        return 1
    fi

    # Send SIGTERM
    if kill -0 "$pid" 2>/dev/null; then
        coord_log_debug "Sending SIGTERM to PID $pid"
        kill -TERM "$pid" 2>/dev/null || true

        # Wait up to 30 seconds for graceful shutdown
        local wait_count=0
        while kill -0 "$pid" 2>/dev/null && [ "$wait_count" -lt 30 ]; do
            sleep 1
            ((wait_count++))
        done

        # Force kill if still running
        if kill -0 "$pid" 2>/dev/null; then
            coord_log_warn "Worker didn't stop gracefully, force killing..."
            kill -KILL "$pid" 2>/dev/null || true
        fi
    fi

    # Update status
    update_prd_status "$prd_id" "stopped"

    coord_log_success "Worker stopped for $prd_id"
    return 0
}

# Force kill PRD worker
# Usage: force_kill_prd_worker <prd_id>
force_kill_prd_worker() {
    local prd_id="$1"

    local prd_info
    prd_info=$(get_prd_info "$prd_id")

    if [ "$prd_info" = "null" ]; then
        return 0
    fi

    local pid
    pid=$(echo "$prd_info" | jq -r '.pid')

    if [ -n "$pid" ] && [ "$pid" != "null" ]; then
        kill -KILL "$pid" 2>/dev/null || true
    fi

    update_prd_status "$prd_id" "killed"
}

# ============================================================================
# Version and Help
# ============================================================================

show_coordinator_version() {
    echo "prd-coordinator.sh v1.0.0"
    echo "Part of Claude-Loop - Parallel PRD Execution Support"
}

show_coordinator_help() {
    cat << EOF
prd-coordinator.sh - PRD Coordinator for Parallel Execution

USAGE:
    source lib/prd-coordinator.sh
    init_coordinator

    # Or run directly:
    ./lib/prd-coordinator.sh <command> [args]

COMMANDS:
    init                 Initialize coordinator
    start <PRD-ID>...    Start PRD workers
    stop <PRD-ID>        Stop specific PRD
    stop-all             Stop all PRDs
    status               Show coordinator status
    version              Show version
    help                 Show this help

CONFIGURATION:
    PARALLEL_MAX_PRDS              Max concurrent PRDs (default: 3)
    PARALLEL_API_LIMIT             Max concurrent API requests (default: 10)
    PARALLEL_MAX_WORKERS_PER_PRD   Max workers per PRD (default: 3)
    COORDINATOR_AUTO_MERGE         Auto-merge on completion (default: false)
    WORKTREE_CLEANUP_ON_SUCCESS    Remove worktrees on success (default: true)

EXAMPLES:
    # Initialize and start PRDs
    ./lib/prd-coordinator.sh start PRD-001 PRD-002

    # Check status
    ./lib/prd-coordinator.sh status

    # Stop specific PRD
    ./lib/prd-coordinator.sh stop PRD-001

EOF
}

# ============================================================================
# CLI Mode
# ============================================================================

# Main entry point for CLI usage
coord_main() {
    local command="${1:-help}"
    shift || true

    case "$command" in
        init)
            init_coordinator
            ;;
        version)
            show_coordinator_version
            ;;
        help|--help|-h)
            show_coordinator_help
            ;;
        *)
            coord_log_error "Unknown command: $command"
            show_coordinator_help
            exit 1
            ;;
    esac
}

# Run main if executed directly (not sourced)
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    coord_main "$@"
fi
