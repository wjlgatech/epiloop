#!/bin/bash
#
# safety-checker.sh - Checkpoint Confirmation System for claude-loop
#
# Detects destructive operations and prompts for user approval before execution.
# Features:
# - File deletion detection (rm, git rm, diff analysis)
# - Major refactor detection (renames, large deletions, directory restructuring)
# - Sensitive file modification detection (.env, credentials, keys, config)
# - Confirmation prompts with batch operations (y/n/a/q)
# - Multiple safety levels (paranoid/cautious/normal/yolo)
# - Audit logging to .claude-loop/safety-log.jsonl
# - Custom safety rules via .claude-loop/safety-rules.json
#
# Usage (as library):
#   source lib/safety-checker.sh
#   init_safety_checker "cautious" "$non_interactive"
#   check_file_deletion "/path/to/file"
#   request_confirmation "delete" "Deleting critical file: config.json"
#
# Usage (standalone):
#   ./lib/safety-checker.sh check-diff "path/to/diff.txt"
#   ./lib/safety-checker.sh check-file "path/to/file"
#

set -euo pipefail

# ============================================================================
# Configuration
# ============================================================================

# Safety configuration (set by init_safety_checker or from environment)
SAFETY_LEVEL="${SAFETY_LEVEL:-normal}"  # paranoid, cautious, normal, yolo
SAFETY_NON_INTERACTIVE="${SAFETY_NON_INTERACTIVE:-false}"
SAFETY_DRY_RUN="${SAFETY_DRY_RUN:-false}"
SAFETY_LOG_FILE="${SAFETY_LOG_FILE:-.claude-loop/safety-log.jsonl}"
SAFETY_RULES_FILE="${SAFETY_RULES_FILE:-.claude-loop/safety-rules.json}"
SAFETY_APPROVED_ALL="${SAFETY_APPROVED_ALL:-false}"  # "yes to all" flag

# Colors for output
SC_RED='\033[0;31m'
SC_GREEN='\033[0;32m'
SC_YELLOW='\033[1;33m'
SC_BLUE='\033[0;34m'
SC_CYAN='\033[0;36m'
SC_NC='\033[0m'

# ============================================================================
# Helper Functions
# ============================================================================

sc_log_info() {
    echo -e "${SC_BLUE}[SAFETY]${SC_NC} $1" >&2
}

sc_log_success() {
    echo -e "${SC_GREEN}[SAFETY]${SC_NC} $1" >&2
}

sc_log_warn() {
    echo -e "${SC_YELLOW}[SAFETY]${SC_NC} $1" >&2
}

sc_log_error() {
    echo -e "${SC_RED}[SAFETY]${SC_NC} $1" >&2
}

sc_log_checkpoint() {
    echo -e "${SC_CYAN}[CHECKPOINT]${SC_NC} $1" >&2
}

# ============================================================================
# Safety Checker Initialization
# ============================================================================

# Initialize safety checker
# Usage: init_safety_checker "cautious" "false" "false"
init_safety_checker() {
    local level="${1:-normal}"
    local non_interactive="${2:-false}"
    local dry_run="${3:-false}"

    SAFETY_LEVEL="$level"
    SAFETY_NON_INTERACTIVE="$non_interactive"
    SAFETY_DRY_RUN="$dry_run"

    # Create log directory if needed
    local log_dir
    log_dir="$(dirname "$SAFETY_LOG_FILE")"
    mkdir -p "$log_dir"

    # Load custom rules if they exist
    load_safety_rules

    sc_log_info "Initialized safety checker"
    sc_log_info "  Safety Level: $SAFETY_LEVEL"
    sc_log_info "  Non-Interactive: $SAFETY_NON_INTERACTIVE"
    sc_log_info "  Dry Run: $SAFETY_DRY_RUN"
    sc_log_info "  Log File: $SAFETY_LOG_FILE"
}

# Load custom safety rules from JSON file
load_safety_rules() {
    if [ -f "$SAFETY_RULES_FILE" ]; then
        sc_log_info "Loaded custom safety rules from $SAFETY_RULES_FILE"
    fi
}

# Get safety level
get_safety_level() {
    echo "$SAFETY_LEVEL"
}

# Check if safety checker is in dry-run mode
is_dry_run() {
    [ "$SAFETY_DRY_RUN" = "true" ]
}

# Check if running in non-interactive mode
is_non_interactive() {
    [ "$SAFETY_NON_INTERACTIVE" = "true" ]
}

# ============================================================================
# Sensitive File Patterns
# ============================================================================

# List of sensitive file patterns (regex)
get_sensitive_patterns() {
    local patterns=(
        "\.env$"
        "\.env\."
        "credentials"
        "secret"
        "password"
        "\.pem$"
        "\.key$"
        "\.p12$"
        "\.pfx$"
        "id_rsa"
        "id_dsa"
        "id_ecdsa"
        "id_ed25519"
        "\.aws/credentials"
        "\.ssh/config"
        "config\.json$"
        "secrets\.yaml$"
        "secrets\.yml$"
        "\.npmrc"
        "\.pypirc"
        "\.dockercfg"
        "\.docker/config\.json"
    )

    # Add custom patterns from safety rules
    if [ -f "$SAFETY_RULES_FILE" ]; then
        local custom_patterns
        custom_patterns=$(jq -r '.sensitive_patterns[]? // empty' "$SAFETY_RULES_FILE" 2>/dev/null || true)
        if [ -n "$custom_patterns" ]; then
            while IFS= read -r pattern; do
                patterns+=("$pattern")
            done <<< "$custom_patterns"
        fi
    fi

    printf '%s\n' "${patterns[@]}"
}

# Check if file matches sensitive pattern
is_sensitive_file() {
    local file="$1"
    local basename
    basename=$(basename "$file")

    while IFS= read -r pattern; do
        if echo "$basename" | grep -qE "$pattern" 2>/dev/null; then
            return 0
        fi
    done < <(get_sensitive_patterns)

    return 1
}

# ============================================================================
# Destructive Operation Detection
# ============================================================================

# Detect file deletions in git diff
# Returns: list of deleted files (one per line)
detect_file_deletions() {
    local diff_file="$1"

    if [ ! -f "$diff_file" ]; then
        return 0
    fi

    # Parse git diff for deleted files
    grep "^--- a/" "$diff_file" 2>/dev/null | while read -r line; do
        local file="${line#--- a/}"
        # Check if this is a deletion (followed by /dev/null)
        if grep -q "^+++ /dev/null" "$diff_file"; then
            echo "$file"
        fi
    done
}

# Detect major refactors (file renames, large deletions)
# Returns: JSON object with refactor details
detect_major_refactors() {
    local diff_file="$1"
    local threshold="${2:-50}"  # lines deleted threshold

    if [ ! -f "$diff_file" ]; then
        echo "[]"
        return 0
    fi

    local refactors=()

    # Detect file renames
    local renames
    renames=$(grep "^rename from\|^rename to" "$diff_file" 2>/dev/null | paste -d ' ' - - | sed 's/rename from //;s/rename to //' || true)
    if [ -n "$renames" ]; then
        while IFS= read -r rename; do
            local from to
            from=$(echo "$rename" | awk '{print $1}')
            to=$(echo "$rename" | awk '{print $2}')
            refactors+=("{\"type\":\"rename\",\"from\":\"$from\",\"to\":\"$to\"}")
        done <<< "$renames"
    fi

    # Detect large deletions
    local current_file=""
    local deletion_count=0

    while IFS= read -r line; do
        if [[ "$line" =~ ^---\ a/(.+) ]]; then
            # New file diff section
            if [ -n "$current_file" ] && [ "$deletion_count" -ge "$threshold" ]; then
                refactors+=("{\"type\":\"large_deletion\",\"file\":\"$current_file\",\"lines\":$deletion_count}")
            fi
            current_file="${BASH_REMATCH[1]}"
            deletion_count=0
        elif [[ "$line" =~ ^- ]]; then
            ((deletion_count++)) || true
        fi
    done < "$diff_file"

    # Check last file
    if [ -n "$current_file" ] && [ "$deletion_count" -ge "$threshold" ]; then
        refactors+=("{\"type\":\"large_deletion\",\"file\":\"$current_file\",\"lines\":$deletion_count}")
    fi

    # Output as JSON array
    if [ ${#refactors[@]} -gt 0 ]; then
        echo "[$(IFS=,; echo "${refactors[*]}")]"
    else
        echo "[]"
    fi
}

# Detect directory restructuring
detect_directory_restructuring() {
    local diff_file="$1"

    if [ ! -f "$diff_file" ]; then
        return 1
    fi

    # Count number of files being moved/renamed
    local move_count
    move_count=$(grep -c "^rename from" "$diff_file" 2>/dev/null || echo 0)

    # If more than 5 files are being renamed, it's likely a restructure
    if [ "$move_count" -ge 5 ]; then
        return 0
    fi

    return 1
}

# ============================================================================
# Confirmation System
# ============================================================================

# Log confirmation request to audit log
log_confirmation() {
    local action="$1"
    local description="$2"
    local decision="$3"  # approved, rejected, skipped

    if [ "$SAFETY_DRY_RUN" = "true" ]; then
        return 0
    fi

    local timestamp
    timestamp=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

    local log_entry
    log_entry=$(jq -n \
        --arg ts "$timestamp" \
        --arg act "$action" \
        --arg desc "$description" \
        --arg dec "$decision" \
        --arg level "$SAFETY_LEVEL" \
        '{
            timestamp: $ts,
            action: $act,
            description: $desc,
            decision: $dec,
            safety_level: $level
        }')

    echo "$log_entry" >> "$SAFETY_LOG_FILE"
}

# Request user confirmation for an action
# Returns: 0 if approved, 1 if rejected, 2 if aborted
request_confirmation() {
    local action="$1"
    local description="$2"

    # Check if we should even ask based on safety level
    if ! should_request_confirmation "$action"; then
        log_confirmation "$action" "$description" "skipped"
        return 0
    fi

    # In non-interactive mode, treat as approved
    if [ "$SAFETY_NON_INTERACTIVE" = "true" ]; then
        log_confirmation "$action" "$description" "approved_auto"
        return 0
    fi

    # Check "approve all" flag
    if [ "$SAFETY_APPROVED_ALL" = "true" ]; then
        log_confirmation "$action" "$description" "approved_all"
        return 0
    fi

    # Dry run mode: show what would be confirmed
    if [ "$SAFETY_DRY_RUN" = "true" ]; then
        sc_log_checkpoint "[DRY-RUN] Would request confirmation:"
        echo -e "  ${SC_YELLOW}Action:${SC_NC} $action"
        echo -e "  ${SC_YELLOW}Description:${SC_NC} $description"
        return 0
    fi

    # Pause progress indicators if enabled
    if declare -f pause_progress >/dev/null 2>&1; then
        pause_progress
    fi

    # Show confirmation prompt
    sc_log_checkpoint "Confirmation required:"
    echo -e "  ${SC_YELLOW}Action:${SC_NC} $action" >&2
    echo -e "  ${SC_YELLOW}Description:${SC_NC} $description" >&2
    echo >&2

    # Prompt for confirmation
    while true; do
        echo -n -e "${SC_CYAN}Approve this action? [y/n/a/q]:${SC_NC} " >&2
        read -r response

        case "$response" in
            y|Y|yes|Yes|YES)
                log_confirmation "$action" "$description" "approved"
                sc_log_success "Action approved"
                # Resume progress indicators
                if declare -f resume_progress >/dev/null 2>&1; then
                    resume_progress
                fi
                return 0
                ;;
            n|N|no|No|NO)
                log_confirmation "$action" "$description" "rejected"
                sc_log_warn "Action rejected"
                # Resume progress indicators
                if declare -f resume_progress >/dev/null 2>&1; then
                    resume_progress
                fi
                return 1
                ;;
            a|A|all|All|ALL)
                SAFETY_APPROVED_ALL=true
                log_confirmation "$action" "$description" "approved_all"
                sc_log_success "Action approved (and all future actions)"
                # Resume progress indicators
                if declare -f resume_progress >/dev/null 2>&1; then
                    resume_progress
                fi
                return 0
                ;;
            q|Q|quit|Quit|QUIT)
                log_confirmation "$action" "$description" "aborted"
                sc_log_error "Aborted by user"
                # Resume progress indicators
                if declare -f resume_progress >/dev/null 2>&1; then
                    resume_progress
                fi
                return 2
                ;;
            *)
                echo -e "${SC_YELLOW}Invalid response. Please enter y (yes), n (no), a (approve all), or q (quit)${SC_NC}" >&2
                ;;
        esac
    done
}

# Determine if confirmation should be requested based on safety level and action type
should_request_confirmation() {
    local action="$1"

    case "$SAFETY_LEVEL" in
        yolo)
            # Never request confirmation
            return 1
            ;;
        normal)
            # Only confirm sensitive file modifications
            if [ "$action" = "modify_sensitive" ] || [ "$action" = "delete_sensitive" ]; then
                return 0
            fi
            return 1
            ;;
        cautious)
            # Confirm destructive operations and sensitive modifications
            if [[ "$action" =~ ^(delete|modify_sensitive|delete_sensitive|major_refactor|directory_restructure)$ ]]; then
                return 0
            fi
            return 1
            ;;
        paranoid)
            # Confirm everything
            return 0
            ;;
        *)
            # Unknown level, default to cautious
            sc_log_warn "Unknown safety level: $SAFETY_LEVEL, defaulting to cautious"
            SAFETY_LEVEL="cautious"
            should_request_confirmation "$action"
            ;;
    esac
}

# ============================================================================
# High-Level Check Functions
# ============================================================================

# Check a git diff file for destructive operations
check_diff() {
    local diff_file="$1"

    if [ ! -f "$diff_file" ]; then
        sc_log_error "Diff file not found: $diff_file"
        return 1
    fi

    sc_log_info "Analyzing diff: $diff_file"

    local has_issues=false

    # Check for file deletions
    local deletions
    deletions=$(detect_file_deletions "$diff_file")
    if [ -n "$deletions" ]; then
        sc_log_warn "Detected file deletions:"
        while IFS= read -r file; do
            echo "  - $file" >&2
            if is_sensitive_file "$file"; then
                if ! request_confirmation "delete_sensitive" "Deleting sensitive file: $file"; then
                    has_issues=true
                fi
            else
                if ! request_confirmation "delete" "Deleting file: $file"; then
                    has_issues=true
                fi
            fi
        done <<< "$deletions"
    fi

    # Check for major refactors
    local refactors
    refactors=$(detect_major_refactors "$diff_file")
    if [ "$refactors" != "[]" ]; then
        sc_log_warn "Detected major refactors:"
        echo "$refactors" | jq -r '.[] | "  - \(.type): \(.file // "")\(.from // "") -> \(.to // "") (\(.lines // 0) lines)"' >&2
        if ! request_confirmation "major_refactor" "Major code refactoring detected"; then
            has_issues=true
        fi
    fi

    # Check for directory restructuring
    if detect_directory_restructuring "$diff_file"; then
        sc_log_warn "Detected directory restructuring"
        if ! request_confirmation "directory_restructure" "Multiple files being moved/renamed"; then
            has_issues=true
        fi
    fi

    # Check for sensitive file modifications
    local sensitive_files
    sensitive_files=$(grep "^--- a/" "$diff_file" 2>/dev/null | sed 's/^--- a\///' || true)
    if [ -n "$sensitive_files" ]; then
        while IFS= read -r file; do
            if is_sensitive_file "$file"; then
                sc_log_warn "Modifying sensitive file: $file"
                if ! request_confirmation "modify_sensitive" "Modifying sensitive file: $file"; then
                    has_issues=true
                fi
            fi
        done <<< "$sensitive_files"
    fi

    if [ "$has_issues" = "true" ]; then
        return 1
    fi

    sc_log_success "Safety check passed"
    return 0
}

# Check a specific file for sensitive content
check_file() {
    local file="$1"

    if ! is_sensitive_file "$file"; then
        return 0
    fi

    sc_log_warn "File is marked as sensitive: $file"
    request_confirmation "modify_sensitive" "Accessing sensitive file: $file"
}

# ============================================================================
# CLI Interface
# ============================================================================

show_help() {
    cat << EOF
Safety Checker - Checkpoint Confirmation System

Usage:
  $0 <command> [options]

Commands:
  check-diff <file>       Analyze a git diff file for destructive operations
  check-file <file>       Check if a file is sensitive
  is-sensitive <file>     Return 0 if file is sensitive, 1 otherwise
  list-patterns           List all sensitive file patterns
  init <level>            Initialize with safety level
  help                    Show this help message

Safety Levels:
  paranoid    Confirm all operations
  cautious    Confirm destructive operations and sensitive modifications (default)
  normal      Confirm only sensitive file modifications
  yolo        No confirmations

Options:
  --non-interactive       Run in non-interactive mode (auto-approve)
  --dry-run              Show what would be confirmed without executing

Environment Variables:
  SAFETY_LEVEL            Safety level (paranoid/cautious/normal/yolo)
  SAFETY_NON_INTERACTIVE  Non-interactive mode (true/false)
  SAFETY_DRY_RUN          Dry-run mode (true/false)
  SAFETY_LOG_FILE         Path to audit log file
  SAFETY_RULES_FILE       Path to custom rules JSON file

Examples:
  # Check a diff file
  $0 check-diff /tmp/changes.diff

  # Check if file is sensitive
  $0 is-sensitive .env && echo "Sensitive!"

  # List sensitive patterns
  $0 list-patterns

  # Initialize with paranoid mode
  $0 init paranoid

  # Dry-run mode
  SAFETY_DRY_RUN=true $0 check-diff /tmp/changes.diff

EOF
}

main() {
    local command="${1:-help}"
    shift || true

    case "$command" in
        check-diff)
            if [ $# -lt 1 ]; then
                sc_log_error "Usage: $0 check-diff <file>"
                exit 1
            fi
            init_safety_checker "$SAFETY_LEVEL" "$SAFETY_NON_INTERACTIVE" "$SAFETY_DRY_RUN"
            check_diff "$1"
            ;;
        check-file)
            if [ $# -lt 1 ]; then
                sc_log_error "Usage: $0 check-file <file>"
                exit 1
            fi
            init_safety_checker "$SAFETY_LEVEL" "$SAFETY_NON_INTERACTIVE" "$SAFETY_DRY_RUN"
            check_file "$1"
            ;;
        is-sensitive)
            if [ $# -lt 1 ]; then
                sc_log_error "Usage: $0 is-sensitive <file>"
                exit 1
            fi
            init_safety_checker "$SAFETY_LEVEL" "$SAFETY_NON_INTERACTIVE" "$SAFETY_DRY_RUN"
            is_sensitive_file "$1"
            ;;
        list-patterns)
            init_safety_checker "$SAFETY_LEVEL" "$SAFETY_NON_INTERACTIVE" "$SAFETY_DRY_RUN"
            get_sensitive_patterns
            ;;
        init)
            local level="${1:-normal}"
            init_safety_checker "$level" "$SAFETY_NON_INTERACTIVE" "$SAFETY_DRY_RUN"
            ;;
        help|--help|-h)
            show_help
            ;;
        *)
            sc_log_error "Unknown command: $command"
            show_help
            exit 1
            ;;
    esac
}

# Only run main if script is executed directly (not sourced)
if [ "${BASH_SOURCE[0]}" = "${0}" ]; then
    main "$@"
fi
