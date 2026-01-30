#!/usr/bin/env python3
"""
Search Cache Module

Caches search results to avoid redundant API calls.
Uses file-based JSON cache with TTL expiration and size limits.
"""

import os
import json
import hashlib
import time
from pathlib import Path
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta


class SearchCache:
    """
    File-based search result cache with TTL and size management.

    Features:
    - SHA256-based cache keys from query + parameters
    - TTL expiration (default: 24 hours)
    - Max cache size with LRU eviction (default: 100MB)
    - Atomic writes to prevent corruption
    """

    def __init__(
        self,
        cache_dir: Optional[str] = None,
        ttl_seconds: int = 86400,  # 24 hours
        max_size_mb: int = 100
    ):
        """
        Initialize search cache.

        Args:
            cache_dir: Cache directory path (default: .claude-loop/search-cache/)
            ttl_seconds: Time-to-live in seconds (default: 86400 = 24h)
            max_size_mb: Maximum cache size in MB (default: 100)
        """
        if cache_dir is None:
            cache_dir = os.path.join(
                os.path.dirname(os.path.dirname(__file__)),
                ".claude-loop", "search-cache"
            )

        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        self.ttl_seconds = ttl_seconds
        self.max_size_bytes = max_size_mb * 1024 * 1024

        self.stats_file = self.cache_dir / "stats.json"
        self._init_stats()

    def _init_stats(self):
        """Initialize or load cache statistics."""
        if not self.stats_file.exists():
            self.stats = {
                "hits": 0,
                "misses": 0,
                "evictions": 0,
                "created_at": datetime.now().isoformat()
            }
            self._save_stats()
        else:
            with open(self.stats_file, "r") as f:
                self.stats = json.load(f)

    def _save_stats(self):
        """Save cache statistics."""
        with open(self.stats_file, "w") as f:
            json.dump(self.stats, f, indent=2)

    def _get_cache_key(self, query: str, params: Optional[Dict[str, Any]] = None) -> str:
        """
        Generate cache key from query and parameters.

        Args:
            query: Search query string
            params: Additional search parameters

        Returns:
            SHA256 hash as cache key
        """
        # Normalize query (lowercase, strip whitespace)
        normalized_query = query.lower().strip()

        # Combine query with params
        cache_input = normalized_query
        if params:
            # Sort params for consistent hashing
            sorted_params = sorted(params.items())
            cache_input += "|" + str(sorted_params)

        # Generate SHA256 hash
        return hashlib.sha256(cache_input.encode()).hexdigest()

    def _get_cache_path(self, cache_key: str) -> Path:
        """Get cache file path for a cache key."""
        return self.cache_dir / f"{cache_key}.json"

    def get(self, query: str, params: Optional[Dict[str, Any]] = None) -> Optional[List[Dict[str, Any]]]:
        """
        Retrieve cached search results.

        Args:
            query: Search query string
            params: Additional search parameters

        Returns:
            Cached results or None if not found/expired
        """
        cache_key = self._get_cache_key(query, params)
        cache_path = self._get_cache_path(cache_key)

        if not cache_path.exists():
            self.stats["misses"] += 1
            self._save_stats()
            return None

        try:
            with open(cache_path, "r") as f:
                cache_entry = json.load(f)

            # Check expiration
            cached_at = datetime.fromisoformat(cache_entry["cached_at"])
            age_seconds = (datetime.now() - cached_at).total_seconds()

            if age_seconds > self.ttl_seconds:
                # Expired, delete cache file
                cache_path.unlink()
                self.stats["misses"] += 1
                self._save_stats()
                return None

            # Cache hit
            self.stats["hits"] += 1
            self._save_stats()

            # Update access time for LRU
            cache_entry["last_accessed"] = datetime.now().isoformat()
            with open(cache_path, "w") as f:
                json.dump(cache_entry, f, indent=2)

            return cache_entry["results"]

        except (json.JSONDecodeError, KeyError, ValueError) as e:
            # Corrupted cache entry, delete it
            cache_path.unlink(missing_ok=True)
            self.stats["misses"] += 1
            self._save_stats()
            return None

    def set(self, query: str, results: List[Dict[str, Any]], params: Optional[Dict[str, Any]] = None):
        """
        Store search results in cache.

        Args:
            query: Search query string
            results: Search results to cache
            params: Additional search parameters
        """
        cache_key = self._get_cache_key(query, params)
        cache_path = self._get_cache_path(cache_key)

        cache_entry = {
            "query": query,
            "params": params,
            "results": results,
            "cached_at": datetime.now().isoformat(),
            "last_accessed": datetime.now().isoformat()
        }

        # Atomic write (write to temp file, then rename)
        temp_path = cache_path.with_suffix(".tmp")
        with open(temp_path, "w") as f:
            json.dump(cache_entry, f, indent=2)

        temp_path.replace(cache_path)

        # Check cache size and evict if necessary
        self._enforce_size_limit()

    def _enforce_size_limit(self):
        """Enforce maximum cache size by evicting LRU entries."""
        total_size = sum(f.stat().st_size for f in self.cache_dir.glob("*.json") if f.name != "stats.json")

        if total_size <= self.max_size_bytes:
            return

        # Get all cache files with access times
        cache_files = []
        for cache_file in self.cache_dir.glob("*.json"):
            if cache_file.name == "stats.json":
                continue

            try:
                with open(cache_file, "r") as f:
                    entry = json.load(f)
                last_accessed = datetime.fromisoformat(entry.get("last_accessed", entry["cached_at"]))
                cache_files.append((cache_file, last_accessed, cache_file.stat().st_size))
            except (json.JSONDecodeError, KeyError, ValueError):
                # Corrupted file, delete it
                cache_file.unlink(missing_ok=True)

        # Sort by last accessed (oldest first)
        cache_files.sort(key=lambda x: x[1])

        # Evict oldest entries until under size limit
        for cache_file, _, file_size in cache_files:
            if total_size <= self.max_size_bytes:
                break

            cache_file.unlink(missing_ok=True)
            total_size -= file_size
            self.stats["evictions"] += 1

        self._save_stats()

    def clear(self):
        """Clear all cache entries."""
        for cache_file in self.cache_dir.glob("*.json"):
            if cache_file.name != "stats.json":
                cache_file.unlink(missing_ok=True)

        # Reset stats
        self.stats["hits"] = 0
        self.stats["misses"] = 0
        self.stats["evictions"] = 0
        self._save_stats()

    def get_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics.

        Returns:
            Dictionary with hits, misses, hit_rate, size, entry_count
        """
        total_requests = self.stats["hits"] + self.stats["misses"]
        hit_rate = self.stats["hits"] / total_requests if total_requests > 0 else 0.0

        # Calculate cache size
        cache_size = sum(f.stat().st_size for f in self.cache_dir.glob("*.json") if f.name != "stats.json")

        # Count entries
        entry_count = len(list(self.cache_dir.glob("*.json"))) - 1  # Exclude stats.json

        return {
            "hits": self.stats["hits"],
            "misses": self.stats["misses"],
            "evictions": self.stats["evictions"],
            "hit_rate": round(hit_rate, 3),
            "total_requests": total_requests,
            "cache_size_bytes": cache_size,
            "cache_size_mb": round(cache_size / (1024 * 1024), 2),
            "entry_count": entry_count,
            "ttl_seconds": self.ttl_seconds,
            "max_size_mb": self.max_size_bytes / (1024 * 1024)
        }


# CLI interface
def main():
    """Command-line interface for search-cache."""
    import sys
    import argparse

    parser = argparse.ArgumentParser(description="Search Cache CLI")
    parser.add_argument("command", choices=["stats", "clear", "get", "test"], help="Command to execute")
    parser.add_argument("query", nargs="?", help="Query for 'get' command")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    parser.add_argument("--cache-dir", help="Cache directory path")

    args = parser.parse_args()

    cache = SearchCache(cache_dir=args.cache_dir)

    if args.command == "stats":
        stats = cache.get_stats()

        if args.json:
            print(json.dumps(stats, indent=2))
        else:
            print("\nSearch Cache Statistics")
            print("=" * 40)
            print(f"Hits:          {stats['hits']}")
            print(f"Misses:        {stats['misses']}")
            print(f"Hit Rate:      {stats['hit_rate']:.1%}")
            print(f"Evictions:     {stats['evictions']}")
            print(f"Entry Count:   {stats['entry_count']}")
            print(f"Cache Size:    {stats['cache_size_mb']} MB")
            print(f"Max Size:      {stats['max_size_mb']} MB")
            print(f"TTL:           {stats['ttl_seconds']} seconds")
            print()

        return 0

    elif args.command == "clear":
        cache.clear()
        print("Cache cleared successfully")
        return 0

    elif args.command == "get":
        if not args.query:
            print("Error: query required for 'get' command", file=sys.stderr)
            return 1

        results = cache.get(args.query)

        if results is None:
            print("Cache miss: no results found")
            return 1

        if args.json:
            print(json.dumps({"query": args.query, "count": len(results), "results": results}, indent=2))
        else:
            print(f"\nCached results for: {args.query}")
            print(f"Found {len(results)} results")

        return 0

    elif args.command == "test":
        # Test cache functionality
        print("Testing search cache...")

        # Test set/get
        test_query = "test query"
        test_results = [{"title": "Test", "url": "https://example.com", "snippet": "Test snippet"}]

        cache.set(test_query, test_results)
        retrieved = cache.get(test_query)

        if retrieved == test_results:
            print("✓ Set/Get test passed")
        else:
            print("✗ Set/Get test failed")
            return 1

        # Test cache miss
        miss_result = cache.get("nonexistent query")
        if miss_result is None:
            print("✓ Cache miss test passed")
        else:
            print("✗ Cache miss test failed")
            return 1

        # Test stats
        stats = cache.get_stats()
        if stats["hits"] >= 1 and stats["misses"] >= 1:
            print("✓ Stats test passed")
        else:
            print("✗ Stats test failed")
            return 1

        # Clean up test data
        cache.clear()
        print("✓ All tests passed")
        return 0


if __name__ == "__main__":
    sys.exit(main())
