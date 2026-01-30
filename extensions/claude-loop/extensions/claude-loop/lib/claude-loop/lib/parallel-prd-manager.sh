#!/bin/bash
#
# parallel-prd-manager.sh - Manages parallel PRD execution with git worktrees
#
# Handles the case where multiple PRDs need different git branches by:
# 1. Detecting parallel execution attempts
# 2. Creating git worktrees for true parallel execution
# 3. Falling back to sequential queuing if worktrees not feasible
#

set -euo pipefail

# Configuration
WORKTREE_BASE_DIR=".claude-loop/worktrees"
LOCK_DIR=".claude-loop/locks"
QUEUE_DIR=".claude-loop/queue"

# ============================================================================
# Git Worktree Management
# ============================================================================

init_worktree_support() {
    local repo_root
    repo_root=$(git rev-parse --show-toplevel)

    # Create worktree base directory in repo root
    mkdir -p "${repo_root}/${WORKTREE_BASE_DIR}"
    mkdir -p "${repo_root}/${LOCK_DIR}"
    mkdir -p "${repo_root}/${QUEUE_DIR}"
}

create_worktree_for_prd() {
    local prd_file="$1"
    local target_branch="$2"
    local repo_root
    repo_root=$(git rev-parse --show-toplevel)

    # Generate worktree name from PRD
    local prd_name
    prd_name=$(basename "$prd_file" .json)
    local worktree_path="${repo_root}/${WORKTREE_BASE_DIR}/${prd_name}"

    # Check if worktree already exists
    if [ -d "$worktree_path" ]; then
        echo "$worktree_path"
        return 0
    fi

    # Create branch if it doesn't exist
    if ! git show-ref --verify --quiet "refs/heads/$target_branch"; then
        git branch "$target_branch" 2>/dev/null || true
    fi

    # Create worktree (suppress all output)
    if git worktree add "$worktree_path" "$target_branch" >/dev/null 2>&1; then
        echo "$worktree_path"
        return 0
    else
        # Worktree creation failed
        return 1
    fi
}

cleanup_worktree() {
    local worktree_path="$1"

    if [ -d "$worktree_path" ]; then
        git worktree remove "$worktree_path" --force 2>/dev/null || true
    fi
}

list_active_worktrees() {
    local repo_root
    repo_root=$(git rev-parse --show-toplevel)

    if [ -d "${repo_root}/${WORKTREE_BASE_DIR}" ]; then
        find "${repo_root}/${WORKTREE_BASE_DIR}" -mindepth 1 -maxdepth 1 -type d
    fi
}

# ============================================================================
# Parallel Execution Detection
# ============================================================================

detect_parallel_execution() {
    local current_prd="$1"
    local current_branch="$2"
    local repo_root
    repo_root=$(git rev-parse --show-toplevel)

    # Check for other active PRD executions
    local lock_files
    lock_files=$(find "${repo_root}/${LOCK_DIR}" -name "*.lock" -type f 2>/dev/null || echo "")

    if [ -z "$lock_files" ]; then
        # No other executions detected
        return 1
    fi

    # Check if any locks are for different branches
    local other_branch_detected=false

    for lock_file in $lock_files; do
        if [ -f "$lock_file" ]; then
            local lock_branch
            lock_branch=$(jq -r '.branch' "$lock_file" 2>/dev/null || echo "")

            if [ -n "$lock_branch" ] && [ "$lock_branch" != "$current_branch" ]; then
                other_branch_detected=true
                break
            fi
        fi
    done

    if [ "$other_branch_detected" = true ]; then
        return 0  # Parallel execution with different branches detected
    else
        return 1  # Same branch or no conflict
    fi
}

# ============================================================================
# Lock File Management
# ============================================================================

acquire_lock() {
    local prd_file="$1"
    local branch="$2"
    local repo_root
    repo_root=$(git rev-parse --show-toplevel)

    local prd_name
    prd_name=$(basename "$prd_file" .json)
    local lock_file="${repo_root}/${LOCK_DIR}/${prd_name}.lock"

    # Create lock file with metadata
    cat > "$lock_file" << EOF
{
    "prd": "$prd_file",
    "branch": "$branch",
    "pid": $$,
    "started_at": "$(date -u +"%Y-%m-%dT%H:%M:%SZ")",
    "hostname": "$(hostname)"
}
EOF

    echo "$lock_file"
}

release_lock() {
    local lock_file="$1"

    if [ -f "$lock_file" ]; then
        rm -f "$lock_file"
    fi
}

is_locked() {
    local prd_file="$1"
    local repo_root
    repo_root=$(git rev-parse --show-toplevel)

    local prd_name
    prd_name=$(basename "$prd_file" .json)
    local lock_file="${repo_root}/${LOCK_DIR}/${prd_name}.lock"

    if [ -f "$lock_file" ]; then
        # Check if process is still running
        local lock_pid
        lock_pid=$(jq -r '.pid' "$lock_file" 2>/dev/null || echo "")

        if [ -n "$lock_pid" ] && kill -0 "$lock_pid" 2>/dev/null; then
            return 0  # Lock is valid and process running
        else
            # Stale lock, remove it
            rm -f "$lock_file"
            return 1  # Not locked
        fi
    fi

    return 1  # Not locked
}

cleanup_stale_locks() {
    local repo_root
    repo_root=$(git rev-parse --show-toplevel)

    if [ ! -d "${repo_root}/${LOCK_DIR}" ]; then
        return
    fi

    for lock_file in "${repo_root}/${LOCK_DIR}"/*.lock; do
        if [ -f "$lock_file" ]; then
            local lock_pid
            lock_pid=$(jq -r '.pid' "$lock_file" 2>/dev/null || echo "")

            if [ -n "$lock_pid" ]; then
                if ! kill -0 "$lock_pid" 2>/dev/null; then
                    # Process not running, remove stale lock
                    rm -f "$lock_file"
                fi
            fi
        fi
    done
}

# ============================================================================
# Queue Management (Fallback for Sequential Execution)
# ============================================================================

enqueue_prd() {
    local prd_file="$1"
    local branch="$2"
    local repo_root
    repo_root=$(git rev-parse --show-toplevel)

    local prd_name
    prd_name=$(basename "$prd_file" .json)
    local queue_file="${repo_root}/${QUEUE_DIR}/${prd_name}.queue"

    cat > "$queue_file" << EOF
{
    "prd": "$prd_file",
    "branch": "$branch",
    "queued_at": "$(date -u +"%Y-%m-%dT%H:%M:%SZ")",
    "priority": 1
}
EOF
}

dequeue_prd() {
    local repo_root
    repo_root=$(git rev-parse --show-toplevel)

    # Find oldest queued PRD
    local oldest_queue_file
    oldest_queue_file=$(find "${repo_root}/${QUEUE_DIR}" -name "*.queue" -type f 2>/dev/null | head -1)

    if [ -n "$oldest_queue_file" ] && [ -f "$oldest_queue_file" ]; then
        local prd_file
        prd_file=$(jq -r '.prd' "$oldest_queue_file")
        rm -f "$oldest_queue_file"
        echo "$prd_file"
    fi
}

get_queue_size() {
    local repo_root
    repo_root=$(git rev-parse --show-toplevel)

    find "${repo_root}/${QUEUE_DIR}" -name "*.queue" -type f 2>/dev/null | wc -l | tr -d ' '
}

# ============================================================================
# Main Entry Point: Parallel Execution Strategy Selection
# ============================================================================

handle_parallel_execution() {
    local prd_file="$1"
    local target_branch="$2"
    local force_sequential="${3:-false}"

    init_worktree_support
    cleanup_stale_locks

    # Check if already locked
    if is_locked "$prd_file"; then
        echo "ERROR: PRD already running: $prd_file" >&2
        return 1
    fi

    # Detect parallel execution with different branches
    if detect_parallel_execution "$prd_file" "$target_branch"; then
        echo "PARALLEL_CONFLICT_DETECTED" >&2

        # Strategy 1: Try git worktrees (true parallel execution)
        if [ "$force_sequential" != "true" ] && command -v git worktree &>/dev/null; then
            local worktree_path
            if worktree_path=$(create_worktree_for_prd "$prd_file" "$target_branch"); then
                echo "WORKTREE:$worktree_path"
                return 0
            fi
        fi

        # Strategy 2: Queue for sequential execution
        enqueue_prd "$prd_file" "$target_branch"

        local queue_size
        queue_size=$(get_queue_size)

        echo "QUEUED:$queue_size"
        return 2  # Queued, not running yet
    fi

    # No conflict, can proceed normally
    echo "NO_CONFLICT"
    return 0
}

# ============================================================================
# Cleanup on Exit
# ============================================================================

cleanup_on_exit() {
    local lock_file="$1"
    local worktree_path="${2:-}"

    release_lock "$lock_file"

    if [ -n "$worktree_path" ] && [ "$worktree_path" != "NONE" ]; then
        cleanup_worktree "$worktree_path"
    fi
}

# ============================================================================
# Status Reporting
# ============================================================================

get_parallel_execution_status() {
    local repo_root
    repo_root=$(git rev-parse --show-toplevel)

    echo "=== Parallel PRD Execution Status ==="
    echo ""

    # Active executions
    echo "Active Executions:"
    local lock_count=0
    shopt -s nullglob
    for lock_file in "${repo_root}/${LOCK_DIR}"/*.lock; do
        if [ -f "$lock_file" ]; then
            local prd_name branch pid started
            prd_name=$(jq -r '.prd' "$lock_file" | xargs basename | sed 's/.json$//')
            branch=$(jq -r '.branch' "$lock_file")
            pid=$(jq -r '.pid' "$lock_file")
            started=$(jq -r '.started_at' "$lock_file")

            echo "  - $prd_name (branch: $branch, PID: $pid, started: $started)"
            lock_count=$((lock_count + 1))
        fi
    done

    if [ $lock_count -eq 0 ]; then
        echo "  (none)"
    fi

    echo ""

    # Queued PRDs
    echo "Queued PRDs:"
    local queue_count=0
    for queue_file in "${repo_root}/${QUEUE_DIR}"/*.queue; do
        if [ -f "$queue_file" ]; then
            local prd_name branch queued
            prd_name=$(jq -r '.prd' "$queue_file" | xargs basename | sed 's/.json$//')
            branch=$(jq -r '.branch' "$queue_file")
            queued=$(jq -r '.queued_at' "$queue_file")

            echo "  - $prd_name (branch: $branch, queued: $queued)"
            queue_count=$((queue_count + 1))
        fi
    done

    if [ $queue_count -eq 0 ]; then
        echo "  (none)"
    fi

    echo ""

    # Active worktrees
    echo "Active Worktrees:"
    local worktree_count=0
    for worktree in $(list_active_worktrees); do
        local worktree_name
        worktree_name=$(basename "$worktree")
        echo "  - $worktree_name"
        worktree_count=$((worktree_count + 1))
    done

    if [ $worktree_count -eq 0 ]; then
        echo "  (none)"
    fi
}

# Export functions for use by claude-loop.sh
export -f init_worktree_support
export -f create_worktree_for_prd
export -f cleanup_worktree
export -f detect_parallel_execution
export -f acquire_lock
export -f release_lock
export -f is_locked
export -f handle_parallel_execution
export -f cleanup_on_exit
export -f get_parallel_execution_status
