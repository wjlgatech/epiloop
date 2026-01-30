# Phase 1 FAQ

Frequently asked questions about Phase 1 features.

## General

### What is Phase 1?

Phase 1 is a set of UX improvements inspired by Cowork's design patterns. It includes:
- Real-time progress indicators
- PRD templates for common project types
- Workspace sandboxing to limit changes
- Safety checkpoints for destructive operations

### Do I need to upgrade?

**No, but you'll love it!** Phase 1 is 100% backwards compatible. Your existing PRDs and workflows continue to work. New features are mostly opt-in (except progress indicators, which you can disable with `--no-progress`).

### How do I get Phase 1?

Phase 1 is included in claude-loop v1.0+. Update to the latest version:
```bash
git pull origin main
```

### Will Phase 1 slow down claude-loop?

**No.** Benchmarks show:
- Progress indicators: <5% overhead
- Workspace validation: <100ms for 1000 files
- Safety checker: <1s for 100 changes

See `tests/phase1/benchmarks/` for full performance validation.

### Can I disable Phase 1 features?

**Yes!** Use these flags:
```bash
--no-progress              # Disable progress UI
--disable-workspace-checks # Disable workspace sandboxing
--safety-level yolo        # Disable safety confirmations
```

For complete old behavior:
```bash
./claude-loop.sh --no-progress --safety-level yolo --disable-workspace-checks
```

## Progress Indicators

### Why don't I see the progress UI?

**Possible reasons:**

1. **You disabled it**: Check for `--no-progress` flag
2. **Non-TTY environment**: Progress UI only works in interactive terminals
3. **Terminal incompatibility**: Your terminal may not support unicode/colors

**Solution**: Run without `--no-progress` in a modern terminal (iTerm2, Windows Terminal, VS Code terminal).

### Can I customize the progress UI?

**Not yet.** The UI is fixed but we're considering:
- Minimal mode (single line instead of box)
- Custom color schemes
- Configurable update frequency

Want this? File a feature request!

### Does the progress UI work in CI/CD?

**No, and it shouldn't.** Use `--no-progress` for CI/CD:
```bash
# CI/CD mode
./claude-loop.sh --no-progress --non-interactive
```

Progress UI is for interactive use only.

### Why are time estimates inaccurate?

**They improve over time!** Initial estimates are rough because claude-loop doesn't know your project's velocity yet. By story 3-4, estimates are usually accurate.

**Factors affecting accuracy:**
- Story complexity variation
- First story takes longer (context building)
- Network/API latency
- Test execution time

### Can I see progress in logs instead?

**Yes!** Logs contain the same information:
```bash
# Follow logs
tail -f .claude-loop/runs/*/metrics.json
```

Or disable progress UI entirely:
```bash
./claude-loop.sh --no-progress
```

## PRD Templates

### What templates are available?

Six templates covering common workflows:

| Template | Use Case | Stories Generated |
|----------|----------|-------------------|
| `web-feature` | Full-stack features | 5-7 stories |
| `api-endpoint` | REST/GraphQL APIs | 4-6 stories |
| `refactoring` | Code restructuring | 3-5 stories |
| `bug-fix` | Bug reproduction & fix | 3-4 stories |
| `documentation` | README/docs updates | 2-3 stories |
| `testing` | Test coverage expansion | 3-4 stories |

List them with: `./claude-loop.sh --list-templates`

### Can I create custom templates?

**Yes!** Add templates to `templates/cowork-inspired/`:

1. Create a new JSON file (see existing templates)
2. Define variables ({{VAR_NAME}})
3. Define user stories with acceptance criteria
4. Use: `./claude-loop.sh --template my-custom-template`

See `templates/cowork-inspired/README.md` for template format.

### Can I modify generated PRDs?

**Absolutely!** Templates are starting points:
```bash
# Generate from template
./claude-loop.sh --template api-endpoint --template-var ENDPOINT_NAME=Tasks

# Edit the generated prd.json
vim prd.json

# Then run
./claude-loop.sh
```

### Do templates support all languages/frameworks?

**Templates are framework-agnostic.** They define *what* to build, not *how*. Claude adapts to your project's language and framework automatically.

Example: The `web-feature` template works for:
- React + Node.js
- Vue + Python/Flask
- Angular + Java/Spring
- Next.js + TypeScript

### Why isn't there a template for X?

We focused on the most common workflows first. Want more templates?
1. Create custom template (see above)
2. Submit PR with new template
3. File feature request

## Workspace Sandboxing

### When should I use workspace sandboxing?

**Use it when:**
- Working on isolated features (only touches certain folders)
- Collaborating (prevent conflicts by sandboxing your area)
- Extra safety (prevent accidental changes to config/infrastructure)
- Learning claude-loop (limit blast radius while testing)

### When should I NOT use workspace sandboxing?

**Don't use it when:**
- Refactoring across many folders
- Story needs to touch multiple unrelated areas
- You're confident in the safety checks
- First time running a PRD (may be too restrictive)

### Can a story modify files outside the workspace?

**In strict mode (default)**: No. Story fails with clear error.

**In permissive mode**: Yes, but you'll see warnings.

```bash
# Strict (default): Hard fail
./claude-loop.sh --workspace "src/api" --workspace-mode strict

# Permissive: Warnings only
./claude-loop.sh --workspace "src/api" --workspace-mode permissive
```

### Does workspace sandboxing work with parallel execution?

**Yes!** Each parallel worker gets its own isolated workspace copy. No conflicts.

### Can I change workspace mid-execution?

**No.** Workspace is set at startup and applies to all stories. To change:
1. Stop claude-loop
2. Restart with new `--workspace` flag

## Checkpoint Confirmations

### What's the difference between safety levels?

| Level | When It Asks | Use Case |
|-------|-------------|----------|
| `paranoid` | Everything | First time using claude-loop |
| `cautious` | Destructive ops (delete, move, major refactor) | Recommended default |
| `normal` | Sensitive files (.env, keys, config) | Trusted PRDs |
| `yolo` | Never | CI/CD, complete trust |

```bash
./claude-loop.sh --safety-level cautious  # Recommended
```

### What operations are considered "destructive"?

- File deletion (`rm`, `git rm`)
- File moves/renames (loses git history)
- Large deletions (>50 lines in a file)
- Directory restructuring
- Sensitive file modifications (.env, credentials, keys)

### Can I customize what's considered sensitive?

**Yes!** Edit `.claude-loop/safety-rules.json`:

```json
{
  "sensitive_patterns": [
    ".env",
    ".env.*",
    "credentials*",
    "*.pem",
    "*.key",
    "secrets/*"
  ],
  "large_deletion_threshold": 50
}
```

### What if I approve something accidentally?

**Check the audit log**:
```bash
cat .claude-loop/safety-log.jsonl
```

Each checkpoint is logged with:
- Timestamp
- Action type
- Files affected
- Your decision (approved/denied)

Then manually revert if needed:
```bash
git reset --hard HEAD~1  # Undo last commit
```

### Can I disable confirmations for specific operations?

**Not yet.** Current options are safety level (applies globally) or non-interactive mode (disables all).

Want fine-grained control? File a feature request!

### Does safety checking work in parallel execution?

**Yes!** Each worker can trigger checkpoints independently. All confirmations are centralized for safety.

## Combining Features

### Can I use all Phase 1 features together?

**Yes! Recommended combination:**
```bash
./claude-loop.sh \
  --template api-endpoint \
  --template-var ENDPOINT_NAME=Tasks \
  --workspace "src/api,tests/api" \
  --safety-level cautious
```

This gives you:
- PRD from template (fast start)
- Workspace sandboxing (safety)
- Progress indicators (visibility, enabled by default)
- Safety confirmations (confidence)

### Do features work with parallel execution?

**Yes!** All Phase 1 features are parallel-safe:
- Progress indicators: Each PRD has its own UI
- Workspace sandboxing: Each worker isolated
- Safety confirmations: Centralized coordination
- Templates: Generate multiple PRDs in parallel

### Do features work with multi-LLM support?

**Yes!** Phase 1 is orthogonal to LLM provider:
```bash
./claude-loop.sh \
  --provider gemini \
  --template web-feature \
  --workspace src/frontend \
  --safety-level cautious
```

### Can I use templates with existing PRDs?

**No.** Templates *generate* PRDs. If you have a PRD, you don't need a template.

**Workflow:**
1. Start without PRD → Use template → Generates prd.json → Run
2. Start with PRD → Just run

### What's the recommended workflow?

**For new projects:**
```bash
# 1. Generate PRD from template
./claude-loop.sh --template <type> --template-var KEY=VALUE

# 2. Review/edit prd.json
vim prd.json

# 3. Run with safety
./claude-loop.sh --workspace <folders> --safety-level cautious
```

**For existing PRDs:**
```bash
# Just run with safety
./claude-loop.sh --workspace <folders> --safety-level cautious
```

## Migration

### Will my old PRDs still work?

**Yes!** 100% backwards compatible. Phase 1 adds new features but doesn't change PRD format.

### Do I need to update existing PRDs?

**No.** Existing PRDs work as-is. You can optionally:
- Add `fileScope` for workspace sandboxing
- Use templates for new PRDs
- Use safety confirmations (works with any PRD)

### How do I migrate from pre-Phase1?

See the [Migration Guide](../MIGRATION-PHASE1.md) for detailed steps.

**TL;DR**: Update claude-loop, no code changes needed!

### Can I roll back to pre-Phase1?

**Yes:**
```bash
git checkout <old-version-tag>
```

Or disable Phase 1 features:
```bash
./claude-loop.sh --no-progress --safety-level yolo --disable-workspace-checks
```

## Performance

### Does Phase 1 add latency?

**Minimal.** See [Performance Guide](../features/performance.md) for benchmarks.

**Measured overhead:**
- Progress indicators: -18% (actually *improves* perceived performance!)
- Workspace validation: 81ms for 1000 files
- Safety checker: 41ms for 100 changes
- Template generation: 76ms

### How does Phase 1 affect token usage?

**No impact.** Phase 1 features run outside Claude's context:
- Progress UI: Pure shell script
- Templates: PRD generation (one-time)
- Workspace sandboxing: Validation only
- Safety checker: Git diff analysis

Claude sees the same prompts as before.

### Can I profile Phase 1 features?

**Yes!** Run benchmarks:
```bash
tests/phase1/benchmarks/run-benchmarks.sh
```

This measures:
- Feature overhead
- Performance vs thresholds
- Optimization recommendations

## Advanced

### Can I use Phase 1 features programmatically?

**Yes!** All features have scriptable interfaces:

```bash
# Progress indicators
source lib/progress-indicators.sh
init_progress "prd.json" "US-001"
update_progress 50 "Running tests"

# Templates
lib/template-generator.sh generate api-endpoint ENDPOINT_NAME=Tasks

# Workspace sandboxing
source lib/workspace-manager.sh
validate_workspace_folders "src,tests"

# Safety checker
source lib/safety-checker.sh
check_for_destructive_changes
```

### Can I extend Phase 1 features?

**Yes!** All features are modular:
- Add custom templates to `templates/cowork-inspired/`
- Customize safety rules in `.claude-loop/safety-rules.json`
- Hook into progress callbacks (see `lib/progress-indicators.sh`)

### How do I contribute Phase 1 improvements?

1. Read `CONTRIBUTING.md`
2. Check existing issues/PRs
3. Discuss feature in issue first
4. Submit PR with tests

**Areas for contribution:**
- New PRD templates
- Progress UI themes
- Safety checker patterns
- Documentation improvements

### What's next for Phase 1?

See the [Roadmap](../roadmap/cowork-inspired-roadmap.md) for Phase 2 and beyond:
- Browser-based progress dashboard
- Template marketplace
- Smart workspace detection
- AI-powered safety suggestions

## Still Have Questions?

- **Documentation**: See `docs/phase1/` and `docs/features/`
- **Tutorial**: Follow the [hands-on tutorial](./tutorial.md)
- **Troubleshooting**: Check the [troubleshooting guide](./troubleshooting.md)
- **Issues**: File questions on GitHub
- **Community**: Join discussions

---

**Didn't find your question?** File an issue and we'll add it to the FAQ!
