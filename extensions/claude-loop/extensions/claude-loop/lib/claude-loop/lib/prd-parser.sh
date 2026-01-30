#!/bin/bash
#
# lib/prd-parser.sh - PRD Schema Parser and Validator
#
# Provides functions for parsing and validating prd.json files with support for:
# - New parallelization fields (dependencies, fileScope, estimatedComplexity, suggestedModel)
# - Top-level parallelization configuration
# - Circular dependency detection
# - Backward compatibility with legacy PRDs (all new fields optional)
#
# Usage:
#   source lib/prd-parser.sh
#   validate_prd "prd.json"           # Returns 0 if valid, 1 if invalid
#   get_story_dependencies "US-001"   # Get dependencies for a story
#   check_circular_dependencies       # Check for circular deps
#

# ============================================================================
# Schema Validation Functions
# ============================================================================

# Validate the entire PRD structure
# Returns: 0 if valid, 1 if invalid (errors printed to stderr)
validate_prd() {
    local prd_file="${1:-prd.json}"
    local errors=0

    if [ ! -f "$prd_file" ]; then
        echo "Error: PRD file not found: $prd_file" >&2
        return 1
    fi

    # Check for valid JSON
    if ! jq empty "$prd_file" 2>/dev/null; then
        echo "Error: Invalid JSON in PRD file" >&2
        return 1
    fi

    # Validate required fields
    if ! jq -e '.project' "$prd_file" >/dev/null 2>&1; then
        echo "Error: Missing required field 'project'" >&2
        ((errors++))
    fi

    if ! jq -e '.userStories' "$prd_file" >/dev/null 2>&1; then
        echo "Error: Missing required field 'userStories'" >&2
        ((errors++))
    fi

    # Validate each user story
    local story_count
    story_count=$(jq '.userStories | length' "$prd_file")

    for ((i=0; i<story_count; i++)); do
        local story_id
        story_id=$(jq -r ".userStories[$i].id // \"unknown\"" "$prd_file")

        # Required fields for each story
        if ! jq -e ".userStories[$i].id" "$prd_file" >/dev/null 2>&1; then
            echo "Error: Story at index $i missing required field 'id'" >&2
            ((errors++))
        fi

        if ! jq -e ".userStories[$i].title" "$prd_file" >/dev/null 2>&1; then
            echo "Error: Story '$story_id' missing required field 'title'" >&2
            ((errors++))
        fi

        if ! jq -e ".userStories[$i].priority" "$prd_file" >/dev/null 2>&1; then
            echo "Error: Story '$story_id' missing required field 'priority'" >&2
            ((errors++))
        fi

        # Validate optional parallelization fields if present
        validate_story_parallelization_fields "$prd_file" "$i" "$story_id" || ((errors++))
    done

    # Check for circular dependencies
    if ! check_circular_dependencies "$prd_file"; then
        ((errors++))
    fi

    # Validate parallelization config if present
    if jq -e '.parallelization' "$prd_file" >/dev/null 2>&1; then
        validate_parallelization_config "$prd_file" || ((errors++))
    fi

    # Validate source_project if present
    if jq -e '.source_project' "$prd_file" >/dev/null 2>&1; then
        validate_source_project "$prd_file" || ((errors++))
    fi

    if [ $errors -gt 0 ]; then
        echo "Validation failed with $errors error(s)" >&2
        return 1
    fi

    return 0
}

# Validate parallelization fields for a single story
validate_story_parallelization_fields() {
    local prd_file="$1"
    local index="$2"
    local story_id="$3"
    local errors=0

    # Validate dependencies array (if present)
    if jq -e ".userStories[$index].dependencies" "$prd_file" >/dev/null 2>&1; then
        local deps_type
        deps_type=$(jq -r ".userStories[$index].dependencies | type" "$prd_file")
        if [ "$deps_type" != "array" ]; then
            echo "Error: Story '$story_id' dependencies must be an array" >&2
            ((errors++))
        else
            # Verify all dependencies reference valid story IDs
            local deps
            deps=$(jq -r ".userStories[$index].dependencies[]" "$prd_file" 2>/dev/null)
            for dep in $deps; do
                if ! jq -e ".userStories[] | select(.id == \"$dep\")" "$prd_file" >/dev/null 2>&1; then
                    echo "Error: Story '$story_id' has invalid dependency: '$dep' (story not found)" >&2
                    ((errors++))
                fi
            done
        fi
    fi

    # Validate fileScope array (if present)
    if jq -e ".userStories[$index].fileScope" "$prd_file" >/dev/null 2>&1; then
        local scope_type
        scope_type=$(jq -r ".userStories[$index].fileScope | type" "$prd_file")
        if [ "$scope_type" != "array" ]; then
            echo "Error: Story '$story_id' fileScope must be an array" >&2
            ((errors++))
        fi
    fi

    # Validate estimatedComplexity (if present)
    if jq -e ".userStories[$index].estimatedComplexity" "$prd_file" >/dev/null 2>&1; then
        local complexity
        complexity=$(jq -r ".userStories[$index].estimatedComplexity" "$prd_file")
        if [[ ! "$complexity" =~ ^(simple|medium|complex)$ ]]; then
            echo "Error: Story '$story_id' has invalid estimatedComplexity: '$complexity' (must be simple|medium|complex)" >&2
            ((errors++))
        fi
    fi

    # Validate suggestedModel (if present)
    if jq -e ".userStories[$index].suggestedModel" "$prd_file" >/dev/null 2>&1; then
        local model
        model=$(jq -r ".userStories[$index].suggestedModel" "$prd_file")
        if [[ ! "$model" =~ ^(haiku|sonnet|opus)$ ]]; then
            echo "Error: Story '$story_id' has invalid suggestedModel: '$model' (must be haiku|sonnet|opus)" >&2
            ((errors++))
        fi
    fi

    return $errors
}

# Validate top-level parallelization configuration
validate_parallelization_config() {
    local prd_file="$1"
    local errors=0

    # Validate maxWorkers (if present)
    if jq -e '.parallelization.maxWorkers' "$prd_file" >/dev/null 2>&1; then
        local max_workers
        max_workers=$(jq '.parallelization.maxWorkers' "$prd_file")
        if ! [[ "$max_workers" =~ ^[0-9]+$ ]] || [ "$max_workers" -lt 1 ]; then
            echo "Error: parallelization.maxWorkers must be a positive integer" >&2
            ((errors++))
        fi
    fi

    # Validate defaultModel (if present)
    if jq -e '.parallelization.defaultModel' "$prd_file" >/dev/null 2>&1; then
        local model
        model=$(jq -r '.parallelization.defaultModel' "$prd_file")
        if [[ ! "$model" =~ ^(haiku|sonnet|opus)$ ]]; then
            echo "Error: parallelization.defaultModel must be haiku|sonnet|opus" >&2
            ((errors++))
        fi
    fi

    # Validate modelStrategy (if present)
    if jq -e '.parallelization.modelStrategy' "$prd_file" >/dev/null 2>&1; then
        local strategy
        strategy=$(jq -r '.parallelization.modelStrategy' "$prd_file")
        if [[ ! "$strategy" =~ ^(auto|always-opus|always-sonnet|always-haiku)$ ]]; then
            echo "Error: parallelization.modelStrategy must be auto|always-opus|always-sonnet|always-haiku" >&2
            ((errors++))
        fi
    fi

    # Validate enabled flag (if present)
    if jq -e '.parallelization.enabled' "$prd_file" >/dev/null 2>&1; then
        local enabled_type
        enabled_type=$(jq -r '.parallelization.enabled | type' "$prd_file")
        if [ "$enabled_type" != "boolean" ]; then
            echo "Error: parallelization.enabled must be a boolean" >&2
            ((errors++))
        fi
    fi

    return $errors
}

# Validate source_project field
validate_source_project() {
    local prd_file="$1"
    local errors=0

    # Check type - must be string or null
    local source_type
    source_type=$(jq -r '.source_project | type' "$prd_file")

    if [ "$source_type" != "string" ] && [ "$source_type" != "null" ]; then
        echo "Error: source_project must be a string path or null" >&2
        ((errors++))
        return $errors
    fi

    # If it's null, that's valid (backward compatible default)
    if [ "$source_type" = "null" ]; then
        return 0
    fi

    # Get the value
    local source_project
    source_project=$(jq -r '.source_project' "$prd_file")

    # Check for empty string
    if [ -z "$source_project" ]; then
        echo "Error: source_project cannot be an empty string (use null instead)" >&2
        ((errors++))
    fi

    # Path validation - both absolute and relative paths are allowed
    # No need to check if path exists at validation time - it will be checked at workspace setup
    # Just ensure it's a reasonable path format (no null bytes, control chars)
    if echo "$source_project" | grep -q $'[\x00-\x1F\x7F]'; then
        echo "Error: source_project contains invalid control characters" >&2
        ((errors++))
    fi

    return $errors
}

# ============================================================================
# Circular Dependency Detection
# ============================================================================

# Check for circular dependencies using DFS
# Returns: 0 if no cycles, 1 if cycles detected
check_circular_dependencies() {
    local prd_file="${1:-prd.json}"

    # Build adjacency list from dependencies
    local story_ids
    story_ids=$(jq -r '.userStories[].id' "$prd_file")

    # Use Python for cycle detection (more reliable for complex graphs)
    python3 << EOF
import json
import sys

def detect_cycle(graph):
    """Detect cycles using DFS with coloring."""
    WHITE, GRAY, BLACK = 0, 1, 2
    color = {node: WHITE for node in graph}
    cycle_path = []

    def dfs(node, path):
        color[node] = GRAY
        path.append(node)

        for neighbor in graph.get(node, []):
            if neighbor not in graph:
                # Skip invalid dependencies (already caught by validation)
                continue
            if color[neighbor] == GRAY:
                # Found cycle
                cycle_start = path.index(neighbor)
                return path[cycle_start:] + [neighbor]
            if color[neighbor] == WHITE:
                result = dfs(neighbor, path)
                if result:
                    return result

        color[node] = BLACK
        path.pop()
        return None

    for node in graph:
        if color[node] == WHITE:
            result = dfs(node, [])
            if result:
                return result
    return None

try:
    with open('$prd_file', 'r') as f:
        prd = json.load(f)

    # Build graph
    graph = {}
    for story in prd.get('userStories', []):
        story_id = story.get('id')
        deps = story.get('dependencies', [])
        graph[story_id] = deps

    cycle = detect_cycle(graph)
    if cycle:
        print(f"Error: Circular dependency detected: {' -> '.join(cycle)}", file=sys.stderr)
        sys.exit(1)

    sys.exit(0)
except Exception as e:
    print(f"Error checking dependencies: {e}", file=sys.stderr)
    sys.exit(1)
EOF
    return $?
}

# ============================================================================
# Story Query Functions
# ============================================================================

# Get dependencies for a specific story
# Args: story_id, prd_file (optional)
# Returns: Space-separated list of dependency IDs
get_story_dependencies() {
    local story_id="$1"
    local prd_file="${2:-prd.json}"

    jq -r --arg id "$story_id" '
        .userStories[] | select(.id == $id) |
        .dependencies // [] | join(" ")
    ' "$prd_file"
}

# Get file scope for a specific story
# Args: story_id, prd_file (optional)
# Returns: Space-separated list of file paths
get_story_file_scope() {
    local story_id="$1"
    local prd_file="${2:-prd.json}"

    jq -r --arg id "$story_id" '
        .userStories[] | select(.id == $id) |
        .fileScope // [] | join(" ")
    ' "$prd_file"
}

# Get estimated complexity for a specific story
# Args: story_id, prd_file (optional)
# Returns: simple, medium, or complex (defaults to medium)
get_story_complexity() {
    local story_id="$1"
    local prd_file="${2:-prd.json}"

    jq -r --arg id "$story_id" '
        .userStories[] | select(.id == $id) |
        .estimatedComplexity // "medium"
    ' "$prd_file"
}

# Get suggested model for a specific story
# Args: story_id, prd_file (optional)
# Returns: haiku, sonnet, or opus (defaults to sonnet)
get_story_suggested_model() {
    local story_id="$1"
    local prd_file="${2:-prd.json}"

    jq -r --arg id "$story_id" '
        .userStories[] | select(.id == $id) |
        .suggestedModel // "sonnet"
    ' "$prd_file"
}

# Get all stories that depend on a specific story
# Args: story_id, prd_file (optional)
# Returns: Space-separated list of dependent story IDs
get_story_dependents() {
    local story_id="$1"
    local prd_file="${2:-prd.json}"

    jq -r --arg id "$story_id" '
        [.userStories[] | select(.dependencies // [] | contains([$id])) | .id] | join(" ")
    ' "$prd_file"
}

# Get stories with no dependencies (can run first)
# Args: prd_file (optional)
# Returns: Space-separated list of story IDs
get_root_stories() {
    local prd_file="${1:-prd.json}"

    jq -r '
        [.userStories[] | select((.dependencies // []) | length == 0) | .id] | join(" ")
    ' "$prd_file"
}

# Get incomplete stories with all dependencies satisfied
# Args: prd_file (optional)
# Returns: Space-separated list of story IDs ready to execute
get_ready_stories() {
    local prd_file="${1:-prd.json}"

    jq -r '
        # Get all completed story IDs
        [.userStories[] | select(.passes == true) | .id] as $completed |
        # Find incomplete stories whose dependencies are all completed
        [.userStories[] |
            select(.passes == false) |
            select((.dependencies // []) - $completed | length == 0) |
            .id
        ] | join(" ")
    ' "$prd_file"
}

# ============================================================================
# Parallelization Config Functions
# ============================================================================

# Get parallelization enabled flag
# Args: prd_file (optional)
# Returns: true or false
get_parallelization_enabled() {
    local prd_file="${1:-prd.json}"

    jq -r '.parallelization.enabled // true' "$prd_file"
}

# Get max workers setting
# Args: prd_file (optional)
# Returns: integer (defaults to 3)
get_max_workers() {
    local prd_file="${1:-prd.json}"

    jq -r '.parallelization.maxWorkers // 3' "$prd_file"
}

# Get default model setting
# Args: prd_file (optional)
# Returns: haiku, sonnet, or opus (defaults to sonnet)
get_default_model() {
    local prd_file="${1:-prd.json}"

    jq -r '.parallelization.defaultModel // "sonnet"' "$prd_file"
}

# Get model strategy setting
# Args: prd_file (optional)
# Returns: auto, always-opus, always-sonnet, or always-haiku (defaults to auto)
get_model_strategy() {
    local prd_file="${1:-prd.json}"

    jq -r '.parallelization.modelStrategy // "auto"' "$prd_file"
}

# Get source project path
# Args: prd_file (optional)
# Returns: source project path or empty string if not specified
get_source_project() {
    local prd_file="${1:-prd.json}"

    jq -r '.source_project // "" | if . == null then "" else . end' "$prd_file"
}

# ============================================================================
# Schema Info
# ============================================================================

# Print schema documentation
print_schema_info() {
    cat << 'EOF'
PRD Schema v2 (with Parallelization Support)
============================================

Top-level fields:
  project          (required) Project name
  branchName       (optional) Git branch for this feature
  description      (optional) Feature description
  source_project   (optional) Path to source repository to clone into workspace
  parallelization  (optional) Parallelization configuration object
  userStories      (required) Array of user story objects

Source Project field:
  source_project   (optional) String path (absolute or relative) to source repository.
                             When specified, the repository contents (excluding .git)
                             will be cloned into the workspace before execution starts.
                             Defaults to null (no cloning). Enables working on existing
                             codebases from within claude-loop workspaces.

Parallelization config fields:
  enabled          (optional) Enable parallel execution (default: true)
  maxWorkers       (optional) Maximum parallel workers (default: 3)
  defaultModel     (optional) Default model: haiku|sonnet|opus (default: sonnet)
  modelStrategy    (optional) Model selection: auto|always-opus|always-sonnet|always-haiku

User story fields:
  id                    (required) Unique story identifier
  title                 (required) Short story title
  description           (optional) Full story description
  acceptanceCriteria    (optional) Array of acceptance criteria strings
  priority              (required) Priority number (lower = higher priority)
  passes                (optional) Whether story is complete (default: false)
  notes                 (optional) Implementation notes

  # New parallelization fields (all optional for backward compatibility):
  dependencies          (optional) Array of story IDs this story depends on
  fileScope             (optional) Array of file paths this story modifies
  estimatedComplexity   (optional) simple|medium|complex (default: medium)
  suggestedModel        (optional) haiku|sonnet|opus (overrides default)

Example:
{
  "project": "my-feature",
  "branchName": "feature/my-feature",
  "source_project": "/path/to/existing/repo",
  "parallelization": {
    "enabled": true,
    "maxWorkers": 4,
    "modelStrategy": "auto"
  },
  "userStories": [
    {
      "id": "US-001",
      "title": "Create base module",
      "priority": 1,
      "dependencies": [],
      "fileScope": ["lib/module.py"],
      "estimatedComplexity": "simple",
      "suggestedModel": "haiku",
      "passes": false
    },
    {
      "id": "US-002",
      "title": "Add feature to module",
      "priority": 2,
      "dependencies": ["US-001"],
      "fileScope": ["lib/module.py", "tests/test_module.py"],
      "estimatedComplexity": "medium",
      "passes": false
    }
  ]
}
EOF
}

# ============================================================================
# Main (for testing)
# ============================================================================

# If run directly, validate the PRD file
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    case "${1:-}" in
        validate)
            validate_prd "${2:-prd.json}"
            ;;
        schema)
            print_schema_info
            ;;
        deps)
            if [ -n "${2:-}" ]; then
                get_story_dependencies "$2" "${3:-prd.json}"
            else
                echo "Usage: $0 deps <story_id> [prd_file]"
                exit 1
            fi
            ;;
        ready)
            get_ready_stories "${2:-prd.json}"
            ;;
        check-cycles)
            check_circular_dependencies "${2:-prd.json}"
            ;;
        *)
            echo "Usage: $0 <command> [args]"
            echo ""
            echo "Commands:"
            echo "  validate [prd_file]     - Validate PRD structure"
            echo "  schema                  - Print schema documentation"
            echo "  deps <story_id> [prd]   - Get story dependencies"
            echo "  ready [prd_file]        - Get stories ready to run"
            echo "  check-cycles [prd]      - Check for circular dependencies"
            exit 1
            ;;
    esac
fi
