#!/bin/bash
#
# test_prd_generator.sh - Test suite for prd-generator.py (US-004)
#
# Tests dynamic PRD generation from natural language goals
#

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
PRD_GENERATOR="$PROJECT_ROOT/lib/prd-generator.py"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

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

# Cleanup function
cleanup() {
    rm -f "$PROJECT_ROOT"/prd-test-*.json
    rm -f "$PROJECT_ROOT"/goal-test-*.txt
}

trap cleanup EXIT

# ============================================================================
# Test Cases
# ============================================================================

# Test 1: Script exists and is executable
test_script_exists() {
    run_test "Script exists and is executable"

    if [ ! -f "$PRD_GENERATOR" ]; then
        log_fail "prd-generator.py not found at $PRD_GENERATOR"
        return
    fi

    if [ ! -x "$PRD_GENERATOR" ]; then
        log_fail "prd-generator.py is not executable"
        return
    fi

    log_pass "Script exists and is executable"
}

# Test 2: Script shows help
test_help_command() {
    run_test "Help command works"

    if ! python3 "$PRD_GENERATOR" --help > /dev/null 2>&1; then
        log_fail "Help command failed"
        return
    fi

    log_pass "Help command works"
}

# Test 3: Generate command requires goal
test_generate_requires_goal() {
    run_test "Generate command requires goal"

    if python3 "$PRD_GENERATOR" generate > /dev/null 2>&1; then
        log_fail "Generate should fail without goal"
        return
    fi

    log_pass "Generate command properly requires goal"
}

# Test 4: Validate command works
test_validate_command() {
    run_test "Validate command works with valid PRD"

    # Create a valid test PRD
    local test_prd="$PROJECT_ROOT/prd-test-validate.json"
    cat > "$test_prd" << 'EOF'
{
  "project": "test-validation",
  "branchName": "feature/test-validation",
  "description": "Test validation",
  "userStories": [
    {
      "id": "US-001",
      "title": "Test story",
      "description": "As a tester, I want validation so that tests pass",
      "acceptanceCriteria": ["Criterion 1", "Criterion 2", "Criterion 3"],
      "priority": 1,
      "dependencies": [],
      "fileScope": [],
      "estimatedComplexity": "simple",
      "passes": false,
      "notes": ""
    }
  ],
  "complexity": 1,
  "estimatedDuration": "2-4 hours",
  "successMetrics": {
    "test": "passes"
  }
}
EOF

    if ! python3 "$PRD_GENERATOR" validate "$test_prd" > /dev/null 2>&1; then
        log_fail "Validate command failed on valid PRD"
        return
    fi

    log_pass "Validate command works with valid PRD"
}

# Test 5: Validate detects missing fields
test_validate_detects_errors() {
    run_test "Validate detects missing required fields"

    # Create an invalid test PRD (missing userStories)
    local test_prd="$PROJECT_ROOT/prd-test-invalid.json"
    cat > "$test_prd" << 'EOF'
{
  "project": "test-invalid",
  "branchName": "feature/test-invalid",
  "description": "Test invalid PRD"
}
EOF

    if python3 "$PRD_GENERATOR" validate "$test_prd" > /dev/null 2>&1; then
        log_fail "Validate should fail on invalid PRD"
        return
    fi

    log_pass "Validate properly detects missing fields"
}

# Test 6: Python module imports
test_python_imports() {
    run_test "Python module can be imported"

    if ! python3 -c "import sys; sys.path.insert(0, '$PROJECT_ROOT/lib'); import importlib.util; spec = importlib.util.spec_from_file_location('prd_generator', '$PRD_GENERATOR'); module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)" 2>&1; then
        log_fail "Python module import failed"
        return
    fi

    log_pass "Python module imports successfully"
}

# Test 7: Kebab case function
test_kebab_case() {
    run_test "Kebab case conversion"

    local result
    result=$(python3 -c "import sys; sys.path.insert(0, '$PROJECT_ROOT/lib'); import importlib.util; spec = importlib.util.spec_from_file_location('prd_generator', '$PRD_GENERATOR'); module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module); print(module.kebab_case('User Authentication with JWT'))")

    if [ "$result" != "user-authentication-with-jwt" ]; then
        log_fail "Kebab case conversion failed: got '$result'"
        return
    fi

    log_pass "Kebab case conversion works"
}

# Test 8: Extract JSON from response
test_json_extraction() {
    run_test "JSON extraction from Claude response"

    # Write test response to file to avoid quoting issues
    local test_file="$PROJECT_ROOT/test-json-response.txt"
    cat > "$test_file" << 'EOF'
Here is the JSON:
{
  "test": "value",
  "nested": {
    "key": "data"
  }
}
That was the JSON.
EOF

    local result
    result=$(python3 -c "import sys, json; sys.path.insert(0, '$PROJECT_ROOT/lib'); import importlib.util; spec = importlib.util.spec_from_file_location('prd_generator', '$PRD_GENERATOR'); module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module); response = open('$test_file').read(); data = module.extract_json_from_response(response); print(json.dumps(data))" 2>&1)

    rm -f "$test_file"

    if ! echo "$result" | jq -e '.test == "value"' > /dev/null 2>&1; then
        log_fail "JSON extraction failed: $result"
        return
    fi

    log_pass "JSON extraction works"
}

# Test 9: File scope inference
test_file_scope_inference() {
    run_test "File scope inference from codebase"

    local result
    result=$(python3 -c "import sys, json; sys.path.insert(0, '$PROJECT_ROOT/lib'); import importlib.util; spec = importlib.util.spec_from_file_location('prd_generator', '$PRD_GENERATOR'); module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module); structure = {'languages': ['python'], 'directories': ['lib', 'tests'], 'file_patterns': {'.py': 50}}; stories = [{'id': 'US-001', 'title': 'Add tests', 'description': 'As a dev I want tests'}]; result = module.estimate_file_scopes_from_codebase(stories, structure); print(json.dumps(result))" 2>&1)

    if ! echo "$result" | jq -e '.[0].fileScope | length > 0' > /dev/null 2>&1; then
        log_fail "File scope inference failed"
        return
    fi

    log_pass "File scope inference works"
}

# Test 10: Dependency inference
test_dependency_inference() {
    run_test "Dependency inference from story order"

    local result
    result=$(python3 -c "import sys, json; sys.path.insert(0, '$PROJECT_ROOT/lib'); import importlib.util; spec = importlib.util.spec_from_file_location('prd_generator', '$PRD_GENERATOR'); module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module); stories = [{'id': 'US-001', 'title': 'Create model', 'description': 'database schema'}, {'id': 'US-002', 'title': 'Add tests', 'description': 'test the API'}, {'id': 'US-003', 'title': 'Integration tests', 'description': 'integration testing'}]; result = module.infer_dependencies(stories); print(json.dumps(result))" 2>&1)

    # US-002 and US-003 should have dependencies
    if ! echo "$result" | jq -e '.[1].dependencies | length > 0' > /dev/null 2>&1; then
        log_fail "Dependency inference failed"
        return
    fi

    log_pass "Dependency inference works"
}

# Test 11: Codebase analysis
test_codebase_analysis() {
    run_test "Codebase structure analysis"

    local result
    result=$(python3 -c "import sys, json; sys.path.insert(0, '$PROJECT_ROOT/lib'); import importlib.util; spec = importlib.util.spec_from_file_location('prd_generator', '$PRD_GENERATOR'); module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module); structure = module.analyze_codebase_structure(); print(json.dumps(structure))" 2>&1)

    if ! echo "$result" | jq -e '.languages | length > 0' > /dev/null 2>&1; then
        log_fail "Codebase analysis failed: $result"
        return
    fi

    log_pass "Codebase analysis works"
}

# Test 12: Complexity detector integration
test_complexity_integration() {
    run_test "Complexity detector integration"

    # Check if complexity-detector.py exists
    local complexity_detector="$PROJECT_ROOT/lib/complexity-detector.py"
    if [ ! -f "$complexity_detector" ]; then
        log_fail "complexity-detector.py not found"
        return
    fi

    # Test that it can be called
    if ! python3 "$complexity_detector" levels > /dev/null 2>&1; then
        log_fail "complexity-detector.py execution failed"
        return
    fi

    log_pass "Complexity detector integration works"
}

# Test 13: UserStory dataclass
test_user_story_dataclass() {
    run_test "UserStory dataclass structure"

    python3 -c "import sys; sys.path.insert(0, '$PROJECT_ROOT/lib'); import importlib.util; spec = importlib.util.spec_from_file_location('prd_generator', '$PRD_GENERATOR'); module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module); story = module.UserStory(id='US-001', title='Test', description='Test story', acceptanceCriteria=['AC1', 'AC2'], priority=1, dependencies=[], fileScope=[], estimatedComplexity='simple'); assert story.id == 'US-001'" 2>&1

    if [ $? -ne 0 ]; then
        log_fail "UserStory dataclass failed"
        return
    fi

    log_pass "UserStory dataclass works"
}

# Test 14: PRDDocument dataclass
test_prd_document_dataclass() {
    run_test "PRDDocument dataclass structure"

    python3 -c "import sys; sys.path.insert(0, '$PROJECT_ROOT/lib'); import importlib.util; spec = importlib.util.spec_from_file_location('prd_generator', '$PRD_GENERATOR'); module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module); story = module.UserStory(id='US-001', title='Test', description='Test story', acceptanceCriteria=['AC1'], priority=1, dependencies=[], fileScope=[], estimatedComplexity='simple'); prd = module.PRDDocument(project='test', branchName='feature/test', description='Test PRD', userStories=[story], complexity=1, estimatedDuration='2-4 hours', successMetrics={}); assert prd.project == 'test'" 2>&1

    if [ $? -ne 0 ]; then
        log_fail "PRDDocument dataclass failed"
        return
    fi

    log_pass "PRDDocument dataclass works"
}

# Test 15: CLI argument parsing
test_cli_parsing() {
    run_test "CLI argument parsing"

    # Test that various CLI patterns work
    if ! python3 "$PRD_GENERATOR" generate --help > /dev/null 2>&1; then
        log_fail "Generate subcommand help failed"
        return
    fi

    if ! python3 "$PRD_GENERATOR" validate --help > /dev/null 2>&1; then
        log_fail "Validate subcommand help failed"
        return
    fi

    log_pass "CLI argument parsing works"
}

# ============================================================================
# Run all tests
# ============================================================================

main() {
    echo "╔════════════════════════════════════════════════════════════════╗"
    echo "║          PRD Generator Test Suite (US-004)                     ║"
    echo "╚════════════════════════════════════════════════════════════════╝"
    echo ""

    # Run tests
    test_script_exists
    test_help_command
    test_generate_requires_goal
    test_validate_command
    test_validate_detects_errors
    test_python_imports
    test_kebab_case
    test_json_extraction
    test_file_scope_inference
    test_dependency_inference
    test_codebase_analysis
    test_complexity_integration
    test_user_story_dataclass
    test_prd_document_dataclass
    test_cli_parsing

    # Summary
    echo ""
    echo "╔════════════════════════════════════════════════════════════════╗"
    echo "║                       Test Summary                             ║"
    echo "╚════════════════════════════════════════════════════════════════╝"
    echo ""
    echo "Tests run:    $TESTS_RUN"
    echo -e "${GREEN}Tests passed: $TESTS_PASSED${NC}"
    echo -e "${RED}Tests failed: $TESTS_FAILED${NC}"
    echo ""

    if [ $TESTS_FAILED -eq 0 ]; then
        echo -e "${GREEN}✓ All tests passed!${NC}"
        exit 0
    else
        echo -e "${RED}✗ Some tests failed${NC}"
        exit 1
    fi
}

main "$@"
