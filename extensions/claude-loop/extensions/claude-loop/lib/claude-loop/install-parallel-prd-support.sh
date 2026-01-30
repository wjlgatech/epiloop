#!/bin/bash
#
# install-parallel-prd-support.sh
#
# Installs parallel PRD execution support into claude-loop
# Enables running multiple PRDs with different branches simultaneously
#

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CLAUDE_LOOP_SCRIPT="${SCRIPT_DIR}/claude-loop.sh"
PARALLEL_MANAGER="${SCRIPT_DIR}/lib/parallel-prd-manager.sh"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check prerequisites
check_prerequisites() {
    log_info "Checking prerequisites..."

    if [ ! -f "$CLAUDE_LOOP_SCRIPT" ]; then
        log_error "claude-loop.sh not found at: $CLAUDE_LOOP_SCRIPT"
        exit 1
    fi

    if ! command -v git &>/dev/null; then
        log_error "git is required but not installed"
        exit 1
    fi

    if ! command -v jq &>/dev/null; then
        log_error "jq is required but not installed"
        exit 1
    fi

    # Check git version (worktree support added in git 2.5+)
    local git_version
    git_version=$(git --version | awk '{print $3}')
    local git_major
    git_major=$(echo "$git_version" | cut -d'.' -f1)
    local git_minor
    git_minor=$(echo "$git_version" | cut -d'.' -f2)

    if [ "$git_major" -lt 2 ] || { [ "$git_major" -eq 2 ] && [ "$git_minor" -lt 5 ]; }; then
        log_warn "Git version $git_version detected. Git 2.5+ required for worktree support."
        log_warn "Sequential queueing will be used instead of parallel execution."
    fi

    log_success "Prerequisites check passed"
}

# Backup original claude-loop.sh
backup_claude_loop() {
    local backup_file="${CLAUDE_LOOP_SCRIPT}.backup.$(date +%Y%m%d_%H%M%S)"

    log_info "Backing up claude-loop.sh to: $backup_file"
    cp "$CLAUDE_LOOP_SCRIPT" "$backup_file"

    log_success "Backup created"
}

# Add integration code to claude-loop.sh
integrate_parallel_support() {
    log_info "Integrating parallel PRD support into claude-loop.sh..."

    # Create temp file for modified script
    local temp_script="${CLAUDE_LOOP_SCRIPT}.temp"

    # Read original script
    local original_script
    original_script=$(cat "$CLAUDE_LOOP_SCRIPT")

    # Find insertion points
    local config_section_line
    config_section_line=$(grep -n "^# Autonomous Mode" "$CLAUDE_LOOP_SCRIPT" | head -1 | cut -d':' -f1)

    if [ -z "$config_section_line" ]; then
        log_error "Could not find configuration section in claude-loop.sh"
        exit 1
    fi

    # Insert parallel PRD configuration
    {
        head -n "$config_section_line" "$CLAUDE_LOOP_SCRIPT"
        cat << 'EOF'

# Parallel PRD Execution Management (handles multiple PRDs with different branches)
PARALLEL_PRD_MANAGER="${SCRIPT_DIR}/lib/parallel-prd-manager.sh"
PARALLEL_PRD_ENABLED=true
FORCE_SEQUENTIAL=false
WORKTREE_PATH="NONE"
LOCK_FILE=""

EOF
        tail -n +"$((config_section_line + 1))" "$CLAUDE_LOOP_SCRIPT"
    } > "$temp_script"

    # Find main execution section
    local main_section_line
    main_section_line=$(grep -n "^# Main execution loop" "$temp_script" | head -1 | cut -d':' -f1)

    if [ -n "$main_section_line" ]; then
        # Insert parallel execution handler before main loop
        {
            head -n "$((main_section_line - 1))" "$temp_script"
            cat << 'EOF'

# ============================================================================
# Parallel PRD Execution Handler
# ============================================================================

source_parallel_prd_manager() {
    if [ "$PARALLEL_PRD_ENABLED" = true ] && [ -f "$PARALLEL_PRD_MANAGER" ]; then
        source "$PARALLEL_PRD_MANAGER"
        return 0
    fi
    return 1
}

handle_parallel_prd_execution() {
    local prd_file="$1"
    local target_branch="$2"

    if ! source_parallel_prd_manager; then
        return 0
    fi

    local result
    result=$(handle_parallel_execution "$prd_file" "$target_branch" "$FORCE_SEQUENTIAL")
    local exit_code=$?

    case "$result" in
        NO_CONFLICT)
            log_info "No parallel execution conflicts"
            WORKTREE_PATH="NONE"
            LOCK_FILE=$(acquire_lock "$prd_file" "$target_branch")
            ;;

        WORKTREE:*)
            WORKTREE_PATH="${result#WORKTREE:}"
            log_success "Created worktree: $WORKTREE_PATH"
            cd "$WORKTREE_PATH"
            PRD_FILE="$prd_file"
            LOCK_FILE=$(acquire_lock "$prd_file" "$target_branch")
            ;;

        QUEUED:*)
            local queue_position="${result#QUEUED:}"
            log_warn "Queued for execution (position: $queue_position)"
            while [ "$(get_queue_size)" -gt 0 ]; do
                sleep 5
            done
            handle_parallel_prd_execution "$prd_file" "$target_branch"
            return $?
            ;;
    esac

    trap "cleanup_on_exit '$LOCK_FILE' '$WORKTREE_PATH'" EXIT INT TERM
}

EOF
            tail -n +"$main_section_line" "$temp_script"
        } > "${temp_script}.2"
        mv "${temp_script}.2" "$temp_script"
    fi

    # Replace original script
    mv "$temp_script" "$CLAUDE_LOOP_SCRIPT"
    chmod +x "$CLAUDE_LOOP_SCRIPT"

    log_success "Integration complete"
}

# Add new CLI options
add_cli_options() {
    log_info "Adding CLI options for parallel execution..."

    # Check if options already exist
    if grep -q "\\-\\-parallel-status" "$CLAUDE_LOOP_SCRIPT"; then
        log_info "CLI options already exist, skipping"
        return
    fi

    # Find help section
    local help_section_line
    help_section_line=$(grep -n "show_usage()" "$CLAUDE_LOOP_SCRIPT" | head -1 | cut -d':' -f1)

    if [ -n "$help_section_line" ]; then
        local temp_script="${CLAUDE_LOOP_SCRIPT}.temp"

        {
            head -n "$((help_section_line + 50))" "$CLAUDE_LOOP_SCRIPT"
            cat << 'EOF'
    echo "PARALLEL PRD EXECUTION:"
    echo "    --parallel-status       Show status of parallel PRD executions"
    echo "    --force-sequential      Disable worktrees, force sequential queuing"
    echo ""
EOF
            tail -n +"$((help_section_line + 51))" "$CLAUDE_LOOP_SCRIPT"
        } > "$temp_script"

        mv "$temp_script" "$CLAUDE_LOOP_SCRIPT"
        chmod +x "$CLAUDE_LOOP_SCRIPT"
    fi

    log_success "CLI options added"
}

# Test installation
test_installation() {
    log_info "Testing installation..."

    # Check if parallel manager exists
    if [ ! -f "$PARALLEL_MANAGER" ]; then
        log_error "parallel-prd-manager.sh not found"
        return 1
    fi

    # Source it to check for syntax errors
    if bash -n "$PARALLEL_MANAGER"; then
        log_success "Parallel manager syntax check passed"
    else
        log_error "Parallel manager has syntax errors"
        return 1
    fi

    # Check if claude-loop.sh still works
    if bash -n "$CLAUDE_LOOP_SCRIPT"; then
        log_success "claude-loop.sh syntax check passed"
    else
        log_error "claude-loop.sh has syntax errors after integration"
        return 1
    fi

    log_success "Installation test passed"
}

# Main installation flow
main() {
    echo ""
    echo "============================================================"
    echo "  Parallel PRD Execution Support Installer"
    echo "============================================================"
    echo ""

    check_prerequisites
    echo ""

    backup_claude_loop
    echo ""

    integrate_parallel_support
    echo ""

    add_cli_options
    echo ""

    test_installation
    echo ""

    log_success "Installation complete!"
    echo ""
    echo "New features:"
    echo "  • Automatic detection of parallel PRD execution"
    echo "  • Git worktree support for true parallel execution"
    echo "  • Sequential queueing as fallback"
    echo "  • Automatic cleanup of worktrees and locks"
    echo ""
    echo "Usage:"
    echo "  ./claude-loop.sh --prd prd-dev-environment.json &"
    echo "  ./claude-loop.sh --prd prd-edge-cloud-inference.json &"
    echo "  ./claude-loop.sh --prd prd-future-improvements.json &"
    echo ""
    echo "  ./claude-loop.sh --parallel-status  # Check running PRDs"
    echo ""
    echo "To rollback: restore from backup file"
    echo ""
}

main "$@"
