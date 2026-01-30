#!/usr/bin/env bash
# lib/progress-indicators.sh
# Real-time progress indicators for claude-loop

set -euo pipefail

# ============================================================================
# Configuration and State
# ============================================================================

# Global state
PROGRESS_ENABLED="${PROGRESS_ENABLED:-true}"
PROGRESS_CURRENT_STORY=""
PROGRESS_TOTAL_STORIES=0
PROGRESS_COMPLETED_STORIES=0
PROGRESS_START_TIME=0
PROGRESS_STORY_START_TIME=0
PROGRESS_CURRENT_ACTION=""
PROGRESS_TERMINAL_WIDTH=80
PROGRESS_TERMINAL_HEIGHT=24
PROGRESS_PAUSED=false  # Pause rendering during confirmations

# Acceptance criteria tracking
declare -a PROGRESS_ACCEPTANCE_CRITERIA=()
declare -a PROGRESS_CRITERIA_STATUS=() # Values: pending, in_progress, done

# Workspace tracking (set externally)
PROGRESS_WORKSPACE_PATH=""

# Color codes (with fallback for non-color terminals)
if [[ -t 1 ]] && command -v tput >/dev/null 2>&1; then
    COLOR_RESET=$(tput sgr0)
    COLOR_GREEN=$(tput setaf 2)
    COLOR_YELLOW=$(tput setaf 3)
    COLOR_RED=$(tput setaf 1)
    COLOR_BLUE=$(tput setaf 4)
    COLOR_BOLD=$(tput bold)
    COLOR_DIM=$(tput dim)
else
    COLOR_RESET=""
    COLOR_GREEN=""
    COLOR_YELLOW=""
    COLOR_RED=""
    COLOR_BLUE=""
    COLOR_BOLD=""
    COLOR_DIM=""
fi

# Unicode symbols (with ASCII fallback)
if [[ "${LANG:-}" =~ UTF-8 ]] || [[ "${LC_ALL:-}" =~ UTF-8 ]]; then
    SYMBOL_DONE="✅"
    SYMBOL_IN_PROGRESS="⏳"
    SYMBOL_PENDING="○"
    SYMBOL_BLOCKED="🚫"
    PROGRESS_CHAR_FULL="█"
    PROGRESS_CHAR_PARTIAL="▓"
    PROGRESS_CHAR_EMPTY="░"
else
    SYMBOL_DONE="[x]"
    SYMBOL_IN_PROGRESS="[.]"
    SYMBOL_PENDING="[ ]"
    SYMBOL_BLOCKED="[!]"
    PROGRESS_CHAR_FULL="#"
    PROGRESS_CHAR_PARTIAL="="
    PROGRESS_CHAR_EMPTY="-"
fi

# ============================================================================
# Initialization and Configuration
# ============================================================================

# Initialize progress tracking
init_progress() {
    local prd_file="${1:-prd.json}"

    if [[ "$PROGRESS_ENABLED" != "true" ]]; then
        return 0
    fi

    # Get terminal dimensions
    update_terminal_dimensions

    # Set up terminal resize handler
    trap 'handle_terminal_resize' WINCH

    # Record start time
    PROGRESS_START_TIME=$(get_timestamp_ms)

    # Count total stories from PRD
    if [[ -f "$prd_file" ]]; then
        PROGRESS_TOTAL_STORIES=$(python3 -c "
import json
with open('$prd_file') as f:
    prd = json.load(f)
    print(len([s for s in prd.get('userStories', [])]))
" 2>/dev/null || echo "0")
    fi

    # Count completed stories
    if [[ -f "$prd_file" ]]; then
        PROGRESS_COMPLETED_STORIES=$(python3 -c "
import json
with open('$prd_file') as f:
    prd = json.load(f)
    print(len([s for s in prd.get('userStories', []) if s.get('passes', False)]))
" 2>/dev/null || echo "0")
    fi
}

# Disable progress indicators (for CI/CD)
disable_progress() {
    PROGRESS_ENABLED="false"
}

# Enable progress indicators
enable_progress() {
    PROGRESS_ENABLED="true"
}

# Check if progress is enabled
is_progress_enabled() {
    [[ "$PROGRESS_ENABLED" == "true" ]]
}

# Check if progress is paused
is_progress_paused() {
    [[ "$PROGRESS_PAUSED" == "true" ]]
}

# Pause progress rendering (for confirmations)
pause_progress() {
    if is_progress_enabled; then
        PROGRESS_PAUSED=true
    fi
}

# Resume progress rendering
resume_progress() {
    if is_progress_enabled; then
        PROGRESS_PAUSED=false
        render_progress_ui
    fi
}

# Set workspace path for display
set_workspace_path() {
    local workspace="$1"
    PROGRESS_WORKSPACE_PATH="$workspace"
}

# ============================================================================
# Terminal Handling
# ============================================================================

# Update terminal dimensions
update_terminal_dimensions() {
    if command -v tput >/dev/null 2>&1; then
        PROGRESS_TERMINAL_WIDTH=$(tput cols 2>/dev/null || echo 80)
        PROGRESS_TERMINAL_HEIGHT=$(tput lines 2>/dev/null || echo 24)
    else
        PROGRESS_TERMINAL_WIDTH=80
        PROGRESS_TERMINAL_HEIGHT=24
    fi
}

# Handle terminal resize signal
handle_terminal_resize() {
    update_terminal_dimensions
    # Redraw the progress UI
    if is_progress_enabled && [[ -n "$PROGRESS_CURRENT_STORY" ]]; then
        render_progress_ui
    fi
}

# ============================================================================
# Time Utilities
# ============================================================================

# Get timestamp in milliseconds (cross-platform)
get_timestamp_ms() {
    if [[ "$(uname)" == "Darwin" ]]; then
        # macOS
        perl -MTime::HiRes=time -e 'printf "%.0f\n", time * 1000'
    else
        # Linux
        date +%s%3N
    fi
}

# Format duration in human-readable format
format_duration() {
    local ms=$1
    local seconds=$((ms / 1000))
    local minutes=$((seconds / 60))
    local hours=$((minutes / 60))

    seconds=$((seconds % 60))
    minutes=$((minutes % 60))

    if [[ $hours -gt 0 ]]; then
        printf "%dh %dm %ds" "$hours" "$minutes" "$seconds"
    elif [[ $minutes -gt 0 ]]; then
        printf "%dm %ds" "$minutes" "$seconds"
    else
        printf "%ds" "$seconds"
    fi
}

# Estimate remaining time based on story velocity
estimate_remaining_time() {
    local completed=$PROGRESS_COMPLETED_STORIES
    local total=$PROGRESS_TOTAL_STORIES
    local elapsed=$(($(get_timestamp_ms) - PROGRESS_START_TIME))

    if [[ $completed -eq 0 ]]; then
        echo "calculating..."
        return
    fi

    local avg_time_per_story=$((elapsed / completed))
    local remaining_stories=$((total - completed))
    local estimated_remaining=$((avg_time_per_story * remaining_stories))

    format_duration "$estimated_remaining"
}

# ============================================================================
# Story Tracking
# ============================================================================

# Start tracking a new story
start_story() {
    local story_id="$1"
    local story_title="${2:-}"
    shift 2
    local acceptance_criteria=("$@")

    if ! is_progress_enabled; then
        return 0
    fi

    PROGRESS_CURRENT_STORY="$story_id"
    PROGRESS_STORY_START_TIME=$(get_timestamp_ms)

    # Load acceptance criteria
    PROGRESS_ACCEPTANCE_CRITERIA=()
    PROGRESS_CRITERIA_STATUS=()

    for criterion in "${acceptance_criteria[@]}"; do
        PROGRESS_ACCEPTANCE_CRITERIA+=("$criterion")
        PROGRESS_CRITERIA_STATUS+=("pending")
    done

    # Render initial UI
    render_progress_ui
}

# Update current action
set_current_action() {
    local action="$1"

    if ! is_progress_enabled; then
        return 0
    fi

    PROGRESS_CURRENT_ACTION="$action"
    render_progress_ui
}

# Mark acceptance criterion as done
mark_criterion_done() {
    local criterion_index=$1

    if ! is_progress_enabled; then
        return 0
    fi

    if [[ $criterion_index -ge 0 ]] && [[ $criterion_index -lt ${#PROGRESS_CRITERIA_STATUS[@]} ]]; then
        PROGRESS_CRITERIA_STATUS[$criterion_index]="done"
        render_progress_ui
    fi
}

# Mark acceptance criterion as in progress
mark_criterion_in_progress() {
    local criterion_index=$1

    if ! is_progress_enabled; then
        return 0
    fi

    if [[ $criterion_index -ge 0 ]] && [[ $criterion_index -lt ${#PROGRESS_CRITERIA_STATUS[@]} ]]; then
        PROGRESS_CRITERIA_STATUS[$criterion_index]="in_progress"
        render_progress_ui
    fi
}

# Complete current story
complete_story() {
    if ! is_progress_enabled; then
        return 0
    fi

    PROGRESS_COMPLETED_STORIES=$((PROGRESS_COMPLETED_STORIES + 1))

    # Mark all criteria as done
    for i in "${!PROGRESS_CRITERIA_STATUS[@]}"; do
        PROGRESS_CRITERIA_STATUS[$i]="done"
    done

    render_progress_ui

    # Clear current story
    PROGRESS_CURRENT_STORY=""
    PROGRESS_CURRENT_ACTION=""
}

# ============================================================================
# Progress Bar Rendering
# ============================================================================

# Render a progress bar
render_progress_bar() {
    local current=$1
    local total=$2
    local width=${3:-40}

    local percentage=0
    if [[ $total -gt 0 ]]; then
        percentage=$((current * 100 / total))
    fi

    local filled=$((width * current / total))
    [[ $total -eq 0 ]] && filled=0

    local empty=$((width - filled))

    # Determine color based on progress and time
    local color="$COLOR_GREEN"
    local elapsed=$(($(get_timestamp_ms) - PROGRESS_STORY_START_TIME))
    local expected_progress=$((percentage))

    # Simple heuristic: if we're behind schedule, show yellow/red
    if [[ $elapsed -gt 300000 ]] && [[ $percentage -lt 50 ]]; then
        color="$COLOR_YELLOW"
    fi
    if [[ $elapsed -gt 600000 ]] && [[ $percentage -lt 50 ]]; then
        color="$COLOR_RED"
    fi

    echo -n "$color["
    for ((i = 0; i < filled; i++)); do
        echo -n "$PROGRESS_CHAR_FULL"
    done
    for ((i = 0; i < empty; i++)); do
        echo -n "$PROGRESS_CHAR_EMPTY"
    done
    echo -n "]$COLOR_RESET $percentage%"
}

# ============================================================================
# Main UI Rendering
# ============================================================================

# Render the complete progress UI
render_progress_ui() {
    if ! is_progress_enabled; then
        return 0
    fi

    if is_progress_paused; then
        return 0
    fi

    if [[ -z "$PROGRESS_CURRENT_STORY" ]]; then
        return 0
    fi

    # Clear screen (just the progress section)
    # We'll use a fixed number of lines to avoid screen flicker
    local ui_lines=10

    # Move cursor up and clear lines
    for ((i = 0; i < ui_lines; i++)); do
        echo -ne "\033[1A\033[2K" 2>/dev/null || true
    done

    echo ""
    echo "${COLOR_BOLD}╔════════════════════════════════════════════════════════════════╗${COLOR_RESET}"
    echo "${COLOR_BOLD}║${COLOR_RESET} ${COLOR_BLUE}Current Story:${COLOR_RESET} $PROGRESS_CURRENT_STORY"

    # Show workspace path if set
    if [[ -n "$PROGRESS_WORKSPACE_PATH" ]]; then
        echo "${COLOR_BOLD}║${COLOR_RESET} ${COLOR_DIM}Workspace:${COLOR_RESET} ${COLOR_YELLOW}$PROGRESS_WORKSPACE_PATH${COLOR_RESET}"
    fi

    echo "${COLOR_BOLD}║${COLOR_RESET}"

    # Overall progress
    local overall_pct=0
    if [[ $PROGRESS_TOTAL_STORIES -gt 0 ]]; then
        overall_pct=$((PROGRESS_COMPLETED_STORIES * 100 / PROGRESS_TOTAL_STORIES))
    fi
    echo -n "${COLOR_BOLD}║${COLOR_RESET} Overall Progress: "
    render_progress_bar "$PROGRESS_COMPLETED_STORIES" "$PROGRESS_TOTAL_STORIES" 30
    echo " ($PROGRESS_COMPLETED_STORIES/$PROGRESS_TOTAL_STORIES stories)"

    # Time tracking
    local elapsed=$(format_duration $(($(get_timestamp_ms) - PROGRESS_START_TIME)))
    local remaining=$(estimate_remaining_time)
    echo "${COLOR_BOLD}║${COLOR_RESET} Time: ${COLOR_GREEN}$elapsed${COLOR_RESET} elapsed | ${COLOR_YELLOW}~$remaining${COLOR_RESET} remaining"

    # Current action
    if [[ -n "$PROGRESS_CURRENT_ACTION" ]]; then
        echo "${COLOR_BOLD}║${COLOR_RESET} ${COLOR_DIM}Currently: $PROGRESS_CURRENT_ACTION${COLOR_RESET}"
    else
        echo "${COLOR_BOLD}║${COLOR_RESET}"
    fi

    # Acceptance criteria checklist
    echo "${COLOR_BOLD}║${COLOR_RESET}"
    echo "${COLOR_BOLD}║${COLOR_RESET} ${COLOR_BLUE}Acceptance Criteria:${COLOR_RESET}"

    local done_count=0
    for i in "${!PROGRESS_ACCEPTANCE_CRITERIA[@]}"; do
        local status="${PROGRESS_CRITERIA_STATUS[$i]}"
        local symbol="$SYMBOL_PENDING"

        case "$status" in
            done)
                symbol="$SYMBOL_DONE"
                done_count=$((done_count + 1))
                ;;
            in_progress)
                symbol="$SYMBOL_IN_PROGRESS"
                ;;
            pending)
                symbol="$SYMBOL_PENDING"
                ;;
        esac

        # Truncate criterion if too long
        local criterion="${PROGRESS_ACCEPTANCE_CRITERIA[$i]}"
        local max_len=$((PROGRESS_TERMINAL_WIDTH - 10))
        if [[ ${#criterion} -gt $max_len ]]; then
            criterion="${criterion:0:$max_len}..."
        fi

        echo "${COLOR_BOLD}║${COLOR_RESET}   $symbol $criterion"
    done

    echo "${COLOR_BOLD}╚════════════════════════════════════════════════════════════════╝${COLOR_RESET}"
    echo ""
}

# ============================================================================
# Simple Progress Logging (fallback for non-TTY)
# ============================================================================

# Log progress message (for non-TTY environments)
log_progress() {
    local message="$1"

    if ! is_progress_enabled; then
        return 0
    fi

    # If not a TTY, just print the message
    if [[ ! -t 1 ]]; then
        echo "[PROGRESS] $message"
    fi
}

# ============================================================================
# Main Function (for testing)
# ============================================================================

if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    # Test mode
    echo "Testing progress indicators..."

    init_progress "prd.json"

    # Simulate a story
    start_story "US-001" "Test Story" \
        "Create lib/progress-indicators.sh" \
        "Add real-time acceptance criteria checklist" \
        "Implement visual progress bar" \
        "Add time tracking"

    sleep 2
    set_current_action "Creating progress indicators file"
    mark_criterion_in_progress 0
    sleep 2

    mark_criterion_done 0
    set_current_action "Implementing checklist display"
    mark_criterion_in_progress 1
    sleep 2

    mark_criterion_done 1
    set_current_action "Adding progress bar"
    mark_criterion_in_progress 2
    sleep 2

    mark_criterion_done 2
    mark_criterion_done 3
    complete_story

    echo "Test complete!"
fi
