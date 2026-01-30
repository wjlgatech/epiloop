# Phase 2 Troubleshooting Guide

Comprehensive troubleshooting guide for Phase 2 features: Skills Framework, Quick Task Mode, Daemon Mode, Dashboard, and Notifications.

## Table of Contents

- [General Issues](#general-issues)
- [Skills Framework Issues](#skills-framework-issues)
- [Quick Task Mode Problems](#quick-task-mode-problems)
- [Daemon Mode Issues](#daemon-mode-issues)
- [Dashboard Connectivity Problems](#dashboard-connectivity-problems)
- [Notification Failures](#notification-failures)
- [Performance Issues](#performance-issues)
- [Common Error Messages](#common-error-messages)

---

## General Issues

### Phase 2 Features Not Available

**Symptom**: `--skill`, `quick`, `daemon`, or `dashboard` commands not recognized

**Check Version:**
```bash
./claude-loop.sh --version
# Should show v2.0.0 or higher
```

**Solution:**
```bash
# Pull latest changes
git pull origin main

# Or download latest release
# https://github.com/your-repo/claude-loop/releases
```

### Permission Denied Errors

**Symptom**: `Permission denied` when executing scripts

**Solution:**
```bash
# Make scripts executable
chmod +x claude-loop.sh
chmod +x lib/*.sh
chmod +x skills/*/scripts/*
```

### Missing Dependencies

**Symptom**: `command not found: python3` or similar

**Check Python:**
```bash
python3 --version
# Should be 3.8 or higher
```

**Check Flask (for dashboard):**
```bash
pip install flask flask-cors
```

**Check Other Dependencies:**
```bash
# jq (for JSON parsing)
which jq || sudo apt-get install jq  # or brew install jq

# curl (for webhooks)
which curl || sudo apt-get install curl
```

---

## Skills Framework Issues

### Skill Not Found

**Symptom**: `Error: Skill 'my-skill' not found`

**Diagnostic Steps:**

1. **Check skill exists:**
   ```bash
   ls -la skills/my-skill/
   # Should show SKILL.md and optionally scripts/
   ```

2. **List all skills:**
   ```bash
   ./claude-loop.sh --list-skills
   # Verify your skill appears in the list
   ```

3. **Check SKILL.md format:**
   ```bash
   head -20 skills/my-skill/SKILL.md
   # Should start with: # /my-skill - Description
   ```

**Common Causes:**

- Skill name mismatch (case-sensitive)
- Missing SKILL.md file
- Incorrect directory structure
- Malformed metadata

**Solution:**

```bash
# Ensure correct structure
mkdir -p skills/my-skill/scripts
touch skills/my-skill/SKILL.md

# Clear cache and reload
rm -rf .claude-loop/skills-cache/
./claude-loop.sh --list-skills
```

### Skill Script Not Executable

**Symptom**: `Error: Skill 'my-skill' has no executable script`

**Check Script:**
```bash
ls -l skills/my-skill/scripts/
# Should show main.sh, main.py, or main.js
```

**Make Executable:**
```bash
chmod +x skills/my-skill/scripts/main.sh
```

**Verify Shebang:**
```bash
head -1 skills/my-skill/scripts/main.sh
# Should be: #!/bin/bash or #!/usr/bin/env bash
```

### Skill Execution Fails

**Symptom**: `Script exited with code 1` or other error

**Debug Script:**
```bash
# Run script directly
skills/my-skill/scripts/main.sh arg1 arg2

# Check stderr
skills/my-skill/scripts/main.sh 2>&1 | tee error.log
```

**Common Issues:**

1. **Missing Dependencies:**
   ```bash
   # For Python scripts
   pip install -r skills/my-skill/requirements.txt

   # For Node.js scripts
   npm install
   ```

2. **Wrong Working Directory:**
   ```bash
   # Skills run from project root
   # Use absolute paths in scripts
   SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
   ```

3. **Environment Variables:**
   ```bash
   # Check what environment the script needs
   cat skills/my-skill/SKILL.md | grep -A 10 "Environment"
   ```

### Skills Cache Issues

**Symptom**: Changes to SKILL.md not reflected

**Solution:**
```bash
# Clear cache
rm -rf .claude-loop/skills-cache/

# Force reload
./claude-loop.sh --list-skills
```

---

## Quick Task Mode Problems

### Plan Approval Timeout

**Symptom**: Quick task hangs at "Waiting for approval..."

**Check Timeout:**
```bash
# Default is 600 seconds (10 minutes)
echo $QUICK_TASK_TIMEOUT
```

**Increase Timeout:**
```bash
export QUICK_TASK_TIMEOUT=1800  # 30 minutes
./claude-loop.sh quick "your task"
```

**Bypass Approval (for scripts):**
```bash
# Auto-approve (use with caution)
echo "y" | ./claude-loop.sh quick "your task"
```

### Task Complexity Too High

**Symptom**: `Task complexity score: 85 (too complex for quick mode)`

**Options:**

1. **Use Escalation:**
   ```bash
   ./claude-loop.sh quick "complex task" --escalate
   # Will offer to convert to PRD
   ```

2. **Break into Smaller Tasks:**
   ```bash
   ./claude-loop.sh quick "part 1 of task"
   ./claude-loop.sh quick "part 2 of task"
   ```

3. **Use PRD Mode:**
   ```bash
   # Create PRD for complex work
   ./claude-loop.sh --prd complex-feature.json
   ```

### Task Execution Hangs

**Symptom**: Task starts but never completes

**Check Logs:**
```bash
# Find task ID
ls -lt .claude-loop/quick-tasks/

# View logs
tail -f .claude-loop/quick-tasks/{timestamp}_{task}/logs/combined.log
```

**Common Causes:**

1. **API Timeout**: Increase `QUICK_TASK_TIMEOUT`
2. **Infinite Loop**: Check logs for repeated messages
3. **Waiting for Input**: Ensure task doesn't require user input

**Force Stop:**
```bash
# Find process
ps aux | grep quick-task

# Kill process
kill <PID>
```

### Continue Mode Not Working

**Symptom**: `--continue` doesn't resume failed task

**Check for Checkpoint:**
```bash
# Last failed task should have checkpoint
ls -la .claude-loop/quick-tasks/*/checkpoint.json
```

**Common Issues:**

1. **No Checkpoint Created**: Task failed before first checkpoint (< 5 steps)
2. **Checkpoint Corrupted**: Delete and retry without continue
3. **Wrong Directory**: Run from same directory as original task

**Solution:**
```bash
# If no checkpoint, start fresh
./claude-loop.sh quick "same task again"
```

### Template Not Found

**Symptom**: `Template 'custom' not found`

**Check Templates:**
```bash
ls templates/quick-tasks/
# Should show: refactor.json, add-tests.json, fix-bug.json
```

**Create Custom Template:**
```bash
cat > templates/quick-tasks/custom.json << 'EOF'
{
  "name": "custom",
  "description": "My custom template",
  "steps": [
    {"id": 1, "action": "Read files", "type": "read"},
    {"id": 2, "action": "Make changes", "type": "write"},
    {"id": 3, "action": "Verify", "type": "verify"}
  ],
  "estimated_complexity": "medium"
}
EOF
```

### History Not Showing

**Symptom**: `./claude-loop.sh quick history` shows no tasks

**Check Audit Log:**
```bash
cat .claude-loop/quick-tasks/quick-tasks.jsonl
# Should contain JSON lines
```

**If Empty:**
- No quick tasks have been executed yet
- Audit log was deleted
- Task execution didn't complete

**Recreate:**
```bash
# Audit log is created on first quick task execution
./claude-loop.sh quick "test task"
```

---

## Daemon Mode Issues

### Daemon Won't Start

**Symptom**: `Daemon is already running` but status shows stopped

**Check Stale PID:**
```bash
# Read PID file
cat .claude-loop/daemon/daemon.pid

# Check if process exists
ps -p $(cat .claude-loop/daemon/daemon.pid)
```

**Clean Up:**
```bash
# Remove stale PID
rm .claude-loop/daemon/daemon.pid
rm .claude-loop/daemon/daemon.lock

# Start again
./claude-loop.sh daemon start
```

**Check Port Conflicts:**
```bash
# If daemon uses a port
lsof -i :PORT_NUMBER
```

### Tasks Stuck in Pending

**Symptom**: Tasks submitted but never execute

**Diagnostic Steps:**

1. **Check Daemon Status:**
   ```bash
   ./claude-loop.sh daemon status
   # Should show "running"
   ```

2. **Check Queue:**
   ```bash
   ./claude-loop.sh daemon queue
   # Verify task is in queue
   ```

3. **Check Daemon Logs:**
   ```bash
   tail -50 .claude-loop/daemon/daemon.log
   ```

**Common Causes:**

1. **Daemon Not Running:**
   ```bash
   ./claude-loop.sh daemon start
   ```

2. **Queue Paused:**
   ```bash
   ./claude-loop.sh daemon resume
   ```

3. **Worker Crashed:**
   ```bash
   # Restart daemon
   ./claude-loop.sh daemon stop
   ./claude-loop.sh daemon start
   ```

4. **Lock File Issue:**
   ```bash
   # Remove stuck lock
   rmdir .claude-loop/daemon/daemon.lock 2>/dev/null
   ```

### Task Failed Unexpectedly

**Symptom**: Task shows status "failed" in queue

**View Error:**
```bash
./claude-loop.sh daemon queue
# Look for task with ❌ status
# Shows error message
```

**Check Daemon Logs:**
```bash
grep "TASK_ID" .claude-loop/daemon/daemon.log
```

**Common Causes:**

1. **Invalid PRD**: Validate PRD structure
   ```bash
   python3 -m json.tool prd.json
   ./claude-loop.sh --skill prd-validator --skill-arg prd.json
   ```

2. **Missing Files**: Check PRD references existing files
3. **API Errors**: Rate limits, token issues
4. **Test Failures**: Check test logs

**Retry:**
```bash
# Fix issue, then resubmit
./claude-loop.sh daemon submit fixed-prd.json
```

### Cannot Cancel Task

**Symptom**: `./claude-loop.sh daemon cancel TASK_ID` fails

**Check Task Status:**
```bash
./claude-loop.sh daemon queue | grep TASK_ID
```

**Restriction**: You can only cancel **pending** tasks, not **running** ones.

**For Running Tasks:**
```bash
# Option 1: Wait for completion
# Option 2: Stop daemon (loses current work)
./claude-loop.sh daemon stop
```

### Queue File Corrupted

**Symptom**: Daemon crashes on startup with JSON parse error

**Backup and Validate:**
```bash
# Backup queue
cp .claude-loop/daemon/queue.json .claude-loop/daemon/queue.json.backup

# Validate JSON
python3 -m json.tool .claude-loop/daemon/queue.json
```

**If Corrupted:**
```bash
# Reset queue (LOSES PENDING TASKS!)
echo '{"tasks": []}' > .claude-loop/daemon/queue.json

# Or manually fix JSON
nano .claude-loop/daemon/queue.json
```

---

## Dashboard Connectivity Problems

### Cannot Connect to Dashboard

**Symptom**: Browser shows "Failed to connect"

**Check Server:**
```bash
./claude-loop.sh dashboard status
# Should show "running"
```

**Check URL:**
```bash
# Default
http://localhost:8080

# Custom port (check status output)
http://localhost:CUSTOM_PORT
```

**Check Firewall:**
```bash
# Test locally
curl http://localhost:8080/api/health

# If remote access
curl http://YOUR_IP:8080/api/health
```

**Restart Dashboard:**
```bash
./claude-loop.sh dashboard stop
./claude-loop.sh dashboard start
```

### Authentication Failed

**Symptom**: "Invalid authentication token" error

**Get Token:**
```bash
cat .claude-loop/dashboard/auth_token.txt
```

**Generate New Token:**
```bash
./claude-loop.sh dashboard generate-token
```

**Clear Browser Cache:**
```javascript
// In browser console (F12)
localStorage.removeItem('auth_token');
location.reload();
```

**Check Token Format:**
- No spaces before/after
- Case-sensitive
- Should be alphanumeric

### Dashboard Shows No Data

**Symptom**: Dashboard loads but displays no stories/logs

**Check Execution:**
```bash
# Verify PRD exists
ls -la prd.json

# Start an execution
./claude-loop.sh --prd prd.json

# Or daemon task
./claude-loop.sh daemon submit prd.json
```

**Check API Responses:**
```bash
# Get auth token
TOKEN=$(cat .claude-loop/dashboard/auth_token.txt)

# Test API
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:8080/api/status
```

### SSE Connection Fails

**Symptom**: "Connection lost, reconnecting..." message persists

**Check Browser Support:**
- Chrome 90+, Firefox 88+, Safari 14+ support EventSource
- Try different browser

**Check Ad Blockers:**
- Some ad blockers block EventSource
- Disable or whitelist `localhost:8080`

**Check CORS:**
```bash
# Dashboard logs should not show CORS errors
tail -f .claude-loop/dashboard/dashboard.log
```

**Manual Test:**
```javascript
// In browser console
const es = new EventSource('http://localhost:8080/api/stream?token=YOUR_TOKEN');
es.onmessage = (e) => console.log(e.data);
es.onerror = (e) => console.error(e);
```

### Dashboard Port Already in Use

**Symptom**: `Address already in use` error on startup

**Find Process:**
```bash
lsof -i :8080
# Shows which process is using the port
```

**Options:**

1. **Kill Existing Process:**
   ```bash
   kill <PID>
   ./claude-loop.sh dashboard start
   ```

2. **Use Different Port:**
   ```bash
   ./claude-loop.sh dashboard start --port 9000
   ```

### High Memory Usage

**Symptom**: Browser tab using excessive RAM

**Solutions:**

1. **Clear Logs:**
   Click "Clear" button in logs tab

2. **Increase Refresh Rate:**
   Settings → Refresh Rate → 10 seconds

3. **Close Unused Tabs:**
   Only keep one dashboard tab open

4. **Restart Browser:**
   ```bash
   # Close all browser windows, then reopen
   ```

---

## Notification Failures

### Email Notifications Not Sending

**Symptom**: Task completes but no email received

**Check Configuration:**
```bash
cat .claude-loop/daemon/notifications.json | grep -A 10 email
```

**Test Email:**
```bash
./lib/notifications.sh test-email your@email.com
```

**Common Issues:**

1. **Sendmail Not Installed:**
   ```bash
   which sendmail || sudo apt-get install sendmail
   ```

2. **SMTP Configuration Wrong:**
   - Verify host, port, username, password
   - For Gmail: Use app-specific password
   - Check TLS setting (usually true for port 587)

3. **Spam Folder:**
   Check spam/junk folder

4. **Email Disabled:**
   ```json
   {
     "email": {
       "enabled": true  // ← Must be true
     }
   }
   ```

**Check Logs:**
```bash
grep -i email .claude-loop/daemon/notifications.log
```

### Slack Webhook Failing

**Symptom**: No Slack messages received

**Test Webhook:**
```bash
./lib/notifications.sh test-slack
```

**Verify Webhook URL:**
```bash
# Manual test
curl -X POST \
  -H 'Content-Type: application/json' \
  -d '{"text":"Test from claude-loop"}' \
  YOUR_WEBHOOK_URL
```

**Common Issues:**

1. **Invalid URL**: Regenerate webhook in Slack settings
2. **Expired Webhook**: Old webhooks may stop working
3. **Rate Limit**: Slack limits webhook frequency
4. **Channel Permissions**: Verify webhook can post to channel

**Check Configuration:**
```bash
cat .claude-loop/daemon/notifications.json | grep -A 10 slack
```

### Generic Webhook Errors

**Symptom**: Webhook notification fails

**Test Endpoint:**
```bash
./lib/notifications.sh test-webhook
```

**Manual Test:**
```bash
curl -X POST \
  -H 'Content-Type: application/json' \
  -H 'Authorization: Bearer YOUR_TOKEN' \
  -d '{"task_id":"test","status":"completed"}' \
  YOUR_ENDPOINT
```

**Common Issues:**

1. **Auth Token Wrong**: Verify bearer token
2. **SSL Certificate**: Check endpoint has valid HTTPS cert
3. **Firewall**: Endpoint might block requests
4. **Request Format**: Check endpoint expects JSON POST

**Check Logs:**
```bash
grep -i webhook .claude-loop/daemon/notifications.log
```

### Notifications Not Triggered

**Symptom**: Task completes but no notification sent

**Verify Submission:**
```bash
# Make sure you used --notify flag
./claude-loop.sh daemon submit prd.json --notify email
```

**Check Daemon Logs:**
```bash
grep "notification" .claude-loop/daemon/daemon.log
```

**Verify Channels Enabled:**
```bash
cat .claude-loop/daemon/notifications.json
# Check "enabled": true for your channels
```

---

## Performance Issues

### High Token Usage

**Symptom**: Phase 2 features using more tokens than expected

**Check Token Costs:**
```bash
# In dashboard, view Cost Tracker tab
# Or check execution logs
cat .claude-loop/execution_log.jsonl
```

**Optimization Tips:**

1. **Use Skills Instead of Prompts:**
   ```bash
   # High tokens
   ./claude-loop.sh --prd "validate this PRD file"

   # Zero tokens
   ./claude-loop.sh --skill prd-validator --skill-arg prd.json
   ```

2. **Use Quick Mode for Simple Tasks:**
   ```bash
   # Lower overhead than PRD mode
   ./claude-loop.sh quick "fix typo in README"
   ```

3. **Check Complexity Detection:**
   ```bash
   # Don't use quick mode for complex tasks
   # It will retry and waste tokens
   ./claude-loop.sh quick "complex task" --escalate
   ```

### Slow Execution

**Symptom**: Tasks taking longer than expected

**Check Daemon Workers:**
```bash
# Single worker processes sequentially
./claude-loop.sh daemon status

# Use multiple workers for parallel processing
./claude-loop.sh daemon stop
./claude-loop.sh daemon start 3
```

**Check API Rate Limits:**
- Claude API has rate limits
- Check logs for "rate limit" errors
- Space out task submissions

**Check System Resources:**
```bash
# CPU usage
top

# Memory usage
free -h

# Disk I/O
iostat
```

### Dashboard Slow to Load

**Symptom**: Dashboard takes long time to load

**Clear Browser Cache:**
```bash
# Hard refresh
Cmd+Shift+R  # macOS
Ctrl+Shift+F5  # Windows/Linux
```

**Reduce History:**
```bash
# Dashboard loads all history
# If you have 100+ runs, it slows down
# Clear old history (not yet implemented)
```

**Increase Refresh Rate:**
```bash
# Settings → Refresh Rate → 10 seconds
# Reduces polling frequency
```

---

## Common Error Messages

### `bash: ./claude-loop.sh: Permission denied`

**Solution:**
```bash
chmod +x claude-loop.sh
```

### `python3: command not found`

**Solution:**
```bash
# Install Python 3.8+
# macOS
brew install python3

# Ubuntu/Debian
sudo apt-get install python3

# Verify
python3 --version
```

### `ModuleNotFoundError: No module named 'flask'`

**Solution:**
```bash
pip install flask flask-cors
```

### `jq: command not found`

**Solution:**
```bash
# macOS
brew install jq

# Ubuntu/Debian
sudo apt-get install jq
```

### `error: unable to read prd.json`

**Solution:**
```bash
# Check file exists
ls -la prd.json

# Check JSON is valid
python3 -m json.tool prd.json
```

### `Error: Task queue lock timeout`

**Solution:**
```bash
# Remove stuck lock
rmdir .claude-loop/daemon/daemon.lock

# Restart daemon
./claude-loop.sh daemon stop
./claude-loop.sh daemon start
```

### `Error: Skill metadata cache corrupted`

**Solution:**
```bash
rm -rf .claude-loop/skills-cache/
./claude-loop.sh --list-skills
```

### `Error: Quick task workspace not found`

**Solution:**
```bash
# Task directory was deleted
# Cannot continue failed task
# Start fresh
./claude-loop.sh quick "task description"
```

### `Error: Dashboard authentication token mismatch`

**Solution:**
```bash
# Regenerate token
./claude-loop.sh dashboard generate-token

# Update browser
# In console: localStorage.removeItem('auth_token')
# Reload page and enter new token
```

---

## Getting More Help

If you're still stuck after trying these solutions:

### 1. Check Logs

```bash
# Daemon logs
tail -100 .claude-loop/daemon/daemon.log

# Dashboard logs
tail -100 .claude-loop/dashboard/dashboard.log

# Notification logs
tail -100 .claude-loop/daemon/notifications.log

# Execution logs
tail -100 .claude-loop/execution_log.jsonl
```

### 2. Run Tests

```bash
# Phase 2 integration tests
./tests/phase2/integration/test_phase2_integration.sh
```

### 3. Enable Debug Mode

```bash
# Add to your command
set -x
./claude-loop.sh daemon start
set +x
```

### 4. Report an Issue

Open a GitHub issue with:
- Error message (full text)
- Steps to reproduce
- Relevant log excerpts
- System info (OS, Python version, etc.)

---

## See Also

- [Migration Guide](../MIGRATION-PHASE2.md)
- [Phase 2 Documentation](../phase2/README.md)
- [Skills Architecture](../features/skills-architecture.md)
- [Quick Task Mode](../features/quick-task-mode.md)
- [Daemon Mode](../features/daemon-mode.md)
- [Dashboard UI](../features/dashboard-ui.md)
- [Notifications](../features/daemon-notifications.md)
