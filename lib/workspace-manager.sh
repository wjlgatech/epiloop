#!/bin/bash
#
# workspace-manager.sh - Workspace Sandboxing for claude-loop
#
# Implements workspace sandboxing to limit claude-loop execution scope to specific folders.
# Features:
# - Folder validation and safety checks
# - Workspace mounting in worker directories
# - Auto-inference of fileScope from workspace contents
# - Strict and permissive modes
#
# Usage (as library):
#   source lib/workspace-manager.sh
#   init_workspace "lib,src" "strict"
#   validate_file_access "/path/to/file"
#
# Usage (standalone):
#   ./lib/workspace-manager.sh validate "lib,src"
#   ./lib/workspace-manager.sh infer-scope "lib,src" "prd.json"
#

set -euo pipefail

# ============================================================================
# Configuration
# ============================================================================

# Workspace configuration (set by init_workspace or from environment)
WORKSPACE_FOLDERS="${WORKSPACE_FOLDERS:-}"
WORKSPACE_MODE="${WORKSPACE_MODE:-permissive}"  # strict or permissive
WORKSPACE_REPO_ROOT="${WORKSPACE_REPO_ROOT:-}"

# Colors for output
WS_RED='\033[0;31m'
WS_GREEN='\033[0;32m'
WS_YELLOW='\033[1;33m'
WS_BLUE='\033[0;34m'
WS_NC='\033[0m'

# ============================================================================
# Helper Functions
# ============================================================================

ws_log_info() {
    echo -e "${WS_BLUE}[WORKSPACE]${WS_NC} $1" >&2
}

ws_log_success() {
    echo -e "${WS_GREEN}[WORKSPACE]${WS_NC} $1" >&2
}

ws_log_warn() {
    echo -e "${WS_YELLOW}[WORKSPACE]${WS_NC} $1" >&2
}

ws_log_error() {
    echo -e "${WS_RED}[WORKSPACE]${WS_NC} $1" >&2
}

# ============================================================================
# Workspace Initialization
# ============================================================================

# Initialize workspace manager
# Usage: init_workspace "lib,src,tests" "strict"
init_workspace() {
    local folders="$1"
    local mode="${2:-permissive}"

    WORKSPACE_FOLDERS="$folders"
    WORKSPACE_MODE="$mode"

    # Get repository root
    if git rev-parse --is-inside-work-tree &> /dev/null; then
        WORKSPACE_REPO_ROOT="$(git rev-parse --show-toplevel)"
    else
        WORKSPACE_REPO_ROOT="$(pwd)"
    fi

    ws_log_info "Initialized workspace manager"
    ws_log_info "  Folders: $WORKSPACE_FOLDERS"
    ws_log_info "  Mode: $WORKSPACE_MODE"
    ws_log_info "  Repo Root: $WORKSPACE_REPO_ROOT"
}

# Check if workspace is enabled
is_workspace_enabled() {
    [ -n "$WORKSPACE_FOLDERS" ]
}

# Get workspace mode
get_workspace_mode() {
    echo "$WORKSPACE_MODE"
}

# Get workspace folders as array
get_workspace_folders() {
    if [ -z "$WORKSPACE_FOLDERS" ]; then
        return
    fi

    # Split by comma and return as array
    echo "$WORKSPACE_FOLDERS" | tr ',' '\n'
}

# ============================================================================
# Folder Validation
# ============================================================================

# Validate that workspace folders exist and are within repo
# Returns: 0 if valid, 1 if invalid
validate_workspace_folders() {
    if [ -z "$WORKSPACE_FOLDERS" ]; then
        ws_log_warn "No workspace folders specified"
        return 0
    fi

    local invalid_folders=()
    local folders
    folders=$(get_workspace_folders)

    while IFS= read -r folder; do
        # Skip empty lines
        [ -z "$folder" ] && continue

        # Resolve relative path
        local abs_path
        if [[ "$folder" = /* ]]; then
            abs_path="$folder"
        else
            abs_path="$WORKSPACE_REPO_ROOT/$folder"
        fi

        # Check if folder exists
        if [ ! -d "$abs_path" ]; then
            ws_log_error "Workspace folder does not exist: $folder (resolved: $abs_path)"
            invalid_folders+=("$folder")
            continue
        fi

        # Check if folder is within repo (resolve symlinks)
        local real_path
        real_path="$(cd "$abs_path" && pwd -P)"
        if [[ ! "$real_path" =~ ^"$WORKSPACE_REPO_ROOT" ]]; then
            ws_log_error "Workspace folder is outside repository: $folder"
            ws_log_error "  Real path: $real_path"
            ws_log_error "  Repo root: $WORKSPACE_REPO_ROOT"
            invalid_folders+=("$folder")
            continue
        fi

        ws_log_success "Validated workspace folder: $folder"
    done <<< "$folders"

    if [ ${#invalid_folders[@]} -gt 0 ]; then
        ws_log_error "Validation failed for ${#invalid_folders[@]} folder(s)"
        return 1
    fi

    ws_log_success "All workspace folders validated"
    return 0
}

# Check if a file path is within workspace boundaries
# Usage: is_file_in_workspace "/path/to/file.ts"
# Returns: 0 if in workspace, 1 if not
is_file_in_workspace() {
    local file_path="$1"

    # If workspace not enabled, all files are allowed
    if ! is_workspace_enabled; then
        return 0
    fi

    # Resolve to absolute path
    local abs_path
    if [[ "$file_path" = /* ]]; then
        abs_path="$file_path"
    else
        abs_path="$WORKSPACE_REPO_ROOT/$file_path"
    fi

    # Normalize path (remove .., ., etc.)
    abs_path="$(cd "$(dirname "$abs_path")" 2>/dev/null && pwd)/$(basename "$abs_path")" || abs_path="$abs_path"

    # Check each workspace folder
    local folders
    folders=$(get_workspace_folders)

    while IFS= read -r folder; do
        [ -z "$folder" ] && continue

        # Resolve workspace folder to absolute path
        local ws_abs_path
        if [[ "$folder" = /* ]]; then
            ws_abs_path="$folder"
        else
            ws_abs_path="$WORKSPACE_REPO_ROOT/$folder"
        fi

        # Normalize workspace path
        ws_abs_path="$(cd "$ws_abs_path" 2>/dev/null && pwd -P)" || continue

        # Check if file is within this workspace folder
        if [[ "$abs_path" =~ ^"$ws_abs_path" ]]; then
            return 0
        fi
    done <<< "$folders"

    return 1
}

# Validate file access according to workspace mode
# Usage: validate_file_access "/path/to/file.ts" "read"
# Returns: 0 if allowed, 1 if blocked
validate_file_access() {
    local file_path="$1"
    local operation="${2:-read}"  # read, write, delete

    # If workspace not enabled, all access is allowed
    if ! is_workspace_enabled; then
        return 0
    fi

    # Check if file is in workspace
    if is_file_in_workspace "$file_path"; then
        return 0
    fi

    # File is outside workspace
    local mode
    mode=$(get_workspace_mode)

    if [ "$mode" = "strict" ]; then
        ws_log_error "BLOCKED: File access outside workspace"
        ws_log_error "  File: $file_path"
        ws_log_error "  Operation: $operation"
        ws_log_error "  Workspace folders: $WORKSPACE_FOLDERS"
        return 1
    else
        ws_log_warn "WARNING: File access outside workspace (permissive mode)"
        ws_log_warn "  File: $file_path"
        ws_log_warn "  Operation: $operation"
        return 0
    fi
}

# ============================================================================
# Source Repository Cloning
# ============================================================================

# Clone source repository into workspace directory
# Usage: clone_source_to_workspace "/path/to/source" "/path/to/workspace"
# Returns: 0 if successful or skipped, 1 if error
clone_source_to_workspace() {
    local source_path="$1"
    local workspace_dir="$2"

    # Skip if source_path is null or empty
    if [ -z "$source_path" ] || [ "$source_path" = "null" ]; then
        ws_log_info "No source project specified, skipping clone"
        return 0
    fi

    # Resolve source path (handle relative paths)
    local resolved_source
    if [[ "$source_path" = /* ]]; then
        resolved_source="$source_path"
    else
        resolved_source="$WORKSPACE_REPO_ROOT/$source_path"
    fi

    # Validate source path exists
    if [ ! -d "$resolved_source" ]; then
        ws_log_error "Source path does not exist: $source_path (resolved: $resolved_source)"
        ws_log_warn "Continuing without source clone"
        return 0  # Don't fail the entire execution
    fi

    # Skip if destination already has content (resume scenario)
    if [ -d "$workspace_dir" ] && [ "$(ls -A "$workspace_dir" 2>/dev/null)" ]; then
        ws_log_warn "Workspace directory already has content, skipping clone"
        ws_log_info "  Workspace: $workspace_dir"
        return 0
    fi

    ws_log_info "Cloning source repository into workspace"
    ws_log_info "  Source: $resolved_source"
    ws_log_info "  Destination: $workspace_dir"

    # Create workspace directory if it doesn't exist
    mkdir -p "$workspace_dir"

    # Copy files excluding .git directory
    # Use rsync for efficient copying with exclusions
    if command -v rsync &> /dev/null; then
        if rsync -a --exclude='.git' --exclude='.claude-loop' "$resolved_source/" "$workspace_dir/" 2>&1; then
            ws_log_success "Source cloned successfully using rsync"
            return 0
        else
            ws_log_error "rsync failed, falling back to cp"
        fi
    fi

    # Fallback to cp if rsync not available or failed
    if cp -R "$resolved_source/." "$workspace_dir/" 2>&1; then
        # Remove .git directory if it was copied
        if [ -d "$workspace_dir/.git" ]; then
            rm -rf "$workspace_dir/.git"
            ws_log_info "Removed .git directory from workspace"
        fi
        # Remove .claude-loop directory if it was copied
        if [ -d "$workspace_dir/.claude-loop" ]; then
            rm -rf "$workspace_dir/.claude-loop"
            ws_log_info "Removed .claude-loop directory from workspace"
        fi
        ws_log_success "Source cloned successfully using cp"
        return 0
    else
        ws_log_error "Failed to clone source repository"
        ws_log_warn "Continuing without source clone"
        return 0  # Don't fail the entire execution
    fi
}

# Read source_project from PRD
# Usage: get_source_project_from_prd "/path/to/prd.json"
# Returns: source_project value or empty string
get_source_project_from_prd() {
    local prd_file="$1"

    if [ ! -f "$prd_file" ]; then
        echo ""
        return
    fi

    if ! command -v jq &> /dev/null; then
        ws_log_warn "jq not available, cannot read source_project from PRD"
        echo ""
        return
    fi

    jq -r '.source_project // empty' "$prd_file" 2>/dev/null || echo ""
}

# ============================================================================
# Workspace Mounting (for Workers)
# ============================================================================

# Mount workspace folders in worker directory using symlinks
# Usage: mount_workspace_in_worker "/path/to/worker/dir"
mount_workspace_in_worker() {
    local worker_dir="$1"

    if ! is_workspace_enabled; then
        return 0
    fi

    ws_log_info "Mounting workspace in worker directory: $worker_dir"

    local folders
    folders=$(get_workspace_folders)

    while IFS= read -r folder; do
        [ -z "$folder" ] && continue

        # Resolve source path
        local source_path
        if [[ "$folder" = /* ]]; then
            source_path="$folder"
        else
            source_path="$WORKSPACE_REPO_ROOT/$folder"
        fi

        # Target path in worker directory
        local target_path="$worker_dir/$folder"

        # Create parent directories
        mkdir -p "$(dirname "$target_path")"

        # Create symlink
        if [ -e "$target_path" ]; then
            ws_log_warn "Target already exists: $target_path"
        else
            ln -s "$source_path" "$target_path"
            ws_log_success "Mounted: $folder -> $target_path"
        fi
    done <<< "$folders"

    ws_log_success "Workspace mounted in worker"
}

# Unmount workspace from worker directory
# Usage: unmount_workspace_from_worker "/path/to/worker/dir"
unmount_workspace_from_worker() {
    local worker_dir="$1"

    if ! is_workspace_enabled; then
        return 0
    fi

    ws_log_info "Unmounting workspace from worker directory: $worker_dir"

    local folders
    folders=$(get_workspace_folders)

    while IFS= read -r folder; do
        [ -z "$folder" ] && continue

        local target_path="$worker_dir/$folder"

        if [ -L "$target_path" ]; then
            rm "$target_path"
            ws_log_success "Unmounted: $target_path"
        fi
    done <<< "$folders"
}

# ============================================================================
# FileScope Auto-Inference
# ============================================================================

# Infer fileScope from workspace contents
# Usage: infer_file_scope_from_workspace
# Returns: JSON array of file patterns
infer_file_scope_from_workspace() {
    if ! is_workspace_enabled; then
        echo "[]"
        return
    fi

    local file_patterns=()
    local folders
    folders=$(get_workspace_folders)

    while IFS= read -r folder; do
        [ -z "$folder" ] && continue

        # Add glob patterns for common file types
        file_patterns+=("\"$folder/**/*.sh\"")
        file_patterns+=("\"$folder/**/*.js\"")
        file_patterns+=("\"$folder/**/*.ts\"")
        file_patterns+=("\"$folder/**/*.py\"")
        file_patterns+=("\"$folder/**/*.json\"")
        file_patterns+=("\"$folder/**/*.md\"")
        file_patterns+=("\"$folder/**/*.yaml\"")
        file_patterns+=("\"$folder/**/*.yml\"")

        # Also add the folder itself
        file_patterns+=("\"$folder/\"")
    done <<< "$folders"

    # Build JSON array
    local json="["
    local first=true
    for pattern in "${file_patterns[@]}"; do
        if [ "$first" = true ]; then
            first=false
        else
            json+=","
        fi
        json+="$pattern"
    done
    json+="]"

    echo "$json"
}

# Update PRD fileScope with workspace-inferred patterns
# Usage: update_prd_file_scope "prd.json"
update_prd_file_scope() {
    local prd_file="$1"

    if ! is_workspace_enabled; then
        ws_log_info "Workspace not enabled, skipping fileScope update"
        return 0
    fi

    if [ ! -f "$prd_file" ]; then
        ws_log_error "PRD file not found: $prd_file"
        return 1
    fi

    ws_log_info "Auto-inferring fileScope from workspace..."

    local inferred_scope
    inferred_scope=$(infer_file_scope_from_workspace)

    # Check if jq is available
    if ! command -v jq &> /dev/null; then
        ws_log_warn "jq not available, cannot update PRD fileScope"
        return 1
    fi

    # Update each story's fileScope if not explicitly set
    local updated_count=0
    local total_stories
    total_stories=$(jq '.userStories | length' "$prd_file")

    for i in $(seq 0 $((total_stories - 1))); do
        local existing_scope
        existing_scope=$(jq -r ".userStories[$i].fileScope // \"null\"" "$prd_file")

        if [ "$existing_scope" = "null" ] || [ "$existing_scope" = "[]" ]; then
            # Update with inferred scope
            local story_id
            story_id=$(jq -r ".userStories[$i].id" "$prd_file")

            ws_log_info "Setting fileScope for story $story_id"

            # Update PRD (create temp file for safe update)
            local tmp_file="${prd_file}.tmp"
            jq ".userStories[$i].fileScope = $inferred_scope" "$prd_file" > "$tmp_file"
            mv "$tmp_file" "$prd_file"

            updated_count=$((updated_count + 1))
        fi
    done

    ws_log_success "Updated fileScope for $updated_count stories"
    return 0
}

# ============================================================================
# Prompt Generation Integration
# ============================================================================

# Generate workspace boundary information for prompt
# Usage: get_workspace_prompt_section
get_workspace_prompt_section() {
    if ! is_workspace_enabled; then
        return
    fi

    cat <<EOF

# Workspace Sandboxing

This iteration is running with workspace sandboxing ENABLED.

## Workspace Configuration

**Mode**: $WORKSPACE_MODE
**Allowed Folders**: $WORKSPACE_FOLDERS

## Workspace Rules

1. **File Access Constraints**: You should primarily work with files within the workspace folders listed above.

2. **Strict Mode**: $(if [ "$WORKSPACE_MODE" = "strict" ]; then echo "File access outside workspace will FAIL. You must stay within workspace boundaries."; else echo "File access outside workspace will generate warnings but is allowed."; fi)

3. **File Scope**: The story's fileScope has been automatically inferred from workspace contents. Focus your changes on these patterns.

4. **Safety**: Do not attempt to access files outside the workspace unless absolutely necessary.

## Workspace Folders

EOF

    local folders
    folders=$(get_workspace_folders)

    while IFS= read -r folder; do
        [ -z "$folder" ] && continue
        echo "- \`$folder/\`"
    done <<< "$folders"

    echo ""
}

# ============================================================================
# Standalone CLI
# ============================================================================

# Show help
show_help() {
    cat <<EOF
workspace-manager.sh - Workspace Sandboxing for claude-loop

USAGE:
    ./workspace-manager.sh <command> [arguments]

COMMANDS:
    validate <folders>              Validate workspace folders exist and are in repo
                                   folders: comma-separated list (e.g., "lib,src,tests")

    check-file <file> <folders>    Check if file is within workspace
                                   Returns: 0 if in workspace, 1 if not

    infer-scope <folders>          Infer fileScope patterns from workspace
                                   Returns: JSON array of file patterns

    update-prd <folders> <prd>     Update PRD fileScope with workspace patterns

    mount <folders> <worker-dir>   Mount workspace in worker directory

    unmount <folders> <worker-dir> Unmount workspace from worker directory

    prompt-section <folders> <mode> Generate workspace section for prompt
                                    mode: strict or permissive

    clone-source <source> <dest>   Clone source repository to destination
                                   Excludes .git and .claude-loop directories

    get-source <prd>               Get source_project field from PRD

EXAMPLES:
    # Validate workspace folders
    ./workspace-manager.sh validate "lib,src,tests"

    # Check if file is in workspace
    ./workspace-manager.sh check-file "src/main.ts" "src,lib"

    # Infer fileScope patterns
    ./workspace-manager.sh infer-scope "lib,src"

    # Update PRD with workspace patterns
    ./workspace-manager.sh update-prd "lib,src" "prd.json"

    # Clone source repository
    ./workspace-manager.sh clone-source "/path/to/source" "/path/to/workspace"

    # Get source_project from PRD
    ./workspace-manager.sh get-source "prd.json"

EOF
}

# Main CLI entry point
main() {
    if [ $# -eq 0 ]; then
        show_help
        exit 0
    fi

    local command="$1"
    shift

    case "$command" in
        validate)
            if [ $# -lt 1 ]; then
                echo "Error: 'validate' requires folders argument" >&2
                exit 1
            fi
            init_workspace "$1" "permissive"
            validate_workspace_folders
            ;;
        check-file)
            if [ $# -lt 2 ]; then
                echo "Error: 'check-file' requires file and folders arguments" >&2
                exit 1
            fi
            local file="$1"
            local folders="$2"
            init_workspace "$folders" "permissive"
            is_file_in_workspace "$file"
            ;;
        infer-scope)
            if [ $# -lt 1 ]; then
                echo "Error: 'infer-scope' requires folders argument" >&2
                exit 1
            fi
            init_workspace "$1" "permissive"
            infer_file_scope_from_workspace
            ;;
        update-prd)
            if [ $# -lt 2 ]; then
                echo "Error: 'update-prd' requires folders and prd arguments" >&2
                exit 1
            fi
            init_workspace "$1" "permissive"
            update_prd_file_scope "$2"
            ;;
        mount)
            if [ $# -lt 2 ]; then
                echo "Error: 'mount' requires folders and worker-dir arguments" >&2
                exit 1
            fi
            init_workspace "$1" "permissive"
            mount_workspace_in_worker "$2"
            ;;
        unmount)
            if [ $# -lt 2 ]; then
                echo "Error: 'unmount' requires folders and worker-dir arguments" >&2
                exit 1
            fi
            init_workspace "$1" "permissive"
            unmount_workspace_from_worker "$2"
            ;;
        prompt-section)
            if [ $# -lt 2 ]; then
                echo "Error: 'prompt-section' requires folders and mode arguments" >&2
                exit 1
            fi
            init_workspace "$1" "$2"
            get_workspace_prompt_section
            ;;
        clone-source)
            if [ $# -lt 2 ]; then
                echo "Error: 'clone-source' requires source and dest arguments" >&2
                exit 1
            fi
            # Initialize workspace manager for standalone use
            init_workspace "" "permissive"
            clone_source_to_workspace "$1" "$2"
            ;;
        get-source)
            if [ $# -lt 1 ]; then
                echo "Error: 'get-source' requires prd argument" >&2
                exit 1
            fi
            get_source_project_from_prd "$1"
            ;;
        help|--help|-h)
            show_help
            ;;
        *)
            echo "Error: Unknown command '$command'" >&2
            echo "Run './workspace-manager.sh help' for usage" >&2
            exit 1
            ;;
    esac
}

# Run main if executed directly (not sourced)
if [ "${BASH_SOURCE[0]}" = "${0}" ]; then
    main "$@"
fi
