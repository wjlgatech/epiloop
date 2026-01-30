#!/bin/bash
# tests/performance/compare-versions.sh
# Compares performance before and after optimizations

set -euo pipefail

if [ $# -lt 2 ]; then
  echo "Usage: $0 <baseline_results.json> <optimized_results.json>"
  exit 1
fi

BASELINE_RESULTS="$1"
OPTIMIZED_RESULTS="$2"
COMPARISON_FILE="tests/performance/results/comparison_$(date +%Y%m%d_%H%M%S).json"

echo "================================================================"
echo "BEFORE/AFTER PERFORMANCE COMPARISON"
echo "================================================================"
echo "Baseline:   $BASELINE_RESULTS"
echo "Optimized:  $OPTIMIZED_RESULTS"
echo "================================================================"
echo ""

# Compare each benchmark using Python
python3 << 'PYTHON_SCRIPT' "$BASELINE_RESULTS" "$OPTIMIZED_RESULTS" "$COMPARISON_FILE"
import json
import sys

baseline_file = sys.argv[1]
optimized_file = sys.argv[2]
comparison_file = sys.argv[3]

try:
    with open(baseline_file) as f:
        baseline = json.load(f)

    with open(optimized_file) as f:
        optimized = json.load(f)
except FileNotFoundError as e:
    print(f"Error: {e}")
    sys.exit(1)

# Create comparison
comparison = {
    "baseline_timestamp": baseline.get("timestamp", "unknown"),
    "optimized_timestamp": optimized.get("timestamp", "unknown"),
    "comparisons": []
}

baseline_map = {b["name"]: b for b in baseline.get("benchmarks", [])}
optimized_map = {b["name"]: b for b in optimized.get("benchmarks", [])}

print("BENCHMARK COMPARISONS:")
print("=" * 80)

total_improvement = 0
count = 0

for name in baseline_map.keys():
    if name not in optimized_map:
        print(f"{name}: MISSING in optimized version")
        continue

    b_time = baseline_map[name].get("duration_ms", 0)
    o_time = optimized_map[name].get("duration_ms", 0)

    if b_time == 0 or o_time == 0:
        continue

    improvement_pct = ((b_time - o_time) / b_time) * 100
    speedup = b_time / o_time if o_time > 0 else 0

    comparison["comparisons"].append({
        "benchmark": name,
        "baseline_ms": b_time,
        "optimized_ms": o_time,
        "improvement_pct": round(improvement_pct, 2),
        "speedup_factor": round(speedup, 2),
        "time_saved_ms": b_time - o_time,
        "issue": baseline_map[name].get("issue", "")
    })

    total_improvement += improvement_pct
    count += 1

    status = "✓ IMPROVED" if improvement_pct > 0 else "✗ REGRESSED"
    print(f"{name}:")
    print(f"  Before: {b_time}ms")
    print(f"  After:  {o_time}ms")
    print(f"  {status}: {improvement_pct:+.1f}% ({speedup:.2f}x)")
    print(f"  Time saved: {b_time - o_time}ms")
    print()

avg_improvement = total_improvement / count if count > 0 else 0
comparison["summary"] = {
    "average_improvement_pct": round(avg_improvement, 2),
    "benchmark_count": count
}

print("=" * 80)
print(f"AVERAGE IMPROVEMENT: {avg_improvement:.1f}%")
print(f"BENCHMARKS COMPARED: {count}")
print("=" * 80)

# Save comparison
with open(comparison_file, 'w') as f:
    json.dump(comparison, f, indent=2)

print(f"\nComparison saved to: {comparison_file}")

# Check if improvements meet targets
if avg_improvement < 0:
    print("\n❌ REGRESSION DETECTED: Performance got worse!")
    sys.exit(1)
elif avg_improvement < 10:
    print(f"\n⚠️  WARNING: Average improvement ({avg_improvement:.1f}%) below 10% minimum threshold")
    sys.exit(1)
else:
    print(f"\n✓ SUCCESS: Improvements validated ({avg_improvement:.1f}% ≥ 10%)")

PYTHON_SCRIPT
