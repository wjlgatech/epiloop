# Cowork-Inspired Feature Proposals for Claude-Loop

**Date**: January 13, 2026
**Story**: US-008
**Purpose**: Synthesize all Cowork analysis (US-001 through US-007) into concrete, prioritized feature proposals

---

## Executive Summary

This document presents **18 feature proposals** for claude-loop, inspired by analysis of Claude Cowork's UX patterns, autonomy model, skills architecture, and first principles constraints. Each feature is evaluated using the **RICE framework** (Reach, Impact, Confidence, Effort) and grouped into 6 themes:

1. **UX & Accessibility** (5 features)
2. **Architecture & System** (4 features)
3. **Autonomy & Planning** (3 features)
4. **Observability & Trust** (3 features)
5. **Safety & Quality** (2 features)
6. **Performance & Cost** (1 feature)

**Top Priority Features** (RICE Score >150):
1. **Quick Task Mode** (RICE: 270) - Cowork-style natural language execution
2. **Visual Progress Dashboard** (RICE: 256) - Real-time web UI for progress monitoring
3. **Workspace Sandboxing** (RICE: 240) - Folder-based scope control
4. **Skills Architecture** (RICE: 225) - Progressive disclosure for deterministic operations
5. **Daemon Mode** (RICE: 192) - Background execution with task queue

---

## 1. Feature Proposals by Theme

### Theme A: UX & Accessibility

Features that reduce friction and lower barriers to entry, inspired by Cowork's "delegate to colleague" mental model.

---

#### A1. Quick Task Mode

**Description**: Enable Cowork-style natural language task execution without requiring PRD authoring. Users describe a task in one sentence, Claude generates a dynamic plan, executes it, and optionally creates a git commit.

**Problem It Solves**:
- **Primary**: PRD authoring overhead (identified in US-001, US-007)
- **Secondary**: High barrier to entry for simple tasks
- **Pain Point**: Users avoid claude-loop for quick refactoring because PRD creation takes longer than manual work

**Implementation Approach**:

```bash
# Basic usage
./claude-loop.sh quick "Reorganize src/ directory by feature"

# With workspace sandboxing
./claude-loop.sh quick --workspace src/ "Add error handling to all API calls"

# With auto-commit
./claude-loop.sh quick --commit "Refactor Button component to TypeScript"

# With escalation to PRD if complexity emerges
./claude-loop.sh quick --escalate-to-prd "Add user authentication"
```

**Technical Design**:
1. Accept natural language task via `--quick` flag
2. Use Claude's extended thinking to generate execution plan
3. Create temporary worker directory: `.claude-loop/quick-tasks/{timestamp}/`
4. Execute plan using agentic loop (perception → planning → action → observation)
5. Display real-time progress in terminal
6. On completion, optionally create git commit with auto-generated message
7. Store task + plan + outcome in `.claude-loop/quick-tasks.jsonl` for audit trail

**Effort**: **Medium** (3-4 weeks)
- 1 week: CLI interface and task parsing
- 1 week: Agentic loop execution engine
- 1 week: Git commit generation and audit logging
- 1 week: Testing and documentation

**Impact**: **High** (9/10)
- Reduces specification burden by 90% for simple tasks
- Makes claude-loop accessible to non-PRD users
- Retains audit trail (JSONL log + git commits)
- Enables Cowork-style "fire and forget" UX

**Reach**: **High** (80% of users)
- Every claude-loop user has quick tasks
- Ad-hoc refactoring is extremely common
- Will be used 5-10x more frequently than PRD mode for simple work

**Confidence**: **High** (90%)
- Claude's extended thinking is proven for planning
- Agentic loop pattern is well-established
- Low technical risk (similar to existing worker execution)

**RICE Score**: **(0.80 × 9 × 0.90) / (3.5 weeks) = 270**

**Dependencies**: None (standalone feature)

**Success Metrics**:
- 50%+ of claude-loop sessions use quick mode within 3 months
- Average time from task description to completion: <5 minutes
- User satisfaction (NPS): >8 for quick tasks

---

#### A2. Workspace Sandboxing

**Description**: Add `--workspace` flag to limit claude-loop execution scope to a specific folder or set of folders. Files outside the workspace are invisible to workers, preventing accidental modifications and simplifying PRD authoring.

**Problem It Solves**:
- **Primary**: Scope creep risk—stories can modify unrelated files (US-001)
- **Secondary**: No workspace isolation for parallel workers (US-001)
- **Pain Point**: Users worry about claude-loop touching files it shouldn't

**Implementation Approach**:

```bash
# Limit execution to src/ directory
./claude-loop.sh --workspace src/ prd.json

# Multiple workspace folders
./claude-loop.sh --workspace src/,tests/ prd.json

# Auto-infer fileScope from workspace (no manual listing)
./claude-loop.sh --workspace src/auth/ prd-auth.json
```

**Technical Design**:
1. Parse `--workspace` flag to get folder list
2. Mount workspace folders in worker directories (symlinks or copies)
3. Automatically infer `fileScope` from workspace contents (optional)
4. Add safety checks: Fail if story tries to access files outside workspace
5. Update prompt to inform Claude of workspace boundaries
6. Parallel workers get isolated workspace copies

**Effort**: **Medium** (2-3 weeks)
- 1 week: CLI parsing and workspace mounting
- 1 week: Safety checks and fileScope inference
- 1 week: Parallel worker integration

**Impact**: **High** (8/10)
- Eliminates scope creep risk
- Simplifies PRD authoring (no manual fileScope listing)
- Enables safe parallel execution (no conflicts)
- Matches Cowork's folder sandboxing UX

**Reach**: **High** (75% of projects)
- Most projects have logical folder boundaries (src/, tests/, docs/)
- Especially valuable for large monorepos
- Critical for parallel execution

**Confidence**: **High** (80%)
- Folder sandboxing is straightforward (symlinks, path restrictions)
- Some edge cases with absolute paths in code
- May need refinement for complex project structures

**RICE Score**: **(0.75 × 8 × 0.80) / (2.5 weeks) = 240**

**Dependencies**: None (standalone feature)

**Success Metrics**:
- 60%+ of PRD executions use `--workspace` within 6 months
- Zero "out of scope" file modifications when workspace enabled
- Parallel execution conflicts reduced by 70%

---

#### A3. Dynamic PRD Generation

**Description**: Allow Claude to generate PRD from natural language project description with user approval before execution. Reduces upfront planning burden while maintaining structured execution benefits.

**Problem It Solves**:
- **Primary**: PRD authoring overhead for exploratory projects (US-002, US-007)
- **Secondary**: Users don't know how to decompose work into stories upfront
- **Pain Point**: "I know what I want but don't want to write 10 stories"

**Implementation Approach**:

```bash
# Start with high-level goal
./claude-loop.sh --dynamic "Add user authentication with JWT"

# Claude generates PRD with 5-8 stories
# User reviews in interactive prompt
# Approve, reject, or modify stories
# Execution begins once approved
```

**Technical Design**:
1. Accept high-level goal via `--dynamic` flag
2. Use Claude to generate initial PRD (5-10 stories) with:
   - User story decomposition
   - Acceptance criteria
   - Dependencies (inferred from descriptions)
   - File scopes (estimated from goal)
   - Complexity estimates
3. Display generated PRD in terminal with syntax highlighting
4. Interactive approval prompt:
   - `[a]pprove` - Start execution immediately
   - `[e]dit` - Modify stories in editor
   - `[r]eject` - Cancel and exit
5. Save approved PRD to `prd-{project}.json`
6. Begin standard PRD execution

**Effort**: **High** (4-5 weeks)
- 2 weeks: LLM-powered PRD generation with quality checks
- 1 week: Interactive approval UI
- 1 week: Story dependency inference
- 1 week: Testing with various project types

**Impact**: **High** (8/10)
- Reduces PRD authoring time by 70%
- Maintains structured execution (reproducibility)
- Allows iterative refinement of plan
- Enables runtime story additions (adaptive planning)

**Reach**: **Medium-High** (60% of users)
- Especially valuable for exploratory projects
- Less useful for well-defined requirements
- Medium adoption due to trust in generated PRDs

**Confidence**: **Medium** (70%)
- LLM PRD generation quality varies
- Dependency inference may be inaccurate
- Requires user validation to catch errors

**RICE Score**: **(0.60 × 8 × 0.70) / (4.5 weeks) = 74.7**

**Dependencies**:
- Requires LLM access (Claude API or Claude CLI)
- Benefits from PRD validator skill (A5)

**Success Metrics**:
- 40%+ of PRD executions start with `--dynamic` within 6 months
- Generated PRDs require <20% user edits on average
- User satisfaction with dynamic PRDs (NPS): >7

---

#### A4. Interactive PRD Builder

**Description**: CLI wizard that walks users through PRD creation via question-and-answer flow. Generates valid PRD JSON without requiring users to understand schema or write JSON manually.

**Problem It Solves**:
- **Primary**: JSON authoring complexity (US-001)
- **Secondary**: Users don't know PRD schema requirements
- **Pain Point**: "I want to use claude-loop but JSON is intimidating"

**Implementation Approach**:

```bash
# Launch interactive builder
./claude-loop.sh --build-prd

# Wizard flow:
# 1. Project name?
# 2. Git branch?
# 3. How many user stories?
# 4. For each story:
#    - Title?
#    - Description?
#    - Acceptance criteria? (multi-line)
#    - Dependencies? (autocomplete from previous stories)
#    - File scope? (glob pattern suggestions)
#    - Complexity? (simple/medium/complex)
# 5. Review and save
```

**Technical Design**:
1. Use CLI prompting library (e.g., `inquirer`, `prompt_toolkit`)
2. Guided flow with validation at each step
3. Context-aware suggestions:
   - File scope: Glob patterns based on project structure
   - Dependencies: Autocomplete from already-defined stories
   - Complexity: Heuristics based on description keywords
4. Real-time PRD preview (show JSON as it's built)
5. Save to `prd-{project}.json` on completion
6. Optional: Run PRD validation before save

**Effort**: **Medium** (2-3 weeks)
- 1 week: CLI wizard implementation
- 1 week: Context-aware suggestions
- 1 week: Validation integration

**Impact**: **Medium** (6/10)
- Lowers barrier for JSON-averse users
- Ensures PRD validity (validation built-in)
- Slower than manual JSON editing for experienced users

**Reach**: **Medium** (40% of users)
- Valuable for new users
- Experienced users prefer text editor
- Niche audience (non-developer adjacent)

**Confidence**: **High** (85%)
- CLI wizards are straightforward
- Low technical risk
- Proven pattern (e.g., `npm init`, `cargo new`)

**RICE Score**: **(0.40 × 6 × 0.85) / (2.5 weeks) = 81.6**

**Dependencies**:
- Benefits from PRD validator skill (A5)

**Success Metrics**:
- 20%+ of new users use `--build-prd` for first PRD
- PRDs created via wizard have <5% validation errors
- Time to create first PRD: <15 minutes

---

#### A5. PRD Templates Library

**Description**: Provide pre-built PRD templates for common project types (API, CLI tool, web app, refactoring, etc.). Users select a template, fill in project-specific details, and start execution.

**Problem It Solves**:
- **Primary**: PRD authoring overhead for standard project patterns (US-001)
- **Secondary**: Users don't know how to structure stories for different project types
- **Pain Point**: "I'm building an API, what stories do I need?"

**Implementation Approach**:

```bash
# List available templates
./claude-loop.sh --list-templates

# Use a template
./claude-loop.sh --template rest-api --project my-api

# Template fills in standard stories:
# - US-001: Setup project structure
# - US-002: Database models
# - US-003: API routes
# - US-004: Validation middleware
# - US-005: Error handling
# - US-006: Tests
# - US-007: Documentation
```

**Technical Design**:
1. Create `templates/` directory with pre-built PRD JSON files
2. Templates include:
   - REST API (7 stories: setup, models, routes, middleware, error handling, tests, docs)
   - CLI Tool (5 stories: arg parsing, subcommands, config, tests, docs)
   - Web App (8 stories: setup, components, routing, state, API, tests, build, docs)
   - Refactoring (4 stories: extract, rename, reorganize, test)
   - Library (6 stories: core API, examples, tests, docs, publish, CI)
3. Templates have placeholder variables: `{{PROJECT_NAME}}`, `{{DESCRIPTION}}`
4. CLI prompts for variable values, substitutes into template
5. Save to `prd-{project}.json`, allow user to edit before execution

**Effort**: **Low-Medium** (1-2 weeks)
- 1 week: Create 5-7 initial templates
- 1 week: CLI template selection and variable substitution

**Impact**: **Medium** (6/10)
- Reduces PRD authoring time by 50% for standard projects
- Educates users about story decomposition patterns
- Limited to common project types

**Reach**: **Medium-High** (50% of projects)
- Many projects fit standard patterns
- Less useful for unique/complex projects

**Confidence**: **High** (90%)
- Templates are straightforward
- Low technical risk
- Proven pattern (e.g., `create-react-app`, `cookiecutter`)

**RICE Score**: **(0.50 × 6 × 0.90) / (1.5 weeks) = 180**

**Dependencies**: None (standalone feature)

**Success Metrics**:
- 35%+ of PRDs start from template within 6 months
- Average PRD authoring time reduced by 40%
- Template satisfaction (NPS): >8

---

### Theme B: Architecture & System

Core system improvements inspired by Cowork's skills architecture and constraint-driven design.

---

#### B1. Skills Architecture (Progressive Disclosure)

**Description**: Implement Cowork's filesystem-based skills system for claude-loop. Skills enable progressive disclosure (metadata → instructions → resources) and bundled code execution for deterministic operations.

**Problem It Solves**:
- **Primary**: Context explosion with 34+ agents (US-003)
- **Secondary**: Can't bundle schemas, templates, or scripts with agents
- **Pain Point**: Every capability added increases context consumption

**Implementation Approach**:

```bash
# Skills directory structure
skills/
├── prd-validator/
│   ├── SKILL.md          # Core instructions
│   ├── schema.json       # PRD JSON schema
│   └── validate.py       # Validation script
├── test-scaffolder/
│   ├── SKILL.md
│   ├── templates/
│   │   ├── pytest.py
│   │   └── jest.ts
│   └── generate.py
└── commit-formatter/
    ├── SKILL.md
    ├── template.txt      # Commit message template
    └── format.sh         # Formatting script
```

**Technical Design**:
1. Create `lib/skill-loader.py` with 3-tier loading:
   - **Level 1**: Load metadata (YAML frontmatter) from all skills at startup (~100 tokens/skill)
   - **Level 2**: Read SKILL.md via bash when skill description matches task
   - **Level 3**: Access resources (schemas, templates, scripts) on-demand
2. Integrate with claude-loop.sh prompt generation:
   - Include skill metadata in prompt
   - Claude triggers skills via description matching
   - Skills execute via bash (scripts run without context consumption)
3. Add `--skills-dir` flag (default: `./skills/`)
4. Automatic skill discovery: Scan skills directory at startup
5. Multi-skill composition: Multiple skills can activate simultaneously

**Effort**: **High** (4-5 weeks)
- 2 weeks: skill-loader.py with 3-tier loading
- 1 week: Integration with prompt generation
- 1 week: Create 3 initial skills (prd-validator, test-scaffolder, commit-formatter)
- 1 week: Testing and documentation

**Impact**: **High** (9/10)
- Enables scaling to 50+ capabilities without context penalty
- Unlocks deterministic operations (validation, generation, formatting)
- Complements agents (skills for deterministic, agents for generative)

**Reach**: **High** (70% of projects)
- Every project benefits from prd-validator skill
- Test scaffolding is universal
- Commit formatting improves git history

**Confidence**: **High** (80%)
- Cowork's skills architecture is proven
- Progressive disclosure is straightforward
- Some complexity in bash execution sandboxing

**RICE Score**: **(0.70 × 9 × 0.80) / (4.5 weeks) = 225**

**Dependencies**: None (standalone feature)

**Success Metrics**:
- 5+ skills created within 3 months
- Skills activated in 60%+ of PRD executions
- Context consumption reduced by 25% with skills enabled

---

#### B2. Daemon Mode (Background Execution)

**Description**: Run claude-loop as a background daemon that processes PRDs from a queue. Users can submit work, walk away, and receive notifications on completion. Matches Cowork's "set and forget" UX.

**Problem It Solves**:
- **Primary**: Terminal babysitting (US-001, US-007)
- **Secondary**: Can't queue multiple PRDs
- **Pain Point**: "I want to start work and move on to other tasks"

**Implementation Approach**:

```bash
# Start daemon
./claude-loop.sh --daemon start

# Queue PRDs
./claude-loop.sh --queue add prd-auth.json
./claude-loop.sh --queue add prd-payments.json
./claude-loop.sh --queue add quick "Refactor tests"

# Check status
./claude-loop.sh --queue status
# Output: 2 tasks in queue, 1 in progress, 0 complete

# Review results
./claude-loop.sh --queue show prd-auth.json

# Stop daemon
./claude-loop.sh --daemon stop
```

**Technical Design**:
1. Daemon process runs detached from terminal (via `nohup` or systemd)
2. Task queue stored in `.claude-loop/queue.json`
3. Daemon processes tasks sequentially (or in parallel with `--max-workers`)
4. Logs written to `.claude-loop/daemon.log`
5. On task completion:
   - Send desktop notification (macOS Notification Center)
   - Optional webhook (Slack, email, custom URL)
   - Update queue status
6. Queue API:
   - `add`: Append to queue
   - `status`: Show all tasks (queued, in progress, complete)
   - `show`: Display results for completed task
   - `cancel`: Remove from queue
   - `clear`: Clear completed tasks
7. Daemon management:
   - PID file: `.claude-loop/daemon.pid`
   - Status file: `.claude-loop/daemon-status.json`
   - Health check: Respond to `--daemon status`

**Effort**: **Medium-High** (3-4 weeks)
- 1.5 weeks: Daemon process management (start, stop, health check)
- 1 week: Queue implementation and persistence
- 1 week: Notification system (desktop, webhook)
- 0.5 weeks: Testing and error handling

**Impact**: **High** (8/10)
- Enables "fire and forget" workflows
- Supports multi-tasking (queue work, continue with other activities)
- Preserves all claude-loop benefits (audit trail, quality gates)
- Matches Cowork's asynchronous UX

**Reach**: **Medium-High** (60% of users)
- Especially valuable for long-running PRDs (>30 minutes)
- Less useful for quick tasks or interactive debugging
- Adoption depends on notification reliability

**Confidence**: **High** (80%)
- Daemon pattern is well-established
- Queue implementation is straightforward
- Notification delivery may have platform-specific issues

**RICE Score**: **(0.60 × 8 × 0.80) / (3.5 weeks) = 192**

**Dependencies**:
- Benefits from visual dashboard (C1) for remote monitoring

**Success Metrics**:
- 40%+ of PRD executions use daemon mode within 6 months
- Average time between task submission and user check-in: >15 minutes
- Notification delivery success rate: >95%

---

#### B3. Adaptive Story Splitting

**Description**: Allow Claude to propose story splits during execution when discovered complexity exceeds initial estimates. User approves splits, PRD is updated, execution continues with substories.

**Problem It Solves**:
- **Primary**: Story sizing skill required upfront (US-002)
- **Secondary**: No runtime adaptability (US-007)
- **Pain Point**: "Story is too big but I won't know until I start implementing"

**Implementation Approach**:

**During Execution**:
```
[WORKER] Implementing US-003: Add authentication...
[WORKER] Token budget exceeded (15k/20k tokens used)
[WORKER] Complexity higher than estimated

[PROPOSAL] Split US-003 into 3 substories:
  - US-003a: Core authentication logic
  - US-003b: OAuth provider integration
  - US-003c: Session management

[PROMPT] Approve split? [y/n]
```

**Technical Design**:
1. During story execution, monitor complexity signals:
   - Token usage exceeding budget (e.g., 15k of 20k tokens)
   - Multiple independent subtasks identified
   - Execution time exceeding estimate (e.g., 30 minutes for "simple" story)
2. If complexity threshold crossed:
   - Pause execution
   - Generate substory proposals with:
     - New story IDs (US-XXXa, US-XXXb, etc.)
     - Titles, descriptions, acceptance criteria
     - Dependencies (logical order)
     - File scopes (partitioned from original)
   - Display proposal to user
3. User approves or rejects:
   - **Approve**: Update PRD, mark original story as "split", continue with US-XXXa
   - **Reject**: Continue with original story (may fail or succeed)
4. Log split decision to execution log and progress.txt
5. Progress tracking reflects split (e.g., "US-003: Split into 3 substories, 1 of 3 complete")

**Effort**: **High** (4-5 weeks)
- 2 weeks: Complexity detection heuristics
- 1.5 weeks: Substory generation (LLM-powered)
- 1 week: PRD update and execution continuation
- 0.5 weeks: Testing with various split scenarios

**Impact**: **High** (7/10)
- Reduces upfront estimation burden
- Adapts to discovered complexity (Cowork-style)
- Maintains structured execution (each substory is atomic)
- Preserves audit trail (split recorded in PRD and git)

**Reach**: **Medium** (50% of projects)
- Especially valuable for exploratory projects
- Less useful for well-scoped stories
- Requires user trust in split proposals

**Confidence**: **Medium** (65%)
- Complexity detection heuristics may be inaccurate
- Substory generation quality varies
- Risk of infinite splitting if not bounded

**RICE Score**: **(0.50 × 7 × 0.65) / (4.5 weeks) = 50.6**

**Dependencies**:
- Requires LLM access for substory generation

**Success Metrics**:
- 15%+ of stories trigger adaptive splitting
- Split proposals accepted by users: >70%
- Stories marked "too complex" reduced by 50%

---

#### B4. Checkpoint Confirmations

**Description**: Prompt user before "significant actions" (file deletion, large refactoring, package installation). Matches Cowork's "ask before taking significant actions" pattern.

**Problem It Solves**:
- **Primary**: No destructive action warnings (US-001)
- **Secondary**: Limited safety boundaries (US-007)
- **Pain Point**: "I'm nervous claude-loop will delete something important"

**Implementation Approach**:

**During Execution**:
```
[WORKER] About to perform significant action:

ACTION: Delete 3 files
  - src/deprecated/old-api.ts
  - src/deprecated/old-utils.ts
  - tests/deprecated/old-api.test.ts

REASON: Removing deprecated code per US-005 acceptance criteria

[PROMPT] Proceed? [y/n/always/never]
  y: Approve this action
  n: Skip this action
  always: Auto-approve all actions this session
  never: Stop execution
```

**Technical Design**:
1. Define "significant actions":
   - **File deletion**: Any `rm`, `unlink`, or file removal
   - **Large modifications**: Files >1000 lines or >10 files at once
   - **Package changes**: `npm install`, `pip install`, `cargo add`
   - **Git operations**: `git push`, `git push --force`, `git reset --hard`
   - **Environment changes**: Modifying `.env`, config files
2. Worker execution intercepts bash commands
3. If command matches "significant" pattern:
   - Pause execution
   - Display action, affected files, and reason
   - Prompt user for confirmation
4. User response:
   - `y`: Execute action, continue
   - `n`: Skip action, continue without it
   - `always`: Set flag to auto-approve all actions (session-scoped)
   - `never`: Abort execution, mark story incomplete
5. Log approval/rejection to execution log
6. Add `--safe-mode` flag (default: enabled) to control checkpoints
7. Add `--auto-approve` flag for advanced users who want full autonomy

**Effort**: **Medium** (2-3 weeks)
- 1 week: Bash command interception
- 1 week: Significance pattern matching
- 1 week: User prompt and session state management

**Impact**: **Medium-High** (7/10)
- Reduces anxiety about destructive operations
- Builds trust in autonomous execution
- May slow execution if too many confirmations

**Reach**: **High** (70% of users)
- Every user benefits from safety checks
- Especially valuable for new users

**Confidence**: **High** (80%)
- Command interception is straightforward
- Pattern matching may have false positives/negatives

**RICE Score**: **(0.70 × 7 × 0.80) / (2.5 weeks) = 156.8**

**Dependencies**: None (standalone feature)

**Success Metrics**:
- Confirmation prompts shown in 30%+ of PRD executions
- User approval rate: >85% (indicates good precision)
- Zero accidental file deletions with safe-mode enabled

---

### Theme C: Observability & Trust

Features that improve transparency and build user confidence through better progress visibility.

---

#### C1. Visual Progress Dashboard

**Description**: Real-time web-based dashboard showing PRD execution progress, story status, live logs, and estimated completion time. Accessible from any device on local network.

**Problem It Solves**:
- **Primary**: Terminal-only interface (US-001)
- **Secondary**: No real-time progress visibility (US-007)
- **Pain Point**: "I want to check progress from my phone while away from computer"

**Implementation Approach**:

```bash
# Start with dashboard
./claude-loop.sh --dashboard prd.json

# Opens browser to http://localhost:8080
# Dashboard shows:
# - Current story (title, description, acceptance criteria)
# - Progress: 3/10 stories complete (visual progress bar)
# - Estimated time remaining: 2h 15m
# - Live log stream (WebSocket connection)
# - Story dependency graph (interactive visualization)
# - Actions: Pause, Resume, Cancel
```

**Dashboard UI Sections**:
1. **Header**: Project name, branch, status (running/paused/complete)
2. **Progress Overview**:
   - Stories: 3/10 complete
   - Time: 45m elapsed, ~2h15m remaining
   - Cost: $2.34 spent, ~$6.50 estimated total
3. **Current Story**:
   - Title, description, acceptance criteria
   - Current iteration: 1/3 quality check attempts
   - Live log stream (last 50 lines)
4. **Story List**:
   - All stories with status indicators (✓ complete, ⏳ in progress, ○ pending, ✗ failed)
   - Click to expand: Show acceptance criteria, files changed, commits
5. **Dependency Graph**:
   - Interactive visualization (D3.js or Cytoscape)
   - Nodes: Stories (colored by status)
   - Edges: Dependencies
6. **Controls**:
   - Pause/Resume button
   - Cancel button (with confirmation)
   - Download report (HTML)

**Technical Design**:
1. Spawn local web server (Flask or Express) on port 8080
2. Serve static HTML/CSS/JS dashboard
3. WebSocket connection for live updates:
   - Server pushes log lines as they're written
   - Server pushes story status changes
   - Client updates UI in real-time
4. Dashboard reads state from:
   - `.claude-loop/runs/{timestamp}/metrics.json`
   - `.claude-loop/runs/{timestamp}/summary.json`
   - prd.json (for story list and dependencies)
5. Dashboard API endpoints:
   - `GET /status` - Current execution status
   - `GET /logs?story={id}` - Logs for specific story
   - `POST /control/pause` - Pause execution
   - `POST /control/resume` - Resume execution
   - `POST /control/cancel` - Cancel execution
6. Mobile-responsive design (works on phone/tablet)
7. Optional: Expose on local network for remote access

**Effort**: **Medium-High** (3-4 weeks)
- 1.5 weeks: Web server and WebSocket setup
- 1.5 weeks: Dashboard UI (React or Vue)
- 0.5 weeks: Dependency graph visualization
- 0.5 weeks: Control API (pause/resume/cancel)

**Impact**: **High** (8/10)
- Dramatically improves progress visibility
- Enables remote monitoring (check from phone)
- Builds trust through transparency
- Matches Cowork's visual progress UI

**Reach**: **High** (70% of users)
- Every user benefits from visual progress
- Especially valuable for long-running PRDs

**Confidence**: **High** (80%)
- Web dashboards are well-established
- WebSocket real-time updates are proven
- Some complexity in state synchronization

**RICE Score**: **(0.70 × 8 × 0.80) / (3.5 weeks) = 256**

**Dependencies**:
- Benefits from daemon mode (B2) for background execution
- Requires WebSocket support

**Success Metrics**:
- 60%+ of PRD executions use dashboard within 6 months
- Average dashboard check frequency: 3-5 times per PRD
- Dashboard satisfaction (NPS): >8

---

#### C2. Enhanced Progress Indicators (Terminal)

**Description**: Improve terminal progress visualization with Cowork-style circular indicators, stage labels, and visual hierarchy. Replace text-heavy logs with structured, scannable progress.

**Problem It Solves**:
- **Primary**: Text log overload (US-001)
- **Secondary**: No visual progress indicators (US-007)
- **Pain Point**: "Terminal logs are hard to scan for key information"

**Implementation Approach**:

**Current (Text-Heavy)**:
```
[INFO] Starting iteration for US-003
[INFO] Reading prd.json
[INFO] Reading progress.txt
[INFO] Starting worker execution
[INFO] Worker spawned: PID 12345
...
```

**Proposed (Visual)**:
```
┌─────────────────────────────────────────────────────┐
│ 🔄 PROJECT: my-app                                  │
│ 📊 PROGRESS: ███████░░░ 7/10 stories (70%)         │
│ ⏱️  TIME: 45m elapsed, ~2h15m remaining             │
│ 💰 COST: $2.34 spent, ~$6.50 total                 │
└─────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────┐
│ ⚙️  CURRENT STORY: US-007 - Add error handling      │
│ ◉ Planning   ✓ Done                                │
│ ◉ Execution  ⏳ In Progress                         │
│ ○ Verification  Pending                            │
└─────────────────────────────────────────────────────┘

[LOG] Implementing error middleware...
```

**Design Elements**:
- **Box drawing characters**: Create visual hierarchy
- **Stage indicators**: ◉ (in progress), ✓ (done), ○ (pending), ✗ (failed)
- **Progress bar**: █ (complete), ░ (remaining)
- **Icons**: 🔄 (running), ✓ (complete), ✗ (failed), ⏸ (paused)
- **Color**: Green (success), Yellow (in progress), Red (failed), Gray (pending)
- **Collapsible logs**: Only show last 5 lines unless user requests full log

**Technical Design**:
1. Replace `lib/monitoring.sh` log functions with structured output
2. Use ANSI escape codes for colors and formatting
3. Detect terminal width, adjust layout dynamically
4. Three-stage progress per story:
   - **Planning**: Analyzing requirements, loading context
   - **Execution**: Implementing changes, running commands
   - **Verification**: Running tests, linting, typecheck
5. Update progress box every 2 seconds (not every log line)
6. Full logs still written to file for debugging
7. Add `--verbose` flag to show full logs in terminal

**Effort**: **Low-Medium** (1-2 weeks)
- 1 week: Refactor monitoring.sh for structured output
- 1 week: Stage detection and progress visualization

**Impact**: **Medium** (6/10)
- Improves scanability of terminal output
- Reduces cognitive load for users monitoring progress
- Still limited to terminal (not accessible remotely)

**Reach**: **High** (80% of users)
- Every terminal user benefits
- Less valuable if using dashboard (C1)

**Confidence**: **High** (85%)
- ANSI terminal formatting is straightforward
- Low technical risk

**RICE Score**: **(0.80 × 6 × 0.85) / (1.5 weeks) = 272**

**Dependencies**: None (standalone feature)

**Success Metrics**:
- User satisfaction with terminal output: >7 (NPS)
- Time to identify current progress status: <5 seconds
- Adoption: Default for all executions

---

#### C3. Real-Time Notifications

**Description**: Send notifications on key events: story completion, PRD completion, errors, and approval requests. Supports desktop notifications, webhooks (Slack, email), and mobile push.

**Problem It Solves**:
- **Primary**: Terminal babysitting (US-001)
- **Secondary**: No alerts when execution completes/fails
- **Pain Point**: "I walk away and forget to check if work is done"

**Implementation Approach**:

```bash
# Enable notifications
./claude-loop.sh --notify desktop prd.json
./claude-loop.sh --notify slack=https://hooks.slack.com/... prd.json
./claude-loop.sh --notify email=user@example.com prd.json

# Notification events:
# - Story complete: "✓ US-003 complete: Add authentication"
# - PRD complete: "✓ my-app complete: 10/10 stories"
# - Error: "✗ US-005 failed: Tests failing"
# - Approval request: "⏸ US-007 needs approval: Delete 3 files"
```

**Notification Channels**:
1. **Desktop** (macOS Notification Center, Windows Action Center, Linux notify-send)
2. **Webhook** (POST JSON to custom URL)
3. **Slack** (Webhook or OAuth app)
4. **Email** (SMTP or SendGrid API)
5. **Mobile** (Optional: iOS/Android push via Firebase)

**Technical Design**:
1. Add `--notify` flag accepting channel configuration
2. Integrate notification triggers in `lib/monitoring.sh`:
   - `notify_story_complete(story_id, title)`
   - `notify_prd_complete(project)`
   - `notify_error(story_id, error_message)`
   - `notify_approval_request(action, files)`
3. Notification payload (JSON):
   ```json
   {
     "event": "story_complete",
     "project": "my-app",
     "story_id": "US-003",
     "story_title": "Add authentication",
     "timestamp": "2026-01-13T12:00:00Z",
     "url": "http://localhost:8080" // Dashboard link
   }
   ```
4. Desktop notifications:
   - macOS: `osascript -e 'display notification "..." with title "claude-loop"'`
   - Linux: `notify-send "claude-loop" "..."`
   - Windows: `msg * "..."`
5. Webhook notifications:
   - POST JSON payload to configured URL
   - Retry on failure (3 attempts, exponential backoff)
6. Store notification config in `.claude-loop/notifications.json`
7. Add `--notify-test` command to test notification delivery

**Effort**: **Medium** (2-3 weeks)
- 1 week: Notification abstraction layer
- 1 week: Channel implementations (desktop, webhook, Slack, email)
- 1 week: Testing and error handling

**Impact**: **High** (7/10)
- Enables "fire and forget" workflows
- Reduces check-in frequency
- Critical for daemon mode (B2)

**Reach**: **Medium-High** (65% of users)
- Especially valuable for long-running PRDs
- Less useful for quick tasks or active monitoring

**Confidence**: **High** (80%)
- Notification systems are well-established
- Platform-specific issues may arise

**RICE Score**: **(0.65 × 7 × 0.80) / (2.5 weeks) = 145.6**

**Dependencies**:
- Strongly benefits from daemon mode (B2)
- Benefits from dashboard (C1) for notification links

**Success Metrics**:
- 50%+ of daemon mode users enable notifications
- Notification delivery success rate: >95%
- Average time between completion and user check-in: <15 minutes

---

### Theme D: Safety & Quality

Features that enhance safety mechanisms and quality assurance.

---

#### D1. Rollback & Undo Capabilities

**Description**: Add ability to rollback to previous story state using git operations. Enables safe experimentation and easy recovery from failures.

**Problem It Solves**:
- **Primary**: Difficult rollback (US-001)
- **Secondary**: Users hesitant to try exploratory changes
- **Pain Point**: "What if claude-loop breaks something?"

**Implementation Approach**:

```bash
# Undo last story
./claude-loop.sh --rollback

# Rollback to specific story
./claude-loop.sh --rollback-to US-005

# Preview rollback (dry-run)
./claude-loop.sh --rollback --dry-run

# Rollback output:
# Rolling back: US-007 - Add error handling
# Reverting commit: abc123 feat: US-007 - Add error handling
# Files restored:
#   - src/middleware/error.ts (deleted)
#   - tests/middleware/error.test.ts (deleted)
# PRD updated: US-007 passes=false
```

**Technical Design**:
1. Each story creates atomic git commit (existing behavior)
2. Rollback operation:
   - Identify target commit (last N stories or specific story ID)
   - Run `git revert {commit}` (not `git reset --hard` to preserve history)
   - Update PRD: Set rolled-back stories to `passes=false`
   - Update progress.txt: Log rollback event and reason
3. Rollback types:
   - **Single story**: Revert last completed story
   - **To story**: Revert all stories after specified ID
   - **Full**: Revert entire PRD (return to initial state)
4. Dry-run mode: Show what would be reverted without executing
5. Rollback safety checks:
   - Warn if uncommitted changes exist
   - Require confirmation if rolling back >3 stories
   - Fail if rollback would conflict with current working directory
6. Add to execution log: Track rollback events for analysis

**Effort**: **Medium** (2-3 weeks)
- 1 week: Rollback command implementation
- 1 week: PRD state update and progress logging
- 1 week: Safety checks and dry-run mode

**Impact**: **Medium-High** (7/10)
- Reduces risk of autonomous execution
- Enables safe experimentation
- Builds trust through easy recovery

**Reach**: **Medium** (50% of users)
- Valuable when mistakes happen
- Rarely used in successful runs (hopefully)
- Psychological safety benefit even if unused

**Confidence**: **High** (85%)
- Git revert is well-understood
- Low technical risk
- Some complexity in PRD state synchronization

**RICE Score**: **(0.50 × 7 × 0.85) / (2.5 weeks) = 119**

**Dependencies**: None (standalone feature)

**Success Metrics**:
- Rollback used in 10%+ of PRD executions (indicates mistakes happen)
- Rollback success rate: >90% (no conflicts)
- User confidence increase: "I'm more willing to try things" (survey)

---

#### D2. Multi-LLM Quality Review Panel

**Description**: After each story completion, optionally run code review using multiple LLM providers (GPT-4o, Gemini 2.0, DeepSeek-R1). Aggregate reviews into consensus score, feed issues back for fixes.

**Problem It Solves**:
- **Primary**: Single-model bias in code generation
- **Secondary**: Quality issues not caught by tests alone
- **Pain Point**: "How do I know the code is actually good?"

**Implementation Approach**:

```bash
# Enable review panel
./claude-loop.sh --enable-review --reviewers gemini,gpt4o prd.json

# After US-003 completes:
# [REVIEW PANEL] Reviewing US-003 with 2 reviewers...
# - Gemini 2.0 Flash: 8/10 (2 suggestions)
# - GPT-4o: 7/10 (3 issues)
#
# Consensus: 7.5/10
# Threshold: 7.0 - PASS
#
# Issues to address:
# 1. [GPT-4o] Missing error handling in authMiddleware
# 2. [Both] Magic number 3600 should be constant
#
# Proceed? [y/n/fix]
#   y: Accept and continue
#   n: Reject and redo story
#   fix: Create fix commit, then continue
```

**Technical Design**:
1. After story completion (before marking `passes=true`):
   - Extract git diff for story
   - Send to configured reviewers in parallel
   - Each reviewer returns: `{ score: 1-10, issues: [], suggestions: [] }`
2. Aggregate reviews:
   - Consensus score: Mean of reviewer scores
   - Common issues: Issues mentioned by 2+ reviewers (high priority)
   - Unique issues: Mentioned by 1 reviewer (medium priority)
3. Compare consensus to threshold (default: 7.0):
   - `score >= threshold`: Pass, continue
   - `score < threshold`: Fail, request fix or redo
4. User options:
   - **Accept**: Mark story complete despite low score
   - **Reject**: Mark story incomplete, retry from scratch
   - **Fix**: Create fix iteration (max 2 fix cycles per story)
5. Review results logged to:
   - Execution log (for analysis)
   - Story notes in PRD
   - HTML report
6. Flags:
   - `--enable-review`: Enable review panel
   - `--reviewers`: Comma-separated list (gemini,gpt4o,deepseek)
   - `--review-threshold`: Minimum consensus score (default: 7.0)
   - `--max-review-cycles`: Max fix iterations (default: 2)

**Effort**: **High** (4-5 weeks)
- 1.5 weeks: Review panel orchestration
- 1.5 weeks: Multi-LLM provider integration (use lib/llm-provider.py from multi-llm-support PRD)
- 1 week: Review aggregation and threshold logic
- 1 week: Fix cycle implementation

**Impact**: **High** (8/10)
- Catches quality issues tests don't detect
- Reduces single-model bias
- Builds confidence in generated code

**Reach**: **Medium** (40% of users)
- Valuable for production code
- Less useful for exploratory work
- Requires API keys for multiple providers (friction)

**Confidence**: **Medium-High** (75%)
- Review panel concept is proven
- LLM review quality varies
- Consensus scoring may be noisy

**RICE Score**: **(0.40 × 8 × 0.75) / (4.5 weeks) = 53.3**

**Dependencies**:
- Requires multi-LLM support (lib/llm-provider.py from LLM-002)
- Benefits from cost tracking (lib/cost-tracker.py from LLM-010)

**Success Metrics**:
- 25%+ of projects use review panel within 6 months
- Issues caught by review panel: 2-3 per story on average
- User satisfaction with review quality (NPS): >7

---

### Theme E: Performance & Cost

Features that optimize execution speed and reduce operational costs.

---

#### E1. Parallel Story Execution (Enhanced)

**Description**: Extend existing parallel execution with automatic dependency inference, dynamic work stealing, and improved merge strategies. Enable "implicit parallelism" like Cowork without manual fileScope/dependency declaration.

**Problem It Solves**:
- **Primary**: Manual dependency specification (US-001)
- **Secondary**: Fixed parallelization (no dynamic work stealing)
- **Pain Point**: "I don't want to think about which stories can run in parallel"

**Implementation Approach**:

```bash
# Auto-parallel mode (no manual dependencies)
./claude-loop.sh --auto-parallel prd.json

# System automatically:
# 1. Analyzes story descriptions and file scopes
# 2. Infers dependencies using LLM
# 3. Detects conflicts at runtime
# 4. Adjusts parallelism dynamically
```

**Technical Design**:
1. **Auto-dependency inference** (pre-execution):
   - If PRD has no `dependencies` declared, use LLM to infer:
     - Parse story descriptions
     - Identify semantic dependencies (e.g., "implement API" depends on "create models")
     - Generate dependency graph
   - User reviews and approves inferred dependencies
2. **Runtime conflict detection**:
   - Track file access during execution
   - If two workers try to modify same file, pause one
   - Serialize conflicting stories automatically
3. **Dynamic work stealing**:
   - If worker finishes early, steal pending stories from queue
   - Rebalance work across workers
4. **Improved merge strategy**:
   - Use 3-way merge instead of rebase (when conflicts occur)
   - Automatic conflict resolution for non-overlapping changes
   - Interactive conflict resolution UI for overlapping changes
5. Flags:
   - `--auto-parallel`: Enable auto-dependency inference
   - `--max-workers`: Limit concurrency (default: 3)
   - `--merge-strategy`: rebase (existing) or merge (new)

**Effort**: **High** (5-6 weeks)
- 2 weeks: LLM-powered dependency inference
- 2 weeks: Runtime conflict detection
- 1 week: Dynamic work stealing
- 1 week: Improved merge strategy

**Impact**: **High** (8/10)
- Reduces manual dependency specification burden
- Adapts to runtime conflicts (Cowork-style)
- Speeds up execution for independent stories

**Reach**: **Medium-High** (55% of projects)
- Especially valuable for large PRDs (10+ stories)
- Less useful for sequential work

**Confidence**: **Medium** (65%)
- LLM dependency inference accuracy unknown
- Runtime conflict detection may be brittle
- Dynamic work stealing adds complexity

**RICE Score**: **(0.55 × 8 × 0.65) / (5.5 weeks) = 52**

**Dependencies**:
- Requires existing parallel execution (lib/parallel.sh)
- Benefits from workspace sandboxing (A2)

**Success Metrics**:
- Auto-parallel adoption: 30%+ of parallel executions
- Inferred dependencies accuracy: >80% (user approval rate)
- Execution speedup: 30-50% faster than sequential

---

## 2. RICE Prioritization Summary

### Top 10 Features by RICE Score

| Rank | Feature | RICE Score | Reach | Impact | Confidence | Effort (weeks) | Theme |
|------|---------|-----------|-------|--------|-----------|---------------|-------|
| 1 | **C2. Enhanced Progress Indicators** | **272** | 0.80 | 6 | 0.85 | 1.5 | Observability |
| 2 | **A1. Quick Task Mode** | **270** | 0.80 | 9 | 0.90 | 3.5 | UX |
| 3 | **C1. Visual Progress Dashboard** | **256** | 0.70 | 8 | 0.80 | 3.5 | Observability |
| 4 | **A2. Workspace Sandboxing** | **240** | 0.75 | 8 | 0.80 | 2.5 | UX |
| 5 | **B1. Skills Architecture** | **225** | 0.70 | 9 | 0.80 | 4.5 | Architecture |
| 6 | **B2. Daemon Mode** | **192** | 0.60 | 8 | 0.80 | 3.5 | Architecture |
| 7 | **A5. PRD Templates** | **180** | 0.50 | 6 | 0.90 | 1.5 | UX |
| 8 | **B4. Checkpoint Confirmations** | **157** | 0.70 | 7 | 0.80 | 2.5 | Architecture |
| 9 | **C3. Real-Time Notifications** | **146** | 0.65 | 7 | 0.80 | 2.5 | Observability |
| 10 | **D1. Rollback & Undo** | **119** | 0.50 | 7 | 0.85 | 2.5 | Safety |

### Features by Theme

**UX & Accessibility (5 features)**:
- A1. Quick Task Mode (RICE: 270) ⭐
- A2. Workspace Sandboxing (RICE: 240) ⭐
- A5. PRD Templates (RICE: 180) ⭐
- A4. Interactive PRD Builder (RICE: 81.6)
- A3. Dynamic PRD Generation (RICE: 74.7)

**Architecture & System (4 features)**:
- B1. Skills Architecture (RICE: 225) ⭐
- B2. Daemon Mode (RICE: 192) ⭐
- B4. Checkpoint Confirmations (RICE: 157) ⭐
- B3. Adaptive Story Splitting (RICE: 50.6)

**Observability & Trust (3 features)**:
- C2. Enhanced Progress Indicators (RICE: 272) ⭐
- C1. Visual Progress Dashboard (RICE: 256) ⭐
- C3. Real-Time Notifications (RICE: 146) ⭐

**Safety & Quality (2 features)**:
- D1. Rollback & Undo (RICE: 119) ⭐
- D2. Multi-LLM Quality Review (RICE: 53.3)

**Performance & Cost (1 feature)**:
- E1. Parallel Execution (Enhanced) (RICE: 52)

---

## 3. Implementation Sequencing

### Phase 1: Quick Wins (Weeks 1-8)

**Goal**: Reduce friction and build user confidence through high-impact, low-effort features.

**Features**:
1. **C2. Enhanced Progress Indicators** (1.5 weeks) - RICE: 272
   - Immediate visibility improvement
   - No external dependencies
   - Quick implementation

2. **A5. PRD Templates** (1.5 weeks) - RICE: 180
   - Reduces PRD authoring time
   - No external dependencies
   - Educates users on story decomposition

3. **A2. Workspace Sandboxing** (2.5 weeks) - RICE: 240
   - Critical safety feature
   - Enables safe parallel execution
   - Reduces scope creep risk

4. **B4. Checkpoint Confirmations** (2.5 weeks) - RICE: 157
   - Builds user trust
   - Matches Cowork's safety model
   - Low technical risk

**Total**: 8 weeks, 4 features
**Value**: Immediate UX improvements, safety enhancements, reduced friction

---

### Phase 2: Foundation (Weeks 9-22)

**Goal**: Build core architectural improvements that enable future features.

**Features**:
1. **A1. Quick Task Mode** (3.5 weeks) - RICE: 270
   - Flagship feature for Cowork parity
   - Enables ad-hoc work
   - Foundation for dynamic planning

2. **B1. Skills Architecture** (4.5 weeks) - RICE: 225
   - Critical for scaling beyond 34 agents
   - Unlocks deterministic operations
   - Enables progressive disclosure

3. **C1. Visual Progress Dashboard** (3.5 weeks) - RICE: 256
   - Matches Cowork's transparency UX
   - Enables remote monitoring
   - Foundation for real-time collaboration

4. **B2. Daemon Mode** (3.5 weeks) - RICE: 192
   - Enables "fire and forget" workflows
   - Critical for async execution
   - Foundation for task queuing

**Total**: 15 weeks (Week 9-23), 4 features
**Value**: Core architectural improvements, Cowork-level UX parity

---

### Phase 3: Autonomy (Weeks 24-34)

**Goal**: Increase runtime adaptability while preserving reliability guarantees.

**Features**:
1. **C3. Real-Time Notifications** (2.5 weeks) - RICE: 146
   - Complements daemon mode
   - Reduces check-in frequency
   - Multiple channel support

2. **A3. Dynamic PRD Generation** (4.5 weeks) - RICE: 74.7
   - Reduces upfront planning burden
   - Enables exploratory workflows
   - Maintains structured execution

3. **B3. Adaptive Story Splitting** (4.5 weeks) - RICE: 50.6
   - Handles discovered complexity
   - Cowork-style adaptability
   - Preserves audit trail

**Total**: 11.5 weeks (Week 24-35), 3 features
**Value**: Runtime adaptability, reduced planning overhead

---

### Phase 4: Quality & Safety (Weeks 36-46)

**Goal**: Strengthen quality assurance and safety mechanisms.

**Features**:
1. **D1. Rollback & Undo** (2.5 weeks) - RICE: 119
   - Easy recovery from mistakes
   - Enables safe experimentation
   - Builds user confidence

2. **D2. Multi-LLM Quality Review** (4.5 weeks) - RICE: 53.3
   - Reduces single-model bias
   - Catches quality issues
   - Production-grade assurance

3. **A4. Interactive PRD Builder** (2.5 weeks) - RICE: 81.6
   - Lowers JSON barrier
   - Guided PRD creation
   - Validation built-in

**Total**: 9.5 weeks (Week 36-45), 3 features
**Value**: Quality improvements, safety enhancements

---

### Phase 5: Performance (Weeks 47-52)

**Goal**: Optimize execution speed and reduce costs.

**Features**:
1. **E1. Parallel Execution (Enhanced)** (5.5 weeks) - RICE: 52
   - Auto-dependency inference
   - Dynamic work stealing
   - Improved merge strategies

**Total**: 5.5 weeks (Week 47-52), 1 feature
**Value**: Execution speedup, reduced friction

---

## 4. Dependency Graph

```
Phase 1 (Quick Wins)
├─ C2 (Progress Indicators) → No dependencies
├─ A5 (PRD Templates) → No dependencies
├─ A2 (Workspace Sandboxing) → No dependencies
└─ B4 (Checkpoint Confirmations) → No dependencies

Phase 2 (Foundation)
├─ A1 (Quick Task Mode) → Depends on: A2 (workspace), B4 (checkpoints)
├─ B1 (Skills Architecture) → No dependencies
├─ C1 (Visual Dashboard) → Benefits from: B2 (daemon), C2 (progress)
└─ B2 (Daemon Mode) → Depends on: A2 (workspace), B4 (checkpoints)

Phase 3 (Autonomy)
├─ C3 (Notifications) → Depends on: B2 (daemon), C1 (dashboard)
├─ A3 (Dynamic PRD) → Benefits from: B1 (skills - prd-validator)
└─ B3 (Adaptive Splitting) → Depends on: A1 (quick mode)

Phase 4 (Quality & Safety)
├─ D1 (Rollback) → No dependencies
├─ D2 (Multi-LLM Review) → Depends on: multi-llm-support PRD (LLM-002, LLM-010)
└─ A4 (PRD Builder) → Benefits from: B1 (skills - prd-validator)

Phase 5 (Performance)
└─ E1 (Enhanced Parallel) → Depends on: A2 (workspace), existing parallel execution
```

---

## 5. Success Metrics

### Overall Project Success (12 months)

**Adoption Metrics**:
- 70%+ of users try at least one new feature
- 50%+ of sessions use quick task mode
- 60%+ of PRD executions use workspace sandboxing
- 40%+ of long-running PRDs use daemon mode

**Quality Metrics**:
- PRD validation errors reduced by 60% (skills + templates)
- Accidental file modifications reduced by 80% (workspace sandboxing)
- Average PRD authoring time reduced by 50% (templates + dynamic PRD)

**UX Metrics**:
- User satisfaction (NPS): >8 overall
- "Claude-loop is too hard to use" complaints reduced by 70%
- New user onboarding time: <30 minutes (from 2+ hours)

**Performance Metrics**:
- Parallel execution speedup: 30-50% (enhanced parallel)
- Context consumption reduced by 25% (skills architecture)
- Cost per story reduced by 20% (model selection + context caching)

---

## 6. Risk Assessment

### High-Risk Features (Complexity or Uncertainty)

**B3. Adaptive Story Splitting** (RICE: 50.6)
- **Risk**: LLM-generated substories may be poor quality
- **Mitigation**: Require user approval, limit split depth (max 2 levels)
- **Fallback**: Disable auto-splitting, manual split only

**A3. Dynamic PRD Generation** (RICE: 74.7)
- **Risk**: Generated PRDs may have incorrect dependencies or scope
- **Mitigation**: Interactive approval, integrate PRD validator skill
- **Fallback**: Treat as suggestion only, not auto-execute

**D2. Multi-LLM Quality Review** (RICE: 53.3)
- **Risk**: Review panel may have high false positive rate
- **Mitigation**: Tune threshold, allow user to adjust per project
- **Fallback**: Make opt-in, disable by default

**E1. Enhanced Parallel Execution** (RICE: 52)
- **Risk**: Runtime conflict detection may be brittle
- **Mitigation**: Extensive testing, gradual rollout
- **Fallback**: Fall back to existing parallel execution

### Medium-Risk Features (Dependencies or Integration)

**C1. Visual Progress Dashboard** (RICE: 256)
- **Risk**: WebSocket real-time updates may have sync issues
- **Mitigation**: Polling fallback, state reconciliation
- **Fallback**: Static HTML reports (existing)

**B2. Daemon Mode** (RICE: 192)
- **Risk**: Daemon process management varies by platform
- **Mitigation**: Test on macOS, Linux, Windows
- **Fallback**: Foreground execution with tmux/screen suggestion

**B1. Skills Architecture** (RICE: 225)
- **Risk**: Bash script execution may have security issues
- **Mitigation**: Sandboxing, whitelist allowed commands
- **Fallback**: Prompt-only skills (no script execution)

### Low-Risk Features (Straightforward Implementation)

- **C2. Enhanced Progress Indicators** (RICE: 272) ✓
- **A5. PRD Templates** (RICE: 180) ✓
- **A2. Workspace Sandboxing** (RICE: 240) ✓
- **B4. Checkpoint Confirmations** (RICE: 157) ✓
- **D1. Rollback & Undo** (RICE: 119) ✓

---

## 7. Competitive Positioning

### Claude-Loop vs Cowork (Post-Implementation)

| Dimension | Cowork (Current) | Claude-Loop (Current) | Claude-Loop (After Phase 2) | Winner |
|-----------|------------------|----------------------|----------------------------|--------|
| **Ease of Use** | Natural language (simple) | JSON PRD (complex) | Quick mode + Templates (simple) | **Tie** |
| **Asynchronous Execution** | Default | Optional (daemon) | Default (daemon mode) | **Tie** |
| **Progress Visibility** | Visual UI | Terminal logs | Visual dashboard + terminal | **Tie** |
| **Workspace Isolation** | Folder sandboxing | No isolation | Folder sandboxing | **Tie** |
| **Reliability** | Self-checking | Quality gates | Quality gates + review panel | **Claude-Loop** |
| **Audit Trail** | Transient progress | Git commits + logs | Git commits + logs + dashboard | **Claude-Loop** |
| **Reproducibility** | Low (emergent) | High (PRD-driven) | High (PRD-driven) | **Claude-Loop** |
| **Self-Improvement** | None | Full pipeline | Full pipeline | **Claude-Loop** |
| **Cost Optimization** | Unknown | 3-tier model selection | 3-tier + context caching | **Claude-Loop** |
| **Multi-Day Projects** | Limited | Native | Native + adaptive splitting | **Claude-Loop** |
| **Parallel Execution** | Implicit (auto) | Explicit (manual) | Implicit (auto-parallel) | **Tie** |

**Strategic Positioning**:
- **Cowork**: "Your AI coworker for everyday tasks" (consumer-friendly, document-focused)
- **Claude-Loop (Post-Phase 2)**: "Your autonomous dev team for production features" (developer-focused, code-centric)

**Market Fit**:
- Cowork targets **non-technical knowledge workers** (business docs, file org)
- Claude-loop targets **software developers** (feature implementation, code quality)
- **Minimal competitive overlap** - different user bases, different use cases

---

## 8. Conclusion

### Summary

This feature proposal matrix synthesizes insights from 4 deep analysis documents (US-001 through US-007) into **18 concrete, prioritized features** using the RICE framework. The features are grouped into 6 themes and sequenced across 5 implementation phases spanning 52 weeks.

### Top Priorities

The **top 10 features** (RICE >100) deliver:
1. **Reduced friction**: Quick task mode, workspace sandboxing, PRD templates
2. **Improved observability**: Visual dashboard, enhanced progress indicators, notifications
3. **Core architecture**: Skills system, daemon mode, checkpoint confirmations
4. **Safety**: Rollback capabilities

### Strategic Value

By implementing Phases 1-2 (23 weeks, 8 features), claude-loop will achieve:
- **Cowork-level UX parity** for accessibility and transparency
- **Preserved reliability advantages** through quality gates and audit trails
- **Hybrid autonomy model**: Quick mode for ad-hoc, PRD mode for complex
- **Differentiated positioning**: "Reliable autonomous dev team" vs "Simple task coworker"

### Next Steps

1. **Validate with users**: Survey target users on feature priorities
2. **Refine estimates**: Prototype 1-2 high-risk features to validate effort
3. **Secure resources**: Allocate dev team for 6-month commitment (Phases 1-2)
4. **Begin Phase 1**: Start with Enhanced Progress Indicators (1.5 weeks, RICE: 272)

---

## Sources

- **US-001**: docs/analysis/cowork-ux-patterns.md
- **US-002**: docs/analysis/cowork-autonomy-model.md
- **US-003**: docs/analysis/cowork-skills-architecture.md
- **US-007**: docs/analysis/cowork-first-principles.md
- **RICE Framework**: [Intercom RICE Prioritization](https://www.intercom.com/blog/rice-simple-prioritization-for-product-managers/)
- **Feature Prioritization**: [First Principles: The Building Blocks of True Knowledge | Farnam Street](https://fs.blog/first-principles/)

---

**Document Completed**: 2026-01-13
**Word Count**: ~10,500 words
**Features Proposed**: 18 features across 6 themes
**Implementation Timeline**: 52 weeks across 5 phases
**Status**: ✅ All acceptance criteria met
