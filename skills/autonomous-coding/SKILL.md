---
name: autonomous-coding
description: "Request autonomous feature implementations using claude-loop. Describe what you want built and the system will generate a PRD, implement it with TDD, run quality gates, and deliver working code."
---

# Autonomous Coding Skill

Use claude-loop to autonomously implement features through conversational requests. Just describe what you want built, and the system handles everything: PRD generation, TDD implementation, quality gates, and delivery.

## Starting an Implementation

Request a feature implementation:
```
Start building a user authentication system with login, signup, and password reset
```

Or be more specific:
```
Start implementing a search feature that:
- Searches across titles and content
- Supports filters by date and category
- Returns results with pagination
- Includes tests with >80% coverage
```

The system will:
1. Generate a structured PRD with user stories
2. Show you a preview for confirmation
3. Start autonomous implementation in the background
4. Send you progress updates as stories complete
5. Notify you when done with PR link and test results

## Checking Progress

Check status of your current implementation:
```
What's the status of my autonomous coding session?
```

Or for a specific session:
```
Status for session abc-123
```

You'll get:
- Current story being worked on
- Progress percentage
- Completed vs total stories
- Estimated time remaining

## Stopping Execution

Stop your current implementation:
```
Stop my autonomous coding session
```

This will:
- Gracefully stop the executor
- Save a checkpoint
- Allow you to resume later

## Resuming from Checkpoint

Resume a stopped implementation:
```
Resume my autonomous coding session
```

This continues from where it left off, skipping already-completed stories.

## Listing Sessions

See all your sessions:
```
List my autonomous coding sessions
```

Shows:
- Session IDs
- Descriptions
- Start times
- Current status (running/stopped/completed)

## Verbosity Levels

Control how much detail you get in updates:

**Minimal** (just essentials):
```
Start building auth system (minimal updates)
```

**Normal** (default, balanced):
```
Start building auth system
```

**Detailed** (everything):
```
Start building auth system (detailed updates)
```

## Providing Codebase Context

Help the system understand your project:
```
Start adding a comment system to my blog
Context: TypeScript, React, uses Prisma for database, has vitest for tests
```

This improves:
- File scope prediction
- Technology-specific patterns
- Integration with existing code

## Progress Updates

You'll receive real-time updates as work progresses:

- 🚀 **Started**: "Starting autonomous implementation of 'user authentication'"
- ⚡ **Progress**: "25% complete" (with progress bar in detailed mode)
- ✅ **Story Complete**: "Completed US-001: Create user model"
- 🎉 **Complete**: Full summary with PR link, tests added, coverage, files changed

## Error Handling

If something goes wrong, you'll get:
- ❌ Clear error message
- 💡 Actionable tip to resolve it
- Option to retry or adjust

Common errors and solutions:
- **"Rate limit exceeded"** → Wait a few minutes
- **"API key not found"** → Check ANTHROPIC_API_KEY
- **"Timeout reached"** → Task too complex, break into smaller stories

## Quality Gates

Every implementation goes through:
- ✅ Tests (minimum 75% coverage)
- ✅ Type checking (TypeScript)
- ✅ Linting (oxlint)
- ✅ Security scanning (OWASP)

If gates fail, the system iterates until they pass or max iterations reached.

## Best Practices

**Be specific about requirements:**
✅ Good: "Add JWT authentication with refresh tokens, password hashing with bcrypt, and rate limiting"
❌ Vague: "Add auth"

**Provide codebase context:**
✅ Good: "Add GraphQL API endpoint (using Apollo Server, TypeScript, with Prisma database)"
❌ Missing context: "Add API endpoint"

**Break down huge features:**
✅ Good: "Add user profile editing (name, email, avatar only)"
❌ Too big: "Build entire social network"

**Use checkpoints for long tasks:**
- Check progress regularly
- Stop and resume if needed
- Don't let sessions run indefinitely

## Examples

### Simple Feature
```
Start adding a dark mode toggle to the settings page
```

### Medium Feature
```
Start building a notification system:
- Bell icon in navbar
- Dropdown with recent notifications
- Mark as read functionality
- Clear all button
- Store in database with timestamps
```

### Complex Feature with Context
```
Start implementing real-time chat:
- Use WebSockets (socket.io)
- Message history from PostgreSQL
- Typing indicators
- Online status
- Unread counts
Context: Next.js app, TypeScript, Tailwind CSS, Prisma ORM
```

### With Specific Testing Requirements
```
Start adding payment processing:
- Stripe integration
- Checkout flow
- Webhook handling
- Receipt emails
- Must have >90% test coverage
- Include integration tests with Stripe test mode
```

## Output

When complete, you'll receive:
- 🔗 **Pull Request** link to review changes
- 🧪 **Test Results**: X tests added, Y passing, Z% coverage
- 📝 **Files Changed**: List of modified files
- ⏱️ **Duration**: Time taken
- ✅ **Quality Gates**: All passed

## Limitations

- **Max execution time**: 2 hours per session (configurable)
- **One session at a time**: Can't run multiple implementations concurrently per user
- **Requires API key**: ANTHROPIC_API_KEY must be set
- **Git repository**: Must be run in a git repo
- **Best for**: New features, bug fixes, refactoring (not greenfield projects)

## Troubleshooting

**Session won't start:**
- Check you don't have an active session already
- Verify ANTHROPIC_API_KEY is set
- Ensure you're in a git repository

**No progress updates:**
- Check verbosity level isn't set to "minimal"
- Verify session is actually running with `status`

**Execution stopped unexpectedly:**
- Check logs for errors
- Look for saved checkpoint
- Resume with `resume` command

## Technical Details

Under the hood, this skill:
1. Uses Claude Sonnet 4.5 to generate PRDs from natural language
2. Spawns claude-loop.sh in isolated workspace
3. Streams events (progress, story-complete, errors) in real-time
4. Formats updates based on verbosity level
5. Saves checkpoints after each story for resumability
6. Runs quality gates before marking complete

All code follows TDD (tests first), uses RG-TDD methodology, and integrates with epiloop's experience store for continuous learning.
