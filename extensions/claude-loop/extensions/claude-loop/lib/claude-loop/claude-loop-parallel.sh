#!/bin/bash
#
# claude-loop-parallel.sh - Wrapper for parallel PRD execution
#
# Enables running multiple PRDs with different branches simultaneously using git worktrees
#

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CLAUDE_LOOP="${SCRIPT_DIR}/claude-loop.sh"
PARALLEL_MANAGER="${SCRIPT_DIR}/lib/parallel-prd-manager.sh"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Source parallel manager
if [ -f "$PARALLEL_MANAGER" ]; then
    source "$PARALLEL_MANAGER"
else
    log_error "Parallel manager not found: $PARALLEL_MANAGER"
    exit 1
fi

# Parse arguments
PRD_FILE=""
REMAINING_ARGS=()

while [[ $# -gt 0 ]]; do
    case $1 in
        -p|--prd)
            PRD_FILE="$2"
            REMAINING_ARGS+=("$1" "$2")
            shift 2
            ;;
        --parallel-status)
            get_parallel_execution_status
            exit 0
            ;;
        --force-sequential)
            FORCE_SEQUENTIAL=true
            shift
            ;;
        *)
            REMAINING_ARGS+=("$1")
            shift
            ;;
    esac
done

# If no PRD specified, pass through to claude-loop
if [ -z "$PRD_FILE" ]; then
    exec "$CLAUDE_LOOP" "${REMAINING_ARGS[@]}"
    exit $?
fi

# Get target branch from PRD
TARGET_BRANCH=$(jq -r '.branchName // "feature/claude-loop"' "$PRD_FILE")

log_info "PRD: $PRD_FILE"
log_info "Target branch: $TARGET_BRANCH"

# Initialize parallel support
init_worktree_support
cleanup_stale_locks

# Handle parallel execution
log_info "Checking for parallel execution conflicts..."

result=$(handle_parallel_execution "$PRD_FILE" "$TARGET_BRANCH" "${FORCE_SEQUENTIAL:-false}")
exit_code=$?

case "$result" in
    NO_CONFLICT)
        log_success "No conflicts detected, proceeding normally"
        LOCK_FILE=$(acquire_lock "$PRD_FILE" "$TARGET_BRANCH")
        trap "release_lock '$LOCK_FILE'" EXIT INT TERM

        # Run claude-loop normally
        exec "$CLAUDE_LOOP" "${REMAINING_ARGS[@]}"
        ;;

    WORKTREE:*)
        WORKTREE_PATH="${result#WORKTREE:}"
        log_success "Created worktree for parallel execution"
        log_info "Worktree path: $WORKTREE_PATH"
        log_info "This PRD will run in isolation"

        LOCK_FILE=$(acquire_lock "$PRD_FILE" "$TARGET_BRANCH")
        trap "cleanup_on_exit '$LOCK_FILE' '$WORKTREE_PATH'" EXIT INT TERM

        # Get absolute path of PRD file before changing directory
        PRD_ABS_PATH=$(cd "$(dirname "$PRD_FILE")" && pwd)/$(basename "$PRD_FILE")
        PRD_BASENAME=$(basename "$PRD_FILE")

        # Copy PRD file into worktree
        cp "$PRD_ABS_PATH" "$WORKTREE_PATH/"

        # Update REMAINING_ARGS to use basename only
        WORKTREE_ARGS=()
        skip_next=false
        for arg in "${REMAINING_ARGS[@]}"; do
            if [ "$skip_next" = true ]; then
                WORKTREE_ARGS+=("$PRD_BASENAME")
                skip_next=false
            elif [ "$arg" = "-p" ] || [ "$arg" = "--prd" ]; then
                WORKTREE_ARGS+=("$arg")
                skip_next=true
            else
                WORKTREE_ARGS+=("$arg")
            fi
        done

        # Run claude-loop in worktree
        cd "$WORKTREE_PATH"
        exec "$CLAUDE_LOOP" "${WORKTREE_ARGS[@]}"
        ;;

    QUEUED:*)
        queue_position="${result#QUEUED:}"
        log_warn "Parallel execution conflict detected!"
        log_info "Another PRD is running on a different branch"
        log_info "This PRD has been queued (position: $queue_position)"
        echo ""
        log_info "Waiting for queue to clear..."

        # Wait for queue
        while [ "$(get_queue_size)" -gt 0 ]; do
            current_size=$(get_queue_size)
            echo -ne "\r  Queue size: $current_size  "
            sleep 5
        done

        echo ""
        log_success "Queue cleared, starting execution..."

        # Retry
        exec "$0" "${REMAINING_ARGS[@]}"
        ;;

    *)
        log_error "Unexpected result from parallel handler: $result"
        exit 1
        ;;
esac
