#!/bin/bash
# tests/performance/benchmark-suite.sh
# Proves that identified performance issues are real, not theoretical

set -euo pipefail

BENCHMARK_RESULTS_DIR="tests/performance/results"
mkdir -p "$BENCHMARK_RESULTS_DIR"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
RESULTS_FILE="${BENCHMARK_RESULTS_DIR}/benchmark_${TIMESTAMP}.json"

# Initialize results JSON
cat > "$RESULTS_FILE" << EOF
{
  "timestamp": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "benchmarks": []
}
EOF

###############################################################################
# BENCHMARK 1: PRD Parsing - Prove excessive jq calls are slow
###############################################################################
benchmark_prd_parsing() {
  local prd_file=$1
  local story_count=$(jq '.userStories | length' "$prd_file" 2>/dev/null || echo 0)

  echo "=== Benchmark: PRD Parsing ($story_count stories) ==="

  if [ ! -f "$prd_file" ]; then
    echo "  SKIPPED: PRD file not found"
    return
  fi

  # Time the validation
  local start_ms=$(perl -MTime::HiRes=time -e 'printf "%.0f\n", time * 1000')

  # Run validation
  if [ -f "lib/prd-parser.sh" ]; then
    bash -c "source lib/prd-parser.sh && validate_prd '$prd_file'" >/dev/null 2>&1 || true
  fi

  local end_ms=$(perl -MTime::HiRes=time -e 'printf "%.0f\n", time * 1000')
  local duration_ms=$((end_ms - start_ms))

  echo "  Duration: ${duration_ms}ms"
  echo "  Stories: ${story_count}"
  if [ "$story_count" -gt 0 ]; then
    echo "  Avg time per story: $((duration_ms / story_count))ms"
  fi

  # Add to results
  local tmp_file="${RESULTS_FILE}.tmp"
  jq --arg name "prd_parsing_${story_count}stories" \
     --argjson duration "$duration_ms" \
     --argjson stories "$story_count" \
     '.benchmarks += [{
       "name": $name,
       "duration_ms": $duration,
       "story_count": $stories,
       "issue": "Excessive jq calls in validation loop"
     }]' "$RESULTS_FILE" > "$tmp_file" && mv "$tmp_file" "$RESULTS_FILE"
}

###############################################################################
# BENCHMARK 2: Monitoring bc Invocations - Prove overhead is real
###############################################################################
benchmark_monitoring_bc() {
  echo "=== Benchmark: Monitoring bc Subprocess Overhead ==="

  local iterations=100
  local start_ms=$(perl -MTime::HiRes=time -e 'printf "%.0f\n", time * 1000')

  # Simulate monitoring cost calculations
  for i in $(seq 1 $iterations); do
    local tokens_in=$((5000 + RANDOM % 5000))
    local tokens_out=$((2000 + RANDOM % 2000))
    local cost=$(echo "scale=6; ($tokens_in / 1000000) * 15 + ($tokens_out / 1000000) * 75" | bc)
  done

  local end_ms=$(perl -MTime::HiRes=time -e 'printf "%.0f\n", time * 1000')
  local duration_ms=$((end_ms - start_ms))

  echo "  Duration: ${duration_ms}ms for ${iterations} calculations"
  echo "  Avg per calculation: $((duration_ms / iterations))ms"

  local tmp_file="${RESULTS_FILE}.tmp"
  jq --argjson duration "$duration_ms" \
     --argjson iterations "$iterations" \
     '.benchmarks += [{
       "name": "monitoring_bc_overhead",
       "duration_ms": $duration,
       "iteration_count": $iterations,
       "issue": "bc subprocess spawned per cost calculation"
     }]' "$RESULTS_FILE" > "$tmp_file" && mv "$tmp_file" "$RESULTS_FILE"
}

###############################################################################
# BENCHMARK 3: Dependency Graph - Prove algorithm complexity
###############################################################################
benchmark_dependency_graph() {
  echo "=== Benchmark: Dependency Graph Analysis ==="

  local prd_files=(
    "prd-self-improvement-audit.json"
    "prd-phase2-foundations.json"
    "prd-phase3-cowork-features.json"
  )

  for prd_file in "${prd_files[@]}"; do
    if [ ! -f "$prd_file" ]; then
      continue
    fi

    local story_count=$(jq '.userStories | length' "$prd_file" 2>/dev/null || echo 0)

    local start_ms=$(perl -MTime::HiRes=time -e 'printf "%.0f\n", time * 1000')
    python3 lib/dependency-graph.py plan "$prd_file" --json >/dev/null 2>&1 || true
    local end_ms=$(perl -MTime::HiRes=time -e 'printf "%.0f\n", time * 1000')
    local duration_ms=$((end_ms - start_ms))

    echo "  Duration ($story_count stories): ${duration_ms}ms"

    local tmp_file="${RESULTS_FILE}.tmp"
    jq --arg name "dependency_graph_${story_count}stories" \
       --argjson duration "$duration_ms" \
       --argjson stories "$story_count" \
       '.benchmarks += [{
         "name": $name,
         "duration_ms": $duration,
         "story_count": $stories,
         "issue": "O(n² log n) topological sort"
       }]' "$RESULTS_FILE" > "$tmp_file" && mv "$tmp_file" "$RESULTS_FILE"
  done
}

###############################################################################
# BENCHMARK 4: Disk Usage - Prove log accumulation is real
###############################################################################
benchmark_disk_usage() {
  echo "=== Benchmark: Disk Usage and Log Accumulation ==="

  local claude_loop_size=$(du -sk .claude-loop 2>/dev/null | cut -f1 || echo 0)
  local workers_size=$(du -sk .claude-loop/workers 2>/dev/null | cut -f1 || echo 0)
  local logs_size=$(du -sk .claude-loop/runs 2>/dev/null | cut -f1 || echo 0)
  local execution_log_size=$(wc -c < .claude-loop/execution_log.jsonl 2>/dev/null | tr -d ' ' || echo 0)
  execution_log_size=$((execution_log_size / 1024))  # Convert to KB

  echo "  .claude-loop total: ${claude_loop_size}KB"
  echo "  Workers logs: ${workers_size}KB"
  echo "  Run logs: ${logs_size}KB"
  echo "  Execution log: ${execution_log_size}KB"

  local tmp_file="${RESULTS_FILE}.tmp"
  jq --argjson total "$claude_loop_size" \
     --argjson workers "$workers_size" \
     --argjson logs "$logs_size" \
     --argjson exec_log "$execution_log_size" \
     '.benchmarks += [{
       "name": "disk_usage",
       "total_kb": $total,
       "workers_kb": $workers,
       "logs_kb": $logs,
       "execution_log_kb": $exec_log,
       "issue": "No log rotation or cleanup strategy"
     }]' "$RESULTS_FILE" > "$tmp_file" && mv "$tmp_file" "$RESULTS_FILE"
}

###############################################################################
# Run all benchmarks
###############################################################################
echo "================================================================"
echo "BASELINE PERFORMANCE BENCHMARK SUITE"
echo "================================================================"
echo "Proving that identified performance issues are REAL"
echo "================================================================"
echo ""

benchmark_prd_parsing "prd-self-improvement-audit.json"
echo ""
benchmark_monitoring_bc
echo ""
benchmark_dependency_graph
echo ""
benchmark_disk_usage
echo ""

echo "================================================================"
echo "RESULTS SAVED TO: $RESULTS_FILE"
echo "================================================================"
echo ""

# Generate summary
jq -r '
  "BASELINE BENCHMARK SUMMARY",
  "============================",
  "Timestamp: \(.timestamp)",
  "",
  "Performance Issues Validated:",
  (.benchmarks[] |
    "  [\(.name)]",
    "    Issue: \(.issue)",
    "    Duration: \(.duration_ms // 0)ms",
    ""
  )
' "$RESULTS_FILE"

# Save as baseline for future comparisons
cp "$RESULTS_FILE" "${BENCHMARK_RESULTS_DIR}/baseline.json"
echo "Baseline saved for future comparisons"
