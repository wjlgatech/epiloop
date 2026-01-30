# Privacy Guarantees for claude-loop

This document describes the privacy architecture and guarantees of claude-loop, designed for enterprise users who require complete control over their data.

## Privacy Philosophy

**Default: FULLY_LOCAL** - All data stays on your machine. No network calls, no telemetry, no analytics, no phone-home. Ever.

We believe that:
1. Your code and experiences are **your intellectual property**
2. You should have **complete visibility** into what data is stored
3. You should have **complete control** over data sharing
4. Privacy should be the **default**, not an opt-in

## Privacy Modes

### FULLY_LOCAL (Default)

The default and most restrictive mode. Ideal for:
- Enterprise environments
- Sensitive projects
- Air-gapped systems
- Individual developers who value privacy

**Guarantees:**
- All data stored locally in `.claude-loop/`
- No network calls for the improvement system
- No telemetry collection
- No analytics
- No phone-home or heartbeat
- No cloud services

**What stays local:**
- Experiences (problem-solution pairs)
- Execution logs
- Improvement proposals
- Capability gap analyses
- All metrics and reports

### TEAM_SYNC (Optional)

For teams who want to share experiences without cloud services.

**How it works:**
- Sync via shared folder (NFS, SMB, etc.)
- Sync via git repository (private repo)
- NO cloud services involved
- Manual export/import for full control

**Guarantees:**
- Data only shared via configured path
- No automatic uploads
- No external network calls
- Full audit trail of synced data

**Configuration:**
```bash
python3 lib/privacy-config.py set-mode team_sync --sync-path /shared/team/claude-loop
# Or via git
python3 lib/privacy-config.py set-mode team_sync --git-remote git@github.com:your-org/private-experiences.git
```

### FEDERATED (Enterprise Agreement Required)

For large organizations with custom deployment needs.

**Requirements:**
- Explicit enterprise agreement
- Custom configuration
- May enable limited telemetry with consent

**Not recommended for:**
- Sensitive projects
- Individual developers
- Teams without dedicated security review

## Data Storage Locations

All data is stored in `.claude-loop/` relative to your project root:

| Location | Contains | Sensitive | Shareable |
|----------|----------|-----------|-----------|
| `experiences/` | Problem-solution pairs with domain context | No | Yes |
| `retrieval_outcomes.jsonl` | Retrieval quality tracking | No | Yes |
| `execution_log.jsonl` | Detailed execution history | **Yes** | No |
| `improvement_queue.json` | Queued improvement proposals | No | Yes |
| `capability_gaps.json` | Identified capability gaps | No | Yes |
| `analysis_cache/` | Cached root cause analyses | **Yes** | No |
| `improvement_history.jsonl` | Approval/rejection history | No | Yes |
| `improvements/` | Generated improvement PRDs | No | Yes |
| `validation_reports/` | Validation reports | No | Yes |
| `held_out_cases/` | Test cases for validation | No | Yes |
| `runs/` | Per-run metrics and reports | **Yes** | No |
| `cache/` | File content cache | **Yes** | No |
| `daemon_status.json` | Daemon status | No | No |
| `daemon.log` | Daemon activity log | **Yes** | No |

## CLI Commands

### Check Privacy Status

```bash
python3 lib/privacy-config.py status
```

Shows:
- Current privacy mode
- Telemetry/analytics status
- Data locations and sizes
- Sync configuration (if applicable)

### Privacy Audit

```bash
# View audit in terminal
python3 lib/privacy-config.py audit

# Export audit report
python3 lib/privacy-config.py audit --export audit_report.json
```

Shows:
- All stored data locations
- Size of each data store
- Number of records
- What would be shared in current mode
- Sensitive vs shareable data classification

### Export Data (Portable Format)

```bash
# Export all experiences
python3 lib/privacy-config.py export --output backup.jsonl.gz

# Export specific domain
python3 lib/privacy-config.py export --domain unity_xr --output unity_backup.jsonl.gz

# Export with quality filters
python3 lib/privacy-config.py export --output quality_backup.jsonl.gz \
    --min-helpful-rate 0.3 \
    --min-retrievals 5
```

Export format: JSONL (optionally gzipped) - portable and human-readable.

### Delete All Data

```bash
# Preview what will be deleted
python3 lib/privacy-config.py purge

# Actually delete (creates backup first)
python3 lib/privacy-config.py purge --confirm

# Delete without backup
python3 lib/privacy-config.py purge --confirm --no-backup
```

This completely removes all claude-loop data from your system.

## Never Shared

The following are NEVER shared, even in TEAM_SYNC mode:

- `daemon.pid` - Process IDs
- `daemon.lock` - Lock files
- `*.pid` - Any process ID files
- `*.lock` - Any lock files

## Network Isolation Verification

To verify no network calls are made, you can:

1. **Check the code**: All improvement system code is in `lib/` and makes no network calls in FULLY_LOCAL mode

2. **Monitor network**: Use tools like `tcpdump`, `wireshark`, or `lsof -i` to verify no outbound connections

3. **Firewall rules**: Block outbound connections for the process - claude-loop will work normally in FULLY_LOCAL mode

## Comparison with Other Tools

| Feature | claude-loop | Copilot | Cursor | Codeium |
|---------|------------|---------|--------|---------|
| Local-first by default | **Yes** | No | No | No |
| No cloud required | **Yes** | No | No | No |
| Self-hosted option | **Yes** | No | No | Partial |
| Full data export | **Yes** | No | No | Limited |
| Privacy audit CLI | **Yes** | No | No | No |
| Open source | **Yes** | No | No | No |

## For Security Teams

### Audit Checklist

1. Verify privacy mode: `python3 lib/privacy-config.py status`
2. Review stored data: `python3 lib/privacy-config.py audit`
3. Export audit report: `python3 lib/privacy-config.py audit --export security_audit.json`
4. Verify no network calls (see above)
5. Review data locations in `.claude-loop/`

### Compliance

claude-loop's FULLY_LOCAL mode is designed to support:
- GDPR (data stays local, full export/delete)
- HIPAA (no PHI transmitted)
- SOC2 (auditable, local-only)
- PCI-DSS (no cardholder data transmitted)

Note: Always consult your compliance team for specific requirements.

## Questions?

For privacy-related questions:
1. Review this document
2. Run `python3 lib/privacy-config.py audit` for your specific setup
3. Review the source code in `lib/privacy-config.py`
4. Open an issue at https://github.com/anthropics/claude-code/issues

## Summary

| Mode | Network Calls | Data Sharing | Use Case |
|------|--------------|--------------|----------|
| FULLY_LOCAL | **None** | **None** | Enterprise, sensitive, default |
| TEAM_SYNC | **None** | Local/Git only | Team collaboration |
| FEDERATED | Possible | With consent | Enterprise agreement |

**Default is FULLY_LOCAL** - maximum privacy, zero network calls, complete local control.
