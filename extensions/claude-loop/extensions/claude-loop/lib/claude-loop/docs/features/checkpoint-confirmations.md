# Checkpoint Confirmations - Safety System

**Status**: ✅ Implemented (US-004)

## Overview

The Checkpoint Confirmation system provides a safety net for destructive operations in claude-loop. It detects potentially dangerous actions (file deletions, major refactors, sensitive file modifications) and prompts for user approval before execution.

## Motivation

During autonomous feature implementation, claude-loop may:
- Delete important files by mistake
- Perform large-scale refactors that are hard to undo
- Modify sensitive files like `.env` or credentials
- Restructure directories unintentionally

The safety system prevents these accidents by:
1. **Detecting** destructive operations before they happen
2. **Prompting** for user confirmation with clear descriptions
3. **Logging** all confirmations to an audit trail
4. **Allowing** different safety levels for different contexts

## Quick Start

### Basic Usage

Enable safety checks with default (normal) level:

```bash
./claude-loop.sh
```

### Different Safety Levels

```bash
# Paranoid: Confirm ALL operations
./claude-loop.sh --safety-level paranoid

# Cautious: Confirm destructive operations and sensitive modifications
./claude-loop.sh --safety-level cautious

# Normal: Confirm only sensitive file modifications (default)
./claude-loop.sh --safety-level normal

# YOLO: No confirmations (use with caution!)
./claude-loop.sh --safety-level yolo
```

### Dry-Run Mode

See what would be confirmed without executing:

```bash
./claude-loop.sh --safety-dry-run
```

### Disable Safety Checks

For trusted CI/CD environments:

```bash
./claude-loop.sh --disable-safety
```

## Features

### 1. File Deletion Detection

Detects when files are being deleted:
- Direct deletion via `rm` or `git rm`
- Deletions in git diffs
- Distinguishes between regular and sensitive files

**Example:**
```
[CHECKPOINT] Confirmation required:
  Action: delete
  Description: Deleting file: tests/old-test.js

Approve this action? [y/n/a/q]:
```

### 2. Major Refactor Detection

Detects large-scale code changes:
- File renames (triggers when >5 files renamed)
- Large deletions (>50 lines removed from a file)
- Directory restructuring

**Example:**
```
[CHECKPOINT] Confirmation required:
  Action: major_refactor
  Description: Major code refactoring detected

Detected major refactors:
  - rename: old-utils.js -> new-utils.js
  - large_deletion: api/routes.js (127 lines)

Approve this action? [y/n/a/q]:
```

### 3. Sensitive File Protection

Automatically detects sensitive files by pattern:
- `.env`, `.env.*` files
- Credential files (`credentials`, `secret`, `password`)
- Private keys (`.pem`, `.key`, `.p12`, `.pfx`)
- SSH keys (`id_rsa`, `id_dsa`, `id_ecdsa`, `id_ed25519`)
- Config files (`.aws/credentials`, `.ssh/config`)
- Package manager configs (`.npmrc`, `.pypirc`, `.dockercfg`)

**Example:**
```
[CHECKPOINT] Confirmation required:
  Action: modify_sensitive
  Description: Modifying sensitive file: .env

Approve this action? [y/n/a/q]:
```

### 4. Batch Confirmation Options

When prompted, you can respond with:
- **y** (yes): Approve this single action
- **n** (no): Reject this action
- **a** (approve all): Approve this and all future actions in this session
- **q** (quit): Abort the entire operation

### 5. Audit Logging

All confirmations are logged to `.claude-loop/safety-log.jsonl`:

```json
{
  "timestamp": "2026-01-13T10:00:00Z",
  "action": "delete_sensitive",
  "description": "Deleting sensitive file: .env.backup",
  "decision": "approved",
  "safety_level": "cautious"
}
```

### 6. Custom Safety Rules

Define custom sensitive file patterns in `.claude-loop/safety-rules.json`:

```json
{
  "sensitive_patterns": [
    "database\\.yml$",
    "private.*\\.json$",
    "master.*\\.key$"
  ]
}
```

## Safety Levels

### Paranoid

**Use when:** Working in production, modifying critical systems, or maximum safety needed

**Confirms:**
- ✅ All operations (every file modification)
- ✅ All deletions
- ✅ All refactors
- ✅ All sensitive file access

**Example scenarios:**
- Deploying to production
- Modifying authentication systems
- Working with customer data

### Cautious (Recommended)

**Use when:** Standard development work with safety nets

**Confirms:**
- ✅ File deletions
- ✅ Major refactors (>50 line deletions, >5 file renames)
- ✅ Sensitive file modifications
- ❌ Regular file modifications

**Example scenarios:**
- Feature development
- Bug fixes
- Refactoring sessions

### Normal (Default)

**Use when:** Routine development with minimal interruptions

**Confirms:**
- ✅ Sensitive file modifications only
- ❌ Regular file deletions
- ❌ Regular file modifications
- ❌ Refactors

**Example scenarios:**
- Adding new features
- Writing tests
- Updating documentation

### YOLO (No Confirmations)

**Use when:** Full trust mode or CI/CD automation

**Confirms:**
- ❌ Nothing (all operations auto-approved)

**Example scenarios:**
- CI/CD pipelines
- Trusted automated testing
- Personal projects where you have full version control

## Integration with claude-loop

The safety checker integrates seamlessly with the claude-loop workflow:

1. **Before each iteration**: Safety checker is initialized based on safety level
2. **During code changes**: Git diffs are analyzed for destructive operations
3. **Before commits**: Confirmations are requested for detected issues
4. **After commits**: All decisions are logged to audit trail

## CLI Usage

### Standalone Commands

```bash
# Check a git diff for destructive operations
./lib/safety-checker.sh check-diff /tmp/changes.diff

# Check if a file is sensitive
./lib/safety-checker.sh is-sensitive .env
echo $?  # Returns 0 if sensitive, 1 otherwise

# List all sensitive file patterns
./lib/safety-checker.sh list-patterns

# Initialize with specific safety level
./lib/safety-checker.sh init cautious
```

### Library Usage (in scripts)

```bash
# Source the library
source lib/safety-checker.sh

# Initialize
init_safety_checker "cautious" "false" "false"

# Check file sensitivity
if is_sensitive_file ".env"; then
    echo "This is a sensitive file!"
fi

# Request confirmation
if request_confirmation "delete" "Deleting config.json"; then
    rm config.json
else
    echo "Operation cancelled"
fi

# Check a diff file
if check_diff "/tmp/changes.diff"; then
    git apply /tmp/changes.diff
else
    echo "Diff contains rejected operations"
fi
```

## Environment Variables

Configure the safety checker via environment variables:

```bash
# Safety level
export SAFETY_LEVEL=cautious

# Non-interactive mode (auto-approve)
export SAFETY_NON_INTERACTIVE=true

# Dry-run mode (show what would be confirmed)
export SAFETY_DRY_RUN=true

# Log file location
export SAFETY_LOG_FILE=.claude-loop/safety-log.jsonl

# Custom rules file
export SAFETY_RULES_FILE=.claude-loop/safety-rules.json
```

## CI/CD Integration

### GitHub Actions

```yaml
- name: Run claude-loop with safety checks disabled
  run: ./claude-loop.sh --disable-safety
  env:
    CI: true
```

### GitLab CI

```yaml
claude-loop:
  script:
    - ./claude-loop.sh --safety-level yolo
  only:
    - main
```

### Jenkins

```groovy
stage('Claude Loop') {
    steps {
        sh './claude-loop.sh --disable-safety'
    }
}
```

## Best Practices

### 1. Use Appropriate Safety Levels

- **Development**: `cautious` or `normal`
- **Production changes**: `paranoid`
- **CI/CD**: `yolo` or `--disable-safety`

### 2. Review Audit Logs

Periodically review `.claude-loop/safety-log.jsonl` to:
- Identify patterns in rejections
- Understand what operations are being performed
- Audit who approved what

### 3. Customize Sensitive Patterns

Add project-specific patterns to `.claude-loop/safety-rules.json`:

```json
{
  "sensitive_patterns": [
    "secrets/.*",
    ".*\\.terraform\\.tfstate$",
    "kubeconfig.*"
  ]
}
```

### 4. Use Dry-Run for Testing

Before running on important projects:

```bash
./claude-loop.sh --safety-dry-run --safety-level paranoid
```

This shows what would be confirmed without actually executing.

### 5. Combine with Workspace Sandboxing

For maximum safety, combine with workspace sandboxing:

```bash
./claude-loop.sh \
    --workspace "lib,tests" \
    --workspace-mode strict \
    --safety-level cautious
```

This limits both the scope (workspace) and actions (safety).

## Troubleshooting

### Issue: Too Many Confirmations

**Solution**: Lower the safety level

```bash
# Instead of paranoid
./claude-loop.sh --safety-level paranoid

# Use cautious or normal
./claude-loop.sh --safety-level cautious
```

### Issue: Safety Checks Blocking CI/CD

**Solution**: Disable safety checks in CI environments

```bash
if [ -n "$CI" ]; then
    ./claude-loop.sh --disable-safety
else
    ./claude-loop.sh --safety-level cautious
fi
```

### Issue: False Positives (Non-sensitive files flagged)

**Solution**: Update sensitive patterns or override in custom rules

1. Check current patterns:
```bash
./lib/safety-checker.sh list-patterns
```

2. Override in `.claude-loop/safety-rules.json` (not recommended)

3. Or use a lower safety level for that operation

### Issue: Missed Sensitive Files

**Solution**: Add custom patterns

Create `.claude-loop/safety-rules.json`:

```json
{
  "sensitive_patterns": [
    "your-sensitive-pattern.*",
    "another\\.pattern$"
  ]
}
```

### Issue: Non-Interactive Mode Not Working

**Check**: Ensure you're either:
1. Setting `--disable-safety`, or
2. Running in a non-TTY environment (CI), or
3. Setting `SAFETY_NON_INTERACTIVE=true`

## Technical Implementation

### Architecture

```
lib/safety-checker.sh
├── Configuration
│   ├── SAFETY_LEVEL (paranoid/cautious/normal/yolo)
│   ├── SAFETY_NON_INTERACTIVE (true/false)
│   └── SAFETY_DRY_RUN (true/false)
├── Detection Functions
│   ├── detect_file_deletions()
│   ├── detect_major_refactors()
│   ├── detect_directory_restructuring()
│   └── is_sensitive_file()
├── Confirmation System
│   ├── request_confirmation()
│   ├── should_request_confirmation()
│   └── log_confirmation()
└── CLI Interface
    ├── check-diff
    ├── check-file
    ├── is-sensitive
    └── list-patterns
```

### Detection Algorithms

**File Deletion Detection:**
- Parses git diff for `--- a/file` followed by `+++ /dev/null`
- Identifies file path and checks sensitivity

**Major Refactor Detection:**
- Counts lines deleted per file (threshold: 50)
- Detects file renames via `rename from/to` in diff
- Counts total renames (threshold: 5)

**Sensitive File Detection:**
- Pattern matching against regex list
- Checks basename against patterns
- Extensible via custom rules

### Integration Points

1. **Initialization**: `check_safety_checker()` called in main()
2. **Before commits**: Git diffs analyzed via `check_diff()`
3. **File access**: Individual file checks via `check_file()`
4. **Audit trail**: All decisions logged to JSONL

## Comparison with Other Systems

### vs. Git Hooks

| Feature | Safety Checker | Git Hooks |
|---------|---------------|-----------|
| Pre-commit checks | ✅ | ✅ |
| Interactive prompts | ✅ | ❌ |
| Multiple safety levels | ✅ | ❌ |
| Audit logging | ✅ | ❌ |
| Custom rules | ✅ | ⚠️ (complex) |
| CI/CD friendly | ✅ | ⚠️ (can block) |

### vs. Manual Review

| Feature | Safety Checker | Manual Review |
|---------|---------------|--------------|
| Speed | Fast | Slow |
| Consistency | Always | Varies |
| Automation | Yes | No |
| Human judgment | Limited | Full |
| Scalability | High | Low |

## Future Enhancements

Planned improvements for future versions:

1. **ML-based sensitivity detection**: Learn from past confirmations
2. **Role-based permissions**: Different levels for different team members
3. **Approval workflows**: Multi-user approval for critical operations
4. **Undo mechanism**: One-click rollback of approved operations
5. **Integration with PR reviews**: Automatic PR comments for destructive operations

## Related Features

- **[Workspace Sandboxing](workspace-sandboxing.md)**: Limit execution scope to specific folders
- **[Progress Indicators](progress-indicators.md)**: Visual progress tracking with acceptance criteria
- **[PRD Templates](prd-templates.md)**: Pre-built templates for common project types

## Support

For issues or questions:
- GitHub Issues: [claude-loop/issues](https://github.com/anthropics/claude-loop/issues)
- Documentation: [docs/](../../)
- Examples: [examples/](../../examples/)

## Version History

- **v1.0** (2026-01-13): Initial implementation (US-004)
  - File deletion detection
  - Major refactor detection
  - Sensitive file protection
  - Multiple safety levels
  - Audit logging
  - Custom rules support
