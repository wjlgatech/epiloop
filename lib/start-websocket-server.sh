#!/bin/bash
# Start WebSocket Server for Real-Time Progress Streaming
#
# Usage:
#   ./lib/start-websocket-server.sh [options]
#
# Options:
#   --port PORT       Port to bind to (default: 18790)
#   --host HOST       Host to bind to (default: 127.0.0.1)
#   --daemon          Run in background
#   --debug           Enable debug logging
#   --pid-file FILE   PID file path (default: .claude-loop/websocket.pid)

set -euo pipefail

# Defaults
PORT="${WEBSOCKET_PORT:-18790}"
HOST="${WEBSOCKET_HOST:-127.0.0.1}"
DAEMON=false
DEBUG=false
PID_FILE=".claude-loop/websocket.pid"

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --port)
            PORT="$2"
            shift 2
            ;;
        --host)
            HOST="$2"
            shift 2
            ;;
        --daemon)
            DAEMON=true
            shift
            ;;
        --debug)
            DEBUG=true
            shift
            ;;
        --pid-file)
            PID_FILE="$2"
            shift 2
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

# Ensure directory exists
mkdir -p "$(dirname "$PID_FILE")"

# Check if already running
if [[ -f "$PID_FILE" ]]; then
    OLD_PID=$(cat "$PID_FILE")
    if kill -0 "$OLD_PID" 2>/dev/null; then
        echo "WebSocket server already running (PID: $OLD_PID)"
        exit 0
    else
        rm -f "$PID_FILE"
    fi
fi

# Build command
CMD="python3 lib/websocket_server.py --host $HOST --port $PORT"
if [[ "$DEBUG" == "true" ]]; then
    CMD="$CMD --debug"
fi

# Start server
if [[ "$DAEMON" == "true" ]]; then
    echo "Starting WebSocket server in background..."
    nohup $CMD > .claude-loop/websocket.log 2>&1 &
    SERVER_PID=$!
    echo $SERVER_PID > "$PID_FILE"

    # Wait a bit to check if it started successfully
    sleep 2
    if kill -0 $SERVER_PID 2>/dev/null; then
        echo "✓ WebSocket server started (PID: $SERVER_PID)"
        echo "  Listening on ws://$HOST:$PORT"
        echo "  Logs: .claude-loop/websocket.log"
    else
        echo "✗ Failed to start WebSocket server"
        rm -f "$PID_FILE"
        exit 1
    fi
else
    echo "Starting WebSocket server..."
    exec $CMD
fi
