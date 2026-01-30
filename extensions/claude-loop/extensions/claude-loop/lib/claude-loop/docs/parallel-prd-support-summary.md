# Parallel PRD Support - Design Summary

**Date**: 2026-01-12
**Status**: Ready for Implementation
**Author**: Claude Sonnet 4.5

## Overview

This document summarizes the design for adding **Parallel PRD Execution** to Claude-Loop, enabling execution of multiple PRDs simultaneously with 3x-5x throughput improvement while maintaining safety, efficiency, and security.

## Problem Statement

Claude-Loop currently executes ONE PRD at a time. While it parallelizes **stories within a PRD**, it cannot execute **multiple PRDs concurrently**. This limits:

- **Throughput**: Underutilization of Claude API capacity
- **Flexibility**: Teams can't work on multiple features simultaneously
- **Efficiency**: No overnight batch processing of multiple PRDs

## Root Cause Analysis

The constraint is **NOT git conflicts** (worktrees solve that).

The **ROOT PROBLEM** is:
1. **Shared State Files**: All PRDs try to write to same state files
2. **No Coordination**: No infrastructure to manage multiple PRDs
3. **Branch Conflicts**: No prevention of duplicate branch names
4. **Resource Limits**: No API rate limiting or max PRD enforcement

## Solution: Coordinator Pattern

### High-Level Architecture

```
┌─────────────────────────────────────┐
│   PRD Coordinator                   │
│   • Registry Management             │
│   • Resource Coordination           │
│   • Unified Dashboard               │
└─────────────────────────────────────┘
         │
         ├─── PRD-001 Worker (Worktree)
         ├─── PRD-002 Worker (Worktree)
         └─── PRD-003 Worker (Worktree)
```

### Key Design Decisions

#### 1. Git Worktree Isolation
Each PRD gets its own worktree on a dedicated branch:

```bash
.claude-loop/worktrees/
├── PRD-001/  # feature/PRD-001 branch
│   ├── .claude-loop/  # Isolated state
│   └── <repo files>
└── PRD-002/  # feature/PRD-002 branch
    ├── .claude-loop/
    └── <repo files>
```

**Benefits**:
- ✅ Perfect git isolation
- ✅ No branch conflicts
- ✅ Independent file system access
- ✅ Safe concurrent commits

#### 2. Registry-Based Coordination

Central registry tracks all active PRDs:

```json
{
  "active_prds": {
    "PRD-001": {
      "prd_id": "PRD-001",
      "branch": "feature/PRD-001",
      "pid": 12345,
      "status": "running",
      "progress": {"completed": 8, "total": 12}
    }
  }
}
```

**Benefits**:
- ✅ Single source of truth
- ✅ Atomic updates via flock
- ✅ Resume capability
- ✅ Status monitoring

#### 3. File-Based Locking

Atomic operations using `flock`:

```bash
(
    flock -x 200
    # Critical section - atomic registry update
    jq ".active_prds.\"$prd_id\" = $info" registry.json > tmp
    mv tmp registry.json
) 200>registry.lock
```

**Benefits**:
- ✅ No race conditions
- ✅ Works with bash 3.x (macOS)
- ✅ Simple, proven pattern
- ✅ No external dependencies

#### 4. Resource Limits

- **Max Parallel PRDs**: Default 3 (configurable)
- **API Rate Limiting**: Semaphore-based token system
- **Worker Limits**: Inherited from story-level parallelization

**Benefits**:
- ✅ Prevents system overload
- ✅ Respects Claude API limits
- ✅ Predictable resource usage

#### 5. Unified Dashboard

Real-time terminal dashboard showing all PRDs:

```
╔═══════════════════════════════════════════════════════════╗
║        Claude-Loop Parallel Execution Status              ║
╠═══════════════════════════════════════════════════════════╣
║  Active PRDs: 3/3                                         ║
║                                                           ║
║  PRD-001: User Authentication                            ║
║  Progress: [████████████░░░░] 8/12 stories (66%)         ║
║  Runtime: 45m 23s                                        ║
║                                                           ║
║  PRD-002: Payment Integration                            ║
║  Progress: [███░░░░░░░░░░░░] 2/8 stories (25%)           ║
║  Runtime: 15m 10s                                        ║
╚═══════════════════════════════════════════════════════════╝
```

## Safety Mechanisms

### 1. Branch Conflict Prevention
```bash
# Automatic suffix if branch exists
feature/PRD-001 → feature/PRD-001-1
```

### 2. Failure Isolation
- One PRD failure doesn't stop others
- Failed worktrees preserved for debugging
- Auto-restart optional

### 3. Graceful Shutdown
- SIGINT/SIGTERM handlers
- Workers get 60s to finish current iteration
- State saved for resume

### 4. Resource Protection
- API rate limiting (global semaphore)
- Max PRD enforcement (queuing)
- CPU/memory limits per PRD

## CLI Interface

```bash
# Start parallel execution (all active PRDs)
./claude-loop.sh --parallel

# Specific PRDs
./claude-loop.sh --parallel PRD-001 PRD-002

# Monitor status
./claude-loop.sh --status

# Stop specific PRD
./claude-loop.sh --stop PRD-001

# Configuration
./claude-loop.sh --parallel --max-prds 5
```

## Implementation Plan

### 18 User Stories in 5 Phases

1. **Phase 1: Foundation** (Stories 1-5)
   - Coordinator script
   - Registry management
   - Worktree lifecycle
   - Resource limits
   - API rate limiting

2. **Phase 2: Execution** (Stories 6-9)
   - Worker launcher
   - Coordinator mode
   - Monitoring
   - Completion handling

3. **Phase 3: Dashboard** (Stories 10-12)
   - Unified dashboard
   - Status command
   - Metrics logging

4. **Phase 4: Safety** (Stories 13-15)
   - Graceful shutdown
   - Failure isolation
   - Resume capability

5. **Phase 5: Polish** (Stories 16-18)
   - Stop command
   - Documentation
   - Integration tests

### Effort Estimate

- **Sequential**: ~22 days
- **With Parallelization**: ~15 days

## Performance Characteristics

### Expected Gains
- **3x-5x throughput** with 3-5 parallel PRDs
- **Near-linear scaling** up to API rate limits
- **<5% overhead** from coordinator

### Resource Usage Per PRD
- **Memory**: ~500MB
- **Disk**: ~2GB (worktree size)
- **API**: Shared account rate limits

### Scalability Limits
- **Max Parallel PRDs**: 5 (practical limit)
- **Max Stories/PRD**: Unlimited (existing support)
- **Max Worktrees**: ~10 (practical limit)

## Backward Compatibility

- ✅ **Single PRD mode** remains default (no breaking changes)
- ✅ **Parallel mode** is opt-in via `--parallel` flag
- ✅ **Existing PRDs** work unchanged
- ✅ **No migration required**

## Security Considerations

### Secret Isolation
- Each worktree has isolated `.env` files
- Secrets never shared between PRDs
- Worktree cleanup scrubs sensitive data

### Branch Protection
- Coordinator prevents accidental overwrites
- Branch naming enforces uniqueness
- Main branch protected from parallel merges

### Resource Exhaustion Prevention
- Max parallel PRD limits
- API rate limiting
- CPU/memory limits per worker

## Files Created

### Design Documentation
1. **ADR-003**: `docs/adrs/adr-003-parallel-prd-execution.md`
   - Architectural Decision Record with full design
   - 500+ lines of detailed architecture

2. **Implementation Plan**: `docs/architecture/parallel-prd-implementation-plan.md`
   - 18 user stories with acceptance criteria
   - Testing strategy
   - Configuration guide

3. **PRD**: `prd-parallel-prd-support.json`
   - Executable PRD for claude-loop
   - Complete with dependencies and parallelization groups
   - Ready to run: `./claude-loop.sh --prd prd-parallel-prd-support.json`

## Next Steps

### To Implement This Feature:

1. **Review Documentation**
   ```bash
   cat docs/adrs/adr-003-parallel-prd-execution.md
   cat docs/architecture/parallel-prd-implementation-plan.md
   ```

2. **Run Claude-Loop with the PRD**
   ```bash
   ./claude-loop.sh --prd prd-parallel-prd-support.json
   ```

3. **Or Manually Start with Phase 1**
   ```bash
   # Story PAR-001: Create coordinator script
   touch lib/prd-coordinator.sh
   chmod +x lib/prd-coordinator.sh
   ```

### Testing After Implementation:

```bash
# Create test PRDs
mkdir -p prds/active/TEST-001 prds/active/TEST-002 prds/active/TEST-003

# Start parallel execution
./claude-loop.sh --parallel --max-prds 3

# Monitor progress
./claude-loop.sh --status

# Stop specific PRD
./claude-loop.sh --stop TEST-002
```

## Success Criteria

1. ✅ Execute 3+ PRDs in parallel without conflicts
2. ✅ Complete isolation of PRD state
3. ✅ Unified progress dashboard
4. ✅ Safe resource limits
5. ✅ Backward compatible
6. ✅ Clean worktree lifecycle
7. ✅ Graceful error handling

## Risks and Mitigations

| Risk | Mitigation |
|------|-----------|
| Git worktree bugs | Extensive testing, fallback to sequential mode |
| API rate limit exhaustion | Semaphore-based token system, configurable limits |
| File system race conditions | Atomic operations with flock |
| Complex debugging | Extensive logging, worktree preservation on failure |
| User confusion | Comprehensive documentation, clear error messages |

## Alternatives Considered

1. ❌ **Docker containers per PRD**: Too heavy, complex setup
2. ❌ **Separate repo clones**: Disk waste, complex merges
3. ❌ **Sequential execution**: Status quo, leaves resources underutilized
4. ✅ **Git worktrees + Coordinator**: Best balance of isolation and simplicity

## References

- **ADR-003**: Full architectural decision record
- **Implementation Plan**: Detailed story breakdown
- **PRD JSON**: Executable feature specification
- **Git Worktrees**: https://git-scm.com/docs/git-worktree
- **Bazel Build System**: Inspiration for coordinator pattern

## Questions?

### Q: Why git worktrees instead of separate clones?
**A**: Worktrees share the git object database (saves disk space) while providing complete file system isolation. Much more efficient than full clones.

### Q: What happens if two PRDs modify the same file?
**A**: Each PRD works on its own branch in isolation. Conflicts only occur at merge time (when both PRDs are complete), which is handled by git's normal merge conflict resolution.

### Q: How does this affect existing claude-loop users?
**A**: Zero impact. Parallel mode is opt-in via `--parallel` flag. Default behavior is unchanged.

### Q: Can I mix sequential and parallel execution?
**A**: Yes! Use `./claude-loop.sh` for sequential (single PRD) and `./claude-loop.sh --parallel` for parallel (multiple PRDs).

### Q: What's the recommended max parallel PRDs?
**A**: Default is 3, which provides good throughput without overwhelming the Claude API. Can be increased to 5 for heavy workloads.

### Q: How do I debug a failed PRD?
**A**: Failed worktrees are preserved at `.claude-loop/worktrees/<PRD-ID>/`. You can `cd` into the worktree and inspect logs, run tests, etc.

---

**Ready to implement!** The PRD is at `prd-parallel-prd-support.json` and can be executed immediately with claude-loop.
