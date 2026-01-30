# Claude-Loop Extension for Epiloop

Autonomous coding agent integration for Epiloop - implement software features from natural language descriptions.

## Overview

This extension integrates [claude-loop](https://github.com/your-repo/claude-loop) into Epiloop, enabling users to request feature implementations via conversational channels (WhatsApp, Telegram, Discord, etc.) that execute autonomously with quality gates and real-time progress reporting.

## Features

- **Autonomous Implementation**: Describe features in natural language, get working code
- **Reality-Grounded TDD**: Implements features using test-driven development
- **Quality Gates**: Automatic testing, type checking, linting, and security scans
- **Real-Time Progress**: Live updates on implementation progress
- **Parallel Execution**: Run multiple autonomous tasks concurrently
- **Self-Improvement**: Learns from failures to improve over time
- **Experience Store**: Learns from past implementations
- **Canvas Visualization**: Beautiful progress UI on iOS/macOS

## Quick Start

### Installation

```bash
# Install the extension
cd extensions/claude-loop
npm install

# Run tests
npm test

# Build
npm run build
```

### Basic Usage

From any Epiloop channel:

```
/autonomous-coding start "Add user authentication with JWT"
```

The system will:
1. Generate a PRD with user stories
2. Implement each story using TDD
3. Run quality gates
4. Report progress
5. Complete with passing tests

## Documentation

- **[User Guide](./docs/USER_GUIDE.md)** - Complete usage guide with examples
- **[Architecture](./docs/ARCHITECTURE.md)** - Technical architecture and design
- **[Configuration](./docs/CONFIGURATION.md)** - Configuration options (TBD)
- **[API Reference](./docs/API.md)** - API documentation (TBD)
- **[Troubleshooting](./docs/TROUBLESHOOTING.md)** - Common issues and solutions (TBD)

## Project Structure

```
extensions/claude-loop/
├── src/
│   ├── index.ts                  # Plugin entry point
│   ├── skill-handler.ts          # Command handler
│   ├── prd-generator.ts          # PRD generation
│   ├── loop-executor.ts          # Execution engine
│   ├── progress-reporter.ts      # Progress formatting
│   ├── workspace-manager.ts      # Session management
│   ├── quality-gates.ts          # Quality validation
│   ├── parallel-coordinator.ts   # Parallel execution
│   ├── metrics-logger.ts         # Metrics tracking
│   ├── improvement-engine.ts     # Self-improvement
│   ├── experience-bridge.ts      # Experience store
│   └── canvas/
│       └── AutonomousCodingProgress.tsx  # Canvas UI
├── lib/
│   └── claude-loop/              # Claude-loop codebase
├── docs/
│   ├── USER_GUIDE.md
│   ├── ARCHITECTURE.md
│   ├── CONFIGURATION.md (TBD)
│   ├── API.md (TBD)
│   └── TROUBLESHOOTING.md (TBD)
├── test/
│   ├── setup.ts
│   └── e2e/                      # E2E tests
├── package.json
├── tsconfig.json
├── vitest.config.ts
└── README.md
```

## Architecture

```
User Command → Skill Handler → PRD Generator
                     ↓
              Loop Executor → Quality Gates
                     ↓              ↓
              Progress Reporter → Metrics Logger
                                      ↓
                                Improvement Engine
```

See [ARCHITECTURE.md](./docs/ARCHITECTURE.md) for detailed architecture.

## Development

### Running Tests

```bash
# All tests
npm test

# Specific test file
npm test prd-generator.test.ts

# With coverage
npm test -- --coverage

# Watch mode
npm test -- --watch
```

### Building

```bash
# TypeScript compilation
npm run build

# Type checking only
npm run typecheck

# Linting
npm run lint
```

### Local Development

```bash
# Link extension for local testing
cd ../..  # Back to epiloop root
npm install
npm run dev

# In another terminal, test commands
epiloop autonomous-coding start "Test feature"
```

## Configuration

Configuration file: `~/.epiloop/config/autonomous-coding.json`

```json
{
  "qualityGates": {
    "requireTests": true,
    "minCoverage": 75
  },
  "execution": {
    "maxConcurrent": 3,
    "timeout": 3600000
  }
}
```

See [CONFIGURATION.md](./docs/CONFIGURATION.md) for all options (TBD).

## Development Status

Progress: **13/15 stories complete (87%)**

- ✅ US-001: Extension package structure
- ✅ US-002: Claude-loop codebase integration
- ✅ US-003: PRD generator with Claude API
- ✅ US-004: Loop executor with event streaming
- ✅ US-005: Progress reporter with formatting
- ✅ US-006: Epiloop skill integration
- ✅ US-007: Workspace management
- ✅ US-008: Experience bridge
- ✅ US-009: Quality gates
- ✅ US-010: Canvas visualization
- ✅ US-011: Parallel coordinator
- ✅ US-012: Logging and metrics
- ✅ US-013: Improvement engine
- ⏳ US-014: Documentation (in progress)
- ⏳ US-015: E2E integration tests

## Examples

### Simple Feature

```
/autonomous-coding start "Add dark mode toggle"
```

### Complex Feature with Context

```
/autonomous-coding start "Implement search with:
- Full-text search using Elasticsearch
- Filters for category, date, author
- Pagination (50 items per page)
- Sort by relevance, date, popularity
- Debounced search input
- Search suggestions"
```

### Custom PRD

```json
{
  "title": "User Profile Page",
  "stories": [
    {
      "id": "US-001",
      "title": "Create profile component",
      "acceptanceCriteria": [
        "Tests written FIRST",
        "Displays user avatar, name, bio",
        "Edit button for profile owner",
        "Responsive design"
      ]
    }
  ]
}
```

```
/autonomous-coding start --prd ./profile-prd.json
```

## Metrics and Monitoring

View session metrics:

```
/autonomous-coding metrics --session <id>
```

Generate monthly report:

```
/autonomous-coding metrics --period monthly
```

Check success rate:

```
/autonomous-coding calibration --days 30
```

## Contributing

1. Follow TDD (tests first!)
2. Run `npm test` before committing
3. Update documentation for new features
4. Add examples to USER_GUIDE.md

## Testing Philosophy

This project uses **Reality-Grounded Test Driven Development (RG-TDD)**:

1. **Foundation Layer**: Core functionality tests
2. **Challenge Layer**: Edge cases and error handling
3. **Reality Layer**: Real-world integration tests

All tests must follow TDD Iron Law:
1. Write test FIRST (RED phase)
2. Verify test FAILS
3. Write minimal implementation (GREEN phase)
4. Verify test PASSES
5. Refactor if needed

## Dependencies

- `epiloop` >= 2026.1.23-1 (peer dependency)
- `@anthropic-ai/sdk` ^0.32.1 (for PRD generation)
- `vitest` ^2.1.8 (testing)
- `typescript` ^5.7.3 (language)

## License

MIT

## Support

- Documentation: https://docs.clawd.bot
- Issues: https://github.com/epiloop/epiloop/issues
- Discord: https://discord.gg/epiloop

## Credits

Built with [claude-loop](https://github.com/your-repo/claude-loop) by the Epiloop team.
