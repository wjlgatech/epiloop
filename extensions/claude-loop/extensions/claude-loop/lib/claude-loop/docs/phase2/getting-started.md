# Phase 2 Getting Started Guide

Welcome to claude-loop Phase 2! This guide will help you get started with the new features: Skills Architecture, Quick Task Mode, Daemon Mode, and Visual Progress Dashboard.

## Table of Contents

- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Quick Start](#quick-start)
- [Feature Overview](#feature-overview)
- [Next Steps](#next-steps)

## Prerequisites

Before you begin, ensure you have:

- **Bash 3.2+** (included in macOS and most Linux distributions)
- **Python 3.7+** with pip
- **Git** for version control
- **Claude Code CLI** installed and configured
- **Basic command-line knowledge**

Optional dependencies for specific features:
- **Flask and flask-cors** (for dashboard): `pip3 install flask flask-cors`
- **sendmail or SMTP** (for email notifications)
- **curl** (for webhook notifications)

## Installation

### 1. Clone the Repository

```bash
git clone https://github.com/yourusername/claude-loop.git
cd claude-loop
```

### 2. Install Python Dependencies

```bash
# For dashboard support
pip3 install flask flask-cors

# Verify installation
python3 -c "import flask; print('Flask installed successfully')"
```

### 3. Verify Installation

```bash
# Test basic functionality
./claude-loop.sh --help

# Check for Phase 2 features
./claude-loop.sh --list-skills
```

## Quick Start

### Your First PRD Execution (Phase 1)

Start with the traditional PRD-based workflow:

```bash
# 1. Create a simple PRD
cat > my-first-prd.json <<EOF
{
  "project": "my-first-project",
  "branchName": "feature/first-project",
  "description": "My first claude-loop project",
  "userStories": [
    {
      "id": "US-001",
      "title": "Create Hello World Script",
      "description": "Create a simple bash script that prints 'Hello World'",
      "priority": 1,
      "acceptanceCriteria": [
        "Create hello.sh script",
        "Script prints 'Hello World' when executed",
        "Script is executable"
      ],
      "passes": false
    }
  ]
}
EOF

# 2. Execute the PRD
./claude-loop.sh --prd my-first-prd.json

# 3. View the results
cat hello.sh
./hello.sh
```

### Your First Quick Task (Phase 2)

Try the new Quick Task Mode for lightweight tasks:

```bash
# Execute a simple task without writing a PRD
./claude-loop.sh quick "Create a function that calculates fibonacci numbers"

# The system will:
# 1. Parse your task description
# 2. Generate an execution plan
# 3. Ask for your approval
# 4. Execute the task
# 5. Create a git commit automatically

# View task history
./claude-loop.sh quick history
```

### Using Skills

Skills are deterministic operations that run instantly without AI:

```bash
# List available skills
./claude-loop.sh --list-skills

# Validate a PRD
./claude-loop.sh --skill prd-validator --skill-arg my-first-prd.json

# Generate test scaffolding
./claude-loop.sh --skill test-scaffolder --skill-arg hello.sh

# Format a commit message
./claude-loop.sh --skill commit-formatter --skill-arg "added new feature"
```

### Starting the Dashboard

Monitor your executions in real-time with the web dashboard:

```bash
# Start the dashboard server
./claude-loop.sh dashboard start

# The dashboard will be available at:
# http://localhost:8080

# Get your authentication token
./claude-loop.sh dashboard generate-token

# Stop the dashboard when done
./claude-loop.sh dashboard stop
```

### Background Execution with Daemon Mode

Run tasks in the background with the daemon:

```bash
# Start the daemon
./claude-loop.sh daemon start

# Submit a PRD for background execution
./claude-loop.sh daemon submit my-prd.json

# Check daemon status
./claude-loop.sh daemon status

# View the queue
./claude-loop.sh daemon queue

# Stop the daemon
./claude-loop.sh daemon stop
```

## Feature Overview

### Skills Architecture

**What it is**: Deterministic operations with progressive disclosure (metadata → instructions → resources).

**When to use**:
- Validating PRDs before execution
- Generating test scaffolding
- Formatting commit messages
- Generating API specifications
- Analyzing story complexity

**Benefits**:
- Zero AI cost (deterministic scripts)
- Instant execution (<1 second)
- Consistent results
- Easy to create custom skills

**Learn more**: See [Skills Development Tutorial](../tutorials/skills-development.md)

### Quick Task Mode

**What it is**: Natural language task execution without PRD authoring.

**When to use**:
- Simple tasks (< 3 stories)
- Single file changes
- Quick fixes or additions
- Exploratory work
- Tasks under $1 cost

**Benefits**:
- 20-40% token reduction vs full PRD
- Faster iteration (no PRD authoring)
- Automatic commit generation
- Task history tracking

**Learn more**: See [Quick Task Mode Tutorial](../tutorials/quick-task-mode.md)

### Daemon Mode

**What it is**: Background task execution with queue management.

**When to use**:
- Long-running tasks (> 1 hour)
- Batch processing multiple PRDs
- Overnight execution
- When you need notifications on completion

**Benefits**:
- Fire-and-forget workflow
- Priority queue management
- Notification integration
- Graceful shutdown

**Learn more**: See [Daemon Mode Tutorial](../tutorials/daemon-mode.md)

### Visual Progress Dashboard

**What it is**: Web-based real-time monitoring dashboard.

**When to use**:
- Monitoring long-running executions
- Tracking multiple concurrent tasks
- Viewing execution history
- Analyzing costs and metrics

**Benefits**:
- Real-time progress updates
- Story status visualization
- Cost tracking with alerts
- File changes viewer
- Dark mode support

**Learn more**: See [Dashboard Tutorial](../tutorials/dashboard.md)

## Next Steps

Now that you've completed the quick start, explore these topics:

### Tutorials

1. **[Skills Development Tutorial](../tutorials/skills-development.md)** - Create custom skills
2. **[Quick Task Mode Tutorial](../tutorials/quick-task-mode.md)** - Master quick tasks
3. **[Daemon Mode Tutorial](../tutorials/daemon-mode.md)** - Background execution
4. **[Dashboard Tutorial](../tutorials/dashboard.md)** - Web UI monitoring

### Configuration

- **[Troubleshooting Guide](../troubleshooting/phase2-troubleshooting.md)** - Common issues
- **[CLI Reference](../reference/cli-reference.md)** - All command-line options
- **[API Reference](../api/dashboard-api.md)** - REST API documentation

### Advanced Topics

- **[PRD Schema v2](../reference/prd-schema-v2.md)** - Advanced PRD features
- **[Notification Configuration](../features/daemon-notifications.md)** - Email, Slack, webhooks
- **[Migration Guide](../MIGRATION-PHASE2.md)** - Upgrading from Phase 1

## Getting Help

If you run into issues:

1. **Check the troubleshooting guide**: [troubleshooting/phase2-troubleshooting.md](../troubleshooting/phase2-troubleshooting.md)
2. **Review the FAQ**: [FAQ](../FAQ.md)
3. **Check logs**: `.claude-loop/runs/{timestamp}/` contains execution logs
4. **GitHub Issues**: Report bugs at https://github.com/yourusername/claude-loop/issues

## What's Next?

After getting comfortable with Phase 2 features:

- **Create your own skills** using the [Skills Development Tutorial](../tutorials/skills-development.md)
- **Try concurrent execution** with daemon mode and multiple workers
- **Monitor executions** with the dashboard in real-time
- **Set up notifications** for long-running tasks
- **Explore cost optimization** using the cost-optimizer skill

Welcome to claude-loop Phase 2! 🚀
