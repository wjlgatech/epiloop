# Migration Guide: Upgrading to Phase 1 (Cowork Features)

This guide helps you upgrade from pre-Phase 1 versions of claude-loop to take advantage of the new productivity features.

## What's New in Phase 1?

Phase 1 adds four major productivity features inspired by the Cowork analysis:

1. **Enhanced Progress Indicators** - Real-time UI with acceptance criteria checklists
2. **PRD Templates** - Pre-built templates for common project types
3. **Workspace Sandboxing** - Limit execution scope to specific folders
4. **Checkpoint Confirmations** - Safety system for destructive operations

## Breaking Changes

**None!** Phase 1 is fully backward compatible. All existing PRDs and workflows continue to work without modification.

## New Features & How to Use Them

### 1. Enhanced Progress Indicators

**What it does:** Shows real-time progress with visual indicators, time estimates, and acceptance criteria checklist.

**How to use:**
```bash
# Progress indicators are enabled by default
./claude-loop.sh

# Disable for CI/CD environments
./claude-loop.sh --no-progress
```

**What you'll see:**
```
╔════════════════════════════════════════════════════════════════╗
║ Current Story: US-003
║ Workspace: lib,src
║
║ Overall Progress: [███████░░░] 3/10 stories
║ Time: 15m elapsed | ~35m remaining
║ Currently: Running tests
║
║ Acceptance Criteria:
║   ✅ Create lib/progress-indicators.sh
║   ✅ Add real-time checklist display
║   ⏳ Implement visual progress bar
║   ○ Add time tracking
╚════════════════════════════════════════════════════════════════╝
```

### 2. PRD Templates

**What it does:** Start from proven PRD structures for common project types instead of writing from scratch.

**How to use:**
```bash
# List available templates
./claude-loop.sh --list-templates

# Show template details
./claude-loop.sh --show-template web-feature

# Generate PRD from template (interactive)
./claude-loop.sh --template web-feature

# Generate PRD non-interactively
./claude-loop.sh --template api-endpoint \
  --template-var FEATURE_NAME=user-profile \
  --template-var ENDPOINT_PATH=/api/users/profile \
  --template-output prd.json
```

**Available templates:**
- `web-feature` - Full-stack web features (frontend + backend + tests)
- `api-endpoint` - REST/GraphQL endpoints with validation and docs
- `refactoring` - Code restructuring with backwards compatibility
- `bug-fix` - Issue reproduction, fix, and regression tests
- `documentation` - README/docs updates with examples
- `testing` - Test coverage expansion (unit + integration)

### 3. Workspace Sandboxing

**What it does:** Limits claude-loop to only modify files within specified folders. Prevents accidental changes to unrelated code.

**How to use:**
```bash
# Limit to specific folders
./claude-loop.sh --workspace "lib,src,tests"

# Strict mode (hard fail on out-of-scope access)
./claude-loop.sh --workspace "lib,src" --workspace-mode strict

# Permissive mode (warning only)
./claude-loop.sh --workspace "lib,src" --workspace-mode permissive

# Disable workspace checks
./claude-loop.sh --disable-workspace-checks
```

**Benefits:**
- **Safety:** Prevents accidental modifications to critical files
- **Focus:** Claude only sees relevant files, reducing context size
- **Parallel execution:** Workspaces enable better isolation for parallel PRDs

### 4. Checkpoint Confirmations

**What it does:** Detects destructive operations and prompts for approval before execution.

**How to use:**
```bash
# Cautious mode (confirm destructive operations) - RECOMMENDED
./claude-loop.sh --safety-level cautious

# Paranoid mode (confirm all operations)
./claude-loop.sh --safety-level paranoid

# Normal mode (confirm sensitive files only)
./claude-loop.sh --safety-level normal

# Yolo mode (no confirmations) - USE WITH CAUTION
./claude-loop.sh --safety-level yolo

# Dry-run mode (show what would be confirmed)
./claude-loop.sh --safety-dry-run

# Disable safety checks entirely
./claude-loop.sh --disable-safety
```

**What it detects:**
- File deletions (rm, git rm)
- Major refactors (file renames, large deletions, directory restructuring)
- Sensitive file modifications (.env, credentials, keys, config files)

**Confirmation prompt:**
```
[CHECKPOINT] Confirmation required:
  Action: delete_sensitive
  Description: Deleting sensitive file: .env

Approve this action? [y/n/a/q]:
  y = yes (approve this action)
  n = no (reject this action)
  a = approve all (yes to all future actions)
  q = quit (abort entirely)
```

## Recommended Workflow

For most users, we recommend this setup:

```bash
# Use workspace sandboxing for focused changes
./claude-loop.sh --workspace "lib,src,tests" \
  --workspace-mode strict \
  --safety-level cautious
```

This gives you:
- ✅ Real-time progress visibility
- ✅ Focused execution scope
- ✅ Safety confirmation for destructive operations
- ✅ Audit trail in `.claude-loop/safety-log.jsonl`

## Migrating Existing PRDs

No migration needed! Your existing `prd.json` files work as-is.

**Optional enhancements** you can add to existing PRDs:

```json
{
  "userStories": [
    {
      "id": "US-001",
      "title": "...",
      "acceptanceCriteria": ["..."],

      // NEW: Add fileScope for workspace sandboxing
      "fileScope": ["lib/auth.ts", "src/models/User.ts", "tests/auth.test.ts"],

      // NEW: Add complexity hint
      "estimatedComplexity": "medium",

      // NEW: Add model suggestion
      "suggestedModel": "sonnet"
    }
  ]
}
```

## CI/CD Integration

For CI/CD pipelines, disable interactive features:

```bash
./claude-loop.sh \
  --no-progress \
  --safety-level yolo \
  --non-interactive
```

Or use environment variables:
```bash
export PROGRESS_ENABLED=false
export SAFETY_LEVEL=yolo
export NON_INTERACTIVE=true
./claude-loop.sh
```

## Feature Detection & Fallbacks

Phase 1 features gracefully degrade when not supported:

- **Progress indicators:** Falls back to simple logging on non-TTY terminals
- **Colors/Unicode:** Falls back to ASCII when terminal doesn't support UTF-8
- **Terminal resize:** Gracefully redraws UI on SIGWINCH
- **Workspace validation:** Warns but doesn't fail in permissive mode

## Troubleshooting

### Progress indicators not showing

**Problem:** Progress UI doesn't appear

**Solutions:**
- Check if you're running in a TTY: `[ -t 1 ] && echo "TTY" || echo "Not TTY"`
- Ensure `--no-progress` is not set
- Check terminal supports colors: `echo $TERM`

### Workspace validation failing

**Problem:** "File outside workspace" errors

**Solutions:**
- Use `--workspace-mode permissive` instead of `strict`
- Add additional folders to workspace: `--workspace "lib,src,tests,config"`
- Disable workspace checks: `--disable-workspace-checks`

### Safety confirmations interrupting automated runs

**Problem:** Prompts block CI/CD pipelines

**Solutions:**
- Use `--safety-level yolo` for automated environments
- Use `--non-interactive` mode
- Set safety level via environment: `export SAFETY_LEVEL=yolo`

## Getting Help

- **Documentation:** See `docs/features/` for detailed guides
- **Examples:** Check `examples/` for sample PRDs
- **Issues:** Report bugs at https://github.com/anthropics/claude-loop/issues

## What's Next?

Phase 1 lays the foundation for future improvements:

- **Phase 2:** Automated testing with computer use agent
- **Phase 3:** Performance optimization and scalability
- **Phase 4:** Advanced collaboration features

Stay tuned!
