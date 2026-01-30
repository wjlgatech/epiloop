#!/usr/bin/env python3
"""
Dashboard Backend Server
========================

Flask-based web server providing REST API and Server-Sent Events (SSE)
for real-time progress monitoring of claude-loop executions.

Features:
- REST API endpoints for status, stories, logs, metrics
- Server-Sent Events (SSE) for real-time updates
- Token-based authentication
- CORS support for local development
- Multiple concurrent execution monitoring
- Historical runs archive
"""

import os
import sys
import json
import time
import secrets
import signal
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime, timezone
from flask import Flask, jsonify, request, Response, stream_with_context, send_from_directory
from flask_cors import CORS
import threading
import queue

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from dashboard.api import DashboardAPI

# Get the directory where this script is located
SCRIPT_DIR = Path(__file__).parent
STATIC_DIR = SCRIPT_DIR / "static"

app = Flask(__name__, static_folder=str(STATIC_DIR), static_url_path='')
CORS(app)  # Enable CORS for all routes

# Configuration
DEFAULT_PORT = 8080
AUTH_TOKEN_FILE = Path(".claude-loop/dashboard/auth_token.txt")
DASHBOARD_PID_FILE = Path(".claude-loop/dashboard/dashboard.pid")

# Global state
api: Optional[DashboardAPI] = None
sse_clients: List[queue.Queue] = []
sse_lock = threading.Lock()


# ==============================================================================
# Authentication
# ==============================================================================

def load_auth_token() -> Optional[str]:
    """Load authentication token from file."""
    if AUTH_TOKEN_FILE.exists():
        return AUTH_TOKEN_FILE.read_text().strip()
    return None


def generate_auth_token() -> str:
    """Generate a new authentication token."""
    token = secrets.token_urlsafe(32)
    AUTH_TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)
    AUTH_TOKEN_FILE.write_text(token)
    AUTH_TOKEN_FILE.chmod(0o600)  # Read/write for owner only
    return token


def require_auth(f):
    """Decorator to require authentication for endpoints."""
    def decorated_function(*args, **kwargs):
        token = load_auth_token()
        if not token:
            return jsonify({"error": "Authentication not configured"}), 500

        # Check Authorization header
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return jsonify({"error": "Missing or invalid Authorization header"}), 401

        provided_token = auth_header[7:]  # Remove "Bearer " prefix
        if provided_token != token:
            return jsonify({"error": "Invalid authentication token"}), 403

        return f(*args, **kwargs)

    decorated_function.__name__ = f.__name__
    return decorated_function


# ==============================================================================
# Server-Sent Events (SSE)
# ==============================================================================

def add_sse_client(client_queue: queue.Queue):
    """Add a new SSE client."""
    with sse_lock:
        sse_clients.append(client_queue)


def remove_sse_client(client_queue: queue.Queue):
    """Remove an SSE client."""
    with sse_lock:
        if client_queue in sse_clients:
            sse_clients.remove(client_queue)


def broadcast_sse_event(event_type: str, data: Dict[str, Any]):
    """Broadcast an event to all SSE clients."""
    message = {
        "type": event_type,
        "data": data,
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    }

    with sse_lock:
        for client_queue in sse_clients[:]:  # Copy list to avoid modification during iteration
            try:
                client_queue.put_nowait(message)
            except queue.Full:
                # Client queue is full, remove it
                sse_clients.remove(client_queue)


def sse_event_generator(client_queue: queue.Queue):
    """Generate SSE events for a client."""
    try:
        # Send initial connection event
        yield f"data: {json.dumps({'type': 'connected', 'timestamp': datetime.utcnow().isoformat() + 'Z'})}\n\n"

        while True:
            try:
                # Wait for events with timeout to allow checking if client disconnected
                message = client_queue.get(timeout=30)
                yield f"data: {json.dumps(message)}\n\n"
            except queue.Empty:
                # Send keepalive ping
                yield f": keepalive\n\n"
    except GeneratorExit:
        # Client disconnected
        remove_sse_client(client_queue)


# ==============================================================================
# Frontend Routes
# ==============================================================================

@app.route("/")
def index():
    """Serve the dashboard frontend."""
    return send_from_directory(str(STATIC_DIR), 'index.html')

@app.route("/<path:path>")
def serve_static(path):
    """Serve static files."""
    return send_from_directory(str(STATIC_DIR), path)

# ==============================================================================
# REST API Endpoints
# ==============================================================================

@app.route("/api/health", methods=["GET"])
def health_check():
    """Health check endpoint (no auth required)."""
    return jsonify({
        "status": "ok",
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "version": "1.0.0"
    })


@app.route("/api/status", methods=["GET"])
@require_auth
def get_status():
    """Get current execution status."""
    if not api:
        return jsonify({"error": "API not initialized"}), 500

    status = api.get_current_status()
    return jsonify(status)


@app.route("/api/stories", methods=["GET"])
@require_auth
def get_stories():
    """Get all stories with their status."""
    if not api:
        return jsonify({"error": "API not initialized"}), 500

    run_id = request.args.get("run_id")
    stories = api.get_stories(run_id)
    return jsonify(stories)


@app.route("/api/logs", methods=["GET"])
@require_auth
def get_logs():
    """Get execution logs."""
    if not api:
        return jsonify({"error": "API not initialized"}), 500

    run_id = request.args.get("run_id")
    limit = request.args.get("limit", type=int, default=100)
    offset = request.args.get("offset", type=int, default=0)

    logs = api.get_logs(run_id, limit=limit, offset=offset)
    return jsonify(logs)


@app.route("/api/metrics", methods=["GET"])
@require_auth
def get_metrics():
    """Get execution metrics."""
    if not api:
        return jsonify({"error": "API not initialized"}), 500

    run_id = request.args.get("run_id")
    metrics = api.get_metrics(run_id)
    return jsonify(metrics)


@app.route("/api/history", methods=["GET"])
@require_auth
def get_history():
    """Get historical runs."""
    if not api:
        return jsonify({"error": "API not initialized"}), 500

    limit = request.args.get("limit", type=int, default=20)
    offset = request.args.get("offset", type=int, default=0)

    history = api.get_history(limit=limit, offset=offset)
    return jsonify(history)


@app.route("/api/stream", methods=["GET"])
@require_auth
def event_stream():
    """Server-Sent Events (SSE) endpoint for real-time updates."""
    client_queue: queue.Queue = queue.Queue(maxsize=100)
    add_sse_client(client_queue)

    return Response(
        stream_with_context(sse_event_generator(client_queue)),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no"
        }
    )


@app.route("/api/runs", methods=["GET"])
@require_auth
def get_runs():
    """Get list of all runs."""
    if not api:
        return jsonify({"error": "API not initialized"}), 500

    runs = api.get_all_runs()
    return jsonify(runs)


@app.route("/api/runs/<run_id>", methods=["GET"])
@require_auth
def get_run_details(run_id: str):
    """Get detailed information about a specific run."""
    if not api:
        return jsonify({"error": "API not initialized"}), 500

    details = api.get_run_details(run_id)
    if not details:
        return jsonify({"error": "Run not found"}), 404

    return jsonify(details)


@app.route("/api/daemon/status", methods=["GET"])
@require_auth
def get_daemon_status():
    """Get daemon status including running state and configuration."""
    daemon_dir = Path(".claude-loop/daemon")
    daemon_pid_file = daemon_dir / "daemon.pid"
    daemon_status_file = daemon_dir / "status.json"

    result = {
        "running": False,
        "pid": None,
        "status": "stopped",
        "message": "Daemon is not running"
    }

    # Check if daemon is running
    if daemon_pid_file.exists():
        try:
            pid = int(daemon_pid_file.read_text().strip())
            # Check if process is alive
            import signal
            try:
                os.kill(pid, 0)  # Signal 0 checks if process exists
                result["running"] = True
                result["pid"] = pid
                result["status"] = "running"
                result["message"] = f"Daemon is running (PID: {pid})"
            except (OSError, ProcessLookupError):
                result["message"] = "Daemon PID file exists but process is not running"
        except (ValueError, IOError):
            result["message"] = "Invalid daemon PID file"

    # Load status file if available
    if daemon_status_file.exists():
        try:
            status_data = json.loads(daemon_status_file.read_text())
            result["details"] = status_data
        except (json.JSONDecodeError, IOError):
            pass

    return jsonify(result)


@app.route("/api/daemon/queue", methods=["GET"])
@require_auth
def get_daemon_queue():
    """Get current daemon queue with all pending/running tasks."""
    queue_file = Path(".claude-loop/daemon/queue.json")

    if not queue_file.exists():
        return jsonify({
            "tasks": [],
            "total": 0,
            "pending": 0,
            "running": 0,
            "completed": 0
        })

    try:
        queue_data = json.loads(queue_file.read_text())
        tasks = queue_data.get("tasks", [])

        # Count by status
        pending = sum(1 for t in tasks if t.get("status") == "pending")
        running = sum(1 for t in tasks if t.get("status") == "running")
        completed = sum(1 for t in tasks if t.get("status") == "completed")

        return jsonify({
            "tasks": tasks,
            "total": len(tasks),
            "pending": pending,
            "running": running,
            "completed": completed
        })
    except (json.JSONDecodeError, IOError) as e:
        return jsonify({"error": f"Failed to read queue: {str(e)}"}), 500


@app.route("/api/notifications/config", methods=["GET"])
@require_auth
def get_notifications_config():
    """Get notification system configuration."""
    config_file = Path(".claude-loop/daemon/notifications.json")

    if not config_file.exists():
        return jsonify({
            "configured": False,
            "channels": {
                "email": {"enabled": False},
                "slack": {"enabled": False},
                "webhook": {"enabled": False}
            }
        })

    try:
        config = json.loads(config_file.read_text())
        return jsonify({
            "configured": True,
            "channels": {
                "email": {
                    "enabled": config.get("email", {}).get("enabled", False),
                    "method": config.get("email", {}).get("method", "sendmail")
                },
                "slack": {
                    "enabled": config.get("slack", {}).get("enabled", False),
                    "configured": bool(config.get("slack", {}).get("webhook_url"))
                },
                "webhook": {
                    "enabled": config.get("webhook", {}).get("enabled", False),
                    "configured": bool(config.get("webhook", {}).get("url"))
                }
            }
        })
    except (json.JSONDecodeError, IOError) as e:
        return jsonify({"error": f"Failed to read config: {str(e)}"}), 500


@app.route("/api/notifications/recent", methods=["GET"])
@require_auth
def get_recent_notifications():
    """Get recent notifications from log."""
    log_file = Path(".claude-loop/daemon/notifications.log")
    limit = request.args.get("limit", type=int, default=50)

    if not log_file.exists():
        return jsonify({"notifications": []})

    try:
        # Read last N lines from log file
        with open(log_file, 'r') as f:
            lines = f.readlines()
            recent_lines = lines[-limit:] if len(lines) > limit else lines

        notifications = []
        for line in recent_lines:
            line = line.strip()
            if line:
                # Parse log line format: [timestamp] [level] message
                try:
                    parts = line.split('] ', 2)
                    if len(parts) >= 3:
                        timestamp = parts[0].lstrip('[')
                        level = parts[1].lstrip('[')
                        message = parts[2]
                        notifications.append({
                            "timestamp": timestamp,
                            "level": level,
                            "message": message
                        })
                except Exception:
                    # If parsing fails, include raw line
                    notifications.append({
                        "timestamp": "",
                        "level": "INFO",
                        "message": line
                    })

        return jsonify({"notifications": notifications})
    except IOError as e:
        return jsonify({"error": f"Failed to read log: {str(e)}"}), 500


# ==============================================================================
# Server Management
# ==============================================================================

def initialize_api():
    """Initialize the Dashboard API."""
    global api
    api = DashboardAPI()

    # Start background thread to monitor for updates and broadcast SSE events
    def monitor_updates():
        while True:
            time.sleep(2)  # Check every 2 seconds

            # Check if there are new updates
            if api:
                current_status = api.get_current_status()
                if current_status and current_status.get("last_update"):
                    # Broadcast update to all SSE clients
                    broadcast_sse_event("status_update", current_status)

            time.sleep(3)  # Wait 3 seconds before next check

    monitor_thread = threading.Thread(target=monitor_updates, daemon=True)
    monitor_thread.start()


def save_pid():
    """Save server PID to file."""
    DASHBOARD_PID_FILE.parent.mkdir(parents=True, exist_ok=True)
    DASHBOARD_PID_FILE.write_text(str(os.getpid()))


def remove_pid():
    """Remove PID file."""
    if DASHBOARD_PID_FILE.exists():
        DASHBOARD_PID_FILE.unlink()


# ==============================================================================
# Main Entry Point
# ==============================================================================

def main():
    """Main entry point for the dashboard server."""
    import argparse

    parser = argparse.ArgumentParser(description="Claude Loop Dashboard Server")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help="Port to listen on")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind to")
    parser.add_argument("--debug", action="store_true", help="Enable debug mode")
    parser.add_argument("--generate-token", action="store_true", help="Generate new auth token and exit")
    args = parser.parse_args()

    if args.generate_token:
        token = generate_auth_token()
        print(f"Generated authentication token: {token}")
        print(f"Token saved to: {AUTH_TOKEN_FILE}")
        print(f"\nUse this token in API requests:")
        print(f"  curl -H 'Authorization: Bearer {token}' http://localhost:{args.port}/api/status")
        return

    # Ensure auth token exists
    token = load_auth_token()
    if not token:
        token = generate_auth_token()
        print(f"Generated new authentication token: {token}")
    else:
        print(f"Using existing authentication token from: {AUTH_TOKEN_FILE}")

    # Initialize API
    initialize_api()

    # Save PID
    save_pid()

    try:
        print(f"Starting Dashboard Server on {args.host}:{args.port}")
        print(f"API endpoints available at: http://{args.host}:{args.port}/api/")
        print(f"Use Authorization header: Bearer {token}")
        app.run(host=args.host, port=args.port, debug=args.debug, threaded=True)
    finally:
        remove_pid()


if __name__ == "__main__":
    main()
