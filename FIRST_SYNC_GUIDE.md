# First Upstream Sync Guide

Your epiloop fork is ready to sync with upstream openclaw/openclaw! However, the first sync will have **hundreds of merge conflicts** due to the rebrand (openclaw → epiloop).

## Current Status

- ✅ Upstream remote added: `upstream` → openclaw/openclaw
- ✅ Weekly automation configured (Sundays 2 AM)
- ✅ Smart sync scripts created
- ⏳ First manual sync needed (555 commits behind)

## Strategy: Incremental Sync

Instead of merging all 555 commits at once, we'll use a **selective strategy**:

### Option A: Cherry-Pick Important Features (Recommended)

This gives you fine-grained control:

```bash
# 1. See what's new in upstream
git log --oneline upstream/main ^main | head -50

# 2. Cherry-pick specific important commits
git cherry-pick <commit-hash>

# 3. Resolve conflicts (if any) for each commit
#    Keep epiloop branding, merge logic improvements

# 4. Test and commit
pnpm build && pnpm test
git push origin main
```

**Benefits**:
- Less overwhelming conflicts
- Better control over what you merge
- Easier to test incrementally

**Look for commits like**:
- Security fixes (priority!)
- Bug fixes you need
- New features that complement autonomous coding
- Performance improvements

### Option B: Merge with Manual Conflict Resolution

For the brave:

```bash
# 1. Create a dedicated branch
git checkout -b sync-upstream-manual

# 2. Merge upstream
git merge upstream/main

# 3. Resolve ALL conflicts (hundreds of files)
#    Follow the guidelines in EPILOOP_FORK.md

# 4. After resolving:
git add .
git commit
git checkout main
git merge sync-upstream-manual
```

**Conflict Resolution Rules**:
1. **Always keep epiloop branding**:
   - `openclaw` → `epiloop`
   - `~/.openclaw/` → `~/.epiloop/`
   - github.com/openclaw/openclaw → github.com/wjlgatech/epiloop

2. **Merge logic improvements**:
   - Take upstream's code improvements
   - Adapt to epiloop names after merging

3. **Keep epiloop-specific features**:
   - All of `extensions/claude-loop/`
   - Autonomous coding documentation
   - NEWS section in README

### Option C: Rebase on Upstream (Advanced)

Create epiloop as a set of patches on top of upstream:

```bash
# 1. Identify epiloop-specific commits
git log --oneline main ^upstream/main

# 2. Save your epiloop commits
git format-patch upstream/main..main -o /tmp/epiloop-patches

# 3. Hard reset to upstream (DANGEROUS - backup first!)
git checkout main
git reset --hard upstream/main

# 4. Apply epiloop patches one by one
git am /tmp/epiloop-patches/*.patch

# 5. Force push (only if you're sure!)
git push origin main --force-with-lease
```

**⚠️ Warning**: This rewrites history. Only do this if you understand the implications.

## Recommended Approach for Your Situation

Given that you have significant customizations (autonomous coding) and 555 commits to catch up:

### Phase 1: Critical Updates (Now)

```bash
# Cherry-pick security fixes and critical bug fixes
git log --oneline --grep="security\|Security\|CVE" upstream/main ^main
git log --oneline --grep="fix:\|Fix:" upstream/main ^main | head -20

# Pick the important ones
git cherry-pick <commit-hash>
```

### Phase 2: Feature Sync (Monthly)

```bash
# Every month, cherry-pick new features you want
git log --oneline --grep="feat:\|Feat:" upstream/main ^main | head -20
git cherry-pick <commit-hash>
```

### Phase 3: Automated Incremental Sync (Weekly)

The weekly automation will handle small incremental updates going forward. After the initial gap is closed, syncing will be much easier.

## Handling Branding Conflicts

When you encounter conflicts like this:

```
<<<<<<< HEAD
epiloop config set gateway.mode=local
=======
openclaw config set gateway.mode=local
>>>>>>> upstream/main
```

**Resolution**:
```bash
# Choose HEAD (epiloop version)
epiloop config set gateway.mode=local
```

Or use this pattern:
```bash
# Accept epiloop version for all branding conflicts
git checkout --ours path/to/file    # Keep your version
git add path/to/file
```

For logic conflicts:
```bash
# Manually merge the logic, keep epiloop branding
# Then:
git add path/to/file
```

## Testing After Sync

After any sync operation:

```bash
# Full test suite
pnpm install
pnpm build
pnpm lint
pnpm test

# Smoke tests
pnpm epiloop --version
pnpm epiloop channels status

# Test autonomous coding (epiloop-specific)
pnpm epiloop epiloop status
```

## Emergency Rollback

If sync goes wrong:

```bash
# You have a backup branch!
git checkout main
git reset --hard backup-pre-sync-YYYYMMDD-HHMMSS
git push origin main --force-with-lease
```

## Next Steps

1. **Decide on strategy**: Cherry-pick (recommended) or full merge
2. **Start small**: Begin with security fixes
3. **Test incrementally**: After each cherry-pick or merge
4. **Document changes**: Update EPILOOP_FORK.md with merged features
5. **Push to origin**: Share your progress

## Need Help?

- View what's new: `git log --oneline upstream/main ^main`
- See a specific commit: `git show <commit-hash>`
- Compare with upstream: `git diff upstream/main...main -- path/to/file`
- Check conflict files: `git diff --name-only --diff-filter=U`

## Automation is Ready

Once you've done the initial sync manually, the weekly automation will keep you updated:

- **Every Sunday at 2 AM**: Auto-sync attempt
- **Notifications**: macOS notifications on success/conflict
- **Logs**: `~/.epiloop/logs/sync-upstream*.log`
- **Manual trigger**: `launchctl start com.epiloop.sync-upstream`

Good luck! 🚀
