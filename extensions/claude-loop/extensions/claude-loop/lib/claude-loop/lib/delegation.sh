#!/bin/bash
#
# delegation.sh - Bounded Delegation Executor
#
# Orchestrates hierarchical task delegation with strict safety bounds.
# Creates subordinate worktrees, executes child tasks, and integrates results.
#
# Usage:
#   source lib/delegation.sh
#   execute_delegation "$delegation_json" "$parent_story_id"
#
# Safety Limits:
#   - MAX_DELEGATION_DEPTH=2 (configurable, hard max=3)
#   - MAX_CONTEXT_PER_AGENT=100k tokens
#   - MAX_DELEGATIONS_PER_STORY=10
#   - Cycle detection prevents infinite loops

set -euo pipefail

# ============================================================================
# Configuration
# ============================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Source dependencies
source "$SCRIPT_DIR/delegation-parser.sh"
source "$SCRIPT_DIR/delegation-tracker.sh"

# Delegation settings
MAX_DELEGATION_DEPTH="${MAX_DELEGATION_DEPTH:-2}"
MAX_CONTEXT_PER_AGENT="${MAX_CONTEXT_PER_AGENT:-100000}"
MAX_DELEGATIONS_PER_STORY="${MAX_DELEGATIONS_PER_STORY:-10}"

# Worker settings
WORKER_SCRIPT="$SCRIPT_DIR/worker.sh"
WORKER_BASE_DIR=".claude-loop/workers"

# ============================================================================
# Context Budget Management
# ============================================================================

#
# Calculate context budget for delegation
#
# Arguments:
#   $1 - parent_context_tokens: Tokens used by parent
#   $2 - child_estimate_tokens: Estimated tokens for child
#
# Returns: 0 if within budget, 1 if would exceed
#
check_context_budget() {
    local parent_context_tokens="$1"
    local child_estimate_tokens="$2"

    local remaining=$((MAX_CONTEXT_PER_AGENT - parent_context_tokens))

    if (( child_estimate_tokens > remaining )); then
        echo "ERROR: Agent context budget ($MAX_CONTEXT_PER_AGENT tokens) exceeded. Simplify subtask." >&2
        echo "" >&2
        echo "Current context: $parent_context_tokens tokens" >&2
        echo "Subtask estimate: $child_estimate_tokens tokens" >&2
        echo "Total would be: $((parent_context_tokens + child_estimate_tokens)) tokens" >&2
        echo "Maximum allowed: $MAX_CONTEXT_PER_AGENT tokens" >&2
        echo "" >&2
        echo "Suggestion: Break subtask into smaller pieces or reduce parent context." >&2
        return 1
    fi

    echo "Context budget OK: $remaining tokens remaining" >&2
    return 0
}

#
# Estimate tokens for delegation
#
# Very rough estimate based on description length.
# In production, use actual token counting.
#
# Arguments:
#   $1 - description: Task description
#
# Output: Estimated tokens (integer)
#
estimate_delegation_tokens() {
    local description="$1"

    # Rough estimate: 4 characters per token
    local char_count=${#description}
    local estimated_tokens=$((char_count / 4))

    # Add base overhead for delegation (prompt, context, etc.)
    local delegation_overhead=5000

    echo $((estimated_tokens + delegation_overhead))
}

# ============================================================================
# Delegation Execution
# ============================================================================

#
# Execute a single delegation
#
# Arguments:
#   $1 - delegation_json: JSON object with delegation details
#   $2 - parent_story_id: Parent story ID
#   $3 - parent_execution_id: Parent execution ID
#   $4 - parent_context_tokens: Current parent context size
#
# Returns: 0 on success, 1 on failure
#
execute_single_delegation() {
    local delegation_json="$1"
    local parent_story_id="$2"
    local parent_execution_id="$3"
    local parent_context_tokens="$4"

    # Extract delegation details
    local description
    local estimated_hours
    local child_story_id
    local depth

    description=$(echo "$delegation_json" | jq -r '.description')
    estimated_hours=$(echo "$delegation_json" | jq -r '.estimated_hours')
    child_story_id=$(echo "$delegation_json" | jq -r '.child_story_id')
    depth=$(echo "$delegation_json" | jq -r '.depth')

    echo "=== Delegation: $child_story_id ===" >&2
    echo "Description: $description" >&2
    echo "Estimated hours: $estimated_hours" >&2
    echo "Depth: $depth" >&2

    # Generate child execution ID
    local child_execution_id
    child_execution_id="exec-$(date +%s)-$$-$RANDOM"

    # Validation: Check depth limit
    if ! check_delegation_depth "$parent_execution_id" "$child_execution_id"; then
        return 1
    fi

    # Validation: Check cycle
    if ! detect_delegation_cycle "$parent_execution_id" "$child_execution_id"; then
        return 1
    fi

    # Validation: Check context budget
    local child_estimate_tokens
    child_estimate_tokens=$(estimate_delegation_tokens "$description")

    if ! check_context_budget "$parent_context_tokens" "$child_estimate_tokens"; then
        return 1
    fi

    # Add execution edge (for cycle detection)
    add_execution_edge "$parent_execution_id" "$child_execution_id"

    # Log delegation start
    log_delegation "started" "$parent_story_id" "$child_story_id" "$depth" \
        "$parent_execution_id" "$child_execution_id" \
        "description=$description" \
        "estimated_hours=$estimated_hours"

    # Create child worktree
    local worktree_path
    worktree_path=$(create_delegation_worktree "$child_story_id")

    if [[ $? -ne 0 ]]; then
        log_delegation "failed" "$parent_story_id" "$child_story_id" "$depth" \
            "$parent_execution_id" "$child_execution_id" \
            "error=Failed to create worktree"
        return 1
    fi

    log_delegation "started" "$parent_story_id" "$child_story_id" "$depth" \
        "$parent_execution_id" "$child_execution_id" \
        "worktree_path=$worktree_path"

    # Execute child task
    local start_time
    start_time=$(date +%s)

    local result
    result=$(execute_child_task "$child_story_id" "$description" "$depth" "$worktree_path")
    local exit_code=$?

    local end_time
    end_time=$(date +%s)
    local duration_ms=$(((end_time - start_time) * 1000))

    # Parse result
    local success
    local tokens_in
    local tokens_out
    local cost_usd
    local files_changed

    if [[ $exit_code -eq 0 ]]; then
        success="true"
        tokens_in=$(echo "$result" | jq -r '.tokens_in // 0')
        tokens_out=$(echo "$result" | jq -r '.tokens_out // 0')
        cost_usd=$(echo "$result" | jq -r '.cost_usd // 0')
        files_changed=$(echo "$result" | jq -r '.files_changed // []')

        # Log success
        log_delegation "completed" "$parent_story_id" "$child_story_id" "$depth" \
            "$parent_execution_id" "$child_execution_id" \
            "duration_ms=$duration_ms" \
            "tokens_in=$tokens_in" \
            "tokens_out=$tokens_out" \
            "cost_usd=$cost_usd" \
            "success=true"

        echo "✓ Delegation completed: $child_story_id ($duration_ms ms)" >&2
    else
        success="false"

        # Log failure
        log_delegation "failed" "$parent_story_id" "$child_story_id" "$depth" \
            "$parent_execution_id" "$child_execution_id" \
            "duration_ms=$duration_ms" \
            "success=false"

        echo "✗ Delegation failed: $child_story_id" >&2
    fi

    # Cleanup worktree
    cleanup_delegation_worktree "$worktree_path"

    # Return result
    echo "$result"
    return $exit_code
}

#
# Execute multiple delegations (parallel if possible)
#
# Arguments:
#   $1 - delegations_json: JSON array of delegation objects
#   $2 - parent_story_id: Parent story ID
#   $3 - parent_execution_id: Parent execution ID
#   $4 - parent_context_tokens: Current parent context size
#
# Output: JSON array of results
#
execute_delegations() {
    local delegations_json="$1"
    local parent_story_id="$2"
    local parent_execution_id="$3"
    local parent_context_tokens="$4"

    local delegation_count
    delegation_count=$(echo "$delegations_json" | jq 'length')

    echo "Executing $delegation_count delegations..." >&2

    # Check delegation limit
    if (( delegation_count > MAX_DELEGATIONS_PER_STORY )); then
        echo "ERROR: Too many delegations ($delegation_count). Maximum: $MAX_DELEGATIONS_PER_STORY" >&2
        return 1
    fi

    local results="[]"
    local failed=0

    # Execute each delegation sequentially (parallel execution would require more complex orchestration)
    for i in $(seq 0 $((delegation_count - 1))); do
        local delegation
        delegation=$(echo "$delegations_json" | jq -c ".[$i]")

        echo "" >&2
        echo "--- Delegation $((i + 1))/$delegation_count ---" >&2

        local result
        result=$(execute_single_delegation "$delegation" "$parent_story_id" \
            "$parent_execution_id" "$parent_context_tokens")

        if [[ $? -eq 0 ]]; then
            results=$(echo "$results" | jq --argjson result "$result" '. + [$result]')
        else
            failed=$((failed + 1))
        fi
    done

    if (( failed > 0 )); then
        echo "" >&2
        echo "WARNING: $failed/$delegation_count delegations failed" >&2
    fi

    echo "$results"
    return 0
}

# ============================================================================
# Worktree Management
# ============================================================================

#
# Create git worktree for delegation
#
# Arguments:
#   $1 - child_story_id: Child story ID
#
# Output: Worktree path
#
create_delegation_worktree() {
    local child_story_id="$1"

    local timestamp
    timestamp=$(date +%Y%m%d_%H%M%S)

    local worktree_name="${child_story_id}_${timestamp}"
    local worktree_path="$WORKER_BASE_DIR/$worktree_name"
    local branch_name="delegation/${child_story_id}_${timestamp}"

    mkdir -p "$WORKER_BASE_DIR"

    # Create git worktree for parallel execution
    # This provides complete isolation between parent and child
    if ! git worktree add -b "$branch_name" "$worktree_path" HEAD 2>&1; then
        echo "Error: Failed to create git worktree for $child_story_id" >&2
        return 1
    fi

    echo "$worktree_path"
}

#
# Cleanup delegation worktree
#
# Arguments:
#   $1 - worktree_path: Path to worktree
#
cleanup_delegation_worktree() {
    local worktree_path="$1"

    if [[ -d "$worktree_path" ]]; then
        # Remove git worktree properly
        git worktree remove "$worktree_path" --force 2>/dev/null || true

        # Also remove the branch (optional, but keeps repo clean)
        local branch_name
        branch_name=$(basename "$worktree_path")
        git branch -D "delegation/$branch_name" 2>/dev/null || true

        # Fallback: if worktree remove failed, manually delete directory
        if [[ -d "$worktree_path" ]]; then
            rm -rf "$worktree_path"
        fi
    fi
}

# ============================================================================
# Child Task Execution
# ============================================================================

#
# Execute child task in isolated worktree
#
# Arguments:
#   $1 - child_story_id: Child story ID
#   $2 - description: Task description
#   $3 - depth: Delegation depth
#   $4 - worktree_path: Path to worktree
#
# Output: JSON result object
#
execute_child_task() {
    local child_story_id="$1"
    local description="$2"
    local depth="$3"
    local worktree_path="$4"

    # Create a minimal PRD for the delegated subtask
    local child_prd_path="$worktree_path/prd.json"
    create_delegation_prd "$child_story_id" "$description" "$child_prd_path"

    # Execute in worktree with delegation depth set
    # Change to worktree directory and run worker
    (
        cd "$worktree_path" || exit 1

        # Set delegation depth environment variable for child
        export DELEGATION_DEPTH=$depth
        export MAX_DELEGATION_DEPTH
        export MAX_CONTEXT_PER_AGENT

        # Run worker script with JSON output
        # Worker will check DELEGATION_DEPTH and enforce limits
        "$WORKER_SCRIPT" "$child_story_id" --json --prd "$child_prd_path" 2>&1
    )
}

#
# Create minimal PRD for delegated subtask
#
# Arguments:
#   $1 - child_story_id: Child story ID
#   $2 - description: Task description
#   $3 - output_path: Path to write PRD
#
create_delegation_prd() {
    local child_story_id="$1"
    local description="$2"
    local output_path="$3"

    cat > "$output_path" <<EOF
{
  "project": "delegation-$child_story_id",
  "branchName": "delegation/$child_story_id",
  "description": "Delegated subtask",
  "userStories": [
    {
      "id": "$child_story_id",
      "title": "Delegated Task",
      "description": "$description",
      "acceptanceCriteria": [
        "Complete the delegated task as described"
      ],
      "priority": 1,
      "passes": false,
      "notes": ""
    }
  ]
}
EOF
}

# ============================================================================
# Result Summarization and Injection
# ============================================================================

#
# Summarize delegation results for parent context injection
#
# Arguments:
#   $1 - results_json: JSON array of delegation results
#
# Output: Summarized text (max 2000 tokens)
#
summarize_delegation_results() {
    local results_json="$1"

    local summary="## Delegation Results\n\n"

    local count
    count=$(echo "$results_json" | jq 'length')

    summary+="Completed $count subtasks:\n\n"

    for i in $(seq 0 $((count - 1))); do
        local result
        result=$(echo "$results_json" | jq -c ".[$i]")

        local story_id
        local success
        local files_changed

        story_id=$(echo "$result" | jq -r '.story_id')
        success=$(echo "$result" | jq -r '.success')
        files_changed=$(echo "$result" | jq -r '.files_changed | join(", ")')

        if [[ "$success" == "true" ]]; then
            summary+="✓ $story_id: Success\n"
            summary+="  Files: $files_changed\n"
        else
            summary+="✗ $story_id: Failed\n"
        fi
    done

    echo -e "$summary"
}

# ============================================================================
# CLI Interface
# ============================================================================

if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    # Script is being run directly, not sourced

    show_help() {
        cat <<EOF
Usage: $0 <command> [options]

Commands:
  execute <file> <parent_id> <exec_id> <tokens>  Execute delegations from file
  check-budget <parent_tokens> <child_tokens>    Check context budget
  help                                            Show this help message

Examples:
  $0 execute delegations.json US-007 exec-001 50000
  $0 check-budget 50000 30000
EOF
    }

    case "${1:-help}" in
        execute)
            if [[ $# -lt 5 ]]; then
                echo "ERROR: Missing arguments" >&2
                echo "Usage: $0 execute <file> <parent_id> <exec_id> <tokens>" >&2
                exit 1
            fi

            delegations=$(cat "$2")
            parent_id="$3"
            exec_id="$4"
            tokens="$5"

            execute_delegations "$delegations" "$parent_id" "$exec_id" "$tokens"
            ;;
        check-budget)
            if [[ $# -lt 3 ]]; then
                echo "ERROR: Missing arguments" >&2
                echo "Usage: $0 check-budget <parent_tokens> <child_tokens>" >&2
                exit 1
            fi
            check_context_budget "$2" "$3"
            ;;
        help|--help|-h)
            show_help
            ;;
        *)
            echo "ERROR: Unknown command: $1" >&2
            show_help >&2
            exit 1
            ;;
    esac
fi
