# Hook System (US-001 - Tier 1 Pattern Extraction)

The Hook System enables lifecycle extension through user-defined bash scripts that execute at key points during claude-loop execution. Inspired by git hooks and agent-zero's extension points, this system provides surgical customization without modifying core code.

## Overview

Hooks are bash scripts placed in `.claude-loop/hooks/` subdirectories that execute automatically at specific lifecycle events. They receive context via environment variables and can abort execution by returning non-zero exit codes.

**Key Features:**
- 🔌 6 lifecycle hook points (pre/post iteration, pre/post commit, on error, on complete)
- 🔢 Alphanumeric execution order (01-99 prefix convention)
- 📊 JSON logging of all hook executions
- 🛡️ Safe abort mechanism (non-zero exit codes)
- 🎛️ Feature flag control (disabled by default)
- 🔧 Environment variable context passing

## Hook Types

### `pre_iteration`
Executes before each iteration starts.

**Use Cases:**
- Validate dependencies
- Check system resources
- Verify preconditions
- Clean up temporary files

**Example**: Check that required tools are installed

### `post_iteration`
Executes after each iteration completes (success, failure, or partial).

**Use Cases:**
- Collect metrics
- Generate reports
- Update dashboards
- Notify stakeholders

**Example**: Send progress updates to Slack

### `pre_commit`
Executes before creating a git commit.

**Use Cases:**
- Run linters
- Format code
- Update documentation
- Run security scans

**Example**: Run eslint before committing

### `post_commit`
Executes after creating a git commit.

**Use Cases:**
- Push to remote
- Trigger CI/CD
- Send notifications
- Update issue trackers

**Example**: Send commit notification to Slack

### `on_error`
Executes when an iteration fails with an error.

**Use Cases:**
- Create GitHub issues
- Send error notifications
- Capture debug information
- Trigger rollback procedures

**Example**: Automatically create GitHub issue with error details

### `on_complete`
Executes when all stories are complete.

**Use Cases:**
- Generate final reports
- Send completion notifications
- Clean up resources
- Deploy artifacts

**Example**: Send completion notification with summary

## Directory Structure

```
.claude-loop/
├── hooks/
│   ├── pre_iteration/
│   │   ├── 01-check-env.sh
│   │   └── 10-check-dependencies.sh
│   ├── post_iteration/
│   │   └── 50-collect-metrics.sh
│   ├── pre_commit/
│   │   ├── 10-lint.sh
│   │   └── 20-format.sh
│   ├── post_commit/
│   │   └── 90-notify-slack.sh
│   ├── on_error/
│   │   └── 50-create-issue.sh
│   ├── on_complete/
│   │   └── 80-deploy.sh
│   └── examples/
│       ├── 10-check-dependencies.sh
│       ├── 50-create-issue.sh
│       └── 90-notify-slack.sh
└── logs/
    └── hooks.jsonl
```

## Execution Order

Hooks within each directory execute in **alphanumeric order** based on filename. Use numeric prefixes (01-99) to control execution sequence:

- `01-*.sh` - Early execution (preconditions, setup)
- `10-*.sh` - Standard execution
- `50-*.sh` - Middle execution
- `90-*.sh` - Late execution (notifications, cleanup)
- `99-*.sh` - Final execution

**Example execution flow:**
```
pre_iteration/01-check-env.sh       (exits 0 - success)
pre_iteration/10-check-dependencies.sh (exits 0 - success)
pre_iteration/99-final-checks.sh     (exits 1 - ABORT!)
```

If `99-final-checks.sh` returns exit code 1, the iteration is aborted.

## Environment Variables

All hooks receive these environment variables:

| Variable | Description | Example |
|----------|-------------|---------|
| `STORY_ID` | Current story being worked on | `US-001` |
| `ITERATION` | Current iteration number | `3` |
| `WORKSPACE` | Current workspace directory | `/path/to/project` |
| `BRANCH` | Current git branch | `feature/my-feature` |
| `PHASE` | Current execution phase | `implementation` |
| `PRD_FILE` | Path to PRD JSON file | `./prd.json` |
| `SCRIPT_DIR` | claude-loop script directory | `/path/to/claude-loop` |

## Hook Logging

All hook executions are logged to `.claude-loop/logs/hooks.jsonl` in JSON Lines format:

```json
{"timestamp":"2026-01-19T23:00:00Z","hook_type":"pre_iteration","hook_name":"10-check-dependencies.sh","exit_code":0,"duration_ms":125,"output":"[INFO] All dependencies checked","story_id":"US-001","iteration":1}
```

**Fields:**
- `timestamp`: ISO 8601 timestamp
- `hook_type`: Type of hook (pre_iteration, post_iteration, etc.)
- `hook_name`: Hook filename
- `exit_code`: Exit code (0 = success, non-zero = failure)
- `duration_ms`: Execution time in milliseconds
- `output`: Captured stdout/stderr output
- `story_id`: Story ID context
- `iteration`: Iteration number context

## Usage

### 1. Enable Hooks

Hooks are **disabled by default**. Enable with the `--enable-hooks` flag:

```bash
./claude-loop.sh --enable-hooks
```

### 2. Create Hook Script

Create a bash script in the appropriate hooks directory:

```bash
#!/bin/bash
# .claude-loop/hooks/pre_iteration/10-check-dependencies.sh

echo "[pre_iteration] Checking dependencies for $STORY_ID"

# Check for required tools
if ! command -v jq &> /dev/null; then
    echo "[ERROR] jq is not installed"
    exit 1
fi

if ! command -v git &> /dev/null; then
    echo "[ERROR] git is not installed"
    exit 1
fi

echo "[pre_iteration] All dependencies present"
exit 0
```

### 3. Make Hook Executable

```bash
chmod +x .claude-loop/hooks/pre_iteration/10-check-dependencies.sh
```

### 4. Run claude-loop

```bash
./claude-loop.sh --enable-hooks
```

The hook will execute before each iteration.

## Example Hooks

### Example 1: Check Dependencies (pre_iteration)

See `.claude-loop/hooks/examples/10-check-dependencies.sh`

```bash
#!/bin/bash
# Validates required tools before each iteration

REQUIRED_TOOLS=("jq" "git" "python3")
for tool in "${REQUIRED_TOOLS[@]}"; do
    if ! command -v "$tool" &> /dev/null; then
        echo "[ERROR] Missing: $tool"
        exit 1
    fi
done
echo "[INFO] All dependencies present"
exit 0
```

**To use:**
```bash
cp .claude-loop/hooks/examples/10-check-dependencies.sh .claude-loop/hooks/pre_iteration/
chmod +x .claude-loop/hooks/pre_iteration/10-check-dependencies.sh
```

### Example 2: Notify Slack (post_commit)

See `.claude-loop/hooks/examples/90-notify-slack.sh`

```bash
#!/bin/bash
# Sends Slack notification after commit

if [ -z "${SLACK_WEBHOOK_URL:-}" ]; then
    echo "[WARN] SLACK_WEBHOOK_URL not set"
    exit 0
fi

COMMIT_SHA=$(git rev-parse --short HEAD)
COMMIT_MSG=$(git log -1 --pretty=%B)

PAYLOAD=$(cat << EOF
{
  "text": "✅ Commit created: $STORY_ID ($COMMIT_SHA)",
  "blocks": [{
    "type": "section",
    "text": {
      "type": "mrkdwn",
      "text": "*Story:* $STORY_ID\n*Commit:* \`$COMMIT_SHA\`\n*Message:* $COMMIT_MSG"
    }
  }]
}
EOF
)

curl -s -X POST "$SLACK_WEBHOOK_URL" \
    -H 'Content-Type: application/json' \
    -d "$PAYLOAD"

exit 0
```

**To use:**
```bash
export SLACK_WEBHOOK_URL="https://hooks.slack.com/services/YOUR/WEBHOOK/URL"
cp .claude-loop/hooks/examples/90-notify-slack.sh .claude-loop/hooks/post_commit/
chmod +x .claude-loop/hooks/post_commit/90-notify-slack.sh
```

### Example 3: Create GitHub Issue (on_error)

See `.claude-loop/hooks/examples/50-create-issue.sh`

```bash
#!/bin/bash
# Creates GitHub issue when iteration fails

if ! command -v gh &> /dev/null; then
    echo "[WARN] GitHub CLI not installed"
    exit 0
fi

STORY_TITLE=$(jq -r ".userStories[] | select(.id == \"$STORY_ID\") | .title" "$PRD_FILE")
GIT_LOG=$(git log -5 --oneline)

ISSUE_BODY="## Story Failed: $STORY_ID

**Iteration:** $ITERATION
**Branch:** $BRANCH
**Recent Commits:**
\`\`\`
$GIT_LOG
\`\`\`"

gh issue create \
    --title "claude-loop: $STORY_ID failed at iteration $ITERATION" \
    --body "$ISSUE_BODY" \
    --label "bug,claude-loop"

exit 0
```

**To use:**
```bash
gh auth login  # Authenticate GitHub CLI
cp .claude-loop/hooks/examples/50-create-issue.sh .claude-loop/hooks/on_error/
chmod +x .claude-loop/hooks/on_error/50-create-issue.sh
```

## Parallel Execution (Git Worktrees)

Hooks work correctly with parallel execution using git worktrees. Each worktree has its own `.claude-loop/hooks/` directory and isolated execution environment.

**Environment variables reflect the worktree context:**
- `WORKSPACE`: Points to worktree directory
- `BRANCH`: Shows worktree branch
- `PRD_FILE`: Points to worktree PRD file

**Hooks are NOT shared between worktrees** - each worker has independent hooks.

## Error Handling

### Non-Zero Exit Codes

Any hook returning a non-zero exit code **aborts the current operation**:

```bash
#!/bin/bash
# This hook will abort the iteration

if [ ! -f "important-file.txt" ]; then
    echo "[ERROR] Missing important-file.txt"
    exit 1  # ABORT ITERATION
fi

exit 0  # Continue normally
```

**Abort behavior:**
- `pre_iteration`: Aborts iteration, moves to next iteration
- `post_iteration`: Logs error, continues to next iteration
- `pre_commit`: Aborts commit, iteration fails
- `post_commit`: Logs error, continues execution
- `on_error`: Logs error (already in error state)
- `on_complete`: Logs error, completion continues

### Best Practices

1. **Don't fail critical hooks**: For notifications and logging, exit 0 even on failure
2. **Validate inputs**: Check environment variables exist before using
3. **Log output**: Use echo for debugging, all output is captured
4. **Use timeouts**: Prevent hanging hooks with timeout commands
5. **Test hooks**: Run hooks manually before enabling

**Example: Safe notification hook**
```bash
#!/bin/bash
# Safe hook that never fails

if [ -z "${SLACK_WEBHOOK_URL:-}" ]; then
    echo "[WARN] SLACK_WEBHOOK_URL not set, skipping"
    exit 0  # Don't fail
fi

# Try to send notification
curl -s -X POST "$SLACK_WEBHOOK_URL" -d "$payload" || {
    echo "[WARN] Slack notification failed"
    exit 0  # Don't fail
}

exit 0
```

## Configuration

### Feature Flag

Hooks are controlled by the `HOOKS_ENABLED` flag:

```bash
# Enable hooks
./claude-loop.sh --enable-hooks

# Hooks disabled by default (no flag needed)
./claude-loop.sh
```

### Config File Support

You can enable hooks in a config file (if you implement config file support):

```yaml
# .claude-loop/config.yaml
hooks:
  enabled: true
  directory: .claude-loop/hooks
  log_file: .claude-loop/logs/hooks.jsonl
```

## Testing

Run the integration test suite:

```bash
./tests/hooks_test.sh
```

**Tests cover:**
- ✅ Hook directory structure
- ✅ Execution order (alphanumeric)
- ✅ Environment variable passing
- ✅ JSON logging
- ✅ Non-zero exit code handling
- ✅ Feature flag behavior

## Troubleshooting

### Hook Not Executing

**Problem**: Hook script exists but doesn't execute

**Solutions:**
1. Check hook is executable: `chmod +x .claude-loop/hooks/pre_iteration/10-myhook.sh`
2. Verify hooks are enabled: `./claude-loop.sh --enable-hooks`
3. Check hook filename (no spaces, .sh extension)
4. Verify hook is in correct directory (pre_iteration, post_iteration, etc.)

### Hook Failing Silently

**Problem**: Hook fails but no error message

**Solutions:**
1. Check hook logs: `cat .claude-loop/logs/hooks.jsonl | jq .`
2. Run hook manually: `./.claude-loop/hooks/pre_iteration/10-myhook.sh`
3. Add debug output: `echo "[DEBUG] Hook running" >&2`
4. Check hook exit code: `echo $?` after running manually

### Environment Variable Missing

**Problem**: Hook can't access environment variables

**Solutions:**
1. Verify variable is exported by claude-loop
2. Use default values: `${STORY_ID:-unknown}`
3. Check hook execution context (may not be in iteration)

### Hook Takes Too Long

**Problem**: Hook execution is slow

**Solutions:**
1. Add timeout to hook: `timeout 10s command`
2. Run expensive operations in background
3. Check hook logs for duration_ms: `jq '.duration_ms' .claude-loop/logs/hooks.jsonl`
4. Optimize or remove slow hooks

## API Reference

### `execute_hooks()`

Execute all hooks of a specific type.

**Signature:**
```bash
execute_hooks <hook_type> <story_id> <iteration> <workspace> <branch> <phase>
```

**Parameters:**
- `hook_type`: Hook type (pre_iteration, post_iteration, etc.)
- `story_id`: Current story ID
- `iteration`: Current iteration number
- `workspace`: Workspace directory path
- `branch`: Git branch name
- `phase`: Execution phase

**Returns:**
- `0`: All hooks succeeded
- Non-zero: A hook failed (returns hook's exit code)

**Example:**
```bash
execute_hooks "pre_iteration" "US-001" 3 "/path/to/workspace" "main" "implementation"
```

### `log_hook_execution()`

Log hook execution to JSONL file.

**Signature:**
```bash
log_hook_execution <hook_type> <hook_name> <exit_code> <duration_ms> <output>
```

**Parameters:**
- `hook_type`: Hook type
- `hook_name`: Hook filename
- `exit_code`: Hook exit code
- `duration_ms`: Execution duration in milliseconds
- `output`: Captured stdout/stderr

**Example:**
```bash
log_hook_execution "pre_iteration" "10-check.sh" 0 125 "All checks passed"
```

## Migration from Other Systems

### From Git Hooks

Git hooks can be adapted to claude-loop hooks:

**Git `pre-commit` → claude-loop `pre_commit`:**
```bash
# Copy and adapt
cp .git/hooks/pre-commit .claude-loop/hooks/pre_commit/10-original.sh
chmod +x .claude-loop/hooks/pre_commit/10-original.sh

# Adapt to use claude-loop env vars instead of git-specific context
```

### From agent-zero Extensions

agent-zero extension points map to claude-loop hooks:

| agent-zero Extension | claude-loop Hook |
|---------------------|------------------|
| `before_execution()` | `pre_iteration` |
| `after_execution()` | `post_iteration` |
| `on_error()` | `on_error` |
| `on_complete()` | `on_complete` |

## Performance Impact

Hook execution adds minimal overhead:

- **Per-hook overhead**: ~1-5ms (hook discovery + logging)
- **Typical hook execution**: 50-200ms (simple checks)
- **Total overhead**: <500ms per iteration (5-10 hooks)

**Optimization tips:**
1. Minimize number of hooks
2. Use early exit in hooks (fail fast)
3. Cache expensive operations
4. Run heavy operations in background

## Security Considerations

⚠️ **Important Security Notes:**

1. **Hooks execute with full shell access** - Only use trusted hook scripts
2. **Environment variables are exported** - Avoid storing secrets in hooks
3. **Hooks can modify files** - Review hooks before running
4. **Hooks can access network** - Be cautious with external API calls
5. **Hooks run as your user** - They have your permissions

**Best Practices:**
- Review all hooks before enabling
- Store secrets in environment variables (not in hooks)
- Use read-only operations where possible
- Limit hook permissions with dedicated service accounts
- Audit hook logs regularly

## Future Enhancements

Potential future improvements (not yet implemented):

- [ ] Hook timeout configuration
- [ ] Async hook execution (non-blocking)
- [ ] Hook templates and marketplace
- [ ] Hook dependency management
- [ ] Hook configuration validation
- [ ] Hook performance profiling
- [ ] Hook test framework
- [ ] Remote hook execution

## Related Documentation

- [AGENTS.md](../../AGENTS.md) - Pattern documentation
- [Parallel Execution](./parallel-execution.md) - Git worktrees and isolation
- [Phase 1 Features](./phase1-features.md) - Cowork-inspired features
- [Testing Guide](../testing/README.md) - Testing strategies

## Support

For issues or questions:
1. Check troubleshooting section above
2. Review hook logs: `.claude-loop/logs/hooks.jsonl`
3. Test hooks manually
4. Open GitHub issue: [claude-loop/issues](https://github.com/anthropics/claude-loop/issues)

---

**Status**: ✅ Complete (US-001 - Tier 1 Pattern Extraction)
**Version**: 1.0.0
**Last Updated**: 2026-01-19
