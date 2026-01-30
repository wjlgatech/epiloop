# Autonomous Coding Skill

Autonomous feature implementation with Reality-Grounded Test Driven Development.

## Commands

### `/autonomous-coding start`

Start autonomous feature implementation.

**Usage:**
```
/autonomous-coding start <feature description>
```

**Examples:**
```
/autonomous-coding start Add user authentication with JWT tokens
/autonomous-coding start Implement dark mode toggle in settings
/autonomous-coding start Create factorial function with tests
```

**Parameters:**
- `feature description` (required): Natural language description of the feature to implement

**Response:**
- Session ID for tracking progress
- Generated PRD preview
- Estimated completion time

---

### `/autonomous-coding status`

Check status of autonomous coding session.

**Usage:**
```
/autonomous-coding status [--session <session-id>]
```

**Examples:**
```
/autonomous-coding status
/autonomous-coding status --session 429ef59f-4528-4c88-bc5d-fbec1105acab
```

**Parameters:**
- `--session <id>` (optional): Specific session ID. If omitted, shows status of your most recent session.

**Response:**
- Session status (running/completed/failed)
- Progress percentage
- Current story being implemented
- Completed stories count

---

### `/autonomous-coding list`

List all your autonomous coding sessions.

**Usage:**
```
/autonomous-coding list
```

**Response:**
- List of all sessions with status
- Session IDs for reference
- Start times and durations

---

### `/autonomous-coding stop`

Stop a running autonomous coding session.

**Usage:**
```
/autonomous-coding stop --session <session-id>
```

**Examples:**
```
/autonomous-coding stop --session 429ef59f-4528-4c88-bc5d-fbec1105acab
```

**Parameters:**
- `--session <id>` (required): Session ID to stop

**Response:**
- Confirmation of session stopped
- Checkpoint saved for potential resume

---

### `/autonomous-coding resume`

Resume a stopped autonomous coding session from checkpoint.

**Usage:**
```
/autonomous-coding resume --session <session-id>
```

**Parameters:**
- `--session <id>` (required): Session ID to resume

**Response:**
- Confirmation of session resumed
- Current story and progress

---

## Configuration

Configuration file: `~/.epiloop/config/autonomous-coding.json`

See [CONFIGURATION.md](./docs/CONFIGURATION.md) for all options.

## Quality Gates

Every implementation runs through quality gates:
- ✅ Tests pass (75%+ coverage required)
- ✅ Type checking (no TypeScript errors)
- ✅ Linting (code style validation)
- ✅ Security scan (no vulnerabilities)

## Progress Notifications

You'll receive real-time progress updates:
- 📊 Story progress percentages
- ✅ Story completions
- ❌ Quality gate failures
- 🎉 Final completion

## Examples

### Simple Feature
```
User: /autonomous-coding start Add a function to calculate fibonacci numbers

Bot: 🚀 Starting autonomous implementation...
     Session ID: abc-123
     PRD: 2 stories identified

     ✅ US-001: Create fibonacci function (COMPLETE)
     ⏳ US-002: Add test coverage (60%)

     Progress: 80%
```

### Complex Feature
```
User: /autonomous-coding start Implement user authentication with JWT tokens and refresh

Bot: 🚀 Starting autonomous implementation...
     Session ID: def-456
     PRD: 5 stories identified

     This will take approximately 45-60 minutes

     ✅ US-001: JWT token generation
     ✅ US-002: Token validation middleware
     ✅ US-003: Refresh token rotation
     ⏳ US-004: Login endpoint (40%)
     ⏹ US-005: Tests & documentation

     Progress: 60%
```

### Check Status
```
User: /autonomous-coding status

Bot: 📊 Session: def-456
     Status: Running
     Progress: 80%

     Current: US-004 Login endpoint
     Completed: 4/5 stories
     Elapsed: 32 minutes
```

## Limitations

- Maximum 3 concurrent sessions per user
- 1 hour timeout per session (configurable)
- Requires ANTHROPIC_API_KEY for PRD generation
- Works best with well-defined features

## Support

- Documentation: See [USER_GUIDE.md](./docs/USER_GUIDE.md)
- Architecture: See [ARCHITECTURE.md](./docs/ARCHITECTURE.md)
- Issues: Report at project repository
