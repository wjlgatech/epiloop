#!/usr/bin/env python3
"""
PRD Retention Policy Automation

Implements automated cleanup based on retention rules:
- Auto-abandon drafts inactive for 30+ days (with warning at 25)
- Move completed PRDs to archive after 90 days
- Delete abandoned PRDs after 30 days (keep audit entries)
- Compress archives older than 7 days

Usage:
    prd-retention.py check [--json]           Preview retention actions
    prd-retention.py run [--dry-run] [--json] Execute retention cleanup
    prd-retention.py stats [--json]           Show retention statistics
"""

import argparse
import hashlib
import json
import os
import shutil
import sys
import tarfile
from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

try:
    import yaml
except ImportError:
    print("Error: PyYAML is required. Install with: pip install pyyaml", file=sys.stderr)
    sys.exit(1)


# Default paths relative to script location
SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent
PRDS_DIR = PROJECT_ROOT / "prds"
ARCHIVE_DIR = PRDS_DIR / "archive"
CLAUDE_LOOP_DIR = PROJECT_ROOT / ".claude-loop"
AUDIT_LOG_FILE = CLAUDE_LOOP_DIR / "audit-log.jsonl"

# Retention policy configuration (in days)
RETENTION_CONFIG = {
    "draft_warning_days": 25,       # Warn about drafts inactive for 25+ days
    "draft_abandon_days": 30,       # Auto-abandon drafts inactive for 30+ days
    "completed_archive_days": 90,   # Archive completed PRDs after 90 days
    "abandoned_delete_days": 30,    # Delete abandoned PRDs after 30 days
    "archive_compress_days": 7,     # Compress archives older than 7 days
}


@dataclass
class RetentionAction:
    """Represents a retention action to be taken"""
    action_type: str  # 'warn', 'abandon', 'archive', 'delete', 'compress'
    prd_id: str
    prd_path: str
    reason: str
    age_days: int
    threshold_days: int
    details: dict = field(default_factory=dict)


@dataclass
class RetentionStats:
    """Statistics about PRD retention"""
    total_prds: int = 0
    drafts: int = 0
    active: int = 0
    completed: int = 0
    abandoned: int = 0
    archived: int = 0
    archived_compressed: int = 0
    warnings_issued: int = 0
    pending_actions: int = 0


def get_current_timestamp() -> str:
    """Get current timestamp in ISO 8601 format"""
    return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def parse_timestamp(timestamp_str: str) -> Optional[datetime]:
    """Parse ISO 8601 timestamp string to datetime"""
    if not timestamp_str:
        return None

    try:
        # Handle various ISO 8601 formats
        formats = [
            '%Y-%m-%dT%H:%M:%SZ',
            '%Y-%m-%dT%H:%M:%S.%fZ',
            '%Y-%m-%dT%H:%M:%S%z',
            '%Y-%m-%d',
        ]

        for fmt in formats:
            try:
                dt = datetime.strptime(timestamp_str, fmt)
                # Ensure timezone awareness
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                return dt
            except ValueError:
                continue

        return None
    except Exception:
        return None


def days_since(timestamp: datetime) -> int:
    """Calculate days since a timestamp"""
    now = datetime.now(timezone.utc)
    delta = now - timestamp
    return delta.days


def load_manifest(manifest_path: Path) -> Optional[dict]:
    """Load and parse a MANIFEST.yaml file"""
    try:
        with open(manifest_path, 'r') as f:
            return yaml.safe_load(f)
    except Exception as e:
        print(f"Warning: Failed to load {manifest_path}: {e}", file=sys.stderr)
        return None


def save_manifest(manifest_path: Path, manifest: dict) -> bool:
    """Save manifest to YAML file"""
    try:
        with open(manifest_path, 'w') as f:
            yaml.dump(manifest, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
        return True
    except Exception as e:
        print(f"Error saving manifest: {e}", file=sys.stderr)
        return False


def get_current_user() -> str:
    """Get the current user (from git config, env var, or system)"""
    import subprocess
    try:
        result = subprocess.run(
            ['git', 'config', 'user.name'],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    except Exception:
        pass

    for var in ['USER', 'USERNAME', 'LOGNAME']:
        user = os.environ.get(var)
        if user:
            return user

    return 'retention-policy'


def compute_content_hash(prd_dir: Path) -> str:
    """Compute SHA256 hash of PRD content (prd.json + MANIFEST.yaml)"""
    hasher = hashlib.sha256()

    prd_json_path = prd_dir / "prd.json"
    if prd_json_path.exists():
        with open(prd_json_path, 'rb') as f:
            hasher.update(f.read())

    manifest_path = prd_dir / "MANIFEST.yaml"
    if manifest_path.exists():
        with open(manifest_path, 'rb') as f:
            hasher.update(f.read())

    return hasher.hexdigest()


def get_previous_audit_hash() -> Optional[str]:
    """Get the hash from the last audit log entry for chain verification"""
    if not AUDIT_LOG_FILE.exists():
        return None

    last_entry = None
    with open(AUDIT_LOG_FILE, 'r') as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    last_entry = json.loads(line)
                except json.JSONDecodeError:
                    continue

    if last_entry:
        return last_entry.get('entry_hash')
    return None


def compute_entry_hash(entry: dict, previous_hash: Optional[str]) -> str:
    """Compute hash for an audit entry, chaining with previous entry"""
    entry_copy = {k: v for k, v in entry.items() if k != 'entry_hash'}
    entry_str = json.dumps(entry_copy, sort_keys=True)

    if previous_hash:
        entry_str = previous_hash + entry_str

    return hashlib.sha256(entry_str.encode('utf-8')).hexdigest()


def log_audit_entry(
    action: str,
    prd_id: str,
    prd_dir: Path,
    actor: Optional[str] = None,
    details: Optional[dict] = None,
    silent: bool = False
) -> bool:
    """Log an audit entry to the audit log file"""
    try:
        CLAUDE_LOOP_DIR.mkdir(parents=True, exist_ok=True)

        previous_hash = get_previous_audit_hash()
        content_hash = compute_content_hash(prd_dir)

        entry = {
            "timestamp": get_current_timestamp(),
            "action": action,
            "prd_id": prd_id,
            "actor": actor or get_current_user(),
            "content_hash": content_hash,
            "prd_path": str(prd_dir),
            "previous_hash": previous_hash,
        }

        if details:
            entry["details"] = details

        entry["entry_hash"] = compute_entry_hash(entry, previous_hash)

        with open(AUDIT_LOG_FILE, 'a') as f:
            f.write(json.dumps(entry) + '\n')

        return True

    except Exception as e:
        if not silent:
            print(f"Warning: Failed to log audit entry: {e}", file=sys.stderr)
        return False


def update_prd_index(silent: bool = False) -> bool:
    """Update the PRD index after any state change"""
    try:
        import importlib.util
        indexer_path = SCRIPT_DIR / "prd-indexer.py"

        if not indexer_path.exists():
            if not silent:
                print("Warning: prd-indexer.py not found, index not updated", file=sys.stderr)
            return False

        spec = importlib.util.spec_from_file_location("prd_indexer", indexer_path)
        if spec is None or spec.loader is None:
            return False

        indexer = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(indexer)

        index = indexer.build_index(PRDS_DIR)

        INDEX_FILE = CLAUDE_LOOP_DIR / "prd-index.json"
        CLAUDE_LOOP_DIR.mkdir(parents=True, exist_ok=True)

        if indexer.save_index(index, INDEX_FILE):
            return True
        return False

    except Exception as e:
        if not silent:
            print(f"Warning: Failed to update index: {e}", file=sys.stderr)
        return False


def get_prd_last_activity(prd_dir: Path, manifest: dict) -> Optional[datetime]:
    """Get the most recent activity date for a PRD"""
    dates = []

    # Check various timestamp fields in manifest
    timestamp_fields = ['updated_at', 'created_at', 'approved_at', 'completed_at', 'abandoned_at']
    for field_name in timestamp_fields:
        val = manifest.get(field_name)
        if val:
            dt = parse_timestamp(str(val))
            if dt:
                dates.append(dt)

    # Also check file modification times
    for filename in ['prd.json', 'MANIFEST.yaml', 'progress.txt']:
        filepath = prd_dir / filename
        if filepath.exists():
            try:
                mtime = filepath.stat().st_mtime
                dates.append(datetime.fromtimestamp(mtime, tz=timezone.utc))
            except Exception:
                pass

    return max(dates) if dates else None


def scan_for_retention_actions(prds_dir: Path) -> tuple[list[RetentionAction], RetentionStats]:
    """Scan PRDs and determine retention actions needed"""
    actions = []
    stats = RetentionStats()

    # Scan each status directory
    for status_dir_name in ['drafts', 'active', 'completed', 'abandoned']:
        status_dir = prds_dir / status_dir_name
        if not status_dir.exists():
            continue

        for prd_dir in status_dir.iterdir():
            if not prd_dir.is_dir() or prd_dir.name.startswith('.'):
                continue

            manifest_path = prd_dir / 'MANIFEST.yaml'
            if not manifest_path.exists():
                continue

            manifest = load_manifest(manifest_path)
            if not manifest:
                continue

            prd_id = manifest.get('id', prd_dir.name)
            status = manifest.get('status', 'unknown')

            stats.total_prds += 1

            # Track status counts
            if status == 'draft':
                stats.drafts += 1
            elif status == 'active':
                stats.active += 1
            elif status == 'completed':
                stats.completed += 1
            elif status == 'abandoned':
                stats.abandoned += 1

            # Get last activity date
            last_activity = get_prd_last_activity(prd_dir, manifest)
            if not last_activity:
                continue

            age_days = days_since(last_activity)

            # Check draft retention
            if status == 'draft':
                if age_days >= RETENTION_CONFIG['draft_abandon_days']:
                    actions.append(RetentionAction(
                        action_type='abandon',
                        prd_id=prd_id,
                        prd_path=str(prd_dir),
                        reason=f"Draft inactive for {age_days} days (threshold: {RETENTION_CONFIG['draft_abandon_days']} days)",
                        age_days=age_days,
                        threshold_days=RETENTION_CONFIG['draft_abandon_days'],
                        details={'status': status, 'last_activity': str(last_activity)}
                    ))
                elif age_days >= RETENTION_CONFIG['draft_warning_days']:
                    actions.append(RetentionAction(
                        action_type='warn',
                        prd_id=prd_id,
                        prd_path=str(prd_dir),
                        reason=f"Draft inactive for {age_days} days (auto-abandon at {RETENTION_CONFIG['draft_abandon_days']} days)",
                        age_days=age_days,
                        threshold_days=RETENTION_CONFIG['draft_warning_days'],
                        details={'status': status, 'last_activity': str(last_activity), 'days_until_abandon': RETENTION_CONFIG['draft_abandon_days'] - age_days}
                    ))
                    stats.warnings_issued += 1

            # Check completed PRD archival
            elif status == 'completed':
                if age_days >= RETENTION_CONFIG['completed_archive_days']:
                    actions.append(RetentionAction(
                        action_type='archive',
                        prd_id=prd_id,
                        prd_path=str(prd_dir),
                        reason=f"Completed PRD older than {age_days} days (threshold: {RETENTION_CONFIG['completed_archive_days']} days)",
                        age_days=age_days,
                        threshold_days=RETENTION_CONFIG['completed_archive_days'],
                        details={'status': status, 'completed_at': manifest.get('completed_at')}
                    ))

            # Check abandoned PRD deletion
            elif status == 'abandoned':
                if age_days >= RETENTION_CONFIG['abandoned_delete_days']:
                    actions.append(RetentionAction(
                        action_type='delete',
                        prd_id=prd_id,
                        prd_path=str(prd_dir),
                        reason=f"Abandoned PRD older than {age_days} days (threshold: {RETENTION_CONFIG['abandoned_delete_days']} days)",
                        age_days=age_days,
                        threshold_days=RETENTION_CONFIG['abandoned_delete_days'],
                        details={'status': status, 'abandoned_at': manifest.get('abandoned_at'), 'abandon_reason': manifest.get('abandon_reason')}
                    ))

    # Check for archives to compress
    archive_dir = prds_dir / 'archive'
    if archive_dir.exists():
        for item in archive_dir.iterdir():
            if item.is_dir():
                stats.archived += 1

                # Check if archive should be compressed
                try:
                    mtime = item.stat().st_mtime
                    age = datetime.now(timezone.utc) - datetime.fromtimestamp(mtime, tz=timezone.utc)
                    if age.days >= RETENTION_CONFIG['archive_compress_days']:
                        actions.append(RetentionAction(
                            action_type='compress',
                            prd_id=item.name,
                            prd_path=str(item),
                            reason=f"Archive older than {age.days} days (threshold: {RETENTION_CONFIG['archive_compress_days']} days)",
                            age_days=age.days,
                            threshold_days=RETENTION_CONFIG['archive_compress_days'],
                            details={'archive_path': str(item)}
                        ))
                except Exception:
                    pass

            elif item.suffix in ['.tar', '.gz', '.tgz']:
                stats.archived_compressed += 1

    stats.pending_actions = len([a for a in actions if a.action_type != 'warn'])

    return actions, stats


def execute_abandon_action(action: RetentionAction, dry_run: bool = False) -> tuple[bool, str]:
    """Execute an auto-abandon action on a draft PRD"""
    prd_path = Path(action.prd_path)

    if dry_run:
        return True, f"Would abandon {action.prd_id} (inactive for {action.age_days} days)"

    # Load manifest
    manifest_path = prd_path / 'MANIFEST.yaml'
    manifest = load_manifest(manifest_path)
    if not manifest:
        return False, "Could not load MANIFEST.yaml"

    timestamp = get_current_timestamp()

    # Update manifest
    manifest['status'] = 'abandoned'
    manifest['updated_at'] = timestamp
    manifest['abandoned_at'] = timestamp
    manifest['abandon_reason'] = f"Auto-abandoned by retention policy: inactive for {action.age_days} days"

    if not save_manifest(manifest_path, manifest):
        return False, "Failed to save MANIFEST.yaml"

    # Move to abandoned directory
    target_dir = PRDS_DIR / 'abandoned' / prd_path.name

    if target_dir.exists():
        return False, f"Target directory already exists: {target_dir}"

    try:
        target_dir.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(prd_path), str(target_dir))
    except Exception as e:
        return False, f"Failed to move directory: {e}"

    # Log audit entry
    log_audit_entry(
        action="retention_abandon",
        prd_id=action.prd_id,
        prd_dir=target_dir,
        actor="retention-policy",
        details={
            "reason": f"Auto-abandoned: inactive for {action.age_days} days",
            "previous_status": "draft",
            "age_days": action.age_days
        },
        silent=True
    )

    return True, f"Abandoned {action.prd_id} and moved to {target_dir}"


def execute_archive_action(action: RetentionAction, dry_run: bool = False) -> tuple[bool, str]:
    """Execute an archive action on a completed PRD"""
    prd_path = Path(action.prd_path)

    if dry_run:
        return True, f"Would archive {action.prd_id} (completed {action.age_days} days ago)"

    # Create archive directory
    archive_dir = PRDS_DIR / 'archive'
    archive_dir.mkdir(parents=True, exist_ok=True)

    target_dir = archive_dir / prd_path.name

    if target_dir.exists():
        return False, f"Archive already exists: {target_dir}"

    try:
        shutil.move(str(prd_path), str(target_dir))
    except Exception as e:
        return False, f"Failed to move to archive: {e}"

    # Log audit entry
    log_audit_entry(
        action="retention_archive",
        prd_id=action.prd_id,
        prd_dir=target_dir,
        actor="retention-policy",
        details={
            "reason": f"Archived: completed for {action.age_days} days",
            "previous_location": str(prd_path),
            "age_days": action.age_days
        },
        silent=True
    )

    return True, f"Archived {action.prd_id} to {target_dir}"


def execute_delete_action(action: RetentionAction, dry_run: bool = False) -> tuple[bool, str]:
    """Execute a delete action on an abandoned PRD (keeps audit entry)"""
    prd_path = Path(action.prd_path)

    if dry_run:
        return True, f"Would delete {action.prd_id} (abandoned {action.age_days} days ago)"

    # Log audit entry BEFORE deletion (preserves record)
    log_audit_entry(
        action="retention_delete",
        prd_id=action.prd_id,
        prd_dir=prd_path,
        actor="retention-policy",
        details={
            "reason": f"Deleted: abandoned for {action.age_days} days",
            "abandon_reason": action.details.get('abandon_reason'),
            "age_days": action.age_days
        },
        silent=True
    )

    try:
        shutil.rmtree(prd_path)
    except Exception as e:
        return False, f"Failed to delete: {e}"

    return True, f"Deleted {action.prd_id} (audit entry preserved)"


def execute_compress_action(action: RetentionAction, dry_run: bool = False) -> tuple[bool, str]:
    """Execute a compress action on an archived PRD"""
    archive_path = Path(action.prd_path)

    if dry_run:
        return True, f"Would compress {action.prd_id} archive ({action.age_days} days old)"

    # Create tar.gz archive
    tar_path = archive_path.with_suffix('.tar.gz')

    if tar_path.exists():
        return False, f"Compressed archive already exists: {tar_path}"

    try:
        with tarfile.open(tar_path, 'w:gz') as tar:
            tar.add(archive_path, arcname=archive_path.name)

        # Remove original directory after successful compression
        shutil.rmtree(archive_path)
    except Exception as e:
        # Clean up partial tar file on failure
        if tar_path.exists():
            tar_path.unlink()
        return False, f"Failed to compress: {e}"

    return True, f"Compressed {action.prd_id} to {tar_path}"


def execute_retention_actions(
    actions: list[RetentionAction],
    dry_run: bool = False
) -> tuple[int, int, list[dict]]:
    """Execute all retention actions

    Returns:
        Tuple of (success_count, failure_count, results)
    """
    success_count = 0
    failure_count = 0
    results = []

    for action in actions:
        # Skip warnings (they're informational only)
        if action.action_type == 'warn':
            results.append({
                "prd_id": action.prd_id,
                "action": action.action_type,
                "success": True,
                "message": action.reason,
                "skipped": False
            })
            continue

        # Execute the action
        if action.action_type == 'abandon':
            success, message = execute_abandon_action(action, dry_run)
        elif action.action_type == 'archive':
            success, message = execute_archive_action(action, dry_run)
        elif action.action_type == 'delete':
            success, message = execute_delete_action(action, dry_run)
        elif action.action_type == 'compress':
            success, message = execute_compress_action(action, dry_run)
        else:
            success = False
            message = f"Unknown action type: {action.action_type}"

        results.append({
            "prd_id": action.prd_id,
            "action": action.action_type,
            "success": success,
            "message": message,
            "dry_run": dry_run
        })

        if success:
            success_count += 1
        else:
            failure_count += 1

    # Update index after changes
    if not dry_run and (success_count > 0):
        update_prd_index(silent=True)

    return success_count, failure_count, results


def format_action_table(actions: list[RetentionAction]) -> str:
    """Format retention actions as a table"""
    if not actions:
        return "No retention actions pending."

    lines = [
        f"{'Action':<10}  {'PRD ID':<20}  {'Age':<8}  {'Threshold':<10}  {'Reason'}",
        "-" * 90
    ]

    for action in actions:
        action_display = action.action_type.upper()
        prd_id_display = action.prd_id[:20]
        age_display = f"{action.age_days}d"
        threshold_display = f"{action.threshold_days}d"

        # Truncate reason if too long
        reason_display = action.reason[:45] + "..." if len(action.reason) > 48 else action.reason

        lines.append(f"{action_display:<10}  {prd_id_display:<20}  {age_display:<8}  {threshold_display:<10}  {reason_display}")

    return '\n'.join(lines)


def cmd_check(args):
    """Handle 'check' command - Preview retention actions"""
    if not PRDS_DIR.exists():
        print(f"Error: PRDs directory not found at {PRDS_DIR}", file=sys.stderr)
        return 1

    actions, stats = scan_for_retention_actions(PRDS_DIR)

    if args.json:
        output = {
            "actions": [asdict(a) for a in actions],
            "stats": asdict(stats),
            "retention_config": RETENTION_CONFIG
        }
        print(json.dumps(output, indent=2, default=str))
    else:
        print("Retention Policy Check")
        print("=" * 50)
        print()
        print(f"Configuration:")
        print(f"  Draft warning at:       {RETENTION_CONFIG['draft_warning_days']} days inactive")
        print(f"  Draft auto-abandon at:  {RETENTION_CONFIG['draft_abandon_days']} days inactive")
        print(f"  Archive completed at:   {RETENTION_CONFIG['completed_archive_days']} days")
        print(f"  Delete abandoned at:    {RETENTION_CONFIG['abandoned_delete_days']} days")
        print(f"  Compress archives at:   {RETENTION_CONFIG['archive_compress_days']} days")
        print()
        print(f"Current Stats:")
        print(f"  Total PRDs:      {stats.total_prds}")
        print(f"  Drafts:          {stats.drafts}")
        print(f"  Active:          {stats.active}")
        print(f"  Completed:       {stats.completed}")
        print(f"  Abandoned:       {stats.abandoned}")
        print(f"  Archived:        {stats.archived}")
        print(f"  Compressed:      {stats.archived_compressed}")
        print()

        if actions:
            # Separate warnings from actions
            warnings = [a for a in actions if a.action_type == 'warn']
            pending = [a for a in actions if a.action_type != 'warn']

            if warnings:
                print("Warnings:")
                print("-" * 50)
                for w in warnings:
                    days_left = w.details.get('days_until_abandon', '?')
                    print(f"  ⚠ {w.prd_id}: {w.reason}")
                    print(f"    Days until auto-abandon: {days_left}")
                print()

            if pending:
                print("Pending Actions:")
                print("-" * 50)
                print(format_action_table(pending))
                print()
                print(f"Total actions pending: {len(pending)}")
                print()
                print("To execute these actions, run:")
                print("  prd-retention.py run")
                print()
                print("To preview without making changes:")
                print("  prd-retention.py run --dry-run")
            else:
                print("No actions pending.")
        else:
            print("No retention actions or warnings found.")

    return 0


def cmd_run(args):
    """Handle 'run' command - Execute retention cleanup"""
    if not PRDS_DIR.exists():
        print(f"Error: PRDs directory not found at {PRDS_DIR}", file=sys.stderr)
        return 1

    actions, _stats = scan_for_retention_actions(PRDS_DIR)

    # Filter out warnings for execution
    executable_actions = [a for a in actions if a.action_type != 'warn']

    if not executable_actions:
        if args.json:
            print(json.dumps({"success": True, "message": "No actions to execute", "executed": 0}))
        else:
            print("No retention actions to execute.")
        return 0

    if args.dry_run:
        print("DRY RUN - No changes will be made")
        print("=" * 50)
        print()

    success_count, failure_count, results = execute_retention_actions(executable_actions, args.dry_run)

    if args.json:
        output = {
            "success": failure_count == 0,
            "dry_run": args.dry_run,
            "executed": success_count,
            "failed": failure_count,
            "results": results
        }
        print(json.dumps(output, indent=2))
    else:
        print("Retention Execution Results")
        print("=" * 50)
        print()

        for result in results:
            status = "✓" if result['success'] else "✗"
            action = result['action'].upper()
            prd_id = result['prd_id']
            message = result['message']

            print(f"  {status} [{action}] {prd_id}")
            print(f"    {message}")

        print()
        print(f"Summary:")
        print(f"  Successful: {success_count}")
        print(f"  Failed:     {failure_count}")

        if args.dry_run:
            print()
            print("(Dry run - no changes were made)")

    return 0 if failure_count == 0 else 1


def cmd_stats(args):
    """Handle 'stats' command - Show retention statistics"""
    if not PRDS_DIR.exists():
        print(f"Error: PRDs directory not found at {PRDS_DIR}", file=sys.stderr)
        return 1

    actions, stats = scan_for_retention_actions(PRDS_DIR)

    # Count actions by type
    action_counts = {}
    for action in actions:
        action_counts[action.action_type] = action_counts.get(action.action_type, 0) + 1

    if args.json:
        output = {
            "stats": asdict(stats),
            "action_counts": action_counts,
            "retention_config": RETENTION_CONFIG
        }
        print(json.dumps(output, indent=2))
    else:
        print("Retention Statistics")
        print("=" * 50)
        print()
        print(f"PRD Counts:")
        print(f"  Total PRDs:             {stats.total_prds}")
        print(f"  Drafts:                 {stats.drafts}")
        print(f"  Active:                 {stats.active}")
        print(f"  Completed:              {stats.completed}")
        print(f"  Abandoned:              {stats.abandoned}")
        print(f"  Archived:               {stats.archived}")
        print(f"  Compressed archives:    {stats.archived_compressed}")
        print()
        print(f"Pending Actions:")
        print(f"  Warnings:               {action_counts.get('warn', 0)}")
        print(f"  Auto-abandon:           {action_counts.get('abandon', 0)}")
        print(f"  Archive:                {action_counts.get('archive', 0)}")
        print(f"  Delete:                 {action_counts.get('delete', 0)}")
        print(f"  Compress:               {action_counts.get('compress', 0)}")
        print(f"  Total pending actions:  {stats.pending_actions}")

    return 0


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="PRD Retention Policy Automation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Preview retention actions without executing
  %(prog)s check

  # Execute retention cleanup
  %(prog)s run

  # Dry-run to preview what would happen
  %(prog)s run --dry-run

  # View retention statistics
  %(prog)s stats

  # JSON output for scripting
  %(prog)s check --json
  %(prog)s run --json
  %(prog)s stats --json

Retention Policies:
  - Drafts inactive for 25+ days: Warning issued
  - Drafts inactive for 30+ days: Auto-abandoned
  - Completed PRDs after 90 days: Moved to archive
  - Abandoned PRDs after 30 days: Deleted (audit log preserved)
  - Archives older than 7 days: Compressed to tar.gz
"""
    )

    subparsers = parser.add_subparsers(dest='command', help='Available commands')

    # Check command
    check_parser = subparsers.add_parser('check', help='Preview retention actions')
    check_parser.add_argument(
        '--json',
        action='store_true',
        help='Output as JSON'
    )

    # Run command
    run_parser = subparsers.add_parser('run', help='Execute retention cleanup')
    run_parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Preview changes without executing'
    )
    run_parser.add_argument(
        '--json',
        action='store_true',
        help='Output as JSON'
    )

    # Stats command
    stats_parser = subparsers.add_parser('stats', help='Show retention statistics')
    stats_parser.add_argument(
        '--json',
        action='store_true',
        help='Output as JSON'
    )

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 0

    commands = {
        'check': cmd_check,
        'run': cmd_run,
        'stats': cmd_stats,
    }

    handler = commands.get(args.command)
    if handler:
        return handler(args)
    else:
        parser.print_help()
        return 1


if __name__ == '__main__':
    sys.exit(main())
