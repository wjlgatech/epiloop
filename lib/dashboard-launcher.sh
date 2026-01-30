#!/usr/bin/env bash
#
# Dashboard Launcher
# ==================
#
# Manages the dashboard backend server lifecycle.
#
# Features:
# - Start/stop/restart dashboard server
# - Status checking and health monitoring
# - Process management with PID file
# - Auto-launch with daemon mode
# - Port configuration
#

set -euo pipefail

# ==============================================================================
# Configuration
# ==============================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
DASHBOARD_SERVER="$SCRIPT_DIR/dashboard/server.py"
DASHBOARD_PID_FILE="$PROJECT_ROOT/.claude-loop/dashboard/dashboard.pid"
DASHBOARD_LOG_FILE="$PROJECT_ROOT/.claude-loop/dashboard/dashboard.log"
AUTH_TOKEN_FILE="$PROJECT_ROOT/.claude-loop/dashboard/auth_token.txt"

DEFAULT_PORT=8080
DEFAULT_HOST="127.0.0.1"

# ==============================================================================
# Helper Functions
# ==============================================================================

log_info() {
    echo "[INFO] $*"
}

log_error() {
    echo "[ERROR] $*" >&2
}

log_success() {
    echo "[SUCCESS] $*"
}

ensure_dashboard_dir() {
    mkdir -p "$(dirname "$DASHBOARD_PID_FILE")"
}

get_dashboard_pid() {
    if [[ -f "$DASHBOARD_PID_FILE" ]]; then
        cat "$DASHBOARD_PID_FILE"
    else
        echo ""
    fi
}

is_dashboard_running() {
    local pid
    pid=$(get_dashboard_pid)

    if [[ -z "$pid" ]]; then
        return 1
    fi

    # Check if process exists
    if kill -0 "$pid" 2>/dev/null; then
        return 0
    else
        # PID file exists but process doesn't - clean up
        rm -f "$DASHBOARD_PID_FILE"
        return 1
    fi
}

# ==============================================================================
# Dashboard Commands
# ==============================================================================

start_dashboard() {
    local port="${1:-$DEFAULT_PORT}"
    local host="${2:-$DEFAULT_HOST}"

    ensure_dashboard_dir

    if is_dashboard_running; then
        log_error "Dashboard is already running (PID: $(get_dashboard_pid))"
        return 1
    fi

    # Check if Python and required packages are available
    if ! command -v python3 &>/dev/null; then
        log_error "Python 3 is not installed"
        return 1
    fi

    # Check for Flask
    if ! python3 -c "import flask" 2>/dev/null; then
        log_error "Flask is not installed. Install with: pip3 install flask flask-cors"
        return 1
    fi

    # Check for flask-cors
    if ! python3 -c "import flask_cors" 2>/dev/null; then
        log_error "flask-cors is not installed. Install with: pip3 install flask-cors"
        return 1
    fi

    log_info "Starting dashboard server on $host:$port..."

    # Start server in background
    nohup python3 "$DASHBOARD_SERVER" --host "$host" --port "$port" > "$DASHBOARD_LOG_FILE" 2>&1 &
    local server_pid=$!

    # Wait a moment for server to start
    sleep 2

    # Verify server started
    if kill -0 "$server_pid" 2>/dev/null; then
        # Server is running
        log_success "Dashboard server started (PID: $server_pid)"
        log_info "Server URL: http://$host:$port"

        # Show auth token
        if [[ -f "$AUTH_TOKEN_FILE" ]]; then
            local token
            token=$(cat "$AUTH_TOKEN_FILE")
            log_info "Authentication token: $token"
            log_info "Use: curl -H 'Authorization: Bearer $token' http://$host:$port/api/status"
        fi

        log_info "Logs: $DASHBOARD_LOG_FILE"
    else
        log_error "Dashboard server failed to start"
        log_error "Check logs: $DASHBOARD_LOG_FILE"
        return 1
    fi
}

stop_dashboard() {
    if ! is_dashboard_running; then
        log_info "Dashboard is not running"
        return 0
    fi

    local pid
    pid=$(get_dashboard_pid)

    log_info "Stopping dashboard server (PID: $pid)..."
    kill "$pid"

    # Wait for graceful shutdown (up to 10 seconds)
    local count=0
    while kill -0 "$pid" 2>/dev/null && [[ $count -lt 10 ]]; do
        sleep 1
        count=$((count + 1))
    done

    # Force kill if still running
    if kill -0 "$pid" 2>/dev/null; then
        log_info "Forcing dashboard server shutdown..."
        kill -9 "$pid"
    fi

    rm -f "$DASHBOARD_PID_FILE"
    log_success "Dashboard server stopped"
}

restart_dashboard() {
    local port="${1:-$DEFAULT_PORT}"
    local host="${2:-$DEFAULT_HOST}"

    log_info "Restarting dashboard server..."
    stop_dashboard
    sleep 1
    start_dashboard "$port" "$host"
}

status_dashboard() {
    if is_dashboard_running; then
        local pid
        pid=$(get_dashboard_pid)
        log_success "Dashboard is running (PID: $pid)"

        # Try to get port from log
        if [[ -f "$DASHBOARD_LOG_FILE" ]]; then
            local port_line
            port_line=$(grep "Running on" "$DASHBOARD_LOG_FILE" | tail -1)
            if [[ -n "$port_line" ]]; then
                echo "$port_line"
            fi
        fi

        # Show auth token
        if [[ -f "$AUTH_TOKEN_FILE" ]]; then
            local token
            token=$(cat "$AUTH_TOKEN_FILE")
            log_info "Authentication token: $token"
        fi

        return 0
    else
        log_info "Dashboard is not running"
        return 1
    fi
}

show_logs() {
    if [[ ! -f "$DASHBOARD_LOG_FILE" ]]; then
        log_error "Log file not found: $DASHBOARD_LOG_FILE"
        return 1
    fi

    tail -f "$DASHBOARD_LOG_FILE"
}

generate_token() {
    python3 "$DASHBOARD_SERVER" --generate-token
}

# ==============================================================================
# Main Entry Point
# ==============================================================================

main() {
    local command="${1:-}"
    shift || true

    case "$command" in
        start)
            start_dashboard "$@"
            ;;
        stop)
            stop_dashboard
            ;;
        restart)
            restart_dashboard "$@"
            ;;
        status)
            status_dashboard
            ;;
        logs)
            show_logs
            ;;
        generate-token)
            generate_token
            ;;
        *)
            echo "Usage: $0 {start|stop|restart|status|logs|generate-token} [options]"
            echo ""
            echo "Commands:"
            echo "  start [--port PORT] [--host HOST]  Start dashboard server"
            echo "  stop                                 Stop dashboard server"
            echo "  restart [--port PORT] [--host HOST] Restart dashboard server"
            echo "  status                               Show dashboard status"
            echo "  logs                                 Show dashboard logs (tail -f)"
            echo "  generate-token                       Generate new auth token"
            echo ""
            echo "Examples:"
            echo "  $0 start                   # Start on default port 8080"
            echo "  $0 start --port 9000       # Start on custom port"
            echo "  $0 status                  # Check if running"
            echo "  $0 logs                    # View logs"
            exit 1
            ;;
    esac
}

# Only run main if script is executed directly
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi
