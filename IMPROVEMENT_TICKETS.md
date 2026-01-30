# Claude-Loop Improvement Tickets
## Generated from Integration Experience - 2026-01-28

---

## Ticket #1: Process Lock Mechanism to Prevent Duplicates

**Priority:** 🔴 High
**Type:** Bug / Infrastructure
**Status:** Proposed

### Problem
Multiple claude-loop processes can start simultaneously, causing:
- Resource conflicts
- State corruption
- Premature termination
- Undefined behavior

**Evidence:** 4 duplicate processes found (PIDs: 36836, 37203, 87648, 88766) during integration attempt.

### Root Cause
No mechanism to prevent multiple instances from starting:
- No lock file check
- No process ID validation
- No cleanup of stale PIDs

### Proposed Solution

**Implementation:**
```bash
# Add to claude-loop.sh startup
LOCK_FILE=".claude-loop/execution.lock"
PID_FILE=".claude-loop/execution.pid"

acquire_lock() {
    if [ -f "$LOCK_FILE" ]; then
        EXISTING_PID=$(cat "$PID_FILE" 2>/dev/null)
        if [ -n "$EXISTING_PID" ] && ps -p "$EXISTING_PID" > /dev/null 2>&1; then
            echo "ERROR: claude-loop already running (PID: $EXISTING_PID)"
            echo "Stop it first: kill $EXISTING_PID"
            echo "Or force restart: ./claude-loop.sh --force"
            exit 1
        fi
        # Stale lock, clean it up
        rm -f "$LOCK_FILE" "$PID_FILE"
    fi

    echo $$ > "$PID_FILE"
    touch "$LOCK_FILE"
    trap "rm -f '$LOCK_FILE' '$PID_FILE'" EXIT
}

acquire_lock
```

**Test Cases:**
1. ✅ Start first instance - should succeed
2. ✅ Start second instance - should fail with clear message
3. ✅ Kill first instance - lock should cleanup
4. ✅ Start after stale lock - should cleanup and start

**Acceptance Criteria:**
- [ ] Lock file prevents duplicate starts
- [ ] Clear error message when already running
- [ ] Automatic stale lock cleanup
- [ ] Proper cleanup on exit (normal and signal)
- [ ] --force flag to override (with warning)

**Estimated Effort:** 2-4 hours
**Impact:** High (prevents major failure mode)

---

## Ticket #2: Checkpoint and Auto-Resume System

**Priority:** 🔴 High
**Type:** Feature / Reliability
**Status:** Proposed

### Problem
When execution stops (crash, kill, timeout), all progress is lost:
- Must restart from beginning
- Wasted API tokens
- Wasted time
- No recovery path

**Evidence:** Execution stopped after completing US-001. Restart had to redo work.

### Root Cause
No intermediate state persistence:
- Progress only saved at completion
- No checkpoint mechanism
- No resume capability

### Proposed Solution

**Architecture:**
```
.claude-loop/
├── checkpoints/
│   ├── latest.json           # Most recent checkpoint
│   ├── checkpoint-001.json   # After US-001
│   ├── checkpoint-002.json   # After US-002
│   └── ...
└── resume.lock              # Resume in progress
```

**Checkpoint Format:**
```json
{
  "timestamp": "2026-01-28T13:43:00Z",
  "prd_path": "prds/active/claude-loop-integration/prd.json",
  "stories_completed": ["US-001"],
  "current_story": "US-002",
  "iteration": 3,
  "git_commit": "81150dc3f",
  "session_state": {},
  "metrics": {
    "duration_seconds": 900,
    "tokens_used": 125000,
    "stories_per_hour": 1.0
  }
}
```

**Implementation:**
```bash
save_checkpoint() {
    local checkpoint_id=$(date +%s)
    local checkpoint_file=".claude-loop/checkpoints/checkpoint-${checkpoint_id}.json"

    jq -n \
        --arg timestamp "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
        --arg prd "$PRD_FILE" \
        --argjson completed "$(jq '.userStories[] | select(.passes == true) | .id' "$PRD_FILE" | jq -s '.')" \
        --arg current "$(jq -r '.userStories[] | select(.passes == false) | .id' "$PRD_FILE" | head -1)" \
        --arg commit "$(git rev-parse HEAD)" \
        '{
            timestamp: $timestamp,
            prd_path: $prd,
            stories_completed: $completed,
            current_story: $current,
            iteration: 1,
            git_commit: $commit
        }' > "$checkpoint_file"

    ln -sf "$checkpoint_file" ".claude-loop/checkpoints/latest.json"
}

resume_from_checkpoint() {
    local checkpoint=".claude-loop/checkpoints/latest.json"
    if [ ! -f "$checkpoint" ]; then
        return 1
    fi

    echo "Found checkpoint: $(jq -r '.timestamp' "$checkpoint")"
    echo "Completed stories: $(jq -r '.stories_completed | length' "$checkpoint")"
    echo "Resume from: $(jq -r '.current_story' "$checkpoint")"

    # Skip completed stories in iteration logic
    SKIP_STORIES=$(jq -r '.stories_completed[]' "$checkpoint")
}

# In main loop
if [ "$RESUME_MODE" = true ]; then
    resume_from_checkpoint
fi

# After each story completion
save_checkpoint
```

**Acceptance Criteria:**
- [ ] Checkpoint saved after each story completion
- [ ] Checkpoint includes all necessary state
- [ ] --resume flag resumes from latest checkpoint
- [ ] Skips already-completed stories
- [ ] Validates checkpoint integrity
- [ ] Cleans old checkpoints (keep last 10)

**Estimated Effort:** 6-8 hours
**Impact:** Critical (enables recovery from failures)

---

## Ticket #3: Process Watchdog and Health Monitoring

**Priority:** 🟡 Medium
**Type:** Feature / Reliability
**Status:** ✅ IMPLEMENTED

### Problem
No visibility into why processes stop:
- Silent failures
- No health monitoring
- No automatic recovery
- No early warning

**Evidence:** Process stopped around 13:38 PST with no clear error message or reason logged.

### Root Cause
Lack of monitoring infrastructure:
- No heartbeat mechanism
- No resource tracking
- No automatic restart
- No health checks

### Proposed Solution

**Watchdog Script:**
```bash
#!/bin/bash
# watchdog.sh - Monitor claude-loop execution health

INTERVAL=30  # Check every 30 seconds
MAX_FAILURES=3
failures=0

while true; do
    # Check if process exists
    if ! ps -p $(cat .execution-pid) > /dev/null 2>&1; then
        echo "ERROR: Process died unexpectedly at $(date)"

        # Capture last lines of log
        tail -50 execution-main.log >> watchdog-crash-$(date +%s).log

        # Auto-restart if under failure limit
        if [ $failures -lt $MAX_FAILURES ]; then
            echo "Auto-restarting (attempt $((failures + 1))/$MAX_FAILURES)..."
            ./START_EXECUTION.sh --resume
            failures=$((failures + 1))
        else
            echo "Max restart attempts reached. Manual intervention required."
            exit 1
        fi
    else
        # Process alive, check health

        # 1. Check memory usage
        MEM=$(ps -o rss= -p $(cat .execution-pid))
        if [ $MEM -gt 1000000 ]; then  # >1GB
            echo "WARNING: High memory usage: ${MEM}KB"
        fi

        # 2. Check if making progress (file modification time)
        LAST_MOD=$(stat -f %m prds/active/claude-loop-integration/prd.json)
        NOW=$(date +%s)
        IDLE=$((NOW - LAST_MOD))
        if [ $IDLE -gt 1800 ]; then  # 30 min no progress
            echo "WARNING: No progress for ${IDLE}s. May be hung."
        fi

        # 3. Heartbeat - check for recent log activity
        LAST_LOG=$(tail -1 execution-main.log)
        echo "$(date): HEARTBEAT - Process alive, working on: $(get_current_story)"

        failures=0  # Reset failure counter on healthy check
    fi

    sleep $INTERVAL
done
```

**Health Metrics Collection:**
```python
# lib/health-monitor.py
import psutil
import json
import time

class HealthMonitor:
    def __init__(self, pid):
        self.process = psutil.Process(pid)

    def collect_metrics(self):
        return {
            "timestamp": time.time(),
            "cpu_percent": self.process.cpu_percent(),
            "memory_mb": self.process.memory_info().rss / 1024 / 1024,
            "num_threads": self.process.num_threads(),
            "open_files": len(self.process.open_files()),
            "status": self.process.status()
        }

    def is_healthy(self):
        metrics = self.collect_metrics()

        # Check thresholds
        if metrics["memory_mb"] > 2000:  # 2GB
            return False, "Memory exceeded 2GB"
        if metrics["cpu_percent"] > 90:
            return False, "CPU usage over 90%"
        if metrics["open_files"] > 1000:
            return False, "Too many open files"

        return True, "Healthy"
```

**Acceptance Criteria:**
- [ ] Watchdog detects process death within 30s
- [ ] Auto-restart with exponential backoff
- [ ] Health metrics logged every 5 minutes
- [ ] Alert on anomalies (memory, CPU, idle time)
- [ ] Configurable thresholds
- [ ] Max restart attempts configurable

**Estimated Effort:** 8-12 hours
**Impact:** Medium-High (improves observability and recovery)

---

## Ticket #4: Better Error Handling and Logging

**Priority:** 🟡 Medium
**Type:** Improvement / Observability
**Status:** Proposed

### Problem
Insufficient error context:
- No structured error logging
- Missing stack traces
- No error classification
- Hard to debug failures

**Evidence:** Process stops but logs don't show why. No error context captured.

### Root Cause
Basic logging infrastructure:
- Simple echo statements
- No structured format
- No error levels
- No context preservation

### Proposed Solution

**Structured Logging:**
```bash
# lib/logger.sh

LOG_FILE="${LOG_FILE:-.claude-loop/logs/execution.jsonl}"
LOG_LEVEL="${LOG_LEVEL:-INFO}"  # DEBUG, INFO, WARN, ERROR

log() {
    local level=$1
    shift
    local message="$*"

    # Skip if below log level
    case "$LOG_LEVEL" in
        ERROR) [[ "$level" != "ERROR" ]] && return ;;
        WARN)  [[ "$level" =~ ^(DEBUG|INFO)$ ]] && return ;;
        INFO)  [[ "$level" == "DEBUG" ]] && return ;;
    esac

    # Structured JSON log
    jq -n \
        --arg timestamp "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
        --arg level "$level" \
        --arg message "$message" \
        --arg pid "$$" \
        --arg story "${CURRENT_STORY:-unknown}" \
        --arg iteration "${ITERATION:-0}" \
        '{
            timestamp: $timestamp,
            level: $level,
            message: $message,
            context: {
                pid: $pid,
                story: $story,
                iteration: $iteration
            }
        }' >> "$LOG_FILE"

    # Also output to console with colors
    case "$level" in
        ERROR) echo -e "\033[0;31m[ERROR]\033[0m $message" ;;
        WARN)  echo -e "\033[0;33m[WARN]\033[0m $message" ;;
        INFO)  echo -e "\033[0;34m[INFO]\033[0m $message" ;;
        DEBUG) echo -e "\033[0;36m[DEBUG]\033[0m $message" ;;
    esac
}

log_error() { log ERROR "$@"; }
log_warn()  { log WARN "$@"; }
log_info()  { log INFO "$@"; }
log_debug() { log DEBUG "$@"; }
```

**Error Context Capture:**
```bash
# Wrap critical sections with error capture
safe_execute() {
    local description=$1
    shift
    local cmd="$@"

    log_info "Starting: $description"

    if ! eval "$cmd" 2>&1 | tee -a .claude-loop/logs/command-output.log; then
        local exit_code=$?
        log_error "FAILED: $description (exit code: $exit_code)"
        log_error "Command: $cmd"
        log_error "See: .claude-loop/logs/command-output.log"

        # Save context
        save_error_context "$description" "$cmd" "$exit_code"

        return $exit_code
    fi

    log_info "Completed: $description"
}

save_error_context() {
    local desc=$1
    local cmd=$2
    local code=$3
    local context_file=".claude-loop/errors/error-$(date +%s).json"

    jq -n \
        --arg desc "$desc" \
        --arg cmd "$cmd" \
        --arg code "$code" \
        --arg story "$CURRENT_STORY" \
        --arg pwd "$PWD" \
        --arg commit "$(git rev-parse HEAD 2>/dev/null || echo 'N/A')" \
        '{
            timestamp: now | strftime("%Y-%m-%dT%H:%M:%SZ"),
            description: $desc,
            command: $cmd,
            exit_code: $code,
            context: {
                story: $story,
                pwd: $pwd,
                git_commit: $commit
            },
            environment: $ENV,
            last_log_lines: "..."
        }' > "$context_file"

    # Capture last 50 log lines
    tail -50 "$LOG_FILE" >> "$context_file.log"
}
```

**Acceptance Criteria:**
- [ ] All logs in structured JSONL format
- [ ] Log levels: DEBUG, INFO, WARN, ERROR
- [ ] Context preserved (story, iteration, etc.)
- [ ] Error context automatically captured
- [ ] Stack traces for exceptions
- [ ] Easy to parse and analyze

**Estimated Effort:** 6-8 hours
**Impact:** Medium (improves debugging significantly)

---

## Ticket #5: Resource Limits and Throttling

**Priority:** 🟢 Low
**Type:** Feature / Stability
**Status:** Proposed

### Problem
No resource management:
- Unlimited API calls
- No rate limiting
- No memory limits
- Can exhaust resources

### Proposed Solution

**API Rate Limiting:**
```bash
# lib/rate-limiter.sh

RATE_LIMIT=10  # Max calls per minute
LAST_CALL_TIME=()

rate_limit() {
    local now=$(date +%s)

    # Remove calls older than 60s
    LAST_CALL_TIME=("${LAST_CALL_TIME[@]/#*/}")
    local recent=0
    for t in "${LAST_CALL_TIME[@]}"; do
        if [ $((now - t)) -lt 60 ]; then
            recent=$((recent + 1))
        fi
    done

    # Wait if at limit
    if [ $recent -ge $RATE_LIMIT ]; then
        local wait_time=$((60 - (now - ${LAST_CALL_TIME[0]})))
        echo "Rate limit reached. Waiting ${wait_time}s..."
        sleep $wait_time
    fi

    LAST_CALL_TIME+=($now)
}

# Before each API call
rate_limit
call_claude_api ...
```

**Memory Monitoring:**
```bash
check_memory() {
    local mem=$(ps -o rss= -p $$)
    local limit=$((2 * 1024 * 1024))  # 2GB in KB

    if [ $mem -gt $limit ]; then
        log_error "Memory limit exceeded: ${mem}KB > ${limit}KB"
        log_error "Triggering graceful shutdown..."
        save_checkpoint
        exit 1
    fi
}

# Check every iteration
check_memory
```

**Acceptance Criteria:**
- [ ] API calls rate-limited (configurable)
- [ ] Memory usage monitored
- [ ] Graceful shutdown on resource exhaustion
- [ ] Token budget tracking
- [ ] Cost estimation and limits

**Estimated Effort:** 4-6 hours
**Impact:** Low-Medium (prevents resource exhaustion)

---

## Summary of Tickets

| # | Title | Priority | Effort | Impact |
|---|-------|----------|--------|--------|
| 1 | Process Lock Mechanism | 🔴 High | 2-4h | High |
| 2 | Checkpoint and Auto-Resume | 🔴 High | 6-8h | Critical |
| 3 | Process Watchdog | 🟡 Medium | 8-12h | Med-High |
| 4 | Better Error Logging | 🟡 Medium | 6-8h | Medium |
| 5 | Resource Limits | 🟢 Low | 4-6h | Low-Med |

**Total Estimated Effort:** 26-38 hours
**Recommended Priority Order:** #1 → #2 → #4 → #3 → #5

---

## Implementation Notes

### Quick Wins (Implement First)
1. **Process Lock** (#1) - Prevents immediate failure mode
2. **Checkpoint System** (#2) - Enables recovery

### Nice to Have (Can Wait)
3. **Watchdog** (#3) - Improves reliability
4. **Logging** (#4) - Improves debugging
5. **Resource Limits** (#5) - Prevents edge cases

### Testing Strategy
- Unit tests for each component
- Integration tests for full flow
- Chaos testing (kill process at random points)
- Long-running stability tests (24+ hours)

---

## Ticket #6: Non-Interactive Mode Session Prompt Hang

**Priority:** 🔴 High
**Type:** Bug
**Status:** Identified

### Problem
Process hangs in non-interactive mode when resuming from crash:
- `init_or_resume_session()` calls `prompt_recovery_confirmation()`
- Prompt waits for user input even when `NON_INTERACTIVE=true`
- Process stuck indefinitely, no timeout

**Evidence:** Process stopped at "Agents: Enabled" message during integration execution (2026-01-28 23:20 PST).

### Root Cause
Session state module (`lib/session-state.sh`) doesn't respect non-interactive mode:
- `prompt_recovery_confirmation()` unconditionally calls `read`
- No fallback behavior for automated execution
- `--no-session` flag doesn't fully disable session features

### Proposed Solution

**Option 1: Auto-answer prompts in non-interactive mode**
```bash
prompt_recovery_confirmation() {
    if $NON_INTERACTIVE; then
        # Auto-resume in non-interactive mode
        log_info "Non-interactive mode: Auto-resuming from checkpoint"
        return 0
    fi

    # Normal interactive prompt
    read -p "Resume from checkpoint? [Y/n] " response
    [[ "$response" =~ ^[Yy]?$ ]]
}
```

**Option 2: Add timeout to all read operations**
```bash
if ! read -t 10 -p "Resume? [Y/n] " response; then
    log_warn "Prompt timeout, defaulting to resume"
    return 0
fi
```

**Option 3: Fully disable session state with --no-session**
```bash
# Ensure --no-session actually disables all session features
if [ "$NO_SESSION" = true ]; then
    SESSION_STATE_ENABLED=false
    export SESSION_STATE_ENABLED
fi
```

**Acceptance Criteria:**
- [ ] Non-interactive mode never blocks on user input
- [ ] All prompts have reasonable defaults
- [ ] Timeout on read operations (10s max)
- [ ] `--no-session` fully disables session state
- [ ] Tested in background execution (nohup, daemon)

**Estimated Effort:** 2-3 hours
**Impact:** Critical (blocks autonomous execution)

---

**Generated:** 2026-01-28 23:25 PST
**Source:** Claude-loop integration experience
**Experience Domain:** integration:devops:automation
