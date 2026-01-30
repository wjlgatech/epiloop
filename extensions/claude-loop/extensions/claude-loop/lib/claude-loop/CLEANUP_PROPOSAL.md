# Codebase Cleanup Proposal

## Current State Analysis

**Python Scripts**: 5 files (some redundant)
- `benchmark_runner.py` (28KB) - Original comparative benchmark
- `benchmark_runner_auto.py` (4KB) - Auto mode variant
- `benchmark_auto_with_fixes.py` (18KB) - **Current/Active** 50-case with fixes
- `ab_test_failed_cases.py` (14KB) - A/B testing script
- `rerun_failed_cases.py` (13KB) - Targeted re-run script

**Markdown Docs**: 10 files (some interim/outdated)
- `README.md` - Main overview (keep)
- `CLAUDE.md` - Claude Code guide (keep, just created)
- `USAGE_GUIDE.md` - Detailed instructions (keep)
- `ANALYSIS.md` - Comprehensive 58-page analysis (keep)
- `DECISION_REPORT.md` - Decision framework (keep)
- `FINAL_DECISION_REPORT.md` - Final decision (keep)
- `IMPLEMENTATION_COMPLETE.md` - Status tracking (archive?)
- `MODE_INVESTIGATION.md` - Mode research (archive?)
- `NEXT_STEPS.md` - Next steps guide (keep or merge?)
- `AGENTS.md` - Empty placeholder (delete)

**Other Files**:
- `benchmark_runner.py.backup` (24KB) - Backup file (delete?)
- `prd.json`, `progress.txt` - Test artifacts (gitignore)
- `.claude-loop/` - Execution artifacts (gitignore)
- `.last-branch` - Claude-loop temp file (gitignore)
- `test.txt` - Test file (delete)

## Proposed Reorganization

### Option A: Minimal Cleanup (Recommended)
**Impact**: Low risk, quick (~5 minutes)
**Changes**:
1. Move old/interim docs to `docs/archive/`
2. Delete obvious cruft (AGENTS.md, test.txt, .backup)
3. Update .gitignore for runtime artifacts
4. Keep all functional Python scripts (they're all useful)

### Option B: Comprehensive Reorganization
**Impact**: Medium risk, longer (~30 minutes)
**Changes**:
1. All Option A changes
2. Consolidate Python scripts into `scripts/` directory
3. Create `docs/` directory structure
4. Consolidate validation scripts
5. Add script README.md explaining each tool

### Option C: No Changes
Just add to .gitignore and commit as-is

## Recommendation: Option A (Minimal)

**Rationale**:
- Keep functionality intact (no code changes)
- Remove obvious cruft
- Prevent artifacts from being committed
- Low risk, quick execution
- Preserve all working scripts (each serves a purpose)

**Actions**:
```bash
# 1. Create archive directory
mkdir -p docs/archive

# 2. Archive interim docs
git mv IMPLEMENTATION_COMPLETE.md docs/archive/
git mv MODE_INVESTIGATION.md docs/archive/

# 3. Delete cruft
rm AGENTS.md test.txt benchmark_runner.py.backup

# 4. Update .gitignore
cat >> .gitignore << 'IGNORE'
# Claude-loop runtime artifacts
.claude-loop/
.last-branch
prd.json
progress.txt

# Python cache
__pycache__/
*.pyc

# OS files
.DS_Store

# Temporary test files
test*.txt
IGNORE

# 5. Clean working directory
git restore prd.json progress.txt
```

**Keep All Python Scripts Because**:
- `benchmark_runner.py` - Multi-framework comparison (original)
- `benchmark_auto_with_fixes.py` - Current primary tool
- `rerun_failed_cases.py` - Debugging tool
- `ab_test_failed_cases.py` - A/B testing tool
- Each serves distinct purpose, all are functional

## Git Workflow Proposal

```bash
# 1. Apply cleanup (Option A)
# ... (commands above)

# 2. Stage changes
git add .

# 3. Commit cleanup
git commit -m "chore: Clean up benchmark suite

- Archive interim documentation (IMPLEMENTATION_COMPLETE, MODE_INVESTIGATION)
- Remove test artifacts and empty files
- Add .gitignore for runtime artifacts
- Keep all functional Python scripts (each serves distinct purpose)"

# 4. Push to remote
git push origin test

# 5. Consider PR to main branch
```

## Risk Assessment

**Option A Risks**: Minimal
- No code changes
- No functional changes
- Just organization and cleanup

**Mitigation**: All changes are reversible via git

## Next Steps

1. Review this proposal
2. Choose option (recommend A)
3. Execute cleanup
4. Git push
5. Continue development with cleaner repo
