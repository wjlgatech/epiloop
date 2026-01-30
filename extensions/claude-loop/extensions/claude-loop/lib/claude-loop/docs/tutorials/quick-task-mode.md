# Quick Task Mode Tutorial

Master Quick Task Mode for lightweight, natural language task execution without PRD authoring.

## Table of Contents

- [What is Quick Task Mode?](#what-is-quick-task-mode)
- [When to Use Quick Mode](#when-to-use-quick-mode)
- [Basic Usage](#basic-usage)
- [Advanced Features](#advanced-features)
- [Task Templates](#task-templates)
- [Best Practices](#best-practices)
- [Troubleshooting](#troubleshooting)

## What is Quick Task Mode?

Quick Task Mode allows you to execute tasks using natural language descriptions without writing a full PRD. The system:

1. Parses your task description
2. Generates an execution plan
3. Asks for your approval
4. Executes the plan
5. Creates a git commit automatically

**Benefits**:
- 20-40% token reduction vs full PRD
- Faster iteration (no PRD authoring)
- Automatic commit message generation
- Task history tracking

## When to Use Quick Mode

### Good Use Cases ✅

- **Simple tasks** (< 3 stories)
- **Single file changes**
- **Quick fixes or additions**
- **Exploratory work**
- **Tasks under $1 cost**

Examples:
- "Add a validation function for email addresses"
- "Fix the bug in the authentication middleware"
- "Refactor the user controller to use async/await"
- "Add unit tests for the API endpoints"

### When to Use PRD Mode Instead ❌

- **Complex features** (3+ stories)
- **Multiple file changes** (5+ files)
- **Architectural changes**
- **Tasks over $1 cost**
- **Tasks requiring careful planning**

Examples:
- "Implement user authentication with OAuth"
- "Add a complete checkout flow"
- "Migrate from REST to GraphQL"
- "Implement a new microservice"

## Basic Usage

### Your First Quick Task

```bash
# Simple task
./claude-loop.sh quick "Create a function that calculates the factorial of a number"
```

This will:
1. Show you a 5-10 step execution plan
2. Estimate the cost
3. Ask for your approval
4. Execute the task
5. Create a git commit with a formatted message

### Viewing Task History

```bash
# Show all past quick tasks
./claude-loop.sh quick history

# Output:
# 2026-01-13 10:30:00 | SUCCESS | Create factorial function | $0.15 | abc123
# 2026-01-13 11:45:00 | SUCCESS | Add email validation | $0.08 | def456
# 2026-01-13 14:20:00 | FAILURE | Complex refactoring | $0.45 | N/A
```

### Filtering History

```bash
# Show only successful tasks
./claude-loop.sh quick history --status success

# Show only failures
./claude-loop.sh quick history --status failure

# Show last 10 tasks
./claude-loop.sh quick history --limit 10
```

### Task Statistics

```bash
# Show aggregate statistics
./claude-loop.sh quick stats

# Output:
# Quick Task Statistics
# ====================
# Total tasks: 25
# Successful: 22 (88%)
# Failed: 3 (12%)
# Total cost: $3.45
# Average cost: $0.14/task
# Average duration: 45s
```

## Advanced Features

### Dry Run Mode

Preview the plan and cost without executing:

```bash
./claude-loop.sh quick "Refactor the API client" --dry-run
```

This shows:
- Execution plan (5-10 steps)
- Estimated cost
- Complexity score

### Custom Workspace

Execute in a specific directory:

```bash
./claude-loop.sh quick "Add tests" --workspace src/api/
```

### Auto-Commit

Automatically commit on success without prompting:

```bash
./claude-loop.sh quick "Fix typo in README" --commit
```

### Complexity Detection

The system automatically detects task complexity:

```bash
./claude-loop.sh quick "Implement complete authentication system"

# Output:
# ⚠️  COMPLEXITY WARNING
# This task has a complexity score of 75 (complex)
# Recommendation: Consider using PRD mode for better results
# Continue anyway? (y/n)
```

**Complexity Levels**:
- **Simple** (0-29): Quick mode ideal
- **Medium** (30-59): Quick mode acceptable with warning
- **Complex** (60-100): PRD mode recommended

### Escalation to PRD Mode

Automatically convert to PRD if complexity is too high:

```bash
./claude-loop.sh quick "Build microservice with database" --escalate

# If complexity > 60:
# This task is too complex for quick mode (score: 85)
# Generating PRD for better execution...
# PRD saved to: .claude-loop/generated-prds/task-20260113-143000.json
# Execute with: ./claude-loop.sh --prd .claude-loop/generated-prds/task-20260113-143000.json
```

### Resuming Failed Tasks

If a quick task fails, resume from the last checkpoint:

```bash
# Find the last failed task
./claude-loop.sh quick history --status failure

# Resume it
./claude-loop.sh quick --continue

# Or specify a specific task
./claude-loop.sh quick --continue .claude-loop/quick-tasks/20260113_143000_my_task
```

### Task Chaining

Execute multiple quick tasks sequentially:

```bash
./claude-loop.sh quick \
    "Add validation" \
    "Add tests" \
    "Update documentation"

# Each task executes after the previous one succeeds
# Stops on first failure and prompts for action
```

## Task Templates

### Using Templates

Templates provide pre-defined execution plans for common patterns:

```bash
# List available templates
./claude-loop.sh quick templates

# Output:
# Available Quick Task Templates:
# - refactor: 6-step refactoring workflow
# - add-tests: 5-step test creation workflow
# - fix-bug: 6-step debugging workflow

# Use a template
./claude-loop.sh quick "Refactor user model" --template refactor
```

### Built-in Templates

#### 1. Refactor Template

**Use case**: Code refactoring and cleanup

**Steps**:
1. Read and understand current code
2. Identify refactoring opportunities
3. Create backup of current state
4. Apply refactoring changes
5. Run tests to verify
6. Update related documentation

```bash
./claude-loop.sh quick "Refactor auth middleware" --template refactor
```

#### 2. Add Tests Template

**Use case**: Adding test coverage

**Steps**:
1. Read the code to be tested
2. Identify test cases needed
3. Create test file structure
4. Write unit tests
5. Run tests and verify passing

```bash
./claude-loop.sh quick "Add tests for API routes" --template add-tests
```

#### 3. Fix Bug Template

**Use case**: Debugging and fixing issues

**Steps**:
1. Reproduce the bug
2. Read relevant code
3. Identify root cause
4. Apply fix
5. Add regression test
6. Verify fix works

```bash
./claude-loop.sh quick "Fix authentication timeout" --template fix-bug
```

### Creating Custom Templates

Create your own template in `templates/quick-tasks/my-template.json`:

```json
{
  "name": "my-template",
  "description": "My custom workflow",
  "steps": [
    {
      "id": 1,
      "action": "Read current implementation",
      "tool": "Read",
      "estimated_tokens": 500
    },
    {
      "id": 2,
      "action": "Make changes",
      "tool": "Edit",
      "estimated_tokens": 300
    },
    {
      "id": 3,
      "action": "Run tests",
      "tool": "Bash",
      "estimated_tokens": 200
    }
  ],
  "estimated_cost_usd": 0.10
}
```

Use it:

```bash
./claude-loop.sh quick "My task" --template my-template
```

## Best Practices

### 1. Keep Tasks Focused

**Good**:
```bash
./claude-loop.sh quick "Add email validation to the signup form"
```

**Bad**:
```bash
./claude-loop.sh quick "Implement complete user authentication with OAuth, 2FA, password reset, and email verification"
```

### 2. Be Specific

**Good**:
```bash
./claude-loop.sh quick "Fix the off-by-one error in the pagination logic in src/api/users.ts"
```

**Bad**:
```bash
./claude-loop.sh quick "Fix bugs"
```

### 3. Use Dry Run for Cost Estimation

```bash
# Always estimate first for unfamiliar tasks
./claude-loop.sh quick "Complex task description" --dry-run

# If cost is acceptable, execute
./claude-loop.sh quick "Complex task description"
```

### 4. Leverage Templates

```bash
# Instead of describing the full workflow
./claude-loop.sh quick "Refactor the user service to improve performance" --template refactor

# The template handles the workflow structure
```

### 5. Check Complexity

```bash
# For medium/large tasks, check complexity first
./claude-loop.sh quick "Task description" --dry-run

# If complexity > 60, use PRD mode instead
```

### 6. Use History for Learning

```bash
# Review successful patterns
./claude-loop.sh quick history --status success

# Analyze failures
./claude-loop.sh quick history --status failure
```

### 7. Workspace Isolation

```bash
# Keep related tasks in the same workspace
./claude-loop.sh quick "Task 1" --workspace feature/my-feature
./claude-loop.sh quick "Task 2" --workspace feature/my-feature
```

## Common Use Cases

### 1. Quick Fixes

```bash
./claude-loop.sh quick "Fix the typo in the error message on line 42 of auth.ts"
```

### 2. Adding Features

```bash
./claude-loop.sh quick "Add a method to calculate the user's age from their birthdate"
```

### 3. Refactoring

```bash
./claude-loop.sh quick "Extract the database logic from the controller into a separate service" --template refactor
```

### 4. Testing

```bash
./claude-loop.sh quick "Add unit tests for the authentication middleware" --template add-tests
```

### 5. Documentation

```bash
./claude-loop.sh quick "Add JSDoc comments to the API client class"
```

### 6. Code Generation

```bash
./claude-loop.sh quick "Generate a REST API endpoint for managing blog posts"
```

## Troubleshooting

### Issue: Task is Too Complex

**Symptom**: Complexity warning or poor results

**Solution**: Use PRD mode instead

```bash
# Convert to PRD
./claude-loop.sh quick "Complex task" --escalate
```

### Issue: Task Fails Midway

**Symptom**: Execution stops with error

**Solution**: Resume from checkpoint

```bash
# Check last failed task
./claude-loop.sh quick history --status failure

# Resume
./claude-loop.sh quick --continue
```

### Issue: Cost Higher Than Expected

**Symptom**: Actual cost exceeds estimate

**Solution**: Break into smaller tasks or use templates

```bash
# Instead of one large task
./claude-loop.sh quick "Large task"

# Break into smaller tasks
./claude-loop.sh quick "Subtask 1"
./claude-loop.sh quick "Subtask 2"
./claude-loop.sh quick "Subtask 3"
```

### Issue: Plan Doesn't Match Intent

**Symptom**: Generated plan is not what you wanted

**Solution**: Be more specific in description

```bash
# Vague
./claude-loop.sh quick "Update API"

# Specific
./claude-loop.sh quick "Update the /api/users endpoint to include the user's email in the response"
```

### Issue: Concurrent Tasks Conflict

**Symptom**: Quick tasks interfere with each other

**Solution**: Use workspace isolation

```bash
# Task 1 in workspace A
./claude-loop.sh quick "Task 1" --workspace .claude-loop/quick-tasks/workspace-a

# Task 2 in workspace B
./claude-loop.sh quick "Task 2" --workspace .claude-loop/quick-tasks/workspace-b
```

## Advanced Workflows

### Workflow 1: Iterative Development

```bash
# 1. Initial implementation
./claude-loop.sh quick "Create basic user API"

# 2. Add validation
./claude-loop.sh quick "Add input validation to user API"

# 3. Add tests
./claude-loop.sh quick "Add tests for user API" --template add-tests

# 4. Add documentation
./claude-loop.sh quick "Add API documentation"
```

### Workflow 2: Bug Fix with Test

```bash
# Use the fix-bug template which includes adding a regression test
./claude-loop.sh quick "Fix the date parsing bug in the analytics module" --template fix-bug
```

### Workflow 3: Feature with Approval Gate

```bash
# 1. Dry run to see plan
./claude-loop.sh quick "Add search functionality" --dry-run

# 2. If plan looks good, execute
./claude-loop.sh quick "Add search functionality"

# 3. Review and test manually

# 4. Commit if satisfied (or already committed with --commit flag)
```

## Cost Optimization

### Tips for Reducing Costs

1. **Use templates** - Pre-defined plans are more efficient
2. **Be specific** - Reduces back-and-forth iterations
3. **Break tasks down** - Smaller tasks are more efficient
4. **Use dry run** - Avoid executing expensive tasks
5. **Leverage checkpoints** - Resume instead of restarting

### Cost Comparison

| Task Type | Without Quick Mode | With Quick Mode | Savings |
|-----------|-------------------|-----------------|---------|
| Simple fix | $0.25 | $0.15 | 40% |
| Add feature | $0.80 | $0.50 | 37.5% |
| Refactoring | $1.20 | $0.75 | 37.5% |
| Add tests | $0.60 | $0.40 | 33% |

## Next Steps

- **Explore daemon mode**: [Daemon Mode Tutorial](daemon-mode.md)
- **Monitor with dashboard**: [Dashboard Tutorial](dashboard.md)
- **Create custom templates**: [Templates Guide](../reference/quick-task-templates.md)
- **Check troubleshooting**: [Troubleshooting Guide](../troubleshooting/phase2-troubleshooting.md)

Happy quick tasking! ⚡
