# Phase 3 Troubleshooting Guide

This guide covers common issues with Phase 3 features (Adaptive Story Splitting and Dynamic PRD Generation) and their solutions.

## Table of Contents

- [Adaptive Story Splitting Issues](#adaptive-story-splitting-issues)
- [Dynamic PRD Generation Issues](#dynamic-prd-generation-issues)
- [Integration Issues](#integration-issues)
- [Performance Issues](#performance-issues)
- [Data Integrity Issues](#data-integrity-issues)

---

## Adaptive Story Splitting Issues

### Issue: Splits Not Triggering When Expected

**Symptoms:**
- Story is clearly complex (many errors, long execution time)
- No split proposal is generated
- Execution continues without intervention

**Possible Causes:**
1. Complexity threshold too high
2. Adaptive splitting disabled
3. Signals not being tracked properly
4. Story hasn't reached trigger point yet

**Solutions:**

**Check if adaptive splitting is enabled:**
```bash
# Check environment
echo $ADAPTIVE_SPLITTING_ENABLED

# Should be true or empty (empty defaults to true)
# If false, enable it:
export ADAPTIVE_SPLITTING_ENABLED=true
```

**Lower the threshold:**
```bash
# Default is 7, try lowering
./claude-loop.sh prd.json --complexity-threshold 5

# Or very sensitive
./claude-loop.sh prd.json --complexity-threshold 4
```

**Check signal tracking:**
```bash
# View signals being logged
tail -f .claude-loop/complexity-signals.jsonl

# Should see entries like:
# {"story_id":"US-001","signal_type":"time_overrun",...}

# If empty, signals aren't being tracked - check monitoring integration
```

**Manual trigger (workaround):**
```bash
# Generate split proposal manually
python3 lib/story-splitter.py propose US-001 prd.json
```

### Issue: Too Many Splits Triggering

**Symptoms:**
- Almost every story triggers a split
- Workflow is interrupted constantly
- Progress is slower due to frequent pauses

**Possible Causes:**
1. Threshold too low
2. Story estimates too optimistic
3. Codebase has unusual complexity

**Solutions:**

**Raise the threshold:**
```bash
# Default is 7, try raising
./claude-loop.sh prd.json --complexity-threshold 9

# Or very conservative
./claude-loop.sh prd.json --complexity-threshold 10
```

**Disable for specific runs:**
```bash
# Disable adaptive splitting for this execution
./claude-loop.sh prd.json --no-adaptive
```

**Adjust signal weights:**
```bash
# Reduce time overrun weight (if that's the main trigger)
export WEIGHT_TIME_OVERRUN=0.20
export WEIGHT_FILE_EXPANSION=0.35
export WEIGHT_ERROR_COUNT=0.30
export WEIGHT_CLARIFICATIONS=0.15
```

**Improve estimates:**
- Review your story estimates
- If splits are consistently needed, stories may be scoped too large initially
- Adjust PRD creation process to write smaller stories

### Issue: Split Proposal Has Poor Quality

**Symptoms:**
- Generated sub-stories overlap or miss requirements
- Acceptance criteria are vague or incorrect
- Dependencies between sub-stories are wrong

**Possible Causes:**
1. Insufficient context for Claude to analyze
2. Story description lacks detail
3. Partial progress not captured properly

**Solutions:**

**Improve story descriptions:**
```json
// Before (vague)
{
  "id": "US-001",
  "title": "Implement auth",
  "description": "Add authentication",
  "acceptanceCriteria": ["Add login"]
}

// After (detailed)
{
  "id": "US-001",
  "title": "JWT Authentication Implementation",
  "description": "As a developer, I want to implement JWT-based authentication with email/password login, token refresh, and integration with existing user database",
  "acceptanceCriteria": [
    "Create JWT token generation function",
    "Implement token validation middleware",
    "Add refresh token mechanism",
    "Integrate with user database for authentication"
  ]
}
```

**Use the [e]dit option:**
```
When prompted with split proposal:
Your choice: e

This opens the proposal in your $EDITOR for manual refinement
```

**Reject and continue:**
```
If the proposal is poor quality:
Your choice: r
Reason: Proposal doesn't match requirements, will handle manually

Then create a better PRD manually after story completes
```

### Issue: PRD Corruption After Accepting Split

**Symptoms:**
- PRD is invalid JSON after accepting split
- Stories missing or duplicated
- Dependencies broken
- `claude-loop.sh` fails to parse PRD

**Possible Causes:**
1. Disk space full during write
2. Process killed mid-update
3. Concurrent modification (rare)
4. Bug in PRD update logic

**Solutions:**

**Restore from backup:**
```bash
# List backups (newest first)
ls -lt .claude-loop/prd-backups/

# Restore latest backup
cp .claude-loop/prd-backups/2026-01-14T10-45-00.json prd.json

# Verify restored PRD
bash lib/prd-parser.sh validate prd.json
```

**Validate PRD structure:**
```bash
# Check JSON syntax
python3 -c "import json; json.load(open('prd.json'))"

# Check PRD schema
bash lib/prd-parser.sh validate prd.json

# Check for circular dependencies
python3 lib/dependency-graph.py check-cycles prd.json
```

**Prevention:**
- Ensure adequate disk space before running
- Don't kill the process during split approval
- Use file system snapshots or git commits before runs

### Issue: Split Approval Prompt Not Showing

**Symptoms:**
- Complexity threshold exceeded
- No interactive prompt appears
- Execution continues without split

**Possible Causes:**
1. Running in non-interactive mode (daemon, CI/CD)
2. STDOUT redirected
3. Prompt timeout

**Solutions:**

**Check if running interactively:**
```bash
# This will prompt:
./claude-loop.sh prd.json

# This won't (daemon mode):
./claude-loop.sh daemon submit prd.json

# This won't (backgrounded):
./claude-loop.sh prd.json > output.log 2>&1 &
```

**For daemon mode:**
```bash
# Configure auto-approval
./claude-loop.sh daemon submit prd.json --auto-approve-splits

# Or require interaction
./claude-loop.sh daemon submit prd.json --interactive-splits
# (PRD will pause, notification sent to review)
```

**For CI/CD:**
```bash
# Disable adaptive splitting in CI
./claude-loop.sh prd.json --no-adaptive
```

---

## Dynamic PRD Generation Issues

### Issue: Generated PRD Has Poor Quality

**Symptoms:**
- Stories too large or too small
- Acceptance criteria vague
- Dependencies incorrect
- File scopes missing or wrong

**Possible Causes:**
1. Goal description too vague
2. Codebase analysis not enabled
3. Claude lacks context about project structure

**Solutions:**

**Improve goal description:**
```bash
# Before (vague)
./claude-loop.sh --dynamic "Add auth"

# After (detailed)
./claude-loop.sh --dynamic "$(cat <<'EOF'
Implement JWT-based authentication system with:

1. User Management:
   - User registration with email verification
   - Login with email/password
   - Password reset via email

2. Token Management:
   - JWT access token (15min expiry)
   - Refresh token (7 day expiry)
   - Token blacklist for logout

3. Security:
   - Bcrypt password hashing
   - Rate limiting on auth endpoints
   - HTTPS-only tokens

Technical Constraints:
- Use PostgreSQL for user storage
- Integrate with existing email service
- RESTful API endpoints
EOF
)"
```

**Enable codebase analysis:**
```bash
# Analyzes your codebase for better file scope predictions
./claude-loop.sh --dynamic "Goal" --codebase-analysis
```

**Iterate and refine:**
```bash
# Generate draft
./claude-loop.sh --dynamic "Goal" --dynamic-output draft-v1.json

# Review
cat draft-v1.json

# If poor quality, refine goal and regenerate
./claude-loop.sh --dynamic "Refined goal with more details" --dynamic-output draft-v2.json

# Manually edit final version
vim draft-v2.json
```

### Issue: File Scopes Are Inaccurate

**Symptoms:**
- Generated file scopes don't match project structure
- Paths use wrong conventions (e.g., `.py` in Node.js project)
- Important files missing from scope

**Possible Causes:**
1. Codebase analysis not enabled
2. Unusual project structure
3. Mixed language project

**Solutions:**

**Enable codebase analysis:**
```bash
./claude-loop.sh --dynamic "Goal" --codebase-analysis
```

**Manually refine after generation:**
```bash
# Generate
./claude-loop.sh --dynamic "Goal" --dynamic-output draft.json

# Update file scopes
vim draft.json

# Find: "fileScope": ["lib/models/user.py"]
# Replace with your actual structure: "fileScope": ["src/models/User.ts"]

# Validate
bash lib/prd-parser.sh validate draft.json
```

**Provide technical constraints:**
```bash
./claude-loop.sh --dynamic "Goal

Technical Constraints:
- Project structure: src/ (TypeScript), tests/ (Jest), docs/
- Naming convention: PascalCase for classes, camelCase for files
- Framework: NestJS
"
```

### Issue: Dependencies Are Incorrect

**Symptoms:**
- Story B depends on Story A, but they can run in parallel
- Circular dependencies detected
- Dependency chain doesn't match logical order

**Possible Causes:**
1. Claude misunderstood logical dependencies
2. Stories can actually run in parallel but were marked sequential
3. Complex dependency graph not fully inferred

**Solutions:**

**Check for circular dependencies:**
```bash
python3 lib/dependency-graph.py check-cycles prd-generated.json
```

**Visualize execution plan:**
```bash
python3 lib/dependency-graph.py plan prd-generated.json
```

**Manually fix dependencies:**
```bash
vim prd-generated.json

# Review each story's "dependencies" array
# Remove unnecessary dependencies
# Add missing dependencies

# Validate
python3 lib/dependency-graph.py check-cycles prd-generated.json
```

**Regenerate with clearer goal:**
```bash
# Be explicit about ordering
./claude-loop.sh --dynamic "Build REST API for blog posts

Implementation Order:
1. First: Database schema and models
2. Second: CRUD endpoints
3. Third: Validation and error handling
4. Fourth: Tests
5. Fifth: Documentation
"
```

### Issue: Generated Complexity Estimates Are Wrong

**Symptoms:**
- Story marked "simple" is actually complex
- Or story marked "complex" is trivial

**Possible Causes:**
1. Complexity detector has different understanding than you
2. Story scope larger/smaller than appears

**Solutions:**

**Review and adjust:**
```bash
vim prd-generated.json

# Change complexity estimates
# "estimatedComplexity": "simple" -> "medium"
# "estimatedComplexity": "complex" -> "medium"
```

**Use with adaptive splitting:**
```bash
# Don't worry too much about initial estimates
# Adaptive splitting will catch underestimated complexity

./claude-loop.sh prd-generated.json  # Adaptive splitting enabled
```

### Issue: Claude API Errors During Generation

**Symptoms:**
- `Error calling Claude API`
- `Rate limit exceeded`
- `Network error`

**Possible Causes:**
1. Claude CLI not configured
2. API rate limits
3. Network issues
4. API key expired

**Solutions:**

**Verify Claude CLI:**
```bash
# Check version
claude --version

# Test basic call
echo "Hello" | claude

# If errors, reconfigure
# Follow Claude CLI setup instructions
```

**Wait and retry for rate limits:**
```bash
# Wait 60 seconds
sleep 60

# Retry generation
./claude-loop.sh --dynamic "Goal" --dynamic-output prd.json
```

**Check network:**
```bash
# Test connectivity
curl -I https://api.anthropic.com

# If network issues, check firewall/proxy
```

---

## Integration Issues

### Issue: Adaptive Splitting + Daemon Mode Conflicts

**Symptoms:**
- Split prompt never appears in daemon mode
- PRD stalls waiting for input

**Cause:**
Daemon mode runs in background, can't show interactive prompts.

**Solution:**
```bash
# Configure daemon to auto-approve splits
./claude-loop.sh daemon submit prd.json --auto-approve-splits

# Or use notifications
./claude-loop.sh daemon submit prd.json --notify email --interactive-splits
# (Sends email when split needed, requires manual approval)
```

### Issue: Dashboard Not Showing Split Events

**Symptoms:**
- Split occurs but doesn't appear in dashboard
- Complexity signals not visible

**Possible Causes:**
1. Dashboard not refreshing
2. Split data not being published to dashboard API
3. Old dashboard version

**Solutions:**

**Restart dashboard:**
```bash
./claude-loop.sh dashboard stop
./claude-loop.sh dashboard start
```

**Check API endpoints:**
```bash
# Test split proposals endpoint
curl http://localhost:8080/api/split-proposals

# Test complexity signals endpoint
curl http://localhost:8080/api/stories/US-001/complexity
```

**Clear browser cache:**
- Hard refresh: Ctrl+Shift+R (Chrome/Firefox) or Cmd+Shift+R (Mac)

### Issue: Quick Mode + Dynamic Generation Not Working

**Symptoms:**
- Quick task set to escalate
- `--dynamic-on-escalate` flag set
- But no PRD is generated

**Possible Causes:**
1. Quick mode escalation not triggering
2. Dynamic generation integration not enabled
3. Missing configuration

**Solutions:**

**Check escalation triggers:**
```bash
# View quick mode complexity score
./claude-loop.sh quick "Task" --dry-run

# If score < threshold, it won't escalate
# Lower threshold: QUICK_MODE_COMPLEXITY_THRESHOLD
```

**Enable dynamic escalation:**
```bash
export QUICK_MODE_DYNAMIC_ESCALATION=true

./claude-loop.sh quick "Complex task" --escalate --dynamic-on-escalate
```

---

## Performance Issues

### Issue: Split Proposal Generation Takes Too Long

**Symptoms:**
- Waiting 2-5 minutes for split proposal
- Execution stalls during proposal generation

**Possible Causes:**
1. Large story with many acceptance criteria
2. Claude API latency
3. Network slow

**Solutions:**

**Check story size:**
```json
// If story has >10 acceptance criteria, it's too large
{
  "acceptanceCriteria": [
    "AC 1", "AC 2", ..., "AC 15"  // Too many!
  ]
}
```

**Monitor API latency:**
```bash
# Time a simple Claude call
time echo "Test" | claude

# Should be <10 seconds
# If slower, check network
```

**Workaround (skip and manual split):**
```
When prompted with slow generation:
[s]kip

Then manually split the story later
```

### Issue: Dynamic PRD Generation Is Slow

**Symptoms:**
- Generation takes >2 minutes
- Codebase analysis never completes

**Possible Causes:**
1. Very large codebase (>10,000 files)
2. Network latency to Claude API
3. Codebase analysis stuck

**Solutions:**

**Disable codebase analysis:**
```bash
# Don't use --codebase-analysis flag
./claude-loop.sh --dynamic "Goal" --dynamic-output prd.json
```

**Limit analysis scope:**
```bash
# Edit lib/prd-generator.py
# Reduce MAX_FILES_TO_SCAN from 1000 to 500
```

**Check Claude API latency:**
```bash
time echo "Analyze this goal: ..." | claude

# Should be <30 seconds for typical goals
```

---

## Data Integrity Issues

### Issue: Complexity Signals Log Corrupted

**Symptoms:**
- `.claude-loop/complexity-signals.jsonl` has invalid JSON
- Can't parse log entries

**Cause:**
Concurrent writes or interrupted writes.

**Solution:**

**Validate and fix:**
```bash
# Find invalid lines
cat .claude-loop/complexity-signals.jsonl | while read line; do
  echo "$line" | python3 -c "import sys, json; json.loads(sys.stdin.read())" || echo "Invalid: $line"
done

# Remove invalid lines
cat .claude-loop/complexity-signals.jsonl | while read line; do
  echo "$line" | python3 -c "import sys, json; json.loads(sys.stdin.read())" 2>/dev/null && echo "$line"
done > .claude-loop/complexity-signals-fixed.jsonl

# Replace
mv .claude-loop/complexity-signals-fixed.jsonl .claude-loop/complexity-signals.jsonl
```

**Prevention:**
- Don't manually edit JSONL files
- Don't run multiple claude-loop instances concurrently

### Issue: Split Proposals Log Missing Entries

**Symptoms:**
- Splits were approved but not in `.claude-loop/split-proposals.jsonl`
- Audit trail incomplete

**Possible Causes:**
1. Logging disabled
2. File permissions
3. Disk full

**Solutions:**

**Check file permissions:**
```bash
ls -l .claude-loop/split-proposals.jsonl

# Should be writable
# If not:
chmod 644 .claude-loop/split-proposals.jsonl
```

**Check disk space:**
```bash
df -h .

# Ensure adequate space (>1GB free)
```

**Regenerate from progress.txt:**
```bash
# Split events are also logged in progress.txt
grep "Adaptive Split" progress.txt
```

---

## Known Issues

### Issue: Sub-Story IDs Not Sortable

**Description:**
Sub-story IDs (US-001A, US-001B, US-001Z, US-001AA) don't sort alphabetically correctly.

**Impact:**
Minor. Doesn't affect execution, just display order in some tools.

**Workaround:**
Use numeric suffixes in manual splits: US-001-1, US-001-2, US-001-3

**Status:**
Will be fixed in future release.

### Issue: Codebase Analysis Doesn't Support Monorepos

**Description:**
Codebase analysis assumes single project structure. Monorepos with multiple sub-projects may get confused file scopes.

**Impact:**
Generated file scopes may span multiple sub-projects incorrectly.

**Workaround:**
- Disable codebase analysis: `--no-codebase-analysis`
- Manually refine file scopes after generation

**Status:**
Monorepo support planned for Phase 4.

### Issue: Split Proposals Don't Consider Git Conflicts

**Description:**
When splitting stories, proposed file scopes don't check for pending git changes or conflicts.

**Impact:**
Sub-stories may have conflicting file scopes if files were already modified.

**Workaround:**
- Commit or stash changes before accepting splits
- Review file scopes in proposal before approving

**Status:**
Git integration planned for future release.

---

## Getting More Help

If your issue isn't covered here:

1. **Check logs:**
   ```bash
   cat .claude-loop/complexity-signals.jsonl
   cat .claude-loop/split-proposals.jsonl
   tail -100 progress.txt
   ```

2. **Enable debug mode:**
   ```bash
   export CLAUDE_LOOP_DEBUG=1
   ./claude-loop.sh prd.json
   ```

3. **Collect diagnostics:**
   ```bash
   # Save diagnostic info
   ./claude-loop.sh --diagnostics > diagnostics.txt
   ```

4. **Ask for help:**
   - GitHub Issues: [github.com/anthropics/claude-loop/issues](https://github.com/anthropics/claude-loop/issues)
   - Include: OS, Phase version, error messages, steps to reproduce

---

**Last Updated:** 2026-01-14 • **Phase:** 3.0 • **Status:** Active
