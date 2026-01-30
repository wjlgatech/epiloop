#!/bin/bash
#
# agent-registry.sh - Agent Registry and Selection Engine
#
# Provides:
#   - Agent manifest generation
#   - Keyword-based selection
#   - Tier-based filtering
#   - Cost controls
#   - Composition support
#

set -euo pipefail

# ============================================================================
# Configuration
# ============================================================================

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CLAUDE_LOOP_DIR="$(dirname "$SCRIPT_DIR")"

# Local bundled agents (always available)
LOCAL_AGENTS_DIR="${LOCAL_AGENTS_DIR:-$CLAUDE_LOOP_DIR/agents}"

# External agents directory (optional, for additional specialists)
AGENTS_DIR="${AGENTS_DIR:-}"

MANIFESTS_FILE="${MANIFESTS_FILE:-/tmp/claude-loop-manifests.json}"
MAX_AGENTS_PER_ITERATION="${MAX_AGENTS_PER_ITERATION:-2}"
MAX_TOKENS_PER_AGENT="${MAX_TOKENS_PER_AGENT:-1000}"
ENABLED_TIERS="${ENABLED_TIERS:-1,2}"
COMPOSITION_MODE="${COMPOSITION_MODE:-true}"

# ============================================================================
# Tier Definitions
# ============================================================================

# Tier 1: Core agents (always trusted, auto-enabled)
TIER1_AGENTS=(
  "code-reviewer"
  "test-runner"
  "debugger"
  "security-auditor"
  "git-workflow"
)

# Tier 2: Curated specialists (verified, enabled by default)
TIER2_AGENTS=(
  "python-dev"
  "typescript-specialist"
  "frontend-developer"
  "backend-architect"
  "api-designer"
  "ml-engineer"
  "devops-engineer"
  "documentation-writer"
  "refactoring-specialist"
  "performance-optimizer"
  "data-scientist"
  "prompt-engineer"
  "dependency-manager"
  "first-principles-analyst"
  "product-strategist"
  "contrarian-challenger"
  "code-explainer"
  "academic-paper-generator"
)

# Tier 3: Physical AI / Domain-specific (opt-in)
TIER3_AGENTS=(
  "vision-analyst"
  "sensor-fusion"
  "safety-supervisor"
  "compliance-guardian"
  "anomaly-detector"
  "decision-planner"
  "device-controller"
  "alert-dispatcher"
  "warehouse-orchestrator"
  "quality-inspector"
  "datacenter-optimizer"
)

# ============================================================================
# Phase-Aware Agent Preferences (INV-005)
# ============================================================================

# Phase preference weights: agents are scored by phase relevance
# Format: agent_name:weight where weight is 0-100

# Analysis phase: strategic thinking, first principles, requirements analysis
PHASE_ANALYSIS_AGENTS=(
  "first-principles-analyst:100"
  "product-strategist:90"
  "contrarian-challenger:80"
  "code-explainer:70"
  "documentation-writer:60"
)

# Planning phase: architecture, system design, API contracts
PHASE_PLANNING_AGENTS=(
  "backend-architect:100"
  "api-designer:90"
  "first-principles-analyst:70"
  "product-strategist:60"
  "devops-engineer:50"
)

# Solutioning phase: detailed architecture, technical decisions
PHASE_SOLUTIONING_AGENTS=(
  "backend-architect:100"
  "api-designer:95"
  "security-auditor:80"
  "devops-engineer:75"
  "performance-optimizer:70"
  "ml-engineer:60"
)

# Implementation phase: use existing keyword-based selection with no phase boost
# This is the default behavior when no phase is specified
# Note: Empty array - keyword-based selection takes precedence
PHASE_IMPLEMENTATION_AGENTS=()

# Get preferred agents for a phase with their weights
# Usage: get_phase_preferred_agents <phase>
# Output: space-separated agent:weight pairs
get_phase_preferred_agents() {
  local phase="$1"
  case "$phase" in
    analysis)
      echo "${PHASE_ANALYSIS_AGENTS[@]}"
      ;;
    planning)
      echo "${PHASE_PLANNING_AGENTS[@]}"
      ;;
    solutioning)
      echo "${PHASE_SOLUTIONING_AGENTS[@]}"
      ;;
    implementation|"")
      # Empty array for implementation - use keyword-based selection
      echo ""
      ;;
    *)
      echo ""
      ;;
  esac
}

# Get the phase boost weight for an agent
# Usage: get_phase_boost <agent_name> <phase>
# Output: weight (0-100) or 0 if not in phase preferences
get_phase_boost() {
  local agent_name="$1"
  local phase="$2"
  local preferred
  preferred=$(get_phase_preferred_agents "$phase")

  for entry in $preferred; do
    local name="${entry%%:*}"
    local weight="${entry##*:}"
    if [[ "$name" == "$agent_name" ]]; then
      echo "$weight"
      return
    fi
  done
  echo "0"
}

# Check if phase-aware selection should add specific agents
# Usage: get_phase_boosted_agents <phase> <max_agents>
# Output: list of agents that should be considered for the phase
get_phase_boosted_agents() {
  local phase="$1"
  local max_agents="${2:-2}"
  local preferred
  preferred=$(get_phase_preferred_agents "$phase")

  local count=0
  for entry in $preferred; do
    if [[ $count -ge $max_agents ]]; then
      break
    fi
    local name="${entry%%:*}"
    local tier
    tier=$(get_agent_tier "$name")

    # Only include if tier is enabled
    if is_tier_enabled "$tier"; then
      echo "$name"
      count=$((count + 1))
    fi
  done
}

# ============================================================================
# Keyword Mappings (bash 3.2 compatible)
# ============================================================================

# Maps a keyword to an agent name
# Returns empty string if no match
get_agent_for_keyword() {
  local keyword="$1"
  case "$keyword" in
    # Testing keywords
    test|tests|testing|"unit test"|jest|pytest|coverage)
      echo "test-runner" ;;
    # Security keywords
    security|secure|vulnerability|owasp|cve|audit|authentication|authorization)
      echo "security-auditor" ;;
    # Code review keywords
    review|"code review"|"pr review")
      echo "code-reviewer" ;;
    # Debugging keywords
    debug|bug|fix|error|crash)
      echo "debugger" ;;
    # Git keywords
    git|commit|branch|merge|rebase)
      echo "git-workflow" ;;
    # Python keywords
    python|django|flask|fastapi|pip)
      echo "python-dev" ;;
    # TypeScript keywords
    typescript|ts|interface|generic)
      echo "typescript-specialist" ;;
    # Frontend keywords
    react|vue|angular|css|ui|frontend|component)
      echo "frontend-developer" ;;
    # Backend keywords
    architecture|microservice|scalability|"system design")
      echo "backend-architect" ;;
    # API keywords
    api|rest|graphql|endpoint|openapi)
      echo "api-designer" ;;
    # ML keywords
    ml|"machine learning"|training|pytorch|tensorflow)
      echo "ml-engineer" ;;
    # DevOps keywords
    docker|kubernetes|"ci/cd"|deploy|pipeline)
      echo "devops-engineer" ;;
    # Documentation keywords
    document|readme|docs)
      echo "documentation-writer" ;;
    # Performance keywords
    performance|optimize|slow|benchmark)
      echo "performance-optimizer" ;;
    # Refactoring keywords
    refactor|"clean up"|"technical debt")
      echo "refactoring-specialist" ;;
    *)
      echo "" ;;
  esac
}

# All keywords for iteration
ALL_KEYWORDS="test tests testing jest pytest coverage security secure vulnerability owasp cve audit authentication authorization review debug bug fix error crash git commit branch merge rebase python django flask fastapi pip typescript ts interface generic react vue angular css ui frontend component architecture microservice scalability api rest graphql endpoint openapi ml training pytorch tensorflow docker kubernetes deploy pipeline document readme docs performance optimize slow benchmark refactor"

# ============================================================================
# Functions
# ============================================================================

get_agent_tier() {
  local agent_name="$1"

  for agent in "${TIER1_AGENTS[@]}"; do
    [[ "$agent" == "$agent_name" ]] && echo "1" && return
  done

  for agent in "${TIER2_AGENTS[@]}"; do
    [[ "$agent" == "$agent_name" ]] && echo "2" && return
  done

  for agent in "${TIER3_AGENTS[@]}"; do
    [[ "$agent" == "$agent_name" ]] && echo "3" && return
  done

  echo "4"  # Community/unknown
}

is_tier_enabled() {
  local tier="$1"
  [[ "$ENABLED_TIERS" == *"$tier"* ]]
}

find_agent_file() {
  local agent_name="$1"
  local external_dir="${2:-}"

  # PRIORITY 1: Check local bundled agents first (always available)
  local local_file="$LOCAL_AGENTS_DIR/${agent_name}.md"
  if [[ -f "$local_file" ]]; then
    echo "$local_file"
    return 0
  fi

  # PRIORITY 2: Check external agents directory if provided
  if [[ -n "$external_dir" ]]; then
    local locations=(
      "$external_dir/${agent_name}.md"
      "$external_dir/specialists/${agent_name}.md"
      "$external_dir/utilities/${agent_name}.md"
      "$external_dir/orchestrators/${agent_name}.md"
      "$external_dir/physical-ai/perception/${agent_name}.md"
      "$external_dir/physical-ai/safety/${agent_name}.md"
      "$external_dir/physical-ai/reasoning/${agent_name}.md"
      "$external_dir/physical-ai/action/${agent_name}.md"
      "$external_dir/physical-ai/industry/${agent_name}.md"
      "$external_dir/core/${agent_name}.md"
      "$external_dir/community/${agent_name}.md"
    )

    for loc in "${locations[@]}"; do
      if [[ -f "$loc" ]]; then
        echo "$loc"
        return 0
      fi
    done
  fi

  return 1
}

count_tokens_approx() {
  local file="$1"
  # Rough approximation: 1 token ≈ 4 characters
  local chars
  chars=$(wc -c < "$file" | tr -d ' ')
  echo $((chars / 4))
}

extract_agent_description() {
  local file="$1"
  # Extract first paragraph after the title
  sed -n '1,/^$/p' "$file" | tail -n +2 | head -5 | tr '\n' ' ' | cut -c1-200
}

extract_agent_keywords() {
  local file="$1"
  local name
  name=$(basename "$file" .md)

  # Start with agent name parts
  echo "$name" | tr '-' '\n'

  # Extract keywords from frontmatter if present
  if head -1 "$file" | grep -q "^---"; then
    sed -n '/^---$/,/^---$/p' "$file" | grep -E "^(keywords|tags):" | sed 's/.*://' | tr ',' '\n' | tr -d '[]"'
  fi
}

generate_manifest() {
  local agents_dir="$1"
  local output_file="$2"

  echo "{" > "$output_file"
  echo '  "version": "1.0.0",' >> "$output_file"
  echo '  "generated": "'$(date -Iseconds)'",' >> "$output_file"
  echo '  "agents": {' >> "$output_file"

  local first=true

  # Find all .md files that look like agents
  while IFS= read -r -d '' file; do
    local name
    name=$(basename "$file" .md)

    # Skip non-agent files
    [[ "$name" == "README" ]] && continue
    [[ "$name" == "SKILL" ]] && continue
    [[ "$name" =~ ^[A-Z] ]] && continue  # Skip uppercase files (docs)

    local tier
    tier=$(get_agent_tier "$name")

    local tokens
    tokens=$(count_tokens_approx "$file")

    local description
    description=$(extract_agent_description "$file" | sed 's/"/\\"/g')

    if [[ "$first" == "true" ]]; then
      first=false
    else
      echo "," >> "$output_file"
    fi

    cat >> "$output_file" << AGENT
    "$name": {
      "file": "$file",
      "tier": $tier,
      "tokens": $tokens,
      "description": "$description"
    }
AGENT

  done < <(find "$agents_dir" -name "*.md" -type f -print0 2>/dev/null)

  echo "" >> "$output_file"
  echo "  }" >> "$output_file"
  echo "}" >> "$output_file"
}

# Check if semantic matcher (Python) is available
check_semantic_matcher() {
  local matcher="$SCRIPT_DIR/semantic-matcher.py"
  if [[ -f "$matcher" ]] && command -v python3 &>/dev/null; then
    # Check if sentence-transformers is installed
    if python3 -c "import sentence_transformers" 2>/dev/null; then
      echo "true"
      return
    fi
  fi
  echo "false"
}

# Hybrid agent selection: semantic + keyword matching with phase awareness
# Usage: select_agents_for_story <story_text> [agents_dir] [max_agents] [phase]
# The phase parameter enables phase-aware selection (analysis/planning/solutioning/implementation)
select_agents_for_story() {
  local story_text="$1"
  local agents_dir="${2:-}"
  local max_agents="${3:-$MAX_AGENTS_PER_ITERATION}"
  local phase="${4:-}"  # Optional: analysis, planning, solutioning, implementation

  local matcher="$SCRIPT_DIR/semantic-matcher.py"
  local use_semantic
  use_semantic=$(check_semantic_matcher)

  # Try semantic matching first (more accurate)
  if [[ "$use_semantic" == "true" ]]; then
    local result
    result=$(python3 "$matcher" select "$story_text" "$agents_dir" "$ENABLED_TIERS" "$max_agents" 2>/dev/null) || result=""

    if [[ -n "$result" ]]; then
      # If phase is specified and not implementation, merge phase-preferred agents
      if [[ -n "$phase" ]] && [[ "$phase" != "implementation" ]]; then
        result=$(merge_phase_agents "$result" "$phase" "$max_agents")
      fi
      echo "$result"
      return
    fi
  fi

  # Fallback to keyword-only matching with phase awareness
  keyword_select_agents "$story_text" "$agents_dir" "$max_agents" "$phase"
}

# Merge phase-preferred agents with keyword-selected agents
# Usage: merge_phase_agents <keyword_agents> <phase> <max_agents>
# Output: merged list prioritizing phase agents
merge_phase_agents() {
  local keyword_agents="$1"
  local phase="$2"
  local max_agents="${3:-$MAX_AGENTS_PER_ITERATION}"

  local phase_agents
  phase_agents=$(get_phase_boosted_agents "$phase" "$max_agents")

  # If no phase agents, return keyword agents as-is
  if [[ -z "$phase_agents" ]]; then
    echo "$keyword_agents"
    return
  fi

  local merged=""
  local count=0

  # First, add phase-preferred agents (they take priority)
  for agent in $phase_agents; do
    if [[ $count -ge $max_agents ]]; then
      break
    fi
    # Avoid duplicates
    if ! echo "$merged" | grep -q "$agent"; then
      if [[ -z "$merged" ]]; then
        merged="$agent"
      else
        merged="$merged"$'\n'"$agent"
      fi
      count=$((count + 1))
    fi
  done

  # Then add keyword agents that aren't already included
  for agent in $keyword_agents; do
    if [[ $count -ge $max_agents ]]; then
      break
    fi
    # Avoid duplicates
    if ! echo "$merged" | grep -q "$agent"; then
      merged="$merged"$'\n'"$agent"
      count=$((count + 1))
    fi
  done

  echo "$merged"
}

# Keyword-only agent selection with phase awareness (fallback)
# Usage: keyword_select_agents <story_text> [agents_dir] [max_agents] [phase]
keyword_select_agents() {
  local story_text="$1"
  local agents_dir="${2:-}"
  local max_agents="${3:-$MAX_AGENTS_PER_ITERATION}"
  local phase="${4:-}"  # Optional: analysis, planning, solutioning, implementation

  local selected=""
  local story_lower
  story_lower=$(echo "$story_text" | tr '[:upper:]' '[:lower:]')

  # If phase is specified (and not implementation), start with phase-preferred agents
  if [[ -n "$phase" ]] && [[ "$phase" != "implementation" ]]; then
    local phase_agents
    phase_agents=$(get_phase_boosted_agents "$phase" "$max_agents")

    for agent in $phase_agents; do
      if [[ -z "$selected" ]]; then
        selected="$agent"
      else
        selected="$selected $agent"
      fi
    done

    # Log phase influence in verbose mode (via stderr so it doesn't pollute output)
    if [[ -n "$phase_agents" ]]; then
      echo "[PHASE] Phase '$phase' added agents: $phase_agents" >&2
    fi
  fi

  # Match keywords to agents
  for keyword in $ALL_KEYWORDS; do
    if echo "$story_lower" | grep -q "$keyword"; then
      local agent
      agent=$(get_agent_for_keyword "$keyword")

      if [[ -n "$agent" ]]; then
        local tier
        tier=$(get_agent_tier "$agent")

        # Check if tier is enabled
        if is_tier_enabled "$tier"; then
          # Avoid duplicates (check if already in selected)
          if ! echo "$selected" | grep -q "$agent"; then
            if [[ -z "$selected" ]]; then
              selected="$agent"
            else
              selected="$selected $agent"
            fi
          fi
        fi
      fi
    fi
  done

  # Limit to max agents and output
  local count=0
  for agent in $selected; do
    if [[ $count -lt $max_agents ]]; then
      echo "$agent"
      count=$((count + 1))
    fi
  done
}

load_agent_prompt() {
  local agent_name="$1"
  local agents_dir="$2"
  local max_tokens="${3:-$MAX_TOKENS_PER_AGENT}"

  local file
  if file=$(find_agent_file "$agent_name" "$agents_dir"); then
    local tokens
    tokens=$(count_tokens_approx "$file")

    if [[ $tokens -le $max_tokens ]]; then
      cat "$file"
    else
      # Truncate to max tokens (approximate)
      local max_chars=$((max_tokens * 4))
      head -c "$max_chars" "$file"
      echo ""
      echo "[Agent prompt truncated to $max_tokens tokens]"
    fi
  else
    echo "# Agent not found: $agent_name"
  fi
}

compose_agents() {
  local agents_dir="$1"
  shift
  local agent_names=("$@")

  echo "# Combined Agent Expertise"
  echo ""
  echo "You have access to the following specialized knowledge:"
  echo ""

  for agent in "${agent_names[@]}"; do
    echo "---"
    echo "## ${agent} Expertise"
    echo ""
    load_agent_prompt "$agent" "$agents_dir"
    echo ""
  done
}

# ============================================================================
# CLI Interface
# ============================================================================

if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
  case "${1:-help}" in
    generate-manifest)
      if [[ -z "${2:-}" ]]; then
        echo "Usage: $0 generate-manifest <agents-dir> [output-file]"
        exit 1
      fi
      generate_manifest "$2" "${3:-$MANIFESTS_FILE}"
      echo "Manifest generated: ${3:-$MANIFESTS_FILE}"
      ;;

    select)
      if [[ -z "${2:-}" ]]; then
        echo "Usage: $0 select <story-text> [agents-dir] [max-agents] [phase]"
        echo "  phase: analysis, planning, solutioning, implementation (optional)"
        exit 1
      fi
      select_agents_for_story "$2" "${3:-}" "${4:-$MAX_AGENTS_PER_ITERATION}" "${5:-}"
      ;;

    phase-agents)
      if [[ -z "${2:-}" ]]; then
        echo "Usage: $0 phase-agents <phase>"
        echo "  phase: analysis, planning, solutioning, implementation"
        exit 1
      fi
      phase_name="$2"
      echo "Phase '$phase_name' preferred agents:"
      agents=$(get_phase_preferred_agents "$phase_name")
      if [[ -z "$agents" ]]; then
        echo "  (no specific preferences - uses keyword-based selection)"
      else
        for entry in $agents; do
          name="${entry%%:*}"
          weight="${entry##*:}"
          tier=$(get_agent_tier "$name")
          enabled=""
          if is_tier_enabled "$tier"; then
            enabled="[enabled]"
          else
            enabled="[disabled - tier $tier]"
          fi
          echo "  - $name (weight: $weight) $enabled"
        done
      fi
      ;;

    list-phases)
      echo "Available phases with preferred agents:"
      echo ""
      for phase in analysis planning solutioning implementation; do
        echo "Phase: $phase"
        agents=$(get_phase_preferred_agents "$phase")
        if [[ -z "$agents" ]]; then
          echo "  (keyword-based selection only)"
        else
          for entry in $agents; do
            name="${entry%%:*}"
            weight="${entry##*:}"
            echo "  - $name (weight: $weight)"
          done
        fi
        echo ""
      done
      ;;

    load)
      if [[ -z "${2:-}" ]]; then
        echo "Usage: $0 load <agent-name> [agents-dir]"
        exit 1
      fi
      load_agent_prompt "$2" "${3:-}"
      ;;

    compose)
      if [[ -z "${2:-}" ]]; then
        echo "Usage: $0 compose <agents-dir> <agent1> [agent2] ..."
        exit 1
      fi
      agents_dir="$2"
      shift 2
      compose_agents "$agents_dir" "$@"
      ;;

    tier)
      if [[ -z "${2:-}" ]]; then
        echo "Usage: $0 tier <agent-name>"
        exit 1
      fi
      get_agent_tier "$2"
      ;;

    list-local)
      echo "Bundled agents in $LOCAL_AGENTS_DIR:"
      if [[ -d "$LOCAL_AGENTS_DIR" ]]; then
        for f in "$LOCAL_AGENTS_DIR"/*.md; do
          if [[ -f "$f" ]]; then
            name=$(basename "$f" .md)
            tier=$(get_agent_tier "$name")
            echo "  - $name (tier $tier)"
          fi
        done
      else
        echo "  (no bundled agents found)"
      fi
      ;;

    setup-semantic)
      echo "Setting up semantic matching (requires Python 3)..."
      if ! command -v python3 &>/dev/null; then
        echo "Error: Python 3 not found. Install Python 3 first."
        exit 1
      fi
      echo "Installing sentence-transformers..."
      python3 -m pip install --quiet sentence-transformers
      echo "Pre-computing embeddings for bundled agents..."
      python3 "$SCRIPT_DIR/semantic-matcher.py" embed-agents "$LOCAL_AGENTS_DIR"
      if [[ -n "${AGENTS_DIR:-}" ]] && [[ -d "$AGENTS_DIR" ]]; then
        echo "Pre-computing embeddings for external agents..."
        python3 "$SCRIPT_DIR/semantic-matcher.py" embed-agents "$AGENTS_DIR"
      fi
      echo "Semantic matching setup complete!"
      ;;

    check-semantic)
      local status
      status=$(check_semantic_matcher)
      if [[ "$status" == "true" ]]; then
        echo "Semantic matching: ENABLED"
        echo "  - Python 3: $(python3 --version)"
        echo "  - sentence-transformers: installed"
      else
        echo "Semantic matching: DISABLED (using keyword-only)"
        echo "  Run './agent-registry.sh setup-semantic' to enable"
      fi
      ;;

    help|*)
      cat << 'EOF'
Agent Registry - Selection Engine for claude-loop

HYBRID MATCHING (Semantic + Keyword):
  Uses embedding-based semantic similarity combined with keyword matching
  for robust, accurate agent selection.

  - Semantic matching: Uses sentence-transformers for meaning-based matching
  - Keyword matching: Fast fallback when semantic not available
  - Hybrid scoring: 70% semantic + 30% keyword weight

  Run 'setup-semantic' to enable semantic matching (recommended).

Commands:
  select <story-text> [agents-dir] [max] [phase]
                                           Select agents for a story (hybrid)
                                           Supports phase-aware selection
  load <agent-name> [agents-dir]           Load agent prompt
  compose [agents-dir] <agents...>         Compose multiple agents
  tier <agent-name>                        Get agent tier (1-4)
  list-local                               List bundled agents
  phase-agents <phase>                     Show agents preferred for a phase
  list-phases                              List all phases with their agents
  setup-semantic                           Install & setup semantic matching
  check-semantic                           Check if semantic matching is enabled
  generate-manifest <agents-dir> [output]  Generate agent manifest

Phases (for phase-aware agent selection):
  analysis        - Strategic thinking: first-principles-analyst, product-strategist
  planning        - Architecture: backend-architect, api-designer
  solutioning     - Technical decisions: backend-architect, security-auditor
  implementation  - Default keyword-based selection

Environment Variables:
  LOCAL_AGENTS_DIR            Bundled agents (default: ./agents)
  AGENTS_DIR                  External agents directory (optional)
  MAX_AGENTS_PER_ITERATION    Max agents to select (default: 2)
  MAX_TOKENS_PER_AGENT        Max tokens per agent (default: 1000)
  ENABLED_TIERS               Enabled tiers, comma-separated (default: 1,2)

Bundled Agents (Tier 1):
  code-reviewer, test-runner, debugger, security-auditor, git-workflow

Examples:
  # Setup semantic matching (one-time)
  ./agent-registry.sh setup-semantic

  # Select agents (uses hybrid matching if available)
  ./agent-registry.sh select "Add unit tests for auth"
  ./agent-registry.sh select "Optimize database queries" ~/claude-agents

  # Phase-aware agent selection
  ./agent-registry.sh select "Design user authentication system" "" 2 analysis
  ./agent-registry.sh select "Create REST API endpoints" "" 2 solutioning

  # View phase preferences
  ./agent-registry.sh phase-agents analysis
  ./agent-registry.sh list-phases

  # Check matching mode
  ./agent-registry.sh check-semantic
EOF
      ;;
  esac
fi
