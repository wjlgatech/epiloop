#!/usr/bin/env python3
"""
PRD Manager CLI - Core and Lifecycle Commands

Provides list, show, search, and lifecycle management for PRDs.
Part of the documentation management system for claude-loop.

Usage:
    prd-manager.py list [--status STATUS] [--json]
    prd-manager.py show <prd_id_or_path> [--json]
    prd-manager.py search <query> [--tag TAG] [--json]
    prd-manager.py create <prd_id> <title> [--owner OWNER] [--type TYPE]
    prd-manager.py approve <prd_id> [--approver APPROVER] [--notes NOTES]
    prd-manager.py abandon <prd_id> --reason REASON [--superseded-by ID]
    prd-manager.py complete <prd_id> [--notes NOTES]
    prd-manager.py verify [<prd_id>] [--fix] [--json]
    prd-manager.py audit [--prd PRD_ID] [--action ACTION] [--limit N] [--json]
    prd-manager.py audit verify [--json]
"""

import argparse
import hashlib
import json
import os
import shutil
import sys
from dataclasses import dataclass, asdict
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
TEMPLATES_DIR = PROJECT_ROOT / "templates"
CLAUDE_LOOP_DIR = PROJECT_ROOT / ".claude-loop"
INDEX_FILE = CLAUDE_LOOP_DIR / "prd-index.json"
AUDIT_LOG_FILE = CLAUDE_LOOP_DIR / "audit-log.jsonl"


@dataclass
class PRDInfo:
    """Summary information about a PRD"""
    id: str
    title: str
    status: str
    owner: str
    created_at: str
    path: str
    description: Optional[str] = None
    tags: Optional[list] = None
    story_count: Optional[int] = None
    completed_stories: Optional[int] = None
    branch_name: Optional[str] = None
    priority: Optional[str] = None
    updated_at: Optional[str] = None
    approved_at: Optional[str] = None
    completed_at: Optional[str] = None
    abandoned_at: Optional[str] = None
    abandon_reason: Optional[str] = None
    superseded_by: Optional[str] = None
    supersedes: Optional[list] = None


def find_prds_directory() -> Path:
    """Find the prds/ directory, checking multiple locations"""
    # Check common locations
    candidates = [
        PRDS_DIR,
        Path.cwd() / "prds",
        PROJECT_ROOT / "prds",
    ]

    for candidate in candidates:
        if candidate.exists() and candidate.is_dir():
            return candidate

    # If none found, return default (will error on use)
    return PRDS_DIR


def load_manifest(manifest_path: Path) -> Optional[dict]:
    """Load and parse a MANIFEST.yaml file"""
    try:
        with open(manifest_path, 'r') as f:
            return yaml.safe_load(f)
    except Exception as e:
        print(f"Warning: Failed to load {manifest_path}: {e}", file=sys.stderr)
        return None


def load_prd_json(prd_path: Path) -> Optional[dict]:
    """Load and parse a prd.json file"""
    try:
        with open(prd_path, 'r') as f:
            return json.load(f)
    except Exception as e:
        print(f"Warning: Failed to load {prd_path}: {e}", file=sys.stderr)
        return None


def get_prd_info(prd_dir: Path) -> Optional[PRDInfo]:
    """Extract PRD info from a PRD directory"""
    manifest_path = prd_dir / "MANIFEST.yaml"
    prd_json_path = prd_dir / "prd.json"

    if not manifest_path.exists():
        return None

    manifest = load_manifest(manifest_path)
    if not manifest:
        return None

    # Get story counts from prd.json if available
    story_count = manifest.get('story_count')
    completed_stories = manifest.get('completed_stories')

    if prd_json_path.exists() and (story_count is None or completed_stories is None):
        prd_data = load_prd_json(prd_json_path)
        if prd_data:
            stories = prd_data.get('userStories', [])
            story_count = len(stories)
            completed_stories = sum(1 for s in stories if s.get('passes', False))

    # Handle supersedes as list
    supersedes = manifest.get('supersedes')
    if isinstance(supersedes, str):
        supersedes = [supersedes]

    return PRDInfo(
        id=manifest.get('id', 'UNKNOWN'),
        title=manifest.get('title', 'Untitled'),
        status=manifest.get('status', 'unknown'),
        owner=manifest.get('owner', 'unknown'),
        created_at=manifest.get('created_at', ''),
        path=str(prd_dir),
        description=manifest.get('description'),
        tags=manifest.get('tags', []),
        story_count=story_count,
        completed_stories=completed_stories,
        branch_name=manifest.get('branch_name'),
        priority=manifest.get('priority'),
        updated_at=manifest.get('updated_at'),
        approved_at=manifest.get('approved_at'),
        completed_at=manifest.get('completed_at'),
        abandoned_at=manifest.get('abandoned_at'),
        abandon_reason=manifest.get('abandon_reason'),
        superseded_by=manifest.get('superseded_by'),
        supersedes=supersedes,
    )


def scan_prds(prds_dir: Path, status_filter: Optional[str] = None) -> list[PRDInfo]:
    """Scan the prds/ directory for all PRDs"""
    prds = []

    # Status subdirectories to scan
    status_dirs = ['active', 'completed', 'abandoned', 'drafts']

    for status_dir_name in status_dirs:
        status_dir = prds_dir / status_dir_name
        if not status_dir.exists():
            continue

        # Each subdirectory in status_dir is a PRD
        for prd_dir in status_dir.iterdir():
            if not prd_dir.is_dir():
                continue
            if prd_dir.name.startswith('.'):
                continue

            prd_info = get_prd_info(prd_dir)
            if prd_info:
                # Apply status filter if provided
                if status_filter and prd_info.status != status_filter:
                    continue
                prds.append(prd_info)

    # Sort by created_at (newest first) - ensure string comparison
    def sort_key(p):
        val = p.created_at
        if val is None:
            return ''
        return str(val) if not isinstance(val, str) else val
    prds.sort(key=sort_key, reverse=True)
    return prds


def format_prd_table(prds: list[PRDInfo]) -> str:
    """Format PRDs as a table for terminal output"""
    if not prds:
        return "No PRDs found."

    # Calculate column widths
    id_width = max(len(p.id) for p in prds)
    id_width = max(id_width, len('ID'))

    title_width = min(40, max(len(p.title[:40]) for p in prds))
    title_width = max(title_width, len('Title'))

    # Build rows
    rows = []
    for p in prds:
        progress = f"{p.completed_stories or 0}/{p.story_count or 0}"
        title_display = p.title[:37] + '...' if len(p.title) > 40 else p.title
        rows.append([
            p.id,
            title_display,
            p.status,
            progress,
            p.priority or '-',
            p.owner,
        ])

    # Build output
    header_line = f"{'ID':<{id_width}}  {'Title':<{title_width}}  {'Status':<10}  {'Stories':<8}  {'Priority':<8}  {'Owner'}"
    separator = '-' * len(header_line)

    lines = [header_line, separator]
    for row in rows:
        lines.append(f"{row[0]:<{id_width}}  {row[1]:<{title_width}}  {row[2]:<10}  {row[3]:<8}  {row[4]:<8}  {row[5]}")

    return '\n'.join(lines)


def format_prd_detail(prd: PRDInfo, prd_data: Optional[dict] = None) -> str:
    """Format detailed PRD information for terminal output"""
    lines = [
        f"PRD: {prd.id}",
        f"{'=' * (5 + len(prd.id))}",
        f"",
        f"Title:       {prd.title}",
        f"Status:      {prd.status}",
        f"Owner:       {prd.owner}",
        f"Priority:    {prd.priority or '-'}",
        f"Path:        {prd.path}",
    ]

    if prd.branch_name:
        lines.append(f"Branch:      {prd.branch_name}")

    if prd.description:
        lines.append(f"")
        lines.append(f"Description:")
        # Word wrap description at 70 chars
        words = prd.description.split()
        current_line = "  "
        for word in words:
            if len(current_line) + len(word) + 1 > 72:
                lines.append(current_line)
                current_line = "  " + word
            else:
                current_line += " " + word if current_line != "  " else word
        if current_line.strip():
            lines.append(current_line)

    lines.append(f"")
    lines.append(f"Progress:    {prd.completed_stories or 0}/{prd.story_count or 0} stories completed")

    if prd.tags:
        lines.append(f"Tags:        {', '.join(prd.tags)}")

    lines.append(f"")
    lines.append(f"Timeline:")
    lines.append(f"  Created:   {prd.created_at or '-'}")
    if prd.approved_at:
        lines.append(f"  Approved:  {prd.approved_at}")
    if prd.completed_at:
        lines.append(f"  Completed: {prd.completed_at}")
    if prd.abandoned_at:
        lines.append(f"  Abandoned: {prd.abandoned_at}")
    if prd.updated_at:
        lines.append(f"  Updated:   {prd.updated_at}")

    if prd.abandon_reason:
        lines.append(f"")
        lines.append(f"Abandon Reason:")
        lines.append(f"  {prd.abandon_reason}")

    if prd.superseded_by:
        lines.append(f"")
        lines.append(f"Superseded by: {prd.superseded_by}")

    if prd.supersedes:
        lines.append(f"Supersedes:    {', '.join(prd.supersedes)}")

    # Show user stories if available
    if prd_data and 'userStories' in prd_data:
        lines.append(f"")
        lines.append(f"User Stories:")
        lines.append(f"-" * 60)
        for story in prd_data['userStories']:
            status = "✓" if story.get('passes', False) else "○"
            lines.append(f"  {status} {story.get('id', '?')}: {story.get('title', 'Untitled')}")

    return '\n'.join(lines)


def find_prd_by_id_or_path(identifier: str, prds_dir: Path) -> Optional[tuple[PRDInfo, Path]]:
    """Find a PRD by its ID or path"""
    # First, check if it's a path
    if os.path.exists(identifier):
        path = Path(identifier)
        if path.is_file():
            path = path.parent
        prd_info = get_prd_info(path)
        if prd_info:
            return (prd_info, path)

    # Search by ID
    all_prds = scan_prds(prds_dir)
    for prd in all_prds:
        if prd.id.lower() == identifier.lower():
            return (prd, Path(prd.path))

    # Search by partial ID
    matches = [p for p in all_prds if identifier.lower() in p.id.lower()]
    if len(matches) == 1:
        return (matches[0], Path(matches[0].path))
    elif len(matches) > 1:
        print(f"Multiple PRDs match '{identifier}':", file=sys.stderr)
        for m in matches:
            print(f"  - {m.id}: {m.title}", file=sys.stderr)
        return None

    return None


def search_prds(prds_dir: Path, query: str, tag: Optional[str] = None) -> list[PRDInfo]:
    """Search PRDs by keyword and/or tag"""
    all_prds = scan_prds(prds_dir)
    results = []

    query_lower = query.lower()

    for prd in all_prds:
        # Check tag filter first
        if tag:
            if not prd.tags or tag.lower() not in [t.lower() for t in prd.tags]:
                continue

        # Search in ID, title, description, and tags
        searchable = ' '.join(filter(None, [
            prd.id,
            prd.title,
            prd.description,
            ' '.join(prd.tags or []),
            prd.owner,
        ])).lower()

        if query_lower in searchable:
            results.append(prd)

    return results


# =============================================================================
# Lifecycle Command Helpers
# =============================================================================

# Valid state transitions
VALID_TRANSITIONS = {
    'draft': ['active', 'abandoned'],
    'active': ['completed', 'abandoned'],
    'completed': [],  # Terminal state
    'abandoned': [],  # Terminal state
}

# Status directory mapping
STATUS_TO_DIR = {
    'draft': 'drafts',
    'active': 'active',
    'completed': 'completed',
    'abandoned': 'abandoned',
}


def get_current_timestamp() -> str:
    """Get current timestamp in ISO 8601 format"""
    return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def get_current_user() -> str:
    """Get the current user (from git config, env var, or system)"""
    # Try git config first
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

    # Try environment variables
    for var in ['USER', 'USERNAME', 'LOGNAME']:
        user = os.environ.get(var)
        if user:
            return user

    return 'unknown'


def compute_prd_hash(prd_json_path: Path) -> str:
    """Compute SHA256 hash of prd.json file"""
    with open(prd_json_path, 'rb') as f:
        return hashlib.sha256(f.read()).hexdigest()


def save_manifest(manifest_path: Path, manifest: dict) -> bool:
    """Save manifest to YAML file"""
    try:
        with open(manifest_path, 'w') as f:
            yaml.dump(manifest, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
        return True
    except Exception as e:
        print(f"Error saving manifest: {e}", file=sys.stderr)
        return False


def validate_state_transition(current_status: str, target_status: str) -> tuple[bool, str]:
    """Validate if a state transition is allowed"""
    if current_status not in VALID_TRANSITIONS:
        return False, f"Unknown current status: {current_status}"

    valid_targets = VALID_TRANSITIONS[current_status]

    if target_status not in valid_targets:
        if not valid_targets:
            return False, f"Cannot transition from '{current_status}' - it is a terminal state"
        return False, f"Cannot transition from '{current_status}' to '{target_status}'. Valid transitions: {', '.join(valid_targets)}"

    return True, ""


def update_prd_index(silent: bool = False) -> bool:
    """Update the PRD index after any state change

    This function imports and calls the prd-indexer to rebuild the index.
    It's called automatically after create, approve, abandon, and complete commands.
    """
    try:
        # Import the indexer module
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

        # Build and save index
        prds_dir = find_prds_directory()
        index = indexer.build_index(prds_dir)

        # Ensure .claude-loop directory exists
        CLAUDE_LOOP_DIR.mkdir(parents=True, exist_ok=True)

        # Save the index
        if indexer.save_index(index, INDEX_FILE):
            return True
        return False

    except Exception as e:
        if not silent:
            print(f"Warning: Failed to update index: {e}", file=sys.stderr)
        return False


# =============================================================================
# Audit Log Functions
# =============================================================================

def compute_content_hash(prd_dir: Path) -> str:
    """Compute SHA256 hash of PRD content (prd.json + MANIFEST.yaml)"""
    hasher = hashlib.sha256()

    # Hash prd.json if it exists
    prd_json_path = prd_dir / "prd.json"
    if prd_json_path.exists():
        with open(prd_json_path, 'rb') as f:
            hasher.update(f.read())

    # Hash MANIFEST.yaml if it exists
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
    # Create a deterministic string from the entry
    # Exclude entry_hash from the hash computation
    entry_copy = {k: v for k, v in entry.items() if k != 'entry_hash'}
    entry_str = json.dumps(entry_copy, sort_keys=True)

    # Chain with previous hash
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
    """Log an audit entry to the audit log file

    Args:
        action: The action performed (create, approve, abandon, complete)
        prd_id: The PRD ID
        prd_dir: Path to the PRD directory
        actor: Who performed the action (default: current user)
        details: Additional details about the action
        silent: If True, suppress error messages

    Returns:
        True if entry was logged successfully, False otherwise
    """
    try:
        # Ensure .claude-loop directory exists
        CLAUDE_LOOP_DIR.mkdir(parents=True, exist_ok=True)

        # Get the previous hash for chaining
        previous_hash = get_previous_audit_hash()

        # Compute content hash of the PRD
        content_hash = compute_content_hash(prd_dir)

        # Build the audit entry
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

        # Compute entry hash (including chain to previous)
        entry["entry_hash"] = compute_entry_hash(entry, previous_hash)

        # Append to audit log
        with open(AUDIT_LOG_FILE, 'a') as f:
            f.write(json.dumps(entry) + '\n')

        return True

    except Exception as e:
        if not silent:
            print(f"Warning: Failed to log audit entry: {e}", file=sys.stderr)
        return False


def read_audit_log(
    prd_id: Optional[str] = None,
    action: Optional[str] = None,
    limit: Optional[int] = None
) -> list[dict]:
    """Read audit log entries with optional filtering

    Args:
        prd_id: Filter by PRD ID
        action: Filter by action type
        limit: Maximum number of entries to return (most recent first)

    Returns:
        List of audit entries (newest first)
    """
    if not AUDIT_LOG_FILE.exists():
        return []

    entries = []
    with open(AUDIT_LOG_FILE, 'r') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)

                # Apply filters
                if prd_id and entry.get('prd_id', '').lower() != prd_id.lower():
                    continue
                if action and entry.get('action', '').lower() != action.lower():
                    continue

                entries.append(entry)
            except json.JSONDecodeError:
                continue

    # Return newest first
    entries.reverse()

    # Apply limit
    if limit:
        entries = entries[:limit]

    return entries


def verify_audit_chain() -> tuple[bool, list[str]]:
    """Verify the integrity of the audit log hash chain

    Returns:
        Tuple of (is_valid, list of issues)
    """
    if not AUDIT_LOG_FILE.exists():
        return True, []  # Empty log is valid

    issues = []
    entries = []

    # Read all entries
    with open(AUDIT_LOG_FILE, 'r') as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
                entries.append((line_num, entry))
            except json.JSONDecodeError:
                issues.append(f"Line {line_num}: Invalid JSON")

    if not entries:
        return True, []  # Empty log is valid

    # Verify the chain
    previous_hash = None
    for line_num, entry in entries:
        stored_hash = entry.get('entry_hash')
        stored_previous = entry.get('previous_hash')

        # Check previous hash matches
        if stored_previous != previous_hash:
            issues.append(
                f"Line {line_num} ({entry.get('prd_id')}): Chain broken - "
                f"previous_hash mismatch"
            )

        # Recompute and verify entry hash
        expected_hash = compute_entry_hash(entry, previous_hash)
        if stored_hash != expected_hash:
            issues.append(
                f"Line {line_num} ({entry.get('prd_id')}): Entry hash mismatch - "
                f"entry may have been tampered with"
            )

        previous_hash = stored_hash

    return len(issues) == 0, issues


# =============================================================================
# Integrity Verification Functions
# =============================================================================

@dataclass
class IntegrityIssue:
    """Represents an integrity issue found during verification"""
    prd_id: str
    issue_type: str  # 'hash_mismatch', 'missing_approval', 'audit_chain_broken', 'missing_manifest'
    description: str
    current_value: Optional[str] = None
    expected_value: Optional[str] = None
    fixable: bool = False
    prd_path: Optional[str] = None


def verify_prd_integrity(prd_dir: Path) -> list[IntegrityIssue]:
    """Verify integrity of a single PRD

    Checks:
    1. MANIFEST.yaml exists and is valid
    2. For active/completed PRDs: approval_hash matches current prd.json hash
    3. For approved PRDs: approval block exists in MANIFEST.yaml

    Returns:
        List of IntegrityIssue objects found
    """
    issues = []

    manifest_path = prd_dir / 'MANIFEST.yaml'
    prd_json_path = prd_dir / 'prd.json'

    # Check if MANIFEST.yaml exists
    if not manifest_path.exists():
        issues.append(IntegrityIssue(
            prd_id=prd_dir.name,
            issue_type='missing_manifest',
            description=f"MANIFEST.yaml not found in {prd_dir}",
            fixable=False,
            prd_path=str(prd_dir)
        ))
        return issues

    # Load manifest
    manifest = load_manifest(manifest_path)
    if not manifest:
        issues.append(IntegrityIssue(
            prd_id=prd_dir.name,
            issue_type='invalid_manifest',
            description=f"Could not parse MANIFEST.yaml in {prd_dir}",
            fixable=False,
            prd_path=str(prd_dir)
        ))
        return issues

    prd_id = manifest.get('id', prd_dir.name)
    status = manifest.get('status', 'unknown')

    # For active or completed PRDs, check approval hash
    if status in ['active', 'completed']:
        approval = manifest.get('approval', {})
        stored_hash = approval.get('approval_hash')

        if not stored_hash:
            issues.append(IntegrityIssue(
                prd_id=prd_id,
                issue_type='missing_approval',
                description=f"PRD is {status} but has no approval_hash in MANIFEST.yaml",
                fixable=True,
                prd_path=str(prd_dir)
            ))
        elif prd_json_path.exists():
            # Compute current hash and compare
            current_hash = compute_prd_hash(prd_json_path)

            if current_hash != stored_hash:
                issues.append(IntegrityIssue(
                    prd_id=prd_id,
                    issue_type='hash_mismatch',
                    description=f"prd.json has been modified since approval",
                    current_value=current_hash,
                    expected_value=stored_hash,
                    fixable=True,
                    prd_path=str(prd_dir)
                ))
        else:
            issues.append(IntegrityIssue(
                prd_id=prd_id,
                issue_type='missing_prd_json',
                description=f"prd.json not found for {status} PRD",
                fixable=False,
                prd_path=str(prd_dir)
            ))

    return issues


def verify_all_prds(prds_dir: Path) -> list[IntegrityIssue]:
    """Verify integrity of all PRDs in the prds/ directory

    Returns:
        List of IntegrityIssue objects found across all PRDs
    """
    all_issues = []

    # Status subdirectories to scan
    status_dirs = ['active', 'completed', 'abandoned', 'drafts']

    for status_dir_name in status_dirs:
        status_dir = prds_dir / status_dir_name
        if not status_dir.exists():
            continue

        # Each subdirectory in status_dir is a PRD
        for prd_dir in status_dir.iterdir():
            if not prd_dir.is_dir():
                continue
            if prd_dir.name.startswith('.'):
                continue

            issues = verify_prd_integrity(prd_dir)
            all_issues.extend(issues)

    return all_issues


def fix_prd_hash(prd_dir: Path, dry_run: bool = False) -> tuple[bool, str]:
    """Fix the approval_hash for a PRD by recalculating it

    Args:
        prd_dir: Path to the PRD directory
        dry_run: If True, don't actually modify files

    Returns:
        Tuple of (success, message)
    """
    manifest_path = prd_dir / 'MANIFEST.yaml'
    prd_json_path = prd_dir / 'prd.json'

    if not manifest_path.exists():
        return False, "MANIFEST.yaml not found"

    if not prd_json_path.exists():
        return False, "prd.json not found"

    manifest = load_manifest(manifest_path)
    if not manifest:
        return False, "Could not parse MANIFEST.yaml"

    # Compute new hash
    new_hash = compute_prd_hash(prd_json_path)
    old_hash = manifest.get('approval', {}).get('approval_hash')

    if dry_run:
        return True, f"Would update approval_hash from {old_hash[:12]}... to {new_hash[:12]}..."

    # Update manifest
    if 'approval' not in manifest:
        manifest['approval'] = {
            'approved_by': get_current_user(),
            'approved_at': get_current_timestamp(),
        }

    manifest['approval']['approval_hash'] = new_hash
    manifest['approval']['hash_fixed_at'] = get_current_timestamp()
    manifest['approval']['hash_fixed_by'] = get_current_user()
    manifest['updated_at'] = get_current_timestamp()

    if save_manifest(manifest_path, manifest):
        return True, f"Updated approval_hash from {old_hash[:12] if old_hash else 'none'}... to {new_hash[:12]}..."
    else:
        return False, "Failed to save MANIFEST.yaml"


def move_prd_directory(prd_dir: Path, prds_dir: Path, new_status: str) -> Optional[Path]:
    """Move a PRD directory to the appropriate status subdirectory"""
    target_status_dir = STATUS_TO_DIR.get(new_status)
    if not target_status_dir:
        print(f"Error: Unknown status '{new_status}'", file=sys.stderr)
        return None

    target_dir = prds_dir / target_status_dir / prd_dir.name

    # Check if target already exists
    if target_dir.exists():
        print(f"Error: Target directory already exists: {target_dir}", file=sys.stderr)
        return None

    # Create parent directory if needed
    target_dir.parent.mkdir(parents=True, exist_ok=True)

    # Move the directory
    try:
        shutil.move(str(prd_dir), str(target_dir))
        return target_dir
    except Exception as e:
        print(f"Error moving PRD directory: {e}", file=sys.stderr)
        return None


def load_prd_template(prd_type: str) -> Optional[dict]:
    """Load a PRD template from the templates directory

    Args:
        prd_type: Type of template (feature, bugfix, refactor)

    Returns:
        Template dict if found, None otherwise
    """
    template_map = {
        'feature': 'prd-feature.json',
        'bugfix': 'prd-bugfix.json',
        'refactor': 'prd-refactor.json',
    }

    template_file = template_map.get(prd_type)
    if not template_file:
        return None

    template_path = TEMPLATES_DIR / template_file
    if not template_path.exists():
        return None

    try:
        with open(template_path, 'r') as f:
            return json.load(f)
    except Exception as e:
        print(f"Warning: Failed to load template {template_path}: {e}", file=sys.stderr)
        return None


def load_manifest_template() -> Optional[str]:
    """Load the manifest template from the templates directory

    Returns:
        Template string if found, None otherwise
    """
    template_path = TEMPLATES_DIR / 'manifest.yaml'
    if not template_path.exists():
        return None

    try:
        with open(template_path, 'r') as f:
            return f.read()
    except Exception as e:
        print(f"Warning: Failed to load manifest template: {e}", file=sys.stderr)
        return None


def apply_template_variables(template_str: str, variables: dict) -> str:
    """Replace {{VAR}} placeholders in template string with actual values

    Args:
        template_str: Template string with {{VAR}} placeholders
        variables: Dict mapping variable names to values

    Returns:
        String with placeholders replaced
    """
    result = template_str
    for key, value in variables.items():
        placeholder = f"{{{{{key}}}}}"
        result = result.replace(placeholder, str(value))
    return result


def create_prd_template(prd_id: str, title: str, prd_type: str = 'feature') -> dict:
    """Create a prd.json based on type, using external template if available

    Args:
        prd_id: The PRD ID (e.g., DOC-001)
        title: The PRD title
        prd_type: Type of PRD (feature, bugfix, refactor)

    Returns:
        Dict containing the prd.json structure
    """
    # Try to load external template first
    template = load_prd_template(prd_type)

    if template:
        # Apply variable substitutions
        project_name = title.lower().replace(' ', '-')
        project_name = ''.join(c for c in project_name if c.isalnum() or c == '-')

        # Define branch prefix based on type
        branch_prefix = {
            'feature': 'feature',
            'bugfix': 'fix',
            'refactor': 'refactor',
        }.get(prd_type, 'feature')

        variables = {
            'PRD_ID': prd_id,
            'PRD_ID_LOWER': prd_id.lower(),
            'PROJECT_NAME': project_name,
            'TITLE': title,
            'DESCRIPTION': f"[Description for {title}]",
        }

        # Convert template to string, apply variables, convert back
        template_str = json.dumps(template)
        template_str = apply_template_variables(template_str, variables)
        result = json.loads(template_str)

        # Remove template metadata fields
        result.pop('$schema', None)
        result.pop('$comment', None)

        return result

    # Fallback to inline template if external template not found
    branch_prefix = {
        'feature': 'feature',
        'bugfix': 'fix',
        'refactor': 'refactor',
    }.get(prd_type, 'feature')

    template = {
        "project": title.lower().replace(' ', '-'),
        "branchName": f"{branch_prefix}/{prd_id.lower()}",
        "description": f"[Description for {title}]",
        "source_project": None,
        "userStories": []
    }

    # Add starter stories based on type (fallback inline templates)
    if prd_type == 'feature':
        template["userStories"] = [
            {
                "id": f"{prd_id}-001",
                "title": "Initial Setup",
                "description": "Set up the basic structure for this feature",
                "acceptanceCriteria": [
                    "Create necessary files and directories",
                    "Add basic configuration",
                ],
                "priority": 1,
                "passes": False,
                "notes": ""
            }
        ]
    elif prd_type == 'bugfix':
        template["userStories"] = [
            {
                "id": f"{prd_id}-001",
                "title": "Investigate Bug",
                "description": "Investigate root cause of the bug",
                "acceptanceCriteria": [
                    "Identify the root cause",
                    "Document findings",
                ],
                "priority": 1,
                "passes": False,
                "notes": ""
            },
            {
                "id": f"{prd_id}-002",
                "title": "Implement Fix",
                "description": "Implement the bug fix",
                "acceptanceCriteria": [
                    "Fix the issue",
                    "Add regression test",
                ],
                "priority": 2,
                "passes": False,
                "notes": ""
            }
        ]
    elif prd_type == 'refactor':
        template["userStories"] = [
            {
                "id": f"{prd_id}-001",
                "title": "Analysis and Planning",
                "description": "Analyze current implementation and plan refactoring",
                "acceptanceCriteria": [
                    "Document current structure",
                    "Define target architecture",
                ],
                "priority": 1,
                "passes": False,
                "notes": ""
            },
            {
                "id": f"{prd_id}-002",
                "title": "Implement Refactoring",
                "description": "Execute the refactoring plan",
                "acceptanceCriteria": [
                    "Refactor code according to plan",
                    "Ensure tests pass",
                ],
                "priority": 2,
                "passes": False,
                "notes": ""
            }
        ]

    return template


def create_manifest_template(prd_id: str, title: str, owner: str, prd_type: str = 'feature', story_count: int = 1) -> dict:
    """Create a MANIFEST.yaml from template or inline

    Args:
        prd_id: The PRD ID (e.g., DOC-001)
        title: The PRD title
        owner: The owner name
        prd_type: Type of PRD (feature, bugfix, refactor)
        story_count: Number of stories in the PRD

    Returns:
        Dict containing the manifest structure
    """
    timestamp = get_current_timestamp()

    # Define branch prefix based on type
    branch_prefix = {
        'feature': 'feature',
        'bugfix': 'fix',
        'refactor': 'refactor',
    }.get(prd_type, 'feature')

    # Try to load and process external template
    manifest_template_str = load_manifest_template()

    if manifest_template_str:
        # Apply variable substitutions
        variables = {
            'PRD_ID': prd_id,
            'TITLE': title,
            'OWNER': owner,
            'CREATED_AT': timestamp,
            'DESCRIPTION': f"[Description for {title}]",
            'BRANCH_NAME': f"{branch_prefix}/{prd_id.lower()}",
            'STORY_COUNT': story_count,
        }

        processed_template = apply_template_variables(manifest_template_str, variables)

        try:
            manifest = yaml.safe_load(processed_template)
            if manifest:
                return manifest
        except Exception as e:
            print(f"Warning: Failed to parse manifest template: {e}", file=sys.stderr)
            # Fall through to inline template

    # Fallback to inline template
    return {
        "id": prd_id,
        "title": title,
        "status": "draft",
        "owner": owner,
        "created_at": timestamp,
        "updated_at": timestamp,
        "tags": [],
        "priority": "medium",
        "description": f"[Description for {title}]",
        "story_count": story_count,
        "completed_stories": 0,
        "branch_name": f"{branch_prefix}/{prd_id.lower()}",
        "contributors": [
            {
                "name": owner,
                "role": "author",
                "added_at": timestamp
            }
        ]
    }


def cmd_list(args):
    """Handle 'list' command"""
    prds_dir = find_prds_directory()

    if not prds_dir.exists():
        print(f"Error: PRDs directory not found at {prds_dir}", file=sys.stderr)
        return 1

    prds = scan_prds(prds_dir, status_filter=args.status)

    if args.json:
        output = [asdict(p) for p in prds]
        print(json.dumps(output, indent=2, default=str))
    else:
        print(format_prd_table(prds))
        print(f"\nTotal: {len(prds)} PRD(s)")

    return 0


def cmd_show(args):
    """Handle 'show' command"""
    prds_dir = find_prds_directory()

    result = find_prd_by_id_or_path(args.prd_id, prds_dir)
    if not result:
        print(f"Error: PRD '{args.prd_id}' not found", file=sys.stderr)
        return 1

    prd_info, prd_path = result

    # Load prd.json for story details
    prd_json_path = prd_path / "prd.json"
    prd_data = None
    if prd_json_path.exists():
        prd_data = load_prd_json(prd_json_path)

    if args.json:
        output = asdict(prd_info)
        if prd_data:
            output['prd_data'] = prd_data
        print(json.dumps(output, indent=2, default=str))
    else:
        print(format_prd_detail(prd_info, prd_data))

    return 0


def cmd_search(args):
    """Handle 'search' command"""
    prds_dir = find_prds_directory()

    if not prds_dir.exists():
        print(f"Error: PRDs directory not found at {prds_dir}", file=sys.stderr)
        return 1

    results = search_prds(prds_dir, args.query, tag=args.tag)

    if args.json:
        output = [asdict(p) for p in results]
        print(json.dumps(output, indent=2, default=str))
    else:
        if results:
            print(f"Search results for '{args.query}'")
            if args.tag:
                print(f"(filtered by tag: {args.tag})")
            print()
            print(format_prd_table(results))
            print(f"\nFound: {len(results)} PRD(s)")
        else:
            print(f"No PRDs found matching '{args.query}'")
            if args.tag:
                print(f"(with tag: {args.tag})")

    return 0


# =============================================================================
# Lifecycle Command Handlers
# =============================================================================

def cmd_create(args):
    """Handle 'create' command - Create a new PRD in drafts"""
    prds_dir = find_prds_directory()

    if not prds_dir.exists():
        print(f"Error: PRDs directory not found at {prds_dir}", file=sys.stderr)
        return 1

    prd_id = args.prd_id.upper()
    title = args.title
    owner = args.owner or get_current_user()
    prd_type = args.type or 'feature'

    # Validate PRD ID format
    import re
    if not re.match(r'^[A-Z]+-[0-9]{3,}$', prd_id):
        print(f"Error: Invalid PRD ID format '{prd_id}'. Expected format: PREFIX-NNN (e.g., DOC-001)", file=sys.stderr)
        return 1

    # Check if PRD ID already exists
    existing = find_prd_by_id_or_path(prd_id, prds_dir)
    if existing:
        print(f"Error: PRD '{prd_id}' already exists at {existing[1]}", file=sys.stderr)
        return 1

    # Create the PRD directory in drafts/
    prd_dir_name = title.lower().replace(' ', '-').replace('_', '-')
    prd_dir_name = re.sub(r'[^a-z0-9-]', '', prd_dir_name)  # Remove special chars
    prd_dir = prds_dir / 'drafts' / prd_dir_name

    if prd_dir.exists():
        print(f"Error: Directory already exists: {prd_dir}", file=sys.stderr)
        return 1

    # Create directory and files
    try:
        prd_dir.mkdir(parents=True, exist_ok=True)

        # Create prd.json
        prd_json = create_prd_template(prd_id, title, prd_type)
        prd_json_path = prd_dir / 'prd.json'
        with open(prd_json_path, 'w') as f:
            json.dump(prd_json, f, indent=2)

        # Create MANIFEST.yaml
        story_count = len(prd_json['userStories'])
        manifest = create_manifest_template(prd_id, title, owner, prd_type, story_count)
        manifest_path = prd_dir / 'MANIFEST.yaml'
        save_manifest(manifest_path, manifest)

        # Create progress.txt
        progress_path = prd_dir / 'progress.txt'
        with open(progress_path, 'w') as f:
            f.write(f"# Progress Log: {prd_id}\n")
            f.write(f"# Created: {get_current_timestamp()}\n")
            f.write("#\n")
            f.write("# This file tracks learnings and progress across claude-loop iterations.\n\n")

    except Exception as e:
        print(f"Error creating PRD: {e}", file=sys.stderr)
        # Clean up on failure
        if prd_dir.exists():
            shutil.rmtree(prd_dir)
        return 1

    # Log audit entry for creation
    log_audit_entry(
        action="create",
        prd_id=prd_id,
        prd_dir=prd_dir,
        actor=owner,
        details={"title": title, "type": prd_type},
        silent=True
    )

    if args.json:
        output = {
            "success": True,
            "prd_id": prd_id,
            "title": title,
            "path": str(prd_dir),
            "status": "draft",
            "type": prd_type,
        }
        print(json.dumps(output, indent=2))
    else:
        print(f"Created PRD: {prd_id}")
        print(f"  Title:  {title}")
        print(f"  Owner:  {owner}")
        print(f"  Type:   {prd_type}")
        print(f"  Path:   {prd_dir}")
        print(f"  Status: draft")
        print(f"\nNext steps:")
        print(f"  1. Edit {prd_dir}/prd.json to add user stories")
        print(f"  2. Run: prd-manager.py approve {prd_id} --approver <name>")

    # Update index after creation
    update_prd_index(silent=True)

    return 0


def cmd_approve(args):
    """Handle 'approve' command - Transition draft to active"""
    prds_dir = find_prds_directory()

    result = find_prd_by_id_or_path(args.prd_id, prds_dir)
    if not result:
        print(f"Error: PRD '{args.prd_id}' not found", file=sys.stderr)
        return 1

    prd_info, prd_path = result

    # Validate state transition
    valid, error = validate_state_transition(prd_info.status, 'active')
    if not valid:
        print(f"Error: {error}", file=sys.stderr)
        return 1

    # Load manifest
    manifest_path = prd_path / 'MANIFEST.yaml'
    manifest = load_manifest(manifest_path)
    if not manifest:
        print(f"Error: Could not load MANIFEST.yaml", file=sys.stderr)
        return 1

    # Compute hash of prd.json
    prd_json_path = prd_path / 'prd.json'
    if not prd_json_path.exists():
        print(f"Error: prd.json not found in {prd_path}", file=sys.stderr)
        return 1

    approval_hash = compute_prd_hash(prd_json_path)
    approver = args.approver or get_current_user()
    timestamp = get_current_timestamp()

    # Update manifest
    manifest['status'] = 'active'
    manifest['updated_at'] = timestamp
    manifest['approved_at'] = timestamp
    manifest['approval'] = {
        'approved_by': approver,
        'approved_at': timestamp,
        'approval_hash': approval_hash,
    }
    if args.notes:
        manifest['approval']['notes'] = args.notes

    # Add approver to contributors if not already present
    contributors = manifest.get('contributors', [])
    approver_exists = any(c.get('name') == approver and c.get('role') == 'approver' for c in contributors)
    if not approver_exists:
        contributors.append({
            'name': approver,
            'role': 'approver',
            'added_at': timestamp
        })
        manifest['contributors'] = contributors

    # Save updated manifest
    if not save_manifest(manifest_path, manifest):
        return 1

    # Move directory from drafts/ to active/
    new_path = move_prd_directory(prd_path, prds_dir, 'active')
    if not new_path:
        # Revert manifest changes
        manifest['status'] = 'draft'
        del manifest['approved_at']
        del manifest['approval']
        save_manifest(manifest_path, manifest)
        return 1

    # Log audit entry for approval
    log_audit_entry(
        action="approve",
        prd_id=prd_info.id,
        prd_dir=new_path,
        actor=approver,
        details={
            "approval_hash": approval_hash,
            "previous_status": "draft",
            "notes": args.notes
        },
        silent=True
    )

    if args.json:
        output = {
            "success": True,
            "prd_id": prd_info.id,
            "status": "active",
            "approved_by": approver,
            "approval_hash": approval_hash,
            "path": str(new_path),
        }
        print(json.dumps(output, indent=2))
    else:
        print(f"Approved PRD: {prd_info.id}")
        print(f"  Status:        draft -> active")
        print(f"  Approved by:   {approver}")
        print(f"  Approval hash: {approval_hash[:16]}...")
        print(f"  New path:      {new_path}")

    # Update index after approval
    update_prd_index(silent=True)

    return 0


def cmd_abandon(args):
    """Handle 'abandon' command - Mark PRD as abandoned"""
    prds_dir = find_prds_directory()

    result = find_prd_by_id_or_path(args.prd_id, prds_dir)
    if not result:
        print(f"Error: PRD '{args.prd_id}' not found", file=sys.stderr)
        return 1

    prd_info, prd_path = result

    # Validate state transition
    valid, error = validate_state_transition(prd_info.status, 'abandoned')
    if not valid:
        print(f"Error: {error}", file=sys.stderr)
        return 1

    # Load manifest
    manifest_path = prd_path / 'MANIFEST.yaml'
    manifest = load_manifest(manifest_path)
    if not manifest:
        print(f"Error: Could not load MANIFEST.yaml", file=sys.stderr)
        return 1

    timestamp = get_current_timestamp()
    old_status = prd_info.status

    # Update manifest
    manifest['status'] = 'abandoned'
    manifest['updated_at'] = timestamp
    manifest['abandoned_at'] = timestamp
    manifest['abandon_reason'] = args.reason

    if args.superseded_by:
        manifest['superseded_by'] = args.superseded_by.upper()

    # Save updated manifest
    if not save_manifest(manifest_path, manifest):
        return 1

    # Move directory to abandoned/
    new_path = move_prd_directory(prd_path, prds_dir, 'abandoned')
    if not new_path:
        # Revert manifest changes
        manifest['status'] = old_status
        del manifest['abandoned_at']
        del manifest['abandon_reason']
        if 'superseded_by' in manifest:
            del manifest['superseded_by']
        save_manifest(manifest_path, manifest)
        return 1

    # Log audit entry for abandonment
    log_audit_entry(
        action="abandon",
        prd_id=prd_info.id,
        prd_dir=new_path,
        details={
            "reason": args.reason,
            "previous_status": old_status,
            "superseded_by": args.superseded_by.upper() if args.superseded_by else None
        },
        silent=True
    )

    if args.json:
        output = {
            "success": True,
            "prd_id": prd_info.id,
            "status": "abandoned",
            "reason": args.reason,
            "superseded_by": args.superseded_by,
            "path": str(new_path),
        }
        print(json.dumps(output, indent=2))
    else:
        print(f"Abandoned PRD: {prd_info.id}")
        print(f"  Status:  {old_status} -> abandoned")
        print(f"  Reason:  {args.reason}")
        if args.superseded_by:
            print(f"  Superseded by: {args.superseded_by.upper()}")
        print(f"  New path: {new_path}")

    # Update index after abandonment
    update_prd_index(silent=True)

    return 0


def cmd_complete(args):
    """Handle 'complete' command - Mark PRD as completed"""
    prds_dir = find_prds_directory()

    result = find_prd_by_id_or_path(args.prd_id, prds_dir)
    if not result:
        print(f"Error: PRD '{args.prd_id}' not found", file=sys.stderr)
        return 1

    prd_info, prd_path = result

    # Validate state transition
    valid, error = validate_state_transition(prd_info.status, 'completed')
    if not valid:
        print(f"Error: {error}", file=sys.stderr)
        return 1

    # Load prd.json to check story completion
    prd_json_path = prd_path / 'prd.json'
    prd_data = load_prd_json(prd_json_path)
    total = 0
    completed = 0
    if prd_data:
        stories = prd_data.get('userStories', [])
        total = len(stories)
        completed = sum(1 for s in stories if s.get('passes', False))

        if completed < total and not args.force:
            print(f"Warning: Not all stories are complete ({completed}/{total})", file=sys.stderr)
            print(f"Use --force to complete anyway", file=sys.stderr)
            return 1

    # Load manifest
    manifest_path = prd_path / 'MANIFEST.yaml'
    manifest = load_manifest(manifest_path)
    if not manifest:
        print(f"Error: Could not load MANIFEST.yaml", file=sys.stderr)
        return 1

    timestamp = get_current_timestamp()
    old_status = prd_info.status

    # Update manifest
    manifest['status'] = 'completed'
    manifest['updated_at'] = timestamp
    manifest['completed_at'] = timestamp

    # Update story counts
    if prd_data:
        manifest['story_count'] = total
        manifest['completed_stories'] = completed

    if args.notes:
        if 'approval' in manifest:
            manifest['approval']['completion_notes'] = args.notes
        else:
            manifest['completion_notes'] = args.notes

    # Save updated manifest
    if not save_manifest(manifest_path, manifest):
        return 1

    # Move directory to completed/
    new_path = move_prd_directory(prd_path, prds_dir, 'completed')
    if not new_path:
        # Revert manifest changes
        manifest['status'] = old_status
        del manifest['completed_at']
        save_manifest(manifest_path, manifest)
        return 1

    # Log audit entry for completion
    log_audit_entry(
        action="complete",
        prd_id=prd_info.id,
        prd_dir=new_path,
        details={
            "previous_status": old_status,
            "stories_completed": completed,
            "stories_total": total,
            "forced": args.force,
            "notes": args.notes
        },
        silent=True
    )

    if args.json:
        output = {
            "success": True,
            "prd_id": prd_info.id,
            "status": "completed",
            "stories_completed": f"{completed}/{total}" if prd_data else "unknown",
            "path": str(new_path),
        }
        print(json.dumps(output, indent=2))
    else:
        print(f"Completed PRD: {prd_info.id}")
        print(f"  Status:   {old_status} -> completed")
        if prd_data:
            print(f"  Stories:  {completed}/{total} complete")
        print(f"  New path: {new_path}")

    # Update index after completion
    update_prd_index(silent=True)

    return 0


# =============================================================================
# Verify Command Handler
# =============================================================================

def cmd_verify(args):
    """Handle 'verify' command - Verify PRD integrity

    Checks:
    1. PRD approval hashes match current prd.json content
    2. Audit log hash chain is intact

    With --fix flag: Recalculate hashes for fixable issues
    """
    prds_dir = find_prds_directory()

    if not prds_dir.exists():
        print(f"Error: PRDs directory not found at {prds_dir}", file=sys.stderr)
        return 1

    all_issues = []
    prds_checked = 0
    prds_with_issues = 0

    # If a specific PRD is specified, verify only that one
    if args.prd_id:
        result = find_prd_by_id_or_path(args.prd_id, prds_dir)
        if not result:
            print(f"Error: PRD '{args.prd_id}' not found", file=sys.stderr)
            return 1

        prd_info, prd_path = result
        issues = verify_prd_integrity(prd_path)
        if issues:
            all_issues.extend(issues)
            prds_with_issues = 1
        prds_checked = 1
    else:
        # Verify all PRDs
        status_dirs = ['active', 'completed', 'abandoned', 'drafts']
        for status_dir_name in status_dirs:
            status_dir = prds_dir / status_dir_name
            if not status_dir.exists():
                continue

            for prd_dir in status_dir.iterdir():
                if not prd_dir.is_dir() or prd_dir.name.startswith('.'):
                    continue

                prds_checked += 1
                issues = verify_prd_integrity(prd_dir)
                if issues:
                    all_issues.extend(issues)
                    prds_with_issues += 1

    # Verify audit log hash chain
    audit_valid, audit_issues = verify_audit_chain()
    if not audit_valid:
        for audit_issue in audit_issues:
            all_issues.append(IntegrityIssue(
                prd_id='audit-log',
                issue_type='audit_chain_broken',
                description=audit_issue,
                fixable=False
            ))

    # Handle --fix option
    fixed_count = 0
    fix_failures = []

    if args.fix and all_issues:
        fixable_issues = [i for i in all_issues if i.fixable]

        if not fixable_issues:
            if not args.json:
                print("No fixable issues found.")
        else:
            if not args.json:
                print(f"Attempting to fix {len(fixable_issues)} issue(s)...")
                print()

            for issue in fixable_issues:
                if issue.prd_path:
                    prd_path = Path(issue.prd_path)
                    success, message = fix_prd_hash(prd_path)

                    if success:
                        fixed_count += 1
                        if not args.json:
                            print(f"  Fixed: {issue.prd_id} - {message}")
                    else:
                        fix_failures.append((issue.prd_id, message))
                        if not args.json:
                            print(f"  Failed: {issue.prd_id} - {message}")

            if not args.json:
                print()

    # Output results
    if args.json:
        output = {
            "verified": len(all_issues) == 0,
            "prds_checked": prds_checked,
            "prds_with_issues": prds_with_issues,
            "audit_log_valid": audit_valid,
            "issues": [asdict(i) for i in all_issues],
            "issues_count": len(all_issues),
            "fixable_count": sum(1 for i in all_issues if i.fixable),
        }

        if args.fix:
            output["fixed_count"] = fixed_count
            output["fix_failures"] = [{"prd_id": p, "reason": r} for p, r in fix_failures]

        print(json.dumps(output, indent=2))
    else:
        if not all_issues:
            print("Integrity Check: PASSED")
            print(f"  PRDs checked:    {prds_checked}")
            print(f"  Audit log:       {'Valid' if audit_valid else 'INVALID'}")
            print(f"  Issues found:    0")
        else:
            print("Integrity Check: FAILED")
            print(f"  PRDs checked:    {prds_checked}")
            print(f"  PRDs with issues: {prds_with_issues}")
            print(f"  Audit log:       {'Valid' if audit_valid else 'INVALID'}")
            print(f"  Total issues:    {len(all_issues)}")

            fixable = [i for i in all_issues if i.fixable]
            if fixable:
                print(f"  Fixable issues:  {len(fixable)}")

            print()
            print("Issues found:")
            print("-" * 70)

            for issue in all_issues:
                print(f"\n  [{issue.issue_type}] {issue.prd_id}")
                print(f"    Description: {issue.description}")
                if issue.expected_value:
                    print(f"    Expected:    {issue.expected_value[:16]}...")
                if issue.current_value:
                    print(f"    Current:     {issue.current_value[:16]}...")
                if issue.fixable:
                    print(f"    Fixable:     Yes (use --fix to repair)")
                if issue.prd_path:
                    print(f"    Path:        {issue.prd_path}")

            if fixable and not args.fix:
                print()
                print(f"Tip: Run with --fix to repair {len(fixable)} fixable issue(s)")

        if args.fix and fixed_count > 0:
            print()
            print(f"Fixed {fixed_count} issue(s)")

    return 0 if len(all_issues) == 0 else 1


# =============================================================================
# Audit Command Handlers
# =============================================================================

def format_audit_entry(entry: dict) -> str:
    """Format a single audit entry for terminal output"""
    timestamp = entry.get('timestamp', 'unknown')
    action = entry.get('action', 'unknown').upper()
    prd_id = entry.get('prd_id', 'unknown')
    actor = entry.get('actor', 'unknown')
    content_hash = entry.get('content_hash', '')[:12] + '...' if entry.get('content_hash') else '-'

    lines = [
        f"[{timestamp}] {action}: {prd_id}",
        f"  Actor: {actor}",
        f"  Hash:  {content_hash}",
    ]

    details = entry.get('details', {})
    if details:
        if details.get('reason'):
            lines.append(f"  Reason: {details['reason']}")
        if details.get('notes'):
            lines.append(f"  Notes: {details['notes']}")
        if details.get('superseded_by'):
            lines.append(f"  Superseded by: {details['superseded_by']}")
        if details.get('stories_completed') is not None and details.get('stories_total') is not None:
            lines.append(f"  Stories: {details['stories_completed']}/{details['stories_total']}")

    return '\n'.join(lines)


def format_audit_table(entries: list[dict]) -> str:
    """Format audit entries as a table"""
    if not entries:
        return "No audit entries found."

    # Build header
    lines = [
        f"{'Timestamp':<24}  {'Action':<10}  {'PRD ID':<15}  {'Actor':<15}  {'Hash':<14}",
        '-' * 85
    ]

    for entry in entries:
        timestamp = entry.get('timestamp', '-')[:24]
        action = entry.get('action', '-')
        prd_id = entry.get('prd_id', '-')[:15]
        actor = entry.get('actor', '-')[:15]
        content_hash = entry.get('content_hash', '')[:12] + '..' if entry.get('content_hash') else '-'

        lines.append(f"{timestamp:<24}  {action:<10}  {prd_id:<15}  {actor:<15}  {content_hash:<14}")

    return '\n'.join(lines)


def cmd_audit(args):
    """Handle 'audit' command - View audit log entries"""
    entries = read_audit_log(
        prd_id=args.prd,
        action=args.action,
        limit=args.limit
    )

    if args.json:
        print(json.dumps(entries, indent=2))
    else:
        if not entries:
            print("No audit entries found.")
            if args.prd:
                print(f"(filtered by PRD: {args.prd})")
            if args.action:
                print(f"(filtered by action: {args.action})")
        else:
            print(format_audit_table(entries))
            print(f"\nTotal: {len(entries)} entries")

    return 0


def cmd_audit_verify(args):
    """Handle 'audit verify' command - Verify audit log integrity"""
    is_valid, issues = verify_audit_chain()

    if args.json:
        output = {
            "valid": is_valid,
            "issues": issues,
            "log_file": str(AUDIT_LOG_FILE),
            "entry_count": len(read_audit_log())
        }
        print(json.dumps(output, indent=2))
    else:
        if is_valid:
            entry_count = len(read_audit_log())
            print("Audit log integrity: VERIFIED")
            print(f"  Log file: {AUDIT_LOG_FILE}")
            print(f"  Entries:  {entry_count}")
            print("  Status:   Hash chain intact")
        else:
            print("Audit log integrity: FAILED")
            print(f"  Log file: {AUDIT_LOG_FILE}")
            print(f"  Issues found: {len(issues)}")
            print()
            for issue in issues:
                print(f"  - {issue}")

    return 0 if is_valid else 1


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="PRD Manager - Manage Product Requirement Documents",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Core commands
  %(prog)s list                      List all PRDs
  %(prog)s list --status active      List only active PRDs
  %(prog)s list --json               Output as JSON
  %(prog)s show SCALE-001            Show details for PRD SCALE-001
  %(prog)s show prds/completed/x     Show PRD at specific path
  %(prog)s search memory             Search for PRDs containing 'memory'
  %(prog)s search memory --tag arch  Search with tag filter

  # Lifecycle commands
  %(prog)s create DOC-020 "My New Feature" --type feature
  %(prog)s approve DOC-020 --approver "John Doe"
  %(prog)s abandon DOC-020 --reason "Requirements changed"
  %(prog)s complete DOC-020

  # Integrity verification commands
  %(prog)s verify                      Verify all PRDs and audit log
  %(prog)s verify SI-001               Verify specific PRD
  %(prog)s verify --fix                Fix hash mismatches
  %(prog)s verify --json               Output as JSON

  # Audit commands
  %(prog)s audit                       View all audit entries
  %(prog)s audit --prd DOC-001         View entries for specific PRD
  %(prog)s audit --action approve      View only approve actions
  %(prog)s audit --limit 10            View last 10 entries
  %(prog)s audit verify                Verify audit log integrity
"""
    )

    subparsers = parser.add_subparsers(dest='command', help='Available commands')

    # List command
    list_parser = subparsers.add_parser('list', help='List all PRDs')
    list_parser.add_argument(
        '--status',
        choices=['draft', 'active', 'completed', 'abandoned'],
        help='Filter by status'
    )
    list_parser.add_argument(
        '--json',
        action='store_true',
        help='Output as JSON'
    )

    # Show command
    show_parser = subparsers.add_parser('show', help='Show PRD details')
    show_parser.add_argument(
        'prd_id',
        help='PRD ID or path to PRD directory'
    )
    show_parser.add_argument(
        '--json',
        action='store_true',
        help='Output as JSON'
    )

    # Search command
    search_parser = subparsers.add_parser('search', help='Search PRDs')
    search_parser.add_argument(
        'query',
        help='Search query (matches ID, title, description, tags)'
    )
    search_parser.add_argument(
        '--tag',
        help='Filter by tag'
    )
    search_parser.add_argument(
        '--json',
        action='store_true',
        help='Output as JSON'
    )

    # Create command
    create_parser = subparsers.add_parser('create', help='Create a new PRD')
    create_parser.add_argument(
        'prd_id',
        help='PRD ID (e.g., DOC-020)'
    )
    create_parser.add_argument(
        'title',
        help='PRD title'
    )
    create_parser.add_argument(
        '--owner',
        help='PRD owner (default: current user)'
    )
    create_parser.add_argument(
        '--type',
        choices=['feature', 'bugfix', 'refactor'],
        default='feature',
        help='PRD type for template (default: feature)'
    )
    create_parser.add_argument(
        '--json',
        action='store_true',
        help='Output as JSON'
    )

    # Approve command
    approve_parser = subparsers.add_parser('approve', help='Approve a draft PRD (transition to active)')
    approve_parser.add_argument(
        'prd_id',
        help='PRD ID to approve'
    )
    approve_parser.add_argument(
        '--approver',
        help='Approver name (default: current user)'
    )
    approve_parser.add_argument(
        '--notes',
        help='Approval notes'
    )
    approve_parser.add_argument(
        '--json',
        action='store_true',
        help='Output as JSON'
    )

    # Abandon command
    abandon_parser = subparsers.add_parser('abandon', help='Abandon a PRD')
    abandon_parser.add_argument(
        'prd_id',
        help='PRD ID to abandon'
    )
    abandon_parser.add_argument(
        '--reason',
        required=True,
        help='Reason for abandonment (required)'
    )
    abandon_parser.add_argument(
        '--superseded-by',
        help='PRD ID that supersedes this one'
    )
    abandon_parser.add_argument(
        '--json',
        action='store_true',
        help='Output as JSON'
    )

    # Complete command
    complete_parser = subparsers.add_parser('complete', help='Mark a PRD as completed')
    complete_parser.add_argument(
        'prd_id',
        help='PRD ID to complete'
    )
    complete_parser.add_argument(
        '--notes',
        help='Completion notes'
    )
    complete_parser.add_argument(
        '--force',
        action='store_true',
        help='Complete even if not all stories are done'
    )
    complete_parser.add_argument(
        '--json',
        action='store_true',
        help='Output as JSON'
    )

    # Verify command
    verify_parser = subparsers.add_parser(
        'verify',
        help='Verify PRD integrity (approval hashes and audit log)'
    )
    verify_parser.add_argument(
        'prd_id',
        nargs='?',
        help='PRD ID to verify (optional - if not specified, verifies all PRDs)'
    )
    verify_parser.add_argument(
        '--fix',
        action='store_true',
        help='Fix issues by recalculating hashes (admin only)'
    )
    verify_parser.add_argument(
        '--json',
        action='store_true',
        help='Output as JSON'
    )

    # Audit command with subcommands
    audit_parser = subparsers.add_parser('audit', help='View or verify audit log')
    audit_subparsers = audit_parser.add_subparsers(dest='audit_command', help='Audit subcommands')

    # Audit view (default when no subcommand)
    audit_parser.add_argument(
        '--prd',
        help='Filter by PRD ID'
    )
    audit_parser.add_argument(
        '--action',
        choices=['create', 'approve', 'abandon', 'complete'],
        help='Filter by action type'
    )
    audit_parser.add_argument(
        '--limit',
        type=int,
        help='Limit number of entries (most recent first)'
    )
    audit_parser.add_argument(
        '--json',
        action='store_true',
        help='Output as JSON'
    )

    # Audit verify subcommand
    audit_verify_parser = audit_subparsers.add_parser('verify', help='Verify audit log hash chain integrity')
    audit_verify_parser.add_argument(
        '--json',
        action='store_true',
        help='Output as JSON'
    )

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 0

    # Dispatch to command handler
    commands = {
        'list': cmd_list,
        'show': cmd_show,
        'search': cmd_search,
        'create': cmd_create,
        'approve': cmd_approve,
        'abandon': cmd_abandon,
        'complete': cmd_complete,
        'verify': cmd_verify,
    }

    # Handle audit command specially (has subcommands)
    if args.command == 'audit':
        if hasattr(args, 'audit_command') and args.audit_command == 'verify':
            return cmd_audit_verify(args)
        else:
            return cmd_audit(args)

    handler = commands.get(args.command)
    if handler:
        return handler(args)
    else:
        parser.print_help()
        return 1


if __name__ == '__main__':
    sys.exit(main())
