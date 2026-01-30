#!/usr/bin/env bash
#
# Dashboard UI Tests
# Tests the frontend UI components and integration
#

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
DASHBOARD_DIR="$PROJECT_ROOT/lib/dashboard"
STATIC_DIR="$DASHBOARD_DIR/static"

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Test counters
TESTS_RUN=0
TESTS_PASSED=0
TESTS_FAILED=0

# Helper functions
test_pass() {
    echo -e "${GREEN}✓${NC} $1"
    ((TESTS_PASSED++))
    ((TESTS_RUN++))
}

test_fail() {
    echo -e "${RED}✗${NC} $1"
    echo -e "  ${RED}Error: $2${NC}"
    ((TESTS_FAILED++))
    ((TESTS_RUN++))
}

test_section() {
    echo ""
    echo -e "${YELLOW}▶ $1${NC}"
}

# ==============================================================================
# Tests
# ==============================================================================

test_section "Static Files Existence"

# Test: index.html exists
if [[ -f "$STATIC_DIR/index.html" ]]; then
    test_pass "index.html exists"
else
    test_fail "index.html exists" "File not found at $STATIC_DIR/index.html"
fi

# Test: styles.css exists
if [[ -f "$STATIC_DIR/styles.css" ]]; then
    test_pass "styles.css exists"
else
    test_fail "styles.css exists" "File not found at $STATIC_DIR/styles.css"
fi

# Test: app.js exists
if [[ -f "$STATIC_DIR/app.js" ]]; then
    test_pass "app.js exists"
else
    test_fail "app.js exists" "File not found at $STATIC_DIR/app.js"
fi

test_section "HTML Structure"

# Test: HTML contains required sections
if grep -q '<section class="section execution-section">' "$STATIC_DIR/index.html"; then
    test_pass "HTML contains execution section"
else
    test_fail "HTML contains execution section" "Section not found in HTML"
fi

if grep -q '<section class="section stories-section">' "$STATIC_DIR/index.html"; then
    test_pass "HTML contains stories section"
else
    test_fail "HTML contains stories section" "Section not found in HTML"
fi

if grep -q '<section class="section tabs-section">' "$STATIC_DIR/index.html"; then
    test_pass "HTML contains tabs section"
else
    test_fail "HTML contains tabs section" "Section not found in HTML"
fi

# Test: HTML contains required tabs
if grep -q 'data-tab="logs"' "$STATIC_DIR/index.html"; then
    test_pass "HTML contains logs tab"
else
    test_fail "HTML contains logs tab" "Logs tab not found"
fi

if grep -q 'data-tab="cost"' "$STATIC_DIR/index.html"; then
    test_pass "HTML contains cost tab"
else
    test_fail "HTML contains cost tab" "Cost tab not found"
fi

if grep -q 'data-tab="files"' "$STATIC_DIR/index.html"; then
    test_pass "HTML contains files tab"
else
    test_fail "HTML contains files tab" "Files tab not found"
fi

if grep -q 'data-tab="history"' "$STATIC_DIR/index.html"; then
    test_pass "HTML contains history tab"
else
    test_fail "HTML contains history tab" "History tab not found"
fi

# Test: HTML contains theme toggle
if grep -q 'id="theme-toggle"' "$STATIC_DIR/index.html"; then
    test_pass "HTML contains theme toggle"
else
    test_fail "HTML contains theme toggle" "Theme toggle not found"
fi

# Test: HTML contains settings button
if grep -q 'id="settings-btn"' "$STATIC_DIR/index.html"; then
    test_pass "HTML contains settings button"
else
    test_fail "HTML contains settings button" "Settings button not found"
fi

test_section "CSS Styling"

# Test: CSS contains theme variables
if grep -q ':root {' "$STATIC_DIR/styles.css"; then
    test_pass "CSS contains root variables"
else
    test_fail "CSS contains root variables" "Root variables not found"
fi

if grep -q '\[data-theme="dark"\]' "$STATIC_DIR/styles.css"; then
    test_pass "CSS contains dark theme"
else
    test_fail "CSS contains dark theme" "Dark theme not found"
fi

# Test: CSS contains responsive design
if grep -q '@media (max-width: 768px)' "$STATIC_DIR/styles.css"; then
    test_pass "CSS contains mobile breakpoint"
else
    test_fail "CSS contains mobile breakpoint" "Mobile breakpoint not found"
fi

if grep -q '@media (max-width: 480px)' "$STATIC_DIR/styles.css"; then
    test_pass "CSS contains small mobile breakpoint"
else
    test_fail "CSS contains small mobile breakpoint" "Small mobile breakpoint not found"
fi

# Test: CSS contains component styles
if grep -q '.story-grid' "$STATIC_DIR/styles.css"; then
    test_pass "CSS contains story grid styles"
else
    test_fail "CSS contains story grid styles" "Story grid styles not found"
fi

if grep -q '.logs-viewer' "$STATIC_DIR/styles.css"; then
    test_pass "CSS contains logs viewer styles"
else
    test_fail "CSS contains logs viewer styles" "Logs viewer styles not found"
fi

test_section "JavaScript Functionality"

# Test: JS contains configuration
if grep -q 'const CONFIG' "$STATIC_DIR/app.js"; then
    test_pass "JS contains configuration object"
else
    test_fail "JS contains configuration object" "CONFIG not found"
fi

# Test: JS contains API client
if grep -q 'class DashboardAPI' "$STATIC_DIR/app.js"; then
    test_pass "JS contains API client class"
else
    test_fail "JS contains API client class" "DashboardAPI not found"
fi

# Test: JS contains SSE handling
if grep -q 'EventSource' "$STATIC_DIR/app.js"; then
    test_pass "JS contains SSE handling"
else
    test_fail "JS contains SSE handling" "EventSource not found"
fi

# Test: JS contains authentication
if grep -q 'checkAuthentication' "$STATIC_DIR/app.js"; then
    test_pass "JS contains authentication check"
else
    test_fail "JS contains authentication check" "checkAuthentication not found"
fi

# Test: JS contains update functions
if grep -q 'updateStoryGrid' "$STATIC_DIR/app.js"; then
    test_pass "JS contains updateStoryGrid function"
else
    test_fail "JS contains updateStoryGrid function" "updateStoryGrid not found"
fi

if grep -q 'updateExecutionStatus' "$STATIC_DIR/app.js"; then
    test_pass "JS contains updateExecutionStatus function"
else
    test_fail "JS contains updateExecutionStatus function" "updateExecutionStatus not found"
fi

if grep -q 'addLogEntry' "$STATIC_DIR/app.js"; then
    test_pass "JS contains addLogEntry function"
else
    test_fail "JS contains addLogEntry function" "addLogEntry not found"
fi

if grep -q 'updateCostTracker' "$STATIC_DIR/app.js"; then
    test_pass "JS contains updateCostTracker function"
else
    test_fail "JS contains updateCostTracker function" "updateCostTracker not found"
fi

test_section "Server Integration"

# Test: Server has static folder configured
if grep -q "static_folder" "$DASHBOARD_DIR/server.py"; then
    test_pass "Server has static folder configured"
else
    test_fail "Server has static folder configured" "static_folder not found in server.py"
fi

# Test: Server has index route
if grep -q '@app.route("/"' "$DASHBOARD_DIR/server.py"; then
    test_pass "Server has index route"
else
    test_fail "Server has index route" "Index route not found"
fi

# Test: Server has static file route
if grep -q "send_from_directory" "$DASHBOARD_DIR/server.py"; then
    test_pass "Server has static file serving"
else
    test_fail "Server has static file serving" "send_from_directory not found"
fi

test_section "Documentation"

# Test: Documentation exists
DOC_FILE="$PROJECT_ROOT/docs/features/dashboard-ui.md"
if [[ -f "$DOC_FILE" ]]; then
    test_pass "Documentation file exists"
else
    test_fail "Documentation file exists" "File not found at $DOC_FILE"
fi

# Test: Documentation contains sections
if [[ -f "$DOC_FILE" ]]; then
    if grep -q "## Features" "$DOC_FILE"; then
        test_pass "Documentation contains Features section"
    else
        test_fail "Documentation contains Features section" "Section not found"
    fi

    if grep -q "## Getting Started" "$DOC_FILE"; then
        test_pass "Documentation contains Getting Started section"
    else
        test_fail "Documentation contains Getting Started section" "Section not found"
    fi

    if grep -q "## Troubleshooting" "$DOC_FILE"; then
        test_pass "Documentation contains Troubleshooting section"
    else
        test_fail "Documentation contains Troubleshooting section" "Section not found"
    fi
fi

# ==============================================================================
# Summary
# ==============================================================================

echo ""
echo "================================================================================"
echo "Test Summary"
echo "================================================================================"
echo "Tests run: $TESTS_RUN"
echo -e "${GREEN}Tests passed: $TESTS_PASSED${NC}"
if [[ $TESTS_FAILED -gt 0 ]]; then
    echo -e "${RED}Tests failed: $TESTS_FAILED${NC}"
else
    echo -e "${GREEN}Tests failed: $TESTS_FAILED${NC}"
fi
echo "================================================================================"

if [[ $TESTS_FAILED -gt 0 ]]; then
    exit 1
else
    exit 0
fi
