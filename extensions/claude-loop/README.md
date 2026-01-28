# Claude Loop - Autonomous Coding Agent Extension

This extension integrates the `claude-loop` autonomous coding agent into Clawdbot, enabling users to request feature implementations conversationally through any supported messaging channel (WhatsApp, Telegram, Discord, etc.).

## Purpose

Enable autonomous feature development by:
1. Converting natural language feature requests into structured PRDs (Product Requirements Documents)
2. Executing autonomous implementation iterations with quality gates
3. Streaming real-time progress updates to users
4. Learning from past implementations to improve future quality

## Architecture

### Core Components

- **PRD Generator** (`src/prd-generator.ts`) - Converts natural language to structured PRD format
- **Loop Executor** (`src/loop-executor.ts`) - Manages claude-loop process lifecycle and event streaming
- **Progress Reporter** (`src/progress-reporter.ts`) - Formats and delivers progress updates to messaging channels
- **Workspace Manager** (`src/workspace-manager.ts`) - Isolates sessions using git worktrees
- **Experience Bridge** (`src/experience-bridge.ts`) - Integrates with claude-loop's learning system
- **Quality Gates** (`src/quality-gates.ts`) - Validates code quality before completion

### Plugin Integration Points

1. **Skill Registration**: Exposes `/autonomous-coding` skill for user interaction
2. **CLI Integration**: Adds `clawdbot autonomous-coding` commands
3. **Channel Integration**: Progress updates delivered to any registered channel
4. **Tool Registration**: Provides tools for PRD management and execution control

### Data Flow

```
User Request → PRD Generator → Loop Executor → Quality Gates → Completion
                                      ↓
                                Progress Reporter
                                      ↓
                             Messaging Channels
```

## Extension Structure

```
extensions/claude-loop/
├── package.json              # Extension dependencies
├── tsconfig.json             # TypeScript configuration
├── clawdbot.plugin.json      # Plugin metadata
├── README.md                 # This file
├── src/
│   ├── index.ts             # Plugin entry point
│   ├── types.ts             # Shared types
│   ├── prd-generator.ts     # Natural language → PRD
│   ├── loop-executor.ts     # Process management
│   ├── progress-reporter.ts # Progress formatting
│   ├── workspace-manager.ts # Session isolation
│   ├── experience-bridge.ts # Learning integration
│   └── quality-gates.ts     # Validation logic
└── lib/
    └── claude-loop/         # Git submodule (added in US-002)
```

## Development Status

- ✅ US-001: Extension package structure created
- ⏳ US-002: Git submodule integration
- ⏳ US-003: PRD generator
- ⏳ US-004: Loop executor
- ⏳ US-005: Progress reporter
- ⏳ US-006: Skill integration
- ⏳ Remaining stories...

## Dependencies

- `clawdbot` >= 2026.1.23-1 (peer dependency)
- `@anthropic-ai/sdk` ^0.32.1 (for PRD generation)

## Usage (After Full Implementation)

```bash
# Start autonomous feature implementation
clawdbot autonomous-coding start "Add user authentication with JWT"

# Check status
clawdbot autonomous-coding status

# View execution logs
clawdbot autonomous-coding logs
```

Or via messaging channels:
```
User: "Implement dark mode for the dashboard"
Bot: "I'll create a PRD and start autonomous implementation. Estimated: 3 stories, ~2 hours..."
```

## Configuration

Configuration will be added in later user stories. Expected settings:

```yaml
claudeLoop:
  maxConcurrent: 3
  experienceStore: ~/.clawdbot/claude-loop/experience-store/
  qualityGates:
    requireTests: true
    requireLint: true
    minCoverage: 75
```

## References

- [Clawdbot Plugin SDK](https://docs.clawd.bot/development/plugin-sdk)
- [Claude Loop Repository](https://github.com/yourusername/claude-loop)
- Main PRD: `prds/active/claude-loop-integration/prd.json`
