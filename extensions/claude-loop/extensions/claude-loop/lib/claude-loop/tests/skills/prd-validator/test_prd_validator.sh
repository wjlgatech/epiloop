#!/bin/bash
#
# Integration tests for prd-validator skill
#

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
VALIDATOR_SCRIPT="$PROJECT_ROOT/skills/prd-validator/scripts/main.py"

# Test counter
TESTS_RUN=0
TESTS_PASSED=0
TESTS_FAILED=0

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Helper functions
pass() {
    echo -e "${GREEN}✓ PASS${NC}: $1"
    TESTS_PASSED=$((TESTS_PASSED + 1))
    TESTS_RUN=$((TESTS_RUN + 1))
}

fail() {
    echo -e "${RED}✗ FAIL${NC}: $1"
    echo -e "  ${YELLOW}$2${NC}"
    TESTS_FAILED=$((TESTS_FAILED + 1))
    TESTS_RUN=$((TESTS_RUN + 1))
}

# Test 1: Valid PRD should pass
test_valid_prd() {
    echo "Test: Valid PRD should pass validation"

    # Create temporary valid PRD
    local temp_prd=$(mktemp)
    cat > "$temp_prd" <<'EOF'
{
  "project": "test-project",
  "branchName": "feature/test",
  "description": "Test PRD",
  "userStories": [
    {
      "id": "US-001",
      "title": "Test Story",
      "description": "Test description",
      "acceptanceCriteria": ["Criterion 1"],
      "priority": 1,
      "passes": false
    }
  ]
}
EOF

    if python3 "$VALIDATOR_SCRIPT" "$temp_prd" > /dev/null 2>&1; then
        pass "Valid PRD passes validation"
    else
        fail "Valid PRD should pass" "Validation failed unexpectedly"
    fi

    rm -f "$temp_prd"
}

# Test 2: Missing required fields should fail
test_missing_fields() {
    echo "Test: Missing required fields should fail"

    local temp_prd=$(mktemp)
    cat > "$temp_prd" <<'EOF'
{
  "project": "test-project",
  "userStories": []
}
EOF

    if python3 "$VALIDATOR_SCRIPT" "$temp_prd" > /dev/null 2>&1; then
        fail "Missing fields should fail" "Validation passed when it should have failed"
    else
        pass "Missing required fields detected"
    fi

    rm -f "$temp_prd"
}

# Test 3: Circular dependencies should be detected
test_circular_dependencies() {
    echo "Test: Circular dependencies should be detected"

    local temp_prd=$(mktemp)
    cat > "$temp_prd" <<'EOF'
{
  "project": "test-project",
  "branchName": "feature/test",
  "description": "Test PRD",
  "userStories": [
    {
      "id": "US-001",
      "title": "Story 1",
      "description": "Test",
      "acceptanceCriteria": ["Test"],
      "priority": 1,
      "passes": false,
      "dependencies": ["US-002"]
    },
    {
      "id": "US-002",
      "title": "Story 2",
      "description": "Test",
      "acceptanceCriteria": ["Test"],
      "priority": 2,
      "passes": false,
      "dependencies": ["US-001"]
    }
  ]
}
EOF

    local output=$(python3 "$VALIDATOR_SCRIPT" "$temp_prd" 2>&1 || true)

    if echo "$output" | grep -q "Circular dependency"; then
        pass "Circular dependency detected"
    else
        fail "Circular dependency not detected" "Expected 'Circular dependency' in output"
    fi

    rm -f "$temp_prd"
}

# Test 4: Invalid complexity value should be caught
test_invalid_complexity() {
    echo "Test: Invalid estimatedComplexity should be caught"

    local temp_prd=$(mktemp)
    cat > "$temp_prd" <<'EOF'
{
  "project": "test-project",
  "branchName": "feature/test",
  "description": "Test PRD",
  "userStories": [
    {
      "id": "US-001",
      "title": "Story 1",
      "description": "Test",
      "acceptanceCriteria": ["Test"],
      "priority": 1,
      "passes": false,
      "estimatedComplexity": "invalid_value"
    }
  ]
}
EOF

    local output=$(python3 "$VALIDATOR_SCRIPT" "$temp_prd" 2>&1 || true)

    if echo "$output" | grep -q "Invalid.*estimatedComplexity"; then
        pass "Invalid complexity value detected"
    else
        fail "Invalid complexity not caught" "Expected error about estimatedComplexity"
    fi

    rm -f "$temp_prd"
}

# Test 5: Script should handle non-existent file
test_nonexistent_file() {
    echo "Test: Non-existent file should be handled gracefully"

    if python3 "$VALIDATOR_SCRIPT" "/nonexistent/file.json" > /dev/null 2>&1; then
        fail "Non-existent file should fail" "Should exit with error"
    else
        pass "Non-existent file handled gracefully"
    fi
}

# Main test execution
main() {
    echo "========================================"
    echo "PRD Validator Integration Tests"
    echo "========================================"
    echo ""

    # Check if validator script exists
    if [[ ! -f "$VALIDATOR_SCRIPT" ]]; then
        echo -e "${RED}ERROR${NC}: Validator script not found: $VALIDATOR_SCRIPT"
        exit 1
    fi

    # Run tests
    test_valid_prd
    test_missing_fields
    test_circular_dependencies
    test_invalid_complexity
    test_nonexistent_file

    # Summary
    echo ""
    echo "========================================"
    echo "Test Summary"
    echo "========================================"
    echo "Tests run: $TESTS_RUN"
    echo -e "${GREEN}Passed: $TESTS_PASSED${NC}"
    echo -e "${RED}Failed: $TESTS_FAILED${NC}"
    echo "========================================"

    # Exit with failure if any tests failed
    if [[ $TESTS_FAILED -gt 0 ]]; then
        exit 1
    fi

    exit 0
}

main "$@"
