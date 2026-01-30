#!/usr/bin/env python3
"""
root-cause-analyzer.py - Root Cause Analysis Engine for claude-loop

Performs automated 5-Whys analysis on failure patterns to identify
root causes and capability gaps.

Features:
- 5-Whys decomposition on failure patterns
- LLM-assisted analysis with caching
- Heuristic-only mode for offline analysis
- Counterfactual analysis ("What capability would prevent this?")
- References similar past patterns that were resolved
- Persistent cache to avoid repeated LLM calls

Usage:
    python lib/root-cause-analyzer.py analyze <pattern_id>
    python lib/root-cause-analyzer.py analyze <pattern_id> --no-llm
    python lib/root-cause-analyzer.py list
    python lib/root-cause-analyzer.py batch-analyze
    python lib/root-cause-analyzer.py cache-stats
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

# Import from sibling modules with hyphenated names
import importlib.util

def _import_module(module_name: str, file_name: str):
    """Import a module from a hyphenated filename."""
    module_path = Path(__file__).parent / file_name
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot import {module_name} from {file_name}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module

_pattern_clusterer = _import_module("pattern_clusterer", "pattern-clusterer.py")
FailurePattern = _pattern_clusterer.FailurePattern
PatternClusterer = _pattern_clusterer.PatternClusterer


@dataclass
class RootCauseAnalysis:
    """Result of root cause analysis on a failure pattern."""

    pattern_id: str
    whys: list[str]  # List of 5 "why" decomposition steps
    root_cause: str
    capability_gap: str
    counterfactual: str  # What capability would have prevented this?
    confidence: float  # 0-1
    similar_patterns: list[dict]  # Past patterns that were resolved
    analysis_method: str  # "llm" or "heuristic"
    timestamp: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "pattern_id": self.pattern_id,
            "whys": self.whys,
            "root_cause": self.root_cause,
            "capability_gap": self.capability_gap,
            "counterfactual": self.counterfactual,
            "confidence": round(self.confidence, 3),
            "similar_patterns": self.similar_patterns,
            "analysis_method": self.analysis_method,
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_dict(cls, data: dict) -> RootCauseAnalysis:
        return cls(
            pattern_id=data.get("pattern_id", ""),
            whys=data.get("whys", []),
            root_cause=data.get("root_cause", ""),
            capability_gap=data.get("capability_gap", ""),
            counterfactual=data.get("counterfactual", ""),
            confidence=data.get("confidence", 0.0),
            similar_patterns=data.get("similar_patterns", []),
            analysis_method=data.get("analysis_method", "unknown"),
            timestamp=data.get("timestamp", ""),
        )


class RootCauseAnalyzer:
    """
    Performs root cause analysis on failure patterns.

    Uses a combination of:
    1. 5-Whys decomposition (LLM-assisted or heuristic)
    2. Pattern matching for common root causes
    3. Historical pattern analysis
    4. Counterfactual reasoning
    """

    # Common root cause patterns for heuristic analysis
    ROOT_CAUSE_PATTERNS = {
        "missing_tool": {
            "keywords": ["not found", "unknown tool", "no handler", "unsupported"],
            "root_cause": "Missing tool or handler for required operation",
            "capability_gap": "Tool or handler implementation",
            "counterfactual": "A registered handler for this operation type",
        },
        "ui_automation": {
            "keywords": ["element not", "cannot click", "ui not", "screenshot", "visual"],
            "root_cause": "UI automation capability is limited or unavailable",
            "capability_gap": "UI interaction and visual automation",
            "counterfactual": "Robust UI automation with element detection and interaction",
        },
        "permission": {
            "keywords": ["permission denied", "access denied", "forbidden", "unauthorized"],
            "root_cause": "Insufficient permissions for required operation",
            "capability_gap": "Permission management and escalation",
            "counterfactual": "Proper permission handling and user prompting",
        },
        "network": {
            "keywords": ["connection", "timeout", "network", "socket", "dns"],
            "root_cause": "Network connectivity or service availability issue",
            "capability_gap": "Network resilience and retry logic",
            "counterfactual": "Robust network handling with retries and fallbacks",
        },
        "parsing": {
            "keywords": ["parse error", "syntax error", "invalid json", "malformed"],
            "root_cause": "Input data format is unexpected or malformed",
            "capability_gap": "Robust parsing with error recovery",
            "counterfactual": "Flexible parsing with format detection and recovery",
        },
        "file_handling": {
            "keywords": ["file not found", "cannot read", "cannot write", "directory"],
            "root_cause": "File system operation failed",
            "capability_gap": "File handling and path resolution",
            "counterfactual": "Robust file handling with existence checks and creation",
        },
        "state_management": {
            "keywords": ["state", "undefined", "null", "missing data", "not initialized"],
            "root_cause": "Application state is inconsistent or missing",
            "capability_gap": "State management and initialization",
            "counterfactual": "Proper state tracking and initialization checks",
        },
        "api_interaction": {
            "keywords": ["api", "endpoint", "request failed", "response", "http"],
            "root_cause": "API interaction failed or returned unexpected response",
            "capability_gap": "API interaction handling",
            "counterfactual": "Robust API client with error handling and retries",
        },
    }

    # 5-Whys templates for common patterns
    WHYS_TEMPLATES = {
        "missing_tool": [
            "The operation failed because the required tool is not available",
            "The tool is not available because it was not registered or implemented",
            "It was not implemented because the capability was not identified as needed",
            "The capability was not identified because similar tasks haven't been attempted",
            "Similar tasks haven't been attempted because the system's scope was limited",
        ],
        "ui_automation": [
            "The UI interaction failed because the element could not be located or clicked",
            "The element could not be located because UI automation is not fully implemented",
            "UI automation is limited because visual element detection is incomplete",
            "Visual detection is incomplete because multi-platform UI support is challenging",
            "Multi-platform support is challenging because UI frameworks vary significantly",
        ],
        "permission": [
            "The operation failed because permission was denied",
            "Permission was denied because the required access level wasn't obtained",
            "Access wasn't obtained because the system didn't prompt for elevation",
            "Elevation wasn't prompted because permission requirements weren't detected",
            "Requirements weren't detected because pre-flight checks are incomplete",
        ],
        "network": [
            "The network operation failed because the connection was unsuccessful",
            "The connection failed because the service was unavailable or unreachable",
            "The service was unreachable due to network conditions or service issues",
            "Network issues weren't handled because retry/fallback logic is limited",
            "Retry logic is limited because network resilience wasn't prioritized",
        ],
        "parsing": [
            "Parsing failed because the input format was unexpected",
            "The format was unexpected because input validation is incomplete",
            "Validation is incomplete because format variations weren't anticipated",
            "Variations weren't anticipated because input sources are diverse",
            "Diverse sources weren't handled because flexible parsing wasn't implemented",
        ],
        "file_handling": [
            "The file operation failed because the file or path doesn't exist",
            "The path doesn't exist because directory structure wasn't verified",
            "Structure wasn't verified because pre-flight checks are incomplete",
            "Pre-flight checks are incomplete because file operations assume valid paths",
            "Valid paths are assumed because explicit creation/verification wasn't added",
        ],
        "state_management": [
            "The operation failed because required state was missing or invalid",
            "State was missing because initialization wasn't complete",
            "Initialization wasn't complete because state dependencies weren't tracked",
            "Dependencies weren't tracked because state management is informal",
            "State management is informal because a formal state machine wasn't implemented",
        ],
        "api_interaction": [
            "The API call failed because the response was unexpected or error",
            "The response was unexpected because API behavior changed or was misunderstood",
            "API behavior was misunderstood because documentation was incomplete",
            "Documentation was incomplete because API integration tests are limited",
            "Tests are limited because API mocking and validation weren't prioritized",
        ],
    }

    def __init__(
        self,
        project_root: Path | None = None,
        cache_dir: Path | None = None,
        use_llm: bool = True,
    ):
        """
        Initialize the analyzer.

        Args:
            project_root: Path to project root directory
            cache_dir: Path to cache directory for analysis results
            use_llm: Whether to use LLM for analysis (vs heuristics only)
        """
        self.project_root = project_root or Path(__file__).parent.parent
        self.cache_dir = cache_dir or self.project_root / ".claude-loop" / "analysis_cache"
        self.use_llm = use_llm

        # Ensure cache directory exists
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        # Initialize pattern clusterer
        log_file = self.project_root / ".claude-loop" / "execution_log.jsonl"
        self.clusterer = PatternClusterer(log_file=log_file)

        # Load resolved patterns cache
        self.resolved_patterns_file = self.cache_dir / "resolved_patterns.json"
        self._resolved_patterns: list[dict] = self._load_resolved_patterns()

    def _load_resolved_patterns(self) -> list[dict]:
        """Load the cache of resolved patterns."""
        if self.resolved_patterns_file.exists():
            try:
                with open(self.resolved_patterns_file) as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                pass
        return []

    def _save_resolved_patterns(self) -> None:
        """Save resolved patterns to cache."""
        try:
            with open(self.resolved_patterns_file, 'w') as f:
                json.dump(self._resolved_patterns, f, indent=2)
        except IOError:
            pass

    def _get_cache_key(self, pattern_id: str) -> str:
        """Generate cache key for a pattern analysis."""
        return hashlib.sha256(pattern_id.encode()).hexdigest()[:16]

    def _get_cached_analysis(self, pattern_id: str) -> RootCauseAnalysis | None:
        """Retrieve cached analysis for a pattern."""
        cache_key = self._get_cache_key(pattern_id)
        cache_file = self.cache_dir / f"{cache_key}.json"

        if cache_file.exists():
            try:
                with open(cache_file) as f:
                    data = json.load(f)
                    return RootCauseAnalysis.from_dict(data)
            except (json.JSONDecodeError, IOError):
                pass

        return None

    def _cache_analysis(self, analysis: RootCauseAnalysis) -> None:
        """Cache an analysis result."""
        cache_key = self._get_cache_key(analysis.pattern_id)
        cache_file = self.cache_dir / f"{cache_key}.json"

        try:
            with open(cache_file, 'w') as f:
                json.dump(analysis.to_dict(), f, indent=2)
        except IOError:
            pass

    def _match_pattern_category(self, pattern: FailurePattern) -> str | None:
        """Match a pattern to a root cause category using keywords."""
        search_text = (
            f"{pattern.error_type} {pattern.normalized_message} "
            f"{pattern.description} {' '.join(pattern.context_indicators)}"
        ).lower()

        best_match = None
        best_count = 0

        for category, config in self.ROOT_CAUSE_PATTERNS.items():
            keyword_matches = sum(
                1 for kw in config["keywords"]
                if kw.lower() in search_text
            )
            if keyword_matches > best_count:
                best_count = keyword_matches
                best_match = category

        return best_match if best_count > 0 else None

    def _find_similar_resolved_patterns(
        self, pattern: FailurePattern
    ) -> list[dict]:
        """Find past patterns that were similar and have been resolved."""
        similar = []
        normalized_msg = pattern.normalized_message.lower()

        for resolved in self._resolved_patterns:
            resolved_msg = resolved.get("normalized_message", "").lower()

            # Check for similarity
            if self._text_similarity(normalized_msg, resolved_msg) > 0.7:
                similar.append({
                    "pattern_id": resolved.get("pattern_id"),
                    "resolution": resolved.get("resolution"),
                    "resolved_date": resolved.get("resolved_date"),
                })

        return similar[:3]  # Return top 3 similar

    def _text_similarity(self, text1: str, text2: str) -> float:
        """Calculate simple word overlap similarity."""
        if not text1 or not text2:
            return 0.0

        words1 = set(text1.split())
        words2 = set(text2.split())

        if not words1 or not words2:
            return 0.0

        intersection = words1 & words2
        union = words1 | words2

        return len(intersection) / len(union)

    def _analyze_with_heuristics(
        self, pattern: FailurePattern
    ) -> RootCauseAnalysis:
        """Perform analysis using heuristics only (no LLM)."""
        category = self._match_pattern_category(pattern)

        if category and category in self.ROOT_CAUSE_PATTERNS:
            config = self.ROOT_CAUSE_PATTERNS[category]
            whys = self.WHYS_TEMPLATES.get(category, [
                f"The operation failed: {pattern.description}",
                "This failure occurred due to a limitation in handling this scenario",
                "The limitation exists because this case wasn't anticipated",
                "It wasn't anticipated because similar patterns hadn't been observed",
                "Similar patterns are now observed, enabling targeted improvement",
            ])

            root_cause = config["root_cause"]
            capability_gap = config["capability_gap"]
            counterfactual = config["counterfactual"]
            confidence = 0.6  # Moderate confidence for heuristics
        else:
            # Generic fallback
            whys = [
                f"The operation failed: {pattern.description}",
                f"Failure type: {pattern.error_type}",
                "Root cause requires further investigation",
                "Pattern matches no known category",
                "Manual analysis recommended",
            ]
            root_cause = f"Unknown root cause for {pattern.error_type} failures"
            capability_gap = "Requires manual investigation"
            counterfactual = "Unknown - manual analysis needed"
            confidence = 0.3

        similar_patterns = self._find_similar_resolved_patterns(pattern)

        return RootCauseAnalysis(
            pattern_id=pattern.pattern_id,
            whys=whys,
            root_cause=root_cause,
            capability_gap=capability_gap,
            counterfactual=counterfactual,
            confidence=confidence,
            similar_patterns=similar_patterns,
            analysis_method="heuristic",
            timestamp=datetime.now().isoformat(),
        )

    def _analyze_with_llm(self, pattern: FailurePattern) -> RootCauseAnalysis:
        """Perform analysis using LLM."""
        # Prepare the prompt for 5-Whys analysis
        prompt = self._build_llm_prompt(pattern)

        try:
            # Call Claude CLI for analysis
            result = subprocess.run(
                ["claude", "-p", prompt, "--output-format", "json"],
                capture_output=True,
                text=True,
                timeout=120,
                cwd=str(self.project_root),
            )

            if result.returncode == 0:
                # Parse LLM response
                response = json.loads(result.stdout)
                return self._parse_llm_response(pattern, response)
        except (subprocess.TimeoutExpired, subprocess.SubprocessError, json.JSONDecodeError) as e:
            # Log error and fall back to heuristics
            print(f"LLM analysis failed: {e}", file=sys.stderr)

        # Fallback to heuristics if LLM fails
        heuristic_result = self._analyze_with_heuristics(pattern)
        heuristic_result.analysis_method = "heuristic_fallback"
        return heuristic_result

    def _build_llm_prompt(self, pattern: FailurePattern) -> str:
        """Build the prompt for LLM analysis."""
        examples_json = json.dumps(pattern.example_failures[:2], indent=2)

        return f"""Analyze this failure pattern using the 5-Whys root cause analysis method.

FAILURE PATTERN:
- Pattern ID: {pattern.pattern_id}
- Error Type: {pattern.error_type}
- Description: {pattern.description}
- Normalized Message: {pattern.normalized_message}
- Occurrences: {pattern.occurrences}
- Affected Stories: {', '.join(pattern.affected_stories)}
- Context Indicators: {', '.join(pattern.context_indicators)}

EXAMPLE FAILURES:
{examples_json}

Please provide a structured analysis in this exact JSON format:
{{
  "whys": [
    "Why 1: The immediate cause of the failure",
    "Why 2: Why that cause occurred",
    "Why 3: The deeper reason",
    "Why 4: The underlying systemic issue",
    "Why 5: The root cause"
  ],
  "root_cause": "A concise statement of the fundamental root cause",
  "capability_gap": "The specific capability that is missing or inadequate",
  "counterfactual": "The capability or feature that would have prevented this failure",
  "confidence": 0.8
}}

Respond with ONLY the JSON, no additional text."""

    def _parse_llm_response(
        self, pattern: FailurePattern, response: dict
    ) -> RootCauseAnalysis:
        """Parse LLM response into RootCauseAnalysis."""
        # Handle both direct JSON and text response containing JSON
        if isinstance(response, dict) and "result" in response:
            # Extract JSON from result text if needed
            result_text = response.get("result", "")
            try:
                # Try to find JSON in the response
                json_match = re.search(r'\{[^{}]*"whys"[^{}]*\}', result_text, re.DOTALL)
                if json_match:
                    data = json.loads(json_match.group())
                else:
                    data = json.loads(result_text)
            except json.JSONDecodeError:
                # Fall back to heuristics if parsing fails
                return self._analyze_with_heuristics(pattern)
        else:
            data = response

        whys = data.get("whys", [])
        # Ensure we have exactly 5 whys
        while len(whys) < 5:
            whys.append("Further investigation needed")
        whys = whys[:5]

        similar_patterns = self._find_similar_resolved_patterns(pattern)

        return RootCauseAnalysis(
            pattern_id=pattern.pattern_id,
            whys=whys,
            root_cause=data.get("root_cause", "Unknown"),
            capability_gap=data.get("capability_gap", "Unknown"),
            counterfactual=data.get("counterfactual", "Unknown"),
            confidence=float(data.get("confidence", 0.7)),
            similar_patterns=similar_patterns,
            analysis_method="llm",
            timestamp=datetime.now().isoformat(),
        )

    def analyze_root_cause(
        self, pattern: FailurePattern, use_cache: bool = True
    ) -> RootCauseAnalysis:
        """
        Perform root cause analysis on a failure pattern.

        Args:
            pattern: The FailurePattern to analyze
            use_cache: Whether to use cached results if available

        Returns:
            RootCauseAnalysis with 5-Whys, root cause, and capability gap
        """
        # Check cache first
        if use_cache:
            cached = self._get_cached_analysis(pattern.pattern_id)
            if cached:
                return cached

        # Perform analysis
        if self.use_llm:
            analysis = self._analyze_with_llm(pattern)
        else:
            analysis = self._analyze_with_heuristics(pattern)

        # Cache the result
        self._cache_analysis(analysis)

        return analysis

    def analyze_by_pattern_id(
        self, pattern_id: str, use_cache: bool = True
    ) -> RootCauseAnalysis | None:
        """
        Analyze a pattern by its ID.

        Args:
            pattern_id: The pattern ID to analyze
            use_cache: Whether to use cached results

        Returns:
            RootCauseAnalysis or None if pattern not found
        """
        self.clusterer.cluster_failures()
        pattern = self.clusterer.get_pattern_by_id(pattern_id)

        if not pattern:
            return None

        return self.analyze_root_cause(pattern, use_cache=use_cache)

    def batch_analyze(
        self, min_occurrences: int = 3
    ) -> list[RootCauseAnalysis]:
        """
        Analyze all patterns meeting minimum occurrence threshold.

        Args:
            min_occurrences: Minimum occurrences for pattern inclusion

        Returns:
            List of RootCauseAnalysis results
        """
        self.clusterer.min_occurrences = min_occurrences
        patterns = self.clusterer.cluster_failures()

        results = []
        for pattern in patterns:
            analysis = self.analyze_root_cause(pattern)
            results.append(analysis)

        return results

    def mark_pattern_resolved(
        self, pattern_id: str, resolution: str
    ) -> None:
        """
        Mark a pattern as resolved for future reference.

        Args:
            pattern_id: The pattern ID that was resolved
            resolution: Description of how it was resolved
        """
        pattern = self.clusterer.get_pattern_by_id(pattern_id)
        if not pattern:
            return

        self._resolved_patterns.append({
            "pattern_id": pattern_id,
            "normalized_message": pattern.normalized_message,
            "resolution": resolution,
            "resolved_date": datetime.now().isoformat(),
        })

        self._save_resolved_patterns()

    def get_cache_stats(self) -> dict[str, Any]:
        """Get statistics about the analysis cache."""
        cache_files = list(self.cache_dir.glob("*.json"))
        # Exclude resolved_patterns.json from count
        analysis_files = [f for f in cache_files if f.name != "resolved_patterns.json"]
        total_size = sum(f.stat().st_size for f in cache_files if f.is_file())

        return {
            "cached_analyses": len(analysis_files),
            "resolved_patterns": len(self._resolved_patterns),
            "cache_size_bytes": total_size,
            "cache_dir": str(self.cache_dir),
        }

    def clear_cache(self) -> int:
        """Clear all cached analyses. Returns count of cleared items."""
        count = 0
        for cache_file in self.cache_dir.glob("*.json"):
            if cache_file.name != "resolved_patterns.json":
                cache_file.unlink()
                count += 1
        return count


# ============================================================================
# CLI Interface
# ============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Root Cause Analysis Engine for claude-loop",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python lib/root-cause-analyzer.py analyze PAT-12345678
    python lib/root-cause-analyzer.py analyze PAT-12345678 --no-llm
    python lib/root-cause-analyzer.py analyze PAT-12345678 --no-cache
    python lib/root-cause-analyzer.py list
    python lib/root-cause-analyzer.py batch-analyze
    python lib/root-cause-analyzer.py cache-stats
    python lib/root-cause-analyzer.py clear-cache
    python lib/root-cause-analyzer.py mark-resolved PAT-12345678 "Fixed by adding handler"
        """,
    )

    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # analyze command
    analyze_parser = subparsers.add_parser(
        "analyze", help="Analyze a specific pattern"
    )
    analyze_parser.add_argument(
        "pattern_id",
        type=str,
        help="Pattern ID to analyze (e.g., PAT-12345678)",
    )
    analyze_parser.add_argument(
        "--no-llm", action="store_true",
        help="Use heuristics only (no LLM calls)",
    )
    analyze_parser.add_argument(
        "--no-cache", action="store_true",
        help="Ignore cached results and force fresh analysis",
    )
    analyze_parser.add_argument(
        "--json", action="store_true",
        help="Output as JSON",
    )

    # list command
    list_parser = subparsers.add_parser(
        "list", help="List available patterns for analysis"
    )
    list_parser.add_argument(
        "--min-occurrences",
        type=int,
        default=3,
        help="Minimum occurrences to include (default: 3)",
    )
    list_parser.add_argument(
        "--json", action="store_true",
        help="Output as JSON",
    )

    # batch-analyze command
    batch_parser = subparsers.add_parser(
        "batch-analyze", help="Analyze all patterns"
    )
    batch_parser.add_argument(
        "--min-occurrences",
        type=int,
        default=3,
        help="Minimum occurrences to include (default: 3)",
    )
    batch_parser.add_argument(
        "--no-llm", action="store_true",
        help="Use heuristics only",
    )
    batch_parser.add_argument(
        "--json", action="store_true",
        help="Output as JSON",
    )

    # cache-stats command
    cache_parser = subparsers.add_parser(
        "cache-stats", help="Show cache statistics"
    )
    cache_parser.add_argument(
        "--json", action="store_true",
        help="Output as JSON",
    )

    # clear-cache command
    subparsers.add_parser(
        "clear-cache", help="Clear the analysis cache"
    )

    # mark-resolved command
    resolved_parser = subparsers.add_parser(
        "mark-resolved", help="Mark a pattern as resolved"
    )
    resolved_parser.add_argument(
        "pattern_id",
        type=str,
        help="Pattern ID to mark as resolved",
    )
    resolved_parser.add_argument(
        "resolution",
        type=str,
        help="Description of how the pattern was resolved",
    )

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    # Determine project root
    script_dir = Path(__file__).parent
    project_root = script_dir.parent

    # Initialize analyzer
    use_llm = not getattr(args, 'no_llm', False)
    analyzer = RootCauseAnalyzer(project_root=project_root, use_llm=use_llm)

    if args.command == "analyze":
        use_cache = not args.no_cache
        analysis = analyzer.analyze_by_pattern_id(
            args.pattern_id, use_cache=use_cache
        )

        if not analysis:
            print(f"Error: Pattern '{args.pattern_id}' not found")
            print("\nUse 'root-cause-analyzer.py list' to see available patterns")
            sys.exit(1)

        if args.json:
            print(json.dumps(analysis.to_dict(), indent=2))
        else:
            print(f"=== Root Cause Analysis: {analysis.pattern_id} ===\n")
            print(f"Analysis Method: {analysis.analysis_method}")
            print(f"Confidence: {analysis.confidence:.0%}")
            print(f"Analyzed: {analysis.timestamp}")
            print()
            print("5-Whys Decomposition:")
            for i, why in enumerate(analysis.whys, 1):
                print(f"  {i}. {why}")
            print()
            print(f"Root Cause: {analysis.root_cause}")
            print()
            print(f"Capability Gap: {analysis.capability_gap}")
            print()
            print(f"Counterfactual: {analysis.counterfactual}")

            if analysis.similar_patterns:
                print()
                print("Similar Resolved Patterns:")
                for sp in analysis.similar_patterns:
                    print(f"  - {sp['pattern_id']}: {sp.get('resolution', 'N/A')}")

    elif args.command == "list":
        analyzer.clusterer.min_occurrences = args.min_occurrences
        patterns = analyzer.clusterer.cluster_failures()

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
                print(f"\nNote: Patterns require at least {args.min_occurrences} occurrences.")
                return

            print(f"Available patterns for analysis ({len(patterns)}):\n")
            print(f"{'Pattern ID':<15} {'Count':>6}  {'Type':<12}  Description")
            print("-" * 80)
            for p in patterns:
                desc = p.description[:40] + "..." if len(p.description) > 40 else p.description
                print(f"{p.pattern_id:<15} {p.occurrences:>6}  {p.error_type:<12}  {desc}")

    elif args.command == "batch-analyze":
        results = analyzer.batch_analyze(min_occurrences=args.min_occurrences)

        if args.json:
            print(json.dumps([r.to_dict() for r in results], indent=2))
        else:
            if not results:
                print("No patterns to analyze.")
                return

            print(f"=== Batch Root Cause Analysis ===\n")
            print(f"Analyzed {len(results)} patterns:\n")

            for analysis in results:
                print(f"[{analysis.pattern_id}] ({analysis.confidence:.0%} confidence)")
                print(f"  Root Cause: {analysis.root_cause}")
                print(f"  Gap: {analysis.capability_gap}")
                print()

    elif args.command == "cache-stats":
        stats = analyzer.get_cache_stats()

        if args.json:
            print(json.dumps(stats, indent=2))
        else:
            print("=== Analysis Cache Statistics ===\n")
            print(f"Cached analyses: {stats['cached_analyses']}")
            print(f"Resolved patterns: {stats['resolved_patterns']}")
            print(f"Cache size: {stats['cache_size_bytes']:,} bytes")
            print(f"Cache directory: {stats['cache_dir']}")

    elif args.command == "clear-cache":
        count = analyzer.clear_cache()
        print(f"Cleared {count} cached analyses.")

    elif args.command == "mark-resolved":
        analyzer.mark_pattern_resolved(args.pattern_id, args.resolution)
        print(f"Marked pattern {args.pattern_id} as resolved.")


if __name__ == "__main__":
    main()
