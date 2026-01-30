#!/usr/bin/env python3
# pylint: disable=broad-except
"""
context-cache.py - File caching layer for claude-loop

Provides file caching to reduce token usage by:
- Caching file contents with mtime-based invalidation
- Tracking file hashes for change detection
- Supporting incremental context (only include changed files)
- Reporting cache hit rates for metrics

Usage:
    # Initialize or get cached file content
    python3 lib/context-cache.py get <file_path>

    # Check if file has changed since last cache
    python3 lib/context-cache.py changed <file_path>

    # Get all changed files from a list
    python3 lib/context-cache.py get-changed <file1> <file2> ...

    # Get cache statistics
    python3 lib/context-cache.py stats

    # Clear cache
    python3 lib/context-cache.py clear

    # Warm cache with file list
    python3 lib/context-cache.py warm <file1> <file2> ...

CLI Options:
    --cache-dir DIR     Cache directory (default: .claude-loop/cache)
    --json              Output as JSON
    --no-cache          Bypass cache entirely (for testing)
    --verbose           Enable verbose output
"""

import argparse
import hashlib
import json
import os
import sys
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, List, Optional, Tuple


# ============================================================================
# Data Classes
# ============================================================================

@dataclass
class CacheEntry:
    """Represents a cached file entry."""
    file_path: str
    content_hash: str
    mtime: float
    size: int
    cached_at: float
    hit_count: int = 0

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> 'CacheEntry':
        return cls(**data)


@dataclass
class CacheStats:
    """Cache statistics for metrics reporting."""
    total_files: int
    cache_hits: int
    cache_misses: int
    hit_rate: float
    total_size_bytes: int
    saved_tokens_estimate: int

    def to_dict(self) -> dict:
        return asdict(self)


# ============================================================================
# File Cache Class
# ============================================================================

class FileCache:
    """
    File cache with mtime-based invalidation and hash tracking.

    The cache stores:
    - File content hashes (for change detection)
    - File mtimes (for invalidation)
    - Cache hit/miss statistics

    Cache entries are invalidated when:
    - File mtime changes
    - File is deleted
    - Cache is explicitly cleared
    """

    CACHE_INDEX_FILE = "cache_index.json"
    CACHE_STATS_FILE = "cache_stats.json"

    def __init__(self, cache_dir: str = ".claude-loop/cache", enabled: bool = True):
        """Initialize the file cache.

        Args:
            cache_dir: Directory to store cache data
            enabled: Whether caching is enabled
        """
        self.cache_dir = Path(cache_dir)
        self.enabled = enabled
        self.entries: Dict[str, CacheEntry] = {}
        self.stats = {
            "hits": 0,
            "misses": 0,
            "invalidations": 0,
        }

        if self.enabled:
            self._ensure_cache_dir()
            self._load_cache_index()

    def _ensure_cache_dir(self) -> None:
        """Create cache directory if it doesn't exist."""
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _get_index_path(self) -> Path:
        """Get path to cache index file."""
        return self.cache_dir / self.CACHE_INDEX_FILE

    def _get_stats_path(self) -> Path:
        """Get path to cache stats file."""
        return self.cache_dir / self.CACHE_STATS_FILE

    def _load_cache_index(self) -> None:
        """Load cache index from disk."""
        index_path = self._get_index_path()
        if index_path.exists():
            try:
                with open(index_path, 'r') as f:
                    data = json.load(f)
                    self.entries = {
                        k: CacheEntry.from_dict(v)
                        for k, v in data.get("entries", {}).items()
                    }
                    self.stats = data.get("stats", self.stats)
            except (json.JSONDecodeError, KeyError):
                # Corrupted cache, start fresh
                self.entries = {}
                self.stats = {"hits": 0, "misses": 0, "invalidations": 0}

    def _save_cache_index(self) -> None:
        """Save cache index to disk."""
        if not self.enabled:
            return

        index_path = self._get_index_path()
        data = {
            "entries": {k: v.to_dict() for k, v in self.entries.items()},
            "stats": self.stats,
            "updated_at": time.time(),
        }
        with open(index_path, 'w') as f:
            json.dump(data, f, indent=2)

    def _compute_file_hash(self, file_path: str) -> str:
        """Compute SHA256 hash of file contents."""
        hasher = hashlib.sha256()
        try:
            with open(file_path, 'rb') as f:
                for chunk in iter(lambda: f.read(65536), b''):
                    hasher.update(chunk)
            return hasher.hexdigest()
        except (IOError, OSError):
            return ""

    def _get_file_mtime(self, file_path: str) -> float:
        """Get file modification time."""
        try:
            return os.path.getmtime(file_path)
        except OSError:
            return 0.0

    def _get_file_size(self, file_path: str) -> int:
        """Get file size in bytes."""
        try:
            return os.path.getsize(file_path)
        except OSError:
            return 0

    def _is_entry_valid(self, entry: CacheEntry) -> bool:
        """Check if cache entry is still valid.

        Entry is valid if:
        - File still exists
        - File mtime hasn't changed
        """
        file_path = entry.file_path
        if not os.path.exists(file_path):
            return False

        current_mtime = self._get_file_mtime(file_path)
        return current_mtime == entry.mtime

    def get(self, file_path: str) -> Tuple[Optional[str], bool]:
        """Get cached file hash, checking for validity.

        Args:
            file_path: Path to file

        Returns:
            Tuple of (content_hash, was_cache_hit)
            If file doesn't exist, returns (None, False)
        """
        if not self.enabled:
            if not os.path.exists(file_path):
                return None, False
            return self._compute_file_hash(file_path), False

        abs_path = os.path.abspath(file_path)

        # Check if file exists
        if not os.path.exists(abs_path):
            return None, False

        # Check cache
        entry = self.entries.get(abs_path)

        if entry and self._is_entry_valid(entry):
            # Cache hit
            self.stats["hits"] += 1
            entry.hit_count += 1
            self._save_cache_index()
            return entry.content_hash, True

        # Cache miss - compute hash and update cache
        self.stats["misses"] += 1
        if entry:
            self.stats["invalidations"] += 1

        content_hash = self._compute_file_hash(abs_path)
        if content_hash:
            self.entries[abs_path] = CacheEntry(
                file_path=abs_path,
                content_hash=content_hash,
                mtime=self._get_file_mtime(abs_path),
                size=self._get_file_size(abs_path),
                cached_at=time.time(),
                hit_count=0,
            )
            self._save_cache_index()

        return content_hash, False

    def has_changed(self, file_path: str) -> bool:
        """Check if file has changed since last cache.

        Args:
            file_path: Path to file

        Returns:
            True if file has changed or is new, False if unchanged
        """
        if not self.enabled:
            return True  # Without cache, assume always changed

        abs_path = os.path.abspath(file_path)

        if not os.path.exists(abs_path):
            return False  # File doesn't exist, not "changed"

        entry = self.entries.get(abs_path)

        if not entry:
            return True  # New file

        if not self._is_entry_valid(entry):
            return True  # mtime changed

        # Verify with hash (mtime same but content might differ)
        current_hash = self._compute_file_hash(abs_path)
        return current_hash != entry.content_hash

    def get_changed_files(self, file_paths: List[str]) -> List[str]:
        """Get list of files that have changed since last cache.

        Args:
            file_paths: List of file paths to check

        Returns:
            List of file paths that have changed
        """
        changed = []
        for path in file_paths:
            if self.has_changed(path):
                changed.append(path)
        return changed

    def warm(self, file_paths: List[str]) -> Dict[str, bool]:
        """Pre-populate cache with file list.

        Args:
            file_paths: List of file paths to cache

        Returns:
            Dict mapping file path to whether it was newly cached
        """
        results = {}
        for path in file_paths:
            _, was_hit = self.get(path)
            results[path] = not was_hit  # True if newly cached
        return results

    def invalidate(self, file_path: str) -> bool:
        """Invalidate cache entry for a file.

        Args:
            file_path: Path to file

        Returns:
            True if entry was removed, False if not found
        """
        abs_path = os.path.abspath(file_path)
        if abs_path in self.entries:
            del self.entries[abs_path]
            self.stats["invalidations"] += 1
            self._save_cache_index()
            return True
        return False

    def clear(self) -> int:
        """Clear all cache entries.

        Returns:
            Number of entries cleared
        """
        count = len(self.entries)
        self.entries = {}
        self.stats = {"hits": 0, "misses": 0, "invalidations": 0}
        self._save_cache_index()
        return count

    def get_stats(self) -> CacheStats:
        """Get cache statistics.

        Returns:
            CacheStats object with hit/miss rates and size info
        """
        total_files = len(self.entries)
        hits = self.stats["hits"]
        misses = self.stats["misses"]
        total_requests = hits + misses

        hit_rate = (hits / total_requests * 100) if total_requests > 0 else 0.0

        total_size = sum(e.size for e in self.entries.values())

        # Estimate tokens saved (cache hits * avg file size / 4 chars per token)
        if self.entries:
            avg_size = total_size / total_files
            saved_tokens = int(hits * avg_size / 4)
        else:
            saved_tokens = 0

        return CacheStats(
            total_files=total_files,
            cache_hits=hits,
            cache_misses=misses,
            hit_rate=round(hit_rate, 2),
            total_size_bytes=total_size,
            saved_tokens_estimate=saved_tokens,
        )

    def get_file_hash(self, file_path: str) -> Optional[str]:
        """Get cached hash for a file without triggering cache update.

        Args:
            file_path: Path to file

        Returns:
            Cached hash or None if not in cache
        """
        abs_path = os.path.abspath(file_path)
        entry = self.entries.get(abs_path)
        if entry and self._is_entry_valid(entry):
            return entry.content_hash
        return None

    def list_cached_files(self) -> List[str]:
        """Get list of all cached file paths.

        Returns:
            List of absolute file paths in cache
        """
        return list(self.entries.keys())


# ============================================================================
# CLI Interface
# ============================================================================

def cmd_get(args: argparse.Namespace, cache: FileCache) -> int:
    """Get cached file hash."""
    file_path = args.file_path

    content_hash, was_hit = cache.get(file_path)

    if args.json:
        result = {
            "file_path": file_path,
            "hash": content_hash,
            "cache_hit": was_hit,
            "exists": content_hash is not None,
        }
        print(json.dumps(result, indent=2))
    else:
        if content_hash:
            hit_str = "(cached)" if was_hit else "(computed)"
            print(f"{file_path}: {content_hash[:16]}... {hit_str}")
        else:
            print(f"{file_path}: not found", file=sys.stderr)
            return 1

    return 0


def cmd_changed(args: argparse.Namespace, cache: FileCache) -> int:
    """Check if file has changed."""
    file_path = args.file_path

    changed = cache.has_changed(file_path)

    if args.json:
        result = {
            "file_path": file_path,
            "changed": changed,
        }
        print(json.dumps(result, indent=2))
    else:
        status = "changed" if changed else "unchanged"
        print(f"{file_path}: {status}")

    return 0 if not changed else 1  # Return 1 if changed (for scripting)


def cmd_get_changed(args: argparse.Namespace, cache: FileCache) -> int:
    """Get list of changed files."""
    file_paths = args.files

    changed = cache.get_changed_files(file_paths)

    if args.json:
        result = {
            "total_files": len(file_paths),
            "changed_count": len(changed),
            "unchanged_count": len(file_paths) - len(changed),
            "changed_files": changed,
        }
        print(json.dumps(result, indent=2))
    else:
        if changed:
            for f in changed:
                print(f)
        elif args.verbose:
            print("No files have changed", file=sys.stderr)

    return 0


def cmd_stats(args: argparse.Namespace, cache: FileCache) -> int:
    """Show cache statistics."""
    stats = cache.get_stats()

    if args.json:
        print(json.dumps(stats.to_dict(), indent=2))
    else:
        print("Cache Statistics:")
        print(f"  Total files cached: {stats.total_files}")
        print(f"  Cache hits:         {stats.cache_hits}")
        print(f"  Cache misses:       {stats.cache_misses}")
        print(f"  Hit rate:           {stats.hit_rate}%")
        print(f"  Total size:         {stats.total_size_bytes:,} bytes")
        print(f"  Tokens saved (est): {stats.saved_tokens_estimate:,}")

    return 0


def cmd_clear(args: argparse.Namespace, cache: FileCache) -> int:
    """Clear cache."""
    count = cache.clear()

    if args.json:
        result = {"cleared": count}
        print(json.dumps(result, indent=2))
    else:
        print(f"Cleared {count} cache entries")

    return 0


def cmd_warm(args: argparse.Namespace, cache: FileCache) -> int:
    """Warm cache with file list."""
    file_paths = args.files

    results = cache.warm(file_paths)

    newly_cached = sum(1 for v in results.values() if v)
    already_cached = len(results) - newly_cached

    if args.json:
        result = {
            "total_files": len(file_paths),
            "newly_cached": newly_cached,
            "already_cached": already_cached,
            "files": {k: "new" if v else "cached" for k, v in results.items()},
        }
        print(json.dumps(result, indent=2))
    else:
        print(f"Warmed cache: {newly_cached} new, {already_cached} already cached")
        if args.verbose:
            for path, is_new in results.items():
                status = "new" if is_new else "cached"
                print(f"  {path}: {status}")

    return 0


def cmd_list(args: argparse.Namespace, cache: FileCache) -> int:
    """List cached files."""
    files = cache.list_cached_files()

    if args.json:
        result = {
            "count": len(files),
            "files": files,
        }
        print(json.dumps(result, indent=2))
    else:
        for f in files:
            print(f)

    return 0


def cmd_invalidate(args: argparse.Namespace, cache: FileCache) -> int:
    """Invalidate cache entry for a file."""
    file_path = args.file_path

    removed = cache.invalidate(file_path)

    if args.json:
        result = {
            "file_path": file_path,
            "invalidated": removed,
        }
        print(json.dumps(result, indent=2))
    else:
        if removed:
            print(f"Invalidated: {file_path}")
        else:
            print(f"Not in cache: {file_path}", file=sys.stderr)
            return 1

    return 0


def create_parser():
    """Create argument parser with shared options."""
    # Create parent parser with shared options
    parent_parser = argparse.ArgumentParser(add_help=False)
    parent_parser.add_argument(
        "--cache-dir",
        default=".claude-loop/cache",
        help="Cache directory (default: .claude-loop/cache)",
    )
    parent_parser.add_argument(
        "--json",
        action="store_true",
        help="Output as JSON",
    )
    parent_parser.add_argument(
        "--no-cache",
        action="store_true",
        help="Bypass cache entirely",
    )
    parent_parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose output",
    )

    # Main parser
    parser = argparse.ArgumentParser(
        description="File caching layer for claude-loop",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        parents=[parent_parser],
    )

    # Subcommands - each inherits from parent_parser
    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # get command
    get_parser = subparsers.add_parser(
        "get", help="Get cached file hash", parents=[parent_parser]
    )
    get_parser.add_argument("file_path", help="Path to file")

    # changed command
    changed_parser = subparsers.add_parser(
        "changed", help="Check if file has changed", parents=[parent_parser]
    )
    changed_parser.add_argument("file_path", help="Path to file")

    # get-changed command
    get_changed_parser = subparsers.add_parser(
        "get-changed", help="Get list of changed files", parents=[parent_parser]
    )
    get_changed_parser.add_argument("files", nargs="+", help="Files to check")

    # stats command
    subparsers.add_parser("stats", help="Show cache statistics", parents=[parent_parser])

    # clear command
    subparsers.add_parser("clear", help="Clear cache", parents=[parent_parser])

    # warm command
    warm_parser = subparsers.add_parser(
        "warm", help="Warm cache with file list", parents=[parent_parser]
    )
    warm_parser.add_argument("files", nargs="+", help="Files to cache")

    # list command
    subparsers.add_parser("list", help="List cached files", parents=[parent_parser])

    # invalidate command
    invalidate_parser = subparsers.add_parser(
        "invalidate", help="Invalidate cache entry", parents=[parent_parser]
    )
    invalidate_parser.add_argument("file_path", help="Path to file")

    return parser


def main():
    """Main entry point."""
    parser = create_parser()

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    # Initialize cache
    cache = FileCache(
        cache_dir=args.cache_dir,
        enabled=not args.no_cache,
    )

    # Dispatch to command handler
    commands = {
        "get": cmd_get,
        "changed": cmd_changed,
        "get-changed": cmd_get_changed,
        "stats": cmd_stats,
        "clear": cmd_clear,
        "warm": cmd_warm,
        "list": cmd_list,
        "invalidate": cmd_invalidate,
    }

    handler = commands.get(args.command)
    if handler:
        return handler(args, cache)

    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
