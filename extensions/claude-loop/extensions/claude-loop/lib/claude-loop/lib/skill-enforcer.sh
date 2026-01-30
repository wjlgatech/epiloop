#!/usr/bin/env bash
#
# skill-enforcer.sh - Mandatory Skill Enforcement for claude-loop
#
# Makes skills NON-OPTIONAL workflows rather than suggestions.
# Skills are enforced based on story content and cannot be rationalized away.
#
# Usage:
#   check_mandatory_skills "<story_text>" - Returns <MANDATORY-SKILL> markers

set -euo pipefail

# ============================================================================
# Skill Detection Rules
# ============================================================================

# Detect if story requires test-driven-development
requires_tdd() {
    local story_text="$1"

    # TDD required for: implement, create, add, build, new feature
    if echo "$story_text" | grep -qiE "(implement|create|add|build|new feature|develop)"; then
        return 0  # true
    fi

    return 1  # false
}

# Detect if story requires systematic-debugging
requires_debugging() {
    local story_text="$1"

    # Debugging required for: bug, fix, debug, issue, error, failure
    if echo "$story_text" | grep -qiE "(bug|fix|debug|issue|error|failure|broken)"; then
        return 0  # true
    fi

    return 1  # false
}

# Detect if story requires brainstorming (if available)
requires_brainstorming() {
    local story_text="$1"
    local complexity="${2:-0}"

    # Brainstorming required for: high complexity OR "design" keyword
    if [ "$complexity" -ge 5 ] || echo "$story_text" | grep -qiE "(design|architect|refactor|rethink)"; then
        return 0  # true
    fi

    return 1  # false
}

# Detect if story requires code review
requires_code_review() {
    local story_text="$1"

    # Code review required for all implementation stories
    if echo "$story_text" | grep -qiE "(implement|create|add|build|modify|update)"; then
        return 0  # true
    fi

    return 1  # false
}

# ============================================================================
# Skill Enforcement
# ============================================================================

check_mandatory_skills() {
    local story_text="$1"
    local complexity="${2:-0}"
    local mandatory_skills=()
    local script_dir="${SCRIPT_DIR:-$(dirname "$0")/..}"

    # Detect mandatory skills based on story content
    # Only add skills that actually exist (have SKILL.md files)

    # TDD skill (TODO: not yet implemented)
    # if requires_tdd "$story_text"; then
    #     if [ -f "$script_dir/skills/test-driven-development/SKILL.md" ]; then
    #         mandatory_skills+=("test-driven-development")
    #     fi
    # fi

    # Systematic debugging skill (TODO: not yet implemented)
    # if requires_debugging "$story_text"; then
    #     if [ -f "$script_dir/skills/systematic-debugging/SKILL.md" ]; then
    #         mandatory_skills+=("systematic-debugging")
    #     fi
    # fi

    # Brainstorming skill (IMPLEMENTED)
    if requires_brainstorming "$story_text" "$complexity"; then
        # Only if brainstorming skill exists
        if [ -f "$script_dir/skills/brainstorming/SKILL.md" ]; then
            mandatory_skills+=("brainstorming")
        fi
    fi

    # Code review skill (TODO: not yet implemented, but two-stage review exists)
    # if requires_code_review "$story_text"; then
    #     if [ -f "$script_dir/skills/requesting-code-review/SKILL.md" ]; then
    #         mandatory_skills+=("requesting-code-review")
    #     fi
    # fi

    # Return empty if no mandatory skills
    if [ ${#mandatory_skills[@]} -eq 0 ]; then
        return 0
    fi

    # Build enforcement markers
    echo ""
    echo "<EXTREMELY-IMPORTANT>"
    echo "The following skills are MANDATORY for this story. You MUST use them."
    echo ""
    echo "This is not negotiable. This is not optional. You cannot rationalize your way out of this."
    echo ""

    for skill in "${mandatory_skills[@]}"; do
        echo "## MANDATORY: $skill"
        echo ""

        # Load skill file if it exists
        local skill_path="${SCRIPT_DIR:-$(dirname "$0")/..}/skills/${skill}/SKILL.md"
        if [ -f "$skill_path" ]; then
            cat "$skill_path"
            echo ""
        else
            echo "Skill file not found: $skill_path"
            echo "But this skill is REQUIRED. Check for the skill in the available skills."
            echo ""
        fi
    done

    echo "</EXTREMELY-IMPORTANT>"
}

# ============================================================================
# CLI Interface
# ============================================================================

if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    # Called directly - check mandatory skills for given story
    if [ $# -lt 1 ]; then
        echo "Usage: $0 '<story_text>' [complexity]"
        exit 1
    fi

    check_mandatory_skills "$1" "${2:-0}"
fi
