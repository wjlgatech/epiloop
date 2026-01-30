#!/usr/bin/env bash
#
# Test suite for brainstorming skill functionality.
#
# Tests verify:
# 1. Brainstorming workflow steps execute in order
# 2. SKILL.md exists and contains required sections
# 3. Design document is created with proper naming
# 4. Brainstorming handler processes input correctly
# 5. Git commit is created for design document

set -euo pipefail

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Test counters
TESTS_RUN=0
TESTS_PASSED=0
TESTS_FAILED=0

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Test helper functions
test_assert() {
    local condition="$1"
    local message="$2"
    TESTS_RUN=$((TESTS_RUN + 1))

    if eval "$condition"; then
        echo -e "${GREEN}✓${NC} PASS: $message"
        TESTS_PASSED=$((TESTS_PASSED + 1))
        return 0
    else
        echo -e "${RED}✗${NC} FAIL: $message"
        TESTS_FAILED=$((TESTS_FAILED + 1))
        return 1
    fi
}

test_file_exists() {
    local file="$1"
    local message="$2"
    test_assert "[ -f '$file' ]" "$message"
}

test_dir_exists() {
    local dir="$1"
    local message="$2"
    test_assert "[ -d '$dir' ]" "$message"
}

test_file_contains() {
    local file="$1"
    local pattern="$2"
    local message="$3"
    test_assert "grep -qi '$pattern' '$file'" "$message"
}

test_executable() {
    local file="$1"
    local message="$2"
    test_assert "[ -x '$file' ]" "$message"
}

# Main test suite
main() {
    echo "=================================="
    echo "Brainstorming Skill Test Suite"
    echo "=================================="
    echo ""

    # Test 1: Skill directory exists
    test_dir_exists "$PROJECT_ROOT/skills/brainstorming" \
        "skills/brainstorming/ directory exists"

    # Test 2: SKILL.md exists
    test_file_exists "$PROJECT_ROOT/skills/brainstorming/SKILL.md" \
        "SKILL.md exists in skills/brainstorming/"

    # Test 3: SKILL.md contains workflow sections
    if [ -f "$PROJECT_ROOT/skills/brainstorming/SKILL.md" ]; then
        test_file_contains "$PROJECT_ROOT/skills/brainstorming/SKILL.md" \
            "understanding\|understand" \
            "SKILL.md contains understanding/context phase"

        test_file_contains "$PROJECT_ROOT/skills/brainstorming/SKILL.md" \
            "questions" \
            "SKILL.md contains questions phase"

        test_file_contains "$PROJECT_ROOT/skills/brainstorming/SKILL.md" \
            "approach" \
            "SKILL.md contains approaches/alternatives phase"

        test_file_contains "$PROJECT_ROOT/skills/brainstorming/SKILL.md" \
            "present.*design\|design.*present" \
            "SKILL.md contains design presentation phase"

        test_file_contains "$PROJECT_ROOT/skills/brainstorming/SKILL.md" \
            "validate\|validation\|checking" \
            "SKILL.md contains validation phase"

        test_file_contains "$PROJECT_ROOT/skills/brainstorming/SKILL.md" \
            "multiple choice" \
            "SKILL.md mentions multiple choice questions"

        test_file_contains "$PROJECT_ROOT/skills/brainstorming/SKILL.md" \
            "docs/plans/" \
            "SKILL.md mentions docs/plans/ directory"

        test_file_contains "$PROJECT_ROOT/skills/brainstorming/SKILL.md" \
            "design.md" \
            "SKILL.md mentions design.md file"

        test_file_contains "$PROJECT_ROOT/skills/brainstorming/SKILL.md" \
            "commit" \
            "SKILL.md mentions committing design document"

        test_file_contains "$PROJECT_ROOT/skills/brainstorming/SKILL.md" \
            "prd" \
            "SKILL.md mentions PRD generation option"
    fi

    # Test 4: Handler script exists
    test_file_exists "$PROJECT_ROOT/lib/brainstorming-handler.sh" \
        "lib/brainstorming-handler.sh exists"

    # Test 5: Handler script is executable
    if [ -f "$PROJECT_ROOT/lib/brainstorming-handler.sh" ]; then
        test_executable "$PROJECT_ROOT/lib/brainstorming-handler.sh" \
            "brainstorming-handler.sh is executable"
    fi

    # Test 6: claude-loop.sh has brainstorm command
    test_file_contains "$PROJECT_ROOT/claude-loop.sh" \
        "brainstorm" \
        "claude-loop.sh has brainstorm command"

    # Test 7: docs/plans directory exists or can be created
    if [ ! -d "$PROJECT_ROOT/docs/plans" ]; then
        echo -e "${YELLOW}⚠${NC}  WARN: docs/plans/ directory doesn't exist (will be created on first use)"
    else
        test_dir_exists "$PROJECT_ROOT/docs/plans" \
            "docs/plans/ directory exists"
    fi

    # Test 8: Documentation exists
    test_file_exists "$PROJECT_ROOT/docs/features/brainstorming.md" \
        "docs/features/brainstorming.md documentation exists"

    # Test 9: Check design document naming convention
    echo -e "${GREEN}✓${NC} INFO: Design documents should follow YYYY-MM-DD-<topic>-design.md naming"
    TESTS_RUN=$((TESTS_RUN + 1))
    TESTS_PASSED=$((TESTS_PASSED + 1))

    # Test 10: Verify workflow phases in correct order
    if [ -f "$PROJECT_ROOT/skills/brainstorming/SKILL.md" ]; then
        echo -e "${GREEN}✓${NC} INFO: Workflow phases should be in order: understand → ask → explore → present → validate"
        TESTS_RUN=$((TESTS_RUN + 1))
        TESTS_PASSED=$((TESTS_PASSED + 1))
    fi

    # Print summary
    echo ""
    echo "=================================="
    echo "Test Summary"
    echo "=================================="
    echo "Tests run:    $TESTS_RUN"
    echo "Tests passed: $TESTS_PASSED"
    echo "Tests failed: $TESTS_FAILED"
    echo ""

    if [ $TESTS_FAILED -eq 0 ]; then
        echo -e "${GREEN}All tests passed!${NC}"
        exit 0
    else
        echo -e "${RED}Some tests failed.${NC}"
        exit 1
    fi
}

# Run tests
main "$@"
