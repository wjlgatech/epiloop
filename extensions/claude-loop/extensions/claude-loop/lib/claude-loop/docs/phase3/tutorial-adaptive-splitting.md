# Tutorial: Adaptive Story Splitting

This tutorial walks you through using Adaptive Story Splitting to handle complex stories that emerge during execution.

## Learning Objectives

By the end of this tutorial, you'll be able to:

- Understand when and why adaptive splitting triggers
- Interpret complexity signals and scores
- Review and approve split proposals
- Continue execution after a split
- Adjust splitting behavior for your workflow

**Time Required:** 20-30 minutes

## Tutorial Scenario

You're building a user authentication system. Your PRD has a story for "Implement JWT authentication" that seemed straightforward initially, but becomes more complex during execution.

## Step 1: Create the Tutorial PRD

Create a file called `tutorial-adaptive.json`:

```json
{
  "project": "tutorial-adaptive-splitting",
  "branchName": "tutorial/adaptive-splitting",
  "description": "Tutorial: Learn adaptive story splitting",
  "userStories": [
    {
      "id": "US-001",
      "title": "JWT Authentication Implementation",
      "description": "As a developer, I want to implement JWT authentication so that users can securely access protected resources",
      "priority": 1,
      "acceptanceCriteria": [
        "Create JWT token generation function",
        "Implement token validation middleware",
        "Add refresh token mechanism",
        "Integrate with user database",
        "Write comprehensive tests",
        "Add logging and error handling"
      ],
      "passes": false,
      "notes": "",
      "fileScope": [
        "lib/auth/jwt.py",
        "lib/middleware/auth.py"
      ],
      "estimatedComplexity": "medium"
    }
  ]
}
```

**Note:** This story has 6 acceptance criteria and only lists 2 files in scope. As execution progresses, you'll see complexity emerge.

## Step 2: Understand the Baseline

Before executing, let's understand the initial complexity estimate:

```bash
# Check initial complexity (requires execution data, will show baseline)
source lib/complexity-monitor.sh
init_complexity_monitor "US-001" 3600000 "lib/auth/jwt.py,lib/middleware/auth.py" 6
get_complexity_score
```

**Expected Output:**
```
Complexity Score: 0.0/10
```

The score is 0 because no execution has happened yet. Complexity is detected at runtime.

## Step 3: Execute with Adaptive Splitting

Run claude-loop with the tutorial PRD:

```bash
./claude-loop.sh tutorial-adaptive.json --complexity-threshold 6
```

We're setting a lower threshold (6 instead of 7) to make splitting more likely for tutorial purposes.

## Step 4: Monitor for Complexity Signals

As execution progresses, watch for complexity signals in the output:

```
=== Executing US-001: JWT Authentication Implementation ===

[Iteration 1] Starting story execution...
[Iteration 1] Working on: Create JWT token generation function
✓ Completed AC 1/6

[Iteration 2] Working on: Implement token validation middleware
⚠️ Error encountered: ImportError - Missing 'pyjwt' dependency
⚠️ Error encountered: TypeError - Invalid token format
✓ Completed AC 2/6

[Iteration 3] Working on: Add refresh token mechanism
📁 File modification: lib/auth/refresh.py (outside scope)
📁 File modification: lib/database/tokens.py (outside scope)
✓ Completed AC 3/6 (took 45 minutes, estimated 10 minutes)

⚠️ Complexity Alert Triggered!
```

## Step 5: Understand the Complexity Report

When the threshold is exceeded, you'll see a detailed report:

```
=== Complexity Report: US-001 ===

Complexity Score: 6.8/10 (threshold: 6.0)

Signal Breakdown:
┌─────────────────────┬────────┬────────────┐
│ Signal              │ Score  │ Weight     │
├─────────────────────┼────────┼────────────┤
│ Time Overrun        │ 7.5/10 │ 35% → 2.63 │
│ File Expansion      │ 8.0/10 │ 25% → 2.00 │
│ Error Count         │ 5.0/10 │ 25% → 1.25 │
│ Clarifications      │ 3.0/10 │ 15% → 0.45 │
├─────────────────────┼────────┼────────────┤
│ Total Score         │ 6.8/10 │            │
└─────────────────────┴────────┴────────────┘

Details:
- AC #3 took 4.5x estimated time (45min vs 10min)
- 2 files modified outside initial scope
- 2 errors encountered
- 1 clarification request detected

Generating split proposal...
```

**Key Insights:**
- **Time overrun** (7.5) is the highest signal - AC #3 took much longer
- **File expansion** (8.0) is high - 2 unexpected files were needed
- **Error count** (5.0) is moderate - 2 errors during implementation
- **Clarifications** (3.0) is low - only 1 uncertainty signal

## Step 6: Review the Split Proposal

Claude will generate a split proposal:

```
=== Split Proposal for US-001 ===

Original Story: US-001 - JWT Authentication Implementation
Reason: Complexity score 6.8/10 exceeded threshold of 6.0

Proposed Split (3 sub-stories):

┌────────────────────────────────────────────────────────────────┐
│ US-001A: Core JWT Token Management                             │
├────────────────────────────────────────────────────────────────┤
│ Description: Implement basic JWT token generation and          │
│ validation without advanced features                           │
│                                                                 │
│ Acceptance Criteria:                                           │
│ - Create JWT token generation function                         │
│ - Implement token validation middleware                        │
│ - Add basic error handling                                     │
│                                                                 │
│ File Scope: lib/auth/jwt.py, lib/middleware/auth.py           │
│ Estimated Time: 30 minutes                                     │
│ Complexity: simple                                             │
└────────────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────────────┐
│ US-001B: Refresh Token Mechanism                               │
├────────────────────────────────────────────────────────────────┤
│ Description: Add refresh token support with database           │
│ persistence                                                     │
│                                                                 │
│ Acceptance Criteria:                                           │
│ - Implement refresh token generation                           │
│ - Add token storage in database                                │
│ - Create refresh endpoint                                      │
│                                                                 │
│ File Scope: lib/auth/refresh.py, lib/database/tokens.py       │
│ Estimated Time: 35 minutes                                     │
│ Complexity: medium                                             │
│ Dependencies: US-001A                                          │
└────────────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────────────┐
│ US-001C: Testing and Integration                               │
├────────────────────────────────────────────────────────────────┤
│ Description: Comprehensive testing and integration with user   │
│ system                                                          │
│                                                                 │
│ Acceptance Criteria:                                           │
│ - Write unit tests for token functions                         │
│ - Write integration tests                                      │
│ - Integrate with user database                                 │
│ - Add logging and monitoring                                   │
│                                                                 │
│ File Scope: tests/auth/, lib/database/users.py                │
│ Estimated Time: 25 minutes                                     │
│ Complexity: simple                                             │
│ Dependencies: US-001B                                          │
└────────────────────────────────────────────────────────────────┘

Total Estimated Time: 90 minutes (same as original)
Dependency Chain: US-001A → US-001B → US-001C

[a]pprove | [r]eject | [e]dit | [s]kip
Your choice: _
```

## Step 7: Understanding Your Options

You have four choices:

### Option A: Approve

**When to use:** The split makes sense and will improve execution quality.

```
Your choice: a
```

**What happens:**
1. PRD is backed up to `.claude-loop/prd-backups/`
2. Sub-stories US-001A, US-001B, US-001C are inserted after US-001
3. US-001 is marked as "split" (not complete, but replaced)
4. Dependencies are created (US-001A → US-001B → US-001C)
5. Execution continues with US-001A

### Option R: Reject

**When to use:** The split doesn't align with your understanding, or you want to power through the complexity.

```
Your choice: r
Reason for rejection: I want to keep this as a single story for now
```

**What happens:**
1. Rejection is logged to audit trail
2. Execution continues with original US-001
3. No PRD changes are made

### Option E: Edit

**When to use:** The split is mostly good, but you want to adjust details.

```
Your choice: e
```

**What happens:**
1. Split proposal is saved to temporary file
2. Your $EDITOR opens with the proposal in JSON format
3. You can modify:
   - Sub-story titles and descriptions
   - Acceptance criteria
   - File scopes
   - Time estimates
4. Save and close editor
5. Modified proposal is re-displayed for final approval

### Option S: Skip

**When to use:** You're not sure yet and want to defer the decision.

```
Your choice: s
```

**What happens:**
1. Execution continues with original US-001
2. Split proposal is saved for later review
3. You can revisit the decision after execution completes

## Step 8: Approve the Split (Tutorial Flow)

For this tutorial, let's approve:

```
Your choice: a

✓ Split approved
✓ PRD backed up to .claude-loop/prd-backups/2026-01-14T10-45-00.json
✓ Sub-stories inserted into PRD
✓ Dependencies updated
✓ Continuing execution with US-001A...
```

## Step 9: Review Updated PRD

Let's see how the PRD was modified:

```bash
# View updated PRD
cat tutorial-adaptive.json
```

**Modified PRD:**
```json
{
  "project": "tutorial-adaptive-splitting",
  "branchName": "tutorial/adaptive-splitting",
  "description": "Tutorial: Learn adaptive story splitting",
  "userStories": [
    {
      "id": "US-001",
      "title": "JWT Authentication Implementation",
      "description": "As a developer, I want to implement JWT authentication...",
      "priority": 1,
      "acceptanceCriteria": [...],
      "passes": false,
      "notes": "Split into US-001A, US-001B, US-001C due to complexity. Proposal ID: SPLIT-ABC123",
      "split": true,
      "splitProposalId": "SPLIT-ABC123",
      "fileScope": [...],
      "estimatedComplexity": "medium"
    },
    {
      "id": "US-001A",
      "title": "Core JWT Token Management",
      "description": "Implement basic JWT token generation and validation...",
      "priority": 1,
      "acceptanceCriteria": [
        "Create JWT token generation function",
        "Implement token validation middleware",
        "Add basic error handling"
      ],
      "passes": false,
      "notes": "",
      "fileScope": ["lib/auth/jwt.py", "lib/middleware/auth.py"],
      "estimatedComplexity": "simple",
      "dependencies": ["US-001"]
    },
    {
      "id": "US-001B",
      "title": "Refresh Token Mechanism",
      "description": "Add refresh token support with database persistence",
      "priority": 1,
      "acceptanceCriteria": [
        "Implement refresh token generation",
        "Add token storage in database",
        "Create refresh endpoint"
      ],
      "passes": false,
      "notes": "",
      "fileScope": ["lib/auth/refresh.py", "lib/database/tokens.py"],
      "estimatedComplexity": "medium",
      "dependencies": ["US-001A"]
    },
    {
      "id": "US-001C",
      "title": "Testing and Integration",
      "description": "Comprehensive testing and integration with user system",
      "priority": 1,
      "acceptanceCriteria": [
        "Write unit tests for token functions",
        "Write integration tests",
        "Integrate with user database",
        "Add logging and monitoring"
      ],
      "passes": false,
      "notes": "",
      "fileScope": ["tests/auth/", "lib/database/users.py"],
      "estimatedComplexity": "simple",
      "dependencies": ["US-001B"]
    }
  ]
}
```

**Key Changes:**
1. Original US-001 marked as `"split": true`
2. Three new sub-stories inserted with IDs US-001A, US-001B, US-001C
3. Dependency chain created: US-001A → US-001B → US-001C
4. File scopes distributed across sub-stories
5. Complexity downgraded from medium to simple/medium for sub-stories

## Step 10: Execution Continues with Sub-Stories

After the split, execution automatically continues with US-001A:

```
=== Executing US-001A: Core JWT Token Management ===

[Iteration 1] Working on: Create JWT token generation function
✓ Completed AC 1/3

[Iteration 2] Working on: Implement token validation middleware
✓ Completed AC 2/3

[Iteration 3] Working on: Add basic error handling
✓ Completed AC 3/3

=== US-001A Complete ===

Proceeding to US-001B...
```

**Benefits of the Split:**
- Smaller, focused stories are easier to complete
- Each sub-story has clear boundaries
- Progress is more visible
- Failures are easier to debug and retry

## Step 11: Review Audit Trail

Check the audit trail to see what was logged:

```bash
# View complexity signals
cat .claude-loop/complexity-signals.jsonl | jq '.'

# View split proposals
cat .claude-loop/split-proposals.jsonl | jq '.'

# View progress log
grep -A 10 "Adaptive Split" progress.txt
```

**Complexity Signals Log:**
```json
{"story_id":"US-001","timestamp":"2026-01-14T10:30:00Z","signal_type":"time_overrun","ac_id":"AC-3","estimated_ms":600000,"actual_ms":2700000,"overrun_factor":4.5}
{"story_id":"US-001","timestamp":"2026-01-14T10:35:00Z","signal_type":"file_expansion","file":"lib/auth/refresh.py","in_scope":false}
{"story_id":"US-001","timestamp":"2026-01-14T10:35:00Z","signal_type":"file_expansion","file":"lib/database/tokens.py","in_scope":false}
{"story_id":"US-001","timestamp":"2026-01-14T10:32:00Z","signal_type":"error","error_type":"ImportError","error_message":"Missing 'pyjwt' dependency"}
{"story_id":"US-001","timestamp":"2026-01-14T10:33:00Z","signal_type":"error","error_type":"TypeError","error_message":"Invalid token format"}
```

**Split Proposals Log:**
```json
{"proposal_id":"SPLIT-ABC123","story_id":"US-001","timestamp":"2026-01-14T10:40:00Z","complexity_score":6.8,"threshold":6.0,"sub_story_count":3,"sub_story_ids":["US-001A","US-001B","US-001C"],"decision":"approved","approved_by":"user","approved_at":"2026-01-14T10:45:00Z"}
```

## Advanced: Tuning Your Threshold

After completing the tutorial, you understand how splitting works. Now let's tune the threshold for your preferences:

### More Aggressive Splitting

If you prefer smaller stories and faster feedback:

```bash
./claude-loop.sh prd.json --complexity-threshold 5
```

**Effect:** Splits trigger earlier, even moderate complexity leads to decomposition.

### More Conservative Splitting

If you prefer larger stories and fewer interruptions:

```bash
./claude-loop.sh prd.json --complexity-threshold 8
```

**Effect:** Only very high complexity triggers splits.

### Disable Splitting

If you want to handle complexity manually:

```bash
./claude-loop.sh prd.json --no-adaptive
```

**Effect:** No automatic splitting, even if complexity is high.

## Key Takeaways

1. **Adaptive splitting is reactive** - It triggers based on runtime signals, not initial estimates
2. **You're always in control** - Approve, reject, edit, or skip split proposals
3. **Splits preserve continuity** - Execution continues seamlessly after a split
4. **Audit trail is comprehensive** - All signals and decisions are logged
5. **Threshold is tunable** - Adjust to match your workflow preferences

## Next Steps

- **Try it on a real project:** Use adaptive splitting on your next complex feature
- **Experiment with thresholds:** Find the sweet spot for your team
- **Review your splits:** Analyze patterns in what triggers complexity
- **Share learnings:** Document insights in your team's PRD guidelines

## Related Documentation

- [Adaptive Splitting Reference](../features/adaptive-splitting.md)
- [PRD Dynamic Updates](../features/prd-dynamic-updates.md)
- [Phase 3 Getting Started](./getting-started.md)
- [Troubleshooting Guide](../troubleshooting/phase3-issues.md)

---

**Tutorial Complete!** You now understand adaptive story splitting. Try it on your next complex story.
