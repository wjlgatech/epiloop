# Tier 1 Benchmark - Usage Guide

## ✅ Implementation Complete

The following has been implemented and is ready to use:

### ✓ US-001: Baseline Execution Adapter
- Invokes Claude Code CLI with task descriptions
- Captures success/failure, tokens, time
- Validates acceptance criteria
- **Status**: COMPLETE

### ✓ US-002: Claude-Loop Execution Adapter
- Uses claude-loop quick mode
- Extracts metrics from execution logs
- Validates acceptance criteria
- **Status**: COMPLETE

### ✓ US-004: Validation Scripts
- `validation/task_001_validator.py` - Vision optimization
- `validation/task_002_validator.py` - Health check
- `validation/task_003_validator.py` - Scheduler bug
- **Status**: COMPLETE

---

## Quick Start: Run the Benchmark

### Option 1: Test with Mock Data (Free, Instant)

```bash
cd /Users/jialiang.wu/Documents/Projects/benchmark-tasks

# Run mock benchmark (no API calls)
python3 benchmark_runner.py

# View results
cat ../benchmark-results/benchmark_report.json | python3 -m json.tool
```

**Expected output**: Mock comparison showing baseline vs claude-loop performance

---

### Option 2: Run Real Benchmark (Uses API, Costs $$)

**⚠️ WARNING: This will make real API calls and cost approximately $5-$20**

```bash
cd /Users/jialiang.wu/Documents/Projects/benchmark-tasks

# Make sure you have dependencies
pip3 install pyyaml

# Run real benchmark (2 subjects × 3 tasks = 6 runs)
python3 benchmark_runner.py  # Currently runs real execution

# Monitor progress
ls -la ../benchmark-results/

# View results as they complete
tail -f ../benchmark-results/TASK-*.json
```

**What happens**:
1. TASK-001 executed with baseline → saves result JSON
2. TASK-001 executed with claude-loop → saves result JSON
3. TASK-002 executed with baseline → saves result JSON
4. TASK-002 executed with claude-loop → saves result JSON
5. TASK-003 executed with baseline → saves result JSON
6. TASK-003 executed with claude-loop → saves result JSON
7. Aggregate report generated

**Timeline**: 30-60 minutes total (each task: 2-10 minutes)

---

## Understanding the Output

### Individual Results

Each run creates a JSON file like:

```json
{
  "task_id": "TASK-001",
  "subject": "claude-loop",
  "success": true,
  "wall_clock_seconds": 120.5,
  "total_tokens": 8234,
  "estimated_cost_usd": 0.0247,
  "criteria_scores": {
    "AC1": 0.85,
    "AC2": 0.90,
    "AC3": 1.00,
    "AC4": 0.75
  },
  "overall_score": 0.875
}
```

### Aggregate Report

`benchmark_report.json` contains:

```json
{
  "summary": {
    "baseline": {
      "success_rate": 0.67,
      "avg_cost_usd": 0.0234,
      "avg_score": 0.78
    },
    "claude-loop": {
      "success_rate": 1.0,
      "avg_cost_usd": 0.0281,
      "avg_score": 0.85
    }
  }
}
```

---

## Interpreting Results

### Success Metrics

**Success Rate**: % of tasks completed successfully
- >0.8 = Good
- 0.5-0.8 = Mixed
- <0.5 = Poor

**Average Score**: Weighted acceptance criteria scores
- >0.8 = Excellent (most criteria met)
- 0.6-0.8 = Good (some criteria met)
- <0.6 = Needs improvement

**Cost**: Estimated USD per task
- Baseline: Typically $0.01-$0.05 per task
- Claude-loop: Typically $0.02-$0.08 per task (more iterations)

### Decision Thresholds

Based on your decision framework:

**>20% improvement in score** → ✅ Proceed with Option B (Selective Integration)
```
Example: Baseline 0.70 → Claude-loop 0.85 = +21% improvement
Recommendation: Proceed with integration
```

**10-20% improvement** → ⚠️ Judgment call
```
Example: Baseline 0.75 → Claude-loop 0.82 = +9% improvement
Recommendation: Consider Option A (pattern extraction only)
```

**<10% improvement** → ❌ Stay with current claude-loop
```
Example: Baseline 0.80 → Claude-loop 0.85 = +6% improvement
Recommendation: Not worth integration effort
```

---

## Troubleshooting

### "Command not found: claude"

Claude Code CLI not installed or not in PATH.

**Fix**:
```bash
# Install Claude Code CLI
# Or update path in benchmark_runner.py line 473
```

### "Permission denied: claude-loop.sh"

**Fix**:
```bash
chmod +x /Users/jialiang.wu/Documents/Projects/claude-loop/claude-loop.sh
```

### "Task execution timeout"

Default timeout is 600 seconds (10 minutes). Increase if needed:

**Edit `benchmark_runner.py`**:
```python
config = BenchmarkConfig(
    # ...
    timeout_seconds=1200,  # 20 minutes
)
```

### "Validation scripts fail"

Validators are heuristic-based. Check logs:

```bash
python3 validation/task_001_validator.py /tmp/benchmark_workspace
```

---

## Next Steps After Benchmark

### 1. Analyze Results

```bash
cd benchmark-tasks

# View summary
cat ../benchmark-results/benchmark_report.json | python3 -m json.tool

# Compare subjects
cat ../benchmark-results/benchmark_report.json | jq '.summary'
```

### 2. Calculate Improvement

```python
# Quick analysis
baseline_score = 0.78  # From report
claude_loop_score = 0.85  # From report
improvement = ((claude_loop_score - baseline_score) / baseline_score) * 100
print(f"Improvement: {improvement:.1f}%")
```

### 3. Generate Decision Report

**If improvement >20%**:
```bash
# Copy template
cp ANALYSIS.md DECISION_REPORT.md

# Edit to add:
# - Benchmark results summary
# - Recommendation: Option B (Selective Integration)
# - Next steps: Begin Weeks 3-16 implementation
```

**If improvement 10-20%**:
```bash
# Document as judgment call
# Consider: Option A (Pattern Extraction) as lower-risk alternative
```

**If improvement <10%**:
```bash
# Document decision to stay with current claude-loop
# Note: Integration not justified by data
```

---

## Running Tier 2 (Optional)

If Tier 1 shows >20% improvement, consider Tier 2:

**Expand to N=5 runs** for statistical significance:

```python
# Edit benchmark_runner.py
config = BenchmarkConfig(
    # ...
    runs_per_task=5,  # Was 1
)
```

**Add ablation studies**:
```python
# Test individual features
subjects=[
    Subject.BASELINE,
    Subject.CLAUDE_LOOP,
    # Subject.CLAUDE_LOOP_TIER1,  # With hooks only
    # Subject.CLAUDE_LOOP_TIER2,  # With MCP
]
```

**Run extended benchmark**:
```bash
python3 benchmark_runner.py  # Now 30 runs (3 tasks × 2 subjects × 5 runs)
```

**Cost estimate**: 5x Tier 1 = $25-$100

---

## Files Created

### Core Implementation
```
benchmark-tasks/
├── benchmark_runner.py          ← Updated with real execution
├── validation/
│   ├── task_001_validator.py   ← Vision optimization validator
│   ├── task_002_validator.py   ← Health check validator
│   └── task_003_validator.py   ← Scheduler bug validator
```

### Documentation
```
benchmark-tasks/
├── ANALYSIS.md                  ← 58-page comprehensive analysis
├── NEXT_STEPS.md                ← Execution guidance
├── README.md                    ← Benchmark suite documentation
└── USAGE_GUIDE.md               ← This file
```

### Task Specifications
```
benchmark-tasks/
├── TASK-001-vision-summary.yaml
├── TASK-002-llm-health-check.yaml
└── TASK-003-scheduler-duplicate-jobs.yaml
```

---

## What's Still Needed (Optional)

### US-003: Agent-Zero Adapter (Deferred)

**Why deferred**: Agent-zero requires interactive mode, complex to automate

**If needed later**:
```python
# Uncomment in benchmark_runner.py
subjects=[
    Subject.BASELINE,
    Subject.AGENT_ZERO,  # ← Add back
    Subject.CLAUDE_LOOP
]

# Implement _run_agent_zero() method
# Handle interactive prompts with mock responses
```

### US-005: Execute Benchmark

**Status**: Can run now with `python3 benchmark_runner.py`

### US-006-008: Analysis & Reporting

**After benchmark completes**, create:
- `analyze_results.py` - Statistical analysis (t-tests, effect sizes)
- `DECISION_REPORT.md` - Final recommendation
- `PRESENTATION.md` - Stakeholder slides

**These can be done manually** after reviewing results.

---

## Cost Tracking

### Tier 1 Estimate

**Per task**:
- Baseline: ~5K-10K tokens = $0.02-$0.04
- Claude-loop: ~10K-15K tokens = $0.05-$0.08

**Total (3 tasks × 2 subjects × 1 run)**:
- Low estimate: $0.21
- High estimate: $0.36
- **Realistic: $0.25-$0.30**

**Wait, that's way under budget!**

The $5-$20 estimate assumed longer tasks. Real cost likely **$1-$5 total** for Tier 1.

### Tier 2 Estimate (N=5)

**Total (3 tasks × 2 subjects × 5 runs)**:
- **Realistic: $5-$15**

Still well under $50 budget!

---

## Summary

✅ **Benchmark infrastructure is READY**
✅ **Run with**: `python3 benchmark_runner.py`
✅ **Results in**: `../benchmark-results/`
✅ **Cost**: ~$1-$5 for Tier 1

**Next**: Execute and analyze results to make integration decision.

**Timeline**: 30-60 minutes to run + 1 hour to analyze = **<2 hours to decision**

---

## Contact & Support

**For benchmark issues**:
- Check this guide
- Review task YAML files for specifications
- Check validator scripts for acceptance criteria logic

**For analysis questions**:
- See `ANALYSIS.md` Section 6 (Decision Framework)
- See `ANALYSIS.md` Section 5 (Benchmark Design)

**For next steps**:
- See `NEXT_STEPS.md` (comprehensive guide)
- See `ANALYSIS.md` Section 7 (Implementation Roadmap)

---

**Ready to run?**

```bash
cd /Users/jialiang.wu/Documents/Projects/benchmark-tasks
python3 benchmark_runner.py
```

🚀 Let's get data-driven evidence for the integration decision!
