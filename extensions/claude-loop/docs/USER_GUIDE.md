# Autonomous Coding with Claude-Loop

Complete guide to using autonomous coding features in Epiloop via the claude-loop integration.

## Overview

The claude-loop integration enables Epiloop to autonomously implement software features from natural language descriptions. Simply describe what you want built, and the system will:

1. Generate a detailed Product Requirements Document (PRD)
2. Execute implementation using Reality-Grounded Test Driven Development (RG-TDD)
3. Run quality gates (tests, type checking, linting, security)
4. Report progress in real-time
5. Learn from failures to improve over time

## Quick Start

### Basic Usage

Start an autonomous coding session from any Epiloop channel (WhatsApp, Telegram, etc.):

```
/autonomous-coding start "Add user authentication with JWT tokens"
```

The system will:
- Generate a PRD with user stories
- Execute each story using TDD
- Report progress as it works
- Complete with passing quality gates

### Monitor Progress

Check status of running sessions:

```
/autonomous-coding status
```

View detailed progress for a specific session:

```
/autonomous-coding status --session <session-id>
```

### Pause and Resume

Pause a running session:

```
/autonomous-coding pause --session <session-id>
```

Resume a paused session:

```
/autonomous-coding resume --session <session-id>
```

### Stop Execution

Gracefully stop a session:

```
/autonomous-coding stop --session <session-id>
```

Force stop immediately:

```
/autonomous-coding stop --session <session-id> --force
```

## Advanced Features

### Custom PRDs

Provide your own PRD instead of auto-generating:

```
/autonomous-coding start --prd ./my-feature.json
```

PRD format example:

```json
{
  "title": "User Authentication",
  "epic": "Security Features",
  "stories": [
    {
      "id": "US-001",
      "title": "Implement JWT token generation",
      "description": "Create utility functions for generating and validating JWT tokens",
      "acceptanceCriteria": [
        "Tests written FIRST (RED phase)",
        "Function generates valid JWT with user payload",
        "Function validates token signature",
        "Handles expired tokens gracefully"
      ],
      "priority": 1,
      "estimatedComplexity": "medium"
    }
  ],
  "technical_architecture": {
    "components": ["auth-service", "token-utils"],
    "data_flow": "User credentials -> Auth service -> JWT token",
    "integration_points": ["User API", "Database"]
  },
  "testing_strategy": {
    "unit_tests": ["token generation", "token validation"],
    "integration_tests": ["auth flow end-to-end"],
    "coverage_requirements": { "minimum": 80 }
  }
}
```

### Parallel Execution

Run multiple autonomous coding tasks in parallel:

```
/autonomous-coding start "Feature A" &
/autonomous-coding start "Feature B" &
/autonomous-coding start "Feature C" &
```

System enforces resource limits (default: 3 concurrent tasks).

### Quality Gate Configuration

Customize quality gates via configuration file `~/.epiloop/config/autonomous-coding.json`:

```json
{
  "qualityGates": {
    "requireTests": true,
    "requireTypecheck": true,
    "requireLint": true,
    "minCoverage": 75,
    "securityScan": true
  },
  "execution": {
    "maxConcurrent": 3,
    "timeout": 3600000,
    "maxMemoryPerTask": 512
  }
}
```

### Experience Store Integration

The system learns from past implementations:

```
/autonomous-coding experience search "authentication"
```

Store custom experiences:

```
/autonomous-coding experience add \
  --problem "JWT token refresh" \
  --solution "Use refresh token rotation with Redis" \
  --domain "security"
```

### Progress Visualization (iOS/macOS)

On iOS and macOS devices, autonomous coding progress appears in the Canvas interface with:

- Real-time story grid showing completion status
- Progress bars for current story
- Interactive controls (pause/resume/abort)
- Expandable logs panel
- File diff viewer

## Best Practices

### 1. Write Clear Feature Descriptions

Good:
```
Add user authentication with email/password login, JWT tokens for sessions,
password hashing with bcrypt, and refresh token rotation for security
```

Better:
```
Implement user authentication system:
- Email/password login with validation
- JWT access tokens (15min expiry)
- Refresh tokens (7 day expiry) with rotation
- Password hashing using bcrypt (12 rounds)
- Rate limiting on login attempts
- Session management in Redis
```

### 2. Start Small

Begin with single, well-defined features before attempting complex multi-component systems.

### 3. Monitor First Execution

Watch the first autonomous execution for your codebase to understand patterns and timing.

### 4. Review Generated PRDs

Check auto-generated PRDs before execution:

```
/autonomous-coding prd-only "My feature description"
```

Edit and then execute:

```
/autonomous-coding start --prd ./reviewed-prd.json
```

### 5. Use Experience Store

Contribute successful implementations to the experience store:

```
/autonomous-coding experience feedback <experience-id> --helpful
```

### 6. Check Metrics

Review periodic metrics to understand system performance:

```
/autonomous-coding metrics --period monthly
```

## Common Workflows

### Workflow 1: Simple Feature Addition

```bash
# Generate and execute
/autonomous-coding start "Add dark mode toggle to settings"

# Monitor
/autonomous-coding status

# Review results
git diff
npm test
```

### Workflow 2: Complex Multi-Story Feature

```bash
# Generate PRD first
/autonomous-coding prd-only "Implement search with filters, pagination, and sorting"

# Review and edit PRD
vim ./generated-prd.json

# Execute with custom PRD
/autonomous-coding start --prd ./generated-prd.json

# Monitor progress
watch -n 5 '/autonomous-coding status --session <id>'
```

### Workflow 3: Parallel Development

```bash
# Start multiple features
/autonomous-coding start "Feature A" --background
/autonomous-coding start "Feature B" --background
/autonomous-coding start "Feature C" --background

# List all sessions
/autonomous-coding list

# Check aggregate status
/autonomous-coding status --all
```

## Troubleshooting

### Session Hangs or Timeout

Check logs:
```bash
tail -f ~/.epiloop/logs/claude-loop/<session-id>.log
```

Increase timeout in config:
```json
{
  "execution": {
    "timeout": 7200000
  }
}
```

### Quality Gates Fail

Review failure details:
```bash
/autonomous-coding status --session <id> --verbose
```

Common fixes:
- Increase test timeout
- Fix linting rules
- Update TypeScript config

### Out of Memory

Reduce concurrent tasks:
```json
{
  "execution": {
    "maxConcurrent": 2,
    "maxMemoryPerTask": 1024
  }
}
```

### Claude API Rate Limits

System automatically handles rate limits with exponential backoff. If persistent:
- Reduce parallel executions
- Implement longer delays between requests
- Consider upgrading API tier

## Integration Examples

### WhatsApp

```
User: /autonomous-coding start "Add push notifications"
Bot: 🚀 Starting autonomous coding session...
     Session ID: session-abc123
     PRD: 5 stories identified
     Estimated: 45-60 minutes

[15 minutes later]

Bot: 📊 Progress Update (session-abc123)
     ✅ US-001: Push notification service setup
     ✅ US-002: Firebase integration
     ⏳ US-003: Notification templates (60%)
     ⏹ US-004: User preferences
     ⏹ US-005: Testing & documentation
```

### Telegram

Use inline buttons for interactive control:

```
Bot: 🔄 Autonomous Coding Progress

     Stories: 3/5 complete (60%)
     Time: 23 minutes elapsed

     [⏸ Pause] [📊 Details] [⏹ Stop]
```

### CLI

```bash
$ epiloop autonomous-coding start "Add rate limiting"

🚀 Starting autonomous coding session...
Session ID: session-xyz789
PRD generated: 3 stories

⏳ US-001: Rate limiter middleware... ████████░░ 80%
✅ US-002: Redis integration
⏹ US-003: Tests & documentation

Estimated completion: 15 minutes
```

## API Reference

See [API.md](./API.md) for complete API documentation.

## Configuration Reference

See [CONFIGURATION.md](./CONFIGURATION.md) for all configuration options.

## Architecture

See [ARCHITECTURE.md](./ARCHITECTURE.md) for system architecture details.

## Support

- Issues: https://github.com/epiloop/epiloop/issues
- Docs: https://docs.clawd.bot
- Discord: https://discord.gg/epiloop
