# Automatic Task Decomposition (US-003 - Tier 1 Pattern Extraction)

The Automatic Task Decomposition system detects oversized user stories and automatically breaks them down into smaller, manageable substories using LLM-powered analysis. This helps manage complex features by decomposing them into incremental, implementable chunks.

## Overview

Task decomposition analyzes user stories before execution and suggests breaking them into substories when complexity thresholds are exceeded. The system uses Claude to intelligently decompose stories while maintaining dependencies, context, and acceptance criteria.

**Key Features:**
- 🎯 Three complexity thresholds (hours, description length, AC count)
- 🤖 LLM-powered story decomposition with Claude
- ✅ Interactive approval with detailed proposal display
- 💾 Atomic PRD updates with automatic backup
- 📊 JSONL logging of all decomposition events
- 🎛️ Feature flag control (disabled by default)
- 🔁 Automatic retries on next iteration if decomposition approved

## Complexity Thresholds

Stories are automatically flagged for decomposition when they exceed ANY of these thresholds:

| Threshold | Default Value | Description |
|-----------|---------------|-------------|
| `estimatedHours` | > 16 hours | Story estimated to take more than 2 work days |
| `description` length | > 1000 chars | Story description is overly detailed |
| `acceptanceCriteria` count | > 8 criteria | Too many acceptance criteria to manage effectively |

### Configuration

Thresholds can be customized by modifying these variables in `claude-loop.sh`:

```bash
DECOMPOSITION_HOURS_THRESHOLD=16
DECOMPOSITION_DESC_LENGTH_THRESHOLD=1000
DECOMPOSITION_AC_COUNT_THRESHOLD=8
```

## Usage

### Basic Usage (Interactive Mode)

Enable decomposition and let the system detect complex stories automatically:

```bash
./claude-loop.sh --enable-decomposition
```

When a complex story is detected:
1. System displays threshold violations
2. Claude generates 2-5 substories
3. Detailed proposal is presented for approval
4. User approves (y) or rejects (n)
5. If approved, PRD is updated atomically with substories
6. Iteration continues with first substory

### Automatic Mode (No Prompts)

Auto-approve all decompositions without user interaction:

```bash
./claude-loop.sh --enable-decomposition --auto-decompose
```

**Use with caution**: This mode skips user review and immediately applies decompositions.

### Manual Decomposition

Force decomposition of a specific story regardless of thresholds:

```bash
./claude-loop.sh --enable-decomposition --decompose-story US-003
```

This is useful for:
- Pre-emptively decomposing known complex stories
- Testing decomposition on specific stories
- Re-decomposing stories after requirements change

## Decomposition Process

### Step 1: Complexity Detection

Before each story execution, `complexity_check()` evaluates:

```bash
complexity_check "$story_id"
```

Returns:
- `0` (true): Story should be decomposed
- `1` (false): Story is fine as-is

### Step 2: LLM Decomposition

If complexity check passes, `decompose_story()` is called:

1. Extracts story details (title, description, acceptance criteria)
2. Builds decomposition prompt for Claude
3. Calls `claude -m sonnet` with structured prompt
4. Parses JSON response containing substories

**Prompt Structure:**
- Original story context (ID, title, description, AC, priority)
- Guidelines for substory creation (2-5 substories)
- JSON schema for response format
- Instructions to maintain dependencies and incremental value

**Expected Response:**
```json
{
  "rationale": "Explanation of decomposition strategy",
  "substories": [
    {
      "id": "US-XXX-1",
      "title": "Substory title",
      "description": "User story description",
      "acceptanceCriteria": ["AC 1", "AC 2"],
      "priority": 1,
      "dependencies": [],
      "passes": false,
      "notes": ""
    }
  ]
}
```

### Step 3: Interactive Approval (if not auto-mode)

Detailed proposal is displayed:

```
================================
Story Decomposition Proposal
================================

Original Story: US-003 - Complex Feature Implementation

Rationale: This story has 10 acceptance criteria and covers multiple independent
components that can be implemented separately, reducing risk and enabling incremental delivery.

Proposed Substories (3):

[1] US-003-1: Implement Core Data Model
    Description: As a developer, I want to implement the data model so that
    other components can build on it.
    Dependencies:

[2] US-003-2: Build API Endpoints
    Description: As a developer, I want to create API endpoints so that
    the frontend can interact with the data.
    Dependencies: US-003-1

[3] US-003-3: Add Validation and Error Handling
    Description: As a developer, I want comprehensive validation so that
    the system handles edge cases gracefully.
    Dependencies: US-003-2

Approve this decomposition? (y/n)
```

User responds:
- **y**: Proceed with decomposition
- **n**: Reject and continue with original story

### Step 4: Atomic PRD Update

If approved, PRD is updated atomically:

1. **Create backup**: `prd.json.backup.YYYYMMDD_HHMMSS`
2. **Mark original story**: Add "Decomposed into substories" to notes
3. **Insert substories**: Add after original story with sequential IDs
4. **Validate JSON**: Ensure updated PRD is valid before replacing
5. **Atomic replace**: Use temp file + atomic `mv` to prevent corruption

**Rollback**: If update fails, automatic rollback to backup occurs.

### Step 5: Iteration Restart

After successful decomposition:
- Current iteration is skipped (`continue` in main loop)
- Next iteration picks up first substory (US-XXX-1)
- Substories execute in dependency order

## Substory Format

Generated substories inherit properties from parent:

| Property | Inherited? | Notes |
|----------|-----------|-------|
| `id` | ✗ | Generated as `{PARENT_ID}-1`, `{PARENT_ID}-2`, etc. |
| `title` | ✗ | Focused title describing substory scope |
| `description` | ✗ | User story format maintained |
| `acceptanceCriteria` | ✗ | 2-4 focused, testable criteria |
| `priority` | ✗ | Sequential (1, 2, 3...) |
| `dependencies` | ✗ | Sequential (`US-XXX-2` depends on `US-XXX-1`) |
| `passes` | ✗ | Always starts as `false` |
| `notes` | ✗ | Empty initially |

**Parent story** is marked with `passes: false` and notes updated to indicate decomposition.

## Logging

All decomposition events are logged to `.claude-loop/logs/decomposition.jsonl`:

**Event Types:**
- `complexity_check`: Threshold violations detected
- `proposal_generated`: Claude generated substory proposal
- `approval`: User approved/rejected or auto-approved
- `prd_updated`: PRD successfully updated with substories

**Log Entry Format:**
```json
{
  "timestamp": "2026-01-20T01:00:00Z",
  "story_id": "US-003",
  "event_type": "proposal_generated",
  "status": "success",
  "context": {
    "rationale": "Story complexity exceeded thresholds...",
    "substory_count": 3,
    "substories": [...]
  }
}
```

**Viewing Logs:**
```bash
cat .claude-loop/logs/decomposition.jsonl | jq .
```

## Examples

### Example 1: Complex Feature with Many Acceptance Criteria

**Original Story:**
```json
{
  "id": "US-042",
  "title": "Implement User Dashboard",
  "description": "As a user, I want a comprehensive dashboard showing all my activity",
  "acceptanceCriteria": [
    "Display user profile information",
    "Show recent activity feed",
    "Display analytics charts",
    "Show notification center",
    "Display settings shortcuts",
    "Show pending tasks",
    "Display team members",
    "Show system status",
    "Display quick actions menu"
  ],
  "priority": 1,
  "estimatedHours": 12,
  "passes": false
}
```

**Decomposed Substories:**
```json
[
  {
    "id": "US-042-1",
    "title": "Dashboard Layout and Profile Display",
    "description": "As a user, I want to see my profile and dashboard layout",
    "acceptanceCriteria": [
      "Dashboard renders with responsive grid layout",
      "Profile information displays correctly (avatar, name, role)",
      "Layout adapts to mobile and desktop views"
    ],
    "priority": 1,
    "dependencies": [],
    "passes": false
  },
  {
    "id": "US-042-2",
    "title": "Activity Feed and Analytics",
    "description": "As a user, I want to see my recent activity and analytics",
    "acceptanceCriteria": [
      "Recent activity feed displays last 10 items",
      "Analytics charts render with correct data",
      "Data refreshes automatically every 5 minutes"
    ],
    "priority": 2,
    "dependencies": ["US-042-1"],
    "passes": false
  },
  {
    "id": "US-042-3",
    "title": "Notifications and Quick Actions",
    "description": "As a user, I want notifications and quick access to common tasks",
    "acceptanceCriteria": [
      "Notification center displays unread count",
      "Quick actions menu provides shortcuts",
      "Pending tasks list shows urgent items",
      "Settings shortcuts work correctly"
    ],
    "priority": 3,
    "dependencies": ["US-042-1"],
    "passes": false
  }
]
```

### Example 2: Large Estimated Hours

**Original Story:**
```json
{
  "id": "US-105",
  "title": "Migrate Database to PostgreSQL",
  "description": "Migrate entire database from MySQL to PostgreSQL",
  "acceptanceCriteria": [
    "Schema converted to PostgreSQL format",
    "All data migrated without loss",
    "Application updated to use PostgreSQL",
    "Performance verified"
  ],
  "priority": 1,
  "estimatedHours": 24,
  "passes": false
}
```

**Decomposed Substories:**
```json
[
  {
    "id": "US-105-1",
    "title": "PostgreSQL Schema Setup",
    "description": "As a developer, I want the PostgreSQL schema created",
    "acceptanceCriteria": [
      "Schema conversion script created",
      "PostgreSQL database initialized",
      "Schema validated against MySQL original"
    ],
    "priority": 1,
    "dependencies": [],
    "estimatedHours": 6,
    "passes": false
  },
  {
    "id": "US-105-2",
    "title": "Data Migration Script",
    "description": "As a developer, I want a reliable data migration process",
    "acceptanceCriteria": [
      "Migration script handles all tables",
      "Data integrity checks implemented",
      "Rollback procedure documented"
    ],
    "priority": 2,
    "dependencies": ["US-105-1"],
    "estimatedHours": 8,
    "passes": false
  },
  {
    "id": "US-105-3",
    "title": "Application PostgreSQL Integration",
    "description": "As a developer, I want the app to use PostgreSQL",
    "acceptanceCriteria": [
      "Database connection updated",
      "All queries tested and working",
      "Performance benchmarks run"
    ],
    "priority": 3,
    "dependencies": ["US-105-2"],
    "estimatedHours": 10,
    "passes": false
  }
]
```

## Best Practices

### When to Use Decomposition

**Good Candidates:**
- Stories with 8+ acceptance criteria
- Stories estimated at 16+ hours
- Stories covering multiple independent components
- Stories with vague or overly detailed descriptions
- Stories blocking multiple other stories

**Poor Candidates:**
- Simple refactoring tasks
- Bug fixes (even if complex)
- Stories that must be atomic (schema migrations, deployments)
- Stories already well-scoped

### Writing Decomposable Stories

To enable better decomposition:

1. **Use clear user story format**: "As a [role], I want [feature] so that [benefit]"
2. **List explicit acceptance criteria**: Makes decomposition points obvious
3. **Estimate conservatively**: Encourages decomposition of truly complex work
4. **Avoid tightly coupled AC**: Independence enables better decomposition

### Reviewing Decomposition Proposals

When reviewing proposals, verify:

- ✅ **Substories are independent**: Each can be implemented separately
- ✅ **Dependencies make sense**: Sequential order is logical
- ✅ **All original ACs covered**: No gaps in substory scope
- ✅ **Incremental value**: Each substory delivers something useful
- ✅ **Reasonable size**: Substories are 2-8 hours each (not too small/large)

## Troubleshooting

### Decomposition not triggering

**Symptom**: Story is complex but decomposition doesn't run

**Causes:**
1. Feature flag not enabled (`--enable-decomposition`)
2. Story below all thresholds (check estimatedHours, description length, AC count)
3. Story already marked `passes: true`

**Solution:**
```bash
# Verify thresholds
jq '.userStories[] | select(.id == "US-XXX") | {estimatedHours, descLength: (.description | length), acCount: (.acceptanceCriteria | length)}' prd.json

# Force decomposition
./claude-loop.sh --enable-decomposition --decompose-story US-XXX
```

### Claude decomposition fails

**Symptom**: "Claude CLI failed to generate decomposition"

**Causes:**
1. Claude CLI not installed or authenticated
2. API rate limiting
3. Invalid story format in PRD

**Solution:**
```bash
# Test Claude CLI
claude --version
claude "Hello world"

# Check API quota
# Wait and retry if rate limited

# Validate PRD
jq empty prd.json
```

### PRD update fails

**Symptom**: "Failed to validate updated PRD"

**Causes:**
1. Invalid JSON structure generated
2. Duplicate story IDs
3. Circular dependencies

**Solution:**
```bash
# Check backup
ls -la prd.json.backup.*

# Restore from backup if needed
cp prd.json.backup.YYYYMMDD_HHMMSS prd.json

# Manually fix issues
jq . prd.json
```

### Substories not executing

**Symptom**: Decomposition succeeds but substories never run

**Causes:**
1. Original story not properly marked (still `passes: true`)
2. Substory priority conflicts with other stories
3. Dependencies not resolvable

**Solution:**
```bash
# Check story status
jq '.userStories[] | select(.id | startswith("US-XXX")) | {id, priority, passes, dependencies}' prd.json

# Fix priorities or dependencies manually
```

## Performance Impact

Decomposition has minimal performance impact:

- **Complexity Check**: < 100ms per story (jq query + threshold checks)
- **LLM Decomposition**: 5-15 seconds (Claude API call)
- **PRD Update**: < 500ms (backup + jq modifications + atomic write)
- **Total Overhead**: ~10-20 seconds per decomposed story (one-time cost)

**Benefits far outweigh costs:**
- Smaller stories = faster iterations
- Better parallelization opportunities
- Reduced context size per story
- Easier rollback on failures

## Integration with Other Features

### With Learnings (US-002)

Decomposition events can be stored as learnings:
- Successful decompositions teach effective breakdown strategies
- Failed decompositions inform future threshold tuning

### With Hooks (US-001)

Hooks can integrate with decomposition:

```bash
# .claude-loop/hooks/post_iteration/50-decomposition-notify.sh
if [ -f ".claude-loop/logs/decomposition.jsonl" ]; then
    last_decomposition=$(tail -1 .claude-loop/logs/decomposition.jsonl)
    # Send notification with decomposition details
fi
```

### With Complexity Monitor (Phase 3)

Future integration potential:
- Runtime complexity signals inform threshold tuning
- Adaptive thresholds based on historical accuracy
- Predictive decomposition before story selection

## Future Enhancements

Potential improvements for future phases:

1. **ML-powered thresholds**: Learn optimal thresholds from historical data
2. **Dependency inference**: Automatically detect dependencies between substories
3. **Template-based decomposition**: Pre-defined decomposition patterns by story type
4. **Multi-level decomposition**: Recursively decompose substories if needed
5. **Cost estimation**: Predict token savings from decomposition
6. **A/B testing**: Compare decomposed vs monolithic story outcomes

## Related Documentation

- [Hook System](./hooks-system.md) - Lifecycle extension points
- [Learnings Storage](./learnings-storage.md) - JSON-based iteration learnings
- [Adaptive Splitting](./adaptive-splitting.md) - Runtime complexity-based splitting (Phase 3)
- [PRD Schema](../prd-schema.md) - PRD format specification

## References

- User Story: US-003 (Tier 1 Pattern Extraction)
- Acceptance Criteria: 12 criteria (all met)
- Implementation: `claude-loop.sh` lines 2017-2377
- Tests: `tests/decomposition_test.sh` (6 tests, all passing)
- Logs: `.claude-loop/logs/decomposition.jsonl`
