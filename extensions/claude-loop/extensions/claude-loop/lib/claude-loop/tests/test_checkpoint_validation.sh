#!/bin/bash
#
# test_checkpoint_validation.sh - Test checkpoint validation (US-002)
#
# Tests for US-002: Add checkpoint validation on load
# - Validate checkpoint JSON schema
# - Check required fields
# - Fall back to previous checkpoint if corrupted
# - Log validation errors

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
TEST_DIR="${PROJECT_ROOT}/.claude-loop/test-validation"

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
  "project": "test-validation",
  "branchName": "feature/test",
  "userStories": [{"id": "TEST-001", "title": "Test", "passes": false}]
}
EOF

    # Initialize session
    init_session "${TEST_DIR}/test-prd.json" >/dev/null 2>&1
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

# Test 1: Valid checkpoint passes validation
test_valid_checkpoint_passes() {
    echo ""
    echo "Test 1: Valid checkpoint passes validation"

    # Create valid checkpoint
    save_checkpoint "TEST-001" 1 '{"test": "data"}' >/dev/null 2>&1
    local checkpoint
    checkpoint=$(get_latest_checkpoint)

    if validate_checkpoint "$checkpoint" 2>/dev/null; then
        assert_equals "0" "0" "Valid checkpoint passes validation"
    else
        assert_equals "0" "1" "Valid checkpoint passes validation"
    fi
}

# Test 2: Invalid JSON fails validation
test_invalid_json_fails() {
    echo ""
    echo "Test 2: Invalid JSON fails validation"

    # Create checkpoint then corrupt it
    save_checkpoint "TEST-001" 2 '{}' >/dev/null 2>&1
    local checkpoint
    checkpoint=$(get_latest_checkpoint)

    # Corrupt the file
    echo "{ invalid json" > "$checkpoint"

    if validate_checkpoint "$checkpoint" 2>/dev/null; then
        assert_equals "1" "0" "Invalid JSON fails validation"
    else
        assert_equals "1" "1" "Invalid JSON fails validation"
    fi
}

# Test 3: Missing required field fails validation
test_missing_field_fails() {
    echo ""
    echo "Test 3: Missing required field fails validation"

    # Create checkpoint then remove a required field
    save_checkpoint "TEST-001" 3 '{}' >/dev/null 2>&1
    local checkpoint
    checkpoint=$(get_latest_checkpoint)

    # Remove story_id field
    local temp_file
    temp_file=$(mktemp)
    jq 'del(.story_id)' "$checkpoint" > "$temp_file"
    mv "$temp_file" "$checkpoint"

    if validate_checkpoint "$checkpoint" 2>/dev/null; then
        assert_equals "1" "0" "Missing field fails validation"
    else
        assert_equals "1" "1" "Missing field fails validation"
    fi
}

# Test 4: Invalid iteration value fails validation
test_invalid_iteration_fails() {
    echo ""
    echo "Test 4: Invalid iteration value fails validation"

    # Create checkpoint then set invalid iteration
    save_checkpoint "TEST-001" 4 '{}' >/dev/null 2>&1
    local checkpoint
    checkpoint=$(get_latest_checkpoint)

    # Set iteration to invalid value
    local temp_file
    temp_file=$(mktemp)
    jq '.iteration = "invalid"' "$checkpoint" > "$temp_file"
    mv "$temp_file" "$checkpoint"

    if validate_checkpoint "$checkpoint" 2>/dev/null; then
        assert_equals "1" "0" "Invalid iteration fails validation"
    else
        assert_equals "1" "1" "Invalid iteration fails validation"
    fi
}

# Test 5: Fallback to previous checkpoint on corruption
test_fallback_to_previous() {
    echo ""
    echo "Test 5: Fallback to previous checkpoint on corruption"

    # Create two valid checkpoints
    save_checkpoint "TEST-001" 10 '{"iter": 10}' >/dev/null 2>&1
    sleep 0.2
    save_checkpoint "TEST-001" 11 '{"iter": 11}' >/dev/null 2>&1

    local session_id
    session_id=$(jq -r '.session_id' "$SESSION_STATE_FILE" 2>/dev/null)
    local checkpoint_dir="${SESSION_CHECKPOINT_DIR}/${session_id}"

    # Corrupt the latest checkpoint (iteration 11)
    local latest_checkpoint
    latest_checkpoint=$(ls -1t "$checkpoint_dir"/checkpoint_*.json | head -1)
    echo "{ invalid json" > "$latest_checkpoint"

    # Try to restore (should fall back to iteration 10)
    local restored
    restored=$(restore_from_checkpoint 2>/dev/null)

    local restored_iteration
    restored_iteration=$(echo "$restored" | jq -r '.iteration' 2>/dev/null)

    assert_equals "10" "$restored_iteration" "Falls back to previous valid checkpoint"
}

# Test 6: Restore specific iteration validates before loading
test_restore_iteration_validates() {
    echo ""
    echo "Test 6: Restore specific iteration validates before loading"

    # Create checkpoint for iteration 20
    save_checkpoint "TEST-001" 20 '{"iter": 20}' >/dev/null 2>&1

    local session_id
    session_id=$(jq -r '.session_id' "$SESSION_STATE_FILE" 2>/dev/null)
    local checkpoint_dir="${SESSION_CHECKPOINT_DIR}/${session_id}"

    # Corrupt the checkpoint
    local checkpoint
    checkpoint=$(ls -1t "$checkpoint_dir"/checkpoint_20_*.json | head -1)
    echo "{ invalid }" > "$checkpoint"

    # Try to restore (should fail validation)
    if restore_from_checkpoint_iteration 20 2>/dev/null; then
        assert_equals "1" "0" "Corrupted checkpoint fails restore"
    else
        assert_equals "1" "1" "Corrupted checkpoint fails restore"
    fi
}

# Test 7: All required fields are validated
test_all_required_fields() {
    echo ""
    echo "Test 7: All required fields are validated"

    local required_fields=("session_id" "story_id" "iteration" "timestamp" "prd_state" "checkpoint_version")
    local all_pass=true

    for field in "${required_fields[@]}"; do
        # Create valid checkpoint
        save_checkpoint "TEST-001" 30 '{}' >/dev/null 2>&1
        local checkpoint
        checkpoint=$(get_latest_checkpoint)

        # Remove the field
        local temp_file
        temp_file=$(mktemp)
        jq "del(.$field)" "$checkpoint" > "$temp_file"
        mv "$temp_file" "$checkpoint"

        # Check validation fails
        if validate_checkpoint "$checkpoint" 2>/dev/null; then
            echo "  Field '$field': validation passed (SHOULD FAIL)"
            all_pass=false
        fi
    done

    if $all_pass; then
        assert_equals "true" "true" "All required fields validated"
    else
        assert_equals "true" "false" "All required fields validated"
    fi
}

# Main test runner
main() {
    echo "======================================"
    echo "Checkpoint Validation Test Suite"
    echo "======================================"

    setup

    test_valid_checkpoint_passes
    test_invalid_json_fails
    test_missing_field_fails
    test_invalid_iteration_fails
    test_fallback_to_previous
    test_restore_iteration_validates
    test_all_required_fields

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
