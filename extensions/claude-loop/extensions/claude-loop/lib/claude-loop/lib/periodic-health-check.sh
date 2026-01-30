#!/usr/bin/env bash
#
# periodic-health-check.sh - Periodic Health Check and Issue Creation
#
# Runs periodically (e.g., via cron) to:
# 1. Check worker health
# 2. Export fixed deficiencies to experience store
# 3. Auto-create GitHub issues for recurring deficiencies
#
# Usage:
#   ./lib/periodic-health-check.sh
#
# Cron example (run every hour):
#   0 * * * * cd /path/to/claude-loop && ./lib/periodic-health-check.sh
#

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_ROOT"

# Source hidden intelligence
if [[ -f "$SCRIPT_DIR/hidden-intelligence.sh" ]]; then
    source "$SCRIPT_DIR/hidden-intelligence.sh" 2>/dev/null || true
fi

LOG_FILE=".claude-loop/hidden-intelligence/periodic-check.log"
mkdir -p "$(dirname "$LOG_FILE")"

log_check() {
    echo "[$(date -u +"%Y-%m-%dT%H:%M:%SZ")] $1" >> "$LOG_FILE"
}

# 1. Check worker health
log_check "Starting periodic health check"

unhealthy_count=0
while IFS=: read -r worker_id status seconds; do
    log_check "Unhealthy worker detected: $worker_id (status=$status, last_seen=${seconds}s ago)"
    unhealthy_count=$((unhealthy_count + 1))
done < <(check_worker_health_silent 2>/dev/null || true)

if [[ $unhealthy_count -gt 0 ]]; then
    log_check "Found $unhealthy_count unhealthy workers"
fi

# 2. Export fixed deficiencies to experience store
log_check "Exporting fixed deficiencies to experience store"

if command -v python3 &>/dev/null; then
    exported_count=$(python3 "$SCRIPT_DIR/deficiency_to_experience.py" export-all-fixed 2>/dev/null | grep -oE '[0-9]+' || echo "0")
    if [[ $exported_count -gt 0 ]]; then
        log_check "Exported $exported_count deficiencies to experience store"
    fi
fi

# 3. Auto-create GitHub issues for recurring deficiencies
log_check "Checking for recurring deficiencies"

if command -v gh &>/dev/null && gh auth status &>/dev/null; then
    auto_create_issues_for_deficiencies 2>/dev/null || true
    log_check "Auto-issue creation completed"
else
    log_check "GitHub CLI not available or not authenticated, skipping auto-issue creation"
fi

log_check "Periodic health check completed"
