#!/usr/bin/env python3
"""
failure-classifier.py - Failure Classification Taxonomy for claude-loop

Classifies execution failures into actionable categories to enable
intelligent self-improvement and gap detection.

Categories:
- SUCCESS: Execution completed successfully
- TASK_FAILURE: Task requirements are impossible/contradictory
- CAPABILITY_GAP: Missing capability that should be added
- TRANSIENT_ERROR: Temporary issue (network, timeout) - retry may help
- UNKNOWN: Unclassified failure

Usage:
    python lib/failure-classifier.py classify <log_entry_id>
    python lib/failure-classifier.py batch-classify --since <date>
    python lib/failure-classifier.py analyze
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any


class FailureCategory(Enum):
    """Failure categories for classification."""

    SUCCESS = "success"
    TASK_FAILURE = "task_failure"       # Impossible requirements
    CAPABILITY_GAP = "capability_gap"   # Missing capability
    TRANSIENT_ERROR = "transient_error" # Temporary issue
    UNKNOWN = "unknown"                 # Cannot classify


@dataclass
class ClassificationResult:
    """Result of failure classification."""

    category: FailureCategory
    confidence: float  # 0-1
    reasoning: str
    contributing_factors: list[str] = field(default_factory=list)
    suggested_action: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "category": self.category.value,
            "confidence": round(self.confidence, 3),
            "reasoning": self.reasoning,
            "contributing_factors": self.contributing_factors,
            "suggested_action": self.suggested_action,
        }


@dataclass
class LogEntry:
    """Parsed execution log entry."""

    story_id: str
    story_title: str
    timestamp_start: str
    timestamp_end: str
    duration_ms: int
    status: str
    exit_code: int
    error_type: str
    error_message: str
    retry_count: int
    fallback_count: int
    attempted_actions: list[dict]
    tools_used: list[str]
    file_types: list[str]
    context: dict

    # Optional fields added during processing
    line_number: int = 0  # Line number in log file for reference

    @classmethod
    def from_dict(cls, data: dict, line_number: int = 0) -> LogEntry:
        return cls(
            story_id=data.get("story_id", ""),
            story_title=data.get("story_title", ""),
            timestamp_start=data.get("timestamp_start", ""),
            timestamp_end=data.get("timestamp_end", ""),
            duration_ms=data.get("duration_ms", 0),
            status=data.get("status", "unknown"),
            exit_code=data.get("exit_code", 1),
            error_type=data.get("error_type", ""),
            error_message=data.get("error_message", ""),
            retry_count=data.get("retry_count", 0),
            fallback_count=data.get("fallback_count", 0),
            attempted_actions=data.get("attempted_actions", []),
            tools_used=data.get("tools_used", []),
            file_types=data.get("file_types", []),
            context=data.get("context", {}),
            line_number=line_number,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "story_id": self.story_id,
            "story_title": self.story_title,
            "timestamp_start": self.timestamp_start,
            "timestamp_end": self.timestamp_end,
            "duration_ms": self.duration_ms,
            "status": self.status,
            "exit_code": self.exit_code,
            "error_type": self.error_type,
            "error_message": self.error_message,
            "retry_count": self.retry_count,
            "fallback_count": self.fallback_count,
            "attempted_actions": self.attempted_actions,
            "tools_used": self.tools_used,
            "file_types": self.file_types,
            "context": self.context,
            "line_number": self.line_number,
        }


class FailureClassifier:
    """
    Classifies execution failures into actionable categories.

    Uses a combination of:
    1. Error pattern matching
    2. Historical analysis (repeated errors -> capability gap)
    3. Task analysis (impossible requirements)
    4. Context analysis (UI, network, file operations)
    """

    # Error patterns that suggest specific categories
    TRANSIENT_PATTERNS = [
        r"timeout|timed out",
        r"connection refused|econnrefused",
        r"network.*error|socket.*error",
        r"rate limit|throttl",
        r"temporary.*unavailable|service unavailable",
        r"503|502|504",
        r"could not connect",
        r"dns.*fail",
        r"retry.*fail|retrying",
    ]

    CAPABILITY_GAP_PATTERNS = [
        r"not (found|supported|available|implemented)",
        r"cannot (access|find|read|write|execute|click|interact)",
        r"no (such|method|handler|capability)",
        r"unknown (tool|command|action)",
        r"permission denied",
        r"unsupported (operation|format|type)",
        r"not (recognized|handled)",
        r"missing (capability|tool|handler)",
        r"unable to (locate|find|access|interact)",
        r"element.*not (found|visible|clickable)",
        r"ui.*not (responding|available)",
        r"screenshot.*fail",
        r"automation.*fail",
    ]

    TASK_FAILURE_PATTERNS = [
        r"contradictory|conflict|incompatible",
        r"impossible|cannot be done",
        r"invalid (requirement|specification|constraint)",
        r"mutually exclusive",
        r"undefined (requirement|behavior)",
        r"ambiguous|unclear",
        r"circular dependency",
        r"infinite (loop|recursion)",
    ]

    # Context indicators for capability gaps
    UI_CONTEXT_INDICATORS = [
        "click", "button", "element", "screenshot", "visual",
        "ui", "gui", "window", "dialog", "menu", "input",
        "form", "field", "select", "dropdown", "checkbox",
    ]

    FILE_CONTEXT_INDICATORS = [
        "file", "directory", "path", "read", "write",
        "open", "save", "load", "create", "delete",
    ]

    NETWORK_CONTEXT_INDICATORS = [
        "api", "request", "response", "http", "https",
        "fetch", "download", "upload", "url", "endpoint",
    ]

    def __init__(self, log_file: Path | None = None):
        """
        Initialize the classifier.

        Args:
            log_file: Path to execution_log.jsonl. If None, uses default.
        """
        self.log_file = log_file or Path(".claude-loop/execution_log.jsonl")
        self._history_cache: dict[str, list[LogEntry]] = {}
        self._error_counts: Counter = Counter()

    def _matches_patterns(
        self, text: str, patterns: list[str]
    ) -> tuple[bool, list[str]]:
        """Check if text matches any patterns. Returns (matched, matching_patterns)."""
        text_lower = text.lower()
        matching = []
        for pattern in patterns:
            if re.search(pattern, text_lower):
                matching.append(pattern)
        return bool(matching), matching

    def _has_context_indicators(
        self, entry: LogEntry, indicators: list[str]
    ) -> bool:
        """Check if log entry has context matching given indicators."""
        # Check error message
        error_lower = entry.error_message.lower()
        if any(ind in error_lower for ind in indicators):
            return True

        # Check tools used
        tools_str = " ".join(entry.tools_used).lower()
        if any(ind in tools_str for ind in indicators):
            return True

        # Check context
        context_str = json.dumps(entry.context).lower()
        if any(ind in context_str for ind in indicators):
            return True

        # Check attempted actions
        actions_str = json.dumps(entry.attempted_actions).lower()
        if any(ind in actions_str for ind in indicators):
            return True

        return False

    def _load_history(self) -> list[LogEntry]:
        """Load all log entries from file."""
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
                    entries.append(LogEntry.from_dict(data, line_number=line_num))
                except json.JSONDecodeError:
                    continue

        return entries

    def _get_error_frequency(self, error_message: str) -> int:
        """Get how many times this error (or similar) has occurred."""
        if not self._error_counts:
            # Build error frequency cache
            entries = self._load_history()
            for entry in entries:
                if entry.status != "success" and entry.error_message:
                    # Normalize error message for counting
                    normalized = self._normalize_error(entry.error_message)
                    self._error_counts[normalized] += 1

        normalized = self._normalize_error(error_message)
        return self._error_counts.get(normalized, 0)

    def _normalize_error(self, error_message: str) -> str:
        """Normalize error message for comparison (remove variable parts)."""
        msg = error_message.lower()
        # Remove file paths
        msg = re.sub(r'/[\w/.-]+', '<PATH>', msg)
        # Remove line numbers
        msg = re.sub(r'line \d+', 'line <N>', msg)
        # Remove timestamps
        msg = re.sub(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}', '<TIMESTAMP>', msg)
        # Remove hex values
        msg = re.sub(r'0x[a-f0-9]+', '<HEX>', msg)
        # Remove IDs and hashes
        msg = re.sub(r'[a-f0-9]{8,}', '<ID>', msg)
        return msg.strip()

    def _get_story_history(self, story_id: str) -> list[LogEntry]:
        """Get all past executions for a specific story."""
        if story_id not in self._history_cache:
            entries = self._load_history()
            self._history_cache[story_id] = [
                e for e in entries if e.story_id == story_id
            ]
        return self._history_cache[story_id]

    def classify_failure(self, entry: LogEntry) -> ClassificationResult:
        """
        Classify a single execution log entry.

        Args:
            entry: The log entry to classify

        Returns:
            ClassificationResult with category, confidence, and reasoning
        """
        # Handle success case
        if entry.status == "success":
            return ClassificationResult(
                category=FailureCategory.SUCCESS,
                confidence=1.0,
                reasoning="Execution completed successfully",
                suggested_action="No action needed",
            )

        # Collect evidence for classification
        factors: list[str] = []
        scores: dict[FailureCategory, float] = {
            FailureCategory.TRANSIENT_ERROR: 0.0,
            FailureCategory.CAPABILITY_GAP: 0.0,
            FailureCategory.TASK_FAILURE: 0.0,
            FailureCategory.UNKNOWN: 0.1,  # Base score for unknown
        }

        error_msg = entry.error_message
        error_type = entry.error_type

        # 1. Check error patterns
        if error_msg:
            # Transient patterns
            is_transient, transient_matches = self._matches_patterns(
                error_msg, self.TRANSIENT_PATTERNS
            )
            if is_transient:
                scores[FailureCategory.TRANSIENT_ERROR] += 0.4
                factors.append(f"Matches transient patterns: {transient_matches[:2]}")

            # Capability gap patterns
            is_gap, gap_matches = self._matches_patterns(
                error_msg, self.CAPABILITY_GAP_PATTERNS
            )
            if is_gap:
                scores[FailureCategory.CAPABILITY_GAP] += 0.3
                factors.append(f"Matches capability gap patterns: {gap_matches[:2]}")

            # Task failure patterns
            is_task_fail, task_matches = self._matches_patterns(
                error_msg, self.TASK_FAILURE_PATTERNS
            )
            if is_task_fail:
                scores[FailureCategory.TASK_FAILURE] += 0.5
                factors.append(f"Matches task failure patterns: {task_matches[:2]}")

        # 2. Check error type from logger
        if error_type:
            if error_type == "timeout":
                scores[FailureCategory.TRANSIENT_ERROR] += 0.3
                factors.append("Error type: timeout")
            elif error_type == "network":
                scores[FailureCategory.TRANSIENT_ERROR] += 0.4
                factors.append("Error type: network")
            elif error_type == "not_found":
                # Could be transient or capability gap
                scores[FailureCategory.CAPABILITY_GAP] += 0.2
                scores[FailureCategory.TRANSIENT_ERROR] += 0.1
                factors.append("Error type: not_found")
            elif error_type == "permission":
                scores[FailureCategory.CAPABILITY_GAP] += 0.3
                factors.append("Error type: permission")
            elif error_type == "parse":
                # Parse errors are usually capability gaps
                scores[FailureCategory.CAPABILITY_GAP] += 0.2
                factors.append("Error type: parse")
            elif error_type == "validation":
                # Could be task issue or implementation bug
                scores[FailureCategory.TASK_FAILURE] += 0.2
                scores[FailureCategory.CAPABILITY_GAP] += 0.1
                factors.append("Error type: validation")

        # 3. Check context indicators (enhances capability gap detection)
        if self._has_context_indicators(entry, self.UI_CONTEXT_INDICATORS):
            # UI context + not_found pattern = likely capability gap
            if "not found" in error_msg.lower() or "cannot" in error_msg.lower():
                scores[FailureCategory.CAPABILITY_GAP] += 0.25
                factors.append("UI context with 'not found' - likely capability gap")
            else:
                scores[FailureCategory.CAPABILITY_GAP] += 0.1
                factors.append("UI context present")

        if self._has_context_indicators(entry, self.NETWORK_CONTEXT_INDICATORS):
            # Network context suggests transient issues
            scores[FailureCategory.TRANSIENT_ERROR] += 0.15
            factors.append("Network context present")

        # 4. Check retry/fallback counts (indicates transient issues were attempted)
        if entry.retry_count > 0:
            # Retries suggest the system thought it was transient
            scores[FailureCategory.TRANSIENT_ERROR] += 0.1 * min(entry.retry_count, 3)
            factors.append(f"Retry count: {entry.retry_count}")

            # But if still failed after retries, might be capability gap
            if entry.retry_count >= 2:
                scores[FailureCategory.CAPABILITY_GAP] += 0.15
                factors.append("Failed despite multiple retries")

        if entry.fallback_count > 0:
            scores[FailureCategory.TRANSIENT_ERROR] += 0.05 * entry.fallback_count
            factors.append(f"Fallback count: {entry.fallback_count}")

        # 5. Check historical frequency (repeated same error = capability gap)
        error_frequency = self._get_error_frequency(error_msg)
        if error_frequency >= 3:
            scores[FailureCategory.CAPABILITY_GAP] += 0.35
            scores[FailureCategory.TRANSIENT_ERROR] -= 0.2
            factors.append(f"Error occurred {error_frequency} times - likely capability gap")
        elif error_frequency == 1:
            scores[FailureCategory.TRANSIENT_ERROR] += 0.1
            factors.append("First occurrence - may be transient")

        # 6. Check story-specific history
        story_history = self._get_story_history(entry.story_id)
        failed_attempts = [h for h in story_history if h.status != "success"]
        if len(failed_attempts) >= 3:
            scores[FailureCategory.CAPABILITY_GAP] += 0.2
            factors.append(f"Story failed {len(failed_attempts)} times")

        # 7. Duration analysis
        if entry.duration_ms > 60000:  # > 1 minute
            # Long duration suggests something hung
            scores[FailureCategory.TRANSIENT_ERROR] += 0.1
            factors.append("Long duration (>1min)")
        elif entry.duration_ms < 1000:  # < 1 second
            # Very fast failure suggests hard error
            scores[FailureCategory.CAPABILITY_GAP] += 0.05
            factors.append("Fast failure (<1s)")

        # Determine category based on highest score
        best_category = max(scores, key=lambda c: scores[c])
        best_score = scores[best_category]

        # Calculate confidence based on score differential
        sorted_scores = sorted(scores.values(), reverse=True)
        if len(sorted_scores) > 1:
            score_gap = sorted_scores[0] - sorted_scores[1]
            confidence = min(0.95, best_score * (1 + score_gap))
        else:
            confidence = min(0.95, best_score)

        # Cap confidence for unknown
        if best_category == FailureCategory.UNKNOWN:
            confidence = min(0.3, confidence)

        # Generate reasoning
        reasoning = self._generate_reasoning(best_category, factors, scores)

        # Generate suggested action
        suggested_action = self._generate_suggested_action(best_category, factors)

        return ClassificationResult(
            category=best_category,
            confidence=confidence,
            reasoning=reasoning,
            contributing_factors=factors,
            suggested_action=suggested_action,
        )

    def _generate_reasoning(
        self,
        category: FailureCategory,
        factors: list[str],
        scores: dict[FailureCategory, float],
    ) -> str:
        """Generate human-readable reasoning for classification."""
        if category == FailureCategory.TRANSIENT_ERROR:
            return (
                f"Classified as transient error (score: {scores[category]:.2f}). "
                f"This appears to be a temporary issue that may resolve with retry. "
                f"Key factors: {', '.join(factors[:3])}"
            )
        elif category == FailureCategory.CAPABILITY_GAP:
            return (
                f"Classified as capability gap (score: {scores[category]:.2f}). "
                f"This failure suggests a missing or incomplete capability. "
                f"Key factors: {', '.join(factors[:3])}"
            )
        elif category == FailureCategory.TASK_FAILURE:
            return (
                f"Classified as task failure (score: {scores[category]:.2f}). "
                f"The task requirements may be impossible or contradictory. "
                f"Key factors: {', '.join(factors[:3])}"
            )
        else:
            return (
                f"Could not confidently classify (score: {scores[category]:.2f}). "
                f"Factors: {', '.join(factors[:3]) if factors else 'none identified'}"
            )

    def _generate_suggested_action(
        self, category: FailureCategory, factors: list[str]
    ) -> str:
        """Generate suggested action based on classification."""
        if category == FailureCategory.TRANSIENT_ERROR:
            return "Retry the operation or wait for external service to recover"
        elif category == FailureCategory.CAPABILITY_GAP:
            if any("ui" in f.lower() for f in factors):
                return "Add UI automation capability for this interaction"
            elif any("permission" in f.lower() for f in factors):
                return "Review and acquire necessary permissions"
            else:
                return "Implement missing capability to handle this scenario"
        elif category == FailureCategory.TASK_FAILURE:
            return "Review task requirements for contradictions or impossible constraints"
        else:
            return "Manual investigation required to determine root cause"

    def batch_classify(
        self, since: str | None = None
    ) -> list[tuple[LogEntry, ClassificationResult]]:
        """
        Classify all failure entries, optionally since a given date.

        Args:
            since: ISO date string to filter entries (optional)

        Returns:
            List of (entry, classification) tuples
        """
        entries = self._load_history()

        # Filter by date if specified
        if since:
            try:
                since_dt = datetime.fromisoformat(since.replace('Z', '+00:00'))
                entries = [
                    e for e in entries
                    if datetime.fromisoformat(
                        e.timestamp_start.replace('Z', '+00:00')
                    ) >= since_dt
                ]
            except ValueError:
                pass

        # Filter to failures only
        failures = [e for e in entries if e.status != "success"]

        # Classify each
        results = []
        for entry in failures:
            classification = self.classify_failure(entry)
            results.append((entry, classification))

        return results

    def get_entry_by_line(self, line_number: int) -> LogEntry | None:
        """Get a specific log entry by line number."""
        if not self.log_file.exists():
            return None

        with open(self.log_file) as f:
            for curr_line, line in enumerate(f, 1):
                if curr_line == line_number:
                    line = line.strip()
                    if not line:
                        return None
                    try:
                        data = json.loads(line)
                        return LogEntry.from_dict(data, line_number=line_number)
                    except json.JSONDecodeError:
                        return None

        return None

    def get_summary_stats(self) -> dict[str, Any]:
        """Get classification summary statistics."""
        results = self.batch_classify()

        if not results:
            return {
                "total_failures": 0,
                "by_category": {},
                "avg_confidence": 0,
                "common_factors": [],
            }

        category_counts = Counter(r.category.value for _, r in results)
        all_factors = []
        confidence_sum = 0

        for _, result in results:
            all_factors.extend(result.contributing_factors)
            confidence_sum += result.confidence

        factor_counts = Counter(all_factors).most_common(10)

        return {
            "total_failures": len(results),
            "by_category": dict(category_counts),
            "avg_confidence": confidence_sum / len(results) if results else 0,
            "common_factors": [
                {"factor": f, "count": c} for f, c in factor_counts
            ],
        }


# ============================================================================
# CLI Interface
# ============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Failure Classification for claude-loop",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python lib/failure-classifier.py classify 5
    python lib/failure-classifier.py batch-classify --since 2026-01-01
    python lib/failure-classifier.py analyze
    python lib/failure-classifier.py categories
        """,
    )

    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # classify command
    classify_parser = subparsers.add_parser(
        "classify", help="Classify a specific log entry"
    )
    classify_parser.add_argument(
        "log_entry_id",
        type=int,
        help="Line number of log entry to classify",
    )
    classify_parser.add_argument(
        "--json", action="store_true", help="Output as JSON"
    )

    # batch-classify command
    batch_parser = subparsers.add_parser(
        "batch-classify", help="Classify all failures"
    )
    batch_parser.add_argument(
        "--since", type=str, help="Only classify entries since this date (ISO format)"
    )
    batch_parser.add_argument(
        "--json", action="store_true", help="Output as JSON"
    )

    # analyze command
    analyze_parser = subparsers.add_parser(
        "analyze", help="Show classification summary statistics"
    )
    analyze_parser.add_argument(
        "--json", action="store_true", help="Output as JSON"
    )

    # categories command
    subparsers.add_parser(
        "categories", help="List all failure categories"
    )

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    # Change to project root if running from different directory
    script_dir = Path(__file__).parent
    project_root = script_dir.parent
    log_file = project_root / ".claude-loop" / "execution_log.jsonl"

    classifier = FailureClassifier(log_file=log_file)

    if args.command == "classify":
        entry = classifier.get_entry_by_line(args.log_entry_id)
        if not entry:
            print(f"Error: No log entry found at line {args.log_entry_id}")
            sys.exit(1)

        result = classifier.classify_failure(entry)

        if args.json:
            output = {
                "entry": entry.to_dict(),
                "classification": result.to_dict(),
            }
            print(json.dumps(output, indent=2))
        else:
            print(f"Story: {entry.story_id} - {entry.story_title}")
            print(f"Status: {entry.status}")
            print(f"Error: {entry.error_message[:100] if entry.error_message else 'N/A'}")
            print()
            print(f"Category: {result.category.value}")
            print(f"Confidence: {result.confidence:.2%}")
            print(f"Reasoning: {result.reasoning}")
            print()
            print("Contributing Factors:")
            for factor in result.contributing_factors:
                print(f"  - {factor}")
            print()
            print(f"Suggested Action: {result.suggested_action}")

    elif args.command == "batch-classify":
        results = classifier.batch_classify(since=args.since)

        if args.json:
            output = [
                {
                    "entry": entry.to_dict(),
                    "classification": result.to_dict(),
                }
                for entry, result in results
            ]
            print(json.dumps(output, indent=2))
        else:
            if not results:
                print("No failure entries found")
                return

            print(f"Classified {len(results)} failures:\n")

            for entry, result in results:
                print(
                    f"  [{result.category.value:15}] "
                    f"({result.confidence:.0%}) "
                    f"{entry.story_id}: {entry.error_message[:50]}..."
                    if entry.error_message else
                    f"  [{result.category.value:15}] "
                    f"({result.confidence:.0%}) "
                    f"{entry.story_id}: <no error message>"
                )

            print()

            # Summary
            by_category = Counter(r.category.value for _, r in results)
            print("Summary by category:")
            for cat, count in sorted(by_category.items()):
                print(f"  {cat}: {count}")

    elif args.command == "analyze":
        stats = classifier.get_summary_stats()

        if args.json:
            print(json.dumps(stats, indent=2))
        else:
            print("=== Classification Analysis ===\n")
            print(f"Total failures analyzed: {stats['total_failures']}")
            print(f"Average confidence: {stats['avg_confidence']:.2%}")
            print()
            print("By Category:")
            for cat, count in stats.get('by_category', {}).items():
                print(f"  {cat}: {count}")
            print()
            print("Common Contributing Factors:")
            for item in stats.get('common_factors', [])[:5]:
                print(f"  - {item['factor']} ({item['count']} occurrences)")

    elif args.command == "categories":
        print("Failure Categories:\n")
        for cat in FailureCategory:
            descriptions = {
                FailureCategory.SUCCESS: "Execution completed successfully",
                FailureCategory.TASK_FAILURE: "Task requirements are impossible or contradictory",
                FailureCategory.CAPABILITY_GAP: "Missing capability that should be added",
                FailureCategory.TRANSIENT_ERROR: "Temporary issue (network, timeout) - retry may help",
                FailureCategory.UNKNOWN: "Cannot confidently classify",
            }
            print(f"  {cat.value}:")
            print(f"    {descriptions[cat]}")
            print()


if __name__ == "__main__":
    main()
