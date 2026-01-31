# Epiloop Fork - Customizations & Sync Strategy

This document tracks how the **epiloop** fork differs from the upstream **openclaw/openclaw** repository.

## Fork Information

- **Upstream**: https://github.com/openclaw/openclaw
- **Fork**: https://github.com/wjlgatech/epiloop
- **Upstream remote**: `git remote add upstream https://github.com/openclaw/openclaw.git`
- **Last synced**: (run `git log --oneline upstream/main ^main | wc -l` to check)

## Major Customizations

### 1. Branding: OpenClaw → EPILOOP

**What changed**:
- Product name: OpenClaw → **EPILOOP**
- Package name: `openclaw` → `epiloop`
- Binary names: `openclaw` → `epiloop`
- Config paths: `~/.openclaw/` → `~/.epiloop/`
- Repository URLs: github.com/openclaw/openclaw → github.com/wjlgatech/epiloop
- Documentation URLs: docs.openclaw.ai → docs.clawd.bot (or epiloop-specific)

**Files affected**:
- `package.json` - package name, bin names
- `README.md` - branding, URLs, examples
- `AGENTS.md` (CLAUDE.md) - all references
- `CHANGELOG.md` - branding
- All documentation in `docs/`
- All source files with hardcoded names
- All test files with brand references
- iOS/Android/macOS app names and identifiers

**Merge strategy**: **Always keep EPILOOP branding** in conflicts

### 2. Autonomous Coding System

**What's new**:
- `extensions/claude-loop/` - Complete autonomous coding extension
- Reality-Grounded TDD implementation
- PRD generation from natural language
- Quality gates and progress reporting
- Integration with messaging channels for autonomous feature requests

**Files added**:
- `extensions/claude-loop/` (entire directory)
- Related documentation in `extensions/claude-loop/docs/`
- Canvas UI components for progress visualization
- Integration points in core codebase

**Merge strategy**: **Keep all epiloop autonomous coding features**. If upstream adds competing features, evaluate and potentially merge or keep both.

### 3. README Enhancements

**What changed**:
- Added "NEWS: Welcome to EPILOOP" section
- Highlighted autonomous coding capabilities
- Examples of overnight feature implementation
- Links to autonomous coding documentation

**Merge strategy**: Keep epiloop section at top, merge upstream improvements to other sections

### 4. Configuration & Paths

**What changed**:
- Config directory: `~/.openclaw/` → `~/.epiloop/`
- Sessions directory: `~/.openclaw/sessions/` → `~/.epiloop/sessions/`
- Credentials: `~/.openclaw/credentials/` → `~/.epiloop/credentials/`
- All CLI commands reference `epiloop` instead of `openclaw`

**Merge strategy**: Always prefer epiloop paths

## Merge Conflict Resolution Guidelines

When syncing with upstream openclaw/openclaw:

### Automatic Resolutions (Safe to Automate)

1. **Branding conflicts**: Always choose epiloop
   - `openclaw` → `epiloop`
   - `OpenClaw` → `EPILOOP` or `Epiloop`
   - `~/.openclaw/` → `~/.epiloop/`
   - `github.com/openclaw/openclaw` → `github.com/wjlgatech/epiloop`

2. **Documentation URLs**:
   - `docs.openclaw.ai` → `docs.clawd.bot` (or epiloop-specific)
   - Keep openclaw references only in "forked from" notes

3. **Package metadata**:
   - Package name stays `epiloop`
   - Binary names stay `epiloop`
   - Repository URLs stay epiloop

### Manual Review Required

1. **Core logic changes**: Merge upstream improvements
2. **New features**: Evaluate compatibility with autonomous coding
3. **Configuration schema changes**: Adapt to both systems
4. **Breaking changes**: Test thoroughly with epiloop features
5. **Security fixes**: Always merge, adapt branding after

### Keep from Epiloop

1. **extensions/claude-loop/** - Entirely epiloop-specific
2. **Autonomous coding docs** - NEWS section in README
3. **Custom canvas UI** - Progress visualization components
4. **Epiloop-specific workflows** - Any custom automation

## Sync Workflow

### Manual Sync

```bash
# Quick check what's new
git fetch upstream
git log --oneline upstream/main ^main | head -20

# Run smart sync script
./scripts/sync-upstream.sh
```

### Automated Weekly Sync

Configured via launchd (see `~/Library/LaunchAgents/com.epiloop.sync-upstream.plist`)

Runs every Sunday at 2 AM, creates a branch, and notifies if conflicts need manual resolution.

## Testing After Sync

Always test after merging upstream:

```bash
pnpm install      # Update dependencies
pnpm build        # TypeScript build
pnpm lint         # Linting
pnpm test         # Unit tests
pnpm epiloop --version  # Smoke test

# Test autonomous coding
epiloop epiloop status
```

## Version Strategy

- **Epiloop versions**: Follow upstream versioning with epiloop identifier when needed
- **Upstream**: v2026.1.29 (example)
- **Epiloop**: v2026.1.29 or v2026.1.29-epiloop.1 (if divergence)

## Contributing Back to Upstream

If you develop generic features (not epiloop-specific) that could benefit openclaw:

1. Create a clean branch without epiloop branding
2. Ensure code is generic and well-tested
3. Open a PR to openclaw/openclaw
4. Reference the PR in epiloop's changelog

**Good candidates**:
- Bug fixes in core logic
- Performance improvements
- New channel integrations (generic)
- Testing improvements

**Not suitable** (epiloop-specific):
- Autonomous coding system
- EPILOOP branding
- Epiloop-specific workflows

## Maintenance Schedule

- **Weekly**: Automated sync check (Sundays 2 AM)
- **Monthly**: Manual review of new upstream features
- **Per-release**: Sync before epiloop releases
- **Security**: Immediate sync for upstream security fixes

## Troubleshooting

### "Working directory not clean"
```bash
git status
git stash  # or commit your changes
```

### "Too many conflicts"
```bash
# Abort and try feature-by-feature cherry-picking
git merge --abort

# Cherry-pick specific features
git log upstream/main ^main
git cherry-pick <commit-hash>
```

### "Build fails after merge"
```bash
# Check for API changes
git diff HEAD~1 package.json
pnpm install
pnpm build --verbose
```

### "Tests fail after merge"
```bash
# Review test changes
git diff HEAD~1 'src/**/*.test.ts'
# Fix broken tests
pnpm test -- <specific-test>
```

## Questions?

- Check upstream changes: `git log upstream/main ^main`
- Compare branches: `git diff main upstream/main`
- See our customizations: `git log --oneline --graph main ^upstream/main`
