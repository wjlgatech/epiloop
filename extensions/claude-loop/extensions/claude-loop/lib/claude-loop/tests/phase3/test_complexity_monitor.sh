#!/bin/bash
#
# test_complexity_monitor.sh - Tests for complexity monitor (US-001)
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# Source the complexity monitor
source "$PROJECT_ROOT/lib/complexity-monitor.sh"

# Test counters
TESTS_RUN=0
TESTS_PASSED=0
TESTS_FAILED=0

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Test helper functions
assert_equals() {
    local expected="$1"
    local actual="$2"
    local test_name="$3"

    TESTS_RUN=$((TESTS_RUN + 1))

    if [ "$expected" = "$actual" ]; then
        echo -e "${GREEN}✓${NC} $test_name"
        TESTS_PASSED=$((TESTS_PASSED + 1))
    else
        echo -e "${RED}✗${NC} $test_name"
        echo "  Expected: $expected"
        echo "  Actual:   $actual"
        TESTS_FAILED=$((TESTS_FAILED + 1))
    fi
}

assert_gt() {
    local value="$1"
    local threshold="$2"
    local test_name="$3"

    TESTS_RUN=$((TESTS_RUN + 1))

    local result=$(echo "$value > $threshold" | bc)
    if [ "$result" -eq 1 ]; then
        echo -e "${GREEN}✓${NC} $test_name"
        TESTS_PASSED=$((TESTS_PASSED + 1))
    else
        echo -e "${RED}✗${NC} $test_name"
        echo "  Expected: $value > $threshold"
        TESTS_FAILED=$((TESTS_FAILED + 1))
    fi
}

assert_lt() {
    local value="$1"
    local threshold="$2"
    local test_name="$3"

    TESTS_RUN=$((TESTS_RUN + 1))

    local result=$(echo "$value < $threshold" | bc)
    if [ "$result" -eq 1 ]; then
        echo -e "${GREEN}✓${NC} $test_name"
        TESTS_PASSED=$((TESTS_PASSED + 1))
    else
        echo -e "${RED}✗${NC} $test_name"
        echo "  Expected: $value < $threshold"
        TESTS_FAILED=$((TESTS_FAILED + 1))
    fi
}

# Setup test environment
setup_test() {
    export CLAUDE_LOOP_DIR="/tmp/claude-loop-test-$$"
    mkdir -p "$CLAUDE_LOOP_DIR"
    init_complexity_monitor "TEST-001" 600000 "lib/,src/,tests/" 5
}

# Cleanup test environment
cleanup_test() {
    rm -rf "$CLAUDE_LOOP_DIR"
}

# ============================================================================
# Test Cases
# ============================================================================

echo "Running Complexity Monitor Tests"
echo "=================================="
echo ""

# Test 1: Initialization
echo "Test Suite: Initialization"
setup_test
assert_equals "TEST-001" "$COMPLEXITY_STORY_ID" "Story ID initialized"
assert_equals "600000" "$COMPLEXITY_ESTIMATED_DURATION_MS" "Estimated duration initialized"
assert_equals "5" "$COMPLEXITY_AC_COUNT" "Acceptance criteria count initialized"
cleanup_test
echo ""

# Test 2: Time tracking
echo "Test Suite: Time Tracking"
setup_test
start_time=$(get_timestamp_ms)
sleep 0.1
end_time=$(get_timestamp_ms)
track_acceptance_criterion "AC-1" "$start_time" "$end_time"
assert_equals "1" "$COMPLEXITY_AC_COMPLETED" "AC completion tracked"
cleanup_test
echo ""

# Test 3: File scope tracking
echo "Test Suite: File Scope Tracking"
setup_test
track_file_modification "lib/test.sh"
assert_equals "0" "$COMPLEXITY_FILES_OUTSIDE_SCOPE" "File inside scope not flagged"
track_file_modification "external/file.ts"
assert_equals "1" "$COMPLEXITY_FILES_OUTSIDE_SCOPE" "File outside scope flagged"
cleanup_test
echo ""

# Test 4: Error tracking
echo "Test Suite: Error Tracking"
setup_test
track_error "Error 1"
track_error "Error 2"
track_error "Error 3"
assert_equals "3" "$COMPLEXITY_ERROR_COUNT" "Error count tracked"
track_error "Error 4"
assert_equals "4" "$COMPLEXITY_ERROR_COUNT" "Error count exceeds threshold"
cleanup_test
echo ""

# Test 5: Clarification detection
echo "Test Suite: Clarification Detection"
setup_test
track_agent_output "I'm not sure which approach to use"
assert_equals "1" "$COMPLEXITY_CLARIFICATION_COUNT" "Clarification detected"
track_agent_output "This is unclear to me"
assert_equals "2" "$COMPLEXITY_CLARIFICATION_COUNT" "Multiple clarifications detected"
track_agent_output "Everything is fine, proceeding"
assert_equals "2" "$COMPLEXITY_CLARIFICATION_COUNT" "Non-clarification not counted"
cleanup_test
echo ""

# Test 6: Complexity score calculation (low complexity)
echo "Test Suite: Complexity Score - Low"
setup_test
# Simulate on-time completion
start_time=$(get_timestamp_ms)
sleep 0.05
end_time=$(get_timestamp_ms)
track_acceptance_criterion "AC-1" "$start_time" "$end_time"
score=$(get_complexity_score)
assert_lt "$score" "2.0" "Low complexity score for on-time execution"
cleanup_test
echo ""

# Test 7: Complexity score calculation (high complexity)
echo "Test Suite: Complexity Score - High"
setup_test
# Simulate: time overrun, file expansion, errors, clarifications
# Time: simulate 3x overrun
COMPLEXITY_AC_COMPLETED=1
COMPLEXITY_AC_TOTAL_TIME_MS=360000  # 3x the estimated 120000 per AC
# Files: 5 outside scope of 3 initial
COMPLEXITY_FILES_OUTSIDE_SCOPE=5
# Errors: 7 (above threshold of 3)
COMPLEXITY_ERROR_COUNT=7
# Clarifications: 3
COMPLEXITY_CLARIFICATION_COUNT=3

score=$(get_complexity_score)
assert_gt "$score" "5.0" "High complexity score for problematic execution"
cleanup_test
echo ""

# Test 8: Split trigger (should not trigger)
echo "Test Suite: Split Trigger - Low Complexity"
setup_test
score=$(get_complexity_score)
if should_trigger_split 7; then
    echo -e "${RED}✗${NC} Split should not trigger for low complexity"
    TESTS_FAILED=$((TESTS_FAILED + 1))
else
    echo -e "${GREEN}✓${NC} Split correctly not triggered"
    TESTS_PASSED=$((TESTS_PASSED + 1))
fi
TESTS_RUN=$((TESTS_RUN + 1))
cleanup_test
echo ""

# Test 9: Split trigger (should trigger)
echo "Test Suite: Split Trigger - High Complexity"
setup_test
# Simulate high complexity
COMPLEXITY_AC_COMPLETED=1
COMPLEXITY_AC_TOTAL_TIME_MS=600000  # 5x overrun
COMPLEXITY_FILES_OUTSIDE_SCOPE=10
COMPLEXITY_ERROR_COUNT=10
COMPLEXITY_CLARIFICATION_COUNT=5
if should_trigger_split 7; then
    echo -e "${GREEN}✓${NC} Split correctly triggered for high complexity"
    TESTS_PASSED=$((TESTS_PASSED + 1))
else
    echo -e "${RED}✗${NC} Split should trigger for high complexity"
    TESTS_FAILED=$((TESTS_FAILED + 1))
fi
TESTS_RUN=$((TESTS_RUN + 1))
cleanup_test
echo ""

# Test 10: JSON report generation
echo "Test Suite: JSON Report"
setup_test
COMPLEXITY_ERROR_COUNT=2
report=$(get_complexity_report_json)
if echo "$report" | jq -e '.story_id == "TEST-001"' > /dev/null 2>&1; then
    echo -e "${GREEN}✓${NC} JSON report contains story_id"
    TESTS_PASSED=$((TESTS_PASSED + 1))
else
    echo -e "${RED}✗${NC} JSON report missing story_id"
    TESTS_FAILED=$((TESTS_FAILED + 1))
fi
TESTS_RUN=$((TESTS_RUN + 1))

if echo "$report" | jq -e '.complexity_score' > /dev/null 2>&1; then
    echo -e "${GREEN}✓${NC} JSON report contains complexity_score"
    TESTS_PASSED=$((TESTS_PASSED + 1))
else
    echo -e "${RED}✗${NC} JSON report missing complexity_score"
    TESTS_FAILED=$((TESTS_FAILED + 1))
fi
TESTS_RUN=$((TESTS_RUN + 1))
cleanup_test
echo ""

# ============================================================================
# Summary
# ============================================================================

echo "=================================="
echo "Test Summary"
echo "=================================="
echo "Tests run:    $TESTS_RUN"
echo -e "Tests passed: ${GREEN}$TESTS_PASSED${NC}"
if [ "$TESTS_FAILED" -gt 0 ]; then
    echo -e "Tests failed: ${RED}$TESTS_FAILED${NC}"
else
    echo -e "Tests failed: ${GREEN}$TESTS_FAILED${NC}"
fi
echo ""

if [ "$TESTS_FAILED" -eq 0 ]; then
    echo -e "${GREEN}All tests passed!${NC}"
    exit 0
else
    echo -e "${RED}Some tests failed.${NC}"
    exit 1
fi
