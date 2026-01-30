#!/usr/bin/env bash
# Progress event emission helpers for bash scripts
# Source this file in coordinator/worker to emit real-time progress events
#
# Usage:
#   source lib/emit_progress.sh
#   emit_story_started "PRD-001" "US-001"
#   emit_test_run "PRD-001" "US-001" 10 2
#   emit_story_completed "PRD-001" "US-001" true

# Check if Python is available
if ! command -v python3 &> /dev/null; then
    # Silently disable if Python not available
    emit_story_started() { :; }
    emit_story_completed() { :; }
    emit_test_run() { :; }
    emit_commit_created() { :; }
    emit_error() { :; }
    emit_prd_started() { :; }
    emit_prd_completed() { :; }
    emit_log_message() { :; }
    return 0
fi

# Get script directory
EMIT_SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Python helper script location
PYTHON_EMITTER="${EMIT_SCRIPT_DIR}/emit_progress_helper.py"

# Create Python helper if it doesn't exist
if [[ ! -f "$PYTHON_EMITTER" ]]; then
    cat > "$PYTHON_EMITTER" << 'PYTHON_EOF'
#!/usr/bin/env python3
"""Helper script for emitting progress events from bash"""
import sys
import os

# Add lib directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from progress_streamer import (
        emit_story_started,
        emit_story_completed,
        emit_test_run,
        emit_commit_created,
        emit_error
    )
    HAS_DEPS = True
except ImportError:
    HAS_DEPS = False

def main():
    if not HAS_DEPS:
        # Silently exit if dependencies not available
        sys.exit(0)

    if len(sys.argv) < 2:
        sys.exit(1)

    event_type = sys.argv[1]

    try:
        if event_type == "story_started":
            prd_id = sys.argv[2]
            story_id = sys.argv[3]
            emit_story_started(prd_id, story_id)

        elif event_type == "story_completed":
            prd_id = sys.argv[2]
            story_id = sys.argv[3]
            success = sys.argv[4].lower() == "true"
            emit_story_completed(prd_id, story_id, success=success)

        elif event_type == "test_run":
            prd_id = sys.argv[2]
            story_id = sys.argv[3]
            passed = int(sys.argv[4])
            failed = int(sys.argv[5])
            emit_test_run(prd_id, story_id, passed, failed)

        elif event_type == "commit_created":
            prd_id = sys.argv[2]
            story_id = sys.argv[3]
            commit_hash = sys.argv[4]
            emit_commit_created(prd_id, story_id, commit_hash)

        elif event_type == "error":
            prd_id = sys.argv[2]
            story_id = sys.argv[3]
            error = sys.argv[4]
            emit_error(prd_id, story_id, error)

    except Exception:
        # Silently fail to avoid breaking calling scripts
        pass

if __name__ == "__main__":
    main()
PYTHON_EOF
    chmod +x "$PYTHON_EMITTER"
fi

# Bash wrapper functions

emit_story_started() {
    local prd_id="$1"
    local story_id="$2"
    python3 "$PYTHON_EMITTER" story_started "$prd_id" "$story_id" 2>/dev/null || true
}

emit_story_completed() {
    local prd_id="$1"
    local story_id="$2"
    local success="${3:-true}"
    python3 "$PYTHON_EMITTER" story_completed "$prd_id" "$story_id" "$success" 2>/dev/null || true
}

emit_test_run() {
    local prd_id="$1"
    local story_id="$2"
    local passed="$3"
    local failed="$4"
    python3 "$PYTHON_EMITTER" test_run "$prd_id" "$story_id" "$passed" "$failed" 2>/dev/null || true
}

emit_commit_created() {
    local prd_id="$1"
    local story_id="$2"
    local commit_hash="$3"
    python3 "$PYTHON_EMITTER" commit_created "$prd_id" "$story_id" "$commit_hash" 2>/dev/null || true
}

emit_error() {
    local prd_id="$1"
    local story_id="$2"
    local error="$3"
    python3 "$PYTHON_EMITTER" error "$prd_id" "$story_id" "$error" 2>/dev/null || true
}

emit_prd_started() {
    local prd_id="$1"
    # Emit as story_started with special story_id
    emit_story_started "$prd_id" "PRD_START"
}

emit_prd_completed() {
    local prd_id="$1"
    local success="${2:-true}"
    # Emit as story_completed with special story_id
    emit_story_completed "$prd_id" "PRD_COMPLETE" "$success"
}

emit_log_message() {
    local prd_id="$1"
    local story_id="$2"
    local level="$3"
    local message="$4"
    # Log messages can be added later if needed
    :
}

# Export functions
export -f emit_story_started
export -f emit_story_completed
export -f emit_test_run
export -f emit_commit_created
export -f emit_error
export -f emit_prd_started
export -f emit_prd_completed
export -f emit_log_message
