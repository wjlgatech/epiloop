#!/usr/bin/env bash
#
# brainstorming-handler.sh - Interactive design refinement handler
#
# This script facilitates the brainstorming workflow by:
# 1. Loading the brainstorming skill
# 2. Preparing context (project files, recent commits)
# 3. Invoking Claude Code with the skill and user description
# 4. Managing the design document creation and git commit
#
# Usage:
#   ./lib/brainstorming-handler.sh '<description>' [options]
#   ./lib/brainstorming-handler.sh --help
#
# Options:
#   --help              Show this help message
#   --skill-path PATH   Override skill file location (default: skills/brainstorming/SKILL.md)
#   --no-commit         Don't auto-commit the design document
#   --output-dir PATH   Override output directory (default: docs/plans/)
#
# Example:
#   ./lib/brainstorming-handler.sh 'Add user authentication with OAuth'
#   ./lib/brainstorming-handler.sh 'Implement real-time notifications' --no-commit
#

set -euo pipefail

# Script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Default configuration
SKILL_PATH="$PROJECT_ROOT/skills/brainstorming/SKILL.md"
OUTPUT_DIR="$PROJECT_ROOT/docs/plans"
AUTO_COMMIT=true
DESCRIPTION=""

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Help message
show_help() {
    cat << EOF
brainstorming-handler.sh - Interactive design refinement

Usage:
  ./lib/brainstorming-handler.sh '<description>' [options]
  ./lib/brainstorming-handler.sh --help

Arguments:
  description         Feature or component description to brainstorm

Options:
  --help              Show this help message
  --skill-path PATH   Override skill file location (default: skills/brainstorming/SKILL.md)
  --no-commit         Don't auto-commit the design document
  --output-dir PATH   Override output directory (default: docs/plans/)

Examples:
  ./lib/brainstorming-handler.sh 'Add user authentication with OAuth'
  ./lib/brainstorming-handler.sh 'Implement real-time notifications' --no-commit

Description:
  This script facilitates interactive design refinement through Socratic dialogue.
  It loads the brainstorming skill, prepares project context, and guides you through:

  1. Understanding context - Asks clarifying questions one at a time
  2. Exploring alternatives - Proposes 2-3 approaches with trade-offs
  3. Presenting design - Shows design in sections (200-300 words each)
  4. Validating incrementally - Checks understanding after each section
  5. Generating documentation - Saves design to docs/plans/
  6. Offering PRD generation - Option to continue to implementation

EOF
    exit 0
}

# Error handler
error_exit() {
    echo -e "${RED}ERROR:${NC} $1" >&2
    exit 1
}

# Parse arguments
parse_arguments() {
    if [ $# -eq 0 ]; then
        error_exit "Description required. Use --help for usage information."
    fi

    while [ $# -gt 0 ]; then
        case "$1" in
            --help|-h)
                show_help
                ;;
            --skill-path)
                SKILL_PATH="$2"
                shift 2
                ;;
            --no-commit)
                AUTO_COMMIT=false
                shift
                ;;
            --output-dir)
                OUTPUT_DIR="$2"
                shift 2
                ;;
            -*)
                error_exit "Unknown option: $1"
                ;;
            *)
                if [ -z "$DESCRIPTION" ]; then
                    DESCRIPTION="$1"
                else
                    error_exit "Multiple descriptions provided. Please provide one description."
                fi
                shift
                ;;
        esac
    done

    if [ -z "$DESCRIPTION" ]; then
        error_exit "Description required. Use --help for usage information."
    fi
}

# Validate prerequisites
validate_prerequisites() {
    # Check if skill file exists
    if [ ! -f "$SKILL_PATH" ]; then
        error_exit "Skill file not found: $SKILL_PATH"
    fi

    # Check if output directory exists, create if not
    if [ ! -d "$OUTPUT_DIR" ]; then
        echo -e "${YELLOW}Creating output directory:${NC} $OUTPUT_DIR"
        mkdir -p "$OUTPUT_DIR"
    fi

    # Check if we're in a git repository
    if ! git rev-parse --git-dir > /dev/null 2>&1; then
        echo -e "${YELLOW}WARNING:${NC} Not in a git repository. Design document won't be committed."
        AUTO_COMMIT=false
    fi
}

# Prepare project context
prepare_context() {
    local context_file="$PROJECT_ROOT/.claude-loop/brainstorming-context.txt"

    echo -e "${BLUE}Preparing project context...${NC}"

    # Create context file
    cat > "$context_file" << EOF
# Project Context for Brainstorming

## Description
$DESCRIPTION

## Project Information

### Recent Commits (last 5)
$(git log -5 --oneline 2>/dev/null || echo "No git history available")

### Current Branch
$(git branch --show-current 2>/dev/null || echo "Not in a git repository")

### Project Structure (top-level)
$(ls -1 "$PROJECT_ROOT" 2>/dev/null | head -20)

### README (first 50 lines)
$(if [ -f "$PROJECT_ROOT/README.md" ]; then head -50 "$PROJECT_ROOT/README.md"; else echo "No README.md found"; fi)

EOF

    echo -e "${GREEN}✓${NC} Context prepared: $context_file"
    echo "$context_file"
}

# Load brainstorming skill
load_skill() {
    echo -e "${BLUE}Loading brainstorming skill...${NC}"

    if [ ! -f "$SKILL_PATH" ]; then
        error_exit "Skill file not found: $SKILL_PATH"
    fi

    echo -e "${GREEN}✓${NC} Skill loaded: $SKILL_PATH"
}

# Invoke Claude Code with brainstorming skill
invoke_claude() {
    local context_file="$1"

    echo ""
    echo -e "${BLUE}======================================${NC}"
    echo -e "${BLUE}Starting Brainstorming Session${NC}"
    echo -e "${BLUE}======================================${NC}"
    echo ""
    echo -e "Description: ${GREEN}$DESCRIPTION${NC}"
    echo ""
    echo -e "${YELLOW}Instructions:${NC}"
    echo "  - Claude will ask clarifying questions one at a time"
    echo "  - Answer questions to refine the design"
    echo "  - Design will be presented in sections (200-300 words each)"
    echo "  - Validate each section before continuing"
    echo "  - Design will be saved to $OUTPUT_DIR/"
    echo ""
    echo -e "${BLUE}--------------------------------------${NC}"
    echo ""

    # Prepare prompt for Claude
    local prompt="I'm using the brainstorming skill to design: $DESCRIPTION

Please follow the brainstorming workflow from skills/brainstorming/SKILL.md:

1. **Understand context**: Ask clarifying questions one at a time
2. **Explore alternatives**: Propose 2-3 approaches with trade-offs
3. **Present design**: Show design in sections (200-300 words each)
4. **Validate incrementally**: Check understanding after each section
5. **Save documentation**: Write validated design to docs/plans/YYYY-MM-DD-<topic>-design.md
6. **Offer PRD generation**: Ask if I want to generate PRD from design

Project context is available in: $context_file

Let's start by understanding the requirements. Ask me clarifying questions one at a time."

    # Note: In a real implementation, this would invoke Claude Code CLI
    # For now, we'll just display instructions
    echo -e "${YELLOW}Note:${NC} This handler prepares the context for brainstorming."
    echo -e "In a full implementation, this would invoke Claude Code with the prepared prompt."
    echo ""
    echo -e "${GREEN}Prompt prepared:${NC}"
    echo "$prompt"
    echo ""
}

# Commit design document if it exists
commit_design() {
    if [ "$AUTO_COMMIT" = false ]; then
        echo -e "${YELLOW}Skipping auto-commit (--no-commit specified)${NC}"
        return 0
    fi

    # Check for design documents in output directory
    local latest_design
    latest_design=$(ls -t "$OUTPUT_DIR"/*.md 2>/dev/null | head -1)

    if [ -n "$latest_design" ] && [ -f "$latest_design" ]; then
        echo -e "${BLUE}Committing design document...${NC}"

        # Add the design document
        git add "$latest_design" 2>/dev/null || error_exit "Failed to add design document to git"

        # Create commit message
        local design_name
        design_name=$(basename "$latest_design" .md)

        git commit -m "docs: Add brainstorming design - $design_name

Design document created through interactive brainstorming session.

Description: $DESCRIPTION
Skill: brainstorming
Output: $latest_design" 2>/dev/null || error_exit "Failed to commit design document"

        echo -e "${GREEN}✓${NC} Design document committed: $latest_design"
    else
        echo -e "${YELLOW}No design document found in $OUTPUT_DIR${NC}"
    fi
}

# Main execution
main() {
    parse_arguments "$@"
    validate_prerequisites
    load_skill

    local context_file
    context_file=$(prepare_context)

    invoke_claude "$context_file"

    # In a full implementation, after Claude completes the brainstorming:
    # commit_design

    echo ""
    echo -e "${GREEN}======================================${NC}"
    echo -e "${GREEN}Brainstorming Session Complete${NC}"
    echo -e "${GREEN}======================================${NC}"
    echo ""
    echo -e "Next steps:"
    echo "  1. Review design document in $OUTPUT_DIR/"
    echo "  2. Generate PRD: ./claude-loop.sh --dynamic '<design summary>'"
    echo "  3. Or manually create PRD from design sections"
    echo ""
}

# Run main function
main "$@"
