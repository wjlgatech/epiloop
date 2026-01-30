#!/bin/bash
#
# claude-loop.sh - Autonomous Claude Code Loop for Feature Implementation
#
# A native Claude Code equivalent of Ralph that runs Claude in repeated
# iterations until all PRD user stories are complete.
#
# SELF-SUFFICIENT: Bundled core agents work out of the box.
# Use --agents-dir to add external specialists on top of bundled agents.
#
# Usage:
#   ./claude-loop.sh [options]
#
# Options:
#   -m, --max-iterations N   Maximum iterations (default: 10)
#   -p, --prd FILE|DIR|ID   Path to prd.json, PRD directory, or PRD ID
#                           (default: auto-detect from prds/active/ or ./prd.json)
#   -a, --agents-dir DIR    Optional: external agents for more specialists
#   -d, --delay N           Delay between iterations in seconds (default: 2)
#   -v, --verbose           Enable verbose output
#   --no-agents             Disable agent integration
#   --resume                Resume from last checkpoint if available
#   --parallel              Enable parallel PRD execution (coordinator mode)
#   --max-prds N            Maximum parallel PRDs (default: 3)
#   --status                Show parallel execution status
#   --stop PRD-ID           Stop specific PRD worker
#   -h, --help              Show this help message
#
# Requirements:
#   - claude CLI installed and authenticated
#   - jq for JSON parsing
#   - git repository initialized
#

set -euo pipefail

# ============================================================================
# Configuration
# ============================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MAX_ITERATIONS=10
PRD_FILE="./prd.json"
PRD_DIR=""  # Directory containing prd.json (for prds/active/* style PRDs)
PROGRESS_FILE=""  # Path to progress.txt (defaults to PRD_DIR/progress.txt or ./progress.txt)
DELAY_SECONDS=2
VERBOSE=false
PROMPT_FILE="${SCRIPT_DIR}/prompt.md"
LAST_BRANCH_FILE="./.last-branch"
ARCHIVE_DIR="./archive"
COMPLETION_SIGNAL="<loop>COMPLETE</loop>"

# Agent Integration (Hybrid Approach)
# Bundled agents are always available; external agents-dir adds specialists
BUNDLED_AGENTS_DIR="${SCRIPT_DIR}/agents"
AGENTS_DIR=""  # Optional: external agents directory for additional specialists
AGENTS_ENABLED=true
AGENT_REGISTRY="${SCRIPT_DIR}/lib/agent-registry.sh"
MAX_AGENTS_PER_ITERATION=2
MAX_TOKENS_PER_AGENT=1000
ENABLED_TIERS="1,2"

# Execution Logging
EXECUTION_LOGGER="${SCRIPT_DIR}/lib/execution-logger.sh"
EXECUTION_LOGGING_ENABLED=true

# Experience Augmentation
PROMPT_AUGMENTER="${SCRIPT_DIR}/lib/prompt-augmenter.py"
EXPERIENCE_AUGMENTATION_ENABLED=true
MIN_HELPFUL_RATE=0.30
MAX_EXPERIENCES=3

# Unity Automation Mode
UNITY_MODE=false
UNITY_ORCHESTRATOR="${SCRIPT_DIR}/agents/computer_use/orchestrator.py"

# Parallel PRD Execution Mode (NEW)
PARALLEL_MODE=false
PARALLEL_MODE_STATUS=false  # --status flag
PARALLEL_MODE_STOP=""       # --stop <PRD-ID>
PARALLEL_MAX_PRDS=3         # Maximum concurrent PRDs in parallel mode
PRD_COORDINATOR="${SCRIPT_DIR}/lib/prd-coordinator.sh"

# Checkpoint/Resume Mode
RESUME_MODE=false
RESUME_FROM_SESSION=""  # Specific session ID to resume from
CHECKPOINT_DIR="./.claude-loop/checkpoints"

# Session State Management (INV-007)
SESSION_STATE_SCRIPT="${SCRIPT_DIR}/lib/session-state.sh"

# Adaptive Story Splitting (Phase 3, US-001, US-002)
COMPLEXITY_MONITOR="${SCRIPT_DIR}/lib/complexity-monitor.sh"
STORY_SPLITTER="${SCRIPT_DIR}/lib/story-splitter.py"
COMPLEXITY_THRESHOLD=7  # Default threshold (0-10 scale) for triggering story split
ADAPTIVE_SPLITTING_ENABLED=true  # Can be disabled with --no-adaptive
SESSION_STATE_ENABLED=true

# Improvement Management
IMPROVEMENT_MANAGER="${SCRIPT_DIR}/lib/improvement-manager.sh"
IMPROVEMENT_VALIDATOR="${SCRIPT_DIR}/lib/improvement-validator.py"
IMPROVEMENT_MODE=""  # list, review, approve, reject, execute, validate, rollback
IMPROVEMENT_TARGET=""  # PRD name for operations
IMPROVEMENT_NOTES=""  # Notes for approve
IMPROVEMENT_REASON=""  # Reason for reject/rollback
IMPROVEMENT_VALIDATE=false  # Run validation before execution
IMPROVEMENT_FORCE=false  # Force past validation failures
IMPROVEMENT_DRY_RUN=false  # Dry run for rollback

# Gap Analysis Daemon
GAP_ANALYSIS_DAEMON="${SCRIPT_DIR}/lib/gap-analysis-daemon.sh"
DAEMON_MODE=""  # start, stop, status

# Task Execution Daemon (US-205)
TASK_DAEMON="${SCRIPT_DIR}/lib/daemon.sh"
TASK_DAEMON_CMD=""  # start, stop, status, submit, queue, cancel, pause, resume
TASK_DAEMON_ARG=""  # Additional arguments (PRD path, task ID, etc.)
TASK_DAEMON_PRIORITY="normal"  # Task priority: high, normal, low
TASK_DAEMON_WORKERS=1  # Number of workers

# Visual Progress Dashboard (US-207)
DASHBOARD_LAUNCHER="${SCRIPT_DIR}/lib/dashboard-launcher.sh"
DASHBOARD_CMD=""  # start, stop, restart, status, logs, generate-token
DASHBOARD_PORT=8080
DASHBOARD_HOST="127.0.0.1"

# Autonomous Mode
AUTONOMOUS_GATE="${SCRIPT_DIR}/lib/autonomous-gate.py"
AUTONOMOUS_MODE=false
DISABLE_AUTONOMOUS=false

# Multi-LLM Review Integration (LLM-007)
REVIEW_PANEL_SCRIPT="${SCRIPT_DIR}/lib/review_panel.py"
REVIEW_ENABLED=false

# Hook System (US-001 - Tier 1 Pattern Extraction)
HOOKS_DIR="./.claude-loop/hooks"
HOOKS_ENABLED=false  # Disabled by default, enable with --enable-hooks
HOOKS_LOG_FILE="./.claude-loop/logs/hooks.jsonl"

# Learnings JSON Storage (US-002 - Tier 1 Pattern Extraction)
LEARNINGS_FILE="./.claude-loop/learnings.json"
LEARNINGS_ENABLED=false  # Disabled by default, enable with --enable-learnings
MAX_LEARNINGS_IN_CONTEXT=3  # Top N relevant learnings to include in prompt
LIST_LEARNINGS=false
LIST_LEARNINGS_TAG=""
LIST_LEARNINGS_SINCE=""
RATE_LEARNING_ID=""
RATE_LEARNING_ACTION=""

REVIEW_PROVIDERS=""  # Empty = all configured providers
REVIEW_THRESHOLD=7   # Minimum consensus score (1-10)
MAX_REVIEW_CYCLES=2  # Maximum review-fix cycles per story

# MCP Integration (US-005 - Phase 2 Tier 2 Library Integration)
MCP_BRIDGE="${SCRIPT_DIR}/lib/mcp_bridge.sh"
MCP_CLIENT="${SCRIPT_DIR}/lib/mcp_client.py"
MCP_CONFIG_FILE="./.claude-loop/mcp-config.json"
ENABLE_MCP=false  # Disabled by default, enable with --enable-mcp
LIST_MCP_TOOLS=false  # --list-mcp-tools flag

# Multi-Provider LLM Integration (US-006 - Phase 2 Tier 2 Library Integration)
PROVIDER_SELECTOR="${SCRIPT_DIR}/lib/provider_selector.py"
COST_REPORT="${SCRIPT_DIR}/lib/cost_report.py"
LLM_PROVIDERS_CONFIG="${SCRIPT_DIR}/lib/llm_providers.yaml"
ENABLE_MULTI_PROVIDER=false  # Disabled by default, enable with --enable-multi-provider
SHOW_COST_REPORT=false  # --cost-report flag
COST_REPORT_DAYS=7  # Default: last 7 days

# Bounded Delegation (US-007 - Phase 2 Tier 2 Library Integration)
DELEGATION_SCRIPT="${SCRIPT_DIR}/lib/delegation.sh"
ENABLE_DELEGATION=false  # Disabled by default (experimental), enable with --enable-delegation
MAX_DELEGATION_DEPTH=2  # Maximum delegation depth (hard limit)
MAX_CONTEXT_PER_AGENT=100000  # Maximum context budget per agent (tokens)
MAX_DELEGATIONS_PER_STORY=10  # Maximum number of delegations per story

# Full Provider Replacement Mode (LLM-013)
AGENT_RUNTIME="${SCRIPT_DIR}/lib/agent_runtime.py"
PRIMARY_PROVIDER="claude"  # claude, openai, gemini, deepseek
PROVIDER_MODELS=""  # Optional: model override (e.g., gpt-4o, gemini-2.0-flash)

# Single-Command Entry Point (INV-008)
PRD_GENERATOR="${SCRIPT_DIR}/lib/prd-from-description.py"
FEATURE_DESCRIPTION=""  # Feature description for auto-PRD generation
AUTO_GENERATE_PRD=false

# Dynamic PRD Generation (Phase 3, US-004)
DYNAMIC_PRD_GENERATOR="${SCRIPT_DIR}/lib/prd-generator.py"
DYNAMIC_GOAL=""  # High-level goal for dynamic PRD generation
DYNAMIC_OUTPUT=""  # Custom output path for generated PRD
CODEBASE_ANALYSIS=false  # Enable codebase analysis for file scopes

# Progress Dashboard (INV-006)
PROGRESS_DASHBOARD="${SCRIPT_DIR}/lib/progress-dashboard.py"
PROGRESS_DASHBOARD_ENABLED=true
DASHBOARD_COMPACT=false  # Use compact single-line mode

# Progress Indicators (US-001)
PROGRESS_INDICATORS="${SCRIPT_DIR}/lib/progress-indicators.sh"
PROGRESS_INDICATORS_ENABLED=true  # Real-time progress UI with acceptance criteria

# PRD Templates (US-002)
TEMPLATE_GENERATOR="${SCRIPT_DIR}/lib/template-generator.sh"
TEMPLATE_MODE=""  # Mode: list, show, generate
TEMPLATE_NAME=""
TEMPLATE_OUTPUT="prd.json"
declare -a TEMPLATE_VARS  # Array of KEY=VALUE pairs
TEMPLATE_VARS_FILE=""

# Quality Gates (INV-009)
QUALITY_GATES_SCRIPT="${SCRIPT_DIR}/lib/quality-gates.py"
QUALITY_GATES_ENABLED=true
CURRENT_COMPLEXITY_LEVEL=""  # Cached complexity level

# Completion Summary (INV-010)
COMPLETION_SUMMARY_SCRIPT="${SCRIPT_DIR}/lib/completion-summary.py"
COMPLETION_SUMMARY_ENABLED=true

# Solutioning Generator (INV-004, integrated in INV-011)
SOLUTIONING_GENERATOR="${SCRIPT_DIR}/lib/solutioning-generator.py"
SOLUTIONING_ENABLED=true  # Auto-generate architecture.md and ADRs for Level >= 3

# Workspace Sandboxing (US-003)
WORKSPACE_MANAGER="${SCRIPT_DIR}/lib/workspace-manager.sh"
WORKSPACE_FOLDERS=""  # Comma-separated list of workspace folders (e.g., "lib,src,tests")
WORKSPACE_MODE="permissive"  # strict or permissive
WORKSPACE_ENABLED=false

# Safety Checker (US-004)
SAFETY_CHECKER="${SCRIPT_DIR}/lib/safety-checker.sh"
SAFETY_LEVEL="normal"  # paranoid, cautious, normal, yolo
SAFETY_NON_INTERACTIVE=false
SAFETY_DRY_RUN=false
SAFETY_ENABLED=true

# Skills Architecture (US-201)
SKILLS_FRAMEWORK="${SCRIPT_DIR}/lib/skills-framework.sh"
SKILLS_DIR="${SCRIPT_DIR}/skills"
SKILLS_MODE=""  # list, execute
SKILL_NAME=""
declare -a SKILL_ARGS  # Array of arguments for skill execution

# Quick Task Mode (US-203, US-204)
QUICK_TASK_FRAMEWORK="${SCRIPT_DIR}/lib/quick-task-mode.sh"
QUICK_TASK_MODE=""  # execute, history, stats, templates, chain, concurrent
QUICK_TASK_DESC=""
QUICK_TASK_WORKSPACE="."
QUICK_TASK_COMMIT=false
QUICK_TASK_ESCALATE=false
QUICK_TASK_DRY_RUN=false
QUICK_TASK_CONTINUE=false
QUICK_TASK_TEMPLATE=""

# Brainstorming Mode (US-004: Interactive Design Refinement)
BRAINSTORM_MODE=false
BRAINSTORM_DESCRIPTION=""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
MAGENTA='\033[0;35m'
NC='\033[0m' # No Color

# ============================================================================
# Helper Functions
# ============================================================================

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

log_iteration() {
    echo -e "${CYAN}[ITERATION $1/$MAX_ITERATIONS]${NC} $2"
}

log_agent() {
    echo -e "${MAGENTA}[AGENT]${NC} $1"
}

log_debug() {
    if $VERBOSE; then
        echo -e "${BLUE}[DEBUG]${NC} $1"
    fi
}

# Check required external tool dependencies
# Validates that all required external tools are available before execution
# Usage: check_dependencies
check_dependencies() {
    local missing_tools=()
    local optional_missing=()

    # Required tools - script cannot function without these
    local required_tools=("jq" "git" "python3")

    # Optional but recommended tools
    local optional_tools=("curl" "bc")

    # Check required tools
    for tool in "${required_tools[@]}"; do
        if ! command -v "$tool" &> /dev/null; then
            missing_tools+=("$tool")
        fi
    done

    # Check optional tools
    for tool in "${optional_tools[@]}"; do
        if ! command -v "$tool" &> /dev/null; then
            optional_missing+=("$tool")
        fi
    done

    # Report missing required tools and exit
    if [ ${#missing_tools[@]} -gt 0 ]; then
        log_error "Missing required tools: ${missing_tools[*]}"
        log_error ""
        log_error "Please install the missing tools:"
        for tool in "${missing_tools[@]}"; do
            case "$tool" in
                jq)
                    log_error "  - jq: Install with 'brew install jq' (macOS) or 'apt-get install jq' (Linux)"
                    ;;
                git)
                    log_error "  - git: Install from https://git-scm.com/downloads"
                    ;;
                python3)
                    log_error "  - python3: Install from https://www.python.org/downloads/ (3.8 or later required)"
                    ;;
            esac
        done
        exit 1
    fi

    # Warn about optional tools but continue
    if [ ${#optional_missing[@]} -gt 0 ]; then
        log_warn "Optional tools not found: ${optional_missing[*]}"
        log_warn "Some features may be limited. Consider installing:"
        for tool in "${optional_missing[@]}"; do
            case "$tool" in
                curl)
                    log_warn "  - curl: Required for notifications and web features"
                    ;;
                bc)
                    log_warn "  - bc: Required for floating point arithmetic in monitoring"
                    ;;
            esac
        done
    fi

    # Validate Python version (3.8 or later required)
    local python_version
    python_version=$(python3 --version 2>&1 | awk '{print $2}' | cut -d. -f1,2)
    local required_version="3.8"

    if ! awk -v ver="$python_version" -v req="$required_version" 'BEGIN { exit (ver < req) }'; then
        log_error "Python $python_version detected, but Python $required_version or later is required"
        log_error "Please upgrade Python: https://www.python.org/downloads/"
        exit 1
    fi

    log_debug "Dependency check passed: All required tools available"
}

# Validate CLI arguments after parsing
# Ensures all user-provided values are valid and safe
# Usage: validate_cli_arguments
validate_cli_arguments() {
    local errors=()

    # Validate MAX_ITERATIONS is a positive integer
    if ! [[ "$MAX_ITERATIONS" =~ ^[0-9]+$ ]] || [ "$MAX_ITERATIONS" -le 0 ]; then
        errors+=("--max-iterations must be a positive integer (got: '$MAX_ITERATIONS')")
    fi

    # Validate MAX_ITERATIONS is reasonable (prevent accidental huge values)
    if [ "$MAX_ITERATIONS" -gt 1000 ]; then
        log_warn "MAX_ITERATIONS is very high ($MAX_ITERATIONS). This may result in excessive cost or execution time."
    fi

    # Validate DELAY_SECONDS is a non-negative number
    if ! [[ "$DELAY_SECONDS" =~ ^[0-9]+(\.[0-9]+)?$ ]]; then
        errors+=("--delay must be a non-negative number (got: '$DELAY_SECONDS')")
    fi

    # Validate PRD_FILE exists if specified (skip if auto-generate mode)
    if [ -n "$PRD_FILE" ] && [ "$PRD_FILE" != "./prd.json" ] && ! $AUTO_GENERATE_PRD; then
        if [ ! -f "$PRD_FILE" ]; then
            errors+=("PRD file not found: $PRD_FILE")
        fi
    fi

    # Validate AGENTS_DIR exists and is a directory if specified
    if [ -n "$AGENTS_DIR" ] && [ ! -d "$AGENTS_DIR" ]; then
        errors+=("Agents directory not found or not a directory: $AGENTS_DIR")
    fi

    # Validate MAX_AGENTS_PER_ITERATION is a positive integer
    if ! [[ "$MAX_AGENTS_PER_ITERATION" =~ ^[0-9]+$ ]] || [ "$MAX_AGENTS_PER_ITERATION" -le 0 ]; then
        errors+=("--max-agents must be a positive integer (got: '$MAX_AGENTS_PER_ITERATION')")
    fi

    # Validate MAX_AGENTS_PER_ITERATION is reasonable
    if [ "$MAX_AGENTS_PER_ITERATION" -gt 10 ]; then
        log_warn "MAX_AGENTS_PER_ITERATION is high ($MAX_AGENTS_PER_ITERATION). This may result in token limit issues."
    fi

    # Validate ENABLED_TIERS format (comma-separated numbers)
    if [ -n "$ENABLED_TIERS" ]; then
        if ! [[ "$ENABLED_TIERS" =~ ^[0-9]+(,[0-9]+)*$ ]]; then
            errors+=("--agent-tiers must be comma-separated numbers (got: '$ENABLED_TIERS')")
        fi
    fi

    # Validate COMPLEXITY_THRESHOLD is a number between 0-10
    if ! [[ "$COMPLEXITY_THRESHOLD" =~ ^[0-9]+$ ]] || [ "$COMPLEXITY_THRESHOLD" -lt 0 ] || [ "$COMPLEXITY_THRESHOLD" -gt 10 ]; then
        errors+=("--complexity-threshold must be an integer between 0-10 (got: '$COMPLEXITY_THRESHOLD')")
    fi

    # Validate PARALLEL_MAX_PRDS is a positive integer
    if ! [[ "$PARALLEL_MAX_PRDS" =~ ^[0-9]+$ ]] || [ "$PARALLEL_MAX_PRDS" -le 0 ]; then
        errors+=("--max-prds must be a positive integer (got: '$PARALLEL_MAX_PRDS')")
    fi

    # Validate REVIEW_THRESHOLD is a number between 1-10
    if ! [[ "$REVIEW_THRESHOLD" =~ ^[0-9]+$ ]] || [ "$REVIEW_THRESHOLD" -lt 1 ] || [ "$REVIEW_THRESHOLD" -gt 10 ]; then
        errors+=("--review-threshold must be an integer between 1-10 (got: '$REVIEW_THRESHOLD')")
    fi

    # Validate MAX_REVIEW_CYCLES is a positive integer
    if ! [[ "$MAX_REVIEW_CYCLES" =~ ^[0-9]+$ ]] || [ "$MAX_REVIEW_CYCLES" -le 0 ]; then
        errors+=("--max-review-cycles must be a positive integer (got: '$MAX_REVIEW_CYCLES')")
    fi

    # Validate SAFETY_LEVEL is a valid option
    case "$SAFETY_LEVEL" in
        paranoid|cautious|normal|yolo)
            # Valid
            ;;
        *)
            errors+=("--safety-level must be one of: paranoid, cautious, normal, yolo (got: '$SAFETY_LEVEL')")
            ;;
    esac

    # Validate WORKSPACE_MODE is a valid option
    case "$WORKSPACE_MODE" in
        strict|permissive)
            # Valid
            ;;
        *)
            errors+=("--workspace-mode must be one of: strict, permissive (got: '$WORKSPACE_MODE')")
            ;;
    esac

    # Validate PRIMARY_PROVIDER is a valid option
    case "$PRIMARY_PROVIDER" in
        claude|openai|gemini|deepseek)
            # Valid
            ;;
        *)
            errors+=("--provider must be one of: claude, openai, gemini, deepseek (got: '$PRIMARY_PROVIDER')")
            ;;
    esac

    # Validate TASK_DAEMON_PRIORITY is a valid option
    case "$TASK_DAEMON_PRIORITY" in
        high|normal|low)
            # Valid
            ;;
        *)
            errors+=("--priority must be one of: high, normal, low (got: '$TASK_DAEMON_PRIORITY')")
            ;;
    esac

    # Validate TASK_DAEMON_WORKERS is a positive integer
    if ! [[ "$TASK_DAEMON_WORKERS" =~ ^[0-9]+$ ]] || [ "$TASK_DAEMON_WORKERS" -le 0 ]; then
        errors+=("--workers must be a positive integer (got: '$TASK_DAEMON_WORKERS')")
    fi

    # Validate DASHBOARD_PORT is a valid port number (1-65535)
    if ! [[ "$DASHBOARD_PORT" =~ ^[0-9]+$ ]] || [ "$DASHBOARD_PORT" -lt 1 ] || [ "$DASHBOARD_PORT" -gt 65535 ]; then
        errors+=("--port must be a valid port number 1-65535 (got: '$DASHBOARD_PORT')")
    fi

    # Report all errors and exit if any found
    if [ ${#errors[@]} -gt 0 ]; then
        log_error "CLI argument validation failed:"
        for error in "${errors[@]}"; do
            log_error "  - $error"
        done
        log_error ""
        log_error "Run './claude-loop.sh --help' for usage information."
        exit 1
    fi

    log_debug "CLI argument validation passed"
}

# Display progress dashboard (INV-006)
# Usage: display_progress_dashboard [--current-story STORY_ID]
display_progress_dashboard() {
    if ! $PROGRESS_DASHBOARD_ENABLED; then
        return 0
    fi

    if [ ! -f "$PROGRESS_DASHBOARD" ]; then
        log_debug "Progress dashboard not found: $PROGRESS_DASHBOARD"
        return 0
    fi

    local current_story=""
    local compact_flag=""

    # Parse arguments
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --current-story)
                current_story="$2"
                shift 2
                ;;
            *)
                shift
                ;;
        esac
    done

    # Build command arguments
    local args="--prd $PRD_FILE"
    if [ -n "$current_story" ]; then
        args="$args --current-story $current_story"
    fi
    if $DASHBOARD_COMPACT; then
        args="$args --compact"
    fi

    # Run the dashboard
    python3 "$PROGRESS_DASHBOARD" $args 2>/dev/null || true
}

# Display compact progress (single line, for between iterations)
display_progress_compact() {
    if ! $PROGRESS_DASHBOARD_ENABLED; then
        return 0
    fi

    if [ ! -f "$PROGRESS_DASHBOARD" ]; then
        return 0
    fi

    local current_story="${1:-}"
    local args="--prd $PRD_FILE --compact"
    if [ -n "$current_story" ]; then
        args="$args --current-story $current_story"
    fi

    python3 "$PROGRESS_DASHBOARD" $args 2>/dev/null || true
}

show_help() {
    cat << EOF
claude-loop - Autonomous Claude Code Loop for Feature Implementation

USAGE:
    ./claude-loop.sh [OPTIONS]
    ./claude-loop.sh "feature description"

SINGLE-COMMAND ENTRY (INV-008):
    Start claude-loop with just a feature description. No PRD required!

    ./claude-loop.sh "Add user authentication with OAuth"
    ./claude-loop.sh "Create a dark mode toggle for settings"

    This will:
    1. Auto-generate a PRD from your description
    2. Auto-detect complexity level (0-4)
    3. Auto-select track (quick/standard/enterprise)
    4. Auto-select phases (analysis/planning/solutioning/implementation)
    5. Show all auto-detected settings before starting
    6. Begin autonomous implementation

OPTIONS:
    -m, --max-iterations N   Maximum number of iterations (default: 10)
    -p, --prd FILE|DIR|ID   Path to prd.json, PRD directory, or PRD ID
                            Accepts: prds/active/my-feature/prd.json, prds/active/my-feature/,
                            DOC-001, or ./prd.json. Auto-detects if only one active PRD exists.
    -a, --agents-dir DIR    Path to claude-agents directory for expertise
    -d, --delay N           Delay between iterations in seconds (default: 2)
    -v, --verbose           Enable verbose output
    --no-agents             Disable agent integration
    --no-experience         Disable experience augmentation
    --enable-hooks          Enable hook system for lifecycle extension (default: disabled)
    --no-dashboard          Disable progress dashboard display
    --compact-dashboard     Use compact single-line progress display
    --no-progress           Disable real-time progress indicators (for CI/CD)
    --max-agents N          Max agents per iteration (default: 2)
    --agent-tiers TIERS     Enabled tiers, comma-separated (default: 1,2)
    --unity                 Enable Unity automation mode (Quest 3 XR development)
    --resume                Resume from last session if available
    --resume-from <id>      Resume from specific session ID
    --list-sessions         List all available sessions
    --no-session            Disable session state auto-save
    -h, --help              Show this help message

ADAPTIVE STORY SPLITTING (Phase 3, US-001):
    --complexity-threshold N
                           Complexity score threshold (0-10) for triggering story split
                           Default: 7. Higher values make splitting less aggressive.
    --no-adaptive          Disable adaptive story splitting entirely

DYNAMIC PRD GENERATION (Phase 3, US-004):
    --dynamic "goal"       Generate PRD from high-level goal using Claude
                           Example: --dynamic "Add user auth with JWT"
                           Uses Claude to:
                           - Analyze goal and identify requirements
                           - Decompose into 5-10 user stories
                           - Infer dependencies from logical order
                           - Assign complexity estimates
                           - Calculate project complexity
    --dynamic-output FILE  Custom output path for generated PRD
                           Default: prd-{project-name}.json
    --codebase-analysis    Enable codebase analysis to estimate file scopes
                           Scans project for languages, directories, patterns

PRD TEMPLATES (US-002):
    --list-templates        List all available PRD templates
    --show-template <name>  Show template details and required variables
    --template <name>       Generate PRD from template (interactive)
    --template-output <file> Output file for generated PRD (default: prd.json)
    --template-var KEY=VAL  Set template variable (can be used multiple times)
    --template-vars <file>  Load variables from JSON file

WORKSPACE SANDBOXING (US-003):
    --workspace <folders>   Limit execution scope to specific folders (comma-separated)
                           Example: --workspace "lib,src,tests"
                           Features:
                           - Validates folders exist and are within repository
                           - Auto-infers fileScope from workspace contents
                           - Mounts workspace in worker directories for parallel execution
                           - Informs Claude of workspace boundaries in prompts
    --workspace-mode <mode> Workspace enforcement mode (default: permissive)
                           Options:
                           - strict: Hard fail if files outside workspace are accessed
                           - permissive: Warning only, allows outside access
    --disable-workspace-checks
                           Disable all workspace sandboxing checks

CHECKPOINT CONFIRMATIONS (US-004):
    --safety-level <level>  Safety confirmation level (default: normal)
                           Options:
                           - paranoid: Confirm all operations
                           - cautious: Confirm destructive operations and sensitive modifications
                           - normal: Confirm only sensitive file modifications
                           - yolo: No confirmations (use with caution!)
    --safety-dry-run       Show what would be confirmed without executing
    --disable-safety       Disable all safety checks (equivalent to --safety-level yolo)

IMPROVEMENT MANAGEMENT:
    --list-improvements     List all improvement PRDs with status
    --review-improvement <prd_name>
                           Show details of a specific improvement PRD
    --approve-improvement <prd_name> [--notes "..."]
                           Approve an improvement PRD for implementation
    --reject-improvement <prd_name> --reason "..."
                           Reject an improvement PRD with feedback
    --validate-improvement <prd_name> [--force]
                           Validate a PRD before deployment
    --execute-improvement <prd_name> [--validate] [--force]
                           Run an approved improvement PRD with claude-loop
                           --validate: run validation before execution
                           --force: bypass validation blocking conditions
    --rollback-improvement <prd_name> [--reason "..."] [--dry-run]
                           Rollback an improvement that caused regressions
                           --reason: specify reason for rollback
                           --dry-run: show what would happen without changes
    --improvement-history   Show improvement history with outcomes

GAP ANALYSIS DAEMON:
    --start-daemon          Start the background gap analysis daemon
    --stop-daemon           Stop the running daemon
    --daemon-status         Show daemon status

DAEMON MODE (US-205):
    daemon start [workers]  Start the background task execution daemon
                           workers: number of concurrent workers (default: 1)
    daemon stop            Stop the running daemon gracefully
    daemon status          Show daemon status and active workers
    daemon submit <prd> [priority]
                           Submit a PRD to the daemon queue
                           priority: high, normal (default), or low
    daemon queue           Show current task queue
    daemon cancel <task_id>
                           Cancel a pending task
    daemon pause           Pause queue processing
    daemon resume          Resume queue processing

DASHBOARD MODE (US-207):
    dashboard start [--port PORT] [--host HOST]
                           Start the visual progress dashboard backend
                           port: HTTP port (default: 8080)
                           host: bind host (default: 127.0.0.1)
    dashboard stop         Stop the running dashboard server
    dashboard restart [--port PORT]
                           Restart the dashboard server
    dashboard status       Show dashboard server status
    dashboard logs         Show dashboard server logs (tail -f)
    dashboard generate-token
                           Generate new authentication token

    Features:
    - Fire-and-forget workflow: submit tasks and let daemon handle them
    - Priority queuing: high/normal/low priority tasks
    - Worker pool: configurable concurrent workers
    - Graceful shutdown: finishes current tasks before stopping
    - Queue management: view, pause, resume, cancel tasks
    - Persistent queue: survives daemon restarts

QUICK TASK MODE (US-203, US-204):
    quick "task description"
                           Execute a single task without PRD authoring
                           Example: ./claude-loop.sh quick "Add error handling to auth.js"

    Quick Task Options:
    --workspace <dir>      Workspace directory for quick task (default: .)
    --commit               Auto-commit changes on success
    --escalate             Warn and confirm if task appears complex (score >= 60)
    --dry-run              Show execution plan without running (includes cost estimate)
    --continue             Resume last failed quick task from checkpoint
    --template <name>      Use predefined template (refactor, add-tests, fix-bug)

    Quick Task Commands:
    quick history [N] [filter]
                           Show last N quick tasks (default: 20)
                           Filters: all, success, failure
    quick stats            Show quick task statistics (success rate, avg cost, etc.)
    quick templates        List available templates

    Advanced Features (US-204):
    - Complexity Detection: Auto-calculates task complexity (0-100 score)
    - Auto-Escalation: Suggests PRD mode for complex tasks (--escalate flag)
    - Task Chaining: Execute multiple tasks sequentially (via lib script)
    - Templates: Pre-defined patterns for common tasks (refactor, tests, bugs)
    - Cost Estimation: Shows estimated Claude API cost before execution
    - Checkpointing: Saves state every 5 steps for resumption (--continue)
    - Concurrent Execution: Run multiple tasks in parallel (via lib script)
    - Enhanced History: Filter by status, view statistics

    Core Features:
    - Natural language task description
    - Automatic plan generation (5-10 steps based on complexity)
    - User approval checkpoint before execution
    - Isolated worker directory per task
    - Real-time progress indicators
    - Automatic commit message generation (Conventional Commits)
    - Audit trail in .claude-loop/quick-tasks.jsonl

TIER 1 PATTERN EXTRACTION (Phase 1):
    --enable-hooks          Enable hook system for lifecycle extension (US-001)
                           Hooks allow injecting custom bash scripts at key execution points.
                           Hook types: pre_iteration, post_iteration, pre_commit, post_commit,
                                      on_error, on_complete
                           Location: .claude-loop/hooks/<type>/
                           Execution: Alphanumeric order (01-99 prefix convention)

    --enable-learnings      Enable lightweight learnings JSON storage (US-002)
                           Complement ChromaDB experience store with simple JSON-based
                           iteration learnings. Enables rating and querying patterns.
    --list-learnings [--tag TAG] [--since DATE]
                           List all learnings with optional filters
    --rate-learning <ID> --helpful|--unhelpful
                           Rate learning usefulness (increments/decrements helpful_count)

    --enable-decomposition  Enable automatic task decomposition (US-003)
                           Detect oversized stories and automatically suggest decomposition
                           into smaller substories using LLM-powered analysis.
                           Thresholds: estimatedHours > 16 OR description length > 1000 chars
                                      OR acceptance criteria count > 8
    --decompose-story <ID>  Force decomposition of specific story
    --auto-decompose        Auto-approve decompositions without user interaction

    --enable-structured-output  Enable structured JSON output parsing (US-004)
                           Replace text-based sigil detection with structured JSON responses.
                           Improves parsing reliability and enables metadata extraction
                           (confidence scores, reasoning, file changes, complexity).
                           Backward compatible: falls back to sigil format if JSON fails.

MCP INTEGRATION (US-005 - Phase 2):
    --enable-mcp           Enable Model Context Protocol (MCP) integration
                           Enables access to community MCP tools for database, filesystem,
                           API, and cloud service operations.
                           Requires: pip install mcp==1.13.1
                           Configure servers in: .claude-loop/mcp-config.json
    --list-mcp-tools       List all available MCP tools from configured servers
                           Shows tool names, descriptions, and server status

MULTI-PROVIDER LLM (US-006 - Phase 2):
    --enable-multi-provider  Enable multi-provider LLM routing with cost optimization
                           Automatically selects cheapest capable provider based on complexity.
                           Complexity 0-2: cheap models (Haiku, GPT-4o-mini, Gemini Flash)
                           Complexity 3-5: medium models (Sonnet, GPT-4o, Gemini Pro)
                           Complexity 6+: powerful models (Opus, O1, Gemini Thinking)
                           Requires: litellm and provider API keys
                           Configure providers in: lib/llm_providers.yaml
    --cost-report [days]   Show cost analysis report (default: last 7 days)
                           Displays: provider usage, cost breakdown, savings vs baseline,
                           success rates, and performance metrics
                           Example: --cost-report 30 (last 30 days)

BOUNDED DELEGATION (US-007 - Phase 2):
    --enable-delegation    Enable hierarchical task delegation (EXPERIMENTAL)
                           Allows agent to delegate subtasks to subordinate agents.
                           Safety bounds: MAX_DEPTH=2, MAX_CONTEXT=100k tokens
                           Delegation syntax: [delegate:description:hours]
                           Features:
                           - Automatic depth limit enforcement (prevents runaway delegation)
                           - Cycle detection (prevents A→B→A loops)
                           - Context budget management (prevents token explosion)
                           - Parallel execution via git worktrees
                           - Cost attribution to parent story
                           Delegation logged to: .claude-loop/logs/delegation.jsonl

SKILLS FRAMEWORK (US-201, US-202):
    --list-skills          List all available skills with descriptions
    --skill <name>         Execute a specific skill
    --skill-arg <arg>      Pass argument to skill (can be used multiple times)

    Available Skills:
    - hello-world: Example skill demonstrating the framework
    - prd-validator: Validate PRD structure and dependencies
    - test-scaffolder: Generate test file structures from code
    - commit-formatter: Enforce Conventional Commits standards
    - api-spec-generator: Generate OpenAPI specs from code
    - cost-optimizer: Analyze story complexity and recommend models

AUTONOMOUS MODE:
    --autonomous            Enable autonomous mode for daemon (auto-approve low-risk improvements)
    --disable-autonomous    Disable autonomous mode (revert to human-approval)
    --autonomous-status     Show autonomous mode gate status

MULTI-LLM REVIEW:
    --enable-review         Enable multi-LLM review panel after story completion
    --reviewers <list>      Comma-separated list of providers (default: all configured)
                           Example: --reviewers openai,gemini,deepseek
    --review-threshold N    Minimum consensus score to pass (1-10, default: 7)
    --max-review-cycles N   Maximum review-fix cycles per story (default: 2)

PROVIDER REPLACEMENT MODE (LLM-013):
    --provider <provider>   Primary provider for implementation (default: claude)
                           Options: claude, openai, gemini, deepseek
                           WARNING: Non-Claude providers have reduced capabilities
    --model <model>         Override model selection for provider
                           Examples: gpt-4o, gemini-2.0-flash, deepseek-chat

VALIDATION & TESTING:
    --validate-classifier   Run classification accuracy tests (requires >80% for autonomous mode)

DESCRIPTION:
    claude-loop runs Claude Code in repeated iterations to implement complete
    features based on a Product Requirements Document (PRD). Each iteration:

    1. Reads prd.json and progress.txt for context
    2. Picks the highest priority incomplete user story
    3. Auto-selects specialist agents based on story keywords
    4. Implements the story with agent expertise
    5. Runs quality checks (tests, typecheck, lint)
    6. Commits changes and updates state files
    7. Repeats until all stories pass or max iterations reached

AGENT INTEGRATION (Hybrid Approach):
    claude-loop comes with bundled core agents that work out of the box:
    - code-reviewer, test-runner, debugger, security-auditor, git-workflow

    For each story, claude-loop will:
    - Analyze keywords (test, security, python, etc.)
    - Load matching specialist agent prompts
    - Combine agent expertise with iteration instructions
    - Use up to --max-agents specialists per story

    Use --agents-dir to add external specialists on top of bundled agents.

    Agent Tiers:
      1 = Core (bundled: code-reviewer, test-runner, debugger, etc.)
      2 = Curated specialists (python-dev, typescript-specialist, etc.)
      3 = Domain-specific (physical AI, industry-specific)
      4 = Community (untrusted, disabled by default)

UNITY AUTOMATION MODE:
    The --unity flag enables Unity Editor automation for Quest 3 XR development.
    Supported commands:
      unity.setup_quest3   - Full Quest 3 SDK setup workflow
      unity.build          - Build APK for Android/Quest
      unity.deploy         - Deploy APK to connected Quest device
      unity.install_meta_sdk - Install Meta XR SDK from Asset Store
      unity.configure_xr   - Configure XR settings for a platform

    Workflow files (YAML) can define multi-step Unity automation sequences.

SELF-IMPROVEMENT WORKFLOW:
    claude-loop includes a self-improvement pipeline that:
    1. Logs execution data and classifies failures
    2. Clusters similar failures into patterns
    3. Analyzes root causes with 5-Whys decomposition
    4. Generalizes to capability gaps
    5. Generates improvement PRDs automatically

    Use --list-improvements to see generated PRDs pending review.
    Use --approve-improvement to approve and --execute-improvement to run.
    Use --rollback-improvement to revert changes if an improvement causes issues.

    PRD Status Lifecycle:
      pending_review -> approved -> in_progress -> complete -> rolled_back
                    \-> rejected

EXAMPLES:
    # Works out of the box with bundled agents
    ./claude-loop.sh

    # Add external specialists for more expertise
    ./claude-loop.sh --agents-dir ~/claude-agents

    # Unity automation mode for Quest 3 development
    ./claude-loop.sh --unity

    # Full options
    ./claude-loop.sh -a ~/claude-agents -m 20 --max-agents 3 -v

    # Improvement management
    ./claude-loop.sh --list-improvements
    ./claude-loop.sh --review-improvement improve-file-handling-abc123
    ./claude-loop.sh --approve-improvement improve-file-handling-abc123 --notes "Looks good"
    ./claude-loop.sh --reject-improvement improve-ui-abc789 --reason "Too risky"
    ./claude-loop.sh --execute-improvement improve-file-handling-abc123
    ./claude-loop.sh --rollback-improvement improve-file-handling-abc123 --reason "Caused test failures"

FILES (legacy mode - ./prd.json):
    prd.json      - Task state machine with user stories
    progress.txt  - Append-only log of learnings
    AGENTS.md     - Pattern documentation for future iterations
    prompt.md     - Instructions for each Claude iteration

FILES (new PRD structure - prds/active/*):
    prds/
    ├── active/         - PRDs currently in progress
    │   └── my-feature/
    │       ├── prd.json        - User stories
    │       ├── MANIFEST.yaml   - PRD metadata and status
    │       └── progress.txt    - Iteration learnings
    ├── completed/      - Successfully completed PRDs (auto-moved)
    ├── abandoned/      - Abandoned PRDs
    └── drafts/         - Draft PRDs (not yet approved)

    When all stories pass:
    1. MANIFEST.yaml status is updated to 'completed'
    2. PRD directory is moved from prds/active/ to prds/completed/

    Use lib/prd-manager.py for PRD lifecycle management:
    - prd-manager.py create DOC-001 "My Feature"
    - prd-manager.py approve DOC-001
    - prd-manager.py list --status active

EOF
}

check_dependencies() {
    local missing=()

    if ! command -v claude &> /dev/null; then
        missing+=("claude")
    fi

    if ! command -v jq &> /dev/null; then
        missing+=("jq")
    fi

    if ! command -v git &> /dev/null; then
        missing+=("git")
    fi

    if [ ${#missing[@]} -ne 0 ]; then
        log_error "❌ Missing required dependencies"
        log_error ""
        log_error "   Missing: ${missing[*]}"
        log_error ""
        log_info "💡 Installation instructions:"
        for dep in "${missing[@]}"; do
            case "$dep" in
                jq)
                    log_info "   • jq:"
                    log_info "       macOS:   brew install jq"
                    log_info "       Ubuntu:  sudo apt-get install jq"
                    log_info "       Other:   https://stedolan.github.io/jq/download/"
                    ;;
                git)
                    log_info "   • git:"
                    log_info "       macOS:   brew install git"
                    log_info "       Ubuntu:  sudo apt-get install git"
                    log_info "       Other:   https://git-scm.com/downloads"
                    ;;
                python3)
                    log_info "   • python3 (3.8 or later):"
                    log_info "       macOS:   brew install python3"
                    log_info "       Ubuntu:  sudo apt-get install python3"
                    log_info "       Other:   https://www.python.org/downloads/"
                    ;;
            esac
            log_info ""
        done
        exit 1
    fi
}

check_git_repo() {
    if ! git rev-parse --is-inside-work-tree &> /dev/null; then
        log_error "❌ Not inside a git repository"
        log_error ""
        log_error "   Current directory: $(pwd)"
        log_error "   Working with: $PRD_FILE"
        log_error ""
        log_info "💡 Why this matters:"
        log_info "   claude-loop uses git to track changes and create commits for each story."
        log_info ""
        log_info "💡 Next steps:"
        log_info "   1. Initialize git in this directory:"
        log_info "      git init"
        log_info ""
        log_info "   2. Or navigate to an existing git repository:"
        log_info "      cd /path/to/your/git/repo"
        log_info ""
        log_info "   3. After initializing, configure git (if needed):"
        log_info "      git config user.name \"Your Name\""
        log_info "      git config user.email \"your.email@example.com\""
        exit 1
    fi
}

check_prd_exists() {
    if [ ! -f "$PRD_FILE" ]; then
        log_error "❌ PRD file not found"
        log_error ""
        log_error "   Location checked: $PRD_FILE"
        log_error "   Current directory: $(pwd)"
        log_error ""
        log_info "💡 Next steps:"
        log_info "   1. Generate a PRD from description:"
        log_info "      ./claude-loop.sh --dynamic \"Your feature description\""
        log_info ""
        log_info "   2. Create a new PRD manually:"
        log_info "      python3 lib/prd-manager.py create <PRD-ID> \"Feature Title\""
        log_info ""
        log_info "   3. Use an existing PRD:"
        log_info "      ./claude-loop.sh --prd path/to/your/prd.json"
        log_info ""
        log_info "   4. List available PRDs:"
        log_info "      ls prds/*.json 2>/dev/null || echo \"No PRDs found in prds/ directory\""
        exit 1
    fi

    # Validate PRD structure and schema
    log_info "Validating PRD structure..."

    # Source prd-parser.sh for validation functions
    local prd_parser="${SCRIPT_DIR}/lib/prd-parser.sh"
    if [ ! -f "$prd_parser" ]; then
        log_warn "PRD parser not found, skipping validation: $prd_parser"
        return 0
    fi

    source "$prd_parser"

    # Run validation and capture errors
    local validation_output
    validation_output=$(validate_prd "$PRD_FILE" 2>&1)
    local validation_result=$?

    if [ $validation_result -ne 0 ]; then
        log_error "❌ PRD validation failed"
        log_error ""
        log_error "   File: $PRD_FILE"
        log_error ""
        log_error "   Validation errors:"
        echo "$validation_output" | while IFS= read -r line; do
            log_error "     • $line"
        done
        log_error ""
        log_info "💡 Common validation issues:"
        log_info "   • Missing required fields (project, branchName, userStories)"
        log_info "   • Invalid JSON syntax (check for missing commas, braces)"
        log_info "   • Missing story fields (id, title, acceptanceCriteria, priority)"
        log_info "   • Circular dependencies between stories"
        log_info ""
        log_info "💡 To fix:"
        log_info "   1. Validate JSON syntax:    jq . $PRD_FILE"
        log_info "   2. Check schema:            cat docs/prd-schema.md"
        log_info "   3. Use PRD validator:       python3 lib/prd-manager.py validate $PRD_FILE"
        exit 1
    fi

    log_success "PRD validation passed"
}

# Auto-detect active PRD if only one exists in prds/active/
auto_detect_active_prd() {
    local prds_active_dir="${SCRIPT_DIR}/prds/active"

    # Check if prds/active/ exists
    if [ ! -d "$prds_active_dir" ]; then
        return 1
    fi

    # Find all prd.json files in prds/active/*/
    local prd_files=()
    for dir in "$prds_active_dir"/*/; do
        if [ -d "$dir" ] && [ -f "$dir/prd.json" ]; then
            prd_files+=("$dir/prd.json")
        fi
    done

    local count=${#prd_files[@]}

    if [ "$count" -eq 0 ]; then
        log_debug "No active PRDs found in prds/active/"
        return 1
    elif [ "$count" -eq 1 ]; then
        PRD_FILE="${prd_files[0]}"
        PRD_DIR="$(dirname "$PRD_FILE")"
        log_info "Auto-detected active PRD: $PRD_FILE"
        return 0
    else
        log_warn "Multiple active PRDs found in prds/active/:"
        for prd in "${prd_files[@]}"; do
            log_warn "  - $prd"
        done
        log_info "Please specify which PRD to use with --prd <path>"
        return 1
    fi
}

# Resolve PRD path - supports new prds/active/* structure
resolve_prd_path() {
    local prd_path="$1"

    # If path is relative to prds/active/, expand it
    if [[ "$prd_path" == prds/active/* ]] || [[ "$prd_path" == ./prds/active/* ]]; then
        # Convert to absolute path
        local full_path="${SCRIPT_DIR}/${prd_path#./}"
        if [ -f "$full_path" ]; then
            PRD_FILE="$full_path"
            PRD_DIR="$(dirname "$full_path")"
            return 0
        fi
    fi

    # Check if it's a directory containing prd.json
    if [ -d "$prd_path" ] && [ -f "$prd_path/prd.json" ]; then
        PRD_FILE="$prd_path/prd.json"
        PRD_DIR="$prd_path"
        return 0
    fi

    # Check if it's a direct path to prd.json
    if [ -f "$prd_path" ]; then
        PRD_FILE="$prd_path"
        PRD_DIR="$(dirname "$prd_path")"
        return 0
    fi

    # Check if it's a PRD ID and search in prds/active/
    local prds_active_dir="${SCRIPT_DIR}/prds/active"
    if [ -d "$prds_active_dir" ]; then
        for dir in "$prds_active_dir"/*/; do
            if [ -d "$dir" ] && [ -f "$dir/prd.json" ]; then
                # Check manifest for matching ID
                local manifest_file="$dir/MANIFEST.yaml"
                if [ -f "$manifest_file" ]; then
                    local prd_id
                    prd_id=$(grep -E '^id:' "$manifest_file" | head -1 | cut -d':' -f2 | tr -d ' ')
                    if [ "$prd_id" = "$prd_path" ]; then
                        PRD_FILE="$dir/prd.json"
                        PRD_DIR="$dir"
                        log_info "Resolved PRD ID '$prd_path' to: $PRD_FILE"
                        return 0
                    fi
                fi
            fi
        done
    fi

    # Fallback to treating it as a file path
    PRD_FILE="$prd_path"
    PRD_DIR=""
    return 0
}

check_prompt_exists() {
    if [ ! -f "$PROMPT_FILE" ]; then
        log_error "Prompt file not found: $PROMPT_FILE"
        log_info "Please ensure prompt.md exists in the script directory."
        exit 1
    fi
}

check_execution_logger() {
    if [ ! -f "$EXECUTION_LOGGER" ]; then
        log_warn "Execution logger not found: $EXECUTION_LOGGER"
        EXECUTION_LOGGING_ENABLED=false
        return
    fi

    # Source the execution logger
    source "$EXECUTION_LOGGER"
    log_info "Execution logging: Enabled"
}

check_prompt_augmenter() {
    if ! $EXPERIENCE_AUGMENTATION_ENABLED; then
        log_info "Experience augmentation: Disabled (--no-experience)"
        return
    fi

    if [ ! -f "$PROMPT_AUGMENTER" ]; then
        log_warn "Prompt augmenter not found: $PROMPT_AUGMENTER"
        EXPERIENCE_AUGMENTATION_ENABLED=false
        return
    fi

    # Check if Python 3 is available
    if ! command -v python3 &> /dev/null; then
        log_warn "Python3 not found, disabling experience augmentation"
        EXPERIENCE_AUGMENTATION_ENABLED=false
        return
    fi

    log_info "Experience augmentation: Enabled"
}

# ============================================================================
# Session State Integration (INV-007)
# ============================================================================

check_session_state() {
    if ! $SESSION_STATE_ENABLED; then
        log_debug "Session state: Disabled"
        return 1
    fi

    if [ ! -f "$SESSION_STATE_SCRIPT" ]; then
        log_warn "Session state script not found: $SESSION_STATE_SCRIPT"
        SESSION_STATE_ENABLED=false
        return 1
    fi

    # Source the session state script
    source "$SESSION_STATE_SCRIPT"
    log_info "Session state: Enabled (progress auto-saves)"
    return 0
}

# Initialize or resume session
# Returns: 0 if new session, iteration number if resuming
init_or_resume_session() {
    if ! $SESSION_STATE_ENABLED; then
        return 0
    fi

    # Check for specific session ID to resume
    if [ -n "$RESUME_FROM_SESSION" ]; then
        log_info "Attempting to resume session: $RESUME_FROM_SESSION"
        if resume_session_by_id "$RESUME_FROM_SESSION" > /dev/null 2>&1; then
            local resume_info
            resume_info=$(resume_session "true")
            local resume_iter
            resume_iter=$(echo "$resume_info" | jq -r '.iteration // 0')
            echo "$resume_iter"
            return 0
        else
            log_error "Session not found: $RESUME_FROM_SESSION"
            exit 1
        fi
    fi

    # Check for crash recovery
    if has_resumable_session "$PRD_FILE"; then
        if detect_crash; then
            # Display crash recovery message
            display_recovery_message

            # Prompt user for recovery choice
            if prompt_recovery_confirmation; then
                # User chose to resume
                log_info "Recovering from crash..."

                # Get crash info for metrics
                local crash_info
                crash_info=$(get_crash_info)
                local last_saved
                last_saved=$(echo "$crash_info" | jq -r '.last_saved_at')
                local current_time
                current_time=$(date -u +%s)
                local last_saved_seconds
                last_saved_seconds=$(date -j -f "%Y-%m-%dT%H:%M:%SZ" "$last_saved" +%s 2>/dev/null) || last_saved_seconds=$current_time
                local time_lost=$((current_time - last_saved_seconds))

                local resume_info
                resume_info=$(resume_session "true")
                local resume_iter
                resume_iter=$(echo "$resume_info" | jq -r '.iteration // 0')

                # Log recovery metrics
                log_recovery_metrics "$resume_iter" "$time_lost"

                log_success "Recovery complete. Continuing from iteration $resume_iter"
                echo ""

                echo "$resume_iter"
                return 0
            else
                # User chose fresh start
                log_info "Starting fresh session..."
                clear_session
                init_session "$PRD_FILE" > /dev/null 2>&1 || true
                echo "0"
                return 0
            fi
        fi
    fi

    # Check for resumable session (normal resume without crash)
    if $RESUME_MODE && has_resumable_session "$PRD_FILE"; then
        echo ""
        log_info "Found previous session to resume"
        local resume_info
        resume_info=$(resume_session "true")
        local resume_iter
        resume_iter=$(echo "$resume_info" | jq -r '.iteration // 0')
        local resume_completed
        resume_completed=$(echo "$resume_info" | jq -r '.stories_completed // 0')
        local resume_total
        resume_total=$(echo "$resume_info" | jq -r '.stories_total // 0')

        log_success "Resuming: $resume_completed/$resume_total stories complete, iteration $resume_iter"
        echo ""

        # Return the iteration to start from
        echo "$resume_iter"
        return 0
    fi

    # Initialize new session
    init_session "$PRD_FILE" > /dev/null 2>&1 || true
    echo "0"
}

# Save session state after story progress
# Usage: save_story_progress <story_id> <iteration> [phase]
save_story_progress() {
    if ! $SESSION_STATE_ENABLED; then
        return 0
    fi

    local story_id="$1"
    local iteration="$2"
    local phase="${3:-$CURRENT_PHASE}"

    save_session_state "$story_id" "$iteration" "$phase" 2>/dev/null || true
}

# Mark session as complete
finish_session() {
    if ! $SESSION_STATE_ENABLED; then
        return 0
    fi

    complete_session 2>/dev/null || true
}

# List available sessions
show_sessions() {
    if ! $SESSION_STATE_ENABLED; then
        log_warn "Session state not enabled"
        return 1
    fi

    check_session_state || return 1
    list_sessions "text"
}

get_experience_augmentation() {
    local problem_text="$1"
    local story_id="$2"

    if ! $EXPERIENCE_AUGMENTATION_ENABLED; then
        return
    fi

    # Run the prompt augmenter to get relevant experiences
    local augmentation
    augmentation=$(python3 "$PROMPT_AUGMENTER" augment "$problem_text" \
        --project-path "." \
        --min-helpful-rate "$MIN_HELPFUL_RATE" \
        --max-experiences "$MAX_EXPERIENCES" \
        2>/dev/null) || true

    # Return the augmentation if not empty
    if [ -n "$augmentation" ] && [ "$augmentation" != "" ]; then
        # Log the augmentation for tracking
        if $EXECUTION_LOGGING_ENABLED; then
            # Get augmentation metadata in JSON
            local aug_meta
            aug_meta=$(python3 "$PROMPT_AUGMENTER" check "$problem_text" \
                --project-path "." \
                --min-helpful-rate "$MIN_HELPFUL_RATE" \
                --max-experiences "$MAX_EXPERIENCES" \
                --json 2>/dev/null) || aug_meta="{}"

            # Extract counts for logging
            local exp_count
            exp_count=$(echo "$aug_meta" | jq -r '.experience_count // 0' 2>/dev/null) || exp_count=0

            log_debug "Experience augmentation: $exp_count experience(s) included"
        fi

        echo "$augmentation"
    fi
}

check_agents_dir() {
    # Check if agent registry exists
    if [ ! -f "$AGENT_REGISTRY" ]; then
        log_warn "Agent registry not found: $AGENT_REGISTRY"
        log_info "Agent integration disabled."
        AGENTS_ENABLED=false
        return
    fi

    # Check bundled agents (always available)
    if [ -d "$BUNDLED_AGENTS_DIR" ]; then
        local bundled_count
        bundled_count=$(ls -1 "$BUNDLED_AGENTS_DIR"/*.md 2>/dev/null | wc -l | tr -d ' ')
        if [ "$bundled_count" -gt 0 ]; then
            log_info "Bundled agents: $bundled_count core agents available"
        fi
    else
        log_warn "Bundled agents directory not found: $BUNDLED_AGENTS_DIR"
    fi

    # Check external agents directory (optional, for additional specialists)
    if [ -n "$AGENTS_DIR" ]; then
        # Expand tilde
        AGENTS_DIR="${AGENTS_DIR/#\~/$HOME}"

        if [ -d "$AGENTS_DIR" ]; then
            log_info "External agents: $AGENTS_DIR"
        else
            log_warn "External agents directory not found: $AGENTS_DIR"
            log_info "Using bundled agents only."
            AGENTS_DIR=""
        fi
    fi

    # Agents enabled if we have bundled or external agents
    if [ -d "$BUNDLED_AGENTS_DIR" ] || [ -n "$AGENTS_DIR" ]; then
        AGENTS_ENABLED=true
    else
        log_warn "No agents available. Agent integration disabled."
        AGENTS_ENABLED=false
    fi
}

check_workspace() {
    if ! $WORKSPACE_ENABLED; then
        log_debug "Workspace sandboxing: Disabled"
        return 0
    fi

    if [ ! -f "$WORKSPACE_MANAGER" ]; then
        log_warn "Workspace manager not found: $WORKSPACE_MANAGER"
        log_info "Workspace sandboxing disabled."
        WORKSPACE_ENABLED=false
        return 1
    fi

    # Source the workspace manager
    source "$WORKSPACE_MANAGER"

    # Initialize workspace
    init_workspace "$WORKSPACE_FOLDERS" "$WORKSPACE_MODE"

    # Validate workspace folders
    if ! validate_workspace_folders; then
        log_error "Workspace validation failed"
        exit 1
    fi

    # Auto-infer fileScope if workspace is enabled
    if [ -f "$PRD_FILE" ]; then
        update_prd_file_scope "$PRD_FILE" || true
    fi

    log_info "Workspace sandboxing: Enabled (mode: $WORKSPACE_MODE)"
    return 0
}

check_safety_checker() {
    if ! $SAFETY_ENABLED; then
        log_debug "Safety checker: Disabled"
        return 0
    fi

    if [ ! -f "$SAFETY_CHECKER" ]; then
        log_warn "Safety checker not found: $SAFETY_CHECKER"
        log_info "Safety checks disabled."
        SAFETY_ENABLED=false
        return 1
    fi

    # Source the safety checker
    source "$SAFETY_CHECKER"

    # Determine non-interactive mode
    # In CI/CD environments or when --non-interactive is set
    local non_interactive="$SAFETY_NON_INTERACTIVE"
    if [ ! -t 0 ] || [ -n "$CI" ]; then
        non_interactive=true
    fi

    # Initialize safety checker
    init_safety_checker "$SAFETY_LEVEL" "$non_interactive" "$SAFETY_DRY_RUN"

    log_info "Safety checker: Enabled (level: $SAFETY_LEVEL)"
    return 0
}

get_branch_from_prd() {
    jq -r '.branchName // "feature/claude-loop"' "$PRD_FILE"
}

get_project_name() {
    jq -r '.project // "unnamed-project"' "$PRD_FILE"
}

get_incomplete_stories_count() {
    jq '[.userStories[] | select(.passes == false)] | length' "$PRD_FILE"
}

get_total_stories_count() {
    jq '.userStories | length' "$PRD_FILE"
}

get_next_story() {
    # Get the highest priority (lowest number) story with passes=false
    jq -r '[.userStories[] | select(.passes == false)] | sort_by(.priority) | .[0] | "\(.id)|\(.title)|\(.description)"' "$PRD_FILE"
}

get_story_text() {
    # Get full story details for agent selection
    local story_id="$1"
    jq -r --arg id "$story_id" '.userStories[] | select(.id == $id) | "\(.title) \(.description) \(.acceptanceCriteria | join(" "))"' "$PRD_FILE"
}

archive_previous_run() {
    local current_branch="$1"

    if [ -f "$LAST_BRANCH_FILE" ]; then
        local last_branch
        last_branch=$(cat "$LAST_BRANCH_FILE")

        if [ "$last_branch" != "$current_branch" ]; then
            log_info "Branch changed from '$last_branch' to '$current_branch'"
            log_info "Archiving previous run..."

            local timestamp
            timestamp=$(date +%Y%m%d_%H%M%S)
            local archive_path="${ARCHIVE_DIR}/${last_branch//\//_}_${timestamp}"

            mkdir -p "$archive_path"

            # Archive state files if they exist
            [ -f "progress.txt" ] && cp "progress.txt" "$archive_path/"
            [ -f "$PRD_FILE" ] && cp "$PRD_FILE" "$archive_path/"

            log_success "Archived to: $archive_path"

            # Reset progress for new branch
            rm -f "progress.txt"
        fi
    fi

    # Update last branch tracker
    echo "$current_branch" > "$LAST_BRANCH_FILE"
}

ensure_correct_branch() {
    local target_branch="$1"
    local current_branch
    current_branch=$(git branch --show-current)

    if [ "$current_branch" != "$target_branch" ]; then
        log_info "Switching to branch: $target_branch"

        # Check if branch exists
        if git show-ref --verify --quiet "refs/heads/$target_branch"; then
            git checkout "$target_branch"
        else
            log_info "Creating new branch: $target_branch"
            git checkout -b "$target_branch"
        fi
    fi
}

initialize_progress_file() {
    # Determine progress file location
    # If PRD_DIR is set (new structure), create progress.txt inside PRD directory
    # Otherwise, use PROGRESS_FILE or default to ./progress.txt
    local progress_path
    if [ -n "$PROGRESS_FILE" ]; then
        progress_path="$PROGRESS_FILE"
    elif [ -n "$PRD_DIR" ]; then
        progress_path="$PRD_DIR/progress.txt"
    else
        progress_path="./progress.txt"
    fi

    # Export for use by other functions
    PROGRESS_FILE="$progress_path"

    if [ ! -f "$progress_path" ]; then
        local project_name
        project_name=$(get_project_name)

        # Ensure parent directory exists
        mkdir -p "$(dirname "$progress_path")"

        cat > "$progress_path" << EOF
# Progress Log: ${project_name}
# Created: $(date '+%Y-%m-%d %H:%M:%S')
#
# This file tracks learnings and progress across claude-loop iterations.
# Each iteration appends its findings here for future iterations to learn from.

## Codebase Patterns
<!-- Critical patterns discovered - updated by each iteration -->

---

## Iteration History

EOF
        log_info "Initialized progress.txt at: $progress_path"
    else
        log_debug "Progress file exists: $progress_path"
    fi
}

initialize_agents_file() {
    if [ ! -f "AGENTS.md" ]; then
        cat > "AGENTS.md" << EOF
# AGENTS.md - Pattern Documentation

This file documents patterns discovered during development for AI agents
and future developers. Updated automatically by claude-loop iterations.

## Project Structure

<!-- Document key directories and their purposes -->

## Common Commands

\`\`\`bash
# Add project-specific commands here
\`\`\`

## Discovered Patterns

<!-- Patterns learned during implementation -->

## Gotchas & Warnings

<!-- Common pitfalls to avoid -->

EOF
        log_info "Initialized AGENTS.md"
    fi
}

# ============================================================================
# Checkpoint Functions
# ============================================================================

get_workflow_id() {
    # Generate a workflow ID based on branch name and project
    local project_name
    project_name=$(get_project_name)
    local branch_name
    branch_name=$(get_branch_from_prd)
    echo "${project_name}_${branch_name}" | tr '/' '_' | tr -cd '[:alnum:]_-'
}

get_checkpoint_file() {
    local workflow_id="$1"
    local step_index="$2"
    local step_id="$3"
    local timestamp
    timestamp=$(date +%Y%m%d_%H%M%S)
    local safe_step_id
    safe_step_id=$(echo "$step_id" | tr -cd '[:alnum:]_-')
    echo "${CHECKPOINT_DIR}/${workflow_id}/$(printf '%04d' "$step_index")_${safe_step_id}_${timestamp}.json"
}

list_checkpoints() {
    local workflow_id="$1"
    local checkpoint_path="${CHECKPOINT_DIR}/${workflow_id}"

    if [ -d "$checkpoint_path" ]; then
        find "$checkpoint_path" -name "*.json" -type f 2>/dev/null | sort
    fi
}

get_latest_checkpoint() {
    local workflow_id="$1"
    list_checkpoints "$workflow_id" | tail -1
}

load_checkpoint() {
    local checkpoint_file="$1"

    if [ -f "$checkpoint_file" ]; then
        cat "$checkpoint_file"
    fi
}

save_checkpoint() {
    local workflow_id="$1"
    local step_id="$2"
    local step_index="$3"
    local context="$4"

    # Ensure checkpoint directory exists
    local checkpoint_path="${CHECKPOINT_DIR}/${workflow_id}"
    mkdir -p "$checkpoint_path"

    # Generate checkpoint file path
    local checkpoint_file
    checkpoint_file=$(get_checkpoint_file "$workflow_id" "$step_index" "$step_id")

    # Create checkpoint JSON
    local timestamp
    timestamp=$(date -u +%Y-%m-%dT%H:%M:%SZ)

    cat > "$checkpoint_file" << EOF
{
  "workflow_id": "${workflow_id}",
  "step_id": "${step_id}",
  "step_index": ${step_index},
  "timestamp": "${timestamp}",
  "context": ${context:-"{}"}
}
EOF

    log_debug "Checkpoint saved: $checkpoint_file"
    echo "$checkpoint_file"
}

cleanup_checkpoints() {
    local workflow_id="$1"
    local keep_latest="${2:-false}"
    local checkpoint_path="${CHECKPOINT_DIR}/${workflow_id}"

    if [ ! -d "$checkpoint_path" ]; then
        return
    fi

    if $keep_latest; then
        # Keep only the latest checkpoint
        local checkpoints
        checkpoints=$(list_checkpoints "$workflow_id")
        local count
        count=$(echo "$checkpoints" | wc -l | tr -d ' ')

        if [ "$count" -gt 1 ]; then
            echo "$checkpoints" | head -n $((count - 1)) | while read -r cp; do
                rm -f "$cp"
            done
        fi
    else
        # Remove all checkpoints
        rm -rf "$checkpoint_path"
    fi

    # Remove checkpoint directory if empty
    if [ -d "$checkpoint_path" ] && [ -z "$(ls -A "$checkpoint_path" 2>/dev/null)" ]; then
        rmdir "$checkpoint_path" 2>/dev/null || true
    fi

    log_info "Checkpoints cleaned up for workflow: $workflow_id"
}

check_resume_from_checkpoint() {
    if ! $RESUME_MODE; then
        return 1
    fi

    local workflow_id
    workflow_id=$(get_workflow_id)
    local latest_checkpoint
    latest_checkpoint=$(get_latest_checkpoint "$workflow_id")

    if [ -z "$latest_checkpoint" ] || [ ! -f "$latest_checkpoint" ]; then
        log_info "No checkpoint found to resume from"
        return 1
    fi

    log_info "Found checkpoint: $latest_checkpoint"

    # Parse checkpoint to get step info
    local step_id
    step_id=$(jq -r '.step_id // ""' "$latest_checkpoint" 2>/dev/null)
    local step_index
    step_index=$(jq -r '.step_index // 0' "$latest_checkpoint" 2>/dev/null)

    if [ -n "$step_id" ]; then
        log_success "Resuming from step: $step_id (index: $step_index)"
        echo "$step_index"
        return 0
    fi

    return 1
}

# ============================================================================
# Hook System Functions (US-001 - Tier 1 Pattern Extraction)
# ============================================================================

# Execute hooks of a specific type
# Hooks are executed in alphanumeric order (01-99 prefix convention)
# Non-zero exit code from any hook aborts execution
# Usage: execute_hooks "pre_iteration" "$story_id" "$iteration" "$workspace" "$branch" "$phase"
execute_hooks() {
    if ! $HOOKS_ENABLED; then
        return 0
    fi

    local hook_type="$1"
    local story_id="${2:-}"
    local iteration="${3:-0}"
    local workspace="${4:-$(pwd)}"
    local branch="${5:-$(git branch --show-current 2>/dev/null || echo "")}"
    local phase="${6:-implementation}"

    local hooks_subdir="${HOOKS_DIR}/${hook_type}"

    if [ ! -d "$hooks_subdir" ]; then
        log_debug "Hooks directory not found: $hooks_subdir"
        return 0
    fi

    # Find all executable hook files, sorted alphanumerically
    local hook_files
    hook_files=$(find "$hooks_subdir" -maxdepth 1 -type f -perm +111 2>/dev/null | sort || true)

    if [ -z "$hook_files" ]; then
        log_debug "No executable hooks found in $hooks_subdir"
        return 0
    fi

    log_info "Executing $hook_type hooks..."

    # Set environment variables for hooks
    export STORY_ID="$story_id"
    export ITERATION="$iteration"
    export WORKSPACE="$workspace"
    export BRANCH="$branch"
    export PHASE="$phase"
    export PRD_FILE="$PRD_FILE"
    export SCRIPT_DIR="$SCRIPT_DIR"

    # Execute each hook
    local hook_count=0
    while IFS= read -r hook_file; do
        if [ -z "$hook_file" ]; then
            continue
        fi

        hook_count=$((hook_count + 1))
        local hook_name
        hook_name=$(basename "$hook_file")

        log_debug "Running hook: $hook_name"

        local start_time
        start_time=$(date +%s%3N 2>/dev/null || perl -MTime::HiRes=time -e 'printf "%.0f\n", time * 1000')

        # Execute hook and capture output
        local hook_output
        local hook_exit_code=0
        hook_output=$("$hook_file" 2>&1) || hook_exit_code=$?

        local end_time
        end_time=$(date +%s%3N 2>/dev/null || perl -MTime::HiRes=time -e 'printf "%.0f\n", time * 1000')
        local duration_ms=$((end_time - start_time))

        # Log hook execution
        log_hook_execution "$hook_type" "$hook_name" "$hook_exit_code" "$duration_ms" "$hook_output"

        if [ $hook_exit_code -ne 0 ]; then
            log_error "Hook failed: $hook_name (exit code: $hook_exit_code)"
            log_error "Hook output: $hook_output"
            return $hook_exit_code
        fi

        log_debug "Hook completed: $hook_name (${duration_ms}ms)"
    done <<< "$hook_files"

    if [ $hook_count -gt 0 ]; then
        log_success "$hook_count $hook_type hook(s) completed successfully"
    fi

    # Unset environment variables
    unset STORY_ID ITERATION WORKSPACE BRANCH PHASE

    return 0
}

# Log hook execution to hooks.jsonl
# Usage: log_hook_execution "hook_type" "hook_name" exit_code duration_ms "output"
log_hook_execution() {
    if ! $HOOKS_ENABLED; then
        return 0
    fi

    local hook_type="$1"
    local hook_name="$2"
    local exit_code="$3"
    local duration_ms="$4"
    local output="$5"

    # Ensure log directory exists
    mkdir -p "$(dirname "$HOOKS_LOG_FILE")"

    # Create timestamp
    local timestamp
    timestamp=$(date -u +%Y-%m-%dT%H:%M:%SZ)

    # Escape output for JSON (replace newlines, quotes)
    local escaped_output
    escaped_output=$(echo "$output" | jq -Rs . 2>/dev/null || echo "\"\"")

    # Write JSON log entry
    cat >> "$HOOKS_LOG_FILE" << EOF
{"timestamp":"$timestamp","hook_type":"$hook_type","hook_name":"$hook_name","exit_code":$exit_code,"duration_ms":$duration_ms,"output":$escaped_output,"story_id":"${STORY_ID:-}","iteration":${ITERATION:-0}}
EOF
}

# ============================================================================
# Learnings JSON Storage Functions (US-002 - Tier 1 Pattern Extraction)
# ============================================================================

# Write a learning to learnings.json
# Usage: learnings_write "$story_id" "$iteration" "$success" "$lesson" "tag1 tag2 ..." "$context_json"
learnings_write() {
    if ! $LEARNINGS_ENABLED; then
        return 0
    fi

    local story_id="$1"
    local iteration="$2"
    local success="$3"
    local lesson="$4"
    local tags_str="$5"
    local context_json="$6"

    # Generate UUID for learning
    local learning_id
    learning_id=$(uuidgen 2>/dev/null || python3 -c "import uuid; print(uuid.uuid4())" 2>/dev/null || echo "$(date +%s)-$$-$RANDOM")

    # Create timestamp
    local timestamp
    timestamp=$(date -u +%Y-%m-%dT%H:%M:%SZ)

    # Convert tags string to JSON array
    local tags_json
    if [ -z "$tags_str" ]; then
        tags_json="[]"
    else
        tags_json=$(echo "$tags_str" | jq -R 'split(" ") | map(select(length > 0))' 2>/dev/null || echo "[]")
    fi

    # Escape lesson text for JSON
    local escaped_lesson
    escaped_lesson=$(echo "$lesson" | jq -Rs . 2>/dev/null || echo "\"\"")

    # Build learning JSON object
    local learning_json
    learning_json=$(jq -n \
        --arg id "$learning_id" \
        --arg ts "$timestamp" \
        --arg sid "$story_id" \
        --argjson iter "$iteration" \
        --argjson succ "$success" \
        --argjson lesson "$escaped_lesson" \
        --argjson tags "$tags_json" \
        --argjson ctx "$context_json" \
        '{
            id: $id,
            timestamp: $ts,
            story_id: $sid,
            iteration: $iter,
            success: $succ,
            lesson: $lesson,
            tags: $tags,
            helpful_count: 0,
            context: $ctx
        }' 2>/dev/null)

    if [ -z "$learning_json" ]; then
        log_error "Failed to create learning JSON"
        return 1
    fi

    # Ensure learnings file exists
    if [ ! -f "$LEARNINGS_FILE" ]; then
        echo "[]" > "$LEARNINGS_FILE"
    fi

    # Atomic append: read existing, add new, write back
    local temp_file
    temp_file=$(mktemp)

    jq --argjson new_learning "$learning_json" '. += [$new_learning]' "$LEARNINGS_FILE" > "$temp_file" 2>/dev/null

    if [ $? -eq 0 ]; then
        mv "$temp_file" "$LEARNINGS_FILE"
        log_debug "Learning saved: $learning_id"
    else
        log_error "Failed to append learning to $LEARNINGS_FILE"
        rm -f "$temp_file"
        return 1
    fi

    return 0
}

# Query learnings by tags
# Usage: learnings_query --tag "error_handling" [--since "2026-01-01"]
learnings_query() {
    if ! $LEARNINGS_ENABLED; then
        return 0
    fi

    if [ ! -f "$LEARNINGS_FILE" ]; then
        echo "[]"
        return 0
    fi

    local tag_filter=""
    local since_filter=""

    while [[ $# -gt 0 ]]; do
        case "$1" in
            --tag)
                tag_filter="$2"
                shift 2
                ;;
            --since)
                since_filter="$2"
                shift 2
                ;;
            *)
                shift
                ;;
        esac
    done

    # Build jq filter
    local jq_filter='.'

    if [ -n "$tag_filter" ]; then
        jq_filter="$jq_filter | map(select(.tags | index(\"$tag_filter\")))"
    fi

    if [ -n "$since_filter" ]; then
        jq_filter="$jq_filter | map(select(.timestamp >= \"$since_filter\"))"
    fi

    # Sort by helpful_count descending
    jq_filter="$jq_filter | sort_by(-.helpful_count)"

    # Execute query
    jq "$jq_filter" "$LEARNINGS_FILE" 2>/dev/null || echo "[]"
}

# Rate a learning (increment or decrement helpful_count)
# Usage: learnings_rate "$learning_id" --helpful | --unhelpful
learnings_rate() {
    if ! $LEARNINGS_ENABLED; then
        return 0
    fi

    if [ ! -f "$LEARNINGS_FILE" ]; then
        log_error "Learnings file not found: $LEARNINGS_FILE"
        return 1
    fi

    local learning_id="$1"
    local action="$2"

    local delta=0
    case "$action" in
        --helpful)
            delta=1
            ;;
        --unhelpful)
            delta=-1
            ;;
        *)
            log_error "Invalid rating action: $action (use --helpful or --unhelpful)"
            return 1
            ;;
    esac

    # Update helpful_count atomically
    local temp_file
    temp_file=$(mktemp)

    jq --arg id "$learning_id" --argjson delta "$delta" \
        'map(if .id == $id then .helpful_count += $delta else . end)' \
        "$LEARNINGS_FILE" > "$temp_file" 2>/dev/null

    if [ $? -eq 0 ]; then
        mv "$temp_file" "$LEARNINGS_FILE"
        log_success "Learning rated: $learning_id ($action)"
    else
        log_error "Failed to rate learning: $learning_id"
        rm -f "$temp_file"
        return 1
    fi

    return 0
}

# Extract relevant learnings for story context
# Usage: get_relevant_learnings "$story_id" "$story_description"
# Returns: JSON array of top N relevant learnings
get_relevant_learnings() {
    if ! $LEARNINGS_ENABLED; then
        echo "[]"
        return 0
    fi

    if [ ! -f "$LEARNINGS_FILE" ]; then
        echo "[]"
        return 0
    fi

    local story_id="$1"
    local story_description="$2"

    # Extract tags from story description (simple keyword extraction)
    local story_tags
    story_tags=$(echo "$story_description" | tr '[:upper:]' '[:lower:]' | grep -oE '\w{4,}' | sort -u | head -20 | tr '\n' ' ')

    # Query learnings by tags and get top N by helpful_count
    local relevant_learnings
    relevant_learnings=$(jq --arg story_tags "$story_tags" --argjson max "$MAX_LEARNINGS_IN_CONTEXT" '
        [.[] | select(
            (.tags | length > 0) and
            ([.tags[] as $tag | $story_tags | contains($tag)] | any)
        )] |
        sort_by(-.helpful_count) |
        .[:$max]
    ' "$LEARNINGS_FILE" 2>/dev/null || echo "[]")

    echo "$relevant_learnings"
}

# Extract tags from story for automatic tagging
# Usage: extract_story_tags "$story_description" "$file_scope"
# Returns: Space-separated list of tags
extract_story_tags() {
    local story_description="$1"
    local file_scope="$2"

    local tags=""

    # Extract keywords from description (4+ char words, lowercase)
    local desc_tags
    desc_tags=$(echo "$story_description" | tr '[:upper:]' '[:lower:]' | grep -oE '\w{4,}' | sort -u | head -10 | tr '\n' ' ')
    tags="$tags $desc_tags"

    # Extract file extensions from file scope
    if [ -n "$file_scope" ]; then
        local ext_tags
        ext_tags=$(echo "$file_scope" | grep -oE '\.\w+$' | sed 's/^\.//' | sort -u | tr '\n' ' ')
        tags="$tags $ext_tags"
    fi

    # Normalize tags: remove duplicates, trim whitespace
    tags=$(echo "$tags" | tr ' ' '\n' | sort -u | grep -v '^$' | tr '\n' ' ')

    echo "$tags"
}

# ============================================================================
# Story Decomposition Functions (US-003 - Tier 1 Pattern Extraction)
# ============================================================================

# Automatic Task Decomposition Feature Flag
DECOMPOSITION_ENABLED=false  # Disabled by default, enable with --enable-decomposition
AUTO_DECOMPOSE=false  # Auto-approve decompositions without user interaction
DECOMPOSITION_LOG_FILE="./.claude-loop/logs/decomposition.jsonl"
DECOMPOSE_STORY_ID=""  # Story ID for --decompose-story command

# Complexity check thresholds for decomposition
DECOMPOSITION_HOURS_THRESHOLD=16
DECOMPOSITION_DESC_LENGTH_THRESHOLD=1000
DECOMPOSITION_AC_COUNT_THRESHOLD=8

# Check if a story should be decomposed based on complexity thresholds
# Args: story_id
# Returns: 0 if should decompose, 1 if not
complexity_check() {
    if ! $DECOMPOSITION_ENABLED; then
        return 1  # Feature disabled
    fi

    local story_id="$1"

    # Get story from PRD
    local story
    story=$(jq --arg id "$story_id" '.userStories[] | select(.id == $id)' "$PRD_FILE" 2>/dev/null)

    if [ -z "$story" ] || [ "$story" = "null" ]; then
        log_warn "Story $story_id not found in PRD"
        return 1
    fi

    # Extract fields
    local estimated_hours
    estimated_hours=$(echo "$story" | jq -r '.estimatedHours // 0')

    local description
    description=$(echo "$story" | jq -r '.description // ""')
    local desc_length=${#description}

    local ac_count
    ac_count=$(echo "$story" | jq -r '.acceptanceCriteria | length')

    # Check thresholds
    local should_decompose=false
    local reasons=()

    if [ "$estimated_hours" -gt "$DECOMPOSITION_HOURS_THRESHOLD" ]; then
        should_decompose=true
        reasons+=("estimatedHours ($estimated_hours) > threshold ($DECOMPOSITION_HOURS_THRESHOLD)")
    fi

    if [ "$desc_length" -gt "$DECOMPOSITION_DESC_LENGTH_THRESHOLD" ]; then
        should_decompose=true
        reasons+=("description length ($desc_length chars) > threshold ($DECOMPOSITION_DESC_LENGTH_THRESHOLD)")
    fi

    if [ "$ac_count" -gt "$DECOMPOSITION_AC_COUNT_THRESHOLD" ]; then
        should_decompose=true
        reasons+=("acceptance criteria count ($ac_count) > threshold ($DECOMPOSITION_AC_COUNT_THRESHOLD)")
    fi

    if $should_decompose; then
        log_info "Story $story_id exceeds complexity thresholds:"
        for reason in "${reasons[@]}"; do
            log_info "  - $reason"
        done

        # Log to decomposition log
        log_decomposition "$story_id" "complexity_check" "triggered" "{\"reasons\": $(printf '%s\n' "${reasons[@]}" | jq -R . | jq -s .), \"estimated_hours\": $estimated_hours, \"description_length\": $desc_length, \"ac_count\": $ac_count}"

        return 0
    fi

    return 1
}

# Decompose a story into substories using Claude
# Args: story_id
# Returns: 0 on success, 1 on failure
decompose_story() {
    local story_id="$1"

    log_info "Decomposing story: $story_id"

    # Get story from PRD
    local story
    story=$(jq --arg id "$story_id" '.userStories[] | select(.id == $id)' "$PRD_FILE" 2>/dev/null)

    if [ -z "$story" ] || [ "$story" = "null" ]; then
        log_error "Story $story_id not found in PRD"
        return 1
    fi

    # Check if story is already marked as decomposed
    local passes
    passes=$(echo "$story" | jq -r '.passes // false')
    if [ "$passes" = "true" ]; then
        log_warn "Story $story_id is already marked complete. Skipping decomposition."
        return 1
    fi

    # Build decomposition prompt
    local story_title
    story_title=$(echo "$story" | jq -r '.title')
    local story_desc
    story_desc=$(echo "$story" | jq -r '.description')
    local story_ac
    story_ac=$(echo "$story" | jq -r '.acceptanceCriteria | join("\n- ")')
    local story_priority
    story_priority=$(echo "$story" | jq -r '.priority')

    local prompt="You are helping decompose a complex user story into smaller, manageable substories.

## Original Story

**ID**: $story_id
**Title**: $story_title
**Priority**: $story_priority

**Description**: $story_desc

**Acceptance Criteria**:
- $story_ac

## Task

Please decompose this story into 2-5 smaller substories. Each substory should:

1. Have a unique ID with suffix (e.g., ${story_id}-1, ${story_id}-2, ${story_id}-3)
2. Have a clear, focused title
3. Have a description following user story format
4. Have 2-4 specific, testable acceptance criteria
5. Have appropriate dependencies on previous substories if needed
6. Inherit context and tags from the parent story

**Important Guidelines**:
- Substories should be implementable independently (after dependencies are met)
- Each substory should deliver incremental value
- The sum of substories should equal the original story scope
- Avoid creating substories that are too small or too large

Please return a JSON response in this EXACT format (JSON only, no other text):

{
  \"rationale\": \"Clear explanation of why this decomposition makes sense\",
  \"substories\": [
    {
      \"id\": \"${story_id}-1\",
      \"title\": \"Substory title\",
      \"description\": \"Substory description\",
      \"acceptanceCriteria\": [\"Criterion 1\", \"Criterion 2\"],
      \"priority\": 1,
      \"dependencies\": [],
      \"passes\": false,
      \"notes\": \"\"
    }
  ]
}"

    # Write prompt to temp file
    local prompt_file
    prompt_file=$(mktemp /tmp/decomposition_prompt_XXXXXX.txt)
    echo "$prompt" > "$prompt_file"

    # Call Claude to generate decomposition
    log_info "Calling Claude to generate decomposition proposal..."
    local claude_output
    claude_output=$(mktemp /tmp/decomposition_output_XXXXXX.txt)

    if ! claude -m sonnet "$prompt_file" > "$claude_output" 2>&1; then
        log_error "Claude CLI failed to generate decomposition"
        rm -f "$prompt_file" "$claude_output"
        return 1
    fi

    rm -f "$prompt_file"

    # Parse Claude's JSON response
    local decomposition_json
    decomposition_json=$(cat "$claude_output")

    # Extract JSON from potential markdown code blocks
    if echo "$decomposition_json" | grep -q '```json'; then
        decomposition_json=$(echo "$decomposition_json" | sed -n '/```json/,/```/p' | sed '1d;$d')
    elif echo "$decomposition_json" | grep -q '```'; then
        decomposition_json=$(echo "$decomposition_json" | sed -n '/```/,/```/p' | sed '1d;$d')
    fi

    # Validate JSON
    if ! echo "$decomposition_json" | jq empty 2>/dev/null; then
        log_error "Invalid JSON response from Claude"
        rm -f "$claude_output"
        return 1
    fi

    rm -f "$claude_output"

    # Extract rationale and substories
    local rationale
    rationale=$(echo "$decomposition_json" | jq -r '.rationale')
    local substories
    substories=$(echo "$decomposition_json" | jq '.substories')
    local substory_count
    substory_count=$(echo "$substories" | jq 'length')

    log_info "Decomposition generated: $substory_count substories"
    log_info "Rationale: $rationale"

    # Log decomposition proposal
    log_decomposition "$story_id" "proposal_generated" "success" "{\"rationale\": $(echo "$rationale" | jq -R .), \"substory_count\": $substory_count, \"substories\": $substories}"

    # Interactive or automatic approval
    local approved=false
    if $AUTO_DECOMPOSE; then
        approved=true
        log_info "Auto-approving decomposition (--auto-decompose enabled)"
        log_decomposition "$story_id" "approval" "auto_approved" "{}"
    else
        # Present decomposition to user
        echo ""
        echo "================================"
        echo "Story Decomposition Proposal"
        echo "================================"
        echo ""
        echo "Original Story: $story_id - $story_title"
        echo ""
        echo "Rationale: $rationale"
        echo ""
        echo "Proposed Substories ($substory_count):"
        echo ""

        for ((i=0; i<substory_count; i++)); do
            local sub_id
            sub_id=$(echo "$substories" | jq -r ".[$i].id")
            local sub_title
            sub_title=$(echo "$substories" | jq -r ".[$i].title")
            local sub_desc
            sub_desc=$(echo "$substories" | jq -r ".[$i].description")
            local sub_deps
            sub_deps=$(echo "$substories" | jq -r ".[$i].dependencies | join(\", \")")

            echo "[$((i+1))] $sub_id: $sub_title"
            echo "    Description: $sub_desc"
            if [ -n "$sub_deps" ] && [ "$sub_deps" != "" ]; then
                echo "    Dependencies: $sub_deps"
            fi
            echo ""
        done

        echo "Approve this decomposition? (y/n)"
        read -r approval

        if [ "$approval" = "y" ] || [ "$approval" = "Y" ]; then
            approved=true
            log_decomposition "$story_id" "approval" "user_approved" "{}"
        else
            log_info "Decomposition rejected by user"
            log_decomposition "$story_id" "approval" "user_rejected" "{}"
            return 1
        fi
    fi

    if ! $approved; then
        return 1
    fi

    # Apply decomposition to PRD
    log_info "Applying decomposition to PRD..."

    # Create backup
    local backup_file
    backup_file="${PRD_FILE}.backup.$(date +%Y%m%d_%H%M%S)"
    cp "$PRD_FILE" "$backup_file"
    log_info "PRD backup created: $backup_file"

    # Update PRD: mark original story as decomposed, add substories
    local prd_content
    prd_content=$(cat "$PRD_FILE")

    # Mark original story as decomposed
    prd_content=$(echo "$prd_content" | jq --arg id "$story_id" '
        .userStories |= map(
            if .id == $id then
                .notes = (if .notes then .notes + " | " else "" end) + "Decomposed into substories"
                | .passes = false
            else
                .
            end
        )
    ')

    # Insert substories after the original story
    local story_index
    story_index=$(echo "$prd_content" | jq --arg id "$story_id" '.userStories | map(.id) | index($id)')

    # Add substories one by one after original story
    for ((i=0; i<substory_count; i++)); do
        local substory
        substory=$(echo "$substories" | jq ".[$i]")
        local insert_index=$((story_index + i + 1))

        prd_content=$(echo "$prd_content" | jq --argjson substory "$substory" --argjson idx "$insert_index" '
            .userStories |= (.[0:$idx] + [$substory] + .[$idx:])
        ')
    done

    # Write updated PRD atomically
    echo "$prd_content" | jq . > "${PRD_FILE}.tmp"

    # Validate updated PRD
    if ! jq empty "${PRD_FILE}.tmp" 2>/dev/null; then
        log_error "Failed to validate updated PRD"
        rm -f "${PRD_FILE}.tmp"
        return 1
    fi

    # Atomic replace
    mv "${PRD_FILE}.tmp" "$PRD_FILE"

    log_info "✓ PRD updated successfully with $substory_count substories"
    log_decomposition "$story_id" "prd_updated" "success" "{\"substory_count\": $substory_count, \"backup_file\": $(echo "$backup_file" | jq -R .)}"

    return 0
}

# Log decomposition event to JSONL
# Args: story_id, event_type, status, context_json
log_decomposition() {
    local story_id="$1"
    local event_type="$2"
    local status="$3"
    local context_json="${4:-{}}"

    # Create logs directory if it doesn't exist
    mkdir -p "$(dirname "$DECOMPOSITION_LOG_FILE")"

    # Build log entry
    local timestamp
    timestamp=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

    local log_entry
    log_entry=$(jq -n \
        --arg timestamp "$timestamp" \
        --arg story_id "$story_id" \
        --arg event_type "$event_type" \
        --arg status "$status" \
        --argjson context "$context_json" \
        '{
            timestamp: $timestamp,
            story_id: $story_id,
            event_type: $event_type,
            status: $status,
            context: $context
        }')

    # Append to log file
    echo "$log_entry" >> "$DECOMPOSITION_LOG_FILE"
}

# ============================================================================
# Structured JSON Output Parser (US-004 - Tier 1 Pattern Extraction)
# ============================================================================

# Feature Flag: Enable structured JSON output parsing
STRUCTURED_OUTPUT_ENABLED=false

# Actions log file for metadata storage
ACTIONS_LOG_FILE=".claude-loop/logs/actions.jsonl"

# Validate JSON response schema
# Returns 0 if valid, 1 if invalid
validate_json_response() {
    local json="$1"

    # Check if it's valid JSON first
    if ! echo "$json" | jq empty 2>/dev/null; then
        return 1
    fi

    # Check for required fields
    local action
    action=$(echo "$json" | jq -r '.action // empty' 2>/dev/null)

    if [ -z "$action" ]; then
        return 1
    fi

    # Validate action is one of the allowed values
    case "$action" in
        implement|commit|skip|delegate|complete)
            return 0
            ;;
        *)
            return 1
            ;;
    esac
}

# Parse JSON response from Claude output
# Extracts action, reasoning, confidence, and metadata
# Returns: Extracted data as JSON or empty string if not found/invalid
parse_json_response() {
    local output_file="$1"

    # Try to extract JSON block from output
    # Look for JSON blocks in common formats:
    # 1. ```json ... ```
    # 2. Standalone {...}

    local json_block=""

    # Try to find JSON code block first
    if grep -q '```json' "$output_file"; then
        json_block=$(sed -n '/```json/,/```/p' "$output_file" | sed '1d;$d')
    fi

    # If no code block, try to find JSON object
    if [ -z "$json_block" ]; then
        # Extract lines that look like JSON (start with { or contain JSON-like content)
        json_block=$(grep -E '^\s*\{.*"action"' "$output_file" | head -1)
    fi

    if [ -z "$json_block" ]; then
        return 1
    fi

    # Validate the JSON
    if ! validate_json_response "$json_block"; then
        return 1
    fi

    echo "$json_block"
    return 0
}

# Extract action from JSON response
get_json_action() {
    local json="$1"
    echo "$json" | jq -r '.action // empty'
}

# Extract reasoning from JSON response
get_json_reasoning() {
    local json="$1"
    echo "$json" | jq -r '.reasoning // "No reasoning provided"'
}

# Extract confidence from JSON response (0-100)
get_json_confidence() {
    local json="$1"
    echo "$json" | jq -r '.confidence // 0'
}

# Extract files from JSON response
get_json_files() {
    local json="$1"
    echo "$json" | jq -r '.files // [] | .[].path' 2>/dev/null
}

# Extract metadata from JSON response
get_json_metadata() {
    local json="$1"
    echo "$json" | jq -r '.metadata // {}' 2>/dev/null
}

# Check if output indicates completion (JSON or sigil)
# Supports both new JSON format and legacy sigil format for backward compatibility
# Returns: 0 if complete, 1 if not complete
check_completion() {
    local output_file="$1"
    local story_id="${2:-}"

    # Try JSON parsing first if enabled
    if [ "$STRUCTURED_OUTPUT_ENABLED" = true ]; then
        local json_response
        if json_response=$(parse_json_response "$output_file"); then
            local action
            action=$(get_json_action "$json_response")

            case "$action" in
                complete|commit)
                    return 0
                    ;;
                skip|delegate)
                    return 1
                    ;;
            esac
        fi
    fi

    # Fallback to sigil-based detection
    if [ -n "$story_id" ]; then
        if grep -q "WORKER_SUCCESS: $story_id" "$output_file"; then
            return 0
        elif grep -q "WORKER_FAILURE: $story_id" "$output_file"; then
            return 1
        fi
    fi

    # Check for standard completion signal
    if grep -q "<loop>COMPLETE</loop>" "$output_file"; then
        return 0
    fi

    # No clear completion signal found
    return 2
}

# Log action metadata to actions.jsonl
# Args: story_id, action, json_response
log_action_metadata() {
    local story_id="$1"
    local action="$2"
    local json_response="$3"

    # Create logs directory if it doesn't exist
    mkdir -p "$(dirname "$ACTIONS_LOG_FILE")"

    # Extract metadata from JSON response
    local reasoning
    reasoning=$(get_json_reasoning "$json_response")

    local confidence
    confidence=$(get_json_confidence "$json_response")

    local metadata
    metadata=$(get_json_metadata "$json_response")

    local files
    files=$(echo "$json_response" | jq -c '.files // []' 2>/dev/null)

    # Build log entry
    local timestamp
    timestamp=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

    local log_entry
    log_entry=$(jq -nc \
        --arg timestamp "$timestamp" \
        --arg story_id "$story_id" \
        --arg action "$action" \
        --arg reasoning "$reasoning" \
        --argjson confidence "$confidence" \
        --argjson files "$files" \
        --argjson metadata "$metadata" \
        '{
            timestamp: $timestamp,
            story_id: $story_id,
            action: $action,
            reasoning: $reasoning,
            confidence: $confidence,
            files: $files,
            metadata: $metadata
        }')

    # Append to log file
    echo "$log_entry" >> "$ACTIONS_LOG_FILE"
}

# Handle low-confidence responses
# If confidence < 50, log warning and return clarification request
handle_low_confidence() {
    local json_response="$1"
    local story_id="$2"

    local confidence
    confidence=$(get_json_confidence "$json_response")

    if [ "$confidence" -lt 50 ]; then
        log_warn "Low confidence ($confidence%) detected for story $story_id"
        log_warn "Requesting clarification in next iteration"

        # Log the low confidence event
        log_action_metadata "$story_id" "low_confidence" "$json_response"

        return 1
    fi

    return 0
}

# ============================================================================
# Improvement Management Functions
# ============================================================================

check_improvement_manager() {
    if [ ! -f "$IMPROVEMENT_MANAGER" ]; then
        log_error "Improvement manager not found: $IMPROVEMENT_MANAGER"
        return 1
    fi

    # Source the improvement manager for function access
    source "$IMPROVEMENT_MANAGER"
    return 0
}

# ============================================================================
# Gap Analysis Daemon Functions
# ============================================================================

check_gap_analysis_daemon() {
    if [ ! -f "$GAP_ANALYSIS_DAEMON" ]; then
        log_error "Gap analysis daemon not found: $GAP_ANALYSIS_DAEMON"
        return 1
    fi

    if [ ! -x "$GAP_ANALYSIS_DAEMON" ]; then
        log_warn "Making gap analysis daemon executable..."
        chmod +x "$GAP_ANALYSIS_DAEMON"
    fi

    return 0
}

run_daemon_mode() {
    # Check if we're in daemon mode
    if [ -z "$DAEMON_MODE" ]; then
        return 1  # Not in daemon mode, continue normal execution
    fi

    # Ensure daemon script is available
    if ! check_gap_analysis_daemon; then
        exit 1
    fi

    case "$DAEMON_MODE" in
        start)
            log_info "Starting gap analysis daemon..."
            "$GAP_ANALYSIS_DAEMON" start
            exit $?
            ;;
        stop)
            log_info "Stopping gap analysis daemon..."
            "$GAP_ANALYSIS_DAEMON" stop
            exit $?
            ;;
        status)
            "$GAP_ANALYSIS_DAEMON" status
            exit 0
            ;;
        *)
            log_error "Unknown daemon mode: $DAEMON_MODE"
            exit 1
            ;;
    esac
}

# Template mode handler (US-002)
run_template_mode() {
    # Check if we're in template mode
    if [ -z "$TEMPLATE_MODE" ]; then
        return 1  # Not in template mode, continue normal execution
    fi

    if [ ! -f "$TEMPLATE_GENERATOR" ]; then
        log_error "Template generator not found: $TEMPLATE_GENERATOR"
        exit 1
    fi

    case "$TEMPLATE_MODE" in
        list)
            "$TEMPLATE_GENERATOR" list
            exit 0
            ;;
        show)
            if [ -z "$TEMPLATE_NAME" ]; then
                log_error "Template name required for --show-template"
                exit 1
            fi
            "$TEMPLATE_GENERATOR" show "$TEMPLATE_NAME"
            exit 0
            ;;
        generate)
            if [ -z "$TEMPLATE_NAME" ]; then
                log_error "Template name required for --template"
                exit 1
            fi

            # Build command
            local cmd=("$TEMPLATE_GENERATOR" "generate" "$TEMPLATE_NAME" "--output" "$TEMPLATE_OUTPUT")

            # Add variables
            for var in "${TEMPLATE_VARS[@]}"; do
                cmd+=("--var" "$var")
            done

            # Add vars file if provided
            if [ -n "$TEMPLATE_VARS_FILE" ]; then
                cmd+=("--vars-file" "$TEMPLATE_VARS_FILE")
            fi

            # If no vars provided, use interactive mode
            if [ ${#TEMPLATE_VARS[@]} -eq 0 ] && [ -z "$TEMPLATE_VARS_FILE" ]; then
                cmd+=("--interactive")
            else
                cmd+=("--non-interactive")
            fi

            # Run generator
            "${cmd[@]}"
            exit $?
            ;;
        *)
            log_error "Unknown template mode: $TEMPLATE_MODE"
            exit 1
            ;;
    esac
}

# Skills mode handler (US-201)
run_skills_mode() {
    # Check if we're in skills mode
    if [ -z "$SKILLS_MODE" ]; then
        return 1  # Not in skills mode, continue normal execution
    fi

    if [ ! -f "$SKILLS_FRAMEWORK" ]; then
        log_error "Skills framework not found: $SKILLS_FRAMEWORK"
        exit 1
    fi

    # Source skills framework
    source "$SKILLS_FRAMEWORK"

    # Initialize skills framework
    init_skills_framework "$SKILLS_DIR" > /dev/null 2>&1

    case "$SKILLS_MODE" in
        list)
            list_skills "text"
            exit 0
            ;;
        execute)
            if [ -z "$SKILL_NAME" ]; then
                log_error "Skill name is required for --skill"
                exit 1
            fi

            # Execute skill with arguments
            if [ ${#SKILL_ARGS[@]} -gt 0 ]; then
                execute_skill "$SKILL_NAME" "${SKILL_ARGS[@]}"
            else
                execute_skill "$SKILL_NAME"
            fi
            exit $?
            ;;
        *)
            log_error "Unknown skills mode: $SKILLS_MODE"
            exit 1
            ;;
    esac
}

# Quick task mode handler (US-203)
run_quick_task_mode() {
    # Check if we're in quick task mode
    if [ -z "$QUICK_TASK_MODE" ]; then
        return 1  # Not in quick task mode, continue normal execution
    fi

    if [ ! -f "$QUICK_TASK_FRAMEWORK" ]; then
        log_error "Quick task framework not found: $QUICK_TASK_FRAMEWORK"
        exit 1
    fi

    # Source quick task framework
    source "$QUICK_TASK_FRAMEWORK"

    case "$QUICK_TASK_MODE" in
        execute)
            if [ -z "$QUICK_TASK_DESC" ] && [ "$QUICK_TASK_CONTINUE" = false ]; then
                log_error "Task description is required for quick mode (or use --continue)"
                echo "Usage: ./claude-loop.sh quick \"task description\" [options]"
                echo ""
                echo "Options:"
                echo "  --workspace DIR    Set workspace directory"
                echo "  --commit           Auto-commit on success"
                echo "  --escalate         Auto-escalate to PRD if complex"
                echo "  --dry-run          Show plan without executing"
                echo "  --continue         Resume last failed task"
                echo "  --template NAME    Use template (refactor, add-tests, fix-bug)"
                exit 1
            fi

            # Build arguments array
            local args=()

            if [ "$QUICK_TASK_CONTINUE" = true ]; then
                args+=("--continue")
            elif [ -n "$QUICK_TASK_DESC" ]; then
                args+=("$QUICK_TASK_DESC")
            fi

            if [ "$QUICK_TASK_WORKSPACE" != "." ]; then
                args+=("--workspace" "$QUICK_TASK_WORKSPACE")
            fi

            if $QUICK_TASK_COMMIT; then
                args+=("--commit")
            fi

            if $QUICK_TASK_ESCALATE; then
                args+=("--escalate")
            fi

            if $QUICK_TASK_DRY_RUN; then
                args+=("--dry-run")
            fi

            if [ -n "$QUICK_TASK_TEMPLATE" ]; then
                args+=("--template" "$QUICK_TASK_TEMPLATE")
            fi

            # Execute quick task
            if [[ ${#args[@]} -gt 0 ]]; then
                run_quick_task "${args[@]}"
            else
                run_quick_task
            fi
            exit $?
            ;;
        history)
            show_quick_task_history 20
            exit 0
            ;;
        stats)
            show_quick_task_stats
            exit 0
            ;;
        templates)
            list_templates
            exit 0
            ;;
        *)
            log_error "Unknown quick task mode: $QUICK_TASK_MODE"
            exit 1
            ;;
    esac
}

run_task_daemon_mode() {
    # Check if we're in daemon mode
    if [ -z "$TASK_DAEMON_CMD" ]; then
        return 1  # Not in daemon mode, continue normal execution
    fi

    if [ ! -f "$TASK_DAEMON" ]; then
        log_error "Task daemon not found: $TASK_DAEMON"
        exit 1
    fi

    # Make daemon executable if not already
    if [ ! -x "$TASK_DAEMON" ]; then
        chmod +x "$TASK_DAEMON"
    fi

    case "$TASK_DAEMON_CMD" in
        start)
            log_info "Starting task execution daemon with $TASK_DAEMON_WORKERS worker(s)..."
            "$TASK_DAEMON" start "$TASK_DAEMON_WORKERS"
            exit $?
            ;;
        stop)
            log_info "Stopping task execution daemon..."
            "$TASK_DAEMON" stop
            exit $?
            ;;
        status)
            "$TASK_DAEMON" status
            exit $?
            ;;
        submit)
            if [ -z "$TASK_DAEMON_ARG" ]; then
                log_error "PRD path is required for daemon submit"
                echo "Usage: ./claude-loop.sh daemon submit <prd_path> [priority]"
                exit 1
            fi
            log_info "Submitting task to daemon queue (priority: $TASK_DAEMON_PRIORITY)..."
            "$TASK_DAEMON" submit "$TASK_DAEMON_ARG" "$TASK_DAEMON_PRIORITY"
            exit $?
            ;;
        queue)
            "$TASK_DAEMON" queue
            exit 0
            ;;
        cancel)
            if [ -z "$TASK_DAEMON_ARG" ]; then
                log_error "Task ID is required for daemon cancel"
                echo "Usage: ./claude-loop.sh daemon cancel <task_id>"
                exit 1
            fi
            log_info "Cancelling task $TASK_DAEMON_ARG..."
            "$TASK_DAEMON" cancel "$TASK_DAEMON_ARG"
            exit $?
            ;;
        pause)
            log_info "Pausing daemon queue..."
            "$TASK_DAEMON" pause
            exit $?
            ;;
        resume)
            log_info "Resuming daemon queue..."
            "$TASK_DAEMON" resume
            exit $?
            ;;
        *)
            log_error "Unknown daemon command: $TASK_DAEMON_CMD"
            exit 1
            ;;
    esac
}

run_dashboard_mode() {
    # Check if we're in dashboard mode
    if [ -z "$DASHBOARD_CMD" ]; then
        return 1  # Not in dashboard mode, continue normal execution
    fi

    if [ ! -f "$DASHBOARD_LAUNCHER" ]; then
        log_error "Dashboard launcher not found: $DASHBOARD_LAUNCHER"
        exit 1
    fi

    # Make launcher executable if not already
    if [ ! -x "$DASHBOARD_LAUNCHER" ]; then
        chmod +x "$DASHBOARD_LAUNCHER"
    fi

    case "$DASHBOARD_CMD" in
        start)
            # Build arguments
            args=()
            if [ "$DASHBOARD_PORT" != "8080" ]; then
                args+=("--port" "$DASHBOARD_PORT")
            fi
            if [ "$DASHBOARD_HOST" != "127.0.0.1" ]; then
                args+=("--host" "$DASHBOARD_HOST")
            fi
            "$DASHBOARD_LAUNCHER" start "${args[@]}"
            exit $?
            ;;
        stop)
            "$DASHBOARD_LAUNCHER" stop
            exit $?
            ;;
        restart)
            # Build arguments
            args=()
            if [ "$DASHBOARD_PORT" != "8080" ]; then
                args+=("--port" "$DASHBOARD_PORT")
            fi
            if [ "$DASHBOARD_HOST" != "127.0.0.1" ]; then
                args+=("--host" "$DASHBOARD_HOST")
            fi
            "$DASHBOARD_LAUNCHER" restart "${args[@]}"
            exit $?
            ;;
        status)
            "$DASHBOARD_LAUNCHER" status
            exit $?
            ;;
        logs)
            "$DASHBOARD_LAUNCHER" logs
            exit $?
            ;;
        generate-token)
            "$DASHBOARD_LAUNCHER" generate-token
            exit $?
            ;;
        *)
            log_error "Unknown dashboard command: $DASHBOARD_CMD"
            exit 1
            ;;
    esac
}

run_brainstorm_mode() {
    # Check if we're in brainstorm mode
    if [ "$BRAINSTORM_MODE" != true ]; then
        return 1  # Not in brainstorm mode, continue normal execution
    fi

    local brainstorm_handler="$LIB_DIR/brainstorming-handler.sh"

    # Check if brainstorming handler exists
    if [ ! -f "$brainstorm_handler" ]; then
        log_error "Brainstorming handler not found: $brainstorming_handler"
        log_info "Expected location: lib/brainstorming-handler.sh"
        exit 1
    fi

    # Check if description provided
    if [ -z "$BRAINSTORM_DESCRIPTION" ]; then
        log_error "Description is required for brainstorm mode"
        log_info "Usage: ./claude-loop.sh brainstorm '<description>'"
        exit 1
    fi

    log_info "Starting brainstorming session..."
    log_info "Description: $BRAINSTORM_DESCRIPTION"

    # Run brainstorming handler
    "$brainstorm_handler" "$BRAINSTORM_DESCRIPTION" || {
        log_error "Brainstorming session failed"
        exit 1
    }

    exit 0
}

run_improvement_mode() {
    # Check if we're in improvement mode
    if [ -z "$IMPROVEMENT_MODE" ]; then
        return 1  # Not in improvement mode, continue normal execution
    fi

    # Ensure improvement manager is available
    if ! check_improvement_manager; then
        exit 1
    fi

    case "$IMPROVEMENT_MODE" in
        list)
            log_info "Listing improvement PRDs..."
            list_improvements "all" "text"
            exit 0
            ;;
        review)
            if [ -z "$IMPROVEMENT_TARGET" ]; then
                log_error "PRD name is required for --review-improvement"
                exit 1
            fi
            log_info "Reviewing improvement PRD: $IMPROVEMENT_TARGET"
            review_improvement "$IMPROVEMENT_TARGET" "text"
            exit 0
            ;;
        approve)
            if [ -z "$IMPROVEMENT_TARGET" ]; then
                log_error "PRD name is required for --approve-improvement"
                exit 1
            fi
            log_info "Approving improvement PRD: $IMPROVEMENT_TARGET"
            approve_improvement "$IMPROVEMENT_TARGET" "$IMPROVEMENT_NOTES"
            exit 0
            ;;
        reject)
            if [ -z "$IMPROVEMENT_TARGET" ]; then
                log_error "PRD name is required for --reject-improvement"
                exit 1
            fi
            if [ -z "$IMPROVEMENT_REASON" ]; then
                log_error "Rejection reason is required (use --reason \"...\")"
                exit 1
            fi
            log_info "Rejecting improvement PRD: $IMPROVEMENT_TARGET"
            reject_improvement "$IMPROVEMENT_TARGET" "$IMPROVEMENT_REASON"
            exit 0
            ;;
        validate)
            if [ -z "$IMPROVEMENT_TARGET" ]; then
                log_error "PRD name is required for --validate-improvement"
                exit 1
            fi
            log_info "Validating improvement PRD: $IMPROVEMENT_TARGET"
            local force_flag=""
            if $IMPROVEMENT_FORCE; then
                force_flag="true"
            fi
            validate_improvement "$IMPROVEMENT_TARGET" "$force_flag"
            exit $?
            ;;
        execute)
            if [ -z "$IMPROVEMENT_TARGET" ]; then
                log_error "PRD name is required for --execute-improvement"
                exit 1
            fi
            log_info "Executing improvement PRD: $IMPROVEMENT_TARGET"
            local validate_flag="false"
            local force_flag="false"
            if $IMPROVEMENT_VALIDATE; then
                validate_flag="true"
            fi
            if $IMPROVEMENT_FORCE; then
                force_flag="true"
            fi
            execute_improvement "$IMPROVEMENT_TARGET" "$validate_flag" "$force_flag"
            exit $?
            ;;
        history)
            log_info "Showing improvement history..."
            show_history 20 "text"
            exit 0
            ;;
        rollback)
            if [ -z "$IMPROVEMENT_TARGET" ]; then
                log_error "PRD name is required for --rollback-improvement"
                exit 1
            fi
            log_warn "Rolling back improvement PRD: $IMPROVEMENT_TARGET"
            rollback_improvement "$IMPROVEMENT_TARGET" "$IMPROVEMENT_REASON" "$IMPROVEMENT_DRY_RUN"
            exit $?
            ;;
        *)
            log_error "Unknown improvement mode: $IMPROVEMENT_MODE"
            exit 1
            ;;
    esac
}

# ============================================================================
# Single-Command Entry Point (INV-008)
# ============================================================================

# Generate PRD from feature description
# Usage: generate_prd_from_description "feature description"
# Sets PRD_FILE to the generated file path
generate_prd_from_description() {
    local description="$1"

    if [ ! -f "$PRD_GENERATOR" ]; then
        log_error "PRD generator not found: $PRD_GENERATOR"
        log_info "Please ensure lib/prd-from-description.py exists."
        exit 1
    fi

    if ! command -v python3 &> /dev/null; then
        log_error "Python3 is required for PRD generation."
        exit 1
    fi

    log_info "Generating PRD from description..."
    log_info "Description: $description"
    echo ""

    # Generate PRD to temporary location first to capture output
    local output_file="prd.json"

    # Run the generator and capture output
    if ! python3 "$PRD_GENERATOR" generate "$description" --output "$output_file" 2>&1; then
        log_error "Failed to generate PRD from description"
        exit 1
    fi

    # Update PRD_FILE to point to generated file
    PRD_FILE="$output_file"

    log_success "PRD generated: $PRD_FILE"
}

# Generate PRD from high-level goal (US-004)
# Uses Claude-powered decomposition for goal analysis and story generation
generate_prd_dynamic() {
    local goal="$1"
    local output_path="$2"
    local with_codebase_analysis="$3"

    if [ ! -f "$DYNAMIC_PRD_GENERATOR" ]; then
        log_error "Dynamic PRD generator not found: $DYNAMIC_PRD_GENERATOR"
        log_info "Please ensure lib/prd-generator.py exists."
        exit 1
    fi

    if ! command -v python3 &> /dev/null; then
        log_error "Python3 is required for dynamic PRD generation."
        exit 1
    fi

    log_info "Generating dynamic PRD from goal (US-004)..."
    log_info "Goal: $goal"
    echo ""

    # Build command
    local cmd="python3 \"$DYNAMIC_PRD_GENERATOR\" generate \"$goal\""

    # Add output path if specified
    if [ -n "$output_path" ]; then
        cmd="$cmd --output \"$output_path\""
    fi

    # Add codebase analysis flag if enabled
    if [ "$with_codebase_analysis" = "true" ]; then
        cmd="$cmd --codebase-analysis"
        log_info "Codebase analysis enabled for file scope estimation"
    fi

    # Run the generator
    if ! eval "$cmd"; then
        log_error "Failed to generate dynamic PRD"
        exit 1
    fi

    # Update PRD_FILE to point to generated file
    if [ -n "$output_path" ]; then
        PRD_FILE="$output_path"
    else
        # Find the generated PRD file (prd-{project}.json)
        local generated_files=(prd-*.json)
        if [ ${#generated_files[@]} -gt 0 ] && [ -f "${generated_files[0]}" ]; then
            PRD_FILE="${generated_files[0]}"
        else
            PRD_FILE="prd.json"
        fi
    fi

    log_success "Dynamic PRD generated: $PRD_FILE"
    echo ""
}

# Display auto-detection summary (INV-008)
# Shows complexity, track, phases before execution
display_auto_detection_summary() {
    if [ ! -f "$COMPLEXITY_DETECTOR" ]; then
        return
    fi

    if ! command -v python3 &> /dev/null; then
        return
    fi

    # Get detection results
    local detection_json
    detection_json=$(python3 "$COMPLEXITY_DETECTOR" detect --prd "$PRD_FILE" --show-track --show-phases --json 2>/dev/null) || return

    # Parse results
    local level
    level=$(echo "$detection_json" | jq -r '.level // 2')
    local level_name
    level_name=$(echo "$detection_json" | jq -r '.level_name // "medium"')
    local track
    track=$(echo "$detection_json" | jq -r '.track // "standard"')
    local phases
    phases=$(echo "$detection_json" | jq -r '.phases | join(" → ")' 2>/dev/null) || phases="implementation"
    local score
    score=$(echo "$detection_json" | jq -r '.score // 0')

    local story_count
    story_count=$(get_total_stories_count)

    # Get quality gates for this level (INV-009)
    local quality_gates=""
    if [ -f "$QUALITY_GATES_SCRIPT" ] && $QUALITY_GATES_ENABLED; then
        quality_gates=$(python3 "$QUALITY_GATES_SCRIPT" get "$level" --json 2>/dev/null | \
                       jq -r '.enabled_gates | join(", ")' 2>/dev/null) || quality_gates=""
    fi

    echo ""
    echo "═══════════════════════════════════════════════════════════════"
    echo "              AUTO-DETECTION RESULTS (INV-008/009)"
    echo "═══════════════════════════════════════════════════════════════"
    echo ""
    echo -e "  ${CYAN}Complexity:${NC}  Level $level ($level_name) - Score: $score"
    echo -e "  ${CYAN}Track:${NC}       $track"
    echo -e "  ${CYAN}Phases:${NC}      $phases"
    echo -e "  ${CYAN}Stories:${NC}     $story_count user stories"
    if [ -n "$quality_gates" ]; then
        echo -e "  ${CYAN}Gates:${NC}       $quality_gates"
    fi
    echo ""
    echo "═══════════════════════════════════════════════════════════════"
    echo ""
}

# ============================================================================
# Phase Detection (INV-005)
# ============================================================================

COMPLEXITY_DETECTOR="${SCRIPT_DIR}/lib/complexity-detector.py"
CURRENT_PHASE=""  # Tracks the current execution phase

# Get phases based on PRD complexity
# Usage: get_prd_phases
# Returns: space-separated list of phases (e.g., "planning solutioning implementation")
get_prd_phases() {
    if [ ! -f "$COMPLEXITY_DETECTOR" ]; then
        log_debug "Complexity detector not found, defaulting to implementation phase"
        echo "implementation"
        return
    fi

    if ! command -v python3 &> /dev/null; then
        log_debug "Python3 not found, defaulting to implementation phase"
        echo "implementation"
        return
    fi

    local phases
    phases=$(python3 "$COMPLEXITY_DETECTOR" detect --prd "$PRD_FILE" --show-phases --json 2>/dev/null | \
             jq -r '.phases | join(" ")' 2>/dev/null) || phases=""

    if [ -z "$phases" ]; then
        echo "implementation"
    else
        echo "$phases"
    fi
}

# Get current phase based on completed stories
# Usage: get_current_phase
# Returns: current phase name (analysis, planning, solutioning, or implementation)
get_current_phase() {
    local total_stories
    total_stories=$(get_total_stories_count)
    local incomplete_stories
    incomplete_stories=$(get_incomplete_stories_count)
    local completed=$((total_stories - incomplete_stories))
    local progress_ratio=0

    if [ "$total_stories" -gt 0 ]; then
        progress_ratio=$((completed * 100 / total_stories))
    fi

    # Get phases for this PRD
    local phases
    phases=$(get_prd_phases)

    # Convert to array
    local phase_array=($phases)
    local num_phases=${#phase_array[@]}

    if [ "$num_phases" -eq 0 ] || [ "$num_phases" -eq 1 ]; then
        echo "implementation"
        return
    fi

    # Determine current phase based on progress
    # Each phase gets an equal portion of the progress bar
    local phase_size=$((100 / num_phases))
    local phase_index=$((progress_ratio / phase_size))

    # Clamp to valid index
    if [ "$phase_index" -ge "$num_phases" ]; then
        phase_index=$((num_phases - 1))
    fi

    echo "${phase_array[$phase_index]}"
}

# Set the current phase (can be overridden via environment or flag)
set_current_phase() {
    local phase="${1:-}"

    if [ -n "$phase" ]; then
        CURRENT_PHASE="$phase"
    else
        CURRENT_PHASE=$(get_current_phase)
    fi

    log_debug "Current phase: $CURRENT_PHASE"
}

# ============================================================================
# Quality Gates (INV-009)
# ============================================================================

# Get complexity level from PRD
# Usage: get_complexity_level
# Returns: complexity level 0-4
get_complexity_level() {
    # Return cached value if available
    if [ -n "$CURRENT_COMPLEXITY_LEVEL" ]; then
        echo "$CURRENT_COMPLEXITY_LEVEL"
        return
    fi

    if [ ! -f "$COMPLEXITY_DETECTOR" ]; then
        log_debug "Complexity detector not found, defaulting to level 2"
        CURRENT_COMPLEXITY_LEVEL="2"
        echo "2"
        return
    fi

    if ! command -v python3 &> /dev/null; then
        log_debug "Python3 not found, defaulting to level 2"
        CURRENT_COMPLEXITY_LEVEL="2"
        echo "2"
        return
    fi

    local level
    level=$(python3 "$COMPLEXITY_DETECTOR" detect --prd "$PRD_FILE" --json 2>/dev/null | \
            jq -r '.level // 2' 2>/dev/null) || level="2"

    CURRENT_COMPLEXITY_LEVEL="$level"
    echo "$level"
}

# Get enabled quality gates for the current complexity level
# Usage: get_enabled_gates
# Returns: space-separated list of enabled gates
get_enabled_gates() {
    if [ ! -f "$QUALITY_GATES_SCRIPT" ]; then
        log_debug "Quality gates script not found"
        echo "tests"
        return
    fi

    local level
    level=$(get_complexity_level)

    local gates
    gates=$(python3 "$QUALITY_GATES_SCRIPT" get "$level" --json 2>/dev/null | \
            jq -r '.enabled_gates | join(" ")' 2>/dev/null) || gates="tests"

    echo "$gates"
}

# Display active quality gates (for verbose mode)
# Usage: display_quality_gates_summary
display_quality_gates_summary() {
    if ! $QUALITY_GATES_ENABLED; then
        return
    fi

    if [ ! -f "$QUALITY_GATES_SCRIPT" ]; then
        return
    fi

    local level
    level=$(get_complexity_level)

    if $VERBOSE; then
        log_info "Quality gates active for complexity level $level:"
        local gates
        gates=$(get_enabled_gates)
        log_debug "  Enabled: $gates"
    fi
}

# Run quality gates for the project
# Usage: run_quality_gates [--verbose]
# Returns: 0 if all blocking gates pass, 1 otherwise
run_quality_gates() {
    if ! $QUALITY_GATES_ENABLED; then
        log_debug "Quality gates disabled, skipping"
        return 0
    fi

    if [ ! -f "$QUALITY_GATES_SCRIPT" ]; then
        log_debug "Quality gates script not found, skipping"
        return 0
    fi

    local verbose_flag=""
    if $VERBOSE; then
        verbose_flag="--verbose"
    fi

    local level
    level=$(get_complexity_level)

    log_info "Running quality gates for complexity level $level..."

    # Run quality gates and capture result
    local result
    local exit_code=0
    result=$(python3 "$QUALITY_GATES_SCRIPT" run "$level" --json $verbose_flag 2>&1) || exit_code=$?

    # Parse result
    local all_passed
    all_passed=$(echo "$result" | jq -r '.all_passed // false' 2>/dev/null) || all_passed="false"

    local blocking_failures
    blocking_failures=$(echo "$result" | jq -r '.blocking_failures | length // 0' 2>/dev/null) || blocking_failures="0"

    local warnings
    warnings=$(echo "$result" | jq -r '.warnings | length // 0' 2>/dev/null) || warnings="0"

    # Report results
    if [ "$all_passed" = "true" ]; then
        log_success "All quality gates passed"
        return 0
    else
        if [ "$blocking_failures" != "0" ]; then
            log_error "Quality gates failed ($blocking_failures blocking failures)"
            # Show blocking failures
            echo "$result" | jq -r '.blocking_failures[]' 2>/dev/null | while read -r failure; do
                log_error "  ✗ $failure"
            done
            return 1
        fi

        if [ "$warnings" != "0" ]; then
            log_warn "Quality gates passed with $warnings warnings"
            # Show warnings
            echo "$result" | jq -r '.warnings[]' 2>/dev/null | while read -r warning; do
                log_warn "  ⚠ $warning"
            done
        fi

        return 0
    fi
}

# ============================================================================
# Completion Summary (INV-010)
# ============================================================================

# Display comprehensive completion summary at end of run
# Usage: display_completion_summary [--json] [--verbose]
display_completion_summary() {
    if ! $COMPLETION_SUMMARY_ENABLED; then
        return 0
    fi

    if [ ! -f "$COMPLETION_SUMMARY_SCRIPT" ]; then
        log_debug "Completion summary script not found: $COMPLETION_SUMMARY_SCRIPT"
        return 0
    fi

    if ! command -v python3 &> /dev/null; then
        log_debug "Python3 not found, skipping completion summary"
        return 0
    fi

    # Build command arguments
    local args="generate --prd $PRD_FILE"

    # Add session state if available
    if [ -f ".claude-loop/session-state.json" ]; then
        args="$args --session .claude-loop/session-state.json"
    fi

    # Find latest metrics file if available
    local latest_metrics=""
    if [ -d ".claude-loop/runs" ]; then
        latest_metrics=$(find .claude-loop/runs -name "metrics.json" -type f 2>/dev/null | sort -r | head -1)
        if [ -n "$latest_metrics" ]; then
            args="$args --metrics $latest_metrics"
        fi
    fi

    # Add verbose flag if enabled
    if $VERBOSE; then
        args="$args --verbose"
    fi

    # Run the completion summary script
    python3 "$COMPLETION_SUMMARY_SCRIPT" $args 2>/dev/null || {
        log_debug "Completion summary generation failed"
        return 0
    }
}

# ============================================================================
# Solutioning Generator (INV-011: Integration of INV-004)
# ============================================================================

# Check if solutioning should run based on complexity level
# Returns: 0 if solutioning should run, 1 otherwise
should_run_solutioning() {
    if ! $SOLUTIONING_ENABLED; then
        log_debug "Solutioning generation disabled"
        return 1
    fi

    if [ ! -f "$SOLUTIONING_GENERATOR" ]; then
        log_debug "Solutioning generator not found: $SOLUTIONING_GENERATOR"
        return 1
    fi

    if ! command -v python3 &> /dev/null; then
        log_debug "Python3 not found, skipping solutioning"
        return 1
    fi

    local level
    level=$(get_complexity_level)

    # Only run solutioning for Level >= 3
    if [ "$level" -ge 3 ]; then
        return 0
    else
        log_debug "Solutioning skipped: complexity level $level < 3"
        return 1
    fi
}

# Run solutioning generator to create architecture.md and ADRs
# Usage: run_solutioning_generator [--force]
# Returns: 0 on success, 1 on failure or skip
run_solutioning_generator() {
    local force_flag=""
    if [ "${1:-}" = "--force" ]; then
        force_flag="--force"
    fi

    if ! should_run_solutioning && [ -z "$force_flag" ]; then
        return 0  # Not needed, but not an error
    fi

    log_info "Running solutioning generator (Level >= 3 detected)..."

    # Determine output directory
    local output_dir="docs"
    if [ -n "$PRD_DIR" ]; then
        output_dir="$PRD_DIR/docs"
    fi

    # Build command arguments
    local args="generate --prd $PRD_FILE --output-dir $output_dir"
    if [ -n "$force_flag" ]; then
        args="$args --force"
    fi

    # Run the generator
    local result
    result=$(python3 "$SOLUTIONING_GENERATOR" $args 2>&1) || {
        log_warn "Solutioning generation encountered issues:"
        echo "$result" | head -5
        return 1
    }

    # Check what was generated
    local arch_file="$output_dir/architecture/architecture.md"
    local adrs_dir="$output_dir/adrs"

    if [ -f "$arch_file" ]; then
        log_success "Generated: $arch_file"
    fi

    if [ -d "$adrs_dir" ] && [ "$(ls -A "$adrs_dir" 2>/dev/null)" ]; then
        local adr_count
        adr_count=$(ls -1 "$adrs_dir"/*.md 2>/dev/null | wc -l | tr -d ' ')
        log_success "Generated: $adr_count ADR template(s) in $adrs_dir"
    fi

    return 0
}

# Display detected ADR topics without generating files
# Usage: display_detected_adrs
display_detected_adrs() {
    if [ ! -f "$SOLUTIONING_GENERATOR" ]; then
        return
    fi

    local level
    level=$(get_complexity_level)

    if [ "$level" -lt 3 ]; then
        return
    fi

    local detected
    detected=$(python3 "$SOLUTIONING_GENERATOR" detect-adrs --prd "$PRD_FILE" --json 2>/dev/null) || return

    local topics
    topics=$(echo "$detected" | jq -r '.detected_topics | keys | join(", ")' 2>/dev/null) || topics=""

    if [ -n "$topics" ] && [ "$topics" != "" ]; then
        log_info "ADR topics detected: $topics"
    fi
}

# ============================================================================
# Agent Integration Functions
# ============================================================================

select_agents_for_story() {
    local story_text="$1"
    local phase="${2:-$CURRENT_PHASE}"  # Use passed phase or current phase

    if ! $AGENTS_ENABLED; then
        return
    fi

    # Export environment for agent registry
    export MAX_AGENTS_PER_ITERATION
    export MAX_TOKENS_PER_AGENT
    export ENABLED_TIERS
    export LOCAL_AGENTS_DIR="$BUNDLED_AGENTS_DIR"

    # Call agent registry to select agents with phase awareness
    # Pass external AGENTS_DIR for additional specialists (empty string if not set)
    local selected_agents
    selected_agents=$("$AGENT_REGISTRY" select "$story_text" "$AGENTS_DIR" "$MAX_AGENTS_PER_ITERATION" "$phase" 2>/dev/null) || true

    # Log phase influence if verbose
    if $VERBOSE && [ -n "$phase" ] && [ "$phase" != "implementation" ]; then
        log_debug "Phase '$phase' influencing agent selection"
    fi

    echo "$selected_agents"
}

load_agent_prompts() {
    # Export bundled agents location for registry
    export LOCAL_AGENTS_DIR="$BUNDLED_AGENTS_DIR"

    local agents_list="$*"

    if [ -z "$agents_list" ]; then
        return
    fi

    echo ""
    echo "# Specialist Agent Expertise"
    echo ""
    echo "The following specialist knowledge is available for this story:"
    echo ""

    for agent in $agents_list; do
        if [ -n "$agent" ]; then
            log_agent "Loading: $agent"
            echo "---"
            echo "## $agent"
            echo ""
            # Pass external AGENTS_DIR for additional specialists
            "$AGENT_REGISTRY" load "$agent" "$AGENTS_DIR" 2>/dev/null || echo "# Agent $agent not found"
            echo ""
        fi
    done
}

build_iteration_prompt() {
    local story_id="$1"
    local story_text="$2"

    # ========================================================================
    # PHASE 1 FIX #3: Complexity-based feature activation
    # ========================================================================
    # Detect task complexity and disable features for simple tasks to avoid noise
    local task_complexity_level=-1
    local original_agents_enabled=$AGENTS_ENABLED
    local original_experience_enabled=$EXPERIENCE_AUGMENTATION_ENABLED

    if command -v python3 &>/dev/null && [ -f "${SCRIPT_DIR}/lib/complexity-detector.py" ]; then
        # Detect complexity (returns level 0-4: micro, small, medium, large, enterprise)
        local complexity_output
        complexity_output=$(python3 "${SCRIPT_DIR}/lib/complexity-detector.py" detect "$story_text" --prd "$PRD_FILE" --json 2>/dev/null || echo "{}")

        task_complexity_level=$(echo "$complexity_output" | jq -r '.level // -1' 2>/dev/null || echo "-1")

        # For simple tasks (levels 0-1: micro, small), disable features to reduce noise
        if [ "$task_complexity_level" -eq 0 ] || [ "$task_complexity_level" -eq 1 ]; then
            log_debug "Simple task detected (level $task_complexity_level), skipping feature activation"
            AGENTS_ENABLED=false
            EXPERIENCE_AUGMENTATION_ENABLED=false
        fi
    fi

    # Start with base prompt
    local full_prompt
    full_prompt=$(cat "$PROMPT_FILE")

    # Add session context (US-001: SessionStart Hook System)
    # Only on first iteration to avoid repeated injection
    if [ -f "${SCRIPT_DIR}/lib/session-hooks.sh" ]; then
        local session_context
        session_context=$("${SCRIPT_DIR}/lib/session-hooks.sh" 2>/dev/null || echo "")

        if [ -n "$session_context" ]; then
            # Prepend session context to prompt
            full_prompt="${session_context}

---

${full_prompt}"
        fi
    fi

    # Add mandatory skill enforcement (US-002: Mandatory Skill Enforcement Layer)
    if [ -f "${SCRIPT_DIR}/lib/skill-enforcer.sh" ]; then
        local mandatory_skills
        # Get complexity from story if available
        local story_complexity
        story_complexity=$(jq -r ".userStories[] | select(.id == \"$story_id\") | .estimatedComplexity // \"medium\"" "$PRD_FILE" 2>/dev/null || echo "medium")

        # Convert complexity to numeric (simple=3, medium=5, complex=7)
        local complexity_num=5
        case "$story_complexity" in
            simple) complexity_num=3 ;;
            medium) complexity_num=5 ;;
            complex) complexity_num=7 ;;
        esac

        mandatory_skills=$("${SCRIPT_DIR}/lib/skill-enforcer.sh" "$story_text" "$complexity_num" 2>/dev/null || echo "")

        if [ -n "$mandatory_skills" ]; then
            # Prepend mandatory skills to prompt
            full_prompt="${mandatory_skills}

---

${full_prompt}"
        fi
    fi

    # Add experience augmentation if enabled
    if $EXPERIENCE_AUGMENTATION_ENABLED; then
        local experience_section
        experience_section=$(get_experience_augmentation "$story_text" "$story_id")

        if [ -n "$experience_section" ]; then
            # Prepend experience section to iteration prompt
            full_prompt="${experience_section}
${full_prompt}"
        fi
    fi

    # Add relevant learnings if enabled (US-002 - Tier 1 Pattern Extraction)
    if $LEARNINGS_ENABLED; then
        local relevant_learnings
        relevant_learnings=$(get_relevant_learnings "$story_id" "$story_text")

        local learnings_count
        learnings_count=$(echo "$relevant_learnings" | jq 'length' 2>/dev/null || echo "0")

        if [ "$learnings_count" -gt 0 ]; then
            local learnings_section
            learnings_section="# Relevant Learnings from Past Iterations

The following learnings from past iterations may be relevant to this story:

"

            # Format learnings as markdown
            learnings_section+=$(echo "$relevant_learnings" | jq -r '.[] | "## Learning from \(.story_id) (iteration \(.iteration))
**Tags:** \(.tags | join(", "))
**Helpful Count:** \(.helpful_count)

\(.lesson)

---
"' 2>/dev/null || echo "")

            # Prepend learnings section to iteration prompt
            full_prompt="${learnings_section}

${full_prompt}"
        fi
    fi

    # Add agent expertise if enabled
    if $AGENTS_ENABLED; then
        local selected_agents
        selected_agents=$(select_agents_for_story "$story_text")

        if [ -n "$selected_agents" ]; then
            local agent_count
            agent_count=$(echo "$selected_agents" | wc -l | tr -d ' ')
            log_agent "Selected $agent_count agent(s) for story $story_id"

            # Log agent selection for benchmark analysis
            mkdir -p .claude-loop/logs
            echo "$selected_agents" | jq -R -s -c 'split("\n") | map(select(length > 0))' > ".claude-loop/logs/agents_${story_id}.json" 2>/dev/null || echo "[]" > ".claude-loop/logs/agents_${story_id}.json"

            # Load agent prompts
            local agent_prompts
            agent_prompts=$(load_agent_prompts $selected_agents)

            # Prepend agent expertise to iteration prompt
            full_prompt="${agent_prompts}

---

${full_prompt}"
        else
            log_debug "No agents matched for this story"
            # Log no agents for benchmark analysis
            mkdir -p .claude-loop/logs
            echo "[]" > ".claude-loop/logs/agents_${story_id}.json"
        fi
    fi

    # Add workspace sandboxing information if enabled
    if $WORKSPACE_ENABLED; then
        local workspace_section
        workspace_section=$(get_workspace_prompt_section)

        if [ -n "$workspace_section" ]; then
            # Prepend workspace section to iteration prompt
            full_prompt="${workspace_section}

---

${full_prompt}"
        fi
    fi

    # Log token breakdown for benchmark analysis
    local prompt_size
    prompt_size=$(echo "$full_prompt" | wc -c | tr -d ' ')
    mkdir -p .claude-loop/logs
    cat > ".claude-loop/logs/tokens_${story_id}.json" << EOF
{
  "story_id": "$story_id",
  "total_chars": $prompt_size,
  "estimated_tokens": $((prompt_size / 4)),
  "complexity_level": $task_complexity_level,
  "agents_enabled": $AGENTS_ENABLED,
  "experience_enabled": $EXPERIENCE_AUGMENTATION_ENABLED
}
EOF

    # PHASE 1 FIX #3: Restore original feature flags
    # Ensure flags are reset for next story
    AGENTS_ENABLED=$original_agents_enabled
    EXPERIENCE_AUGMENTATION_ENABLED=$original_experience_enabled

    echo "$full_prompt"
}

# ============================================================================
# Review Panel Functions (LLM-007, US-005)
# ============================================================================

# Run spec compliance review (US-005: Two-Stage Review System)
# Stage 1: Verify all requirements met, nothing extra
run_spec_compliance_review() {
    local story_id=$1

    if [ ! -f "${SCRIPT_DIR}/lib/spec-compliance-reviewer.py" ]; then
        log_warn "Spec compliance reviewer not found, skipping"
        return 0
    fi

    log_info "Running spec compliance review (Stage 1/2)..."

    # Get changes summary from recent commits
    local changes_summary
    changes_summary=$(git log -1 --pretty=format:"%B" 2>/dev/null || echo "No commit message available")

    # Run spec compliance review
    local review_output
    local review_exit_code=0
    review_output=$(python3 "${SCRIPT_DIR}/lib/spec-compliance-reviewer.py" "$PRD_FILE" "$story_id" "$changes_summary" 2>&1) || review_exit_code=$?

    # Display review output
    echo "$review_output"

    if [ $review_exit_code -eq 0 ]; then
        log_success "Spec compliance: PASS"
        return 0
    else
        log_warn "Spec compliance: FAIL"
        echo "$review_output"
        return 1  # Need to fix and re-review
    fi
}

# Run multi-LLM review on completed story (Stage 2: Code Quality)
run_review_panel() {
    local story_id=$1
    local story_title=$2

    if ! $REVIEW_ENABLED; then
        return 0  # Review not enabled, skip
    fi

    if [ ! -f "$REVIEW_PANEL_SCRIPT" ]; then
        log_warn "Review panel script not found: $REVIEW_PANEL_SCRIPT"
        return 0
    fi

    log_info "Running multi-LLM review panel for $story_id..."

    # Get the git diff for the completed story
    local diff_output
    diff_output=$(git diff HEAD~1 HEAD 2>/dev/null || echo "")

    if [ -z "$diff_output" ]; then
        log_warn "No changes detected for review, skipping"
        return 0
    fi

    # Get story context from prd.json
    local story_context
    story_context=$(jq -r ".userStories[] | select(.id == \"$story_id\") | {id, title, description, acceptanceCriteria}" "$PRD_FILE" 2>/dev/null || echo "{}")

    # Save diff to temp file
    local diff_file
    diff_file=$(mktemp)
    echo "$diff_output" > "$diff_file"

    # Save context to temp file
    local context_file
    context_file=$(mktemp)
    echo "$story_context" > "$context_file"

    # Build review command
    local review_cmd="python3 \"$REVIEW_PANEL_SCRIPT\" review --diff \"$diff_file\" --context \"$context_file\""

    # Add reviewers if specified
    if [ -n "$REVIEW_PROVIDERS" ]; then
        review_cmd="$review_cmd --reviewers $REVIEW_PROVIDERS"
    fi

    # Run review and capture output
    local review_output
    local review_exit_code=0
    review_output=$(eval "$review_cmd" 2>&1) || review_exit_code=$?

    # Clean up temp files
    rm -f "$diff_file" "$context_file"

    if [ $review_exit_code -ne 0 ]; then
        log_warn "Review panel failed: $review_output"
        return 1
    fi

    # Parse review results (expecting JSON)
    local consensus_score
    consensus_score=$(echo "$review_output" | jq -r '.consensus_score // 0' 2>/dev/null || echo "0")

    local total_issues
    total_issues=$(echo "$review_output" | jq -r '.total_issues // 0' 2>/dev/null || echo "0")

    local critical_issues
    critical_issues=$(echo "$review_output" | jq -r '.critical_issues // 0' 2>/dev/null || echo "0")

    log_info "Review Results: Score=$consensus_score/10, Issues=$total_issues (Critical=$critical_issues)"

    # Check if score meets threshold
    if [ "$consensus_score" -lt "$REVIEW_THRESHOLD" ]; then
        log_warn "Review score ($consensus_score) below threshold ($REVIEW_THRESHOLD)"

        # Return review results for potential fix cycle
        echo "$review_output"
        return 2  # Special exit code: needs fixes
    else
        log_success "Review passed! Score: $consensus_score/10"

        # Log review results
        echo "$review_output"
        return 0
    fi
}

# ============================================================================
# Delegation Processing
# ============================================================================

# Process delegation requests from Claude output
# Parses [delegate:...] syntax and executes subordinate tasks
#
# Arguments:
#   $1 - output: Claude's iteration output
#   $2 - story_id: Parent story ID
#   $3 - iteration: Current iteration number
#
# Returns: 0 on success, 1 on failure
process_delegations() {
    local output="$1"
    local story_id="$2"
    local iteration="$3"

    # Skip if delegation is not enabled
    if ! $ENABLE_DELEGATION; then
        return 0
    fi

    # Check for delegation syntax in output
    if ! echo "$output" | grep -q '\[delegate:'; then
        log_debug "No delegation requests found in output"
        return 0
    fi

    # Source delegation library
    if [ ! -f "$DELEGATION_SCRIPT" ]; then
        log_error "Delegation script not found: $DELEGATION_SCRIPT"
        return 1
    fi

    source "$DELEGATION_SCRIPT"

    # Parse delegations from output
    local delegations_json
    delegations_json=$(echo "$output" | "$SCRIPT_DIR/lib/delegation-parser.sh" count)
    local delegation_count
    delegation_count=$(echo "$delegations_json" | jq -r '.count' 2>/dev/null || echo "0")

    if [ "$delegation_count" -eq 0 ]; then
        log_debug "No valid delegation requests parsed"
        return 0
    fi

    log_info "Found $delegation_count delegation request(s) in iteration output"

    # Get parent execution ID (use story_id + iteration for now)
    local parent_execution_id="${story_id}-iter-${iteration}"

    # Calculate current context size (estimate from prompt)
    local parent_context_tokens
    parent_context_tokens=$(echo "$output" | wc -w | tr -d ' ')  # Rough estimate

    # Process each delegation
    local delegation_idx=0
    local delegation_failures=0

    while [ $delegation_idx -lt "$delegation_count" ]; do
        # Extract delegation at index
        local delegation_json
        delegation_json=$(echo "$output" | "$SCRIPT_DIR/lib/delegation-parser.sh" parse "$delegation_idx")

        if [ -z "$delegation_json" ]; then
            log_warn "Failed to parse delegation at index $delegation_idx"
            ((delegation_failures++))
            ((delegation_idx++))
            continue
        fi

        # Execute the delegation
        log_info "Executing delegation $((delegation_idx + 1))/$delegation_count"

        if execute_single_delegation "$delegation_json" "$story_id" "$parent_execution_id" "$parent_context_tokens"; then
            log_success "Delegation $((delegation_idx + 1)) completed successfully"
        else
            log_error "Delegation $((delegation_idx + 1)) failed"
            ((delegation_failures++))
        fi

        ((delegation_idx++))
    done

    # Report results
    local delegation_successes=$((delegation_count - delegation_failures))
    log_info "Delegation summary: $delegation_successes/$delegation_count successful"

    # Return success if at least one delegation succeeded
    if [ $delegation_successes -gt 0 ]; then
        return 0
    else
        return 1
    fi
}

# ============================================================================
# Iteration Functions
# ============================================================================

# Run iteration with non-Claude provider using agent-runtime
run_iteration_with_agent_runtime() {
    local iteration=$1
    local story_id=$2
    local story_title=$3
    local task_description=$4

    log_iteration "$iteration" "Working on: $story_id - $story_title (Provider: $PRIMARY_PROVIDER)"

    # Build task from story context
    local story_details
    story_details=$(jq -r --arg id "$story_id" '.userStories[] | select(.id == $id)' "$PRD_FILE")

    local acceptance_criteria
    acceptance_criteria=$(echo "$story_details" | jq -r '.acceptanceCriteria | join("\n- ")' 2>/dev/null || echo "")

    local task_prompt="
# Story: $story_id - $story_title

## Description
$task_description

## Acceptance Criteria
- $acceptance_criteria

## Instructions
Implement this story by:
1. Reading relevant files to understand the codebase
2. Making necessary code changes
3. Running tests to verify functionality
4. Committing changes with appropriate message

Use the available tools (read_file, write_file, run_bash, git_command) to complete this task.
Update the prd.json file to mark this story as complete (set passes: true).
"

    # Build agent-runtime command
    local runtime_cmd="python3 \"$AGENT_RUNTIME\" run --provider $PRIMARY_PROVIDER --task \"$task_prompt\""

    # Add model override if specified
    if [ -n "$PROVIDER_MODELS" ]; then
        runtime_cmd="$runtime_cmd --model $PROVIDER_MODELS"
    fi

    # Add JSON output for parsing
    runtime_cmd="$runtime_cmd --json"

    log_debug "Running agent-runtime with provider: $PRIMARY_PROVIDER"

    # Execute agent-runtime
    local output
    local exit_code=0
    output=$(eval "$runtime_cmd" 2>&1) || exit_code=$?

    # Parse JSON output
    local success
    success=$(echo "$output" | jq -r '.success // false' 2>/dev/null || echo "false")

    local error_msg
    error_msg=$(echo "$output" | jq -r '.error // ""' 2>/dev/null || echo "")

    if [ "$success" = "true" ]; then
        log_success "Story $story_id completed with $PRIMARY_PROVIDER"

        # Verify story was marked complete in prd.json
        local story_passes
        story_passes=$(jq -r ".userStories[] | select(.id == \"$story_id\") | .passes" "$PRD_FILE" 2>/dev/null || echo "false")

        if [ "$story_passes" = "true" ]; then
            return 0
        else
            log_warn "Story completed but not marked as passes=true in prd.json"
            return 1
        fi
    else
        log_error "Story $story_id failed: $error_msg"
        return 1
    fi
}

run_iteration() {
    local iteration=$1
    local output
    local exit_code=0

    # Update current phase based on progress
    set_current_phase

    # Get the next story to work on
    local story_info
    story_info=$(get_next_story)
    local story_id
    story_id=$(echo "$story_info" | cut -d'|' -f1)
    local story_title
    story_title=$(echo "$story_info" | cut -d'|' -f2)
    local story_description
    story_description=$(echo "$story_info" | cut -d'|' -f3)

    # Route to agent-runtime if using non-Claude provider (LLM-013)
    if [ "$PRIMARY_PROVIDER" != "claude" ]; then
        log_info "Using provider: $PRIMARY_PROVIDER (non-Claude)"
        run_iteration_with_agent_runtime "$iteration" "$story_id" "$story_title" "$story_description"
        return $?
    fi

    log_iteration "$iteration" "Working on: $story_id - $story_title"

    # Execute pre_iteration hooks (US-001 - Tier 1 Pattern Extraction)
    execute_hooks "pre_iteration" "$story_id" "$iteration" "$(pwd)" "$(git branch --show-current 2>/dev/null || echo "")" "${CURRENT_PHASE:-implementation}" || {
        log_error "pre_iteration hooks failed, aborting iteration"
        return 1
    }

    # Log current phase if not default implementation
    if [ -n "$CURRENT_PHASE" ] && [ "$CURRENT_PHASE" != "implementation" ]; then
        log_info "Current phase: $CURRENT_PHASE (phase-aware agent selection active)"
    fi

    # Start progress tracking (US-001)
    if $PROGRESS_INDICATORS_ENABLED && type start_story >/dev/null 2>&1; then
        # Get acceptance criteria from PRD
        local acceptance_criteria
        acceptance_criteria=$(jq -r ".userStories[] | select(.id == \"$story_id\") | .acceptanceCriteria[]" "$PRD_FILE" 2>/dev/null)
        if [ -n "$acceptance_criteria" ]; then
            # Convert to array for start_story function
            local criteria_array=()
            while IFS= read -r line; do
                criteria_array+=("$line")
            done <<< "$acceptance_criteria"

            start_story "$story_id" "$story_title" "${criteria_array[@]}"
            set_current_action "Preparing iteration prompt..."
        fi
    fi

    # Start execution logging
    if $EXECUTION_LOGGING_ENABLED; then
        # Build context with iteration info, agents, phase, and provider
        local exec_context
        exec_context=$(cat << EOF
{
  "iteration": $iteration,
  "max_iterations": $MAX_ITERATIONS,
  "agents_enabled": $AGENTS_ENABLED,
  "current_phase": "$CURRENT_PHASE",
  "provider": "$PRIMARY_PROVIDER",
  "project": "$(get_project_name)",
  "branch": "$(get_branch_from_prd)"
}
EOF
)
        log_execution_start "$story_id" "$story_title" "$exec_context"
    fi

    # Get full story text for agent selection
    local story_text
    story_text=$(get_story_text "$story_id")

    # Build prompt with agent expertise
    local full_prompt
    full_prompt=$(build_iteration_prompt "$story_id" "$story_text")

    log_debug "Prompt size: $(echo "$full_prompt" | wc -c | tr -d ' ') chars"

    # Update progress action (US-001)
    if $PROGRESS_INDICATORS_ENABLED && type set_current_action >/dev/null 2>&1; then
        set_current_action "Running Claude Code iteration..."
    fi

    # Log the Claude invocation action
    if $EXECUTION_LOGGING_ENABLED; then
        local prompt_size
        prompt_size=$(echo "$full_prompt" | wc -c | tr -d ' ')
        log_action "Claude" "{\"prompt_size\": $prompt_size, \"mode\": \"print\"}" "started" ""
    fi

    # Run Claude Code with the prompt
    if $VERBOSE; then
        output=$(echo "$full_prompt" | claude --print --dangerously-skip-permissions 2>&1) || exit_code=$?
    else
        output=$(echo "$full_prompt" | claude --print --dangerously-skip-permissions 2>&1) || exit_code=$?
    fi

    # Process any delegation requests (US-007 - Phase 2)
    # Must happen before story completion check so delegations can contribute to AC
    if $ENABLE_DELEGATION; then
        process_delegations "$output" "$story_id" "$iteration" || {
            log_warn "Delegation processing encountered errors, but continuing iteration"
        }
    fi

    # Check for completion signal - but ONLY if PRD confirms all stories complete
    if echo "$output" | grep -q "$COMPLETION_SIGNAL"; then
        # Verify PRD actually shows all stories complete (prevent false positives)
        local remaining_stories
        remaining_stories=$(get_incomplete_stories_count)

        if [ "$remaining_stories" -eq 0 ]; then
            # Log successful completion
            if $EXECUTION_LOGGING_ENABLED; then
                log_execution_end "success" "" "$exit_code"
            fi
            return 0  # All stories complete (verified)
        else
            # Completion signal found but PRD shows incomplete stories - likely false positive
            log_warn "Completion signal detected but $remaining_stories stories remain incomplete. Continuing execution."
        fi
    fi

    # Check if story completed (by checking if passes is now true)
    local story_passes
    story_passes=$(jq -r ".userStories[] | select(.id == \"$story_id\") | .passes" "$PRD_FILE" 2>/dev/null || echo "false")

    if [ "$story_passes" = "true" ]; then
        # Story completed successfully
        log_success "Story $story_id completed"

        # Mark story as complete in progress indicators (US-001)
        if $PROGRESS_INDICATORS_ENABLED && type complete_story >/dev/null 2>&1; then
            complete_story
        fi

        # Run two-stage review if enabled (LLM-007, US-005)
        if $REVIEW_ENABLED; then
            local review_cycle=1
            local review_passed=false
            local spec_compliance_passed=false

            while [ $review_cycle -le $MAX_REVIEW_CYCLES ] && ! $review_passed; do
                if [ $review_cycle -gt 1 ]; then
                    log_info "Review-fix cycle $review_cycle/$MAX_REVIEW_CYCLES"
                fi

                # Stage 1: Spec compliance review (US-005)
                # Must pass before code quality review
                if ! $spec_compliance_passed; then
                    log_info "Stage 1/2: Spec Compliance Review"
                    local spec_result
                    local spec_exit_code=0
                    spec_result=$(run_spec_compliance_review "$story_id") || spec_exit_code=$?

                    if [ $spec_exit_code -eq 0 ]; then
                        spec_compliance_passed=true
                        log_success "Spec compliance: PASS"

                        # Log spec compliance results
                        if $EXECUTION_LOGGING_ENABLED; then
                            log_action "SpecCompliance" "$spec_result" "success" ""
                        fi
                    else
                        log_warn "Spec compliance: FAIL (cycle $review_cycle/$MAX_REVIEW_CYCLES)"

                        # If more cycles available, continue to fix
                        if [ $review_cycle -lt $MAX_REVIEW_CYCLES ]; then
                            review_cycle=$((review_cycle + 1))
                            continue
                        else
                            log_error "Spec compliance failed after $MAX_REVIEW_CYCLES cycles"
                            break
                        fi
                    fi
                fi

                # Stage 2: Code quality review (only if spec compliance passed)
                if $spec_compliance_passed; then
                    log_info "Stage 2/2: Code Quality Review"
                    local review_result
                    local review_exit_code=0
                    review_result=$(run_review_panel "$story_id" "$story_title") || review_exit_code=$?

                    if [ $review_exit_code -eq 0 ]; then
                        # Both reviews passed
                        review_passed=true
                        log_success "Code quality review: PASS"
                        log_success "Two-stage review complete: Both stages passed"

                        # Log review results to execution log
                        if $EXECUTION_LOGGING_ENABLED && [ -n "$review_result" ]; then
                            log_action "ReviewPanel" "$review_result" "success" ""
                        fi
                elif [ $review_exit_code -eq 2 ]; then
                    # Review failed, needs fixes
                    if [ $review_cycle -lt $MAX_REVIEW_CYCLES ]; then
                        log_warn "Review failed, requesting fixes (cycle $review_cycle/$MAX_REVIEW_CYCLES)"

                        # Extract issues for fix prompt
                        local issues_summary
                        issues_summary=$(echo "$review_result" | jq -r '.reviews[].issues[].description' 2>/dev/null | head -10 | paste -sd "," - || echo "Review identified issues")

                        # Build fix prompt
                        local fix_prompt
                        fix_prompt="The previous implementation was reviewed by multiple LLMs and identified issues:

$issues_summary

Please address these review comments and fix the identified issues. Make sure all acceptance criteria are still met."

                        # Run another iteration with fix prompt
                        local fix_output
                        local fix_exit_code=0
                        fix_output=$(echo "$fix_prompt" | claude --print --dangerously-skip-permissions 2>&1) || fix_exit_code=$?

                        # Increment review cycle
                        ((review_cycle++))
                    else
                        log_warn "Maximum review cycles reached, proceeding despite review failures"
                        review_passed=true  # Force pass to avoid infinite loop

                        # Log review failure
                        if $EXECUTION_LOGGING_ENABLED && [ -n "$review_result" ]; then
                            log_action "ReviewPanel" "$review_result" "failure" "Maximum cycles reached"
                        fi
                    fi
                else
                    # Review panel error
                    log_warn "Review panel error, skipping review"
                    review_passed=true  # Skip review on error
                    break
                fi
            fi  # Close the "if $spec_compliance_passed" block from line 3233
            done
        fi

        # Log successful execution
        if $EXECUTION_LOGGING_ENABLED; then
            log_execution_end "success" "" "$exit_code"
        fi

        # Check if all stories complete
        local remaining
        remaining=$(get_incomplete_stories_count)
        if [ "$remaining" -eq 0 ]; then
            # Execute post_iteration hook (US-001)
            execute_hooks "post_iteration" "$story_id" "$iteration" "$(pwd)" "$(git branch --show-current 2>/dev/null || echo "")" "${CURRENT_PHASE:-implementation}"
            return 0  # All stories complete
        fi

        # Execute post_iteration hook on success (US-001)
        execute_hooks "post_iteration" "$story_id" "$iteration" "$(pwd)" "$(git branch --show-current 2>/dev/null || echo "")" "${CURRENT_PHASE:-implementation}"

        # Write learning after successful iteration (US-002)
        if $LEARNINGS_ENABLED; then
            local story_description
            story_description=$(jq -r ".userStories[] | select(.id == \"$story_id\") | .description" "$PRD_FILE" 2>/dev/null || echo "")

            local story_files
            story_files=$(jq -r ".userStories[] | select(.id == \"$story_id\") | .fileScope[]?" "$PRD_FILE" 2>/dev/null | tr '\n' ' ' || echo "")

            # Extract tags
            local tags
            tags=$(extract_story_tags "$story_description" "$story_files")

            # Extract lesson from output (last meaningful section)
            local lesson
            lesson=$(echo "$output" | grep -E "Story.*complete|implemented|added|created|fixed" | tail -5 | tr '\n' ' ' | cut -c1-500 || echo "Iteration completed successfully")

            # Build context JSON
            local context_json
            context_json=$(jq -n \
                --arg files "$story_files" \
                --argjson duration 0 \
                '{files: ($files | split(" ") | map(select(length > 0))), duration_ms: $duration}' 2>/dev/null || echo '{}')

            learnings_write "$story_id" "$iteration" "true" "$lesson" "$tags" "$context_json"
        fi
    fi

    # Check for errors
    if [ $exit_code -ne 0 ]; then
        log_warn "Iteration $iteration exited with code $exit_code"

        # Execute on_error hooks (US-001)
        execute_hooks "on_error" "$story_id" "$iteration" "$(pwd)" "$(git branch --show-current 2>/dev/null || echo "")" "${CURRENT_PHASE:-implementation}"

        # Write learning after failed iteration (US-002)
        if $LEARNINGS_ENABLED; then
            local story_description
            story_description=$(jq -r ".userStories[] | select(.id == \"$story_id\") | .description" "$PRD_FILE" 2>/dev/null || echo "")

            local story_files
            story_files=$(jq -r ".userStories[] | select(.id == \"$story_id\") | .fileScope[]?" "$PRD_FILE" 2>/dev/null | tr '\n' ' ' || echo "")

            # Extract tags
            local tags
            tags=$(extract_story_tags "$story_description" "$story_files")

            # Extract error/lesson from output
            local lesson
            lesson="Failed with exit code $exit_code. Error: $(echo "$output" | tail -10 | head -5 | tr '\n' ' ' | cut -c1-500)"

            # Build context JSON
            local context_json
            context_json=$(jq -n \
                --arg files "$story_files" \
                --argjson duration 0 \
                --argjson exit_code "$exit_code" \
                '{files: ($files | split(" ") | map(select(length > 0))), duration_ms: $duration, exit_code: $exit_code}' 2>/dev/null || echo '{}')

            learnings_write "$story_id" "$iteration" "false" "$lesson" "$tags" "$context_json"
        fi

        # Log failed execution
        if $EXECUTION_LOGGING_ENABLED; then
            # Extract error message from output (last few lines often contain error)
            local error_msg
            error_msg=$(echo "$output" | tail -10 | head -5 | tr '\n' ' ' | cut -c1-500)
            log_execution_end "failure" "$error_msg" "$exit_code"
        fi
    else
        # Story not complete but no error - still in progress
        if $EXECUTION_LOGGING_ENABLED; then
            log_execution_end "in_progress" "" "$exit_code"
        fi

        # Execute post_iteration hook on partial success (US-001)
        execute_hooks "post_iteration" "$story_id" "$iteration" "$(pwd)" "$(git branch --show-current 2>/dev/null || echo "")" "${CURRENT_PHASE:-implementation}"
    fi

    return 1  # More work to do
}

# =============================================================================
# PRD Completion Functions (for new prds/active/* structure)
# =============================================================================

# Update MANIFEST.yaml when all stories are complete
update_manifest_on_completion() {
    # Only applicable if we're using the new PRD structure with PRD_DIR
    if [ -z "$PRD_DIR" ]; then
        log_debug "Not using new PRD structure, skipping MANIFEST.yaml update"
        return 0
    fi

    local manifest_file="$PRD_DIR/MANIFEST.yaml"
    if [ ! -f "$manifest_file" ]; then
        log_warn "MANIFEST.yaml not found at $manifest_file"
        return 1
    fi

    # Use Python to update the MANIFEST.yaml (handles YAML properly)
    python3 << EOF
import sys
try:
    import yaml
except ImportError:
    print("PyYAML not installed, skipping MANIFEST.yaml update", file=sys.stderr)
    sys.exit(0)

from datetime import datetime, timezone
import json

manifest_file = "$manifest_file"
prd_file = "$PRD_FILE"

# Load manifest
with open(manifest_file, 'r') as f:
    manifest = yaml.safe_load(f)

# Load prd.json to get story counts
with open(prd_file, 'r') as f:
    prd_data = json.load(f)

stories = prd_data.get('userStories', [])
total = len(stories)
completed = sum(1 for s in stories if s.get('passes', False))

# Update manifest
timestamp = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
manifest['status'] = 'completed'
manifest['updated_at'] = timestamp
manifest['completed_at'] = timestamp
manifest['story_count'] = total
manifest['completed_stories'] = completed

# Save manifest
with open(manifest_file, 'w') as f:
    yaml.dump(manifest, f, default_flow_style=False, allow_unicode=True, sort_keys=False)

print(f"Updated MANIFEST.yaml: status=completed, stories={completed}/{total}")
EOF

    local exit_code=$?
    if [ $exit_code -eq 0 ]; then
        log_success "Updated MANIFEST.yaml to status=completed"
        return 0
    else
        log_warn "Failed to update MANIFEST.yaml"
        return 1
    fi
}

# Move PRD to prds/completed/ on successful completion
move_prd_to_completed() {
    # Only applicable if we're using the new PRD structure with PRD_DIR
    if [ -z "$PRD_DIR" ]; then
        log_debug "Not using new PRD structure, skipping PRD move"
        return 0
    fi

    # Check if PRD_DIR is in prds/active/
    local prds_active_dir="${SCRIPT_DIR}/prds/active"
    if [[ "$PRD_DIR" != "$prds_active_dir"* ]]; then
        log_debug "PRD is not in prds/active/, skipping move"
        return 0
    fi

    local prd_name
    prd_name=$(basename "$PRD_DIR")
    local completed_dir="${SCRIPT_DIR}/prds/completed/$prd_name"

    # Check if target already exists
    if [ -d "$completed_dir" ]; then
        log_warn "Completed directory already exists: $completed_dir"
        log_warn "PRD not moved. Manual intervention may be required."
        return 1
    fi

    # Create prds/completed/ if it doesn't exist
    mkdir -p "${SCRIPT_DIR}/prds/completed"

    # Move the PRD directory
    log_info "Moving PRD to prds/completed/..."
    if mv "$PRD_DIR" "$completed_dir"; then
        log_success "Moved PRD to: $completed_dir"

        # Update PRD_DIR and PRD_FILE to reflect new location
        PRD_DIR="$completed_dir"
        PRD_FILE="$completed_dir/prd.json"
        PROGRESS_FILE="$completed_dir/progress.txt"

        # Log audit entry using prd-manager if available
        local prd_manager="${SCRIPT_DIR}/lib/prd-manager.py"
        if [ -f "$prd_manager" ]; then
            # Get PRD ID from manifest
            local prd_id
            prd_id=$(grep -E '^id:' "$completed_dir/MANIFEST.yaml" 2>/dev/null | head -1 | cut -d':' -f2 | tr -d ' ')
            if [ -n "$prd_id" ]; then
                # Log completion using prd-manager's audit function
                python3 "$prd_manager" audit --json 2>/dev/null | head -1 >/dev/null || true
            fi
        fi

        return 0
    else
        log_error "Failed to move PRD to completed/"
        return 1
    fi
}

# Handle PRD completion (update manifest and move)
handle_prd_completion() {
    log_info "Handling PRD completion..."

    # Update MANIFEST.yaml
    update_manifest_on_completion

    # Move PRD to completed directory
    move_prd_to_completed

    # Update PRD index if indexer is available
    local indexer="${SCRIPT_DIR}/lib/prd-indexer.py"
    if [ -f "$indexer" ]; then
        log_info "Updating PRD index..."
        python3 "$indexer" rebuild 2>/dev/null >/dev/null || log_debug "Index rebuild skipped"
    fi

    return 0
}

print_summary() {
    local total
    local complete
    local incomplete

    total=$(get_total_stories_count)
    incomplete=$(get_incomplete_stories_count)
    complete=$((total - incomplete))

    echo ""
    echo "═══════════════════════════════════════════════════════════════"
    echo "                      CLAUDE-LOOP SUMMARY"
    echo "═══════════════════════════════════════════════════════════════"
    echo ""
    echo "  Stories: $complete/$total complete"
    echo ""

    if [ "$incomplete" -eq 0 ]; then
        echo -e "  Status: ${GREEN}ALL STORIES COMPLETE${NC}"
    else
        echo -e "  Status: ${YELLOW}$incomplete stories remaining${NC}"
    fi

    if $AGENTS_ENABLED; then
        echo ""
        echo -e "  Agents: ${MAGENTA}Enabled${NC} (max $MAX_AGENTS_PER_ITERATION per story)"
    fi

    if $EXPERIENCE_AUGMENTATION_ENABLED; then
        echo -e "  Experience: ${CYAN}Enabled${NC} (helpful_rate > ${MIN_HELPFUL_RATE}, max ${MAX_EXPERIENCES})"
    fi

    if $UNITY_MODE; then
        echo -e "  Unity:  ${CYAN}Enabled${NC} (Quest 3 XR mode)"
    fi

    if $RESUME_MODE; then
        echo -e "  Resume: ${GREEN}Enabled${NC} (will check for checkpoints)"
    fi

    # Display execution logging stats if available
    if $EXECUTION_LOGGING_ENABLED && [ -f "$EXECUTION_LOG_FILE" ]; then
        local exec_count
        exec_count=$(get_execution_count)
        echo ""
        echo -e "  Execution Log: ${CYAN}$exec_count entries${NC}"
    fi

    echo ""
    echo "  Files:"
    echo "    - prd.json:     Task state (check passes: true/false)"
    echo "    - progress.txt: Iteration learnings"
    echo "    - AGENTS.md:    Discovered patterns"
    if $EXECUTION_LOGGING_ENABLED; then
        echo "    - .claude-loop/execution_log.jsonl: Execution logs"
    fi
    echo ""
    echo "═══════════════════════════════════════════════════════════════"
}

# ============================================================================
# Main Script
# ============================================================================

main() {
    # Parse command line arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            -m|--max-iterations)
                MAX_ITERATIONS="$2"
                shift 2
                ;;
            -p|--prd)
                # Resolve PRD path (supports prds/active/* structure)
                resolve_prd_path "$2"
                shift 2
                ;;
            -a|--agents-dir)
                AGENTS_DIR="$2"
                shift 2
                ;;
            -d|--delay)
                DELAY_SECONDS="$2"
                shift 2
                ;;
            -v|--verbose)
                VERBOSE=true
                shift
                ;;
            --no-agents)
                AGENTS_ENABLED=false
                shift
                ;;
            --no-experience)
                EXPERIENCE_AUGMENTATION_ENABLED=false
                shift
                ;;
            --enable-hooks)
                HOOKS_ENABLED=true
                shift
                ;;
            --enable-learnings)
                LEARNINGS_ENABLED=true
                shift
                ;;
            --list-learnings)
                LIST_LEARNINGS=true
                LIST_LEARNINGS_TAG="${2:-}"
                LIST_LEARNINGS_SINCE="${3:-}"
                shift
                # Shift additional args if provided
                [ -n "$LIST_LEARNINGS_TAG" ] && shift
                [ -n "$LIST_LEARNINGS_SINCE" ] && shift
                ;;
            --rate-learning)
                RATE_LEARNING_ID="$2"
                RATE_LEARNING_ACTION="$3"
                shift 3
                ;;
            --enable-decomposition)
                DECOMPOSITION_ENABLED=true
                shift
                ;;
            --decompose-story)
                DECOMPOSE_STORY_ID="$2"
                shift 2
                ;;
            --auto-decompose)
                AUTO_DECOMPOSE=true
                shift
                ;;
            --enable-structured-output)
                STRUCTURED_OUTPUT_ENABLED=true
                shift
                ;;
            --enable-mcp)
                ENABLE_MCP=true
                shift
                ;;
            --list-mcp-tools)
                LIST_MCP_TOOLS=true
                shift
                ;;
            --enable-multi-provider)
                ENABLE_MULTI_PROVIDER=true
                shift
                ;;
            --cost-report)
                SHOW_COST_REPORT=true
                # Optional: --cost-report 30 for last 30 days
                if [[ -n "$2" ]] && [[ "$2" =~ ^[0-9]+$ ]]; then
                    COST_REPORT_DAYS="$2"
                    shift 2
                else
                    shift
                fi
                ;;
            --enable-delegation)
                ENABLE_DELEGATION=true
                shift
                ;;
            --no-dashboard)
                PROGRESS_DASHBOARD_ENABLED=false
                shift
                ;;
            --compact-dashboard)
                DASHBOARD_COMPACT=true
                shift
                ;;
            --no-progress)
                PROGRESS_INDICATORS_ENABLED=false
                shift
                ;;
            --max-agents)
                MAX_AGENTS_PER_ITERATION="$2"
                shift 2
                ;;
            --agent-tiers)
                ENABLED_TIERS="$2"
                shift 2
                ;;
            --unity)
                UNITY_MODE=true
                shift
                ;;
            --resume)
                RESUME_MODE=true
                shift
                ;;
            --resume-from)
                RESUME_MODE=true
                RESUME_FROM_SESSION="$2"
                shift 2
                ;;
            --parallel)
                PARALLEL_MODE=true
                shift
                ;;
            --max-prds)
                PARALLEL_MAX_PRDS="$2"
                shift 2
                ;;
            --status)
                PARALLEL_MODE_STATUS=true
                shift
                ;;
            --stop)
                PARALLEL_MODE_STOP="$2"
                shift 2
                ;;
            --list-sessions)
                # Source session state and list sessions
                if [ -f "$SESSION_STATE_SCRIPT" ]; then
                    source "$SESSION_STATE_SCRIPT"
                    list_sessions "text"
                    exit 0
                else
                    log_error "Session state script not found: $SESSION_STATE_SCRIPT"
                    exit 1
                fi
                ;;
            --no-session)
                SESSION_STATE_ENABLED=false
                shift
                ;;
            --complexity-threshold)
                COMPLEXITY_THRESHOLD="$2"
                shift 2
                ;;
            --no-adaptive)
                ADAPTIVE_SPLITTING_ENABLED=false
                COMPLEXITY_THRESHOLD=999  # Effectively disable adaptive splitting
                shift
                ;;
            --dynamic)
                DYNAMIC_GOAL="$2"
                shift 2
                ;;
            --dynamic-output)
                DYNAMIC_OUTPUT="$2"
                shift 2
                ;;
            --codebase-analysis)
                CODEBASE_ANALYSIS=true
                shift
                ;;
            brainstorm|--brainstorm)
                BRAINSTORM_MODE=true
                BRAINSTORM_DESCRIPTION="$2"
                shift 2
                ;;
            --list-improvements)
                IMPROVEMENT_MODE="list"
                shift
                ;;
            --review-improvement)
                IMPROVEMENT_MODE="review"
                IMPROVEMENT_TARGET="$2"
                shift 2
                ;;
            --approve-improvement)
                IMPROVEMENT_MODE="approve"
                IMPROVEMENT_TARGET="$2"
                shift 2
                ;;
            --reject-improvement)
                IMPROVEMENT_MODE="reject"
                IMPROVEMENT_TARGET="$2"
                shift 2
                ;;
            --validate-improvement)
                IMPROVEMENT_MODE="validate"
                IMPROVEMENT_TARGET="$2"
                shift 2
                ;;
            --execute-improvement)
                IMPROVEMENT_MODE="execute"
                IMPROVEMENT_TARGET="$2"
                shift 2
                ;;
            --improvement-history)
                IMPROVEMENT_MODE="history"
                shift
                ;;
            --rollback-improvement)
                IMPROVEMENT_MODE="rollback"
                IMPROVEMENT_TARGET="$2"
                shift 2
                ;;
            --notes)
                IMPROVEMENT_NOTES="$2"
                shift 2
                ;;
            --reason)
                IMPROVEMENT_REASON="$2"
                shift 2
                ;;
            --validate)
                IMPROVEMENT_VALIDATE=true
                shift
                ;;
            --force)
                IMPROVEMENT_FORCE=true
                shift
                ;;
            --dry-run)
                IMPROVEMENT_DRY_RUN=true
                shift
                ;;
            --start-daemon)
                DAEMON_MODE="start"
                shift
                ;;
            --stop-daemon)
                DAEMON_MODE="stop"
                shift
                ;;
            --daemon-status)
                DAEMON_MODE="status"
                shift
                ;;
            --validate-classifier)
                # Run classification accuracy tests
                log_info "Running classification accuracy validation..."
                if [ -f ".venv/bin/pytest" ]; then
                    .venv/bin/pytest tests/test_failure_classification.py -v -s
                    exit $?
                elif command -v pytest &> /dev/null; then
                    pytest tests/test_failure_classification.py -v -s
                    exit $?
                else
                    log_error "pytest not found. Install with: pip install pytest"
                    exit 1
                fi
                ;;
            --autonomous)
                AUTONOMOUS_MODE=true
                shift
                ;;
            --disable-autonomous)
                DISABLE_AUTONOMOUS=true
                shift
                ;;
            --autonomous-status)
                # Show autonomous gate status
                if [ -f "$AUTONOMOUS_GATE" ]; then
                    python3 "$AUTONOMOUS_GATE" status
                    exit $?
                else
                    log_error "Autonomous gate not found: $AUTONOMOUS_GATE"
                    exit 1
                fi
                ;;
            --enable-review)
                REVIEW_ENABLED=true
                shift
                ;;
            --reviewers)
                REVIEW_PROVIDERS="$2"
                shift 2
                ;;
            --review-threshold)
                REVIEW_THRESHOLD="$2"
                shift 2
                ;;
            --max-review-cycles)
                MAX_REVIEW_CYCLES="$2"
                shift 2
                ;;
            --provider)
                PRIMARY_PROVIDER="$2"
                shift 2
                ;;
            --model)
                PROVIDER_MODELS="$2"
                shift 2
                ;;
            --list-templates)
                TEMPLATE_MODE="list"
                shift
                ;;
            --show-template)
                TEMPLATE_MODE="show"
                TEMPLATE_NAME="$2"
                shift 2
                ;;
            --template)
                TEMPLATE_MODE="generate"
                TEMPLATE_NAME="$2"
                shift 2
                ;;
            --template-output)
                TEMPLATE_OUTPUT="$2"
                shift 2
                ;;
            --template-var)
                TEMPLATE_VARS+=("$2")
                shift 2
                ;;
            --template-vars)
                TEMPLATE_VARS_FILE="$2"
                shift 2
                ;;
            --workspace)
                WORKSPACE_FOLDERS="$2"
                WORKSPACE_ENABLED=true
                shift 2
                ;;
            --workspace-mode)
                WORKSPACE_MODE="$2"
                shift 2
                ;;
            --disable-workspace-checks)
                WORKSPACE_ENABLED=false
                WORKSPACE_FOLDERS=""
                shift
                ;;
            --safety-level)
                SAFETY_LEVEL="$2"
                shift 2
                ;;
            --safety-dry-run)
                SAFETY_DRY_RUN=true
                shift
                ;;
            --disable-safety)
                SAFETY_ENABLED=false
                SAFETY_LEVEL="yolo"
                shift
                ;;
            --list-skills)
                SKILLS_MODE="list"
                shift
                ;;
            --skill)
                SKILLS_MODE="execute"
                SKILL_NAME="$2"
                shift 2
                ;;
            --skill-arg)
                SKILL_ARGS+=("$2")
                shift 2
                ;;
            quick)
                # Check for subcommands
                case "$2" in
                    history|stats|templates)
                        QUICK_TASK_MODE="$2"
                        shift 2
                        ;;
                    --continue)
                        QUICK_TASK_MODE="execute"
                        QUICK_TASK_CONTINUE=true
                        shift 2
                        ;;
                    *)
                        QUICK_TASK_MODE="execute"
                        QUICK_TASK_DESC="$2"
                        shift 2
                        ;;
                esac

                # Parse additional quick task options
                while [[ $# -gt 0 ]]; do
                    case "$1" in
                        --workspace)
                            QUICK_TASK_WORKSPACE="$2"
                            shift 2
                            ;;
                        --commit)
                            QUICK_TASK_COMMIT=true
                            shift
                            ;;
                        --escalate)
                            QUICK_TASK_ESCALATE=true
                            shift
                            ;;
                        --dry-run)
                            QUICK_TASK_DRY_RUN=true
                            shift
                            ;;
                        --continue)
                            QUICK_TASK_CONTINUE=true
                            shift
                            ;;
                        --template)
                            QUICK_TASK_TEMPLATE="$2"
                            shift 2
                            ;;
                        *)
                            break
                            ;;
                    esac
                done
                ;;
            daemon)
                TASK_DAEMON_CMD="$2"
                shift 2
                # Parse daemon-specific arguments
                case "$TASK_DAEMON_CMD" in
                    start)
                        if [[ $# -gt 0 && "$1" =~ ^[0-9]+$ ]]; then
                            TASK_DAEMON_WORKERS="$1"
                            shift
                        fi
                        ;;
                    submit)
                        TASK_DAEMON_ARG="$1"
                        shift
                        if [[ $# -gt 0 && "$1" =~ ^(high|normal|low)$ ]]; then
                            TASK_DAEMON_PRIORITY="$1"
                            shift
                        fi
                        ;;
                    cancel)
                        TASK_DAEMON_ARG="$1"
                        shift
                        ;;
                    stop|status|queue|pause|resume)
                        # No additional arguments
                        ;;
                    *)
                        log_error "Unknown daemon command: $TASK_DAEMON_CMD"
                        log_info "Available commands: start, stop, status, submit, queue, cancel, pause, resume"
                        exit 1
                        ;;
                esac
                ;;
            dashboard)
                DASHBOARD_CMD="$2"
                shift 2
                # Parse dashboard-specific arguments
                case "$DASHBOARD_CMD" in
                    start|restart)
                        # Parse port and host options
                        while [[ $# -gt 0 ]]; do
                            case "$1" in
                                --port)
                                    DASHBOARD_PORT="$2"
                                    shift 2
                                    ;;
                                --host)
                                    DASHBOARD_HOST="$2"
                                    shift 2
                                    ;;
                                *)
                                    break
                                    ;;
                            esac
                        done
                        ;;
                    stop|status|logs|generate-token)
                        # No additional arguments
                        ;;
                    *)
                        log_error "Unknown dashboard command: $DASHBOARD_CMD"
                        log_info "Available commands: start, stop, restart, status, logs, generate-token"
                        exit 1
                        ;;
                esac
                ;;
            -h|--help)
                show_help
                exit 0
                ;;
            -*)
                log_error "Unknown option: $1"
                show_help
                exit 1
                ;;
            *)
                # Positional argument: treat as feature description (INV-008)
                FEATURE_DESCRIPTION="$1"
                AUTO_GENERATE_PRD=true
                shift
                ;;
        esac
    done

    # Check required dependencies (jq, python3, git, etc.)
    check_dependencies

    # Validate CLI arguments
    validate_cli_arguments

    # Handle autonomous mode commands
    if $DISABLE_AUTONOMOUS; then
        if [ -f "$AUTONOMOUS_GATE" ]; then
            log_info "Disabling autonomous mode..."
            python3 "$AUTONOMOUS_GATE" disable
            exit $?
        else
            log_error "Autonomous gate not found: $AUTONOMOUS_GATE"
            exit 1
        fi
    fi

    # Handle daemon mode first (exits if in daemon mode)
    # Pass --autonomous flag if enabled
    if [ -n "$DAEMON_MODE" ] && $AUTONOMOUS_MODE; then
        export DAEMON_AUTONOMOUS_MODE=true
    fi
    run_daemon_mode || true

    # Handle task daemon mode (US-205)
    run_task_daemon_mode || true

    # Handle dashboard mode (US-207)
    run_dashboard_mode || true

    # Handle template mode (US-002)
    run_template_mode || true

    # Handle skills mode (US-201)
    run_skills_mode || true

    # Handle quick task mode (US-203)
    run_quick_task_mode || true

    # Handle brainstorming mode (US-004)
    run_brainstorm_mode || true

    # Handle improvement management mode first (exits if in improvement mode)
    run_improvement_mode || true

    # ========================================================================
    # Learnings Management Mode (US-002 - Tier 1 Pattern Extraction)
    # ========================================================================

    # Handle --list-learnings
    if $LIST_LEARNINGS; then
        log_info "Listing learnings from $LEARNINGS_FILE"

        if [ ! -f "$LEARNINGS_FILE" ]; then
            log_warn "No learnings file found: $LEARNINGS_FILE"
            exit 0
        fi

        # Build query command
        local query_cmd="jq '.'"

        if [ -n "$LIST_LEARNINGS_TAG" ]; then
            query_cmd="jq 'map(select(.tags | index(\"$LIST_LEARNINGS_TAG\")))'"
        fi

        if [ -n "$LIST_LEARNINGS_SINCE" ]; then
            query_cmd="$query_cmd | jq 'map(select(.timestamp >= \"$LIST_LEARNINGS_SINCE\"))'"
        fi

        # Sort by helpful_count descending
        query_cmd="$query_cmd | jq 'sort_by(-.helpful_count)'"

        # Execute query and display results
        local results
        results=$(eval "$query_cmd" < "$LEARNINGS_FILE")

        local count
        count=$(echo "$results" | jq 'length')

        if [ "$count" -eq 0 ]; then
            log_info "No learnings found matching criteria"
        else
            log_success "Found $count learning(s):"
            echo ""

            # Display as table
            echo "$results" | jq -r '.[] | "\u001b[36m[\(.id[0:8])]\u001b[0m \u001b[33m[\(.helpful_count)⭐]\u001b[0m \u001b[90m[\(.story_id)] [\(.timestamp[0:10])]\u001b[0m\n  \(.lesson)\n  Tags: \(.tags | join(", "))\n"'
        fi

        exit 0
    fi

    # Handle --list-mcp-tools
    if $LIST_MCP_TOOLS; then
        log_info "Listing MCP tools from configured servers"

        # Source MCP bridge
        if [ -f "$MCP_BRIDGE" ]; then
            # Set ENABLE_MCP temporarily for listing
            export ENABLE_MCP=true
            source "$MCP_BRIDGE"

            # Initialize MCP
            if mcp_init; then
                # List tools
                mcp_list_tools
            else
                log_error "MCP initialization failed"
                exit 1
            fi
        else
            log_error "MCP bridge not found: $MCP_BRIDGE"
            exit 1
        fi

        exit 0
    fi

    # Handle --cost-report (US-006)
    if $SHOW_COST_REPORT; then
        log_info "Generating cost analysis report (last $COST_REPORT_DAYS days)"

        # Check if cost report tool exists
        if [ ! -f "$COST_REPORT" ]; then
            log_error "Cost report tool not found: $COST_REPORT"
            log_info "Please ensure US-006 (Multi-Provider LLM) is implemented"
            exit 1
        fi

        # Generate report
        python3 "$COST_REPORT" report --days "$COST_REPORT_DAYS" --verbose

        exit 0
    fi

    # Handle --rate-learning
    if [ -n "$RATE_LEARNING_ID" ]; then
        if [ -z "$RATE_LEARNING_ACTION" ]; then
            log_error "Usage: ./claude-loop.sh --rate-learning <ID> --helpful|--unhelpful"
            exit 1
        fi

        log_info "Rating learning $RATE_LEARNING_ID as $RATE_LEARNING_ACTION"

        learnings_rate "$RATE_LEARNING_ID" "$RATE_LEARNING_ACTION"

        if [ $? -eq 0 ]; then
            log_success "Learning rated successfully"
        else
            log_error "Failed to rate learning"
            exit 1
        fi

        exit 0
    fi

    # ========================================================================
    # Story Decomposition Mode (US-003 - Tier 1 Pattern Extraction)
    # ========================================================================

    # Handle --decompose-story
    if [ -n "$DECOMPOSE_STORY_ID" ]; then
        log_info "Decomposing story: $DECOMPOSE_STORY_ID"

        # Enable decomposition if not already enabled
        if ! $DECOMPOSITION_ENABLED; then
            log_warn "Decomposition not enabled, enabling it for this command"
            DECOMPOSITION_ENABLED=true
        fi

        # Check if PRD file exists
        if [ ! -f "$PRD_FILE" ]; then
            log_error "PRD file not found: $PRD_FILE"
            exit 1
        fi

        # Decompose the story
        if decompose_story "$DECOMPOSE_STORY_ID"; then
            log_success "Story decomposed successfully"
            log_info "Check updated PRD: $PRD_FILE"
            exit 0
        else
            log_error "Failed to decompose story"
            exit 1
        fi
    fi

    # ========================================================================
    # Parallel PRD Execution Mode (NEW - PAR-007)
    # ========================================================================
    if $PARALLEL_MODE || $PARALLEL_MODE_STATUS || [ -n "$PARALLEL_MODE_STOP" ]; then
        if [ ! -f "$PRD_COORDINATOR" ]; then
            log_error "PRD coordinator not found: $PRD_COORDINATOR"
            log_info "Parallel mode requires lib/prd-coordinator.sh"
            exit 1
        fi

        # Source coordinator
        source "$PRD_COORDINATOR"
        init_coordinator

        # Handle --status
        if $PARALLEL_MODE_STATUS; then
            coord_log_info "Coordinator Status:"
            [ -f "$COORDINATOR_REGISTRY" ] && jq '.' "$COORDINATOR_REGISTRY" || coord_log_warn "No active session"
            exit 0
        fi

        # Handle --stop
        if [ -n "$PARALLEL_MODE_STOP" ]; then
            stop_prd_worker "$PARALLEL_MODE_STOP"
            exit $?
        fi

        # Parallel mode - launch PRDs
        coord_log_info "Parallel PRD Execution Mode"
        coord_log_info "Max parallel PRDs: $PARALLEL_MAX_PRDS"

        # Find active PRDs
        local active_prds=()
        [ -d "prds/active" ] && for prd_dir in prds/active/*; do
            [ -d "$prd_dir" ] && [ -f "$prd_dir/prd.json" ] && active_prds+=("$(basename "$prd_dir")")
        done

        [ ${#active_prds[@]} -eq 0 ] && { coord_log_warn "No PRDs in prds/active/"; exit 1; }

        # Launch workers
        local launched=0
        for prd_id in "${active_prds[@]}"; do
            can_start_prd && launch_prd_worker "$prd_id" "prds/active/$prd_id" && ((launched++))
        done

        coord_log_success "Launched $launched worker(s). Use --status to monitor."

        # Monitor workers
        while [ "$(get_active_prd_count)" -gt 0 ]; do
            for prd_id in $(list_active_prds); do
                is_worker_alive "$prd_id" || deregister_prd "$prd_id" "completed"
            done
            sleep 5
        done

        coord_log_success "All workers completed"
        exit 0
    fi

    echo ""
    echo "═══════════════════════════════════════════════════════════════"
    echo "             CLAUDE-LOOP - Autonomous Feature Builder"
    echo "═══════════════════════════════════════════════════════════════"
    echo ""

    # Pre-flight checks
    log_info "Running pre-flight checks..."
    check_dependencies
    check_git_repo

    # Handle single-command entry point (INV-008)
    # If a feature description was provided, auto-generate PRD
    if $AUTO_GENERATE_PRD && [ -n "$FEATURE_DESCRIPTION" ]; then
        log_info "Single-command entry point detected (INV-008)"
        generate_prd_from_description "$FEATURE_DESCRIPTION"
    fi

    # Handle dynamic PRD generation (US-004)
    # If --dynamic flag was provided, generate PRD from goal
    if [ -n "$DYNAMIC_GOAL" ]; then
        log_info "Dynamic PRD generation detected (US-004)"
        generate_prd_dynamic "$DYNAMIC_GOAL" "$DYNAMIC_OUTPUT" "$CODEBASE_ANALYSIS"
    fi

    # Handle brainstorming mode (US-004: Interactive Design Refinement)
    # If --brainstorm flag was provided, invoke brainstorming workflow
    if [ "$BRAINSTORM_MODE" = true ]; then
        log_info "Brainstorming mode detected (US-004)"
        if [ -z "$BRAINSTORM_DESCRIPTION" ]; then
            log_error "Brainstorming description required. Usage: ./claude-loop.sh brainstorm '<description>'"
            exit 1
        fi

        # Invoke brainstorming handler
        if [ -f "${SCRIPT_DIR}/lib/brainstorming-handler.sh" ]; then
            "${SCRIPT_DIR}/lib/brainstorming-handler.sh" "$BRAINSTORM_DESCRIPTION"
            exit 0
        else
            log_error "Brainstorming handler not found: ${SCRIPT_DIR}/lib/brainstorming-handler.sh"
            exit 1
        fi
    fi

    # If PRD_FILE is default (./prd.json) and doesn't exist, try auto-detection
    if [ "$PRD_FILE" = "./prd.json" ] && [ ! -f "$PRD_FILE" ]; then
        log_info "Default prd.json not found, checking prds/active/..."
        if ! auto_detect_active_prd; then
            # Auto-detection failed, let check_prd_exists show the error
            :
        fi
    fi

    check_prd_exists
    check_prompt_exists
    check_agents_dir
    check_execution_logger
    check_prompt_augmenter
    check_session_state
    check_workspace
    check_safety_checker

    # Source progress indicators (US-001)
    if $PROGRESS_INDICATORS_ENABLED && [ -f "$PROGRESS_INDICATORS" ]; then
        source "$PROGRESS_INDICATORS"
        init_progress "$PRD_FILE"
    fi

    # Get branch from PRD and handle archiving
    local target_branch
    target_branch=$(get_branch_from_prd)
    archive_previous_run "$target_branch"

    # Ensure we're on the correct branch
    ensure_correct_branch "$target_branch"

    # Initialize state files
    initialize_progress_file
    initialize_agents_file

    # Display initial status
    local project_name
    project_name=$(get_project_name)
    local total_stories
    total_stories=$(get_total_stories_count)
    local incomplete_stories
    incomplete_stories=$(get_incomplete_stories_count)

    # Display auto-detection summary for all runs (INV-011)
    # Shows complexity, track, phases, and quality gates
    display_auto_detection_summary

    log_info "Project: $project_name"
    log_info "Branch: $target_branch"
    log_info "Stories: $incomplete_stories incomplete out of $total_stories total"
    log_info "Max iterations: $MAX_ITERATIONS"

    # Display provider information (LLM-013)
    log_info "Primary Provider: $PRIMARY_PROVIDER"
    if [ "$PRIMARY_PROVIDER" != "claude" ]; then
        log_warn "═══════════════════════════════════════════════════════════════"
        log_warn "WARNING: Using non-Claude provider ($PRIMARY_PROVIDER)"
        log_warn "Non-Claude providers have reduced capabilities:"
        log_warn "  - Limited tool availability (only read_file, write_file, run_bash, git_command)"
        log_warn "  - No access to Claude Code's advanced features"
        log_warn "  - May have lower success rates for complex tasks"
        log_warn "  - Recommended for testing and experimentation only"
        log_warn "═══════════════════════════════════════════════════════════════"
        if [ -n "$PROVIDER_MODELS" ]; then
            log_info "Model Override: $PROVIDER_MODELS"
        fi
    fi

    if $AGENTS_ENABLED; then
        log_agent "Agents: Enabled (tiers: $ENABLED_TIERS, max: $MAX_AGENTS_PER_ITERATION)"
    fi
    if $UNITY_MODE; then
        log_info "Unity Mode: Enabled (Quest 3 XR development)"
        if [ -f "$UNITY_ORCHESTRATOR" ]; then
            log_info "Unity Orchestrator: $UNITY_ORCHESTRATOR"
        else
            log_warn "Unity Orchestrator not found: $UNITY_ORCHESTRATOR"
        fi
    fi
    echo ""

    # Check if already complete
    if [ "$incomplete_stories" -eq 0 ]; then
        log_success "All stories already complete!"
        # Handle PRD completion (update MANIFEST.yaml, move to completed/)
        handle_prd_completion
        # Cleanup checkpoints on successful completion
        local workflow_id
        workflow_id=$(get_workflow_id)
        cleanup_checkpoints "$workflow_id" false
        # Finish session state
        finish_session
        print_summary
        exit 0
    fi

    # Set up cleanup trap for unexpected exits (US-003)
    cleanup_on_exit() {
        if $SESSION_STATE_ENABLED; then
            # Don't mark clean shutdown on trap - this indicates abnormal exit
            # The absence of clean_shutdown marker will trigger crash recovery
            :
        fi
    }
    trap cleanup_on_exit EXIT INT TERM

    # Initialize or resume session state (INV-007)
    local resume_iteration=0
    if $SESSION_STATE_ENABLED; then
        resume_iteration=$(init_or_resume_session)
        if [ "$resume_iteration" -gt 0 ]; then
            log_info "Session will continue from iteration $resume_iteration"
        else
            echo -e "${CYAN}[INFO]${NC} You can close this. Progress auto-saves."
        fi
    fi

    # Initialize MCP if enabled (US-005 - Phase 2)
    if $ENABLE_MCP; then
        log_info "Initializing MCP integration..."
        if [ -f "$MCP_BRIDGE" ]; then
            source "$MCP_BRIDGE"
            if mcp_init; then
                log_success "MCP initialized successfully"
            else
                log_warn "MCP initialization failed, continuing without MCP"
                ENABLE_MCP=false
            fi
        else
            log_warn "MCP bridge not found: $MCP_BRIDGE"
            ENABLE_MCP=false
        fi
    fi

    # Check for resume from checkpoint (legacy)
    local resume_step_index=0
    if $RESUME_MODE && [ "$resume_iteration" -eq 0 ]; then
        resume_step_index=$(check_resume_from_checkpoint) || resume_step_index=0
    fi

    # Run solutioning generator for complex projects (Level >= 3) (INV-011)
    # Generates architecture.md and ADR templates before implementation
    if [ "$resume_iteration" -eq 0 ] && [ "$resume_step_index" -eq 0 ]; then
        # Only run solutioning for fresh starts (not resumes)
        if should_run_solutioning; then
            run_solutioning_generator
            display_detected_adrs
        fi
    fi

    # Main iteration loop - start from resume point if available
    local iteration=1
    if [ "$resume_iteration" -gt 0 ]; then
        iteration=$((resume_iteration + 1))  # Continue from next iteration
    elif [ "$resume_step_index" -gt 0 ]; then
        iteration=$((resume_step_index + 1))
    fi
    local all_complete=false
    local workflow_id
    workflow_id=$(get_workflow_id)

    # Display initial progress dashboard
    display_progress_dashboard

    while [ $iteration -le $MAX_ITERATIONS ]; do
        # Check remaining stories
        incomplete_stories=$(get_incomplete_stories_count)
        if [ "$incomplete_stories" -eq 0 ]; then
            all_complete=true
            break
        fi

        log_iteration "$iteration" "Stories remaining: $incomplete_stories"

        # Get current story for checkpoint
        local story_info
        story_info=$(get_next_story)
        local story_id
        story_id=$(echo "$story_info" | cut -d'|' -f1)

        # Check if story should be decomposed (US-003 - Tier 1 Pattern Extraction)
        if $DECOMPOSITION_ENABLED && [ -n "$story_id" ] && [ "$story_id" != "null" ]; then
            if complexity_check "$story_id"; then
                log_info "Story $story_id exceeds complexity thresholds"
                log_info "Attempting automatic decomposition..."

                if decompose_story "$story_id"; then
                    log_success "Story decomposed successfully. Restarting iteration to pick up substories."
                    # Skip this iteration and get the next story (which will be the first substory)
                    continue
                else
                    log_warn "Decomposition failed or was rejected. Proceeding with original story."
                fi
            fi
        fi

        # Display progress with current story running
        display_progress_compact "$story_id"

        # Run the iteration
        if run_iteration $iteration; then
            all_complete=true
            log_success "All stories complete!"

            # Execute on_complete hooks (US-001)
            execute_hooks "on_complete" "$story_id" "$iteration" "$(pwd)" "$(git branch --show-current 2>/dev/null || echo "")" "${CURRENT_PHASE:-implementation}"

            # Handle PRD completion (update MANIFEST.yaml, move to completed/)
            handle_prd_completion

            # Cleanup checkpoints on successful completion
            cleanup_checkpoints "$workflow_id" false

            # Finish session state (INV-007)
            finish_session

            break
        fi

        # Save checkpoint after each successful iteration (legacy)
        local context
        context=$(printf '{"story_id": "%s", "iteration": %d, "incomplete_stories": %d}' "$story_id" "$iteration" "$incomplete_stories")
        save_checkpoint "$workflow_id" "$story_id" "$iteration" "$context" > /dev/null

        # Save session state after each iteration (INV-007)
        save_story_progress "$story_id" "$iteration" "$CURRENT_PHASE"

        # Display updated progress after iteration
        display_progress_compact

        # Delay between iterations
        if [ $iteration -lt $MAX_ITERATIONS ]; then
            log_info "Waiting ${DELAY_SECONDS}s before next iteration..."
            sleep "$DELAY_SECONDS"
        fi

        ((iteration++))
    done

    # Final summary with full dashboard
    display_progress_dashboard
    print_summary

    # Display completion summary (INV-010) for successful runs
    if $all_complete; then
        display_completion_summary
        log_success "Feature implementation complete!"
        exit 0
    else
        log_warn "Max iterations ($MAX_ITERATIONS) reached. Some stories may be incomplete."
        log_info "You can continue by running: ./claude-loop.sh --resume"
        exit 1
    fi
}

# Run main function
main "$@"
