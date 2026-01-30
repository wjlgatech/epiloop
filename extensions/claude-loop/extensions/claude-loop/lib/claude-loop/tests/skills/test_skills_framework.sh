#!/bin/bash
#
# Integration tests for skills framework (US-201)
#

set -euo pipefail

# Test configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
SKILLS_FRAMEWORK="${PROJECT_ROOT}/lib/skills-framework.sh"
TEST_SKILLS_DIR="${PROJECT_ROOT}/skills"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Test counters
TESTS_RUN=0
TESTS_PASSED=0
TESTS_FAILED=0

# Helper functions
log_test() {
    echo -e "${YELLOW}[TEST]${NC} $1"
}

log_pass() {
    echo -e "${GREEN}[PASS]${NC} $1"
    TESTS_PASSED=$((TESTS_PASSED + 1))
}

log_fail() {
    echo -e "${RED}[FAIL]${NC} $1"
    TESTS_FAILED=$((TESTS_FAILED + 1))
}

run_test() {
    local test_name="$1"
    TESTS_RUN=$((TESTS_RUN + 1))
    log_test "$test_name"
}

# Source skills framework
if [ ! -f "$SKILLS_FRAMEWORK" ]; then
    echo "Error: Skills framework not found: $SKILLS_FRAMEWORK"
    exit 1
fi

source "$SKILLS_FRAMEWORK"

# ============================================================================
# Test Suite
# ============================================================================

# Test 1: Framework initialization
run_test "Framework initialization"
if init_skills_framework "$TEST_SKILLS_DIR" > /dev/null 2>&1; then
    log_pass "Framework initialized successfully"
else
    log_fail "Framework initialization failed"
fi

# Test 2: Metadata loading
run_test "Metadata loading"
if load_skills_metadata "$TEST_SKILLS_DIR" > /dev/null 2>&1; then
    if [ -f ".claude-loop/skills-cache/metadata.json" ]; then
        log_pass "Metadata loaded and cached"
    else
        log_fail "Metadata cache file not created"
    fi
else
    log_fail "Metadata loading failed"
fi

# Test 3: Get skills metadata
run_test "Get skills metadata"
metadata=$(get_skills_metadata)
if [ -n "$metadata" ]; then
    skill_count=$(echo "$metadata" | jq -r 'length')
    if [ "$skill_count" -gt 0 ]; then
        log_pass "Found $skill_count skills"
    else
        log_fail "No skills found"
    fi
else
    log_fail "Failed to get metadata"
fi

# Test 4: Skill exists check
run_test "Skill exists check"
if skill_exists "hello-world"; then
    log_pass "hello-world skill exists"
else
    log_fail "hello-world skill not found"
fi

# Test 5: Get specific skill metadata
run_test "Get specific skill metadata"
skill_meta=$(get_skill_metadata "hello-world")
if [ -n "$skill_meta" ]; then
    skill_name=$(echo "$skill_meta" | jq -r '.name')
    if [ "$skill_name" == "hello-world" ]; then
        log_pass "Retrieved hello-world metadata"
    else
        log_fail "Wrong skill metadata returned: $skill_name"
    fi
else
    log_fail "Failed to get hello-world metadata"
fi

# Test 6: Load skill instructions
run_test "Load skill instructions"
instructions=$(load_skill_instructions "hello-world")
if [ -n "$instructions" ]; then
    if echo "$instructions" | grep -q "Example Skill"; then
        log_pass "Instructions loaded successfully"
    else
        log_fail "Instructions content unexpected"
    fi
else
    log_fail "Failed to load instructions"
fi

# Test 7: Execute skill script
run_test "Execute skill script (no args)"
output=$(execute_skill_script "hello-world" 2>&1)
if [ $? -eq 0 ]; then
    if echo "$output" | grep -q "Hello, World!"; then
        log_pass "Script executed successfully"
    else
        log_fail "Script output unexpected: $output"
    fi
else
    log_fail "Script execution failed"
fi

# Test 8: Execute skill script with arguments
run_test "Execute skill script (with args)"
output=$(execute_skill_script "hello-world" "Alice" 2>&1)
if [ $? -eq 0 ]; then
    if echo "$output" | grep -q "Hello, Alice!"; then
        log_pass "Script executed with arguments"
    else
        log_fail "Script output unexpected: $output"
    fi
else
    log_fail "Script execution with args failed"
fi

# Test 9: List skills (text format)
run_test "List skills (text format)"
output=$(list_skills "text" 2>&1)
if [ $? -eq 0 ]; then
    if echo "$output" | grep -q "hello-world"; then
        log_pass "Skills listed in text format"
    else
        log_fail "hello-world not found in skills list"
    fi
else
    log_fail "Failed to list skills"
fi

# Test 10: List skills (JSON format)
run_test "List skills (JSON format)"
output=$(list_skills "json" 2>&1)
if [ $? -eq 0 ]; then
    if echo "$output" | jq -e '.[] | select(.name == "hello-world")' > /dev/null 2>&1; then
        log_pass "Skills listed in JSON format"
    else
        log_fail "hello-world not found in JSON list"
    fi
else
    log_fail "Failed to list skills as JSON"
fi

# Test 11: Search skills
run_test "Search skills by keyword"
output=$(search_skills "example" 2>&1)
if [ $? -eq 0 ]; then
    if echo "$output" | grep -q "hello-world"; then
        log_pass "Skill search successful"
    else
        log_fail "Expected skill not found in search results"
    fi
else
    log_fail "Skill search failed"
fi

# Test 12: Validate skill
run_test "Validate skill structure"
if validate_skill "hello-world" 2>&1; then
    log_pass "Skill validation passed"
else
    log_fail "Skill validation failed"
fi

# Test 13: Non-existent skill
run_test "Handle non-existent skill"
if ! skill_exists "non-existent-skill"; then
    log_pass "Correctly detected non-existent skill"
else
    log_fail "False positive for non-existent skill"
fi

# Test 14: Execute non-existent skill
run_test "Execute non-existent skill (should fail)"
if ! execute_skill "non-existent-skill" > /dev/null 2>&1; then
    log_pass "Correctly failed on non-existent skill"
else
    log_fail "Should have failed on non-existent skill"
fi

# Test 15: Clear cache
run_test "Clear skills cache"
clear_skills_cache > /dev/null 2>&1
if [ ! -f ".claude-loop/skills-cache/metadata.json" ]; then
    log_pass "Cache cleared successfully"
else
    log_fail "Cache not cleared"
fi

# Test 16: Reload after cache clear
run_test "Reload metadata after cache clear"
if load_skills_metadata "$TEST_SKILLS_DIR" > /dev/null 2>&1; then
    if [ -f ".claude-loop/skills-cache/metadata.json" ]; then
        log_pass "Metadata reloaded after cache clear"
    else
        log_fail "Cache not recreated after reload"
    fi
else
    log_fail "Failed to reload metadata"
fi

# ============================================================================
# Test Summary
# ============================================================================

echo ""
echo "======================================================================"
echo "Test Results"
echo "======================================================================"
echo "Tests run:    $TESTS_RUN"
echo -e "Tests passed: ${GREEN}$TESTS_PASSED${NC}"
echo -e "Tests failed: ${RED}$TESTS_FAILED${NC}"
echo "======================================================================"

if [ $TESTS_FAILED -eq 0 ]; then
    echo -e "${GREEN}All tests passed!${NC}"
    exit 0
else
    echo -e "${RED}Some tests failed!${NC}"
    exit 1
fi
