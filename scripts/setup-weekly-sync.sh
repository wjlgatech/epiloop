#!/usr/bin/env bash
#
# setup-weekly-sync.sh - Configure weekly upstream sync automation
#
# This script sets up a launchd agent to automatically sync with upstream
# every Sunday at 2 AM

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LAUNCH_AGENTS_DIR="$HOME/Library/LaunchAgents"
PLIST_NAME="com.epiloop.sync-upstream.plist"
PLIST_PATH="$LAUNCH_AGENTS_DIR/$PLIST_NAME"

# Color output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info() { echo -e "${BLUE}ℹ${NC} $*"; }
log_success() { echo -e "${GREEN}✓${NC} $*"; }
log_warning() { echo -e "${YELLOW}⚠${NC} $*"; }

# Create LaunchAgents directory if it doesn't exist
mkdir -p "$LAUNCH_AGENTS_DIR"

# Create the plist file
log_info "Creating launchd configuration..."

cat > "$PLIST_PATH" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.epiloop.sync-upstream</string>

    <key>ProgramArguments</key>
    <array>
        <string>$REPO_ROOT/scripts/sync-upstream-weekly.sh</string>
    </array>

    <key>StartCalendarInterval</key>
    <dict>
        <key>Weekday</key>
        <integer>0</integer> <!-- Sunday -->
        <key>Hour</key>
        <integer>2</integer>
        <key>Minute</key>
        <integer>0</integer>
    </dict>

    <key>StandardOutPath</key>
    <string>$HOME/.epiloop/logs/sync-upstream.log</string>

    <key>StandardErrorPath</key>
    <string>$HOME/.epiloop/logs/sync-upstream.error.log</string>

    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:$HOME/Library/pnpm:$HOME/.local/bin</string>
        <key>EPILOOP_AUTO_SYNC</key>
        <string>1</string>
    </dict>

    <key>WorkingDirectory</key>
    <string>$REPO_ROOT</string>

    <key>RunAtLoad</key>
    <false/>

    <key>Nice</key>
    <integer>10</integer> <!-- Low priority -->
</dict>
</plist>
EOF

# Create logs directory
mkdir -p "$HOME/.epiloop/logs"

# Create the weekly sync wrapper script
log_info "Creating weekly sync wrapper..."

cat > "$REPO_ROOT/scripts/sync-upstream-weekly.sh" <<'EOFSCRIPT'
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
EOFSCRIPT

chmod +x "$REPO_ROOT/scripts/sync-upstream-weekly.sh"

log_success "Launchd configuration created: $PLIST_PATH"
log_success "Weekly sync script created"

# Load the agent
log_info "Loading launchd agent..."

# Unload if already loaded
launchctl unload "$PLIST_PATH" 2>/dev/null || true

# Load the new agent
if launchctl load "$PLIST_PATH"; then
    log_success "Launchd agent loaded successfully!"
else
    log_warning "Failed to load launchd agent. You may need to load it manually:"
    echo "  launchctl load $PLIST_PATH"
fi

# Show status
echo ""
log_info "Weekly sync is now configured!"
echo ""
echo "Schedule: Every Sunday at 2:00 AM"
echo "Logs: ~/.epiloop/logs/sync-upstream*.log"
echo "Config: $PLIST_PATH"
echo ""
echo "Manual commands:"
echo "  • Check status:  launchctl list | grep epiloop.sync-upstream"
echo "  • Trigger now:   launchctl start com.epiloop.sync-upstream"
echo "  • Disable:       launchctl unload $PLIST_PATH"
echo "  • Enable:        launchctl load $PLIST_PATH"
echo "  • View logs:     tail -f ~/.epiloop/logs/sync-upstream.log"
echo ""
log_success "Setup complete!"
