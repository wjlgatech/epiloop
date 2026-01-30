#!/usr/bin/env bash
# template-generator.sh - PRD Template Generator
# Generates PRD files from templates with variable substitution

set -euo pipefail

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
TEMPLATES_DIR="$PROJECT_ROOT/templates/cowork-inspired"

# Colors for output
if [[ -t 1 ]] && command -v tput >/dev/null 2>&1; then
    RED=$(tput setaf 1)
    GREEN=$(tput setaf 2)
    YELLOW=$(tput setaf 3)
    BLUE=$(tput setaf 4)
    MAGENTA=$(tput setaf 5)
    CYAN=$(tput setaf 6)
    BOLD=$(tput bold)
    RESET=$(tput sgr0)
else
    RED="" GREEN="" YELLOW="" BLUE="" MAGENTA="" CYAN="" BOLD="" RESET=""
fi

# Print functions
print_error() { echo "${RED}ERROR:${RESET} $*" >&2; }
print_success() { echo "${GREEN}✓${RESET} $*"; }
print_info() { echo "${BLUE}ℹ${RESET} $*"; }
print_warning() { echo "${YELLOW}⚠${RESET} $*"; }

# Show usage
show_usage() {
    cat <<EOF
${BOLD}Usage:${RESET} template-generator.sh <command> [options]

${BOLD}Commands:${RESET}
  list                    List all available templates
  show <template>         Show template details and variables
  generate <template>     Generate PRD from template (interactive)
  generate <template> -v  Generate with variables from file or flags
  validate <prd.json>     Validate a generated PRD file

${BOLD}Options:${RESET}
  --output <file>         Output file path (default: prd.json)
  --var KEY=VALUE         Set template variable (can be used multiple times)
  --vars-file <file>      Load variables from JSON file
  --interactive           Force interactive mode
  --non-interactive       Non-interactive mode (use defaults)
  --help                  Show this help message

${BOLD}Examples:${RESET}
  # List all templates
  template-generator.sh list

  # Show template details
  template-generator.sh show web-feature

  # Generate PRD interactively
  template-generator.sh generate web-feature

  # Generate PRD with variables
  template-generator.sh generate api-endpoint \\
    --var PROJECT_NAME=user-service \\
    --var ENDPOINT_NAME=users \\
    --output prd-users-api.json

  # Generate from variables file
  template-generator.sh generate refactoring \\
    --vars-file my-vars.json \\
    --output prd-refactor.json

${BOLD}Variables File Format:${RESET}
  {
    "PROJECT_NAME": "my-project",
    "FEATURE_NAME": "my-feature",
    "BRANCH_NAME": "feature/my-feature"
  }
EOF
}

# List all available templates
list_templates() {
    if [[ ! -d "$TEMPLATES_DIR" ]]; then
        print_error "Templates directory not found: $TEMPLATES_DIR"
        return 1
    fi

    echo "${BOLD}Available Templates:${RESET}"
    echo ""

    local template_files=("$TEMPLATES_DIR"/*.json)
    if [[ ! -e "${template_files[0]}" ]]; then
        print_warning "No templates found in $TEMPLATES_DIR"
        return 0
    fi

    for template_file in "${template_files[@]}"; do
        local template_name
        template_name=$(basename "$template_file" .json)

        # Extract metadata using jq
        if command -v jq >/dev/null 2>&1; then
            local description complexity duration
            description=$(jq -r '.metadata.description // "No description"' "$template_file")
            complexity=$(jq -r '.metadata.estimatedComplexity // "unknown"' "$template_file")
            duration=$(jq -r '.metadata.typicalDuration // "unknown"' "$template_file")

            echo "${CYAN}${template_name}${RESET}"
            echo "  Description: $description"
            echo "  Complexity:  $complexity"
            echo "  Duration:    $duration"
            echo ""
        else
            echo "${CYAN}${template_name}${RESET}"
            echo "  (Install jq for detailed information)"
            echo ""
        fi
    done
}

# Show template details
show_template() {
    local template_name="$1"
    local template_file="$TEMPLATES_DIR/${template_name}.json"

    if [[ ! -f "$template_file" ]]; then
        print_error "Template not found: $template_name"
        print_info "Run 'template-generator.sh list' to see available templates"
        return 1
    fi

    if ! command -v jq >/dev/null 2>&1; then
        print_error "jq is required to show template details"
        print_info "Install jq: brew install jq (macOS) or apt-get install jq (Linux)"
        return 1
    fi

    echo "${BOLD}Template: ${CYAN}${template_name}${RESET}"
    echo ""

    # Show metadata
    echo "${BOLD}Metadata:${RESET}"
    jq -r '.metadata | "  Description: \(.description)\n  Complexity:  \(.estimatedComplexity)\n  Duration:    \(.typicalDuration)\n  Skills:      \(.requiredSkills | join(", "))"' "$template_file"
    echo ""

    # Show variables
    echo "${BOLD}Variables:${RESET}"
    local var_count
    var_count=$(jq '.metadata.variables | length' "$template_file")

    if [[ "$var_count" -eq 0 ]]; then
        echo "  No variables defined"
    else
        jq -r '.metadata.variables[] | "  \(.name) (\(if .required then "required" else "optional" end))\n    Description: \(.description)\n    Example: \(.example // .default // "N/A")\n"' "$template_file"
    fi

    # Show user stories count
    local story_count
    story_count=$(jq '.prd.userStories | length' "$template_file")
    echo "${BOLD}User Stories:${RESET} $story_count stories"
    echo ""
}

# Prompt for variable value
prompt_variable() {
    local var_name="$1"
    local var_desc="$2"
    local var_required="$3"
    local var_default="$4"
    local var_example="$5"
    local existing_vars="$6"  # Existing var_pairs for substitution

    # Substitute variables in default value
    if [[ -n "$var_default" && -n "$existing_vars" ]]; then
        while IFS='=' read -r def_var_name def_var_value; do
            [[ -z "$def_var_name" ]] && continue
            def_var_value=$(echo "$def_var_value" | sed 's/[&/\]/\\&/g')
            var_default=$(echo "$var_default" | sed "s/{{${def_var_name}}}/${def_var_value}/g")
        done <<< "$existing_vars"
    fi

    echo ""
    echo "${BOLD}${var_name}${RESET} ${var_required:+${RED}(required)${RESET}}"
    echo "  $var_desc"
    [[ -n "$var_example" ]] && echo "  ${CYAN}Example:${RESET} $var_example"

    if [[ -n "$var_default" ]]; then
        echo -n "  ${YELLOW}[${var_default}]${RESET} > "
    else
        echo -n "  > "
    fi

    local value
    read -r value

    # Use default if empty and default is provided
    if [[ -z "$value" && -n "$var_default" ]]; then
        value="$var_default"
    fi

    # Check required
    if [[ "$var_required" == "true" && -z "$value" ]]; then
        print_error "This variable is required"
        prompt_variable "$var_name" "$var_desc" "$var_required" "$var_default" "$var_example" "$existing_vars"
        return
    fi

    echo "$value"
}

# Substitute variables in template
# Takes template content and newline-separated KEY=VALUE pairs
substitute_variables() {
    local template_content="$1"
    local var_pairs="$2"

    local result="$template_content"

    # Substitute each variable from newline-separated KEY=VALUE pairs
    while IFS='=' read -r var_name var_value; do
        [[ -z "$var_name" ]] && continue
        # Escape special characters in value for sed
        var_value=$(echo "$var_value" | sed 's/[&/\]/\\&/g')
        result=$(echo "$result" | sed "s/{{${var_name}}}/${var_value}/g")
    done <<< "$var_pairs"

    echo "$result"
}

# Generate PRD from template
generate_prd() {
    local template_name="$1"
    shift

    local output_file="prd.json"
    local interactive=true
    local vars_file=""
    local var_pairs=""  # Newline-separated KEY=VALUE pairs

    # Parse options
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --output)
                output_file="$2"
                shift 2
                ;;
            --var)
                # Append to var_pairs
                var_pairs="${var_pairs}${2}"$'\n'
                shift 2
                ;;
            --vars-file)
                vars_file="$2"
                shift 2
                ;;
            --interactive)
                interactive=true
                shift
                ;;
            --non-interactive)
                interactive=false
                shift
                ;;
            *)
                print_error "Unknown option: $1"
                return 1
                ;;
        esac
    done

    local template_file="$TEMPLATES_DIR/${template_name}.json"
    if [[ ! -f "$template_file" ]]; then
        print_error "Template not found: $template_name"
        print_info "Run 'template-generator.sh list' to see available templates"
        return 1
    fi

    if ! command -v jq >/dev/null 2>&1; then
        print_error "jq is required to generate PRDs"
        print_info "Install jq: brew install jq (macOS) or apt-get install jq (Linux)"
        return 1
    fi

    # Helper function to check if variable is already defined
    has_var() {
        local name="$1"
        echo "$var_pairs" | grep -q "^${name}="
    }

    # Helper function to get variable value
    get_var() {
        local name="$1"
        echo "$var_pairs" | grep "^${name}=" | head -1 | cut -d= -f2-
    }

    # Load variables from file if provided
    if [[ -n "$vars_file" ]]; then
        if [[ ! -f "$vars_file" ]]; then
            print_error "Variables file not found: $vars_file"
            return 1
        fi

        # Load variables from JSON file
        local file_vars
        file_vars=$(jq -r 'to_entries | .[] | "\(.key)=\(.value)"' "$vars_file")
        var_pairs="${var_pairs}${file_vars}"$'\n'
    fi

    # Interactive prompting if needed
    if [[ "$interactive" == "true" ]]; then
        echo "${BOLD}Generating PRD from template: ${CYAN}${template_name}${RESET}"
        echo ""

        # Get variables from template
        local var_count
        var_count=$(jq '.metadata.variables | length' "$template_file")

        if [[ "$var_count" -gt 0 ]]; then
            echo "${BOLD}Please provide values for template variables:${RESET}"

            # Iterate through variables
            for i in $(seq 0 $((var_count - 1))); do
                local var_name var_desc var_required var_default var_example
                var_name=$(jq -r ".metadata.variables[$i].name" "$template_file")
                var_desc=$(jq -r ".metadata.variables[$i].description" "$template_file")
                var_required=$(jq -r ".metadata.variables[$i].required" "$template_file")
                var_default=$(jq -r ".metadata.variables[$i].default // empty" "$template_file")
                var_example=$(jq -r ".metadata.variables[$i].example // empty" "$template_file")

                # Skip if already provided via --var or --vars-file
                if has_var "$var_name"; then
                    local existing_value
                    existing_value=$(get_var "$var_name")
                    echo ""
                    echo "${BOLD}${var_name}${RESET}: ${existing_value} ${GREEN}(provided)${RESET}"
                    continue
                fi

                # Prompt for value
                local value
                value=$(prompt_variable "$var_name" "$var_desc" "$var_required" "$var_default" "$var_example" "$var_pairs")

                if [[ -n "$value" ]]; then
                    var_pairs="${var_pairs}${var_name}=${value}"$'\n'
                fi
            done
        fi
    else
        # Non-interactive: ensure all required variables are provided
        local var_count
        var_count=$(jq '.metadata.variables | length' "$template_file")

        for i in $(seq 0 $((var_count - 1))); do
            local var_name var_required var_default
            var_name=$(jq -r ".metadata.variables[$i].name" "$template_file")
            var_required=$(jq -r ".metadata.variables[$i].required" "$template_file")
            var_default=$(jq -r ".metadata.variables[$i].default // empty" "$template_file")

            # Check if required variable is missing
            if [[ "$var_required" == "true" ]] && ! has_var "$var_name"; then
                print_error "Required variable not provided: $var_name"
                print_info "Use --var ${var_name}=VALUE or --vars-file <file>"
                return 1
            fi

            # Use default if not provided
            if ! has_var "$var_name" && [[ -n "$var_default" ]]; then
                # Substitute variables in default value
                local substituted_default="$var_default"
                while IFS='=' read -r def_var_name def_var_value; do
                    [[ -z "$def_var_name" ]] && continue
                    def_var_value=$(echo "$def_var_value" | sed 's/[&/\]/\\&/g')
                    substituted_default=$(echo "$substituted_default" | sed "s/{{${def_var_name}}}/${def_var_value}/g")
                done <<< "$var_pairs"
                var_pairs="${var_pairs}${var_name}=${substituted_default}"$'\n'
            fi
        done
    fi

    # Read template content
    local template_content
    template_content=$(cat "$template_file")

    # Substitute variables
    local prd_content
    prd_content=$(substitute_variables "$template_content" "$var_pairs")

    # Extract just the PRD part (remove metadata wrapper)
    prd_content=$(echo "$prd_content" | jq '.prd')

    # Validate generated PRD has no remaining placeholders
    if echo "$prd_content" | grep -q '{{[A-Z_]*}}'; then
        print_warning "Some variables were not substituted:"
        echo "$prd_content" | grep -o '{{[A-Z_]*}}' | sort -u
        echo ""
        read -p "Continue anyway? (y/N) " -n 1 -r
        echo ""
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            print_error "Aborted"
            return 1
        fi
    fi

    # Write output file
    echo "$prd_content" | jq '.' > "$output_file"

    if [[ $? -eq 0 ]]; then
        echo ""
        print_success "PRD generated successfully: ${CYAN}${output_file}${RESET}"

        # Show summary
        local story_count
        story_count=$(jq '.userStories | length' "$output_file")
        echo ""
        echo "${BOLD}Summary:${RESET}"
        echo "  Template:     $template_name"
        echo "  Output:       $output_file"
        echo "  User Stories: $story_count"
        echo "  Branch:       $(jq -r '.branchName' "$output_file")"
        echo ""
        print_info "Run: ./claude-loop.sh to start working on this PRD"
    else
        print_error "Failed to generate PRD"
        return 1
    fi
}

# Validate PRD file
validate_prd() {
    local prd_file="$1"

    if [[ ! -f "$prd_file" ]]; then
        print_error "PRD file not found: $prd_file"
        return 1
    fi

    if ! command -v jq >/dev/null 2>&1; then
        print_error "jq is required to validate PRDs"
        return 1
    fi

    # Check JSON validity
    if ! jq empty "$prd_file" 2>/dev/null; then
        print_error "Invalid JSON in $prd_file"
        return 1
    fi

    # Check required fields
    local errors=0

    # Check top-level fields
    for field in project branchName description userStories; do
        if ! jq -e ".$field" "$prd_file" >/dev/null 2>&1; then
            print_error "Missing required field: $field"
            ((errors++))
        fi
    done

    # Check user stories
    local story_count
    story_count=$(jq '.userStories | length' "$prd_file")

    if [[ "$story_count" -eq 0 ]]; then
        print_error "No user stories defined"
        ((errors++))
    fi

    # Check each story
    for i in $(seq 0 $((story_count - 1))); do
        for field in id title description acceptanceCriteria priority passes; do
            local has_field
            has_field=$(jq -r ".userStories[$i] | has(\"$field\")" "$prd_file")
            if [[ "$has_field" != "true" ]]; then
                print_error "Story $i: missing required field: $field"
                ((errors++))
            fi
        done
    done

    # Check for remaining placeholders
    if grep -q '{{[A-Z_]*}}' "$prd_file"; then
        print_warning "Found unsubstituted variables:"
        grep -o '{{[A-Z_]*}}' "$prd_file" | sort -u
        ((errors++))
    fi

    if [[ $errors -eq 0 ]]; then
        print_success "PRD validation passed: $prd_file"
        return 0
    else
        print_error "PRD validation failed with $errors error(s)"
        return 1
    fi
}

# Main command router
main() {
    if [[ $# -eq 0 ]]; then
        show_usage
        exit 0
    fi

    local command="$1"
    shift

    case "$command" in
        list)
            list_templates
            ;;
        show)
            if [[ $# -eq 0 ]]; then
                print_error "Template name required"
                echo "Usage: template-generator.sh show <template>"
                exit 1
            fi
            show_template "$1"
            ;;
        generate)
            if [[ $# -eq 0 ]]; then
                print_error "Template name required"
                echo "Usage: template-generator.sh generate <template> [options]"
                exit 1
            fi
            generate_prd "$@"
            ;;
        validate)
            if [[ $# -eq 0 ]]; then
                print_error "PRD file required"
                echo "Usage: template-generator.sh validate <prd.json>"
                exit 1
            fi
            validate_prd "$1"
            ;;
        --help|-h|help)
            show_usage
            ;;
        *)
            print_error "Unknown command: $command"
            echo ""
            show_usage
            exit 1
            ;;
    esac
}

# Run if executed directly
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi
