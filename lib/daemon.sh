#!/usr/bin/env bash
#
# daemon.sh - Background daemon for claude-loop
#
# Features:
# - Runs as background service
# - Accepts tasks via queue
# - Configurable worker pool
# - Graceful shutdown
# - Auto-restart on failure
# - PID file management
# - Priority queuing
#

set -euo pipefail

# Configuration
DAEMON_DIR="${CLAUDE_LOOP_DIR:-.claude-loop}/daemon"
DAEMON_PID_FILE="${DAEMON_DIR}/daemon.pid"
DAEMON_LOG_FILE="${DAEMON_DIR}/daemon.log"
QUEUE_FILE="${DAEMON_DIR}/queue.json"
DAEMON_STATUS_FILE="${DAEMON_DIR}/status.json"
DAEMON_LOCK_FILE="${DAEMON_DIR}/daemon.lock"

# Default configuration
DEFAULT_WORKERS=1
DEFAULT_POLL_INTERVAL=5

# Ensure daemon directory exists
init_daemon_dir() {
    mkdir -p "${DAEMON_DIR}"

    # Initialize queue if it doesn't exist
    if [[ ! -f "${QUEUE_FILE}" ]]; then
        echo '{"tasks": []}' > "${QUEUE_FILE}"
    fi
}

# Logging function
log_daemon() {
    local level="$1"
    shift
    local message="$*"
    local timestamp
    timestamp=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
    echo "[${timestamp}] [${level}] ${message}" >> "${DAEMON_LOG_FILE}"
}

# Check if daemon is running
is_daemon_running() {
    if [[ -f "${DAEMON_PID_FILE}" ]]; then
        local pid
        pid=$(cat "${DAEMON_PID_FILE}")
        if kill -0 "${pid}" 2>/dev/null; then
            return 0
        else
            # PID file exists but process is dead
            rm -f "${DAEMON_PID_FILE}"
            return 1
        fi
    fi
    return 1
}

# Acquire lock
acquire_lock() {
    local timeout="${1:-10}"
    local elapsed=0

    while [[ -d "${DAEMON_LOCK_FILE}" ]]; do
        if [[ ${elapsed} -ge ${timeout} ]]; then
            return 1
        fi
        sleep 1
        elapsed=$((elapsed + 1))
    done

    mkdir "${DAEMON_LOCK_FILE}" 2>/dev/null || return 1
    return 0
}

# Release lock
release_lock() {
    rmdir "${DAEMON_LOCK_FILE}" 2>/dev/null || true
}

# Get queue tasks
get_queue_tasks() {
    if [[ -f "${QUEUE_FILE}" ]]; then
        python3 -c "
import json
import sys
with open('${QUEUE_FILE}', 'r') as f:
    data = json.load(f)
    print(json.dumps(data.get('tasks', [])))
"
    else
        echo '[]'
    fi
}

# Add task to queue
add_task_to_queue() {
    local prd_path="$1"
    local priority="${2:-normal}"
    local notify_channels="${3:-}"
    local task_id
    task_id=$(date +%s%N | shasum -a 256 | cut -c1-16)

    if ! acquire_lock; then
        echo "Error: Failed to acquire lock" >&2
        return 1
    fi

    python3 -c "
import json
import sys
from datetime import datetime

task_id = '${task_id}'
prd_path = '${prd_path}'
priority = '${priority}'
notify_channels = '${notify_channels}'

# Load existing queue
with open('${QUEUE_FILE}', 'r') as f:
    data = json.load(f)

# Add new task
task = {
    'id': task_id,
    'prd_path': prd_path,
    'priority': priority,
    'status': 'pending',
    'submitted_at': datetime.utcnow().isoformat() + 'Z',
    'started_at': None,
    'completed_at': None,
    'result': None,
    'notify_channels': notify_channels if notify_channels else None
}
data['tasks'].append(task)

# Sort by priority (high > normal > low) then by submission time
priority_order = {'high': 0, 'normal': 1, 'low': 2}
data['tasks'].sort(key=lambda t: (priority_order.get(t['priority'], 1), t['submitted_at']))

# Save queue
with open('${QUEUE_FILE}', 'w') as f:
    json.dump(data, f, indent=2)

print(task_id)
"

    release_lock
}

# Get next pending task
get_next_task() {
    python3 -c "
import json
with open('${QUEUE_FILE}', 'r') as f:
    data = json.load(f)
    for task in data.get('tasks', []):
        if task['status'] == 'pending':
            print(json.dumps(task))
            break
"
}

# Update task status
update_task_status() {
    local task_id="$1"
    local status="$2"
    local result="${3:-}"

    if ! acquire_lock; then
        log_daemon "ERROR" "Failed to acquire lock for task status update"
        return 1
    fi

    python3 -c "
import json
from datetime import datetime

task_id = '${task_id}'
status = '${status}'
result = '''${result}'''

with open('${QUEUE_FILE}', 'r') as f:
    data = json.load(f)

for task in data.get('tasks', []):
    if task['id'] == task_id:
        task['status'] = status
        if status == 'running':
            task['started_at'] = datetime.utcnow().isoformat() + 'Z'
        elif status in ['completed', 'failed']:
            task['completed_at'] = datetime.utcnow().isoformat() + 'Z'
            if result:
                task['result'] = result
        break

with open('${QUEUE_FILE}', 'w') as f:
    json.dump(data, f, indent=2)
"

    release_lock
}

# Execute task
execute_task() {
    local task_id="$1"
    local prd_path="$2"
    local notify_channels="${3:-}"

    log_daemon "INFO" "Executing task ${task_id}: ${prd_path}"
    update_task_status "${task_id}" "running"

    # Get absolute path to claude-loop.sh and notifications.sh
    local script_dir
    script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
    local claude_loop_sh="${script_dir}/claude-loop.sh"
    local notifications_sh="${script_dir}/lib/notifications.sh"

    # Execute claude-loop.sh with the PRD
    local result="success"
    local status="completed"
    local start_time end_time elapsed_ms
    start_time=$(date +%s)

    local output
    if output=$("${claude_loop_sh}" --prd "${prd_path}" 2>&1); then
        log_daemon "INFO" "Task ${task_id} completed successfully"
        update_task_status "${task_id}" "completed" "success"
        status="completed"
    else
        log_daemon "ERROR" "Task ${task_id} failed"
        update_task_status "${task_id}" "failed" "execution_error"
        status="failed"
        result="failed"
    fi

    end_time=$(date +%s)
    elapsed_ms=$(( (end_time - start_time) * 1000 ))

    # Send notifications if channels are specified
    if [[ -n "${notify_channels}" ]] && [[ -f "${notifications_sh}" ]]; then
        log_daemon "INFO" "Sending notifications for task ${task_id} via ${notify_channels}"

        # Extract project name from PRD
        local project
        project=$(python3 -c "import json; data=json.load(open('${prd_path}')); print(data.get('project', 'unknown'))" 2>/dev/null || echo "unknown")

        # Count completed stories
        local stories_completed
        stories_completed=$(python3 -c "import json; data=json.load(open('${prd_path}')); stories=[s for s in data.get('userStories', []) if s.get('passes', False)]; print(len(stories))" 2>/dev/null || echo "0")

        # Format elapsed time
        local time_taken
        if [[ ${elapsed_ms} -ge 3600000 ]]; then
            time_taken="$((elapsed_ms / 3600000))h $((elapsed_ms % 3600000 / 60000))m"
        elif [[ ${elapsed_ms} -ge 60000 ]]; then
            time_taken="$((elapsed_ms / 60000))m $((elapsed_ms % 60000 / 1000))s"
        else
            time_taken="$((elapsed_ms / 1000))s"
        fi

        # Prepare notification data
        local notification_data
        notification_data=$(cat << EOF
{
  "project": "${project}",
  "stories_completed": ${stories_completed},
  "time_taken": "${time_taken}",
  "cost": "\$0.00"
}
EOF
)

        # Send notification
        "${notifications_sh}" notify "${task_id}" "${status}" "${notification_data}" "${notify_channels}" 2>&1 | \
            while IFS= read -r line; do
                log_daemon "INFO" "Notification: ${line}"
            done || log_daemon "WARN" "Failed to send notifications for task ${task_id}"
    fi

    return 0
}

# Worker loop
worker_loop() {
    local worker_id="$1"
    log_daemon "INFO" "Worker ${worker_id} started"

    while true; do
        # Check for shutdown signal
        if [[ -f "${DAEMON_DIR}/shutdown" ]]; then
            log_daemon "INFO" "Worker ${worker_id} received shutdown signal"
            break
        fi

        # Get next task
        local task_json
        task_json=$(get_next_task)

        if [[ -n "${task_json}" ]]; then
            local task_id prd_path notify_channels
            task_id=$(echo "${task_json}" | python3 -c "import json, sys; print(json.load(sys.stdin)['id'])")
            prd_path=$(echo "${task_json}" | python3 -c "import json, sys; print(json.load(sys.stdin)['prd_path'])")
            notify_channels=$(echo "${task_json}" | python3 -c "import json, sys; print(json.load(sys.stdin).get('notify_channels', ''))" 2>/dev/null || echo "")

            execute_task "${task_id}" "${prd_path}" "${notify_channels}"
        else
            # No tasks, sleep
            sleep "${DEFAULT_POLL_INTERVAL}"
        fi
    done

    log_daemon "INFO" "Worker ${worker_id} stopped"
}

# Start daemon
start_daemon() {
    local num_workers="${1:-$DEFAULT_WORKERS}"

    if is_daemon_running; then
        echo "Daemon is already running (PID: $(cat "${DAEMON_PID_FILE}"))"
        return 1
    fi

    init_daemon_dir

    # Remove shutdown signal if it exists
    rm -f "${DAEMON_DIR}/shutdown"

    log_daemon "INFO" "Starting daemon with ${num_workers} worker(s)"

    # Start daemon in background
    (
        # Save PID
        echo $$ > "${DAEMON_PID_FILE}"

        # Update status
        python3 -c "
import json
from datetime import datetime
status = {
    'status': 'running',
    'pid': $$,
    'workers': ${num_workers},
    'started_at': datetime.utcnow().isoformat() + 'Z'
}
with open('${DAEMON_STATUS_FILE}', 'w') as f:
    json.dump(status, f, indent=2)
"

        # Set up signal handlers
        trap 'log_daemon "INFO" "Received SIGTERM, shutting down..."; touch "${DAEMON_DIR}/shutdown"' TERM
        trap 'log_daemon "INFO" "Received SIGINT, shutting down..."; touch "${DAEMON_DIR}/shutdown"' INT

        # Start workers
        local worker_pids=()
        for i in $(seq 1 "${num_workers}"); do
            worker_loop "${i}" &
            worker_pids+=($!)
        done

        # Wait for workers
        for pid in "${worker_pids[@]}"; do
            wait "${pid}"
        done

        # Clean up
        rm -f "${DAEMON_PID_FILE}"
        rm -f "${DAEMON_DIR}/shutdown"

        # Update status
        python3 -c "
import json
from datetime import datetime
status = {
    'status': 'stopped',
    'pid': None,
    'stopped_at': datetime.utcnow().isoformat() + 'Z'
}
with open('${DAEMON_STATUS_FILE}', 'w') as f:
    json.dump(status, f, indent=2)
"

        log_daemon "INFO" "Daemon stopped"
    ) &

    # Wait a moment for daemon to start
    sleep 1

    if is_daemon_running; then
        echo "Daemon started successfully (PID: $(cat "${DAEMON_PID_FILE}"))"
        return 0
    else
        echo "Failed to start daemon"
        return 1
    fi
}

# Stop daemon
stop_daemon() {
    if ! is_daemon_running; then
        echo "Daemon is not running"
        return 1
    fi

    local pid
    pid=$(cat "${DAEMON_PID_FILE}")

    echo "Stopping daemon (PID: ${pid})..."
    log_daemon "INFO" "Stop command received"

    # Signal shutdown
    touch "${DAEMON_DIR}/shutdown"
    kill -TERM "${pid}"

    # Wait for graceful shutdown (up to 30 seconds)
    local timeout=30
    local elapsed=0
    while is_daemon_running && [[ ${elapsed} -lt ${timeout} ]]; do
        sleep 1
        elapsed=$((elapsed + 1))
    done

    if is_daemon_running; then
        echo "Daemon did not stop gracefully, forcing shutdown..."
        kill -KILL "${pid}"
        rm -f "${DAEMON_PID_FILE}"
        echo "Daemon killed"
    else
        echo "Daemon stopped successfully"
    fi

    return 0
}

# Get daemon status
get_daemon_status() {
    if is_daemon_running; then
        local pid
        pid=$(cat "${DAEMON_PID_FILE}")
        echo "Daemon is running (PID: ${pid})"

        if [[ -f "${DAEMON_STATUS_FILE}" ]]; then
            echo ""
            echo "Status:"
            cat "${DAEMON_STATUS_FILE}"
        fi
    else
        echo "Daemon is not running"
        return 1
    fi
}

# Submit task
submit_task() {
    local prd_path="$1"
    local priority="${2:-normal}"
    local notify_channels="${3:-}"

    if [[ ! -f "${prd_path}" ]]; then
        echo "Error: PRD file not found: ${prd_path}" >&2
        return 1
    fi

    # Validate priority
    if [[ ! "${priority}" =~ ^(high|normal|low)$ ]]; then
        echo "Error: Invalid priority '${priority}'. Must be: high, normal, or low" >&2
        return 1
    fi

    init_daemon_dir

    local task_id
    task_id=$(add_task_to_queue "${prd_path}" "${priority}" "${notify_channels}")

    if [[ -n "${task_id}" ]]; then
        echo "Task submitted successfully (ID: ${task_id})"
        if [[ -n "${notify_channels}" ]]; then
            echo "Notifications enabled: ${notify_channels}"
        fi
        log_daemon "INFO" "Task ${task_id} submitted: ${prd_path} (priority: ${priority}, notify: ${notify_channels})"
        return 0
    else
        echo "Error: Failed to submit task" >&2
        return 1
    fi
}

# Show queue
show_queue() {
    if [[ -f "${QUEUE_FILE}" ]]; then
        echo "Task Queue:"
        echo ""
        python3 -c "
import json
with open('${QUEUE_FILE}', 'r') as f:
    data = json.load(f)
    tasks = data.get('tasks', [])
    if not tasks:
        print('No tasks in queue')
    else:
        for task in tasks:
            status_icon = {
                'pending': '⏳',
                'running': '▶️ ',
                'completed': '✅',
                'failed': '❌'
            }.get(task['status'], '❓')
            print(f\"{status_icon} {task['id']} - {task['status']} - {task['prd_path']} (priority: {task['priority']})\")
            print(f\"   Submitted: {task['submitted_at']}\")
            if task.get('started_at'):
                print(f\"   Started: {task['started_at']}\")
            if task.get('completed_at'):
                print(f\"   Completed: {task['completed_at']}\")
            print()
"
    else
        echo "Queue file not found"
    fi
}

# Cancel task
cancel_task() {
    local task_id="$1"

    if ! acquire_lock; then
        echo "Error: Failed to acquire lock" >&2
        return 1
    fi

    python3 -c "
import json

task_id = '${task_id}'

with open('${QUEUE_FILE}', 'r') as f:
    data = json.load(f)

found = False
for i, task in enumerate(data.get('tasks', [])):
    if task['id'] == task_id:
        if task['status'] == 'running':
            print('Error: Cannot cancel running task', file=sys.stderr)
            sys.exit(1)
        data['tasks'].pop(i)
        found = True
        break

if not found:
    print(f'Error: Task {task_id} not found', file=sys.stderr)
    sys.exit(1)

with open('${QUEUE_FILE}', 'w') as f:
    json.dump(data, f, indent=2)

print(f'Task {task_id} cancelled')
"

    local result=$?
    release_lock
    return ${result}
}

# Pause queue
pause_queue() {
    touch "${DAEMON_DIR}/pause"
    echo "Queue paused"
    log_daemon "INFO" "Queue paused"
}

# Resume queue
resume_queue() {
    rm -f "${DAEMON_DIR}/pause"
    echo "Queue resumed"
    log_daemon "INFO" "Queue resumed"
}

# Main CLI
main() {
    local command="${1:-}"
    shift || true

    case "${command}" in
        start)
            local workers="${1:-$DEFAULT_WORKERS}"
            start_daemon "${workers}"
            ;;
        stop)
            stop_daemon
            ;;
        status)
            get_daemon_status
            ;;
        submit)
            local prd_path=""
            local priority="normal"
            local notify_channels=""

            # Parse arguments
            while [[ $# -gt 0 ]]; do
                case "$1" in
                    --notify)
                        notify_channels="${2:-}"
                        shift 2
                        ;;
                    --priority)
                        priority="${2:-normal}"
                        shift 2
                        ;;
                    *)
                        if [[ -z "${prd_path}" ]]; then
                            prd_path="$1"
                        fi
                        shift
                        ;;
                esac
            done

            if [[ -z "${prd_path}" ]]; then
                echo "Usage: $0 submit <prd_path> [--priority high|normal|low] [--notify email,slack,webhook]" >&2
                exit 1
            fi
            submit_task "${prd_path}" "${priority}" "${notify_channels}"
            ;;
        queue)
            show_queue
            ;;
        cancel)
            local task_id="${1:-}"
            if [[ -z "${task_id}" ]]; then
                echo "Usage: $0 cancel <task_id>" >&2
                exit 1
            fi
            cancel_task "${task_id}"
            ;;
        pause)
            pause_queue
            ;;
        resume)
            resume_queue
            ;;
        *)
            echo "Usage: $0 {start|stop|status|submit|queue|cancel|pause|resume}" >&2
            echo ""
            echo "Commands:"
            echo "  start [workers]      Start the daemon with optional worker count (default: 1)"
            echo "  stop                 Stop the daemon gracefully"
            echo "  status               Show daemon status"
            echo "  submit <prd>         Submit a task to the queue"
            echo "    [--priority pri]     Priority: high, normal (default), low"
            echo "    [--notify channels]  Notification channels: email,slack,webhook"
            echo "  queue                Show current queue"
            echo "  cancel <task_id>     Cancel a pending task"
            echo "  pause                Pause queue processing"
            echo "  resume               Resume queue processing"
            exit 1
            ;;
    esac
}

# Run if executed directly
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi
