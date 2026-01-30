#!/bin/bash
#
# checkpoint-functions.sh - Per-Iteration Checkpoint Functions
#
# Provides frequent checkpoint saving after each iteration with atomic writes
# and automatic cleanup of old checkpoints.
#
# Usage:
#   source lib/checkpoint-functions.sh
#
#   # Save checkpoint after each iteration
#   save_checkpoint "$story_id" "$iteration" "$prd_file"
#
#   # Load latest checkpoint
#   checkpoint_data=$(load_latest_checkpoint)
#
#   # List all checkpoints
#   list_checkpoints
#
#   # Validate checkpoint integrity
#   validate_checkpoint "$checkpoint_file"

set -euo pipefail

# ============================================================================
# Checkpoint Functions (Per-Iteration Saves - US-001)
# ============================================================================

# Save checkpoint after each iteration with atomic write
# US-001: Write to temp file first, then atomic rename to prevent corruption
# Usage: save_checkpoint <story_id> <iteration> <prd_file>
save_checkpoint() {
    local story_id="$1"
    local iteration="$2"
    local prd_file="$3"

    if [ -z "${SESSION_ID:-}" ]; then
        echo "[CHECKPOINT] Warning: No active session - cannot save checkpoint" >&2
        return 1
    fi

    # Create checkpoint directory for this session
    local checkpoint_session_dir="${SESSION_CHECKPOINT_DIR}/${SESSION_ID}"
    mkdir -p "$checkpoint_session_dir"

    # Generate checkpoint filename with iteration number (US-001: timestamped)
    local checkpoint_num
    checkpoint_num=$(printf "%04d" "$iteration")
    local checkpoint_file="${checkpoint_session_dir}/${checkpoint_num}_${story_id}_$(date +%Y%m%d_%H%M%S).json"
    local temp_file="${checkpoint_file}.tmp"

    # Get PRD state (story completion status)
    local prd_state="{}"
    if [ -f "$prd_file" ]; then
        prd_state=$(jq '{
            total_stories: (.userStories | length),
            completed_stories: ([.userStories[] | select(.passes == true)] | length),
            current_story_status: (.userStories[] | select(.id == $story_id) | {id, title, passes, notes})
        }' --arg story_id "$story_id" "$prd_file" 2>/dev/null) || prd_state="{}"
    fi

    # Build checkpoint JSON (US-001: includes all required fields)
    local timestamp
    timestamp=$(date -u +%Y-%m-%dT%H:%M:%SZ)

    # US-001: Write to temp file first (atomic write protection)
    cat > "$temp_file" << EOF
{
  "session_id": "$SESSION_ID",
  "story_id": "$story_id",
  "iteration": $iteration,
  "timestamp": "$timestamp",
  "prd_file": "$(realpath "$prd_file" 2>/dev/null || echo "$prd_file")",
  "prd_state": $prd_state,
  "checkpoint_file": "$checkpoint_file"
}
EOF

    # US-001: Atomic rename (prevents corruption if process killed mid-write)
    if ! mv "$temp_file" "$checkpoint_file"; then
        echo "[CHECKPOINT] Warning: Failed to save checkpoint" >&2
        rm -f "$temp_file"
        return 1
    fi

    echo "[CHECKPOINT] Saved: iteration $iteration, story $story_id" >&2

    # US-001: Clean up old checkpoints (keep last 3)
    cleanup_old_checkpoints "$checkpoint_session_dir"

    return 0
}

# Clean up old checkpoints, keeping last MAX_CHECKPOINTS
# US-001: Keep last 3 checkpoints for rollback
# Usage: cleanup_old_checkpoints <checkpoint_dir>
cleanup_old_checkpoints() {
    local checkpoint_dir="$1"
    local max_checkpoints="${MAX_CHECKPOINTS:-3}"

    if [ ! -d "$checkpoint_dir" ]; then
        return 0
    fi

    # Count checkpoint files
    local checkpoint_count
    checkpoint_count=$(find "$checkpoint_dir" -name "*.json" -type f 2>/dev/null | wc -l | tr -d ' ')

    if [ "$checkpoint_count" -le "$max_checkpoints" ]; then
        return 0
    fi

    # Remove oldest checkpoints (sorted by filename, which includes timestamp)
    local to_remove=$((checkpoint_count - max_checkpoints))
    find "$checkpoint_dir" -name "*.json" -type f | sort | head -n "$to_remove" | while read -r old_checkpoint; do
        rm -f "$old_checkpoint"
        echo "[CHECKPOINT] Removed old checkpoint: $(basename "$old_checkpoint")" >&2
    done
}

# Load latest checkpoint for recovery
# Usage: load_latest_checkpoint
# Returns: JSON checkpoint data or empty object
load_latest_checkpoint() {
    if [ -z "${SESSION_ID:-}" ]; then
        echo "{}"
        return 1
    fi

    local checkpoint_session_dir="${SESSION_CHECKPOINT_DIR}/${SESSION_ID}"

    if [ ! -d "$checkpoint_session_dir" ]; then
        echo "{}"
        return 1
    fi

    # Get latest checkpoint file (most recent by filename)
    local latest_checkpoint
    latest_checkpoint=$(find "$checkpoint_session_dir" -name "*.json" -type f 2>/dev/null | sort -r | head -1)

    if [ -z "$latest_checkpoint" ] || [ ! -f "$latest_checkpoint" ]; then
        echo "{}"
        return 1
    fi

    cat "$latest_checkpoint"
}

# List all checkpoints for current session
# Usage: list_checkpoints [session_id]
list_checkpoints() {
    local target_session="${1:-${SESSION_ID:-}}"

    if [ -z "$target_session" ]; then
        echo "No active session"
        return 1
    fi

    local checkpoint_session_dir="${SESSION_CHECKPOINT_DIR}/${target_session}"

    if [ ! -d "$checkpoint_session_dir" ]; then
        echo "No checkpoints found for session: $target_session"
        return 0
    fi

    echo "Checkpoints for session: $target_session"
    echo ""

    local checkpoints
    checkpoints=$(find "$checkpoint_session_dir" -name "*.json" -type f 2>/dev/null | sort -r)

    if [ -z "$checkpoints" ]; then
        echo "  No checkpoints found"
        return 0
    fi

    while IFS= read -r checkpoint_file; do
        local iteration story_id timestamp
        iteration=$(jq -r '.iteration // "?"' "$checkpoint_file" 2>/dev/null)
        story_id=$(jq -r '.story_id // "?"' "$checkpoint_file" 2>/dev/null)
        timestamp=$(jq -r '.timestamp // "?"' "$checkpoint_file" 2>/dev/null)
        printf "  Iteration %4s | Story: %-15s | %s\n" "$iteration" "$story_id" "$timestamp"
    done <<< "$checkpoints"
}

# Validate checkpoint file integrity (US-002 preparation)
# Usage: validate_checkpoint <checkpoint_file>
# Returns: 0 if valid, 1 if invalid
validate_checkpoint() {
    local checkpoint_file="$1"

    if [ ! -f "$checkpoint_file" ]; then
        echo "[CHECKPOINT] Error: Checkpoint file not found: $checkpoint_file" >&2
        return 1
    fi

    # Check if valid JSON
    if ! jq empty "$checkpoint_file" 2>/dev/null; then
        echo "[CHECKPOINT] Error: Invalid JSON in checkpoint: $checkpoint_file" >&2
        return 1
    fi

    # Check required fields (US-001)
    local required_fields=("session_id" "story_id" "iteration" "timestamp")
    for field in "${required_fields[@]}"; do
        local value
        value=$(jq -r ".$field // empty" "$checkpoint_file" 2>/dev/null)
        if [ -z "$value" ]; then
            echo "[CHECKPOINT] Error: Missing required field '$field' in checkpoint: $checkpoint_file" >&2
            return 1
        fi
    done

    echo "[CHECKPOINT] Checkpoint valid: $checkpoint_file" >&2
    return 0
}

# Test checkpoint save/load by simulating a crash recovery
# Usage: test_checkpoint_recovery <prd_file>
test_checkpoint_recovery() {
    local prd_file="$1"

    echo "Testing checkpoint save/load cycle..."
    echo ""

    # Save a test checkpoint
    echo "1. Saving test checkpoint..."
    if save_checkpoint "TEST-001" 1 "$prd_file"; then
        echo "   ✓ Checkpoint saved successfully"
    else
        echo "   ✗ Failed to save checkpoint"
        return 1
    fi

    # Load the checkpoint
    echo ""
    echo "2. Loading latest checkpoint..."
    local checkpoint_data
    checkpoint_data=$(load_latest_checkpoint)

    if [ "$checkpoint_data" != "{}" ]; then
        echo "   ✓ Checkpoint loaded successfully"
        echo ""
        echo "   Checkpoint data:"
        echo "$checkpoint_data" | jq '.'
    else
        echo "   ✗ Failed to load checkpoint"
        return 1
    fi

    # Validate the checkpoint
    echo ""
    echo "3. Validating checkpoint..."
    local checkpoint_file
    checkpoint_file=$(echo "$checkpoint_data" | jq -r '.checkpoint_file')

    if validate_checkpoint "$checkpoint_file"; then
        echo "   ✓ Checkpoint validation passed"
    else
        echo "   ✗ Checkpoint validation failed"
        return 1
    fi

    echo ""
    echo "✓ Checkpoint recovery test passed!"
    return 0
}
