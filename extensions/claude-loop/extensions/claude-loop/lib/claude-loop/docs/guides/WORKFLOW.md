# claude-loop Workflow Guide

Detailed guide for using claude-loop to implement features autonomously.

## End-to-End Workflow

### Phase 1: Define the Feature

**Option A: Generate PRD with /prd skill**
```bash
# Describe your feature
claude "/prd Add user authentication with email/password and OAuth support"

# Claude generates PRD.md with:
# - Overview and problem statement
# - Goals and non-goals
# - User stories with acceptance criteria
# - Technical considerations
```

**Option B: Write PRD manually**
```markdown
# PRD: User Authentication

## Overview
Add secure user authentication to the application.

## User Stories

### US-001: Create auth database schema
**As a** developer
**I want** database tables for users and sessions
**So that** I can persist authentication data

**Acceptance Criteria:**
- [ ] Users table with id, email, password_hash, created_at
- [ ] Sessions table with id, user_id, token, expires_at
- [ ] Migrations run without errors
- [ ] Schema tests pass

**Priority:** 1
```

### Phase 2: Convert to prd.json

```bash
# Use the /claude-loop skill
claude "/claude-loop PRD.md"

# Verify the output
cat prd.json | jq .
```

Review and adjust:
- Priorities reflect correct dependency order
- Stories are small enough for single iterations
- Acceptance criteria are verifiable

### Phase 3: Run claude-loop

```bash
# Start the autonomous loop
./claude-loop.sh

# Or with options
./claude-loop.sh --max-iterations 15 --verbose
```

**What happens:**
1. Loop reads prd.json for story list
2. Picks first story with `passes: false`
3. Spawns Claude Code to implement it
4. Claude runs tests, commits, updates state
5. Loop continues until all stories pass

### Phase 4: Monitor Progress

**During execution:**
```bash
# In another terminal
watch -n 5 'cat prd.json | jq ".userStories[] | {id, passes}"'
```

**After completion:**
```bash
# View what was done
cat progress.txt

# View commits
git log --oneline

# Check all stories passed
cat prd.json | jq '[.userStories[] | select(.passes == false)] | length'
```

### Phase 5: Review and Merge

```bash
# Review changes
git diff main...HEAD

# Run full test suite
npm test  # or your test command

# Create PR
gh pr create --title "Feature: $(cat prd.json | jq -r .project)"
```

## Story Writing Best Practices

### Good Story Example

```json
{
  "id": "US-003",
  "title": "Implement login endpoint",
  "description": "As a user, I want to log in with email/password so that I can access my account",
  "acceptanceCriteria": [
    "POST /auth/login accepts email and password",
    "Returns JWT token on successful login",
    "Returns 401 for invalid credentials",
    "Returns 400 for missing fields",
    "Rate limiting prevents brute force (5 attempts/minute)",
    "All endpoint tests pass"
  ],
  "priority": 3,
  "passes": false,
  "notes": ""
}
```

**Why it's good:**
- Clear, verifiable criteria
- Appropriate scope (one endpoint)
- Includes error cases
- Mentions tests

### Bad Story Example

```json
{
  "id": "US-001",
  "title": "Add authentication",
  "description": "Users should be able to authenticate",
  "acceptanceCriteria": [
    "Authentication works"
  ],
  "priority": 1,
  "passes": false,
  "notes": ""
}
```

**Why it's bad:**
- Too vague ("authentication works")
- Too large (entire auth system)
- Not verifiable
- No specific requirements

### Splitting Large Stories

**Before (too large):**
```json
{
  "id": "US-001",
  "title": "Implement complete auth system",
  "acceptanceCriteria": [
    "Users can register",
    "Users can login",
    "Users can logout",
    "Sessions are managed",
    "Passwords are secure"
  ]
}
```

**After (properly split):**
```json
[
  {
    "id": "US-001",
    "title": "Create user model and schema",
    "priority": 1,
    "acceptanceCriteria": ["User model exists", "Password hashing works", "Tests pass"]
  },
  {
    "id": "US-002",
    "title": "Implement registration endpoint",
    "priority": 2,
    "acceptanceCriteria": ["POST /auth/register works", "Validation works", "Tests pass"]
  },
  {
    "id": "US-003",
    "title": "Implement login endpoint",
    "priority": 3,
    "acceptanceCriteria": ["POST /auth/login works", "Returns JWT", "Tests pass"]
  },
  {
    "id": "US-004",
    "title": "Implement logout endpoint",
    "priority": 4,
    "acceptanceCriteria": ["POST /auth/logout works", "Session invalidated", "Tests pass"]
  }
]
```

## Iteration Deep Dive

### What Claude Does Each Iteration

```
1. READ CONTEXT
   ├── Read prd.json (task list)
   ├── Read progress.txt (previous learnings)
   └── Read AGENTS.md (patterns)

2. SELECT STORY
   ├── Filter: passes == false
   ├── Sort: by priority (ascending)
   └── Pick: first one

3. IMPLEMENT
   ├── Understand requirements
   ├── Write code
   ├── Write tests
   └── Handle edge cases

4. QUALITY GATES
   ├── Run typecheck
   ├── Run linter
   └── Run tests (must all pass!)

5. COMMIT
   └── git commit -m "feat: [US-XXX] - Title"

6. UPDATE STATE
   ├── prd.json: set passes = true
   ├── progress.txt: append learnings
   └── AGENTS.md: add patterns (if discovered)

7. SIGNAL
   ├── If all done: <loop>COMPLETE</loop>
   └── Otherwise: "Story US-XXX complete. N remaining."
```

### Progress.txt Format

```markdown
---

### Iteration: 2024-01-15 14:30:00
**Story**: US-002 - Implement registration endpoint
**Status**: Complete

**What was implemented**:
- POST /auth/register endpoint
- Input validation for email and password
- Password hashing with bcrypt
- Duplicate email detection

**Files changed**:
- src/routes/auth.ts (new)
- src/services/auth.service.ts (new)
- tests/auth.test.ts (new)

**Learnings for future iterations**:
- Use Joi for input validation (already configured in project)
- bcrypt rounds set to 12 in config
- Error responses follow { error: string, code: string } format
```

## Troubleshooting

### Story Won't Complete

**Symptoms:**
- Same story attempted multiple iterations
- Never marked as `passes: true`

**Diagnosis:**
```bash
# Check progress.txt for error patterns
grep -A 10 "US-003" progress.txt

# Check if tests are failing
npm test
```

**Solutions:**
1. Story too large → Split it
2. Tests failing → Fix tests manually, re-run
3. Missing dependency → Check story ordering

### Loop Exits Early

**Symptoms:**
- Loop exits before all stories complete
- Max iterations reached

**Diagnosis:**
```bash
# Check how many stories remain
cat prd.json | jq '[.userStories[] | select(.passes == false)] | length'
```

**Solutions:**
```bash
# Increase max iterations
./claude-loop.sh --max-iterations 30

# Or just re-run (continues from where it left off)
./claude-loop.sh
```

### Wrong Branch

**Symptoms:**
- Changes appearing on wrong branch
- Branch doesn't match prd.json

**Fix:**
```bash
# Check current branch
git branch --show-current

# Check prd.json branch
cat prd.json | jq -r .branchName

# Switch if needed
git checkout $(cat prd.json | jq -r .branchName)
```

### Context Issues

**Symptoms:**
- Claude doesn't understand previous work
- Repeating mistakes from earlier iterations

**Fix:**
1. Check progress.txt has useful learnings
2. Check AGENTS.md has patterns documented
3. Manually add critical context to these files

## Tips for Success

### Before Running

1. **Review prd.json thoroughly** - Fix issues before running
2. **Check story dependencies** - Order matters!
3. **Ensure tests exist** - Quality gates need tests
4. **Start small** - Try with 3-5 stories first

### During Execution

1. **Monitor progress.txt** - Watch learnings accumulate
2. **Check git log** - Verify commits are correct
3. **Don't interrupt** - Let iterations complete

### After Completion

1. **Review all changes** - Don't blindly merge
2. **Run full test suite** - Verify nothing broke
3. **Check documentation** - Ensure it's updated
4. **Clean up** - Remove any debugging code

## Example: Full Feature Implementation

### Feature: Add Dark Mode

**Step 1: Generate PRD**
```bash
claude "/prd Add a dark mode toggle to the settings page that persists across sessions"
```

**Step 2: Convert to JSON**
```bash
claude "/claude-loop PRD.md"
```

**Step 3: Review prd.json**
```json
{
  "project": "dark-mode",
  "branchName": "feature/dark-mode",
  "userStories": [
    {"id": "US-001", "title": "Create theme context", "priority": 1},
    {"id": "US-002", "title": "Add theme persistence", "priority": 2},
    {"id": "US-003", "title": "Create CSS variables", "priority": 3},
    {"id": "US-004", "title": "Add toggle component", "priority": 4},
    {"id": "US-005", "title": "Apply to existing components", "priority": 5}
  ]
}
```

**Step 4: Run claude-loop**
```bash
./claude-loop.sh -v
```

**Step 5: Monitor**
```
[ITERATION 1/10] Stories remaining: 5
[ITERATION 1/10] Starting Claude Code...
Story US-001 complete. 4 stories remaining.

[ITERATION 2/10] Stories remaining: 4
[ITERATION 2/10] Starting Claude Code...
Story US-002 complete. 3 stories remaining.

...

[SUCCESS] All stories complete!

═══════════════════════════════════════════════════════════════
                      CLAUDE-LOOP SUMMARY
═══════════════════════════════════════════════════════════════

  Stories: 5/5 complete
  Status: ALL STORIES COMPLETE
```

**Step 6: Review and Merge**
```bash
git diff main...HEAD
npm test
gh pr create --title "feat: Add dark mode toggle"
```
