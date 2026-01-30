# Frequently Asked Questions (FAQ) - Phase 2

Common questions about Phase 2 features: Skills, Quick Tasks, Daemon Mode, Dashboard, and Notifications.

## Table of Contents

- [General Questions](#general-questions)
- [Quick Task Mode](#quick-task-mode)
- [Daemon Mode](#daemon-mode)
- [Dashboard](#dashboard)
- [Skills Framework](#skills-framework)
- [Notifications](#notifications)
- [Performance and Costs](#performance-and-costs)
- [Integration and Compatibility](#integration-and-compatibility)

---

## General Questions

### What's new in Phase 2?

Phase 2 introduces five major capabilities:

1. **Skills Architecture**: Deterministic operations with zero token cost
2. **Quick Task Mode**: Natural language tasks without PRD authoring
3. **Daemon Mode**: Background execution with task queuing
4. **Visual Dashboard**: Real-time web-based monitoring
5. **Notifications**: Multi-channel alerts (email, Slack, webhook)

These features enable Cowork-level UX, making claude-loop faster, cheaper, and more user-friendly.

### Is Phase 2 compatible with Phase 1?

**Yes, fully compatible!** Phase 2 is purely additive:

- All Phase 1 PRD features work unchanged
- Existing PRDs execute exactly as before
- No breaking changes to CLI or APIs
- You can mix Phase 1 and Phase 2 features

Example:
```bash
# Phase 1 (still works)
./claude-loop.sh --prd prd.json

# Phase 2 (new capability)
./claude-loop.sh quick "quick fix" --commit

# Combined (Phase 1 + Phase 2 dashboard)
./claude-loop.sh --prd prd.json --dashboard
```

### Do I need to migrate existing workflows?

**No migration required.** Your existing workflows continue working:

- PRD files don't need changes
- Scripts and automation work as-is
- All Phase 1 flags still supported

**Optional**: You can enhance workflows with Phase 2 features:
- Use quick mode for simple tasks instead of creating PRDs
- Use daemon mode for batch processing
- Use dashboard for visibility

### What are the system requirements?

**Minimum**:
- Python 3.8+
- Bash 4.0+
- 500MB disk space
- 2GB RAM

**Recommended**:
- Python 3.10+
- 4GB RAM
- SSD storage

**Optional Dependencies**:
- Flask + flask-cors (for dashboard)
- sendmail or SMTP server (for email notifications)
- Slack workspace (for Slack notifications)

---

## Quick Task Mode

### When should I use quick mode vs PRD mode?

**Use Quick Mode For**:
- Single-file changes
- Bug fixes
- Adding tests
- Documentation updates
- Simple refactoring
- Tasks < 15 minutes
- Complexity score < 60

**Use PRD Mode For**:
- Multi-file features
- Complex refactoring
- New architectural components
- Tasks with dependencies
- Tasks > 15 minutes
- Complexity score ≥ 60

**Rule of Thumb**: If it requires 3+ user stories, use PRD mode.

### How does complexity detection work?

Quick mode analyzes your task description for:

- **Word count**: Longer descriptions = more complex
- **Connectors**: "and", "with", "plus" indicate multiple requirements
- **Architecture keywords**: "refactor", "redesign", "migrate"
- **Multiple components**: "various", "several", "all"
- **Testing requirements**: "tests", "coverage"
- **Integration work**: "API", "database", "external"

**Scoring**:
- 0-29: Simple (5 steps, ~2 min, $0.10-0.30)
- 30-59: Medium (7 steps, ~5 min, $0.30-0.80)
- 60-100: Complex (suggest PRD mode)

**Example**:
```bash
# Simple (score: 15)
./claude-loop.sh quick "fix typo in README"

# Medium (score: 45)
./claude-loop.sh quick "add error handling to login function"

# Complex (score: 75)
./claude-loop.sh quick "refactor entire authentication system with OAuth"
# → Suggests: Use PRD mode instead
```

### Can I chain multiple quick tasks together?

**Yes, sequentially**:

```bash
# Option 1: Shell commands
./claude-loop.sh quick "fix bug" --commit && \
./claude-loop.sh quick "add tests" --commit && \
./claude-loop.sh quick "update docs" --commit
```

**Not Yet**: True parallel execution with dependency management (planned for future).

**Workaround for Parallel**:
```bash
# Start multiple terminal windows
# Terminal 1
./claude-loop.sh quick "fix bug A"

# Terminal 2
./claude-loop.sh quick "fix bug B"
```

### What happens if a quick task fails?

**Immediate**:
- Execution stops
- Error logged to task workspace
- Changes not committed (even with `--commit`)
- Checkpoint saved (every 5 steps)

**Recovery**:
```bash
# Option 1: Resume from checkpoint
./claude-loop.sh quick --continue

# Option 2: Start fresh
./claude-loop.sh quick "same task"
```

**Note**: Checkpoints only exist if task ran ≥ 5 steps.

### How much do quick tasks cost?

**Typical Costs**:
- Simple: $0.10 - $0.30
- Medium: $0.30 - $0.80
- Complex: $0.80 - $2.00+

**Cost Savings vs PRD Mode**:
- 20-40% lower token overhead
- No multi-story coordination overhead
- Single-iteration execution

**View Actual Cost**:
```bash
./claude-loop.sh quick stats
# Shows average cost per task
```

---

## Daemon Mode

### Can I run tasks in the background?

**Yes!** That's what daemon mode is for:

```bash
# Start daemon
./claude-loop.sh daemon start

# Submit task (returns immediately)
./claude-loop.sh daemon submit prd.json --notify email

# Continue working while task runs in background
# Get email when done
```

**Benefits**:
- Terminal free for other work
- Submit multiple tasks to queue
- Get notified on completion
- Batch process overnight

### How do I monitor background tasks?

**Three Ways**:

1. **Check Queue**:
   ```bash
   ./claude-loop.sh daemon queue
   ```

2. **View Logs**:
   ```bash
   tail -f .claude-loop/daemon/daemon.log
   ```

3. **Use Dashboard** (recommended):
   ```bash
   ./claude-loop.sh dashboard start
   # Open http://localhost:8080
   ```

### What happens if the daemon crashes?

**Queue Preserved**: Tasks remain in queue (stored in JSON file)

**Recovery**:
```bash
# Check status
./claude-loop.sh daemon status

# If crashed, restart
./claude-loop.sh daemon stop  # Clean up
./claude-loop.sh daemon start

# Queue automatically resumes
./claude-loop.sh daemon queue  # Verify tasks still there
```

**Running Tasks**: If daemon crashes during execution:
- Task marked as failed
- Can resubmit after fixing issue
- No corruption of other tasks

**Prevention**: Daemon uses graceful shutdown to avoid crashes.

### Can I pause the daemon without stopping it?

**Yes**:

```bash
# Pause queue (finish current task, hold new ones)
./claude-loop.sh daemon pause

# Do maintenance, testing, etc.

# Resume when ready
./claude-loop.sh daemon resume
```

**Use Cases**:
- System maintenance
- Testing new configurations
- Temporarily halt non-urgent work

### How many workers should I use?

**Recommendations**:

| Use Case | Workers | Reason |
|----------|---------|--------|
| Sequential execution | 1 | Simple, stable, no conflicts |
| Independent features | 2-3 | Balance speed and safety |
| Heavy batch processing | 3-5 | Maximize throughput |

**Caution with Many Workers**:
- File conflicts if tasks touch same files
- Memory usage scales linearly
- Complexity in debugging

**Start Small**:
```bash
# Start with 1 worker
./claude-loop.sh daemon start

# Scale up if needed
./claude-loop.sh daemon stop
./claude-loop.sh daemon start 3
```

---

## Dashboard

### What is the dashboard and why should I use it?

**What It Is**: Real-time web interface for monitoring claude-loop execution.

**Benefits**:
- **Visual Progress**: Story grid, progress bar, time tracking
- **Live Logs**: Color-coded streaming logs
- **Cost Tracking**: Token usage and budget alerts
- **File Changes**: See what was modified
- **History**: Browse past runs
- **Mobile Access**: Check from phone

**Without Dashboard**: Tail log files, parse JSON manually

**With Dashboard**: Beautiful UI updates automatically

### Can I access the dashboard remotely?

**Yes, with caution**:

```bash
# Start with public host
./claude-loop.sh dashboard start --host 0.0.0.0

# Access from other devices
http://YOUR_IP_ADDRESS:8080
```

**Security Considerations**:
- Dashboard requires authentication token
- Use only on trusted networks
- Consider VPN for public networks
- HTTPS not included (use reverse proxy if needed)

**Better for Public Access**: Use SSH tunnel

```bash
# On remote machine
./claude-loop.sh dashboard start

# On local machine
ssh -L 8080:localhost:8080 user@remote-host

# Access locally at http://localhost:8080
```

### Can multiple people view the same dashboard?

**Yes**, each with their own browser:

1. **Share auth token** (from `.claude-loop/dashboard/auth_token.txt`)
2. **All viewers see same data** (single execution)
3. **Updates in real-time** via Server-Sent Events

**Collaborative Monitoring**:
```bash
# Start dashboard on server
./claude-loop.sh dashboard start --host 0.0.0.0

# Share URL and token with team
# Everyone sees live progress
```

**Limitations**: No multi-user authentication (yet)

---

## Skills Framework

### How do I create custom skills?

**Step-by-Step**:

1. **Create Skill Directory**:
   ```bash
   mkdir -p skills/my-skill/scripts
   ```

2. **Create SKILL.md** (documentation):
   ```markdown
   # /my-skill - Brief Description

   Longer description here.

   ## Usage
   ```
   /my-skill [args]
   ```

   ## Parameters
   - arg1: Description
   ```

3. **Create Executable Script** (optional):
   ```bash
   cat > skills/my-skill/scripts/main.sh << 'EOF'
   #!/bin/bash
   echo "Executing my skill with args: $@"
   # Your logic here
   exit 0
   EOF
   chmod +x skills/my-skill/scripts/main.sh
   ```

4. **Test**:
   ```bash
   ./claude-loop.sh --skill my-skill --skill-arg "test"
   ```

**Full Guide**: See [Skills Architecture Documentation](../features/skills-architecture.md)

### What's the difference between documentation-only and executable skills?

**Documentation-Only**:
- Just SKILL.md file
- Provides guidance to Claude
- No scripts directory
- Used for patterns, guidelines, instructions

**Example**: Code review guidelines, architecture patterns

**Executable Skills**:
- SKILL.md + scripts directory
- Scripts perform deterministic operations
- Zero token cost (runs outside LLM)
- Used for validation, formatting, generation

**Example**: PRD validator, test scaffolder, commit formatter

### How much do skills cost?

**At Startup**: ~50 tokens per skill (metadata only)

**At Execution**:
- Documentation skills: ~200-500 tokens (full instructions loaded)
- Executable skills: ~0 tokens (script runs, not loaded into LLM)

**Example**:
- 10 skills = ~500 tokens at startup
- Executing 5 deterministic operations = ~0 tokens (vs ~2,500 without skills)

**Savings**: 50-100x for deterministic operations

---

## Notifications

### Can I get notifications when tasks complete?

**Yes, via three channels**:

1. **Email** (sendmail or SMTP)
2. **Slack** (webhook)
3. **Generic Webhook** (any HTTP endpoint)

**Setup**:
```bash
# Initialize
./lib/notifications.sh init

# Configure (edit file)
nano .claude-loop/daemon/notifications.json

# Test
./lib/notifications.sh test-email you@example.com

# Use
./claude-loop.sh daemon submit prd.json --notify email
```

### What triggers notifications?

**Three Events**:

1. **Task Completed**: Success notification
   - Stories completed
   - Time taken
   - Total cost

2. **Task Failed**: Failure notification
   - Error details
   - Failed story
   - Troubleshooting suggestions

3. **Checkpoint Required** (future): Manual approval needed
   - Reason for checkpoint
   - Next steps

### Can I customize notification messages?

**Yes**, via templates:

**Templates Location**: `templates/notifications/`

**Available Templates**:
- `success.txt`
- `failure.txt`
- `checkpoint.txt`

**Variables**:
- `{{TASK_ID}}`: Task identifier
- `{{PROJECT}}`: Project name
- `{{STORIES_COMPLETED}}`: Count
- `{{TIME_TAKEN}}`: Duration
- `{{COST}}`: Estimated cost

**Example Custom Template**:
```bash
cat > templates/notifications/custom.txt << 'EOF'
🚀 Deployment Complete

Project: {{PROJECT}}
Task: {{TASK_ID}}
Stories: {{STORIES_COMPLETED}}
Time: {{TIME_TAKEN}}
Cost: {{COST}}

Ready for QA testing!
EOF
```

---

## Performance and Costs

### How much faster is Phase 2?

**Quick Mode vs PRD Mode**:
- 5-10x faster for simple tasks
- Example: Fix typo
  - PRD mode: Create PRD, validate, execute (~5 min + overhead)
  - Quick mode: Describe, execute (~1 min)

**Skills vs LLM Calls**:
- Instant execution (no API latency)
- Example: Validate PRD
  - Without skills: ~10-15 seconds (API call + processing)
  - With skills: <1 second (local script)

**Overall**: 2-5x faster workflow for typical development tasks

### Does Phase 2 reduce costs?

**Yes, significantly**:

**Skills**: 50-100x cost reduction for deterministic operations
- Validation, formatting, generation = $0 (was ~$0.05-0.20 each)

**Quick Mode**: 20-40% lower token overhead vs PRD mode
- Single-iteration execution
- No multi-story coordination

**Daemon Mode**: Indirect savings
- Batch processing reduces setup overhead
- Run tasks overnight at lower priority

**Dashboard**: Zero token cost
- Separate process, no LLM calls

**Example Savings**:
- 100 validations: $20 saved (skills vs LLM)
- 50 quick tasks: $10-20 saved (vs PRD mode)
- Monthly: $50-100+ in token savings

### What are the resource requirements?

**Disk Space**:
- Core: ~50MB
- Skills cache: ~1MB
- Logs: ~10-100MB (varies with usage)
- Quick tasks: ~1MB per task workspace

**Memory**:
- Base: ~100MB (Python + Bash)
- Dashboard: ~50-100MB (Flask server)
- Daemon: ~100MB + (50MB per worker)
- Browser: ~50-200MB (depends on usage)

**CPU**:
- Minimal during idle
- Moderate during execution (mostly API waiting)
- Dashboard: <5% CPU typical

**Network**:
- API calls to Claude
- Webhook notifications
- Dashboard SSE (minimal)

---

## Integration and Compatibility

### Can I use Phase 2 in CI/CD pipelines?

**Absolutely!** Example:

```yaml
# .github/workflows/deploy.yml
name: Deploy with claude-loop

on: [push]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2

      - name: Setup claude-loop
        run: |
          pip install flask flask-cors

      - name: Start daemon
        run: ./claude-loop.sh daemon start

      - name: Submit deployment tasks
        run: |
          ./claude-loop.sh daemon submit pre-deploy.json high --notify webhook
          ./claude-loop.sh daemon submit deploy-staging.json high --notify webhook

      - name: Wait for completion
        run: |
          while true; do
            status=$(./claude-loop.sh daemon queue | grep "completed" | wc -l)
            if [ $status -eq 2 ]; then break; fi
            sleep 10
          done
```

### Can I integrate with my existing tools?

**Yes, multiple integration points**:

**1. Webhooks**: Send events to any HTTP endpoint
```json
{
  "webhook": {
    "url": "https://your-tool.com/webhook",
    "enabled": true
  }
}
```

**2. Dashboard API**: Consume data in your apps
```javascript
fetch('http://localhost:8080/api/status', {
  headers: {'Authorization': 'Bearer ' + token}
})
```

**3. File-Based**: Parse JSON logs
```bash
# Read execution logs
jq '.stories[] | select(.status=="completed")' \
  .claude-loop/execution_log.jsonl
```

**4. Skills**: Create custom skills for your tools
```bash
# Example: Jira integration skill
./claude-loop.sh --skill jira-create-issue --skill-arg "Bug found"
```

### Does Phase 2 work on Windows?

**Partially**:

- **Windows Subsystem for Linux (WSL)**: ✅ Full support
- **Git Bash**: ⚠️ Most features work
- **Native Windows**: ❌ Not officially supported

**Recommended**: Use WSL2 for best experience

```bash
# Install WSL2 (PowerShell as Admin)
wsl --install

# Inside WSL
git clone https://github.com/your-repo/claude-loop
cd claude-loop
./claude-loop.sh --help
```

### Can I run multiple claude-loop instances simultaneously?

**Yes, with isolation**:

**Option 1: Different Directories**
```bash
# Terminal 1
cd project-a
./claude-loop.sh daemon start

# Terminal 2
cd project-b
./claude-loop.sh daemon start

# Each has own queue, logs, etc.
```

**Option 2: Different Ports (Dashboard)**
```bash
# Terminal 1
./claude-loop.sh dashboard start --port 8080

# Terminal 2
./claude-loop.sh dashboard start --port 8081
```

**Caution**: Ensure projects don't modify same files.

---

## Troubleshooting

### Where can I find help if something goes wrong?

**1. Check Documentation**:
- [Troubleshooting Guide](../troubleshooting/phase2-troubleshooting.md)
- [CLI Reference](../reference/cli-reference.md)
- Feature-specific docs in `docs/features/`

**2. Check Logs**:
```bash
# Daemon
tail -100 .claude-loop/daemon/daemon.log

# Dashboard
tail -100 .claude-loop/dashboard/dashboard.log

# Notifications
tail -100 .claude-loop/daemon/notifications.log
```

**3. Run Tests**:
```bash
./tests/phase2/integration/test_phase2_integration.sh
```

**4. Search Issues**: GitHub Issues (existing solutions)

**5. Ask for Help**: GitHub Discussions or Discord

### How do I report a bug?

**Create GitHub Issue** with:

1. **Title**: Brief description
2. **Description**:
   - What you expected
   - What actually happened
   - Steps to reproduce
3. **Environment**:
   - OS and version
   - Python version
   - claude-loop version
4. **Logs**: Relevant log excerpts
5. **PRD/Task**: Minimal example that reproduces issue

**Template**:
```markdown
**Bug**: Quick task hangs on plan approval

**Expected**: Show plan and wait for input
**Actual**: Shows plan but hangs indefinitely

**Steps**:
1. Run: ./claude-loop.sh quick "test"
2. Plan displays
3. Hangs (no input prompt)

**Environment**:
- OS: Ubuntu 22.04
- Python: 3.10.6
- Version: 2.0.0

**Logs**:
```
[00:12:34] Generating plan...
[00:12:35] Plan generated
[Hangs here]
```
```

---

## See Also

- [Phase 2 Overview](../phase2/README.md)
- [Migration Guide](../MIGRATION-PHASE2.md)
- [Daemon Tutorial](../tutorials/daemon-mode.md)
- [Dashboard Tutorial](../tutorials/dashboard.md)
- [CLI Reference](../reference/cli-reference.md)
- [Troubleshooting Guide](../troubleshooting/phase2-troubleshooting.md)
