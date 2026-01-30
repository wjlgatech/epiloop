# Phase 1 Troubleshooting Guide

Common issues and solutions for Phase 1 features (Progress Indicators, PRD Templates, Workspace Sandboxing, Checkpoint Confirmations).

## Progress Indicators

### Issue: Progress UI looks broken or garbled

**Symptoms:**
```
â    â    â     [     ] 3/10 stories
ââ³ Implement visual progress bar
```

**Cause**: Terminal doesn't support unicode characters or ANSI colors.

**Solutions:**

1. **Disable progress UI** (recommended for non-TTY):
   ```bash
   ./claude-loop.sh --no-progress
   ```

2. **Use a modern terminal**:
   - ✅ iTerm2 (macOS)
   - ✅ Terminal.app (macOS with SF Mono font)
   - ✅ Windows Terminal
   - ✅ VS Code integrated terminal
   - ❌ Basic xterm without unicode support

3. **Check terminal capabilities**:
   ```bash
   # Check if terminal supports unicode
   echo -e "\u2705 \u23f3 \u25cb"
   # Should show: ✅ ⏳ ○
   ```

### Issue: Progress bar doesn't update

**Symptoms**: Progress bar stays at 0% or doesn't change.

**Possible causes:**

1. **First iteration takes longer**: Progress updates after first story completes.
   - **Solution**: Wait for first story (~2-5 minutes)

2. **Terminal not a TTY**: Running in a pipe or non-interactive mode.
   - **Solution**: Use `--no-progress` for scripts/CI

3. **Terminal resize**: UI may need refresh.
   - **Solution**: Resize terminal window (sends SIGWINCH)

### Issue: Time estimates are wildly inaccurate

**Symptoms**: "~2 hours remaining" but completes in 10 minutes.

**Cause**: Not enough data to estimate velocity.

**Solution**:
- Estimates improve after 2-3 stories complete
- Initial estimates are rough averages
- By story 3-4, estimates are usually accurate

### Issue: Progress UI overlaps with output

**Symptoms**: Claude's output mixed with progress bars.

**Cause**: Output happening while progress UI is rendering.

**Solution**:
- This is expected during certain operations
- Progress UI will redraw and correct itself
- For clean logs, use `--no-progress`

## PRD Templates

### Issue: Template not found

**Symptoms:**
```
Error: Template 'api' not found
```

**Cause**: Invalid template name.

**Solution**:
```bash
# List available templates
./claude-loop.sh --list-templates

# Use exact name from the list
./claude-loop.sh --template api-endpoint  # Not 'api'
```

### Issue: Template variables not substituted

**Symptoms:**
```
{{ENDPOINT_NAME}} in generated PRD instead of actual name
```

**Cause**: Missing or misspelled template variable.

**Solutions:**

1. **Check required variables**:
   ```bash
   # Show template details
   ./claude-loop.sh --template api-endpoint --show

   # Look for "Required variables:" section
   ```

2. **Provide all required variables**:
   ```bash
   ./claude-loop.sh --template api-endpoint \
     --template-var ENDPOINT_NAME=TaskManager \
     --template-var DESCRIPTION="Task management API" \
     --template-var HTTP_METHOD=GET,POST,PUT,DELETE \
     --template-var ENDPOINT_PATH=/api/tasks
   ```

3. **Use interactive mode** (asks for variables):
   ```bash
   ./claude-loop.sh --template api-endpoint --template-interactive
   ```

### Issue: Generated PRD doesn't match my needs

**Symptoms**: Template creates stories I don't want.

**Solutions:**

1. **Edit the generated PRD**:
   ```bash
   # Generate template
   ./claude-loop.sh --template web-feature --template-var FEATURE_NAME=MyFeature

   # Edit prd.json
   vim prd.json

   # Then run
   ./claude-loop.sh
   ```

2. **Choose different template**: Maybe `refactoring` or `bug-fix` fits better

3. **Write custom PRD**: Templates are starting points, not requirements

### Issue: Template generation fails

**Symptoms:**
```
Error: Failed to generate PRD from template
```

**Possible causes:**

1. **Corrupt template file**:
   ```bash
   # Verify template integrity
   ls -la templates/cowork-inspired/
   ```

2. **Missing template directory**:
   ```bash
   # Check templates exist
   ls templates/cowork-inspired/

   # If missing, reinstall claude-loop
   ```

3. **Permission issues**:
   ```bash
   # Check write permissions
   touch prd.json && rm prd.json
   ```

## Workspace Sandboxing

### Issue: Workspace validation fails

**Symptoms:**
```
Error: Workspace path 'src/api' does not exist
```

**Cause**: Specified folder doesn't exist.

**Solutions:**

1. **Create the folders first**:
   ```bash
   mkdir -p src/api tests/api
   ./claude-loop.sh --workspace "src/api,tests/api"
   ```

2. **Check for typos**:
   ```bash
   # Wrong
   ./claude-loop.sh --workspace "src/api,test/api"

   # Right (tests not test)
   ./claude-loop.sh --workspace "src/api,tests/api"
   ```

3. **Use relative paths** from repo root:
   ```bash
   # If you're in a subdirectory, paths should still be from root
   cd src/
   ./claude-loop.sh --workspace "src/api"  # Not just "api"
   ```

### Issue: Workspace path outside repository

**Symptoms:**
```
Error: Workspace path '/Users/name/other-project' is outside repository
```

**Cause**: Workspace must be within the git repository.

**Solution**: Only use paths inside your repo:
```bash
# Wrong
./claude-loop.sh --workspace "/Users/name/other-project"

# Right
./claude-loop.sh --workspace "src,lib"
```

### Issue: Story fails with "file access outside workspace"

**Symptoms:**
```
Error: Story attempted to modify file 'config/app.yaml' outside workspace
```

**Cause**: Story needs files outside the sandboxed folders.

**Solutions:**

1. **Expand workspace** to include needed folders:
   ```bash
   ./claude-loop.sh --workspace "src,lib,config"
   ```

2. **Use permissive mode** (warnings only, doesn't fail):
   ```bash
   ./claude-loop.sh --workspace "src" --workspace-mode permissive
   ```

3. **Remove workspace restriction** if it's too limiting:
   ```bash
   ./claude-loop.sh  # No --workspace flag
   ```

### Issue: Workspace symlink issues

**Symptoms**: Symlinks not followed or causing errors.

**Cause**: Workspace manager checks symlink targets for security.

**Solution**:
- If symlink points outside repo, workspace validation will fail
- Use real paths instead of symlinks
- Or include symlink target in workspace

## Checkpoint Confirmations

### Issue: Too many confirmations

**Symptoms**: Getting interrupted constantly for approval.

**Cause**: Safety level too high.

**Solutions:**

1. **Lower safety level**:
   ```bash
   # From paranoid
   ./claude-loop.sh --safety-level paranoid  # Confirms everything

   # To cautious
   ./claude-loop.sh --safety-level cautious  # Only destructive ops

   # To normal (default)
   ./claude-loop.sh --safety-level normal    # Only sensitive files

   # To yolo (no confirmations)
   ./claude-loop.sh --safety-level yolo      # ⚠️ Use with caution
   ```

2. **Use "Yes to all"** during a confirmation:
   ```
   Your choice: a   # Approve all future checkpoints
   ```

3. **Run in non-interactive mode** (CI/CD):
   ```bash
   ./claude-loop.sh --non-interactive  # Auto-approves all
   ```

### Issue: Checkpoint timeout

**Symptoms**: "Confirmation timed out after 5 minutes"

**Cause**: You didn't respond within the timeout.

**Solution**:
- Respond within 5 minutes
- Or use `--non-interactive` for unattended runs
- Manual test: See `tests/phase1/computer-use/EDGE-CASES.md`

### Issue: Checkpoint prompt doesn't appear

**Symptoms**: Destructive operation happened without asking.

**Possible causes:**

1. **Safety level too low**:
   ```bash
   # Increase safety level
   ./claude-loop.sh --safety-level cautious
   ```

2. **Non-interactive mode enabled**:
   ```bash
   # Check if you accidentally used --non-interactive
   # Remove the flag if you want confirmations
   ```

3. **Operation not classified as destructive**:
   - Safety checker may not detect all destructive operations
   - Report as issue if something dangerous wasn't caught

### Issue: Safety log not written

**Symptoms**: `.claude-loop/safety-log.jsonl` missing or empty.

**Possible causes:**

1. **No destructive operations yet**: Log only records approvals/denials

2. **Permission issues**:
   ```bash
   # Check permissions
   ls -la .claude-loop/

   # Create directory if needed
   mkdir -p .claude-loop
   chmod 755 .claude-loop
   ```

3. **Read-only filesystem**: Falls back to stdout logging

## General Issues

### Issue: Phase 1 features not working

**Symptoms**: Features seem disabled or not available.

**Possible causes:**

1. **Old version of claude-loop**:
   ```bash
   # Check version
   ./claude-loop.sh --version

   # Should be >= v1.0
   # Update if needed
   git pull origin main
   ```

2. **Features explicitly disabled**:
   ```bash
   # Check flags
   --no-progress              # Disables progress UI
   --disable-workspace-checks # Disables workspace sandboxing
   --safety-level yolo        # Disables confirmations
   ```

3. **Missing dependencies**:
   ```bash
   # Phase 1 requires bash 4.0+
   bash --version

   # Check for required tools
   which git tput
   ```

### Issue: Features conflict with custom hooks

**Symptoms**: Custom git hooks or CI fail with Phase 1 enabled.

**Solution**:
```bash
# For CI/CD pipelines
./claude-loop.sh --no-progress --non-interactive --safety-level yolo

# Or disable specific features
./claude-loop.sh --no-progress --disable-workspace-checks
```

### Issue: Performance degradation

**Symptoms**: claude-loop slower with Phase 1 features.

**Measurement**:
```bash
# Run benchmarks
tests/phase1/benchmarks/run-benchmarks.sh
```

**Expected overhead**:
- Progress indicators: <5% overhead
- Workspace validation: <100ms for 1000 files
- Safety checker: <1s for 100 changes
- Templates: <500ms generation

**If overhead exceeds these**:
1. Report issue with benchmark results
2. Disable specific features:
   ```bash
   ./claude-loop.sh --no-progress --disable-workspace-checks
   ```

## Still Stuck?

If your issue isn't covered here:

1. **Check logs**:
   ```bash
   # Iteration logs
   tail -f .claude-loop/runs/*/metrics.json

   # Safety logs
   cat .claude-loop/safety-log.jsonl
   ```

2. **Run edge case tests**:
   ```bash
   tests/phase1/computer-use/common-cases.sh
   tests/phase1/computer-use/edge-cases.sh
   ```

3. **File an issue**:
   - Include: OS, terminal, claude-loop version
   - Include: command you ran and error message
   - Include: relevant logs

4. **Read detailed docs**:
   - `docs/features/progress-indicators.md`
   - `docs/features/prd-templates.md`
   - `docs/features/workspace-sandboxing.md`
   - `docs/features/checkpoint-confirmations.md`

## Quick Fixes Summary

| Problem | Quick Fix |
|---------|-----------|
| Broken unicode | `--no-progress` |
| Too many confirmations | `--safety-level normal` |
| Template not found | `--list-templates` |
| Workspace validation fails | `mkdir -p <folders>` |
| Time estimates wrong | Wait for 2-3 stories |
| File access denied | Expand `--workspace` |
| CI/CD integration | `--no-progress --non-interactive` |
| Want old behavior | `--no-progress --safety-level yolo --disable-workspace-checks` |

---

**Pro tip**: Most issues come from:
1. Terminal incompatibility → Use `--no-progress`
2. Workspace too restrictive → Expand or use `--workspace-mode permissive`
3. Safety too aggressive → Lower to `normal` or `yolo`
