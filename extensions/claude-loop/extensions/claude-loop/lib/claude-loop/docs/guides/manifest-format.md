# MANIFEST.yaml Format Guide

This guide documents the MANIFEST.yaml file format used in PRD directories. Each PRD in `prds/` must have a MANIFEST.yaml file that describes its metadata, lifecycle status, and relationships.

## Overview

The MANIFEST.yaml file serves as the metadata layer for PRDs, enabling:
- **Lifecycle tracking**: Status progression from draft to completion
- **Discoverability**: Tags and search integration
- **Accountability**: Owner and contributor tracking
- **Integrity**: Approval hashes for tamper detection
- **Organization**: Supersedes/superseded_by relationships

## Schema Location

The JSON Schema for validation is located at: `schemas/manifest.schema.json`

## Required Fields

Every MANIFEST.yaml must include these fields:

| Field | Type | Description |
|-------|------|-------------|
| `id` | string | Unique identifier (e.g., `PRD-001`, `DOC-015`). Must match pattern `^[A-Z]+-[0-9]{3,}$` |
| `title` | string | Human-readable title (5-100 characters) |
| `status` | enum | Current lifecycle status: `draft`, `active`, `completed`, `abandoned` |
| `owner` | string | Primary owner/author (username or email) |
| `created_at` | datetime | ISO 8601 timestamp when PRD was created |

## Optional Fields

### Timestamps

| Field | Type | Description |
|-------|------|-------------|
| `updated_at` | datetime | Last modification timestamp |
| `approved_at` | datetime | When PRD was approved (moved to active) |
| `completed_at` | datetime | When PRD was marked completed |
| `abandoned_at` | datetime | When PRD was abandoned |

### Relationships

| Field | Type | Description |
|-------|------|-------------|
| `supersedes` | string/array | PRD ID(s) this PRD replaces |
| `superseded_by` | string | PRD ID that replaces this one |

### Classification

| Field | Type | Description |
|-------|------|-------------|
| `tags` | array | Lowercase kebab-case tags for categorization |
| `priority` | enum | `critical`, `high`, `medium`, `low` |
| `estimated_effort` | enum | `small`, `medium`, `large`, `x-large` |
| `description` | string | Brief description (max 1000 chars) |

### Progress Tracking

| Field | Type | Description |
|-------|------|-------------|
| `story_count` | integer | Total user stories in PRD |
| `completed_stories` | integer | Completed user stories |
| `branch_name` | string | Git branch for implementation |

### Approval Metadata

Required when status is `active` or `completed`:

```yaml
approval:
  approved_by: username
  approved_at: 2026-01-12T10:00:00Z
  approval_hash: sha256_hash_of_prd_json  # 64-char hex string
  notes: "Optional approver notes"
```

### Contributors

```yaml
contributors:
  - name: Alice
    role: author
    email: alice@example.com  # optional
    added_at: 2026-01-10T08:00:00Z  # optional
  - name: Bob
    role: reviewer
  - name: Charlie
    role: implementer
```

Valid roles: `author`, `reviewer`, `implementer`, `approver`

### Related Documentation

```yaml
related_docs:
  - path: docs/rfcs/RFC-001-feature-design.md
    type: rfc
    title: "Feature Design RFC"
  - path: docs/adrs/ADR-002-architecture.md
    type: adr
```

Valid types: `rfc`, `adr`, `guide`, `design-doc`, `external`

### Abandonment

Required when status is `abandoned`:

| Field | Type | Description |
|-------|------|-------------|
| `abandon_reason` | string | Explanation (10-500 chars) |

## Status Lifecycle

```
draft --> active --> completed
  |         |
  |         v
  +-----> abandoned
```

### Transitions

| From | To | Requirements |
|------|----|--------------|
| draft | active | Must have `approval` object |
| active | completed | All stories must pass |
| draft | abandoned | Must have `abandon_reason` |
| active | abandoned | Must have `abandon_reason` |

## Example MANIFEST.yaml

### Draft PRD

```yaml
id: DOC-015
title: Comprehensive Documentation Management Tests
status: draft
owner: jialiang.wu
created_at: 2026-01-12T08:00:00Z
updated_at: 2026-01-12T08:30:00Z

description: Create tests for all documentation management components
tags:
  - testing
  - documentation
  - cli

priority: medium
estimated_effort: medium

story_count: 7
completed_stories: 0
branch_name: feature/doc-management

contributors:
  - name: jialiang.wu
    role: author
```

### Active PRD

```yaml
id: PRD-042
title: User Authentication System
status: active
owner: alice
created_at: 2026-01-01T09:00:00Z
updated_at: 2026-01-10T14:30:00Z
approved_at: 2026-01-05T10:00:00Z

description: Implement secure user authentication with OAuth2 and MFA
tags:
  - security
  - authentication
  - oauth2

priority: high
estimated_effort: large

story_count: 12
completed_stories: 5
branch_name: feature/user-auth

approval:
  approved_by: bob
  approved_at: 2026-01-05T10:00:00Z
  approval_hash: a1b2c3d4e5f6789012345678901234567890123456789012345678901234abcd
  notes: "Approved with condition to add rate limiting"

contributors:
  - name: alice
    role: author
  - name: bob
    role: approver
  - name: charlie
    role: implementer

related_docs:
  - path: docs/rfcs/RFC-003-auth-design.md
    type: rfc
    title: "Authentication Design RFC"
```

### Completed PRD

```yaml
id: PRD-001
title: Initial Project Setup
status: completed
owner: founder
created_at: 2025-12-01T00:00:00Z
completed_at: 2025-12-15T18:00:00Z

description: Set up project structure and CI/CD
tags:
  - infrastructure
  - setup

story_count: 5
completed_stories: 5

approval:
  approved_by: lead
  approved_at: 2025-12-02T10:00:00Z
  approval_hash: 0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef
```

### Abandoned PRD

```yaml
id: PRD-OLD-001
title: Legacy API Migration
status: abandoned
owner: developer
created_at: 2025-11-01T00:00:00Z
abandoned_at: 2025-12-01T00:00:00Z

abandon_reason: "Superseded by PRD-042 which takes a different architectural approach with better security properties"
superseded_by: PRD-042

tags:
  - deprecated
  - api
```

## Validation

Validate a MANIFEST.yaml against the schema:

```bash
# Using Python jsonschema
pip install jsonschema pyyaml
python -c "
import json, yaml, sys
from jsonschema import validate, ValidationError

with open('schemas/manifest.schema.json') as f:
    schema = json.load(f)
with open('prds/active/my-prd/MANIFEST.yaml') as f:
    manifest = yaml.safe_load(f)
try:
    validate(manifest, schema)
    print('Valid!')
except ValidationError as e:
    print(f'Invalid: {e.message}')
    sys.exit(1)
"

# Using prd-manager.py (coming in DOC-005)
./lib/prd-manager.py validate my-prd
```

## Best Practices

1. **IDs**: Use meaningful prefixes (`DOC-`, `FEAT-`, `FIX-`, `SCALE-`)
2. **Tags**: Use 3-5 tags per PRD for discoverability
3. **Timestamps**: Always use UTC with `Z` suffix
4. **Approval Hash**: Never modify prd.json after approval without re-approval
5. **Contributors**: Add all contributors with appropriate roles
6. **Abandon Reason**: Provide actionable context for future reference
7. **Related Docs**: Link to design documents for context

## Schema Updates

The schema follows JSON Schema draft 2020-12. To propose changes:

1. Create an RFC in `docs/rfcs/`
2. Update `schemas/manifest.schema.json`
3. Update this guide
4. Ensure backward compatibility (new fields should be optional)
