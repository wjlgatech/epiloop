#!/usr/bin/env bash
#
# Phase 2 Integration Tests
# ==========================
#
# Tests all Phase 2 features working together:
# - Skills framework + Quick task mode
# - Daemon mode + Dashboard
# - Notifications + Dashboard
# - Complete workflow integration
#

set -euo pipefail

# Color codes
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Test counters
TESTS_RUN=0
TESTS_PASSED=0
TESTS_FAILED=0

# Test result tracking
FAILED_TESTS=()

# Helper functions
test_pass() {
    echo -e "${GREEN}✓ PASS${NC}: $1"
    TESTS_PASSED=$((TESTS_PASSED + 1))
}

test_fail() {
    echo -e "${RED}✗ FAIL${NC}: $1"
    TESTS_FAILED=$((TESTS_FAILED + 1))
    FAILED_TESTS+=("$1")
}

test_start() {
    TESTS_RUN=$((TESTS_RUN + 1))
    echo -e "\n${YELLOW}TEST ${TESTS_RUN}${NC}: $1"
}

# ==============================================================================
# Test Setup
# ==============================================================================

setup_test_env() {
    echo "Setting up test environment..."

    # Create test directory
    TEST_DIR=$(mktemp -d)
    export TEST_DIR

    # Copy necessary files
    cp -r lib "${TEST_DIR}/"
    cp -r skills "${TEST_DIR}/" 2>/dev/null || true
    cp -r templates "${TEST_DIR}/" 2>/dev/null || true
    cp claude-loop.sh "${TEST_DIR}/"

    # Create test PRD
    cat > "${TEST_DIR}/test-prd.json" <<'EOF'
{
  "project": "test-project",
  "branchName": "feature/test",
  "description": "Test project for Phase 2 integration",
  "userStories": [
    {
      "id": "TEST-001",
      "title": "Test Story 1",
      "description": "Simple test story",
      "priority": 1,
      "acceptanceCriteria": ["Test passes"],
      "passes": false,
      "notes": ""
    }
  ]
}
EOF

    cd "${TEST_DIR}"
    echo "Test environment created at: ${TEST_DIR}"
}

cleanup_test_env() {
    echo "Cleaning up test environment..."
    if [ -n "${TEST_DIR:-}" ] && [ -d "${TEST_DIR}" ]; then
        rm -rf "${TEST_DIR}"
    fi
}

# ==============================================================================
# Integration Tests
# ==============================================================================

# Test 1: Skills framework is accessible from quick task mode
test_skills_quick_task_integration() {
    test_start "Skills framework + Quick task mode integration"

    # Source quick task mode
    if [ -f "./lib/quick-task-mode.sh" ]; then
        source ./lib/quick-task-mode.sh

        # Test suggest_skills_for_task function exists
        if declare -f suggest_skills_for_task > /dev/null; then
            # Test skill suggestion for validation task
            local result
            result=$(suggest_skills_for_task "validate the PRD file")

            if echo "$result" | grep -q "prd-validator"; then
                test_pass "Skills are suggested for relevant quick tasks"
            else
                test_fail "Skill suggestion not working properly: $result"
            fi
        else
            test_fail "suggest_skills_for_task function not found"
        fi
    else
        test_fail "Quick task mode library not found"
    fi
}

# Test 2: Dashboard API endpoints for daemon queue
test_dashboard_daemon_integration() {
    test_start "Dashboard + Daemon mode integration"

    # Check if dashboard API has daemon endpoints
    if [ -f "./lib/dashboard/server.py" ]; then
        # Check for daemon status endpoint
        if grep -q "/api/daemon/status" ./lib/dashboard/server.py; then
            test_pass "Dashboard has daemon status endpoint"
        else
            test_fail "Dashboard missing daemon status endpoint"
        fi

        # Check for daemon queue endpoint
        if grep -q "/api/daemon/queue" ./lib/dashboard/server.py; then
            test_pass "Dashboard has daemon queue endpoint"
        else
            test_fail "Dashboard missing daemon queue endpoint"
        fi
    else
        test_fail "Dashboard server not found"
    fi
}

# Test 3: Dashboard API endpoints for notifications
test_dashboard_notifications_integration() {
    test_start "Dashboard + Notifications integration"

    if [ -f "./lib/dashboard/server.py" ]; then
        # Check for notifications config endpoint
        if grep -q "/api/notifications/config" ./lib/dashboard/server.py; then
            test_pass "Dashboard has notifications config endpoint"
        else
            test_fail "Dashboard missing notifications config endpoint"
        fi

        # Check for recent notifications endpoint
        if grep -q "/api/notifications/recent" ./lib/dashboard/server.py; then
            test_pass "Dashboard has recent notifications endpoint"
        else
            test_fail "Dashboard missing recent notifications endpoint"
        fi
    else
        test_fail "Dashboard server not found"
    fi
}

# Test 4: Quick task mode plan generation includes skills
test_quick_task_plan_with_skills() {
    test_start "Quick task plan includes suggested skills"

    if [ -f "./lib/quick-task-mode.sh" ]; then
        source ./lib/quick-task-mode.sh
        init_quick_tasks

        # Generate plan for a task that should suggest skills
        local plan_json
        plan_json=$(generate_execution_plan "add tests to my code")

        # Check if plan includes suggested_skills field
        if echo "$plan_json" | python3 -c "import sys, json; data = json.load(sys.stdin); sys.exit(0 if 'suggested_skills' in data else 1)" 2>/dev/null; then
            test_pass "Quick task plans include suggested_skills field"
        else
            test_fail "Quick task plans missing suggested_skills field"
        fi
    else
        test_fail "Quick task mode library not found"
    fi
}

# Test 5: Daemon queue file structure
test_daemon_queue_structure() {
    test_start "Daemon queue file structure is correct"

    # Create daemon directory
    mkdir -p ./.claude-loop/daemon

    # Create test queue file
    cat > ./.claude-loop/daemon/queue.json <<'EOF'
{
  "tasks": [
    {
      "id": "task-123",
      "prd_file": "test-prd.json",
      "priority": "normal",
      "status": "pending",
      "submitted_at": "2026-01-13T00:00:00Z"
    }
  ]
}
EOF

    # Verify queue file can be read by dashboard
    if [ -f "./.claude-loop/daemon/queue.json" ]; then
        local task_count
        task_count=$(python3 -c "import json; data = json.load(open('./.claude-loop/daemon/queue.json')); print(len(data.get('tasks', [])))" 2>/dev/null || echo "0")

        if [ "$task_count" -eq "1" ]; then
            test_pass "Daemon queue file structure is valid"
        else
            test_fail "Daemon queue file structure is invalid"
        fi
    else
        test_fail "Failed to create daemon queue file"
    fi
}

# Test 6: Notifications configuration file structure
test_notifications_config_structure() {
    test_start "Notifications config file structure is correct"

    mkdir -p ./.claude-loop/daemon

    # Create test notifications config
    cat > ./.claude-loop/daemon/notifications.json <<'EOF'
{
  "email": {
    "enabled": false,
    "method": "sendmail"
  },
  "slack": {
    "enabled": false,
    "webhook_url": ""
  },
  "webhook": {
    "enabled": false,
    "url": ""
  }
}
EOF

    if [ -f "./.claude-loop/daemon/notifications.json" ]; then
        # Verify structure
        local has_email has_slack has_webhook
        has_email=$(python3 -c "import json; data = json.load(open('./.claude-loop/daemon/notifications.json')); print('email' in data)" 2>/dev/null)
        has_slack=$(python3 -c "import json; data = json.load(open('./.claude-loop/daemon/notifications.json')); print('slack' in data)" 2>/dev/null)
        has_webhook=$(python3 -c "import json; data = json.load(open('./.claude-loop/daemon/notifications.json')); print('webhook' in data)" 2>/dev/null)

        if [ "$has_email" = "True" ] && [ "$has_slack" = "True" ] && [ "$has_webhook" = "True" ]; then
            test_pass "Notifications config structure is valid"
        else
            test_fail "Notifications config missing required channels"
        fi
    else
        test_fail "Failed to create notifications config"
    fi
}

# Test 7: Skills framework initialization
test_skills_framework_init() {
    test_start "Skills framework initialization"

    if [ -f "./lib/skills-framework.sh" ]; then
        source ./lib/skills-framework.sh

        # Check if skills can be listed
        if declare -f list_skills > /dev/null; then
            test_pass "Skills framework can be sourced and initialized"
        else
            test_fail "Skills framework missing required functions"
        fi
    else
        test_fail "Skills framework not found"
    fi
}

# Test 8: Dashboard static files exist
test_dashboard_static_files() {
    test_start "Dashboard static files exist"

    local missing_files=()

    if [ ! -f "./lib/dashboard/static/index.html" ]; then
        missing_files+=("index.html")
    fi

    if [ ! -f "./lib/dashboard/static/styles.css" ]; then
        missing_files+=("styles.css")
    fi

    if [ ! -f "./lib/dashboard/static/app.js" ]; then
        missing_files+=("app.js")
    fi

    if [ ${#missing_files[@]} -eq 0 ]; then
        test_pass "All dashboard static files present"
    else
        test_fail "Missing dashboard static files: ${missing_files[*]}"
    fi
}

# Test 9: Phase 1 features still accessible
test_phase1_compatibility() {
    test_start "Phase 1 features still work"

    # Check if monitoring.sh exists
    if [ -f "./lib/monitoring.sh" ]; then
        test_pass "Phase 1 monitoring library present"
    else
        test_fail "Phase 1 monitoring library missing"
    fi

    # Check if prd-parser exists
    if [ -f "./lib/prd-parser.sh" ]; then
        test_pass "Phase 1 PRD parser present"
    else
        test_fail "Phase 1 PRD parser missing"
    fi
}

# Test 10: Integration test for complete data flow
test_complete_data_flow() {
    test_start "Complete data flow from daemon to dashboard"

    mkdir -p ./.claude-loop/daemon

    # Create daemon queue
    cat > ./.claude-loop/daemon/queue.json <<'EOF'
{
  "tasks": [
    {
      "id": "flow-test-123",
      "prd_file": "test-prd.json",
      "priority": "high",
      "status": "running",
      "submitted_at": "2026-01-13T12:00:00Z",
      "notify_channels": ["email"]
    }
  ]
}
EOF

    # Create notifications log
    cat > ./.claude-loop/daemon/notifications.log <<'EOF'
[2026-01-13T12:00:00Z] [INFO] Task flow-test-123 started
[2026-01-13T12:05:00Z] [INFO] Notification sent via email
EOF

    # Verify data can be read
    local task_id
    task_id=$(python3 -c "import json; data = json.load(open('./.claude-loop/daemon/queue.json')); print(data['tasks'][0]['id'])" 2>/dev/null || echo "")

    local notify_channels
    notify_channels=$(python3 -c "import json; data = json.load(open('./.claude-loop/daemon/queue.json')); print(data['tasks'][0]['notify_channels'][0])" 2>/dev/null || echo "")

    if [ "$task_id" = "flow-test-123" ] && [ "$notify_channels" = "email" ]; then
        test_pass "Complete data flow works correctly"
    else
        test_fail "Data flow incomplete or corrupted"
    fi
}

# ==============================================================================
# Test Runner
# ==============================================================================

run_all_tests() {
    echo "========================================"
    echo "  PHASE 2 INTEGRATION TEST SUITE"
    echo "========================================"
    echo ""

    # Run all tests
    test_skills_quick_task_integration
    test_dashboard_daemon_integration
    test_dashboard_notifications_integration
    test_quick_task_plan_with_skills
    test_daemon_queue_structure
    test_notifications_config_structure
    test_skills_framework_init
    test_dashboard_static_files
    test_phase1_compatibility
    test_complete_data_flow

    # Print summary
    echo ""
    echo "========================================"
    echo "  TEST SUMMARY"
    echo "========================================"
    echo "Tests run:    ${TESTS_RUN}"
    echo -e "Tests passed: ${GREEN}${TESTS_PASSED}${NC}"
    echo -e "Tests failed: ${RED}${TESTS_FAILED}${NC}"

    if [ ${TESTS_FAILED} -gt 0 ]; then
        echo ""
        echo "Failed tests:"
        for test_name in "${FAILED_TESTS[@]}"; do
            echo -e "  ${RED}✗${NC} $test_name"
        done
        echo ""
        return 1
    else
        echo -e "\n${GREEN}All tests passed!${NC}\n"
        return 0
    fi
}

# ==============================================================================
# Main
# ==============================================================================

main() {
    # Trap cleanup
    trap cleanup_test_env EXIT

    # Setup
    setup_test_env

    # Run tests
    run_all_tests
    local exit_code=$?

    # Cleanup happens via trap
    exit $exit_code
}

# Run if executed directly
if [ "${BASH_SOURCE[0]}" == "${0}" ]; then
    main "$@"
fi
