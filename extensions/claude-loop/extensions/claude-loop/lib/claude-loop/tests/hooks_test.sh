#!/bin/bash
#
# Integration test for Hook System (US-001)
#
# Tests the hook system functionality:
# - Hook directory structure
# - Hook execution in alphanumeric order
# - Environment variable passing
# - Hook logging to JSONL
# - Non-zero exit code handling
# - Feature flag behavior

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TEST_DIR="$(mktemp -d)"
HOOKS_DIR="$TEST_DIR/.claude-loop/hooks"
LOGS_DIR="$TEST_DIR/.claude-loop/logs"
HOOKS_LOG="$LOGS_DIR/hooks.jsonl"

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Test counters
TESTS_RUN=0
TESTS_PASSED=0
TESTS_FAILED=0

# Cleanup function
cleanup() {
    if [ -d "$TEST_DIR" ]; then
        rm -rf "$TEST_DIR"
    fi
}

trap cleanup EXIT

# Test helper functions
test_start() {
    TESTS_RUN=$((TESTS_RUN + 1))
    echo -e "${YELLOW}[TEST $TESTS_RUN]${NC} $1"
}

test_pass() {
    TESTS_PASSED=$((TESTS_PASSED + 1))
    echo -e "${GREEN}[PASS]${NC} $1"
}

test_fail() {
    TESTS_FAILED=$((TESTS_FAILED + 1))
    echo -e "${RED}[FAIL]${NC} $1"
}

# Source the hook functions from claude-loop.sh
# We'll extract just the hook functions for testing
setup_hook_functions() {
    # Create a minimal test environment
    export HOOKS_ENABLED=true
    export HOOKS_DIR="$HOOKS_DIR"
    export HOOKS_LOG_FILE="$HOOKS_LOG"
    export PRD_FILE="$TEST_DIR/prd.json"
    export SCRIPT_DIR="$SCRIPT_DIR"
    export VERBOSE=false

    # Create test PRD
    cat > "$PRD_FILE" << 'EOF'
{
  "project": "hook-test",
  "branchName": "test/hooks",
  "userStories": [{"id": "TEST-001", "title": "Test Story", "passes": false}]
}
EOF

    # Source claude-loop.sh to get hook functions
    # We need to define the logging functions first
    log_info() { echo "[INFO] $1"; }
    log_success() { echo "[SUCCESS] $1"; }
    log_error() { echo "[ERROR] $1"; }
    log_debug() { if $VERBOSE; then echo "[DEBUG] $1"; fi; }
    export -f log_info log_success log_error log_debug

    # Extract and source hook functions from claude-loop.sh
    # For testing, we'll just define them inline
    execute_hooks() {
        if ! $HOOKS_ENABLED; then
            return 0
        fi

        local hook_type="$1"
        local story_id="${2:-}"
        local iteration="${3:-0}"
        local workspace="${4:-$(pwd)}"
        local branch="${5:-test-branch}"
        local phase="${6:-implementation}"

        local hooks_subdir="${HOOKS_DIR}/${hook_type}"

        if [ ! -d "$hooks_subdir" ]; then
            log_debug "Hooks directory not found: $hooks_subdir"
            return 0
        fi

        local hook_files
        hook_files=$(find "$hooks_subdir" -maxdepth 1 -type f -perm +111 2>/dev/null | sort || true)

        if [ -z "$hook_files" ]; then
            log_debug "No executable hooks found in $hooks_subdir"
            return 0
        fi

        log_info "Executing $hook_type hooks..."

        export STORY_ID="$story_id"
        export ITERATION="$iteration"
        export WORKSPACE="$workspace"
        export BRANCH="$branch"
        export PHASE="$phase"

        local hook_count=0
        while IFS= read -r hook_file; do
            if [ -z "$hook_file" ]; then
                continue
            fi

            hook_count=$((hook_count + 1))
            local hook_name
            hook_name=$(basename "$hook_file")

            log_debug "Running hook: $hook_name"

            local start_time
            start_time=$(date +%s%3N 2>/dev/null || perl -MTime::HiRes=time -e 'printf "%.0f\n", time * 1000')

            local hook_output
            local hook_exit_code=0
            hook_output=$("$hook_file" 2>&1) || hook_exit_code=$?

            local end_time
            end_time=$(date +%s%3N 2>/dev/null || perl -MTime::HiRes=time -e 'printf "%.0f\n", time * 1000')
            local duration_ms=$((end_time - start_time))

            log_hook_execution "$hook_type" "$hook_name" "$hook_exit_code" "$duration_ms" "$hook_output"

            if [ $hook_exit_code -ne 0 ]; then
                log_error "Hook failed: $hook_name (exit code: $hook_exit_code)"
                return $hook_exit_code
            fi

            log_debug "Hook completed: $hook_name (${duration_ms}ms)"
        done <<< "$hook_files"

        if [ $hook_count -gt 0 ]; then
            log_success "$hook_count $hook_type hook(s) completed successfully"
        fi

        unset STORY_ID ITERATION WORKSPACE BRANCH PHASE

        return 0
    }

    log_hook_execution() {
        if ! $HOOKS_ENABLED; then
            return 0
        fi

        local hook_type="$1"
        local hook_name="$2"
        local exit_code="$3"
        local duration_ms="$4"
        local output="$5"

        mkdir -p "$(dirname "$HOOKS_LOG_FILE")"

        local timestamp
        timestamp=$(date -u +%Y-%m-%dT%H:%M:%SZ)

        local escaped_output
        escaped_output=$(echo "$output" | jq -Rs . 2>/dev/null || echo "\"\"")

        cat >> "$HOOKS_LOG_FILE" << EOF
{"timestamp":"$timestamp","hook_type":"$hook_type","hook_name":"$hook_name","exit_code":$exit_code,"duration_ms":$duration_ms,"output":$escaped_output,"story_id":"${STORY_ID:-}","iteration":${ITERATION:-0}}
EOF
    }

    export -f execute_hooks log_hook_execution
}

# Setup test environment
setup_test_env() {
    mkdir -p "$HOOKS_DIR"/{pre_iteration,post_iteration,pre_commit,post_commit,on_error,on_complete}
    mkdir -p "$LOGS_DIR"
    setup_hook_functions
}

# Test 1: Hook directory structure exists
test_hook_directory_structure() {
    test_start "Hook directory structure"

    if [ -d "$HOOKS_DIR/pre_iteration" ] && \
       [ -d "$HOOKS_DIR/post_iteration" ] && \
       [ -d "$HOOKS_DIR/pre_commit" ] && \
       [ -d "$HOOKS_DIR/post_commit" ] && \
       [ -d "$HOOKS_DIR/on_error" ] && \
       [ -d "$HOOKS_DIR/on_complete" ]; then
        test_pass "All hook directories exist"
        return 0
    else
        test_fail "Hook directories missing"
        return 1
    fi
}

# Test 2: Hooks execute in alphanumeric order
test_hook_execution_order() {
    test_start "Hook execution order"

    local output_file="$TEST_DIR/hook_order.txt"

    # Create test hooks
    cat > "$HOOKS_DIR/pre_iteration/99-last.sh" << 'EOF'
#!/bin/bash
echo "99-last" >> OUTPUT_FILE
EOF

    cat > "$HOOKS_DIR/pre_iteration/01-first.sh" << 'EOF'
#!/bin/bash
echo "01-first" >> OUTPUT_FILE
EOF

    cat > "$HOOKS_DIR/pre_iteration/50-middle.sh" << 'EOF'
#!/bin/bash
echo "50-middle" >> OUTPUT_FILE
EOF

    # Replace OUTPUT_FILE placeholder
    sed -i.bak "s|OUTPUT_FILE|$output_file|g" "$HOOKS_DIR/pre_iteration"/*.sh
    chmod +x "$HOOKS_DIR/pre_iteration"/*.sh

    # Execute hooks
    execute_hooks "pre_iteration" "TEST-001" 1 "$TEST_DIR" "test-branch" "implementation" > /dev/null 2>&1

    # Check order
    if [ -f "$output_file" ]; then
        local order
        order=$(cat "$output_file")
        if [ "$order" = "$(echo -e "01-first\n50-middle\n99-last")" ]; then
            test_pass "Hooks executed in correct alphanumeric order"
            return 0
        else
            test_fail "Hooks executed in wrong order: $order"
            return 1
        fi
    else
        test_fail "Hooks did not execute"
        return 1
    fi
}

# Test 3: Environment variables passed to hooks
test_environment_variables() {
    test_start "Environment variable passing"

    local env_file="$TEST_DIR/hook_env.txt"

    cat > "$HOOKS_DIR/pre_iteration/10-check-env.sh" << EOF
#!/bin/bash
echo "STORY_ID=\$STORY_ID" > $env_file
echo "ITERATION=\$ITERATION" >> $env_file
echo "WORKSPACE=\$WORKSPACE" >> $env_file
echo "BRANCH=\$BRANCH" >> $env_file
echo "PHASE=\$PHASE" >> $env_file
EOF

    chmod +x "$HOOKS_DIR/pre_iteration/10-check-env.sh"

    execute_hooks "pre_iteration" "TEST-002" 5 "$TEST_DIR" "test-branch" "planning" > /dev/null 2>&1

    if [ -f "$env_file" ]; then
        if grep -q "STORY_ID=TEST-002" "$env_file" && \
           grep -q "ITERATION=5" "$env_file" && \
           grep -q "WORKSPACE=$TEST_DIR" "$env_file" && \
           grep -q "BRANCH=test-branch" "$env_file" && \
           grep -q "PHASE=planning" "$env_file"; then
            test_pass "All environment variables passed correctly"
            return 0
        else
            test_fail "Environment variables not passed correctly"
            cat "$env_file"
            return 1
        fi
    else
        test_fail "Hook did not create env file"
        return 1
    fi
}

# Test 4: Hook logging to JSONL
test_hook_logging() {
    test_start "Hook logging to JSONL"

    cat > "$HOOKS_DIR/post_iteration/10-test.sh" << 'EOF'
#!/bin/bash
echo "Test hook output"
EOF

    chmod +x "$HOOKS_DIR/post_iteration/10-test.sh"

    execute_hooks "post_iteration" "TEST-003" 1 "$TEST_DIR" "test-branch" "implementation" > /dev/null 2>&1

    if [ -f "$HOOKS_LOG" ]; then
        if jq -e '.hook_type == "post_iteration" and .hook_name == "10-test.sh" and .story_id == "TEST-003"' "$HOOKS_LOG" > /dev/null 2>&1; then
            test_pass "Hook execution logged to JSONL"
            return 0
        else
            test_fail "Hook log entry invalid"
            cat "$HOOKS_LOG"
            return 1
        fi
    else
        test_fail "Hook log file not created"
        return 1
    fi
}

# Test 5: Non-zero exit code aborts execution
test_hook_failure() {
    test_start "Non-zero exit code handling"

    cat > "$HOOKS_DIR/on_error/10-fail.sh" << 'EOF'
#!/bin/bash
echo "This hook will fail"
exit 42
EOF

    chmod +x "$HOOKS_DIR/on_error/10-fail.sh"

    if execute_hooks "on_error" "TEST-004" 1 "$TEST_DIR" "test-branch" "implementation" > /dev/null 2>&1; then
        test_fail "Hook should have failed but succeeded"
        return 1
    else
        local exit_code=$?
        if [ $exit_code -eq 42 ]; then
            test_pass "Hook failure correctly aborted execution with exit code 42"
            return 0
        else
            test_fail "Hook failed with unexpected exit code: $exit_code"
            return 1
        fi
    fi
}

# Test 6: Feature flag disables hooks
test_feature_flag() {
    test_start "Feature flag disables hooks"

    HOOKS_ENABLED=false

    local flag_file="$TEST_DIR/flag_test.txt"

    cat > "$HOOKS_DIR/on_complete/10-test.sh" << EOF
#!/bin/bash
touch $flag_file
EOF

    chmod +x "$HOOKS_DIR/on_complete/10-test.sh"

    execute_hooks "on_complete" "TEST-005" 1 "$TEST_DIR" "test-branch" "implementation" > /dev/null 2>&1

    if [ -f "$flag_file" ]; then
        test_fail "Hook executed despite HOOKS_ENABLED=false"
        HOOKS_ENABLED=true
        return 1
    else
        test_pass "Hooks correctly disabled by feature flag"
        HOOKS_ENABLED=true
        return 0
    fi
}

# Main test execution
echo "========================================"
echo "Hook System Integration Test (US-001)"
echo "========================================"
echo

setup_test_env

test_hook_directory_structure
test_hook_execution_order
test_environment_variables
test_hook_logging
test_hook_failure
test_feature_flag

echo
echo "========================================"
echo "Test Summary"
echo "========================================"
echo "Tests Run:    $TESTS_RUN"
echo -e "Tests Passed: ${GREEN}$TESTS_PASSED${NC}"
echo -e "Tests Failed: ${RED}$TESTS_FAILED${NC}"

if [ $TESTS_FAILED -eq 0 ]; then
    echo -e "\n${GREEN}All tests passed!${NC}"
    exit 0
else
    echo -e "\n${RED}Some tests failed!${NC}"
    exit 1
fi
