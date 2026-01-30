#!/bin/bash
#
# gap-analysis-daemon.sh - Background Gap Analysis Daemon for claude-loop
#
# Runs the capability gap analysis pipeline in the background without blocking
# active development work. Periodically analyzes execution logs to discover
# patterns, perform root cause analysis, and generate improvement PRDs.
#
# Features:
# - Periodic analysis (configurable interval)
# - Triggers on time interval OR new log entry count
# - Lockfile to prevent multiple daemon instances
# - Graceful shutdown on SIGTERM/SIGINT
# - Status tracking in daemon_status.json
# - Activity logging to daemon.log
#
# Usage:
#   ./lib/gap-analysis-daemon.sh start          # Start daemon in background
#   ./lib/gap-analysis-daemon.sh stop           # Stop running daemon
#   ./lib/gap-analysis-daemon.sh status         # Check daemon status
#   ./lib/gap-analysis-daemon.sh run-once       # Run analysis once (foreground)
#   ./lib/gap-analysis-daemon.sh help           # Show help
#
# Configuration:
#   DAEMON_INTERVAL_SECONDS - Analysis interval (default: 3600 = 1 hour)
#   DAEMON_LOG_THRESHOLD - New log entries to trigger (default: 10)
#   DAEMON_AUTO_GENERATE_PRD - Auto-generate PRDs for new gaps (default: true)
#

set -uo pipefail

# ============================================================================
# Configuration
# ============================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
CLAUDE_LOOP_DIR="${PROJECT_ROOT}/.claude-loop"

# Daemon configuration
DAEMON_INTERVAL_SECONDS="${DAEMON_INTERVAL_SECONDS:-3600}"  # 1 hour
DAEMON_LOG_THRESHOLD="${DAEMON_LOG_THRESHOLD:-10}"  # 10 new entries
DAEMON_AUTO_GENERATE_PRD="${DAEMON_AUTO_GENERATE_PRD:-true}"

# File paths
LOCKFILE="${CLAUDE_LOOP_DIR}/daemon.lock"
PID_FILE="${CLAUDE_LOOP_DIR}/daemon.pid"
STATUS_FILE="${CLAUDE_LOOP_DIR}/daemon_status.json"
LOG_FILE="${CLAUDE_LOOP_DIR}/daemon.log"
EXECUTION_LOG="${CLAUDE_LOOP_DIR}/execution_log.jsonl"
LAST_ANALYZED_FILE="${CLAUDE_LOOP_DIR}/daemon_last_analyzed.txt"

# Python modules
FAILURE_CLASSIFIER="${SCRIPT_DIR}/failure-classifier.py"
PATTERN_CLUSTERER="${SCRIPT_DIR}/pattern-clusterer.py"
ROOT_CAUSE_ANALYZER="${SCRIPT_DIR}/root-cause-analyzer.py"
GAP_GENERALIZER="${SCRIPT_DIR}/gap-generalizer.py"
IMPROVEMENT_GENERATOR="${SCRIPT_DIR}/improvement-prd-generator.py"
AUTONOMOUS_GATE="${SCRIPT_DIR}/autonomous-gate.py"

# Autonomous mode (can be set via DAEMON_AUTONOMOUS_MODE env var)
DAEMON_AUTONOMOUS_MODE="${DAEMON_AUTONOMOUS_MODE:-false}"

# Colors for output
CYAN='\033[0;36m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

# Daemon state
DAEMON_RUNNING=false
SHUTDOWN_REQUESTED=false

# ============================================================================
# Helper Functions
# ============================================================================

daemon_log() {
    local level="$1"
    local message="$2"
    local timestamp
    timestamp=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
    echo "${timestamp} [${level}] ${message}" >> "$LOG_FILE"

    # Also output to console if not running as daemon
    if [ "$DAEMON_RUNNING" != "true" ]; then
        case "$level" in
            INFO)  echo -e "${CYAN}[DAEMON]${NC} $message" ;;
            WARN)  echo -e "${YELLOW}[DAEMON]${NC} $message" ;;
            ERROR) echo -e "${RED}[DAEMON]${NC} $message" ;;
            *)     echo "[DAEMON] $message" ;;
        esac
    fi
}

ensure_directories() {
    mkdir -p "$CLAUDE_LOOP_DIR"
    touch "$LOG_FILE"
}

get_timestamp() {
    date -u +"%Y-%m-%dT%H:%M:%SZ"
}

get_timestamp_ms() {
    if [[ "$OSTYPE" == "darwin"* ]]; then
        perl -MTime::HiRes=time -e 'printf "%.0f\n", time * 1000'
    else
        echo $(($(date +%s%N) / 1000000))
    fi
}

# ============================================================================
# Status Management
# ============================================================================

write_status() {
    local status="$1"
    local message="${2:-}"
    local timestamp
    timestamp=$(get_timestamp)

    local last_run="${3:-}"
    local next_run="${4:-}"
    local patterns_found="${5:-0}"
    local gaps_found="${6:-0}"
    local prds_generated="${7:-0}"

    cat > "$STATUS_FILE" << EOF
{
    "status": "$status",
    "message": "$message",
    "timestamp": "$timestamp",
    "pid": ${BASHPID:-$$},
    "config": {
        "interval_seconds": $DAEMON_INTERVAL_SECONDS,
        "log_threshold": $DAEMON_LOG_THRESHOLD,
        "auto_generate_prd": $DAEMON_AUTO_GENERATE_PRD
    },
    "last_run": "$last_run",
    "next_run": "$next_run",
    "stats": {
        "patterns_found": $patterns_found,
        "gaps_found": $gaps_found,
        "prds_generated": $prds_generated
    }
}
EOF
}

read_status() {
    if [ -f "$STATUS_FILE" ]; then
        cat "$STATUS_FILE"
    else
        echo '{"status": "not_running", "message": "Daemon has never been started"}'
    fi
}

# ============================================================================
# Lock Management
# ============================================================================

acquire_lock() {
    # Use flock if available (Linux), otherwise use mkdir
    if command -v flock &> /dev/null; then
        exec 200>"$LOCKFILE"
        if ! flock -n 200; then
            return 1
        fi
    else
        # macOS fallback using mkdir
        if ! mkdir "$LOCKFILE" 2>/dev/null; then
            # Check if lock is stale
            if [ -f "$PID_FILE" ]; then
                local old_pid
                old_pid=$(cat "$PID_FILE")
                if ! kill -0 "$old_pid" 2>/dev/null; then
                    # Stale lock, remove and retry
                    rm -rf "$LOCKFILE"
                    rm -f "$PID_FILE"
                    if ! mkdir "$LOCKFILE" 2>/dev/null; then
                        return 1
                    fi
                else
                    return 1
                fi
            else
                return 1
            fi
        fi
    fi

    # Write PID file
    echo $$ > "$PID_FILE"
    return 0
}

release_lock() {
    rm -f "$PID_FILE"

    if command -v flock &> /dev/null; then
        exec 200>&-
        rm -f "$LOCKFILE"
    else
        rm -rf "$LOCKFILE"
    fi
}

check_running() {
    if [ -f "$PID_FILE" ]; then
        local pid
        pid=$(cat "$PID_FILE")
        if kill -0 "$pid" 2>/dev/null; then
            echo "$pid"
            return 0
        fi
    fi
    return 1
}

# ============================================================================
# Log Analysis
# ============================================================================

get_log_count() {
    if [ -f "$EXECUTION_LOG" ]; then
        wc -l < "$EXECUTION_LOG" | tr -d ' '
    else
        echo "0"
    fi
}

get_last_analyzed_count() {
    if [ -f "$LAST_ANALYZED_FILE" ]; then
        cat "$LAST_ANALYZED_FILE"
    else
        echo "0"
    fi
}

save_last_analyzed_count() {
    echo "$1" > "$LAST_ANALYZED_FILE"
}

should_run_analysis() {
    local current_count
    local last_count

    current_count=$(get_log_count)
    last_count=$(get_last_analyzed_count)

    local new_entries=$((current_count - last_count))

    if [ "$new_entries" -ge "$DAEMON_LOG_THRESHOLD" ]; then
        daemon_log "INFO" "Triggering analysis: $new_entries new log entries (threshold: $DAEMON_LOG_THRESHOLD)"
        return 0
    fi

    return 1
}

# ============================================================================
# Analysis Pipeline
# ============================================================================

run_analysis_pipeline() {
    local start_time
    start_time=$(get_timestamp_ms)

    local patterns_found=0
    local gaps_found=0
    local prds_generated=0

    daemon_log "INFO" "Starting analysis pipeline..."

    # Step 1: Cluster failures into patterns
    daemon_log "INFO" "Step 1/4: Clustering failures..."
    local cluster_output
    if cluster_output=$(python3 "$PATTERN_CLUSTERER" analyze --json 2>&1); then
        patterns_found=$(echo "$cluster_output" | jq -r '.total_patterns // 0')
        daemon_log "INFO" "Found $patterns_found patterns"
    else
        daemon_log "WARN" "Pattern clustering failed: $cluster_output"
    fi

    if [ "$patterns_found" -eq 0 ]; then
        daemon_log "INFO" "No patterns found, skipping further analysis"
        save_last_analyzed_count "$(get_log_count)"
        return 0
    fi

    # Step 2: Batch analyze root causes
    daemon_log "INFO" "Step 2/4: Analyzing root causes..."
    local rca_output
    if rca_output=$(python3 "$ROOT_CAUSE_ANALYZER" batch-analyze --no-llm 2>&1); then
        daemon_log "INFO" "Root cause analysis complete"
    else
        daemon_log "WARN" "Root cause analysis had issues: $rca_output"
    fi

    # Step 3: Generalize to capability gaps
    daemon_log "INFO" "Step 3/4: Generalizing capability gaps..."
    local gap_output
    if gap_output=$(python3 "$GAP_GENERALIZER" batch-generalize --json 2>&1); then
        gaps_found=$(echo "$gap_output" | jq -r 'length // 0' 2>/dev/null || echo "0")
        daemon_log "INFO" "Generalized to $gaps_found capability gaps"
    else
        daemon_log "WARN" "Gap generalization had issues: $gap_output"
    fi

    # Step 4: Generate PRDs for new gaps (if enabled)
    if [ "$DAEMON_AUTO_GENERATE_PRD" = "true" ] && [ "$gaps_found" -gt 0 ]; then
        daemon_log "INFO" "Step 4/4: Generating improvement PRDs..."

        # Get list of active gaps
        local gap_list
        gap_list=$(python3 "$GAP_GENERALIZER" list --json 2>&1)

        if [ -n "$gap_list" ]; then
            # Get existing PRD gap IDs to avoid duplicates
            local existing_prd_gaps
            existing_prd_gaps=$(python3 "$IMPROVEMENT_GENERATOR" list --json 2>&1 | jq -r '.[].gap_id // empty' 2>/dev/null | sort -u)

            # Generate PRDs for new gaps
            echo "$gap_list" | jq -r '.[].gap_id // empty' 2>/dev/null | while read -r gap_id; do
                if [ -n "$gap_id" ]; then
                    # Check if PRD already exists for this gap
                    if echo "$existing_prd_gaps" | grep -q "^${gap_id}$"; then
                        daemon_log "INFO" "PRD already exists for gap $gap_id, skipping"
                        continue
                    fi

                    daemon_log "INFO" "Generating PRD for gap: $gap_id"
                    if python3 "$IMPROVEMENT_GENERATOR" generate "$gap_id" --no-save &>/dev/null; then
                        # Actually save it
                        if python3 "$IMPROVEMENT_GENERATOR" generate "$gap_id" 2>&1 >/dev/null; then
                            prds_generated=$((prds_generated + 1))
                            daemon_log "INFO" "Generated PRD for gap $gap_id"

                            # Autonomous approval if enabled
                            if [ "$DAEMON_AUTONOMOUS_MODE" = "true" ] && [ -f "$AUTONOMOUS_GATE" ]; then
                                local prd_name
                                prd_name="improve-${gap_id}"
                                daemon_log "INFO" "Attempting autonomous approval for: $prd_name"

                                local approval_result
                                if approval_result=$(python3 "$AUTONOMOUS_GATE" approve "$prd_name" --json 2>&1); then
                                    local approved
                                    approved=$(echo "$approval_result" | jq -r '.approved // false')
                                    local reason
                                    reason=$(echo "$approval_result" | jq -r '.reason // "unknown"')

                                    if [ "$approved" = "true" ]; then
                                        daemon_log "INFO" "PRD auto-approved: $prd_name"
                                    else
                                        daemon_log "INFO" "PRD requires manual approval: $prd_name ($reason)"
                                    fi
                                else
                                    daemon_log "WARN" "Failed to check autonomous approval for $prd_name"
                                fi
                            fi
                        fi
                    else
                        daemon_log "WARN" "Failed to generate PRD for gap $gap_id"
                    fi
                fi
            done
        fi
    else
        daemon_log "INFO" "Step 4/4: Skipping PRD generation (disabled or no new gaps)"
    fi

    # Update last analyzed count
    save_last_analyzed_count "$(get_log_count)"

    # Calculate duration
    local end_time
    end_time=$(get_timestamp_ms)
    local duration_ms=$((end_time - start_time))

    daemon_log "INFO" "Analysis complete in ${duration_ms}ms: patterns=$patterns_found, gaps=$gaps_found, prds=$prds_generated"

    # Return values via global variables (bash limitation)
    ANALYSIS_PATTERNS_FOUND=$patterns_found
    ANALYSIS_GAPS_FOUND=$gaps_found
    ANALYSIS_PRDS_GENERATED=$prds_generated
}

# ============================================================================
# Signal Handlers
# ============================================================================

handle_shutdown() {
    daemon_log "INFO" "Shutdown signal received, cleaning up..."
    SHUTDOWN_REQUESTED=true
    write_status "stopping" "Shutdown requested"
}

setup_signal_handlers() {
    trap handle_shutdown SIGTERM SIGINT SIGHUP
}

# ============================================================================
# Daemon Operations
# ============================================================================

start_daemon() {
    ensure_directories

    # Check if already running
    local running_pid
    if running_pid=$(check_running); then
        echo -e "${YELLOW}Daemon is already running with PID $running_pid${NC}"
        return 1
    fi

    echo -e "${CYAN}Starting gap analysis daemon...${NC}"

    # Fork to background
    nohup "$0" run-daemon >> "$LOG_FILE" 2>&1 &
    local daemon_pid=$!

    # Wait briefly to check if it started
    sleep 1

    if kill -0 $daemon_pid 2>/dev/null; then
        echo -e "${GREEN}Daemon started with PID $daemon_pid${NC}"
        echo "Log file: $LOG_FILE"
        echo "Status file: $STATUS_FILE"
        return 0
    else
        echo -e "${RED}Failed to start daemon${NC}"
        return 1
    fi
}

run_daemon() {
    ensure_directories

    # Acquire lock
    if ! acquire_lock; then
        daemon_log "ERROR" "Cannot acquire lock - another daemon may be running"
        exit 1
    fi

    DAEMON_RUNNING=true
    setup_signal_handlers

    daemon_log "INFO" "Daemon started (PID: $$)"
    daemon_log "INFO" "Configuration: interval=${DAEMON_INTERVAL_SECONDS}s, threshold=${DAEMON_LOG_THRESHOLD}, auto_prd=${DAEMON_AUTO_GENERATE_PRD}"

    local last_run=""
    local next_run=""
    local total_patterns=0
    local total_gaps=0
    local total_prds=0

    # Main daemon loop
    while [ "$SHUTDOWN_REQUESTED" != "true" ]; do
        # Calculate next run time
        next_run=$(date -u -v+${DAEMON_INTERVAL_SECONDS}S +"%Y-%m-%dT%H:%M:%SZ" 2>/dev/null || date -u -d "+${DAEMON_INTERVAL_SECONDS} seconds" +"%Y-%m-%dT%H:%M:%SZ")

        write_status "running" "Waiting for next analysis cycle" "$last_run" "$next_run" "$total_patterns" "$total_gaps" "$total_prds"

        # Sleep loop with checks
        local sleep_counter=0
        while [ $sleep_counter -lt "$DAEMON_INTERVAL_SECONDS" ] && [ "$SHUTDOWN_REQUESTED" != "true" ]; do
            sleep 10
            sleep_counter=$((sleep_counter + 10))

            # Check if we should run based on log count
            if should_run_analysis; then
                break
            fi
        done

        if [ "$SHUTDOWN_REQUESTED" = "true" ]; then
            break
        fi

        # Run analysis
        write_status "analyzing" "Running analysis pipeline" "$last_run" "" "$total_patterns" "$total_gaps" "$total_prds"

        ANALYSIS_PATTERNS_FOUND=0
        ANALYSIS_GAPS_FOUND=0
        ANALYSIS_PRDS_GENERATED=0

        run_analysis_pipeline

        last_run=$(get_timestamp)
        total_patterns=$((total_patterns + ANALYSIS_PATTERNS_FOUND))
        total_gaps=$((total_gaps + ANALYSIS_GAPS_FOUND))
        total_prds=$((total_prds + ANALYSIS_PRDS_GENERATED))
    done

    # Cleanup
    daemon_log "INFO" "Daemon shutting down"
    write_status "stopped" "Daemon stopped gracefully" "$last_run" "" "$total_patterns" "$total_gaps" "$total_prds"
    release_lock

    daemon_log "INFO" "Daemon stopped"
}

stop_daemon() {
    local running_pid
    if running_pid=$(check_running); then
        echo -e "${CYAN}Stopping daemon (PID $running_pid)...${NC}"

        # Send SIGTERM for graceful shutdown
        kill -TERM "$running_pid" 2>/dev/null

        # Wait for shutdown (max 10 seconds)
        local wait_count=0
        while [ $wait_count -lt 10 ]; do
            if ! kill -0 "$running_pid" 2>/dev/null; then
                echo -e "${GREEN}Daemon stopped${NC}"
                return 0
            fi
            sleep 1
            wait_count=$((wait_count + 1))
        done

        # Force kill if still running
        if kill -0 "$running_pid" 2>/dev/null; then
            echo -e "${YELLOW}Force killing daemon...${NC}"
            kill -KILL "$running_pid" 2>/dev/null
            release_lock
        fi

        echo -e "${GREEN}Daemon stopped${NC}"
        return 0
    else
        echo -e "${YELLOW}Daemon is not running${NC}"
        return 1
    fi
}

show_status() {
    local status_json
    status_json=$(read_status)

    local status
    status=$(echo "$status_json" | jq -r '.status // "unknown"')

    echo -e "${CYAN}=== Gap Analysis Daemon Status ===${NC}"
    echo ""

    case "$status" in
        running|analyzing)
            local pid
            pid=$(echo "$status_json" | jq -r '.pid // "unknown"')
            echo -e "Status: ${GREEN}$status${NC}"
            echo "PID: $pid"
            ;;
        stopped)
            echo -e "Status: ${YELLOW}$status${NC}"
            ;;
        *)
            echo -e "Status: ${RED}not_running${NC}"
            ;;
    esac

    echo ""
    echo "Configuration:"
    echo "  Interval: $(echo "$status_json" | jq -r '.config.interval_seconds // 3600')s"
    echo "  Log threshold: $(echo "$status_json" | jq -r '.config.log_threshold // 10') entries"
    echo "  Auto PRD: $(echo "$status_json" | jq -r '.config.auto_generate_prd // true')"
    echo "  Autonomous Mode: $DAEMON_AUTONOMOUS_MODE"

    echo ""
    echo "Statistics:"
    echo "  Last run: $(echo "$status_json" | jq -r '.last_run // "never"')"
    echo "  Next run: $(echo "$status_json" | jq -r '.next_run // "N/A"')"
    echo "  Patterns found: $(echo "$status_json" | jq -r '.stats.patterns_found // 0')"
    echo "  Gaps found: $(echo "$status_json" | jq -r '.stats.gaps_found // 0')"
    echo "  PRDs generated: $(echo "$status_json" | jq -r '.stats.prds_generated // 0')"

    echo ""
    echo "Files:"
    echo "  Log: $LOG_FILE"
    echo "  Status: $STATUS_FILE"

    # Check actual running status
    if running_pid=$(check_running); then
        echo ""
        echo -e "${GREEN}Daemon is running (PID: $running_pid)${NC}"
    else
        if [ "$status" = "running" ] || [ "$status" = "analyzing" ]; then
            echo ""
            echo -e "${YELLOW}Warning: Status file shows running but process not found${NC}"
        fi
    fi
}

run_once() {
    ensure_directories

    echo -e "${CYAN}Running gap analysis pipeline (foreground)...${NC}"

    ANALYSIS_PATTERNS_FOUND=0
    ANALYSIS_GAPS_FOUND=0
    ANALYSIS_PRDS_GENERATED=0

    run_analysis_pipeline

    echo ""
    echo -e "${GREEN}Analysis complete:${NC}"
    echo "  Patterns found: $ANALYSIS_PATTERNS_FOUND"
    echo "  Gaps found: $ANALYSIS_GAPS_FOUND"
    echo "  PRDs generated: $ANALYSIS_PRDS_GENERATED"
}

show_help() {
    cat << EOF
gap-analysis-daemon.sh - Background Gap Analysis Daemon

USAGE:
    ./lib/gap-analysis-daemon.sh <command> [options]

COMMANDS:
    start       Start the daemon in background
    stop        Stop the running daemon
    status      Show daemon status
    run-once    Run analysis once (foreground, no daemon)
    run-daemon  Internal: run daemon loop (used by start)
    help        Show this help message

CONFIGURATION (environment variables):
    DAEMON_INTERVAL_SECONDS   Analysis interval (default: 3600 = 1 hour)
    DAEMON_LOG_THRESHOLD      New log entries to trigger (default: 10)
    DAEMON_AUTO_GENERATE_PRD  Auto-generate PRDs for new gaps (default: true)

EXAMPLES:
    # Start daemon with defaults (1 hour interval)
    ./lib/gap-analysis-daemon.sh start

    # Start with custom interval (30 minutes)
    DAEMON_INTERVAL_SECONDS=1800 ./lib/gap-analysis-daemon.sh start

    # Run analysis once without starting daemon
    ./lib/gap-analysis-daemon.sh run-once

    # Check daemon status
    ./lib/gap-analysis-daemon.sh status

    # Stop daemon
    ./lib/gap-analysis-daemon.sh stop

FILES:
    .claude-loop/daemon.log          - Daemon activity log
    .claude-loop/daemon_status.json  - Current status
    .claude-loop/daemon.pid          - Process ID file
    .claude-loop/daemon.lock         - Lock file/directory

ANALYSIS PIPELINE:
    1. Pattern Clustering     - Group similar failures
    2. Root Cause Analysis    - 5-Whys decomposition (heuristic mode)
    3. Gap Generalization     - Map to capability categories
    4. PRD Generation         - Create improvement PRDs

EOF
}

# ============================================================================
# Main Entry Point
# ============================================================================

main() {
    local command="${1:-help}"

    case "$command" in
        start)
            start_daemon
            ;;
        stop)
            stop_daemon
            ;;
        status)
            show_status
            ;;
        run-once)
            run_once
            ;;
        run-daemon)
            run_daemon
            ;;
        help|--help|-h)
            show_help
            ;;
        *)
            echo -e "${RED}Unknown command: $command${NC}"
            echo "Run './lib/gap-analysis-daemon.sh help' for usage"
            exit 1
            ;;
    esac
}

# Run if executed directly
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi
