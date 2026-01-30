# Getting Started with Phase 3

Phase 3 introduces powerful differentiating features that elevate claude-loop beyond traditional workflow automation. These features leverage AI to make your development process more adaptive, intelligent, and effortless.

## What's New in Phase 3?

Phase 3 adds four major capabilities:

1. **Adaptive Story Splitting** - Automatically detects when stories are too complex and suggests breaking them into smaller, manageable pieces
2. **Dynamic PRD Generation** - Generate complete project plans from natural language descriptions
3. **Multi-LLM Quality Review** (covered in Multi-LLM support PRD)
4. **Real-Time Notifications** (coming in later phases)

This guide focuses on the two core Phase 3 features: Adaptive Story Splitting and Dynamic PRD Generation.

## Prerequisites

Before using Phase 3 features, ensure you have:

- ✅ Phase 2 features installed and working
- ✅ Claude CLI configured (`claude` command available)
- ✅ Git repository initialized
- ✅ Basic familiarity with claude-loop PRD structure

## Quick Start: Dynamic PRD Generation

The easiest way to experience Phase 3 is to generate a PRD from a natural language goal.

### Example: Generate a PRD for User Authentication

```bash
./claude-loop.sh --dynamic "Implement user authentication with JWT tokens, including login, signup, and password reset"
```

This command will:
1. Analyze your goal using Claude AI
2. Decompose it into 5-10 user stories
3. Generate acceptance criteria for each story
4. Infer dependencies between stories
5. Estimate file scopes and complexity
6. Save the PRD to `prd-user-authentication.json`

### Example Output

```
=== Analyzing Goal ===
Goal: Implement user authentication with JWT tokens...

=== Generated Stories ===
US-001: User Model and Database Schema
US-002: JWT Token Generation and Validation
US-003: Login Endpoint Implementation
US-004: Signup Endpoint Implementation
US-005: Password Reset Flow
US-006: Middleware for Protected Routes
US-007: Integration Tests
US-008: Documentation

=== PRD Summary ===
Project: user-authentication
Branch: feature/user-authentication
Total Stories: 8
Estimated Complexity: Level 3 (Complex)
Estimated Duration: 2-3 weeks

PRD saved to: prd-user-authentication.json
```

### Customizing Output

You can control where the PRD is saved:

```bash
./claude-loop.sh --dynamic "Your goal" --dynamic-output my-project.json
```

Enable codebase analysis to improve file scope estimates:

```bash
./claude-loop.sh --dynamic "Your goal" --codebase-analysis
```

## Quick Start: Adaptive Story Splitting

Adaptive splitting automatically detects when a story is more complex than initially estimated and offers to break it down mid-execution.

### How It Works

As claude-loop executes a story, it monitors four complexity signals:

1. **Time Overrun** - Acceptance criteria taking >2x estimated time
2. **File Scope Expansion** - Modifying files outside the initial scope
3. **Error Count** - Encountering >3 errors during execution
4. **Clarification Requests** - Agent expressing uncertainty or asking questions

When these signals exceed a threshold, adaptive splitting triggers.

### Example: Enabling Adaptive Splitting

Adaptive splitting is enabled by default. To run with adaptive splitting:

```bash
./claude-loop.sh prd.json
```

When a story becomes complex, you'll see:

```
⚠️  Complexity Alert: US-003
Complexity Score: 8.2/10 (threshold: 7.0)

Signals detected:
- Time overrun: Acceptance criteria #3 took 3.2x estimated time
- File scope expansion: 4 files modified outside initial scope
- Error count: 5 errors encountered
- Clarifications: Agent requested clarification 2 times

Generating split proposal...
```

### Interactive Approval

After generating a split proposal, you'll be prompted:

```
=== Split Proposal for US-003 ===

Original Story: US-003 - Complex Feature Implementation
Split into 3 sub-stories:

US-003A: Core Feature Logic
- Implement base functionality
- Add error handling
Estimated time: 30 minutes

US-003B: Integration and Testing
- Integrate with existing systems
- Write unit tests
Estimated time: 25 minutes

US-003C: Documentation and Polish
- Add inline documentation
- Update user guides
Estimated time: 15 minutes

[a]pprove | [r]eject | [e]dit | [s]kip
```

**Options:**

- **[a]pprove** - Accept the split, insert sub-stories into PRD, continue with US-003A
- **[r]eject** - Reject the split, continue with original US-003 (logs reason in audit trail)
- **[e]dit** - Open proposal in your $EDITOR to manually adjust before approving
- **[s]kip** - Defer decision, continue with original story for now

### Configuring Complexity Threshold

You can adjust when splits are triggered:

```bash
# More sensitive (split earlier)
./claude-loop.sh prd.json --complexity-threshold 5

# Less sensitive (split later)
./claude-loop.sh prd.json --complexity-threshold 9

# Disable adaptive splitting entirely
./claude-loop.sh prd.json --no-adaptive
```

## Phase 3 Workflow Examples

### Workflow 1: Start from Scratch with Dynamic Generation

Perfect for new projects or features.

```bash
# 1. Generate PRD from goal
./claude-loop.sh --dynamic "Build a REST API for blog posts with CRUD operations"

# 2. Review the generated PRD
cat prd-blog-api.json

# 3. Execute with adaptive splitting enabled (default)
./claude-loop.sh prd-blog-api.json

# 4. If any story triggers splitting, approve/reject/edit as needed
```

### Workflow 2: Use Adaptive Splitting on Existing PRD

If you already have a PRD:

```bash
# Execute with default adaptive splitting
./claude-loop.sh my-existing-prd.json

# If you want more aggressive splitting
./claude-loop.sh my-existing-prd.json --complexity-threshold 6

# If you want to disable it for this run
./claude-loop.sh my-existing-prd.json --no-adaptive
```

### Workflow 3: Iterate on Generated PRD

Sometimes the first generation needs refinement:

```bash
# 1. Generate initial PRD
./claude-loop.sh --dynamic "My project goal" --dynamic-output draft.json

# 2. Review and manually edit draft.json
# - Adjust story priorities
# - Refine acceptance criteria
# - Update file scopes
# - Add dependencies

# 3. Execute the refined PRD
./claude-loop.sh draft.json
```

## Understanding the Adaptive Splitting System

### Complexity Signals

The complexity monitor tracks these signals during execution:

| Signal | Weight | Trigger Condition | Example |
|--------|--------|-------------------|---------|
| Time Overrun | 35% | AC takes >2x estimated time | AC estimated 10min, took 25min |
| File Expansion | 25% | Files modified outside scope | Scope was `lib/`, modified `tests/` |
| Error Count | 25% | >3 errors in single story | TypeError, ImportError, ValidationError |
| Clarifications | 15% | Agent expresses uncertainty | "I'm not sure", "unclear" |

### Scoring Algorithm

Complexity score is calculated as:

```
score = (time_signal × 0.35) +
        (file_signal × 0.25) +
        (error_signal × 0.25) +
        (clarification_signal × 0.15)
```

Each signal is normalized to 0-10 scale. The final score ranges from 0-10.

### Split Proposal Generation

When complexity exceeds threshold:

1. **Context Collection** - Gather story details, partial progress, encountered issues
2. **Claude Analysis** - Send context to Claude for decomposition analysis
3. **Sub-Story Generation** - Create 2-4 sub-stories with:
   - Clear boundaries
   - Independent acceptance criteria
   - Estimated time per sub-story
   - Dependencies between sub-stories (A → B → C)
4. **User Review** - Present proposal with before/after comparison
5. **PRD Update** - If approved, atomically update PRD with sub-stories

### PRD Dynamic Updates

When a split is approved:

1. **Backup Creation** - Save current PRD to `.claude-loop/prd-backups/{timestamp}.json`
2. **Atomic Update** - Use file locking and write-to-temp-then-rename for safety
3. **Sub-Story Insertion** - Insert sub-stories after parent story
4. **Dependency Chain** - Create sequential dependencies (US-003A → US-003B → US-003C)
5. **Parent Marking** - Mark original story as "split" (not complete, but replaced)
6. **Metadata Update** - Update story count and complexity totals
7. **Validation** - Run prd-validator to ensure PRD integrity
8. **Resume Execution** - Continue with first sub-story (US-003A)

## Audit Trail and Visibility

### Complexity Signals Log

All complexity signals are logged to `.claude-loop/complexity-signals.jsonl`:

```json
{"story_id":"US-003","timestamp":"2026-01-14T10:30:00Z","signal_type":"time_overrun","ac_id":"AC-3","estimated_ms":600000,"actual_ms":1920000,"overrun_factor":3.2}
{"story_id":"US-003","timestamp":"2026-01-14T10:35:00Z","signal_type":"file_expansion","file":"tests/integration/test_api.py","in_scope":false}
```

### Split Proposals Log

All split proposals and decisions are logged to `.claude-loop/split-proposals.jsonl`:

```json
{"proposal_id":"SPLIT-ABC123","story_id":"US-003","timestamp":"2026-01-14T10:40:00Z","complexity_score":8.2,"sub_story_count":3,"decision":"approved","approved_by":"user"}
```

### Progress Log

Split events are recorded in `progress.txt`:

```markdown
### Adaptive Split: US-003

**Reason**: Complexity score 8.2/10 exceeded threshold
**Decision**: Approved
**Sub-stories**: US-003A, US-003B, US-003C

Learnings:
- Original estimate was too optimistic for integration work
- Breaking into smaller pieces improved focus and success rate
```

## Configuration Reference

### Environment Variables

```bash
# Complexity threshold (0-10 scale)
export COMPLEXITY_THRESHOLD=7

# Disable adaptive splitting
export ADAPTIVE_SPLITTING_ENABLED=false

# Complexity signal weights (must sum to 1.0)
export WEIGHT_TIME_OVERRUN=0.35
export WEIGHT_FILE_EXPANSION=0.25
export WEIGHT_ERROR_COUNT=0.25
export WEIGHT_CLARIFICATIONS=0.15
```

### CLI Flags

```bash
# Adaptive splitting control
--complexity-threshold N      # Set complexity threshold (0-10)
--no-adaptive                 # Disable adaptive splitting

# Dynamic PRD generation
--dynamic "goal"              # Generate PRD from natural language goal
--dynamic-output FILE         # Specify output file path
--codebase-analysis           # Enable codebase scanning for file scope estimation
```

## Best Practices

### 1. Trust the Complexity Detection

If adaptive splitting triggers, there's usually a good reason. The signals indicate real complexity that's harder than initially estimated.

**✅ Do:**
- Review the split proposal carefully
- Consider why the complexity emerged
- Use the split as a learning opportunity

**❌ Don't:**
- Always reject splits out of principle
- Set threshold too high to avoid splits entirely

### 2. Start with Generated PRDs for New Work

Dynamic generation is great for bootstrapping new projects.

**✅ Do:**
- Use `--dynamic` for new features or projects
- Review and refine the generated PRD before execution
- Use generated file scopes as a starting point

**❌ Don't:**
- Execute generated PRDs blindly without review
- Expect perfect file scope predictions (they're estimates)

### 3. Iterate on Your Threshold

The default threshold (7/10) works well, but you can tune it:

**Lower threshold (5-6):** More splits, smaller stories, faster feedback
**Higher threshold (8-9):** Fewer splits, larger stories, more risk

**✅ Do:**
- Start with default (7)
- Lower if you prefer smaller stories
- Raise if splits are too frequent

**❌ Don't:**
- Set to 10 (effectively disables splitting)
- Change drastically without testing

### 4. Use Adaptive Splitting as a Learning Tool

Each split reveals estimation challenges.

**✅ Do:**
- Review why splits occurred after execution
- Update your PRD writing to avoid similar issues
- Share learnings with your team

**❌ Don't:**
- Ignore patterns in what triggers splits
- Treat splits as failures (they're adaptive responses)

### 5. Combine with Phase 2 Features

Phase 3 builds on Phase 2 capabilities.

**✅ Do:**
- Use skills within quick tasks
- Monitor splits via the dashboard
- Get notifications when splits occur

**❌ Don't:**
- Disable Phase 2 features when using Phase 3
- Ignore Phase 2 monitoring data

## Troubleshooting

### Split Not Triggering When Expected

**Symptoms:** Story is clearly complex, but no split is offered.

**Causes:**
- Complexity threshold too high
- Signals not being tracked properly
- Adaptive splitting disabled

**Solutions:**
```bash
# Lower threshold
./claude-loop.sh prd.json --complexity-threshold 5

# Check if disabled
grep ADAPTIVE_SPLITTING_ENABLED ~/.claude-loop/config

# Enable explicitly
export ADAPTIVE_SPLITTING_ENABLED=true
./claude-loop.sh prd.json
```

### Generated PRD Has Poor File Scopes

**Symptoms:** File scopes are too broad or missing key files.

**Causes:**
- Codebase analysis not enabled
- Complex or unusual project structure

**Solutions:**
```bash
# Enable codebase analysis
./claude-loop.sh --dynamic "goal" --codebase-analysis

# Manually refine after generation
./claude-loop.sh --dynamic "goal" --dynamic-output draft.json
# Edit draft.json
vim draft.json
./claude-loop.sh draft.json
```

### Split Proposal Generation Fails

**Symptoms:** Split is triggered, but proposal generation errors out.

**Causes:**
- Claude API not configured
- Rate limiting
- Network issues

**Solutions:**
```bash
# Check Claude CLI
claude --version

# Test Claude API
echo "Test" | claude

# Check rate limits
claude --help | grep -i limit

# Continue without split (reject)
# When prompted: [r]eject
```

### PRD Corruption After Split

**Symptoms:** PRD is invalid JSON or missing stories after split approval.

**Causes:**
- Concurrent modification
- Disk full
- Process killed mid-update

**Solutions:**
```bash
# Restore from backup
cp .claude-loop/prd-backups/<latest>.json prd.json

# Validate PRD
bash lib/prd-parser.sh validate prd.json

# Re-run with clean state
./claude-loop.sh prd.json
```

## Next Steps

- **Tutorial:** [Adaptive Story Splitting Tutorial](./tutorial-adaptive-splitting.md)
- **Tutorial:** [Dynamic PRD Generation Tutorial](./tutorial-dynamic-prd.md)
- **Reference:** [Complexity Detection Algorithm](../features/adaptive-splitting.md)
- **Reference:** [PRD Dynamic Updates](../features/prd-dynamic-updates.md)
- **Migration:** [Migrating from Phase 2 to Phase 3](../MIGRATION-PHASE3.md)

## Support

If you encounter issues with Phase 3 features:

1. Check the [troubleshooting guide](../troubleshooting/phase3-issues.md)
2. Review the [FAQ](../FAQ.md#phase-3)
3. Open an issue on [GitHub](https://github.com/anthropics/claude-loop/issues)
4. Join the community discussion

---

**Phase 3 Status:** Released • **Version:** 1.0.0 • **Last Updated:** 2026-01-14
