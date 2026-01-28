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
