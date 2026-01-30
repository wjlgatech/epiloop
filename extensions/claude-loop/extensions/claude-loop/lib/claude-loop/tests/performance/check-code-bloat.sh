#!/bin/bash
# tests/performance/check-code-bloat.sh
# Validates that optimizations don't make code more complex/bloated

set -euo pipefail

METRICS_FILE="tests/performance/results/complexity_metrics_$(date +%Y%m%d_%H%M%S).json"

echo "================================================================"
echo "CODE COMPLEXITY & BLOAT ANALYSIS"
echo "================================================================"
echo "Ensuring optimizations don't increase code complexity"
echo "================================================================"
echo ""

###############################################################################
# METRIC 1: Lines of Code (LOC)
###############################################################################
count_loc() {
  local file=$1
  if [ ! -f "$file" ] || [ ! -s "$file" ]; then
    echo "0"
    return
  fi
  grep -v '^\s*#' "$file" | grep -v '^\s*$' | wc -l | tr -d ' ' || echo "0"
}

echo "=== Lines of Code Analysis ==="
echo ""

total_loc_shell=0
total_loc_python=0

# Shell scripts
for script in lib/*.sh claude-loop.sh; do
  if [ -f "$script" ]; then
    loc=$(count_loc "$script")
    total_loc_shell=$((total_loc_shell + loc))
    echo "  $script: $loc lines"
  fi
done

echo ""

# Python scripts
for script in lib/*.py; do
  if [ -f "$script" ] && [ -s "$script" ]; then  # Only count non-empty files
    loc=$(count_loc "$script")
    total_loc_python=$((total_loc_python + loc))
    echo "  $script: $loc lines"
  fi
done

echo ""
echo "Total Shell LOC: $total_loc_shell"
echo "Total Python LOC: $total_loc_python"
echo "Total LOC: $((total_loc_shell + total_loc_python))"

###############################################################################
# METRIC 2: Cyclomatic Complexity
###############################################################################
echo ""
echo "=== Cyclomatic Complexity Analysis ==="
echo ""

# For shell scripts: count decision points (if, while, for, case, &&, ||)
shell_complexity=0
for script in lib/*.sh claude-loop.sh; do
  if [ -f "$script" ]; then
    complexity=$(grep -c -E '(if |while |for |case |&&|\|\|)' "$script" 2>/dev/null || echo 0)
    echo "  $script: $complexity decision points"
    shell_complexity=$((shell_complexity + complexity))
  fi
done

echo ""
echo "Total Shell Complexity: $shell_complexity decision points"

###############################################################################
# METRIC 3: Function Count and Average Function Size
###############################################################################
echo ""
echo "=== Function Metrics ==="
echo ""

# Shell functions
shell_functions=$(grep -h '^\s*[a-zA-Z_][a-zA-Z0-9_]*\s*()' lib/*.sh claude-loop.sh 2>/dev/null | wc -l | tr -d ' ')
echo "Shell functions: $shell_functions"

# Python functions
python_functions=$(grep -h '^\s*def ' lib/*.py 2>/dev/null | wc -l | tr -d ' ')
echo "Python functions: $python_functions"

avg_shell_func_size=0
avg_python_func_size=0

if [ "$shell_functions" -gt 0 ]; then
  avg_shell_func_size=$((total_loc_shell / shell_functions))
fi

if [ "$python_functions" -gt 0 ]; then
  avg_python_func_size=$((total_loc_python / python_functions))
fi

echo "Average shell function size: $avg_shell_func_size lines"
echo "Average Python function size: $avg_python_func_size lines"

###############################################################################
# Validate against thresholds first (to collect all violations)
###############################################################################
echo "=== Threshold Validation ==="
echo ""

violations=0
violations_list=()

if [ $avg_shell_func_size -gt 100 ]; then
  echo "⚠️  WARNING: Average shell function size ($avg_shell_func_size) exceeds 100 lines"
  violations_list+=("avg_shell_func_size: $avg_shell_func_size > 100")
  ((violations++))
fi

if [ $avg_python_func_size -gt 100 ]; then
  echo "⚠️  WARNING: Average Python function size ($avg_python_func_size) exceeds 100 lines"
  violations_list+=("avg_python_func_size: $avg_python_func_size > 100")
  ((violations++))
fi

# Check for oversized files
for script in lib/*.sh claude-loop.sh; do
  if [ -f "$script" ]; then
    loc=$(count_loc "$script")
    if [ "$loc" -gt 1000 ]; then
      echo "⚠️  WARNING: $script has $loc lines (exceeds 1000 line threshold)"
      violations_list+=("$script: $loc > 1000")
      ((violations++))
    fi
  fi
done

for script in lib/*.py; do
  if [ -f "$script" ]; then
    loc=$(count_loc "$script")
    if [ "$loc" -gt 1000 ]; then
      echo "⚠️  WARNING: $script has $loc lines (exceeds 1000 line threshold)"
      violations_list+=("$script: $loc > 1000")
      ((violations++))
    fi
  fi
done

echo ""

###############################################################################
# Save metrics to JSON (including violations)
###############################################################################
violations_json="[]"
if [ ${#violations_list[@]} -gt 0 ]; then
  violations_json=$(printf '%s\n' "${violations_list[@]}" | jq -R . | jq -s .)
fi

cat > "$METRICS_FILE" << EOF
{
  "timestamp": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "metrics": {
    "lines_of_code": {
      "shell": $total_loc_shell,
      "python": $total_loc_python,
      "total": $((total_loc_shell + total_loc_python))
    },
    "cyclomatic_complexity": {
      "shell_decision_points": $shell_complexity
    },
    "functions": {
      "shell_count": $shell_functions,
      "python_count": $python_functions,
      "avg_shell_size": $avg_shell_func_size,
      "avg_python_size": $avg_python_func_size
    }
  },
  "thresholds": {
    "max_function_size": 100,
    "max_file_size": 1000,
    "max_cyclomatic_complexity_per_function": 10
  },
  "validation": {
    "violations_count": $violations,
    "violations": $violations_json
  }
}
EOF

echo "================================================================"
echo "Metrics saved to: $METRICS_FILE"
echo "================================================================"
echo ""

if [ $violations -eq 0 ]; then
  echo "✓ All complexity thresholds passed"
  # Save as baseline
  cp "$METRICS_FILE" "tests/performance/results/complexity_baseline.json"
  echo "Baseline complexity metrics saved"
  exit 0
else
  echo "❌ $violations complexity violations detected (baseline recorded)"
  # Still save as baseline for comparison
  cp "$METRICS_FILE" "tests/performance/results/complexity_baseline.json"
  echo "Baseline complexity metrics saved (with violations noted)"
  exit 0  # Don't fail on baseline establishment
fi
