#!/usr/bin/env bash
#
# hidden-intelligence.sh - Invisible Intelligence Layer
#
# This script provides "hidden intelligence" features that work automatically
# without user knowledge or intervention:
#
# 1. Failure logging on worker/coordinator errors
# 2. Worker heartbeat monitoring
# 3. Deficiency tracking and learning
# 4. Auto-export to experience store
# 5. Auto-create GitHub issues for recurring deficiencies
#
# Usage:
#   source lib/hidden-intelligence.sh
#
#   # Initialize (call once at startup)
#   init_hidden_intelligence
#
#   # Log failures automatically
#   log_failure_silent "PRD-001" "api_error" "Rate limit exceeded" "$exit_code"
#
#   # Start worker heartbeat (background)
#   start_worker_heartbeat "worker-001" "PRD-001" &
#
#   # Check for recurring deficiencies (periodic)
#   auto_create_issues_for_deficiencies
#

set -euo pipefail

HIDDEN_INTEL_DIR=".claude-loop/hidden-intelligence"
HIDDEN_INTEL_LOG="${HIDDEN_INTEL_DIR}/activity.log"

# ============================================================================
# Initialization
# ============================================================================

init_hidden_intelligence() {
    # Create directories silently
    mkdir -p "$HIDDEN_INTEL_DIR" 2>/dev/null || true
    mkdir -p ".claude-loop/failures" 2>/dev/null || true
    mkdir -p ".claude-loop/deficiencies" 2>/dev/null || true

    # Log initialization (debug only)
    if [[ "${DEBUG:-}" == "true" ]]; then
        echo "[Hidden Intelligence] Initialized" >> "$HIDDEN_INTEL_LOG"
    fi
}

# ============================================================================
# Failure Logging (Hidden)
# ============================================================================

log_failure_silent() {
    local prd_id="$1"
    local failure_type="$2"
    local error_message="$3"
    local exit_code="${4:-1}"
    local story_id="${5:-}"
    local worker_id="${6:-}"

    # Call Python failure logger silently
    python3 -c "
import sys
sys.path.insert(0, '.')
from lib.failure_logger import FailureLogger, FailureType

logger = FailureLogger()

# Map failure type string to enum
type_map = {
    'api_error': FailureType.API_ERROR,
    'timeout': FailureType.TIMEOUT,
    'resource_exhaustion': FailureType.RESOURCE_EXHAUSTION,
    'bug': FailureType.BUG,
    'logic_error': FailureType.BUG,
    'quality_gate_failure': FailureType.QUALITY_GATE_FAILURE,
    'coordinator_error': FailureType.COORDINATOR_ERROR,
    'unknown': FailureType.UNKNOWN
}

failure_type = type_map.get('${failure_type}', FailureType.UNKNOWN)

logger.log_failure(
    prd_id='${prd_id}',
    failure_type=failure_type,
    error_message='${error_message}',
    exit_code=${exit_code},
    story_id='${story_id}' if '${story_id}' else None,
    worker_id='${worker_id}' if '${worker_id}' else None
)
" 2>/dev/null || true
}

# ============================================================================
# Deficiency Tracking (Hidden)
# ============================================================================

record_deficiency_silent() {
    local deficiency_type="$1"
    local description="$2"
    local solution="${3:-}"
    local context_json="${4:-{}}"

    # Call Python deficiency tracker silently
    python3 -c "
import sys
import json
sys.path.insert(0, '.')
from lib.deficiency_tracker import DeficiencyTracker, DeficiencyType

tracker = DeficiencyTracker()

# Map type string to enum
type_map = {
    'coordinator_bug': DeficiencyType.COORDINATOR_BUG,
    'silent_failure': DeficiencyType.SILENT_FAILURE,
    'resource_issue': DeficiencyType.RESOURCE_ISSUE,
    'api_failure': DeficiencyType.API_FAILURE,
    'logic_error': DeficiencyType.LOGIC_ERROR,
    'quality_gate_bug': DeficiencyType.QUALITY_GATE_BUG,
    'configuration_error': DeficiencyType.CONFIGURATION_ERROR,
    'missing_feature': DeficiencyType.MISSING_FEATURE
}

deficiency_type = type_map.get('${deficiency_type}', DeficiencyType.LOGIC_ERROR)
context = json.loads('${context_json}')

deficiency_id = tracker.record_deficiency(
    deficiency_type=deficiency_type,
    description='${description}',
    solution='${solution}' if '${solution}' else None,
    context=context
)

# Auto-export to experience store if has solution
if '${solution}':
    export = tracker.export_for_experience_store(deficiency_id)

    # Import experience store and add
    try:
        from lib.experience_store import store_experience
        store_experience(
            problem=export['problem'],
            solution=export['solution'],
            context=export['context']
        )
    except Exception:
        pass  # Silently fail if experience store not available

print(deficiency_id)
" 2>/dev/null || true
}

# ============================================================================
# Worker Heartbeat (Hidden Background Process)
# ============================================================================

start_worker_heartbeat() {
    local worker_id="$1"
    local prd_id="$2"
    local story_id="${3:-}"

    # Start background heartbeat loop
    (
        local iteration=0
        local api_calls=0

        while true; do
            # Write heartbeat silently
            python3 -c "
import sys
sys.path.insert(0, '.')
from lib.health_monitor import HealthMonitor

monitor = HealthMonitor()
monitor.write_heartbeat(
    worker_id='${worker_id}',
    prd_id='${prd_id}',
    story_id='${story_id}' if '${story_id}' else None,
    iteration=${iteration},
    api_calls_made=${api_calls},
    context={'pid': $$}
)
" 2>/dev/null || true

            iteration=$((iteration + 1))
            sleep 30
        done
    ) &

    # Store PID for cleanup
    echo $! > "${HIDDEN_INTEL_DIR}/heartbeat_${worker_id}.pid"
}

stop_worker_heartbeat() {
    local worker_id="$1"
    local pid_file="${HIDDEN_INTEL_DIR}/heartbeat_${worker_id}.pid"

    if [[ -f "$pid_file" ]]; then
        local pid=$(cat "$pid_file")
        kill "$pid" 2>/dev/null || true
        rm "$pid_file" 2>/dev/null || true
    fi
}

# ============================================================================
# Retry Decision (Hidden)
# ============================================================================

should_retry_silent() {
    local prd_id="$1"
    local failure_type="$2"
    local attempt="${3:-0}"

    # Returns exit code 0 if should retry, 1 if not
    python3 -c "
import sys
sys.path.insert(0, '.')
from lib.retry_handler import RetryHandler

handler = RetryHandler()
decision = handler.should_retry(
    prd_id='${prd_id}',
    failure_type='${failure_type}',
    attempt=${attempt}
)

if decision.should_retry:
    print(int(decision.backoff_seconds))
    sys.exit(0)
else:
    sys.exit(1)
" 2>/dev/null
}

# ============================================================================
# Auto-Create GitHub Issues (Hidden)
# ============================================================================

auto_create_issues_for_deficiencies() {
    # Check if gh CLI is available
    if ! command -v gh &> /dev/null; then
        return 0
    fi

    # Get recurring deficiencies (frequency >= 5)
    python3 -c "
import sys
import json
sys.path.insert(0, '.')
from lib.deficiency_tracker import DeficiencyTracker

tracker = DeficiencyTracker()
patterns = tracker.detect_patterns()

# Filter for high-frequency deficiencies
high_freq = [p for p in patterns if p['frequency'] >= 5 and p['status'] == 'open']

for pattern in high_freq:
    # Check if already has GitHub issue
    deficiency_id = pattern['id']
    deficiency = tracker._deficiencies.get(deficiency_id)

    if deficiency and not deficiency.github_issue:
        # Create issue
        print(json.dumps({
            'id': deficiency_id,
            'title': pattern['description'],
            'body': '\\n'.join([
                '## Deficiency',
                f\"Type: {pattern['type']}\",
                f\"Frequency: {pattern['frequency']} occurrences\",
                '',
                '## Suggested Improvements',
                *[f'- {s}' for s in pattern['suggestions']],
                '',
                '## Context',
                f\"First seen: {deficiency.first_seen}\",
                f\"Last seen: {deficiency.last_seen}\",
                '',
                '---',
                '*Auto-generated by claude-loop hidden intelligence*'
            ])
        }))
" 2>/dev/null | while read -r line; do
        # Parse JSON
        local deficiency_id=$(echo "$line" | jq -r '.id')
        local title=$(echo "$line" | jq -r '.title')
        local body=$(echo "$line" | jq -r '.body')

        # Create GitHub issue silently
        local issue_url=$(gh issue create \
            --title "🤖 Auto-detected: $title" \
            --body "$body" \
            --label "auto-detected,deficiency" 2>/dev/null || echo "")

        if [[ -n "$issue_url" ]]; then
            # Mark as in_progress with issue link
            python3 -c "
import sys
sys.path.insert(0, '.')
from lib.deficiency_tracker import DeficiencyTracker

tracker = DeficiencyTracker()
tracker.mark_in_progress('${deficiency_id}', github_issue='${issue_url}')
" 2>/dev/null || true
        fi
    done
}

# ============================================================================
# Health Check (Periodic)
# ============================================================================

check_worker_health_silent() {
    # Check all workers and log unhealthy ones
    python3 -c "
import sys
sys.path.insert(0, '.')
from lib.health_monitor import HealthMonitor

monitor = HealthMonitor()
unhealthy = monitor.get_unhealthy_workers()

for worker in unhealthy:
    print(f\"{worker.worker_id}:{worker.status}:{worker.seconds_since_heartbeat}\")
" 2>/dev/null || true
}

# ============================================================================
# Main Entry Point (for standalone execution)
# ============================================================================

if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    # Called directly
    case "${1:-}" in
        init)
            init_hidden_intelligence
            ;;
        log-failure)
            log_failure_silent "$2" "$3" "$4" "${5:-1}" "${6:-}" "${7:-}"
            ;;
        start-heartbeat)
            start_worker_heartbeat "$2" "$3" "${4:-}"
            ;;
        stop-heartbeat)
            stop_worker_heartbeat "$2"
            ;;
        should-retry)
            should_retry_silent "$2" "$3" "${4:-0}"
            ;;
        check-health)
            check_worker_health_silent
            ;;
        auto-issues)
            auto_create_issues_for_deficiencies
            ;;
        record-deficiency)
            record_deficiency_silent "$2" "$3" "${4:-}" "${5:-{}}"
            ;;
        *)
            echo "Usage: $0 {init|log-failure|start-heartbeat|stop-heartbeat|should-retry|check-health|auto-issues|record-deficiency}"
            exit 1
            ;;
    esac
fi
