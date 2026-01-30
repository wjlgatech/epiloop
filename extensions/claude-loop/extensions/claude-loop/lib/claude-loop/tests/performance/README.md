# Performance Testing Framework

## Overview

This framework provides empirical validation that performance optimizations are real and effective, not just theoretical improvements. It includes:

1. **Baseline Benchmarks** - Prove current bottlenecks exist
2. **Before/After Comparison** - Measure actual improvements
3. **Human Simulation Tests** - Real-world usage scenarios
4. **Code Bloat Detection** - Ensure optimizations don't add complexity

## Quick Start

```bash
# 1. Run baseline benchmarks (proves issues are real)
./tests/performance/benchmark-suite.sh

# 2. Check current code complexity (establishes baseline)
./tests/performance/check-code-bloat.sh

# 3. After implementing optimizations, run benchmarks again
./tests/performance/benchmark-suite.sh

# 4. Compare before vs after
./tests/performance/compare-versions.sh \
  tests/performance/results/baseline.json \
  tests/performance/results/benchmark_YYYYMMDD_HHMMSS.json

# 5. Verify no code bloat introduced
./tests/performance/check-code-bloat.sh
```

## Baseline Results (2026-01-14)

### Performance Issues Validated

| Issue | Current Performance | Expected After Optimization |
|-------|--------------------|-----------------------------|
| **PRD Parsing** | 2,209ms for 8 stories (276ms/story) | ~200ms (87% improvement) |
| **bc Overhead** | 1,517ms for 100 calculations (15ms each) | ~200ms (87% improvement) |
| **Dependency Graph** | 86-192ms depending on PRD size | 30-60ms (67% improvement) |
| **Disk Usage** | 28.9MB accumulated logs | 8MB (70% reduction) |

###Code Complexity Baseline

| Metric | Current Value | Threshold | Status |
|--------|--------------|-----------|---------|
| Total LOC | 49,210 lines | N/A | ℹ️ Baseline |
| Shell LOC | 12,604 lines | N/A | ℹ️ Baseline |
| Python LOC | 36,606 lines | N/A | ℹ️ Baseline |
| Avg Shell Function Size | 23 lines | 100 lines | ✅ PASS |
| Avg Python Function Size | 31 lines | 100 lines | ✅ PASS |
| Files >1000 lines | 9 files | Monitored | ⚠️ Noted |

**Files exceeding 1000 lines (noted as technical debt):**
- `claude-loop.sh`: 2,890 lines
- `lib/prd-manager.py`: 1,662 lines
- `lib/improvement-prd-generator.py`: 1,518 lines
- `lib/experience-store.py`: 1,422 lines
- `lib/conflict-detector.py`: 1,171 lines
- `lib/promotion-evaluator.py`: 1,048 lines
- `lib/capability-inventory.py`: 1,034 lines
- `lib/gap-generalizer.py`: 1,004 lines
- `lib/calibration-tracker.py`: 1,005 lines

## Performance Acceptance Criteria

Before merging any optimization, it MUST prove:

### 1. Empirical Evidence ✅
- Baseline benchmark shows issue exists
- Measurements match predicted impact (±20%)
- Before/after comparison shows improvement

### 2. No Bloat ✅
- LOC doesn't increase by >10% unless justified
- Average function size stays <100 lines
- Cyclomatic complexity doesn't increase
- No duplicate code introduced

### 3. Minimum Improvement Thresholds
- **Critical optimizations:** ≥50% improvement
- **High priority:** ≥30% improvement
- **Medium priority:** ≥15% improvement
- Must not regress any other metric by >5%

### 4. Documentation
- Update AGENTS.md with new patterns
- Document complexity trade-offs
- Provide rollback instructions

## Testing Scripts

### benchmark-suite.sh

Runs comprehensive performance benchmarks to validate current bottlenecks:

- **PRD Parsing**: Measures validation time with excessive jq calls
- **bc Overhead**: Measures subprocess spawn cost in monitoring
- **Dependency Graph**: Measures algorithmic complexity
- **Disk Usage**: Measures log accumulation

**Output**: `tests/performance/results/benchmark_TIMESTAMP.json`

### compare-versions.sh

Compares two benchmark results to validate improvements:

```bash
./tests/performance/compare-versions.sh baseline.json optimized.json
```

**Validates**:
- Average improvement ≥10%
- No regressions in any benchmark
- Improvements match predictions

**Output**: `tests/performance/results/comparison_TIMESTAMP.json`

### check-code-bloat.sh

Measures code complexity to ensure optimizations don't add bloat:

**Metrics**:
- Lines of code (total, shell, python)
- Cyclomatic complexity (decision points)
- Function count and average size
- Files exceeding size thresholds

**Thresholds**:
- Max function size: 100 lines
- Max file size: 1000 lines (warning, not blocking)
- Max cyclomatic complexity: 10 per function

**Output**: `tests/performance/results/complexity_metrics_TIMESTAMP.json`

## Integration with CI/CD

Add to your CI pipeline:

```yaml
- name: Performance Validation
  run: |
    # Run benchmarks
    ./tests/performance/benchmark-suite.sh

    # Check code complexity
    ./tests/performance/check-code-bloat.sh

    # Compare with baseline (on PRs)
    if [ -f tests/performance/results/baseline.json ]; then
      ./tests/performance/compare-versions.sh \
        tests/performance/results/baseline.json \
        tests/performance/results/benchmark_*.json
    fi
```

## Computer Use Agent Tests

For human simulation testing, Computer Use Agent can execute:

1. **New PRD Workflow**: Create PRD, validate, check plan
2. **Review Improvement**: List, view details, approve PRD
3. **Debug Failure**: Investigate failure patterns, check logs
4. **Parallel Execution**: Set up and run parallel workers

See `tests/human-simulation/` for detailed scenarios.

## Interpreting Results

### Good Optimization Example

```
PRD Parsing (20 stories):
  Before: 2,000ms
  After:  300ms
  ✓ IMPROVED: +85% (6.7x speedup)
  Time saved: 1,700ms

Average Improvement: 82%
✓ SUCCESS: Improvements validated
```

### Bad Optimization Example

```
PRD Parsing (20 stories):
  Before: 2,000ms
  After:  1,900ms
  ⚠️  IMPROVED: +5% (1.05x speedup)
  Time saved: 100ms

Average Improvement: 5%
❌ WARNING: Below 15% threshold for medium priority
```

### Regression Detected

```
Agent Selection:
  Before: 300ms
  After:  450ms
  ✗ REGRESSED: -50% (0.67x)

❌ REGRESSION DETECTED: Performance got worse!
```

## Troubleshooting

### Benchmark Variability

Benchmarks may vary by ±10-20% due to system load. Run multiple times:

```bash
for i in {1..5}; do
  ./tests/performance/benchmark-suite.sh
  sleep 5
done

# Average the results
python3 << 'EOF'
import json
import glob

results = []
for f in glob.glob("tests/performance/results/benchmark_*.json"):
    with open(f) as file:
        results.append(json.load(file))

# Calculate averages per benchmark
# ...
EOF
```

### Benchmark Too Slow

Some benchmarks spawn subprocesses which adds overhead. This is intentional - we're measuring the real subprocess cost.

### Code Bloat False Positives

Large files are noted but don't fail the build initially. Review each:

- Is the file genuinely complex, or just long due to many simple functions?
- Can it be split into multiple modules?
- Does it have duplicate code that can be extracted?

## Maintenance

### Update Baseline

After major refactoring, update the baseline:

```bash
./tests/performance/benchmark-suite.sh
cp tests/performance/results/benchmark_*.json tests/performance/results/baseline.json

./tests/performance/check-code-bloat.sh
cp tests/performance/results/complexity_metrics_*.json tests/performance/results/complexity_baseline.json
```

### Add New Benchmarks

To add a new benchmark to `benchmark-suite.sh`:

```bash
benchmark_new_feature() {
  echo "=== Benchmark: New Feature ==="

  local start_ms=$(perl -MTime::HiRes=time -e 'printf "%.0f\n", time * 1000')

  # Your code to benchmark
  ./lib/new-feature.sh

  local end_ms=$(perl -MTime::HiRes=time -e 'printf "%.0f\n", time * 1000')
  local duration_ms=$((end_ms - start_ms))

  echo "  Duration: ${duration_ms}ms"

  # Add to results
  local tmp_file="${RESULTS_FILE}.tmp"
  jq --argjson duration "$duration_ms" \
     '.benchmarks += [{
       "name": "new_feature",
       "duration_ms": $duration,
       "issue": "Description of what you're measuring"
     }]' "$RESULTS_FILE" > "$tmp_file" && mv "$tmp_file" "$RESULTS_FILE"
}
```

## Related Documentation

- [Performance Audit Report](../../docs/audits/performance-audit.md) - Detailed analysis of all performance issues
- [AGENTS.md](../../AGENTS.md) - Codebase patterns and discovered optimizations
- [Code Organization Audit](../../docs/audits/code-organization-audit.md) - Related audit covering code structure
