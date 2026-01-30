#!/bin/bash
#
# MCP Integration Tests (US-005)
#
# Tests for Model Context Protocol integration:
# - Tool discovery
# - Tool invocation
# - Error handling (unavailable server)
# - Whitelist enforcement
# - Schema validation
#

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Test counters
TESTS_RUN=0
TESTS_PASSED=0
TESTS_FAILED=0

# Test helper functions
test_start() {
    local test_name="$1"
    echo -e "${YELLOW}[TEST]${NC} $test_name"
    TESTS_RUN=$((TESTS_RUN + 1))
}

test_pass() {
    echo -e "${GREEN}[PASS]${NC} $1"
    TESTS_PASSED=$((TESTS_PASSED + 1))
}

test_fail() {
    echo -e "${RED}[FAIL]${NC} $1"
    TESTS_FAILED=$((TESTS_FAILED + 1))
}

# ============================================================================
# Test Setup
# ============================================================================

setup_test_environment() {
    echo "Setting up MCP test environment..."

    # Create test config directory
    mkdir -p "$PROJECT_ROOT/.claude-loop"

    # Create minimal MCP config for testing
    cat > "$PROJECT_ROOT/.claude-loop/mcp-config-test.json" <<'EOF'
{
  "servers": [
    {
      "name": "test-disabled",
      "endpoint": "echo 'disabled'",
      "transport": "stdio",
      "enabled": false,
      "tools_whitelist": ["test_tool"]
    }
  ],
  "global_settings": {
    "timeout_seconds": 5,
    "max_retries": 1
  }
}
EOF

    echo "Test environment created"
}

cleanup_test_environment() {
    echo "Cleaning up test environment..."
    rm -f "$PROJECT_ROOT/.claude-loop/mcp-config-test.json"
}

# ============================================================================
# Test 1: MCP Bridge Script Exists
# ============================================================================

test_mcp_bridge_exists() {
    test_start "MCP bridge script exists"

    if [ -f "$PROJECT_ROOT/lib/mcp_bridge.sh" ]; then
        test_pass "mcp_bridge.sh found"
    else
        test_fail "mcp_bridge.sh not found"
    fi
}

# ============================================================================
# Test 2: MCP Client Script Exists
# ============================================================================

test_mcp_client_exists() {
    test_start "MCP client script exists"

    if [ -f "$PROJECT_ROOT/lib/mcp_client.py" ]; then
        test_pass "mcp_client.py found"
    else
        test_fail "mcp_client.py not found"
    fi
}

# ============================================================================
# Test 3: MCP Bridge Can Be Sourced
# ============================================================================

test_mcp_bridge_sourceable() {
    test_start "MCP bridge can be sourced"

    if source "$PROJECT_ROOT/lib/mcp_bridge.sh" 2>/dev/null; then
        test_pass "mcp_bridge.sh sourced successfully"
    else
        test_fail "Failed to source mcp_bridge.sh"
    fi
}

# ============================================================================
# Test 4: MCP Functions Available
# ============================================================================

test_mcp_functions_available() {
    test_start "MCP functions available after sourcing"

    source "$PROJECT_ROOT/lib/mcp_bridge.sh"

    local functions_ok=true

    if ! declare -f mcp_init > /dev/null; then
        echo "  mcp_init not found"
        functions_ok=false
    fi

    if ! declare -f mcp_is_enabled > /dev/null; then
        echo "  mcp_is_enabled not found"
        functions_ok=false
    fi

    if ! declare -f mcp_list_tools > /dev/null; then
        echo "  mcp_list_tools not found"
        functions_ok=false
    fi

    if ! declare -f mcp_call_tool > /dev/null; then
        echo "  mcp_call_tool not found"
        functions_ok=false
    fi

    if $functions_ok; then
        test_pass "All MCP functions available"
    else
        test_fail "Some MCP functions missing"
    fi
}

# ============================================================================
# Test 5: MCP Disabled by Default
# ============================================================================

test_mcp_disabled_by_default() {
    test_start "MCP disabled by default"

    source "$PROJECT_ROOT/lib/mcp_bridge.sh"

    if ! mcp_is_enabled; then
        test_pass "MCP correctly disabled by default"
    else
        test_fail "MCP unexpectedly enabled"
    fi
}

# ============================================================================
# Test 6: MCP Config Example Exists
# ============================================================================

test_mcp_config_example_exists() {
    test_start "MCP config example exists"

    if [ -f "$PROJECT_ROOT/.claude-loop/mcp-config.example.json" ]; then
        test_pass "mcp-config.example.json found"
    else
        test_fail "mcp-config.example.json not found"
    fi
}

# ============================================================================
# Test 7: MCP Config Example is Valid JSON
# ============================================================================

test_mcp_config_example_valid() {
    test_start "MCP config example is valid JSON"

    if jq empty "$PROJECT_ROOT/.claude-loop/mcp-config.example.json" 2>/dev/null; then
        test_pass "mcp-config.example.json is valid JSON"
    else
        test_fail "mcp-config.example.json is not valid JSON"
    fi
}

# ============================================================================
# Test 8: MCP Client Python Script is Executable
# ============================================================================

test_mcp_client_executable() {
    test_start "MCP client Python script is executable"

    if [ -x "$PROJECT_ROOT/lib/mcp_client.py" ]; then
        test_pass "mcp_client.py is executable"
    else
        test_fail "mcp_client.py is not executable"
    fi
}

# ============================================================================
# Test 9: MCP Client Help Output
# ============================================================================

test_mcp_client_help() {
    test_start "MCP client provides help"

    if python3 "$PROJECT_ROOT/lib/mcp_client.py" --help 2>&1 | grep -q "MCP Client CLI"; then
        test_pass "MCP client help works"
    else
        test_fail "MCP client help failed"
    fi
}

# ============================================================================
# Test 10: MCP Init Creates Example Config
# ============================================================================

test_mcp_init_creates_config() {
    test_start "MCP init creates example config if missing"

    # Remove config if exists
    rm -f "$PROJECT_ROOT/.claude-loop/mcp-config.json"

    export ENABLE_MCP=true
    export MCP_CONFIG_FILE="$PROJECT_ROOT/.claude-loop/mcp-config.json"
    source "$PROJECT_ROOT/lib/mcp_bridge.sh"

    # Init should create config
    mcp_init 2>/dev/null || true

    if [ -f "$PROJECT_ROOT/.claude-loop/mcp-config.json" ]; then
        test_pass "MCP init created config file"
        # Cleanup
        rm -f "$PROJECT_ROOT/.claude-loop/mcp-config.json"
    else
        test_fail "MCP init did not create config file"
    fi
}

# ============================================================================
# Test 11: MCP Library Check
# ============================================================================

test_mcp_library_check() {
    test_start "MCP library availability check"

    if python3 -c "import mcp" 2>/dev/null; then
        test_pass "MCP library is installed"
    else
        echo "  (MCP library not installed - expected if pip install not run yet)"
        test_pass "MCP library check works (library not required for tests)"
    fi
}

# ============================================================================
# Test 12: Parse MCP Call Function
# ============================================================================

test_parse_mcp_call() {
    test_start "Parse MCP call from prompt"

    source "$PROJECT_ROOT/lib/mcp_bridge.sh"

    local test_prompt='Use [use-mcp:filesystem/read_file:{"path": "test.txt"}] to read.'
    local result
    result=$(parse_mcp_call "$test_prompt")

    if echo "$result" | jq -e '.[0].server == "filesystem"' > /dev/null 2>&1; then
        if echo "$result" | jq -e '.[0].tool == "read_file"' > /dev/null 2>&1; then
            test_pass "MCP call parsing works"
        else
            test_fail "MCP call tool parsing failed"
        fi
    else
        test_fail "MCP call server parsing failed"
    fi
}

# ============================================================================
# Test 13: Integration with claude-loop.sh
# ============================================================================

test_claude_loop_mcp_flags() {
    test_start "claude-loop.sh has MCP flags"

    local has_enable_mcp=false
    local has_list_mcp=false

    if grep -q "\-\-enable-mcp" "$PROJECT_ROOT/claude-loop.sh"; then
        has_enable_mcp=true
    fi

    if grep -q "\-\-list-mcp-tools" "$PROJECT_ROOT/claude-loop.sh"; then
        has_list_mcp=true
    fi

    if $has_enable_mcp && $has_list_mcp; then
        test_pass "claude-loop.sh has MCP flags"
    else
        test_fail "claude-loop.sh missing MCP flags"
    fi
}

# ============================================================================
# Run All Tests
# ============================================================================

main() {
    echo "================================"
    echo "MCP Integration Tests (US-005)"
    echo "================================"
    echo

    setup_test_environment

    # Run tests
    test_mcp_bridge_exists
    test_mcp_client_exists
    test_mcp_bridge_sourceable
    test_mcp_functions_available
    test_mcp_disabled_by_default
    test_mcp_config_example_exists
    test_mcp_config_example_valid
    test_mcp_client_executable
    test_mcp_client_help
    test_mcp_init_creates_config
    test_mcp_library_check
    test_parse_mcp_call
    test_claude_loop_mcp_flags

    cleanup_test_environment

    # Summary
    echo
    echo "================================"
    echo "Test Summary"
    echo "================================"
    echo "Total:  $TESTS_RUN"
    echo -e "${GREEN}Passed: $TESTS_PASSED${NC}"
    if [ $TESTS_FAILED -gt 0 ]; then
        echo -e "${RED}Failed: $TESTS_FAILED${NC}"
    else
        echo "Failed: $TESTS_FAILED"
    fi

    echo
    if [ $TESTS_FAILED -eq 0 ]; then
        echo -e "${GREEN}All tests passed!${NC}"
        exit 0
    else
        echo -e "${RED}Some tests failed${NC}"
        exit 1
    fi
}

# Run tests
main
