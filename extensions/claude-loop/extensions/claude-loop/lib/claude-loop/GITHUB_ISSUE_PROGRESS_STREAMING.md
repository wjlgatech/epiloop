# GitHub Issue: Implement Real-Time Progress Streaming (v1.5.0)

**Labels**: `enhancement`, `v1.5.0`, `deferred`, `ux`
**Milestone**: v1.5.0
**Priority**: Medium
**Estimated Time**: 2-3 hours

---

## Summary

Implement real-time progress streaming to provide live updates during task execution, improving user experience and enabling better monitoring. This feature was planned for v1.4.0 but deferred to v1.5.0 due to time constraints during the 8-hour meta-improvement battle plan.

---

## Background

During the meta-improvement session (January 24, 2026), progress streaming was identified as a valuable UX enhancement but couldn't be completed within the time-boxed session. The feature was properly scoped with 3 user stories and test templates prepared.

**Related PRD**: `prds/progress-streaming.json`
**Test Templates**: `tests/test_progress_streaming_TEMPLATE.py` (14 test cases)

---

## User Stories (from prds/progress-streaming.json)

### US-001: Server-Sent Events (SSE) Infrastructure
**Description**: As a developer, I want an SSE endpoint so that clients can receive real-time progress updates without polling.

**Acceptance Criteria**:
- Implement SSE server using Flask-SSE or custom implementation
- Create `/stream/progress` endpoint that emits events
- Support multiple concurrent client connections
- Handle client disconnections gracefully
- Implement reconnection logic with last-event-id support
- Use JSON format for events with event type and data fields

**File Scope**: `lib/streaming-server.py`, `lib/event-emitter.py`

---

### US-002: Progress Event Emission
**Description**: As a user, I want to see real-time progress updates so that I know what's happening during execution.

**Acceptance Criteria**:
- Emit progress events for key milestones:
  - Task started (with PRD details)
  - Story started (with US-ID and acceptance criteria)
  - Acceptance criterion completed (with index and text)
  - Story completed (with pass/fail status)
  - Task completed (with summary stats)
  - Error occurred (with error type and message)
- Include timestamps and unique event IDs
- Rate-limit events (max 10/second to avoid overwhelming clients)
- Buffer events if no clients connected (keep last 100)
- Integrate with existing execution logger

**File Scope**: `lib/progress-emitter.sh`, `lib/execution-logger.sh`

---

### US-003: CLI and Dashboard Integration
**Description**: As a user, I want to see progress updates in both CLI and dashboard so that I can monitor from anywhere.

**Acceptance Criteria**:
- **CLI Mode**:
  - Add `--stream` flag to enable real-time progress display
  - Use Unicode box-drawing characters for visual progress
  - Update progress in-place (no scroll spam)
  - Show: current story, AC checklist, elapsed time, estimated remaining
- **Dashboard Mode**:
  - Add real-time progress panel to dashboard
  - Subscribe to SSE stream on page load
  - Update UI reactively as events arrive
  - Show live AC checklist with checkmarks
  - Display progress bar with percentage
- Gracefully degrade if streaming unavailable (fall back to polling)

**File Scope**: `lib/progress-display.sh`, `lib/dashboard/progress-panel.html`, `lib/dashboard/stream-client.js`

---

## Technical Design

### SSE Server Architecture

```python
# lib/streaming-server.py

from flask import Flask, Response
import json
import queue
import threading

app = Flask(__name__)
event_queues = []

def emit_event(event_type, data):
    """Emit event to all connected clients"""
    event = {
        'event': event_type,
        'data': data,
        'timestamp': time.time(),
        'id': str(uuid.uuid4())
    }

    # Add to all client queues
    for q in event_queues:
        try:
            q.put_nowait(event)
        except queue.Full:
            pass  # Drop event if queue full

@app.route('/stream/progress')
def stream_progress():
    def generate():
        q = queue.Queue(maxsize=100)
        event_queues.append(q)

        try:
            while True:
                event = q.get()
                yield f"event: {event['event']}\n"
                yield f"data: {json.dumps(event['data'])}\n"
                yield f"id: {event['id']}\n\n"
        finally:
            event_queues.remove(q)

    return Response(generate(), mimetype='text/event-stream')
```

### Event Emission Integration

```bash
# lib/progress-emitter.sh

emit_progress_event() {
    local event_type=$1
    local data=$2

    # Send to Python SSE server
    curl -X POST http://localhost:5000/emit \
        -H "Content-Type: application/json" \
        -d "{\"type\":\"$event_type\",\"data\":$data}" \
        2>/dev/null &
}

# Hook into execution logger
log_story_start() {
    local story_id=$1
    local story_data=$2

    # Existing logging
    echo "[$story_id] Starting..." >> progress.txt

    # New: Emit progress event
    emit_progress_event "story_started" "$story_data"
}
```

### CLI Display

```bash
# lib/progress-display.sh

render_progress() {
    local current_story=$1
    local completed_acs=$2
    local total_acs=$3

    # Clear screen and move cursor to top
    tput clear

    echo "╔════════════════════════════════════════════╗"
    echo "║ Current Story: $current_story"
    echo "║"
    echo "║ Progress: [$(progress_bar $completed_acs $total_acs)] $completed_acs/$total_acs"
    echo "║"
    echo "║ Acceptance Criteria:"

    for ac in "${acs[@]}"; do
        if [ "${ac_status[$ac]}" == "complete" ]; then
            echo "║   ✅ $ac"
        elif [ "${ac_status[$ac]}" == "in_progress" ]; then
            echo "║   ⏳ $ac"
        else
            echo "║   ○ $ac"
        fi
    done

    echo "╚════════════════════════════════════════════╝"
}
```

---

## Event Types

### Core Events

1. **task_started**
   ```json
   {
     "task_id": "PRD-001",
     "task_name": "User Authentication",
     "story_count": 5,
     "estimated_duration": 1800
   }
   ```

2. **story_started**
   ```json
   {
     "story_id": "US-003",
     "title": "Implement login endpoint",
     "ac_count": 4,
     "priority": 1
   }
   ```

3. **ac_completed**
   ```json
   {
     "story_id": "US-003",
     "ac_index": 2,
     "ac_text": "Validate email format",
     "duration_ms": 5230
   }
   ```

4. **story_completed**
   ```json
   {
     "story_id": "US-003",
     "status": "passed",
     "duration_ms": 18450,
     "commits": ["a1b2c3d"]
   }
   ```

5. **error_occurred**
   ```json
   {
     "story_id": "US-003",
     "error_type": "timeout",
     "error_message": "API call timed out after 30s",
     "retryable": true
   }
   ```

---

## Testing Plan

### Unit Tests
- Test SSE server connection handling
- Test event emission and queuing
- Test rate limiting (max 10/second)
- Test event buffer management
- Test CLI progress rendering

### Integration Tests
- Test end-to-end event flow (emitter → server → client)
- Test multiple concurrent clients
- Test client reconnection
- Test dashboard real-time updates
- Test graceful degradation (streaming → polling)

### E2E Tests
- Test full task execution with live streaming
- Test CLI `--stream` mode
- Test dashboard progress panel

**Test Template**: `tests/test_progress_streaming_TEMPLATE.py` (14 test cases prepared)

---

## Success Metrics

- **User Experience**: Users can see live progress without refreshing/polling
- **Performance**: <10ms latency from event emission to client receipt
- **Reliability**: 99%+ event delivery rate
- **Adoption**: 50%+ of users enable `--stream` flag within 1 month

---

## Dependencies

**Blocked By**: None
**Blocks**: None

**Required**: Python Flask-SSE (or equivalent)

**Related Features**:
- Retry logic (both features improve UX during execution)
- Progress dashboard (streaming enhances existing dashboard)

---

## Implementation Checklist

- [ ] Implement SSE server in `lib/streaming-server.py`
- [ ] Implement event emitter in `lib/event-emitter.py`
- [ ] Create `/stream/progress` endpoint
- [ ] Integrate event emission into execution logger
- [ ] Implement CLI `--stream` flag
- [ ] Create CLI progress display renderer
- [ ] Create dashboard progress panel HTML/CSS
- [ ] Implement dashboard SSE client JavaScript
- [ ] Add event rate limiting (10/second)
- [ ] Add event buffer (last 100 events)
- [ ] Write 14 unit tests (template already prepared)
- [ ] Write 5 integration tests
- [ ] Write 3 E2E tests
- [ ] Document `--stream` flag in README
- [ ] Create `docs/features/progress-streaming.md` usage guide
- [ ] Test with multiple concurrent clients (load test)
- [ ] Commit with message: "feat: Add real-time progress streaming (v1.5.0)"

---

## UI Mockups

### CLI Stream Mode

```
╔══════════════════════════════════════════════════════════════╗
║ Task: User Authentication                                    ║
║ Progress: [█████████░░░] 5/8 stories                        ║
╠══════════════════════════════════════════════════════════════╣
║                                                              ║
║ Current Story: US-003 - Implement login endpoint            ║
║ Time: 2m 34s elapsed | ~3m remaining                        ║
║                                                              ║
║ Acceptance Criteria:                                         ║
║   ✅ Create POST /api/auth/login endpoint                   ║
║   ✅ Validate email format                                   ║
║   ✅ Hash password with bcrypt                               ║
║   ⏳ Generate JWT token                                      ║
║   ○ Return user profile with token                          ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝
```

### Dashboard Panel

```
┌─────────────────────────────────────┐
│ Live Progress                       │
├─────────────────────────────────────┤
│ Story: US-003                       │
│ [████████░░░░] 65%                  │
│                                     │
│ ✅ Create POST endpoint             │
│ ✅ Validate email                   │
│ ✅ Hash password                    │
│ ⏳ Generate JWT                     │
│ ○ Return profile                    │
│                                     │
│ 2m 34s elapsed | ~1m 30s remaining  │
└─────────────────────────────────────┘
```

---

## Reference

**Meta-Improvement Session**: Saturday, January 24, 2026 (00:45-14:30)
**Original PRD**: `~/Documents/Projects/claude-loop/prds/progress-streaming.json`
**Battle Plan**: `AUTONOMOUS_8HOUR_BATTLE_PLAN.md`
**Deferral Decision**: Made at 12:30 during Phase 3 status check

**Status in Battle Plan**:
- Priority: Medium (3rd of 3 Phase 3 features)
- Complexity: Medium
- Time estimate: 2-3 hours
- Completion: 0% (deferred to v1.5.0)

---

**Note**: This feature significantly improves user experience by making execution feel more responsive and transparent. Implementation is straightforward with Flask-SSE, and all planning/testing is already complete.
