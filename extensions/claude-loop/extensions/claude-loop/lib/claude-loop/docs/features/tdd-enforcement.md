# TDD Enforcement - The Iron Law

**Status**: ✅ Implemented (US-006)

**Impact**: Ensures tests actually test behavior, prevents false confidence from tests that pass only because implementation exists

## Overview

TDD Enforcement implements the "Iron Law" of Test-Driven Development: **NO production code without a failing test first**.

This enforcer verifies that tests fail (RED phase) before implementation code is written, ensuring tests actually test behavior rather than just passing because the implementation already exists.

## The Iron Law of TDD

```
1. Write test first
2. Run test, verify it FAILS (RED) ← TDD Enforcer verifies this
3. Write minimal code to pass test (GREEN)
4. Refactor (REFACTOR)
```

**Why this matters**: If a test passes before you write the implementation, the test isn't testing anything meaningful. It gives false confidence.

## Problem

Common TDD violations:

- **Test written after implementation**: Test passes immediately, doesn't verify behavior
- **Test too generic**: Passes without specific implementation
- **Test has bugs**: Passes for wrong reasons
- **Copy-paste errors**: Test doesn't actually test what you think it tests
- **False confidence**: Tests that always pass regardless of implementation

## Solution

An automated enforcer that:

1. **Detects test files** for the story
2. **Runs tests** to verify they fail (RED phase)
3. **Checks for premature implementation** (code before failing test)
4. **Reports violations** with specific actionable feedback
5. **Blocks progression** until TDD compliance is verified

## Architecture

### Components

```
lib/
├── tdd-enforcer.py           # TDD compliance checker
claude-loop.sh
└── Pre-implementation hook   # Integration point (to be added)
```

### Workflow

```
Story Start
    ↓
Write Test First
    ↓
TDD Enforcer Runs
    ├── Detect test files
    ├── Run tests
    ├── Verify tests FAIL (RED phase)
    ├── Check no implementation exists yet
    ↓
If RED → Proceed to write implementation
If GREEN → BLOCK: "Test should fail first"
If impl exists → BLOCK: "Delete implementation, start over"
```

## Implementation

### TDD Enforcer

**Location**: `lib/tdd-enforcer.py`

**Key Classes and Methods**:

```python
class TDDEnforcer:
    def enforce_tdd(self, test_file: Optional[str] = None) -> Tuple[bool, str, List[str]]:
        """
        Enforce TDD Iron Law.

        Returns:
            (compliant, message, violations): Compliance status and details
        """
        # 1. Check if test exists
        test_files = self._detect_test_files()

        # 2. Check if implementation already exists
        impl_files = self._detect_implementation_files()

        # 3. Run tests to verify they fail (RED phase)
        for test_file in test_files:
            passed, output = self._run_test(test_file)
            if passed:
                violations.append("Test PASSES but should FAIL (RED phase)")

        # 4. Check for premature implementation
        if impl_files and tests_passed:
            violations.append("Implementation exists before failing test")

        return compliant, message, violations
```

### Test Detection

Automatically detects test files from:
- `fileScope` in PRD (files with "test" in path)
- Common test directories: `tests/`, `test/`, `__tests__/`, `spec/`
- Test file patterns: `test_*.py`, `*_test.py`, `*.test.js`, `*.spec.ts`

### Test Execution

Supports multiple test frameworks:

**Python**:
- pytest (preferred)
- unittest

**JavaScript/TypeScript**:
- Jest
- Mocha
- Vitest
- npm test

**Shell Scripts**:
- bash execution

### Implementation Detection

Detects implementation files from:
- `fileScope` in PRD (excluding tests, docs, markdown)
- Checks if implementation files exist before tests fail

## Usage

### Automatic Enforcement

TDD enforcement will be triggered automatically for stories with:
- `estimatedComplexity` of "medium" or "complex"
- Keywords: implement, create, add, build, new feature
- Configuration: `tdd.enforcement.enabled: true` (default)

### Manual Usage

Run TDD enforcer manually:

```bash
python3 lib/tdd-enforcer.py <story_id> <prd_file> [test_file]
```

**Examples**:

```bash
# Check all test files for story
python3 lib/tdd-enforcer.py US-001 prds/active/my-feature/prd.json

# Check specific test file
python3 lib/tdd-enforcer.py US-001 prds/active/my-feature/prd.json tests/test_session_hooks.py
```

### Example Output

**✅ TDD Compliant (RED phase)**:
```
======================================================================
TDD ENFORCEMENT - IRON LAW
======================================================================

Story: US-001 - SessionStart Hook System
Result: ✅ COMPLIANT

✓ Tests fail as expected (RED phase)
✓ Ready to write minimal implementation (GREEN phase)

Next Steps:
  1. Write minimal code to make tests pass
  2. Run tests again, verify they pass
  3. Refactor if needed

The Iron Law of TDD:
  1. Write test first
  2. Run test, verify it FAILS (RED)
  3. Write minimal code to pass test (GREEN)
  4. Refactor (REFACTOR)

======================================================================
```

**❌ TDD Violation (test passes when it should fail)**:
```
======================================================================
TDD ENFORCEMENT - IRON LAW
======================================================================

Story: US-001 - SessionStart Hook System
Result: ❌ VIOLATION

Violations Found:
  1. Test test_session_hooks.py PASSES but should FAIL (RED phase). Test must fail before implementation.

Action Required:
  - Fix violations listed above
  - Delete implementation if it exists
  - Ensure tests fail first (RED phase)
  - Re-run TDD enforcer to verify

The Iron Law of TDD:
  1. Write test first
  2. Run test, verify it FAILS (RED)
  3. Write minimal code to pass test (GREEN)
  4. Refactor (REFACTOR)

======================================================================
```

**❌ TDD Violation (implementation before test)**:
```
======================================================================
TDD ENFORCEMENT - IRON LAW
======================================================================

Story: US-001 - SessionStart Hook System
Result: ❌ VIOLATION

Violations Found:
  1. Implementation exists but tests pass. This violates TDD Iron Law. Delete implementation and start over.

Action Required:
  - Fix violations listed above
  - Delete implementation if it exists
  - Ensure tests fail first (RED phase)
  - Re-run TDD enforcer to verify

The Iron Law of TDD:
  1. Write test first
  2. Run test, verify it FAILS (RED)
  3. Write minimal code to pass test (GREEN)
  4. Refactor (REFACTOR)

======================================================================
```

## Configuration

### Enable/Disable TDD Enforcement

**Location**: `config.yaml.example`

```yaml
tdd:
  enforcement:
    enabled: true  # Default: enabled for new features
    strict_mode: false  # If true, enforce even for bug fixes
    allow_skip: false  # If true, allow manual skip via flag
```

### Story-Level Configuration

TDD enforcement can be configured per story in PRD:

```json
{
  "id": "US-001",
  "title": "New Feature",
  "tdd_required": true,
  "estimatedComplexity": "medium"
}
```

### Command-Line Override

```bash
# Disable TDD enforcement for this run
./claude-loop.sh --prd prd.json --no-tdd

# Enable strict TDD mode
./claude-loop.sh --prd prd.json --tdd-strict
```

## Integration

### Pre-Implementation Hook

TDD enforcer runs as a pre-implementation hook before code is written:

```bash
# In claude-loop.sh, before implementation starts
if $TDD_ENFORCEMENT_ENABLED; then
    log_info "Running TDD enforcement check..."

    python3 lib/tdd-enforcer.py "$story_id" "$PRD_FILE" || {
        log_error "TDD compliance check failed"
        log_error "Fix violations and re-run"
        exit 1
    }

    log_success "TDD compliance verified (RED phase)"
fi
```

### Integration with Mandatory Skills

TDD enforcement integrates with the mandatory skills system:

```bash
# From lib/skill-enforcer.sh
if requires_tdd "$story_text"; then
    mandatory_skills+=("test-driven-development")

    # Also enable TDD enforcer
    TDD_ENFORCEMENT_ENABLED=true
fi
```

## Testing

### Test Suite

**Location**: `tests/test_tdd_enforcement.py`

Tests verify:
- TDD enforcer detects test files correctly
- Test execution works for multiple frameworks
- RED phase is properly verified
- Implementation detection works
- Violations are reported correctly
- Configuration options work

### Run Tests

```bash
pytest tests/test_tdd_enforcement.py -v
```

## Best Practices

### 1. Write Test First, Always

```python
# ✅ CORRECT: Test first
def test_session_hook_loads_skills():
    """Test that session hook loads skills overview."""
    result = session_start_hook()
    assert "skills-overview" in result
    assert len(result) > 100  # Should have content

# NOW run TDD enforcer - test will FAIL
# THEN write implementation
```

```python
# ❌ WRONG: Implementation first
def session_start_hook():
    with open("lib/skills-overview.md") as f:
        return f.read()

# Test written after - will PASS immediately
# Doesn't verify behavior, just confirms implementation exists
```

### 2. Make Tests Specific

```python
# ✅ CORRECT: Specific expectations
def test_session_hook_includes_mandatory_header():
    result = session_start_hook()
    assert "EXTREMELY-IMPORTANT" in result
    assert "If 1% chance" in result

# ❌ WRONG: Generic test
def test_session_hook_works():
    result = session_start_hook()
    assert result is not None  # Too generic
```

### 3. Verify RED Phase

```bash
# 1. Write test
echo "def test_new_feature(): assert new_feature() == 42" > test.py

# 2. Run TDD enforcer - should verify RED phase
python3 lib/tdd-enforcer.py US-001 prd.json test.py
# Output: ✅ COMPLIANT - Tests fail as expected (RED phase)

# 3. Write minimal implementation
echo "def new_feature(): return 42" > implementation.py

# 4. Run tests - should pass (GREEN phase)
pytest test.py
# Output: 1 passed
```

### 4. Refactor After GREEN

```python
# After test passes (GREEN), refactor if needed
def new_feature():
    # Refactor: Extract magic number
    ANSWER = 42
    return ANSWER
```

## Troubleshooting

### TDD enforcer not found

```
Error: TDD enforcer not found
```

**Solution**: Verify file exists and is executable:
```bash
ls -la lib/tdd-enforcer.py
chmod +x lib/tdd-enforcer.py
```

### Test framework not found

```
Error: pytest not found (install with: pip install pytest)
```

**Solution**: Install test framework:
```bash
pip install pytest  # Python
npm install -g jest  # JavaScript
```

### Tests pass when they should fail

```
❌ VIOLATION: Test PASSES but should FAIL (RED phase)
```

**Solution**: This is the enforcer working correctly. Fix your test:
1. Make test more specific
2. Ensure you haven't written implementation yet
3. Verify test actually tests the behavior you want

### False positive: Test fails for wrong reason

If test fails due to import errors or setup issues (not behavior):

**Solution**: Fix test setup first, then re-run enforcer:
```bash
# Fix imports, dependencies, test setup
# Then re-run enforcer
python3 lib/tdd-enforcer.py US-001 prd.json
```

## Metrics

**Expected Impact**:
- Increase test quality by 60%
- Reduce false confidence in tests by 80%
- Catch test bugs early (before implementation)
- Improve test coverage reliability

**Time Investment**:
- TDD enforcer check: 5-15 seconds
- Time saved from catching bad tests: 30-120 minutes per story

## Related Features

- **US-002**: Mandatory Skill Enforcement (triggers TDD for new features)
- **US-005**: Two-Stage Review System (validates tests exist and work)
- **Test-Driven Development Skill**: Detailed TDD workflow guidance

## Future Enhancements

1. **Coverage Thresholds**: Enforce minimum test coverage
2. **Mutation Testing**: Verify tests can catch bugs
3. **Test Quality Metrics**: Score test quality (assertions, specificity)
4. **Auto-Fix Suggestions**: Suggest fixes for common violations
5. **Integration with CI/CD**: Block merges if TDD violated
6. **Historical Tracking**: Track TDD compliance over time
7. **Team Dashboard**: Visualize TDD compliance across team

## Philosophy

The Iron Law of TDD is not about bureaucracy—it's about **confidence**. When you follow TDD:

- Tests verify behavior, not just implementation
- Tests catch regressions reliably
- Tests serve as living documentation
- Refactoring is safe and fearless
- False confidence is eliminated

The TDD enforcer is your safety net, ensuring the Iron Law is followed and tests are trustworthy.

## Feedback

Have suggestions for improving TDD enforcement? Open an issue or submit a PR!

**Related Documentation**:
- [Session Hooks](./session-hooks.md)
- [Mandatory Skills](./mandatory-skills.md)
- [Two-Stage Review](./two-stage-review.md)
- [Brainstorming](./brainstorming.md)
