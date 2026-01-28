#!/bin/bash
#
# delegation-parser.sh - Parse Delegation Syntax from LLM Output
#
# Parses [delegate:description:estimated_hours] syntax from Claude responses
# and creates structured delegation requests.
#
# Usage:
#   source lib/delegation-parser.sh
#   parse_delegations "$llm_output" "$parent_story_id"
#
# Output: JSON array of delegation requests

set -euo pipefail

# ============================================================================
# Delegation Syntax Parser
# ============================================================================

#
# Parse delegation syntax from LLM output
#
# Arguments:
#   $1 - llm_output: Full text output from Claude
#   $2 - parent_story_id: ID of parent story (e.g., "US-007")
#
# Output: JSON array of delegations to stdout
#
# Example output:
#   [
#     {
#       "description": "Implement JWT token generation",
#       "estimated_hours": 4,
#       "parent_story_id": "US-007",
#       "child_story_id": "US-007-DEL-001",
#       "depth": 1
#     }
#   ]
#
parse_delegations() {
    local llm_output="$1"
    local parent_story_id="$2"
    local current_depth="${DELEGATION_DEPTH:-0}"

    # Extract all [delegate:...:...] patterns
    local delegations
    delegations=$(echo "$llm_output" | grep -oE '\[delegate:[^]]+\]' || true)

    if [[ -z "$delegations" ]]; then
        echo "[]"
        return 0
    fi

    # Parse each delegation
    local json_array="["
    local count=1
    local first=true

    while IFS= read -r delegation_line; do
        [[ -z "$delegation_line" ]] && continue

        # Remove brackets and split by colons
        delegation_line="${delegation_line#\[delegate:}"
        delegation_line="${delegation_line%\]}"

        # Split into components (description:estimated_hours)
        local description
        local estimated_hours

        # Use last colon as delimiter (description may contain colons)
        if [[ "$delegation_line" =~ ^(.+):([0-9]+)$ ]]; then
            description="${BASH_REMATCH[1]}"
            estimated_hours="${BASH_REMATCH[2]}"
        else
            echo "ERROR: Invalid delegation syntax: $delegation_line" >&2
            echo "Expected format: [delegate:description:estimated_hours]" >&2
            continue
        fi

        # Generate child story ID
        local child_story_id="${parent_story_id}-DEL-$(printf '%03d' $count)"
        local child_depth=$((current_depth + 1))

        # Add to JSON array
        if [[ "$first" == "true" ]]; then
            first=false
        else
            json_array+=","
        fi

        # Escape description for JSON
        local escaped_description
        escaped_description=$(echo "$description" | sed 's/"/\\"/g' | sed "s/'/\\'/g")

        json_array+=$(cat <<EOF

  {
    "description": "${escaped_description}",
    "estimated_hours": ${estimated_hours},
    "parent_story_id": "${parent_story_id}",
    "child_story_id": "${child_story_id}",
    "depth": ${child_depth}
  }
EOF
)

        ((count++))
    done <<< "$delegations"

    json_array+=$'\n]'

    echo "$json_array"
}

#
# Validate delegation syntax
#
# Arguments:
#   $1 - delegation_text: The [delegate:...:...] text
#
# Returns: 0 if valid, 1 if invalid
#
validate_delegation_syntax() {
    local delegation_text="$1"

    # Check format: [delegate:description:hours]
    if [[ ! "$delegation_text" =~ ^\[delegate:.+:[0-9]+\]$ ]]; then
        echo "ERROR: Invalid delegation syntax: $delegation_text" >&2
        echo "Expected: [delegate:description:estimated_hours]" >&2
        echo "Example: [delegate:Implement JWT auth:4]" >&2
        return 1
    fi

    return 0
}

#
# Extract description from delegation
#
# Arguments:
#   $1 - delegation_text: The [delegate:...:...] text
#
# Output: Description string
#
extract_description() {
    local delegation_text="$1"

    # Remove [delegate: prefix and ] suffix
    delegation_text="${delegation_text#\[delegate:}"
    delegation_text="${delegation_text%\]}"

    # Extract description (everything before last colon)
    if [[ "$delegation_text" =~ ^(.+):([0-9]+)$ ]]; then
        echo "${BASH_REMATCH[1]}"
    else
        echo ""
    fi
}

#
# Extract estimated hours from delegation
#
# Arguments:
#   $1 - delegation_text: The [delegate:...:...] text
#
# Output: Estimated hours (integer)
#
extract_estimated_hours() {
    local delegation_text="$1"

    # Remove [delegate: prefix and ] suffix
    delegation_text="${delegation_text#\[delegate:}"
    delegation_text="${delegation_text%\]}"

    # Extract hours (after last colon)
    if [[ "$delegation_text" =~ ^(.+):([0-9]+)$ ]]; then
        echo "${BASH_REMATCH[2]}"
    else
        echo "0"
    fi
}

#
# Count delegations in LLM output
#
# Arguments:
#   $1 - llm_output: Full text output from Claude
#
# Output: Number of delegations found
#
count_delegations() {
    local llm_output="$1"

    local count
    count=$(echo "$llm_output" | grep -c '\[delegate:' || echo "0")

    echo "$count"
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
  parse <file> <parent_id>   Parse delegations from file
  validate <text>            Validate delegation syntax
  count <file>               Count delegations in file
  help                       Show this help message

Examples:
  $0 parse output.txt US-007
  $0 validate "[delegate:Implement auth:4]"
  $0 count response.txt
EOF
    }

    case "${1:-help}" in
        parse)
            if [[ $# -lt 3 ]]; then
                echo "ERROR: Missing arguments" >&2
                echo "Usage: $0 parse <file> <parent_id>" >&2
                exit 1
            fi
            llm_output=$(cat "$2")
            parent_id="$3"
            parse_delegations "$llm_output" "$parent_id"
            ;;
        validate)
            if [[ $# -lt 2 ]]; then
                echo "ERROR: Missing delegation text" >&2
                exit 1
            fi
            validate_delegation_syntax "$2"
            ;;
        count)
            if [[ $# -lt 2 ]]; then
                echo "ERROR: Missing file argument" >&2
                exit 1
            fi
            llm_output=$(cat "$2")
            count_delegations "$llm_output"
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
