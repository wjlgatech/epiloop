# Validation Gap Tests - Pre-Flight Checklist

**Before running tests, verify all prerequisites are met.**

---

## ✅ File Verification

### Test Case Definitions
- [x] VGAP-001.yaml (3.7KB) - File Copy Utility
- [x] VGAP-002.yaml (3.9KB) - JSON Validator
- [x] VGAP-003.yaml (3.4KB) - String Reversal
- [x] VGAP-004.yaml (4.5KB) - Config Parser
- [x] VGAP-005.yaml (4.6KB) - Email Validator

**Verification**:
```bash
ls -lh VGAP-*.yaml | wc -l
# Expected: 5 files
```

### Test Infrastructure
- [x] validation_gap_test.py (17KB) - Test runner
- [x] run_validation_gap_tests.sh (3.9KB) - Quick start script
- [x] Both scripts executable (chmod +x)

**Verification**:
```bash
test -x validation_gap_test.py && test -x run_validation_gap_tests.sh && echo "✓ Scripts executable"
```

### Documentation
- [x] VALIDATION_GAP_TESTS_README.md (9.8KB) - Full documentation
- [x] VALIDATION_GAP_TESTS_SUMMARY.md (13KB) - Implementation summary
- [x] VALIDATION_GAP_TESTS_CHECKLIST.md (this file)

**Verification**:
```bash
ls VALIDATION_GAP_TESTS*.md | wc -l
# Expected: 3 files
```

---

## ✅ Environment Prerequisites

### Claude-Loop Installation
- [ ] Claude-loop installed at: `/Users/jialiang.wu/Documents/Projects/claude-loop`
- [ ] Priority 1 fixes deployed (check branch: `feature/priority1-validation-gap-fixes`)
- [ ] Claude Code CLI available (`claude` command)

**Verification**:
```bash
# Check claude-loop exists
test -d /Users/jialiang.wu/Documents/Projects/claude-loop && echo "✓ claude-loop installed"

# Check Priority 1 fixes (should have prominent warning in prompt.md)
grep -A 5 "CRITICAL STEP - VALIDATION WILL FAIL" /Users/jialiang.wu/Documents/Projects/claude-loop/prompt.md | head -1
# Expected: "### Step 6: Update State Files"

# Check prd-updater.py exists
test -f /Users/jialiang.wu/Documents/Projects/claude-loop/lib/prd-updater.py && echo "✓ prd-updater.py exists"

# Check auto-pass logic in spec-compliance-reviewer.py
grep "calculate_criteria_score" /Users/jialiang.wu/Documents/Projects/claude-loop/lib/spec-compliance-reviewer.py && echo "✓ auto-pass logic exists"

# Check claude CLI
which claude
# Expected: path to claude executable
```

### Python Dependencies
- [ ] Python 3.7+ installed
- [ ] PyYAML installed (`pip install pyyaml`)
- [ ] Git installed

**Verification**:
```bash
python3 --version
# Expected: Python 3.7 or higher

python3 -c "import yaml; print('✓ PyYAML installed')"
# Expected: ✓ PyYAML installed

git --version
# Expected: git version 2.x or higher
```

### Disk Space
- [ ] At least 500MB free space (for temporary workspaces)

**Verification**:
```bash
df -h /tmp | tail -1
# Check "Avail" column for >500MB
```

---

## ✅ Configuration Verification

### Test Runner Configuration
- [ ] BENCHMARK_DIR path correct: `/Users/jialiang.wu/Documents/Projects/benchmark-tasks`
- [ ] CLAUDE_LOOP_DIR path correct: `/Users/jialiang.wu/Documents/Projects/claude-loop`
- [ ] RESULTS_DIR will be created: `validation_gap_results/`

**Verification**:
```bash
# Check paths in validation_gap_test.py
grep "BENCHMARK_DIR = Path" validation_gap_test.py
grep "CLAUDE_LOOP_DIR = Path" validation_gap_test.py
# Verify paths match your system
```

### Timeout Settings
- [ ] Default timeout: 300s (5 minutes) per test case
- [ ] Adjust if needed in validation_gap_test.py line ~180

**Verification**:
```bash
grep "timeout=300" validation_gap_test.py
# Expected: timeout=300 in subprocess.run call
```

---

## ✅ Baseline Mode Setup

**Important**: For baseline testing (without Priority 1 fixes), you have two options:

### Option A: Use Flag to Disable Fixes (Recommended)
If claude-loop supports a `--no-auto-pass` flag:
```bash
# Check if flag exists
/Users/jialiang.wu/Documents/Projects/claude-loop/claude-loop.sh --help | grep "no-auto-pass"
```

If flag exists:
- [x] No additional setup needed
- [x] Baseline mode will use `--no-auto-pass` flag

If flag doesn't exist:
- [ ] Need Option B (use older commit)

### Option B: Use Older Commit (Before Priority 1)
If no flag available, checkout older claude-loop:
```bash
cd /Users/jialiang.wu/Documents/Projects/claude-loop
git stash  # Save current work
git checkout <commit-before-priority1>  # e.g., commit before a86b8e2

# After baseline tests complete:
git checkout feature/priority1-validation-gap-fixes
git stash pop
```

**Note**: Update `_run_test_case()` in validation_gap_test.py to handle baseline mode appropriately.

---

## ✅ Test Execution Checklist

### Before Running

1. [ ] All files verified (see above)
2. [ ] Environment prerequisites met
3. [ ] Claude Code has sufficient API credits
4. [ ] No other intensive processes running (tests need CPU)
5. [ ] Results directory cleared (optional): `rm -rf validation_gap_results/`

### Quick Validation (Recommended First Run)

```bash
./run_validation_gap_tests.sh quick
```

**Expected Duration**: 15 minutes
**Expected Output**: <5% validation gap rate

**Success Criteria**:
- [ ] All 5 test cases execute
- [ ] No crashes or timeouts
- [ ] Results saved to validation_gap_results/
- [ ] Summary report shows validation gap rate <5%

### Full Validation (After Quick Validation Succeeds)

```bash
./run_validation_gap_tests.sh full
```

**Expected Duration**: 1 hour
**Expected Output**:
- Baseline: 20-40% validation gap rate
- With-fixes: <5% validation gap rate
- Comparison: >50% reduction

**Success Criteria**:
- [ ] Baseline tests complete (5 cases × 3 runs = 15 tests)
- [ ] With-fixes tests complete (5 cases × 3 runs = 15 tests)
- [ ] Comparison report generated
- [ ] Improvement >50% documented

---

## ✅ Troubleshooting Verification

### If Tests Fail to Start

**Check**:
```bash
# Verify paths
cat validation_gap_test.py | grep "BENCHMARK_DIR\|CLAUDE_LOOP_DIR"

# Verify VGAP files loadable
python3 -c "import yaml; yaml.safe_load(open('VGAP-001.yaml'))"
```

### If Tests Timeout

**Check**:
```bash
# Verify claude-loop works manually
cd /tmp/test_workspace
git init
echo '{"project":"test","userStories":[{"id":"US-001","passes":false}]}' > prd.json
/Users/jialiang.wu/Documents/Projects/claude-loop/claude-loop.sh --prd prd.json -m 1
```

### If No Validation Gaps Detected

**Check**:
```bash
# Verify baseline mode disables fixes
# (see "Baseline Mode Setup" section above)

# Manually verify PRD not auto-updated
cd /tmp/test_workspace
# (run claude-loop without auto-pass)
cat prd.json | jq '.userStories[0].passes'
# Should show: false (if auto-pass disabled)
```

---

## ✅ Expected Results Verification

### After Quick Validation (1 run per case)

**Expected Metrics**:
```
Total runs: 5
High scores (≥0.80): 5 (100%)
passes:true set: 4-5 (80-100%)
Validation gaps: 0-1 (0-20%)
```

**Files Created**:
```
validation_gap_results/
├── VGAP-001_with_fixes_run1.json
├── VGAP-002_with_fixes_run1.json
├── VGAP-003_with_fixes_run1.json
├── VGAP-004_with_fixes_run1.json
├── VGAP-005_with_fixes_run1.json
└── summary_with_fixes_TIMESTAMP.json
```

### After Full Validation (3 runs per case, both modes)

**Expected Metrics**:
```
Baseline:
  Total runs: 15
  Validation gap rate: 20-40%
  Success rate: 60-80%

With-fixes:
  Total runs: 15
  Validation gap rate: <5%
  Success rate: >95%

Improvement: >50% reduction in validation gaps
```

**Files Created**:
```
validation_gap_results/
├── VGAP-001_baseline_run{1,2,3}.json
├── VGAP-001_with_fixes_run{1,2,3}.json
├── ... (similar for VGAP-002 through VGAP-005)
├── summary_baseline_TIMESTAMP.json
└── summary_with_fixes_TIMESTAMP.json
```

---

## ✅ Post-Test Checklist

### After Tests Complete

1. [ ] Review summary report: `validation_gap_results/summary_*.json`
2. [ ] Verify improvement >50% (if running both modes)
3. [ ] Check individual test results for patterns
4. [ ] Document findings in PRIORITY1_BENCHMARK_RESULTS.md
5. [ ] If successful, proceed to full 50-case benchmark
6. [ ] If unsuccessful, review troubleshooting section

### Cleanup (Optional)

```bash
# Remove temporary workspaces (auto-cleaned, but verify)
rm -rf /tmp/vgap_test_*

# Archive results
tar -czf validation_gap_results_$(date +%Y%m%d).tar.gz validation_gap_results/

# Keep or remove raw results
# rm -rf validation_gap_results/  # Optional
```

---

## ✅ Ready to Run?

**If all items above are checked**, you're ready to run:

```bash
# Start with quick validation
./run_validation_gap_tests.sh quick
```

**If some items are unchecked**:
1. Complete missing prerequisites
2. Fix any verification failures
3. Re-check this list
4. Then run tests

---

## Quick Reference Commands

### Verify Everything
```bash
# One-liner to check all prerequisites
cd /Users/jialiang.wu/Documents/Projects/benchmark-tasks && \
ls VGAP-*.yaml | wc -l && \
test -x validation_gap_test.py && \
test -x run_validation_gap_tests.sh && \
test -d /Users/jialiang.wu/Documents/Projects/claude-loop && \
python3 -c "import yaml" && \
echo "✓ All prerequisites met"
```

### Run Quick Test
```bash
./run_validation_gap_tests.sh quick
```

### View Results
```bash
# View latest summary
ls -t validation_gap_results/summary_*.json | head -1 | xargs cat | python3 -m json.tool

# Count validation gaps
grep -r "validation_gap.*true" validation_gap_results/*.json | wc -l
```

---

**Created**: January 23, 2026
**Status**: Ready for testing
**Contact**: See VALIDATION_GAP_TESTS_README.md for support
