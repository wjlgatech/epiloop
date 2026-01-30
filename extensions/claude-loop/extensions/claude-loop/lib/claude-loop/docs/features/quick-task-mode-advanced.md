# Quick Task Mode - Advanced Features (US-204)

**Status**: ✅ Implemented
**Priority**: High
**Feature ID**: US-204

## Overview

Quick Task Mode Advanced Features extends US-203 with complexity detection, auto-escalation, task chaining, templates, and advanced execution capabilities. This update transforms quick mode from a simple task runner into a sophisticated workflow engine.

## New Features

### 1. Complexity Detection

Automatically estimates task complexity based on:
- Word count (long descriptions = complex)
- Multiple requirements (and, with, plus connectors)
- Architecture keywords (refactor, redesign, migrate)
- Multiple components (various, several, all)
- Testing requirements
- API/integration work

**Complexity Score**: 0-100
- 0-29: Simple
- 30-59: Medium
- 60-100: Complex

**Usage:**
```bash
# Complexity detected automatically in all quick tasks
./claude-loop.sh quick "Add validation to user input"
# Output: Estimated Complexity: simple (score: 20/100)

./claude-loop.sh quick "Refactor authentication system with OAuth and tests"
# Output: Estimated Complexity: complex (score: 75/100)
```

### 2. Auto-Escalation to PRD Mode

Automatically suggests PRD mode for complex tasks:

**Usage:**
```bash
# Enable escalation with --escalate flag
./claude-loop.sh quick "Refactor entire auth system with OAuth" --escalate

# Output:
# ⚠️  COMPLEXITY WARNING ⚠️
# This task appears complex (score: 75/100)
# Consider using PRD mode instead: ./claude-loop.sh --prd <prd-file>
#
# Continue with quick mode anyway? [y/N]
```

**Configuration:**
- Default threshold: 60
- Customize: Set threshold in code or via environment variable

### 3. Task Chaining

Execute multiple tasks sequentially with failure handling:

**Usage:**
```bash
# Method 1: Multiple arguments
./lib/quick-task-mode.sh chain "Fix bug in auth" "Add tests" "Update docs"

# Method 2: Semicolon-separated (from main script)
./claude-loop.sh quick "Fix bug in auth; Add tests; Update docs"

# Output:
# ========================================
#   TASK CHAIN EXECUTION
# ========================================
# Total tasks: 3
#
# Task 1/3: Fix bug in auth
# ✓ Task 1 completed successfully
#
# Task 2/3: Add tests
# ✓ Task 2 completed successfully
#
# Task 3/3: Update docs
# ✓ Task 3 completed successfully
#
# ========================================
#   TASK CHAIN SUMMARY
# ========================================
# Completed: 3/3
# Failed: 0/3
```

**Features:**
- Sequential execution (one after another)
- Progress tracking (N/total)
- Failure handling (ask to continue or abort)
- Summary report

### 4. Quick Task Templates

Pre-defined patterns for common tasks:

**Available Templates:**
1. **refactor** - Refactor code for better structure
2. **add-tests** - Add test coverage
3. **fix-bug** - Debug and fix issues

**Usage:**
```bash
# Use template
./claude-loop.sh quick "Refactor user service" --template refactor

# List available templates
./lib/quick-task-mode.sh templates

# Output:
# ========================================
#   AVAILABLE QUICK TASK TEMPLATES
# ========================================
#
#   - refactor: Refactor code for better structure and maintainability
#   - add-tests: Add test coverage for existing code
#   - fix-bug: Fix a bug in existing code
```

**Template Structure:**
```json
{
  "name": "refactor",
  "description": "Refactor code for better structure",
  "steps": [
    {"id": 1, "action": "Read and understand current implementation", "type": "read"},
    {"id": 2, "action": "Identify code smells", "type": "read"},
    {"id": 3, "action": "Plan refactoring approach", "type": "plan"},
    {"id": 4, "action": "Apply refactoring changes", "type": "write"},
    {"id": 5, "action": "Verify functionality preserved", "type": "verify"},
    {"id": 6, "action": "Run existing tests", "type": "bash"}
  ],
  "estimated_complexity": "medium"
}
```

**Custom Templates:**
Create your own in `templates/quick-tasks/*.json`

### 5. Dry-Run Mode

Preview execution plan without running:

**Usage:**
```bash
./claude-loop.sh quick "Add error handling to API" --dry-run

# Output:
# ========================================
#   QUICK TASK MODE
# ========================================
#
# Task: Add error handling to API
# Workspace: .
# Mode: DRY RUN (no execution)
#
# [... plan displayed ...]
#
# Estimated cost: $0.0245
#
# ========================================
#   DRY RUN COMPLETE
# ========================================
# Plan generated successfully. Use without --dry-run to execute.
```

**Benefits:**
- Preview before committing to execution
- Estimate cost and duration
- Verify plan correctness
- No side effects

### 6. Continue Mode

Resume failed quick tasks from checkpoint:

**Usage:**
```bash
# Task fails during execution
./claude-loop.sh quick "Complex refactoring task"
# ✗ Task execution failed
# To resume this task, use: ./claude-loop.sh quick --continue

# Resume from where it left off
./claude-loop.sh quick --continue

# Output:
# Resuming failed task from: .claude-loop/quick-tasks/20260113_150030_complex
# Loaded checkpoint:
#   Step: 3   Status: in progress
```

**Features:**
- Finds last failed task automatically
- Loads checkpoint if available
- Resumes from current step
- Preserves plan and context

### 7. Cost Estimation

Estimate Claude API cost before execution:

**Algorithm:**
```
1. Count steps in plan
2. Estimate tokens per step (2000 base)
3. Apply complexity multiplier (1.0x, 1.5x, 2.0x)
4. Calculate cost using Sonnet pricing:
   - Input: $3.00 per 1M tokens
   - Output: $15.00 per 1M tokens
```

**Output:**
```bash
./claude-loop.sh quick "Add validation to user input"

# Output:
# Generating execution plan...
# Estimated cost: $0.0210
#
# [... plan approval ...]
```

**Accuracy:**
- Simple tasks: ±20%
- Medium tasks: ±30%
- Complex tasks: ±40%

### 8. Progress Checkpointing

Save execution state every 5 steps:

**Checkpoint Format:**
```json
{
  "timestamp": "2026-01-13T15:30:00Z",
  "current_step": 3,
  "status": "in progress",
  "plan": { ... }
}
```

**Storage:**
- Location: `.claude-loop/quick-tasks/{task_id}/checkpoint.json`
- Updated every 5 steps automatically
- Used by --continue mode for resumption

### 9. Concurrent Quick Tasks

Execute multiple tasks in parallel with workspace isolation:

**Usage:**
```bash
./lib/quick-task-mode.sh concurrent "Fix bug A" "Fix bug B" "Fix bug C"

# Output:
# ========================================
#   CONCURRENT TASK EXECUTION
# ========================================
# Total tasks: 3
#
# Launching task 1: Fix bug A
# Launching task 2: Fix bug B
# Launching task 3: Fix bug C
#
# All tasks launched. Waiting for completion...
#
# ✓ Task 1 completed successfully
# ✓ Task 2 completed successfully
# ✓ Task 3 completed successfully
#
# ========================================
#   CONCURRENT EXECUTION SUMMARY
# ========================================
# Completed: 3/3
# Failed: 0/3
# Logs: .claude-loop/concurrent-tasks-12345/
```

**Features:**
- Complete workspace isolation
- No interference between tasks
- All tasks run simultaneously
- Aggregate results at end

### 10. Enhanced History

View history with filtering and statistics:

**Usage:**
```bash
# Show all tasks (default)
./lib/quick-task-mode.sh history

# Show only successful tasks
./lib/quick-task-mode.sh history 20 success

# Show only failed tasks
./lib/quick-task-mode.sh history 20 failure

# Show statistics
./lib/quick-task-mode.sh stats

# Output:
# ========================================
#   QUICK TASK STATISTICS
# ========================================
#
# Total tasks: 47
# Successful: 42 (89.4%)
# Failed: 5 (10.6%)
#
# Average duration: 45.2s
# Total cost: $1.2450
# Average cost: $0.0265
```

## Updated CLI Flags

### All Flags

```bash
./claude-loop.sh quick "task description" [OPTIONS]

Options:
  --workspace DIR       Set workspace directory (default: .)
  --commit              Auto-commit on success
  --escalate            Auto-escalate to PRD if complex (threshold: 60)
  --dry-run             Show plan without executing
  --continue            Resume last failed task
  --template NAME       Use template (refactor, add-tests, fix-bug)
```

### Flag Combinations

```bash
# Preview with cost estimate
./claude-loop.sh quick "Add API endpoint" --dry-run

# Resume with auto-commit
./claude-loop.sh quick --continue --commit

# Template with workspace
./claude-loop.sh quick "Refactor auth logic" --template refactor --workspace src/auth

# Escalation check with workspace
./claude-loop.sh quick "Complex refactoring" --escalate --workspace src/
```

## Updated Audit Log Schema

Enhanced JSONL format with cost tracking:

```json
{
  "task_id": "20260113_150030_add_tests",
  "task": "Add unit tests for utils",
  "status": "success",
  "duration_ms": 45000,
  "workspace": "src/utils",
  "timestamp": "2026-01-13T15:01:15Z",
  "worker_dir": ".claude-loop/quick-tasks/20260113_150030_add_tests",
  "cost_estimate": 0.0245
}
```

## Examples

### Example 1: Complex Task with Escalation

```bash
$ ./claude-loop.sh quick "Redesign entire database schema with migrations and tests" --escalate

========================================
  QUICK TASK MODE
========================================

Task: Redesign entire database schema with migrations and tests
Workspace: .

Generating execution plan...
Estimated cost: $0.1250

⚠️  COMPLEXITY WARNING ⚠️
This task appears complex (score: 85/100)
Consider using PRD mode instead: ./claude-loop.sh --prd <prd-file>

Continue with quick mode anyway? [y/N] n

Task aborted. Please create a PRD for this task.
```

### Example 2: Task Chain

```bash
$ ./lib/quick-task-mode.sh chain "Fix typo in README" "Run linter" "Update changelog"

========================================
  TASK CHAIN EXECUTION
========================================
Total tasks: 3

----------------------------------------
Task 1/3: Fix typo in README
----------------------------------------

[... task 1 execution ...]
✓ Task 1 completed successfully

----------------------------------------
Task 2/3: Run linter
----------------------------------------

[... task 2 execution ...]
✓ Task 2 completed successfully

----------------------------------------
Task 3/3: Update changelog
----------------------------------------

[... task 3 execution ...]
✓ Task 3 completed successfully

========================================
  TASK CHAIN SUMMARY
========================================
Completed: 3/3
Failed: 0/3
```

### Example 3: Template with Dry-Run

```bash
$ ./claude-loop.sh quick "Refactor user authentication" --template refactor --dry-run

========================================
  QUICK TASK MODE
========================================

Task: Refactor user authentication
Workspace: .
Mode: DRY RUN (no execution)
Template: refactor

Loading template...
Estimated cost: $0.0320

========================================
  QUICK TASK EXECUTION PLAN
========================================

Task: Refactor user authentication

Planned Steps:
  1. [read] Read and understand current implementation
  2. [read] Identify code smells and improvement opportunities
  3. [plan] Plan refactoring approach
  4. [write] Apply refactoring changes
  5. [verify] Verify functionality preserved
  6. [bash] Run existing tests

Estimated Complexity: medium

========================================

Proceed with this plan? [y/N] n

========================================
  DRY RUN COMPLETE
========================================
Plan generated successfully. Use without --dry-run to execute.
```

### Example 4: Continue Failed Task

```bash
# Initial attempt fails
$ ./claude-loop.sh quick "Complex database migration"
✗ Task execution failed
To resume this task, use: ./claude-loop.sh quick --continue

# Resume
$ ./claude-loop.sh quick --continue

Resuming failed task from: .claude-loop/quick-tasks/20260113_160000_complex
Loaded checkpoint:
  Step: 7   Status: error during migration

[... continues from step 7 ...]

✓ Task completed successfully on retry
```

### Example 5: History with Filter

```bash
$ ./lib/quick-task-mode.sh history 10 failure

========================================
  QUICK TASK HISTORY (last 10)
  Filter: failure
========================================

✗ [2026-01-13T16:00:00Z] Complex database migration (180s, $0.0890)
✗ [2026-01-13T15:45:00Z] Refactor entire auth system (240s, $0.1200)
✗ [2026-01-13T14:30:00Z] Add comprehensive test suite (156s, $0.0780)
```

### Example 6: Concurrent Execution

```bash
$ ./lib/quick-task-mode.sh concurrent "Fix bug #123" "Fix bug #124" "Fix bug #125"

========================================
  CONCURRENT TASK EXECUTION
========================================
Total tasks: 3

Launching task 1: Fix bug #123
Launching task 2: Fix bug #124
Launching task 3: Fix bug #125

All tasks launched. Waiting for completion...

✓ Task 1 completed successfully
✓ Task 3 completed successfully
✓ Task 2 completed successfully

========================================
  CONCURRENT EXECUTION SUMMARY
========================================
Completed: 3/3
Failed: 0/3
Logs: .claude-loop/concurrent-tasks-56789/
```

## Configuration

### Environment Variables

```bash
# Timeout per task (default: 600s = 10 min)
export QUICK_TASK_TIMEOUT=900

# Tasks directory (default: ./.claude-loop/quick-tasks)
export QUICK_TASKS_DIR="/custom/path"

# Templates directory (default: ./templates/quick-tasks)
export QUICK_TASK_TEMPLATES_DIR="/custom/templates"

# Checkpoint interval (default: 5 steps)
export QUICK_TASK_CHECKPOINT_INTERVAL=3

# Complexity threshold for escalation (default: 60)
export QUICK_TASK_ESCALATION_THRESHOLD=70
```

## Testing

Comprehensive test suite for advanced features:

```bash
# Run all quick mode advanced tests
./tests/quick-mode/test_quick_mode_advanced.sh

# Tests include:
# - Complexity detection
# - Escalation logic
# - Template creation/loading
# - Cost estimation
# - Checkpoint save/load
# - History filtering
# - Statistics calculation
# - Concurrent execution
# - Task chaining
```

## Integration Points

### With Skills Framework (US-201, US-202)

```bash
# Use skills in quick tasks
./claude-loop.sh quick "Validate PRD with prd-validator skill"

# Use templates that invoke skills
./claude-loop.sh quick "Scaffold tests" --template test-scaffolder
```

### With Daemon Mode (US-205)

```bash
# Submit quick task to daemon queue
./claude-loop.sh daemon submit-quick "Complex long-running task"

# Chain of tasks in daemon
./claude-loop.sh daemon submit-quick-chain "Task 1" "Task 2" "Task 3"
```

### With Dashboard (US-207, US-208)

- Real-time quick task progress in dashboard
- History view with filtering by status/cost
- Statistics and success rate charts
- Cost tracking over time

## Performance

### Complexity Detection
- Overhead: < 50ms per task
- No external calls required
- Heuristic-based (instant)

### Cost Estimation
- Overhead: < 100ms per task
- Python calculation (fast)
- Accuracy: ±20-40% depending on complexity

### Checkpointing
- Overhead: < 200ms per checkpoint
- Saves every 5 steps (configurable)
- JSON serialization (efficient)

### Template Loading
- Overhead: < 100ms per template
- Cached after first load
- JSON parsing only

## Limitations

1. **Complexity Detection**: Heuristic-based, may misclassify edge cases
2. **Cost Estimation**: Estimates only, actual cost may vary
3. **Concurrent Execution**: No dependency management between tasks
4. **Template Library**: Only 3 templates included (extensible)
5. **Checkpoint Granularity**: Fixed at 5 steps (configurable via env var)

## Future Enhancements

1. **Machine Learning Complexity Detection**: Learn from historical data
2. **Dynamic Cost Adjustment**: Update estimates as task progresses
3. **Smart Template Suggestions**: Recommend templates based on task description
4. **Checkpoint Optimization**: Variable checkpoint frequency based on cost
5. **Advanced Concurrency**: DAG-based dependency management for parallel tasks
6. **Template Marketplace**: Share and discover community templates

## Troubleshooting

### Complexity Detection Issues

**Problem**: Task classified incorrectly

**Solution**: Adjust threshold or add keywords
```bash
# Lower escalation threshold
export QUICK_TASK_ESCALATION_THRESHOLD=50

# Add custom complexity keywords in code
# (modify detect_task_complexity function)
```

### Cost Estimation Inaccurate

**Problem**: Actual cost differs significantly from estimate

**Solution**: Cost is estimated, not exact. For precise cost tracking, check dashboard after completion.

### Template Not Found

**Problem**: `Template not found: custom-template`

**Solution**:
```bash
# Check template exists
ls templates/quick-tasks/custom-template.json

# Create custom template
cat > templates/quick-tasks/custom-template.json <<EOF
{
  "name": "custom-template",
  "description": "My custom template",
  "steps": [ ... ]
}
EOF
```

### Checkpoint Not Loading

**Problem**: `No checkpoint found, starting from beginning`

**Solution**: Checkpoints only saved during execution. If task failed before first checkpoint (< 5 steps), no checkpoint exists.

### Concurrent Tasks Interfere

**Problem**: Concurrent tasks modify same files

**Solution**: Use workspace isolation or run sequentially
```bash
# Sequential (task chain)
./lib/quick-task-mode.sh chain "Task 1" "Task 2"

# Concurrent with isolation (automatic)
./lib/quick-task-mode.sh concurrent "Task 1" "Task 2"
```

## See Also

- [Quick Task Mode Core](./quick-task-mode.md) - US-203
- [Skills Architecture](./skills-architecture.md) - US-201, US-202
- [Daemon Mode](./daemon-mode.md) - US-205, US-206
- [Visual Progress Dashboard](./dashboard-ui.md) - US-207, US-208
