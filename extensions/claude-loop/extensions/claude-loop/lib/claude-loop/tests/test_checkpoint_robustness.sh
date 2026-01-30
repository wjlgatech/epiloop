#!/bin/bash
#
# test_checkpoint_robustness.sh - Test checkpoint functionality
#
# Tests for US-001: Increase checkpoint frequency
# - Save checkpoint after every iteration
# - Atomic writes (temp file + rename)
# - Keep last 3 checkpoints
# - Recovery from checkpoint

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
TEST_DIR="${PROJECT_ROOT}/.claude-loop/test-checkpoints"

# Load session-state functions
source "${PROJECT_ROOT}/lib/session-state.sh"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Test counters
TESTS_RUN=0
TESTS_PASSED=0
TESTS_FAILED=0

# Test results
declare -a FAILED_TESTS

# Setup test environment
setup() {
    echo "Setting up test environment..."
    rm -rf "$TEST_DIR"
    mkdir -p "$TEST_DIR"

    # Override session directories for testing
    export SESSION_STATE_DIR="$TEST_DIR"
    export SESSION_STATE_FILE="${TEST_DIR}/session-state.json"
    export SESSION_CHECKPOINT_DIR="${TEST_DIR}/checkpoints"

    # Create minimal test PRD
    cat > "${TEST_DIR}/test-prd.json" << 'EOF'
{
  "project": "test-checkpoint",
  "branchName": "feature/test",
  "userStories": [
    {
      "id": "TEST-001",
      "title": "Test Story 1",
      "passes": false
    },
    {
      "id": "TEST-002",
      "title": "Test Story 2",
      "passes": false
    }
  ]
}
EOF
}

# Teardown test environment
teardown() {
    echo "Cleaning up test environment..."
    rm -rf "$TEST_DIR"
}

# Test helper
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
        FAILED_TESTS+=("$message")
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
        FAILED_TESTS+=("$message")
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
        FAILED_TESTS+=("$message")
    fi
}

# Test 1: Initialize session creates checkpoint directory
test_init_creates_checkpoint_dir() {
    echo ""
    echo "Test 1: Initialize session creates checkpoint directory"

    init_session "${TEST_DIR}/test-prd.json" >/dev/null 2>&1

    assert_file_exists "$SESSION_CHECKPOINT_DIR" "Checkpoint directory created"
}

# Test 2: Save checkpoint creates checkpoint file
test_save_checkpoint_creates_file() {
    echo ""
    echo "Test 2: Save checkpoint creates checkpoint file"

    local prd_state='{"test": "data"}'
    save_checkpoint "TEST-001" 1 "$prd_state" >/dev/null 2>&1

    local session_id
    session_id=$(jq -r '.session_id' "$SESSION_STATE_FILE" 2>/dev/null)
    local checkpoint_dir="${SESSION_CHECKPOINT_DIR}/${session_id}"

    local checkpoint_count
    checkpoint_count=$(ls -1 "$checkpoint_dir"/checkpoint_*.json 2>/dev/null | wc -l | tr -d ' ')

    assert_equals "1" "$checkpoint_count" "Checkpoint file created"
}

# Test 3: Checkpoint contains required fields
test_checkpoint_contains_required_fields() {
    echo ""
    echo "Test 3: Checkpoint contains required fields"

    local prd_state='{"userStories": []}'
    save_checkpoint "TEST-001" 2 "$prd_state" >/dev/null 2>&1

    local latest_checkpoint
    latest_checkpoint=$(get_latest_checkpoint)

    local has_session_id
    has_session_id=$(jq 'has("session_id")' "$latest_checkpoint" 2>/dev/null)
    assert_equals "true" "$has_session_id" "Checkpoint has session_id"

    local has_story_id
    has_story_id=$(jq 'has("story_id")' "$latest_checkpoint" 2>/dev/null)
    assert_equals "true" "$has_story_id" "Checkpoint has story_id"

    local has_iteration
    has_iteration=$(jq 'has("iteration")' "$latest_checkpoint" 2>/dev/null)
    assert_equals "true" "$has_iteration" "Checkpoint has iteration"

    local has_timestamp
    has_timestamp=$(jq 'has("timestamp")' "$latest_checkpoint" 2>/dev/null)
    assert_equals "true" "$has_timestamp" "Checkpoint has timestamp"

    local has_prd_state
    has_prd_state=$(jq 'has("prd_state")' "$latest_checkpoint" 2>/dev/null)
    assert_equals "true" "$has_prd_state" "Checkpoint has prd_state"
}

# Test 4: Keep only last 3 checkpoints
test_keep_last_three_checkpoints() {
    echo ""
    echo "Test 4: Keep only last 3 checkpoints"

    # Create 5 checkpoints
    for i in {1..5}; do
        save_checkpoint "TEST-001" "$i" '{}' >/dev/null 2>&1
        sleep 0.1  # Ensure different timestamps
    done

    local session_id
    session_id=$(jq -r '.session_id' "$SESSION_STATE_FILE" 2>/dev/null)
    local checkpoint_dir="${SESSION_CHECKPOINT_DIR}/${session_id}"

    local checkpoint_count
    checkpoint_count=$(ls -1 "$checkpoint_dir"/checkpoint_*.json 2>/dev/null | wc -l | tr -d ' ')

    assert_equals "3" "$checkpoint_count" "Only 3 checkpoints kept"
}

# Test 5: Atomic writes (no .tmp files left behind)
test_atomic_writes() {
    echo ""
    echo "Test 5: Atomic writes - no temp files left behind"

    save_checkpoint "TEST-001" 10 '{}' >/dev/null 2>&1

    local session_id
    session_id=$(jq -r '.session_id' "$SESSION_STATE_FILE" 2>/dev/null)
    local checkpoint_dir="${SESSION_CHECKPOINT_DIR}/${session_id}"

    local tmp_files
    tmp_files=$(ls -1 "$checkpoint_dir"/*.tmp 2>/dev/null | wc -l | tr -d ' ')

    assert_equals "0" "$tmp_files" "No temp files left behind"
}

# Test 6: Restore from latest checkpoint
test_restore_from_latest_checkpoint() {
    echo ""
    echo "Test 6: Restore from latest checkpoint"

    local test_prd_state='{"test": "restore_data", "iteration": 15}'
    save_checkpoint "TEST-002" 15 "$test_prd_state" >/dev/null 2>&1

    local restored
    restored=$(restore_from_checkpoint 2>/dev/null)

    local restored_iteration
    restored_iteration=$(echo "$restored" | jq -r '.iteration' 2>/dev/null)

    assert_equals "15" "$restored_iteration" "Restored correct iteration"

    local restored_story
    restored_story=$(echo "$restored" | jq -r '.story_id' 2>/dev/null)

    assert_equals "TEST-002" "$restored_story" "Restored correct story"
}

# Test 7: Restore from specific iteration
test_restore_from_specific_iteration() {
    echo ""
    echo "Test 7: Restore from specific iteration"

    # Create checkpoints for iterations 20, 21, 22
    for i in {20..22}; do
        save_checkpoint "TEST-001" "$i" "{\"iter\": $i}" >/dev/null 2>&1
        sleep 0.1
    done

    # Restore iteration 21
    local restored
    restored=$(restore_from_checkpoint_iteration 21 2>/dev/null)

    local restored_iteration
    restored_iteration=$(echo "$restored" | jq -r '.iteration' 2>/dev/null)

    assert_equals "21" "$restored_iteration" "Restored specific iteration"
}

# Test 8: List checkpoints
test_list_checkpoints() {
    echo ""
    echo "Test 8: List checkpoints"

    # Create 3 checkpoints
    for i in {30..32}; do
        save_checkpoint "TEST-001" "$i" '{}' >/dev/null 2>&1
        sleep 0.1
    done

    local checkpoints_json
    checkpoints_json=$(list_checkpoints json 2>/dev/null)

    local count
    count=$(echo "$checkpoints_json" | jq 'length' 2>/dev/null)

    assert_equals "3" "$count" "List shows 3 checkpoints"
}

# Main test runner
main() {
    echo "======================================"
    echo "Checkpoint Robustness Test Suite"
    echo "======================================"

    setup

    test_init_creates_checkpoint_dir
    test_save_checkpoint_creates_file
    test_checkpoint_contains_required_fields
    test_keep_last_three_checkpoints
    test_atomic_writes
    test_restore_from_latest_checkpoint
    test_restore_from_specific_iteration
    test_list_checkpoints

    teardown

    echo ""
    echo "======================================"
    echo "Test Results"
    echo "======================================"
    echo "Tests run:    $TESTS_RUN"
    echo -e "Tests passed: ${GREEN}$TESTS_PASSED${NC}"
    echo -e "Tests failed: ${RED}$TESTS_FAILED${NC}"

    if [ $TESTS_FAILED -gt 0 ]; then
        echo ""
        echo "Failed tests:"
        for test in "${FAILED_TESTS[@]}"; do
            echo -e "  ${RED}✗${NC} $test"
        done
        exit 1
    fi

    echo ""
    echo -e "${GREEN}All tests passed!${NC}"
    exit 0
}

main "$@"
