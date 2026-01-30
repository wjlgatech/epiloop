#!/bin/bash
#
# delegation-tracker.sh - Delegation Hierarchy Tracking and Cycle Detection
#
# Tracks delegation hierarchy, enforces depth limits, and detects cycles
# to prevent infinite delegation loops.
#
# Usage:
#   source lib/delegation-tracker.sh
#   init_delegation_tracking
#   check_delegation_depth "$parent_id" "$child_id"
#   detect_delegation_cycle "$parent_id" "$child_id"
#
# Storage:
#   .claude-loop/delegation/execution_graph.json - Execution graph for cycle detection
#   .claude-loop/delegation/depth_tracker.json - Current depth per agent
#   .claude-loop/logs/delegation.jsonl - Delegation event log

set -euo pipefail

# ============================================================================
# Configuration
# ============================================================================

DELEGATION_DIR=".claude-loop/delegation"
EXECUTION_GRAPH_FILE="$DELEGATION_DIR/execution_graph.json"
DEPTH_TRACKER_FILE="$DELEGATION_DIR/depth_tracker.json"
DELEGATION_LOG=".claude-loop/logs/delegation.jsonl"

MAX_DELEGATION_DEPTH="${MAX_DELEGATION_DEPTH:-2}"
MAX_CONTEXT_PER_AGENT="${MAX_CONTEXT_PER_AGENT:-100000}"
MAX_DELEGATIONS_PER_STORY="${MAX_DELEGATIONS_PER_STORY:-10}"

# ============================================================================
# Initialization
# ============================================================================

#
# Initialize delegation tracking infrastructure
#
# Creates necessary directories and files if they don't exist.
#
init_delegation_tracking() {
    # Create directories
    mkdir -p "$DELEGATION_DIR"
    mkdir -p "$(dirname "$DELEGATION_LOG")"

    # Initialize execution graph if not exists
    if [[ ! -f "$EXECUTION_GRAPH_FILE" ]]; then
        echo "{}" > "$EXECUTION_GRAPH_FILE"
    fi

    # Initialize depth tracker if not exists
    if [[ ! -f "$DEPTH_TRACKER_FILE" ]]; then
        echo "{}" > "$DEPTH_TRACKER_FILE"
    fi

    # Initialize delegation log if not exists
    if [[ ! -f "$DELEGATION_LOG" ]]; then
        touch "$DELEGATION_LOG"
    fi
}

# ============================================================================
# Depth Tracking
# ============================================================================

#
# Get current delegation depth for an agent
#
# Arguments:
#   $1 - agent_id: Unique agent identifier
#
# Output: Current depth (integer, defaults to 0)
#
get_delegation_depth() {
    local agent_id="$1"

    init_delegation_tracking

    local depth
    depth=$(jq -r --arg id "$agent_id" '.[$id] // 0' "$DEPTH_TRACKER_FILE")

    echo "$depth"
}

#
# Set delegation depth for an agent
#
# Arguments:
#   $1 - agent_id: Unique agent identifier
#   $2 - depth: Delegation depth (integer)
#
set_delegation_depth() {
    local agent_id="$1"
    local depth="$2"

    init_delegation_tracking

    # Update depth tracker
    local tmp_file
    tmp_file=$(mktemp)

    jq --arg id "$agent_id" --argjson depth "$depth" \
        '.[$id] = $depth' \
        "$DEPTH_TRACKER_FILE" > "$tmp_file"

    mv "$tmp_file" "$DEPTH_TRACKER_FILE"
}

#
# Check if delegation would exceed depth limit
#
# Arguments:
#   $1 - parent_id: Parent agent ID
#   $2 - child_id: Child agent ID
#
# Returns: 0 if within limit, 1 if would exceed
#
check_delegation_depth() {
    local parent_id="$1"
    local child_id="$2"

    local parent_depth
    parent_depth=$(get_delegation_depth "$parent_id")

    local child_depth=$((parent_depth + 1))

    if (( child_depth > MAX_DELEGATION_DEPTH )); then
        echo "ERROR: Delegation depth limit ($MAX_DELEGATION_DEPTH) reached. Cannot delegate further." >&2
        echo "" >&2
        echo "Current depth: $parent_depth" >&2
        echo "Attempted child depth: $child_depth" >&2
        echo "Maximum allowed: $MAX_DELEGATION_DEPTH" >&2
        echo "" >&2
        echo "Suggestion: Complete this task at current level or simplify." >&2
        return 1
    fi

    # Set child depth
    set_delegation_depth "$child_id" "$child_depth"

    return 0
}

# ============================================================================
# Cycle Detection
# ============================================================================

#
# Add edge to execution graph
#
# Arguments:
#   $1 - parent_id: Parent agent ID
#   $2 - child_id: Child agent ID
#
add_execution_edge() {
    local parent_id="$1"
    local child_id="$2"

    init_delegation_tracking

    local tmp_file
    tmp_file=$(mktemp)

    # Add child to parent's children array
    jq --arg parent "$parent_id" --arg child "$child_id" \
        '.[$parent] = (.[$parent] // []) + [$child] | .[$parent] |= unique' \
        "$EXECUTION_GRAPH_FILE" > "$tmp_file"

    mv "$tmp_file" "$EXECUTION_GRAPH_FILE"
}

#
# Get children of an agent
#
# Arguments:
#   $1 - agent_id: Parent agent ID
#
# Output: JSON array of child IDs
#
get_execution_children() {
    local agent_id="$1"

    init_delegation_tracking

    jq -r --arg id "$agent_id" '.[$id] // []' "$EXECUTION_GRAPH_FILE"
}

#
# Detect if adding edge would create cycle
#
# Uses DFS (Depth-First Search) to detect cycles.
#
# Arguments:
#   $1 - parent_id: Parent agent ID (start of new edge)
#   $2 - child_id: Child agent ID (end of new edge)
#
# Returns: 0 if no cycle, 1 if cycle detected
#
detect_delegation_cycle() {
    local parent_id="$1"
    local child_id="$2"

    init_delegation_tracking

    # If child == parent, obvious cycle
    if [[ "$parent_id" == "$child_id" ]]; then
        echo "ERROR: Delegation cycle detected. Cannot delegate to self." >&2
        echo "" >&2
        echo "Attempted: $parent_id → $child_id" >&2
        return 1
    fi

    # Check if child is ancestor of parent (would create cycle)
    if is_ancestor "$child_id" "$parent_id"; then
        echo "ERROR: Delegation cycle detected. Cannot delegate to avoid infinite loop." >&2
        echo "" >&2
        echo "Cycle path: $(get_cycle_path "$child_id" "$parent_id")" >&2
        echo "" >&2
        echo "This would create an infinite delegation loop." >&2
        return 1
    fi

    return 0
}

#
# Check if 'ancestor' is an ancestor of 'node' in execution graph
#
# Arguments:
#   $1 - ancestor: Potential ancestor ID
#   $2 - node: Node ID
#
# Returns: 0 if ancestor found, 1 otherwise
#
is_ancestor() {
    local ancestor="$1"
    local node="$2"

    # DFS from node to find ancestor
    local visited=()
    local stack=("$node")

    while (( ${#stack[@]} > 0 )); do
        # Pop from stack
        local current="${stack[-1]}"
        unset 'stack[-1]'

        # Check if visited
        if [[ " ${visited[*]} " =~ " ${current} " ]]; then
            continue
        fi

        visited+=("$current")

        # Check if current is ancestor
        if [[ "$current" == "$ancestor" ]]; then
            return 0
        fi

        # Add children to stack
        local children
        children=$(get_execution_children "$current")

        if [[ "$children" != "[]" ]]; then
            while IFS= read -r child; do
                child=$(echo "$child" | tr -d '"')
                stack+=("$child")
            done < <(echo "$children" | jq -r '.[]')
        fi
    done

    return 1
}

#
# Get cycle path for error message
#
# Arguments:
#   $1 - start: Start node
#   $2 - end: End node (creates cycle back to start)
#
# Output: Cycle path string (e.g., "A → B → C → A")
#
get_cycle_path() {
    local start="$1"
    local end="$2"

    # Simplified path: end → ... → start (attempted)
    echo "$end → ... → $start → $end (attempted)"
}

# ============================================================================
# Delegation Logging
# ============================================================================

#
# Log delegation event
#
# Arguments:
#   $1 - event_type: "started", "completed", "failed"
#   $2 - parent_story: Parent story ID
#   $3 - child_story: Child story ID
#   $4 - depth: Delegation depth
#   $5 - parent_id: Parent agent execution ID
#   $6 - child_id: Child agent execution ID
#   $7... - additional fields (JSON format: key=value)
#
log_delegation() {
    local event_type="$1"
    local parent_story="$2"
    local child_story="$3"
    local depth="$4"
    local parent_id="$5"
    local child_id="$6"
    shift 6

    init_delegation_tracking

    local timestamp
    timestamp=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

    # Build JSON log entry
    local log_entry
    log_entry=$(jq -n \
        --arg timestamp "$timestamp" \
        --arg parent_story "$parent_story" \
        --arg child_story "$child_story" \
        --argjson depth "$depth" \
        --arg parent_id "$parent_id" \
        --arg child_id "$child_id" \
        --arg status "$event_type" \
        '{
            timestamp: $timestamp,
            parent_story: $parent_story,
            child_story: $child_story,
            depth: $depth,
            parent_id: $parent_id,
            child_id: $child_id,
            status: $status
        }')

    # Add optional fields
    while [[ $# -gt 0 ]]; do
        local field="$1"
        shift

        if [[ "$field" =~ ^([^=]+)=(.+)$ ]]; then
            local key="${BASH_REMATCH[1]}"
            local value="${BASH_REMATCH[2]}"

            # Add field to JSON
            log_entry=$(echo "$log_entry" | jq --arg key "$key" --arg value "$value" \
                '. + {($key): $value}')
        fi
    done

    # Append to log
    echo "$log_entry" >> "$DELEGATION_LOG"
}

#
# Get delegation statistics
#
# Output: JSON object with delegation stats
#
get_delegation_stats() {
    init_delegation_tracking

    local total_delegations
    local max_depth_seen
    local active_delegations

    total_delegations=$(wc -l < "$DELEGATION_LOG" | tr -d ' ')
    max_depth_seen=$(jq -s 'map(.depth) | max // 0' "$DELEGATION_LOG")
    active_delegations=$(jq -s 'map(select(.status == "started")) | length' "$DELEGATION_LOG")

    jq -n \
        --argjson total "$total_delegations" \
        --argjson max_depth "$max_depth_seen" \
        --argjson active "$active_delegations" \
        --argjson max_allowed "$MAX_DELEGATION_DEPTH" \
        '{
            total_delegations: $total,
            max_depth_seen: $max_depth,
            active_delegations: $active,
            max_allowed_depth: $max_allowed
        }'
}

#
# Get total cost for a story including all delegated children
#
# Arguments:
#   $1 - story_id: Parent story ID
#
# Output: Total cost in USD (float)
#
get_story_total_cost() {
    local story_id="$1"

    init_delegation_tracking

    # Sum all costs for this story and its delegated children
    local total_cost
    total_cost=$(jq -s --arg story "$story_id" '
        map(select(.parent_story == $story and .status == "completed" and .cost_usd != null))
        | map(.cost_usd | tonumber)
        | add // 0
    ' "$DELEGATION_LOG")

    echo "$total_cost"
}

#
# Get delegation cost breakdown for a story
#
# Arguments:
#   $1 - story_id: Parent story ID
#
# Output: JSON object with cost breakdown
#
get_delegation_cost_breakdown() {
    local story_id="$1"

    init_delegation_tracking

    jq -s --arg story "$story_id" '
        map(select(.parent_story == $story and .status == "completed"))
        | group_by(.child_story)
        | map({
            child_story: .[0].child_story,
            cost_usd: (map(.cost_usd // "0" | tonumber) | add),
            tokens_in: (map(.tokens_in // "0" | tonumber) | add),
            tokens_out: (map(.tokens_out // "0" | tonumber) | add),
            duration_ms: (map(.duration_ms // "0" | tonumber) | add),
            depth: .[0].depth
        })
        | {
            parent_story: $story,
            total_delegations: length,
            total_cost: (map(.cost_usd) | add // 0),
            total_tokens_in: (map(.tokens_in) | add // 0),
            total_tokens_out: (map(.tokens_out) | add // 0),
            total_duration_ms: (map(.duration_ms) | add // 0),
            children: .
        }
    ' "$DELEGATION_LOG"
}

# ============================================================================
# Cleanup
# ============================================================================

#
# Clear delegation tracking data
#
# WARNING: This removes all delegation history
#
clear_delegation_data() {
    if [[ -d "$DELEGATION_DIR" ]]; then
        rm -rf "$DELEGATION_DIR"
    fi

    echo "Delegation tracking data cleared"
}

# ============================================================================
# CLI Interface (for testing)
# ============================================================================

if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    # Script is being run directly, not sourced

    show_help() {
        cat <<EOF
Usage: $0 <command> [options]

Commands:
  init                          Initialize delegation tracking
  check-depth <parent> <child>  Check if delegation within depth limit
  detect-cycle <parent> <child> Detect if delegation creates cycle
  log <type> <parent> <child> <depth> <p_id> <c_id>  Log delegation event
  stats                         Show delegation statistics
  story-cost <story_id>         Get total cost for story (including delegations)
  cost-breakdown <story_id>     Get detailed cost breakdown for story
  clear                         Clear all delegation data
  help                          Show this help message

Examples:
  $0 init
  $0 check-depth exec-001 exec-002
  $0 detect-cycle exec-001 exec-002
  $0 log started US-007 US-007-DEL-001 1 exec-001 exec-002
  $0 stats
  $0 story-cost US-007
  $0 cost-breakdown US-007
EOF
    }

    case "${1:-help}" in
        init)
            init_delegation_tracking
            echo "Delegation tracking initialized"
            ;;
        check-depth)
            if [[ $# -lt 3 ]]; then
                echo "ERROR: Missing arguments" >&2
                echo "Usage: $0 check-depth <parent_id> <child_id>" >&2
                exit 1
            fi
            check_delegation_depth "$2" "$3"
            ;;
        detect-cycle)
            if [[ $# -lt 3 ]]; then
                echo "ERROR: Missing arguments" >&2
                echo "Usage: $0 detect-cycle <parent_id> <child_id>" >&2
                exit 1
            fi
            detect_delegation_cycle "$2" "$3"
            ;;
        log)
            if [[ $# -lt 7 ]]; then
                echo "ERROR: Missing arguments" >&2
                echo "Usage: $0 log <type> <parent_story> <child_story> <depth> <parent_id> <child_id>" >&2
                exit 1
            fi
            log_delegation "$2" "$3" "$4" "$5" "$6" "$7"
            ;;
        stats)
            get_delegation_stats
            ;;
        story-cost)
            if [[ $# -lt 2 ]]; then
                echo "ERROR: Missing story ID" >&2
                echo "Usage: $0 story-cost <story_id>" >&2
                exit 1
            fi
            get_story_total_cost "$2"
            ;;
        cost-breakdown)
            if [[ $# -lt 2 ]]; then
                echo "ERROR: Missing story ID" >&2
                echo "Usage: $0 cost-breakdown <story_id>" >&2
                exit 1
            fi
            get_delegation_cost_breakdown "$2"
            ;;
        clear)
            clear_delegation_data
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
