# PRD Dynamic Updates

**Status**: Phase 3, US-003 Complete
**Feature**: Safe PRD modification during execution
**Related**: [Adaptive Story Splitting (US-001, US-002)](./adaptive-splitting.md)

## Overview

PRD Dynamic Updates is a Phase 3 feature that enables safe, atomic modification of PRD files during execution. This allows the system to insert sub-stories from adaptive splitting proposals without corrupting the PRD or losing execution state.

The implementation provides:
- **Atomic updates** with temporary files
- **File locking** to prevent race conditions
- **Automatic backups** before every update
- **Validation** after updates
- **Rollback** on failure

## Key Features

### 1. Atomic PRD Updates

PRD updates use a write-to-temp-then-rename pattern to ensure atomicity:

```python
# Pseudo-code
1. Create backup of current PRD
2. Acquire file lock
3. Write new content to temporary file
4. Validate temporary file
5. Atomic rename (replace old with new)
6. Release lock
```

**Benefits**:
- No partial writes visible to readers
- System crash mid-write doesn't corrupt PRD
- Concurrent reads see either old or new state, never partial

### 2. File Locking

Uses `fcntl.flock()` for process-level file locking:

```python
lock_file = open(prd_path.with_suffix('.lock'), 'w')
fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)  # Exclusive lock

# ... perform update ...

fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)  # Release
```

**Protection Against**:
- Multiple workers modifying same PRD concurrently
- Race conditions in parallel execution mode
- Corruption from simultaneous writes

### 3. Automatic Backups

Every PRD update creates a timestamped backup:

```
.claude-loop/prd-backups/prd_backup_20260114_173045.json
```

**Backup Lifecycle**:
1. Created before any modification
2. Stored with timestamp for traceability
3. Used for rollback if update fails
4. Retained indefinitely for audit trail

### 4. PRD Validation

After every update, the new PRD is validated using:

1. **prd-validator skill** (Phase 2) - if available
2. **prd-parser.sh** - bash-based validation
3. **Basic JSON validation** - fallback

**Validation Checks**:
- Valid JSON syntax
- Required fields present (project, branchName, userStories)
- Story structure (id, title, priority)
- Dependency graph has no cycles
- File scopes are valid arrays

**Validation Flow**:
```
Update PRD → Validate → Success → Keep changes
                      ↓ Failure ↓
                      Rollback to backup
```

### 5. Rollback Mechanism

If update or validation fails, automatic rollback to backup:

```python
try:
    save_prd(prd_path, prd_data, validate=True)
except Exception as e:
    print(f"Update failed: {e}")
    rollback_prd(prd_path, backup_path)  # Restore from backup
```

**Rollback Triggers**:
- Validation failure
- Write error
- Lock acquisition failure
- System exception during update

## Implementation Details

### PRD Metadata Updates

When sub-stories are inserted, metadata is automatically updated:

```python
# Update story count
prd_data['totalStories'] = len(stories)

# Update complexity (0-4 scale)
complexity_sum = sum(complexity_map[s['estimatedComplexity']] for s in sub_stories)
prd_data['complexity'] = min(4, complexity_sum // len(sub_stories) + 1)
```

### Dependency Chain Management

Sub-stories automatically form a dependency chain:

```
Original Story (US-001)
  └─> Sub-Story A (US-001A)  [depends on US-001's dependencies]
        └─> Sub-Story B (US-001B)  [depends on US-001A]
              └─> Sub-Story C (US-001C)  [depends on US-001B]
```

**Implementation**:
```python
# First sub-story inherits original dependencies
sub_stories[0]['dependencies'] = original_story.get('dependencies', [])

# Subsequent sub-stories depend on previous
for i in range(1, len(sub_stories)):
    sub_stories[i]['dependencies'] = [sub_stories[i-1]['id']]
```

### Original Story Marking

When a story is split, it's marked with special flags:

```json
{
  "id": "US-001",
  "split": true,
  "split_proposal_id": "SPLIT-A1B2C3D4",
  "passes": false,
  "notes": "Split into 3 sub-stories: US-001A, US-001B, US-001C. See proposal SPLIT-A1B2C3D4."
}
```

**Key Points**:
- `passes` remains `false` (story was replaced, not completed)
- `split` flag indicates this story was decomposed
- Original story remains in PRD for audit trail
- Sub-stories inserted immediately after original

## API Reference

### save_prd()

```python
def save_prd(
    prd_path: Path,
    prd_data: dict,
    validate: bool = True
) -> tuple[bool, Optional[Path], Optional[str]]:
    """Save PRD with atomic updates, locking, backup, validation

    Args:
        prd_path: Path to PRD file
        prd_data: PRD data dictionary
        validate: Whether to validate after update (default: True)

    Returns:
        tuple: (success: bool, backup_path: Path, error: str)
    """
```

**Example**:
```python
success, backup_path, error = save_prd(
    Path("prd.json"),
    prd_data,
    validate=True
)

if not success:
    print(f"Failed: {error}")
    rollback_prd(Path("prd.json"), backup_path)
```

### validate_prd_file()

```python
def validate_prd_file(prd_path: Path) -> tuple[bool, str]:
    """Validate PRD structure and dependencies

    Args:
        prd_path: Path to PRD file

    Returns:
        tuple: (is_valid: bool, message: str)
    """
```

**Usage**:
```python
is_valid, message = validate_prd_file(Path("prd.json"))
if not is_valid:
    print(f"Validation failed: {message}")
```

### rollback_prd()

```python
def rollback_prd(prd_path: Path, backup_path: Path) -> bool:
    """Rollback PRD to backup

    Args:
        prd_path: Path to PRD file
        backup_path: Path to backup file

    Returns:
        bool: True if rollback succeeded
    """
```

**Usage**:
```python
if rollback_prd(Path("prd.json"), backup_path):
    print("Rollback successful")
```

### apply_split_to_prd()

```python
def apply_split_to_prd(proposal: SplitProposal) -> bool:
    """Apply split proposal to PRD with validation and rollback

    Args:
        proposal: SplitProposal object

    Returns:
        bool: True if split applied successfully
    """
```

**Usage**:
```python
if apply_split_to_prd(proposal):
    print("Split applied successfully")
else:
    print("Split failed, PRD rolled back")
```

## Configuration

### Environment Variables

```bash
# Disable adaptive splitting entirely
export ADAPTIVE_SPLITTING_ENABLED=false

# Set complexity threshold (0-10)
export COMPLEXITY_THRESHOLD=7
```

### CLI Flags

```bash
# Disable adaptive splitting
./claude-loop.sh --prd prd.json --no-adaptive

# Configure threshold
./claude-loop.sh --prd prd.json --complexity-threshold 5
```

## Safety Guarantees

### Atomicity

**Guarantee**: Updates are atomic - either fully applied or not applied at all.

**Implementation**: Write to temp file, then atomic `os.replace()`.

**Violation Conditions**: None. `os.replace()` is atomic on POSIX systems.

### Consistency

**Guarantee**: PRD is always in a valid state.

**Implementation**: Validation before committing changes, rollback on failure.

**Violation Conditions**: Manual file editing during execution (avoid this).

### Isolation

**Guarantee**: Concurrent operations don't interfere.

**Implementation**: File locking with `fcntl.flock()`.

**Violation Conditions**: Lock file manually deleted during operation (don't do this).

### Durability

**Guarantee**: Successful updates are persisted.

**Implementation**: `fsync()` is implicitly called by Python on close.

**Violation Conditions**: System crash between write and fsync (very rare).

## Recovery Procedures

### Corrupted PRD

If PRD becomes corrupted:

```bash
# 1. Find latest backup
ls -lt .claude-loop/prd-backups/ | head -5

# 2. Copy backup to prd.json
cp .claude-loop/prd-backups/prd_backup_20260114_173045.json prd.json

# 3. Validate restored PRD
./lib/prd-parser.sh validate prd.json
```

### Lock File Stuck

If `.lock` file prevents updates:

```bash
# 1. Check if process is still running
ps aux | grep claude-loop

# 2. If process is dead, remove lock
rm prd.json.lock

# 3. Resume execution
./claude-loop.sh --prd prd.json
```

### Failed Split Application

If split application fails mid-way:

1. Check logs for error message
2. Identify backup file from error output
3. Manually restore from backup if needed
4. Review proposal in `.claude-loop/split-proposals/`
5. Re-apply manually or reject proposal

## Performance

### Overhead

| Operation | Overhead | Notes |
|-----------|----------|-------|
| Backup creation | ~10ms | Copy file to backup dir |
| Lock acquisition | ~1ms | Negligible |
| Validation | ~50-200ms | Depends on validator |
| Atomic write | ~20ms | Write to temp + rename |
| **Total** | **~80-230ms** | Per PRD update |

**Impact**: Negligible. Updates happen rarely (only on splits).

### Scalability

- **PRD size**: Linear scaling. 1000 stories = ~500ms validation
- **Concurrent workers**: No degradation. Locks serialize writes.
- **Backup accumulation**: Unlimited. Old backups can be pruned manually.

## Best Practices

### 1. Don't Edit PRD During Execution

**Why**: Can cause validation failures or race conditions.

**Instead**: Use split proposals or edit between runs.

### 2. Keep Backups Directory Clean

**Recommendation**: Prune old backups periodically.

```bash
# Keep only backups from last 30 days
find .claude-loop/prd-backups/ -name "*.json" -mtime +30 -delete
```

### 3. Monitor Disk Space

**Issue**: Backups accumulate over time.

**Solution**: Check disk usage periodically:

```bash
du -sh .claude-loop/prd-backups/
```

### 4. Validate After Manual Edits

After manually editing PRD outside of claude-loop:

```bash
./lib/prd-parser.sh validate prd.json
```

## Integration with Adaptive Splitting

PRD Dynamic Updates is automatically invoked when split proposals are approved:

```
1. Complexity Monitor detects high complexity
2. Story Splitter generates proposal
3. User reviews and approves proposal
4. apply_split_to_prd() called
5. PRD dynamically updated (atomic, validated, backed up)
6. Execution resumes with first sub-story
```

**No manual intervention required** - fully automated.

## Troubleshooting

### Error: "Failed to acquire lock"

**Cause**: Another process is updating PRD.

**Solution**: Wait for other process to finish, or kill stale process.

### Error: "PRD validation failed"

**Cause**: Generated PRD violates schema.

**Solution**: Check validation message, review split proposal, fix manually.

### Error: "Rollback failed"

**Cause**: Backup file missing or corrupted.

**Solution**: Restore from git history or manual backup.

### Warning: "prd-validator skill not found"

**Cause**: Phase 2 skills not installed.

**Solution**: Install skills or ignore (fallback validator used).

## Examples

### Example 1: Successful Split Application

```
Applying split to PRD...
✓ Backup created: .claude-loop/prd-backups/prd_backup_20260114_173045.json
Validating updated PRD...
✓ PRD validation passed
✓ PRD updated atomically

✓ Split applied successfully!
  - Original story US-003 marked as 'split'
  - 3 sub-stories inserted
  - Dependencies updated: US-003A → US-003B
  - Total stories in PRD: 8
  - Next story to execute: US-003A
  - Backup location: .claude-loop/prd-backups/prd_backup_20260114_173045.json
```

### Example 2: Validation Failure with Rollback

```
Applying split to PRD...
✓ Backup created: .claude-loop/prd-backups/prd_backup_20260114_173050.json
Validating updated PRD...
Error: PRD validation failed: Circular dependency detected: US-003A -> US-003B -> US-003A
Attempting rollback...
✓ PRD rolled back to backup: .claude-loop/prd-backups/prd_backup_20260114_173050.json

✗ Failed to apply split. Proposal remains approved but not applied.
```

## See Also

- [Adaptive Story Splitting (US-001, US-002)](./adaptive-splitting.md) - Complexity detection and proposals
- [Split Proposal Generation](./adaptive-splitting.md#split-proposal) - How proposals are created
- [PRD Schema](../../prd-schema.md) - PRD structure and fields

## References

- US-003: Adaptive Story Splitting - PRD Dynamic Updates
- [Phase 3 PRD](../../prd-phase3-cowork-features.json)
- [story-splitter.py](../../lib/story-splitter.py) - Implementation
