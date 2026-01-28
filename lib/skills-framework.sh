#!/bin/bash
#
# skills-framework.sh - Skills Architecture Core Framework
#
# Implements Cowork-style progressive disclosure:
# - Metadata layer: Always loaded (< 100 tokens/skill)
# - Instructions layer: On-demand (when skill triggered)
# - Resources layer: Zero upfront cost (scripts executed only when needed)
#
# Usage:
#   source lib/skills-framework.sh
#   load_skills_metadata
#   list_skills
#   execute_skill "skill-name" "arg1" "arg2"
#

set -euo pipefail

# ============================================================================
# Configuration
# ============================================================================

SKILLS_DIR="${SKILLS_DIR:-./skills}"
SKILLS_CACHE_DIR="./.claude-loop/skills-cache"
SKILLS_METADATA_CACHE="${SKILLS_CACHE_DIR}/metadata.json"

# ============================================================================
# Metadata Layer - Always Loaded (< 100 tokens per skill)
# ============================================================================

# Load all skill metadata at startup
# Metadata includes: name, description, usage, tags
# IMPORTANT: Does NOT load full instructions (on-demand only)
load_skills_metadata() {
    local skills_dir="$1"
    local metadata_output="${2:-}"

    # Create cache directory
    mkdir -p "${SKILLS_CACHE_DIR}"

    # Find all SKILL.md files
    local skill_files=()
    while IFS= read -r -d '' file; do
        skill_files+=("$file")
    done < <(find "${skills_dir}" -name "SKILL.md" -type f -print0 2>/dev/null || true)

    if [[ ${#skill_files[@]} -eq 0 ]]; then
        echo "[]" > "${SKILLS_METADATA_CACHE}"
        return 0
    fi

    # Extract metadata from each skill (first 20 lines only)
    local json_array="["
    local first=true

    for skill_file in "${skill_files[@]}"; do
        local skill_dir=$(dirname "$skill_file")
        local skill_name=$(basename "$skill_dir")

        # Extract metadata from first few lines of SKILL.md
        local title=$(head -n 1 "$skill_file" | sed 's/^# //' | sed 's/ - /|/' | cut -d'|' -f2 || echo "")
        local description=$(head -n 20 "$skill_file" | grep -A 1 "^#" | tail -n 1 | sed 's/^[[:space:]]*//' || echo "")

        # Extract usage pattern
        local usage=$(head -n 20 "$skill_file" | grep -A 3 "## Usage" | grep '^/' | head -n 1 || echo "")

        # Build JSON object for this skill
        if [[ "$first" == true ]]; then
            first=false
        else
            json_array+=","
        fi

        json_array+=$(cat <<EOF

{
  "name": "$skill_name",
  "title": "$title",
  "description": "$description",
  "usage": "$usage",
  "path": "$skill_file",
  "has_scripts": $([ -d "${skill_dir}/scripts" ] && echo "true" || echo "false")
}
EOF
)
    done

    json_array+=$'\n]'

    # Save to cache
    echo "$json_array" > "${SKILLS_METADATA_CACHE}"

    # Optionally output to specified file
    if [[ -n "$metadata_output" ]]; then
        echo "$json_array" > "$metadata_output"
    fi

    return 0
}

# Get metadata for all skills
get_skills_metadata() {
    if [[ ! -f "${SKILLS_METADATA_CACHE}" ]]; then
        load_skills_metadata "${SKILLS_DIR}"
    fi
    cat "${SKILLS_METADATA_CACHE}"
}

# Get metadata for a specific skill
get_skill_metadata() {
    local skill_name="$1"
    get_skills_metadata | jq -r ".[] | select(.name == \"${skill_name}\")"
}

# Check if a skill exists
skill_exists() {
    local skill_name="$1"
    local metadata=$(get_skill_metadata "$skill_name")
    [[ -n "$metadata" ]]
}

# ============================================================================
# Instructions Layer - On-Demand Loading
# ============================================================================

# Load full instructions for a skill (only when triggered)
load_skill_instructions() {
    local skill_name="$1"

    # Get skill metadata
    local metadata=$(get_skill_metadata "$skill_name")
    if [[ -z "$metadata" ]]; then
        echo "Error: Skill '$skill_name' not found" >&2
        return 1
    fi

    # Get skill file path
    local skill_file=$(echo "$metadata" | jq -r '.path')

    # Read full SKILL.md content
    cat "$skill_file"
}

# ============================================================================
# Resources Layer - Script Execution (Zero Upfront Cost)
# ============================================================================

# Execute a skill's script with arguments
execute_skill_script() {
    local skill_name="$1"
    shift
    local args=("$@")

    # Get skill metadata
    local metadata=$(get_skill_metadata "$skill_name")
    if [[ -z "$metadata" ]]; then
        echo "Error: Skill '$skill_name' not found" >&2
        return 1
    fi

    # Get skill directory
    local skill_file=$(echo "$metadata" | jq -r '.path')
    local skill_dir=$(dirname "$skill_file")

    # Check if skill has scripts
    local has_scripts=$(echo "$metadata" | jq -r '.has_scripts')
    if [[ "$has_scripts" != "true" ]]; then
        echo "Error: Skill '$skill_name' has no scripts directory" >&2
        return 1
    fi

    # Look for main script (check for various extensions)
    local script_file=""
    for ext in sh py js; do
        if [[ -f "${skill_dir}/scripts/main.${ext}" ]]; then
            script_file="${skill_dir}/scripts/main.${ext}"
            break
        fi
    done

    if [[ -z "$script_file" ]]; then
        echo "Error: Skill '$skill_name' has no main script (main.sh/main.py/main.js)" >&2
        return 1
    fi

    # Execute script based on extension
    case "$script_file" in
        *.sh)
            if [[ ${#args[@]} -gt 0 ]]; then
                bash "$script_file" "${args[@]}"
            else
                bash "$script_file"
            fi
            ;;
        *.py)
            if [[ ${#args[@]} -gt 0 ]]; then
                python3 "$script_file" "${args[@]}"
            else
                python3 "$script_file"
            fi
            ;;
        *.js)
            if [[ ${#args[@]} -gt 0 ]]; then
                node "$script_file" "${args[@]}"
            else
                node "$script_file"
            fi
            ;;
        *)
            echo "Error: Unsupported script type: $script_file" >&2
            return 1
            ;;
    esac
}

# ============================================================================
# Skill Execution Engine
# ============================================================================

# Execute a skill (loads instructions and executes script if available)
execute_skill() {
    local skill_name="$1"
    shift
    local args=("$@")

    # Verify skill exists
    if ! skill_exists "$skill_name"; then
        echo "Error: Skill '$skill_name' not found" >&2
        echo "Available skills:" >&2
        list_skills >&2
        return 1
    fi

    # Load instructions (for context)
    local instructions=$(load_skill_instructions "$skill_name")

    # Check if skill has executable scripts
    local metadata=$(get_skill_metadata "$skill_name")
    local has_scripts=$(echo "$metadata" | jq -r '.has_scripts')

    if [[ "$has_scripts" == "true" ]]; then
        # Execute script
        echo "Executing skill: $skill_name"
        if [[ ${#args[@]} -gt 0 ]]; then
            execute_skill_script "$skill_name" "${args[@]}"
        else
            execute_skill_script "$skill_name"
        fi
    else
        # Documentation-only skill (like existing /prd and /claude-loop)
        echo "Skill: $skill_name"
        echo ""
        echo "$instructions"
    fi
}

# ============================================================================
# Skill Discovery
# ============================================================================

# List all available skills
list_skills() {
    local format="${1:-text}"  # text or json

    if [[ "$format" == "json" ]]; then
        get_skills_metadata
    else
        # Text format for human consumption
        echo "Available Skills:"
        echo ""

        local skills=$(get_skills_metadata)
        local count=$(echo "$skills" | jq -r 'length')

        if [[ "$count" -eq 0 ]]; then
            echo "  No skills found in ${SKILLS_DIR}/"
            return 0
        fi

        # Print each skill
        echo "$skills" | jq -r '.[] | "  \(.name)\n    \(.description)\n    Usage: \(.usage)\n"'
    fi
}

# Search skills by keyword
search_skills() {
    local keyword="$1"
    get_skills_metadata | jq -r ".[] | select(.description | test(\"${keyword}\"; \"i\")) | .name"
}

# ============================================================================
# Initialization
# ============================================================================

# Initialize skills framework
init_skills_framework() {
    local skills_dir="${1:-./skills}"
    SKILLS_DIR="$skills_dir"

    # Load metadata
    load_skills_metadata "$skills_dir"

    # Return count
    local count=$(get_skills_metadata | jq -r 'length')
    echo "Loaded $count skills" >&2
    return 0
}

# ============================================================================
# Utility Functions
# ============================================================================

# Clear skills cache (force reload)
clear_skills_cache() {
    rm -rf "${SKILLS_CACHE_DIR}"
    echo "Skills cache cleared" >&2
}

# Validate skill structure
validate_skill() {
    local skill_name="$1"
    local skill_dir="${SKILLS_DIR}/${skill_name}"

    local errors=0

    # Check SKILL.md exists
    if [[ ! -f "${skill_dir}/SKILL.md" ]]; then
        echo "Error: Missing SKILL.md" >&2
        errors=$((errors + 1))
    fi

    # If scripts/ exists, check for main script
    if [[ -d "${skill_dir}/scripts" ]]; then
        local has_main=false
        for ext in sh py js; do
            if [[ -f "${skill_dir}/scripts/main.${ext}" ]]; then
                has_main=true
                break
            fi
        done

        if [[ "$has_main" != true ]]; then
            echo "Warning: scripts/ directory exists but no main script found" >&2
        fi
    fi

    return $errors
}

# Export functions for use in other scripts
export -f load_skills_metadata
export -f get_skills_metadata
export -f get_skill_metadata
export -f skill_exists
export -f load_skill_instructions
export -f execute_skill_script
export -f execute_skill
export -f list_skills
export -f search_skills
export -f init_skills_framework
export -f clear_skills_cache
export -f validate_skill
