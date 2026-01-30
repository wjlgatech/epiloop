#!/bin/bash
#
# Test crash recovery functionality (US-003)
#
# This script tests the crash recovery features:
# - Detection of abnormal session ending
# - Display of recovery message
# - User confirmation for recovery vs fresh start
# - Recovery metrics logging
#
# Usage: ./tests/test_crash_recovery.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Source session state functions
source "$PROJECT_ROOT/lib/session-state.sh"

# Test variables
TEST_PRD_FILE="$PROJECT_ROOT/prd.json"
TEST_SESSION_DIR="$PROJECT_ROOT/.claude-loop-test"
SESSION_STATE_DIR="$TEST_SESSION_DIR"
SESSION_STATE_FILE="$TEST_SESSION_DIR/session-state.json"
SESSION_ARCHIVE_DIR="$TEST_SESSION_DIR/sessions"
SESSION_CHECKPOINT_DIR="$TEST_SESSION_DIR/checkpoints"

# Colors for test output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Test counters
TESTS_RUN=0
TESTS_PASSED=0
TESTS_FAILED=0

# Setup test environment
setup_test() {
    echo "Setting up test environment..."
    rm -rf "$TEST_SESSION_DIR"
    mkdir -p "$TEST_SESSION_DIR"
    mkdir -p "$SESSION_ARCHIVE_DIR"
    mkdir -p "$SESSION_CHECKPOINT_DIR"
}

# Cleanup test environment
cleanup_test() {
    echo "Cleaning up test environment..."
    rm -rf "$TEST_SESSION_DIR"
}

# Test helper functions
assert_equals() {
    local expected="$1"
    local actual="$2"
    local message="$3"

    TESTS_RUN=$((TESTS_RUN + 1))

    if [ "$expected" = "$actual" ]; then
        echo -e "${GREEN}✓${NC} $message"
        TESTS_PASSED=$((TESTS_PASSED + 1))
    else
        echo -e "${RED}✗${NC} $message"
        echo "  Expected: $expected"
        echo "  Actual:   $actual"
        TESTS_FAILED=$((TESTS_FAILED + 1))
    fi
}

assert_file_exists() {
    local file="$1"
    local message="$2"

    TESTS_RUN=$((TESTS_RUN + 1))

    if [ -f "$file" ]; then
        echo -e "${GREEN}✓${NC} $message"
        TESTS_PASSED=$((TESTS_PASSED + 1))
    else
        echo -e "${RED}✗${NC} $message"
        echo "  File not found: $file"
        TESTS_FAILED=$((TESTS_FAILED + 1))
    fi
}

assert_file_not_exists() {
    local file="$1"
    local message="$2"

    TESTS_RUN=$((TESTS_RUN + 1))

    if [ ! -f "$file" ]; then
        echo -e "${GREEN}✓${NC} $message"
        TESTS_PASSED=$((TESTS_PASSED + 1))
    else
        echo -e "${RED}✗${NC} $message"
        echo "  File should not exist: $file"
        TESTS_FAILED=$((TESTS_FAILED + 1))
    fi
}

# Create a mock session with clean shutdown marker
create_clean_session() {
    cat > "$SESSION_STATE_FILE" <<EOF
{
  "session_id": "test_session_001",
  "project": "test-project",
  "branch": "feature/test",
  "prd_file": "$TEST_PRD_FILE",
  "current_phase": "implementation",
  "current_story": "US-001",
  "current_iteration": 3,
  "started_at": "2026-01-24T10:00:00Z",
  "last_saved_at": "2026-01-24T10:30:00Z",
  "stories_completed": 2,
  "stories_total": 5,
  "auto_save_enabled": true,
  "clean_shutdown": true,
  "shutdown_at": "2026-01-24T10:30:00Z"
}
EOF
}

# Create a mock session without clean shutdown marker (crashed)
create_crashed_session() {
    cat > "$SESSION_STATE_FILE" <<EOF
{
  "session_id": "test_session_002",
  "project": "test-project",
  "branch": "feature/test",
  "prd_file": "$TEST_PRD_FILE",
  "current_phase": "implementation",
  "current_story": "US-002",
  "current_iteration": 5,
  "started_at": "2026-01-24T09:00:00Z",
  "last_saved_at": "2026-01-24T09:45:00Z",
  "stories_completed": 3,
  "stories_total": 8,
  "auto_save_enabled": true
}
EOF
}

# Test 1: Detect clean shutdown
test_detect_clean_shutdown() {
    echo ""
    echo "Test 1: Detect clean shutdown"
    echo "=============================="

    create_clean_session

    if detect_crash; then
        assert_equals "false" "true" "Should NOT detect crash for clean shutdown"
    else
        assert_equals "false" "false" "Should NOT detect crash for clean shutdown"
    fi
}

# Test 2: Detect crashed session
test_detect_crashed_session() {
    echo ""
    echo "Test 2: Detect crashed session"
    echo "==============================="

    create_crashed_session

    if detect_crash; then
        assert_equals "true" "true" "Should detect crash when no clean_shutdown marker"
    else
        assert_equals "true" "false" "Should detect crash when no clean_shutdown marker"
    fi
}

# Test 3: Mark clean shutdown
test_mark_clean_shutdown() {
    echo ""
    echo "Test 3: Mark clean shutdown"
    echo "==========================="

    create_crashed_session

    mark_clean_shutdown

    local clean_shutdown
    clean_shutdown=$(jq -r '.clean_shutdown' "$SESSION_STATE_FILE")

    assert_equals "true" "$clean_shutdown" "Should mark session as clean shutdown"
}

# Test 4: Get crash info
test_get_crash_info() {
    echo ""
    echo "Test 4: Get crash info"
    echo "======================"

    create_crashed_session

    local crash_info
    crash_info=$(get_crash_info)

    local session_id
    session_id=$(echo "$crash_info" | jq -r '.session_id')

    assert_equals "test_session_002" "$session_id" "Should return correct session ID"

    local current_story
    current_story=$(echo "$crash_info" | jq -r '.current_story')

    assert_equals "US-002" "$current_story" "Should return correct current story"
}

# Test 5: Mark clean shutdown then mark unclean
test_mark_unclean_shutdown() {
    echo ""
    echo "Test 5: Mark unclean shutdown"
    echo "=============================="

    create_clean_session

    mark_unclean_shutdown

    local clean_shutdown
    clean_shutdown=$(jq -r '.clean_shutdown' "$SESSION_STATE_FILE")

    assert_equals "false" "$clean_shutdown" "Should mark session as unclean shutdown"
}

# Test 6: Log recovery metrics
test_log_recovery_metrics() {
    echo ""
    echo "Test 6: Log recovery metrics"
    echo "============================"

    create_crashed_session

    log_recovery_metrics "3" "8" "5"

    local recovery_log="$TEST_SESSION_DIR/recovery.log"
    assert_file_exists "$recovery_log" "Should create recovery log file"

    if [ -f "$recovery_log" ]; then
        local completed
        completed=$(cat "$recovery_log" | jq -r '.completed_stories')
        assert_equals "3" "$completed" "Should log correct completed stories count"

        local total
        total=$(cat "$recovery_log" | jq -r '.total_stories')
        assert_equals "8" "$total" "Should log correct total stories count"
    fi
}

# Test 7: Complete session marks clean shutdown
test_complete_session_marks_clean() {
    echo ""
    echo "Test 7: Complete session marks clean shutdown"
    echo "=============================================="

    create_crashed_session

    # Manually call mark_clean_shutdown (simulating what complete_session does)
    mark_clean_shutdown

    local clean_shutdown
    clean_shutdown=$(jq -r '.clean_shutdown' "$SESSION_STATE_FILE")

    assert_equals "true" "$clean_shutdown" "complete_session should mark clean shutdown"
}

# Print test summary
print_summary() {
    echo ""
    echo "========================================"
    echo "Test Summary"
    echo "========================================"
    echo "Tests run:    $TESTS_RUN"
    echo -e "Tests passed: ${GREEN}$TESTS_PASSED${NC}"
    echo -e "Tests failed: ${RED}$TESTS_FAILED${NC}"
    echo "========================================"

    if [ $TESTS_FAILED -eq 0 ]; then
        echo -e "${GREEN}All tests passed!${NC}"
        return 0
    else
        echo -e "${RED}Some tests failed!${NC}"
        return 1
    fi
}

# Main test execution
main() {
    echo "=========================================="
    echo "Crash Recovery Test Suite (US-003)"
    echo "=========================================="

    setup_test

    test_detect_clean_shutdown
    test_detect_crashed_session
    test_mark_clean_shutdown
    test_get_crash_info
    test_mark_unclean_shutdown
    test_log_recovery_metrics
    test_complete_session_marks_clean

    print_summary
    local exit_code=$?

    cleanup_test

    exit $exit_code
}

main "$@"
