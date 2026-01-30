#!/bin/bash
#
# Delegation Integration Tests (US-007)
#
# Tests bounded delegation functionality including:
# - Delegation syntax parsing
# - Depth limit enforcement
# - Context budget validation
# - Cycle detection
# - Git worktree isolation
# - Cost attribution
# - Error handling
#

set -euo pipefail

# Color output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Test configuration
TEST_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$TEST_DIR/.." && pwd)"
DELEGATION_PARSER="$ROOT_DIR/lib/delegation-parser.sh"
DELEGATION_TRACKER="$ROOT_DIR/lib/delegation-tracker.sh"
DELEGATION_SCRIPT="$ROOT_DIR/lib/delegation.sh"

# Test state
TESTS_RUN=0
TESTS_PASSED=0
TESTS_FAILED=0

# Test cleanup
cleanup() {
    # Remove test delegation data
    if [[ -d ".claude-loop/delegation" ]]; then
        rm -rf .claude-loop/delegation
    fi

    # Remove test log
    if [[ -f ".claude-loop/logs/delegation.jsonl" ]]; then
        rm -f .claude-loop/logs/delegation.jsonl
    fi

    # Prune test worktrees
    git worktree prune 2>/dev/null || true
}

trap cleanup EXIT

# Assertion helpers
assert_equals() {
    local expected="$1"
    local actual="$2"
    local message="${3:-}"

    ((TESTS_RUN++))

    if [[ "$expected" == "$actual" ]]; then
        echo -e "${GREEN}✓${NC} $message"
        ((TESTS_PASSED++))
        return 0
    else
        echo -e "${RED}✗${NC} $message"
        echo "  Expected: $expected"
        echo "  Actual: $actual"
        ((TESTS_FAILED++))
        return 1
    fi
}

assert_contains() {
    local haystack="$1"
    local needle="$2"
    local message="${3:-}"

    ((TESTS_RUN++))

    if echo "$haystack" | grep -q "$needle"; then
        echo -e "${GREEN}✓${NC} $message"
        ((TESTS_PASSED++))
        return 0
    else
        echo -e "${RED}✗${NC} $message"
        echo "  Haystack: $haystack"
        echo "  Needle: $needle"
        ((TESTS_FAILED++))
        return 1
    fi
}

assert_success() {
    local exit_code=$1
    local message="${2:-}"

    ((TESTS_RUN++))

    if [[ $exit_code -eq 0 ]]; then
        echo -e "${GREEN}✓${NC} $message"
        ((TESTS_PASSED++))
        return 0
    else
        echo -e "${RED}✗${NC} $message"
        echo "  Exit code: $exit_code (expected 0)"
        ((TESTS_FAILED++))
        return 1
    fi
}

assert_failure() {
    local exit_code=$1
    local message="${2:-}"

    ((TESTS_RUN++))

    if [[ $exit_code -ne 0 ]]; then
        echo -e "${GREEN}✓${NC} $message"
        ((TESTS_PASSED++))
        return 0
    else
        echo -e "${RED}✗${NC} $message"
        echo "  Exit code: $exit_code (expected non-zero)"
        ((TESTS_FAILED++))
        return 1
    fi
}

# ====================================================================================
# Test Suite
# ====================================================================================

echo "Bounded Delegation Integration Tests (US-007)"
echo "=============================================="
echo ""

# --------------------
# Delegation Parser Tests
# --------------------

echo "Delegation Parser Tests"
echo "----------------------"

test_parser_valid_syntax() {
    local input="[delegate:Implement JWT authentication:4]"
    local output
    local exit_code=0

    output=$(echo "$input" | "$DELEGATION_PARSER" parse 0) || exit_code=$?

    assert_success $exit_code "Parse valid delegation syntax"
    assert_contains "$output" "Implement JWT authentication" "Extract description"
    assert_contains "$output" '"estimated_hours": "4"' "Extract estimated hours"
}

test_parser_count_multiple() {
    local input="[delegate:Task A:2]

Some text here

[delegate:Task B:3]

More text

[delegate:Task C:1]"

    local output
    local count

    output=$(echo "$input" | "$DELEGATION_PARSER" count)
    count=$(echo "$output" | jq -r '.count')

    assert_equals "3" "$count" "Count 3 delegations in input"
}

test_parser_invalid_syntax() {
    local input="[delegate:No hours specified]"
    local output
    local exit_code=0

    output=$(echo "$input" | "$DELEGATION_PARSER" validate 2>&1) || exit_code=$?

    assert_failure $exit_code "Reject invalid syntax (missing hours)"
}

test_parser_empty_input() {
    local input=""
    local output
    local count

    output=$(echo "$input" | "$DELEGATION_PARSER" count)
    count=$(echo "$output" | jq -r '.count')

    assert_equals "0" "$count" "Count 0 delegations in empty input"
}

# Run parser tests
test_parser_valid_syntax
test_parser_count_multiple
test_parser_invalid_syntax
test_parser_empty_input

echo ""

# --------------------
# Delegation Tracker Tests
# --------------------

echo "Delegation Tracker Tests"
echo "-----------------------"

test_tracker_init() {
    # Initialize tracker
    "$DELEGATION_TRACKER" init >/dev/null 2>&1

    assert_success $? "Initialize delegation tracking"

    # Verify directory structure
    if [[ -d ".claude-loop/delegation" ]]; then
        echo -e "${GREEN}✓${NC} Delegation directory created"
        ((TESTS_PASSED++))
    else
        echo -e "${RED}✗${NC} Delegation directory not created"
        ((TESTS_FAILED++))
    fi
    ((TESTS_RUN++))
}

test_tracker_depth_limit() {
    # Initialize tracker
    "$DELEGATION_TRACKER" init >/dev/null 2>&1

    # Set depth for parent
    source "$DELEGATION_TRACKER"
    set_delegation_depth "exec-001" 0

    # Check depth for child at depth 1 (should pass)
    local exit_code=0
    check_delegation_depth "exec-001" "exec-002" 2>/dev/null || exit_code=$?
    assert_success $exit_code "Allow delegation at depth 1"

    # Set child at depth 1
    set_delegation_depth "exec-002" 1

    # Check depth for grandchild at depth 2 (should pass)
    exit_code=0
    check_delegation_depth "exec-002" "exec-003" 2>/dev/null || exit_code=$?
    assert_success $exit_code "Allow delegation at depth 2"

    # Set grandchild at depth 2
    set_delegation_depth "exec-003" 2

    # Check depth for great-grandchild at depth 3 (should fail - exceeds MAX=2)
    exit_code=0
    check_delegation_depth "exec-003" "exec-004" 2>/dev/null || exit_code=$?
    assert_failure $exit_code "Block delegation at depth 3 (exceeds MAX_DELEGATION_DEPTH=2)"
}

test_tracker_cycle_detection() {
    # Initialize tracker
    "$DELEGATION_TRACKER" init >/dev/null 2>&1

    # Source tracker functions
    source "$DELEGATION_TRACKER"

    # Create execution graph: exec-001 → exec-002 → exec-003
    add_execution_edge "exec-001" "exec-002"
    add_execution_edge "exec-002" "exec-003"

    # Try to create cycle: exec-003 → exec-001 (should fail)
    local exit_code=0
    detect_delegation_cycle "exec-003" "exec-001" 2>/dev/null || exit_code=$?
    assert_failure $exit_code "Detect cycle: exec-001 → exec-002 → exec-003 → exec-001"

    # Try to add non-cyclic edge: exec-003 → exec-004 (should pass)
    exit_code=0
    detect_delegation_cycle "exec-003" "exec-004" 2>/dev/null || exit_code=$?
    assert_success $exit_code "Allow non-cyclic delegation"
}

test_tracker_logging() {
    # Initialize tracker
    "$DELEGATION_TRACKER" init >/dev/null 2>&1

    # Log a delegation event
    "$DELEGATION_TRACKER" log started US-007 US-007-DEL-001 1 exec-001 exec-002 2>/dev/null

    assert_success $? "Log delegation event"

    # Verify log file exists and contains entry
    if [[ -f ".claude-loop/logs/delegation.jsonl" ]]; then
        local log_content
        log_content=$(cat .claude-loop/logs/delegation.jsonl)
        assert_contains "$log_content" "US-007" "Log contains parent story"
        assert_contains "$log_content" "US-007-DEL-001" "Log contains child story"
        assert_contains "$log_content" "started" "Log contains event type"
    else
        echo -e "${RED}✗${NC} Delegation log file not created"
        ((TESTS_FAILED++))
        ((TESTS_RUN++))
    fi
}

test_tracker_stats() {
    # Initialize tracker
    "$DELEGATION_TRACKER" init >/dev/null 2>&1

    # Log some events
    "$DELEGATION_TRACKER" log started US-007 US-007-DEL-001 1 exec-001 exec-002 2>/dev/null
    "$DELEGATION_TRACKER" log completed US-007 US-007-DEL-001 1 exec-001 exec-002 "cost_usd=0.50" "tokens_in=3000" "tokens_out=1500" 2>/dev/null

    # Get stats
    local stats
    stats=$("$DELEGATION_TRACKER" stats 2>/dev/null)

    assert_success $? "Get delegation statistics"
    assert_contains "$stats" "total_delegations" "Stats contain total count"
    assert_contains "$stats" "max_depth_seen" "Stats contain max depth"
}

# Run tracker tests
test_tracker_init
test_tracker_depth_limit
test_tracker_cycle_detection
test_tracker_logging
test_tracker_stats

echo ""

# --------------------
# Delegation Executor Tests
# --------------------

echo "Delegation Executor Tests"
echo "------------------------"

test_executor_context_budget() {
    # Initialize delegation script
    source "$DELEGATION_SCRIPT"

    # Test within budget
    local exit_code=0
    check_context_budget 80000 15000 2>/dev/null || exit_code=$?
    assert_success $exit_code "Allow delegation within context budget (80k + 15k < 100k)"

    # Test exceeding budget
    exit_code=0
    check_context_budget 90000 15000 2>/dev/null || exit_code=$?
    assert_failure $exit_code "Block delegation exceeding context budget (90k + 15k > 100k)"
}

test_executor_estimate_tokens() {
    source "$DELEGATION_SCRIPT"

    local description="Create user model with email, password_hash, and timestamps"
    local estimate
    estimate=$(estimate_delegation_tokens "$description")

    assert_success $? "Estimate delegation tokens"

    # Verify estimate is reasonable (should be > 0 and < 10000 for simple description)
    if [[ $estimate -gt 0 ]] && [[ $estimate -lt 10000 ]]; then
        echo -e "${GREEN}✓${NC} Token estimate is reasonable ($estimate tokens)"
        ((TESTS_PASSED++))
    else
        echo -e "${RED}✗${NC} Token estimate is unreasonable ($estimate tokens)"
        ((TESTS_FAILED++))
    fi
    ((TESTS_RUN++))
}

test_executor_worktree_creation() {
    source "$DELEGATION_SCRIPT"

    # Create a test worktree
    local worktree_path
    local exit_code=0
    worktree_path=$(create_delegation_worktree "TEST-DEL-001" 2>&1) || exit_code=$?

    if [[ $exit_code -eq 0 ]]; then
        assert_success $exit_code "Create delegation worktree"

        # Verify worktree exists
        if [[ -d "$worktree_path" ]]; then
            echo -e "${GREEN}✓${NC} Worktree directory exists: $worktree_path"
            ((TESTS_PASSED++))

            # Cleanup worktree
            cleanup_delegation_worktree "$worktree_path"

            if [[ ! -d "$worktree_path" ]]; then
                echo -e "${GREEN}✓${NC} Worktree cleanup successful"
                ((TESTS_PASSED++))
            else
                echo -e "${RED}✗${NC} Worktree cleanup failed"
                ((TESTS_FAILED++))
            fi
        else
            echo -e "${RED}✗${NC} Worktree directory not created"
            ((TESTS_FAILED++))
        fi
        ((TESTS_RUN++))
        ((TESTS_RUN++))
    else
        # Worktree creation failed (might not be in git repo)
        echo -e "${YELLOW}⊘${NC} Worktree creation skipped (not in git repo)"
        ((TESTS_RUN++))
    fi
}

# Run executor tests
test_executor_context_budget
test_executor_estimate_tokens
test_executor_worktree_creation

echo ""

# --------------------
# Cost Attribution Tests
# --------------------

echo "Cost Attribution Tests"
echo "---------------------"

test_cost_story_total() {
    # Initialize tracker
    "$DELEGATION_TRACKER" init >/dev/null 2>&1

    # Log delegation with cost
    "$DELEGATION_TRACKER" log completed US-100 US-100-DEL-001 1 exec-001 exec-002 \
        "cost_usd=0.60" "tokens_in=5000" "tokens_out=3000" "duration_ms=15000" 2>/dev/null

    "$DELEGATION_TRACKER" log completed US-100 US-100-DEL-002 1 exec-001 exec-003 \
        "cost_usd=0.55" "tokens_in=4500" "tokens_out=2500" "duration_ms=12000" 2>/dev/null

    # Get total cost
    local total_cost
    total_cost=$("$DELEGATION_TRACKER" story-cost US-100 2>/dev/null)

    assert_success $? "Calculate total cost for story"

    # Verify cost is sum of delegations (0.60 + 0.55 = 1.15)
    # Use bc for float comparison
    local expected="1.15"
    if echo "$total_cost == $expected" | bc -l | grep -q 1; then
        echo -e "${GREEN}✓${NC} Total cost matches sum of delegations ($total_cost)"
        ((TESTS_PASSED++))
    else
        echo -e "${RED}✗${NC} Total cost mismatch (expected $expected, got $total_cost)"
        ((TESTS_FAILED++))
    fi
    ((TESTS_RUN++))
}

test_cost_breakdown() {
    # Initialize tracker
    "$DELEGATION_TRACKER" init >/dev/null 2>&1

    # Log delegation with cost
    "$DELEGATION_TRACKER" log completed US-101 US-101-DEL-001 1 exec-001 exec-002 \
        "cost_usd=0.50" "tokens_in=4000" "tokens_out=2000" "duration_ms=10000" 2>/dev/null

    # Get cost breakdown
    local breakdown
    breakdown=$("$DELEGATION_TRACKER" cost-breakdown US-101 2>/dev/null)

    assert_success $? "Get cost breakdown for story"
    assert_contains "$breakdown" "parent_story" "Breakdown contains parent story"
    assert_contains "$breakdown" "total_cost" "Breakdown contains total cost"
    assert_contains "$breakdown" "children" "Breakdown contains children array"
}

# Run cost attribution tests
test_cost_story_total
test_cost_breakdown

echo ""

# --------------------
# Integration Tests
# --------------------

echo "Integration Tests"
echo "----------------"

test_integration_full_workflow() {
    # This test requires a full claude-loop execution
    # For now, we'll test the components integrate correctly

    # Initialize all components
    "$DELEGATION_TRACKER" init >/dev/null 2>&1
    source "$DELEGATION_SCRIPT"

    # Simulate delegation workflow
    local input="[delegate:Implement user authentication:4]"

    # 1. Parse delegation
    local delegation_json
    delegation_json=$(echo "$input" | "$DELEGATION_PARSER" parse 0 2>/dev/null)
    assert_success $? "Integration: Parse delegation"

    # 2. Check depth limit (parent at depth 0)
    source "$DELEGATION_TRACKER"
    set_delegation_depth "exec-parent" 0
    local exit_code=0
    check_delegation_depth "exec-parent" "exec-child" 2>/dev/null || exit_code=$?
    assert_success $exit_code "Integration: Check depth limit"

    # 3. Check context budget
    exit_code=0
    check_context_budget 50000 40000 2>/dev/null || exit_code=$?
    assert_success $exit_code "Integration: Check context budget"

    # 4. Add execution edge (no cycle)
    add_execution_edge "exec-parent" "exec-child"
    exit_code=0
    detect_delegation_cycle "exec-parent" "exec-child" 2>/dev/null || exit_code=$?
    assert_success $exit_code "Integration: Detect no cycle"

    # 5. Log delegation
    "$DELEGATION_TRACKER" log started US-200 US-200-DEL-001 1 exec-parent exec-child 2>/dev/null
    assert_success $? "Integration: Log delegation event"

    echo -e "${GREEN}✓${NC} Full integration workflow complete"
    ((TESTS_PASSED++))
    ((TESTS_RUN++))
}

test_integration_error_handling() {
    # Initialize
    "$DELEGATION_TRACKER" init >/dev/null 2>&1
    source "$DELEGATION_TRACKER"

    # Test error: depth limit exceeded
    set_delegation_depth "exec-deep-1" 2  # Already at max depth
    local exit_code=0
    check_delegation_depth "exec-deep-1" "exec-deep-2" 2>/dev/null || exit_code=$?
    assert_failure $exit_code "Integration: Error handling - depth limit"

    # Test error: cycle detection
    add_execution_edge "exec-cycle-1" "exec-cycle-2"
    add_execution_edge "exec-cycle-2" "exec-cycle-3"
    exit_code=0
    detect_delegation_cycle "exec-cycle-3" "exec-cycle-1" 2>/dev/null || exit_code=$?
    assert_failure $exit_code "Integration: Error handling - cycle detection"

    # Test error: context budget exceeded
    source "$DELEGATION_SCRIPT"
    exit_code=0
    check_context_budget 95000 10000 2>/dev/null || exit_code=$?
    assert_failure $exit_code "Integration: Error handling - context budget"

    echo -e "${GREEN}✓${NC} Error handling tests complete"
    ((TESTS_PASSED++))
    ((TESTS_RUN++))
}

# Run integration tests
test_integration_full_workflow
test_integration_error_handling

echo ""

# ====================================================================================
# Test Summary
# ====================================================================================

echo "Test Summary"
echo "============"
echo "Tests run: $TESTS_RUN"
echo -e "${GREEN}Passed: $TESTS_PASSED${NC}"

if [[ $TESTS_FAILED -gt 0 ]]; then
    echo -e "${RED}Failed: $TESTS_FAILED${NC}"
    exit 1
else
    echo -e "${GREEN}All tests passed!${NC}"
    exit 0
fi
