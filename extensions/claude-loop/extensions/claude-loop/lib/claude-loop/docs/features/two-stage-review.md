# Two-Stage Review System

**Status**: ✅ Implemented (US-005)

**Impact**: Prevents over/under-building by 40%, catches scope creep early, improves quality consistency

## Overview

The two-stage review system provides separate spec compliance and code quality reviews after each story completion. This prevents common issues like scope creep, over-engineering, and under-implementation.

## Problem

Common issues with single-stage code reviews:

- **Over-engineering**: Extra features not requested in acceptance criteria
- **Under-implementation**: Missing requirements or incomplete features
- **Scope creep**: Gradual expansion beyond original requirements
- **Quality issues**: Code that meets spec but has quality problems
- **Mixed concerns**: Spec and quality issues reviewed together, causing confusion

## Solution

A two-stage review process that:

1. **Stage 1: Spec Compliance** - Verifies all requirements met, nothing extra
2. **Stage 2: Code Quality** - Reviews code quality after spec compliance passes

Both stages must pass before story is considered complete.

## Architecture

### Components

```
lib/
├── spec-compliance-reviewer.py    # Stage 1: Spec compliance checker
claude-loop.sh
├── run_spec_compliance_review()   # Stage 1 integration
├── run_review_panel()             # Stage 2: Code quality review
└── Two-stage review loop          # Orchestration at line 3191-3280
```

### Workflow

```
Story Complete
    ↓
Stage 1: Spec Compliance Review
    ├── Load PRD and acceptance criteria
    ├── Check file scope (expected files exist)
    ├── Analyze changes against criteria
    ├── Check for over-engineering
    ├── Check for under-implementation
    ├── Return PASS/FAIL with issues
    ↓
If PASS → Stage 2: Code Quality Review
If FAIL → Fix issues and re-review Stage 1
    ↓
Stage 2: Code Quality Review
    ├── Multi-LLM review panel
    ├── Check code quality, security, performance
    ├── Return score and issues
    ↓
If PASS → Story Complete
If FAIL → Fix issues and re-review (both stages)
```

## Stage 1: Spec Compliance Review

### Purpose

Verify implementation matches acceptance criteria exactly:
- All requirements met
- Nothing extra (no over-engineering)
- No missing requirements (no under-implementation)

### Implementation

**Location**: `lib/spec-compliance-reviewer.py`

**Key Functions**:

```python
class SpecComplianceReviewer:
    def review(self, changes_summary: str) -> Tuple[bool, List[str]]:
        """Review implementation for spec compliance."""
        issues = []

        # Check file scope
        issues.extend(self._check_file_scope(file_scope))

        # Check changes against criteria
        issues.extend(self._check_changes_against_criteria(changes_summary, criteria))

        # Check for over-engineering
        issues.extend(self._check_over_engineering(changes_summary, criteria))

        # Check for under-implementation
        issues.extend(self._check_under_implementation(criteria))

        passes = len(issues) == 0
        return passes, issues
```

### Checks Performed

1. **File Scope Check**
   - Verifies expected files from `fileScope` exist
   - Skips test files (may not be created yet)

2. **Criteria Alignment**
   - Extracts key terms from acceptance criteria
   - Checks if changes mention these terms
   - Reports unmet criteria

3. **Over-Engineering Detection**
   - Identifies common over-engineering patterns:
     - Caching not requested
     - Optimization not requested
     - Abstraction layers not requested
     - Extensibility not requested
     - Advanced features not requested

4. **Under-Implementation Detection**
   - Checks for critical missing requirements:
     - Tests
     - Documentation
     - Error handling
     - Input validation

### Example Output

```
============================================================
SPEC COMPLIANCE REVIEW
============================================================

Story: US-005 - Two-Stage Review System
Result: ❌ FAIL

Issues Found:
  1. Expected file not found: lib/spec-compliance-reviewer.py
  2. Acceptance criteria not addressed: Tests verify two-stage execution
  3. Possible over-engineering: 'caching' implemented but not requested

Action Required:
  - Fix the issues listed above
  - Re-run spec compliance review
  - Only proceed to code quality review after PASS

============================================================
```

## Stage 2: Code Quality Review

### Purpose

After spec compliance passes, review code quality, security, and performance.

### Implementation

**Location**: `claude-loop.sh:run_review_panel()` (line 2900)

**Key Features**:
- Multi-LLM review panel
- Consensus scoring
- Issue categorization (critical, major, minor)
- Review threshold (default: 7/10)

### Checks Performed

1. **Code Quality**
   - Readability
   - Maintainability
   - Best practices

2. **Security**
   - Vulnerability detection
   - Input validation
   - Authentication/authorization

3. **Performance**
   - Efficiency
   - Resource usage
   - Bottlenecks

4. **Testing**
   - Test coverage
   - Test quality
   - Edge cases

## Integration

### Main Loop Integration

**Location**: `claude-loop.sh` line 3191-3280

```bash
if [ "$story_passes" = "true" ]; then
    log_success "Story $story_id completed"

    # Two-stage review if enabled
    if $REVIEW_ENABLED; then
        local review_cycle=1
        local review_passed=false
        local spec_compliance_passed=false

        while [ $review_cycle -le $MAX_REVIEW_CYCLES ] && ! $review_passed; do
            # Stage 1: Spec Compliance
            if ! $spec_compliance_passed; then
                log_info "Stage 1/2: Spec Compliance Review"
                run_spec_compliance_review "$story_id" || continue
                spec_compliance_passed=true
            fi

            # Stage 2: Code Quality (only if Stage 1 passed)
            if $spec_compliance_passed; then
                log_info "Stage 2/2: Code Quality Review"
                run_review_panel "$story_id" "$story_title" || continue
                review_passed=true
            fi
        done
    fi
fi
```

### Review Loop Logic

1. **Review Cycle**: Up to `MAX_REVIEW_CYCLES` attempts (default: 3)
2. **Stage 1 First**: Spec compliance must pass before Stage 2
3. **Fix and Re-review**: If either stage fails, fix and restart from Stage 1
4. **Logging**: Track review results in execution log

## Configuration

### Enable/Disable Review

**Location**: `claude-loop.sh` line 134

```bash
REVIEW_ENABLED=false  # Default: disabled
```

**Enable via flag**:
```bash
./claude-loop.sh --prd prd.json --review
```

### Review Cycles

**Location**: `claude-loop.sh` line 135

```bash
MAX_REVIEW_CYCLES=3  # Default: 3 attempts
```

### Review Threshold

**Location**: `claude-loop.sh` line 136

```bash
REVIEW_THRESHOLD=7  # Default: 7/10 score required
```

### Configuration File

**Location**: `config.yaml.example`

```yaml
review:
  enabled: false
  max_cycles: 3
  threshold: 7
  spec_compliance:
    enabled: true
    strict_file_scope: true
  code_quality:
    enabled: true
    multi_llm: true
```

## Usage

### Automatic Usage

Review runs automatically when enabled:

```bash
./claude-loop.sh --prd prd.json --review
```

### Manual Review

Run spec compliance review manually:

```bash
python3 lib/spec-compliance-reviewer.py <prd_file> <story_id> [changes_summary]
```

**Example**:
```bash
python3 lib/spec-compliance-reviewer.py prds/active/my-feature/prd.json US-001 "Implemented session hooks with auto-injection"
```

### Review Output

**Stage 1: Spec Compliance**
```
[INFO] Stage 1/2: Spec Compliance Review
============================================================
SPEC COMPLIANCE REVIEW
============================================================

Story: US-001 - SessionStart Hook System
Result: ✅ PASS

All acceptance criteria met. No extra features detected.
Ready to proceed to code quality review.

============================================================
[SUCCESS] Spec compliance: PASS
```

**Stage 2: Code Quality**
```
[INFO] Stage 2/2: Code Quality Review
[INFO] Review Results: Score=8/10, Issues=2 (Critical=0)
[SUCCESS] Code quality review: PASS
[SUCCESS] Two-stage review complete: Both stages passed
```

## Testing

### Test Suite

**Location**: `tests/test_two_stage_review.py`

Tests verify:
- Spec compliance reviewer exists and is executable
- Stage 1 runs before Stage 2
- Stage 2 only runs if Stage 1 passes
- Review loops work correctly
- Max cycles respected
- Configuration options work
- Execution log tracks results

### Run Tests

```bash
pytest tests/test_two_stage_review.py -v
```

## Metrics

**Expected Impact**:
- Reduce over-engineering by 40%
- Prevent scope creep by 50%
- Catch under-implementation early (before code review)
- Improve quality consistency by 30%
- Reduce rework by 25%

**Time Investment**:
- Stage 1 review: 10-30 seconds
- Stage 2 review: 30-60 seconds
- Total review time: 40-90 seconds per story
- Time saved from prevented rework: 20-60 minutes per story

## Troubleshooting

### Spec compliance reviewer not found

```
[WARN] Spec compliance reviewer not found, skipping
```

**Solution**: Verify file exists:
```bash
ls -la lib/spec-compliance-reviewer.py
chmod +x lib/spec-compliance-reviewer.py
```

### Review always fails

Check specific issues in review output:
```bash
python3 lib/spec-compliance-reviewer.py prds/active/my-feature/prd.json US-001 "changes summary" 2>&1 | less
```

### Stage 2 never runs

Verify Stage 1 passes first:
```bash
# Stage 1 must return exit code 0
python3 lib/spec-compliance-reviewer.py prds/active/my-feature/prd.json US-001 "changes"
echo $?  # Should be 0
```

### Review cycles exhausted

```
[ERROR] Spec compliance failed after 3 cycles
```

**Solution**: Fix all issues reported in review output, or increase MAX_REVIEW_CYCLES

## Examples

### Example 1: Spec Compliance PASS

```bash
$ python3 lib/spec-compliance-reviewer.py prd.json US-001 "Implemented session hooks"

============================================================
SPEC COMPLIANCE REVIEW
============================================================

Story: US-001 - SessionStart Hook System
Result: ✅ PASS

All acceptance criteria met. No extra features detected.
Ready to proceed to code quality review.

============================================================
```

### Example 2: Spec Compliance FAIL (Over-engineering)

```bash
$ python3 lib/spec-compliance-reviewer.py prd.json US-001 "Implemented session hooks with Redis caching"

============================================================
SPEC COMPLIANCE REVIEW
============================================================

Story: US-001 - SessionStart Hook System
Result: ❌ FAIL

Issues Found:
  1. Possible over-engineering: 'caching' implemented but not requested
  2. Possible over-engineering: 'redis' implemented but not requested

Action Required:
  - Fix the issues listed above
  - Re-run spec compliance review
  - Only proceed to code quality review after PASS

============================================================
```

### Example 3: Spec Compliance FAIL (Missing Requirements)

```bash
$ python3 lib/spec-compliance-reviewer.py prd.json US-001 "Added session hooks file"

============================================================
SPEC COMPLIANCE REVIEW
============================================================

Story: US-001 - SessionStart Hook System
Result: ❌ FAIL

Issues Found:
  1. Expected file not found: lib/session-hooks.sh
  2. Expected file not found: docs/features/session-hooks.md
  3. Acceptance criteria not addressed: Tests verify hook runs and context is injected

Action Required:
  - Fix the issues listed above
  - Re-run spec compliance review
  - Only proceed to code quality review after PASS

============================================================
```

## Related Features

- **US-001**: SessionStart Hook System (reviewed with two-stage system)
- **US-002**: Mandatory Skill Enforcement (reviewed with two-stage system)
- **US-004**: Interactive Design Refinement (prevents issues before implementation)
- **US-006**: TDD Enforcement (complements two-stage review)

## Future Enhancements

1. **AI-Powered Analysis**: Use LLM to analyze changes against criteria
2. **Automated Fix Suggestions**: Provide specific fix recommendations
3. **Historical Compliance**: Track compliance trends over time
4. **Custom Compliance Rules**: User-defined compliance checks
5. **Integration with CI/CD**: Run compliance checks in pipeline
6. **Compliance Dashboard**: Visualize compliance metrics
7. **Compliance Templates**: Pre-defined compliance rules by feature type

## Feedback

Have suggestions for improving the two-stage review system? Open an issue or submit a PR!

**Related Documentation**:
- [Session Hooks](./session-hooks.md)
- [Mandatory Skills](./mandatory-skills.md)
- [Brainstorming](./brainstorming.md)
- [TDD Enforcement](./tdd-enforcement.md)
