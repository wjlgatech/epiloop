#!/usr/bin/env python3
"""
merge-controller.py - Git Merge Controller for Parallel Execution

Manages git operations for parallel worker execution:
- File locking to prevent concurrent access
- Worker branch creation and isolation
- Conflict detection before parallel execution
- Rebase-based sequential merging
- Cleanup of worker branches after merge

Usage:
    # Check for file conflicts between stories
    python3 lib/merge-controller.py check-conflicts prd.json

    # Create worker branch for a story
    python3 lib/merge-controller.py create-branch US-001 --base main

    # Merge worker branch back to base
    python3 lib/merge-controller.py merge US-001 --base main

    # Clean up worker branches
    python3 lib/merge-controller.py cleanup --older-than 24h
"""

import argparse
import fcntl
import json
import os
import re
import subprocess
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

# ============================================================================
# Configuration
# ============================================================================

LOCK_DIR = ".claude-loop/locks"
WORKER_BRANCH_PREFIX = "worker/"
DEFAULT_BASE_BRANCH = "main"
LOCK_TIMEOUT = 30  # seconds

# ============================================================================
# Data Classes
# ============================================================================

@dataclass
class StoryInfo:
    """Information about a story from prd.json"""
    id: str
    title: str
    file_scope: List[str]
    dependencies: List[str]
    passes: bool

    @classmethod
    def from_dict(cls, data: dict) -> 'StoryInfo':
        return cls(
            id=data.get('id', ''),
            title=data.get('title', ''),
            file_scope=data.get('fileScope', []),
            dependencies=data.get('dependencies', []),
            passes=data.get('passes', False)
        )


@dataclass
class ConflictInfo:
    """Information about potential file conflicts"""
    stories: Tuple[str, str]  # Two story IDs that conflict
    conflicting_files: List[str]

    def to_dict(self) -> dict:
        return {
            'stories': list(self.stories),
            'conflicting_files': self.conflicting_files
        }


@dataclass
class MergeResult:
    """Result of a merge operation"""
    success: bool
    story_id: str
    branch_name: str
    base_branch: str
    commit_hash: Optional[str] = None
    error: Optional[str] = None
    files_merged: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            'success': self.success,
            'story_id': self.story_id,
            'branch_name': self.branch_name,
            'base_branch': self.base_branch,
            'commit_hash': self.commit_hash,
            'error': self.error,
            'files_merged': self.files_merged
        }


# ============================================================================
# File Locking
# ============================================================================

class FileLock:
    """File-based locking for concurrent access control"""

    def __init__(self, lock_name: str, timeout: int = LOCK_TIMEOUT):
        self.lock_name = lock_name
        self.timeout = timeout
        self.lock_dir = Path(LOCK_DIR)
        self.lock_file = self.lock_dir / f"{lock_name}.lock"
        self._fd = None

    def __enter__(self):
        self.acquire()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.release()
        return False

    def acquire(self) -> bool:
        """Acquire the lock with timeout"""
        # Ensure lock directory exists
        self.lock_dir.mkdir(parents=True, exist_ok=True)

        start_time = time.time()
        self._fd = open(self.lock_file, 'w')

        while True:
            try:
                fcntl.flock(self._fd.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                # Write PID to lock file
                self._fd.write(str(os.getpid()))
                self._fd.flush()
                return True
            except BlockingIOError:
                if time.time() - start_time > self.timeout:
                    self._fd.close()
                    self._fd = None
                    raise TimeoutError(f"Could not acquire lock '{self.lock_name}' within {self.timeout}s")
                time.sleep(0.1)

    def release(self):
        """Release the lock"""
        if self._fd:
            try:
                fcntl.flock(self._fd.fileno(), fcntl.LOCK_UN)
                self._fd.close()
            except (OSError, ValueError) as e:
                # SAFETY: Catch specific exceptions instead of bare except
                # Lock release may fail if fd is already closed or invalid
                pass
            finally:
                self._fd = None
                # Remove lock file
                try:
                    self.lock_file.unlink()
                except (OSError, FileNotFoundError) as e:
                    # SAFETY: Catch specific exceptions instead of bare except
                    # Lock file may already be deleted
                    pass

    @staticmethod
    def is_locked(lock_name: str) -> bool:
        """Check if a lock is currently held"""
        lock_file = Path(LOCK_DIR) / f"{lock_name}.lock"
        if not lock_file.exists():
            return False
        try:
            fd = open(lock_file, 'r')
            fcntl.flock(fd.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            fcntl.flock(fd.fileno(), fcntl.LOCK_UN)
            fd.close()
            return False
        except BlockingIOError:
            return True


class MultiFileLock:
    """Lock multiple files atomically"""

    def __init__(self, file_paths: List[str], timeout: int = LOCK_TIMEOUT):
        # Sort paths to avoid deadlocks
        self.file_paths = sorted(file_paths)
        self.timeout = timeout
        self.locks: List[FileLock] = []

    def __enter__(self):
        self.acquire_all()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.release_all()
        return False

    def acquire_all(self):
        """Acquire locks for all files in order"""
        for path in self.file_paths:
            # Use path hash for lock name
            lock_name = f"file_{hash(path) % 1000000:06d}"
            lock = FileLock(lock_name, self.timeout)
            try:
                lock.acquire()
                self.locks.append(lock)
            except TimeoutError:
                # Release any acquired locks on failure
                self.release_all()
                raise

    def release_all(self):
        """Release all acquired locks"""
        for lock in reversed(self.locks):
            lock.release()
        self.locks = []


# ============================================================================
# Git Operations
# ============================================================================

def run_git(*args, check: bool = True, capture: bool = True) -> subprocess.CompletedProcess:
    """Run a git command and return the result"""
    cmd = ['git'] + list(args)
    try:
        result = subprocess.run(
            cmd,
            capture_output=capture,
            text=True,
            check=check
        )
        return result
    except subprocess.CalledProcessError as e:
        if capture:
            print(f"Git error: {e.stderr}", file=sys.stderr)
        raise


def get_current_branch() -> str:
    """Get the current git branch name"""
    result = run_git('branch', '--show-current')
    return result.stdout.strip()


def get_base_branch() -> str:
    """Get the base branch (main or master)"""
    result = run_git('branch', '-l', 'main', 'master')
    branches = result.stdout.strip().split('\n')
    for branch in branches:
        branch = branch.strip().lstrip('* ')
        if branch in ('main', 'master'):
            return branch
    return DEFAULT_BASE_BRANCH


def branch_exists(branch_name: str, remote: bool = False) -> bool:
    """Check if a branch exists"""
    if remote:
        result = run_git('branch', '-r', '-l', f'origin/{branch_name}', check=False)
    else:
        result = run_git('branch', '-l', branch_name, check=False)
    return bool(result.stdout.strip())


def get_worker_branch_name(story_id: str, timestamp: Optional[str] = None) -> str:
    """Generate worker branch name for a story"""
    if timestamp is None:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    return f"{WORKER_BRANCH_PREFIX}{story_id}_{timestamp}"


def create_worker_branch(story_id: str, base_branch: Optional[str] = None) -> str:
    """Create a worker branch for a story"""
    if base_branch is None:
        base_branch = get_current_branch()

    branch_name = get_worker_branch_name(story_id)

    # Ensure we're on latest base
    run_git('fetch', 'origin', base_branch, check=False)

    # Create branch from base
    run_git('checkout', '-b', branch_name, base_branch)

    return branch_name


def delete_worker_branch(branch_name: str, force: bool = False) -> bool:
    """Delete a worker branch"""
    flag = '-D' if force else '-d'
    try:
        run_git('branch', flag, branch_name)
        return True
    except subprocess.CalledProcessError:
        return False


def get_worker_branches() -> List[str]:
    """Get all worker branches"""
    result = run_git('branch', '-l', f'{WORKER_BRANCH_PREFIX}*')
    branches = []
    for line in result.stdout.strip().split('\n'):
        branch = line.strip().lstrip('* ')
        if branch.startswith(WORKER_BRANCH_PREFIX):
            branches.append(branch)
    return branches


def get_changed_files(branch: str, base: str) -> List[str]:
    """Get files changed between two branches"""
    try:
        result = run_git('diff', '--name-only', f'{base}...{branch}')
        files = [f.strip() for f in result.stdout.strip().split('\n') if f.strip()]
        return files
    except subprocess.CalledProcessError:
        return []


def get_uncommitted_files() -> List[str]:
    """Get list of uncommitted files"""
    result = run_git('status', '--porcelain')
    files = []
    for line in result.stdout.strip().split('\n'):
        if line.strip():
            # Extract filename from status line
            file_path = line[3:].strip()
            # Handle renamed files
            if ' -> ' in file_path:
                file_path = file_path.split(' -> ')[1]
            files.append(file_path)
    return files


# ============================================================================
# Conflict Detection
# ============================================================================

def load_prd(prd_file: str) -> dict:
    """Load PRD JSON file"""
    with open(prd_file, 'r') as f:
        return json.load(f)


def get_stories_from_prd(prd: dict) -> List[StoryInfo]:
    """Extract story information from PRD"""
    stories = []
    for story_data in prd.get('userStories', []):
        stories.append(StoryInfo.from_dict(story_data))
    return stories


def get_incomplete_stories(stories: List[StoryInfo]) -> List[StoryInfo]:
    """Filter to incomplete stories only"""
    return [s for s in stories if not s.passes]


def detect_file_conflicts(stories: List[StoryInfo]) -> List[ConflictInfo]:
    """
    Detect potential file conflicts between stories.
    Two stories conflict if they both modify the same file.
    """
    conflicts = []

    # Build file -> stories mapping
    file_to_stories: Dict[str, List[str]] = {}
    for story in stories:
        for file_path in story.file_scope:
            if file_path not in file_to_stories:
                file_to_stories[file_path] = []
            file_to_stories[file_path].append(story.id)

    # Find conflicts (files touched by multiple stories)
    checked_pairs: Set[Tuple[str, str]] = set()

    for file_path, story_ids in file_to_stories.items():
        if len(story_ids) > 1:
            # Check each pair
            for i, id1 in enumerate(story_ids):
                for id2 in story_ids[i+1:]:
                    pair: Tuple[str, str] = (min(id1, id2), max(id1, id2))
                    if pair not in checked_pairs:
                        checked_pairs.add(pair)

                        # Find all conflicting files for this pair
                        story1_files = set(next(s.file_scope for s in stories if s.id == id1))
                        story2_files = set(next(s.file_scope for s in stories if s.id == id2))
                        conflicting = story1_files & story2_files

                        if conflicting:
                            conflicts.append(ConflictInfo(
                                stories=pair,
                                conflicting_files=sorted(conflicting)
                            ))

    return conflicts


def can_run_parallel(story_ids: List[str], stories: List[StoryInfo]) -> Tuple[bool, List[ConflictInfo]]:
    """
    Check if a list of stories can run in parallel.
    Returns (can_parallel, conflicts)
    """
    # Filter to requested stories
    requested = [s for s in stories if s.id in story_ids]
    conflicts = detect_file_conflicts(requested)
    return len(conflicts) == 0, conflicts


def split_parallel_groups(story_ids: List[str], stories: List[StoryInfo]) -> List[List[str]]:
    """
    Split stories into groups that can run in parallel.
    Stories with file conflicts are placed in separate groups.
    """
    # Build conflict graph
    story_map = {s.id: s for s in stories if s.id in story_ids}
    conflicts = detect_file_conflicts([story_map[sid] for sid in story_ids if sid in story_map])

    # Build adjacency list for conflicts
    conflict_graph: Dict[str, Set[str]] = {sid: set() for sid in story_ids}
    for conflict in conflicts:
        s1, s2 = conflict.stories
        if s1 in conflict_graph and s2 in conflict_graph:
            conflict_graph[s1].add(s2)
            conflict_graph[s2].add(s1)

    # Greedy graph coloring to assign groups
    groups: List[List[str]] = []

    for story_id in story_ids:
        # Find first group where this story doesn't conflict
        assigned_group = None
        for i, group in enumerate(groups):
            has_conflict = any(s in conflict_graph[story_id] for s in group)
            if not has_conflict:
                assigned_group = i
                break

        if assigned_group is not None:
            groups[assigned_group].append(story_id)
        else:
            # Need new group
            groups.append([story_id])

    return groups


# ============================================================================
# Merge Operations
# ============================================================================

def rebase_worker_branch(worker_branch: str, base_branch: str) -> bool:
    """Rebase worker branch onto latest base"""
    current = get_current_branch()
    try:
        run_git('checkout', worker_branch)
        run_git('rebase', base_branch)
        return True
    except subprocess.CalledProcessError:
        # Abort failed rebase
        run_git('rebase', '--abort', check=False)
        return False
    finally:
        run_git('checkout', current, check=False)


def merge_worker_branch(
    worker_branch: str,
    base_branch: str,
    story_id: str,
    delete_after: bool = True
) -> MergeResult:
    """
    Merge a worker branch back to base using rebase strategy.

    1. Rebase worker onto latest base
    2. Fast-forward merge to base
    3. Clean up worker branch
    """
    current = get_current_branch()

    try:
        # Lock the base branch during merge
        with FileLock(f"branch_{base_branch}"):
            # Get files that will be merged
            files_to_merge = get_changed_files(worker_branch, base_branch)

            # Lock the files being merged
            with MultiFileLock(files_to_merge):
                # Checkout base branch
                run_git('checkout', base_branch)

                # Pull latest changes
                run_git('pull', '--rebase', 'origin', base_branch, check=False)

                # Rebase worker branch onto base
                if not rebase_worker_branch(worker_branch, base_branch):
                    return MergeResult(
                        success=False,
                        story_id=story_id,
                        branch_name=worker_branch,
                        base_branch=base_branch,
                        error="Rebase failed - conflicts detected"
                    )

                # Fast-forward merge
                run_git('merge', '--ff-only', worker_branch)

                # Get the merge commit hash
                result = run_git('rev-parse', 'HEAD')
                commit_hash = result.stdout.strip()

                # Delete worker branch if requested
                if delete_after:
                    delete_worker_branch(worker_branch)

                return MergeResult(
                    success=True,
                    story_id=story_id,
                    branch_name=worker_branch,
                    base_branch=base_branch,
                    commit_hash=commit_hash,
                    files_merged=files_to_merge
                )

    except Exception as e:
        return MergeResult(
            success=False,
            story_id=story_id,
            branch_name=worker_branch,
            base_branch=base_branch,
            error=str(e)
        )
    finally:
        # Return to original branch
        run_git('checkout', current, check=False)


def sequential_merge_all(
    worker_branches: List[Tuple[str, str]],  # (branch_name, story_id)
    base_branch: str
) -> List[MergeResult]:
    """
    Merge multiple worker branches sequentially using rebase.
    Each merge updates the base before the next merge.
    """
    results = []

    for branch_name, story_id in worker_branches:
        result = merge_worker_branch(branch_name, base_branch, story_id)
        results.append(result)

        if not result.success:
            # Stop on first failure
            break

    return results


# ============================================================================
# Branch Cleanup
# ============================================================================

def parse_branch_timestamp(branch_name: str) -> Optional[datetime]:
    """Extract timestamp from worker branch name"""
    # Format: worker/{story_id}_{timestamp}
    match = re.search(r'_(\d{8}_\d{6})$', branch_name)
    if match:
        try:
            return datetime.strptime(match.group(1), '%Y%m%d_%H%M%S')
        except ValueError:
            pass
    return None


def cleanup_old_branches(older_than_hours: int = 24, dry_run: bool = False) -> List[str]:
    """Clean up worker branches older than specified hours"""
    cutoff = datetime.now() - timedelta(hours=older_than_hours)
    worker_branches = get_worker_branches()
    deleted = []

    for branch in worker_branches:
        timestamp = parse_branch_timestamp(branch)
        if timestamp and timestamp < cutoff:
            if dry_run:
                print(f"Would delete: {branch}")
            else:
                if delete_worker_branch(branch, force=True):
                    deleted.append(branch)

    return deleted


def cleanup_merged_branches(dry_run: bool = False) -> List[str]:
    """Clean up worker branches that have been merged"""
    base = get_base_branch()
    worker_branches = get_worker_branches()
    deleted = []

    for branch in worker_branches:
        # Check if branch is merged into base
        result = run_git('branch', '--merged', base, '-l', branch, check=False)
        if branch in result.stdout:
            if dry_run:
                print(f"Would delete (merged): {branch}")
            else:
                if delete_worker_branch(branch):
                    deleted.append(branch)

    return deleted


# ============================================================================
# CLI Commands
# ============================================================================

def cmd_check_conflicts(args):
    """Check for file conflicts in PRD"""
    prd = load_prd(args.prd_file)
    stories = get_stories_from_prd(prd)

    if args.incomplete_only:
        stories = get_incomplete_stories(stories)

    conflicts = detect_file_conflicts(stories)

    if args.json:
        result = {
            'has_conflicts': len(conflicts) > 0,
            'conflict_count': len(conflicts),
            'conflicts': [c.to_dict() for c in conflicts]
        }
        print(json.dumps(result, indent=2))
    else:
        if conflicts:
            print(f"Found {len(conflicts)} potential conflict(s):\n")
            for conflict in conflicts:
                print(f"  {conflict.stories[0]} <-> {conflict.stories[1]}")
                print(f"    Files: {', '.join(conflict.conflicting_files)}")
                print()
        else:
            print("No file conflicts detected.")

    return 0 if not conflicts else 1


def cmd_split_groups(args):
    """Split stories into parallel-safe groups"""
    prd = load_prd(args.prd_file)
    stories = get_stories_from_prd(prd)

    if args.incomplete_only:
        stories = get_incomplete_stories(stories)

    story_ids = [s.id for s in stories]
    groups = split_parallel_groups(story_ids, stories)

    if args.json:
        print(json.dumps(groups, indent=2))
    else:
        print(f"Split {len(story_ids)} stories into {len(groups)} parallel-safe group(s):\n")
        for i, group in enumerate(groups, 1):
            print(f"  Group {i}: {', '.join(group)}")

    return 0


def cmd_can_parallel(args):
    """Check if specific stories can run in parallel"""
    prd = load_prd(args.prd_file)
    stories = get_stories_from_prd(prd)

    story_ids = args.stories.split(',')
    can_parallel_result, conflicts = can_run_parallel(story_ids, stories)

    if args.json:
        result = {
            'can_parallel': can_parallel_result,
            'stories': story_ids,
            'conflicts': [c.to_dict() for c in conflicts]
        }
        print(json.dumps(result, indent=2))
    else:
        if can_parallel_result:
            print(f"Stories can run in parallel: {', '.join(story_ids)}")
        else:
            print(f"Stories CANNOT run in parallel due to conflicts:")
            for conflict in conflicts:
                print(f"  {conflict.stories[0]} <-> {conflict.stories[1]}: {', '.join(conflict.conflicting_files)}")

    return 0 if can_parallel_result else 1


def cmd_create_branch(args):
    """Create a worker branch for a story"""
    base = args.base or get_current_branch()

    try:
        branch_name = create_worker_branch(args.story_id, base)

        if args.json:
            print(json.dumps({
                'success': True,
                'branch_name': branch_name,
                'story_id': args.story_id,
                'base_branch': base
            }, indent=2))
        else:
            print(f"Created worker branch: {branch_name}")

        return 0
    except Exception as e:
        if args.json:
            print(json.dumps({
                'success': False,
                'error': str(e)
            }, indent=2))
        else:
            print(f"Error: {e}", file=sys.stderr)
        return 1


def cmd_merge(args):
    """Merge a worker branch back to base"""
    base = args.base or get_base_branch()

    result = merge_worker_branch(
        args.branch,
        base,
        args.story_id or args.branch,
        delete_after=not args.keep_branch
    )

    if args.json:
        print(json.dumps(result.to_dict(), indent=2))
    else:
        if result.success:
            print(f"Successfully merged {args.branch} to {base}")
            print(f"  Commit: {result.commit_hash}")
            print(f"  Files: {len(result.files_merged)}")
        else:
            print(f"Failed to merge {args.branch}: {result.error}", file=sys.stderr)

    return 0 if result.success else 1


def cmd_cleanup(args):
    """Clean up old worker branches"""
    deleted = []

    if args.merged:
        deleted.extend(cleanup_merged_branches(dry_run=args.dry_run))

    if args.older_than:
        # Parse "24h" format
        match = re.match(r'(\d+)([hd])', args.older_than)
        if match:
            value, unit = int(match.group(1)), match.group(2)
            hours = value if unit == 'h' else value * 24
            deleted.extend(cleanup_old_branches(hours, dry_run=args.dry_run))

    if args.json:
        print(json.dumps({
            'deleted': deleted,
            'count': len(deleted),
            'dry_run': args.dry_run
        }, indent=2))
    else:
        action = "Would delete" if args.dry_run else "Deleted"
        print(f"{action} {len(deleted)} branch(es)")
        for branch in deleted:
            print(f"  - {branch}")

    return 0


def cmd_list_branches(args):
    """List all worker branches"""
    branches = get_worker_branches()

    if args.json:
        result = []
        for branch in branches:
            timestamp = parse_branch_timestamp(branch)
            result.append({
                'branch': branch,
                'timestamp': timestamp.isoformat() if timestamp else None
            })
        print(json.dumps(result, indent=2))
    else:
        if branches:
            print(f"Worker branches ({len(branches)}):")
            for branch in branches:
                print(f"  - {branch}")
        else:
            print("No worker branches found.")

    return 0


def cmd_lock_status(args):
    """Show status of file locks"""
    lock_dir = Path(LOCK_DIR)

    if not lock_dir.exists():
        print("No locks directory found.")
        return 0

    lock_files = list(lock_dir.glob("*.lock"))

    if args.json:
        locks = []
        for lock_file in lock_files:
            lock_name = lock_file.stem
            locks.append({
                'name': lock_name,
                'locked': FileLock.is_locked(lock_name),
                'file': str(lock_file)
            })
        print(json.dumps(locks, indent=2))
    else:
        if lock_files:
            print(f"Lock files ({len(lock_files)}):")
            for lock_file in lock_files:
                lock_name = lock_file.stem
                status = "LOCKED" if FileLock.is_locked(lock_name) else "free"
                print(f"  - {lock_name}: {status}")
        else:
            print("No active locks.")

    return 0


# ============================================================================
# Main Entry Point
# ============================================================================

def main():
    parser = argparse.ArgumentParser(
        description='Git Merge Controller for Parallel Execution',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    parser.add_argument('--json', action='store_true', help='Output in JSON format')

    subparsers = parser.add_subparsers(dest='command', help='Available commands')

    # check-conflicts command
    check_parser = subparsers.add_parser('check-conflicts', help='Check for file conflicts')
    check_parser.add_argument('prd_file', help='Path to prd.json')
    check_parser.add_argument('--incomplete-only', action='store_true',
                              help='Only check incomplete stories')
    check_parser.set_defaults(func=cmd_check_conflicts)

    # split-groups command
    split_parser = subparsers.add_parser('split-groups', help='Split stories into parallel-safe groups')
    split_parser.add_argument('prd_file', help='Path to prd.json')
    split_parser.add_argument('--incomplete-only', action='store_true',
                              help='Only process incomplete stories')
    split_parser.set_defaults(func=cmd_split_groups)

    # can-parallel command
    canpar_parser = subparsers.add_parser('can-parallel', help='Check if stories can run in parallel')
    canpar_parser.add_argument('stories', help='Comma-separated story IDs')
    canpar_parser.add_argument('prd_file', help='Path to prd.json')
    canpar_parser.set_defaults(func=cmd_can_parallel)

    # create-branch command
    create_parser = subparsers.add_parser('create-branch', help='Create worker branch')
    create_parser.add_argument('story_id', help='Story ID')
    create_parser.add_argument('--base', help='Base branch (default: current branch)')
    create_parser.set_defaults(func=cmd_create_branch)

    # merge command
    merge_parser = subparsers.add_parser('merge', help='Merge worker branch to base')
    merge_parser.add_argument('branch', help='Worker branch name')
    merge_parser.add_argument('--base', help='Base branch (default: main/master)')
    merge_parser.add_argument('--story-id', help='Story ID (for tracking)')
    merge_parser.add_argument('--keep-branch', action='store_true',
                              help='Keep worker branch after merge')
    merge_parser.set_defaults(func=cmd_merge)

    # cleanup command
    cleanup_parser = subparsers.add_parser('cleanup', help='Clean up worker branches')
    cleanup_parser.add_argument('--older-than', help='Delete branches older than (e.g., 24h, 7d)')
    cleanup_parser.add_argument('--merged', action='store_true',
                                help='Delete branches that have been merged')
    cleanup_parser.add_argument('--dry-run', action='store_true',
                                help='Show what would be deleted without deleting')
    cleanup_parser.set_defaults(func=cmd_cleanup)

    # list-branches command
    list_parser = subparsers.add_parser('list-branches', help='List worker branches')
    list_parser.set_defaults(func=cmd_list_branches)

    # lock-status command
    lock_parser = subparsers.add_parser('lock-status', help='Show lock status')
    lock_parser.set_defaults(func=cmd_lock_status)

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    return args.func(args)


if __name__ == '__main__':
    sys.exit(main())
