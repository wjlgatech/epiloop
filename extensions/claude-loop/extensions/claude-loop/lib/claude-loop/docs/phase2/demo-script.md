# Phase 2 Demo Video Script

## Overview
Duration: 10-12 minutes
Target: Developers familiar with AI coding tools
Goal: Showcase Phase 2 capabilities and demonstrate the Cowork-level UX

---

## Act 1: Introduction (1 min)

**[Screen: Terminal with claude-loop logo]**

**Narrator:**
> "Meet claude-loop v2.0 - the autonomous coding agent that just got five game-changing upgrades. In this demo, we'll show you how Phase 2 transforms the developer experience from 'write a PRD, wait, review' to 'describe what you want, go to lunch, come back to a PR.'"

**[Show quick montage of:]**
- Skills executing instantly
- Quick task mode accepting natural language
- Daemon processing queue in background
- Dashboard showing real-time progress
- Slack notification of completion

---

## Act 2: Skills Architecture (2 min)

**[Screen: Terminal]**

**Narrator:**
> "First, let's talk about skills. Skills are deterministic operations that don't need LLM calls - validation, formatting, generation. Progressive disclosure means we only load what we need, when we need it."

**Commands:**
```bash
# List available skills
./claude-loop.sh --list-skills
```

**[Screen shows:]**
```
Available Skills:

  prd-validator - Validates PRD structure and dependencies
  test-scaffolder - Generates test file scaffolding
  commit-formatter - Enforces Conventional Commits standard
  api-spec-generator - Generates OpenAPI specifications
  cost-optimizer - Analyzes complexity and recommends models
  hello-world - Example skill demonstrating the framework
```

**Narrator:**
> "Let's validate a PRD. No LLM call needed - instant feedback."

**Commands:**
```bash
# Validate PRD
./claude-loop.sh --skill prd-validator --skill-arg prd.json
```

**[Screen shows validation output:]**
```
✓ PRD structure valid
✓ All story IDs unique
✓ No circular dependencies
✓ All dependencies exist
⚠ Story TEST-003 has high complexity (8 acceptance criteria)
```

**Narrator:**
> "Instant. Zero cost. And it integrates seamlessly with the rest of the system."

---

## Act 3: Quick Task Mode (3 min)

**[Screen: Terminal]**

**Narrator:**
> "Now the real magic: Quick Task Mode. Describe what you want in natural language, get a plan, approve it, and Claude executes it. No PRD authoring required."

**Commands:**
```bash
# Simple task
./claude-loop.sh quick "add tests to the authentication module"
```

**[Screen shows plan:]**
```
========================================
  QUICK TASK EXECUTION PLAN
========================================

Task: add tests to the authentication module

Planned Steps:
  1. [read] Analyze task requirements
  2. [read] Identify files to modify
  3. [write] Implement changes
  4. [verify] Verify changes work
  5. [bash] Run tests if applicable

Estimated Complexity: simple
Estimated Cost: $0.15
Suggested Skills: test-scaffolder

Approve this plan? (y/n):
```

**Narrator:**
> "Notice the complexity detection, cost estimate, and suggested skills. Let's approve it."

**[Type 'y']**

**[Screen shows execution:]**
```
Executing step 1/5: Analyze task requirements...
Executing step 2/5: Identify files to modify...
Using skill: test-scaffolder for src/auth.py...
Executing step 3/5: Implement changes...
Executing step 4/5: Verify changes work...
Executing step 5/5: Run tests if applicable...

✓ Task complete! (2m 15s, $0.14)

Created commit: test: add tests for authentication module

Files changed:
  - tests/test_auth.py (new)
  - src/auth.py (modified)
```

**Narrator:**
> "Two minutes, auto-committed, tests passing. That's the power of quick mode. But what about complex tasks?"

**Commands:**
```bash
# Complex task with escalation
./claude-loop.sh quick "implement OAuth 2.0 authentication with Google and GitHub providers" --escalate
```

**[Screen shows:]**
```
Complexity Analysis:
  - Word count: 25 (high)
  - Multiple components: OAuth + Google + GitHub (15 points)
  - Architecture keywords: authentication (10 points)
  - Total complexity: 75/100 (complex)

⚠ This task is too complex for quick mode (threshold: 60)

Recommendation: Create a full PRD for better results.
Would you like to:
  1. Continue anyway (not recommended)
  2. Create PRD (recommended)
  3. Cancel
```

**Narrator:**
> "Automatic complexity detection saves you from starting tasks that should be PRDs. Let's see the daemon mode instead."

---

## Act 4: Daemon Mode (2 min)

**[Screen: Terminal]**

**Narrator:**
> "Daemon mode is for fire-and-forget workflows. Submit your PRD, go to lunch, get notified when it's done."

**Commands:**
```bash
# Start daemon
./claude-loop.sh daemon start
```

**[Screen shows:]**
```
Starting claude-loop daemon...
✓ Daemon started (PID: 12345)
✓ Log file: .claude-loop/daemon/daemon.log
```

**Commands:**
```bash
# Submit a PRD
./claude-loop.sh daemon submit feature-prd.json --priority high --notify slack
```

**[Screen shows:]**
```
Task submitted successfully
  ID: task-1705147200
  Priority: high
  Notifications: slack
  Position in queue: 1
```

**Commands:**
```bash
# Check queue
./claude-loop.sh daemon queue
```

**[Screen shows:]**
```
Daemon Queue (1 task)

  task-1705147200 [running] feature-prd.json (high)
    Started: 2026-01-13 12:00:00
    Progress: 3/8 stories complete
```

**Narrator:**
> "The daemon is working in the background. Time to check the dashboard."

---

## Act 5: Visual Progress Dashboard (2 min)

**[Screen: Terminal]**

**Commands:**
```bash
# Start dashboard
./claude-loop.sh dashboard start
```

**[Browser opens to http://localhost:8080]**

**[Dashboard shows:]**
- Live execution view: "Running US-204 (3/8 complete)"
- Progress bar: 38%
- Story status grid with 3 green (completed), 1 yellow (in progress), 4 gray (pending)
- Real-time logs streaming
- Cost tracker: $2.45 / $5.00 budget (49%)

**Narrator:**
> "Real-time updates via Server-Sent Events. Watch the logs stream, see stories turn green, track your cost. This is what Cowork-level UX looks like."

**[Navigate to History tab]**

**[Shows historical runs:]**
```
Recent Runs:
  Jan 13, 12:00 - feature-prd.json (in progress)
  Jan 12, 18:30 - bugfix-prd.json (complete, 8/8 stories)
  Jan 12, 14:00 - refactor-prd.json (complete, 5/5 stories)
```

**Narrator:**
> "Full history, detailed metrics, and it all works with both foreground and daemon mode."

---

## Act 6: Notifications (1 min)

**[Screen: Slack channel]**

**[Slack notification appears:]**
```
claude-loop [12:15 PM]
✓ Task Complete: feature-prd.json

Stories completed: 8/8
Time taken: 15m 30s
Cost: $3.20

All acceptance criteria met.
Branch: feature/oauth-implementation
Ready for review!
```

**Narrator:**
> "Notifications via Slack, email, or custom webhooks. Configure once, get alerted everywhere."

---

## Act 7: Complete Workflow Demo (1 min)

**[Screen: Split view - Terminal + Dashboard + Slack]**

**Narrator:**
> "Let's see it all together. One workflow, five Phase 2 features."

**[Terminal commands in rapid succession:]**
```bash
# 1. Validate PRD with skill
./claude-loop.sh --skill prd-validator --skill-arg new-feature.json

# 2. Start dashboard
./claude-loop.sh dashboard start &

# 3. Submit to daemon with notification
./claude-loop.sh daemon submit new-feature.json --notify slack
```

**[Dashboard comes alive with:]**
- Status changes
- Logs streaming
- Progress advancing

**[Slack notification appears when complete]**

**Narrator:**
> "Describe the feature. Go to lunch. Come back to a PR. That's the claude-loop promise, now powered by Phase 2."

---

## Act 8: Closing (30 sec)

**[Screen: Terminal with Phase 2 feature list]**

**Narrator:**
> "Phase 2 brings five foundational capabilities:
> 1. Skills Architecture - Instant, zero-cost operations
> 2. Quick Task Mode - Natural language task execution
> 3. Daemon Mode - Fire-and-forget background processing
> 4. Visual Progress Dashboard - Real-time monitoring
> 5. Notification System - Multi-channel alerts
>
> All fully backward compatible with Phase 1. All working together seamlessly. All designed to get you from idea to PR as fast as possible.
>
> Ready to try it? Check out the migration guide and get started today."

**[Show links:]**
- Migration Guide: `docs/MIGRATION-PHASE2.md`
- Documentation: `docs/phase2/`
- GitHub: `github.com/your-repo/claude-loop`

**[Fade to claude-loop logo]**

---

## Technical Setup for Recording

### Terminal Setup
- Theme: Dark theme with high contrast
- Font: Fira Code or JetBrains Mono, size 16
- Window size: 1920x1080, fullscreen
- Shell: zsh with minimal prompt (just `$`)

### Browser Setup
- Dashboard: Pre-configure with dummy data for smooth demo
- Window size: 1920x1080
- Zoom: 125% for readability

### Timing
- Script total: ~10 minutes
- Leave 2 minutes buffer for transitions
- Pre-record complex operations to avoid waiting

### Demo Data
Create test PRDs that complete quickly:
- `feature-prd.json` - 8 stories, ~2 minutes total
- `bugfix-prd.json` - 3 stories, ~1 minute total
- Use simple acceptance criteria for fast execution

### Voiceover Notes
- Pace: Moderate (not too slow, not rushed)
- Tone: Professional but enthusiastic
- Emphasis: "instant", "zero cost", "fire-and-forget", "real-time"
- Pause after each feature for impact

### Post-Production
- Add subtle background music (low volume)
- Highlight important commands/output with zoom/overlay
- Speed up long-running operations (2x speed with note)
- Add captions for accessibility
- Include chapter markers for easy navigation
