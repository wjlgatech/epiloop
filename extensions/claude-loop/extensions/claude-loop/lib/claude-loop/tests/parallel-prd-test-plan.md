# Parallel PRD Execution - Test Plan

**Date**: 2026-01-13
**Feature**: Parallel PRD Execution (v1.0)
**Test Approach**: Computer Use Agent as real user

---

## Test Objectives

1. ✅ Verify common workflows work as expected
2. ✅ Validate edge cases and error handling
3. ✅ Confirm isolation and safety mechanisms
4. ✅ Test resource limits and constraints

---

## Test Environment Setup

### Prerequisites
```bash
# Location
cd /Users/jialiang.wu/Documents/Projects/claude-loop

# Branch
git checkout feature/phase1-cowork-features

# Coordinator available
ls -la lib/prd-coordinator.sh

# Clean state
rm -rf .claude-loop/coordinator .claude-loop/worktrees
```

### Test PRD Structure
```
prds/active/
├── TEST-001/          # Simple PRD (1 story, fast)
├── TEST-002/          # Simple PRD (1 story, fast)
├── TEST-003/          # Simple PRD (1 story, fast)
├── TEST-CONFLICT/     # PRD with duplicate branch name
└── TEST-FAIL/         # PRD designed to fail
```

---

## Common Use Cases

### TC-001: Basic Parallel Execution (2 PRDs)
**Objective**: Verify 2 PRDs can run in parallel successfully

**Setup**:
```bash
# Create 2 simple test PRDs
mkdir -p prds/active/TEST-001 prds/active/TEST-002

# TEST-001 PRD
cat > prds/active/TEST-001/prd.json << 'EOF'
{
  "project": "test-001",
  "title": "Test PRD 001",
  "branchName": "test/prd-001",
  "userStories": [
    {
      "id": "US-001",
      "title": "Create test file",
      "description": "Create a simple test file",
      "passes": false,
      "acceptanceCriteria": [
        "File test-001.txt exists",
        "File contains 'TEST-001 COMPLETE'"
      ]
    }
  ]
}
EOF

# TEST-002 PRD (similar structure)
cat > prds/active/TEST-002/prd.json << 'EOF'
{
  "project": "test-002",
  "title": "Test PRD 002",
  "branchName": "test/prd-002",
  "userStories": [
    {
      "id": "US-001",
      "title": "Create test file",
      "description": "Create a simple test file",
      "passes": false,
      "acceptanceCriteria": [
        "File test-002.txt exists",
        "File contains 'TEST-002 COMPLETE'"
      ]
    }
  ]
}
EOF
```

**Execution**:
```bash
# Start parallel execution
./claude-loop.sh --parallel --max-prds 3
```

**Expected Results**:
- ✅ Coordinator initializes successfully
- ✅ Registry created at `.claude-loop/coordinator/registry.json`
- ✅ 2 workers launched (TEST-001, TEST-002)
- ✅ 2 worktrees created in `.claude-loop/worktrees/`
- ✅ Worker logs created in `.claude-loop/coordinator/logs/`
- ✅ Both workers complete successfully
- ✅ Test files created in each worktree

**Validation**:
```bash
# Check registry
cat .claude-loop/coordinator/registry.json | jq '.completed_prds'

# Check worktrees exist
ls -la .claude-loop/worktrees/

# Check test files created
cat .claude-loop/worktrees/TEST-001/test-001.txt
cat .claude-loop/worktrees/TEST-002/test-002.txt
```

---

### TC-002: Status Monitoring
**Objective**: Verify --status command shows accurate information

**Execution**:
```bash
# In another terminal during execution
./claude-loop.sh --status
```

**Expected Results**:
- ✅ Shows active PRDs with PIDs
- ✅ Shows progress if available
- ✅ JSON output is valid
- ✅ Status reflects current state

---

### TC-003: Stop Specific Worker
**Objective**: Verify --stop command works correctly

**Execution**:
```bash
# Stop TEST-001 worker
./claude-loop.sh --stop TEST-001
```

**Expected Results**:
- ✅ Worker receives SIGTERM
- ✅ Worker stops gracefully (within 30s)
- ✅ Registry updated with "stopped" status
- ✅ Other workers continue running
- ✅ Worktree preserved for TEST-001

---

## Edge Cases

### TC-004: Resource Limit Enforcement
**Objective**: Verify max_prds limit is enforced

**Setup**:
```bash
# Create 5 test PRDs
for i in {1..5}; do
    mkdir -p "prds/active/TEST-00$i"
    cat > "prds/active/TEST-00$i/prd.json" << EOF
{
  "project": "test-00$i",
  "branchName": "test/prd-00$i",
  "userStories": [{"id": "US-001", "title": "Test", "passes": false}]
}
EOF
done
```

**Execution**:
```bash
# Launch with max 3
./claude-loop.sh --parallel --max-prds 3
```

**Expected Results**:
- ✅ Only 3 workers launch initially
- ✅ Remaining 2 PRDs queued (or wait)
- ✅ No more than 3 active in registry at once
- ✅ When worker completes, next queued PRD starts

---

### TC-005: Branch Conflict Resolution
**Objective**: Verify automatic branch suffix on conflicts

**Setup**:
```bash
# Create 2 PRDs with SAME branch name
mkdir -p prds/active/TEST-A prds/active/TEST-B

# Both use "test/shared-branch"
for id in A B; do
    cat > "prds/active/TEST-$id/prd.json" << EOF
{
  "project": "test-$id",
  "branchName": "test/shared-branch",
  "userStories": [{"id": "US-001", "title": "Test", "passes": false}]
}
EOF
done
```

**Execution**:
```bash
./claude-loop.sh --parallel
```

**Expected Results**:
- ✅ First PRD uses `test/shared-branch`
- ✅ Second PRD uses `test/shared-branch-1` (auto-suffix)
- ✅ Both worktrees created successfully
- ✅ No git errors in logs
- ✅ Registry shows different branches for each PRD

**Validation**:
```bash
# Check registry for branch names
cat .claude-loop/coordinator/registry.json | jq '.active_prds | to_entries[] | {id: .key, branch: .value.branch}'
```

---

### TC-006: Worker Failure Isolation
**Objective**: Verify one PRD failure doesn't affect others

**Setup**:
```bash
# Create failing PRD
mkdir -p prds/active/TEST-FAIL
cat > prds/active/TEST-FAIL/prd.json << 'EOF'
{
  "project": "test-fail",
  "branchName": "test/fail",
  "userStories": [
    {
      "id": "US-001",
      "title": "Impossible task",
      "description": "This will fail",
      "passes": false,
      "acceptanceCriteria": [
        "Create a file that cannot be created",
        "Achieve the impossible"
      ]
    }
  ]
}
EOF

# Create normal PRD
mkdir -p prds/active/TEST-OK
cat > prds/active/TEST-OK/prd.json << 'EOF'
{
  "project": "test-ok",
  "branchName": "test/ok",
  "userStories": [
    {
      "id": "US-001",
      "title": "Simple task",
      "passes": false,
      "acceptanceCriteria": ["Create file ok.txt"]
    }
  ]
}
EOF
```

**Execution**:
```bash
./claude-loop.sh --parallel
```

**Expected Results**:
- ✅ TEST-FAIL worker starts
- ✅ TEST-OK worker starts
- ✅ TEST-FAIL worker fails/stops
- ✅ TEST-OK worker continues and completes
- ✅ TEST-FAIL marked as "failed" in registry
- ✅ TEST-OK marked as "completed" in registry
- ✅ TEST-FAIL worktree preserved for debugging

**Validation**:
```bash
# Check both PRDs in registry
cat .claude-loop/coordinator/registry.json | jq '{failed: .failed_prds, completed: .completed_prds}'

# Verify TEST-OK completed
cat .claude-loop/worktrees/TEST-OK/ok.txt
```

---

### TC-007: Graceful Shutdown (Ctrl+C)
**Objective**: Verify SIGINT handler cleans up properly

**Execution**:
```bash
# Start parallel execution
./claude-loop.sh --parallel

# After 10 seconds, press Ctrl+C
# (Computer Use Agent will send SIGINT)
```

**Expected Results**:
- ✅ Coordinator receives SIGINT
- ✅ All workers receive SIGTERM
- ✅ Workers have 60s to finish current iteration
- ✅ Force kill after timeout if needed
- ✅ Registry saved with current state
- ✅ Worktrees preserved for resume
- ✅ Exit code indicates interrupted (130 or 1)

**Validation**:
```bash
# Check registry exists
test -f .claude-loop/coordinator/registry.json && echo "✓ Registry saved"

# Check worktrees preserved
ls -la .claude-loop/worktrees/

# Check worker logs
tail .claude-loop/coordinator/logs/*_worker.log
```

---

### TC-008: Empty Active PRDs
**Objective**: Verify helpful error when no PRDs found

**Setup**:
```bash
# Ensure prds/active is empty
rm -rf prds/active/*
```

**Execution**:
```bash
./claude-loop.sh --parallel
```

**Expected Results**:
- ✅ Coordinator initializes
- ✅ Clear error message: "No PRDs in prds/active/"
- ✅ Helpful suggestion to create PRDs
- ✅ Exit code 1
- ✅ No worktrees created

---

### TC-009: Already Checked Out Branch
**Objective**: Verify handling when main branch is checked out

**Setup**:
```bash
# Create PRD with current branch name
git branch --show-current  # e.g., feature/phase1-cowork-features

mkdir -p prds/active/TEST-CURRENT
cat > prds/active/TEST-CURRENT/prd.json << EOF
{
  "project": "test-current",
  "branchName": "$(git branch --show-current)",
  "userStories": [{"id": "US-001", "title": "Test", "passes": false}]
}
EOF
```

**Execution**:
```bash
./claude-loop.sh --parallel
```

**Expected Results**:
- ✅ Git error: "branch is already checked out"
- ✅ Coordinator handles error gracefully
- ✅ Error logged to worker logs
- ✅ PRD marked as failed
- ✅ Helpful error message suggests switching branches

---

### TC-010: API Rate Limiting
**Objective**: Verify API token semaphore works

**Validation** (requires instrumentation):
```bash
# Check API tokens file during execution
watch -n 1 'cat .claude-loop/coordinator/api_tokens 2>/dev/null || echo "0"'

# Expected: Never exceeds PARALLEL_API_LIMIT (default: 10)
```

**Expected Results**:
- ✅ API tokens file exists
- ✅ Token count never exceeds limit
- ✅ Tokens released when workers complete
- ✅ No token leaks

---

## Safety & Isolation Tests

### TC-011: Worktree Isolation
**Objective**: Verify PRDs don't interfere with each other

**Setup**: Run TC-001 (2 PRDs in parallel)

**Validation**:
```bash
# Check worktrees are separate
ls -la .claude-loop/worktrees/TEST-001/.claude-loop/
ls -la .claude-loop/worktrees/TEST-002/.claude-loop/

# Verify session state is isolated
cat .claude-loop/worktrees/TEST-001/.claude-loop/session-state.json
cat .claude-loop/worktrees/TEST-002/.claude-loop/session-state.json

# Verify no cross-contamination
diff -r .claude-loop/worktrees/TEST-001/test-001.txt \
         .claude-loop/worktrees/TEST-002/test-001.txt
# Should fail - files shouldn't exist in other worktree
```

**Expected Results**:
- ✅ Each worktree has isolated `.claude-loop/` directory
- ✅ Session state files are separate
- ✅ Files created in one PRD don't appear in another
- ✅ Git history is separate per branch

---

### TC-012: Registry Atomic Operations
**Objective**: Verify concurrent updates don't corrupt registry

**Test** (requires concurrent operations):
```bash
# Simulate concurrent registration (if possible)
# This is hard to test with Computer Use Agent
# Manual verification: inspect registry after parallel execution
cat .claude-loop/coordinator/registry.json | jq '.'

# Should be valid JSON with no corruption
```

**Expected Results**:
- ✅ Registry is always valid JSON
- ✅ No missing or duplicate entries
- ✅ All fields properly populated

---

## Performance Tests

### TC-013: Memory Usage
**Objective**: Measure memory per worker

**Execution**:
```bash
# Monitor memory during parallel execution
while true; do
    ps aux | grep "claude-loop" | grep -v grep
    sleep 5
done
```

**Expected**: ~500MB per active worker

---

### TC-014: Disk Usage
**Objective**: Measure disk per worktree

**Validation**:
```bash
du -sh .claude-loop/worktrees/TEST-*
```

**Expected**: ~2GB per worktree (depends on repo size)

---

## Computer Use Agent Test Script

```python
# Pseudo-code for Computer Use Agent test execution

test_scenarios = [
    ("TC-001", "Basic Parallel Execution", test_basic_parallel),
    ("TC-002", "Status Monitoring", test_status),
    ("TC-003", "Stop Worker", test_stop),
    ("TC-004", "Resource Limits", test_resource_limits),
    ("TC-005", "Branch Conflicts", test_branch_conflicts),
    ("TC-006", "Failure Isolation", test_failure_isolation),
    ("TC-007", "Graceful Shutdown", test_graceful_shutdown),
    ("TC-008", "Empty PRDs", test_empty_prds),
    ("TC-009", "Current Branch", test_current_branch),
    ("TC-011", "Worktree Isolation", test_worktree_isolation),
]

for test_id, test_name, test_func in test_scenarios:
    print(f"Running {test_id}: {test_name}")
    result = test_func()

    if result.passed:
        print(f"✅ {test_id} PASSED")
    else:
        print(f"❌ {test_id} FAILED: {result.error}")

    # Cleanup between tests
    cleanup_test_environment()
```

---

## Success Criteria

### Must Pass (Critical)
- [ ] TC-001: Basic parallel execution
- [ ] TC-004: Resource limits
- [ ] TC-006: Failure isolation
- [ ] TC-007: Graceful shutdown
- [ ] TC-011: Worktree isolation

### Should Pass (Important)
- [ ] TC-002: Status monitoring
- [ ] TC-003: Stop worker
- [ ] TC-005: Branch conflicts
- [ ] TC-008: Empty PRDs
- [ ] TC-009: Current branch

### Nice to Have (Optional)
- [ ] TC-010: API rate limiting
- [ ] TC-012: Atomic operations
- [ ] TC-013: Memory usage
- [ ] TC-014: Disk usage

---

## Test Report Template

```markdown
# Parallel PRD Execution - Test Report

**Date**: [Date]
**Tester**: Computer Use Agent
**Environment**: macOS, bash 3.x

## Summary

- **Total Tests**: 14
- **Passed**: X
- **Failed**: Y
- **Skipped**: Z

## Critical Issues

[List any critical failures]

## Results

| Test ID | Name | Status | Notes |
|---------|------|--------|-------|
| TC-001 | Basic Parallel | ✅ PASS | 2 PRDs completed successfully |
| TC-002 | Status | ✅ PASS | JSON output valid |
| ... | ... | ... | ... |

## Recommendations

[Based on test results]
```

---

## Next Steps

1. Execute all test cases with Computer Use Agent
2. Document results in test report
3. Fix any critical issues found
4. Re-test after fixes
5. Update PR with test results
