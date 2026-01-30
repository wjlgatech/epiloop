# Getting Started with Phase 1 Features

Welcome to claude-loop Phase 1! This guide will help you get up and running with the new productivity features inspired by Cowork's UX patterns.

## What's New in Phase 1?

Phase 1 adds four key features that make claude-loop more visible, safer, and easier to use:

| Feature | What It Does | Why You'll Love It |
|---------|--------------|-------------------|
| **Progress Indicators** | Real-time UI showing what's happening | No more wondering "is it stuck?" |
| **PRD Templates** | 6 ready-to-use project templates | Start from proven patterns |
| **Workspace Sandboxing** | Limit changes to specific folders | Prevent accidental edits |
| **Checkpoint Confirmations** | Ask before destructive operations | Sleep well knowing it's safe |

## Quick Start

### 1. Your First Run with Progress Indicators

Progress indicators are **enabled by default** - just run claude-loop normally:

```bash
./claude-loop.sh
```

You'll see a rich terminal UI like this:

```
╔════════════════════════════════════════════════════════════════╗
║ Current Story: US-003
║ Workspace: lib,src
║
║ Overall Progress: [███████░░░] 3/10 stories
║ Time: 15m elapsed | ~35m remaining
║ Currently: Running tests
║
║ Acceptance Criteria:
║   ✅ Create lib/progress-indicators.sh
║   ✅ Add real-time checklist display
║   ⏳ Implement visual progress bar
║   ○ Add time tracking
╚════════════════════════════════════════════════════════════════╝
```

**Tip**: If you're running in CI/CD, use `--no-progress` to disable the fancy UI.

### 2. Start from a Template

Instead of writing a PRD from scratch, use a template:

```bash
# List available templates
./claude-loop.sh --list-templates

# Generate a PRD from a template
./claude-loop.sh --template web-feature \
  --template-var FEATURE_NAME=user-dashboard \
  --template-var DESCRIPTION="A dashboard showing user activity"

# This creates prd.json ready to execute!
./claude-loop.sh
```

**Available templates:**
- `web-feature` - Full-stack feature with frontend + backend + tests
- `api-endpoint` - REST/GraphQL endpoint with validation
- `refactoring` - Code restructuring with backwards compatibility
- `bug-fix` - Issue reproduction + fix + regression tests
- `documentation` - README/docs updates with examples
- `testing` - Test coverage expansion

### 3. Sandbox Your Workspace

Limit claude-loop to only modify specific folders:

```bash
# Only allow changes to lib/ and tests/
./claude-loop.sh --workspace "lib,tests"
```

**Use cases:**
- Working on a feature that should only touch certain folders
- Collaborating with others - avoid conflicts by sandboxing your area
- Extra safety - prevent accidental changes to config files

### 4. Add Safety Confirmations

Choose your safety level based on trust:

```bash
# Cautious: Ask before destructive operations (recommended)
./claude-loop.sh --safety-level cautious

# Paranoid: Ask for confirmation on EVERYTHING
./claude-loop.sh --safety-level paranoid

# Normal: Only ask for sensitive files (default)
./claude-loop.sh --safety-level normal

# YOLO: No confirmations (use with caution!)
./claude-loop.sh --safety-level yolo
```

When claude-loop wants to do something destructive, you'll see:

```
⚠️  CHECKPOINT CONFIRMATION REQUIRED ⚠️
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Action: Delete 3 files
Files affected:
  - src/old_module.py
  - src/deprecated.py
  - tests/old_tests.py

Reason: Removing deprecated code as part of refactoring

Do you approve this action?
  [y] Yes     [n] No     [a] Yes to all     [q] Abort

Your choice:
```

## Combining Features

The real power comes from using features together:

```bash
# Create a web feature from template, sandbox to frontend, with safety
./claude-loop.sh \
  --template web-feature \
  --template-var FEATURE_NAME=user-settings \
  --workspace "src/frontend,src/components" \
  --safety-level cautious
```

This will:
1. Generate a PRD for a web feature (from template)
2. Only allow changes to frontend folders (sandbox)
3. Ask before deleting/moving files (safety)
4. Show real-time progress as it works (progress indicators)

## What to Expect

### First Iteration (0-2 minutes)
- Progress UI appears
- Claude Code starts implementing first story
- You see acceptance criteria being checked off ✅

### Mid-Execution (5-10 minutes)
- Time estimates become more accurate
- You can see which story is being worked on
- Any checkpoint confirmations will interrupt progress UI

### Completion
- All stories marked complete ✅
- Final summary shows total time and cost
- Ready to commit with git!

## Next Steps

- **Learn more**: Read the [feature deep-dives](../features/) for advanced usage
- **Troubleshooting**: See [troubleshooting guide](./troubleshooting.md) for common issues
- **Tutorial**: Follow the [complete tutorial](./tutorial.md) for a hands-on example
- **FAQ**: Check the [FAQ](./faq.md) for answers to common questions

## Tips for Success

1. **Start with templates** - They encode best practices
2. **Use sandboxing** when working on isolated features
3. **Start cautious** - You can always switch to `--safety-level normal` later
4. **Watch the progress** - The UI tells you what's happening
5. **Check docs/features/** - Each feature has a detailed guide

## Migration from Pre-Phase1

Upgrading from an older version? See the [Migration Guide](../MIGRATION-PHASE1.md).

**Good news**: Phase 1 is 100% backwards compatible! Your existing PRDs and workflows still work. New features are opt-in (except progress indicators, which you can disable with `--no-progress`).

## Getting Help

- **Documentation**: `docs/features/` and `docs/phase1/`
- **CLI Help**: `./claude-loop.sh --help`
- **Issues**: File issues on GitHub
- **Examples**: See `tests/phase1/` for real examples

---

Ready to build? Pick a workflow:

- 🚀 **Fast Start**: Use a template → Run
- 🎯 **Safe Start**: Template + Workspace + Safety
- 📊 **Full Experience**: All Phase 1 features enabled

Happy coding! 🔄
