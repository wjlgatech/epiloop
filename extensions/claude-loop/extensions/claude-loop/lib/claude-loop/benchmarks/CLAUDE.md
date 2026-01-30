# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository Overview

**benchmark-tasks** is a real-world benchmark suite for evaluating autonomous coding agents (Agent-Zero, Claude-Loop) using actual TODO/FIXME comments extracted from production codebases rather than synthetic problems.

The repository contains:
- 10 real-world coding tasks (TASK-001 through TASK-010) as YAML specifications
- Multiple benchmark runner scripts with different configurations
- Validation scripts for automated acceptance criteria checking
- Comprehensive analysis and results documentation

## Common Commands

### Running Benchmarks

```bash
# Run mock benchmark (no API calls, instant results)
python3 benchmark_runner.py

# Run full 50-case benchmark with Phase 1 fixes
python3 benchmark_auto_with_fixes.py

# Run targeted re-test on specific failed cases
python3 rerun_failed_cases.py

# Run A/B test on previously failed cases only
python3 ab_test_failed_cases.py
```

### Validation and Testing

```bash
# Validate a specific task implementation
python3 validation/task_001_validator.py /path/to/workspace

# Check all validators exist
ls -la validation/task_*.py

# Test YAML task loading
python3 -c "import yaml; print(yaml.safe_load(open('TASK-001-vision-summary.yaml')))"
```

### Results Analysis

```bash
# View benchmark summary
cat ../benchmark-results/benchmark_auto_with_fixes_results.json | jq '.summary'

# Check efficiency metrics
cat ../benchmark-results/benchmark_auto_with_fixes_results.json | jq '.efficiency_metrics'

# List all result files
ls -lh ../benchmark-results/*.json

# Monitor real-time progress (when benchmark is running)
./monitor_efficiency.sh
```

### Dependencies

```bash
# Install required packages
pip3 install pyyaml

# Check Python version (requires 3.7+)
python3 --version
```

## High-Level Architecture

### Task Specification Format (YAML)

Each `TASK-*.yaml` file defines a real-world coding problem with this structure:

```yaml
id: TASK-XXX
name: "Task Name"
tier: micro | meso | regression      # Complexity tier
difficulty: 1-5                      # Human difficulty estimate
estimated_time_human_minutes: N

description: |
  Actual TODO/FIXME from production code with full context

acceptance_criteria:
  - id: AC1
    description: "What must be validated"
    weight: 0.40                     # Sum of all weights = 1.0
    validation_method: "unit_test | integration_test | code_inspection"
    validation_script: |
      # Shell commands to validate this criterion
```

**Key insight**: Tasks are NOT synthetic - they come from real TODOs in agent-zero and claude-loop codebases.

### Benchmark Runner Architecture

There are three main benchmark scripts with different purposes:

#### 1. `benchmark_runner.py` (Original)
- **Purpose**: Compare baseline (raw Claude) vs Claude-Loop vs Agent-Zero
- **Runs**: 1 run per task per subject
- **Subjects**: Can test multiple frameworks
- **Output**: `benchmark_report.json` with comparative analysis

#### 2. `benchmark_auto_with_fixes.py` (Current)
- **Purpose**: Test Claude-Loop with Phase 1 fixes at scale
- **Runs**: 50 total (10 tasks × 5 runs each)
- **Features**: Tracks efficiency metrics (tokens, cost, complexity filtering)
- **Output**: `benchmark_auto_with_fixes_results.json`

#### 3. `rerun_failed_cases.py` (Targeted)
- **Purpose**: Re-test only failed cases to verify fixes
- **Runs**: Variable (only failed cases from previous runs)
- **Features**: Debug logging, workspace preservation
- **Output**: `benchmark_failed_cases_rerun.json`

### Execution Flow

```
1. Load Task YAML
   ↓
2. Create PRD (Product Requirements Document) from task
   ↓
3. Initialize git workspace
   ↓
4. Execute with target framework (baseline/agent-zero/claude-loop)
   ↓
5. Check success (PRD userStories[0].passes == true)
   ↓
6. Extract metrics (tokens, cost, time, complexity)
   ↓
7. Validate acceptance criteria (run validation scripts)
   ↓
8. Save result JSON
   ↓
9. Cleanup workspace (or preserve for debugging)
```

### Validation Architecture

Each task has a Python validator script that programmatically checks acceptance criteria:

```python
# validation/task_001_validator.py
def validate_task_001(workspace_path: str) -> Dict[str, Any]:
    """
    Validates acceptance criteria for vision optimization task.

    Returns:
        {
            "AC1": {"passed": bool, "score": float, "reason": str},
            "AC2": {...},
            "overall_score": float  # Weighted average
        }
    """
```

Validators use heuristics like:
- Code inspection (grep, AST parsing)
- File existence checks
- Test execution results
- Token usage measurements

### Results Storage

All results go to `../benchmark-results/` directory:

```
benchmark-results/
├── benchmark_report.json                    # Original comparative benchmark
├── benchmark_auto_with_fixes_results.json   # Full 50-case with fixes
├── benchmark_failed_cases_rerun.json        # Targeted re-run
├── AB_TEST_PHASE1_RESULTS.md               # A/B test analysis
├── FINAL_ANALYSIS_AGENT_ZERO_VS_CLAUDE_LOOP.md  # Comprehensive comparison
├── EFFICIENCY_ANALYSIS_RESULTS.md           # Efficiency metrics analysis
└── PHASE1_FIXES_IMPLEMENTATION.md           # Fix validation docs
```

### Key Classes and Data Structures

#### EfficiencyMetrics (benchmark_auto_with_fixes.py)

Tracks optimization metrics across benchmark runs:

```python
{
    "total_tokens": int,
    "total_cost": float,
    "total_time": float,
    "feature_activations": {
        "complexity_filtered": int,      # Cases with features disabled
        "agents_enabled": int,
        "experience_enabled": int
    },
    "by_complexity": {
        "0": {"count": int, "tokens": int, "successes": int},  # micro
        "1": {...},  # small
        # ...
    },
    "by_tier": {
        "micro": {...},
        "meso": {...},
        "regression": {...}
    }
}
```

#### TaskResult (benchmark_runner.py)

Individual task execution result:

```python
{
    "task_id": "TASK-001",
    "subject": "claude-loop",
    "success": bool,
    "wall_clock_seconds": float,
    "total_tokens": int,
    "estimated_cost_usd": float,
    "criteria_passed": {"AC1": bool, "AC2": bool, ...},
    "criteria_scores": {"AC1": float, "AC2": float, ...},
    "overall_score": float,  # Weighted average
    "error_message": str | None
}
```

## Task Categories

### By Tier
- **micro** (TASK-001, 004, 006): Simple, 1-2 file changes, 20-30 min
- **meso** (TASK-002, 005, 007, 008, 010): Medium complexity, multi-file, 45-90 min
- **regression** (TASK-003, 009): Bug fixes, prevention focus, 30-60 min

### By Source Project
- **agent-zero**: TASK-001, 003, 009 (interactive agent framework)
- **claude-loop**: TASK-002, 004-010 (autonomous coding agent)

### By Difficulty
- **Level 2**: TASK-001, 004, 006 (straightforward implementations)
- **Level 3**: TASK-002, 003, 005, 007, 008, 009, 010 (moderate complexity)

## Phase 1 Fixes

The benchmark suite was used to validate critical fixes to claude-loop:

### Fix #1: Empty Experience Store Guard
- **Issue**: RAG retrieval attempted even with empty vector DB
- **Fix**: Added `has_data()` check before retrieval
- **Impact**: Eliminates overhead for first-time tasks

### Fix #2: Non-Coding Agent Filtering
- **Issue**: Market analyst, academic scanner selected for coding tasks
- **Fix**: Filter to coding-relevant agents only
- **Impact**: Reduces noise, improves validation success

### Fix #3: Complexity-Based Feature Activation
- **Issue**: Complex features (agents, RAG) enabled for simple tasks
- **Fix**: Disable features for complexity level 0-1 (micro/small)
- **Impact**: 93-95% speedup on simple tasks, eliminates timeouts
- **File**: `/Users/jialiang.wu/Documents/Projects/claude-loop/claude-loop.sh` line 3835
- **Change**: Removed `--text` flag from complexity detector call

## Critical Paths

### When Adding New Tasks

1. Create `TASK-XXX-description.yaml` following existing format
2. Ensure acceptance criteria are measurable
3. Create `validation/task_XXX_validator.py` script
4. Test validator independently before benchmark
5. Add task to appropriate tier (micro/meso/regression)

### When Running Benchmarks

1. **First**: Test with mock data (`benchmark_runner.py` mock mode)
2. **Then**: Run single task to verify execution adapter works
3. **Then**: Run full benchmark (budget 1-4 hours depending on task count)
4. **Finally**: Analyze results and document findings

### When Debugging Failed Cases

1. Check `benchmark_auto_with_fixes_results.json` for error messages
2. Use `rerun_failed_cases.py` with `preserve=True` to inspect workspace
3. Check preserved workspace at `/tmp/benchmark_debug_*/`
4. Look for:
   - `.claude-loop/logs/tokens_*.json` (metrics)
   - `.claude-loop/execution_log.jsonl` (execution trace)
   - `prd.json` (check `passes` field)
   - `progress.txt` (implementation notes)

## Important Implementation Details

### PRD Format

Benchmarks convert YAML tasks to claude-loop PRD format:

```python
prd = {
    "project": f"benchmark-{task['id']}",
    "branchName": f"benchmark/{task['id']}",
    "description": task['description'],
    "userStories": [{
        "id": "US-001",
        "title": task['name'],
        "description": task['description'],
        "acceptanceCriteria": task['acceptance_criteria'],
        "priority": 1,
        "passes": False  # Set to True when complete
    }]
}
```

The `passes: true` field is CRITICAL - this is how success is determined.

### Success Validation

A task succeeds if and only if:

```python
success = prd['userStories'][0]['passes'] == True
```

**Validation gap**: Sometimes implementations are correct but Claude forgets to set `passes: true`. This is a known issue causing ~8% failure rate.

### Metrics Extraction

Token/cost metrics are extracted from claude-loop logs:

```bash
# Token logs created by claude-loop at:
.claude-loop/logs/tokens_US-001.json

# Contains:
{
  "story_id": "US-001",
  "total_chars": 21395,
  "estimated_tokens": 5348,
  "complexity_level": 0,
  "agents_enabled": false,
  "experience_enabled": false
}
```

**Critical**: Metrics must be extracted BEFORE workspace cleanup or they're lost.

### Workspace Management

Each benchmark run creates isolated workspaces:

```bash
/tmp/benchmark_auto_TASK-001_run1_1769111911/
├── prd.json           # Task specification
├── progress.txt       # Implementation notes
├── AGENTS.md          # Agent patterns
└── .claude-loop/
    ├── logs/
    │   └── tokens_US-001.json
    ├── execution_log.jsonl
    └── session-state.json
```

Workspaces are cleaned up after each run unless `preserve=True` is set for debugging.

## Benchmark Results Interpretation

### Success Rates

- **≥95%**: Excellent (production-ready)
- **90-95%**: Good (acceptable with monitoring)
- **85-90%**: Fair (needs improvement)
- **<85%**: Poor (not production-ready)

### Quality Scores (Weighted Acceptance Criteria)

- **≥0.80**: High quality (most criteria met well)
- **0.60-0.80**: Medium quality (some criteria partially met)
- **<0.60**: Low quality (significant gaps)

### Agent-Zero vs Claude-Loop Findings

From comprehensive benchmarking:

| Framework | Success Rate | Quality | Verdict |
|-----------|--------------|---------|---------|
| Agent-Zero | 54% (27/50) | 0.25 | ❌ Not production-ready (46% failure rate) |
| Claude-Loop | 90-92% (46/50) | 0.78 | ✅ Production-ready |

**Key insight**: Agent-Zero optimizes for speed (121s avg) but sacrifices correctness. Claude-Loop is 2× slower (245s avg) but 3× better quality and 38 points higher success rate.

## File Organization

### Core Benchmark Scripts
- `benchmark_runner.py` - Multi-framework comparison
- `benchmark_auto_with_fixes.py` - 50-case efficiency test
- `rerun_failed_cases.py` - Targeted debugging/recovery
- `ab_test_failed_cases.py` - A/B testing Phase 1 fixes

### Task Specifications (10 tasks)
- `TASK-001-vision-summary.yaml` through `TASK-010-rate-limiting-middleware.yaml`
- Each ~100-300 lines with full context and acceptance criteria

### Validation Scripts
- `validation/task_001_validator.py` through `validation/task_003_validator.py`
- Return structured validation results with per-criterion scores

### Monitoring Tools
- `monitor_efficiency.sh` - Real-time benchmark progress tracking
- `monitor_and_continue.sh` - Continue interrupted benchmarks

### Documentation
- `README.md` - Overview and quick start
- `USAGE_GUIDE.md` - Detailed usage instructions
- `ANALYSIS.md` - 58-page decision framework and analysis
- `DECISION_REPORT.md` - Integration decision based on results
- `IMPLEMENTATION_COMPLETE.md` - Implementation status tracking

### Results Documentation
See `../benchmark-results/` directory for all analysis reports and findings.

## Testing Philosophy

This benchmark suite follows a "zero synthetic bias" philosophy:

1. **Real problems only**: All tasks from actual TODO/FIXME comments
2. **Real codebases**: Agent-zero and claude-loop production code
3. **Real complexity**: Includes integration challenges, ambiguity, context requirements
4. **Real value**: Implementations that actually improve the projects

**Anti-pattern**: Creating artificial "toy problems" that don't reflect real-world challenges.

**Validation**: Benchmark results have been validated against manual implementation and production usage.

