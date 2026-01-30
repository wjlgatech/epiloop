# Ralph vs Claude-Loop Comparison Report

**Test Date**: 2026-01-10
**Test Project**: Simple Task Manager (TypeScript)
**Iterations**: 2 per system

## Executive Summary

Both systems successfully implemented 2 user stories in 2 iterations. Claude-loop is a **viable equivalent** to Ralph, with some differences in behavior and documentation quality.

| Metric | Ralph (Amp) | Claude-Loop |
|--------|-------------|-------------|
| Stories Completed | 2/4 | 2/4 |
| Iterations Used | 2 | 2 |
| Build Status | PASSED | PASSED |
| PRD State Updated | NO (bug) | YES |
| Progress File Quality | Empty | Detailed |
| Code Documentation | Minimal | Extensive JSDoc |

## Test Setup

### Sample Project
- TypeScript Node.js project
- 4 user stories:
  1. US-001: Create Task interface and types
  2. US-002: Implement TaskManager class
  3. US-003: Add unit tests
  4. US-004: Export public API

### Configuration
- Ralph: `/scripts/ralph/ralph.sh 2`
- Claude-loop: `/scripts/claude-loop/claude-loop.sh --max-iterations 2`

---

## Detailed Comparison

### 1. Story Completion Rate

**Both systems completed identical work:**
- US-001: Created `src/types.ts` with Task interface and TaskInput type
- US-002: Created `src/TaskManager.ts` with CRUD operations

**Result**: ✅ **TIE** - Equal performance

---

### 2. State Management

#### Ralph
```json
// prd.json - ALL stories still show passes: false
{
  "id": "US-001",
  "passes": false  // ❌ Should be true
}
```
- prd.json NOT updated despite completing stories
- Progress file empty (only header)
- **Bug**: Amp agent didn't persist state changes

#### Claude-Loop
```json
// prd.json - Completed stories correctly marked
{
  "id": "US-001",
  "passes": true  // ✅ Correct
}
```
- prd.json correctly updated
- Progress file has detailed iteration history
- All state properly persisted

**Result**: ✅ **Claude-Loop wins** - Better state management

---

### 3. Code Quality

#### types.ts Comparison

**Ralph (178 bytes)**:
```typescript
export interface Task {
  id: string;
  title: string;
  description: string;
  completed: boolean;
  createdAt: Date;
}

export type TaskInput = Omit<Task, 'id' | 'createdAt'>;
```
- Concise
- Uses `Omit` utility type (elegant)
- No documentation

**Claude-Loop (685 bytes)**:
```typescript
/**
 * Represents a task in the task manager.
 */
export interface Task {
  /** Unique identifier for the task */
  id: string;
  // ... with JSDoc for all fields
}
```
- Verbose with JSDoc comments
- Explicit TaskInput interface
- Better for team projects

**Result**: 🤝 **Tie** - Different styles, both valid

---

### 4. TaskManager Implementation

#### Ralph (1055 bytes)
- Clean, minimal implementation
- Uses spread operators effectively
- Random ID generation: `task_${Date.now()}_${Math.random()...}`

#### Claude-Loop (2540 bytes)
- Extensive JSDoc documentation
- Counter-based ID: `task-${counter}-${timestamp}`
- Explicit handling in update (preserves id/createdAt)

**Result**: 🤝 **Tie** - Both implementations are correct

---

### 5. Progress Documentation

#### Ralph progress.txt
```
# Ralph Progress Log
Started: Sat Jan 10 11:30:20 PST 2026
---
```
(Empty - no iteration details captured)

#### Claude-Loop progress.txt
```markdown
### Iteration: 2026-01-10 11:31
**Story**: US-001 - Create Task interface and types
**Status**: Complete

**What was implemented**:
- Created `src/types.ts` with Task interface and TaskInput type
...

**Learnings for future iterations**:
- Node modules were corrupted initially; reinstalling fixed it
- Project uses TypeScript strict mode with ES2020 target
...
```
(Detailed iteration history with learnings)

**Result**: ✅ **Claude-Loop wins** - Much better documentation

---

### 6. Git History

#### Ralph
```
654e408 chore: update PRD and progress for US-002
63e7bbb feat: [US-002] - Implement TaskManager class
95ae4f7 feat: US-001 - Create Task interface and types
0a864cd Initial project setup
```
- 4 commits for 2 stories
- Extra "chore" commit for PRD updates

#### Claude-Loop
```
ab83a4d feat: [US-002] - Implement TaskManager class
e4ef843 feat: [US-001] - Create Task interface and types
0a864cd Initial project setup
```
- 2 commits for 2 stories (cleaner)
- State updates included in story commits

**Result**: ✅ **Claude-Loop wins** - Cleaner git history

---

## Architecture Comparison

| Aspect | Ralph | Claude-Loop |
|--------|-------|-------------|
| CLI Used | Amp | Claude Code |
| Script Language | Bash | Bash |
| Completion Signal | `<promise>COMPLETE</promise>` | `<loop>COMPLETE</loop>` |
| PRD Location | Script directory | Working directory (configurable) |
| Branch Handling | Manual checkout | Auto-create branch |
| Quality Gates | Project-specific | Project-specific |
| Verbose Mode | No | Yes (`-v` flag) |
| Dry Run | No | No |
| Color Output | No | Yes |
| Progress Summary | No | Yes (end summary) |

---

## Verdict: Does Claude-Loop Live Up to Ralph?

### ✅ YES - Claude-Loop successfully replicates Ralph's core functionality:

1. **Autonomous iteration loop** - Both run multiple iterations until completion
2. **Story-per-iteration** - Both complete exactly one story per iteration
3. **Persistent memory** - Both use prd.json, progress.txt, AGENTS.md
4. **Quality gates** - Both enforce typecheck/tests before commits
5. **Completion detection** - Both detect when all stories are done

### Claude-Loop Advantages:

1. **Better state management** - Actually updates prd.json (ralph had a bug)
2. **Better documentation** - Detailed progress.txt with learnings
3. **Better UX** - Colored output, progress summary, verbose mode
4. **Cleaner git history** - Fewer commits per story
5. **More defensive** - Pre-flight checks, branch auto-creation

### Ralph Advantages:

1. **More concise code output** - Less verbose, uses TypeScript utilities
2. **Established pattern** - Based on Geoffrey Huntley's tested approach
3. **Amp integration** - Access to Amp-specific features (threads, tools)

---

## Recommendations

1. **Use Claude-Loop** for Claude Code users - native integration, better state management
2. **Use Ralph** for Amp users - designed for Amp's ecosystem
3. **Consider fixing Ralph's state persistence bug** - prd.json not being updated

---

## Test Artifacts

| File | Ralph | Claude-Loop |
|------|-------|-------------|
| `src/types.ts` | ✅ Created | ✅ Created |
| `src/TaskManager.ts` | ✅ Created | ✅ Created |
| `prd.json` | ❌ Not updated | ✅ Updated |
| `progress.txt` | ❌ Empty | ✅ Detailed |
| Build | ✅ Passes | ✅ Passes |
| TypeCheck | ✅ Passes | ✅ Passes |
