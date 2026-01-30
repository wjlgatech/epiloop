# RFC-001: Documentation Management System

**Status**: Draft
**Author**: Claude Code + Human Review
**Created**: 2026-01-12
**Target**: claude-loop v2.0

---

## Problem Statement

### Current Chaos

```
claude-loop/
├── prd.json                          # Active? Which feature?
├── prd-backup.json                   # Backup of what? When?
├── prd-claude-loop-upgrade.json      # Completed? Abandoned?
├── prd-p2.json                       # What is p2?
├── prd-p3.json                       # What is p3?
├── prd-self-improvement.json         # v1? Superseded by v2?
├── prd-stratified-memory.json        # Superseded by v2
├── prd-stratified-memory-v2.json     # Current? Completed?
├── prd-test-parallel.json            # Test file or real?
├── prd-unity-automation.json         # Status?
├── prd-vision-gui-automation.json    # Status?
└── docs/
    ├── PRD-Computer-Use.md           # Markdown PRD (why not JSON?)
    ├── PRD-Enhanced-GUI-Automation.md
    ├── PRD-Parallelization.md
    ├── GAP-ANALYSIS-*.md             # 2 gap analysis files
    ├── SCALE-ARCHITECTURE-DECISION.md # Decision record
    ├── SELF-IMPROVEMENT-STRATEGY.md   # Strategy doc
    ├── WORKFLOW.md                    # Technical doc
    ├── demo-presentation.md           # Marketing
    └── one-pager.md                   # Marketing
```

### Problems at Scale (1000 Contributors)

| Problem | Impact at Scale |
|---------|-----------------|
| **No naming convention** | PRD-123 vs prd-feature vs feature-prd chaos |
| **No versioning** | Which version is current? What changed? |
| **No lifecycle tracking** | Draft → Active → Completed → Archived unclear |
| **No ownership** | Who owns this PRD? Who can approve changes? |
| **Mixed formats** | JSON in root, MD in docs, no standard |
| **No security** | Anyone can modify, no signing, no audit trail |
| **No discoverability** | Can't find PRDs by feature, date, or status |
| **No retention policy** | Archive grows forever, no cleanup rules |

### Security Threats at Scale

| Threat | Attack Vector |
|--------|---------------|
| **Malicious PRD injection** | Bad actor submits PRD with backdoor acceptance criteria |
| **History tampering** | Modify completed PRD to claim different scope |
| **Ownership hijacking** | Claim ownership of someone else's PRD |
| **Denial of service** | Flood with thousands of PRDs |
| **Social engineering** | Fake "approved" status on malicious PRD |

---

## Proposed Solution

### 1. Directory Structure

```
claude-loop/
├── docs/
│   ├── rfcs/                    # Request for Comments (design decisions)
│   │   ├── RFC-001-*.md
│   │   └── RFC-002-*.md
│   ├── adrs/                    # Architecture Decision Records
│   │   ├── ADR-001-*.md
│   │   └── ADR-002-*.md
│   ├── guides/                  # User & developer guides
│   │   ├── getting-started.md
│   │   ├── prd-format.md
│   │   └── agent-development.md
│   └── marketing/               # Presentations, one-pagers
│       ├── demo-presentation.md
│       └── one-pager.md
│
├── prds/                        # All PRDs live here
│   ├── active/                  # Currently being implemented
│   │   └── YYYYMMDD-feature-name/
│   │       ├── prd.json         # The PRD
│   │       ├── MANIFEST.yaml    # Metadata, ownership, signatures
│   │       └── progress.txt     # Implementation progress
│   ├── completed/               # Successfully implemented
│   │   └── YYYYMMDD-feature-name/
│   ├── abandoned/               # Explicitly abandoned
│   │   └── YYYYMMDD-feature-name/
│   └── drafts/                  # Work in progress, not approved
│       └── YYYYMMDD-feature-name/
│
├── archive/                     # Historical runs (auto-cleaned)
│   └── YYYYMMDD-feature-name-HHMMSS/
│
└── .claude-loop/
    ├── prd-index.json           # Searchable index of all PRDs
    └── audit-log.jsonl          # Append-only audit trail
```

### 2. PRD Naming Convention

```
Format: YYYYMMDD-kebab-case-feature-name

Examples:
  20260112-stratified-memory-v2
  20260111-self-improvement-infrastructure
  20260110-unity-automation

Rules:
  - Date is creation date (immutable)
  - Feature name is kebab-case
  - Version suffix only if superseding previous PRD
  - Max 50 characters total
```

### 3. MANIFEST.yaml Schema

Every PRD directory MUST contain a MANIFEST.yaml:

```yaml
# MANIFEST.yaml - PRD Metadata
version: "1.0"

# Identity
id: "20260112-stratified-memory-v2"
title: "Stratified Memory Architecture v2"
description: "Scale self-improvement to 1000 users without bloating"

# Lifecycle
status: "completed"  # draft | active | completed | abandoned
created_at: "2026-01-12T00:00:00Z"
updated_at: "2026-01-12T10:30:00Z"
completed_at: "2026-01-12T07:13:00Z"

# Ownership
owner:
  github: "wjlgatech"
  email: "owner@example.com"
contributors:
  - github: "contributor1"
    role: "reviewer"

# Lineage
supersedes: "20260111-stratified-memory"  # Previous version
superseded_by: null                        # If this is superseded

# Metrics
stories_total: 16
stories_completed: 16
estimated_effort: "2 days"
actual_effort: "1 day"

# Security
approval:
  required: true
  approvers:
    - github: "wjlgatech"
  approved_at: "2026-01-11T23:24:00Z"
  approval_hash: "sha256:abc123..."  # Hash of prd.json at approval time

# Tags for discoverability
tags:
  - scale
  - memory
  - architecture
  - self-improvement

# Related artifacts
related_prds:
  - "20260111-self-improvement-infrastructure"
related_adrs:
  - "ADR-002-stratified-memory"
```

### 4. Lifecycle State Machine

```
                    ┌──────────────┐
                    │              │
                    ▼              │
┌─────────┐    ┌─────────┐    ┌─────────┐    ┌───────────┐
│  DRAFT  │───▶│ ACTIVE  │───▶│COMPLETED│───▶│ ARCHIVED  │
└─────────┘    └─────────┘    └─────────┘    └───────────┘
     │              │
     │              │
     ▼              ▼
┌─────────────────────┐
│     ABANDONED       │
└─────────────────────┘

Transitions:
  DRAFT → ACTIVE:      Requires approval (MANIFEST.approval)
  DRAFT → ABANDONED:   Owner decision, must document reason
  ACTIVE → COMPLETED:  All stories pass, auto-transition
  ACTIVE → ABANDONED:  Owner decision, must document reason
  COMPLETED → ARCHIVED: After retention period (90 days default)
```

### 5. Security Model

#### 5.1 Ownership & Permissions

```yaml
# Role-based access control
roles:
  owner:
    - create_prd
    - edit_prd
    - approve_prd
    - abandon_prd
    - transfer_ownership

  contributor:
    - propose_changes  # Via PR
    - comment

  reviewer:
    - approve_prd     # If in approvers list
    - request_changes

  admin:
    - all_permissions
    - manage_roles
    - audit_access
```

#### 5.2 Integrity Verification

```python
# Every PRD state change is recorded
class PRDStateChange:
    prd_id: str
    timestamp: datetime
    actor: str           # GitHub username
    action: str          # create, edit, approve, complete, abandon
    previous_hash: str   # SHA256 of previous state
    current_hash: str    # SHA256 of current state
    signature: str       # GPG signature of actor (optional but recommended)
```

#### 5.3 Audit Trail

```jsonl
# .claude-loop/audit-log.jsonl (append-only)
{"ts":"2026-01-12T00:00:00Z","actor":"wjlgatech","action":"create","prd":"20260112-stratified-memory-v2","hash":"sha256:abc..."}
{"ts":"2026-01-12T00:01:00Z","actor":"wjlgatech","action":"approve","prd":"20260112-stratified-memory-v2","hash":"sha256:def..."}
{"ts":"2026-01-12T07:13:00Z","actor":"claude-loop","action":"complete","prd":"20260112-stratified-memory-v2","hash":"sha256:ghi..."}
```

#### 5.4 Threat Mitigations

| Threat | Mitigation |
|--------|------------|
| **Malicious PRD injection** | Approval required before ACTIVE; reviewers must verify |
| **History tampering** | Append-only audit log; hash chain verification |
| **Ownership hijacking** | Ownership transfer requires current owner signature |
| **DoS via PRD flood** | Rate limiting; draft quota per user |
| **Social engineering** | Approval hash must match current prd.json |

### 6. Discoverability & Search

#### 6.1 PRD Index

```json
// .claude-loop/prd-index.json
{
  "version": "1.0",
  "updated_at": "2026-01-12T10:30:00Z",
  "prds": [
    {
      "id": "20260112-stratified-memory-v2",
      "title": "Stratified Memory Architecture v2",
      "status": "completed",
      "owner": "wjlgatech",
      "tags": ["scale", "memory", "architecture"],
      "created_at": "2026-01-12",
      "stories": {"total": 16, "completed": 16}
    }
  ]
}
```

#### 6.2 CLI Commands

```bash
# List PRDs by status
prd list --status active
prd list --status completed --since 2026-01-01

# Search PRDs
prd search "memory architecture"
prd search --tag scale --owner wjlgatech

# Show PRD details
prd show 20260112-stratified-memory-v2

# Create new PRD
prd create "New Feature Name"
# → Creates prds/drafts/20260112-new-feature-name/

# Transition PRD
prd approve 20260112-new-feature-name
prd abandon 20260112-new-feature-name --reason "Superseded by v2"

# Verify integrity
prd verify 20260112-stratified-memory-v2
# → Checks hash chain, approval signatures
```

### 7. Retention Policy

```yaml
# Retention rules
retention:
  drafts:
    max_age_days: 30        # Auto-abandon after 30 days of inactivity
    warning_at_days: 25     # Notify owner 5 days before

  completed:
    archive_after_days: 90  # Move to archive after 90 days
    keep_manifest: true     # Keep MANIFEST.yaml for history
    keep_prd: false         # PRD content can be deleted

  abandoned:
    delete_after_days: 30   # Permanently delete after 30 days
    keep_audit: true        # Audit log entries preserved forever

  archive:
    compress_after_days: 7  # Compress old archives
    delete_after_days: 365  # Delete archives older than 1 year
```

### 8. Migration Plan

#### Phase 1: Reorganize (Immediate)

```bash
# Create new structure
mkdir -p prds/{active,completed,abandoned,drafts}
mkdir -p docs/{rfcs,adrs,guides,marketing}

# Migrate completed PRDs
mv prd-stratified-memory-v2.json prds/completed/20260112-stratified-memory-v2/prd.json
mv prd-self-improvement.json prds/completed/20260111-self-improvement/prd.json
# ... create MANIFEST.yaml for each

# Migrate active PRD
mv prd.json prds/active/20260112-current-feature/prd.json

# Migrate docs
mv docs/demo-presentation.md docs/marketing/
mv docs/one-pager.md docs/marketing/
mv docs/SCALE-ARCHITECTURE-DECISION.md docs/adrs/ADR-002-stratified-memory.md
# ... etc
```

#### Phase 2: Tooling (Week 1)

```bash
# Implement prd CLI
lib/prd-manager.py
  - create, list, search, show
  - approve, abandon, complete
  - verify, audit

# Implement index rebuilder
lib/prd-indexer.py
  - Scan prds/ directory
  - Build prd-index.json
  - Verify hash chain
```

#### Phase 3: Automation (Week 2)

```yaml
# GitHub Actions
.github/workflows/prd-management.yml
  - On PR: Validate MANIFEST.yaml schema
  - On merge to main: Update prd-index.json
  - Daily: Check retention policy, cleanup
  - Daily: Verify audit log integrity
```

#### Phase 4: Security Hardening (Week 3)

```yaml
# GPG signing for approvals
# Branch protection for prds/active/
# CODEOWNERS for PRD directories
# Automated security scanning of PRD content
```

---

## Implementation Stories

| ID | Title | Priority | Effort |
|----|-------|----------|--------|
| DOC-001 | Create new directory structure | P0 | 1h |
| DOC-002 | Define MANIFEST.yaml schema | P0 | 2h |
| DOC-003 | Migrate existing PRDs to new structure | P0 | 4h |
| DOC-004 | Implement prd-manager.py CLI | P1 | 8h |
| DOC-005 | Implement prd-indexer.py | P1 | 4h |
| DOC-006 | Create GitHub Actions workflows | P1 | 4h |
| DOC-007 | Implement audit log system | P1 | 4h |
| DOC-008 | Add GPG signing support | P2 | 4h |
| DOC-009 | Implement retention automation | P2 | 4h |
| DOC-010 | Create migration guide for contributors | P1 | 2h |

---

## Success Criteria

| Metric | Target |
|--------|--------|
| PRD discoverability | Find any PRD in <5 seconds |
| Lifecycle clarity | 100% of PRDs have clear status |
| Audit coverage | 100% of state changes logged |
| Integrity verification | Detect tampering within 1 minute |
| Onboarding time | New contributor understands system in <10 minutes |
| False positive rate | <1% for security alerts |

---

## Alternatives Considered

### Alternative 1: GitHub Issues as PRDs

**Pros**: Built-in tracking, comments, labels
**Cons**: No structured schema, hard to version, no offline access
**Decision**: Rejected - need structured JSON for automation

### Alternative 2: Notion/Confluence

**Pros**: Rich UI, collaboration features
**Cons**: External dependency, no git integration, vendor lock-in
**Decision**: Rejected - need git-native solution

### Alternative 3: Simple flat files with naming convention

**Pros**: Simple, no tooling needed
**Cons**: Doesn't scale, no security, no discoverability
**Decision**: Rejected - doesn't meet 1000 contributor scale

---

## Open Questions

1. **GPG key management**: How do contributors set up signing?
2. **CI/CD integration**: How does claude-loop.sh find the active PRD?
3. **Cross-repo PRDs**: What if a PRD spans multiple repositories?
4. **PRD templates**: Should we have different templates for different PRD types?

---

## References

- [Architectural Decision Records](https://adr.github.io/)
- [RFC Process](https://www.ietf.org/standards/rfcs/)
- [Git-based workflow](https://nvie.com/posts/a-successful-git-branching-model/)

---

*This RFC is open for comment. Please submit feedback via GitHub Issues or PRs.*
