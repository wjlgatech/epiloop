# Real-World Benchmark Suite for Agentic Frameworks

## Overview

This benchmark suite contains **10 real tasks** extracted from actual codebases (agent-zero and claude-loop) to validate AI coding agents with **zero synthetic bias**.

## 📰 NEWS: Agent-Zero vs Claude-Loop Comprehensive Comparison

**Date**: January 23, 2026 | **Total Cases**: 107 (50 v1 + 50 v2 + 7 re-run)

### Executive Summary

| Framework | Success Rate | Quality Score | Verdict |
|-----------|--------------|---------------|---------|
| **Agent-Zero** | **54%** (27/50) | **0.25** | ❌ **Not production-ready** - 46% failure rate |
| **Claude-Loop v1** | **92%** (46/50) | **0.78** | ✅ **Production-ready** |
| **Claude-Loop (Fixed)** | **90%** (47/52) | **0.78** | ✅✅ **Best** - With Phase 1 fixes |

**Key Findings**:
- 🎯 **Claude-Loop wins by 36-38 percentage points** in success rate
- 🏆 **3.1× better quality** (0.78 vs 0.25 score)
- 📉 **83% fewer failures** (4 vs 23 per 50 tasks)
- 💰 **60% better ROI** despite 5× higher cost (value per dollar)

**Agent-Zero Root Cause**: Optimizes for speed (121s avg) over correctness, resulting in 46% failure rate with low-quality implementations (0.25 score). No quality gates or error diagnostics.

**Claude-Loop Strengths**: High reliability (90-92% success), high-quality implementations (0.78 score), clear error diagnostics, acceptable speed (4.1 min avg).

**📊 [Read Full Analysis](../benchmark-results/FINAL_ANALYSIS_AGENT_ZERO_VS_CLAUDE_LOOP.md)** - 58-page comprehensive comparison with root cause analysis, efficiency metrics, and recommendations.

---

### Philosophy

Instead of creating artificial "toy problems", we use actual TODOs, FIXMEs, and bugs from production code. This ensures:
- ✓ Real-world complexity and ambiguity
- ✓ Genuine integration challenges
- ✓ Actual value delivered (improvements that matter)
- ✓ Realistic failure modes

## Benchmark Tasks

This suite contains **10 real-world tasks** across three complexity tiers:

### Task Overview

| Task | Name | Tier | Difficulty | Est. Time | Source |
|------|------|------|------------|-----------|--------|
| TASK-001 | Vision Summary Optimization | MICRO | 2/5 | 20 min | agent-zero |
| TASK-002 | LLM Provider Health Check | MESO | 3/5 | 60 min | claude-loop |
| TASK-003 | Scheduler Duplicate Jobs Bug | REGRESSION | 3/5 | 45 min | agent-zero |
| TASK-004 | Git Worktree Cleanup | MICRO | 2/5 | 30 min | claude-loop |
| TASK-005 | Multi-Provider LLM Support | MESO | 3/5 | 90 min | claude-loop |
| TASK-006 | Interactive Mode Exit Command | MICRO | 2/5 | 20 min | claude-loop |
| TASK-007 | Token Usage Metrics | MESO | 3/5 | 60 min | claude-loop |
| TASK-008 | Experience Store Integration | MESO | 3/5 | 75 min | claude-loop |
| TASK-009 | Memory Context Limit Bug | REGRESSION | 3/5 | 45 min | agent-zero |
| TASK-010 | Rate Limiting Middleware | MESO | 3/5 | 60 min | claude-loop |

**See individual `TASK-*.yaml` files for detailed specifications, acceptance criteria, and validation scripts.**

### Task Categories

**By Tier**:
- **MICRO** (TASK-001, 004, 006): Simple, 1-2 file changes, 20-30 min
- **MESO** (TASK-002, 005, 007, 008, 010): Medium complexity, multi-file, 45-90 min
- **REGRESSION** (TASK-003, 009): Bug fixes, prevention focus, 30-60 min

**By Source Project**:
- **agent-zero**: TASK-001, 003, 009 (interactive agent framework)
- **claude-loop**: TASK-002, 004-010 (autonomous coding agent)

---

## Quick Start

### 1. View Existing Results

```bash
# View comprehensive analysis
cat ../benchmark-results/FINAL_ANALYSIS_AGENT_ZERO_VS_CLAUDE_LOOP.md

# View benchmark summary
cat ../benchmark-results/benchmark_auto_with_fixes_results.json | jq '.summary'

# Check efficiency metrics
cat ../benchmark-results/benchmark_auto_with_fixes_results.json | jq '.efficiency_metrics'
```

### 2. Run 50-Case Benchmark (Claude-Loop)

```bash
# Install dependencies
pip install pyyaml

# Run full 50-case benchmark with Phase 1 fixes
python3 benchmark_auto_with_fixes.py
```

This will:
- Load 10 task specifications
- Execute each task 5 times (50 total runs)
- Track efficiency metrics (tokens, cost, complexity)
- Validate acceptance criteria
- Generate detailed results

**Expected Output**:
```
================================================================================
BENCHMARK AUTO WITH FIXES - 50 CASES
================================================================================

Progress: 50/50 completed
Success Rate: 90-92% (45-46/50)
Average Time: ~4 minutes per task
Total Cost: ~$0.66 ($0.013 per case)
Quality Score: 0.78 average

✓ Full report saved to: ../benchmark-results/benchmark_auto_with_fixes_results.json
```

### 3. Run Comparative Benchmark (Multi-Framework)

**Prerequisites**:
- Claude Code CLI installed and authenticated
- Agent-zero setup (if testing)
- Claude-loop setup (if testing)

**Implementation Steps**:

1. **Implement execution adapters** in `benchmark_runner.py`:

```python
def _run_claude_loop(self, task: Dict) -> Tuple[bool, Dict, int, float, Optional[str]]:
    """Run task with Claude-Loop framework"""
    # Create temporary PRD from task
    prd = self._task_to_prd(task)
    prd_file = self._write_temp_prd(prd)

    # Execute with claude-loop
    result = subprocess.run(
        ["./claude-loop.sh", "--prd", prd_file],
        cwd="/Users/jialiang.wu/Documents/Projects/claude-loop",
        capture_output=True,
        timeout=self.config.timeout_seconds
    )

    # Validate acceptance criteria
    success, criteria = self._validate_criteria(task, result)

    # Extract token/cost metrics
    tokens, cost = self._extract_metrics(result.stdout)

    return success, criteria, tokens, cost, None
```

2. **Run real benchmark**:

```bash
python benchmark_runner.py --real-execution
```

3. **Analyze results**:

```bash
# View detailed report
cat benchmark-results/benchmark_report.json | jq .

# Compare specific metrics
python analyze_results.py --metric success_rate
python analyze_results.py --metric cost
```

## Benchmark Output

### Individual Results

Each task execution creates a JSON file:

```json
{
  "task_id": "TASK-001",
  "subject": "claude-loop",
  "success": true,
  "wall_clock_seconds": 42.3,
  "total_tokens": 8234,
  "estimated_cost_usd": 0.0247,
  "criteria_passed": {
    "AC1": true,
    "AC2": true,
    "AC3": true,
    "AC4": false
  },
  "criteria_scores": {
    "AC1": 1.0,
    "AC2": 1.0,
    "AC3": 1.0,
    "AC4": 0.3
  },
  "error_message": null,
  "timestamp": "2026-01-19T14:32:10",
  "run_number": 1
}
```

### Aggregate Report

Summary statistics across all runs:

```json
{
  "summary": {
    "baseline": {
      "success_rate": 0.67,
      "avg_time_seconds": 45.2,
      "avg_cost_usd": 0.0234,
      "avg_score": 0.78,
      "total_results": 3
    },
    "claude-loop": {
      "success_rate": 1.0,
      "avg_time_seconds": 52.1,
      "avg_cost_usd": 0.0298,
      "avg_score": 0.85,
      "total_results": 3
    }
  }
}
```

## Extending the Benchmark

### Adding New Tasks

1. **Find a real TODO/FIXME** in your codebase:

```bash
grep -r "TODO\|FIXME" agent-zero/ claude-loop/ | head -10
```

2. **Create task specification**:

```bash
cp TASK-001-vision-summary.yaml TASK-004-your-task.yaml
```

3. **Fill in details**:
   - Problem description
   - Acceptance criteria (with weights)
   - Test data
   - Validation scripts

4. **Run benchmark**:

```bash
python benchmark_runner.py  # Automatically discovers new tasks
```

### Task Template

```yaml
id: TASK-XXX
name: "Your Task Name"
tier: micro | meso | macro | regression
source_project: agent-zero | claude-loop | your-project
difficulty: 1-5
estimated_time_human_minutes: XX

description: |
  Clear problem statement with context

acceptance_criteria:
  - id: AC1
    description: "What must be true"
    weight: 0.40
    validation_method: "unit_test | integration_test | code_inspection"
    validation_script: |
      # Shell commands to validate

implementation_hints:
  approach: |
    High-level solution strategy

test_data:
  # Example inputs and expected outputs

success_definition: |
  When is the task truly complete?
```

## Analysis Tools

### Statistical Significance

```bash
# Compare two subjects with t-test
python analyze_results.py --compare claude-loop agent-zero --metric success_rate

# Output:
# t-statistic: 2.45
# p-value: 0.032
# Conclusion: Claude-loop is significantly better (p < 0.05)
```

### Failure Analysis

```bash
# Classify failure modes
python analyze_results.py --failures

# Output:
# Context overflow: 2 (33%)
# Tool misuse: 1 (17%)
# Incorrect code: 3 (50%)
```

### Cost-Benefit Analysis

```bash
# Calculate ROI for integration
python analyze_results.py --roi

# Output:
# Agent-Zero → Claude-Loop integration:
# - Success rate improvement: +33% (0.67 → 1.0)
# - Cost increase: +27% ($0.0234 → $0.0298)
# - ROI: High (1.3x improvement for 1.27x cost)
```

## Best Practices

### 1. Start Small

Run **Tier 1 (Quick Validation)** first:
- 3 tasks (1 micro, 1 meso, 1 regression)
- 1 run per task
- Mock execution for rapid iteration
- **Timeline**: 1 hour
- **Cost**: $0 (mock)

### 2. Expand If Promising

Run **Tier 2 (Focused Benchmark)** if Tier 1 shows >20% improvement:
- All 3 tasks
- 3-5 runs per task (for statistical significance)
- Real execution
- **Timeline**: 1 day
- **Cost**: $5-$10 in API calls

### 3. Dogfood in Parallel

While running benchmarks:
- Use both systems on real work
- Track subjective experience
- Note failure modes not captured in benchmark

**Dogfooding > Exhaustive benchmarking**

## Limitations

### What This Benchmark CAN Tell You

✓ Relative performance on well-defined coding tasks
✓ Cost-benefit tradeoffs
✓ Feature value (via ablation)
✓ Failure modes
✓ Statistical confidence in differences

### What It CAN'T Tell You

✗ Long-term maintenance burden (6+ months)
✗ Team collaboration effectiveness
✗ Edge cases not in benchmark
✗ Subjective "feels better to use"
✗ Political/organizational fit

### Known Biases

- **Synthetic task bias**: Even "real" tasks are cleaner than day-to-day chaos
- **Paradigm bias**: Interactive (agent-zero) vs autonomous (claude-loop) serve different needs
- **Maturity bias**: Claude-loop is more mature, has more features

**Mitigation**: Use benchmark for directional guidance, not absolute truth. Validate with real usage.

## Troubleshooting

### "No tasks found"

```bash
# Ensure tasks directory exists
ls benchmark-tasks/TASK-*.yaml

# Should see:
# TASK-001-vision-summary.yaml
# TASK-002-llm-health-check.yaml
# TASK-003-scheduler-duplicate-jobs.yaml
```

### "Import error: yaml module not found"

```bash
pip install pyyaml
```

### "Timeout errors"

Increase timeout in configuration:

```python
config = BenchmarkConfig(
    # ...
    timeout_seconds=1200  # 20 minutes
)
```

## Contributing

### Adding Tasks from Your Projects

Have a real TODO or bug? Contribute it!

1. Create task YAML following template
2. Add validation scripts
3. Submit PR with:
   - Task specification
   - Ground truth solution (optional)
   - Why this task is representative

### Improving Runners

Execution adapters need love:
- Better error handling
- Token extraction from different systems
- Cost calculation improvements
- Validation automation

## Next Steps

1. **Run mock benchmark** to understand output format
2. **Review task specifications** to ensure they're clear
3. **Implement execution adapters** for your systems
4. **Run Tier 1 validation** (1 hour, 3 tasks, 1 run)
5. **Analyze results** and decide if Tier 2 is warranted
6. **Dogfood** both systems in parallel with real work

## Questions?

See `TASK-*.yaml` files for detailed task specifications.

**Philosophy**: Benchmarks inform decisions, they don't make them. Use this as one input among many (user feedback, maintainability, team preference, etc.).

**Reality check**: The best benchmark is shipping to production and iterating based on real usage.
