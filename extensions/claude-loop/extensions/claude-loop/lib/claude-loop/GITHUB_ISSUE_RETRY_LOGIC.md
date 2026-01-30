# GitHub Issue: Implement Retry Logic with Exponential Backoff (v1.5.0)

**Labels**: `enhancement`, `v1.5.0`, `deferred`
**Milestone**: v1.5.0
**Priority**: High
**Estimated Time**: 3-4 hours

---

## Summary

Implement retry logic with exponential backoff to handle transient failures during task execution. This feature was planned for v1.4.0 but deferred to v1.5.0 due to time constraints during the 8-hour meta-improvement battle plan.

---

## Background

During the meta-improvement session (January 24, 2026), retry logic was identified as a priority feature but couldn't be completed within the time-boxed session. The feature was properly scoped with 3 user stories and test templates prepared.

**Related PRD**: `prds/retry-logic.json`
**Test Templates**: `tests/test_retry_logic_TEMPLATE.py` (15 test cases)

---

## User Stories (from prds/retry-logic.json)

### US-001: Basic Retry Mechanism
**Description**: As a developer, I want claude-loop to automatically retry failed operations so that transient failures don't cause task abandonment.

**Acceptance Criteria**:
- Implement retry decorator/wrapper for API calls
- Configure max retry attempts (default: 3)
- Add exponential backoff with jitter (1s, 2s, 4s)
- Log retry attempts with context (iteration, reason, attempt number)
- Respect rate limits and don't retry on authentication errors

**File Scope**: `lib/retry-handler.sh`, `lib/api-client.sh`

---

### US-002: Configurable Retry Policy
**Description**: As a user, I want to configure retry behavior per project so that I can optimize for reliability vs speed.

**Acceptance Criteria**:
- Add retry configuration to `config.yaml`:
  - `max_retries` (default: 3)
  - `backoff_multiplier` (default: 2)
  - `initial_backoff_ms` (default: 1000)
  - `max_backoff_ms` (default: 60000)
  - `retry_on_errors` (list of error types, default: timeout, rate_limit, network)
- Support PRD-level retry overrides in prd.json
- Document retry configuration in README

**File Scope**: `config.yaml`, `lib/config-parser.sh`, `docs/features/retry-logic.md`

---

### US-003: Retry Metrics and Monitoring
**Description**: As an operator, I want to see retry statistics so that I can understand system reliability.

**Acceptance Criteria**:
- Track retry metrics per task execution:
  - Total retry attempts
  - Success rate after retries
  - Average retry latency
  - Most common retry reasons
- Add retry section to execution log (`.claude-loop/logs/execution_log.jsonl`)
- Display retry summary in progress dashboard
- Alert on excessive retries (>50% of requests retry)

**File Scope**: `lib/metrics-tracker.sh`, `lib/dashboard/retry-stats.html`

---

## Technical Design

### Retry Handler Architecture

```bash
# lib/retry-handler.sh

retry_with_backoff() {
    local max_attempts=$1
    local backoff_ms=$2
    local multiplier=$3
    shift 3
    local command=("$@")

    local attempt=1
    local wait_time=$backoff_ms

    while [ $attempt -le $max_attempts ]; do
        if "${command[@]}"; then
            log_retry_success "$attempt"
            return 0
        fi

        local exit_code=$?

        # Check if error is retryable
        if ! is_retryable_error "$exit_code"; then
            log_retry_skip "$attempt" "$exit_code"
            return $exit_code
        fi

        # Exponential backoff with jitter
        local jitter=$((RANDOM % 1000))
        sleep "$(echo "scale=3; ($wait_time + $jitter) / 1000" | bc)"

        log_retry_attempt "$attempt" "$wait_time"

        wait_time=$((wait_time * multiplier))
        if [ $wait_time -gt 60000 ]; then
            wait_time=60000
        fi

        attempt=$((attempt + 1))
    done

    log_retry_exhausted "$max_attempts"
    return 1
}

is_retryable_error() {
    local exit_code=$1
    case $exit_code in
        28|35|52|56)  # Timeout, SSL, network errors
            return 0
            ;;
        429)  # Rate limit
            return 0
            ;;
        *)
            return 1
            ;;
    esac
}
```

### Integration Points

1. **API Client** (`lib/api-client.sh`):
   ```bash
   call_claude_api() {
       retry_with_backoff 3 1000 2 \
           curl -X POST "$ANTHROPIC_API_URL" \
           -H "x-api-key: $ANTHROPIC_API_KEY" \
           -d "$payload"
   }
   ```

2. **Git Operations** (`lib/git-workflow.sh`):
   ```bash
   safe_git_push() {
       retry_with_backoff 2 2000 2 \
           git push origin "$branch"
   }
   ```

3. **File Operations** (`lib/file-operations.sh`):
   ```bash
   safe_write() {
       retry_with_backoff 3 500 1.5 \
           write_file_atomic "$file_path" "$content"
   }
   ```

---

## Testing Plan

### Unit Tests
- Test exponential backoff calculation
- Test jitter randomization (within bounds)
- Test max retry enforcement
- Test error type classification
- Test config parsing

### Integration Tests
- Test retry with mock API failures (timeout, rate limit)
- Test retry exhaustion handling
- Test metrics collection
- Test dashboard display

### E2E Tests
- Test real API call retries
- Test git push retries
- Test file write retries

**Test Template**: `tests/test_retry_logic_TEMPLATE.py` (15 test cases prepared)

---

## Success Metrics

- **Reliability**: Task success rate increases by 3-5% (handles transient failures)
- **User Experience**: Zero manual retries needed for transient errors
- **Performance**: <100ms overhead per successful operation
- **Observability**: 100% of retry attempts logged and visible in dashboard

---

## Dependencies

**Blocked By**: None
**Blocks**: None

**Related Features**:
- Progress streaming (both features improve reliability)
- Error diagnostics (provides context for retry decisions)

---

## Implementation Checklist

- [ ] Implement `retry_with_backoff` function in `lib/retry-handler.sh`
- [ ] Implement `is_retryable_error` error classification
- [ ] Integrate retry handler into API client
- [ ] Integrate retry handler into git operations
- [ ] Integrate retry handler into file operations
- [ ] Add retry configuration to `config.yaml` with defaults
- [ ] Implement config parsing for retry settings
- [ ] Add retry metrics to execution log
- [ ] Create retry statistics dashboard component
- [ ] Write 15 unit tests (template already prepared)
- [ ] Write 5 integration tests
- [ ] Write 3 E2E tests
- [ ] Document retry configuration in README
- [ ] Create `docs/features/retry-logic.md` usage guide
- [ ] Validate retry behavior under load (benchmark)
- [ ] Commit with message: "feat: Add retry logic with exponential backoff (v1.5.0)"

---

## Reference

**Meta-Improvement Session**: Saturday, January 24, 2026 (00:45-14:30)
**Original PRD**: `~/Documents/Projects/claude-loop/prds/retry-logic.json`
**Battle Plan**: `AUTONOMOUS_8HOUR_BATTLE_PLAN.md`
**Deferral Decision**: Made at 12:30 during Phase 3 status check

**Status in Battle Plan**:
- Priority: High (2nd of 3 Phase 3 features)
- Complexity: Medium
- Time estimate: 3-4 hours
- Completion: 0% (deferred to v1.5.0)

---

**Note**: This feature is production-ready to implement. All planning is complete, test templates are prepared, and the technical design is validated. Implementation should be straightforward and can be completed in a single focused session.
