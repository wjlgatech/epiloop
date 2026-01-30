#!/usr/bin/env bash
# run-scwm-research.sh - Execute autonomous SCWM research
#
# Usage:
#   ./run-scwm-research.sh                    # Start from beginning
#   ./run-scwm-research.sh --resume           # Resume from checkpoint
#   ./run-scwm-research.sh --story RS-005     # Run specific story
#   ./run-scwm-research.sh --milestone week2  # Run milestone stories
#   ./run-scwm-research.sh --status           # Show research status

set -euo pipefail

# Script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Configuration
CONFIG_FILE="${SCRIPT_DIR}/config-scwm-research.yaml"
PRD_FILE="${SCRIPT_DIR}/prds/scwm-research.json"
STATE_FILE="${SCRIPT_DIR}/.claude-loop/scwm-research-state.json"
OUTPUT_DIR="${SCRIPT_DIR}/research-outputs/scwm"
LOG_DIR="${SCRIPT_DIR}/logs/scwm-research"

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
CYAN='\033[0;36m'
MAGENTA='\033[0;35m'
NC='\033[0m'

# Defaults
RESUME_MODE=false
SPECIFIC_STORY=""
MILESTONE=""
STATUS_ONLY=false
INTERACTIVE=true
VERBOSE=false

# Display banner
show_banner() {
  echo -e "${CYAN}"
  echo "  ╔═══════════════════════════════════════════════════════════════════╗"
  echo "  ║                                                                   ║"
  echo "  ║   █▀ █▀▀ █░█░█ █▀▄▀█   █▀█ █▀▀ █▀ █▀▀ ▄▀█ █▀█ █▀▀ █░█           ║"
  echo "  ║   ▄█ █▄▄ ▀▄▀▄▀ █░▀░█   █▀▄ ██▄ ▄█ ██▄ █▀█ █▀▄ █▄▄ █▀█           ║"
  echo "  ║                                                                   ║"
  echo "  ║   Self-Calibrating World Model - Autonomous Research Execution   ║"
  echo "  ║                                                                   ║"
  echo "  ╚═══════════════════════════════════════════════════════════════════╝"
  echo -e "${NC}"
}

# Display usage
usage() {
  cat <<EOF
Usage: $0 [OPTIONS]

Autonomous research execution for Self-Calibrating World Model (SCWM)

Options:
  -r, --resume           Resume from existing state
  -s, --story ID         Run specific research story (e.g., RS-005)
  -m, --milestone NAME   Run all stories in milestone (week1, week2, etc.)
  --status               Show current research status
  --interactive          Enable human checkpoints (default: true)
  --auto                 Auto-approve checkpoints (non-interactive)
  -v, --verbose          Verbose output
  -h, --help             Show this help

Milestones:
  week1    Foundation (RS-001, RS-002, RS-003)
  week2    Architecture (RS-004, RS-005)
  week3    Integration (RS-006, RS-007)
  week4    Planning (RS-008, RS-009, RS-010)
  week5    Publication (RS-011)
  week6    Synthesis (RS-012)

Examples:
  # Start full research from beginning
  $0

  # Resume after checkpoint
  $0 --resume

  # Run only literature survey
  $0 --story RS-001

  # Run week 1 milestone
  $0 --milestone week1

  # Run in auto-approve mode (for CI)
  $0 --auto --milestone week1

EOF
  exit 1
}

# Parse arguments
while [[ $# -gt 0 ]]; do
  case $1 in
    -r|--resume)
      RESUME_MODE=true
      shift
      ;;
    -s|--story)
      SPECIFIC_STORY="$2"
      shift 2
      ;;
    -m|--milestone)
      MILESTONE="$2"
      shift 2
      ;;
    --status)
      STATUS_ONLY=true
      shift
      ;;
    --interactive)
      INTERACTIVE=true
      shift
      ;;
    --auto)
      INTERACTIVE=false
      shift
      ;;
    -v|--verbose)
      VERBOSE=true
      shift
      ;;
    -h|--help)
      usage
      ;;
    *)
      echo -e "${RED}Unknown option: $1${NC}"
      usage
      ;;
  esac
done

# Ensure directories exist
mkdir -p "$OUTPUT_DIR"
mkdir -p "$LOG_DIR"
mkdir -p "$(dirname "$STATE_FILE")"

# Check dependencies
check_dependencies() {
  echo -e "${BLUE}Checking dependencies...${NC}"

  if ! command -v python3 &> /dev/null; then
    echo -e "${RED}Error: python3 is required${NC}"
    exit 1
  fi

  if ! command -v jq &> /dev/null; then
    echo -e "${YELLOW}Warning: jq not found, some features may be limited${NC}"
  fi

  # Check PRD file exists
  if [[ ! -f "$PRD_FILE" ]]; then
    echo -e "${RED}Error: PRD file not found: $PRD_FILE${NC}"
    exit 1
  fi

  # Check config file exists
  if [[ ! -f "$CONFIG_FILE" ]]; then
    echo -e "${RED}Error: Config file not found: $CONFIG_FILE${NC}"
    exit 1
  fi

  echo -e "${GREEN}Dependencies OK${NC}"
}

# Show research status
show_status() {
  echo -e "\n${BLUE}═══════════════════════════════════════════════════════════════════${NC}"
  echo -e "${BLUE}                    SCWM Research Status${NC}"
  echo -e "${BLUE}═══════════════════════════════════════════════════════════════════${NC}\n"

  if [[ -f "$STATE_FILE" ]]; then
    # Parse state file
    local total_stories=$(python3 -c "import json; d=json.load(open('$PRD_FILE')); print(len(d['userStories']))")
    local completed=0
    local in_progress=0
    local pending=0

    # Count by parsing passes field
    for status in $(python3 -c "import json; d=json.load(open('$PRD_FILE')); print(' '.join(['true' if s['passes'] else 'false' for s in d['userStories']]))"); do
      if [[ "$status" == "true" ]]; then
        ((completed++)) || true
      else
        ((pending++)) || true
      fi
    done

    echo -e "  Total Stories:    ${CYAN}$total_stories${NC}"
    echo -e "  Completed:        ${GREEN}$completed${NC}"
    echo -e "  Pending:          ${YELLOW}$pending${NC}"
    echo ""

    # Show milestone progress
    echo -e "  ${MAGENTA}Milestone Progress:${NC}"
    for milestone in week1 week2 week3 week4 week5 week6; do
      local milestone_name=$(python3 -c "import json; d=json.load(open('$PRD_FILE')); print(d['milestones']['$milestone']['name'])")
      local milestone_stories=$(python3 -c "import json; d=json.load(open('$PRD_FILE')); print(' '.join(d['milestones']['$milestone']['stories']))")
      local ms_done=0
      local ms_total=0

      for story_id in $milestone_stories; do
        ((ms_total++)) || true
        local passes=$(python3 -c "import json; d=json.load(open('$PRD_FILE')); print([s['passes'] for s in d['userStories'] if s['id']=='$story_id'][0])")
        if [[ "$passes" == "True" ]]; then
          ((ms_done++)) || true
        fi
      done

      if [[ $ms_done -eq $ms_total ]]; then
        echo -e "    $milestone ($milestone_name): ${GREEN}COMPLETE${NC} [$ms_done/$ms_total]"
      elif [[ $ms_done -gt 0 ]]; then
        echo -e "    $milestone ($milestone_name): ${YELLOW}IN PROGRESS${NC} [$ms_done/$ms_total]"
      else
        echo -e "    $milestone ($milestone_name): ${CYAN}PENDING${NC} [$ms_done/$ms_total]"
      fi
    done
  else
    echo -e "  ${YELLOW}No research state found. Starting fresh.${NC}"
  fi

  # Show output files
  echo ""
  echo -e "  ${MAGENTA}Generated Outputs:${NC}"
  if [[ -d "$OUTPUT_DIR" ]] && [[ "$(ls -A $OUTPUT_DIR 2>/dev/null)" ]]; then
    for f in "$OUTPUT_DIR"/*.md; do
      if [[ -f "$f" ]]; then
        echo -e "    - $(basename "$f")"
      fi
    done
  else
    echo -e "    ${YELLOW}No outputs generated yet${NC}"
  fi

  echo ""
}

# Get stories for milestone
get_milestone_stories() {
  local milestone="$1"
  python3 -c "
import json
with open('$PRD_FILE') as f:
    d = json.load(f)
    if '$milestone' in d.get('milestones', {}):
        print(' '.join(d['milestones']['$milestone']['stories']))
    else:
        print('')
"
}

# Run research for a specific story
run_story() {
  local story_id="$1"

  echo -e "\n${BLUE}═══════════════════════════════════════════════════════════════════${NC}"
  echo -e "${BLUE}  Running Research Story: ${CYAN}$story_id${NC}"
  echo -e "${BLUE}═══════════════════════════════════════════════════════════════════${NC}\n"

  # Get story details
  local story_title=$(python3 -c "import json; d=json.load(open('$PRD_FILE')); print([s['title'] for s in d['userStories'] if s['id']=='$story_id'][0])")
  local story_type=$(python3 -c "import json; d=json.load(open('$PRD_FILE')); print([s.get('researchType', 'general') for s in d['userStories'] if s['id']=='$story_id'][0])")
  local suggested_model=$(python3 -c "import json; d=json.load(open('$PRD_FILE')); print([s.get('suggestedModel', 'sonnet') for s in d['userStories'] if s['id']=='$story_id'][0])")
  local agents=$(python3 -c "import json; d=json.load(open('$PRD_FILE')); print(','.join([s.get('suggestedAgents', ['lead-researcher']) for s in d['userStories'] if s['id']=='$story_id'][0]))")

  echo -e "  Title: ${CYAN}$story_title${NC}"
  echo -e "  Type:  ${MAGENTA}$story_type${NC}"
  echo -e "  Model: ${YELLOW}$suggested_model${NC}"
  echo -e "  Agents: ${GREEN}$agents${NC}"
  echo ""

  # Build research question from story
  local research_question=$(python3 -c "
import json
with open('$PRD_FILE') as f:
    d = json.load(f)
    for s in d['userStories']:
        if s['id'] == '$story_id':
            # Combine description and acceptance criteria into research question
            desc = s['description']
            criteria = s['acceptanceCriteria']
            question = f\"{desc}\n\nResearch objectives:\n\"
            for i, c in enumerate(criteria, 1):
                question += f\"{i}. {c}\n\"
            print(question)
            break
")

  # Run research-loop with the story
  local checkpoint_args=""
  if [[ "$INTERACTIVE" == "true" ]]; then
    checkpoint_args=""
  else
    checkpoint_args="--auto-approve"
  fi

  # Execute research-loop
  echo -e "${GREEN}Starting research...${NC}\n"

  # Use research-loop.sh with the constructed question
  if [[ -f "${SCRIPT_DIR}/research-loop.sh" ]]; then
    RESEARCH_STATE_FILE="${STATE_FILE%.json}-${story_id}.json" \
    "${SCRIPT_DIR}/research-loop.sh" $checkpoint_args "$research_question"
  else
    # Fallback to claude-loop.sh with research adapter
    "${SCRIPT_DIR}/claude-loop.sh" \
      --prd "$PRD_FILE" \
      --story "$story_id" \
      --adapter "physical-ai" \
      $checkpoint_args
  fi

  local exit_code=$?

  if [[ $exit_code -eq 0 ]]; then
    echo -e "\n${GREEN}Story $story_id completed successfully!${NC}"

    # Update PRD to mark story as passed
    python3 -c "
import json
with open('$PRD_FILE', 'r') as f:
    d = json.load(f)
for s in d['userStories']:
    if s['id'] == '$story_id':
        s['passes'] = True
        s['notes'] = 'Completed by autonomous research loop'
with open('$PRD_FILE', 'w') as f:
    json.dump(d, f, indent=2)
"
  elif [[ $exit_code -eq 2 ]]; then
    echo -e "\n${YELLOW}Story $story_id paused at checkpoint${NC}"
    echo -e "Resume with: $0 --resume --story $story_id"
  else
    echo -e "\n${RED}Story $story_id failed with exit code: $exit_code${NC}"
    return $exit_code
  fi
}

# Run research for milestone
run_milestone() {
  local milestone="$1"
  local stories=$(get_milestone_stories "$milestone")

  if [[ -z "$stories" ]]; then
    echo -e "${RED}Unknown milestone: $milestone${NC}"
    exit 1
  fi

  local milestone_name=$(python3 -c "import json; d=json.load(open('$PRD_FILE')); print(d['milestones']['$milestone']['name'])")

  echo -e "\n${MAGENTA}═══════════════════════════════════════════════════════════════════${NC}"
  echo -e "${MAGENTA}  Running Milestone: ${CYAN}$milestone - $milestone_name${NC}"
  echo -e "${MAGENTA}═══════════════════════════════════════════════════════════════════${NC}\n"

  # Check dependencies first
  for story_id in $stories; do
    local deps=$(python3 -c "import json; d=json.load(open('$PRD_FILE')); print(' '.join([s.get('dependencies', []) for s in d['userStories'] if s['id']=='$story_id'][0]))")

    for dep in $deps; do
      local dep_passes=$(python3 -c "import json; d=json.load(open('$PRD_FILE')); print([s['passes'] for s in d['userStories'] if s['id']=='$dep'][0])")
      if [[ "$dep_passes" != "True" ]]; then
        echo -e "${YELLOW}Warning: Story $story_id depends on $dep which is not complete${NC}"
      fi
    done
  done

  # Run each story in milestone
  for story_id in $stories; do
    # Check if already complete
    local passes=$(python3 -c "import json; d=json.load(open('$PRD_FILE')); print([s['passes'] for s in d['userStories'] if s['id']=='$story_id'][0])")

    if [[ "$passes" == "True" ]]; then
      echo -e "${GREEN}Story $story_id already complete, skipping${NC}"
      continue
    fi

    run_story "$story_id"

    # Check for human checkpoint between stories
    if [[ "$INTERACTIVE" == "true" ]]; then
      echo ""
      read -p "Continue to next story? [Y/n] " -n 1 -r
      echo
      if [[ $REPLY =~ ^[Nn]$ ]]; then
        echo -e "${YELLOW}Pausing milestone execution${NC}"
        return 2
      fi
    fi
  done

  echo -e "\n${GREEN}Milestone $milestone complete!${NC}"
}

# Run full research
run_full_research() {
  echo -e "\n${MAGENTA}Starting full SCWM research execution...${NC}\n"

  for milestone in week1 week2 week3 week4 week5 week6; do
    # Check if milestone already complete
    local stories=$(get_milestone_stories "$milestone")
    local all_complete=true

    for story_id in $stories; do
      local passes=$(python3 -c "import json; d=json.load(open('$PRD_FILE')); print([s['passes'] for s in d['userStories'] if s['id']=='$story_id'][0])")
      if [[ "$passes" != "True" ]]; then
        all_complete=false
        break
      fi
    done

    if [[ "$all_complete" == "true" ]]; then
      echo -e "${GREEN}Milestone $milestone already complete, skipping${NC}"
      continue
    fi

    run_milestone "$milestone"

    local exit_code=$?
    if [[ $exit_code -ne 0 ]]; then
      return $exit_code
    fi
  done

  echo -e "\n${GREEN}═══════════════════════════════════════════════════════════════════${NC}"
  echo -e "${GREEN}  SCWM Research Complete!${NC}"
  echo -e "${GREEN}═══════════════════════════════════════════════════════════════════${NC}\n"

  echo -e "Final report: ${CYAN}$OUTPUT_DIR/scwm-research-report.md${NC}"
  echo -e "Executive summary: ${CYAN}$OUTPUT_DIR/executive-summary.md${NC}"
}

# Main execution
main() {
  show_banner
  check_dependencies

  if [[ "$STATUS_ONLY" == "true" ]]; then
    show_status
    exit 0
  fi

  show_status

  if [[ -n "$SPECIFIC_STORY" ]]; then
    run_story "$SPECIFIC_STORY"
  elif [[ -n "$MILESTONE" ]]; then
    run_milestone "$MILESTONE"
  elif [[ "$RESUME_MODE" == "true" ]]; then
    echo -e "${YELLOW}Resuming research from last checkpoint...${NC}"
    # Find first incomplete story and run from there
    local next_story=$(python3 -c "
import json
with open('$PRD_FILE') as f:
    d = json.load(f)
    for s in d['userStories']:
        if not s['passes']:
            print(s['id'])
            break
")
    if [[ -n "$next_story" ]]; then
      run_story "$next_story"
    else
      echo -e "${GREEN}All stories complete!${NC}"
    fi
  else
    run_full_research
  fi
}

# Run main
main
