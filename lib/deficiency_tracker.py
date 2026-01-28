#!/usr/bin/env python3
"""
Deficiency Learning System for Claude-Loop

Automatically learns from failures and deficiencies to avoid repeating mistakes.
Tracks patterns, generates improvement suggestions, and supports remediation tracking.

Usage:
    from lib.deficiency_tracker import DeficiencyTracker, DeficiencyType

    tracker = DeficiencyTracker()

    # Record a deficiency
    tracker.record_deficiency(
        deficiency_type=DeficiencyType.COORDINATOR_BUG,
        description="Unbound variable in deregister_prd",
        context={"file": "lib/prd-coordinator.sh", "line": 378},
        solution="Fixed variable name from $target to $target_list"
    )

    # Detect patterns
    patterns = tracker.detect_patterns()

    # Get improvement suggestions
    suggestions = tracker.get_suggestions()
"""

import json
import hashlib
from dataclasses import dataclass, asdict
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Optional, Dict, Any, List
from collections import defaultdict


class DeficiencyType(Enum):
    """Categories of deficiencies"""
    COORDINATOR_BUG = "coordinator_bug"
    SILENT_FAILURE = "silent_failure"
    RESOURCE_ISSUE = "resource_issue"
    API_FAILURE = "api_failure"
    LOGIC_ERROR = "logic_error"
    QUALITY_GATE_BUG = "quality_gate_bug"
    CONFIGURATION_ERROR = "configuration_error"
    MISSING_FEATURE = "missing_feature"


@dataclass
class Deficiency:
    """A tracked deficiency with learning metadata"""
    id: str  # Hash of type + description
    deficiency_type: str
    description: str
    context: Dict[str, Any]
    solution: Optional[str]
    first_seen: str
    last_seen: str
    frequency: int
    remediation_status: str  # "open", "in_progress", "fixed"
    remediation_commit: Optional[str]
    github_issue: Optional[str]
    improvement_suggestions: List[str]


class DeficiencyTracker:
    """Tracks deficiencies and learns from failures"""

    RECURRING_THRESHOLD = 3  # Same deficiency 3+ times = pattern

    def __init__(self, deficiencies_file: Optional[Path] = None):
        """
        Initialize deficiency tracker

        Args:
            deficiencies_file: Path to deficiencies.jsonl (default: .claude-loop/deficiencies.jsonl)
        """
        if deficiencies_file is None:
            claude_loop_dir = Path.home() / ".claude-loop"
            claude_loop_dir.mkdir(exist_ok=True)
            deficiencies_file = claude_loop_dir / "deficiencies.jsonl"

        self.deficiencies_file = Path(deficiencies_file)
        self.deficiencies_file.parent.mkdir(parents=True, exist_ok=True)

        # In-memory cache
        self._deficiencies: Dict[str, Deficiency] = {}
        self._load_deficiencies()

    def record_deficiency(
        self,
        deficiency_type: DeficiencyType,
        description: str,
        context: Optional[Dict[str, Any]] = None,
        solution: Optional[str] = None
    ) -> str:
        """
        Record a deficiency

        Args:
            deficiency_type: Category of deficiency
            description: Human-readable description
            context: Additional context (file, line, PRD, etc)
            solution: Solution if known

        Returns:
            Deficiency ID
        """
        # Generate stable ID from type + description
        deficiency_id = self._generate_id(deficiency_type, description)

        now = datetime.utcnow().isoformat() + "Z"

        if deficiency_id in self._deficiencies:
            # Update existing
            deficiency = self._deficiencies[deficiency_id]
            deficiency.last_seen = now
            deficiency.frequency += 1

            # Merge context
            deficiency.context.update(context or {})

            # Update solution if provided
            if solution:
                deficiency.solution = solution

            # Generate suggestions if recurring
            if deficiency.frequency >= self.RECURRING_THRESHOLD:
                deficiency.improvement_suggestions = self._generate_suggestions(deficiency)
        else:
            # Create new
            deficiency = Deficiency(
                id=deficiency_id,
                deficiency_type=deficiency_type.value,
                description=description,
                context=context or {},
                solution=solution,
                first_seen=now,
                last_seen=now,
                frequency=1,
                remediation_status="open",
                remediation_commit=None,
                github_issue=None,
                improvement_suggestions=[]
            )
            self._deficiencies[deficiency_id] = deficiency

        # Persist
        self._save_deficiency(deficiency)

        return deficiency_id

    def mark_fixed(
        self,
        deficiency_id: str,
        commit_hash: Optional[str] = None,
        github_issue: Optional[str] = None
    ) -> None:
        """
        Mark a deficiency as fixed

        Args:
            deficiency_id: Deficiency ID
            commit_hash: Git commit that fixed it
            github_issue: GitHub issue reference
        """
        if deficiency_id not in self._deficiencies:
            raise ValueError(f"Deficiency {deficiency_id} not found")

        deficiency = self._deficiencies[deficiency_id]
        deficiency.remediation_status = "fixed"
        deficiency.remediation_commit = commit_hash
        if github_issue:
            deficiency.github_issue = github_issue

        self._save_deficiency(deficiency)

    def mark_in_progress(
        self,
        deficiency_id: str,
        github_issue: Optional[str] = None
    ) -> None:
        """Mark a deficiency as being worked on"""
        if deficiency_id not in self._deficiencies:
            raise ValueError(f"Deficiency {deficiency_id} not found")

        deficiency = self._deficiencies[deficiency_id]
        deficiency.remediation_status = "in_progress"
        if github_issue:
            deficiency.github_issue = github_issue

        self._save_deficiency(deficiency)

    def detect_patterns(self) -> List[Dict[str, Any]]:
        """
        Detect recurring deficiency patterns

        Returns:
            List of detected patterns with frequencies
        """
        patterns = []

        for deficiency in self._deficiencies.values():
            if deficiency.frequency >= self.RECURRING_THRESHOLD:
                patterns.append({
                    'id': deficiency.id,
                    'type': deficiency.deficiency_type,
                    'description': deficiency.description,
                    'frequency': deficiency.frequency,
                    'first_seen': deficiency.first_seen,
                    'last_seen': deficiency.last_seen,
                    'status': deficiency.remediation_status,
                    'suggestions': deficiency.improvement_suggestions
                })

        # Sort by frequency (most recurring first)
        return sorted(patterns, key=lambda p: p['frequency'], reverse=True)

    def get_suggestions(
        self,
        deficiency_type: Optional[DeficiencyType] = None,
        status: str = "open"
    ) -> List[Dict[str, Any]]:
        """
        Get improvement suggestions

        Args:
            deficiency_type: Filter by type
            status: Filter by remediation status ("open", "in_progress", "fixed")

        Returns:
            List of suggestions with priorities
        """
        suggestions = []

        for deficiency in self._deficiencies.values():
            # Filter
            if deficiency_type and deficiency.deficiency_type != deficiency_type.value:
                continue
            if deficiency.remediation_status != status:
                continue
            if not deficiency.improvement_suggestions:
                continue

            suggestions.append({
                'id': deficiency.id,
                'type': deficiency.deficiency_type,
                'description': deficiency.description,
                'frequency': deficiency.frequency,
                'priority': self._calculate_priority(deficiency),
                'suggestions': deficiency.improvement_suggestions,
                'context': deficiency.context
            })

        # Sort by priority (highest first)
        return sorted(suggestions, key=lambda s: s['priority'], reverse=True)

    def get_deficiency_stats(self) -> Dict[str, Any]:
        """
        Get deficiency statistics

        Returns:
            Statistics dictionary
        """
        by_type = defaultdict(int)
        by_status = defaultdict(int)
        recurring = 0

        for deficiency in self._deficiencies.values():
            by_type[deficiency.deficiency_type] += 1
            by_status[deficiency.remediation_status] += 1
            if deficiency.frequency >= self.RECURRING_THRESHOLD:
                recurring += 1

        return {
            'total': len(self._deficiencies),
            'recurring': recurring,
            'by_type': dict(by_type),
            'by_status': dict(by_status),
            'patterns_detected': self.detect_patterns()
        }

    def export_for_experience_store(self, deficiency_id: str) -> Dict[str, Any]:
        """
        Export deficiency for experience store

        Args:
            deficiency_id: Deficiency ID

        Returns:
            Dictionary suitable for experience store
        """
        if deficiency_id not in self._deficiencies:
            raise ValueError(f"Deficiency {deficiency_id} not found")

        deficiency = self._deficiencies[deficiency_id]

        return {
            'problem': deficiency.description,
            'solution': deficiency.solution or "No solution yet",
            'context': deficiency.context,
            'frequency': deficiency.frequency,
            'deficiency_type': deficiency.deficiency_type,
            'improvement_suggestions': deficiency.improvement_suggestions
        }

    def _generate_id(self, deficiency_type: DeficiencyType, description: str) -> str:
        """Generate stable ID from type + description"""
        content = f"{deficiency_type.value}:{description}"
        return hashlib.sha256(content.encode()).hexdigest()[:16]

    def _generate_suggestions(self, deficiency: Deficiency) -> List[str]:
        """Generate improvement suggestions for a deficiency"""
        suggestions = []

        dtype = deficiency.deficiency_type
        freq = deficiency.frequency

        # Type-specific suggestions
        if dtype == DeficiencyType.COORDINATOR_BUG.value:
            suggestions.append("Add comprehensive unit tests for coordinator functions")
            suggestions.append("Implement stricter variable validation with set -u")
            suggestions.append("Add integration tests that exercise coordinator edge cases")

        elif dtype == DeficiencyType.SILENT_FAILURE.value:
            suggestions.append("Implement comprehensive failure logging (lib/failure_logger.py)")
            suggestions.append("Add worker heartbeat monitoring")
            suggestions.append("Improve process exit code handling and reporting")

        elif dtype == DeficiencyType.RESOURCE_ISSUE.value:
            suggestions.append("Add resource usage monitoring and alerting")
            suggestions.append("Implement worker resource limits (cgroups/ulimit)")
            suggestions.append("Add automatic cleanup of stale worker processes")

        elif dtype == DeficiencyType.API_FAILURE.value:
            suggestions.append("Implement model failover with exponential backoff")
            suggestions.append("Add API key rotation for rate limit handling")
            suggestions.append("Cache API responses where possible")

        elif dtype == DeficiencyType.LOGIC_ERROR.value:
            suggestions.append("Add more comprehensive test coverage")
            suggestions.append("Implement stricter type checking")
            suggestions.append("Add pre-commit hooks for validation")

        # Frequency-based suggestions
        if freq >= 5:
            suggestions.append(f"CRITICAL: This deficiency occurred {freq} times - prioritize fixing")
            suggestions.append("Consider adding automated prevention mechanisms")

        return suggestions

    def _calculate_priority(self, deficiency: Deficiency) -> int:
        """Calculate priority score (0-100) for a deficiency"""
        score = 0

        # Frequency weight (0-40 points)
        score += min(40, deficiency.frequency * 5)

        # Type weight (0-30 points)
        high_priority_types = [
            DeficiencyType.COORDINATOR_BUG.value,
            DeficiencyType.SILENT_FAILURE.value,
            DeficiencyType.LOGIC_ERROR.value
        ]
        if deficiency.deficiency_type in high_priority_types:
            score += 30
        else:
            score += 15

        # Recency weight (0-30 points)
        # More recent = higher priority
        try:
            last_seen = datetime.fromisoformat(deficiency.last_seen.replace('Z', '+00:00'))
            days_ago = (datetime.utcnow() - last_seen.replace(tzinfo=None)).days
            score += max(0, 30 - days_ago)
        except Exception:
            score += 15

        return min(100, score)

    def _load_deficiencies(self) -> None:
        """Load deficiencies from file"""
        if not self.deficiencies_file.exists():
            return

        with open(self.deficiencies_file, 'r') as f:
            for line in f:
                if line.strip():
                    data = json.loads(line)
                    deficiency = Deficiency(**data)
                    self._deficiencies[deficiency.id] = deficiency

    def _save_deficiency(self, deficiency: Deficiency) -> None:
        """Save deficiency to file"""
        # Rewrite entire file (not ideal for huge files, but fine for deficiencies)
        with open(self.deficiencies_file, 'w') as f:
            for d in self._deficiencies.values():
                f.write(json.dumps(asdict(d)) + '\n')


if __name__ == '__main__':
    # CLI interface
    import argparse

    parser = argparse.ArgumentParser(description='View and manage deficiencies')
    parser.add_argument('--stats', action='store_true', help='Show deficiency statistics')
    parser.add_argument('--patterns', action='store_true', help='Show recurring patterns')
    parser.add_argument('--suggestions', action='store_true', help='Show improvement suggestions')
    parser.add_argument('--type', help='Filter by deficiency type')

    args = parser.parse_args()

    tracker = DeficiencyTracker()

    if args.stats:
        stats = tracker.get_deficiency_stats()
        print(json.dumps(stats, indent=2))
    elif args.patterns:
        patterns = tracker.detect_patterns()
        print(json.dumps(patterns, indent=2))
    elif args.suggestions:
        dtype = DeficiencyType(args.type) if args.type else None
        suggestions = tracker.get_suggestions(deficiency_type=dtype)
        print(json.dumps(suggestions, indent=2))
    else:
        print("Use --stats, --patterns, or --suggestions")
