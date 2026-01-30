#!/usr/bin/env bash
#
# test_session_hooks.sh - Tests for lib/session-hooks.sh (US-001)
#
# Tests cover:
# - Session hook execution
# - Skills overview loading
# - Agent registry loading
# - Experience store status loading
# - Context generation
# - Integration with claude-loop.sh
#

set -euo pipefail

# Test framework colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Test counters
TESTS_RUN=0
TESTS_PASSED=0
TESTS_FAILED=0

# Script paths
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CLAUDE_LOOP_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
SESSION_HOOKS="${CLAUDE_LOOP_ROOT}/lib/session-hooks.sh"
SKILLS_OVERVIEW="${CLAUDE_LOOP_ROOT}/lib/skills-overview.md"

# Helper: Assert equality
assert_equals() {
    local expected="$1"
    local actual="$2"
    local message="${3:-Assertion failed}"

    ((TESTS_RUN++))

    if [[ "$expected" == "$actual" ]]; then
        echo -e "${GREEN}✓${NC} $message"
        ((TESTS_PASSED++))
        return 0
    else
        echo -e "${RED}✗${NC} $message"
        echo "  Expected: $expected"
        echo "  Actual:   $actual"
        ((TESTS_FAILED++))
        return 1
    fi
}

# Helper: Assert contains
assert_contains() {
    local haystack="$1"
    local needle="$2"
    local message="${3:-String should contain substring}"

    ((TESTS_RUN++))

    if [[ "$haystack" == *"$needle"* ]]; then
        echo -e "${GREEN}✓${NC} $message"
        ((TESTS_PASSED++))
        return 0
    else
        echo -e "${RED}✗${NC} $message"
        echo "  String should contain: $needle"
        echo "  But got: ${haystack:0:100}..."
        ((TESTS_FAILED++))
        return 1
    fi
}

# Helper: Assert file exists
assert_file_exists() {
    local file_path="$1"
    local message="${2:-File should exist: $file_path}"

    ((TESTS_RUN++))

    if [[ -f "$file_path" ]]; then
        echo -e "${GREEN}✓${NC} $message"
        ((TESTS_PASSED++))
        return 0
    else
        echo -e "${RED}✗${NC} $message"
        echo "  File not found: $file_path"
        ((TESTS_FAILED++))
        return 1
    fi
}

# Helper: Assert not empty
assert_not_empty() {
    local value="$1"
    local message="${2:-Value should not be empty}"

    ((TESTS_RUN++))

    if [[ -n "$value" ]]; then
        echo -e "${GREEN}✓${NC} $message"
        ((TESTS_PASSED++))
        return 0
    else
        echo -e "${RED}✗${NC} $message"
        echo "  Value was empty"
        ((TESTS_FAILED++))
        return 1
    fi
}

# ============================================================================
# Tests
# ============================================================================

echo "═══════════════════════════════════════════════════════════════"
echo "Session Hooks Tests (US-001)"
echo "═══════════════════════════════════════════════════════════════"
echo ""

# Test 1: Session hooks script exists
echo "Test 1: Session hooks script exists"
assert_file_exists "$SESSION_HOOKS" "lib/session-hooks.sh should exist"
echo ""

# Test 2: Skills overview exists
echo "Test 2: Skills overview exists"
assert_file_exists "$SKILLS_OVERVIEW" "lib/skills-overview.md should exist"
echo ""

# Test 3: Session hooks script is executable
echo "Test 3: Session hooks script is executable"
if [[ -x "$SESSION_HOOKS" ]]; then
    echo -e "${GREEN}✓${NC} lib/session-hooks.sh is executable"
    ((TESTS_RUN++))
    ((TESTS_PASSED++))
else
    echo -e "${RED}✗${NC} lib/session-hooks.sh is not executable"
    ((TESTS_RUN++))
    ((TESTS_FAILED++))
fi
echo ""

# Test 4: Session hook generates output
echo "Test 4: Session hook generates output"
output=$("$SESSION_HOOKS" 2>/dev/null || echo "")
assert_not_empty "$output" "Session hook should generate output"
echo ""

# Test 5: Output contains SESSION-CONTEXT tags
echo "Test 5: Output contains SESSION-CONTEXT tags"
output=$("$SESSION_HOOKS" 2>/dev/null || echo "")
assert_contains "$output" "<SESSION-CONTEXT>" "Output should contain opening tag"
assert_contains "$output" "</SESSION-CONTEXT>" "Output should contain closing tag"
echo ""

# Test 6: Output contains skills overview section
echo "Test 6: Output contains skills overview section"
output=$("$SESSION_HOOKS" 2>/dev/null || echo "")
assert_contains "$output" "Using claude-loop Skills" "Output should contain skills overview header"
echo ""

# Test 7: Output contains agent registry section
echo "Test 7: Output contains agent registry section"
output=$("$SESSION_HOOKS" 2>/dev/null || echo "")
assert_contains "$output" "Available Agents" "Output should contain agent registry section"
echo ""

# Test 8: Output contains experience store section
echo "Test 8: Output contains experience store section"
output=$("$SESSION_HOOKS" 2>/dev/null || echo "")
assert_contains "$output" "Experience Store Status" "Output should contain experience store section"
echo ""

# Test 9: Output contains configuration section
echo "Test 9: Output contains configuration section"
output=$("$SESSION_HOOKS" 2>/dev/null || echo "")
assert_contains "$output" "Configuration" "Output should contain configuration section"
echo ""

# Test 10: Skills overview mentions EXTREMELY-IMPORTANT
echo "Test 10: Skills overview enforces mandatory usage"
if [[ -f "$SKILLS_OVERVIEW" ]]; then
    content=$(cat "$SKILLS_OVERVIEW")
    assert_contains "$content" "EXTREMELY-IMPORTANT" "Skills overview should emphasize mandatory usage"
else
    echo -e "${YELLOW}⊘${NC} Skipped (skills overview not found)"
    ((TESTS_RUN++))
fi
echo ""

# Test 11: Skills overview mentions 1% rule
echo "Test 11: Skills overview mentions 1% rule"
if [[ -f "$SKILLS_OVERVIEW" ]]; then
    content=$(cat "$SKILLS_OVERVIEW")
    assert_contains "$content" "1%" "Skills overview should mention 1% rule"
else
    echo -e "${YELLOW}⊘${NC} Skipped (skills overview not found)"
    ((TESTS_RUN++))
fi
echo ""

# Test 12: Integration with claude-loop.sh
echo "Test 12: Integration with claude-loop.sh"
if grep -q "session-hooks.sh" "${CLAUDE_LOOP_ROOT}/claude-loop.sh"; then
    echo -e "${GREEN}✓${NC} claude-loop.sh integrates session hooks"
    ((TESTS_RUN++))
    ((TESTS_PASSED++))
else
    echo -e "${RED}✗${NC} claude-loop.sh does not integrate session hooks"
    ((TESTS_RUN++))
    ((TESTS_FAILED++))
fi
echo ""

# ============================================================================
# Summary
# ============================================================================

echo "═══════════════════════════════════════════════════════════════"
echo "Test Summary"
echo "═══════════════════════════════════════════════════════════════"
echo ""
echo "Tests run:    $TESTS_RUN"
echo -e "${GREEN}Tests passed: $TESTS_PASSED${NC}"

if [[ $TESTS_FAILED -gt 0 ]]; then
    echo -e "${RED}Tests failed: $TESTS_FAILED${NC}"
    echo ""
    exit 1
else
    echo -e "${GREEN}All tests passed!${NC}"
    echo ""
    exit 0
fi
