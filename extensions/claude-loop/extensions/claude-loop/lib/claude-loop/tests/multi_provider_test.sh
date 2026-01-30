#!/usr/bin/env bash
#
# Integration tests for Multi-Provider LLM (US-006)
#
# Tests:
# - Provider selection logic (complexity-based routing)
# - Fallback chain behavior
# - Cost tracking accuracy
# - Provider failure handling
# - Capability filtering (vision, tools, JSON mode)
# - CLI integration (--enable-multi-provider, --cost-report)
#
# Usage:
#   ./tests/multi_provider_test.sh
#   ./tests/multi_provider_test.sh --verbose

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Test counters
TESTS_PASSED=0
TESTS_FAILED=0
VERBOSE=false

# Parse arguments
if [[ "$1" == "--verbose" ]]; then
    VERBOSE=true
fi

# Helper functions
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

log_info() {
    if $VERBOSE; then
        echo -e "${NC}[INFO]${NC} $1"
    fi
}

# Setup
setup_tests() {
    log_info "Setting up test environment"

    # Create test directories
    mkdir -p .claude-loop/logs

    # Backup existing provider usage log if exists
    if [ -f ".claude-loop/logs/provider_usage.jsonl" ]; then
        cp .claude-loop/logs/provider_usage.jsonl .claude-loop/logs/provider_usage.jsonl.backup
    fi

    # Create clean test log
    rm -f .claude-loop/logs/provider_usage.jsonl
}

# Cleanup
cleanup_tests() {
    log_info "Cleaning up test environment"

    # Restore backup if exists
    if [ -f ".claude-loop/logs/provider_usage.jsonl.backup" ]; then
        mv .claude-loop/logs/provider_usage.jsonl.backup .claude-loop/logs/provider_usage.jsonl
    fi
}

# Test 1: Provider selector lists providers
test_provider_list() {
    log_test "Test 1: Provider selector lists configured providers"

    output=$(python3 lib/provider_selector.py list 2>&1)

    if echo "$output" | grep -q "claude-haiku"; then
        log_pass "Provider list includes claude-haiku"
    else
        log_fail "Provider list missing claude-haiku"
    fi

    if echo "$output" | grep -q "litellm/gpt-4o-mini"; then
        log_pass "Provider list includes litellm/gpt-4o-mini"
    else
        log_fail "Provider list missing litellm/gpt-4o-mini"
    fi
}

# Test 2: Complexity-based routing (cheap tier)
test_complexity_cheap() {
    log_test "Test 2: Complexity-based routing selects cheap models for complexity 0-2"

    output=$(python3 lib/provider_selector.py select --complexity 2 2>&1)

    if echo "$output" | grep -qE "(deepseek|gemini-flash|gpt-4o-mini|haiku)"; then
        log_pass "Complexity 2 selected cheap model: $(echo "$output" | grep "Model:")"
    else
        log_fail "Complexity 2 did not select cheap model"
    fi
}

# Test 3: Complexity-based routing (medium tier)
test_complexity_medium() {
    log_test "Test 3: Complexity-based routing selects medium models for complexity 3-5"

    output=$(python3 lib/provider_selector.py select --complexity 4 2>&1)

    if echo "$output" | grep -qE "(sonnet|gpt-4o|gemini-pro)"; then
        log_pass "Complexity 4 selected medium model: $(echo "$output" | grep "Model:")"
    else
        log_fail "Complexity 4 did not select medium model"
    fi
}

# Test 4: Complexity-based routing (powerful tier)
test_complexity_powerful() {
    log_test "Test 4: Complexity-based routing selects powerful models for complexity 6+"

    output=$(python3 lib/provider_selector.py select --complexity 7 2>&1)

    if echo "$output" | grep -qE "(opus|o1)"; then
        log_pass "Complexity 7 selected powerful model: $(echo "$output" | grep "Model:")"
    else
        log_fail "Complexity 7 did not select powerful model"
    fi
}

# Test 5: Capability filtering (vision)
test_capability_vision() {
    log_test "Test 5: Capability filtering for vision requirement"

    output=$(python3 lib/provider_selector.py select --complexity 2 --requires-vision 2>&1)

    # Check that selected model supports vision
    if echo "$output" | grep -qE "(gpt-4o|gemini|claude|haiku)"; then
        log_pass "Vision requirement selected vision-capable model"
    else
        log_fail "Vision requirement did not select vision-capable model"
    fi

    # DeepSeek doesn't support vision, should not be selected
    if ! echo "$output" | grep -q "deepseek"; then
        log_pass "Vision requirement filtered out non-vision models (deepseek)"
    else
        log_fail "Vision requirement did not filter out deepseek"
    fi
}

# Test 6: Capability filtering (tools)
test_capability_tools() {
    log_test "Test 6: Capability filtering for tools requirement"

    output=$(python3 lib/provider_selector.py select --complexity 7 --requires-tools 2>&1)

    # O1 doesn't support tools, should not be selected
    if ! echo "$output" | grep -qE "Model: o1"; then
        log_pass "Tools requirement filtered out non-tool models (o1)"
    else
        log_fail "Tools requirement selected o1 which doesn't support tools"
    fi
}

# Test 7: Fallback chain
test_fallback_chain() {
    log_test "Test 7: Fallback chain includes reliable fallbacks"

    output=$(python3 lib/provider_selector.py fallback-chain --provider "litellm/gpt-4o-mini" 2>&1)

    if echo "$output" | grep -q "claude-sonnet"; then
        log_pass "Fallback chain includes claude-sonnet"
    else
        log_fail "Fallback chain missing claude-sonnet"
    fi

    if echo "$output" | grep -q "claude-code-cli"; then
        log_pass "Fallback chain includes claude-code-cli as ultimate fallback"
    else
        log_fail "Fallback chain missing claude-code-cli"
    fi
}

# Test 8: Provider selection speed (<50ms requirement)
test_selection_speed() {
    log_test "Test 8: Provider selection completes in <50ms"

    output=$(python3 lib/provider_selector.py select --complexity 3 2>&1)

    if echo "$output" | grep -qE "Selection time: [0-4]?[0-9]\.[0-9]+ms"; then
        selection_time=$(echo "$output" | grep "Selection time:" | grep -oE "[0-9]+\.[0-9]+")
        log_pass "Provider selection completed in ${selection_time}ms (<50ms)"
    else
        log_fail "Provider selection took >50ms or time not reported"
    fi
}

# Test 9: JSON output format
test_json_output() {
    log_test "Test 9: JSON output format is valid"

    output=$(python3 lib/provider_selector.py select --complexity 3 --json 2>&1)

    if echo "$output" | python3 -m json.tool > /dev/null 2>&1; then
        log_pass "JSON output is valid"
    else
        log_fail "JSON output is invalid"
    fi

    if echo "$output" | grep -q '"provider"'; then
        log_pass "JSON output includes provider field"
    else
        log_fail "JSON output missing provider field"
    fi
}

# Test 10: Cost report with no data
test_cost_report_no_data() {
    log_test "Test 10: Cost report handles no data gracefully"

    # Ensure no log file exists
    rm -f .claude-loop/logs/provider_usage.jsonl

    output=$(python3 lib/cost_report.py summary 2>&1)

    if echo "$output" | grep -q "No provider usage data found"; then
        log_pass "Cost report handles empty log gracefully"
    else
        log_fail "Cost report did not handle empty log"
    fi
}

# Test 11: Cost report with test data
test_cost_report_with_data() {
    log_test "Test 11: Cost report generates report from test data"

    # Create test data
    cat > .claude-loop/logs/provider_usage.jsonl << 'EOF'
{"timestamp": "2026-01-20T10:00:00Z", "story_id": "US-001", "iteration": 1, "provider": "deepseek", "model": "deepseek-chat", "complexity": 2, "input_tokens": 1500, "output_tokens": 800, "cost_usd": 0.434, "latency_ms": 1250, "success": true, "fallback_used": false}
{"timestamp": "2026-01-20T10:05:00Z", "story_id": "US-001", "iteration": 2, "provider": "litellm", "model": "gpt-4o-mini", "complexity": 2, "input_tokens": 1800, "output_tokens": 900, "cost_usd": 0.81, "latency_ms": 1100, "success": true, "fallback_used": false}
EOF

    output=$(python3 lib/cost_report.py summary 2>&1)

    if echo "$output" | grep -q "2 requests"; then
        log_pass "Cost report shows correct request count"
    else
        log_fail "Cost report shows incorrect request count"
    fi

    if echo "$output" | grep -q "saved"; then
        log_pass "Cost report shows savings calculation"
    else
        log_fail "Cost report missing savings calculation"
    fi
}

# Test 12: Cost report JSON output
test_cost_report_json() {
    log_test "Test 12: Cost report JSON output is valid"

    output=$(python3 lib/cost_report.py report --json 2>&1)

    if echo "$output" | python3 -m json.tool > /dev/null 2>&1; then
        log_pass "Cost report JSON output is valid"
    else
        log_fail "Cost report JSON output is invalid"
    fi
}

# Test 13: CLI --cost-report integration
test_cli_cost_report() {
    log_test "Test 13: CLI --cost-report flag works"

    # Use timeout to prevent hanging
    output=$(timeout 10 ./claude-loop.sh --cost-report 7 2>&1 || true)

    if echo "$output" | grep -q "Cost Analysis Report"; then
        log_pass "CLI --cost-report generates report"
    else
        log_info "CLI output: $output"
        log_fail "CLI --cost-report did not generate report"
    fi
}

# Test 14: YAML configuration loading
test_yaml_config_loading() {
    log_test "Test 14: YAML configuration loads correctly"

    if [ ! -f "lib/llm_providers.yaml" ]; then
        log_fail "lib/llm_providers.yaml not found"
        return
    fi

    # Test that provider_selector can load YAML config
    output=$(python3 lib/provider_selector.py list --verbose 2>&1)

    if echo "$output" | grep -q "capabilities"; then
        log_pass "YAML configuration loaded with capabilities"
    else
        log_fail "YAML configuration not loaded correctly"
    fi
}

# Test 15: Preferred provider override
test_preferred_provider() {
    log_test "Test 15: Preferred provider override works"

    output=$(python3 lib/provider_selector.py select --complexity 2 --preferred "claude-opus" 2>&1)

    if echo "$output" | grep -q "claude-opus"; then
        log_pass "Preferred provider override selected claude-opus"
    else
        log_fail "Preferred provider override did not work"
    fi

    if echo "$output" | grep -q "Preferred provider specified"; then
        log_pass "Reasoning shows preferred provider override"
    else
        log_fail "Reasoning missing preferred provider note"
    fi
}

# Main test execution
main() {
    echo ""
    echo "================================================================"
    echo " Multi-Provider LLM Integration Tests (US-006)"
    echo "================================================================"
    echo ""

    setup_tests

    # Run all tests
    test_provider_list
    test_complexity_cheap
    test_complexity_medium
    test_complexity_powerful
    test_capability_vision
    test_capability_tools
    test_fallback_chain
    test_selection_speed
    test_json_output
    test_cost_report_no_data
    test_cost_report_with_data
    test_cost_report_json
    test_cli_cost_report
    test_yaml_config_loading
    test_preferred_provider

    cleanup_tests

    # Summary
    echo ""
    echo "================================================================"
    echo " Test Results"
    echo "================================================================"
    echo -e "Passed: ${GREEN}${TESTS_PASSED}${NC}"
    echo -e "Failed: ${RED}${TESTS_FAILED}${NC}"
    echo "================================================================"
    echo ""

    # Exit with failure if any tests failed
    if [ $TESTS_FAILED -gt 0 ]; then
        exit 1
    fi
}

# Run tests
main "$@"
