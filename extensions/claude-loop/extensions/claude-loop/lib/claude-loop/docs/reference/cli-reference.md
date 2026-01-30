# CLI Reference

Complete command-line interface reference for claude-loop Phase 2.

## Table of Contents

- [Global Options](#global-options)
- [Skills Framework](#skills-framework)
- [Quick Task Mode](#quick-task-mode)
- [Daemon Mode](#daemon-mode)
- [Dashboard](#dashboard)
- [PRD Mode (Phase 1)](#prd-mode-phase-1)
- [Environment Variables](#environment-variables)
- [Exit Codes](#exit-codes)

---

## Global Options

Options that work with all modes.

### `--help`

Display help information and usage examples.

```bash
./claude-loop.sh --help
```

**Output**: Displays available commands, options, and examples.

### `--version`

Show claude-loop version.

```bash
./claude-loop.sh --version
```

**Output**: Version number (e.g., `2.0.0`)

### `--verbose` or `-v`

Enable verbose logging.

```bash
./claude-loop.sh --verbose quick "task"
```

**Effect**: Prints detailed execution information to stdout.

### `--quiet` or `-q`

Suppress non-essential output.

```bash
./claude-loop.sh --quiet --prd prd.json
```

**Effect**: Only prints errors and critical messages.

---

## Skills Framework

Commands for working with skills (deterministic operations).

### `--list-skills`

List all available skills with metadata.

```bash
./claude-loop.sh --list-skills
```

**Output**:
```
Available Skills:

prd-validator
  Description: Validates PRD JSON structure and dependencies
  Usage: /prd-validator <prd-file>

test-scaffolder
  Description: Generates test scaffolding for code files
  Usage: /test-scaffolder <file-path>

commit-formatter
  Description: Formats commit messages to Conventional Commits
  Usage: /commit-formatter <message>

api-spec-generator
  Description: Generates OpenAPI specification from code
  Usage: /api-spec-generator <directory>

cost-optimizer
  Description: Analyzes and suggests token optimization
  Usage: /cost-optimizer <log-file>
```

**Format**: JSON output available with `--format json`

### `--skill <skill-name>`

Execute a specific skill.

```bash
./claude-loop.sh --skill prd-validator
./claude-loop.sh --skill test-scaffolder
```

**Arguments**: Skill name (no `/` prefix needed)

**With Arguments**: Use `--skill-arg` to pass arguments to skill.

### `--skill-arg <value>`

Pass an argument to the skill. Can be used multiple times.

```bash
# Single argument
./claude-loop.sh --skill prd-validator --skill-arg prd.json

# Multiple arguments
./claude-loop.sh --skill test-scaffolder --skill-arg src/auth.py --skill-arg pytest
```

**Order**: Arguments are passed to skill script in the order specified.

**Examples**:

```bash
# Validate PRD
./claude-loop.sh --skill prd-validator --skill-arg prd.json

# Generate tests
./claude-loop.sh --skill test-scaffolder --skill-arg src/utils.py

# Format commit message
./claude-loop.sh --skill commit-formatter --skill-arg "added new feature"

# Generate API spec
./claude-loop.sh --skill api-spec-generator --skill-arg src/api/

# Analyze costs
./claude-loop.sh --skill cost-optimizer --skill-arg .claude-loop/execution_log.jsonl
```

---

## Quick Task Mode

Execute tasks with natural language without creating a PRD.

### `quick <task-description>`

Execute a quick task with natural language description.

```bash
./claude-loop.sh quick "add error handling to auth.js"
```

**Task Description**: Plain English description of what to do (required).

**Flow**:
1. Generates execution plan
2. Shows plan for approval
3. Executes if approved
4. Commits changes (if `--commit` flag used)

**Examples**:

```bash
# Simple file edit
./claude-loop.sh quick "fix typo in README line 42"

# Add feature
./claude-loop.sh quick "add validateEmail function to utils.js"

# Refactoring
./claude-loop.sh quick "refactor error handling in auth module"

# Add tests
./claude-loop.sh quick "add unit tests for the login function"

# Documentation
./claude-loop.sh quick "update API documentation for /users endpoint"
```

### `quick --workspace <directory>`

Execute quick task in specific workspace directory.

```bash
./claude-loop.sh quick "refactor utils" --workspace src/utils/
```

**Default**: Current directory (`.`)

**Effect**: Task execution is scoped to specified directory.

### `quick --commit`

Automatically commit changes on successful completion.

```bash
./claude-loop.sh quick "fix login bug" --commit
```

**Commit Message**: Generated automatically using Conventional Commits format.

**Format**: `<type>: <task description>`

**Types**: `feat`, `fix`, `refactor`, `test`, `docs` (detected from task description)

### `quick --dry-run`

Show execution plan without actually executing.

```bash
./claude-loop.sh quick "complex refactoring" --dry-run
```

**Output**: Displays plan, complexity score, and estimated cost.

**Effect**: No files are modified, no execution occurs.

**Use Case**: Preview before committing to execution.

### `quick --continue`

Resume last failed quick task from checkpoint.

```bash
./claude-loop.sh quick --continue
```

**Requirements**: Last task must have failed and created a checkpoint.

**Effect**: Loads checkpoint and resumes from current step.

**Note**: Cannot specify new task description with `--continue`.

### `quick --template <template-name>`

Use a predefined template for the task.

```bash
./claude-loop.sh quick "refactor auth logic" --template refactor
```

**Available Templates**:
- `refactor`: Refactor code for better structure
- `add-tests`: Add test coverage
- `fix-bug`: Debug and fix issues

**Effect**: Uses template's predefined steps instead of generating new plan.

**Custom Templates**: Create in `templates/quick-tasks/`

### `quick --escalate`

Enable automatic escalation to PRD mode if task is too complex.

```bash
./claude-loop.sh quick "rewrite entire auth system" --escalate
```

**Threshold**: Complexity score ≥ 60 (configurable via env var)

**Effect**: If task is complex, offers to convert to PRD mode instead.

**Use Case**: Safety net for accidentally using quick mode for large tasks.

### `quick history`

View history of past quick tasks.

```bash
./claude-loop.sh quick history
```

**Output**:
```
========================================
  QUICK TASK HISTORY (last 20)
========================================

✓ [2026-01-13T15:12:00Z] Add validateEmail function (67s)
✓ [2026-01-13T15:00:30Z] Fix typo in README (23s)
✗ [2026-01-13T14:45:00Z] Refactor database (120s)
✓ [2026-01-13T14:30:00Z] Update dependencies (45s)
```

**Limit**: Shows last 20 tasks by default.

### `quick stats`

Show statistics for quick tasks.

```bash
./claude-loop.sh quick stats
```

**Output**:
```
========================================
  QUICK TASK STATISTICS
========================================

Total tasks: 47
Successful: 42 (89.4%)
Failed: 5 (10.6%)

Average duration: 45.2s
Total cost: $1.2450
Average cost: $0.0265
```

### `quick templates`

List available quick task templates.

```bash
./claude-loop.sh quick templates
```

**Output**:
```
========================================
  AVAILABLE QUICK TASK TEMPLATES
========================================

  - refactor: Refactor code for better structure
  - add-tests: Add test coverage for existing code
  - fix-bug: Fix a bug in existing code
```

---

## Daemon Mode

Background service for asynchronous task execution.

### `daemon start [workers]`

Start the daemon with optional worker count.

```bash
# Start with default 1 worker
./claude-loop.sh daemon start

# Start with 3 workers
./claude-loop.sh daemon start 3
```

**Workers**: Number of concurrent workers (default: 1, max: 10)

**Effect**: Starts background daemon process.

**Output**: Displays PID and log location.

### `daemon stop`

Stop the daemon gracefully.

```bash
./claude-loop.sh daemon stop
```

**Effect**:
- Finishes current tasks
- Waits up to 30 seconds
- Preserves queue
- Cleans up PID file

### `daemon status`

Check daemon status.

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

**Exit Code**: 0 if running, 1 if stopped

### `daemon submit <prd-file> [priority]`

Submit a PRD to the daemon queue.

```bash
# Normal priority (default)
./claude-loop.sh daemon submit prd.json

# High priority
./claude-loop.sh daemon submit urgent.json high

# Low priority
./claude-loop.sh daemon submit background.json low
```

**Priority Levels**:
- `high`: Processed first
- `normal`: Default (FIFO)
- `low`: Processed last

**Output**: Task ID for tracking

### `daemon submit --notify <channels>`

Submit task with notifications.

```bash
# Email notification
./claude-loop.sh daemon submit prd.json --notify email

# Multiple channels
./claude-loop.sh daemon submit prd.json --notify email,slack,webhook

# With priority
./claude-loop.sh daemon submit prd.json high --notify slack
```

**Channels**: Comma-separated list of notification channels

**Available**:
- `email`: Email via sendmail or SMTP
- `slack`: Slack webhook
- `webhook`: Generic webhook

**Requirements**: Channels must be configured in `.claude-loop/daemon/notifications.json`

### `daemon queue`

View current task queue.

```bash
./claude-loop.sh daemon queue
```

**Output**:
```
Task Queue:

⏳ a1b2c3d4 - pending - feature.json (priority: high)
   Submitted: 2026-01-13T10:00:00Z

▶️  b2c3d4e5 - running - another.json (priority: normal)
   Submitted: 2026-01-13T10:01:00Z
   Started: 2026-01-13T10:02:00Z

✅ c3d4e5f6 - completed - done.json (priority: normal)
   Completed: 2026-01-13T09:45:00Z

❌ d4e5f678 - failed - error.json (priority: low)
   Error: Execution failed at US-003
```

**Status Icons**:
- ⏳ pending
- ▶️ running
- ✅ completed
- ❌ failed

### `daemon cancel <task-id>`

Cancel a pending task.

```bash
./claude-loop.sh daemon cancel a1b2c3d4e5f67890
```

**Task ID**: First 8 or full 16 characters

**Restriction**: Can only cancel **pending** tasks, not running ones.

### `daemon pause`

Pause queue processing.

```bash
./claude-loop.sh daemon pause
```

**Effect**:
- Current task continues
- No new tasks picked up
- Queue remains accessible

### `daemon resume`

Resume queue processing.

```bash
./claude-loop.sh daemon resume
```

**Effect**: Workers start picking up pending tasks again.

---

## Dashboard

Web-based monitoring interface.

### `dashboard start`

Start the dashboard server.

```bash
./claude-loop.sh dashboard start
```

**Default URL**: `http://localhost:8080`

**Effect**: Starts Flask server in background.

**Output**: URL and authentication token.

### `dashboard start --port <port>`

Start dashboard on custom port.

```bash
./claude-loop.sh dashboard start --port 9000
```

**Default**: 8080

**Range**: 1024-65535

**URL**: `http://localhost:<port>`

### `dashboard start --host <host>`

Start dashboard on custom host.

```bash
# Allow remote access
./claude-loop.sh dashboard start --host 0.0.0.0
```

**Default**: `localhost`

**Common Values**:
- `localhost`: Local only
- `0.0.0.0`: All interfaces (remote access)
- Specific IP: Bind to that IP

**Security**: Use `0.0.0.0` only on trusted networks.

### `dashboard stop`

Stop the dashboard server.

```bash
./claude-loop.sh dashboard stop
```

**Effect**: Stops Flask process gracefully.

### `dashboard status`

Check dashboard server status.

```bash
./claude-loop.sh dashboard status
```

**Output**:
```
Dashboard is running (PID: 12345)
URL: http://localhost:8080
Uptime: 2h 15m
Auth token: AbCdEf123456
```

### `dashboard logs`

View dashboard server logs.

```bash
./claude-loop.sh dashboard logs
```

**Output**: Tails `.claude-loop/dashboard/dashboard.log`

**Options**:
```bash
# Last 50 lines
tail -50 .claude-loop/dashboard/dashboard.log

# Follow live
tail -f .claude-loop/dashboard/dashboard.log
```

### `dashboard restart`

Restart the dashboard server.

```bash
./claude-loop.sh dashboard restart
```

**Effect**: Equivalent to `dashboard stop && dashboard start`

### `dashboard generate-token`

Generate new authentication token.

```bash
./claude-loop.sh dashboard generate-token
```

**Effect**:
- Creates new random token
- Saves to `.claude-loop/dashboard/auth_token.txt`
- Invalidates old token

**Note**: Existing browser sessions will need to re-authenticate.

---

## PRD Mode (Phase 1)

Traditional PRD-based execution (still fully supported in Phase 2).

### `--prd <prd-file>`

Execute a Product Requirements Document.

```bash
./claude-loop.sh --prd prd.json
```

**File Format**: JSON containing project and user stories

**Effect**: Full multi-story execution with checkpoints

**Example**:
```bash
./claude-loop.sh --prd feature-auth.json
```

### `--dashboard`

Launch dashboard along with PRD execution.

```bash
./claude-loop.sh --prd prd.json --dashboard
```

**Effect**:
- Starts dashboard server (if not already running)
- Executes PRD
- Dashboard shows real-time progress

### `--resume`

Resume from last checkpoint.

```bash
./claude-loop.sh --prd prd.json --resume
```

**Effect**: Continues from last saved checkpoint instead of starting over.

### Other Phase 1 Options

See Phase 1 documentation for complete PRD mode reference:
- `--parallel <n>`: Parallel story execution
- `--checkpoint-interval <n>`: Checkpoint frequency
- `--max-retries <n>`: Retry count for failed stories
- `--timeout <seconds>`: Execution timeout

---

## Environment Variables

Configure behavior via environment variables.

### Skills Framework

```bash
# Skills directory (default: ./skills)
export CLAUDE_LOOP_SKILLS_DIR="/custom/path/skills"

# Cache directory (default: ./.claude-loop/skills-cache)
export SKILLS_CACHE_DIR="/tmp/skills-cache"
```

### Quick Task Mode

```bash
# Task timeout in seconds (default: 600)
export QUICK_TASK_TIMEOUT=1800

# Tasks directory (default: ./.claude-loop/quick-tasks)
export QUICK_TASKS_DIR="/custom/path/quick-tasks"

# Templates directory (default: ./templates/quick-tasks)
export QUICK_TASK_TEMPLATES_DIR="/custom/templates"

# Checkpoint interval in steps (default: 5)
export QUICK_TASK_CHECKPOINT_INTERVAL=10

# Complexity threshold for escalation (default: 60)
export QUICK_TASK_ESCALATION_THRESHOLD=50
```

### Daemon Mode

```bash
# Daemon directory (default: ./.claude-loop/daemon)
export DAEMON_DIR="/custom/path/daemon"

# Worker count (default: 1)
export DAEMON_WORKERS=3

# Task timeout in seconds (default: 3600)
export DAEMON_TASK_TIMEOUT=7200

# Queue poll interval in seconds (default: 5)
export DAEMON_POLL_INTERVAL=10
```

### Dashboard

```bash
# Dashboard port (default: 8080)
export DASHBOARD_PORT=9000

# Dashboard host (default: localhost)
export DASHBOARD_HOST="0.0.0.0"

# Token length (default: 16)
export DASHBOARD_TOKEN_LENGTH=32

# Log level: DEBUG, INFO, WARNING, ERROR (default: INFO)
export DASHBOARD_LOG_LEVEL=DEBUG
```

### Notifications

```bash
# Max retry attempts (default: 3)
export NOTIFICATION_MAX_RETRIES=5

# Initial retry delay in seconds (default: 5)
export NOTIFICATION_RETRY_DELAY=10

# Timeout per attempt in seconds (default: 30)
export NOTIFICATION_TIMEOUT=60

# Enable/disable channels
export NOTIFICATION_EMAIL_ENABLED=true
export NOTIFICATION_SLACK_ENABLED=false
export NOTIFICATION_WEBHOOK_ENABLED=false
```

### General

```bash
# Claude API key
export ANTHROPIC_API_KEY="your-api-key"

# Model selection (default: claude-sonnet-4)
export CLAUDE_MODEL="claude-opus-4"

# Verbosity level (default: 0)
export CLAUDE_LOOP_VERBOSE=1

# Log file (default: .claude-loop/execution_log.jsonl)
export CLAUDE_LOOP_LOG_FILE="/custom/path/log.jsonl"
```

---

## Exit Codes

Standard exit codes for scripting and automation.

| Code | Meaning |
|------|---------|
| `0` | Success |
| `1` | General error |
| `2` | Invalid arguments |
| `3` | File not found |
| `4` | Permission denied |
| `5` | Execution failed |
| `6` | Timeout |
| `7` | API error |
| `8` | Checkpoint required (manual approval) |
| `9` | User cancelled |

**Usage in Scripts**:

```bash
./claude-loop.sh quick "task"
exit_code=$?

if [ $exit_code -eq 0 ]; then
    echo "Success!"
elif [ $exit_code -eq 5 ]; then
    echo "Execution failed, check logs"
elif [ $exit_code -eq 6 ]; then
    echo "Timeout, task took too long"
fi
```

---

## Command Combinations

Powerful combinations of commands and flags.

### Quick Task with All Options

```bash
./claude-loop.sh quick "refactor auth module" \
  --workspace src/auth/ \
  --template refactor \
  --dry-run \
  --escalate
```

### Daemon Batch Submission

```bash
./claude-loop.sh daemon start 3
for prd in prds/*.json; do
    ./claude-loop.sh daemon submit "$prd" --notify email
done
./claude-loop.sh daemon queue
```

### Dashboard with PRD Execution

```bash
./claude-loop.sh dashboard start
./claude-loop.sh --prd large-feature.json --dashboard
# Monitor at http://localhost:8080
```

### Skills Pipeline

```bash
# Validate → Execute → Optimize
./claude-loop.sh --skill prd-validator --skill-arg prd.json && \
./claude-loop.sh --prd prd.json && \
./claude-loop.sh --skill cost-optimizer --skill-arg .claude-loop/execution_log.jsonl
```

### Quick Task Chain

```bash
# Execute multiple tasks sequentially
./claude-loop.sh quick "fix bug in auth" --commit && \
./claude-loop.sh quick "add tests for fix" --commit && \
./claude-loop.sh quick "update changelog" --commit
```

---

## Shortcuts and Aliases

Recommended shell aliases for common commands.

```bash
# Add to ~/.bashrc or ~/.zshrc

alias cl='./claude-loop.sh'
alias clq='./claude-loop.sh quick'
alias cld='./claude-loop.sh daemon'
alias cldash='./claude-loop.sh dashboard'
alias clsk='./claude-loop.sh --skill'

# Usage
clq "fix README typo" --commit
cld submit prd.json high --notify slack
cldash start
clsk prd-validator --skill-arg prd.json
```

---

## See Also

- [Daemon Mode Tutorial](../tutorials/daemon-mode.md)
- [Dashboard Tutorial](../tutorials/dashboard.md)
- [Quick Task Mode](../features/quick-task-mode.md)
- [Skills Architecture](../features/skills-architecture.md)
- [Phase 2 Documentation](../phase2/README.md)
