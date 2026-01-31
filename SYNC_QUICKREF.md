# Upstream Sync - Quick Reference

## Status Check

```bash
# How many commits behind?
git fetch upstream && git log --oneline upstream/main ^main | wc -l

# What's new?
git log --oneline --graph upstream/main ^main | head -20

# Check automation status
launchctl list | grep epiloop.sync-upstream
```

## Manual Sync

```bash
# Quick sync (automated)
./scripts/sync-upstream.sh

# Cherry-pick specific features
git log --oneline upstream/main ^main | head -50
git cherry-pick <commit-hash>
pnpm build && pnpm test && git push

# Full merge (for brave souls)
git checkout -b sync-upstream-$(date +%Y%m%d)
git merge upstream/main
# ... resolve conflicts ...
git checkout main && git merge sync-upstream-$(date +%Y%m%d)
```

## Automation

```bash
# Trigger sync now
launchctl start com.epiloop.sync-upstream

# View logs
tail -f ~/.epiloop/logs/sync-upstream.log

# Disable weekly sync
launchctl unload ~/Library/LaunchAgents/com.epiloop.sync-upstream.plist

# Re-enable weekly sync
launchctl load ~/Library/LaunchAgents/com.epiloop.sync-upstream.plist
```

## Conflict Resolution

```bash
# List conflicted files
git diff --name-only --diff-filter=U

# For branding conflicts (keep epiloop)
git checkout --ours <file>
git add <file>

# For logic conflicts (merge manually)
# Edit the file, then:
git add <file>

# Complete the merge
git commit
```

## Testing

```bash
# Quick test
pnpm build && pnpm epiloop --version

# Full gate
pnpm install && pnpm lint && pnpm build && pnpm test

# Test autonomous coding
pnpm epiloop epiloop status
```

## Emergency

```bash
# Abort merge
git merge --abort

# Rollback (use backup branch created by sync script)
git branch | grep backup-pre-sync
git reset --hard backup-pre-sync-YYYYMMDD-HHMMSS

# Force push (if needed)
git push origin main --force-with-lease
```

## Daily Schedule

- **When**: Every day at 2:00 AM
- **What**: Automatic fetch and merge attempt
- **Notifications**: macOS notification on success/conflict
- **Logs**: `~/.epiloop/logs/sync-upstream-*.log`

## Important Files

- `EPILOOP_FORK.md` - Customization documentation
- `FIRST_SYNC_GUIDE.md` - Detailed sync strategies
- `scripts/sync-upstream.sh` - Smart sync script
- `scripts/sync-upstream-daily.sh` - Daily automation wrapper
- `~/Library/LaunchAgents/com.epiloop.sync-upstream.plist` - launchd config

## Branding Rules

**Always keep epiloop**:
- `openclaw` → `epiloop`
- `OpenClaw` → `EPILOOP`
- `~/.openclaw/` → `~/.epiloop/`
- `github.com/openclaw/openclaw` → `github.com/wjlgatech/epiloop`

**Always merge logic improvements** from upstream, just adapt the branding.

**Always keep epiloop-specific features**:
- `extensions/claude-loop/` (autonomous coding)
- NEWS section in README
- Custom documentation

## Getting Started

1. Read `FIRST_SYNC_GUIDE.md` for strategy
2. Start with security fixes: `git log --grep="security" upstream/main ^main`
3. Cherry-pick incrementally
4. Let automation handle future updates
