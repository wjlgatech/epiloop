#!/usr/bin/env bash
#
# sync-upstream-weekly.sh - Weekly automated sync wrapper
#
# This script runs weekly and handles notification/logging

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

LOG_FILE="$HOME/.epiloop/logs/sync-upstream-$(date +%Y%m%d-%H%M%S).log"
CONFLICTS_FILE="$HOME/.epiloop/logs/sync-conflicts-$(date +%Y%m%d).txt"

echo "=== Epiloop Upstream Sync - $(date) ===" | tee "$LOG_FILE"
echo "" | tee -a "$LOG_FILE"

# Run the sync script
export EPILOOP_AUTO_SYNC=1

if "$REPO_ROOT/scripts/sync-upstream.sh" >> "$LOG_FILE" 2>&1; then
    echo "✓ Sync successful!" | tee -a "$LOG_FILE"

    # Send macOS notification
    osascript -e 'display notification "Epiloop successfully synced with upstream openclaw" with title "Epiloop Sync" sound name "Glass"' || true

    exit 0
else
    EXIT_CODE=$?
    echo "✗ Sync failed with exit code $EXIT_CODE" | tee -a "$LOG_FILE"

    # Check if there are conflicts
    if git status | grep -q "Unmerged paths"; then
        echo "⚠ Merge conflicts detected" | tee -a "$LOG_FILE"
        git diff --name-only --diff-filter=U > "$CONFLICTS_FILE" || true

        # Send notification about conflicts
        osascript -e 'display notification "Upstream sync has conflicts. Manual resolution needed." with title "Epiloop Sync - Conflicts" sound name "Basso"' || true
    else
        # General error notification
        osascript -e 'display notification "Upstream sync failed. Check logs." with title "Epiloop Sync - Error" sound name "Basso"' || true
    fi

    exit $EXIT_CODE
fi
