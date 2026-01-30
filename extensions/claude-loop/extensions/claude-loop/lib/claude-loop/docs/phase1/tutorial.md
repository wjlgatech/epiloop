# Tutorial: Your First Claude-Loop Project with Phase 1 Features

**Goal**: Build a complete "Task Manager" API using all Phase 1 features.

**Time**: 15-20 minutes
**Difficulty**: Beginner

## What You'll Learn

- How to use PRD templates to jumpstart projects
- How workspace sandboxing protects your codebase
- How progress indicators keep you informed
- How safety confirmations prevent mistakes

## Prerequisites

- claude-loop installed and configured
- Basic understanding of REST APIs
- Git repository initialized

## Step 1: Choose a Template

We're building an API, so let's use the `api-endpoint` template:

```bash
# List available templates
./claude-loop.sh --list-templates
```

You should see:

```
Available PRD Templates:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📱 web-feature       - Full-stack feature with frontend + backend
🔌 api-endpoint      - REST/GraphQL API endpoint
🔧 refactoring       - Code restructuring
🐛 bug-fix           - Issue reproduction and fix
📚 documentation     - README/docs updates
🧪 testing           - Test coverage expansion
```

## Step 2: Generate Your PRD

Generate a PRD for a task management API:

```bash
./claude-loop.sh --template api-endpoint \
  --template-var ENDPOINT_NAME=TaskManager \
  --template-var DESCRIPTION="CRUD API for managing tasks with title, description, status, and due date" \
  --template-var HTTP_METHOD=GET,POST,PUT,DELETE \
  --template-var ENDPOINT_PATH=/api/tasks
```

This creates `prd.json` with 5-7 user stories covering:
- Model/schema definition
- CRUD endpoints (GET, POST, PUT, DELETE)
- Input validation
- Error handling
- Unit and integration tests
- API documentation

**Tip**: Open `prd.json` to see the generated stories!

## Step 3: Set Up Workspace Sandboxing

Let's limit claude-loop to only modify API-related files:

```bash
./claude-loop.sh --workspace "src/api,tests/api" --safety-level cautious
```

**What this does:**
- `--workspace "src/api,tests/api"` - Only allow changes to these folders
- `--safety-level cautious` - Ask before destructive operations

## Step 4: Watch It Work!

Once you run the command above, you'll see the progress UI:

```
╔════════════════════════════════════════════════════════════════╗
║ Story 1/7: Create Task Model with Validation
║ Workspace: src/api, tests/api
║
║ Overall Progress: [██░░░░░░░░] 1/7 stories (14%)
║ Time: 2m elapsed | ~12m remaining
║ Currently: Writing model schema
║
║ Acceptance Criteria:
║   ✅ Create Task model with fields (id, title, description, status, due_date)
║   ⏳ Add Pydantic validation for required fields
║   ○ Add status enum (TODO, IN_PROGRESS, DONE)
║   ○ Write unit tests for model validation
╚════════════════════════════════════════════════════════════════╝
```

### What's Happening?

1. **Story 1/7** - Claude is implementing the first user story
2. **Progress Bar** - Visual indicator of completion (14% done)
3. **Time Estimates** - Based on story velocity
4. **Acceptance Criteria** - Real-time checklist of what's being done
5. **Workspace** - Reminds you of the sandboxed folders

## Step 5: Approve Checkpoint (If Needed)

If claude-loop needs to do something destructive, you'll see:

```
⚠️  CHECKPOINT CONFIRMATION REQUIRED ⚠️
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Action: Create new directory
Path: src/api/models/

Reason: Organizing Task model in models directory

Do you approve this action?
  [y] Yes     [n] No     [a] Yes to all     [q] Abort

Your choice: _
```

**For this tutorial**: Type `a` (Yes to all) since we trust the API template.

## Step 6: Monitor Progress

As claude-loop works through stories, you'll see:

```
╔════════════════════════════════════════════════════════════════╗
║ Story 3/7: Implement POST /api/tasks Endpoint
║ Workspace: src/api, tests/api
║
║ Overall Progress: [██████░░░░] 3/7 stories (43%)
║ Time: 8m elapsed | ~10m remaining
║ Currently: Running tests
║
║ Acceptance Criteria:
║   ✅ Create POST /api/tasks endpoint handler
║   ✅ Add request validation with Pydantic
║   ✅ Add error handling (400, 500)
║   ⏳ Write integration tests for POST endpoint
╚════════════════════════════════════════════════════════════════╝
```

**Notice:**
- Progress increased from 14% → 43%
- Time estimate updated based on actual velocity
- Acceptance criteria being checked off ✅

## Step 7: Completion!

After ~15 minutes, all stories complete:

```
╔════════════════════════════════════════════════════════════════╗
║ ✅ ALL STORIES COMPLETE!
║
║ Overall Progress: [██████████] 7/7 stories (100%)
║ Time: 14m 32s total
║
║ Summary:
║   - 7 stories completed
║   - 15 files created
║   - 32 acceptance criteria met
║   - All tests passing ✅
╚════════════════════════════════════════════════════════════════╝
```

## Step 8: Review the Changes

Let's see what was created:

```bash
# Check git status
git status

# You should see:
#   new file:   src/api/models/task.py
#   new file:   src/api/routes/tasks.py
#   new file:   tests/api/test_task_model.py
#   new file:   tests/api/test_task_endpoints.py
#   new file:   docs/api/tasks-endpoint.md
#   ...and more

# Review the diff
git diff --cached
```

**Key points:**
- Only `src/api/` and `tests/api/` were modified (workspace sandboxing worked!)
- No changes to other parts of your codebase
- All tests are included

## Step 9: Commit and Deploy

```bash
# Claude-loop already staged the changes
git commit -m "feat: Add Task Manager API with CRUD endpoints

Implemented via claude-loop using api-endpoint template.

Features:
- Task model with validation
- CRUD endpoints (GET, POST, PUT, DELETE)
- Input validation and error handling
- Comprehensive test coverage
- API documentation

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"

# Push to remote
git push origin feature/task-manager-api
```

## What You Accomplished

In ~15 minutes, you:

✅ Generated a complete API implementation from a template
✅ Sandboxed the workspace to protect other code
✅ Monitored progress in real-time with visual indicators
✅ Approved checkpoints with safety confirmations
✅ Got a production-ready API with tests and docs

## Next Steps

### Customize the API

You can now:
- Add authentication to the endpoints
- Implement task assignment and collaboration
- Add search and filtering
- Connect to a real database

Just create a new PRD (or modify `prd.json`) and run claude-loop again!

### Try Other Templates

Experiment with other templates:

```bash
# Web feature (frontend + backend)
./claude-loop.sh --template web-feature \
  --template-var FEATURE_NAME=task-dashboard

# Bug fix
./claude-loop.sh --template bug-fix \
  --template-var ISSUE_NUMBER=123 \
  --template-var ISSUE_DESCRIPTION="API returns 500 on invalid task ID"

# Refactoring
./claude-loop.sh --template refactoring \
  --template-var REFACTOR_TARGET=src/api/routes/tasks.py \
  --template-var REFACTOR_GOAL="Split into smaller functions"
```

### Advanced: Combine Templates

For a full feature with frontend + backend:

1. Generate API with `api-endpoint` template
2. Let it complete
3. Generate frontend with `web-feature` template (different workspace)
4. Let it complete
5. Integration complete!

## Troubleshooting

**Problem**: Progress UI looks broken
**Solution**: Your terminal might not support unicode/colors. Use `--no-progress`.

**Problem**: Workspace validation fails
**Solution**: Make sure the folders exist: `mkdir -p src/api tests/api`

**Problem**: Safety prompts are annoying
**Solution**: Switch to `--safety-level normal` (less confirmations)

**Problem**: Time estimates are way off
**Solution**: They improve after 2-3 stories. Initial estimates are rough.

## Key Takeaways

1. **Templates save time** - Start from proven patterns
2. **Sandboxing prevents accidents** - Limit blast radius
3. **Progress indicators reduce anxiety** - Know what's happening
4. **Safety confirmations build trust** - Review before destructive ops
5. **All features work together** - Combine for maximum productivity

## Compare: Before vs After Phase 1

### Before Phase 1
```bash
# Write PRD manually (30 minutes)
vim prd.json

# Run claude-loop blindly
./claude-loop.sh

# Wait and wonder "is it stuck?"
# ...
# ...5 minutes later...still nothing visible
# ...
# Check logs to see progress
tail -f .claude-loop/logs/iteration.log
```

### After Phase 1
```bash
# Generate PRD from template (30 seconds)
./claude-loop.sh --template api-endpoint --template-var ENDPOINT_NAME=TaskManager

# Run with safety and visibility
./claude-loop.sh --workspace src/api,tests/api --safety-level cautious

# Watch real-time progress
# [██████░░░░] 3/7 stories | 8m elapsed | ~10m remaining
# Currently: Writing tests...
```

**Time saved**: 29.5 minutes on PRD creation
**Anxiety saved**: 100% (you can see what's happening!)
**Mistakes prevented**: Sandboxing + safety confirmations

---

## What's Next?

- **Deep dive**: Read [feature documentation](../features/) for advanced usage
- **Real project**: Apply these patterns to your own project
- **Share**: Tell us how Phase 1 features helped you!

Happy building! 🔄
