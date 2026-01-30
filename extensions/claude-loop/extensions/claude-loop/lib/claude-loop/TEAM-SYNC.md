# Team Experience Sharing Protocol

This document describes how teams can share experiences in claude-loop without any cloud services. All synchronization happens via local filesystem or git repositories.

## Overview

Team experience sharing enables multiple developers to benefit from each other's learned experiences while maintaining strict privacy guarantees:

- **NO cloud services** - All data stays on local filesystems or git repositories
- **NO telemetry** - No tracking or analytics of shared data
- **Privacy-first** - Sensitive execution logs are never shared
- **Conflict resolution** - Higher helpful_rate experiences win on conflicts
- **Deduplication** - Similar experiences are merged, not duplicated

## Quick Start

### Export Experiences

Export your local experiences for sharing:

```bash
# Export all experiences (auto-generates filename)
python3 lib/experience-sync.py export

# Export specific domain
python3 lib/experience-sync.py export --domain unity_xr

# Export with quality filters
python3 lib/experience-sync.py export --min-helpful-rate 0.3 --min-retrievals 5

# Export to specific file
python3 lib/experience-sync.py export --output /shared/team/my-experiences.jsonl.gz
```

### Import Experiences

Import experiences from a teammate:

```bash
# Import and merge with local experiences
python3 lib/experience-sync.py import teammate-experiences.jsonl.gz --merge

# Dry run to see what would happen
python3 lib/experience-sync.py import teammate-experiences.jsonl.gz --dry-run
```

### Shared Folder Sync

Set up a shared folder for automatic synchronization:

```bash
# One-time sync with shared folder
python3 lib/experience-sync.py sync-folder /shared/team/experiences

# Watch for new files continuously
python3 lib/experience-sync.py sync-folder /shared/team/experiences --watch
```

## Export Format

Exports use the filename pattern:
```
experiences-{domain}-{date}.jsonl.gz
```

Examples:
- `experiences-all-20260112-143022.jsonl.gz` - All domains
- `experiences-unity_xr-20260112-143022.jsonl.gz` - Unity XR domain only

### File Structure

Each line is a JSON object representing one experience:

```json
{
  "id": "abc123def456",
  "problem_signature": "UI element not found in hierarchy",
  "solution_approach": "Use FindObjectOfType with includeInactive=true",
  "domain_context": {
    "project_type": "unity_xr",
    "language": "csharp",
    "frameworks": ["Unity XR"],
    "tools_used": ["OpenXR"]
  },
  "success_count": 5,
  "retrieval_count": 10,
  "helpful_count": 7,
  "last_used": "2026-01-12T14:30:00Z",
  "created_at": "2026-01-10T09:00:00Z",
  "category": "UI",
  "tags": ["unity", "xr", "ui"],
  "source_machine": "dev-workstation-01",
  "export_version": "1.0"
}
```

## Sync Modes

### 1. Manual Export/Import

The simplest approach - manually export and share files:

1. Developer A exports: `python3 lib/experience-sync.py export -o shared/my-experiences.jsonl.gz`
2. Developer A shares the file (email, Slack, shared drive)
3. Developer B imports: `python3 lib/experience-sync.py import shared/my-experiences.jsonl.gz`

Best for:
- Small teams
- Occasional sharing
- One-time knowledge transfer

### 2. Shared Folder Watch

Use a shared network folder for automatic sync:

```bash
# Mount shared folder (example for macOS/Linux)
mount -t nfs server:/shared/experiences /mnt/team-experiences

# Start watching
python3 lib/experience-sync.py sync-folder /mnt/team-experiences --watch
```

Best for:
- Teams with shared network storage
- Continuous collaboration
- Hands-off synchronization

### 3. Git-Based Sync

Use a git repository for version-controlled sharing:

```bash
# In your experiences git repo
cd team-experiences-repo

# Export experiences
python3 lib/experience-sync.py export --output ./exports/$(hostname)-$(date +%Y%m%d).jsonl.gz

# Commit and push
git add exports/
git commit -m "Add experiences from $(hostname)"
git push

# Pull and import teammate experiences
git pull
for f in exports/*.jsonl.gz; do
  python3 lib/experience-sync.py import "$f" --merge
done
```

Best for:
- Distributed teams
- Version history
- Pull request-based review

## Conflict Resolution

When importing experiences that conflict with local ones:

### Same ID Conflict
If an imported experience has the same ID as a local one:
- **Keep higher helpful_rate** - The experience that has helped more often wins
- Track resolution in audit log

### Similar Experience Deduplication
If an imported experience is >90% similar to an existing one:
- Compare helpful_rate of both
- Keep the better-performing one
- Skip if local is better

### Resolution Details

View conflict resolutions in the import result:

```bash
python3 lib/experience-sync.py import file.jsonl.gz --verbose
```

Output:
```
Import successful!
  Total read: 50
  Imported: 42
  Skipped (duplicate): 5
  Conflicts resolved: 3

  Conflict Details:
    [exp-abc123]
      Local rate: 60.00%
      Remote rate: 75.00%
      Resolution: kept_remote
```

## Quality Filters

Control which experiences are exported/shared:

| Filter | Description | Example |
|--------|-------------|---------|
| `--domain` | Only specific domain | `--domain unity_xr` |
| `--min-helpful-rate` | Minimum helpful rate (0.0-1.0) | `--min-helpful-rate 0.3` |
| `--min-retrievals` | Minimum retrieval count | `--min-retrievals 5` |

### Recommended Filters for Sharing

For high-quality team sharing, use these filters:

```bash
# Only share experiences that have proven helpful
python3 lib/experience-sync.py export \
  --min-helpful-rate 0.3 \
  --min-retrievals 5 \
  --output /shared/proven-experiences.jsonl.gz
```

## Audit Log

All sync operations are logged to `.claude-loop/sync_audit.jsonl`:

```json
{
  "operation": "export",
  "timestamp": "2026-01-12T14:30:00Z",
  "path": ".claude-loop/exports/experiences-all-20260112-143000.jsonl.gz",
  "experience_count": 42,
  "domains": ["unity_xr", "web_frontend"],
  "duration_ms": 156,
  "success": true,
  "details": {
    "filters": {"domain": null, "min_helpful_rate": 0.3, "min_retrievals": 5},
    "checksum": "a1b2c3d4e5f6g7h8"
  }
}
```

### View Audit History

```bash
# Recent sync operations
python3 lib/experience-sync.py history

# Last 50 operations as JSON
python3 lib/experience-sync.py history --limit 50 --json
```

### Sync Statistics

```bash
python3 lib/experience-sync.py stats
```

Output:
```
Sync Statistics:
  Total exports: 12
  Total imports: 8
  Experiences exported: 420
  Experiences imported: 280
  Conflicts resolved: 15
  Duplicates skipped: 45
  Last export: 2026-01-12T14:30:00Z
  Last import: 2026-01-12T10:15:00Z
  Domains synced: unity_xr, web_frontend, ml_training
```

## CLI Reference

### Commands

| Command | Description |
|---------|-------------|
| `export` | Export experiences to file |
| `import` | Import experiences from file |
| `sync-folder` | Sync with shared folder |
| `history` | Show sync operation history |
| `stats` | Show sync statistics |
| `config` | Show sync configuration |

### Global Options

| Option | Description |
|--------|-------------|
| `--json` | Output as JSON |
| `--verbose` | Verbose output |
| `--base-dir` | Base directory (default: current) |

### Export Options

| Option | Description |
|--------|-------------|
| `--output`, `-o` | Output file path (auto-generated if not specified) |
| `--domain`, `-d` | Filter by domain type |
| `--min-helpful-rate` | Minimum helpful rate filter (0.0-1.0) |
| `--min-retrievals` | Minimum retrieval count filter |
| `--no-compress` | Don't gzip compress output |

### Import Options

| Option | Description |
|--------|-------------|
| `file` | File to import (.jsonl or .jsonl.gz) |
| `--merge` | Merge with existing experiences (default) |
| `--replace` | Replace existing experiences |
| `--dry-run` | Only report what would happen |

### Sync-Folder Options

| Option | Description |
|--------|-------------|
| `path` | Path to shared folder |
| `--watch`, `-w` | Watch for changes continuously |
| `--no-export` | Don't export local experiences |
| `--no-import` | Don't import existing files |

## Privacy Guarantees

### What IS Shared

- Problem signatures and solutions
- Domain context (project type, language, frameworks)
- Success/retrieval/helpful counts
- Categories and tags
- Timestamps

### What is NEVER Shared

- Execution logs (detailed task history)
- Daemon logs
- File paths from your machine (sanitized in problem signatures)
- Analysis cache
- Process IDs or lock files

## Troubleshooting

### "watchdog package not available"

Install watchdog for folder watching:
```bash
pip install watchdog
```

### "File not found" during import

Ensure the file exists and is accessible:
```bash
ls -la path/to/file.jsonl.gz
```

### Conflicts not resolving as expected

Check helpful rates of both experiences:
```bash
# View local experience
python3 lib/experience-store.py get <experience_id>

# Import with verbose to see conflict details
python3 lib/experience-sync.py import file.jsonl.gz --verbose
```

### Large export files

Use quality filters to reduce size:
```bash
python3 lib/experience-sync.py export --min-helpful-rate 0.3 --min-retrievals 5
```

## Best Practices

1. **Regular exports**: Export weekly to keep shared knowledge fresh
2. **Quality filters**: Only share proven experiences (helpful_rate > 0.3)
3. **Domain focus**: Export specific domains for targeted sharing
4. **Review imports**: Use `--dry-run` before importing large files
5. **Audit regularly**: Check `history` and `stats` for sync health
6. **Backup before import**: Keep backups before large imports

## Integration with Privacy Config

Team sync respects privacy settings from `lib/privacy-config.py`:

```bash
# Check current privacy mode
python3 lib/privacy-config.py status

# Team sync requires TEAM_SYNC mode
python3 lib/privacy-config.py set-mode team_sync --sync-path /shared/experiences
```

In FULLY_LOCAL mode, sync operations still work but emit warnings about sharing.
