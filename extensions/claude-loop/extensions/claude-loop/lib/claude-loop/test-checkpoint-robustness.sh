#!/bin/bash
#
# Test script for US-001: Increase checkpoint frequency
#
# Tests:
# 1. Checkpoints are saved after every iteration
# 2. Atomic writes prevent corruption
# 3. Checkpoint rotation keeps last 3
# 4. Recovery works after simulated crash
# 5. Checkpoint data includes story, iteration, timestamp, PRD state

set -uo pipefail  # Remove -e to prevent early exit on test failures

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Source the session-state.sh library
source lib/session-state.sh

# Test configuration
TEST_PRD="prd.json"
TEST_SESSION_DIR=".claude-loop-test"
TEST_CHECKPOINT_DIR="$TEST_SESSION_DIR/checkpoints"
PASS_COUNT=0
FAIL_COUNT=0
TOTAL_TESTS=0

# Override session state directory for testing
export SESSION_STATE_DIR="$TEST_SESSION_DIR"
export SESSION_STATE_FILE="$TEST_SESSION_DIR/session-state.json"
export SESSION_CHECKPOINT_DIR="$TEST_CHECKPOINT_DIR"

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Test helpers
test_passed() {
    echo -e "${GREEN}✓ PASS${NC}: $1"
    ((PASS_COUNT++))
    ((TOTAL_TESTS++))
}

test_failed() {
    echo -e "${RED}✗ FAIL${NC}: $1"
    echo -e "  ${YELLOW}Reason${NC}: $2"
    ((FAIL_COUNT++))
    ((TOTAL_TESTS++))
}

test_header() {
    echo ""
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BLUE}TEST: $1${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
}

# Cleanup function
cleanup_test_env() {
    echo -e "\n${YELLOW}Cleaning up test environment...${NC}"
    rm -rf "$TEST_SESSION_DIR" 2>/dev/null || true
    rm -f lib/session-state.sh.backup 2>/dev/null || true
}

# Trap to ensure cleanup on exit
trap cleanup_test_env EXIT

# ============================================================================
# Test 1: Checkpoints are saved after every iteration
# ============================================================================
test_header "US-001 AC1: Checkpoints saved after every iteration"

# Initialize session
init_session "$TEST_PRD" "test-project" "feature/test" > /dev/null 2>&1

# Save state for multiple iterations
for i in 1 2 3; do
    save_session_state "US-001" "$i" "implementation" > /dev/null 2>&1
done

# Check that checkpoints were created
CHECKPOINT_COUNT=$(find "$TEST_CHECKPOINT_DIR" -name "*.json" 2>/dev/null | wc -l | tr -d ' ')

if [ "$CHECKPOINT_COUNT" -eq 3 ]; then
    test_passed "Created 3 checkpoints for 3 iterations"
else
    test_failed "Expected 3 checkpoints, found $CHECKPOINT_COUNT" "save_checkpoint not called after each iteration"
fi

# ============================================================================
# Test 2: Atomic writes prevent corruption
# ============================================================================
test_header "US-001 AC2: Atomic writes with temp file + rename"

# Save a checkpoint and verify temp file was used
save_session_state "US-001" 4 "implementation" > /dev/null 2>&1

# Check that no .tmp files remain (atomic rename succeeded)
TMP_FILE_COUNT=$(find "$TEST_CHECKPOINT_DIR" -name "*.tmp" 2>/dev/null | wc -l | tr -d ' ')

if [ "$TMP_FILE_COUNT" -eq 0 ]; then
    test_passed "No .tmp files remain after checkpoint save (atomic rename)"
else
    test_failed "Found $TMP_FILE_COUNT .tmp files" "Atomic rename may have failed"
fi

# Verify checkpoint files are valid JSON
LATEST_CHECKPOINT=$(ls -1t "$TEST_CHECKPOINT_DIR"/*/*.json 2>/dev/null | head -1)
if [ -n "$LATEST_CHECKPOINT" ] && jq empty "$LATEST_CHECKPOINT" 2>/dev/null; then
    test_passed "Checkpoint file is valid JSON"
else
    test_failed "Checkpoint file is invalid or missing" "File may be corrupted"
fi

# ============================================================================
# Test 3: Checkpoint rotation keeps last 3
# ============================================================================
test_header "US-001 AC4: Keep last 3 checkpoints for rollback"

# Save 5 more iterations to trigger rotation
for i in 5 6 7 8 9; do
    save_session_state "US-001" "$i" "implementation" > /dev/null 2>&1
    sleep 0.1  # Small delay to ensure different timestamps
done

# Count total checkpoints
FINAL_CHECKPOINT_COUNT=$(find "$TEST_CHECKPOINT_DIR" -name "checkpoint_*.json" 2>/dev/null | wc -l | tr -d ' ')

if [ "$FINAL_CHECKPOINT_COUNT" -le 3 ]; then
    test_passed "Rotation limited checkpoints to $FINAL_CHECKPOINT_COUNT (≤3)"
else
    test_failed "Expected ≤3 checkpoints, found $FINAL_CHECKPOINT_COUNT" "Rotation did not clean up old checkpoints"
fi

# ============================================================================
# Test 4: Checkpoint includes required metadata
# ============================================================================
test_header "US-001 AC3: Checkpoint includes story, iteration, timestamp, PRD state"

LATEST_CHECKPOINT=$(ls -1t "$TEST_CHECKPOINT_DIR"/*/*.json 2>/dev/null | head -1)

if [ -f "$LATEST_CHECKPOINT" ]; then
    # Check for required fields
    HAS_STORY=$(jq -r '.story_id // empty' "$LATEST_CHECKPOINT" 2>/dev/null)
    HAS_ITERATION=$(jq -r '.iteration // empty' "$LATEST_CHECKPOINT" 2>/dev/null)
    HAS_TIMESTAMP=$(jq -r '.timestamp // empty' "$LATEST_CHECKPOINT" 2>/dev/null)
    HAS_PRD_STATE=$(jq -r '.prd_state // empty' "$LATEST_CHECKPOINT" 2>/dev/null)

    MISSING_FIELDS=()
    [ -z "$HAS_STORY" ] && MISSING_FIELDS+=("story_id")
    [ -z "$HAS_ITERATION" ] && MISSING_FIELDS+=("iteration")
    [ -z "$HAS_TIMESTAMP" ] && MISSING_FIELDS+=("timestamp")
    [ -z "$HAS_PRD_STATE" ] && MISSING_FIELDS+=("prd_state")

    if [ ${#MISSING_FIELDS[@]} -eq 0 ]; then
        test_passed "Checkpoint includes all required metadata (story_id, iteration, timestamp, prd_state)"
    else
        test_failed "Checkpoint missing fields: ${MISSING_FIELDS[*]}" "Checkpoint schema incomplete"
    fi
else
    test_failed "No checkpoint file found for metadata validation" "Checkpoint may not have been created"
fi

# ============================================================================
# Test 5: Recovery from checkpoint after crash
# ============================================================================
test_header "US-001 AC5: Recovery from checkpoint after simulated crash"

# Save current session state
save_session_state "US-002" 3 "implementation" > /dev/null 2>&1

# Get current iteration from session
ITERATION_BEFORE=$(jq -r '.current_iteration' "$SESSION_STATE_FILE" 2>/dev/null)

# Simulate crash by corrupting session state
echo "CORRUPTED" > "$SESSION_STATE_FILE"

# Attempt to restore from checkpoint
CHECKPOINT_TO_RESTORE=$(ls -1t "$TEST_CHECKPOINT_DIR"/*/*.json 2>/dev/null | head -1)

if [ -n "$CHECKPOINT_TO_RESTORE" ]; then
    restore_from_checkpoint "$CHECKPOINT_TO_RESTORE" > /dev/null 2>&1

    # Verify restoration
    if [ -f "$SESSION_STATE_FILE" ] && jq empty "$SESSION_STATE_FILE" 2>/dev/null; then
        ITERATION_AFTER=$(jq -r '.current_iteration' "$SESSION_STATE_FILE" 2>/dev/null)

        if [ "$ITERATION_AFTER" = "$ITERATION_BEFORE" ]; then
            test_passed "Successfully restored session from checkpoint after crash"
        else
            test_failed "Iteration mismatch after restore (before: $ITERATION_BEFORE, after: $ITERATION_AFTER)" "Restore may be incomplete"
        fi
    else
        test_failed "Session state file is invalid after restore" "Restore function may have failed"
    fi
else
    test_failed "No checkpoint available for restore" "Cannot test recovery"
fi

# ============================================================================
# Test 6: List checkpoints functionality
# ============================================================================
test_header "Additional: list_checkpoints function"

CHECKPOINT_LIST=$(list_checkpoints 2>/dev/null)

if echo "$CHECKPOINT_LIST" | grep -q "Iteration"; then
    test_passed "list_checkpoints shows available checkpoints"
else
    test_failed "list_checkpoints did not list checkpoints" "Function may not be working correctly"
fi

# ============================================================================
# Test Summary
# ============================================================================
echo ""
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}TEST SUMMARY${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "Total Tests: $TOTAL_TESTS"
echo -e "${GREEN}Passed: $PASS_COUNT${NC}"
echo -e "${RED}Failed: $FAIL_COUNT${NC}"
echo ""

if [ "$FAIL_COUNT" -eq 0 ]; then
    echo -e "${GREEN}✓ ALL TESTS PASSED${NC}"
    echo -e "${GREEN}US-001 acceptance criteria verified successfully!${NC}"
    exit 0
else
    echo -e "${RED}✗ SOME TESTS FAILED${NC}"
    echo -e "${YELLOW}Please review failures and fix before marking US-001 complete${NC}"
    exit 1
fi
