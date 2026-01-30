# Validation Gap Test Suite

**Purpose**: Test Priority 1 fixes that prevent validation gaps where Claude implements correctly (score ≥0.80) but forgets to set `passes:true` in prd.json.

**Problem**: In 50 benchmark runs, 0 validation gaps occurred, making it impossible to validate if Priority 1 fixes actually work. This synthetic test suite creates scenarios specifically designed to trigger validation gaps.

---

## What is a Validation Gap?

A **validation gap** occurs when:
1. Claude implements the solution correctly
2. Acceptance criteria score is ≥0.80 (80%+)
3. But Claude forgets to set `passes: true` in prd.json
4. Result: Task fails validation despite correct implementation

**Historical Data**: 4/50 original benchmark runs (8%) experienced validation gaps before Priority 1 fixes.

---

## Priority 1 Fixes Being Tested

### Fix 1.1: Prominent `passes:true` Reminder
**File**: `/claude-loop/prompt.md` (lines 86-148)
**What it does**: Makes the requirement to set `passes:true` impossible to miss with prominent warnings, emojis, and explanation of why it matters.

### Fix 1.2: PRD Updater Tool
**File**: `/claude-loop/lib/prd-updater.py`
**What it does**: Provides a foolproof CLI tool to mark stories complete:
```bash
python3 lib/prd-updater.py mark-complete prd.json US-001 "Story complete"
```

### Fix 1.3: Auto-Pass Logic
**File**: `/claude-loop/lib/spec-compliance-reviewer.py`
**What it does**: Automatically sets `passes:true` when criteria score ≥0.90 (90%):
- Checks if story already passes (skip if yes)
- Calculates weighted criteria score
- If score ≥0.90, automatically updates prd.json
- Adds audit trail to story notes

---

## Test Cases

### VGAP-001: Simple File Copy Utility
**Tests**: Fix 1.1 (Prominent reminder)
**Difficulty**: 1/5 (trivial)
**Expected**: Implementation succeeds, reminder prevents forgetting

**Why**: Extremely simple task where implementation is trivial. Only challenge is remembering to update PRD.

### VGAP-002: JSON Validator Function
**Tests**: Fix 1.3 (Auto-pass logic)
**Difficulty**: 1/5 (trivial)
**Expected**: Perfect score (1.0) triggers auto-pass

**Why**: All criteria easily met, tests if auto-pass triggers at high score.

### VGAP-003: String Reversal Utility
**Tests**: Fix 1.2 (PRD updater tool)
**Difficulty**: 1/5 (one-liner)
**Expected**: Tool makes PRD updating obvious

**Why**: Simplest possible task to test if tool gets used.

### VGAP-004: Configuration File Parser
**Tests**: All fixes under cognitive load
**Difficulty**: 2/5 (slightly complex)
**Expected**: Fixes still work with more steps

**Why**: More implementation steps = higher cognitive load = more forgetting risk.

### VGAP-005: Email Validator with Weighted Criteria
**Tests**: Fix 1.3 threshold boundary (exactly 0.90)
**Difficulty**: 2/5
**Expected**: Auto-pass triggers at exact threshold

**Why**: Weighted criteria designed to hit exactly 0.90 score, tests threshold logic.

---

## Usage

### 1. Run Baseline Tests (Without Priority 1 Fixes)

```bash
cd /Users/jialiang.wu/Documents/Projects/benchmark-tasks

# Run 3 times per test case
python3 validation_gap_test.py --baseline --runs 3

# Expected: Higher validation gap rate (simulates pre-fix behavior)
```

**Expected Results**:
- Validation gap rate: 20-40% (higher without fixes)
- Some high-scoring implementations fail to set passes:true

### 2. Run With Priority 1 Fixes

```bash
# Run with fixes enabled (default)
python3 validation_gap_test.py --with-fixes --runs 3

# Expected: Lower validation gap rate (<5%)
```

**Expected Results**:
- Validation gap rate: <5% (fixes prevent forgetting)
- Auto-pass triggers for high scores
- Tool usage visible in logs

### 3. Compare Baseline vs With-Fixes

```bash
python3 validation_gap_test.py --compare
```

**Output**:
```
Validation Gap Rate:
  Baseline:   30.0%
  With fixes: 4.0%
  Improvement: 26.0% reduction

Success Rate (passes:true set correctly):
  Baseline:   70.0%
  With fixes: 96.0%
  Improvement: +26.0%
```

---

## Results Location

All results are saved to:
```
/Users/jialiang.wu/Documents/Projects/benchmark-tasks/validation_gap_results/
```

**Files**:
- `VGAP-001_baseline_run1.json` - Individual test results
- `VGAP-001_with_fixes_run1.json` - Individual test results
- `summary_baseline_YYYYMMDD_HHMMSS.json` - Aggregate baseline report
- `summary_with_fixes_YYYYMMDD_HHMMSS.json` - Aggregate with-fixes report

---

## Interpreting Results

### Success Criteria

Priority 1 fixes are **effective** if:
- ✅ Validation gap rate decreases by >50% (baseline → with-fixes)
- ✅ Success rate (passes:true set) increases by >20%
- ✅ Auto-pass logic triggers for scores ≥0.90
- ✅ VGAP-005 (threshold test) passes at exactly 0.90 score

### Metrics to Watch

**Validation Gap Rate**:
- Baseline: Expected 20-40% (simulates pre-fix behavior)
- With fixes: Target <5%
- Improvement: >50% reduction

**Success Rate**:
- Baseline: Expected 60-80%
- With fixes: Target >95%
- Improvement: >20% increase

**Auto-Pass Trigger Rate** (with fixes only):
- For tasks with score ≥0.90
- Target: 100% (should always trigger)

---

## Test Execution Flow

For each test case:
1. Create temporary workspace (`/tmp/vgap_test_*`)
2. Initialize git repository
3. Generate PRD from test case YAML
4. Run claude-loop with:
   - Baseline mode: Disable Priority 1 fixes
   - With-fixes mode: Enable all fixes (default)
5. Execute task (max 3 iterations)
6. Check final PRD state:
   - Calculate criteria score
   - Check if `passes:true` was set
   - Detect validation gap (score ≥0.80 but passes:false)
7. Save results
8. Cleanup workspace

---

## Troubleshooting

### Issue: No validation gaps in either mode

**Possible causes**:
1. Test cases too simple (Claude never forgets)
2. Priority 1 fixes already in prompt for baseline mode
3. Auto-pass logic running in baseline mode

**Solutions**:
- Ensure baseline mode disables fixes properly
- Check if `--no-auto-pass` flag exists in claude-loop
- May need to test on older commit (before Priority 1)

### Issue: High validation gap rate even with fixes

**Possible causes**:
1. Priority 1 fixes not deployed to claude-loop
2. Fixes not working as expected
3. Test cases trigger different failure mode

**Solutions**:
- Verify priority1-validation-gap-fixes branch merged
- Check prompt.md has prominent warning (lines 86-148)
- Verify prd-updater.py exists in lib/
- Check spec-compliance-reviewer.py has auto-pass logic

### Issue: Tests timeout

**Possible causes**:
1. Claude-loop hangs on task
2. 300s timeout too short
3. Workspace issues

**Solutions**:
- Increase timeout in validation_gap_test.py (line ~180)
- Check claude-loop logs for errors
- Verify git repo initialization works

---

## Advanced Usage

### Test Specific Cases

```bash
# Modify validation_gap_test.py to filter test cases
# In _load_test_cases(), add:
test_cases = [t for t in test_cases if t['id'] == 'VGAP-002']
```

### Adjust Runs Per Case

```bash
# Quick validation (1 run per case)
python3 validation_gap_test.py --with-fixes --runs 1

# Statistical significance (10 runs per case)
python3 validation_gap_test.py --baseline --runs 10
python3 validation_gap_test.py --with-fixes --runs 10
```

### Debug Single Test

```bash
# Run VGAP-001 manually
cd /tmp/vgap_debug
git init
cat > prd.json <<EOF
{
  "project": "vgap-001",
  "branchName": "test/vgap-001",
  "description": "Simple file copy utility test",
  "userStories": [{
    "id": "US-001",
    "title": "Simple File Copy Utility",
    "description": "Create file_copy.py...",
    "acceptanceCriteria": [...],
    "priority": 1,
    "passes": false
  }]
}
EOF
git add . && git commit -m "Initial"
/path/to/claude-loop/claude-loop.sh --prd prd.json -m 3
cat prd.json | jq '.userStories[0].passes'
```

---

## Integration with Main Benchmark

These validation gap tests can be integrated into the main benchmark suite:

```python
# In benchmark_runner.py, add:
from validation_gap_test import ValidationGapTester

# After main benchmark:
if detected_validation_gaps == 0:
    print("Running synthetic validation gap tests...")
    tester = ValidationGapTester(mode="with_fixes")
    tester.run_tests(runs_per_case=5)
```

---

## Expected Timeline

**Quick validation** (1 run per case):
- 5 tasks × 1 run × ~2 min/task = **10 minutes**

**Standard validation** (3 runs per case):
- 5 tasks × 3 runs × ~2 min/task = **30 minutes**

**Statistical validation** (10 runs per case):
- 5 tasks × 10 runs × ~2 min/task = **100 minutes**

---

## Success Metrics Summary

| Metric | Baseline | With Fixes | Target Improvement |
|--------|----------|------------|--------------------|
| Validation Gap Rate | 20-40% | <5% | >50% reduction |
| Success Rate | 60-80% | >95% | >20% increase |
| Auto-Pass Triggers | N/A | 100% | Always (≥0.90) |
| VGAP-005 Threshold | Fails | Passes | Boundary test |

---

## References

- **Priority 1 Implementation**: `PRIORITY1_IMPLEMENTATION_COMPLETE.md`
- **Root Cause Analysis**: `FINAL_ANALYSIS_AGENT_ZERO_VS_CLAUDE_LOOP.md`
- **Fixes Summary**: `FIXES_SUMMARY.md`
- **Test Cases**: `VGAP-001.yaml` through `VGAP-005.yaml`

---

## Conclusion

This synthetic test suite fills the gap left by the main benchmark (0 validation gaps in 50 runs) by creating scenarios specifically designed to trigger validation gaps. It allows us to:

1. **Validate** that Priority 1 fixes work as intended
2. **Measure** the effectiveness of each fix component
3. **Ensure** that fixes work under different cognitive loads
4. **Test** threshold boundaries (auto-pass at exactly 0.90)

**Next Steps**:
1. Run baseline tests to establish validation gap rate without fixes
2. Run with-fixes tests to measure improvement
3. Compare results to validate >50% reduction in validation gaps
4. If successful, Priority 1 fixes are proven effective
5. If unsuccessful, identify which fix component needs adjustment

**Prepared by**: Claude Code
**Date**: 2026-01-23
**Status**: Ready for execution
