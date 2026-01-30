# Phase 2 Foundations - Complete Documentation

## Table of Contents

1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Features](#features)
4. [Installation](#installation)
5. [Usage Guide](#usage-guide)
6. [Integration](#integration)
7. [API Reference](#api-reference)
8. [Performance](#performance)
9. [Troubleshooting](#troubleshooting)
10. [Examples](#examples)

---

## Overview

Phase 2 introduces five foundational capabilities that enable Cowork-level UX in claude-loop:

### 1. Skills Architecture (US-201, US-202)
Progressive disclosure framework for deterministic operations. Metadata loaded upfront (~50 tokens/skill), instructions and resources loaded on-demand, zero cost until execution.

**Key Benefits:**
- 50-100x token reduction for deterministic operations
- Instant execution (no LLM latency)
- Extensible (add custom skills easily)
- Composable (skills work together)

**Documentation:** `docs/features/skills-architecture.md`

### 2. Quick Task Mode (US-203, US-204)
Natural language task execution without PRD authoring. Automatic plan generation, complexity detection, template support, and skills integration.

**Key Benefits:**
- 5-10x faster for small tasks vs full PRD
- Lower token overhead (20-40% reduction)
- Automatic complexity detection prevents wasted effort
- Template library for common patterns

**Documentation:** `docs/features/quick-task-mode.md`, `docs/features/quick-task-mode-advanced.md`

### 3. Daemon Mode (US-205, US-206)
Background service with task queue. Fire-and-forget workflow for long-running PRD executions with priority queuing and notification support.

**Key Benefits:**
- Non-blocking execution (submit and continue working)
- Priority queuing (high/normal/low)
- Notification integration (email, Slack, webhook)
- Graceful shutdown and recovery

**Documentation:** `docs/features/daemon-mode.md`, `docs/features/daemon-notifications.md`

### 4. Visual Progress Dashboard (US-207, US-208)
Real-time web-based monitoring with Server-Sent Events (SSE). Story status grid, live logs, cost tracking, and historical runs.

**Key Benefits:**
- Real-time visibility without polling
- Multi-execution monitoring
- Historical analytics
- Mobile-responsive design

**Documentation:** `docs/features/dashboard-ui.md`, `docs/api/dashboard-api.md`

### 5. Notification System (US-206)
Multi-channel notifications for daemon task completion. Email (sendmail/SMTP), Slack webhook, and generic webhook support with retry logic.

**Key Benefits:**
- Get alerted when work completes
- Multiple channels (email, Slack, custom)
- Configurable per-task or globally
- Automatic retry on failure

**Documentation:** `docs/features/daemon-notifications.md`

---

## Architecture

### System Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                       CLI Interface                          │
│  ./claude-loop.sh [quick|daemon|dashboard|--skill]          │
└────────────┬────────────────────────────────────────────────┘
             │
   ┌─────────┼─────────┐
   │         │         │
   v         v         v
┌─────┐  ┌──────┐  ┌────────┐
│Quick│  │Skills│  │ PRD    │
│Mode │  │Frame │  │ Mode   │
└──┬──┘  └───┬──┘  └───┬────┘
   │         │         │
   │    ┌────┴─────────┴────┐
   │    │                    │
   v    v                    v
┌──────────────┐      ┌──────────┐
│ Daemon Queue │<─────│ Executor │
│  (FIFO +     │      │ (Worker) │
│  Priority)   │      └─────┬────┘
└──────┬───────┘            │
       │                    │
       v                    v
┌──────────────┐      ┌──────────┐
│Notifications │      │Dashboard │
│   System     │      │   API    │
│ (Email/Slack)│      │  (REST + │
└──────────────┘      │   SSE)   │
                      └─────┬────┘
                            │
                            v
                      ┌──────────┐
                      │Dashboard │
                      │   UI     │
                      │(Browser) │
                      └──────────┘
```

### Data Flow

**Quick Task Flow:**
```
User Input (NL) → Parse → Complexity Detection → Plan Generation
                                                  ↓
                                       Skill Suggestion
                                                  ↓
                             User Approval ← Display Plan
                                                  ↓
                                         Execute (Isolated)
                                                  ↓
                                   Commit + Audit Log
```

**Daemon Task Flow:**
```
Submit PRD → Add to Queue (with priority)
                   ↓
            Worker Poll ← Queue Sorted
                   ↓
              Execute PRD
                   ↓
        ┌──────────┴──────────┐
        v                     v
  Update Status        Send Notifications
        │                     │
        └──────────┬──────────┘
                   v
          Dashboard Broadcast (SSE)
```

### File Structure

```
claude-loop/
├── lib/
│   ├── skills-framework.sh      # Skills loader and executor
│   ├── quick-task-mode.sh       # Quick task implementation
│   ├── daemon.sh                # Daemon process manager
│   ├── notifications.sh         # Notification system
│   ├── dashboard/
│   │   ├── server.py            # Flask REST API + SSE
│   │   ├── api.py               # Data access layer
│   │   └── static/
│   │       ├── index.html       # Dashboard UI
│   │       ├── styles.css       # Styling
│   │       └── app.js           # Client logic
│   └── dashboard-launcher.sh    # Dashboard process manager
├── skills/
│   ├── prd-validator/
│   │   ├── SKILL.md             # Metadata + instructions
│   │   └── scripts/main.py      # Executable
│   ├── test-scaffolder/
│   ├── commit-formatter/
│   ├── api-spec-generator/
│   ├── cost-optimizer/
│   └── hello-world/
├── templates/
│   ├── quick-tasks/
│   │   ├── refactor.json        # Refactoring template
│   │   ├── add-tests.json       # Test addition template
│   │   └── fix-bug.json         # Bug fixing template
│   └── notifications/
│       ├── success.txt          # Success template
│       ├── failure.txt          # Failure template
│       └── checkpoint.txt       # Checkpoint template
├── .claude-loop/
│   ├── skills-cache/            # Skills metadata cache
│   ├── quick-tasks/             # Quick task workspaces
│   │   └── {timestamp}/
│   ├── daemon/
│   │   ├── queue.json           # Task queue
│   │   ├── daemon.pid           # Process ID
│   │   ├── daemon.log           # Daemon log
│   │   ├── notifications.json   # Notification config
│   │   └── notifications.log    # Notification log
│   └── dashboard/
│       ├── dashboard.pid        # Process ID
│       ├── auth_token.txt       # Auth token
│       └── dashboard.log        # Dashboard log
└── tests/
    ├── phase2/
    │   └── integration/
    │       └── test_phase2_integration.sh
    ├── skills/
    ├── quick-mode/
    └── notifications/
```

---

## Features

### Skills Architecture

**Metadata Layer** (always loaded):
```yaml
name: prd-validator
version: 1.0.0
description: Validates PRD structure and dependencies
category: validation
tags: [prd, validation, dependencies]
cost: zero
latency: instant
```

**Instructions Layer** (on-demand):
```markdown
## Usage
./claude-loop.sh --skill prd-validator --skill-arg <prd-file>

## Description
Validates PRD JSON structure, checks for circular dependencies,
verifies story dependencies exist, and checks for common issues.

## Output
Exit code 0 on success, 1 on validation errors.
Prints validation results to stdout.
```

**Resources Layer** (zero cost):
- Executable scripts (Python, Bash, Node.js)
- Supporting libraries
- Configuration files

### Quick Task Mode

**Complexity Scoring** (0-100):
- Word count: 0-25 points
- Connectors ("and", "with", "plus"): 15 points each
- Architecture keywords: 10 points each
- Multiple components: 10-20 points
- Testing requirements: 10 points
- Validation/error handling: 5 points each

**Levels:**
- Simple (0-29): 5 steps, ~2 minutes, $0.10-0.30
- Medium (30-59): 7 steps, ~5 minutes, $0.30-0.80
- Complex (60-100): 10 steps, ~10 minutes, $0.80-2.00+

**Auto-escalation:** Threshold 60 (configurable)

### Daemon Mode

**Queue Priority:**
1. High priority tasks
2. Normal priority tasks (FIFO within priority)
3. Low priority tasks

**Worker Pool:**
- Default: 1 worker (single-threaded)
- Configurable: 1-10 workers
- Worker isolation: separate processes
- Task locking: prevents concurrent execution

**Graceful Shutdown:**
- Signal handling (SIGTERM, SIGINT)
- 30-second timeout for current task
- Queue preserved across restarts

### Dashboard

**Frontend Technology:**
- Vanilla JavaScript (no build step)
- CSS Grid + Flexbox (responsive)
- Server-Sent Events (SSE) for real-time
- Local Storage for settings persistence

**Backend Technology:**
- Flask (Python web framework)
- Flask-CORS (CORS support)
- Token-based authentication
- Background monitoring thread

**Performance:**
- API latency: <100ms (typical)
- UI refresh: 2-second SSE interval
- Logs pagination: 100 entries/page
- History limit: 1000 runs

### Notifications

**Channels:**
- **Email**: Sendmail (default) or SMTP
- **Slack**: Webhook integration with attachments
- **Webhook**: Generic POST with JSON payload

**Retry Logic:**
- Attempts: 3 (default)
- Backoff: Exponential (5s, 10s, 20s)
- Timeout: 10 seconds per attempt

**Templates:**
- Success: Green color, summary stats
- Failure: Red color, error details
- Checkpoint: Yellow color, approval required

---

## Installation

Phase 2 is included in claude-loop v2.0+. No separate installation required.

### Verify Installation

```bash
# Check Phase 2 features are available
./claude-loop.sh --list-skills        # Should show skills
./claude-loop.sh quick --help         # Should show quick mode help
./claude-loop.sh daemon status        # Should show daemon status
./claude-loop.sh dashboard status     # Should show dashboard status
```

### Dependencies

**Required (already included):**
- Python 3.10+
- Bash 4.0+

**Optional (for dashboard):**
- Flask: `pip install flask flask-cors`

**Optional (for notifications):**
- Sendmail (email): `apt-get install sendmail` or `brew install sendmail`
- Python smtplib (SMTP email): included in Python standard library
- curl (webhooks): usually pre-installed

---

## Usage Guide

### Getting Started

**1. Try Quick Task Mode:**
```bash
# Simple task
./claude-loop.sh quick "add a comment to the main function"

# With dry-run
./claude-loop.sh quick "refactor the error handling" --dry-run

# With template
./claude-loop.sh quick --template refactor "clean up the utils module"
```

**2. Use Skills:**
```bash
# Validate PRD
./claude-loop.sh --skill prd-validator --skill-arg prd.json

# Generate test scaffolding
./claude-loop.sh --skill test-scaffolder --skill-arg src/auth.py

# Format commit message
./claude-loop.sh --skill commit-formatter --skill-arg "added new feature"
```

**3. Start Daemon (Optional):**
```bash
# Start daemon
./claude-loop.sh daemon start

# Submit PRD
./claude-loop.sh daemon submit feature-prd.json

# Monitor queue
./claude-loop.sh daemon queue
```

**4. Start Dashboard (Recommended):**
```bash
# Start dashboard
./claude-loop.sh dashboard start

# Open http://localhost:8080 in browser
# Get auth token: cat .claude-loop/dashboard/auth_token.txt
```

**5. Configure Notifications (Optional):**
```bash
# Edit notification config
cat > .claude-loop/daemon/notifications.json <<EOF
{
  "email": {
    "enabled": true,
    "method": "sendmail",
    "from": "claude-loop@example.com",
    "to": "you@example.com"
  },
  "slack": {
    "enabled": false,
    "webhook_url": ""
  }
}
EOF

# Submit with notification
./claude-loop.sh daemon submit prd.json --notify email
```

### Common Workflows

**Workflow 1: Quick Fix**
```bash
# Use quick mode for fast iteration
./claude-loop.sh quick "fix typo in README"
# → Plan generated, approved, executed, committed (< 1 min)
```

**Workflow 2: Feature Development**
```bash
# Use PRD mode for complex features
./claude-loop.sh --prd feature-oauth.json
# → Multi-story execution, checkpoints, comprehensive (30-60 min)
```

**Workflow 3: Batch Processing**
```bash
# Submit multiple PRDs to daemon
./claude-loop.sh daemon start
./claude-loop.sh daemon submit prd-1.json --priority high --notify slack
./claude-loop.sh daemon submit prd-2.json
./claude-loop.sh daemon submit prd-3.json
# → Execute overnight, get notified in morning
```

**Workflow 4: Monitoring**
```bash
# Start dashboard for real-time visibility
./claude-loop.sh dashboard start &
./claude-loop.sh --prd large-feature.json
# → Watch progress in browser, track cost, view logs
```

---

## Integration

### With Phase 1 Features

Phase 2 integrates seamlessly with Phase 1:

- **Monitoring System:** Dashboard consumes Phase 1 metrics
- **PRD Parser:** Skills validate PRD structure
- **Parallel Execution:** Dashboard shows all parallel workers
- **Context Cache:** Quick mode benefits from caching
- **Cost Tracking:** Dashboard displays Phase 1 cost metrics

### With External Tools

**Git Integration:**
- Quick mode auto-commits with Conventional Commits format
- Skills can format commit messages
- Dashboard shows file changes

**CI/CD Integration:**
- Daemon mode ideal for CI/CD pipelines
- Webhook notifications trigger downstream jobs
- Exit codes indicate success/failure

**Slack Integration:**
- Webhook notifications for team updates
- Customizable message templates
- Color-coded by status (green/red/yellow)

**Monitoring Integration:**
- Dashboard API for external monitoring tools
- SSE stream for real-time integrations
- Metrics endpoint for Prometheus/Grafana

---

## API Reference

See `docs/api/dashboard-api.md` for complete API documentation.

**Quick Reference:**

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/health` | GET | Health check (no auth) |
| `/api/status` | GET | Current execution status |
| `/api/stories` | GET | All stories with status |
| `/api/logs` | GET | Execution logs (paginated) |
| `/api/metrics` | GET | Token usage and cost |
| `/api/history` | GET | Historical runs |
| `/api/stream` | GET | SSE for real-time updates |
| `/api/daemon/status` | GET | Daemon status |
| `/api/daemon/queue` | GET | Daemon queue |
| `/api/notifications/config` | GET | Notification config |
| `/api/notifications/recent` | GET | Recent notifications |

---

## Performance

### Benchmarks

Tested on MacBook Pro M1, 16GB RAM, Claude Sonnet 4:

| Operation | Latency | Cost |
|-----------|---------|------|
| Skill execution | <100ms | $0 |
| Quick task (simple) | 1-2 min | $0.10-0.30 |
| Quick task (medium) | 3-5 min | $0.30-0.80 |
| PRD (8 stories) | 15-30 min | $2-5 |
| Dashboard API | <100ms | N/A |
| Dashboard UI load | <2s | N/A |

### Optimization Tips

**Token Reduction:**
- Use skills for validation/formatting (zero tokens)
- Use quick mode for simple tasks (20-40% reduction)
- Use complexity detection to avoid over-engineering

**Cost Reduction:**
- Skills replace LLM calls (100% savings)
- Quick mode lighter than PRD (50-70% savings)
- Daemon batching reduces setup overhead

**Time Reduction:**
- Quick mode 5-10x faster for small tasks
- Skills instant (no LLM latency)
- Dashboard eliminates polling overhead

---

## Troubleshooting

See `docs/MIGRATION-PHASE2.md` for full troubleshooting guide.

**Common Issues:**

| Issue | Solution |
|-------|----------|
| Skills not found | Ensure `skills/` directory exists |
| Quick mode timeout | Set `QUICK_TASK_TIMEOUT` env var |
| Daemon won't start | Check `daemon status`, kill stale PID |
| Dashboard 401 | Get token: `dashboard generate-token` |
| Notifications not sending | Check config in `.claude-loop/daemon/notifications.json` |

---

## Examples

See `docs/phase2/demo-script.md` for comprehensive examples and demo video script.

**Quick Examples:**

```bash
# Validate PRD before execution
./claude-loop.sh --skill prd-validator --skill-arg prd.json

# Quick fix with auto-commit
./claude-loop.sh quick "fix the login bug" --commit

# Dry-run to see plan without executing
./claude-loop.sh quick "refactor database layer" --dry-run

# Submit to daemon with notification
./claude-loop.sh daemon submit prd.json --priority high --notify slack

# Monitor execution in dashboard
./claude-loop.sh dashboard start
# Open http://localhost:8080
```

---

## Next Steps

- Read the [Migration Guide](../MIGRATION-PHASE2.md)
- Try the [Quick Start Tutorial](#getting-started)
- Watch the [Demo Video](demo-script.md)
- Explore the [API Documentation](../api/dashboard-api.md)
- Check out [Phase 3 Roadmap](#) (coming soon)

---

## Support

For questions, issues, or feature requests:
- GitHub Issues: https://github.com/your-repo/claude-loop/issues
- Documentation: `docs/`
- Integration Tests: `tests/phase2/integration/`
