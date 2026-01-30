# Quick Task Mode (US-203)

**Status**: ✅ Implemented
**Priority**: High
**Feature ID**: US-203

## Overview

Quick Task Mode implements Cowork-style natural language task execution without PRD authoring. Users describe a task in plain English, Claude generates an execution plan, gets approval, and implements it with automatic commit.

## Key Features

1. **Natural Language Input**: Describe tasks conversationally
2. **Automatic Plan Generation**: Claude creates 5-10 step execution plan
3. **User Approval Checkpoint**: Review plan before execution
4. **Isolated Worker Directory**: Each task runs in isolated environment
5. **Progress Indicators**: Real-time feedback during execution
6. **Auto-Commit**: Optional automatic git commit on success
7. **Audit Trail**: Complete history logged in JSONL format

## Usage

### Basic Quick Task

```bash
./claude-loop.sh quick "Add error handling to auth.js"
```

### With Options

```bash
# Execute in specific workspace
./claude-loop.sh quick "Fix typo in README" --workspace docs/

# Auto-commit on success
./claude-loop.sh quick "Update dependencies" --commit

# Both options
./claude-loop.sh quick "Add unit tests for utils" --workspace src/utils --commit
```

### View History

```bash
# Show last 20 quick tasks
./claude-loop.sh quick history

# Script can show custom limit (when sourced)
source lib/quick-task-mode.sh
show_quick_task_history 50
```

## Execution Flow

```
User Input → Parse Task → Generate Plan → Display for Approval
                                              ↓
                                         User Approves?
                                              ↓
                                   Create Worker Directory
                                              ↓
                                    Execute Task (Agentic Loop)
                                              ↓
                                    Generate Commit Message
                                              ↓
                                      Auto-Commit (optional)
                                              ↓
                                        Log to Audit Trail
```

## Architecture

### Components

1. **Task Parser** (`parse_task_description`)
   - Sanitizes natural language input
   - Removes special characters that could break scripts
   - Preserves meaningful content

2. **Plan Generator** (`generate_execution_plan`)
   - Creates 5-10 concrete, actionable steps
   - Categorizes each step by type (read/write/bash/verify)
   - Estimates complexity (simple/medium/complex)
   - Returns JSON structure

3. **Approval Interface** (`display_plan_for_approval`)
   - Shows task description
   - Lists all steps with types
   - Displays estimated complexity
   - Prompts user for approval

4. **Worker Manager** (`create_quick_task_worker`)
   - Creates isolated directory: `.claude-loop/quick-tasks/{timestamp}_{task}/`
   - Includes logs subdirectory
   - Prevents interference with other tasks

5. **Execution Engine** (`execute_quick_task`)
   - Saves plan to worker directory
   - Creates iteration prompt for Claude
   - Runs agentic perception-planning-action loop
   - Checks for completion marker
   - Returns success/failure status

6. **Commit Generator** (`generate_commit_message`)
   - Heuristically determines commit type (feat/fix/refactor/test/docs)
   - Formats message according to Conventional Commits
   - Includes Co-Authored-By for Claude

7. **Audit Logger** (`log_quick_task`)
   - Appends to `.claude-loop/quick-tasks.jsonl`
   - Logs: task_id, description, status, duration, timestamp
   - Enables history and analytics

## File Structure

```
.claude-loop/
└── quick-tasks/
    ├── quick-tasks.jsonl              # Audit trail (append-only)
    └── 20260113_150030_add_tests/     # Worker directory
        ├── plan.json                  # Execution plan
        ├── prompt.txt                 # Iteration prompt
        └── logs/
            ├── output.log             # stdout
            ├── error.log              # stderr
            └── combined.log           # both
```

## Plan JSON Schema

```json
{
  "task": "task description",
  "steps": [
    {
      "id": 1,
      "action": "step description",
      "type": "read|write|bash|verify"
    }
  ],
  "estimated_complexity": "simple|medium|complex"
}
```

## Audit Log Schema (JSONL)

Each line is a JSON object:

```json
{
  "task_id": "20260113_150030_add_tests",
  "task": "Add unit tests for utils",
  "status": "success",
  "duration_ms": 45000,
  "workspace": "src/utils",
  "timestamp": "2026-01-13T15:01:15Z",
  "worker_dir": ".claude-loop/quick-tasks/20260113_150030_add_tests"
}
```

## Configuration

Environment variables can customize behavior:

```bash
# Timeout for quick task execution (default: 600 seconds = 10 minutes)
export QUICK_TASK_TIMEOUT=900

# Quick tasks directory (default: ./.claude-loop/quick-tasks)
export QUICK_TASKS_DIR="/custom/path/quick-tasks"
```

## Commit Message Format

Quick task commits follow this pattern:

```
{type}: {task description}

Quick task executed via claude-loop quick mode.

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>
```

Where `{type}` is determined heuristically:
- `feat`: Default for new functionality
- `fix`: If task mentions "fix" or "bug"
- `refactor`: If task mentions "refactor"
- `test`: If task mentions "test"
- `docs`: If task mentions "doc" or "documentation"

## Examples

### Example 1: Simple File Edit

```bash
$ ./claude-loop.sh quick "Fix typo in README.md line 42" --commit

========================================
  QUICK TASK MODE
========================================

Task: Fix typo in README.md line 42
Workspace: .

Generating execution plan...

========================================
  QUICK TASK EXECUTION PLAN
========================================

Task: Fix typo in README.md line 42

Planned Steps:
  1. [read] Analyze task requirements
  2. [read] Identify files to modify
  3. [write] Implement changes
  4. [verify] Verify changes work
  5. [bash] Run tests if applicable

Estimated Complexity: simple

========================================

Proceed with this plan? [y/N] y

Executing task...
Working directory: .

✓ Task completed successfully

Creating git commit...
[main abc1234] fix: Fix typo in README.md line 42

========================================
  QUICK TASK SUCCESS
========================================
Duration: 23s
Logs: .claude-loop/quick-tasks/20260113_150030_fix_typo/logs/
```

### Example 2: Add Feature with Tests

```bash
$ ./claude-loop.sh quick "Add validateEmail function to utils.js with tests" --workspace src/utils --commit

========================================
  QUICK TASK MODE
========================================

Task: Add validateEmail function to utils.js with tests
Workspace: src/utils

[... plan generation and approval ...]

Executing task...
Working directory: src/utils

✓ Task completed successfully

Creating git commit...
[main def5678] feat: Add validateEmail function to utils.js with tests

========================================
  QUICK TASK SUCCESS
========================================
Duration: 67s
Logs: .claude-loop/quick-tasks/20260113_151200_add_validate/logs/
```

### Example 3: View History

```bash
$ ./claude-loop.sh quick history

========================================
  QUICK TASK HISTORY (last 20)
========================================

✓ [2026-01-13T15:12:00Z] Add validateEmail function to utils.js with tests (67s)
✓ [2026-01-13T15:00:30Z] Fix typo in README.md line 42 (23s)
✗ [2026-01-13T14:45:00Z] Refactor database connection logic (120s)
✓ [2026-01-13T14:30:00Z] Update dependencies to latest versions (45s)
```

## Limitations (Current Implementation)

1. **Plan Generation**: Currently uses a template plan. Full implementation would call Claude API to generate custom plans.

2. **Execution Engine**: Currently simulates execution. Full implementation would use the same agentic loop as main claude-loop.

3. **Escalation**: `--escalate` flag is recognized but not yet implemented. Future feature to convert complex quick tasks to PRD.

4. **Error Recovery**: Basic error handling. Future versions will support rollback and retry.

5. **Concurrency**: Quick tasks run sequentially. Future versions may support parallel execution.

## Future Enhancements (US-204)

The following features are planned for US-204 (Quick Task Mode - Advanced Features):

1. **Complexity Detection**: Auto-estimate if task is quick or needs PRD
2. **Auto-Escalation**: Convert to PRD if complexity threshold exceeded
3. **Task Chaining**: Execute multiple quick tasks sequentially
4. **Templates**: Common patterns (refactor, add tests, fix bug)
5. **Dry Run**: `--dry-run` flag to show plan without executing
6. **Resume**: `--continue` flag to resume failed tasks
7. **Cost Estimation**: Show estimated cost before execution
8. **Checkpointing**: Save state every N steps
9. **Concurrency**: `--concurrent` for parallel quick tasks
10. **Enhanced History**: Search, filter, replay previous tasks

## Integration Points

### With Skills Framework (US-201)

Quick tasks can leverage skills:
- Task: "Validate PRD using prd-validator skill"
- Plan step: `execute_skill "prd-validator" "prd.json"`

### With Daemon Mode (US-205)

Quick tasks can be submitted to daemon:
- `./claude-loop.sh daemon submit-quick "task description"`
- Background execution with notification on completion

### With Dashboard (US-207, US-208)

Quick task progress visible in dashboard:
- Real-time status updates
- History view with filtering
- Success rate analytics

## Testing

Quick task mode includes integration tests:

```bash
# Run quick task mode tests (when implemented)
./tests/quick-mode/test_quick_task_mode.sh

# Test plan generation
./tests/quick-mode/test_plan_generation.sh

# Test worker isolation
./tests/quick-mode/test_worker_isolation.sh

# Test commit generation
./tests/quick-mode/test_commit_generation.sh

# Test audit logging
./tests/quick-mode/test_audit_logging.sh
```

## Troubleshooting

### Task Fails to Execute

Check worker logs:
```bash
tail -f .claude-loop/quick-tasks/{task_id}/logs/combined.log
```

### Plan Not Generated

Ensure Python 3 is available for JSON parsing:
```bash
python3 --version
```

### Commit Fails

Check git status and ensure there are changes:
```bash
git status
git diff
```

### History Not Showing

Check audit log exists and is readable:
```bash
cat .claude-loop/quick-tasks/quick-tasks.jsonl
```

## See Also

- [Skills Architecture](./skills-architecture.md) - US-201, US-202
- [Daemon Mode](./daemon-mode.md) - US-205, US-206
- [Visual Progress Dashboard](./dashboard-ui.md) - US-207, US-208
- [Quick Task Mode Advanced Features](./quick-task-mode-advanced.md) - US-204 (planned)
