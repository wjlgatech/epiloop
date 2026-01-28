#!/usr/bin/env python3
"""
PRD Indexer - Build and maintain searchable PRD index

Creates and maintains .claude-loop/prd-index.json with metadata for all PRDs.
Supports rebuilding the index and verifying index integrity against filesystem.

Usage:
    prd-indexer.py rebuild              Rebuild index from filesystem
    prd-indexer.py verify               Verify index matches filesystem
    prd-indexer.py show                 Show current index contents
    prd-indexer.py stats                Show index statistics
"""

import argparse
import hashlib
import json
import sys
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
CLAUDE_LOOP_DIR = PROJECT_ROOT / ".claude-loop"
INDEX_FILE = CLAUDE_LOOP_DIR / "prd-index.json"


@dataclass
class PRDIndexEntry:
    """Index entry for a single PRD"""
    id: str
    title: str
    status: str
    owner: str
    created_at: str
    path: str
    directory_name: str
    tags: list = field(default_factory=list)
    story_count: int = 0
    completed_stories: int = 0
    branch_name: Optional[str] = None
    priority: Optional[str] = None
    description: Optional[str] = None
    updated_at: Optional[str] = None
    supersedes: Optional[list] = None
    superseded_by: Optional[str] = None
    manifest_hash: Optional[str] = None
    prd_json_hash: Optional[str] = None


@dataclass
class PRDIndex:
    """Full PRD index with metadata"""
    version: str = "1.0"
    generated_at: str = ""
    prds_directory: str = ""
    total_prds: int = 0
    by_status: dict = field(default_factory=dict)
    entries: list = field(default_factory=list)


def find_prds_directory() -> Path:
    """Find the prds/ directory, checking multiple locations"""
    candidates = [
        PRDS_DIR,
        Path.cwd() / "prds",
        PROJECT_ROOT / "prds",
    ]

    for candidate in candidates:
        if candidate.exists() and candidate.is_dir():
            return candidate

    return PRDS_DIR


def ensure_claude_loop_dir() -> Path:
    """Ensure .claude-loop directory exists"""
    claude_loop_dir = PROJECT_ROOT / ".claude-loop"
    if not claude_loop_dir.exists():
        claude_loop_dir.mkdir(parents=True, exist_ok=True)
    return claude_loop_dir


def compute_file_hash(file_path: Path) -> Optional[str]:
    """Compute SHA256 hash of a file"""
    if not file_path.exists():
        return None
    try:
        with open(file_path, 'rb') as f:
            return hashlib.sha256(f.read()).hexdigest()
    except Exception:
        return None


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


def build_index_entry(prd_dir: Path) -> Optional[PRDIndexEntry]:
    """Build an index entry from a PRD directory"""
    manifest_path = prd_dir / "MANIFEST.yaml"
    prd_json_path = prd_dir / "prd.json"

    if not manifest_path.exists():
        return None

    manifest = load_manifest(manifest_path)
    if not manifest:
        return None

    # Get story counts from prd.json if available
    story_count = manifest.get('story_count', 0)
    completed_stories = manifest.get('completed_stories', 0)

    if prd_json_path.exists():
        prd_data = load_prd_json(prd_json_path)
        if prd_data:
            stories = prd_data.get('userStories', [])
            story_count = len(stories)
            completed_stories = sum(1 for s in stories if s.get('passes', False))

    # Handle supersedes as list
    supersedes = manifest.get('supersedes')
    if isinstance(supersedes, str):
        supersedes = [supersedes]

    # Compute file hashes for verification
    manifest_hash = compute_file_hash(manifest_path)
    prd_json_hash = compute_file_hash(prd_json_path) if prd_json_path.exists() else None

    return PRDIndexEntry(
        id=manifest.get('id', 'UNKNOWN'),
        title=manifest.get('title', 'Untitled'),
        status=manifest.get('status', 'unknown'),
        owner=manifest.get('owner', 'unknown'),
        created_at=str(manifest.get('created_at', '')),
        path=str(prd_dir),
        directory_name=prd_dir.name,
        tags=manifest.get('tags', []),
        story_count=story_count,
        completed_stories=completed_stories,
        branch_name=manifest.get('branch_name'),
        priority=manifest.get('priority'),
        description=manifest.get('description'),
        updated_at=str(manifest.get('updated_at', '')) if manifest.get('updated_at') else None,
        supersedes=supersedes,
        superseded_by=manifest.get('superseded_by'),
        manifest_hash=manifest_hash,
        prd_json_hash=prd_json_hash,
    )


def scan_prds_for_index(prds_dir: Path) -> list[PRDIndexEntry]:
    """Scan the prds/ directory and build index entries"""
    entries = []
    status_dirs = ['active', 'completed', 'abandoned', 'drafts']

    for status_dir_name in status_dirs:
        status_dir = prds_dir / status_dir_name
        if not status_dir.exists():
            continue

        for prd_dir in status_dir.iterdir():
            if not prd_dir.is_dir():
                continue
            if prd_dir.name.startswith('.'):
                continue

            entry = build_index_entry(prd_dir)
            if entry:
                entries.append(entry)

    # Sort by created_at (newest first)
    entries.sort(key=lambda e: e.created_at or '', reverse=True)
    return entries


def build_index(prds_dir: Path) -> PRDIndex:
    """Build the complete PRD index"""
    entries = scan_prds_for_index(prds_dir)

    # Count by status
    by_status = {}
    for entry in entries:
        status = entry.status
        by_status[status] = by_status.get(status, 0) + 1

    return PRDIndex(
        version="1.0",
        generated_at=datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
        prds_directory=str(prds_dir),
        total_prds=len(entries),
        by_status=by_status,
        entries=[asdict(e) for e in entries],
    )


def save_index(index: PRDIndex, index_path: Path) -> bool:
    """Save index to JSON file"""
    try:
        index_path.parent.mkdir(parents=True, exist_ok=True)
        with open(index_path, 'w') as f:
            json.dump(asdict(index), f, indent=2, default=str)
        return True
    except Exception as e:
        print(f"Error saving index: {e}", file=sys.stderr)
        return False


def load_index(index_path: Path) -> Optional[dict]:
    """Load index from JSON file"""
    if not index_path.exists():
        return None
    try:
        with open(index_path, 'r') as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading index: {e}", file=sys.stderr)
        return None


def verify_index(prds_dir: Path, index_path: Path) -> dict:
    """Verify index matches filesystem and return verification results"""
    results = {
        "verified": True,
        "issues": [],
        "missing_from_index": [],
        "missing_from_filesystem": [],
        "hash_mismatches": [],
        "status_mismatches": [],
    }

    # Load current index
    current_index = load_index(index_path)
    if not current_index:
        results["verified"] = False
        results["issues"].append("Index file does not exist or is invalid")
        return results

    # Build fresh index from filesystem
    fresh_entries = scan_prds_for_index(prds_dir)
    fresh_by_id = {e.id: e for e in fresh_entries}

    # Index entries by ID
    index_entries = current_index.get('entries', [])
    index_by_id = {e['id']: e for e in index_entries}

    # Check for PRDs in filesystem but not in index
    for prd_id, entry in fresh_by_id.items():
        if prd_id not in index_by_id:
            results["verified"] = False
            results["missing_from_index"].append({
                "id": prd_id,
                "title": entry.title,
                "path": entry.path,
            })
            results["issues"].append(f"PRD '{prd_id}' exists in filesystem but not in index")

    # Check for PRDs in index but not in filesystem
    for prd_id, entry in index_by_id.items():
        if prd_id not in fresh_by_id:
            results["verified"] = False
            results["missing_from_filesystem"].append({
                "id": prd_id,
                "title": entry.get('title', 'Unknown'),
                "path": entry.get('path', 'Unknown'),
            })
            results["issues"].append(f"PRD '{prd_id}' in index but not found in filesystem")

    # Check for hash mismatches (content changed)
    for prd_id, fresh_entry in fresh_by_id.items():
        if prd_id in index_by_id:
            indexed = index_by_id[prd_id]

            # Check manifest hash
            if indexed.get('manifest_hash') and fresh_entry.manifest_hash:
                if indexed['manifest_hash'] != fresh_entry.manifest_hash:
                    results["verified"] = False
                    results["hash_mismatches"].append({
                        "id": prd_id,
                        "file": "MANIFEST.yaml",
                        "indexed_hash": indexed['manifest_hash'][:16] + "...",
                        "current_hash": fresh_entry.manifest_hash[:16] + "...",
                    })
                    results["issues"].append(f"PRD '{prd_id}' MANIFEST.yaml has changed since indexing")

            # Check prd.json hash
            if indexed.get('prd_json_hash') and fresh_entry.prd_json_hash:
                if indexed['prd_json_hash'] != fresh_entry.prd_json_hash:
                    results["verified"] = False
                    results["hash_mismatches"].append({
                        "id": prd_id,
                        "file": "prd.json",
                        "indexed_hash": indexed['prd_json_hash'][:16] + "...",
                        "current_hash": fresh_entry.prd_json_hash[:16] + "...",
                    })
                    results["issues"].append(f"PRD '{prd_id}' prd.json has changed since indexing")

            # Check status matches
            if indexed.get('status') != fresh_entry.status:
                results["verified"] = False
                results["status_mismatches"].append({
                    "id": prd_id,
                    "indexed_status": indexed.get('status'),
                    "current_status": fresh_entry.status,
                })
                results["issues"].append(f"PRD '{prd_id}' status mismatch: index={indexed.get('status')}, filesystem={fresh_entry.status}")

    return results


# =============================================================================
# Command Handlers
# =============================================================================

def cmd_rebuild(args):
    """Handle 'rebuild' command - Rebuild index from filesystem"""
    prds_dir = find_prds_directory()

    if not prds_dir.exists():
        print(f"Error: PRDs directory not found at {prds_dir}", file=sys.stderr)
        return 1

    # Ensure .claude-loop directory exists
    ensure_claude_loop_dir()

    # Build and save index
    print(f"Scanning {prds_dir}...")
    index = build_index(prds_dir)

    index_path = CLAUDE_LOOP_DIR / "prd-index.json"
    if not save_index(index, index_path):
        return 1

    if args.json:
        output = {
            "success": True,
            "index_path": str(index_path),
            "total_prds": index.total_prds,
            "by_status": index.by_status,
            "generated_at": index.generated_at,
        }
        print(json.dumps(output, indent=2))
    else:
        print(f"\nIndex rebuilt successfully!")
        print(f"  Location:   {index_path}")
        print(f"  Total PRDs: {index.total_prds}")
        print(f"  By status:")
        for status, count in sorted(index.by_status.items()):
            print(f"    {status}: {count}")
        print(f"  Generated:  {index.generated_at}")

    return 0


def cmd_verify(args):
    """Handle 'verify' command - Verify index matches filesystem"""
    prds_dir = find_prds_directory()
    index_path = CLAUDE_LOOP_DIR / "prd-index.json"

    if not prds_dir.exists():
        print(f"Error: PRDs directory not found at {prds_dir}", file=sys.stderr)
        return 1

    results = verify_index(prds_dir, index_path)

    if args.json:
        print(json.dumps(results, indent=2))
    else:
        if results["verified"]:
            print("Index verification: PASSED")
            print("  All PRDs in index match filesystem")
        else:
            print("Index verification: FAILED")
            print(f"  Issues found: {len(results['issues'])}")

            if results["missing_from_index"]:
                print(f"\n  Missing from index ({len(results['missing_from_index'])}):")
                for item in results["missing_from_index"]:
                    print(f"    - {item['id']}: {item['title']}")

            if results["missing_from_filesystem"]:
                print(f"\n  Missing from filesystem ({len(results['missing_from_filesystem'])}):")
                for item in results["missing_from_filesystem"]:
                    print(f"    - {item['id']}: {item['title']}")

            if results["hash_mismatches"]:
                print(f"\n  Content changed ({len(results['hash_mismatches'])}):")
                for item in results["hash_mismatches"]:
                    print(f"    - {item['id']}: {item['file']}")

            if results["status_mismatches"]:
                print(f"\n  Status mismatches ({len(results['status_mismatches'])}):")
                for item in results["status_mismatches"]:
                    print(f"    - {item['id']}: {item['indexed_status']} -> {item['current_status']}")

            print("\n  Run 'prd-indexer.py rebuild' to fix")

    return 0 if results["verified"] else 1


def cmd_show(args):
    """Handle 'show' command - Show current index contents"""
    index_path = CLAUDE_LOOP_DIR / "prd-index.json"

    if not index_path.exists():
        print(f"Error: Index not found at {index_path}", file=sys.stderr)
        print("Run 'prd-indexer.py rebuild' to create index", file=sys.stderr)
        return 1

    index_data = load_index(index_path)
    if not index_data:
        return 1

    if args.json:
        print(json.dumps(index_data, indent=2))
    else:
        entries = index_data.get('entries', [])

        # Filter by status if specified
        if args.status:
            entries = [e for e in entries if e.get('status') == args.status]

        print(f"PRD Index (generated: {index_data.get('generated_at', 'unknown')})")
        print(f"Total: {index_data.get('total_prds', 0)} PRDs")
        print()

        if not entries:
            print("No entries found.")
            return 0

        # Calculate column widths
        id_width = max(len(e.get('id', '')) for e in entries)
        id_width = max(id_width, len('ID'))

        title_width = min(40, max(len(e.get('title', '')[:40]) for e in entries))
        title_width = max(title_width, len('Title'))

        # Build table
        header = f"{'ID':<{id_width}}  {'Title':<{title_width}}  {'Status':<10}  {'Stories':<10}  {'Owner'}"
        separator = '-' * len(header)

        print(header)
        print(separator)

        for entry in entries:
            title_display = entry.get('title', '')[:37]
            if len(entry.get('title', '')) > 40:
                title_display += '...'
            stories = f"{entry.get('completed_stories', 0)}/{entry.get('story_count', 0)}"
            print(f"{entry.get('id', ''):<{id_width}}  {title_display:<{title_width}}  {entry.get('status', ''):<10}  {stories:<10}  {entry.get('owner', '')}")

    return 0


def cmd_stats(args):
    """Handle 'stats' command - Show index statistics"""
    index_path = CLAUDE_LOOP_DIR / "prd-index.json"

    if not index_path.exists():
        print(f"Error: Index not found at {index_path}", file=sys.stderr)
        print("Run 'prd-indexer.py rebuild' to create index", file=sys.stderr)
        return 1

    index_data = load_index(index_path)
    if not index_data:
        return 1

    entries = index_data.get('entries', [])

    # Calculate statistics
    stats = {
        "total_prds": len(entries),
        "by_status": index_data.get('by_status', {}),
        "total_stories": sum(e.get('story_count', 0) for e in entries),
        "completed_stories": sum(e.get('completed_stories', 0) for e in entries),
        "by_owner": {},
        "by_priority": {},
        "with_tags": 0,
        "index_generated_at": index_data.get('generated_at', 'unknown'),
    }

    for entry in entries:
        # Count by owner
        owner = entry.get('owner', 'unknown')
        stats["by_owner"][owner] = stats["by_owner"].get(owner, 0) + 1

        # Count by priority
        priority = entry.get('priority', 'unset')
        stats["by_priority"][priority] = stats["by_priority"].get(priority, 0) + 1

        # Count with tags
        if entry.get('tags'):
            stats["with_tags"] += 1

    # Calculate completion rate
    if stats["total_stories"] > 0:
        stats["completion_rate"] = round(stats["completed_stories"] / stats["total_stories"] * 100, 1)
    else:
        stats["completion_rate"] = 0

    if args.json:
        print(json.dumps(stats, indent=2))
    else:
        print("PRD Index Statistics")
        print("=" * 40)
        print(f"\nTotal PRDs: {stats['total_prds']}")
        print(f"\nBy Status:")
        for status, count in sorted(stats["by_status"].items()):
            print(f"  {status}: {count}")

        print(f"\nStories:")
        print(f"  Total: {stats['total_stories']}")
        print(f"  Completed: {stats['completed_stories']}")
        print(f"  Completion rate: {stats['completion_rate']}%")

        print(f"\nBy Owner:")
        for owner, count in sorted(stats["by_owner"].items(), key=lambda x: -x[1]):
            print(f"  {owner}: {count}")

        print(f"\nBy Priority:")
        for priority, count in sorted(stats["by_priority"].items()):
            print(f"  {priority}: {count}")

        print(f"\nWith Tags: {stats['with_tags']}")
        print(f"\nIndex generated: {stats['index_generated_at']}")

    return 0


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="PRD Indexer - Build and maintain searchable PRD index",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s rebuild              Rebuild index from filesystem
  %(prog)s rebuild --json       Rebuild and output result as JSON
  %(prog)s verify               Verify index matches filesystem
  %(prog)s show                 Show all indexed PRDs
  %(prog)s show --status active Show only active PRDs
  %(prog)s stats                Show index statistics
"""
    )

    subparsers = parser.add_subparsers(dest='command', help='Available commands')

    # Rebuild command
    rebuild_parser = subparsers.add_parser('rebuild', help='Rebuild index from filesystem')
    rebuild_parser.add_argument(
        '--json',
        action='store_true',
        help='Output as JSON'
    )

    # Verify command
    verify_parser = subparsers.add_parser('verify', help='Verify index matches filesystem')
    verify_parser.add_argument(
        '--json',
        action='store_true',
        help='Output as JSON'
    )

    # Show command
    show_parser = subparsers.add_parser('show', help='Show current index contents')
    show_parser.add_argument(
        '--status',
        choices=['draft', 'active', 'completed', 'abandoned'],
        help='Filter by status'
    )
    show_parser.add_argument(
        '--json',
        action='store_true',
        help='Output as JSON'
    )

    # Stats command
    stats_parser = subparsers.add_parser('stats', help='Show index statistics')
    stats_parser.add_argument(
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
        'rebuild': cmd_rebuild,
        'verify': cmd_verify,
        'show': cmd_show,
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
