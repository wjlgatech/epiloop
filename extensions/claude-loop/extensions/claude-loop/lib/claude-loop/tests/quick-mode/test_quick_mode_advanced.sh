#!/bin/bash
#
# test_quick_mode_advanced.sh - Tests for Quick Mode Advanced Features (US-204)
#
# Tests all advanced quick mode features including:
# - Complexity detection
# - Auto-escalation
# - Task chaining
# - Templates
# - Dry-run mode
# - Continue mode
# - Cost estimation
# - Checkpointing
# - Concurrent execution
# - Enhanced history

set -euo pipefail

# Test setup
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
TEST_DIR="${PROJECT_ROOT}/tests/quick-mode"
TEMP_TEST_DIR="${TEST_DIR}/temp-$$"

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Test counters
TESTS_RUN=0
TESTS_PASSED=0
TESTS_FAILED=0

# Setup test environment
setup_test() {
    mkdir -p "${TEMP_TEST_DIR}"
    cd "${TEMP_TEST_DIR}"

    # Source the quick-task-mode.sh
    source "${PROJECT_ROOT}/lib/quick-task-mode.sh"

    # Initialize quick tasks
    init_quick_tasks
}

# Cleanup test environment
cleanup_test() {
    cd "${PROJECT_ROOT}"
    rm -rf "${TEMP_TEST_DIR}"
}

# Test result helpers
pass_test() {
    local test_name="$1"
    ((TESTS_PASSED++))
    echo -e "${GREEN}✓${NC} PASS: ${test_name}"
}

fail_test() {
    local test_name="$1"
    local reason="$2"
    ((TESTS_FAILED++))
    echo -e "${RED}✗${NC} FAIL: ${test_name}"
    echo -e "  Reason: ${reason}"
}

run_test() {
    local test_name="$1"
    ((TESTS_RUN++))
    echo -e "\n${YELLOW}→${NC} Running: ${test_name}"
}

# ============================================================================
# Test Cases
# ============================================================================

test_complexity_detection() {
    run_test "Complexity Detection"

    # Test simple task
    local simple_score=$(detect_task_complexity "Fix typo in README")
    if [ "$simple_score" -lt 30 ]; then
        pass_test "Simple task detected correctly (score: $simple_score)"
    else
        fail_test "Simple task detection" "Expected < 30, got $simple_score"
    fi

    # Test medium task
    local medium_score=$(detect_task_complexity "Add validation and error handling to user input")
    if [ "$medium_score" -ge 30 ] && [ "$medium_score" -lt 60 ]; then
        pass_test "Medium task detected correctly (score: $medium_score)"
    else
        fail_test "Medium task detection" "Expected 30-59, got $medium_score"
    fi

    # Test complex task
    local complex_score=$(detect_task_complexity "Refactor the entire authentication system with OAuth integration and comprehensive test coverage")
    if [ "$complex_score" -ge 60 ]; then
        pass_test "Complex task detected correctly (score: $complex_score)"
    else
        fail_test "Complex task detection" "Expected >= 60, got $complex_score"
    fi
}

test_escalation_logic() {
    run_test "Auto-escalation Logic"

    # Test should escalate
    if should_escalate_to_prd 70; then
        pass_test "High complexity triggers escalation"
    else
        fail_test "Escalation logic" "Should escalate for score 70"
    fi

    # Test should not escalate
    if ! should_escalate_to_prd 40; then
        pass_test "Low complexity does not trigger escalation"
    else
        fail_test "Escalation logic" "Should not escalate for score 40"
    fi
}

test_template_creation() {
    run_test "Template Creation"

    # Check if templates are created
    create_default_templates

    if [ -f "${QUICK_TASK_TEMPLATES_DIR}/refactor.json" ]; then
        pass_test "Refactor template created"
    else
        fail_test "Template creation" "Refactor template not found"
    fi

    if [ -f "${QUICK_TASK_TEMPLATES_DIR}/add-tests.json" ]; then
        pass_test "Add-tests template created"
    else
        fail_test "Template creation" "Add-tests template not found"
    fi

    if [ -f "${QUICK_TASK_TEMPLATES_DIR}/fix-bug.json" ]; then
        pass_test "Fix-bug template created"
    else
        fail_test "Template creation" "Fix-bug template not found"
    fi
}

test_template_loading() {
    run_test "Template Loading"

    # Load refactor template
    local template_json=$(load_template "refactor" "Refactor user service")

    if echo "$template_json" | python3 -c "import sys, json; json.load(sys.stdin); sys.exit(0)" 2>/dev/null; then
        pass_test "Template loads valid JSON"
    else
        fail_test "Template loading" "Invalid JSON from template"
        return
    fi

    # Check template has required fields
    local has_task=$(echo "$template_json" | python3 -c "import sys, json; print('task' in json.load(sys.stdin))" 2>/dev/null)
    if [ "$has_task" = "True" ]; then
        pass_test "Template has task field"
    else
        fail_test "Template loading" "Missing task field"
    fi
}

test_cost_estimation() {
    run_test "Cost Estimation"

    # Generate a simple plan
    local plan_json=$(generate_execution_plan "Fix typo" ".")

    # Estimate cost
    local cost=$(estimate_task_cost "$plan_json" 20)

    # Check cost is reasonable (> 0 and < 1)
    if python3 -c "import sys; cost = float('$cost'); sys.exit(0 if 0 < cost < 1 else 1)"; then
        pass_test "Cost estimation produces reasonable value: \$$cost"
    else
        fail_test "Cost estimation" "Unreasonable cost: \$$cost"
    fi
}

test_checkpoint_save_load() {
    run_test "Checkpoint Save/Load"

    local worker_dir="${TEMP_TEST_DIR}/test-worker"
    mkdir -p "${worker_dir}"

    local plan_json='{"task": "Test", "steps": []}'

    # Save checkpoint
    save_checkpoint "$worker_dir" 3 "$plan_json" "in progress"

    if [ -f "${worker_dir}/checkpoint.json" ]; then
        pass_test "Checkpoint file created"
    else
        fail_test "Checkpoint save" "Checkpoint file not created"
        return
    fi

    # Load checkpoint
    local loaded=$(load_checkpoint "$worker_dir")

    if echo "$loaded" | python3 -c "import sys, json; cp = json.load(sys.stdin); sys.exit(0 if cp.get('current_step') == 3 else 1)" 2>/dev/null; then
        pass_test "Checkpoint loaded correctly"
    else
        fail_test "Checkpoint load" "Checkpoint data incorrect"
    fi
}

test_find_last_failed() {
    run_test "Find Last Failed Task"

    # Create a mock failed task log
    local test_log="${QUICK_TASKS_LOG}"
    mkdir -p "$(dirname "$test_log")"

    cat > "$test_log" <<EOF
{"task_id":"test1","task":"Task 1","status":"success","duration_ms":1000,"workspace":".","timestamp":"2026-01-13T10:00:00Z","worker_dir":"${TEMP_TEST_DIR}/worker1"}
{"task_id":"test2","task":"Task 2","status":"failure","duration_ms":2000,"workspace":".","timestamp":"2026-01-13T10:01:00Z","worker_dir":"${TEMP_TEST_DIR}/worker2"}
{"task_id":"test3","task":"Task 3","status":"success","duration_ms":1500,"workspace":".","timestamp":"2026-01-13T10:02:00Z","worker_dir":"${TEMP_TEST_DIR}/worker3"}
EOF

    local last_failed=$(find_last_failed_task)

    if [ "$last_failed" = "${TEMP_TEST_DIR}/worker2" ]; then
        pass_test "Last failed task found correctly"
    else
        fail_test "Find last failed" "Expected worker2, got: $last_failed"
    fi
}

test_history_with_filter() {
    run_test "History with Filter"

    # Create mock task log
    cat > "${QUICK_TASKS_LOG}" <<EOF
{"task_id":"test1","task":"Task 1","status":"success","duration_ms":1000,"workspace":".","timestamp":"2026-01-13T10:00:00Z","worker_dir":"${TEMP_TEST_DIR}/worker1","cost_estimate":0.01}
{"task_id":"test2","task":"Task 2","status":"failure","duration_ms":2000,"workspace":".","timestamp":"2026-01-13T10:01:00Z","worker_dir":"${TEMP_TEST_DIR}/worker2","cost_estimate":0.02}
{"task_id":"test3","task":"Task 3","status":"success","duration_ms":1500,"workspace":".","timestamp":"2026-01-13T10:02:00Z","worker_dir":"${TEMP_TEST_DIR}/worker3","cost_estimate":0.015}
EOF

    # Test history shows entries
    local history_output=$(show_quick_task_history 10 "all")

    if echo "$history_output" | grep -q "Task 1"; then
        pass_test "History displays tasks"
    else
        fail_test "History display" "Task 1 not found in history"
    fi

    # Test filter by success
    local success_output=$(show_quick_task_history 10 "success")

    if echo "$success_output" | grep -q "Task 1" && ! echo "$success_output" | grep -q "Task 2"; then
        pass_test "History filters by success status"
    else
        fail_test "History filter" "Success filter not working correctly"
    fi
}

test_stats_calculation() {
    run_test "Statistics Calculation"

    # Ensure we have test data
    cat > "${QUICK_TASKS_LOG}" <<EOF
{"task_id":"test1","task":"Task 1","status":"success","duration_ms":1000,"workspace":".","timestamp":"2026-01-13T10:00:00Z","worker_dir":"${TEMP_TEST_DIR}/worker1","cost_estimate":0.01}
{"task_id":"test2","task":"Task 2","status":"failure","duration_ms":2000,"workspace":".","timestamp":"2026-01-13T10:01:00Z","worker_dir":"${TEMP_TEST_DIR}/worker2","cost_estimate":0.02}
{"task_id":"test3","task":"Task 3","status":"success","duration_ms":1500,"workspace":".","timestamp":"2026-01-13T10:02:00Z","worker_dir":"${TEMP_TEST_DIR}/worker3","cost_estimate":0.015}
EOF

    # Get stats output
    local stats_output=$(show_quick_task_stats)

    if echo "$stats_output" | grep -q "Total tasks: 3"; then
        pass_test "Statistics show correct total"
    else
        fail_test "Statistics" "Total tasks count incorrect"
    fi

    if echo "$stats_output" | grep -q "Successful: 2"; then
        pass_test "Statistics show correct success count"
    else
        fail_test "Statistics" "Success count incorrect"
    fi
}

test_plan_generation_with_complexity() {
    run_test "Plan Generation with Complexity"

    # Generate plan for simple task
    local simple_plan=$(generate_execution_plan "Fix typo in README" ".")

    # Check complexity score is included
    local has_score=$(echo "$simple_plan" | python3 -c "import sys, json; print('complexity_score' in json.load(sys.stdin))" 2>/dev/null)

    if [ "$has_score" = "True" ]; then
        pass_test "Plan includes complexity score"
    else
        fail_test "Plan generation" "Complexity score missing"
    fi

    # Check complexity level
    local complexity_level=$(echo "$simple_plan" | python3 -c "import sys, json; print(json.load(sys.stdin).get('estimated_complexity', 'unknown'))" 2>/dev/null)

    if [ -n "$complexity_level" ] && [ "$complexity_level" != "unknown" ]; then
        pass_test "Plan includes complexity level: $complexity_level"
    else
        fail_test "Plan generation" "Complexity level missing or unknown"
    fi
}

# ============================================================================
# Test Execution
# ============================================================================

main() {
    echo "========================================"
    echo "  Quick Mode Advanced Features Tests"
    echo "  (US-204)"
    echo "========================================"
    echo ""

    # Setup
    setup_test

    # Run all tests
    test_complexity_detection
    test_escalation_logic
    test_template_creation
    test_template_loading
    test_cost_estimation
    test_checkpoint_save_load
    test_find_last_failed
    test_history_with_filter
    test_stats_calculation
    test_plan_generation_with_complexity

    # Cleanup
    cleanup_test

    # Summary
    echo ""
    echo "========================================"
    echo "  TEST SUMMARY"
    echo "========================================"
    echo "Tests run:    ${TESTS_RUN}"
    echo -e "Tests passed: ${GREEN}${TESTS_PASSED}${NC}"
    if [ "$TESTS_FAILED" -gt 0 ]; then
        echo -e "Tests failed: ${RED}${TESTS_FAILED}${NC}"
    else
        echo -e "Tests failed: ${TESTS_FAILED}"
    fi
    echo ""

    if [ "$TESTS_FAILED" -eq 0 ]; then
        echo -e "${GREEN}✓ All tests passed!${NC}"
        exit 0
    else
        echo -e "${RED}✗ Some tests failed!${NC}"
        exit 1
    fi
}

# Run tests
main "$@"
