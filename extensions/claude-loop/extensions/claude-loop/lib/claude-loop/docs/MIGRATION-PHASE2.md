# Phase 2 Migration Guide

## Overview

Phase 2 introduces significant new features to claude-loop:

1. **Skills Architecture** - Cowork-style progressive disclosure for deterministic operations
2. **Quick Task Mode** - Natural language task execution without PRD authoring
3. **Daemon Mode** - Background execution with task queuing
4. **Visual Progress Dashboard** - Real-time web-based monitoring
5. **Notification System** - Multi-channel notifications for task completion

This guide helps you migrate from Phase 1 to Phase 2 and understand new capabilities.

---

## What's New in Phase 2

### Skills Architecture

**What it is**: A framework for encapsulating deterministic operations (validation, formatting, generation) with progressive disclosure to minimize token costs.

**Key features**:
- Three-layer architecture: metadata (always loaded), instructions (on-demand), resources (zero cost)
- Built-in skills: `prd-validator`, `test-scaffolder`, `commit-formatter`, `api-spec-generator`, `cost-optimizer`
- Extensible: create custom skills by adding SKILL.md files to `skills/` directory
- Token-efficient: ~50 tokens/skill at startup vs 200-500 on-demand

**How to use**:
```bash
# List available skills
./claude-loop.sh --list-skills

# Use a skill
./claude-loop.sh --skill prd-validator --skill-arg prd.json
```

**Migration notes**:
- Phase 1 PRD execution unchanged
- Skills are optional - existing workflows continue to work
- Skills integrate with quick task mode automatically

---

### Quick Task Mode

**What it is**: Execute tasks with natural language descriptions without creating a full PRD. Claude generates a plan, gets your approval, executes it, and commits the result.

**Key features**:
- Natural language task description
- Automatic plan generation with complexity detection
- User approval checkpoint
- Workspace isolation for each task
- Automatic commit message generation
- Task history and audit trail
- Template support for common patterns (refactor, add-tests, fix-bug)
- Skills integration (automatically suggests relevant skills)

**How to use**:
```bash
# Basic usage
./claude-loop.sh quick "add tests to the authentication module"

# With workspace
./claude-loop.sh quick "refactor error handling" --workspace src/

# Auto-commit on success
./claude-loop.sh quick "fix bug in login" --commit

# Dry-run (show plan without executing)
./claude-loop.sh quick "update API docs" --dry-run

# Use template
./claude-loop.sh quick --template refactor "clean up utils module"

# View history
./claude-loop.sh quick history
./claude-loop.sh quick stats
```

**Migration notes**:
- Quick mode complements PRD mode (doesn't replace it)
- Use quick mode for: single-file changes, bug fixes, small features (<3 user stories)
- Use PRD mode for: complex features, multi-file refactorings, anything with dependencies
- Complexity detection (0-100 score) helps you choose the right mode
- Auto-escalation available with `--escalate` flag (threshold: 60)

---

### Daemon Mode

**What it is**: Background service that accepts tasks via queue and executes them asynchronously. Fire-and-forget workflow for long-running PRD executions.

**Key features**:
- Runs as background daemon process
- FIFO queue with priority support (high/normal/low)
- Configurable worker pool (default: 1)
- Graceful shutdown (finishes current task)
- PID file management
- Comprehensive logging
- Task submission via CLI or API
- Queue management: view, pause, resume, cancel

**How to use**:
```bash
# Start daemon
./claude-loop.sh daemon start

# Check status
./claude-loop.sh daemon status

# Submit task
./claude-loop.sh daemon submit prd.json
./claude-loop.sh daemon submit prd.json --priority high --notify email

# View queue
./claude-loop.sh daemon queue

# Pause/resume queue
./claude-loop.sh daemon pause
./claude-loop.sh daemon resume

# Cancel task
./claude-loop.sh daemon cancel <task-id>

# Stop daemon
./claude-loop.sh daemon stop
```

**Migration notes**:
- Daemon mode is optional (PRDs can still run in foreground)
- Use daemon when:
  - You want to submit multiple PRDs and let them execute overnight
  - You're iterating on PRD and want fast feedback on queued work
  - You want notifications when work completes
- Worker pool is single-worker by default for stability
- Multi-worker support available (set in queue.json config)

---

### Visual Progress Dashboard

**What it is**: Real-time web-based dashboard for monitoring claude-loop executions with live updates, story status grid, logs viewer, cost tracking, and historical runs.

**Key features**:
- Real-time updates via Server-Sent Events (SSE)
- Story status grid with color coding (green/yellow/gray)
- Live logs viewer with streaming
- Cost tracker with budget alerts
- File changes viewer
- Historical runs archive
- Dark mode support
- Responsive design (mobile/tablet/desktop)
- Token-based authentication

**How to use**:
```bash
# Start dashboard
./claude-loop.sh dashboard start
# Dashboard runs on http://localhost:8080

# Start on custom port/host
./claude-loop.sh dashboard start --port 3000 --host 0.0.0.0

# Check dashboard status
./claude-loop.sh dashboard status

# View dashboard logs
./claude-loop.sh dashboard logs

# Stop dashboard
./claude-loop.sh dashboard stop

# Generate new auth token
./claude-loop.sh dashboard generate-token
```

**API Endpoints**:
- `GET /api/status` - Current execution status
- `GET /api/stories` - All stories with status
- `GET /api/logs` - Execution logs (paginated)
- `GET /api/metrics` - Token usage and cost metrics
- `GET /api/history` - Historical runs
- `GET /api/runs` - List all runs
- `GET /api/runs/<run_id>` - Run details
- `GET /api/stream` - SSE for real-time updates
- `GET /api/daemon/status` - Daemon status
- `GET /api/daemon/queue` - Daemon queue
- `GET /api/notifications/config` - Notification config
- `GET /api/notifications/recent` - Recent notifications

**Migration notes**:
- Dashboard is independent of execution (doesn't affect PRD runs)
- Auto-launched with `--dashboard` flag or separately
- Authentication token auto-generated on first start
- Multiple concurrent executions supported
- Works with both foreground and daemon mode

---

### Notification System

**What it is**: Multi-channel notification system for daemon mode. Get notified when tasks complete via email, Slack, or custom webhooks.

**Key features**:
- Three channels: email (sendmail/SMTP), Slack webhook, generic webhook
- Template-based notifications (success, failure, checkpoint)
- Retry logic with exponential backoff (up to 3 attempts)
- Task summary in notifications (stories completed, time taken, cost)
- Multiple channels per task
- Configurable per-task or globally

**How to use**:
```bash
# Configure notifications
# Edit .claude-loop/daemon/notifications.json
cat > .claude-loop/daemon/notifications.json <<EOF
{
  "email": {
    "enabled": true,
    "method": "sendmail",
    "from": "claude-loop@example.com",
    "to": "you@example.com"
  },
  "slack": {
    "enabled": true,
    "webhook_url": "https://hooks.slack.com/services/YOUR/WEBHOOK/URL"
  },
  "webhook": {
    "enabled": false,
    "url": "https://example.com/webhook"
  }
}
EOF

# Submit task with notifications
./claude-loop.sh daemon submit prd.json --notify email
./claude-loop.sh daemon submit prd.json --notify email,slack
```

**Migration notes**:
- Notifications only work with daemon mode
- Configure once, use for all tasks (or override per-task)
- Templates are customizable (edit `templates/notifications/*.txt`)
- Retry logic handles transient failures automatically
- Check `.claude-loop/daemon/notifications.log` for notification history

---

## Breaking Changes

**None!** Phase 2 is fully backward compatible with Phase 1.

- All Phase 1 features continue to work unchanged
- PRD schema unchanged (optional new fields for advanced features)
- CLI arguments unchanged (new subcommands added)
- File structure unchanged (new directories are optional)

---

## New CLI Commands

### Skills
```bash
./claude-loop.sh --list-skills              # List available skills
./claude-loop.sh --skill <name>             # Execute a skill
./claude-loop.sh --skill-arg <arg>          # Pass argument to skill
```

### Quick Task Mode
```bash
./claude-loop.sh quick "<task>"             # Execute quick task
./claude-loop.sh quick history              # View task history
./claude-loop.sh quick stats                # View statistics
./claude-loop.sh quick templates            # List available templates
./claude-loop.sh quick --template <name>    # Use template
./claude-loop.sh quick --dry-run            # Show plan without executing
./claude-loop.sh quick --continue           # Resume failed task
./claude-loop.sh quick --commit             # Auto-commit on success
./claude-loop.sh quick --escalate           # Auto-escalate complex tasks to PRD
```

### Daemon Mode
```bash
./claude-loop.sh daemon start               # Start daemon
./claude-loop.sh daemon stop                # Stop daemon
./claude-loop.sh daemon status              # Check status
./claude-loop.sh daemon submit <prd>        # Submit task
./claude-loop.sh daemon queue               # View queue
./claude-loop.sh daemon pause               # Pause queue
./claude-loop.sh daemon resume              # Resume queue
./claude-loop.sh daemon cancel <task-id>    # Cancel task
```

### Dashboard
```bash
./claude-loop.sh dashboard start            # Start dashboard
./claude-loop.sh dashboard stop             # Stop dashboard
./claude-loop.sh dashboard status           # Check status
./claude-loop.sh dashboard logs             # View logs
./claude-loop.sh dashboard restart          # Restart server
./claude-loop.sh dashboard generate-token   # Generate auth token
```

---

## Migration Checklist

### For Existing Projects

- [ ] **Test Phase 1 features** - Run existing PRDs to ensure compatibility
  ```bash
  ./claude-loop.sh --prd your-existing-prd.json
  ```

- [ ] **Try quick task mode** - For small tasks that don't need full PRD
  ```bash
  ./claude-loop.sh quick "add a test for the login function"
  ```

- [ ] **Explore skills** - See what deterministic operations are available
  ```bash
  ./claude-loop.sh --list-skills
  ./claude-loop.sh --skill prd-validator --skill-arg prd.json
  ```

- [ ] **Start dashboard** - Monitor execution in real-time
  ```bash
  ./claude-loop.sh dashboard start
  # Open http://localhost:8080 in browser
  ```

- [ ] **Optional: Enable daemon mode** - For background execution
  ```bash
  ./claude-loop.sh daemon start
  ./claude-loop.sh daemon submit prd.json
  ```

- [ ] **Optional: Configure notifications** - Get alerted when tasks complete
  ```bash
  # Edit .claude-loop/daemon/notifications.json
  # Then submit with: --notify email
  ```

### For New Projects

- [ ] **Start with quick task mode** - For prototyping and small changes
- [ ] **Use skills** - For validation, formatting, generation tasks
- [ ] **Graduate to PRD mode** - When tasks grow to 3+ user stories
- [ ] **Enable dashboard** - Always run for visibility
- [ ] **Consider daemon mode** - For multi-PRD workflows

---

## Performance Considerations

### Token Usage
- **Skills**: ~50 tokens/skill at startup (vs inline prompts: 200-500)
- **Quick mode**: Lower overhead than full PRD (single-iteration execution)
- **Dashboard**: No token impact (runs separately)
- **Daemon**: Same token usage as foreground (just decouples execution)

### Execution Time
- **Skills**: Instant (pre-written scripts, no LLM)
- **Quick mode**: 1-5 minutes typical (vs PRD: 10-60 minutes)
- **Dashboard**: <100ms API latency, <1s UI refresh
- **Daemon**: Background execution (doesn't block terminal)

### Cost Savings
- Skills replace LLM calls for deterministic operations (100% cost savings)
- Quick mode uses lighter prompts (20-40% token reduction)
- Dashboard enables monitoring without running multiple executions

---

## Troubleshooting

### Skills Not Working
**Problem**: `--list-skills` shows no skills
**Solution**: Ensure `skills/` directory exists and contains SKILL.md files

**Problem**: Skill execution fails
**Solution**: Check skill script has execute permissions: `chmod +x skills/*/scripts/*.py`

### Quick Mode Issues
**Problem**: Plan approval times out
**Solution**: Set `QUICK_TASK_TIMEOUT` environment variable (default: 600s)

**Problem**: Task fails with "complexity too high"
**Solution**: Use `--escalate` flag to convert to PRD, or break into smaller tasks

### Daemon Not Starting
**Problem**: `daemon start` fails
**Solution**: Check if daemon is already running: `daemon status`. Kill stale process if needed.

**Problem**: Queue not processing
**Solution**: Check daemon log: `.claude-loop/daemon/daemon.log` for errors

### Dashboard Not Loading
**Problem**: Connection refused on port 8080
**Solution**: Check if dashboard is running: `dashboard status`. Ensure port is not in use.

**Problem**: Authentication fails
**Solution**: Get token: `dashboard generate-token`. Use in Authorization header.

### Notifications Not Sending
**Problem**: Email notifications not received
**Solution**: Check sendmail is installed (`which sendmail`) or use SMTP method

**Problem**: Slack notifications fail
**Solution**: Verify webhook URL is correct. Check `.claude-loop/daemon/notifications.log`

---

## Best Practices

### When to Use Each Mode

**Quick Task Mode**:
- Single file changes
- Bug fixes
- Adding tests
- Documentation updates
- Code formatting/refactoring (single module)
- Complexity score < 60

**PRD Mode**:
- Multi-file features
- Anything with dependencies between stories
- Complex refactorings (multiple modules)
- New architectural components
- Complexity score ≥ 60
- When you need checkpoint/resume capability

**Daemon Mode**:
- Multiple PRDs to execute overnight
- Long-running executions you don't want to babysit
- When you need notifications
- CI/CD integration

### Workflow Recommendations

**Development Workflow**:
1. Use quick mode for rapid iteration on small changes
2. Use skills for validation and formatting
3. Keep dashboard running for visibility
4. Graduate to PRD mode when task grows beyond 1-2 stories

**Production Workflow**:
1. Author PRD for planned feature work
2. Submit to daemon queue
3. Monitor via dashboard
4. Get notified on completion
5. Review results and iterate

---

## Support

### Documentation
- Phase 2 Features: `docs/phase2/`
- Skills Architecture: `docs/features/skills-architecture.md`
- Quick Task Mode: `docs/features/quick-task-mode.md`
- Daemon Mode: `docs/features/daemon-mode.md`
- Dashboard API: `docs/api/dashboard-api.md`
- Notifications: `docs/features/daemon-notifications.md`

### Testing
- Integration tests: `tests/phase2/integration/test_phase2_integration.sh`
- Skills tests: `tests/skills/`
- Quick mode tests: `tests/quick-mode/`

### Getting Help
1. Check troubleshooting section above
2. Review relevant documentation
3. Check logs:
   - Daemon: `.claude-loop/daemon/daemon.log`
   - Dashboard: `.claude-loop/dashboard/dashboard.log`
   - Notifications: `.claude-loop/daemon/notifications.log`
4. Run integration tests to verify installation

---

## What's Next (Phase 3 Preview)

Phase 3 will introduce:
- **Multi-Agent Orchestration** - Parallel specialized agents
- **Context Caching** - Dramatic token cost reduction
- **Self-Improvement Loop** - Automatic capability gap detection
- **Experience Library** - Learn from past executions
- **Cost Forecasting** - Predict PRD cost before execution

Stay tuned for Phase 3 release!
