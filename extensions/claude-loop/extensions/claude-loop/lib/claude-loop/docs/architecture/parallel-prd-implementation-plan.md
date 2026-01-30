# Parallel PRD Execution - Implementation Plan

**Based on**: ADR-003: Parallel PRD Execution Architecture
**Target**: Claude-Loop v2.0
**Estimated Complexity**: Level 4 (Major Feature)

## Overview

Transform Claude-Loop from a sequential PRD executor into a parallel PRD coordinator that can execute multiple PRDs simultaneously while maintaining safety, efficiency, and observability.

## Success Criteria

1. ✅ Execute 3+ PRDs in parallel without conflicts
2. ✅ Complete isolation of PRD state and git branches
3. ✅ Unified progress dashboard showing all active PRDs
4. ✅ Safe resource limits (API rate limiting, max PRDs)
5. ✅ Backward compatible with single-PRD mode
6. ✅ Clean worktree lifecycle management
7. ✅ Graceful error handling and recovery

## Architecture Summary

```
┌──────────────────────────────────────┐
│   PRD Coordinator (lib/prd-coordinator.sh)   │
│   • Registry Management                      │
│   • Resource Coordination                    │
│   • Unified Dashboard                        │
└──────────────────────────────────────┘
            │
            ├─── PRD-001 Worker (Worktree 1)
            ├─── PRD-002 Worker (Worktree 2)
            └─── PRD-003 Worker (Worktree 3)
```

### Directory Structure
```
.claude-loop/
├── coordinator/              # NEW
│   ├── registry.json
│   ├── locks/
│   └── metrics.jsonl
├── worktrees/               # NEW
│   ├── PRD-001/            # Git worktree
│   │   └── .claude-loop/   # Isolated state
│   └── PRD-002/
│       └── .claude-loop/
└── global/                  # Shared resources
    └── cache/
```

## Implementation Phases

### Phase 1: Coordinator Foundation (Stories 1-5)

**Goal**: Create coordinator infrastructure and registry management

#### US-001: Create PRD Coordinator Script
**Priority**: 1 (Foundational)
**Complexity**: Medium
**Dependencies**: None

**Tasks**:
- Create `lib/prd-coordinator.sh` with basic structure
- Implement initialization and configuration loading
- Add logging utilities
- Create coordinator state directory structure

**Acceptance Criteria**:
- [ ] Script exists and is executable
- [ ] Creates `.claude-loop/coordinator/` structure
- [ ] Loads configuration from environment/args
- [ ] Logs initialization events

**File Scope**:
- `lib/prd-coordinator.sh` (new)
- `.claude-loop/coordinator/` (directory creation)

---

#### US-002: Implement PRD Registry Management
**Priority**: 1 (Foundational)
**Complexity**: Medium
**Dependencies**: US-001

**Tasks**:
- Design registry JSON schema
- Implement `register_prd()` function with atomic updates
- Implement `deregister_prd()` function
- Add registry query functions (`list_active_prds`, `get_prd_info`)
- Add file-based locking for registry updates

**Acceptance Criteria**:
- [ ] Registry JSON schema documented
- [ ] Atomic PRD registration using flock
- [ ] Safe deregistration with cleanup hooks
- [ ] Query functions return accurate data
- [ ] Concurrent updates don't corrupt registry

**File Scope**:
- `lib/prd-coordinator.sh` (registry functions)
- `.claude-loop/coordinator/registry.json` (data file)

**Test Data**:
```json
{
  "version": "1.0",
  "max_parallel_prds": 3,
  "active_prds": {
    "PRD-001": {
      "prd_id": "PRD-001",
      "branch": "feature/PRD-001",
      "pid": 12345,
      "started_at": "2026-01-12T10:00:00Z",
      "status": "running"
    }
  }
}
```

---

#### US-003: Implement Git Worktree Lifecycle Management
**Priority**: 1 (Foundational)
**Complexity**: High
**Dependencies**: US-002

**Tasks**:
- Implement `create_prd_worktree()` function
- Add branch conflict detection and resolution
- Implement `remove_prd_worktree()` with safe cleanup
- Handle worktree creation failures gracefully
- Add worktree status checking

**Acceptance Criteria**:
- [ ] Creates worktrees in `.claude-loop/worktrees/<PRD-ID>/`
- [ ] Uses unique branches (feature/<PRD-ID>)
- [ ] Detects and resolves branch name conflicts
- [ ] Safely removes worktrees on completion
- [ ] Handles git errors gracefully
- [ ] Preserves worktrees on failure for debugging

**File Scope**:
- `lib/prd-coordinator.sh` (worktree functions)
- `.claude-loop/worktrees/` (directory)

**Edge Cases**:
- Branch already exists
- Worktree path already exists
- Git worktree command fails
- Disk space exhaustion

---

#### US-004: Add Resource Limit Enforcement
**Priority**: 2 (Important)
**Complexity**: Medium
**Dependencies**: US-002

**Tasks**:
- Implement max parallel PRDs limit
- Add `can_start_prd()` check function
- Implement PRD queuing when limit reached
- Add configuration for resource limits
- Create resource utilization tracking

**Acceptance Criteria**:
- [ ] Enforces `max_parallel_prds` limit (default: 3)
- [ ] Queues PRDs when limit reached
- [ ] Auto-starts queued PRDs when slot available
- [ ] Resource limits configurable via CLI/config
- [ ] Tracks active worker count

**File Scope**:
- `lib/prd-coordinator.sh` (resource limit functions)
- `.claude-loop/coordinator/registry.json` (queue tracking)

**Configuration**:
```bash
MAX_PARALLEL_PRDS=3  # Default
MAX_WORKERS_PER_PRD=3  # Story-level parallelism
```

---

#### US-005: Implement File-Based API Rate Limiting
**Priority**: 2 (Important)
**Complexity**: High
**Dependencies**: US-002

**Tasks**:
- Create API token semaphore system
- Implement `acquire_api_token()` with atomic ops
- Implement `release_api_token()` with cleanup
- Add token tracking and metrics
- Handle token leaks (abandoned PRDs)

**Acceptance Criteria**:
- [ ] Global API token limit enforced (e.g., 10 concurrent)
- [ ] Atomic token acquire/release using flock
- [ ] No token leaks on PRD failure
- [ ] Timeout on token acquisition
- [ ] Metrics track token utilization

**File Scope**:
- `lib/prd-coordinator.sh` (rate limiting functions)
- `.claude-loop/coordinator/locks/api_limit.lock`
- `.claude-loop/coordinator/api_tokens` (counter file)

**Algorithm**:
```bash
acquire_api_token() {
    flock -x api_limit.lock bash -c "
        current=\$(cat api_tokens)
        if [ \$current -lt MAX ]; then
            echo \$((current + 1)) > api_tokens
            exit 0
        fi
        exit 1
    "
}
```

---

### Phase 2: Parallel Execution (Stories 6-9)

**Goal**: Enable parallel PRD worker launching and execution

#### US-006: Create PRD Worker Launcher
**Priority**: 1 (Core)
**Complexity**: High
**Dependencies**: US-003, US-004, US-005

**Tasks**:
- Implement `launch_prd_worker()` function
- Set up isolated environment per worker
- Launch `claude-loop.sh` in worktree as background process
- Capture worker PID and track in registry
- Handle worker launch failures

**Acceptance Criteria**:
- [ ] Launches claude-loop in worktree directory
- [ ] Worker runs as background process
- [ ] PID tracked in registry
- [ ] Worker inherits correct environment
- [ ] Isolated .claude-loop/ state per worker
- [ ] Worker stdout/stderr logged separately

**File Scope**:
- `lib/prd-coordinator.sh` (worker launcher)
- `.claude-loop/coordinator/logs/<PRD-ID>.log` (worker logs)

**Launch Command**:
```bash
(
    cd "$worktree_path"
    ../claude-loop.sh --prd "prd.json" --no-parallel > logs/output.log 2>&1
    echo $? > exit_code
) &
pid=$!
```

---

#### US-007: Modify claude-loop.sh for Coordinator Mode
**Priority**: 1 (Core)
**Complexity**: Medium
**Dependencies**: US-006

**Tasks**:
- Add `--parallel` flag to claude-loop.sh
- Detect if running as coordinator or worker
- Coordinator mode: Launch PRD workers
- Worker mode: Execute single PRD (existing behavior)
- Add `--max-prds` configuration

**Acceptance Criteria**:
- [ ] `--parallel` flag enables coordinator mode
- [ ] Coordinator launches multiple PRD workers
- [ ] Worker mode runs unchanged (backward compat)
- [ ] Auto-detects PRDs in prds/active/
- [ ] `--prd` accepts multiple PRD IDs in parallel mode

**File Scope**:
- `claude-loop.sh` (add coordinator mode)
- `lib/prd-coordinator.sh` (integration)

**CLI Examples**:
```bash
# Parallel mode - all active PRDs
./claude-loop.sh --parallel

# Parallel mode - specific PRDs
./claude-loop.sh --parallel PRD-001 PRD-002

# Worker mode (unchanged)
./claude-loop.sh --prd prd.json
```

---

#### US-008: Implement Worker Monitoring and Health Checks
**Priority**: 2 (Important)
**Complexity**: Medium
**Dependencies**: US-006

**Tasks**:
- Poll worker processes for liveness
- Detect crashed/hung workers
- Update registry with worker status
- Implement automatic worker restart on failure
- Add worker timeout detection

**Acceptance Criteria**:
- [ ] Polls workers every 10 seconds
- [ ] Detects crashed workers (PID doesn't exist)
- [ ] Detects hung workers (no progress in 15 minutes)
- [ ] Updates registry status: running/failed/complete
- [ ] Optional: Auto-restart failed workers
- [ ] Logs worker status changes

**File Scope**:
- `lib/prd-coordinator.sh` (monitoring functions)
- `.claude-loop/coordinator/registry.json` (status updates)

---

#### US-009: Add Worker Completion Handling
**Priority**: 2 (Important)
**Complexity**: Medium
**Dependencies**: US-008

**Tasks**:
- Detect worker completion (exit code 0)
- Execute post-completion cleanup
- Move PRD from active to completed
- Optional: Auto-merge to main
- Deregister from coordinator
- Start next queued PRD if any

**Acceptance Criteria**:
- [ ] Detects worker exit via PID check
- [ ] Reads exit code from worker
- [ ] Moves prds/active/<PRD> to prds/completed/
- [ ] Optionally merges branch to main
- [ ] Removes worktree or archives it
- [ ] Starts next queued PRD automatically

**File Scope**:
- `lib/prd-coordinator.sh` (completion handler)
- `prds/active/` → `prds/completed/` (move)

**Cleanup Flow**:
```
Worker Exits → Read Exit Code → Cleanup Worktree →
Move PRD → Deregister → Start Next Queued
```

---

### Phase 3: Dashboard & Observability (Stories 10-12)

**Goal**: Unified progress dashboard and monitoring

#### US-010: Create Unified Progress Dashboard
**Priority**: 1 (UX Critical)
**Complexity**: High
**Dependencies**: US-008

**Tasks**:
- Design terminal dashboard layout
- Implement real-time progress display
- Show per-PRD progress bars
- Display resource utilization metrics
- Add color-coded status indicators
- Update dashboard at 1-second intervals

**Acceptance Criteria**:
- [ ] Shows all active PRDs with progress
- [ ] Real-time updates (1-second refresh)
- [ ] Color-coded status (green=ok, red=error)
- [ ] Shows current story per PRD
- [ ] Shows runtime per PRD
- [ ] Shows queued PRDs
- [ ] Resource utilization summary

**File Scope**:
- `lib/prd-coordinator.sh` (dashboard rendering)
- `.claude-loop/coordinator/registry.json` (data source)

**Dashboard Layout** (see ADR-003 for full design)

---

#### US-011: Add --status Command for Monitoring
**Priority**: 2 (UX)
**Complexity**: Low
**Dependencies**: US-010

**Tasks**:
- Add `--status` flag to claude-loop.sh
- Display current coordinator state
- Show active/queued/completed PRDs
- Support JSON output mode
- Allow filtering by PRD ID

**Acceptance Criteria**:
- [ ] `./claude-loop.sh --status` shows dashboard
- [ ] `--status --json` outputs JSON
- [ ] `--status PRD-001` shows single PRD details
- [ ] Works when coordinator is running or stopped
- [ ] Shows historical data from registry

**File Scope**:
- `claude-loop.sh` (status command)
- `lib/prd-coordinator.sh` (status functions)

---

#### US-012: Implement Aggregate Metrics Logging
**Priority**: 3 (Optional)
**Complexity**: Low
**Dependencies**: US-009

**Tasks**:
- Create `.claude-loop/coordinator/metrics.jsonl` log
- Log coordinator events (start, completion, failures)
- Track throughput metrics (PRDs/hour)
- Calculate resource utilization stats
- Export metrics for analysis

**Acceptance Criteria**:
- [ ] JSONL log with one event per line
- [ ] Logs PRD start/complete/fail events
- [ ] Calculates aggregate throughput
- [ ] Tracks API usage across all PRDs
- [ ] Metrics exportable to CSV/JSON

**File Scope**:
- `.claude-loop/coordinator/metrics.jsonl`
- `lib/prd-coordinator.sh` (metrics functions)

**Metrics Schema**:
```json
{
  "timestamp": "2026-01-12T10:00:00Z",
  "event": "prd_started",
  "prd_id": "PRD-001",
  "branch": "feature/PRD-001",
  "metadata": {}
}
```

---

### Phase 4: Safety & Error Handling (Stories 13-15)

**Goal**: Robust error handling and graceful shutdown

#### US-013: Implement Graceful Shutdown Handler
**Priority**: 1 (Critical)
**Complexity**: Medium
**Dependencies**: US-008

**Tasks**:
- Add SIGINT/SIGTERM signal handlers
- Stop all active PRD workers gracefully
- Save coordinator state before exit
- Preserve worktrees for resume
- Wait for workers to finish current iteration

**Acceptance Criteria**:
- [ ] Ctrl+C triggers graceful shutdown
- [ ] All workers receive SIGTERM
- [ ] Wait up to 60s for workers to finish
- [ ] Force kill after timeout
- [ ] Registry saved with current state
- [ ] Worktrees preserved for resume
- [ ] Exit with proper status code

**File Scope**:
- `lib/prd-coordinator.sh` (signal handlers)
- `claude-loop.sh` (shutdown logic)

---

#### US-014: Add PRD Failure Isolation
**Priority**: 2 (Important)
**Complexity**: Medium
**Dependencies**: US-008

**Tasks**:
- Detect and handle worker failures
- Mark failed PRD in registry
- Preserve failed worktree for debugging
- Continue other PRDs on failure
- Add failure notification/logging

**Acceptance Criteria**:
- [ ] Failed PRD doesn't stop other PRDs
- [ ] Failure logged with error details
- [ ] Failed worktree preserved by default
- [ ] Registry marks PRD as "failed"
- [ ] Queued PRDs continue normally
- [ ] Option to auto-retry failed PRDs

**File Scope**:
- `lib/prd-coordinator.sh` (error handling)
- `.claude-loop/coordinator/registry.json` (failure tracking)

---

#### US-015: Add Coordinator State Persistence and Resume
**Priority**: 3 (Enhancement)
**Complexity**: High
**Dependencies**: US-013, US-014

**Tasks**:
- Save coordinator state periodically
- Detect crashed coordinator on startup
- Resume active PRDs from registry
- Reattach to running workers if possible
- Clean up orphaned worktrees

**Acceptance Criteria**:
- [ ] Coordinator state auto-saved every 60s
- [ ] On restart, detects previous session
- [ ] Prompts to resume or start fresh
- [ ] Reattaches to running workers by PID
- [ ] Orphaned workers detected and cleaned up
- [ ] Resume preserves queue order

**File Scope**:
- `lib/prd-coordinator.sh` (persistence/resume)
- `.claude-loop/coordinator/registry.json` (state)

---

### Phase 5: CLI & Polish (Stories 16-18)

**Goal**: User experience improvements and documentation

#### US-016: Add --stop Command for Worker Control
**Priority**: 2 (UX)
**Complexity**: Low
**Dependencies**: US-013

**Tasks**:
- Add `--stop <PRD-ID>` command
- Stop specific PRD worker gracefully
- Add `--stop-all` option
- Update registry status

**Acceptance Criteria**:
- [ ] `./claude-loop.sh --stop PRD-001` stops worker
- [ ] `--stop-all` stops all workers
- [ ] Graceful shutdown (SIGTERM, then SIGKILL)
- [ ] Worker marked as "stopped" in registry
- [ ] Worktree preserved for resume

**File Scope**:
- `claude-loop.sh` (stop command)
- `lib/prd-coordinator.sh` (stop functions)

---

#### US-017: Enhance Help and Documentation
**Priority**: 3 (Documentation)
**Complexity**: Low
**Dependencies**: All previous stories

**Tasks**:
- Update `--help` with parallel mode docs
- Add examples for common workflows
- Document coordinator architecture
- Create troubleshooting guide
- Add performance tuning guide

**Acceptance Criteria**:
- [ ] `--help` documents all parallel flags
- [ ] Examples cover common use cases
- [ ] Architecture diagram in docs/
- [ ] Troubleshooting guide created
- [ ] Performance tuning documented

**File Scope**:
- `claude-loop.sh` (help text)
- `docs/parallel-prd-guide.md` (new)
- `docs/troubleshooting.md` (new)

---

#### US-018: Add Comprehensive Testing Suite
**Priority**: 3 (Quality)
**Complexity**: High
**Dependencies**: All previous stories

**Tasks**:
- Create integration tests for coordinator
- Test concurrent PRD execution
- Test failure scenarios
- Test resource limits
- Add performance benchmarks

**Acceptance Criteria**:
- [ ] Integration test suite in tests/
- [ ] Tests cover happy path and error cases
- [ ] Simulates 3 concurrent PRDs
- [ ] Tests resource limit enforcement
- [ ] Performance benchmarks documented
- [ ] All tests pass on macOS and Linux

**File Scope**:
- `tests/integration/test_parallel_prd.sh` (new)
- `tests/integration/test_coordinator.sh` (new)

---

## Configuration

### Environment Variables
```bash
# Parallel execution limits
PARALLEL_MAX_PRDS=3            # Max concurrent PRDs
PARALLEL_MAX_WORKERS_PER_PRD=3 # Max concurrent stories per PRD
PARALLEL_API_LIMIT=10          # Max concurrent API requests

# Coordinator behavior
COORDINATOR_AUTO_MERGE=false   # Auto-merge on PRD completion
COORDINATOR_AUTO_RETRY=false   # Auto-retry failed PRDs
COORDINATOR_DASHBOARD_REFRESH=1 # Dashboard refresh interval (seconds)

# Worktree management
WORKTREE_CLEANUP_ON_SUCCESS=true  # Remove worktrees on success
WORKTREE_CLEANUP_ON_FAILURE=false # Preserve worktrees on failure
```

### Config File Support
Create `.claude-loop/config.yaml`:
```yaml
parallel:
  max_prds: 3
  max_workers_per_prd: 3
  api_limit: 10
  auto_merge: false
  auto_retry: false
  dashboard_refresh_seconds: 1

worktree:
  cleanup_on_success: true
  cleanup_on_failure: false
  base_path: ".claude-loop/worktrees"
```

## Testing Strategy

### Unit Tests
- Registry operations (atomic updates)
- Worktree lifecycle management
- Resource limit enforcement
- API rate limiting

### Integration Tests
1. **3 PRDs in Parallel**: Verify no conflicts, all complete successfully
2. **Resource Limit**: Start 5 PRDs with limit=3, verify queueing
3. **Failure Isolation**: Fail 1 PRD, verify others continue
4. **Graceful Shutdown**: SIGINT during execution, verify clean stop
5. **Resume**: Stop coordinator, restart, verify resume works

### Performance Tests
- Throughput: Measure PRDs/hour vs sequential
- Latency: Overhead of coordinator vs direct execution
- Resource Usage: Memory, CPU, disk per PRD

## Deployment

### Rollout Plan
1. **Alpha**: Internal testing with 2-3 PRDs
2. **Beta**: Limited users, feedback collection
3. **GA**: Full release with documentation

### Rollback Plan
- Parallel mode is opt-in (`--parallel` flag)
- Default behavior unchanged (sequential mode)
- No data migration required
- Can disable parallel mode via config

## Success Metrics

1. **Throughput**: 3x improvement with 3 parallel PRDs
2. **Safety**: Zero cross-PRD conflicts in testing
3. **Reliability**: 99% completion rate
4. **Adoption**: 50% of users try parallel mode within 1 month
5. **Performance**: <5% coordinator overhead vs direct execution

## Open Questions

1. **Auto-merge vs Manual**: Should completed PRDs auto-merge to main?
   - **Recommendation**: Default=false, configurable per PRD

2. **Priority Queueing**: Support high-priority PRDs?
   - **Recommendation**: FIFO for v1, priority queue in v2

3. **Cross-PRD Dependencies**: How to handle?
   - **Recommendation**: Document as unsupported, use sequential mode

4. **Merge Conflicts**: What if parallel branches conflict on merge?
   - **Recommendation**: Manual resolution required, coordinator alerts

## Timeline Estimate

- **Phase 1**: Foundation (Stories 1-5) - ~5 days
- **Phase 2**: Execution (Stories 6-9) - ~7 days
- **Phase 3**: Dashboard (Stories 10-12) - ~3 days
- **Phase 4**: Safety (Stories 13-15) - ~4 days
- **Phase 5**: Polish (Stories 16-18) - ~3 days

**Total**: ~22 days (sequential), ~15 days (with parallelization)

## Dependencies

### External
- Git (worktree support)
- jq (JSON processing)
- flock (file locking)
- Claude API (rate limits)

### Internal
- `lib/parallel.sh` (story parallelization)
- `lib/worker.sh` (story workers)
- `lib/session-state.sh` (state management)
- `claude-loop.sh` (main loop)

## References

- ADR-003: Parallel PRD Execution Architecture
- Git Worktrees: https://git-scm.com/docs/git-worktree
- File Locking: `man flock`
