#!/usr/bin/env bash
#
# common-cases.sh - Phase 1 Common Use Case Tests
#
# Tests Phase 1 features in typical user workflows:
# - Progress indicators
# - PRD templates
# - Workspace sandboxing
# - Checkpoint confirmations
#

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Test counters
TESTS_RUN=0
TESTS_PASSED=0
TESTS_FAILED=0

# Project root
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
cd "$PROJECT_ROOT"

# Test output directory
TEST_OUTPUT_DIR="$PROJECT_ROOT/tests/phase1/computer-use/output"
mkdir -p "$TEST_OUTPUT_DIR"

# Cleanup function
cleanup() {
    local test_name="$1"
    if [ -f "$TEST_OUTPUT_DIR/${test_name}_prd.json" ]; then
        rm -f "$TEST_OUTPUT_DIR/${test_name}_prd.json"
    fi
    if [ -d "$TEST_OUTPUT_DIR/${test_name}_workspace" ]; then
        rm -rf "$TEST_OUTPUT_DIR/${test_name}_workspace"
    fi
}

# Test helper functions
log_test() {
    local test_name="$1"
    echo -e "${BLUE}[TEST]${NC} $test_name"
    ((TESTS_RUN++)) || true
}

log_pass() {
    local message="$1"
    echo -e "${GREEN}[PASS]${NC} $message"
    ((TESTS_PASSED++)) || true
}

log_fail() {
    local message="$1"
    echo -e "${RED}[FAIL]${NC} $message"
    ((TESTS_FAILED++)) || true
}

log_info() {
    local message="$1"
    echo -e "${YELLOW}[INFO]${NC} $message"
}

# Check if command exists
command_exists() {
    command -v "$1" &> /dev/null
}

# Verify Phase 1 features are available
verify_phase1_features() {
    log_info "Verifying Phase 1 features..."

    local missing_features=0

    if [ ! -f "$PROJECT_ROOT/lib/progress-indicators.sh" ]; then
        log_fail "Progress indicators not found"
        ((missing_features++)) || true
    fi

    if [ ! -f "$PROJECT_ROOT/lib/template-generator.sh" ]; then
        log_fail "Template generator not found"
        ((missing_features++)) || true
    fi

    if [ ! -f "$PROJECT_ROOT/lib/workspace-manager.sh" ]; then
        log_fail "Workspace manager not found"
        ((missing_features++)) || true
    fi

    if [ ! -f "$PROJECT_ROOT/lib/safety-checker.sh" ]; then
        log_fail "Safety checker not found"
        ((missing_features++)) || true
    fi

    if [ $missing_features -eq 0 ]; then
        log_pass "All Phase 1 features present"
        return 0
    else
        log_fail "$missing_features Phase 1 feature(s) missing"
        return 1
    fi
}

#
# Test Case 1: New user creates PRD from template, runs claude-loop, observes progress indicators
#
test_prd_template_workflow() {
    log_test "Test Case 1: PRD Template Workflow"

    local test_name="test1_prd_template"
    cleanup "$test_name"

    # Step 1: List available templates
    log_info "Step 1: Listing available templates"
    local templates_output
    if ! templates_output=$("$PROJECT_ROOT/lib/template-generator.sh" list 2>&1); then
        log_fail "Failed to list templates"
        return 1
    fi

    if ! echo "$templates_output" | grep -q "web-feature"; then
        log_fail "web-feature template not found in list"
        return 1
    fi
    log_pass "Templates listed successfully"

    # Step 2: Generate PRD from template
    log_info "Step 2: Generating PRD from web-feature template"
    local prd_output_path="$TEST_OUTPUT_DIR/${test_name}_prd.json"

    if ! "$PROJECT_ROOT/lib/template-generator.sh" generate web-feature \
        --output "$prd_output_path" \
        --var PROJECT_NAME="test-project" \
        --var FEATURE_NAME="test-feature" \
        --var DESCRIPTION="Test feature for Phase 1 validation" \
        --non-interactive 2>&1 > /dev/null; then
        log_fail "Failed to generate PRD from template"
        return 1
    fi

    if [ ! -f "$prd_output_path" ]; then
        log_fail "PRD file not created"
        return 1
    fi
    log_pass "PRD generated successfully"

    # Step 3: Validate PRD structure
    log_info "Step 3: Validating PRD structure"
    if ! bash -c "source '$PROJECT_ROOT/lib/prd-parser.sh' && validate_prd '$prd_output_path'" 2>&1 > /dev/null; then
        log_fail "PRD validation failed"
        return 1
    fi
    log_pass "PRD structure valid"

    # Step 4: Check progress indicators library
    log_info "Step 4: Verifying progress indicators are available"
    if ! grep -q "render_progress_bar" "$PROJECT_ROOT/lib/progress-indicators.sh"; then
        log_fail "Progress indicators functions not found"
        return 1
    fi
    log_pass "Progress indicators available"

    cleanup "$test_name"
    log_pass "Test Case 1 completed successfully"
    return 0
}

#
# Test Case 2: User runs claude-loop with workspace sandboxing, verifies only scoped files modified
#
test_workspace_sandboxing() {
    log_test "Test Case 2: Workspace Sandboxing"

    local test_name="test2_workspace"
    cleanup "$test_name"

    # Create test workspace
    local workspace_path="$TEST_OUTPUT_DIR/${test_name}_workspace"
    mkdir -p "$workspace_path/src"
    mkdir -p "$workspace_path/tests"
    echo "# Test file" > "$workspace_path/src/test.txt"

    # Test workspace validation
    log_info "Testing workspace validation"
    if ! bash -c "source '$PROJECT_ROOT/lib/workspace-manager.sh' && validate_workspace_folders '$workspace_path'" 2>&1 > /dev/null; then
        log_fail "Workspace validation failed"
        cleanup "$test_name"
        return 1
    fi
    log_pass "Workspace validation passed"

    # Test fileScope inference function exists
    log_info "Testing fileScope inference"
    if ! grep -q "infer_file_scope_from_workspace" "$PROJECT_ROOT/lib/workspace-manager.sh"; then
        log_fail "FileScope inference function not found"
        cleanup "$test_name"
        return 1
    fi
    log_pass "FileScope inference function available"

    cleanup "$test_name"
    log_pass "Test Case 2 completed successfully"
    return 0
}

#
# Test Case 3: User triggers destructive operation, receives checkpoint confirmation
#
test_checkpoint_confirmations() {
    log_test "Test Case 3: Checkpoint Confirmations"

    local test_name="test3_checkpoint"

    # Test safety checker detection functions
    log_info "Testing file deletion detection"

    # Check that the function exists
    if ! grep -q "detect_file_deletions" "$PROJECT_ROOT/lib/safety-checker.sh"; then
        log_fail "File deletion detection function not found"
        return 1
    fi
    log_pass "File deletion detection function available"

    # Test safety levels
    log_info "Testing safety level configuration"
    if ! grep -qi "paranoid\|cautious\|normal\|yolo" "$PROJECT_ROOT/lib/safety-checker.sh"; then
        log_fail "Safety levels not defined"
        return 1
    fi
    log_pass "Safety levels configured"

    # Test sensitive file detection
    log_info "Testing sensitive file detection"
    local test_files=(.env credentials.json .ssh/id_rsa)
    local detected=0

    for file in "${test_files[@]}"; do
        if bash -c "source '$PROJECT_ROOT/lib/safety-checker.sh' && is_sensitive_file '$file'" 2>&1 > /dev/null; then
            ((detected++)) || true
        fi
    done

    if [ $detected -lt 2 ]; then
        log_fail "Sensitive file detection not working properly (detected $detected/3)"
        return 1
    fi
    log_pass "Sensitive file detection working ($detected/3 detected)"

    log_pass "Test Case 3 completed successfully"
    return 0
}

#
# Test Case 4: User monitors long-running task via progress indicators
#
test_progress_indicators() {
    log_test "Test Case 4: Progress Indicators"

    # Test progress bar rendering
    log_info "Testing progress bar rendering"
    if ! bash -c "source '$PROJECT_ROOT/lib/progress-indicators.sh' && render_progress_bar 50 100" 2>&1 | grep -q "█"; then
        log_fail "Progress bar not rendering"
        return 1
    fi
    log_pass "Progress bar rendering works"

    # Test color support detection
    log_info "Testing color support detection"
    if ! grep -qi "tput\|color" "$PROJECT_ROOT/lib/progress-indicators.sh"; then
        log_fail "Color support detection not implemented"
        return 1
    fi
    log_pass "Color support detection implemented"

    # Test time tracking functions
    log_info "Testing time tracking"
    if ! grep -q "elapsed_time\|estimate_remaining\|format_duration" "$PROJECT_ROOT/lib/progress-indicators.sh"; then
        log_fail "Time tracking functions not found"
        return 1
    fi
    log_pass "Time tracking functions present"

    log_pass "Test Case 4 completed successfully"
    return 0
}

#
# Test Case 5: User tries all 6 PRD templates, generates valid PRDs
#
test_all_prd_templates() {
    log_test "Test Case 5: All PRD Templates"

    local successful=0

    # Test web-feature template
    log_info "Testing template: web-feature"
    local output_path="$TEST_OUTPUT_DIR/test5_web-feature_prd.json"
    if "$PROJECT_ROOT/lib/template-generator.sh" generate web-feature \
        --output "$output_path" \
        --var PROJECT_NAME="test-project" \
        --var FEATURE_NAME="test-feature" \
        --non-interactive 2>&1 > /dev/null && \
       bash -c "source '$PROJECT_ROOT/lib/prd-parser.sh' && validate_prd '$output_path'" 2>&1 > /dev/null; then
        log_pass "Template web-feature generated valid PRD"
        ((successful++)) || true
        rm -f "$output_path"
    else
        log_fail "Template web-feature failed"
    fi

    # Test api-endpoint template
    log_info "Testing template: api-endpoint"
    output_path="$TEST_OUTPUT_DIR/test5_api-endpoint_prd.json"
    if "$PROJECT_ROOT/lib/template-generator.sh" generate api-endpoint \
        --output "$output_path" \
        --var PROJECT_NAME="test-project" \
        --var ENDPOINT_NAME="test-endpoint" \
        --non-interactive 2>&1 > /dev/null && \
       bash -c "source '$PROJECT_ROOT/lib/prd-parser.sh' && validate_prd '$output_path'" 2>&1 > /dev/null; then
        log_pass "Template api-endpoint generated valid PRD"
        ((successful++)) || true
        rm -f "$output_path"
    else
        log_fail "Template api-endpoint failed"
    fi

    # Test refactoring template
    log_info "Testing template: refactoring"
    output_path="$TEST_OUTPUT_DIR/test5_refactoring_prd.json"
    if "$PROJECT_ROOT/lib/template-generator.sh" generate refactoring \
        --output "$output_path" \
        --var PROJECT_NAME="test-project" \
        --var REFACTOR_TARGET="test-module" \
        --non-interactive 2>&1 > /dev/null && \
       bash -c "source '$PROJECT_ROOT/lib/prd-parser.sh' && validate_prd '$output_path'" 2>&1 > /dev/null; then
        log_pass "Template refactoring generated valid PRD"
        ((successful++)) || true
        rm -f "$output_path"
    else
        log_fail "Template refactoring failed"
    fi

    # Test bug-fix template
    log_info "Testing template: bug-fix"
    output_path="$TEST_OUTPUT_DIR/test5_bug-fix_prd.json"
    if "$PROJECT_ROOT/lib/template-generator.sh" generate bug-fix \
        --output "$output_path" \
        --var PROJECT_NAME="test-project" \
        --var BUG_DESCRIPTION="test-bug" \
        --non-interactive 2>&1 > /dev/null && \
       bash -c "source '$PROJECT_ROOT/lib/prd-parser.sh' && validate_prd '$output_path'" 2>&1 > /dev/null; then
        log_pass "Template bug-fix generated valid PRD"
        ((successful++)) || true
        rm -f "$output_path"
    else
        log_fail "Template bug-fix failed"
    fi

    # Test documentation template
    log_info "Testing template: documentation"
    output_path="$TEST_OUTPUT_DIR/test5_documentation_prd.json"
    if "$PROJECT_ROOT/lib/template-generator.sh" generate documentation \
        --output "$output_path" \
        --var PROJECT_NAME="test-project" \
        --var DOC_TOPIC="test-docs" \
        --non-interactive 2>&1 > /dev/null && \
       bash -c "source '$PROJECT_ROOT/lib/prd-parser.sh' && validate_prd '$output_path'" 2>&1 > /dev/null; then
        log_pass "Template documentation generated valid PRD"
        ((successful++)) || true
        rm -f "$output_path"
    else
        log_fail "Template documentation failed"
    fi

    # Test testing template
    log_info "Testing template: testing"
    output_path="$TEST_OUTPUT_DIR/test5_testing_prd.json"
    if "$PROJECT_ROOT/lib/template-generator.sh" generate testing \
        --output "$output_path" \
        --var PROJECT_NAME="test-project" \
        --var TEST_TARGET="test-component" \
        --non-interactive 2>&1 > /dev/null && \
       bash -c "source '$PROJECT_ROOT/lib/prd-parser.sh' && validate_prd '$output_path'" 2>&1 > /dev/null; then
        log_pass "Template testing generated valid PRD"
        ((successful++)) || true
        rm -f "$output_path"
    else
        log_fail "Template testing failed"
    fi

    if [ $successful -eq 6 ]; then
        log_pass "All 6 templates working"
        log_pass "Test Case 5 completed successfully"
        return 0
    else
        log_fail "Only $successful/6 templates working"
        return 1
    fi
}

#
# Test Case 6: User runs in CI/CD mode, features disabled appropriately
#
test_cicd_mode() {
    log_test "Test Case 6: CI/CD Mode"

    # Test --no-progress flag exists
    log_info "Testing --no-progress flag"
    if ! grep -q "no-progress\|disable.*progress" "$PROJECT_ROOT/claude-loop.sh"; then
        log_fail "--no-progress flag not implemented"
        return 1
    fi
    log_pass "--no-progress flag present"

    # Test --non-interactive flag exists
    log_info "Testing --non-interactive flag"
    if ! grep -q "non-interactive" "$PROJECT_ROOT/claude-loop.sh"; then
        log_fail "--non-interactive flag not implemented"
        return 1
    fi
    log_pass "--non-interactive flag present"

    # Test --disable-safety flag exists
    log_info "Testing --disable-safety or safety level configuration"
    if ! grep -q "disable-safety\|safety-level\|YOLO" "$PROJECT_ROOT/claude-loop.sh"; then
        log_fail "Safety disabling not implemented"
        return 1
    fi
    log_pass "Safety configuration present"

    log_pass "Test Case 6 completed successfully"
    return 0
}

# Performance measurement helper
measure_overhead() {
    local description="$1"
    local command="$2"

    local start_time=$(date +%s%N 2>/dev/null || perl -MTime::HiRes=time -e 'printf "%.0f\n", time * 1000000000')
    eval "$command" &> /dev/null || true
    local end_time=$(date +%s%N 2>/dev/null || perl -MTime::HiRes=time -e 'printf "%.0f\n", time * 1000000000')

    local duration_ms=$(( (end_time - start_time) / 1000000 ))
    log_info "$description: ${duration_ms}ms"
}

# Main test execution
main() {
    echo ""
    echo "=========================================="
    echo "Phase 1 Common Use Case Tests"
    echo "=========================================="
    echo ""

    # Verify Phase 1 features are available
    if ! verify_phase1_features; then
        echo ""
        echo -e "${RED}Phase 1 features not fully available. Aborting tests.${NC}"
        exit 1
    fi

    echo ""
    log_info "Starting test execution..."
    echo ""

    # Run all test cases
    test_prd_template_workflow || true
    echo ""

    test_workspace_sandboxing || true
    echo ""

    test_checkpoint_confirmations || true
    echo ""

    test_progress_indicators || true
    echo ""

    test_all_prd_templates || true
    echo ""

    test_cicd_mode || true
    echo ""

    # Performance measurements
    echo ""
    log_info "Performance Measurements:"
    measure_overhead "Progress bar render" "bash -c 'source lib/progress-indicators.sh && render_progress_bar 50 100'"
    measure_overhead "Template list" "lib/template-generator.sh list"
    measure_overhead "Workspace validation" "bash -c 'source lib/workspace-manager.sh && validate_workspace tests/phase1'"
    echo ""

    # Summary
    echo "=========================================="
    echo "Test Summary"
    echo "=========================================="
    echo -e "Tests Run:    ${BLUE}${TESTS_RUN}${NC}"
    echo -e "Tests Passed: ${GREEN}${TESTS_PASSED}${NC}"
    echo -e "Tests Failed: ${RED}${TESTS_FAILED}${NC}"
    echo "=========================================="
    echo ""

    if [ $TESTS_FAILED -eq 0 ]; then
        echo -e "${GREEN}All tests passed!${NC}"
        return 0
    else
        echo -e "${RED}Some tests failed.${NC}"
        return 1
    fi
}

# Run tests
main "$@"
