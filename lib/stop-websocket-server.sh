#!/bin/bash
# Stop WebSocket Server
#
# Usage:
#   ./lib/stop-websocket-server.sh [--pid-file FILE]

set -euo pipefail

PID_FILE="${1:-.claude-loop/websocket.pid}"

if [[ ! -f "$PID_FILE" ]]; then
    echo "WebSocket server is not running (no PID file found)"
    exit 0
fi

PID=$(cat "$PID_FILE")

if ! kill -0 "$PID" 2>/dev/null; then
    echo "WebSocket server is not running (stale PID file)"
    rm -f "$PID_FILE"
    exit 0
fi

echo "Stopping WebSocket server (PID: $PID)..."
kill -TERM "$PID"

# Wait for graceful shutdown
for i in {1..10}; do
    if ! kill -0 "$PID" 2>/dev/null; then
        echo "✓ WebSocket server stopped"
        rm -f "$PID_FILE"
        exit 0
    fi
    sleep 0.5
done

# Force kill if still running
if kill -0 "$PID" 2>/dev/null; then
    echo "Forcing shutdown..."
    kill -KILL "$PID"
    sleep 1
fi

rm -f "$PID_FILE"
echo "✓ WebSocket server stopped"
