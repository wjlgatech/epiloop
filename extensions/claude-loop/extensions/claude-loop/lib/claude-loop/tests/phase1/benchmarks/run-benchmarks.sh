#!/usr/bin/env bash
# Performance Benchmark Suite for Phase 1 Features
# Tests performance characteristics and overhead of new features

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
cd "$PROJECT_ROOT"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Benchmark thresholds
PROGRESS_OVERHEAD_THRESHOLD=5  # <5% of total execution time
WORKSPACE_MOUNT_THRESHOLD=2000 # <2 seconds for 1000 files (in ms)
SAFETY_CHECK_THRESHOLD=1000    # <1 second for 100 file changes (in ms)
TEMPLATE_GEN_THRESHOLD=500     # <500ms for complex templates

# Test results
declare -a BENCHMARK_RESULTS=()
TOTAL_BENCHMARKS=0
PASSED_BENCHMARKS=0
FAILED_BENCHMARKS=0

# Utility: Get millisecond timestamp (cross-platform)
get_ms_timestamp() {
    if command -v perl >/dev/null 2>&1; then
        perl -MTime::HiRes=time -e 'printf "%.0f\n", time * 1000'
    else
        # Fallback for systems without perl
        date +%s000 | sed 's/..$//'
    fi
}

# Utility: Calculate duration in milliseconds
calculate_duration() {
    local start=$1
    local end=$2
    echo $((end - start))
}

# Utility: Run command and measure time
measure_execution_time() {
    local start=$(get_ms_timestamp)
    "$@" >/dev/null 2>&1
    local end=$(get_ms_timestamp)
    calculate_duration $start $end
}

# Utility: Record benchmark result
record_result() {
    local name=$1
    local duration=$2
    local threshold=$3
    local unit=${4:-ms}

    TOTAL_BENCHMARKS=$((TOTAL_BENCHMARKS + 1))

    if [ "$duration" -le "$threshold" ]; then
        PASSED_BENCHMARKS=$((PASSED_BENCHMARKS + 1))
        echo -e "${GREEN}✓${NC} $name: ${duration}${unit} (threshold: ${threshold}${unit})"
        BENCHMARK_RESULTS+=("PASS|$name|$duration|$threshold|$unit")
    else
        FAILED_BENCHMARKS=$((FAILED_BENCHMARKS + 1))
        echo -e "${RED}✗${NC} $name: ${duration}${unit} (threshold: ${threshold}${unit}) ${RED}EXCEEDED${NC}"
        BENCHMARK_RESULTS+=("FAIL|$name|$duration|$threshold|$unit")
    fi
}

# Utility: Print section header
print_header() {
    echo ""
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
}

# Setup: Create temporary test environment
setup_test_env() {
    echo -e "${YELLOW}Setting up test environment...${NC}"

    # Create temporary directory
    TEST_DIR=$(mktemp -d -t claude-loop-bench-XXXXXX)
    export TEST_DIR

    # Create test PRD
    cat > "$TEST_DIR/test-prd.json" <<'EOF'
{
  "project": "benchmark-test",
  "branchName": "feature/benchmark-test",
  "description": "Test PRD for benchmarking",
  "userStories": [
    {
      "id": "BENCH-001",
      "title": "Test Story",
      "description": "A test story for benchmarking",
      "acceptanceCriteria": [
        "Criterion 1",
        "Criterion 2",
        "Criterion 3"
      ],
      "priority": 1,
      "passes": false,
      "notes": ""
    }
  ]
}
EOF

    # Create test files for workspace benchmarking
    mkdir -p "$TEST_DIR/workspace"
    for i in {1..1000}; do
        echo "test content $i" > "$TEST_DIR/workspace/file_$i.txt"
    done

    # Create test files for safety checker
    mkdir -p "$TEST_DIR/changes"
    for i in {1..100}; do
        echo "original content $i" > "$TEST_DIR/changes/file_$i.txt"
    done

    echo -e "${GREEN}✓${NC} Test environment created at $TEST_DIR"
}

# Cleanup: Remove temporary test environment
cleanup_test_env() {
    if [ -n "${TEST_DIR:-}" ] && [ -d "$TEST_DIR" ]; then
        rm -rf "$TEST_DIR"
        echo -e "${GREEN}✓${NC} Test environment cleaned up"
    fi
}

# Benchmark 1: Progress Indicator Overhead
benchmark_progress_overhead() {
    print_header "Benchmark 1: Progress Indicator Overhead"

    if [ ! -f "lib/progress-indicators.sh" ]; then
        echo -e "${YELLOW}⊘${NC} Skipping: lib/progress-indicators.sh not found"
        return
    fi

    source lib/progress-indicators.sh

    # Measure baseline: realistic simulated work (file operations)
    local baseline_start=$(get_ms_timestamp)
    for i in {1..1000}; do
        echo "test content line $i" >> "$TEST_DIR/baseline_work.txt"
    done
    local baseline_end=$(get_ms_timestamp)
    local baseline_duration=$(calculate_duration $baseline_start $baseline_end)

    # Measure with progress indicators (realistic update frequency - every 100 operations)
    local progress_start=$(get_ms_timestamp)
    init_progress "$TEST_DIR/test-prd.json" "BENCH-001" >/dev/null 2>&1 || true
    for i in {1..1000}; do
        echo "test content line $i" >> "$TEST_DIR/progress_work.txt"
        # Only update progress every 100 iterations (realistic frequency)
        if [ $((i % 100)) -eq 0 ]; then
            update_progress_action "Processing batch $i" >/dev/null 2>&1 || true
        fi
    done
    cleanup_progress >/dev/null 2>&1 || true
    local progress_end=$(get_ms_timestamp)
    local progress_duration=$(calculate_duration $progress_start $progress_end)

    # Calculate overhead percentage
    local overhead=$((((progress_duration - baseline_duration) * 100) / baseline_duration))

    echo "  Baseline execution: ${baseline_duration}ms"
    echo "  With progress indicators: ${progress_duration}ms"
    echo "  Progress updates: 10 (every 100 operations)"
    echo "  Overhead: ${overhead}%"

    record_result "Progress indicator overhead" "$overhead" "$PROGRESS_OVERHEAD_THRESHOLD" "%"
}

# Benchmark 2: Workspace Mounting Time
benchmark_workspace_mounting() {
    print_header "Benchmark 2: Workspace Mounting Time"

    if [ ! -f "lib/workspace-manager.sh" ]; then
        echo -e "${YELLOW}⊘${NC} Skipping: lib/workspace-manager.sh not found"
        return
    fi

    source lib/workspace-manager.sh

    # Create temporary worker directory
    local worker_dir="$TEST_DIR/worker"
    mkdir -p "$worker_dir"

    # Set environment variables
    export WORKSPACE_FOLDERS="$TEST_DIR/workspace"
    export WORKSPACE_REPO_ROOT="$TEST_DIR"
    export WORKER_DIR="$worker_dir"

    # Measure workspace validation time
    local start=$(get_ms_timestamp)
    validate_workspace_folders >/dev/null 2>&1 || true
    local end=$(get_ms_timestamp)
    local duration=$(calculate_duration $start $end)

    echo "  Files in workspace: 1000"
    echo "  Validation time: ${duration}ms"

    record_result "Workspace validation (1000 files)" "$duration" "$WORKSPACE_MOUNT_THRESHOLD"

    # Cleanup
    unset WORKSPACE_FOLDERS WORKSPACE_REPO_ROOT WORKER_DIR
}

# Benchmark 3: Safety Checker Scan Time
benchmark_safety_checker() {
    print_header "Benchmark 3: Safety Checker Scan Time"

    if [ ! -f "lib/safety-checker.sh" ]; then
        echo -e "${YELLOW}⊘${NC} Skipping: lib/safety-checker.sh not found"
        return
    fi

    source lib/safety-checker.sh

    # Modify files to create changes
    for i in {1..100}; do
        echo "modified content $i" > "$TEST_DIR/changes/file_$i.txt"
    done

    # Create a git diff-like output
    local diff_file="$TEST_DIR/changes.diff"
    cd "$TEST_DIR/changes"
    git init >/dev/null 2>&1
    git add . >/dev/null 2>&1
    git diff --cached > "$diff_file" 2>/dev/null || true
    cd "$PROJECT_ROOT"

    # Measure safety check time
    export SAFETY_LEVEL="normal"
    local start=$(get_ms_timestamp)
    check_destructive_operations "$diff_file" >/dev/null 2>&1 || true
    local end=$(get_ms_timestamp)
    local duration=$(calculate_duration $start $end)

    echo "  Files changed: 100"
    echo "  Safety check time: ${duration}ms"

    record_result "Safety checker (100 file changes)" "$duration" "$SAFETY_CHECK_THRESHOLD"

    unset SAFETY_LEVEL
}

# Benchmark 4: Template Generation Time
benchmark_template_generation() {
    print_header "Benchmark 4: Template Generation Time"

    if [ ! -f "lib/template-generator.sh" ]; then
        echo -e "${YELLOW}⊘${NC} Skipping: lib/template-generator.sh not found"
        return
    fi

    # Test all templates
    local templates=("web-feature" "api-endpoint" "refactoring" "bug-fix" "documentation" "testing")

    for template in "${templates[@]}"; do
        local output_file="$TEST_DIR/generated-${template}.json"

        local start=$(get_ms_timestamp)
        bash lib/template-generator.sh generate "$template" \
            --project-name "test-project" \
            --feature-name "test-feature" \
            --endpoint-name "/api/test" \
            --refactor-target "test-module" \
            --issue-id "BUG-123" \
            --doc-type "guide" \
            --test-type "unit" \
            --output "$output_file" >/dev/null 2>&1 || true
        local end=$(get_ms_timestamp)
        local duration=$(calculate_duration $start $end)

        echo "  Template: $template - ${duration}ms"

        # Only record the slowest template against threshold
        if [ "$template" = "web-feature" ]; then
            record_result "Template generation (web-feature)" "$duration" "$TEMPLATE_GEN_THRESHOLD"
        fi
    done
}

# Benchmark 5: Git Diff Performance (for safety checker optimization)
benchmark_git_diff() {
    print_header "Benchmark 5: Git Diff Performance"

    # Create a git repo with changes
    local git_test="$TEST_DIR/git-test"
    mkdir -p "$git_test"
    cd "$git_test"
    git init >/dev/null 2>&1

    # Create initial commit
    for i in {1..100}; do
        echo "initial $i" > "file_$i.txt"
    done
    git add . >/dev/null 2>&1
    git commit -m "Initial" >/dev/null 2>&1

    # Make changes
    for i in {1..100}; do
        echo "modified $i" >> "file_$i.txt"
    done

    # Measure git diff time
    local start=$(get_ms_timestamp)
    git diff > /dev/null 2>&1
    local end=$(get_ms_timestamp)
    local duration=$(calculate_duration $start $end)

    cd "$PROJECT_ROOT"

    echo "  Git diff time (100 modified files): ${duration}ms"
    echo -e "  ${GREEN}✓${NC} (Reference only, no threshold)"
}

# Generate performance report
generate_report() {
    print_header "Performance Report"

    echo ""
    echo "Summary:"
    echo "  Total benchmarks: $TOTAL_BENCHMARKS"
    echo -e "  ${GREEN}Passed: $PASSED_BENCHMARKS${NC}"
    if [ $FAILED_BENCHMARKS -gt 0 ]; then
        echo -e "  ${RED}Failed: $FAILED_BENCHMARKS${NC}"
    else
        echo "  Failed: $FAILED_BENCHMARKS"
    fi
    echo ""

    # Save results to file
    local results_file="$SCRIPT_DIR/benchmark-results.txt"
    {
        echo "Claude-Loop Phase 1 Performance Benchmarks"
        echo "=========================================="
        echo ""
        echo "Run Date: $(date)"
        echo "System: $(uname -s) $(uname -m)"
        echo ""
        echo "Results:"
        echo "--------"
        for result in "${BENCHMARK_RESULTS[@]}"; do
            IFS='|' read -r status name duration threshold unit <<< "$result"
            printf "  [%s] %s: %s%s (threshold: %s%s)\n" "$status" "$name" "$duration" "$unit" "$threshold" "$unit"
        done
        echo ""
        echo "Summary:"
        echo "  Total: $TOTAL_BENCHMARKS"
        echo "  Passed: $PASSED_BENCHMARKS"
        echo "  Failed: $FAILED_BENCHMARKS"
    } > "$results_file"

    echo "Results saved to: $results_file"
    echo ""

    if [ $FAILED_BENCHMARKS -eq 0 ]; then
        echo -e "${GREEN}✓ All benchmarks passed!${NC}"
        return 0
    else
        echo -e "${RED}✗ Some benchmarks failed. See results above.${NC}"
        return 1
    fi
}

# Main execution
main() {
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BLUE}Phase 1 Performance Benchmark Suite${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""

    # Setup
    setup_test_env

    # Run benchmarks
    benchmark_progress_overhead
    benchmark_workspace_mounting
    benchmark_safety_checker
    benchmark_template_generation
    benchmark_git_diff

    # Generate report
    local exit_code=0
    generate_report || exit_code=$?

    # Cleanup
    cleanup_test_env

    exit $exit_code
}

# Trap cleanup on exit
trap cleanup_test_env EXIT INT TERM

# Run main
main "$@"
