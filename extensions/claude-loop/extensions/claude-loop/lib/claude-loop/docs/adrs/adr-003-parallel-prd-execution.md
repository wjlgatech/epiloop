# ADR-003: Parallel PRD Execution Architecture

**Status**: Proposed
**Date**: 2026-01-12
**Authors**: Claude Sonnet 4.5

## Context

Claude-Loop currently supports parallel execution of **user stories** within a single PRD using worker processes and git worktrees. However, it can only execute ONE PRD at a time. This limitation prevents:

1. **Concurrent Feature Development**: Multiple teams cannot work on different features simultaneously
2. **Resource Utilization**: Claude API capacity and developer time are underutilized
3. **Parallel Testing**: Cannot test multiple approaches or architectures in parallel
4. **Batch Processing**: Cannot queue multiple PRD implementations for overnight execution

### Current Architecture

```
claude-loop (single PRD executor)
├── Stories parallelized via lib/parallel.sh
│   └── Workers in .claude-loop/workers/
├── Single branch per execution (from PRD.branchName)
├── Single session state (.claude-loop/session-state.json)
└── Single progress tracking per PRD
```

### Key Constraint Identified

**The problem is NOT git conflicts** - git worktrees already solve repository isolation.

**The ROOT PROBLEM is**: Shared state files and lack of coordination infrastructure.

## First Principles Analysis

### Root Causes of Conflicts

1. **Shared State Files**: All PRDs try to write to the same state files:
   - `.claude-loop/session-state.json` (current PRD state)
   - `.claude-loop/execution_log.jsonl` (execution events)
   - `.claude-loop/capability_gaps.json` (gap analysis)
   - Progress files in PRD directories

2. **Single Execution Context**: `claude-loop.sh` assumes exclusive control:
   - No awareness of other running PRDs
   - No resource coordination (API rate limits)
   - No unified progress visibility

3. **Branch Conflicts**: If two PRDs specify the same `branchName`, they conflict

4. **Checkpoint Collisions**: Checkpoint directories use predictable paths that can overlap

### False Constraints (Not Actually Problems)

1. ✅ **Git Repository Access**: Worktrees provide perfect isolation
2. ✅ **File System Access**: Each PRD has its own worktree directory
3. ✅ **Story-Level Parallelism**: Already solved by `lib/parallel.sh`
4. ✅ **Claude API**: Supports concurrent requests from same account
5. ✅ **Directory Organization**: `prds/active/*` already namespace PRDs

### Core Isolation Requirements

From first principles, each PRD execution needs:

1. **Process Isolation**: Separate `claude-loop` process per PRD
2. **Git Isolation**: Dedicated worktree on unique branch
3. **State Isolation**: PRD-specific state directories
4. **Logging Isolation**: Separate logs per PRD
5. **Checkpoint Isolation**: PRD-namespaced checkpoint paths

## Decision

Implement **PRD Coordinator** architecture with the following components:

### 1. Git Worktree Strategy

Each PRD gets its own worktree on a dedicated branch:

```bash
# PRD-001 execution
git worktree add .claude-loop/worktrees/PRD-001 feature/PRD-001

# PRD-002 execution (parallel)
git worktree add .claude-loop/worktrees/PRD-002 feature/PRD-002
```

**Branch Naming Convention**:
- Default: `feature/<PRD-ID>` (from PRD manifest)
- Override: Use `branchName` from `prd.json` if specified
- Conflict Detection: Coordinator prevents duplicate branches

**Worktree Lifecycle**:
```
Start PRD → Create Worktree → Execute Stories → Merge to Main → Remove Worktree
```

### 2. State Isolation Architecture

```
Repository Root
├── .claude-loop/
│   ├── coordinator/                 # NEW: Coordinator state
│   │   ├── registry.json           # Active PRD executions
│   │   ├── locks/                  # File-based locks
│   │   │   ├── PRD-001.lock
│   │   │   └── PRD-002.lock
│   │   └── metrics.jsonl           # Aggregate metrics
│   │
│   ├── worktrees/                  # NEW: Worktree directories
│   │   ├── PRD-001/                # Git worktree for PRD-001
│   │   │   ├── .claude-loop/       # Isolated state for PRD-001
│   │   │   │   ├── session-state.json
│   │   │   │   ├── execution_log.jsonl
│   │   │   │   └── workers/
│   │   │   └── <repo files>
│   │   │
│   │   └── PRD-002/                # Git worktree for PRD-002
│   │       ├── .claude-loop/       # Isolated state for PRD-002
│   │       └── <repo files>
│   │
│   └── global/                     # Shared read-only resources
│       ├── cache/                  # Shared prompt cache
│       └── experiences/            # Shared experience DB
│
├── prds/
│   ├── active/
│   │   ├── PRD-001/
│   │   │   ├── MANIFEST.yaml
│   │   │   ├── prd.json
│   │   │   └── progress.txt       # PRD-specific progress
│   │   └── PRD-002/
│   │       ├── MANIFEST.yaml
│   │       ├── prd.json
│   │       └── progress.txt
│   └── ...
└── <repo files>
```

### 3. Coordinator Component

**New script**: `lib/prd-coordinator.sh`

**Responsibilities**:
1. Maintain PRD execution registry
2. Enforce resource limits (max parallel PRDs)
3. Prevent branch conflicts
4. Coordinate shared resources (API rate limits)
5. Provide unified progress dashboard
6. Handle cleanup on completion/failure

**Registry Format** (`.claude-loop/coordinator/registry.json`):
```json
{
  "version": "1.0",
  "max_parallel_prds": 3,
  "active_prds": {
    "PRD-001": {
      "prd_id": "PRD-001",
      "prd_path": "prds/active/PRD-001",
      "worktree_path": ".claude-loop/worktrees/PRD-001",
      "branch": "feature/PRD-001",
      "pid": 12345,
      "started_at": "2026-01-12T10:00:00Z",
      "status": "running",
      "current_story": "US-003",
      "progress": {
        "completed": 2,
        "total": 10
      }
    },
    "PRD-002": {
      "prd_id": "PRD-002",
      "worktree_path": ".claude-loop/worktrees/PRD-002",
      "branch": "feature/PRD-002",
      "pid": 12346,
      "started_at": "2026-01-12T10:05:00Z",
      "status": "running",
      "current_story": "US-001",
      "progress": {
        "completed": 0,
        "total": 8
      }
    }
  },
  "completed_prds": [
    {
      "prd_id": "PRD-000",
      "completed_at": "2026-01-12T09:55:00Z",
      "duration_seconds": 3600,
      "stories_completed": 12
    }
  ]
}
```

### 4. Execution Flow

```
┌─────────────────────────────────────────────────────────────┐
│                   PRD Coordinator (Main Process)            │
│                                                             │
│  ┌──────────────────────────────────────────────────┐     │
│  │  Registry Management                             │     │
│  │  - Track active PRDs                            │     │
│  │  - Enforce limits                               │     │
│  │  - Detect conflicts                             │     │
│  └──────────────────────────────────────────────────┘     │
│                                                             │
│  ┌──────────────────────────────────────────────────┐     │
│  │  Resource Coordination                           │     │
│  │  - API rate limiting                            │     │
│  │  - CPU/Memory limits                            │     │
│  └──────────────────────────────────────────────────┘     │
│                                                             │
│  ┌──────────────────────────────────────────────────┐     │
│  │  Unified Dashboard                               │     │
│  │  - Progress across all PRDs                     │     │
│  │  - Resource utilization                         │     │
│  └──────────────────────────────────────────────────┘     │
└─────────────────────────────────────────────────────────────┘
            │                    │                    │
            ▼                    ▼                    ▼
┌────────────────────┐  ┌────────────────────┐  ┌────────────────────┐
│   PRD-001 Worker   │  │   PRD-002 Worker   │  │   PRD-003 Worker   │
│                    │  │                    │  │                    │
│ Worktree:          │  │ Worktree:          │  │ Worktree:          │
│ .claude-loop/      │  │ .claude-loop/      │  │ .claude-loop/      │
│   worktrees/       │  │   worktrees/       │  │   worktrees/       │
│   PRD-001/         │  │   PRD-002/         │  │   PRD-003/         │
│                    │  │                    │  │                    │
│ Branch:            │  │ Branch:            │  │ Branch:            │
│ feature/PRD-001    │  │ feature/PRD-002    │  │ feature/PRD-003    │
│                    │  │                    │  │                    │
│ Stories:           │  │ Stories:           │  │ Stories:           │
│ ├─ US-001 ✓        │  │ ├─ US-001 ⚙        │  │ ├─ US-001 ⏸        │
│ ├─ US-002 ✓        │  │ ├─ US-002 ⏸        │  │ ├─ US-002 ⏸        │
│ ├─ US-003 ⚙        │  │ └─ US-003 ⏸        │  │ └─ US-003 ⏸        │
│ └─ ...             │  │                    │  │                    │
└────────────────────┘  └────────────────────┘  └────────────────────┘
```

### 5. CLI Interface

**Start multiple PRDs in parallel**:
```bash
# Start PRD coordinator with max 3 parallel PRDs
./claude-loop.sh --parallel --max-prds 3

# Coordinator will:
# 1. Find all PRDs in prds/active/
# 2. Launch up to 3 PRD executions in parallel
# 3. Show unified dashboard
# 4. Queue remaining PRDs

# Start specific PRDs
./claude-loop.sh --parallel PRD-001 PRD-002

# Monitor parallel executions
./claude-loop.sh --status

# Stop a specific PRD
./claude-loop.sh --stop PRD-002
```

**Unified Dashboard**:
```
╔═══════════════════════════════════════════════════════════════╗
║            Claude-Loop Parallel Execution Status              ║
╠═══════════════════════════════════════════════════════════════╣
║                                                               ║
║  Active PRDs: 3/3                                            ║
║  Queued PRDs: 2                                              ║
║                                                               ║
║  ┌────────────────────────────────────────────────────────┐  ║
║  │ PRD-001: User Authentication System                    │  ║
║  │ Branch: feature/PRD-001                                │  ║
║  │ Progress: [████████████░░░░] 8/12 stories (66%)        │  ║
║  │ Current: US-008 (Iteration 2/10)                       │  ║
║  │ Runtime: 45m 23s                                       │  ║
║  └────────────────────────────────────────────────────────┘  ║
║                                                               ║
║  ┌────────────────────────────────────────────────────────┐  ║
║  │ PRD-002: Payment Integration                           │  ║
║  │ Branch: feature/PRD-002                                │  ║
║  │ Progress: [███░░░░░░░░░░░░] 2/8 stories (25%)          │  ║
║  │ Current: US-003 (Iteration 1/10)                       │  ║
║  │ Runtime: 15m 10s                                       │  ║
║  └────────────────────────────────────────────────────────┘  ║
║                                                               ║
║  ┌────────────────────────────────────────────────────────┐  ║
║  │ PRD-003: Notification System                           │  ║
║  │ Branch: feature/PRD-003                                │  ║
║  │ Progress: [█░░░░░░░░░░░░░░░] 1/10 stories (10%)        │  ║
║  │ Current: US-002 (Iteration 3/10)                       │  ║
║  │ Runtime: 8m 45s                                        │  ║
║  └────────────────────────────────────────────────────────┘  ║
║                                                               ║
║  Queued:                                                     ║
║  - PRD-004: Analytics Dashboard                              ║
║  - PRD-005: Admin Panel                                      ║
║                                                               ║
║  Resource Utilization:                                       ║
║  - Claude API: 75% capacity (90/120 req/min)                ║
║  - CPU: 65%                                                  ║
║  - Workers: 9 active                                         ║
║                                                               ║
╚═══════════════════════════════════════════════════════════════╝
```

### 6. Safety Mechanisms

#### Branch Conflict Prevention
```bash
# Before creating worktree, check if branch exists
check_branch_conflict() {
    local branch="$1"
    local prd_id="$2"

    # Check in registry
    if branch_in_use "$branch" "$prd_id"; then
        log_error "Branch $branch already in use by another PRD"
        return 1
    fi

    # Check git
    if git rev-parse --verify "$branch" &>/dev/null; then
        log_warn "Branch $branch exists. Will use unique suffix."
        branch="${branch}-${prd_id}"
    fi

    echo "$branch"
}
```

#### Resource Limits
```bash
# Enforce max parallel PRDs
can_start_prd() {
    local active_count=$(count_active_prds)
    local max_prds=$(get_max_parallel_prds)

    if [ "$active_count" -ge "$max_prds" ]; then
        log_warn "Max parallel PRDs reached ($max_prds). Queueing."
        return 1
    fi

    return 0
}

# Claude API rate limiting (global coordinator)
acquire_api_token() {
    local prd_id="$1"

    # File-based semaphore for API rate limiting
    local lock_file=".claude-loop/coordinator/locks/api_limit.lock"
    local max_concurrent_api=10

    # Atomic check and increment
    flock -x "$lock_file" bash -c "
        current=\$(cat .claude-loop/coordinator/api_tokens 2>/dev/null || echo 0)
        if [ \$current -lt $max_concurrent_api ]; then
            echo \$((current + 1)) > .claude-loop/coordinator/api_tokens
            exit 0
        fi
        exit 1
    " || return 1
}

release_api_token() {
    local lock_file=".claude-loop/coordinator/locks/api_limit.lock"

    flock -x "$lock_file" bash -c "
        current=\$(cat .claude-loop/coordinator/api_tokens 2>/dev/null || echo 1)
        echo \$((current - 1)) > .claude-loop/coordinator/api_tokens
    "
}
```

#### Lock-Free Coordination
```bash
# Atomic PRD registration using flock
register_prd() {
    local prd_id="$1"
    local registry=".claude-loop/coordinator/registry.json"
    local lock=".claude-loop/coordinator/locks/registry.lock"

    # Atomic update
    (
        flock -x 200

        # Check if already registered
        if jq -e ".active_prds.\"$prd_id\"" "$registry" &>/dev/null; then
            echo "PRD already registered"
            exit 1
        fi

        # Add to registry
        jq ".active_prds.\"$prd_id\" = $prd_info" "$registry" > "$registry.tmp"
        mv "$registry.tmp" "$registry"

    ) 200>"$lock"
}
```

### 7. Error Handling

#### PRD Failure Isolation
```bash
# If one PRD fails, others continue
handle_prd_failure() {
    local prd_id="$1"
    local error="$2"

    log_error "PRD $prd_id failed: $error"

    # Update registry
    mark_prd_failed "$prd_id" "$error"

    # Clean up worktree (optional - keep for debugging)
    cleanup_worktree "$prd_id" --keep-on-failure

    # Continue with other PRDs
    log_info "Other PRDs continue running"
}
```

#### Graceful Shutdown
```bash
# Handle SIGINT/SIGTERM
cleanup_on_exit() {
    log_warn "Shutting down coordinator..."

    # Stop all PRD workers
    for prd_id in $(list_active_prds); do
        stop_prd_worker "$prd_id"
    done

    # Save state
    save_coordinator_state

    # Keep worktrees for resume
    log_info "Worktrees preserved for resume"
}

trap cleanup_on_exit SIGINT SIGTERM
```

### 8. Cleanup Strategy

#### On PRD Completion
```bash
cleanup_prd_on_success() {
    local prd_id="$1"
    local worktree_path="$2"
    local branch="$3"

    # 1. Merge to main (if configured)
    if should_auto_merge "$prd_id"; then
        git checkout main
        git merge --no-ff "$branch" -m "Merge $prd_id"
    fi

    # 2. Move PRD to completed
    mv "prds/active/$prd_id" "prds/completed/$prd_id"

    # 3. Archive worktree state
    tar -czf ".claude-loop/archives/$prd_id-worktree.tar.gz" "$worktree_path/.claude-loop"

    # 4. Remove worktree
    git worktree remove "$worktree_path" --force

    # 5. Deregister from coordinator
    deregister_prd "$prd_id"

    log_success "PRD $prd_id completed and cleaned up"
}
```

## Security Considerations

### 1. Secret Isolation
- Each worktree has isolated `.env` files
- Secrets are never shared between PRD executions
- Worktree cleanup scrubs sensitive data

### 2. Branch Protection
- Coordinator prevents accidental overwrites
- Branch naming enforces uniqueness
- Main branch protected from parallel merges

### 3. File System Security
- Worktree paths are predictable but namespaced
- Lock files prevent race conditions
- Atomic operations for all shared state updates

### 4. Resource Exhaustion Prevention
- Max parallel PRDs limit (default: 3)
- API rate limiting per account
- CPU/memory limits per PRD worker

## Performance Characteristics

### Resource Usage
- **Memory**: ~500MB per active PRD worker
- **Disk**: ~2GB per worktree (repository size dependent)
- **API**: Shared Claude account rate limits
- **CPU**: Proportional to parallel stories within each PRD

### Scalability Limits
- **Max Parallel PRDs**: 5 (configurable, limited by API rate limits)
- **Max Stories per PRD**: Already supported (limited by parallel.sh)
- **Worktree Count**: No technical limit, practical limit ~10

### Expected Performance Gains
- **3x-5x throughput** with 3-5 parallel PRDs
- **Near-linear scaling** up to API rate limits
- **Zero interference** between isolated PRD executions

## Migration Strategy

### Phase 1: Coordinator Infrastructure
1. Implement `lib/prd-coordinator.sh`
2. Add registry management
3. Add worktree lifecycle management

### Phase 2: Parallel Execution
1. Modify `claude-loop.sh` to support `--parallel` mode
2. Implement PRD worker launcher
3. Add unified dashboard

### Phase 3: Safety & Monitoring
1. Add resource limits
2. Implement lock-free coordination
3. Add error handling and recovery

### Phase 4: Polish
1. CLI improvements
2. Documentation
3. Testing and validation

### Backward Compatibility
- **Single PRD mode** remains default (no breaking changes)
- **Parallel mode** is opt-in via `--parallel` flag
- **Existing PRDs** work unchanged

## Alternatives Considered

### Alternative 1: Sequential Execution (Status Quo)
**Rejected**: Leaves resources underutilized, slow batch processing

### Alternative 2: Docker Containers per PRD
**Rejected**: Too heavy, requires Docker, complex setup

### Alternative 3: Full Rebuild per PRD
**Rejected**: Wasteful, loses git history integration

### Alternative 4: Separate Repository Clones
**Rejected**: Disk space waste, complex merge workflows

## References

- Git Worktrees: https://git-scm.com/docs/git-worktree
- Bazel Build System: https://bazel.build/
- File-based Locking: `flock(1)` man page
- ADR-002: Stratified Memory System (precedent for coordinator pattern)

## Success Metrics

1. **Throughput**: 3x increase with 3 parallel PRDs
2. **Safety**: Zero data corruption events
3. **Isolation**: Zero cross-PRD conflicts
4. **Observability**: Real-time progress visibility
5. **Reliability**: 99% completion rate for queued PRDs

## Open Questions

1. **Merge Strategy**: Auto-merge to main, or leave branches for manual review?
   - **Recommendation**: Configurable per PRD via MANIFEST.yaml

2. **Priority Queuing**: Should high-priority PRDs jump the queue?
   - **Recommendation**: Phase 2 feature, FIFO for now

3. **Resume Support**: How to resume all PRDs after coordinator restart?
   - **Recommendation**: Registry persists state, auto-resume on startup

4. **Cross-PRD Dependencies**: What if PRD-002 depends on PRD-001?
   - **Recommendation**: Document as unsupported, manual sequencing required

## Conclusion

This architecture provides **safe, efficient, and secure** parallel PRD execution by:

1. **Git Worktrees**: Perfect repository isolation per PRD
2. **Coordinator Pattern**: Central orchestration without coupling
3. **File-Based Locks**: Lock-free coordination using atomic operations
4. **Namespaced State**: Complete isolation of PRD execution state
5. **Resource Limits**: Prevent overload and respect API constraints

The design is **backward compatible**, **incrementally deployable**, and builds on existing claude-loop primitives (parallel.sh, worker.sh, session-state.sh).

Implementation can proceed in phases with immediate value at each milestone.
