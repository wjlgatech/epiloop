# PRD Workflow Guide for Contributors

This guide documents the complete workflow for creating, managing, and implementing PRDs (Product Requirement Documents) in claude-loop.

## Table of Contents

1. [Overview](#overview)
2. [Directory Structure](#directory-structure)
3. [Lifecycle States](#lifecycle-states)
4. [Getting Started](#getting-started)
5. [CLI Commands Reference](#cli-commands-reference)
6. [Security Model](#security-model)
7. [Audit and Integrity](#audit-and-integrity)
8. [Troubleshooting](#troubleshooting)
9. [Quick Reference Card](#quick-reference-card)

---

## Overview

The PRD management system provides:

- **Lifecycle tracking**: Draft → Active → Completed (or Abandoned)
- **Integrity verification**: SHA256 hashes ensure PRDs aren't modified after approval
- **Audit trail**: All state changes are logged with hash chains
- **Discoverability**: Search and filter PRDs by status, tags, and keywords
- **Automation**: Integration with `claude-loop.sh` for autonomous implementation

### Key Components

| Component | Location | Purpose |
|-----------|----------|---------|
| `prd-manager.py` | `lib/prd-manager.py` | CLI for PRD lifecycle management |
| `prd-indexer.py` | `lib/prd-indexer.py` | Searchable index builder |
| `prd-retention.py` | `lib/prd-retention.py` | Retention policy enforcement |
| Schema | `schemas/manifest.schema.json` | MANIFEST.yaml validation |

---

## Directory Structure

PRDs are organized in the `prds/` directory by their lifecycle status:

```
prds/
├── active/           # PRDs currently being implemented
│   └── my-feature/
│       ├── MANIFEST.yaml   # Metadata and status
│       ├── prd.json        # User stories
│       └── progress.txt    # Implementation log
│
├── completed/        # Successfully completed PRDs
│   └── old-feature/
│       ├── MANIFEST.yaml
│       └── prd.json
│
├── abandoned/        # Cancelled or superseded PRDs
│   └── failed-idea/
│       ├── MANIFEST.yaml
│       └── prd.json
│
├── drafts/           # Work-in-progress PRDs
│   └── new-idea/
│       ├── MANIFEST.yaml
│       ├── prd.json
│       └── progress.txt
│
└── archive/          # Archived PRDs (after retention period)
    └── old-prd.tar.gz
```

### Files in Each PRD Directory

| File | Required | Description |
|------|----------|-------------|
| `MANIFEST.yaml` | Yes | PRD metadata, status, approval info |
| `prd.json` | Yes | User stories with acceptance criteria |
| `progress.txt` | No | Implementation notes and learnings |

---

## Lifecycle States

### State Machine

```
                    ┌──────────────────────────┐
                    │                          │
                    v                          │
┌─────────┐    ┌─────────┐    ┌───────────┐   │
│  DRAFT  │───>│ ACTIVE  │───>│ COMPLETED │   │
└─────────┘    └─────────┘    └───────────┘   │
     │              │                          │
     │              │                          │
     v              v                          │
┌───────────────────────┐                      │
│       ABANDONED       │──────────────────────┘
└───────────────────────┘  (can be superseded by new PRD)
```

### State Descriptions

| Status | Directory | Description |
|--------|-----------|-------------|
| `draft` | `prds/drafts/` | Initial state; PRD is being written |
| `active` | `prds/active/` | Approved and under implementation |
| `completed` | `prds/completed/` | All stories done, implementation finished |
| `abandoned` | `prds/abandoned/` | Cancelled or superseded |

### Allowed Transitions

| From | To | Command | Requirements |
|------|----|---------|--------------|
| `draft` | `active` | `approve` | Needs approver, creates approval hash |
| `draft` | `abandoned` | `abandon` | Must provide reason |
| `active` | `completed` | `complete` | All stories must pass (or use `--force`) |
| `active` | `abandoned` | `abandon` | Must provide reason |
| `completed` | - | - | Terminal state |
| `abandoned` | - | - | Terminal state |

---

## Getting Started

### Prerequisites

```bash
# Ensure Python 3 with required packages
pip install pyyaml

# Set up the virtual environment (optional but recommended)
python3 -m venv .venv
source .venv/bin/activate
pip install pyyaml jsonschema
```

### Creating Your First PRD

1. **Create a new PRD**:

   ```bash
   python3 lib/prd-manager.py create DOC-020 "My New Feature" --type feature
   ```

   This creates:
   - `prds/drafts/my-new-feature/MANIFEST.yaml`
   - `prds/drafts/my-new-feature/prd.json`
   - `prds/drafts/my-new-feature/progress.txt`

2. **Edit the prd.json** to add your user stories:

   ```json
   {
     "project": "my-new-feature",
     "branchName": "feature/doc-020",
     "description": "Description of the feature",
     "userStories": [
       {
         "id": "DOC-020-001",
         "title": "First story",
         "description": "What needs to be done",
         "acceptanceCriteria": [
           "Criterion 1",
           "Criterion 2"
         ],
         "priority": 1,
         "passes": false,
         "notes": ""
       }
     ]
   }
   ```

3. **Get approval**:

   ```bash
   python3 lib/prd-manager.py approve DOC-020 --approver "Reviewer Name"
   ```

4. **Run claude-loop** to implement:

   ```bash
   ./claude-loop.sh --prd prds/active/my-new-feature/prd.json
   ```

5. **Mark complete** when done:

   ```bash
   python3 lib/prd-manager.py complete DOC-020
   ```

---

## CLI Commands Reference

### Core Commands

#### `list` - List PRDs

Show all PRDs or filter by status.

```bash
# List all PRDs
python3 lib/prd-manager.py list

# List only active PRDs
python3 lib/prd-manager.py list --status active

# Output as JSON (for scripting)
python3 lib/prd-manager.py list --json
```

**Example output:**
```
ID         Title                         Status      Stories   Priority  Owner
---------------------------------------------------------------------------------
DOC-015    Comprehensive Tests           draft       0/7       medium    jialiang.wu
DOC-013    Create Contributor Guide      active      0/6       medium    jialiang.wu
SCALE-001  Stratified Memory v2          completed   16/16     high      jialiang.wu

Total: 3 PRD(s)
```

#### `show` - Show PRD Details

Display detailed information about a specific PRD.

```bash
# By PRD ID
python3 lib/prd-manager.py show DOC-013

# By path
python3 lib/prd-manager.py show prds/active/contributor-guide/

# Output as JSON
python3 lib/prd-manager.py show DOC-013 --json
```

**Example output:**
```
PRD: DOC-013
============

Title:       Create Contributor Guide
Status:      active
Owner:       jialiang.wu
Priority:    medium
Path:        prds/active/contributor-guide

Description:
  Document the new PRD workflow for contributors

Progress:    2/6 stories completed
Tags:        documentation, guides

Timeline:
  Created:   2026-01-12T08:00:00Z
  Approved:  2026-01-12T10:00:00Z

User Stories:
------------------------------------------------------------
  ○ DOC-013-001: Write overview section
  ✓ DOC-013-002: Document CLI commands
  ✓ DOC-013-003: Document lifecycle states
  ○ DOC-013-004: Add security documentation
```

#### `search` - Search PRDs

Search PRDs by keyword or tag.

```bash
# Search by keyword
python3 lib/prd-manager.py search memory

# Search with tag filter
python3 lib/prd-manager.py search documentation --tag guides

# Output as JSON
python3 lib/prd-manager.py search auth --json
```

### Lifecycle Commands

#### `create` - Create New PRD

Create a new PRD in the drafts directory.

```bash
# Create a feature PRD
python3 lib/prd-manager.py create DOC-020 "User Authentication" --type feature

# Create a bugfix PRD
python3 lib/prd-manager.py create BUG-001 "Fix Login Issue" --type bugfix

# Create a refactor PRD
python3 lib/prd-manager.py create REF-001 "Refactor Auth Module" --type refactor

# Specify owner (defaults to git user)
python3 lib/prd-manager.py create DOC-021 "New Feature" --owner alice@example.com

# Output as JSON
python3 lib/prd-manager.py create DOC-022 "Another Feature" --json
```

**PRD ID format**: Must match `PREFIX-NNN` (e.g., `DOC-001`, `FEAT-042`, `BUG-123`)

**PRD types and their templates**:
| Type | Branch Prefix | Use Case |
|------|---------------|----------|
| `feature` | `feature/` | New functionality |
| `bugfix` | `fix/` | Bug fixes |
| `refactor` | `refactor/` | Code refactoring |

#### `approve` - Approve PRD

Transition a draft PRD to active status.

```bash
# Basic approval
python3 lib/prd-manager.py approve DOC-020

# With specific approver
python3 lib/prd-manager.py approve DOC-020 --approver "Alice Smith"

# With approval notes
python3 lib/prd-manager.py approve DOC-020 --notes "Approved with minor suggestions"

# Output as JSON
python3 lib/prd-manager.py approve DOC-020 --json
```

**What happens on approval**:
1. SHA256 hash of `prd.json` is computed (for integrity verification)
2. `approval` block added to MANIFEST.yaml
3. PRD moved from `prds/drafts/` to `prds/active/`
4. Audit log entry created
5. Index updated

#### `abandon` - Abandon PRD

Mark a PRD as abandoned (cancelled or superseded).

```bash
# Abandon with reason (required)
python3 lib/prd-manager.py abandon DOC-020 --reason "Requirements changed"

# Abandon and link to replacement PRD
python3 lib/prd-manager.py abandon DOC-020 \
  --reason "Superseded by new approach" \
  --superseded-by DOC-025

# Output as JSON
python3 lib/prd-manager.py abandon DOC-020 --reason "No longer needed" --json
```

**What happens on abandonment**:
1. `abandon_reason` added to MANIFEST.yaml
2. `superseded_by` added if specified
3. PRD moved to `prds/abandoned/`
4. Audit log entry created
5. Index updated

#### `complete` - Complete PRD

Mark a PRD as completed.

```bash
# Basic completion (requires all stories to pass)
python3 lib/prd-manager.py complete DOC-020

# Force completion even if stories incomplete
python3 lib/prd-manager.py complete DOC-020 --force

# With completion notes
python3 lib/prd-manager.py complete DOC-020 --notes "All features verified"

# Output as JSON
python3 lib/prd-manager.py complete DOC-020 --json
```

**What happens on completion**:
1. Story counts updated in MANIFEST.yaml
2. `completed_at` timestamp added
3. PRD moved from `prds/active/` to `prds/completed/`
4. Audit log entry created
5. Index updated

### Integrity Commands

#### `verify` - Verify Integrity

Verify PRD approval hashes and audit log integrity.

```bash
# Verify all PRDs
python3 lib/prd-manager.py verify

# Verify specific PRD
python3 lib/prd-manager.py verify DOC-020

# Fix hash mismatches (recalculate hashes)
python3 lib/prd-manager.py verify --fix

# Output as JSON
python3 lib/prd-manager.py verify --json
```

**Example output:**
```
Integrity Check: PASSED
  PRDs checked:    12
  Audit log:       Valid
  Issues found:    0
```

**Example with issues:**
```
Integrity Check: FAILED
  PRDs checked:    12
  PRDs with issues: 1
  Audit log:       Valid
  Total issues:    1
  Fixable issues:  1

Issues found:
----------------------------------------------------------------------

  [hash_mismatch] DOC-015
    Description: prd.json has been modified since approval
    Expected:    a1b2c3d4e5f6...
    Current:     9876543210ab...
    Fixable:     Yes (use --fix to repair)
    Path:        prds/active/comprehensive-tests

Tip: Run with --fix to repair 1 fixable issue(s)
```

### Audit Commands

#### `audit` - View Audit Log

View audit log entries with filtering.

```bash
# View all audit entries
python3 lib/prd-manager.py audit

# Filter by PRD
python3 lib/prd-manager.py audit --prd DOC-020

# Filter by action
python3 lib/prd-manager.py audit --action approve

# Limit results
python3 lib/prd-manager.py audit --limit 10

# Output as JSON
python3 lib/prd-manager.py audit --json
```

**Example output:**
```
Timestamp                 Action      PRD ID           Actor            Hash
-------------------------------------------------------------------------------------
2026-01-12T10:00:00Z      APPROVE     DOC-013          jialiang.wu      a1b2c3d4e5f6..
2026-01-12T09:30:00Z      CREATE      DOC-013          jialiang.wu      9876543210ab..
2026-01-12T08:00:00Z      COMPLETE    DOC-012          jialiang.wu      fedcba987654..

Total: 3 entries
```

#### `audit verify` - Verify Audit Log

Verify the integrity of the audit log hash chain.

```bash
# Verify audit log integrity
python3 lib/prd-manager.py audit verify

# Output as JSON
python3 lib/prd-manager.py audit verify --json
```

**Example output:**
```
Audit log integrity: VERIFIED
  Log file: .claude-loop/audit-log.jsonl
  Entries:  45
  Status:   Hash chain intact
```

---

## Security Model

### Approval Hash

When a PRD is approved, the SHA256 hash of `prd.json` is stored in `MANIFEST.yaml`:

```yaml
approval:
  approved_by: alice
  approved_at: 2026-01-12T10:00:00Z
  approval_hash: a1b2c3d4e5f6789012345678901234567890123456789012345678901234abcd
```

This hash ensures:
- Any modification to `prd.json` after approval is detectable
- The scope of approved work is immutable
- Tampering can be identified via `verify` command

### Audit Log Hash Chain

Each audit entry includes:

```json
{
  "timestamp": "2026-01-12T10:00:00Z",
  "action": "approve",
  "prd_id": "DOC-013",
  "actor": "alice",
  "content_hash": "sha256_of_prd_content",
  "previous_hash": "hash_of_previous_entry",
  "entry_hash": "sha256_including_previous"
}
```

The hash chain ensures:
- Audit entries cannot be modified without detection
- Entries cannot be deleted or reordered
- Complete audit trail is preserved

### Best Practices

1. **Never modify `prd.json` after approval** without re-approval
2. **Always provide reasons** when abandoning PRDs
3. **Use meaningful PRD IDs** with prefixes (`DOC-`, `FEAT-`, `FIX-`)
4. **Run `verify`** periodically to check integrity
5. **Review audit log** for unexpected changes

---

## Audit and Integrity

### Index Management

The PRD index is stored at `.claude-loop/prd-index.json` and is automatically updated by lifecycle commands. You can manually rebuild it:

```bash
# Rebuild index
python3 lib/prd-indexer.py rebuild

# Verify index matches filesystem
python3 lib/prd-indexer.py verify

# Show index contents
python3 lib/prd-indexer.py show

# Show statistics
python3 lib/prd-indexer.py stats
```

### Retention Policies

The retention system automatically manages old PRDs:

| Status | Age | Action |
|--------|-----|--------|
| `draft` | 25+ days | Warning issued |
| `draft` | 30+ days | Auto-abandoned |
| `completed` | 90+ days | Moved to archive |
| `abandoned` | 30+ days | Deleted (audit log preserved) |
| `archive` | 7+ days | Compressed to `.tar.gz` |

```bash
# Preview retention actions (dry run)
python3 lib/prd-retention.py check

# Execute retention cleanup
python3 lib/prd-retention.py run

# Dry run (show what would happen)
python3 lib/prd-retention.py run --dry-run

# Show retention statistics
python3 lib/prd-retention.py stats
```

---

## Troubleshooting

### Common Issues

#### "PRD not found"

**Symptom**: `Error: PRD 'DOC-020' not found`

**Solutions**:
1. Check the PRD ID is correct (case-insensitive)
2. Verify the PRD exists: `python3 lib/prd-manager.py list`
3. Try using the full path: `python3 lib/prd-manager.py show prds/active/my-prd/`

#### "Cannot transition from X to Y"

**Symptom**: `Error: Cannot transition from 'completed' to 'active'`

**Cause**: Invalid state transition (completed and abandoned are terminal states)

**Solution**: Create a new PRD that supersedes the old one:
```bash
python3 lib/prd-manager.py create DOC-021 "Updated Feature"
# In MANIFEST.yaml, add: supersedes: DOC-020
```

#### "Hash mismatch detected"

**Symptom**: `verify` reports hash_mismatch issues

**Cause**: `prd.json` was modified after approval

**Solutions**:
1. If changes were intentional, re-approve or use `--fix`:
   ```bash
   python3 lib/prd-manager.py verify --fix
   ```
2. If changes were unintentional, revert `prd.json` to the approved version

#### "Approval required"

**Symptom**: `Error: Cannot transition from 'draft' to 'completed'`

**Cause**: Trying to complete a PRD without approving it first

**Solution**: Approve the PRD first:
```bash
python3 lib/prd-manager.py approve DOC-020
python3 lib/prd-manager.py complete DOC-020
```

#### "Not all stories complete"

**Symptom**: `Warning: Not all stories are complete (5/7)`

**Cause**: Trying to complete a PRD with incomplete stories

**Solutions**:
1. Complete remaining stories
2. Use `--force` to complete anyway (not recommended)
3. Mark stories as passes: true in `prd.json` if already done

#### "MANIFEST.yaml not found"

**Symptom**: `Error: MANIFEST.yaml not found`

**Cause**: PRD directory missing required MANIFEST.yaml

**Solution**: Recreate the PRD or manually create MANIFEST.yaml following the schema

### Getting Help

```bash
# General help
python3 lib/prd-manager.py --help

# Command-specific help
python3 lib/prd-manager.py create --help
python3 lib/prd-manager.py approve --help
```

### Debug Mode

For verbose output, check the audit log:
```bash
python3 lib/prd-manager.py audit --prd DOC-020
```

---

## Quick Reference Card

### PRD Lifecycle Commands

```bash
# Create
prd-manager.py create <ID> "<TITLE>" [--type feature|bugfix|refactor]

# View
prd-manager.py list [--status draft|active|completed|abandoned]
prd-manager.py show <ID>
prd-manager.py search <QUERY> [--tag TAG]

# Transitions
prd-manager.py approve <ID> [--approver NAME] [--notes "..."]
prd-manager.py complete <ID> [--notes "..."] [--force]
prd-manager.py abandon <ID> --reason "..." [--superseded-by ID]

# Integrity
prd-manager.py verify [<ID>] [--fix]
prd-manager.py audit [--prd ID] [--action ACTION] [--limit N]
prd-manager.py audit verify
```

### State Transitions

```
draft ──approve──> active ──complete──> completed
  │                  │
  └──abandon──> abandoned <──abandon───┘
```

### File Locations

| File | Location |
|------|----------|
| PRDs | `prds/{drafts,active,completed,abandoned}/` |
| Index | `.claude-loop/prd-index.json` |
| Audit Log | `.claude-loop/audit-log.jsonl` |
| Schema | `schemas/manifest.schema.json` |

### Required MANIFEST.yaml Fields

```yaml
id: PREFIX-NNN         # e.g., DOC-001
title: "Title"         # 5-100 chars
status: draft          # draft|active|completed|abandoned
owner: username        # Author
created_at: ISO8601    # 2026-01-12T10:00:00Z
```

### Integration with claude-loop

```bash
# Auto-detect active PRD
./claude-loop.sh

# Specify PRD explicitly
./claude-loop.sh --prd prds/active/my-feature/prd.json

# After all stories pass, PRD auto-completes and moves to prds/completed/
```

### Common Patterns

```bash
# Full workflow: create → edit → approve → implement → complete
prd-manager.py create DOC-030 "New Feature"
# Edit prds/drafts/new-feature/prd.json with stories
prd-manager.py approve DOC-030
./claude-loop.sh --prd prds/active/new-feature/prd.json
# (claude-loop implements stories)
prd-manager.py complete DOC-030  # or auto-completed by claude-loop
```

---

## Related Documentation

- [MANIFEST.yaml Format Guide](./manifest-format.md) - Detailed schema documentation
- [RFC-001: Documentation Management](../rfcs/RFC-001-DOCUMENTATION-MANAGEMENT.md) - Original RFC
- [ADR-002: Stratified Memory Architecture](../adrs/ADR-002-stratified-memory.md) - Architecture decisions
