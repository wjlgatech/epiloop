# Daemon Mode Tutorial

Learn how to use claude-loop's daemon mode to run tasks in the background with automatic queuing and notifications.

## Table of Contents

- [What is Daemon Mode?](#what-is-daemon-mode)
- [When to Use Daemon Mode](#when-to-use-daemon-mode)
- [Getting Started](#getting-started)
- [Starting and Stopping the Daemon](#starting-and-stopping-the-daemon)
- [Submitting Tasks](#submitting-tasks)
- [Priority Management](#priority-management)
- [Monitoring the Queue](#monitoring-the-queue)
- [Notification Configuration](#notification-configuration)
- [Common Workflows](#common-workflows)
- [Troubleshooting](#troubleshooting)

---

## What is Daemon Mode?

Daemon mode turns claude-loop into a background service that processes PRD tasks asynchronously. Instead of blocking your terminal while a task runs, you can submit tasks to a queue and continue working. The daemon processes tasks one by one (or in parallel with multiple workers) and can notify you when they complete.

### Key Benefits

- **Fire-and-forget**: Submit tasks and continue working immediately
- **Batch processing**: Queue multiple tasks to run overnight
- **Priority control**: Urgent tasks jump to the front of the queue
- **Notifications**: Get alerted via email or Slack when tasks complete
- **Graceful handling**: Daemon safely shuts down, preserving your queue

### How It Works

```
┌─────────────────┐
│   You Submit    │
│   Tasks to      │ → Submit PRD → ┌──────────────┐
│   Daemon Queue  │                │ Task Queue   │
└─────────────────┘                │ (Priority)   │
                                   └──────┬───────┘
┌─────────────────┐                       │
│   Daemon        │ ← Pick Next Task ─────┘
│   Worker        │
│   Processes     │
│   Tasks         │
└────────┬────────┘
         │
         ├─→ Execute PRD
         ├─→ Update Status
         └─→ Send Notification
```

---

## When to Use Daemon Mode

### Good Use Cases

**1. Long-Running Tasks**
Submit large PRDs that take hours to complete and let them run in the background.

```bash
./claude-loop.sh daemon submit large-feature.json --notify email
# Continue working while it processes overnight
```

**2. Batch Processing**
Queue multiple features to execute sequentially without supervision.

```bash
./claude-loop.sh daemon submit feature-1.json
./claude-loop.sh daemon submit feature-2.json
./claude-loop.sh daemon submit feature-3.json
# All three will execute in order
```

**3. Priority Workflows**
Normal work gets interrupted by urgent fixes.

```bash
# Regular feature in progress...
./claude-loop.sh daemon submit feature.json

# Urgent hotfix arrives!
./claude-loop.sh daemon submit hotfix.json high
# Hotfix processes next, even though submitted later
```

**4. Team Collaboration**
Multiple team members can submit tasks to a shared daemon.

```bash
# Team member 1
./claude-loop.sh daemon submit alice-feature.json

# Team member 2
./claude-loop.sh daemon submit bob-feature.json
# Both tasks process automatically
```

### When NOT to Use Daemon Mode

- **Quick iterations**: Use foreground mode or quick task mode for fast feedback
- **Debugging**: Easier to see errors in real-time without daemon
- **Single tasks**: Daemon overhead not worth it for one task
- **Interactive workflows**: Tasks requiring manual checkpoints

---

## Getting Started

### Prerequisites

1. **claude-loop installed** and working
2. **Python 3.8+** (for queue management)
3. **Disk space** for queue and logs

### Quick Start

```bash
# 1. Start the daemon
./claude-loop.sh daemon start

# 2. Submit a task
./claude-loop.sh daemon submit my-prd.json

# 3. Check status
./claude-loop.sh daemon status

# 4. Monitor queue
./claude-loop.sh daemon queue

# 5. Stop daemon when done
./claude-loop.sh daemon stop
```

That's it! You now have a background task processor running.

---

## Starting and Stopping the Daemon

### Starting the Daemon

**Basic Start (1 worker):**
```bash
./claude-loop.sh daemon start
```

Output:
```
Daemon started successfully (PID: 12345)
Worker: 1
Queue: .claude-loop/daemon/queue.json
Logs: .claude-loop/daemon/daemon.log
```

**Start with Multiple Workers:**
```bash
# 3 workers for parallel processing
./claude-loop.sh daemon start 3
```

This allows up to 3 tasks to run concurrently. Useful for batch processing multiple independent features.

**Verify It's Running:**
```bash
./claude-loop.sh daemon status
```

Output:
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

### Stopping the Daemon

**Graceful Stop:**
```bash
./claude-loop.sh daemon stop
```

This:
- Signals workers to stop accepting new tasks
- Waits for current tasks to complete (up to 30 seconds)
- Preserves queue for next startup
- Cleans up process IDs

Output:
```
Stopping daemon (PID: 12345)...
Waiting for tasks to complete...
Daemon stopped successfully
```

**What Happens to Running Tasks?**

The daemon gracefully finishes the current task before stopping. Pending tasks remain in the queue and will be processed when you restart the daemon.

**Force Stop (Not Recommended):**
```bash
# Only if graceful stop fails
kill -9 $(cat .claude-loop/daemon/daemon.pid)
```

Note: Force stopping may leave tasks in an inconsistent state.

### Checking Status

```bash
./claude-loop.sh daemon status
```

Possible states:
- **Running**: Daemon is active and processing tasks
- **Stopped**: No daemon process found
- **Stale PID**: PID file exists but process is dead (run `daemon stop` to clean up)

---

## Submitting Tasks

### Basic Submission

```bash
./claude-loop.sh daemon submit path/to/prd.json
```

Output:
```
Task submitted successfully (ID: a1b2c3d4e5f67890)
Priority: normal
Position in queue: 3
```

The task ID is a unique 16-character identifier you can use to track or cancel the task.

### Submission with Options

```bash
# High priority (processes first)
./claude-loop.sh daemon submit urgent.json high

# Low priority (processes last)
./claude-loop.sh daemon submit background-work.json low

# With notifications
./claude-loop.sh daemon submit feature.json --notify email

# Combine options
./claude-loop.sh daemon submit critical.json high --notify email,slack
```

### What Happens After Submission?

1. **Task added to queue** with timestamp and priority
2. **Worker picks up task** (if available) or waits in queue
3. **Execution begins** using standard PRD processing
4. **Status updates** are logged to `.claude-loop/daemon/daemon.log`
5. **Notification sent** when task completes (if configured)

### Submitting Multiple Tasks

```bash
# Script to batch submit
for prd in prds/*.json; do
    ./claude-loop.sh daemon submit "$prd"
done
```

Or manually:
```bash
./claude-loop.sh daemon submit feature-auth.json
./claude-loop.sh daemon submit feature-payments.json
./claude-loop.sh daemon submit feature-notifications.json
```

All tasks will execute in order (by priority, then submission time).

---

## Priority Management

### Priority Levels

| Priority | When to Use | Queue Position |
|----------|-------------|----------------|
| **high** | Critical bugs, urgent features, time-sensitive work | Front of queue |
| **normal** | Regular features (default) | Middle of queue (FIFO) |
| **low** | Nice-to-have features, cleanup, documentation | End of queue |

### How Priority Works

Tasks are processed in this order:
1. All **high** priority tasks (oldest first)
2. All **normal** priority tasks (oldest first)
3. All **low** priority tasks (oldest first)

**Example:**

```bash
# Current time: 10:00
./claude-loop.sh daemon submit task-1.json low       # Submitted: 10:00

# Current time: 10:01
./claude-loop.sh daemon submit task-2.json normal    # Submitted: 10:01

# Current time: 10:02
./claude-loop.sh daemon submit task-3.json high      # Submitted: 10:02

# Processing order: task-3 (high), task-2 (normal), task-1 (low)
```

### Changing Priority (Not Supported)

Currently, you cannot change priority after submission. If you need to reprioritize:

```bash
# Cancel low priority task
./claude-loop.sh daemon cancel <task-id>

# Resubmit with higher priority
./claude-loop.sh daemon submit task.json high
```

### Priority Best Practices

**Use High Priority For:**
- Production hotfixes
- Customer-blocking issues
- Deadline-driven features
- Security patches

**Use Normal Priority For:**
- Regular feature development (90% of work)
- Refactoring
- Performance improvements
- Most day-to-day tasks

**Use Low Priority For:**
- Technical debt cleanup
- Documentation updates
- Experimental features
- Nice-to-have improvements

---

## Monitoring the Queue

### View Current Queue

```bash
./claude-loop.sh daemon queue
```

Output:
```
Task Queue:

⏳ a1b2c3d4 - pending - feature-auth.json (priority: high)
   Submitted: 2026-01-13T10:00:00Z

▶️  b2c3d4e5 - running - feature-payments.json (priority: normal)
   Submitted: 2026-01-13T10:01:00Z
   Started: 2026-01-13T10:05:00Z

✅ c3d4e5f6 - completed - feature-notifications.json (priority: normal)
   Submitted: 2026-01-13T09:00:00Z
   Started: 2026-01-13T09:05:00Z
   Completed: 2026-01-13T09:45:00Z

❌ d4e5f678 - failed - buggy-feature.json (priority: low)
   Submitted: 2026-01-13T08:00:00Z
   Started: 2026-01-13T08:05:00Z
   Completed: 2026-01-13T08:30:00Z
   Error: Execution failed at story US-003
```

### Status Icons

- ⏳ **pending**: Waiting to be processed
- ▶️ **running**: Currently executing
- ✅ **completed**: Successfully finished
- ❌ **failed**: Execution failed (check logs)

### Task Details

Each task shows:
- **ID**: First 8 characters of task ID
- **Status**: Current state
- **PRD file**: Path to PRD
- **Priority**: high/normal/low
- **Timestamps**: Submitted, started, completed times

### Watching the Queue

Monitor queue in real-time:

```bash
# Update every 5 seconds
watch -n 5 ./claude-loop.sh daemon queue

# Or manually in a loop
while true; do
    clear
    ./claude-loop.sh daemon queue
    sleep 5
done
```

### Checking Daemon Logs

```bash
# View recent activity
tail -f .claude-loop/daemon/daemon.log

# Search for specific task
grep "a1b2c3d4" .claude-loop/daemon/daemon.log

# View errors only
grep "ERROR" .claude-loop/daemon/daemon.log
```

### Pausing and Resuming

**Pause Queue** (finish current task, hold new ones):
```bash
./claude-loop.sh daemon pause
```

**Resume Queue**:
```bash
./claude-loop.sh daemon resume
```

**Use Cases:**
- Maintenance windows
- System resource management
- Testing new configurations

### Canceling Tasks

**Cancel a Pending Task:**
```bash
./claude-loop.sh daemon cancel a1b2c3d4e5f67890
```

Note: You can only cancel **pending** tasks. Running tasks cannot be cancelled (let them finish or stop the daemon).

---

## Notification Configuration

Get notified when tasks complete, fail, or require action.

### Supported Channels

1. **Email** (sendmail or SMTP)
2. **Slack** (webhook integration)
3. **Generic Webhook** (any HTTP endpoint)

### Initial Setup

```bash
# Initialize notification system
./lib/notifications.sh init
```

This creates:
- `.claude-loop/daemon/notifications.json` (configuration)
- `templates/notifications/` (message templates)

### Email Configuration

**Option 1: Sendmail (Simple)**

Edit `.claude-loop/daemon/notifications.json`:
```json
{
  "email": {
    "enabled": true,
    "method": "sendmail",
    "from": "claude-loop@localhost",
    "to": ["you@example.com"]
  }
}
```

Requirements: `sendmail` installed and configured on your system.

**Option 2: SMTP (Gmail, Office365, etc.)**

```json
{
  "email": {
    "enabled": true,
    "method": "smtp",
    "from": "your-email@gmail.com",
    "to": ["recipient@example.com"],
    "smtp": {
      "host": "smtp.gmail.com",
      "port": 587,
      "username": "your-email@gmail.com",
      "password": "your-app-password",
      "tls": true
    }
  }
}
```

For Gmail: Use [App Passwords](https://myaccount.google.com/apppasswords), not your regular password.

### Slack Configuration

1. **Create Slack Incoming Webhook:**
   - Go to https://api.slack.com/apps
   - Create app → Enable "Incoming Webhooks"
   - Add webhook to workspace
   - Copy webhook URL

2. **Configure claude-loop:**
```json
{
  "slack": {
    "enabled": true,
    "webhook_url": "https://hooks.slack.com/services/YOUR/WEBHOOK/URL",
    "channel": "#dev-notifications",
    "username": "claude-loop",
    "icon_emoji": ":robot_face:"
  }
}
```

### Generic Webhook Configuration

```json
{
  "webhook": {
    "enabled": true,
    "url": "https://your-api.com/webhook",
    "method": "POST",
    "auth": {
      "type": "bearer",
      "token": "your-api-token"
    }
  }
}
```

The webhook receives JSON:
```json
{
  "task_id": "abc123",
  "status": "completed",
  "project": "my-project",
  "stories_completed": 5,
  "time_taken": "15m 30s",
  "cost": "$1.25"
}
```

### Testing Notifications

```bash
# Test email
./lib/notifications.sh test-email you@example.com

# Test Slack
./lib/notifications.sh test-slack

# Test webhook
./lib/notifications.sh test-webhook
```

### Using Notifications

```bash
# Submit with email notification
./claude-loop.sh daemon submit prd.json --notify email

# Submit with multiple channels
./claude-loop.sh daemon submit prd.json --notify email,slack

# High priority with notifications
./claude-loop.sh daemon submit urgent.json high --notify email,slack
```

### Notification Messages

**On Success:**
- Email subject: `claude-loop: Task abc123 completed`
- Message includes: stories completed, time taken, estimated cost

**On Failure:**
- Email subject: `claude-loop: Task abc123 failed`
- Message includes: error details, failed story, suggestions

**On Checkpoint:**
- Email subject: `claude-loop: Task abc123 requires approval`
- Message includes: reason for checkpoint, next steps

### Customizing Templates

Edit templates in `templates/notifications/`:
- `success.txt` - Task completed successfully
- `failure.txt` - Task failed
- `checkpoint.txt` - Manual approval required

Variables available:
- `{{TASK_ID}}` - Task identifier
- `{{PROJECT}}` - Project name from PRD
- `{{STORIES_COMPLETED}}` - Number completed
- `{{TIME_TAKEN}}` - Elapsed time
- `{{COST}}` - Estimated cost

---

## Common Workflows

### Workflow 1: Overnight Batch Processing

Run multiple features while you sleep.

```bash
# Before leaving for the day
./claude-loop.sh daemon start

# Submit all your PRDs
./claude-loop.sh daemon submit feature-1.json --notify email
./claude-loop.sh daemon submit feature-2.json --notify email
./claude-loop.sh daemon submit feature-3.json --notify email

# Check status
./claude-loop.sh daemon queue

# Go home, check email in the morning for results
```

### Workflow 2: Urgent Hotfix

Normal work gets interrupted by critical bug.

```bash
# You have a regular feature running
./claude-loop.sh daemon submit regular-feature.json

# Critical production bug reported!
./claude-loop.sh daemon submit hotfix.json high --notify slack

# Hotfix processes immediately
# Team gets Slack notification when fixed
```

### Workflow 3: Weekly Refactoring

Queue low-priority cleanup tasks.

```bash
# Every Friday, queue technical debt work
./claude-loop.sh daemon submit cleanup-auth.json low
./claude-loop.sh daemon submit update-docs.json low
./claude-loop.sh daemon submit refactor-utils.json low

# Runs over the weekend, low priority ensures
# it doesn't interfere with urgent work
```

### Workflow 4: Multi-Worker Parallel Processing

Process independent features simultaneously.

```bash
# Start daemon with 3 workers
./claude-loop.sh daemon start 3

# Submit 3 independent features
./claude-loop.sh daemon submit feature-auth.json
./claude-loop.sh daemon submit feature-payments.json
./claude-loop.sh daemon submit feature-notifications.json

# All 3 run in parallel (if they don't touch same files)
```

### Workflow 5: CI/CD Integration

Integrate daemon into your deployment pipeline.

```bash
#!/bin/bash
# deploy.sh

# Start daemon if not running
./claude-loop.sh daemon status || ./claude-loop.sh daemon start

# Submit deployment tasks
./claude-loop.sh daemon submit pre-deploy.json high --notify webhook
./claude-loop.sh daemon submit deploy-staging.json high --notify webhook
./claude-loop.sh daemon submit deploy-production.json high --notify webhook

# Webhook triggers next pipeline stage
```

---

## Troubleshooting

### Daemon Won't Start

**Problem:** `Daemon is already running` but status shows stopped

**Solution:**
```bash
# Check if PID file is stale
cat .claude-loop/daemon/daemon.pid

# If process doesn't exist, remove PID file
rm .claude-loop/daemon/daemon.pid

# Try starting again
./claude-loop.sh daemon start
```

### Tasks Stuck in Pending

**Problem:** Tasks submitted but never execute

**Check 1:** Is daemon running?
```bash
./claude-loop.sh daemon status
```

**Check 2:** Is queue paused?
```bash
# Resume if paused
./claude-loop.sh daemon resume
```

**Check 3:** Check daemon logs for errors
```bash
tail -50 .claude-loop/daemon/daemon.log
```

**Check 4:** Worker might have crashed
```bash
# Restart daemon
./claude-loop.sh daemon stop
./claude-loop.sh daemon start
```

### Task Failed

**Problem:** Task shows failed status

**Investigation:**
```bash
# 1. Check daemon log
grep "TASK_ID" .claude-loop/daemon/daemon.log

# 2. Check PRD execution logs
ls -la .claude-loop/execution_log.jsonl

# 3. Review queue entry
./claude-loop.sh daemon queue | grep TASK_ID
```

**Common Causes:**
- Invalid PRD JSON
- Missing dependencies
- File conflicts
- API rate limits
- Test failures

**Solution:** Fix the issue and resubmit
```bash
./claude-loop.sh daemon submit fixed-prd.json
```

### Notifications Not Sending

**Problem:** No email/Slack messages received

**Check 1:** Configuration file
```bash
cat .claude-loop/daemon/notifications.json
```

**Check 2:** Test notifications
```bash
./lib/notifications.sh test-email your@email.com
./lib/notifications.sh test-slack
```

**Check 3:** Check notification logs
```bash
tail -50 .claude-loop/daemon/notifications.log
```

**Check 4:** Verify submission included notification
```bash
# Make sure you used --notify flag
./claude-loop.sh daemon submit prd.json --notify email
```

### Queue File Corrupted

**Problem:** Daemon crashes on startup, queue unreadable

**Recovery:**
```bash
# 1. Backup current queue
cp .claude-loop/daemon/queue.json .claude-loop/daemon/queue.json.backup

# 2. Check JSON validity
python3 -m json.tool .claude-loop/daemon/queue.json

# 3. If corrupted, reset queue (LOSES PENDING TASKS!)
echo '{"tasks": []}' > .claude-loop/daemon/queue.json

# 4. Restart daemon
./claude-loop.sh daemon start
```

### High Memory Usage

**Problem:** Daemon consuming too much memory with multiple workers

**Solutions:**
1. Reduce worker count:
```bash
./claude-loop.sh daemon stop
./claude-loop.sh daemon start 1
```

2. Monitor memory usage:
```bash
ps aux | grep daemon
```

3. Use lower priority to reduce load:
```bash
./claude-loop.sh daemon submit prd.json low
```

---

## Best Practices

### 1. Start Small

Begin with a single worker and normal priority for all tasks. Add complexity as you understand the system.

### 2. Use Meaningful PRD Names

```bash
# Good
./claude-loop.sh daemon submit feature-user-auth.json
./claude-loop.sh daemon submit hotfix-login-bug.json

# Bad
./claude-loop.sh daemon submit prd1.json
./claude-loop.sh daemon submit temp.json
```

### 3. Monitor Regularly

Check queue and logs periodically, especially when running overnight:

```bash
# Morning check
./claude-loop.sh daemon queue
tail -100 .claude-loop/daemon/daemon.log
```

### 4. Clean Up Completed Tasks

Periodically clear old completed/failed tasks to keep queue manageable.

### 5. Use Notifications Wisely

Configure notifications for:
- High priority tasks (always)
- Long-running tasks (useful to know when done)
- Failed tasks (need investigation)

Skip notifications for:
- Low priority background work
- Tasks you'll check manually

### 6. Graceful Shutdowns

Always use `daemon stop` instead of killing the process:

```bash
# Good
./claude-loop.sh daemon stop

# Bad
kill -9 $(cat .claude-loop/daemon/daemon.pid)
```

### 7. Test PRDs First

Test PRDs in foreground mode before submitting to daemon:

```bash
# Test first
./claude-loop.sh --prd test-feature.json

# If it works, submit to daemon
./claude-loop.sh daemon submit production-feature.json
```

---

## Next Steps

- **Learn Quick Task Mode**: [Quick Task Tutorial](./quick-task-tutorial.md)
- **Monitor with Dashboard**: [Dashboard Tutorial](./dashboard.md)
- **Configure Notifications**: [Notifications Guide](../features/daemon-notifications.md)
- **Advanced Features**: [Phase 2 Documentation](../phase2/README.md)

---

## See Also

- [Daemon Mode Reference](../features/daemon-mode.md)
- [Notification System](../features/daemon-notifications.md)
- [CLI Reference](../reference/cli-reference.md)
- [Troubleshooting Guide](../troubleshooting/phase2-troubleshooting.md)
