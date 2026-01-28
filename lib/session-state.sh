#!/bin/bash
#
# session-state.sh - Session State Management for claude-loop
#
# Provides auto-save and resume capability for long-running feature implementations.
# Saves progress state after each story completion and allows resuming from interruption.
#
# Session State File: .claude-loop/session-state.json
# Contains: current phase, story, iteration, timestamps, project info
#
# Usage:
#   source lib/session-state.sh
#
#   # Initialize session
#   init_session "$PRD_FILE"
#
#   # Save after story completion
#   save_session_state "$story_id" "$iteration" "$phase"
#
#   # Resume from last session
#   resume_session
#
#   # Resume from specific session
#   resume_session_by_id "session_abc123"
#
# Session State JSON Format:
# {
#   "session_id": "proj_branch_20260112_143000",
#   "project": "invisible-intelligence",
#   "branch": "feature/invisible-intelligence",
#   "prd_file": "/path/to/prd.json",
#   "current_phase": "implementation",
#   "current_story": "INV-007",
#   "current_iteration": 3,
#   "started_at": "2026-01-12T14:30:00Z",
#   "last_saved_at": "2026-01-12T15:45:00Z",
#   "stories_completed": 6,
#   "stories_total": 12,
#   "auto_save_enabled": true
# }

# NOTE: Removed "set -euo pipefail" to allow this file to be sourced without affecting the caller's error handling
# Individual functions use proper error handling with explicit returns

# ============================================================================
# Configuration
# ============================================================================

SESSION_STATE_DIR="${SESSION_STATE_DIR:-.claude-loop}"
SESSION_STATE_FILE="${SESSION_STATE_FILE:-${SESSION_STATE_DIR}/session-state.json}"
SESSION_ARCHIVE_DIR="${SESSION_STATE_DIR}/sessions"
SESSION_CHECKPOINT_DIR="${SESSION_STATE_DIR}/checkpoints"
MAX_SESSION_ARCHIVES=10  # Keep last N session archives
MAX_CHECKPOINTS=3  # Keep last N checkpoints for rollback
SESSION_ID=""  # Current session ID, set by init_session
AUTO_SAVE_ENABLED=true

# Colors for output
SESSION_CYAN='\033[0;36m'
SESSION_GREEN='\033[0;32m'
SESSION_YELLOW='\033[1;33m'
SESSION_NC='\033[0m'

# ============================================================================
# Helper Functions
# ============================================================================

session_log() {
    echo -e "${SESSION_CYAN}[SESSION]${SESSION_NC} $1"
}

session_success() {
    echo -e "${SESSION_GREEN}[SESSION]${SESSION_NC} $1"
}

session_warn() {
    echo -e "${SESSION_YELLOW}[SESSION]${SESSION_NC} $1"
}

# Generate a unique session ID based on project, branch, and timestamp
generate_session_id() {
    local project="$1"
    local branch="$2"
    local timestamp
    timestamp=$(date +%Y%m%d_%H%M%S)

    # Sanitize project and branch names
    local safe_project
    safe_project=$(echo "$project" | tr -cd '[:alnum:]-_' | cut -c1-20)
    local safe_branch
    safe_branch=$(echo "$branch" | tr '/' '_' | tr -cd '[:alnum:]-_' | cut -c1-30)

    echo "${safe_project}_${safe_branch}_${timestamp}"
}

# Get ISO 8601 timestamp
get_iso_timestamp() {
    date -u +%Y-%m-%dT%H:%M:%SZ
}

# ============================================================================
# Session State Functions
# ============================================================================

# Initialize session state directory and return session info
# Usage: init_session <prd_file> [project_name] [branch_name]
init_session() {
    local prd_file="$1"
    local project_name="${2:-}"
    local branch_name="${3:-}"

    # Ensure state directory exists
    mkdir -p "$SESSION_STATE_DIR"
    mkdir -p "$SESSION_ARCHIVE_DIR"
    mkdir -p "$SESSION_CHECKPOINT_DIR"

    # Extract project and branch from PRD if not provided
    if [ -z "$project_name" ] && [ -f "$prd_file" ]; then
        project_name=$(jq -r '.project // "unnamed"' "$prd_file" 2>/dev/null) || project_name="unnamed"
    fi
    if [ -z "$branch_name" ] && [ -f "$prd_file" ]; then
        branch_name=$(jq -r '.branchName // "feature/main"' "$prd_file" 2>/dev/null) || branch_name="feature/main"
    fi

    # US-003 AC1,AC2,AC3: Check for crash recovery before continuing
    if [ -f "$SESSION_STATE_FILE" ]; then
        local clean_shutdown
        clean_shutdown=$(jq -r '.clean_shutdown // false' "$SESSION_STATE_FILE" 2>/dev/null) || clean_shutdown="false"

        # If unclean shutdown detected, handle recovery
        if [ "$clean_shutdown" = "false" ]; then
            if ! handle_crash_recovery "$prd_file"; then
                return 1
            fi
        fi
    fi

    # Check for existing session
    if [ -f "$SESSION_STATE_FILE" ]; then
        local existing_prd
        existing_prd=$(jq -r '.prd_file // ""' "$SESSION_STATE_FILE" 2>/dev/null) || existing_prd=""

        # If same PRD file, continue existing session
        if [ "$existing_prd" = "$prd_file" ] || [ "$existing_prd" = "$(realpath "$prd_file" 2>/dev/null)" ]; then
            SESSION_ID=$(jq -r '.session_id // ""' "$SESSION_STATE_FILE" 2>/dev/null) || SESSION_ID=""
            if [ -n "$SESSION_ID" ]; then
                session_log "Continuing existing session: $SESSION_ID"
                # Mark as unclean since we're starting work
                mark_unclean_shutdown
                return 0
            fi
        fi
    fi

    # Generate new session ID
    SESSION_ID=$(generate_session_id "$project_name" "$branch_name")

    # Get story counts
    local total_stories=0
    local completed_stories=0
    if [ -f "$prd_file" ]; then
        total_stories=$(jq '.userStories | length' "$prd_file" 2>/dev/null) || total_stories=0
        completed_stories=$(jq '[.userStories[] | select(.passes == true)] | length' "$prd_file" 2>/dev/null) || completed_stories=0
    fi

    # Create initial session state
    local timestamp
    timestamp=$(get_iso_timestamp)

    cat > "$SESSION_STATE_FILE" << EOF
{
  "session_id": "$SESSION_ID",
  "project": "$project_name",
  "branch": "$branch_name",
  "prd_file": "$(realpath "$prd_file" 2>/dev/null || echo "$prd_file")",
  "current_phase": "implementation",
  "current_story": null,
  "current_iteration": 0,
  "started_at": "$timestamp",
  "last_saved_at": "$timestamp",
  "stories_completed": $completed_stories,
  "stories_total": $total_stories,
  "auto_save_enabled": true,
  "clean_shutdown": false
}
EOF

    session_success "New session initialized: $SESSION_ID"
    session_log "Progress auto-saves after each story. You can close this safely."

    echo "$SESSION_ID"
}

# Save current session state
# Usage: save_session_state <story_id> <iteration> [phase]
save_session_state() {
    local story_id="$1"
    local iteration="$2"
    local phase="${3:-implementation}"

    if [ ! -f "$SESSION_STATE_FILE" ]; then
        session_warn "No active session to save"
        return 1
    fi

    local timestamp
    timestamp=$(get_iso_timestamp)

    # Get current story counts from PRD
    local prd_file
    prd_file=$(jq -r '.prd_file // ""' "$SESSION_STATE_FILE" 2>/dev/null) || prd_file=""

    local total_stories=0
    local completed_stories=0
    if [ -f "$prd_file" ]; then
        total_stories=$(jq '.userStories | length' "$prd_file" 2>/dev/null) || total_stories=0
        completed_stories=$(jq '[.userStories[] | select(.passes == true)] | length' "$prd_file" 2>/dev/null) || completed_stories=0
    fi

    # SAFETY: Update session state using jq with file locking to prevent TOCTOU race conditions
    local temp_file
    temp_file=$(mktemp) || {
        session_warn "Failed to create temp file"
        return 1
    }

    # Ensure temp file is cleaned up on function exit
    trap "rm -f '$temp_file'" RETURN

    # Acquire exclusive lock on session state file
    local lock_file="${SESSION_STATE_FILE}.lock"
    exec 200>"$lock_file" || {
        session_warn "Failed to create lock file"
        return 1
    }

    # Use flock if available, otherwise use simple lock file
    if command -v flock >/dev/null 2>&1; then
        flock -x 200 || {
            session_warn "Failed to acquire lock"
            return 1
        }
    fi

    # Perform atomic update with lock held
    if ! jq --arg story "$story_id" \
       --arg phase "$phase" \
       --argjson iter "$iteration" \
       --arg timestamp "$timestamp" \
       --argjson completed "$completed_stories" \
       --argjson total "$total_stories" \
       '.current_story = $story |
        .current_phase = $phase |
        .current_iteration = $iter |
        .last_saved_at = $timestamp |
        .stories_completed = $completed |
        .stories_total = $total' \
       "$SESSION_STATE_FILE" > "$temp_file" 2>&1; then
        session_warn "jq processing failed"
        return 1
    fi

    if ! mv "$temp_file" "$SESSION_STATE_FILE"; then
        session_warn "Failed to update session state file"
        return 1
    fi

    # Lock is released automatically when fd 200 closes (on function exit)

    # US-001 AC1: Save checkpoint after every iteration (not just story completion)
    # Create a compact PRD summary for the checkpoint (to avoid shell escaping issues with large JSON)
    local prd_summary="{}"
    if [ -f "$prd_file" ]; then
        # Extract just the essential PRD state (project, stories completed count)
        prd_summary=$(jq -c '{project: .project, branchName: .branchName, stories_completed: ([.userStories[] | select(.passes)] | length), stories_total: (.userStories | length)}' "$prd_file" 2>/dev/null) || prd_summary="{}"
    fi

    # Save checkpoint with PRD summary
    save_checkpoint "$story_id" "$iteration" "$prd_summary"

    session_log "Progress saved: Story $story_id, Iteration $iteration"
}

# Mark a story as completed and save state
# Usage: mark_story_complete <story_id> <iteration> [phase]
mark_story_complete() {
    local story_id="$1"
    local iteration="$2"
    local phase="${3:-implementation}"

    save_session_state "$story_id" "$iteration" "$phase"
    session_success "Story $story_id completed. Progress auto-saved."
}

# Get session state summary for display
# Usage: get_session_summary
# Returns: formatted summary string
get_session_summary() {
    if [ ! -f "$SESSION_STATE_FILE" ]; then
        echo "No active session"
        return 1
    fi

    local session_id project branch phase story iteration completed total started last_saved
    session_id=$(jq -r '.session_id // "unknown"' "$SESSION_STATE_FILE")
    project=$(jq -r '.project // "unknown"' "$SESSION_STATE_FILE")
    branch=$(jq -r '.branch // "unknown"' "$SESSION_STATE_FILE")
    phase=$(jq -r '.current_phase // "unknown"' "$SESSION_STATE_FILE")
    story=$(jq -r '.current_story // "none"' "$SESSION_STATE_FILE")
    iteration=$(jq -r '.current_iteration // 0' "$SESSION_STATE_FILE")
    completed=$(jq -r '.stories_completed // 0' "$SESSION_STATE_FILE")
    total=$(jq -r '.stories_total // 0' "$SESSION_STATE_FILE")
    started=$(jq -r '.started_at // "unknown"' "$SESSION_STATE_FILE")
    last_saved=$(jq -r '.last_saved_at // "unknown"' "$SESSION_STATE_FILE")

    cat << EOF
Session: $session_id
Project: $project
Branch:  $branch
Phase:   $phase
Story:   $story
Progress: $completed/$total stories complete
Iteration: $iteration
Started:  $started
Last Saved: $last_saved
EOF
}

# Check if there's a session to resume
# Usage: has_resumable_session [prd_file]
# Returns: 0 if resumable, 1 if not
has_resumable_session() {
    local prd_file="${1:-}"

    if [ ! -f "$SESSION_STATE_FILE" ]; then
        return 1
    fi

    # Check if session is for the same PRD (if specified)
    if [ -n "$prd_file" ]; then
        local session_prd
        session_prd=$(jq -r '.prd_file // ""' "$SESSION_STATE_FILE" 2>/dev/null) || session_prd=""
        local real_prd
        real_prd=$(realpath "$prd_file" 2>/dev/null) || real_prd="$prd_file"

        if [ "$session_prd" != "$prd_file" ] && [ "$session_prd" != "$real_prd" ]; then
            return 1
        fi
    fi

    # Check if session has any progress
    local iteration
    iteration=$(jq -r '.current_iteration // 0' "$SESSION_STATE_FILE" 2>/dev/null) || iteration=0

    if [ "$iteration" -gt 0 ]; then
        return 0
    fi

    return 1
}

# Resume from existing session
# Usage: resume_session [show_summary]
# Returns: JSON with resume info: {"iteration": N, "story": "...", "phase": "..."}
resume_session() {
    local show_summary="${1:-true}"

    if [ ! -f "$SESSION_STATE_FILE" ]; then
        session_warn "No session to resume"
        return 1
    fi

    if [ "$show_summary" = "true" ]; then
        echo ""
        echo "Resuming from previous session:"
        echo "================================"
        get_session_summary
        echo "================================"
        echo ""
    fi

    # Return resume info as JSON
    jq '{
        iteration: .current_iteration,
        story: .current_story,
        phase: .current_phase,
        stories_completed: .stories_completed,
        stories_total: .stories_total
    }' "$SESSION_STATE_FILE"
}

# Resume from a specific session ID
# Usage: resume_session_by_id <session_id>
resume_session_by_id() {
    local target_id="$1"

    # Check current session
    if [ -f "$SESSION_STATE_FILE" ]; then
        local current_id
        current_id=$(jq -r '.session_id // ""' "$SESSION_STATE_FILE" 2>/dev/null) || current_id=""

        if [ "$current_id" = "$target_id" ]; then
            session_log "Session $target_id is the current session"
            resume_session "true"
            return $?
        fi
    fi

    # Search in archives
    local archive_file="${SESSION_ARCHIVE_DIR}/${target_id}.json"
    if [ -f "$archive_file" ]; then
        session_log "Restoring session from archive: $target_id"
        cp "$archive_file" "$SESSION_STATE_FILE"
        SESSION_ID="$target_id"
        resume_session "true"
        return $?
    fi

    session_warn "Session not found: $target_id"
    return 1
}

# List available sessions (current and archived)
# Usage: list_sessions [format]
# format: text (default) or json
list_sessions() {
    local format="${1:-text}"

    local sessions=()

    # Add current session if exists
    if [ -f "$SESSION_STATE_FILE" ]; then
        local current
        current=$(jq -c '. + {"status": "current"}' "$SESSION_STATE_FILE" 2>/dev/null) || current=""
        if [ -n "$current" ]; then
            sessions+=("$current")
        fi
    fi

    # Add archived sessions
    if [ -d "$SESSION_ARCHIVE_DIR" ]; then
        for archive in "$SESSION_ARCHIVE_DIR"/*.json; do
            if [ -f "$archive" ]; then
                local archived
                archived=$(jq -c '. + {"status": "archived"}' "$archive" 2>/dev/null) || continue
                sessions+=("$archived")
            fi
        done
    fi

    if [ ${#sessions[@]} -eq 0 ]; then
        if [ "$format" = "json" ]; then
            echo "[]"
        else
            echo "No sessions found"
        fi
        return 0
    fi

    if [ "$format" = "json" ]; then
        printf '%s\n' "${sessions[@]}" | jq -s '.'
    else
        echo "Available sessions:"
        echo ""
        for session in "${sessions[@]}"; do
            local id status project completed total
            id=$(echo "$session" | jq -r '.session_id')
            status=$(echo "$session" | jq -r '.status')
            project=$(echo "$session" | jq -r '.project')
            completed=$(echo "$session" | jq -r '.stories_completed')
            total=$(echo "$session" | jq -r '.stories_total')
            printf "  %-40s [%s] %s (%d/%d stories)\n" "$id" "$status" "$project" "$completed" "$total"
        done
    fi
}

# Archive current session and clean up
# Usage: archive_session [reason]
archive_session() {
    local reason="${1:-completed}"

    if [ ! -f "$SESSION_STATE_FILE" ]; then
        return 0
    fi

    local session_id
    session_id=$(jq -r '.session_id // ""' "$SESSION_STATE_FILE" 2>/dev/null) || session_id=""

    if [ -z "$session_id" ]; then
        return 0
    fi

    # Add archive metadata
    local timestamp
    timestamp=$(get_iso_timestamp)

    local temp_file
    temp_file=$(mktemp)

    jq --arg reason "$reason" \
       --arg timestamp "$timestamp" \
       '. + {"archived_at": $timestamp, "archive_reason": $reason}' \
       "$SESSION_STATE_FILE" > "$temp_file"

    # Move to archive
    mv "$temp_file" "${SESSION_ARCHIVE_DIR}/${session_id}.json"

    session_log "Session archived: $session_id (reason: $reason)"

    # Clean up old archives
    cleanup_old_sessions
}

# Clean up old session archives
cleanup_old_sessions() {
    if [ ! -d "$SESSION_ARCHIVE_DIR" ]; then
        return 0
    fi

    # Count archives
    local count
    count=$(ls -1 "$SESSION_ARCHIVE_DIR"/*.json 2>/dev/null | wc -l | tr -d ' ')

    if [ "$count" -le "$MAX_SESSION_ARCHIVES" ]; then
        return 0
    fi

    # Remove oldest archives (sorted by modification time)
    local to_remove=$((count - MAX_SESSION_ARCHIVES))
    ls -1t "$SESSION_ARCHIVE_DIR"/*.json 2>/dev/null | tail -n "$to_remove" | while read -r old_archive; do
        rm -f "$old_archive"
        session_log "Cleaned up old session: $(basename "$old_archive" .json)"
    done
}

# Clear current session (for fresh start)
# Usage: clear_session
clear_session() {
    if [ -f "$SESSION_STATE_FILE" ]; then
        archive_session "cleared"
        rm -f "$SESSION_STATE_FILE"
        session_log "Session cleared"
    fi
    SESSION_ID=""
}

# Complete session successfully
# Usage: complete_session
complete_session() {
    if [ ! -f "$SESSION_STATE_FILE" ]; then
        return 0
    fi

    # Mark clean shutdown before archiving
    mark_clean_shutdown

    session_success "All stories complete! Session finished."
    archive_session "completed"
    rm -f "$SESSION_STATE_FILE"
    SESSION_ID=""
}

# Mark clean shutdown in session state
# Usage: mark_clean_shutdown
mark_clean_shutdown() {
    if [ ! -f "$SESSION_STATE_FILE" ]; then
        return 0
    fi

    local timestamp
    timestamp=$(get_iso_timestamp)

    local temp_file
    temp_file=$(mktemp)

    jq --arg timestamp "$timestamp" \
       '. + {"clean_shutdown": true, "shutdown_at": $timestamp}' \
       "$SESSION_STATE_FILE" > "$temp_file"

    mv "$temp_file" "$SESSION_STATE_FILE"
}

# Detect if last session ended abnormally (crash)
# Usage: detect_crash
# Returns: 0 if crash detected, 1 if clean shutdown or no session
detect_crash() {
    if [ ! -f "$SESSION_STATE_FILE" ]; then
        return 1
    fi

    local clean_shutdown
    clean_shutdown=$(jq -r '.clean_shutdown // false' "$SESSION_STATE_FILE" 2>/dev/null)

    if [ "$clean_shutdown" = "true" ]; then
        return 1  # Clean shutdown, no crash
    else
        return 0  # No shutdown marker, assume crash
    fi
}

# Get crash recovery info for display
# Usage: get_crash_info
# Returns: JSON with crash details
get_crash_info() {
    if [ ! -f "$SESSION_STATE_FILE" ]; then
        echo "{}"
        return 1
    fi

    local last_saved
    last_saved=$(jq -r '.last_saved_at // ""' "$SESSION_STATE_FILE" 2>/dev/null)

    local current_time
    current_time=$(date -u +%s)

    local crash_time_seconds=0
    if [ -n "$last_saved" ]; then
        # Convert ISO 8601 to Unix timestamp
        local last_saved_seconds
        last_saved_seconds=$(date -j -f "%Y-%m-%dT%H:%M:%SZ" "$last_saved" +%s 2>/dev/null) || last_saved_seconds=0
        crash_time_seconds=$((current_time - last_saved_seconds))
    fi

    # Convert seconds to human-readable duration
    local hours=$((crash_time_seconds / 3600))
    local minutes=$(((crash_time_seconds % 3600) / 60))
    local time_since_crash
    if [ $hours -gt 0 ]; then
        time_since_crash="${hours}h ${minutes}m"
    elif [ $minutes -gt 0 ]; then
        time_since_crash="${minutes}m"
    else
        time_since_crash="<1m"
    fi

    jq -n \
        --arg time_since "$time_since_crash" \
        --argjson session "$(cat "$SESSION_STATE_FILE")" \
        '{
            time_since_crash: $time_since,
            session_id: $session.session_id,
            project: $session.project,
            current_story: $session.current_story,
            current_iteration: $session.current_iteration,
            stories_completed: $session.stories_completed,
            stories_total: $session.stories_total,
            last_saved_at: $session.last_saved_at
        }'
}

# Display recovery message with crash details
# Usage: display_recovery_message
display_recovery_message() {
    local crash_info
    crash_info=$(get_crash_info)

    local time_since
    time_since=$(echo "$crash_info" | jq -r '.time_since_crash')
    local project
    project=$(echo "$crash_info" | jq -r '.project')
    local story
    story=$(echo "$crash_info" | jq -r '.current_story')
    local iteration
    iteration=$(echo "$crash_info" | jq -r '.current_iteration')
    local completed
    completed=$(echo "$crash_info" | jq -r '.stories_completed')
    local total
    total=$(echo "$crash_info" | jq -r '.stories_total')

    echo ""
    echo -e "${SESSION_YELLOW}╔════════════════════════════════════════════════════════════════╗${SESSION_NC}"
    echo -e "${SESSION_YELLOW}║                    CRASH RECOVERY DETECTED                     ║${SESSION_NC}"
    echo -e "${SESSION_YELLOW}╚════════════════════════════════════════════════════════════════╝${SESSION_NC}"
    echo ""
    echo -e "${SESSION_CYAN}The previous session ended unexpectedly.${SESSION_NC}"
    echo ""
    echo "  Time since crash:    $time_since ago"
    echo "  Project:             $project"
    echo "  Current story:       $story (iteration $iteration)"
    echo "  Progress:            $completed/$total stories completed"
    echo ""
    echo "Recovery options:"
    echo "  [r] Resume from checkpoint - Continue from last saved state"
    echo "  [f] Fresh start - Clear session and start over"
    echo ""
}

# Prompt user for recovery confirmation
# Usage: prompt_recovery_confirmation
# Returns: 0 for resume, 1 for fresh start
prompt_recovery_confirmation() {
    local choice
    while true; do
        read -p "Choose recovery option [r/f]: " choice
        case "$choice" in
            r|R|resume)
                return 0
                ;;
            f|F|fresh)
                return 1
                ;;
            *)
                echo "Invalid choice. Please enter 'r' for resume or 'f' for fresh start."
                ;;
        esac
    done
}

# Log recovery metrics
# Usage: log_recovery_metrics <iterations_recovered> <time_lost_seconds>
log_recovery_metrics() {
    local iterations_recovered="$1"
    local time_lost_seconds="$2"

    if [ ! -f "$SESSION_STATE_FILE" ]; then
        return 0
    fi

    local timestamp
    timestamp=$(get_iso_timestamp)

    local temp_file
    temp_file=$(mktemp)

    # Convert time lost to hours for readability
    local hours_lost
    hours_lost=$(echo "scale=2; $time_lost_seconds / 3600" | bc)

    jq --arg timestamp "$timestamp" \
       --argjson iterations "$iterations_recovered" \
       --arg hours_lost "$hours_lost" \
       '. + {
           "recovery_metrics": {
               "recovered_at": $timestamp,
               "iterations_recovered": $iterations,
               "hours_lost": $hours_lost
           }
       }' \
       "$SESSION_STATE_FILE" > "$temp_file"

    mv "$temp_file" "$SESSION_STATE_FILE"

    session_log "Recovery metrics logged: $iterations_recovered iterations, ~${hours_lost}h lost"
}

# ============================================================================
# Checkpoint Functions (for iteration-level auto-save)
# ============================================================================

# Save checkpoint after each iteration
# Usage: save_checkpoint <story_id> <iteration> <prd_state_json>
# prd_state_json: JSON string containing current PRD state
# Returns: 0 on success, 1 on failure
save_checkpoint() {
    local story_id="$1"
    local iteration="$2"
    local prd_state="${3:-{}}"

    if [ ! -f "$SESSION_STATE_FILE" ]; then
        session_warn "No active session for checkpoint"
        return 1
    fi

    # Get session ID
    local session_id
    session_id=$(jq -r '.session_id // ""' "$SESSION_STATE_FILE" 2>/dev/null) || session_id=""
    if [ -z "$session_id" ]; then
        session_warn "No session ID found"
        return 1
    fi

    # Create checkpoint directory for this session
    local checkpoint_dir="${SESSION_CHECKPOINT_DIR}/${session_id}"
    mkdir -p "$checkpoint_dir"

    # Generate checkpoint filename with timestamp
    local timestamp
    timestamp=$(date +%Y%m%d_%H%M%S_%N)
    local checkpoint_file="${checkpoint_dir}/checkpoint_${iteration}_${timestamp}.json"
    local temp_file="${checkpoint_file}.tmp"

    # Build checkpoint data
    local iso_timestamp
    iso_timestamp=$(get_iso_timestamp)

    # Validate that prd_state is valid JSON
    if ! echo "$prd_state" | jq empty 2>/dev/null; then
        session_warn "Invalid PRD state JSON provided to checkpoint"
        # Use empty object as fallback
        prd_state="{}"
    fi

    # Create checkpoint JSON using jq for proper escaping (write to temp file first for atomicity)
    if ! jq -n \
        --arg session_id "$session_id" \
        --arg story_id "$story_id" \
        --argjson iteration "$iteration" \
        --arg timestamp "$iso_timestamp" \
        --argjson prd_state "$prd_state" \
        '{
            session_id: $session_id,
            story_id: $story_id,
            iteration: $iteration,
            timestamp: $timestamp,
            prd_state: $prd_state,
            checkpoint_version: "1.0"
        }' > "$temp_file" 2>&1; then
        session_warn "Failed to create checkpoint JSON"
        rm -f "$temp_file" 2>/dev/null || true
        return 1
    fi

    if [ ! -s "$temp_file" ]; then
        session_warn "Checkpoint file is empty"
        rm -f "$temp_file" 2>/dev/null || true
        return 1
    fi

    # Atomic rename to final checkpoint file
    if ! mv "$temp_file" "$checkpoint_file"; then
        session_warn "Failed to save checkpoint atomically"
        rm -f "$temp_file" 2>/dev/null || true
        return 1
    fi

    # Clean up old checkpoints (keep only last N)
    cleanup_old_checkpoints "$checkpoint_dir"

    session_log "Checkpoint saved: iteration $iteration"
    return 0
}

# Clean up old checkpoints, keeping only the last N
# Usage: cleanup_old_checkpoints <checkpoint_dir>
cleanup_old_checkpoints() {
    local checkpoint_dir="$1"

    if [ ! -d "$checkpoint_dir" ]; then
        return 0
    fi

    # Count checkpoints
    local count
    count=$(ls -1 "$checkpoint_dir"/checkpoint_*.json 2>/dev/null | wc -l | tr -d ' ')

    if [ "$count" -le "$MAX_CHECKPOINTS" ]; then
        return 0
    fi

    # Remove oldest checkpoints (sorted by modification time)
    local to_remove=$((count - MAX_CHECKPOINTS))
    ls -1t "$checkpoint_dir"/checkpoint_*.json 2>/dev/null | tail -n "$to_remove" | while read -r old_checkpoint; do
        rm -f "$old_checkpoint"
    done
}

# Validate checkpoint file (US-002)
# Usage: validate_checkpoint <checkpoint_file>
# Returns: 0 if valid, 1 if invalid
# Checks: JSON schema, required fields, file integrity
validate_checkpoint() {
    local checkpoint_file="$1"

    if [ ! -f "$checkpoint_file" ]; then
        session_warn "Checkpoint file not found: $checkpoint_file"
        return 1
    fi

    # AC2: Check if file is valid JSON
    if ! jq empty "$checkpoint_file" 2>/dev/null; then
        session_warn "Checkpoint file is not valid JSON: $checkpoint_file"
        return 1
    fi

    # AC2: Check required fields
    local required_fields=("session_id" "story_id" "iteration" "timestamp" "prd_state" "checkpoint_version")
    for field in "${required_fields[@]}"; do
        if ! jq -e "has(\"$field\")" "$checkpoint_file" >/dev/null 2>&1; then
            session_warn "Checkpoint missing required field '$field': $checkpoint_file"
            return 1
        fi
    done

    # AC2: Verify checkpoint_version is supported
    local version
    version=$(jq -r '.checkpoint_version // ""' "$checkpoint_file" 2>/dev/null)
    if [ "$version" != "1.0" ]; then
        session_warn "Unsupported checkpoint version '$version': $checkpoint_file"
        return 1
    fi

    # AC2: Verify iteration is a positive integer
    local iteration
    iteration=$(jq -r '.iteration // ""' "$checkpoint_file" 2>/dev/null)
    if ! [[ "$iteration" =~ ^[0-9]+$ ]]; then
        session_warn "Invalid iteration value '$iteration': $checkpoint_file"
        return 1
    fi

    # AC2: Verify timestamp is in ISO 8601 format
    local timestamp
    timestamp=$(jq -r '.timestamp // ""' "$checkpoint_file" 2>/dev/null)
    if ! [[ "$timestamp" =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z$ ]]; then
        session_warn "Invalid timestamp format '$timestamp': $checkpoint_file"
        return 1
    fi

    # All checks passed
    return 0
}

# Get the latest checkpoint for current session
# Usage: get_latest_checkpoint
# Returns: path to latest checkpoint file, or empty string if none exists
get_latest_checkpoint() {
    if [ ! -f "$SESSION_STATE_FILE" ]; then
        echo ""
        return 1
    fi

    local session_id
    session_id=$(jq -r '.session_id // ""' "$SESSION_STATE_FILE" 2>/dev/null) || session_id=""
    if [ -z "$session_id" ]; then
        echo ""
        return 1
    fi

    local checkpoint_dir="${SESSION_CHECKPOINT_DIR}/${session_id}"
    if [ ! -d "$checkpoint_dir" ]; then
        echo ""
        return 1
    fi

    # Get most recent checkpoint
    local latest
    latest=$(ls -1t "$checkpoint_dir"/checkpoint_*.json 2>/dev/null | head -1)
    echo "$latest"
}

# List all available checkpoints for current session
# Usage: list_checkpoints [format]
# format: text (default) or json
list_checkpoints() {
    local format="${1:-text}"

    if [ ! -f "$SESSION_STATE_FILE" ]; then
        if [ "$format" = "json" ]; then
            echo "[]"
        else
            echo "No active session"
        fi
        return 1
    fi

    local session_id
    session_id=$(jq -r '.session_id // ""' "$SESSION_STATE_FILE" 2>/dev/null) || session_id=""
    if [ -z "$session_id" ]; then
        if [ "$format" = "json" ]; then
            echo "[]"
        else
            echo "No session ID found"
        fi
        return 1
    fi

    local checkpoint_dir="${SESSION_CHECKPOINT_DIR}/${session_id}"
    if [ ! -d "$checkpoint_dir" ]; then
        if [ "$format" = "json" ]; then
            echo "[]"
        else
            echo "No checkpoints found"
        fi
        return 0
    fi

    local checkpoints=()
    for checkpoint_file in "$checkpoint_dir"/checkpoint_*.json; do
        if [ -f "$checkpoint_file" ]; then
            if [ "$format" = "json" ]; then
                checkpoints+=("$(cat "$checkpoint_file")")
            else
                local story_id iteration timestamp
                story_id=$(jq -r '.story_id // "unknown"' "$checkpoint_file" 2>/dev/null) || story_id="unknown"
                iteration=$(jq -r '.iteration // 0' "$checkpoint_file" 2>/dev/null) || iteration=0
                timestamp=$(jq -r '.timestamp // "unknown"' "$checkpoint_file" 2>/dev/null) || timestamp="unknown"
                checkpoints+=("Iteration $iteration - Story $story_id - $timestamp")
            fi
        fi
    done

    if [ ${#checkpoints[@]} -eq 0 ]; then
        if [ "$format" = "json" ]; then
            echo "[]"
        else
            echo "No checkpoints found"
        fi
        return 0
    fi

    if [ "$format" = "json" ]; then
        printf '%s\n' "${checkpoints[@]}" | jq -s '.'
    else
        echo "Available checkpoints (newest first):"
        echo ""
        printf '%s\n' "${checkpoints[@]}"
    fi
}

# Restore from latest checkpoint (with validation and fallback - US-002)
# Usage: restore_from_checkpoint
# Returns: JSON with restored checkpoint data
# AC3: Falls back to previous checkpoint if current is corrupted
restore_from_checkpoint() {
    if [ ! -f "$SESSION_STATE_FILE" ]; then
        session_warn "No active session"
        return 1
    fi

    local session_id
    session_id=$(jq -r '.session_id // ""' "$SESSION_STATE_FILE" 2>/dev/null) || session_id=""
    if [ -z "$session_id" ]; then
        session_warn "No session ID found"
        return 1
    fi

    local checkpoint_dir="${SESSION_CHECKPOINT_DIR}/${session_id}"
    if [ ! -d "$checkpoint_dir" ]; then
        session_warn "No checkpoints available for recovery"
        return 1
    fi

    # AC3: Get all checkpoints sorted by modification time (newest first)
    local checkpoints
    checkpoints=$(ls -1t "$checkpoint_dir"/checkpoint_*.json 2>/dev/null || echo "")

    if [ -z "$checkpoints" ]; then
        session_warn "No checkpoint available for recovery"
        return 1
    fi

    # AC3: Try each checkpoint until we find a valid one (fallback mechanism)
    local checkpoint_found=false
    local checkpoint_file=""

    while IFS= read -r cp_file; do
        if [ ! -f "$cp_file" ]; then
            continue
        fi

        # AC1,AC2: Validate checkpoint before loading
        if validate_checkpoint "$cp_file"; then
            checkpoint_file="$cp_file"
            checkpoint_found=true
            break
        else
            # AC4: Log validation errors with details
            session_warn "Checkpoint validation failed, trying previous checkpoint"
        fi
    done <<< "$checkpoints"

    if ! $checkpoint_found; then
        session_warn "No valid checkpoints found for recovery"
        return 1
    fi

    session_log "Restoring from checkpoint: $(basename "$checkpoint_file")"

    # Return checkpoint data
    cat "$checkpoint_file"
}

# Restore from specific checkpoint by iteration number (with validation - US-002)
# Usage: restore_from_checkpoint_iteration <iteration>
# Returns: JSON with restored checkpoint data
restore_from_checkpoint_iteration() {
    local target_iteration="$1"

    if [ ! -f "$SESSION_STATE_FILE" ]; then
        session_warn "No active session"
        return 1
    fi

    local session_id
    session_id=$(jq -r '.session_id // ""' "$SESSION_STATE_FILE" 2>/dev/null) || session_id=""
    if [ -z "$session_id" ]; then
        session_warn "No session ID found"
        return 1
    fi

    local checkpoint_dir="${SESSION_CHECKPOINT_DIR}/${session_id}"
    if [ ! -d "$checkpoint_dir" ]; then
        session_warn "No checkpoints found"
        return 1
    fi

    # Find checkpoint with matching iteration
    local target_checkpoint=""
    for checkpoint_file in "$checkpoint_dir"/checkpoint_*.json; do
        if [ -f "$checkpoint_file" ]; then
            local iteration
            iteration=$(jq -r '.iteration // 0' "$checkpoint_file" 2>/dev/null) || iteration=0
            if [ "$iteration" -eq "$target_iteration" ]; then
                # US-002 AC1,AC2: Validate before using
                if validate_checkpoint "$checkpoint_file"; then
                    target_checkpoint="$checkpoint_file"
                    break
                else
                    # US-002 AC4: Log validation errors
                    session_warn "Checkpoint for iteration $target_iteration failed validation"
                    return 1
                fi
            fi
        fi
    done

    if [ -z "$target_checkpoint" ]; then
        session_warn "No valid checkpoint found for iteration $target_iteration"
        return 1
    fi

    session_log "Restoring from checkpoint: iteration $target_iteration"

    # Return checkpoint data
    cat "$target_checkpoint"
}

# ============================================================================
# Crash Recovery Functions (US-003)
# ============================================================================

# Handle crash recovery with user confirmation
# Usage: handle_crash_recovery <prd_file>
# Returns: 0 if recovery successful or user chose to start fresh, 1 on error
# US-003 AC1,AC2,AC3: Detect crash, display recovery message, ask for confirmation
handle_crash_recovery() {
    local prd_file="$1"

    if [ ! -f "$SESSION_STATE_FILE" ]; then
        return 0  # No session to recover
    fi

    # US-003 AC1: Check clean_shutdown marker
    local clean_shutdown
    clean_shutdown=$(jq -r '.clean_shutdown // false' "$SESSION_STATE_FILE" 2>/dev/null) || clean_shutdown="false"

    if [ "$clean_shutdown" = "true" ]; then
        return 0  # Clean shutdown, no recovery needed
    fi

    # US-003 AC2: Calculate time since crash
    local last_saved_at started_at
    last_saved_at=$(jq -r '.last_saved_at // ""' "$SESSION_STATE_FILE" 2>/dev/null) || last_saved_at=""
    started_at=$(jq -r '.started_at // ""' "$SESSION_STATE_FILE" 2>/dev/null) || started_at=""

    local time_since_crash="unknown"
    if [ -n "$last_saved_at" ]; then
        # Calculate time difference (simplified - shows last saved time)
        time_since_crash="$last_saved_at"
    fi

    # US-003 AC2: Get progress info
    local completed_stories total_stories current_story current_iteration
    completed_stories=$(jq -r '.stories_completed // 0' "$SESSION_STATE_FILE" 2>/dev/null) || completed_stories=0
    total_stories=$(jq -r '.stories_total // 0' "$SESSION_STATE_FILE" 2>/dev/null) || total_stories=0
    current_story=$(jq -r '.current_story // "unknown"' "$SESSION_STATE_FILE" 2>/dev/null) || current_story="unknown"
    current_iteration=$(jq -r '.current_iteration // 0' "$SESSION_STATE_FILE" 2>/dev/null) || current_iteration=0

    # Count stories to retry (incomplete stories)
    local stories_to_retry=$((total_stories - completed_stories))

    # US-003 AC2: Display recovery message
    echo ""
    echo -e "${SESSION_YELLOW}╔═══════════════════════════════════════════════════════════════╗${SESSION_NC}"
    echo -e "${SESSION_YELLOW}║              🔄 CRASH RECOVERY DETECTED 🔄                    ║${SESSION_NC}"
    echo -e "${SESSION_YELLOW}╚═══════════════════════════════════════════════════════════════╝${SESSION_NC}"
    echo ""
    echo "The previous session ended abnormally."
    echo ""
    echo "Recovery Information:"
    echo "  • Last saved:         $time_since_crash"
    echo "  • Session started:    $started_at"
    echo "  • Progress:           $completed_stories/$total_stories stories complete"
    echo "  • Current story:      $current_story (iteration $current_iteration)"
    echo "  • Stories to retry:   $stories_to_retry"
    echo ""

    # Check for available checkpoints
    local session_id
    session_id=$(jq -r '.session_id // ""' "$SESSION_STATE_FILE" 2>/dev/null) || session_id=""

    if [ -n "$session_id" ]; then
        local checkpoint_dir="${SESSION_CHECKPOINT_DIR}/${session_id}"
        if [ -d "$checkpoint_dir" ]; then
            local checkpoint_count
            checkpoint_count=$(ls -1 "$checkpoint_dir"/checkpoint_*.json 2>/dev/null | wc -l | tr -d ' ')
            if [ "$checkpoint_count" -gt 0 ]; then
                echo "  • Checkpoints found:  $checkpoint_count (last $MAX_CHECKPOINTS iterations)"
                echo ""
            fi
        fi
    fi

    # US-003 AC3: Ask user for confirmation
    echo "Options:"
    echo "  1) Resume from last checkpoint (recommended)"
    echo "  2) Start fresh (discard progress)"
    echo "  3) View checkpoints first"
    echo ""
    read -p "What would you like to do? [1/2/3]: " choice

    case "$choice" in
        1)
            # Resume from checkpoint
            echo ""
            session_log "Resuming from last checkpoint..."

            # US-003 AC4: Log recovery metrics
            log_recovery_metrics "$completed_stories" "$total_stories" "$current_iteration"

            # Mark session as recovered
            mark_clean_shutdown

            session_success "Recovery successful! Continuing from iteration $current_iteration"
            return 0
            ;;
        2)
            # Start fresh
            echo ""
            session_log "Starting fresh..."

            # Archive old session
            archive_session "abandoned-after-crash"

            # Clear session file to allow new init
            rm -f "$SESSION_STATE_FILE"

            session_log "Previous session archived. Starting new session..."
            return 0
            ;;
        3)
            # View checkpoints
            echo ""
            echo "Available checkpoints:"
            list_checkpoints
            echo ""
            # Recursively ask again
            handle_crash_recovery "$prd_file"
            return $?
            ;;
        *)
            session_warn "Invalid choice. Please try again."
            handle_crash_recovery "$prd_file"
            return $?
            ;;
    esac
}

# Log recovery metrics to execution logger
# Usage: log_recovery_metrics <completed_stories> <total_stories> <iterations_recovered>
# US-003 AC4: Log recovery metrics
log_recovery_metrics() {
    local completed_stories="$1"
    local total_stories="$2"
    local iterations_recovered="$3"

    if [ -f "$SESSION_STATE_DIR/../lib/execution-logger.sh" ]; then
        # Log to execution logger if available
        local timestamp
        timestamp=$(get_iso_timestamp)

        # Create recovery log entry
        cat >> "${SESSION_STATE_DIR}/recovery.log" << EOF
{"timestamp": "$timestamp", "completed_stories": $completed_stories, "total_stories": $total_stories, "iterations_recovered": $iterations_recovered, "event": "crash_recovery"}
EOF
    fi

    session_log "Recovery metrics logged: $completed_stories/$total_stories stories, $iterations_recovered iterations recovered"
}

# Mark session as having clean shutdown
# Usage: mark_clean_shutdown
mark_clean_shutdown() {
    if [ ! -f "$SESSION_STATE_FILE" ]; then
        return 0
    fi

    local temp_file
    temp_file=$(mktemp) || return 1

    trap "rm -f '$temp_file'" RETURN

    jq '.clean_shutdown = true' "$SESSION_STATE_FILE" > "$temp_file" 2>/dev/null || return 1
    mv "$temp_file" "$SESSION_STATE_FILE" || return 1

    return 0
}

# Mark session as having unclean shutdown (call before any potentially crashing operation)
# Usage: mark_unclean_shutdown
mark_unclean_shutdown() {
    if [ ! -f "$SESSION_STATE_FILE" ]; then
        return 0
    fi

    local temp_file
    temp_file=$(mktemp) || return 1

    trap "rm -f '$temp_file'" RETURN

    jq '.clean_shutdown = false' "$SESSION_STATE_FILE" > "$temp_file" 2>/dev/null || return 1
    mv "$temp_file" "$SESSION_STATE_FILE" || return 1

    return 0
}

# ============================================================================
# CLI Mode (for direct execution)
# ============================================================================

if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    case "${1:-help}" in
        init)
            if [ -z "${2:-}" ]; then
                echo "Usage: $0 init <prd_file>"
                exit 1
            fi
            init_session "$2" "${3:-}" "${4:-}"
            ;;
        save)
            if [ -z "${2:-}" ] || [ -z "${3:-}" ]; then
                echo "Usage: $0 save <story_id> <iteration> [phase]"
                exit 1
            fi
            save_session_state "$2" "$3" "${4:-implementation}"
            ;;
        checkpoint)
            if [ -z "${2:-}" ] || [ -z "${3:-}" ]; then
                echo "Usage: $0 checkpoint <story_id> <iteration> [prd_state_json]"
                exit 1
            fi
            save_checkpoint "$2" "$3" "${4:-{}}"
            ;;
        list-checkpoints)
            list_checkpoints "${2:-text}"
            ;;
        restore-checkpoint)
            restore_from_checkpoint
            ;;
        restore-checkpoint-iteration)
            if [ -z "${2:-}" ]; then
                echo "Usage: $0 restore-checkpoint-iteration <iteration>"
                exit 1
            fi
            restore_from_checkpoint_iteration "$2"
            ;;
        resume)
            resume_session "true"
            ;;
        resume-id)
            if [ -z "${2:-}" ]; then
                echo "Usage: $0 resume-id <session_id>"
                exit 1
            fi
            resume_session_by_id "$2"
            ;;
        summary)
            get_session_summary
            ;;
        list)
            list_sessions "${2:-text}"
            ;;
        has-resumable)
            if has_resumable_session "${2:-}"; then
                echo "true"
                exit 0
            else
                echo "false"
                exit 1
            fi
            ;;
        archive)
            archive_session "${2:-manual}"
            ;;
        clear)
            clear_session
            ;;
        complete)
            complete_session
            ;;
        help|*)
            cat << EOF
session-state.sh - Session State Management for claude-loop

Usage: $0 <command> [args]

Commands:
  init <prd_file>                     Initialize new session
  save <story_id> <iter> [phase]      Save session state
  checkpoint <story_id> <iter> [prd]  Save checkpoint (after iteration)
  list-checkpoints [text|json]        List available checkpoints
  restore-checkpoint                  Restore from latest checkpoint
  restore-checkpoint-iteration <iter> Restore from specific iteration
  resume                              Resume current session
  resume-id <session_id>              Resume specific session
  summary                             Show session summary
  list [text|json]                    List all sessions
  has-resumable [prd_file]            Check if resumable session exists
  archive [reason]                    Archive current session
  clear                               Clear current session
  complete                            Mark session as complete
  help                                Show this help

Examples:
  $0 init prd.json
  $0 save INV-007 3 implementation
  $0 checkpoint INV-007 5 '{"userStories": [...]}'
  $0 list-checkpoints
  $0 restore-checkpoint
  $0 resume
  $0 list json
EOF
            ;;
    esac
fi
