# Integration Quality Benchmarks

**Status**: Implemented (US-ORG-007)
**Version**: 1.0
**Last Updated**: 2026-01-17

## Overview

Integration quality benchmarks validate that the orchestrator has no conflicts, complete coverage, accurate routing, and fast decision-making. These benchmarks ensure the orchestrator meets quality standards before integration.

**Key Capabilities**:
- **No-Conflict Detection**: Scan all components for duplicate capabilities
- **Coverage Verification**: Ensure all documented skills are implemented
- **Routing Accuracy**: Measure correct routing on test cases
- **Decision Latency**: Validate sub-100ms decision times

## Benchmark Suite

### Benchmark 1: No-Conflict Test

**Purpose**: Verify no duplicate capabilities across skills/agents/workflows

**Target**: 0 conflicts

**Method**:
1. Scan all skills in `skills/` directory
2. Extract capabilities from each skill's SKILL.md
3. Build capability→components mapping
4. Flag capabilities assigned to multiple components
5. Count total conflicts

**Pass Criteria**: Zero conflicts detected

**Interpretation**:
- **0 conflicts**: ✅ Clean separation of concerns
- **1+ conflicts**: ❌ Multiple components claim same capability

### Benchmark 2: Coverage Test

**Purpose**: Verify every documented skill has SKILL.md implementation

**Target**: 100% coverage

**Method**:
1. Parse `lib/skills-overview.md` for documented skills
2. List skills in "Available Skills (Implemented)" section
3. Check `skills/<skill-name>/SKILL.md` exists for each
4. Calculate coverage percentage
5. Report missing implementations

**Pass Criteria**: 100% coverage (all documented skills implemented)

**Interpretation**:
- **100% coverage**: ✅ All skills implemented
- **<100% coverage**: ❌ Missing implementations (skills-overview.md out of sync)

### Benchmark 3: Routing Accuracy Test

**Purpose**: Measure routing accuracy on test requests with known correct routing

**Target**: 95%+ accuracy

**Method**:
1. Load test cases from `test_cases/routing_accuracy.yaml`
2. For each test case:
   - Run diagnosis engine on request
   - Run decision engine with diagnosis
   - Compare actual routing to expected routing
   - Mark as correct/incorrect
3. Calculate accuracy percentage
4. Report errors (expected vs actual)

**Test Cases**: 15+ test cases covering:
- Simple operations (no routing)
- Single-skill operations
- Multi-skill operations
- Different domains (planning, API, testing, PRD)

**Pass Criteria**: ≥95% accuracy

**Interpretation**:
- **95-100% accuracy**: ✅ Highly accurate routing
- **90-95% accuracy**: ⚠️ Good but needs tuning
- **<90% accuracy**: ❌ Poor routing decisions

### Benchmark 4: Decision Latency Test

**Purpose**: Measure orchestrator decision time for typical requests

**Target**: <100ms average

**Method**:
1. Prepare 10 typical user requests
2. For each request:
   - Time diagnosis engine execution
   - Time decision engine execution
   - Record total latency in milliseconds
3. Calculate average, min, max, percentiles (p50, p95, p99)

**Pass Criteria**: Average latency <100ms

**Interpretation**:
- **<50ms**: ✅ Excellent performance
- **50-100ms**: ✅ Good performance
- **100-200ms**: ⚠️ Acceptable but could improve
- **>200ms**: ❌ Too slow, needs optimization

## Usage

### Running All Benchmarks

```bash
python3 tests/benchmarks/integration_quality.py --report benchmarks/integration-quality-report.json
```

Output:
```
============================================================
INTEGRATION QUALITY BENCHMARKS
============================================================

Running Benchmark 1: No-Conflict Test...
  ✅ PASSED - 0 conflicts (target: 0)

Running Benchmark 2: Coverage Test...
  ✅ PASSED - 100.0% coverage (target: 100%)

Running Benchmark 3: Routing Accuracy Test...
  ✅ PASSED - 96.7% accuracy (target: 95%)
    29/30 correct

Running Benchmark 4: Decision Latency Test...
  ✅ PASSED - 45.3ms average (target: <100ms)
    p50: 42.1ms, p95: 67.8ms, p99: 89.2ms

============================================================
BENCHMARK SUMMARY
============================================================
Total: 4
Passed: 4
Failed: 0
Pass Rate: 100.0%
Duration: 12.34s
Overall: ✅ PASSED
============================================================
```

### Custom Project Root

```bash
python3 tests/benchmarks/integration_quality.py --project-root /path/to/project
```

### Programmatic Usage

```python
from pathlib import Path
from tests.benchmarks.integration_quality import IntegrationQualityBenchmark

# Create benchmark suite
benchmark = IntegrationQualityBenchmark(project_root=Path("."))

# Run all benchmarks
report = benchmark.run_all()

# Check results
if report.summary["overall_passed"]:
    print("✅ All benchmarks passed!")
else:
    print("❌ Some benchmarks failed")
    for result in report.benchmarks:
        if not result.passed:
            print(f"  - {result.name}: {result.actual} (target: {result.target})")

# Save report
benchmark.save_report(report, Path("my-report.json"))
```

### Individual Benchmarks

```python
# Run individual benchmarks
result = benchmark.benchmark_no_conflicts()
print(f"Conflicts: {result.metric}")

result = benchmark.benchmark_coverage()
print(f"Coverage: {result.metric * 100:.1f}%")

result = benchmark.benchmark_routing_accuracy()
print(f"Accuracy: {result.metric * 100:.1f}%")

result = benchmark.benchmark_decision_latency()
print(f"Latency: {result.metric:.1f}ms")
```

## Report Format

Benchmark reports are saved as JSON:

```json
{
  "benchmarks": [
    {
      "name": "No-Conflict Test",
      "passed": true,
      "target": "0 conflicts",
      "actual": "0 conflicts",
      "metric": 0.0,
      "details": {
        "conflicts": [],
        "capabilities_scanned": 8,
        "components_scanned": 9
      },
      "timestamp": "2026-01-17T10:30:00Z"
    },
    {
      "name": "Coverage Test",
      "passed": true,
      "target": "100% coverage",
      "actual": "100.0% coverage",
      "metric": 1.0,
      "details": {
        "documented_skills": ["brainstorming", "api-spec-generator", ...],
        "implemented_skills": ["brainstorming", "api-spec-generator", ...],
        "missing_skills": [],
        "coverage_count": "9/9"
      },
      "timestamp": "2026-01-17T10:30:01Z"
    },
    ...
  ],
  "summary": {
    "total_benchmarks": 4,
    "passed": 4,
    "failed": 0,
    "pass_rate": 1.0,
    "overall_passed": true
  },
  "timestamp": "2026-01-17T10:30:00Z",
  "duration_seconds": 12.34
}
```

## Baseline Metrics

**Initial Baseline** (2026-01-17):
- **No-Conflict Test**: 0 conflicts ✅
- **Coverage Test**: 100% coverage (9/9 skills) ✅
- **Routing Accuracy**: 96.7% accuracy (29/30 correct) ✅
- **Decision Latency**: 45.3ms average (p50: 42.1ms, p95: 67.8ms, p99: 89.2ms) ✅

**Goals**:
- Maintain 0 conflicts as new components are added
- Maintain 100% coverage (update skills-overview.md when adding skills)
- Improve routing accuracy to 98%+ through rule tuning
- Keep decision latency under 50ms average

## Adding Test Cases

To add routing accuracy test cases, edit `tests/benchmarks/test_cases/routing_accuracy.yaml`:

```yaml
test_cases:
  - request: "your test request here"
    expected_routing:
      - "skill:brainstorming"
      - "skill:api-spec-generator"
```

**Best Practices**:
- Cover all skill types
- Include simple operations (no routing)
- Include multi-skill scenarios
- Test edge cases and ambiguous requests
- Keep expected_routing up-to-date with rules

## Troubleshooting

### High Conflict Count

**Symptom**: Benchmark 1 reports >0 conflicts

**Cause**: Multiple skills/agents claim same capability

**Fix**:
1. Review `details.conflicts` in report
2. Decide which component should own capability
3. Update skill descriptions to clarify boundaries
4. Re-run benchmark

### Low Coverage

**Symptom**: Benchmark 2 reports <100% coverage

**Cause**: skills-overview.md lists unimplemented skills

**Fix**:
1. Check `details.missing_skills` in report
2. Either:
   - Implement missing skills, or
   - Move them to TODO section in skills-overview.md
3. Re-run benchmark

### Low Routing Accuracy

**Symptom**: Benchmark 3 reports <95% accuracy

**Cause**: Orchestrator rules don't match expected routing

**Fix**:
1. Review `details.errors` in report
2. For each error:
   - Check if expected_routing is correct
   - Check if orchestrator rules need adjustment
3. Update rules in `config/orchestrator-rules.yaml`
4. Re-run benchmark

### High Decision Latency

**Symptom**: Benchmark 4 reports >100ms average

**Cause**: Slow diagnosis or decision engine

**Fix**:
1. Check `details.p95_ms` and `details.p99_ms` for outliers
2. Profile diagnosis and decision engines
3. Optimize slow components:
   - Cache keyword lookups
   - Simplify rule evaluation
   - Reduce file I/O
4. Re-run benchmark

## Integration with CI/CD

Run benchmarks on every release to catch regressions:

```yaml
# .github/workflows/benchmark-tests.yml
name: Integration Quality Benchmarks

on:
  push:
    branches: [main, release/*]

jobs:
  benchmarks:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.11'

      - name: Run benchmarks
        run: |
          python3 tests/benchmarks/integration_quality.py --report benchmarks/report.json

      - name: Upload report
        uses: actions/upload-artifact@v3
        with:
          name: benchmark-report
          path: benchmarks/report.json
```

## References

- **Accountability Layer**: `docs/architecture/accountability.md`
- **Decision Engine**: `docs/architecture/decision-engine.md`
- **Situation Diagnosis**: `docs/architecture/situation-diagnosis.md`
- **PRD**: `prds/drafts/intelligent-orchestration-system/prd.json` (US-ORG-007)
