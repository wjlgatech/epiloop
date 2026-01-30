# Daemon Mode - Background Task Execution

**Status**: ✅ Implemented (US-205)
**Phase**: Phase 2 - Foundations
**Related Features**: Quick Task Mode (US-203), Visual Progress Dashboard (US-207/208)

## Overview

Daemon Mode enables fire-and-forget workflow for claude-loop. Submit PRD tasks to a background daemon and let it process them asynchronously while you continue working. The daemon manages a queue, worker pool, and provides persistent task tracking.

## Key Features

- **Background Execution**: Daemon runs as a background service, processing tasks asynchronously
- **Task Queue**: FIFO queue with priority support (high/normal/low)
- **Worker Pool**: Configurable concurrent workers (default: 1)
- **Graceful Shutdown**: Finishes current tasks before stopping
- **Queue Management**: View, pause, resume, and cancel tasks
- **Persistent State**: Queue survives daemon restarts
- **PID Management**: Process ID tracking for daemon control
- **Logging**: Comprehensive logging to `.claude-loop/daemon/daemon.log`

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      Daemon Process                         │
│                                                             │
│  ┌────────────┐     ┌────────────┐     ┌────────────┐    │
│  │  Worker 1  │     │  Worker 2  │     │  Worker N  │    │
│  │            │     │            │     │            │    │
│  │  Executes  │     │  Executes  │     │  Executes  │    │
│  │   Tasks    │     │   Tasks    │     │   Tasks    │    │
│  └────────────┘     └────────────┘     └────────────┘    │
│         ▲                  ▲                  ▲            │
│         │                  │                  │            │
│         └──────────────────┴──────────────────┘            │
│                            │                               │
│                    ┌───────▼──────┐                        │
│                    │  Task Queue  │                        │
│                    │  (FIFO+Pri)  │                        │
│                    └──────────────┘                        │
│                            ▲                               │
└────────────────────────────┼───────────────────────────────┘
                             │
                    ┌────────▼──────────┐
                    │  Submit Command   │
                    │  (User submits    │
                    │   PRD to queue)   │
                    └───────────────────┘
```

### File Structure

```
.claude-loop/daemon/
├── daemon.pid          # Process ID of running daemon
├── daemon.log          # Daemon activity log
├── queue.json          # Task queue (persistent)
├── status.json         # Daemon status
├── daemon.lock/        # Lock directory for queue operations
├── shutdown            # Shutdown signal file
└── pause               # Pause signal file
```

## Commands

### Start Daemon

Start the background daemon with optional worker count:

```bash
# Start with default 1 worker
./claude-loop.sh daemon start

# Start with 3 concurrent workers
./claude-loop.sh daemon start 3
```

**Behavior**:
- Creates daemon process in background
- Initializes queue if not exists
- Saves PID to `.claude-loop/daemon/daemon.pid`
- Starts specified number of workers
- Returns immediately (non-blocking)

### Stop Daemon

Stop the daemon gracefully:

```bash
./claude-loop.sh daemon stop
```

**Behavior**:
- Signals all workers to shutdown
- Waits up to 30 seconds for current tasks to finish
- Forces kill if graceful shutdown fails
- Cleans up PID file

### Show Status

Display daemon status and configuration:

```bash
./claude-loop.sh daemon status
```

**Output**:
```
Daemon is running (PID: 12345)

Status:
{
  "status": "running",
  "pid": 12345,
  "workers": 1,
  "started_at": "2026-01-13T10:00:00Z"
}
```

### Submit Task

Submit a PRD to the daemon queue:

```bash
# Normal priority (default)
./claude-loop.sh daemon submit prd.json

# High priority
./claude-loop.sh daemon submit prd.json high

# Low priority
./claude-loop.sh daemon submit prd.json low
```

**Priorities**:
- `high`: Processed before normal and low priority tasks
- `normal`: Default priority (processed in submission order)
- `low`: Processed only when no high/normal tasks are available

**Output**:
```
Task submitted successfully (ID: a1b2c3d4e5f67890)
```

### Show Queue

View current task queue:

```bash
./claude-loop.sh daemon queue
```

**Output**:
```
Task Queue:

⏳ a1b2c3d4e5f67890 - pending - prd.json (priority: high)
   Submitted: 2026-01-13T10:00:00Z

▶️  b2c3d4e5f6789012 - running - another-prd.json (priority: normal)
   Submitted: 2026-01-13T10:01:00Z
   Started: 2026-01-13T10:02:00Z

✅ c3d4e5f678901234 - completed - completed-prd.json (priority: normal)
   Submitted: 2026-01-13T09:00:00Z
   Started: 2026-01-13T09:01:00Z
   Completed: 2026-01-13T09:45:00Z

❌ d4e5f67890123456 - failed - failed-prd.json (priority: low)
   Submitted: 2026-01-13T08:00:00Z
   Started: 2026-01-13T08:01:00Z
   Completed: 2026-01-13T08:30:00Z
```

**Status Icons**:
- ⏳ `pending`: Waiting to be processed
- ▶️  `running`: Currently being processed
- ✅ `completed`: Successfully completed
- ❌ `failed`: Failed during execution

### Cancel Task

Cancel a pending task:

```bash
./claude-loop.sh daemon cancel a1b2c3d4e5f67890
```

**Note**: Can only cancel pending tasks. Running tasks cannot be cancelled.

### Pause Queue

Pause queue processing:

```bash
./claude-loop.sh daemon pause
```

**Behavior**:
- Current running tasks continue to completion
- No new tasks are picked up from queue
- Queue remains accessible for viewing and submission

### Resume Queue

Resume queue processing:

```bash
./claude-loop.sh daemon resume
```

**Behavior**:
- Workers resume picking up tasks from queue
- Pending tasks are processed in priority order

## Queue Format

The queue is stored in `.claude-loop/daemon/queue.json` with the following structure:

```json
{
  "tasks": [
    {
      "id": "a1b2c3d4e5f67890",
      "prd_path": "/path/to/prd.json",
      "priority": "normal",
      "status": "pending",
      "submitted_at": "2026-01-13T10:00:00Z",
      "started_at": null,
      "completed_at": null,
      "result": null
    }
  ]
}
```

### Task Fields

- **id**: Unique 16-character task identifier
- **prd_path**: Absolute or relative path to PRD file
- **priority**: `high`, `normal`, or `low`
- **status**: `pending`, `running`, `completed`, or `failed`
- **submitted_at**: ISO 8601 timestamp of submission
- **started_at**: ISO 8601 timestamp when task started (null if not started)
- **completed_at**: ISO 8601 timestamp when task finished (null if not finished)
- **result**: Result status (`success` or error message)

## Worker Pool

Workers are independent processes that poll the queue for tasks. Each worker:

1. Checks for shutdown signal
2. Retrieves next pending task (sorted by priority and submission time)
3. Executes task by calling `claude-loop.sh --prd <prd_path>`
4. Updates task status (completed/failed)
5. Logs activity to daemon log
6. Repeats (polls every 5 seconds when idle)

### Concurrency

Multiple workers execute tasks concurrently:

```bash
# Start with 3 workers
./claude-loop.sh daemon start 3
```

**Benefits**:
- Process multiple PRDs simultaneously
- Maximize resource utilization
- Reduce total completion time

**Considerations**:
- Workers may compete for file access (use `fileScope` in PRDs)
- Memory usage scales with worker count
- Recommended: 1-4 workers depending on system resources

## Logging

All daemon activity is logged to `.claude-loop/daemon/daemon.log`:

```
[2026-01-13T10:00:00Z] [INFO] Starting daemon with 1 worker(s)
[2026-01-13T10:00:01Z] [INFO] Worker 1 started
[2026-01-13T10:00:05Z] [INFO] Task a1b2c3d4e5f67890 submitted: prd.json (priority: normal)
[2026-01-13T10:00:06Z] [INFO] Executing task a1b2c3d4e5f67890: prd.json
[2026-01-13T10:45:00Z] [INFO] Task a1b2c3d4e5f67890 completed successfully
[2026-01-13T11:00:00Z] [INFO] Stop command received
[2026-01-13T11:00:01Z] [INFO] Worker 1 received shutdown signal
[2026-01-13T11:00:02Z] [INFO] Worker 1 stopped
[2026-01-13T11:00:03Z] [INFO] Daemon stopped
```

### Log Levels

- **INFO**: Normal operations (start, stop, task execution)
- **ERROR**: Failures (task execution errors, queue errors)

## Graceful Shutdown

When stopping the daemon, it follows this process:

1. Creates shutdown signal file (`.claude-loop/daemon/shutdown`)
2. Sends TERM signal to daemon process
3. Workers finish current tasks
4. Workers exit after checking shutdown signal
5. Daemon cleans up PID file and shutdown signal
6. If timeout (30 seconds), force KILL signal

**During shutdown**:
- Running tasks complete normally
- Pending tasks remain in queue
- Queue is preserved and available on restart

## Process Management

### PID File

The daemon PID is stored in `.claude-loop/daemon/daemon.pid`:

```bash
# Check if daemon is running
if [ -f .claude-loop/daemon/daemon.pid ]; then
  pid=$(cat .claude-loop/daemon/daemon.pid)
  if kill -0 $pid 2>/dev/null; then
    echo "Daemon is running (PID: $pid)"
  fi
fi
```

### Lock File

Queue operations use a lock directory (`.claude-loop/daemon/daemon.lock`) to prevent concurrent modifications:

- Lock acquired before queue updates
- 10-second timeout for lock acquisition
- Automatic release after operation

## Signal Handling

The daemon responds to these signals:

- **TERM**: Graceful shutdown (finishes current tasks)
- **INT**: Graceful shutdown (Ctrl+C equivalent)
- **KILL**: Force shutdown (not recommended, may leave tasks in inconsistent state)

## Error Handling

### Task Execution Failures

If a task fails during execution:
- Task status set to `failed`
- Error logged to daemon log
- Next task picked up from queue
- Failed task remains in queue for inspection

### Daemon Crashes

If the daemon process crashes:
- Queue is preserved (persistent JSON file)
- PID file may be stale (cleaned up on next start)
- Restart daemon to resume processing

**Note**: Auto-restart on crash is planned for US-204 (Advanced Features).

## Use Cases

### Fire-and-Forget Workflow

Submit tasks and continue working:

```bash
# Submit multiple PRDs
./claude-loop.sh daemon submit feature-1.json high
./claude-loop.sh daemon submit feature-2.json normal
./claude-loop.sh daemon submit feature-3.json low

# Check progress later
./claude-loop.sh daemon queue
```

### Batch Processing

Process multiple features overnight:

```bash
# Start daemon with multiple workers
./claude-loop.sh daemon start 2

# Submit all PRDs
for prd in prds/*.json; do
  ./claude-loop.sh daemon submit "$prd"
done

# Daemon processes them in background
```

### Priority Management

Urgent fixes take precedence:

```bash
# Normal work
./claude-loop.sh daemon submit feature.json normal

# Urgent hotfix arrives
./claude-loop.sh daemon submit hotfix.json high

# Hotfix processed first, even if submitted later
```

## Integration with Other Features

### Quick Task Mode (US-203)

Quick tasks can be submitted to the daemon (future integration):

```bash
# Future: Submit quick task to daemon
./claude-loop.sh daemon submit-quick "fix auth bug" high
```

### Visual Progress Dashboard (US-207/208)

Dashboard displays daemon queue and progress (future integration):

```bash
# Future: Launch dashboard to monitor daemon
./claude-loop.sh dashboard start
```

### Notifications (US-206)

Get notified when tasks complete (future integration):

```bash
# Future: Submit with notification
./claude-loop.sh daemon submit prd.json --notify email
```

## Best Practices

### Worker Count

- **1 worker**: Sequential processing, lowest memory usage
- **2-3 workers**: Good balance for most systems
- **4+ workers**: High parallelism, requires sufficient system resources

### Priority Usage

- **High**: Urgent fixes, critical features, time-sensitive work
- **Normal**: Regular features, most work should be normal priority
- **Low**: Nice-to-have features, background work, low-priority refactoring

### Queue Management

- Check queue regularly: `./claude-loop.sh daemon queue`
- Clean up completed/failed tasks periodically
- Monitor daemon log for errors
- Use pause/resume for maintenance windows

### Graceful Shutdown

Always use `daemon stop` instead of killing the process:

```bash
# Good: Graceful shutdown
./claude-loop.sh daemon stop

# Bad: Force kill (may corrupt queue)
kill -9 $(cat .claude-loop/daemon/daemon.pid)
```

## Troubleshooting

### Daemon Won't Start

**Issue**: "Daemon is already running"

**Solution**:
```bash
# Check if actually running
./claude-loop.sh daemon status

# If PID file is stale, remove it
rm .claude-loop/daemon/daemon.pid

# Try starting again
./claude-loop.sh daemon start
```

### Tasks Stuck in Pending

**Issue**: Tasks not being processed

**Possible Causes**:
1. Daemon not running → `./claude-loop.sh daemon status`
2. Queue paused → `./claude-loop.sh daemon resume`
3. Worker crashed → Check daemon log, restart daemon

### Task Failed

**Issue**: Task shows failed status

**Solution**:
```bash
# Check daemon log for error details
tail -n 50 .claude-loop/daemon/daemon.log

# Review failed task
./claude-loop.sh daemon queue

# Re-submit after fixing issue
./claude-loop.sh daemon submit prd.json
```

### Cannot Acquire Lock

**Issue**: "Failed to acquire lock" error

**Solution**:
```bash
# Remove stale lock directory
rmdir .claude-loop/daemon/daemon.lock

# Try operation again
```

## Implementation Details

### File: `lib/daemon.sh`

Core daemon implementation with functions:

- `start_daemon(workers)`: Start daemon process
- `stop_daemon()`: Stop daemon gracefully
- `get_daemon_status()`: Check daemon status
- `submit_task(prd_path, priority)`: Add task to queue
- `show_queue()`: Display task queue
- `cancel_task(task_id)`: Cancel pending task
- `pause_queue()` / `resume_queue()`: Queue control
- `worker_loop(worker_id)`: Worker main loop
- `execute_task(task_id, prd_path)`: Execute task
- `acquire_lock()` / `release_lock()`: Queue locking

### Integration: `claude-loop.sh`

Daemon commands integrated into main script:

- Configuration variables (lines 107-112)
- Help text (lines 399-419)
- Argument parsing (lines 3164-3195)
- Mode handler: `run_task_daemon_mode()` (lines 1530-1600)

## Future Enhancements

### US-204: Quick Task Mode - Advanced Features
- Submit quick tasks to daemon
- Background quick task processing

### US-206: Daemon Mode - Notifications System
- Email notifications on completion
- Slack webhook integration
- Custom webhook support

### US-207/208: Visual Progress Dashboard
- Web UI for queue monitoring
- Real-time task progress
- Historical task analytics

### Auto-Restart on Crash
- Watchdog process for daemon
- Automatic restart on failure
- Crash report generation

## Acceptance Criteria

All acceptance criteria from US-205 have been met:

- ✅ Create daemon process: lib/daemon.sh runs as background service
- ✅ Implement task queue: .claude-loop/daemon/queue.json (append-only, FIFO)
- ✅ Add daemon subcommands: start, stop, status, submit, queue
- ✅ Implement worker pool: configurable workers (default: 1)
- ✅ Add PID file: .claude-loop/daemon/daemon.pid for process management
- ✅ Implement graceful shutdown: finish current task before stopping
- ✅ Add task submission: ./claude-loop.sh daemon submit prd.json
- ✅ Implement queue management: view, pause, resume, cancel tasks
- ✅ Add daemon logging: .claude-loop/daemon/daemon.log
- ✅ Support priority queuing: high/normal/low priority tasks
- ⏳ Handle daemon crashes: auto-restart on failure (planned for future)
- ✅ Document daemon mode in docs/features/daemon-mode.md

## Related Documentation

- [Quick Task Mode](./quick-task-mode.md) - Single task execution without PRD
- [Skills Architecture](./skills-architecture.md) - Deterministic operations framework
- [Phase 2 Foundations](../phase2/README.md) - Phase 2 overview

## Examples

### Example 1: Simple Batch Processing

```bash
# Start daemon
./claude-loop.sh daemon start

# Submit tasks
./claude-loop.sh daemon submit feature-auth.json
./claude-loop.sh daemon submit feature-payments.json
./claude-loop.sh daemon submit feature-notifications.json

# Check queue
./claude-loop.sh daemon queue

# Output:
# ▶️  abc123 - running - feature-auth.json (priority: normal)
# ⏳ def456 - pending - feature-payments.json (priority: normal)
# ⏳ ghi789 - pending - feature-notifications.json (priority: normal)

# Later... check completion
./claude-loop.sh daemon queue

# Output:
# ✅ abc123 - completed - feature-auth.json (priority: normal)
# ✅ def456 - completed - feature-payments.json (priority: normal)
# ▶️  ghi789 - running - feature-notifications.json (priority: normal)
```

### Example 2: Priority Handling

```bash
# Start daemon
./claude-loop.sh daemon start

# Submit low priority task
./claude-loop.sh daemon submit refactor.json low

# Submit normal priority task
./claude-loop.sh daemon submit feature.json normal

# Urgent hotfix arrives!
./claude-loop.sh daemon submit hotfix.json high

# Check queue - hotfix is first despite being submitted last
./claude-loop.sh daemon queue

# Output:
# ▶️  xyz789 - running - hotfix.json (priority: high)
# ⏳ abc123 - pending - feature.json (priority: normal)
# ⏳ def456 - pending - refactor.json (priority: low)
```

### Example 3: Multiple Workers

```bash
# Start daemon with 3 workers
./claude-loop.sh daemon start 3

# Submit multiple tasks
./claude-loop.sh daemon submit feature-1.json
./claude-loop.sh daemon submit feature-2.json
./claude-loop.sh daemon submit feature-3.json

# All 3 tasks run concurrently
./claude-loop.sh daemon queue

# Output:
# ▶️  task1 - running - feature-1.json (priority: normal)
# ▶️  task2 - running - feature-2.json (priority: normal)
# ▶️  task3 - running - feature-3.json (priority: normal)
```

## Conclusion

Daemon Mode provides a robust background task execution system for claude-loop, enabling fire-and-forget workflows with priority queuing, graceful shutdown, and comprehensive queue management. It serves as a foundation for Phase 2's enhanced user experience, integrating with quick task mode, visual dashboard, and notifications for a complete autonomous implementation system.
