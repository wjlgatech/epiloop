#!/usr/bin/env bash
# research-loop.sh - Agentic research team orchestrator
#
# Usage:
#   ./research-loop.sh "What are the latest advances in AI reasoning models?"
#   ./research-loop.sh --state research-state.json  # Resume from existing state
#   ./research-loop.sh --no-checkpoint "Quick research question"  # Skip checkpoint

set -euo pipefail

# Script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Default paths
RESEARCH_STATE_FILE="${RESEARCH_STATE_FILE:-./.claude-loop/research-state.json}"
LIB_DIR="${SCRIPT_DIR}/lib"
DATA_DIR="${SCRIPT_DIR}/data"

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Checkpoint settings
CHECKPOINT_ENABLED=true
AUTO_APPROVE=false

# Display usage
usage() {
  cat <<EOF
Usage: $0 [OPTIONS] "RESEARCH_QUESTION"

Options:
  -s, --state FILE       Path to research state file (default: ./.claude-loop/research-state.json)
  -o, --output DIR       Output directory for research reports (default: ./research-outputs/)
  -h, --help             Display this help message
  --resume               Resume from existing research state
  --no-checkpoint        Disable human checkpoint (not recommended for investment)
  --auto-approve         Auto-approve checkpoints (non-interactive mode)

Human Checkpoint Options:
  --list-pending         List all pending checkpoints
  --approve ID           Approve checkpoint for research ID
  --checkpoint-summary   Show checkpoint summary for current research

Examples:
  # Start new research
  $0 "What are the latest advances in AI reasoning models?"

  # Resume existing research
  $0 --resume

  # Custom state file
  $0 --state my-research.json "How does GPT-4 compare to Claude?"

  # Auto-approve mode (for CI/automation)
  $0 --auto-approve "What are current market trends?"

  # List pending checkpoints
  $0 --list-pending

EOF
  exit 1
}

# Parse command line arguments
RESEARCH_QUESTION=""
RESUME_MODE=false
LIST_PENDING=false
APPROVE_ID=""
CHECKPOINT_SUMMARY=false

while [[ $# -gt 0 ]]; do
  case $1 in
    -s|--state)
      RESEARCH_STATE_FILE="$2"
      shift 2
      ;;
    -o|--output)
      OUTPUT_DIR="$2"
      shift 2
      ;;
    --resume)
      RESUME_MODE=true
      shift
      ;;
    --no-checkpoint)
      CHECKPOINT_ENABLED=false
      shift
      ;;
    --auto-approve)
      AUTO_APPROVE=true
      shift
      ;;
    --list-pending)
      LIST_PENDING=true
      shift
      ;;
    --approve)
      APPROVE_ID="$2"
      shift 2
      ;;
    --checkpoint-summary)
      CHECKPOINT_SUMMARY=true
      shift
      ;;
    -h|--help)
      usage
      ;;
    *)
      if [[ -z "$RESEARCH_QUESTION" ]]; then
        RESEARCH_QUESTION="$1"
        shift
      else
        echo -e "${RED}Error: Multiple research questions provided${NC}"
        usage
      fi
      ;;
  esac
done

# Ensure lib directory exists
if [[ ! -d "$LIB_DIR" ]]; then
  echo -e "${RED}Error: lib directory not found at $LIB_DIR${NC}"
  exit 1
fi

# Ensure data directory exists
mkdir -p "$DATA_DIR"

# Ensure Python 3 is available
if ! command -v python3 &> /dev/null; then
  echo -e "${RED}Error: python3 is required but not installed${NC}"
  exit 1
fi

# Handle checkpoint-related commands
if [[ "$LIST_PENDING" == "true" ]]; then
  echo -e "${BLUE}=== Pending Checkpoints ===${NC}"
  python3 "$LIB_DIR/human_checkpoint.py" --list-pending --state-dir "$(dirname "$RESEARCH_STATE_FILE")"
  exit $?
fi

if [[ -n "$APPROVE_ID" ]]; then
  echo -e "${BLUE}=== Approving Checkpoint ===${NC}"
  python3 "$LIB_DIR/human_checkpoint.py" --approve "$APPROVE_ID" --state-dir "$(dirname "$RESEARCH_STATE_FILE")"
  exit $?
fi

if [[ "$CHECKPOINT_SUMMARY" == "true" ]]; then
  if [[ ! -f "$RESEARCH_STATE_FILE" ]]; then
    echo -e "${RED}Error: No research state file found at $RESEARCH_STATE_FILE${NC}"
    exit 1
  fi
  # Extract research ID from state file
  RESEARCH_ID=$(python3 -c "import json; print(json.load(open('$RESEARCH_STATE_FILE')).get('researchId', 'UNKNOWN'))")
  echo -e "${BLUE}=== Checkpoint Summary ===${NC}"

  CHECKPOINT_ARGS="--research-id $RESEARCH_ID --summary --state-dir $(dirname "$RESEARCH_STATE_FILE")"
  if [[ "$AUTO_APPROVE" == "true" ]]; then
    CHECKPOINT_ARGS="$CHECKPOINT_ARGS --auto-approve"
  fi

  python3 "$LIB_DIR/human_checkpoint.py" $CHECKPOINT_ARGS
  exit $?
fi

# Validate inputs for research mode
if [[ "$RESUME_MODE" == "false" ]] && [[ -z "$RESEARCH_QUESTION" ]]; then
  echo -e "${RED}Error: Research question required (or use --resume)${NC}"
  usage
fi

# Create .claude-loop directory if it doesn't exist
mkdir -p "$(dirname "$RESEARCH_STATE_FILE")"

# Function to run human checkpoint
run_checkpoint() {
  local research_id="$1"
  local state_dir="$(dirname "$RESEARCH_STATE_FILE")"

  if [[ "$CHECKPOINT_ENABLED" != "true" ]]; then
    echo -e "${YELLOW}Checkpoint disabled - proceeding automatically${NC}"
    return 0
  fi

  echo ""
  echo -e "${CYAN}=== Human Checkpoint ===${NC}"

  local checkpoint_args="--research-id $research_id --summary --state-dir $state_dir"

  if [[ "$AUTO_APPROVE" == "true" ]]; then
    checkpoint_args="$checkpoint_args --auto-approve"
  fi

  # Run checkpoint
  if python3 "$LIB_DIR/human_checkpoint.py" $checkpoint_args; then
    return 0
  else
    local exit_code=$?
    # Exit code 1 = cancelled/rejected
    if [[ $exit_code -eq 1 ]]; then
      echo -e "${YELLOW}Checkpoint not approved - research paused${NC}"
      echo -e "Use '$0 --approve $research_id' to approve later"
      return 1
    fi
    return $exit_code
  fi
}

# Function to check if checkpoint is required based on domain
check_if_checkpoint_required() {
  local state_file="$1"

  if [[ ! -f "$state_file" ]]; then
    return 1
  fi

  # Check domain from state file
  local domain=$(python3 -c "import json; print(json.load(open('$state_file')).get('metadata', {}).get('domain', 'general'))" 2>/dev/null || echo "general")

  # Investment domain always requires checkpoint
  if [[ "$domain" == "investment" ]]; then
    if [[ "$CHECKPOINT_ENABLED" != "true" ]]; then
      echo -e "${RED}WARNING: Investment research detected!${NC}"
      echo -e "${RED}Checkpoints are mandatory for investment domain.${NC}"
      echo -e "${YELLOW}Enabling checkpoint...${NC}"
      CHECKPOINT_ENABLED=true
    fi
  fi

  return 0
}

# Main execution
echo -e "${BLUE}=== Research Loop ===${NC}"
echo ""

if [[ "$RESUME_MODE" == "true" ]]; then
  if [[ ! -f "$RESEARCH_STATE_FILE" ]]; then
    echo -e "${RED}Error: No research state file found at $RESEARCH_STATE_FILE${NC}"
    exit 1
  fi
  echo -e "${GREEN}Resuming research from: $RESEARCH_STATE_FILE${NC}"

  # Check if checkpoint required for resumed research
  check_if_checkpoint_required "$RESEARCH_STATE_FILE"
else
  echo -e "${GREEN}Research Question:${NC} $RESEARCH_QUESTION"
  echo ""
fi

# Execute orchestrator
if [[ "$RESUME_MODE" == "true" ]]; then
  python3 "$LIB_DIR/research-orchestrator.py" \
    --state "$RESEARCH_STATE_FILE" \
    --resume
else
  python3 "$LIB_DIR/research-orchestrator.py" \
    --state "$RESEARCH_STATE_FILE" \
    --question "$RESEARCH_QUESTION"
fi

ORCHESTRATOR_EXIT=$?

if [[ $ORCHESTRATOR_EXIT -ne 0 ]]; then
  echo ""
  echo -e "${RED}Research orchestration failed with exit code: $ORCHESTRATOR_EXIT${NC}"
  exit $ORCHESTRATOR_EXIT
fi

# Check if checkpoint required after orchestration
check_if_checkpoint_required "$RESEARCH_STATE_FILE"

# Extract research ID for checkpoint
RESEARCH_ID=$(python3 -c "import json; print(json.load(open('$RESEARCH_STATE_FILE')).get('researchId', 'UNKNOWN'))" 2>/dev/null || echo "UNKNOWN")

# Run checkpoint at synthesis stage
if [[ "$CHECKPOINT_ENABLED" == "true" ]] && [[ "$RESEARCH_ID" != "UNKNOWN" ]]; then
  if ! run_checkpoint "$RESEARCH_ID"; then
    echo ""
    echo -e "${YELLOW}Research paused at checkpoint.${NC}"
    echo -e "State saved to: $RESEARCH_STATE_FILE"
    echo ""
    echo -e "To continue:"
    echo -e "  ${GREEN}$0 --approve $RESEARCH_ID${NC}  # Approve checkpoint"
    echo -e "  ${GREEN}$0 --resume${NC}                # Resume research"
    exit 2  # Special exit code for paused at checkpoint
  fi
fi

echo ""
echo -e "${GREEN}Research completed successfully!${NC}"
echo -e "Results saved to: $RESEARCH_STATE_FILE"

# Show checkpoint log location if logging enabled
if [[ -f "$DATA_DIR/checkpoint_log.json" ]]; then
  echo -e "Checkpoint log: $DATA_DIR/checkpoint_log.json"
fi
