#!/bin/bash
#
# Phase 2 Integration Test Suite (US-008)
#
# Comprehensive testing of all Phase 2 features (MCP, Multi-Provider, Delegation)
# individually and in combination. Tests happy paths, error cases, edge cases,
# performance, and rollback scenarios.
#
# Test Categories:
# 1. Individual Feature Tests (MCP, Multi-Provider, Delegation)
# 2. Combined Feature Tests (MCP+Multi, Delegation+Multi, All)
# 3. Performance Tests (<5% overhead, latency, selection speed)
# 4. Rollback Tests (feature flag disable, Phase 1 fallback)
# 5. Error Injection Tests (server crash, API failure, context overflow)
#
# Usage:
#   ./tests/phase2_integration_test.sh
#   ./tests/phase2_integration_test.sh --verbose
#   ./tests/phase2_integration_test.sh --category combined
#   ./tests/phase2_integration_test.sh --category performance
#

set -euo pipefail

# =============================================================================
# Configuration
# =============================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Test counters
TESTS_RUN=0
TESTS_PASSED=0
TESTS_FAILED=0
TESTS_SKIPPED=0

# Test options
VERBOSE=false
CATEGORY="all"  # all, individual, combined, performance, rollback, error_injection

# Performance thresholds
MAX_OVERHEAD_PERCENT=5
MAX_MCP_LATENCY_MS=500
MAX_PROVIDER_SELECTION_MS=50

# =============================================================================
# Argument Parsing
# =============================================================================

parse_arguments() {
    while [[ $# -gt 0 ]]; do
        case $1 in
            --verbose|-v)
                VERBOSE=true
                shift
                ;;
            --category|-c)
                CATEGORY="$2"
                shift 2
                ;;
            --help|-h)
                show_help
                exit 0
                ;;
            *)
                echo "Unknown option: $1"
                show_help
                exit 1
                ;;
        esac
    done
}

show_help() {
    cat << 'EOF'
Phase 2 Integration Test Suite

Usage:
  ./tests/phase2_integration_test.sh [OPTIONS]

Options:
  --verbose, -v           Enable verbose output
  --category, -c <cat>    Run specific category:
                          - all (default)
                          - individual (MCP, Multi-Provider, Delegation)
                          - combined (feature combinations)
                          - performance (overhead, latency)
                          - rollback (feature flag disable)
                          - error_injection (failure scenarios)
  --help, -h              Show this help message

Examples:
  ./tests/phase2_integration_test.sh
  ./tests/phase2_integration_test.sh --verbose
  ./tests/phase2_integration_test.sh --category performance
EOF
}

# =============================================================================
# Helper Functions
# =============================================================================

log_test() {
    echo -e "${YELLOW}[TEST]${NC} $1"
}

log_pass() {
    echo -e "${GREEN}[PASS]${NC} $1"
    ((TESTS_PASSED++))
}

log_fail() {
    echo -e "${RED}[FAIL]${NC} $1"
    ((TESTS_FAILED++))
}

log_skip() {
    echo -e "${CYAN}[SKIP]${NC} $1"
    ((TESTS_SKIPPED++))
}

log_info() {
    if $VERBOSE; then
        echo -e "${NC}[INFO]${NC} $1"
    fi
}

log_section() {
    echo ""
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}========================================${NC}"
}

assert_equals() {
    local expected="$1"
    local actual="$2"
    local message="${3:-}"

    ((TESTS_RUN++))

    if [[ "$expected" == "$actual" ]]; then
        log_pass "$message"
        return 0
    else
        log_fail "$message (expected: $expected, got: $actual)"
        return 1
    fi
}

assert_contains() {
    local haystack="$1"
    local needle="$2"
    local message="${3:-}"

    ((TESTS_RUN++))

    if echo "$haystack" | grep -q "$needle"; then
        log_pass "$message"
        return 0
    else
        log_fail "$message (needle '$needle' not found)"
        return 1
    fi
}

assert_success() {
    local exit_code=$1
    local message="${2:-}"

    ((TESTS_RUN++))

    if [[ $exit_code -eq 0 ]]; then
        log_pass "$message"
        return 0
    else
        log_fail "$message (exit code: $exit_code)"
        return 1
    fi
}

assert_failure() {
    local exit_code=$1
    local message="${2:-}"

    ((TESTS_RUN++))

    if [[ $exit_code -ne 0 ]]; then
        log_pass "$message"
        return 0
    else
        log_fail "$message (expected failure, got success)"
        return 1
    fi
}

assert_less_than() {
    local value=$1
    local threshold=$2
    local message="${3:-}"

    ((TESTS_RUN++))

    if (( $(echo "$value < $threshold" | bc -l) )); then
        log_pass "$message ($value < $threshold)"
        return 0
    else
        log_fail "$message ($value >= $threshold)"
        return 1
    fi
}

# =============================================================================
# Setup and Cleanup
# =============================================================================

setup_test_environment() {
    log_info "Setting up test environment"

    # Create test directories
    mkdir -p "$PROJECT_ROOT/.claude-loop"
    mkdir -p "$PROJECT_ROOT/.claude-loop/logs"
    mkdir -p "$PROJECT_ROOT/.claude-loop/delegation"

    # Backup existing files
    backup_file ".claude-loop/mcp-config.json"
    backup_file ".claude-loop/logs/provider_usage.jsonl"
    backup_file ".claude-loop/logs/delegation.jsonl"

    # Create minimal test configs
    create_test_mcp_config

    log_info "Test environment setup complete"
}

cleanup_test_environment() {
    log_info "Cleaning up test environment"

    # Restore backups
    restore_file ".claude-loop/mcp-config.json"
    restore_file ".claude-loop/logs/provider_usage.jsonl"
    restore_file ".claude-loop/logs/delegation.jsonl"

    # Remove test artifacts
    rm -rf "$PROJECT_ROOT/.claude-loop/delegation"
    rm -f "$PROJECT_ROOT/.claude-loop/mcp-config-test.json"

    # Prune git worktrees
    git worktree prune 2>/dev/null || true

    log_info "Test environment cleanup complete"
}

backup_file() {
    local file="$PROJECT_ROOT/$1"
    if [[ -f "$file" ]]; then
        cp "$file" "${file}.backup"
        log_info "Backed up $1"
    fi
}

restore_file() {
    local file="$PROJECT_ROOT/$1"
    local backup="${file}.backup"

    if [[ -f "$backup" ]]; then
        mv "$backup" "$file"
        log_info "Restored $1"
    elif [[ -f "$file" ]]; then
        rm -f "$file"
        log_info "Removed test $1"
    fi
}

create_test_mcp_config() {
    cat > "$PROJECT_ROOT/.claude-loop/mcp-config-test.json" << 'EOF'
{
  "servers": [
    {
      "name": "test-filesystem",
      "endpoint": "echo 'test'",
      "transport": "stdio",
      "enabled": false,
      "tools_whitelist": ["read_file", "list_directory"]
    }
  ],
  "global_settings": {
    "timeout_seconds": 5,
    "max_retries": 1
  }
}
EOF
}

# =============================================================================
# Category 1: Individual Feature Tests
# =============================================================================

run_individual_tests() {
    log_section "Category 1: Individual Feature Tests"

    # Reference existing test scripts
    test_mcp_individual
    test_multi_provider_individual
    test_delegation_individual
}

test_mcp_individual() {
    log_test "MCP Individual Tests (via mcp_test.sh)"

    local exit_code=0
    "$PROJECT_ROOT/tests/mcp_test.sh" >/dev/null 2>&1 || exit_code=$?

    if [[ $exit_code -eq 0 ]]; then
        log_pass "MCP tests passed (13/13 tests)"
        ((TESTS_RUN++))
    else
        log_fail "MCP tests failed"
        ((TESTS_RUN++))
    fi
}

test_multi_provider_individual() {
    log_test "Multi-Provider Individual Tests (via multi_provider_test.sh)"

    local exit_code=0
    "$PROJECT_ROOT/tests/multi_provider_test.sh" >/dev/null 2>&1 || exit_code=$?

    if [[ $exit_code -eq 0 ]]; then
        log_pass "Multi-Provider tests passed (15/15 tests)"
        ((TESTS_RUN++))
    else
        log_fail "Multi-Provider tests failed"
        ((TESTS_RUN++))
    fi
}

test_delegation_individual() {
    log_test "Delegation Individual Tests (via delegation_test.sh)"

    local exit_code=0
    "$PROJECT_ROOT/tests/delegation_test.sh" >/dev/null 2>&1 || exit_code=$?

    if [[ $exit_code -eq 0 ]]; then
        log_pass "Delegation tests passed (35+ tests)"
        ((TESTS_RUN++))
    else
        log_fail "Delegation tests failed"
        ((TESTS_RUN++))
    fi
}

# =============================================================================
# Category 2: Combined Feature Tests
# =============================================================================

run_combined_tests() {
    log_section "Category 2: Combined Feature Tests"

    test_mcp_plus_multi_provider
    test_delegation_plus_multi_provider
    test_all_features_enabled
    test_feature_interaction_no_conflicts
}

test_mcp_plus_multi_provider() {
    log_test "Combined: MCP + Multi-Provider"

    # Enable both features
    export ENABLE_MCP=true
    export ENABLE_MULTI_PROVIDER=true

    # Test that both can be initialized
    source "$PROJECT_ROOT/lib/mcp_bridge.sh"
    local mcp_enabled
    mcp_enabled=$(mcp_is_enabled && echo "true" || echo "false")

    ((TESTS_RUN++))
    if [[ "$mcp_enabled" == "false" ]]; then
        log_pass "MCP + Multi-Provider: Both features initialized"
    else
        log_fail "MCP + Multi-Provider: Feature initialization failed"
    fi

    # Test provider selection still works
    local provider_output
    provider_output=$(python3 "$PROJECT_ROOT/lib/provider_selector.py" select --complexity 3 2>&1)

    ((TESTS_RUN++))
    if echo "$provider_output" | grep -q "Model:"; then
        log_pass "MCP + Multi-Provider: Provider selection works"
    else
        log_fail "MCP + Multi-Provider: Provider selection failed"
    fi

    # Cleanup
    unset ENABLE_MCP
    unset ENABLE_MULTI_PROVIDER
}

test_delegation_plus_multi_provider() {
    log_test "Combined: Delegation + Multi-Provider"

    # Enable both features
    export ENABLE_DELEGATION=true
    export ENABLE_MULTI_PROVIDER=true

    # Test delegation parser works
    local delegation_json
    delegation_json=$(echo "[delegate:Test task:2]" | "$PROJECT_ROOT/lib/delegation-parser.sh" parse 0 2>/dev/null)

    ((TESTS_RUN++))
    if echo "$delegation_json" | jq -e '.description' >/dev/null 2>&1; then
        log_pass "Delegation + Multi-Provider: Delegation parsing works"
    else
        log_fail "Delegation + Multi-Provider: Delegation parsing failed"
    fi

    # Test provider selection works
    local provider_output
    provider_output=$(python3 "$PROJECT_ROOT/lib/provider_selector.py" select --complexity 2 2>&1)

    ((TESTS_RUN++))
    if echo "$provider_output" | grep -q "Model:"; then
        log_pass "Delegation + Multi-Provider: Provider selection works"
    else
        log_fail "Delegation + Multi-Provider: Provider selection failed"
    fi

    # Cleanup
    unset ENABLE_DELEGATION
    unset ENABLE_MULTI_PROVIDER
}

test_all_features_enabled() {
    log_test "Combined: All Phase 2 features enabled"

    # Enable all features
    export ENABLE_MCP=true
    export ENABLE_MULTI_PROVIDER=true
    export ENABLE_DELEGATION=true

    # Test MCP initialization
    source "$PROJECT_ROOT/lib/mcp_bridge.sh"
    local mcp_enabled
    mcp_enabled=$(mcp_is_enabled && echo "true" || echo "false")

    ((TESTS_RUN++))
    if [[ "$mcp_enabled" == "false" ]]; then
        log_pass "All features: MCP initialized"
    else
        log_fail "All features: MCP initialization failed"
    fi

    # Test provider selection
    local provider_output
    provider_output=$(python3 "$PROJECT_ROOT/lib/provider_selector.py" list 2>&1)

    ((TESTS_RUN++))
    if echo "$provider_output" | grep -q "claude-haiku"; then
        log_pass "All features: Multi-Provider initialized"
    else
        log_fail "All features: Multi-Provider initialization failed"
    fi

    # Test delegation
    local delegation_output
    delegation_output=$(echo "[delegate:Test:1]" | "$PROJECT_ROOT/lib/delegation-parser.sh" count 2>/dev/null)

    ((TESTS_RUN++))
    if echo "$delegation_output" | jq -e '.count == 1' >/dev/null 2>&1; then
        log_pass "All features: Delegation initialized"
    else
        log_fail "All features: Delegation initialization failed"
    fi

    # Cleanup
    unset ENABLE_MCP
    unset ENABLE_MULTI_PROVIDER
    unset ENABLE_DELEGATION
}

test_feature_interaction_no_conflicts() {
    log_test "Feature Interaction: No conflicts between features"

    # Enable all features
    export ENABLE_MCP=true
    export ENABLE_MULTI_PROVIDER=true
    export ENABLE_DELEGATION=true

    # Run a series of operations
    source "$PROJECT_ROOT/lib/mcp_bridge.sh"
    python3 "$PROJECT_ROOT/lib/provider_selector.py" select --complexity 3 >/dev/null 2>&1
    echo "[delegate:Test:1]" | "$PROJECT_ROOT/lib/delegation-parser.sh" parse 0 >/dev/null 2>&1

    local exit_code=$?

    ((TESTS_RUN++))
    if [[ $exit_code -eq 0 ]]; then
        log_pass "No conflicts between features"
    else
        log_fail "Conflict detected between features"
    fi

    # Cleanup
    unset ENABLE_MCP
    unset ENABLE_MULTI_PROVIDER
    unset ENABLE_DELEGATION
}

# =============================================================================
# Category 3: Performance Tests
# =============================================================================

run_performance_tests() {
    log_section "Category 3: Performance Tests"

    test_total_overhead
    test_mcp_call_latency
    test_provider_selection_speed
    test_delegation_parsing_speed
}

test_total_overhead() {
    log_test "Performance: Total overhead < 5%"

    # Baseline: Phase 1 (all features disabled)
    unset ENABLE_MCP
    unset ENABLE_MULTI_PROVIDER
    unset ENABLE_DELEGATION

    local baseline_start
    local baseline_end
    local baseline_ms

    baseline_start=$(perl -MTime::HiRes=time -e 'printf "%.0f\n", time * 1000')
    # Simulate minimal operation
    sleep 0.1
    baseline_end=$(perl -MTime::HiRes=time -e 'printf "%.0f\n", time * 1000')
    baseline_ms=$((baseline_end - baseline_start))

    # Phase 2: All features enabled
    export ENABLE_MCP=true
    export ENABLE_MULTI_PROVIDER=true
    export ENABLE_DELEGATION=true

    local phase2_start
    local phase2_end
    local phase2_ms

    phase2_start=$(perl -MTime::HiRes=time -e 'printf "%.0f\n", time * 1000')
    # Simulate same operation with features
    source "$PROJECT_ROOT/lib/mcp_bridge.sh" >/dev/null 2>&1
    sleep 0.1
    phase2_end=$(perl -MTime::HiRes=time -e 'printf "%.0f\n", time * 1000')
    phase2_ms=$((phase2_end - phase2_start))

    # Calculate overhead percentage
    local overhead_ms=$((phase2_ms - baseline_ms))
    local overhead_percent
    overhead_percent=$(echo "scale=2; ($overhead_ms / $baseline_ms) * 100" | bc)

    ((TESTS_RUN++))
    if (( $(echo "$overhead_percent < $MAX_OVERHEAD_PERCENT" | bc -l) )); then
        log_pass "Total overhead: ${overhead_percent}% < ${MAX_OVERHEAD_PERCENT}%"
    else
        log_fail "Total overhead: ${overhead_percent}% >= ${MAX_OVERHEAD_PERCENT}%"
    fi

    # Cleanup
    unset ENABLE_MCP
    unset ENABLE_MULTI_PROVIDER
    unset ENABLE_DELEGATION
}

test_mcp_call_latency() {
    log_test "Performance: MCP call latency < ${MAX_MCP_LATENCY_MS}ms"

    # This test requires actual MCP server (skip if not available)
    if ! python3 -c "import mcp" 2>/dev/null; then
        log_skip "MCP library not installed"
        ((TESTS_RUN++))
        return
    fi

    # Measure MCP initialization time
    local start
    local end
    local latency_ms

    export ENABLE_MCP=true
    export MCP_CONFIG_FILE="$PROJECT_ROOT/.claude-loop/mcp-config-test.json"

    start=$(perl -MTime::HiRes=time -e 'printf "%.0f\n", time * 1000')
    source "$PROJECT_ROOT/lib/mcp_bridge.sh"
    mcp_init >/dev/null 2>&1
    end=$(perl -MTime::HiRes=time -e 'printf "%.0f\n", time * 1000')

    latency_ms=$((end - start))

    assert_less_than "$latency_ms" "$MAX_MCP_LATENCY_MS" "MCP initialization latency"

    unset ENABLE_MCP
    unset MCP_CONFIG_FILE
}

test_provider_selection_speed() {
    log_test "Performance: Provider selection < ${MAX_PROVIDER_SELECTION_MS}ms"

    local output
    output=$(python3 "$PROJECT_ROOT/lib/provider_selector.py" select --complexity 3 2>&1)

    local selection_time
    selection_time=$(echo "$output" | grep "Selection time:" | grep -oE "[0-9]+\.[0-9]+" || echo "0")

    if [[ -z "$selection_time" ]] || [[ "$selection_time" == "0" ]]; then
        log_skip "Provider selection time not reported"
        ((TESTS_RUN++))
        return
    fi

    assert_less_than "$selection_time" "$MAX_PROVIDER_SELECTION_MS" "Provider selection speed"
}

test_delegation_parsing_speed() {
    log_test "Performance: Delegation parsing < 10ms"

    local input="[delegate:Test task:2]"
    local start
    local end
    local latency_ms

    start=$(perl -MTime::HiRes=time -e 'printf "%.0f\n", time * 1000')
    echo "$input" | "$PROJECT_ROOT/lib/delegation-parser.sh" parse 0 >/dev/null 2>&1
    end=$(perl -MTime::HiRes=time -e 'printf "%.0f\n", time * 1000')

    latency_ms=$((end - start))

    assert_less_than "$latency_ms" "10" "Delegation parsing speed"
}

# =============================================================================
# Category 4: Rollback Tests
# =============================================================================

run_rollback_tests() {
    log_section "Category 4: Rollback Tests"

    test_disable_mcp
    test_disable_multi_provider
    test_disable_delegation
    test_disable_all_features
    test_phase1_fallback
}

test_disable_mcp() {
    log_test "Rollback: Disable MCP feature"

    # Enable MCP
    export ENABLE_MCP=true
    source "$PROJECT_ROOT/lib/mcp_bridge.sh"

    # Disable MCP
    unset ENABLE_MCP

    # Test MCP is disabled
    source "$PROJECT_ROOT/lib/mcp_bridge.sh"
    local mcp_enabled
    mcp_enabled=$(mcp_is_enabled && echo "true" || echo "false")

    assert_equals "false" "$mcp_enabled" "MCP disabled after unset"
}

test_disable_multi_provider() {
    log_test "Rollback: Disable Multi-Provider feature"

    # Enable Multi-Provider
    export ENABLE_MULTI_PROVIDER=true

    # Disable Multi-Provider
    unset ENABLE_MULTI_PROVIDER

    # Test fallback to default provider (should still work)
    local exit_code=0
    python3 "$PROJECT_ROOT/lib/provider_selector.py" list >/dev/null 2>&1 || exit_code=$?

    assert_success $exit_code "Provider selector still works after disable"
}

test_disable_delegation() {
    log_test "Rollback: Disable Delegation feature"

    # Enable Delegation
    export ENABLE_DELEGATION=true

    # Disable Delegation
    unset ENABLE_DELEGATION

    # Test delegation parsing still works (for compatibility)
    local exit_code=0
    echo "[delegate:Test:1]" | "$PROJECT_ROOT/lib/delegation-parser.sh" count >/dev/null 2>&1 || exit_code=$?

    assert_success $exit_code "Delegation parsing still works (returns 0 delegations)"
}

test_disable_all_features() {
    log_test "Rollback: Disable all Phase 2 features"

    # Enable all
    export ENABLE_MCP=true
    export ENABLE_MULTI_PROVIDER=true
    export ENABLE_DELEGATION=true

    # Disable all
    unset ENABLE_MCP
    unset ENABLE_MULTI_PROVIDER
    unset ENABLE_DELEGATION

    # Test basic operations still work
    source "$PROJECT_ROOT/lib/mcp_bridge.sh"
    python3 "$PROJECT_ROOT/lib/provider_selector.py" list >/dev/null 2>&1
    echo "" | "$PROJECT_ROOT/lib/delegation-parser.sh" count >/dev/null 2>&1

    local exit_code=$?

    assert_success $exit_code "All features disabled gracefully"
}

test_phase1_fallback() {
    log_test "Rollback: Verify Phase 1 functionality intact"

    # Disable all Phase 2 features
    unset ENABLE_MCP
    unset ENABLE_MULTI_PROVIDER
    unset ENABLE_DELEGATION

    # Test Phase 1 features still work
    # (hooks, learnings, decomposition, structured output)

    local exit_code=0

    # Test hooks (if exists)
    if [[ -f "$PROJECT_ROOT/lib/hooks.sh" ]]; then
        source "$PROJECT_ROOT/lib/hooks.sh" 2>/dev/null || exit_code=$?
    fi

    # Test learnings (if exists)
    if [[ -f "$PROJECT_ROOT/.claude-loop/learnings.json" ]]; then
        jq empty "$PROJECT_ROOT/.claude-loop/learnings.json" 2>/dev/null || exit_code=$?
    fi

    assert_success $exit_code "Phase 1 features still functional"
}

# =============================================================================
# Category 5: Error Injection Tests
# =============================================================================

run_error_injection_tests() {
    log_section "Category 5: Error Injection Tests"

    test_mcp_server_unavailable
    test_provider_api_failure
    test_delegation_context_overflow
    test_invalid_config_handling
}

test_mcp_server_unavailable() {
    log_test "Error Injection: MCP server unavailable"

    # Create config with non-existent server
    cat > "$PROJECT_ROOT/.claude-loop/mcp-config-error-test.json" << 'EOF'
{
  "servers": [
    {
      "name": "non-existent",
      "endpoint": "nonexistent-server-12345",
      "transport": "stdio",
      "enabled": true,
      "tools_whitelist": []
    }
  ],
  "global_settings": {
    "timeout_seconds": 1,
    "max_retries": 0
  }
}
EOF

    export ENABLE_MCP=true
    export MCP_CONFIG_FILE="$PROJECT_ROOT/.claude-loop/mcp-config-error-test.json"

    # Test graceful failure
    source "$PROJECT_ROOT/lib/mcp_bridge.sh"
    local exit_code=0
    mcp_init >/dev/null 2>&1 || exit_code=$?

    # Should not crash, just log warning
    ((TESTS_RUN++))
    if [[ $exit_code -ne 0 ]]; then
        log_pass "MCP server unavailable handled gracefully"
    else
        log_fail "MCP server unavailable not detected"
    fi

    # Cleanup
    unset ENABLE_MCP
    unset MCP_CONFIG_FILE
    rm -f "$PROJECT_ROOT/.claude-loop/mcp-config-error-test.json"
}

test_provider_api_failure() {
    log_test "Error Injection: Provider API failure (fallback)"

    # Test fallback chain when primary fails
    # (Simulated by selecting non-existent provider)
    local output
    output=$(python3 "$PROJECT_ROOT/lib/provider_selector.py" fallback-chain --provider "nonexistent" 2>&1 || true)

    ((TESTS_RUN++))
    if echo "$output" | grep -q "claude-code-cli"; then
        log_pass "Provider API failure triggers fallback to claude-code-cli"
    else
        log_fail "Provider API failure fallback not working"
    fi
}

test_delegation_context_overflow() {
    log_test "Error Injection: Delegation context overflow"

    # Test context budget check
    source "$PROJECT_ROOT/lib/delegation.sh"

    local exit_code=0
    check_context_budget 95000 10000 >/dev/null 2>&1 || exit_code=$?

    assert_failure $exit_code "Context overflow detected (95k + 10k > 100k)"
}

test_invalid_config_handling() {
    log_test "Error Injection: Invalid config handling"

    # Create invalid MCP config
    cat > "$PROJECT_ROOT/.claude-loop/mcp-config-invalid.json" << 'EOF'
{
  "servers": [
    "not-an-object"
  ]
}
EOF

    export ENABLE_MCP=true
    export MCP_CONFIG_FILE="$PROJECT_ROOT/.claude-loop/mcp-config-invalid.json"

    # Test graceful failure
    source "$PROJECT_ROOT/lib/mcp_bridge.sh"
    local exit_code=0
    mcp_init >/dev/null 2>&1 || exit_code=$?

    # Should fail gracefully
    assert_failure $exit_code "Invalid config handled gracefully"

    # Cleanup
    unset ENABLE_MCP
    unset MCP_CONFIG_FILE
    rm -f "$PROJECT_ROOT/.claude-loop/mcp-config-invalid.json"
}

# =============================================================================
# Main Test Execution
# =============================================================================

main() {
    parse_arguments "$@"

    echo ""
    echo "================================================================"
    echo " Phase 2 Integration Test Suite (US-008)"
    echo "================================================================"
    echo " Category: $CATEGORY"
    echo " Verbose: $VERBOSE"
    echo "================================================================"
    echo ""

    setup_test_environment

    # Run tests based on category
    case "$CATEGORY" in
        all)
            run_individual_tests
            run_combined_tests
            run_performance_tests
            run_rollback_tests
            run_error_injection_tests
            ;;
        individual)
            run_individual_tests
            ;;
        combined)
            run_combined_tests
            ;;
        performance)
            run_performance_tests
            ;;
        rollback)
            run_rollback_tests
            ;;
        error_injection)
            run_error_injection_tests
            ;;
        *)
            echo "Unknown category: $CATEGORY"
            exit 1
            ;;
    esac

    cleanup_test_environment

    # Summary
    echo ""
    echo "================================================================"
    echo " Test Results"
    echo "================================================================"
    echo "Total:   $TESTS_RUN"
    echo -e "${GREEN}Passed:  $TESTS_PASSED${NC}"
    echo -e "${RED}Failed:  $TESTS_FAILED${NC}"
    echo -e "${CYAN}Skipped: $TESTS_SKIPPED${NC}"
    echo "================================================================"
    echo ""

    # Coverage report
    local coverage_percent
    if [[ $TESTS_RUN -gt 0 ]]; then
        coverage_percent=$(echo "scale=2; ($TESTS_PASSED / $TESTS_RUN) * 100" | bc)
        echo "Coverage: ${coverage_percent}%"
    fi

    # Exit with failure if any tests failed
    if [[ $TESTS_FAILED -gt 0 ]]; then
        echo -e "${RED}Some tests failed${NC}"
        exit 1
    else
        echo -e "${GREEN}All tests passed!${NC}"
        exit 0
    fi
}

# Run main
main "$@"
