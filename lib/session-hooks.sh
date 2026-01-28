#!/usr/bin/env bash
#
# session-hooks.sh - SessionStart hook system for claude-loop
#
# Automatically injects context on every session start:
# - Skills overview
# - Agent registry
# - Experience store status
# - Configuration
#
# Eliminates setup friction (80% reduction)

set -euo pipefail

# Determine script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CLAUDE_LOOP_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

# ============================================================================
# Context Builders
# ============================================================================

build_skills_overview() {
    local skills_file="${CLAUDE_LOOP_ROOT}/lib/skills-overview.md"
    if [[ -f "$skills_file" ]]; then
        cat "$skills_file"
    else
        echo "# Skills Overview (Not yet configured)"
    fi
}

build_agent_registry_context() {
    local agents_dir="${CLAUDE_LOOP_ROOT}/agents"

    if [[ ! -d "$agents_dir" ]]; then
        echo "No agents available"
        return
    fi

    echo ""
    echo "## Available Agents"
    echo ""

    # List bundled agents
    for agent_file in "$agents_dir"/*.md; do
        if [[ -f "$agent_file" ]]; then
            local agent_name=$(basename "$agent_file" .md)
            local description=$(grep -m1 "^#" "$agent_file" | sed 's/^# //' || echo "No description")
            echo "- **$agent_name**: $description"
        fi
    done
}

build_experience_store_status() {
    local experience_store="${CLAUDE_LOOP_ROOT}/lib/experience-store.py"

    if [[ ! -f "$experience_store" ]]; then
        echo "Experience store not configured"
        return
    fi

    echo ""
    echo "## Experience Store Status"
    echo ""

    # Try to get brief stats
    if command -v python3 &> /dev/null; then
        local stats=$(python3 "$experience_store" stats --brief 2>/dev/null || echo "Status unavailable")
        echo "$stats"
    else
        echo "Python3 not available - cannot load experience stats"
    fi
}

build_configuration_context() {
    local config_file="${CLAUDE_LOOP_ROOT}/config.yaml"

    echo ""
    echo "## Configuration"
    echo ""

    if [[ -f "$config_file" ]]; then
        echo "- Config loaded from: \`config.yaml\`"

        # Extract key settings if yq available
        if command -v yq &> /dev/null; then
            local exec_mode=$(yq eval '.execution_mode.default // "autonomous"' "$config_file" 2>/dev/null)
            local max_agents=$(yq eval '.agents.max_per_iteration // 2' "$config_file" 2>/dev/null)
            echo "- Execution mode: $exec_mode"
            echo "- Max agents per iteration: $max_agents"
        fi
    else
        echo "- Using default configuration"
        echo "- Execution mode: autonomous"
        echo "- Max agents per iteration: 2"
    fi
}

# ============================================================================
# Main Session Hook
# ============================================================================

session_start_hook() {
    local context=""

    # Build context from all sources
    context+="<SESSION-CONTEXT>"
    context+=$'\n'
    context+="# claude-loop Session Context"
    context+=$'\n\n'
    context+="This context is automatically injected on session start."
    context+=$'\n\n'

    # 1. Skills overview (most important)
    context+="$(build_skills_overview)"
    context+=$'\n'

    # 2. Available agents
    context+="$(build_agent_registry_context)"
    context+=$'\n'

    # 3. Experience store status
    context+="$(build_experience_store_status)"
    context+=$'\n'

    # 4. Configuration
    context+="$(build_configuration_context)"
    context+=$'\n'

    context+="</SESSION-CONTEXT>"

    echo "$context"
}

# ============================================================================
# CLI Interface
# ============================================================================

if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    # Called directly - run hook and output context
    session_start_hook
fi
