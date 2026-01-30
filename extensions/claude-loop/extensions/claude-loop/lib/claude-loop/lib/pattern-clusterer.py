#!/usr/bin/env python3
"""
pattern-clusterer.py - Failure Pattern Clustering for claude-loop

Groups similar failures into patterns for analysis. This reduces noise and
enables higher-level analysis by identifying recurring issues.

Features:
- Clusters failures by error_type + context similarity
- Uses fuzzy text matching on error messages
- Requires minimum occurrences before creating a pattern
- Automatically merges patterns with >80% similarity
- Outputs patterns with example failures for each

Usage:
    python lib/pattern-clusterer.py analyze
    python lib/pattern-clusterer.py analyze --min-occurrences 3
    python lib/pattern-clusterer.py list
    python lib/pattern-clusterer.py show <pattern_id>
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any


@dataclass
class FailurePattern:
    """A pattern representing a group of similar failures."""

    pattern_id: str
    description: str
    error_type: str
    normalized_message: str  # The canonical normalized error message
    occurrences: int
    first_seen: str  # ISO timestamp
    last_seen: str   # ISO timestamp
    affected_stories: list[str] = field(default_factory=list)
    example_failures: list[dict] = field(default_factory=list)  # Up to 3 examples
    context_indicators: list[str] = field(default_factory=list)  # Common context keys

    def to_dict(self) -> dict[str, Any]:
        return {
            "pattern_id": self.pattern_id,
            "description": self.description,
            "error_type": self.error_type,
            "normalized_message": self.normalized_message,
            "occurrences": self.occurrences,
            "first_seen": self.first_seen,
            "last_seen": self.last_seen,
            "affected_stories": self.affected_stories,
            "example_failures": self.example_failures,
            "context_indicators": self.context_indicators,
        }

    @classmethod
    def from_dict(cls, data: dict) -> FailurePattern:
        return cls(
            pattern_id=data.get("pattern_id", ""),
            description=data.get("description", ""),
            error_type=data.get("error_type", ""),
            normalized_message=data.get("normalized_message", ""),
            occurrences=data.get("occurrences", 0),
            first_seen=data.get("first_seen", ""),
            last_seen=data.get("last_seen", ""),
            affected_stories=data.get("affected_stories", []),
            example_failures=data.get("example_failures", []),
            context_indicators=data.get("context_indicators", []),
        )


@dataclass
class LogEntry:
    """Parsed execution log entry (minimal version for clustering)."""

    story_id: str
    timestamp_start: str
    timestamp_end: str
    status: str
    error_type: str
    error_message: str
    tools_used: list[str]
    context: dict
    line_number: int = 0

    @classmethod
    def from_dict(cls, data: dict, line_number: int = 0) -> LogEntry:
        return cls(
            story_id=data.get("story_id", ""),
            timestamp_start=data.get("timestamp_start", ""),
            timestamp_end=data.get("timestamp_end", ""),
            status=data.get("status", "unknown"),
            error_type=data.get("error_type", ""),
            error_message=data.get("error_message", ""),
            tools_used=data.get("tools_used", []),
            context=data.get("context", {}),
            line_number=line_number,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "story_id": self.story_id,
            "timestamp_start": self.timestamp_start,
            "timestamp_end": self.timestamp_end,
            "status": self.status,
            "error_type": self.error_type,
            "error_message": self.error_message,
            "tools_used": self.tools_used,
            "context": self.context,
            "line_number": self.line_number,
        }


class PatternClusterer:
    """
    Clusters similar execution failures into patterns.

    Clustering approach:
    1. Group failures by error_type
    2. Within each type, cluster by normalized error message similarity
    3. Merge clusters with >80% message similarity
    4. Create patterns from clusters meeting minimum occurrence threshold
    """

    # Default configuration
    DEFAULT_MIN_OCCURRENCES = 3
    DEFAULT_SIMILARITY_THRESHOLD = 0.80
    DEFAULT_MAX_EXAMPLES = 3

    def __init__(
        self,
        log_file: Path | None = None,
        min_occurrences: int = DEFAULT_MIN_OCCURRENCES,
        similarity_threshold: float = DEFAULT_SIMILARITY_THRESHOLD,
    ):
        """
        Initialize the clusterer.

        Args:
            log_file: Path to execution_log.jsonl
            min_occurrences: Minimum failures needed to form a pattern
            similarity_threshold: Minimum similarity (0-1) for merging patterns
        """
        self.log_file = log_file or Path(".claude-loop/execution_log.jsonl")
        self.min_occurrences = min_occurrences
        self.similarity_threshold = similarity_threshold
        self._patterns_cache: list[FailurePattern] | None = None

    def _load_failures(self) -> list[LogEntry]:
        """Load all failure entries from the log file."""
        if not self.log_file.exists():
            return []

        entries = []
        with open(self.log_file) as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    entry = LogEntry.from_dict(data, line_number=line_num)
                    # Only include failures
                    if entry.status != "success":
                        entries.append(entry)
                except json.JSONDecodeError:
                    continue

        return entries

    def _normalize_error(self, error_message: str) -> str:
        """
        Normalize error message for comparison.

        Removes variable parts like paths, line numbers, timestamps, IDs.
        """
        if not error_message:
            return ""

        msg = error_message.lower()

        # Remove file paths
        msg = re.sub(r'/[\w/.\-_]+', '<PATH>', msg)
        msg = re.sub(r'[A-Za-z]:\\[\w\\.\-_]+', '<PATH>', msg)  # Windows paths

        # Remove line numbers
        msg = re.sub(r'line \d+', 'line <N>', msg)
        msg = re.sub(r':\d+:\d+', ':<N>:<N>', msg)  # file:line:col format

        # Remove timestamps
        msg = re.sub(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}[Z\+\-\d:]*', '<TIMESTAMP>', msg)
        msg = re.sub(r'\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}', '<TIMESTAMP>', msg)

        # Remove hex values
        msg = re.sub(r'0x[a-f0-9]+', '<HEX>', msg)

        # Remove IDs and hashes (8+ hex chars)
        msg = re.sub(r'[a-f0-9]{8,}', '<ID>', msg)

        # Remove UUIDs
        msg = re.sub(r'[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}', '<UUID>', msg)

        # Remove numeric values
        msg = re.sub(r'\b\d+\b', '<NUM>', msg)

        # Remove extra whitespace
        msg = re.sub(r'\s+', ' ', msg).strip()

        return msg

    def _text_similarity(self, text1: str, text2: str) -> float:
        """
        Calculate text similarity using SequenceMatcher.

        Returns a value between 0 and 1.
        """
        if not text1 and not text2:
            return 1.0
        if not text1 or not text2:
            return 0.0

        return SequenceMatcher(None, text1, text2).ratio()

    def _generate_pattern_id(self, error_type: str, normalized_msg: str) -> str:
        """Generate a unique pattern ID from error type and normalized message."""
        content = f"{error_type}:{normalized_msg}"
        hash_val = hashlib.sha256(content.encode()).hexdigest()[:8]
        return f"PAT-{hash_val.upper()}"

    def _generate_description(
        self,
        error_type: str,
        normalized_msg: str,
    ) -> str:
        """Generate a human-readable description for a pattern."""
        if not normalized_msg:
            return f"Failures of type '{error_type}' with no error message"

        # Extract key phrases from normalized message
        key_words = []
        keywords_to_check = [
            "not found", "cannot", "permission", "timeout", "network",
            "parse", "invalid", "undefined", "missing", "failed",
            "error", "exception", "denied", "refused", "unavailable",
        ]

        msg_lower = normalized_msg.lower()
        for keyword in keywords_to_check:
            if keyword in msg_lower:
                key_words.append(keyword)

        if key_words:
            key_phrase = ", ".join(key_words[:3])
            return f"'{error_type}' failures involving {key_phrase}"
        else:
            # Truncate and use the message directly
            if len(normalized_msg) > 60:
                return f"'{error_type}': {normalized_msg[:60]}..."
            return f"'{error_type}': {normalized_msg}"

    def _extract_context_indicators(self, entries: list[LogEntry]) -> list[str]:
        """Extract common context indicators from a set of entries."""
        context_keys: defaultdict[str, int] = defaultdict(int)
        tools_count: defaultdict[str, int] = defaultdict(int)

        for entry in entries:
            # Count context keys
            for key in entry.context.keys():
                context_keys[key] += 1

            # Count tools used
            for tool in entry.tools_used:
                tools_count[tool] += 1

        # Get indicators that appear in at least half of entries
        threshold = len(entries) / 2
        indicators = []

        for key, count in context_keys.items():
            if count >= threshold:
                indicators.append(f"context:{key}")

        for tool, count in tools_count.items():
            if count >= threshold:
                indicators.append(f"tool:{tool}")

        return sorted(indicators)

    def cluster_failures(self, logs: list[LogEntry] | None = None) -> list[FailurePattern]:
        """
        Cluster failures into patterns.

        Args:
            logs: Optional list of log entries. If None, loads from file.

        Returns:
            List of FailurePattern objects
        """
        if logs is None:
            logs = self._load_failures()

        if not logs:
            return []

        # Step 1: Group by error_type
        by_type: defaultdict[str, list[LogEntry]] = defaultdict(list)
        for entry in logs:
            error_type = entry.error_type or "unknown"
            by_type[error_type].append(entry)

        # Step 2: Within each type, cluster by normalized message similarity
        preliminary_clusters: list[tuple[str, str, list[LogEntry]]] = []

        for error_type, entries in by_type.items():
            # Build similarity clusters
            clusters = self._build_similarity_clusters(entries)

            for cluster in clusters:
                if cluster:
                    # Use the first entry's normalized message as representative
                    rep_msg = self._normalize_error(cluster[0].error_message)
                    preliminary_clusters.append((error_type, rep_msg, cluster))

        # Step 3: Merge similar patterns across types
        merged_clusters = self._merge_similar_clusters(preliminary_clusters)

        # Step 4: Create patterns from clusters meeting threshold
        patterns: list[FailurePattern] = []
        for error_type, normalized_msg, entries in merged_clusters:
            if len(entries) >= self.min_occurrences:
                pattern = self._create_pattern(error_type, normalized_msg, entries)
                patterns.append(pattern)

        # Sort by occurrences (most frequent first)
        patterns.sort(key=lambda p: p.occurrences, reverse=True)

        self._patterns_cache = patterns
        return patterns

    def _build_similarity_clusters(self, entries: list[LogEntry]) -> list[list[LogEntry]]:
        """
        Build clusters of similar entries based on message similarity.

        Uses a simple greedy approach: assign each entry to the most similar
        existing cluster, or create a new cluster if no match exceeds threshold.
        """
        clusters: list[tuple[str, list[LogEntry]]] = []  # (representative_msg, entries)

        for entry in entries:
            normalized = self._normalize_error(entry.error_message)

            # Find best matching cluster
            best_match_idx = -1
            best_similarity = 0.0

            for idx, (rep_msg, _) in enumerate(clusters):
                sim = self._text_similarity(normalized, rep_msg)
                if sim > best_similarity:
                    best_similarity = sim
                    best_match_idx = idx

            if best_similarity >= self.similarity_threshold and best_match_idx >= 0:
                # Add to existing cluster
                clusters[best_match_idx][1].append(entry)
            else:
                # Create new cluster
                clusters.append((normalized, [entry]))

        return [entries for _, entries in clusters]

    def _merge_similar_clusters(
        self,
        clusters: list[tuple[str, str, list[LogEntry]]],
    ) -> list[tuple[str, str, list[LogEntry]]]:
        """
        Merge clusters that are highly similar across error types.

        This handles cases where the same underlying issue manifests with
        slightly different error types.
        """
        if len(clusters) <= 1:
            return clusters

        merged: list[tuple[str, str, list[LogEntry]]] = []
        used = set()

        for i, (type_i, msg_i, entries_i) in enumerate(clusters):
            if i in used:
                continue

            # Start with this cluster
            merged_entries = list(entries_i)
            merged_type = type_i
            merged_msg = msg_i

            # Check for similar clusters to merge
            for j, (type_j, msg_j, entries_j) in enumerate(clusters):
                if j <= i or j in used:
                    continue

                # Check similarity
                sim = self._text_similarity(msg_i, msg_j)
                if sim >= self.similarity_threshold:
                    merged_entries.extend(entries_j)
                    used.add(j)
                    # Keep the type with more occurrences
                    if len(entries_j) > len(entries_i):
                        merged_type = type_j
                        merged_msg = msg_j

            merged.append((merged_type, merged_msg, merged_entries))
            used.add(i)

        return merged

    def _create_pattern(
        self,
        error_type: str,
        normalized_msg: str,
        entries: list[LogEntry],
    ) -> FailurePattern:
        """Create a FailurePattern from a cluster of entries."""
        # Sort entries by timestamp to get first/last seen
        sorted_entries = sorted(
            entries,
            key=lambda e: e.timestamp_start or "1970-01-01T00:00:00Z"
        )

        first_seen = sorted_entries[0].timestamp_start if sorted_entries else ""
        last_seen = sorted_entries[-1].timestamp_start if sorted_entries else ""

        # Get unique affected stories
        affected_stories = list(set(e.story_id for e in entries if e.story_id))

        # Select example failures (first, middle, last for variety)
        examples: list[dict] = []
        if len(sorted_entries) >= 3:
            examples = [
                sorted_entries[0].to_dict(),
                sorted_entries[len(sorted_entries) // 2].to_dict(),
                sorted_entries[-1].to_dict(),
            ]
        else:
            examples = [e.to_dict() for e in sorted_entries[:self.DEFAULT_MAX_EXAMPLES]]

        # Generate pattern ID and description
        pattern_id = self._generate_pattern_id(error_type, normalized_msg)
        description = self._generate_description(error_type, normalized_msg)

        # Extract common context indicators
        context_indicators = self._extract_context_indicators(entries)

        return FailurePattern(
            pattern_id=pattern_id,
            description=description,
            error_type=error_type,
            normalized_message=normalized_msg,
            occurrences=len(entries),
            first_seen=first_seen,
            last_seen=last_seen,
            affected_stories=affected_stories,
            example_failures=examples,
            context_indicators=context_indicators,
        )

    def get_pattern_by_id(self, pattern_id: str) -> FailurePattern | None:
        """Get a specific pattern by its ID."""
        if self._patterns_cache is None:
            self.cluster_failures()

        for pattern in self._patterns_cache or []:
            if pattern.pattern_id == pattern_id:
                return pattern
        return None

    def get_summary(self) -> dict[str, Any]:
        """Get summary statistics of all patterns."""
        patterns = self._patterns_cache
        if patterns is None:
            patterns = self.cluster_failures()

        if not patterns:
            return {
                "total_patterns": 0,
                "total_failures_covered": 0,
                "by_error_type": {},
                "coverage_rate": 0,
            }

        total_covered = sum(p.occurrences for p in patterns)
        all_failures = self._load_failures()

        by_type: defaultdict[str, int] = defaultdict(int)
        for p in patterns:
            by_type[p.error_type] += p.occurrences

        return {
            "total_patterns": len(patterns),
            "total_failures_covered": total_covered,
            "total_failures": len(all_failures),
            "coverage_rate": total_covered / len(all_failures) if all_failures else 0,
            "by_error_type": dict(by_type),
            "patterns": [p.to_dict() for p in patterns],
        }


# ============================================================================
# CLI Interface
# ============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Failure Pattern Clustering for claude-loop",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python lib/pattern-clusterer.py analyze
    python lib/pattern-clusterer.py analyze --min-occurrences 2
    python lib/pattern-clusterer.py analyze --json
    python lib/pattern-clusterer.py list
    python lib/pattern-clusterer.py show PAT-12345678
        """,
    )

    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # analyze command
    analyze_parser = subparsers.add_parser(
        "analyze", help="Analyze failures and create patterns"
    )
    analyze_parser.add_argument(
        "--min-occurrences",
        type=int,
        default=PatternClusterer.DEFAULT_MIN_OCCURRENCES,
        help=f"Minimum occurrences to form a pattern (default: {PatternClusterer.DEFAULT_MIN_OCCURRENCES})",
    )
    analyze_parser.add_argument(
        "--similarity-threshold",
        type=float,
        default=PatternClusterer.DEFAULT_SIMILARITY_THRESHOLD,
        help=f"Similarity threshold for merging (default: {PatternClusterer.DEFAULT_SIMILARITY_THRESHOLD})",
    )
    analyze_parser.add_argument(
        "--json", action="store_true", help="Output as JSON"
    )

    # list command
    list_parser = subparsers.add_parser(
        "list", help="List all discovered patterns"
    )
    list_parser.add_argument(
        "--min-occurrences",
        type=int,
        default=PatternClusterer.DEFAULT_MIN_OCCURRENCES,
        help="Minimum occurrences to include",
    )
    list_parser.add_argument(
        "--json", action="store_true", help="Output as JSON"
    )

    # show command
    show_parser = subparsers.add_parser(
        "show", help="Show details of a specific pattern"
    )
    show_parser.add_argument(
        "pattern_id",
        type=str,
        help="Pattern ID (e.g., PAT-12345678)",
    )
    show_parser.add_argument(
        "--json", action="store_true", help="Output as JSON"
    )

    # summary command
    summary_parser = subparsers.add_parser(
        "summary", help="Show summary statistics"
    )
    summary_parser.add_argument(
        "--min-occurrences",
        type=int,
        default=PatternClusterer.DEFAULT_MIN_OCCURRENCES,
        help="Minimum occurrences for patterns",
    )
    summary_parser.add_argument(
        "--json", action="store_true", help="Output as JSON"
    )

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    # Determine log file path
    script_dir = Path(__file__).parent
    project_root = script_dir.parent
    log_file = project_root / ".claude-loop" / "execution_log.jsonl"

    # Create clusterer with options
    min_occ = getattr(args, 'min_occurrences', PatternClusterer.DEFAULT_MIN_OCCURRENCES)
    sim_thresh = getattr(args, 'similarity_threshold', PatternClusterer.DEFAULT_SIMILARITY_THRESHOLD)

    clusterer = PatternClusterer(
        log_file=log_file,
        min_occurrences=min_occ,
        similarity_threshold=sim_thresh,
    )

    if args.command == "analyze":
        patterns = clusterer.cluster_failures()

        if args.json:
            output = {
                "patterns": [p.to_dict() for p in patterns],
                "total_patterns": len(patterns),
                "min_occurrences": clusterer.min_occurrences,
                "similarity_threshold": clusterer.similarity_threshold,
            }
            print(json.dumps(output, indent=2))
        else:
            if not patterns:
                print("No patterns discovered.")
                print(f"\nNote: Patterns require at least {clusterer.min_occurrences} occurrences.")
                print("Try lowering --min-occurrences or adding more failure data.")
                return

            print(f"=== Failure Pattern Analysis ===")
            print(f"Min occurrences: {clusterer.min_occurrences}")
            print(f"Similarity threshold: {clusterer.similarity_threshold:.0%}")
            print(f"\nDiscovered {len(patterns)} patterns:\n")

            for i, pattern in enumerate(patterns, 1):
                print(f"{i}. [{pattern.pattern_id}] ({pattern.occurrences} occurrences)")
                print(f"   Type: {pattern.error_type}")
                print(f"   {pattern.description}")
                print(f"   First seen: {pattern.first_seen[:10] if pattern.first_seen else 'N/A'}")
                print(f"   Last seen: {pattern.last_seen[:10] if pattern.last_seen else 'N/A'}")
                print(f"   Affected stories: {', '.join(pattern.affected_stories[:3])}")
                if len(pattern.affected_stories) > 3:
                    print(f"   ... and {len(pattern.affected_stories) - 3} more")
                print()

    elif args.command == "list":
        patterns = clusterer.cluster_failures()

        if args.json:
            output = [
                {
                    "pattern_id": p.pattern_id,
                    "occurrences": p.occurrences,
                    "error_type": p.error_type,
                    "description": p.description,
                }
                for p in patterns
            ]
            print(json.dumps(output, indent=2))
        else:
            if not patterns:
                print("No patterns found.")
                return

            print(f"{'Pattern ID':<15} {'Count':>6}  {'Type':<12}  Description")
            print("-" * 80)
            for p in patterns:
                desc = p.description[:40] + "..." if len(p.description) > 40 else p.description
                print(f"{p.pattern_id:<15} {p.occurrences:>6}  {p.error_type:<12}  {desc}")

    elif args.command == "show":
        # Need to analyze first to find the pattern
        clusterer.cluster_failures()
        pattern = clusterer.get_pattern_by_id(args.pattern_id)

        if not pattern:
            print(f"Error: Pattern '{args.pattern_id}' not found")
            print("\nUse 'pattern-clusterer.py list' to see available patterns")
            sys.exit(1)

        if args.json:
            print(json.dumps(pattern.to_dict(), indent=2))
        else:
            print(f"=== Pattern: {pattern.pattern_id} ===\n")
            print(f"Description: {pattern.description}")
            print(f"Error Type: {pattern.error_type}")
            print(f"Occurrences: {pattern.occurrences}")
            print(f"First Seen: {pattern.first_seen}")
            print(f"Last Seen: {pattern.last_seen}")
            print(f"\nNormalized Message:")
            print(f"  {pattern.normalized_message or '<empty>'}")
            print(f"\nAffected Stories ({len(pattern.affected_stories)}):")
            for story in pattern.affected_stories:
                print(f"  - {story}")
            print(f"\nContext Indicators:")
            for indicator in pattern.context_indicators:
                print(f"  - {indicator}")
            print(f"\nExample Failures ({len(pattern.example_failures)}):")
            for i, ex in enumerate(pattern.example_failures, 1):
                print(f"\n  Example {i}:")
                print(f"    Story: {ex.get('story_id', 'N/A')}")
                print(f"    Time: {ex.get('timestamp_start', 'N/A')}")
                err_msg = ex.get('error_message', '')
                if err_msg:
                    err_msg = err_msg[:80] + "..." if len(err_msg) > 80 else err_msg
                    print(f"    Error: {err_msg}")

    elif args.command == "summary":
        summary = clusterer.get_summary()

        if args.json:
            # Remove full patterns from JSON summary (too verbose)
            summary_output = {k: v for k, v in summary.items() if k != 'patterns'}
            summary_output['pattern_ids'] = [p['pattern_id'] for p in summary.get('patterns', [])]
            print(json.dumps(summary_output, indent=2))
        else:
            print("=== Pattern Clustering Summary ===\n")
            print(f"Total patterns: {summary['total_patterns']}")
            print(f"Total failures covered: {summary['total_failures_covered']}")
            print(f"Total failures analyzed: {summary.get('total_failures', 0)}")
            print(f"Coverage rate: {summary['coverage_rate']:.1%}")
            print(f"\nBy Error Type:")
            for error_type, count in summary.get('by_error_type', {}).items():
                print(f"  {error_type}: {count}")


if __name__ == "__main__":
    main()
