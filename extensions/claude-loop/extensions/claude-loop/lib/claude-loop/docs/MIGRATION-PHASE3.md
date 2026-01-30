# Migration Guide: Phase 2 to Phase 3

This guide helps you upgrade from Phase 2 (Foundations) to Phase 3 (Differentiators) and take advantage of new adaptive features.

## Overview

**Phase 3** introduces two major features that differentiate claude-loop from competitors:

1. **Adaptive Story Splitting** - Real-time complexity detection and decomposition
2. **Dynamic PRD Generation** - Generate PRDs from natural language goals

These features work seamlessly with Phase 2 capabilities (skills, quick tasks, daemon, dashboard, notifications).

## Migration Checklist

- [ ] Verify Phase 2 features are working
- [ ] Review new Phase 3 CLI flags
- [ ] Understand adaptive splitting behavior (enabled by default)
- [ ] Test dynamic PRD generation
- [ ] Update team workflows to leverage new features
- [ ] Review and adjust complexity thresholds
- [ ] Update documentation references

## Prerequisites

Before migrating to Phase 3:

1. **Phase 2 must be complete and stable**
   ```bash
   # Verify Phase 2 features work
   ./claude-loop.sh --list-skills
   ./claude-loop.sh quick "test quick mode"
   ./claude-loop.sh daemon status
   ./claude-loop.sh dashboard start
   ```

2. **Claude CLI must be configured**
   ```bash
   # Verify Claude CLI works
   claude --version
   echo "Test" | claude
   ```

3. **Git repository must be initialized**
   ```bash
   git status  # Should not error
   ```

## Breaking Changes

### None!

Phase 3 is **fully backward compatible** with Phase 2. Existing PRDs, scripts, and workflows will continue to work without modification.

**Key Compatibility Points:**
- ✅ Existing PRDs execute normally (adaptive splitting can be disabled)
- ✅ Phase 2 CLI flags still work
- ✅ Skills, quick mode, daemon, dashboard unchanged
- ✅ PRD schema is backward compatible (new fields are optional)

## New Features

### 1. Adaptive Story Splitting

#### What Changed

**Before (Phase 2):**
- Stories executed as written
- If a story was too complex, it would fail or take excessively long
- Manual intervention required to split complex stories

**After (Phase 3):**
- Claude Loop monitors complexity during execution
- When threshold is exceeded, automatically generates split proposal
- User approves/rejects/edits split
- PRD updates dynamically, execution continues

#### How to Use

**Default Behavior:**
Adaptive splitting is **enabled by default**. No changes needed:

```bash
# This now includes adaptive splitting
./claude-loop.sh prd.json
```

**Adjust Threshold:**
```bash
# More sensitive (split earlier)
./claude-loop.sh prd.json --complexity-threshold 5

# Less sensitive (split later)
./claude-loop.sh prd.json --complexity-threshold 9
```

**Disable:**
```bash
# Disable adaptive splitting for this run
./claude-loop.sh prd.json --no-adaptive
```

**Permanently Disable:**
```bash
# Add to your config or environment
export ADAPTIVE_SPLITTING_ENABLED=false
```

#### New Files Created

Adaptive splitting creates audit trail files:

```bash
.claude-loop/
├── complexity-signals.jsonl     # Real-time complexity signals
├── split-proposals.jsonl        # Split proposals and decisions
└── prd-backups/                 # Automatic PRD backups before splits
    └── {timestamp}.json
```

These files are gitignored by default.

#### Configuration Options

New environment variables:

```bash
# Complexity threshold (0-10 scale)
export COMPLEXITY_THRESHOLD=7  # Default

# Disable adaptive splitting
export ADAPTIVE_SPLITTING_ENABLED=false

# Signal weights (must sum to 1.0)
export WEIGHT_TIME_OVERRUN=0.35
export WEIGHT_FILE_EXPANSION=0.25
export WEIGHT_ERROR_COUNT=0.25
export WEIGHT_CLARIFICATIONS=0.15
```

### 2. Dynamic PRD Generation

#### What Changed

**Before (Phase 2):**
- PRDs created manually or via `generate_prd_from_description` (INV-008)
- Manual decomposition of features into stories
- Manual specification of acceptance criteria and dependencies

**After (Phase 3):**
- Generate PRDs from natural language goals
- Claude analyzes goal and decomposes into 5-10 stories
- Automatic dependency inference
- File scope prediction via codebase analysis
- Complexity estimation

#### How to Use

**Generate PRD:**
```bash
./claude-loop.sh --dynamic "Implement user authentication with JWT tokens"
```

**With Codebase Analysis:**
```bash
./claude-loop.sh --dynamic "Add REST API for blog posts" --codebase-analysis
```

**Custom Output Path:**
```bash
./claude-loop.sh --dynamic "Your goal" --dynamic-output my-prd.json
```

#### New CLI Flags

| Flag | Description | Example |
|------|-------------|---------|
| `--dynamic "goal"` | Generate PRD from goal | `--dynamic "Add auth"` |
| `--dynamic-output FILE` | Custom output path | `--dynamic-output prd-v1.json` |
| `--codebase-analysis` | Enable file scope analysis | `--codebase-analysis` |

#### Workflow Changes

**Old Workflow:**
1. Manually write PRD
2. Define stories, acceptance criteria, dependencies
3. Execute PRD

**New Workflow (Optional):**
1. Describe goal in natural language
2. Review generated PRD
3. Refine if needed
4. Execute PRD with adaptive splitting

**You can still use manual PRDs!** Dynamic generation is optional.

## Updated PRD Schema

Phase 3 adds optional fields to user stories:

```json
{
  "id": "US-001",
  "title": "Story Title",
  "split": false,                    // NEW: Marks story as replaced by sub-stories
  "splitProposalId": "SPLIT-ABC123", // NEW: References split proposal
  // ... existing fields
}
```

**Backward Compatibility:** These fields are optional. Existing PRDs work without them.

## Dashboard Integration

### Adaptive Splitting in Dashboard

The Phase 2 dashboard now shows adaptive splitting events:

**New Dashboard Elements:**
- **Complexity Alerts**: Visual indicators when stories trigger splitting
- **Split Proposals**: View pending split proposals
- **Complexity Chart**: Graph of complexity scores over time
- **Split History**: Timeline of split events

**No Action Required:** Dashboard updates automatically.

### New API Endpoints

If you're using the dashboard API:

```bash
# Get complexity signals for a story
GET /api/stories/{story_id}/complexity

# Get split proposals
GET /api/split-proposals

# Get complexity history
GET /api/complexity-history?story_id={id}
```

## Daemon Mode Integration

### Adaptive Splitting in Daemon Mode

When running PRDs via daemon mode, adaptive splitting prompts are **non-interactive**:

**Behavior:**
- If `--no-interactive` flag is set: Splits are auto-approved
- Otherwise: Splits are logged, PRD pauses, notification sent

**Configuration:**
```bash
# Auto-approve splits in daemon mode
./claude-loop.sh daemon submit prd.json --auto-approve-splits

# Always prompt (requires manual intervention)
./claude-loop.sh daemon submit prd.json --interactive-splits
```

### Notifications for Splits

New notification template: `split_required`

**Configure in `.claude-loop/daemon/notifications.json`:**
```json
{
  "email": {
    "enabled": true,
    "templates": {
      "split_required": {
        "subject": "Split Required: {{story_id}}",
        "body": "Story {{story_id}} requires splitting. Complexity: {{score}}/10"
      }
    }
  }
}
```

## Quick Task Mode Integration

### Dynamic Generation in Quick Mode

Quick tasks can now escalate to full PRD generation:

```bash
# If task is complex, auto-generate PRD
./claude-loop.sh quick "Build OAuth system" --escalate --dynamic-on-escalate
```

**Workflow:**
1. Quick mode detects complexity > threshold
2. Instead of failing, generates full PRD via dynamic generation
3. User reviews PRD
4. Executes PRD with adaptive splitting

**Configuration:**
```bash
# Enable dynamic generation on escalation
export QUICK_MODE_DYNAMIC_ESCALATION=true
```

## Skills Integration

### New Skills

Phase 3 adds skills for adaptive splitting:

```bash
# Analyze complexity of current execution
./claude-loop.sh --skill complexity-report --skill-arg US-001

# Preview split proposal for a story
./claude-loop.sh --skill split-preview --skill-arg US-003

# Validate PRD after dynamic generation
./claude-loop.sh --skill prd-validator --skill-arg generated-prd.json
```

## Performance Considerations

### Token Usage

Adaptive splitting and dynamic generation use Claude API:

**Adaptive Splitting:**
- **Per split proposal**: ~2,000-4,000 tokens
- **Frequency**: Only when complexity threshold exceeded (typically 5-15% of stories)
- **Model**: Uses Sonnet for split analysis

**Dynamic PRD Generation:**
- **Per generation**: ~5,000-10,000 tokens
- **Frequency**: Only when explicitly requested
- **Model**: Uses Sonnet for goal analysis

**Cost Impact:**
- Adaptive splitting: ~$0.05-$0.15 per split proposal
- Dynamic generation: ~$0.10-$0.25 per PRD

### Execution Time

**Adaptive Splitting:**
- Adds ~10-30 seconds when triggered (for proposal generation)
- User approval time (variable)
- PRD update: ~1-2 seconds (atomic operation)

**Dynamic PRD Generation:**
- Generation time: ~30-60 seconds
- Codebase analysis: +10-20 seconds (if enabled)

## Testing Your Migration

### Step 1: Verify Phase 2 Works

```bash
# Test skills
./claude-loop.sh --list-skills

# Test quick mode
./claude-loop.sh quick "Add a test file" --dry-run

# Test daemon
./claude-loop.sh daemon status

# Test dashboard
./claude-loop.sh dashboard start
```

### Step 2: Test Adaptive Splitting

Create a test PRD with a deliberately complex story:

```bash
cat > test-adaptive.json << 'EOF'
{
  "project": "test-adaptive",
  "branchName": "test/adaptive",
  "description": "Test adaptive splitting",
  "userStories": [
    {
      "id": "US-001",
      "title": "Complex Feature",
      "description": "A complex story",
      "priority": 1,
      "acceptanceCriteria": [
        "AC 1", "AC 2", "AC 3", "AC 4", "AC 5", "AC 6"
      ],
      "passes": false,
      "fileScope": ["lib/"],
      "estimatedComplexity": "complex"
    }
  ]
}
EOF

# Run with low threshold to trigger split
./claude-loop.sh test-adaptive.json --complexity-threshold 5
```

### Step 3: Test Dynamic Generation

```bash
# Generate a simple PRD
./claude-loop.sh --dynamic "Add basic user login with email and password" --dynamic-output test-dynamic.json

# Review generated PRD
cat test-dynamic.json

# Validate structure
bash lib/prd-parser.sh validate test-dynamic.json
```

### Step 4: Test Integration

```bash
# Generate + Execute + Adapt
./claude-loop.sh --dynamic "Add comment system" --dynamic-output comments-prd.json
./claude-loop.sh comments-prd.json
```

## Troubleshooting

### Issue: Splits Triggering Too Often

**Symptoms:** Almost every story triggers a split proposal.

**Solution:**
```bash
# Raise threshold
./claude-loop.sh prd.json --complexity-threshold 9

# Or disable
./claude-loop.sh prd.json --no-adaptive
```

### Issue: Splits Not Triggering When Expected

**Symptoms:** Story is clearly complex, but no split offered.

**Solution:**
```bash
# Lower threshold
./claude-loop.sh prd.json --complexity-threshold 5

# Check if disabled
grep ADAPTIVE_SPLITTING_ENABLED ~/.claude-loop/config
```

### Issue: Generated PRD Has Poor Quality

**Symptoms:** Stories are too large, dependencies wrong, file scopes inaccurate.

**Solution:**
```bash
# Be more specific in goal description
./claude-loop.sh --dynamic "Detailed goal with technical constraints"

# Enable codebase analysis
./claude-loop.sh --dynamic "Goal" --codebase-analysis

# Manually refine after generation
./claude-loop.sh --dynamic "Goal" --dynamic-output draft.json
vim draft.json  # Edit
./claude-loop.sh draft.json
```

### Issue: Claude API Errors During Split/Generation

**Symptoms:** "API error" or "Rate limit exceeded"

**Solution:**
```bash
# Check Claude CLI
claude --version
echo "Test" | claude

# Check rate limits
# Wait a few minutes and retry
```

### Issue: PRD Corruption After Split

**Symptoms:** PRD is invalid after accepting split.

**Solution:**
```bash
# Restore from backup
ls -lt .claude-loop/prd-backups/
cp .claude-loop/prd-backups/<latest>.json prd.json

# Re-run
./claude-loop.sh prd.json
```

## Best Practices

### 1. Start with Defaults

Don't adjust thresholds immediately. Use defaults for 5-10 PRDs, then tune based on experience.

### 2. Review Split Proposals Carefully

Don't auto-approve all splits. Review to understand why complexity emerged.

### 3. Iterate on Generated PRDs

Don't execute generated PRDs blindly. Review, refine, validate.

### 4. Use Codebase Analysis

Enable `--codebase-analysis` for better file scope predictions, especially in large projects.

### 5. Combine Features

Use dynamic generation + adaptive splitting + Phase 2 dashboard for optimal workflow:

```bash
# Generate
./claude-loop.sh --dynamic "Goal" --dynamic-output prd.json

# Review
cat prd.json

# Execute with dashboard
./claude-loop.sh dashboard start &
./claude-loop.sh prd.json

# Monitor in real-time at http://localhost:8080
```

## Rollback Plan

If Phase 3 causes issues, you can disable new features:

```bash
# Disable adaptive splitting
export ADAPTIVE_SPLITTING_ENABLED=false

# Don't use dynamic generation
# (just use manual PRDs)

# Everything else works as in Phase 2
./claude-loop.sh prd.json
```

**No code changes required.** Phase 3 features are opt-out by nature.

## Getting Help

If you encounter issues during migration:

1. **Check documentation:**
   - `docs/phase3/getting-started.md`
   - `docs/phase3/tutorial-adaptive-splitting.md`
   - `docs/phase3/tutorial-dynamic-prd.md`
   - `docs/troubleshooting/phase3-issues.md`

2. **Review logs:**
   - `.claude-loop/complexity-signals.jsonl`
   - `.claude-loop/split-proposals.jsonl`
   - `progress.txt`

3. **Ask for help:**
   - GitHub Issues: [github.com/anthropics/claude-loop/issues](https://github.com/anthropics/claude-loop/issues)
   - Community discussions

## Summary

Phase 3 migration is **low-risk** and **high-reward**:

✅ **No breaking changes** - Existing workflows continue to work
✅ **Opt-in features** - Adaptive splitting can be disabled, dynamic generation is optional
✅ **Backward compatible** - Existing PRDs work without modification
✅ **Strategic advantages** - Differentiation from competitors
✅ **Enhanced workflows** - Generate → Execute → Adapt in one flow

**Recommended Migration Path:**
1. Verify Phase 2 works
2. Test adaptive splitting on a simple PRD
3. Try dynamic generation on a new project
4. Gradually roll out to team

---

**Next Steps:**
- [Phase 3 Getting Started Guide](./phase3/getting-started.md)
- [Adaptive Splitting Tutorial](./phase3/tutorial-adaptive-splitting.md)
- [Dynamic PRD Tutorial](./phase3/tutorial-dynamic-prd.md)
- [Phase 3 Troubleshooting](./troubleshooting/phase3-issues.md)
