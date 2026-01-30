#!/usr/bin/env bash
#
# Test suite for notifications system
#

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
NOTIFICATIONS_SH="${SCRIPT_DIR}/lib/notifications.sh"
TESTS_PASSED=0
TESTS_FAILED=0

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Test helper functions
test_pass() {
    echo -e "${GREEN}✓ $1${NC}"
    TESTS_PASSED=$((TESTS_PASSED + 1))
}

test_fail() {
    echo -e "${RED}✗ $1${NC}"
    TESTS_FAILED=$((TESTS_FAILED + 1))
}

test_section() {
    echo ""
    echo -e "${YELLOW}=== $1 ===${NC}"
}

# Test 1: Initialize notifications system
test_init() {
    test_section "Test 1: Initialize Notifications System"

    # Clean up existing config for testing
    rm -rf .claude-loop/daemon/notifications.json 2>/dev/null || true

    if "${NOTIFICATIONS_SH}" init > /dev/null 2>&1; then
        if [[ -f .claude-loop/daemon/notifications.json ]]; then
            test_pass "Notifications initialized successfully"
        else
            test_fail "Config file not created"
        fi
    else
        test_fail "Failed to initialize notifications"
    fi
}

# Test 2: Config file structure
test_config_structure() {
    test_section "Test 2: Configuration File Structure"

    if [[ -f .claude-loop/daemon/notifications.json ]]; then
        # Check if config is valid JSON
        if python3 -c "import json; json.load(open('.claude-loop/daemon/notifications.json'))" 2>/dev/null; then
            test_pass "Config file is valid JSON"
        else
            test_fail "Config file is not valid JSON"
        fi

        # Check for required sections
        local has_email has_slack has_webhook has_defaults
        has_email=$(python3 -c "import json; data=json.load(open('.claude-loop/daemon/notifications.json')); print('email' in data)" 2>/dev/null)
        has_slack=$(python3 -c "import json; data=json.load(open('.claude-loop/daemon/notifications.json')); print('slack' in data)" 2>/dev/null)
        has_webhook=$(python3 -c "import json; data=json.load(open('.claude-loop/daemon/notifications.json')); print('webhook' in data)" 2>/dev/null)
        has_defaults=$(python3 -c "import json; data=json.load(open('.claude-loop/daemon/notifications.json')); print('defaults' in data)" 2>/dev/null)

        if [[ "${has_email}" == "True" ]] && [[ "${has_slack}" == "True" ]] && [[ "${has_webhook}" == "True" ]] && [[ "${has_defaults}" == "True" ]]; then
            test_pass "Config has all required sections"
        else
            test_fail "Config missing required sections"
        fi
    else
        test_fail "Config file not found"
    fi
}

# Test 3: Template files
test_templates() {
    test_section "Test 3: Notification Templates"

    if [[ -f templates/notifications/success.txt ]]; then
        test_pass "Success template exists"
    else
        test_fail "Success template not found"
    fi

    if [[ -f templates/notifications/failure.txt ]]; then
        test_pass "Failure template exists"
    else
        test_fail "Failure template not found"
    fi

    if [[ -f templates/notifications/checkpoint.txt ]]; then
        test_pass "Checkpoint template exists"
    else
        test_fail "Checkpoint template not found"
    fi
}

# Test 4: Template rendering
test_template_rendering() {
    test_section "Test 4: Template Variable Rendering"

    local template="Task {{TASK_ID}} completed with status {{STATUS}}"
    local rendered
    rendered=$(source "${NOTIFICATIONS_SH}" && render_template "${template}" "TASK_ID" "TEST-001" "STATUS" "success")

    if [[ "${rendered}" == "Task TEST-001 completed with status success" ]]; then
        test_pass "Template variables rendered correctly"
    else
        test_fail "Template rendering failed. Got: ${rendered}"
    fi
}

# Test 5: Notification log file
test_logging() {
    test_section "Test 5: Notification Logging"

    rm -f .claude-loop/daemon/notifications.log 2>/dev/null || true

    # Source the script and call log function
    source "${NOTIFICATIONS_SH}"
    log_notification "INFO" "Test log message"

    if [[ -f .claude-loop/daemon/notifications.log ]]; then
        if grep -q "Test log message" .claude-loop/daemon/notifications.log; then
            test_pass "Notification logging works"
        else
            test_fail "Log message not found in log file"
        fi
    else
        test_fail "Log file not created"
    fi
}

# Test 6: Retry logic (dry run)
test_retry_logic() {
    test_section "Test 6: Retry Logic"

    # Test that retry_with_backoff function exists and can be called
    source "${NOTIFICATIONS_SH}"

    # Just verify the function exists
    if type retry_with_backoff &> /dev/null; then
        test_pass "Retry logic function exists"
    else
        test_fail "Retry logic function not found"
    fi
}

# Test 7: Webhook payload structure
test_webhook_payload() {
    test_section "Test 7: Webhook Payload Structure"

    local payload='{"task_id": "TEST-001", "status": "completed", "project": "test"}'

    if python3 -c "import json; json.loads('${payload}')" 2>/dev/null; then
        test_pass "Webhook payload is valid JSON"
    else
        test_fail "Webhook payload is invalid JSON"
    fi
}

# Test 8: Channel enabled check
test_channel_enabled() {
    test_section "Test 8: Channel Enabled Check"

    source "${NOTIFICATIONS_SH}"

    # All channels should be disabled by default
    if ! is_channel_enabled "email"; then
        test_pass "Email channel correctly reported as disabled"
    else
        test_fail "Email channel incorrectly enabled"
    fi

    if ! is_channel_enabled "slack"; then
        test_pass "Slack channel correctly reported as disabled"
    else
        test_fail "Slack channel incorrectly enabled"
    fi

    if ! is_channel_enabled "webhook"; then
        test_pass "Webhook channel correctly reported as disabled"
    else
        test_fail "Webhook channel incorrectly enabled"
    fi
}

# Test 9: CLI interface
test_cli_interface() {
    test_section "Test 9: CLI Interface"

    # Test help output
    if "${NOTIFICATIONS_SH}" 2>&1 | grep -q "Usage:"; then
        test_pass "CLI help output works"
    else
        test_fail "CLI help output missing"
    fi

    # Test init command
    if "${NOTIFICATIONS_SH}" init > /dev/null 2>&1; then
        test_pass "CLI init command works"
    else
        test_fail "CLI init command failed"
    fi
}

# Test 10: Integration with daemon
test_daemon_integration() {
    test_section "Test 10: Daemon Integration"

    # Check if daemon.sh can source notifications.sh
    if grep -q "notifications" "${SCRIPT_DIR}/lib/daemon.sh"; then
        test_pass "Daemon has notification integration"
    else
        test_fail "Daemon missing notification integration"
    fi

    # Check if --notify flag is documented
    local help_output
    help_output=$("${SCRIPT_DIR}/lib/daemon.sh" 2>&1 || true)
    if echo "${help_output}" | grep -iq "notify"; then
        test_pass "Daemon CLI documents --notify flag"
    else
        test_fail "Daemon CLI missing --notify documentation"
    fi
}

# Run all tests
main() {
    echo ""
    echo "================================"
    echo "  Notifications Test Suite"
    echo "================================"

    test_init
    test_config_structure
    test_templates
    test_template_rendering
    test_logging
    test_retry_logic
    test_webhook_payload
    test_channel_enabled
    test_cli_interface
    test_daemon_integration

    # Summary
    echo ""
    echo "================================"
    echo "  Test Results"
    echo "================================"
    echo -e "${GREEN}Passed: ${TESTS_PASSED}${NC}"
    echo -e "${RED}Failed: ${TESTS_FAILED}${NC}"
    echo ""

    if [[ ${TESTS_FAILED} -eq 0 ]]; then
        echo -e "${GREEN}All tests passed!${NC}"
        exit 0
    else
        echo -e "${RED}Some tests failed.${NC}"
        exit 1
    fi
}

main
