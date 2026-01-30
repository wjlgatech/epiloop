#!/usr/bin/env python3
"""
gap-generalizer.py - Capability Gap Generalizer for claude-loop

Generalizes specific failure root causes to broader capability categories,
enabling targeted improvements that address multiple failure patterns.

Features:
- Maps root causes to capability taxonomy
- Identifies task families affected by each gap
- Calculates priority based on frequency, impact, and feasibility
- Maintains a registry of known capability gaps
- Estimates future failure probability without improvement

Usage:
    python lib/gap-generalizer.py generalize <root_cause_id>
    python lib/gap-generalizer.py list
    python lib/gap-generalizer.py show <gap_id>
    python lib/gap-generalizer.py registry
    python lib/gap-generalizer.py prioritize
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from dataclasses import dataclass, field
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


_root_cause_analyzer = _import_module("root_cause_analyzer", "root-cause-analyzer.py")
RootCauseAnalysis = _root_cause_analyzer.RootCauseAnalysis
RootCauseAnalyzer = _root_cause_analyzer.RootCauseAnalyzer


# ============================================================================
# Capability Taxonomy
# ============================================================================

class CapabilityCategory:
    """Enumeration of capability categories."""

    UI_INTERACTION = "UI_INTERACTION"
    FILE_HANDLING = "FILE_HANDLING"
    NETWORK = "NETWORK"
    PARSING = "PARSING"
    TOOL_INTEGRATION = "TOOL_INTEGRATION"
    STATE_MANAGEMENT = "STATE_MANAGEMENT"
    PERMISSION_HANDLING = "PERMISSION_HANDLING"
    API_INTERACTION = "API_INTERACTION"
    ERROR_RECOVERY = "ERROR_RECOVERY"
    VALIDATION = "VALIDATION"
    UNKNOWN = "UNKNOWN"

    @classmethod
    def all_categories(cls) -> list[str]:
        """Return all capability categories."""
        return [
            cls.UI_INTERACTION,
            cls.FILE_HANDLING,
            cls.NETWORK,
            cls.PARSING,
            cls.TOOL_INTEGRATION,
            cls.STATE_MANAGEMENT,
            cls.PERMISSION_HANDLING,
            cls.API_INTERACTION,
            cls.ERROR_RECOVERY,
            cls.VALIDATION,
            cls.UNKNOWN,
        ]


# Mapping from keywords to capability categories
CAPABILITY_KEYWORDS: dict[str, list[str]] = {
    CapabilityCategory.UI_INTERACTION: [
        "ui", "click", "element", "visual", "screenshot", "button", "window",
        "dialog", "form", "input", "menu", "interface", "gui", "display",
        "automation", "mouse", "keyboard", "focus",
    ],
    CapabilityCategory.FILE_HANDLING: [
        "file", "directory", "path", "read", "write", "create", "delete",
        "folder", "filesystem", "permission", "exists", "open", "close",
        "copy", "move", "rename", "access",
    ],
    CapabilityCategory.NETWORK: [
        "network", "connection", "socket", "http", "https", "dns", "timeout",
        "ssl", "tls", "tcp", "udp", "host", "port", "url", "request",
        "response", "download", "upload", "latency",
    ],
    CapabilityCategory.PARSING: [
        "parse", "json", "xml", "yaml", "syntax", "format", "decode",
        "encode", "serialize", "deserialize", "malformed", "invalid",
        "schema", "structure", "token",
    ],
    CapabilityCategory.TOOL_INTEGRATION: [
        "tool", "handler", "command", "execute", "shell", "subprocess",
        "cli", "invoke", "call", "mcp", "extension", "plugin", "integration",
    ],
    CapabilityCategory.STATE_MANAGEMENT: [
        "state", "session", "context", "variable", "memory", "cache",
        "initialize", "undefined", "null", "missing", "persist", "storage",
        "track", "maintain",
    ],
    CapabilityCategory.PERMISSION_HANDLING: [
        "permission", "denied", "access", "forbidden", "unauthorized",
        "privilege", "credential", "auth", "security", "sandbox", "restrict",
    ],
    CapabilityCategory.API_INTERACTION: [
        "api", "endpoint", "rest", "graphql", "rpc", "service", "external",
        "integration", "client", "server", "request", "response", "webhook",
    ],
    CapabilityCategory.ERROR_RECOVERY: [
        "retry", "fallback", "recover", "resilience", "handle", "catch",
        "exception", "error", "failure", "graceful", "rollback", "undo",
    ],
    CapabilityCategory.VALIDATION: [
        "validate", "check", "verify", "assert", "test", "constraint",
        "requirement", "precondition", "postcondition", "invariant",
    ],
}


# Task families affected by each capability category
TASK_FAMILIES: dict[str, list[str]] = {
    CapabilityCategory.UI_INTERACTION: [
        "GUI automation",
        "Desktop application testing",
        "Visual verification",
        "Form filling",
        "User simulation",
        "Screenshot-based navigation",
    ],
    CapabilityCategory.FILE_HANDLING: [
        "File processing",
        "Configuration management",
        "Log analysis",
        "Data import/export",
        "Backup operations",
        "Directory management",
    ],
    CapabilityCategory.NETWORK: [
        "Web scraping",
        "API consumption",
        "Remote service integration",
        "File downloads",
        "Health checks",
        "External service monitoring",
    ],
    CapabilityCategory.PARSING: [
        "Data transformation",
        "Configuration parsing",
        "Log parsing",
        "Code analysis",
        "Document processing",
        "Format conversion",
    ],
    CapabilityCategory.TOOL_INTEGRATION: [
        "External tool invocation",
        "CI/CD pipelines",
        "Build automation",
        "Script execution",
        "Development workflows",
        "System administration",
    ],
    CapabilityCategory.STATE_MANAGEMENT: [
        "Multi-step workflows",
        "Session-based operations",
        "Stateful interactions",
        "Transaction management",
        "Context preservation",
        "Progress tracking",
    ],
    CapabilityCategory.PERMISSION_HANDLING: [
        "System administration",
        "Security operations",
        "Resource access",
        "User management",
        "Credential handling",
        "Privilege escalation",
    ],
    CapabilityCategory.API_INTERACTION: [
        "Third-party integrations",
        "Microservice communication",
        "External data fetching",
        "Webhook handling",
        "Service orchestration",
        "API testing",
    ],
    CapabilityCategory.ERROR_RECOVERY: [
        "Fault-tolerant operations",
        "Long-running tasks",
        "Retry-intensive workflows",
        "Error handling automation",
        "Recovery procedures",
        "Idempotent operations",
    ],
    CapabilityCategory.VALIDATION: [
        "Input validation",
        "Data quality checks",
        "Test execution",
        "Contract verification",
        "Compliance checks",
        "Schema validation",
    ],
}


# Feasibility scores for each category (0-1, higher = easier to implement)
FEASIBILITY_SCORES: dict[str, float] = {
    CapabilityCategory.UI_INTERACTION: 0.3,  # Challenging: multi-platform, visual
    CapabilityCategory.FILE_HANDLING: 0.9,   # Easy: well-defined APIs
    CapabilityCategory.NETWORK: 0.7,         # Medium: external dependencies
    CapabilityCategory.PARSING: 0.8,         # Fairly easy: libraries available
    CapabilityCategory.TOOL_INTEGRATION: 0.7, # Medium: depends on tool
    CapabilityCategory.STATE_MANAGEMENT: 0.6, # Medium: architectural changes
    CapabilityCategory.PERMISSION_HANDLING: 0.5, # Medium-hard: security concerns
    CapabilityCategory.API_INTERACTION: 0.7,  # Medium: external dependencies
    CapabilityCategory.ERROR_RECOVERY: 0.8,   # Fairly easy: pattern-based
    CapabilityCategory.VALIDATION: 0.9,       # Easy: well-understood patterns
    CapabilityCategory.UNKNOWN: 0.4,          # Hard: requires investigation
}


# ============================================================================
# Data Classes
# ============================================================================

@dataclass
class GeneralizedGap:
    """A generalized capability gap derived from root cause analysis."""

    gap_id: str
    category: str  # One of CapabilityCategory values
    description: str
    affected_task_types: list[str]  # Task families that would benefit
    priority_score: float  # Combined priority (0-100)

    # Component scores
    frequency_score: float  # Based on occurrence count (0-1)
    impact_score: float     # Based on affected stories (0-1)
    feasibility_score: float # Based on category (0-1)

    # Analysis details
    root_cause_ids: list[str] = field(default_factory=list)  # Source RCA IDs
    pattern_ids: list[str] = field(default_factory=list)     # Source pattern IDs
    affected_stories: list[str] = field(default_factory=list)

    # Projections
    estimated_future_failures: float = 0.0  # Expected failures without fix
    improvement_benefit: str = ""  # Description of improvement benefit

    # Metadata
    created_at: str = ""
    updated_at: str = ""
    status: str = "active"  # active, resolved, deferred

    def to_dict(self) -> dict[str, Any]:
        return {
            "gap_id": self.gap_id,
            "category": self.category,
            "description": self.description,
            "affected_task_types": self.affected_task_types,
            "priority_score": round(self.priority_score, 2),
            "frequency_score": round(self.frequency_score, 3),
            "impact_score": round(self.impact_score, 3),
            "feasibility_score": round(self.feasibility_score, 3),
            "root_cause_ids": self.root_cause_ids,
            "pattern_ids": self.pattern_ids,
            "affected_stories": self.affected_stories,
            "estimated_future_failures": round(self.estimated_future_failures, 1),
            "improvement_benefit": self.improvement_benefit,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "status": self.status,
        }

    @classmethod
    def from_dict(cls, data: dict) -> GeneralizedGap:
        return cls(
            gap_id=data.get("gap_id", ""),
            category=data.get("category", CapabilityCategory.UNKNOWN),
            description=data.get("description", ""),
            affected_task_types=data.get("affected_task_types", []),
            priority_score=data.get("priority_score", 0.0),
            frequency_score=data.get("frequency_score", 0.0),
            impact_score=data.get("impact_score", 0.0),
            feasibility_score=data.get("feasibility_score", 0.0),
            root_cause_ids=data.get("root_cause_ids", []),
            pattern_ids=data.get("pattern_ids", []),
            affected_stories=data.get("affected_stories", []),
            estimated_future_failures=data.get("estimated_future_failures", 0.0),
            improvement_benefit=data.get("improvement_benefit", ""),
            created_at=data.get("created_at", ""),
            updated_at=data.get("updated_at", ""),
            status=data.get("status", "active"),
        )


# ============================================================================
# Gap Generalizer
# ============================================================================

class GapGeneralizer:
    """
    Generalizes specific failure root causes to broader capability categories.

    The generalization process:
    1. Extract keywords from root cause analysis
    2. Map to capability taxonomy based on keyword matching
    3. Identify task families that would benefit from fixing the gap
    4. Calculate priority: frequency * impact * feasibility
    5. Estimate future failure probability
    6. Store in capability gaps registry
    """

    def __init__(
        self,
        project_root: Path | None = None,
        registry_path: Path | None = None,
    ):
        """
        Initialize the generalizer.

        Args:
            project_root: Path to project root
            registry_path: Path to capability_gaps.json registry
        """
        self.project_root = project_root or Path(__file__).parent.parent
        self.claude_loop_dir = self.project_root / ".claude-loop"
        self.registry_path = registry_path or self.claude_loop_dir / "capability_gaps.json"

        # Ensure .claude-loop directory exists
        self.claude_loop_dir.mkdir(parents=True, exist_ok=True)

        # Initialize root cause analyzer for loading analyses
        self.analyzer = RootCauseAnalyzer(
            project_root=self.project_root,
            use_llm=False,  # Only need to read cached analyses
        )

        # Load existing registry
        self._registry: dict[str, GeneralizedGap] = self._load_registry()

    def _load_registry(self) -> dict[str, GeneralizedGap]:
        """Load the capability gaps registry."""
        if not self.registry_path.exists():
            return {}

        try:
            with open(self.registry_path) as f:
                data = json.load(f)
                return {
                    gap_id: GeneralizedGap.from_dict(gap_data)
                    for gap_id, gap_data in data.get("gaps", {}).items()
                }
        except (json.JSONDecodeError, IOError):
            return {}

    def _save_registry(self) -> None:
        """Save the capability gaps registry."""
        data = {
            "version": "1.0",
            "updated_at": datetime.now().isoformat(),
            "gaps": {
                gap_id: gap.to_dict()
                for gap_id, gap in self._registry.items()
            },
        }

        try:
            with open(self.registry_path, 'w') as f:
                json.dump(data, f, indent=2)
        except IOError as e:
            print(f"Warning: Could not save registry: {e}", file=sys.stderr)

    def _extract_keywords(self, analysis: RootCauseAnalysis) -> list[str]:
        """Extract keywords from a root cause analysis."""
        # Combine all text for keyword extraction
        text_parts = [
            analysis.root_cause,
            analysis.capability_gap,
            analysis.counterfactual,
        ]
        text_parts.extend(analysis.whys)

        combined_text = " ".join(text_parts).lower()

        # Extract individual words
        words = re.findall(r'\b[a-z]+\b', combined_text)

        # Remove common stop words
        stop_words = {
            "the", "a", "an", "is", "are", "was", "were", "be", "been",
            "being", "have", "has", "had", "do", "does", "did", "will",
            "would", "could", "should", "may", "might", "must", "shall",
            "can", "need", "to", "of", "in", "for", "on", "with", "at",
            "by", "from", "as", "into", "through", "during", "before",
            "after", "above", "below", "between", "under", "again",
            "further", "then", "once", "here", "there", "when", "where",
            "why", "how", "all", "each", "few", "more", "most", "other",
            "some", "such", "no", "nor", "not", "only", "own", "same",
            "so", "than", "too", "very", "just", "also", "now", "and",
            "but", "or", "because", "if", "while", "this", "that",
        }

        return [w for w in words if w not in stop_words and len(w) > 2]

    def _determine_category(self, analysis: RootCauseAnalysis) -> str:
        """Determine the capability category for a root cause analysis."""
        keywords = self._extract_keywords(analysis)

        # Count matches for each category
        category_scores: dict[str, int] = {}

        for category, category_keywords in CAPABILITY_KEYWORDS.items():
            score = sum(
                1 for kw in keywords
                if any(ckw in kw or kw in ckw for ckw in category_keywords)
            )
            if score > 0:
                category_scores[category] = score

        if not category_scores:
            return CapabilityCategory.UNKNOWN

        # Return category with highest score
        return max(category_scores.items(), key=lambda x: x[1])[0]

    def _generate_gap_id(self, category: str, description: str) -> str:
        """Generate a unique gap ID."""
        content = f"{category}:{description}"
        hash_val = hashlib.sha256(content.encode()).hexdigest()[:8]
        return f"GAP-{hash_val.upper()}"

    def _calculate_frequency_score(self, analysis: RootCauseAnalysis) -> float:
        """Calculate frequency score based on pattern occurrences."""
        # Get the pattern to check occurrences
        pattern = self.analyzer.clusterer.get_pattern_by_id(analysis.pattern_id)

        if not pattern:
            return 0.3  # Default moderate score if pattern not found

        # Normalize occurrences (assuming 10+ is very frequent)
        occurrences = pattern.occurrences
        if occurrences >= 10:
            return 1.0
        elif occurrences >= 7:
            return 0.9
        elif occurrences >= 5:
            return 0.8
        elif occurrences >= 3:
            return 0.6
        elif occurrences >= 2:
            return 0.4
        else:
            return 0.2

    def _calculate_impact_score(self, analysis: RootCauseAnalysis) -> float:
        """Calculate impact score based on affected stories."""
        pattern = self.analyzer.clusterer.get_pattern_by_id(analysis.pattern_id)

        if not pattern:
            return 0.3

        # Normalize affected stories (assuming 5+ is high impact)
        num_stories = len(pattern.affected_stories)
        if num_stories >= 5:
            return 1.0
        elif num_stories >= 4:
            return 0.85
        elif num_stories >= 3:
            return 0.7
        elif num_stories >= 2:
            return 0.5
        else:
            return 0.3

    def _estimate_future_failures(
        self,
        frequency_score: float,
        impact_score: float,
        projection_days: int = 30,
    ) -> float:
        """
        Estimate future failures if the gap is not addressed.

        Based on current failure rate, projects future failures.

        Args:
            frequency_score: How often failures occur (0-1)
            impact_score: How impactful failures are (0-1)
            projection_days: Number of days to project failures for

        Returns:
            Estimated number of failures in the projection period
        """
        # Base rate: 1 failure per day at maximum scores
        base_rate = frequency_score * impact_score * 0.5

        # Project for the specified number of days
        return base_rate * projection_days

    def _generate_improvement_benefit(
        self,
        category: str,
        frequency_score: float,
        impact_score: float,
    ) -> str:
        """Generate a description of the improvement benefit."""
        task_families = TASK_FAMILIES.get(category, ["general tasks"])

        if frequency_score > 0.8 and impact_score > 0.8:
            severity = "critical"
        elif frequency_score > 0.6 or impact_score > 0.6:
            severity = "significant"
        else:
            severity = "moderate"

        return (
            f"Addressing this {severity} gap in {category.lower().replace('_', ' ')} "
            f"would improve success rates for: {', '.join(task_families[:3])}. "
            f"Expected reduction in failures: {int((frequency_score * impact_score) * 100)}%."
        )

    def generalize_gap(
        self,
        analysis: RootCauseAnalysis,
        save_to_registry: bool = True,
    ) -> GeneralizedGap:
        """
        Generalize a root cause analysis to a capability gap.

        Args:
            analysis: The RootCauseAnalysis to generalize
            save_to_registry: Whether to save to the registry

        Returns:
            GeneralizedGap with category, priority, and task families
        """
        # Determine category
        category = self._determine_category(analysis)

        # Get affected task families
        affected_task_types = TASK_FAMILIES.get(category, ["General tasks"])

        # Calculate component scores
        frequency_score = self._calculate_frequency_score(analysis)
        impact_score = self._calculate_impact_score(analysis)
        feasibility_score = FEASIBILITY_SCORES.get(category, 0.5)

        # Calculate combined priority score (0-100)
        # Formula: (frequency * 0.35 + impact * 0.40 + feasibility * 0.25) * 100
        priority_score = (
            frequency_score * 0.35 +
            impact_score * 0.40 +
            feasibility_score * 0.25
        ) * 100

        # Get pattern details
        pattern = self.analyzer.clusterer.get_pattern_by_id(analysis.pattern_id)
        pattern_ids = [analysis.pattern_id]
        affected_stories = pattern.affected_stories if pattern else []

        # Generate description
        description = (
            f"{analysis.capability_gap}. "
            f"Root cause: {analysis.root_cause}"
        )

        # Generate gap ID
        gap_id = self._generate_gap_id(category, description)

        # Check if we should merge with existing gap
        existing_gap = self._find_similar_gap(category, description)
        if existing_gap:
            # Merge with existing gap
            return self._merge_gap(existing_gap, analysis, save_to_registry)

        # Estimate future failures
        estimated_future_failures = self._estimate_future_failures(
            frequency_score, impact_score
        )

        # Generate improvement benefit
        improvement_benefit = self._generate_improvement_benefit(
            category, frequency_score, impact_score
        )

        now = datetime.now().isoformat()

        gap = GeneralizedGap(
            gap_id=gap_id,
            category=category,
            description=description,
            affected_task_types=affected_task_types,
            priority_score=priority_score,
            frequency_score=frequency_score,
            impact_score=impact_score,
            feasibility_score=feasibility_score,
            root_cause_ids=[analysis.pattern_id],
            pattern_ids=pattern_ids,
            affected_stories=affected_stories,
            estimated_future_failures=estimated_future_failures,
            improvement_benefit=improvement_benefit,
            created_at=now,
            updated_at=now,
            status="active",
        )

        if save_to_registry:
            self._registry[gap_id] = gap
            self._save_registry()

        return gap

    def _find_similar_gap(self, category: str, description: str) -> GeneralizedGap | None:
        """Find an existing similar gap in the registry."""
        for gap in self._registry.values():
            if gap.category != category:
                continue

            if gap.status != "active":
                continue

            # Check for text similarity
            if self._text_similarity(gap.description, description) > 0.7:
                return gap

        return None

    def _text_similarity(self, text1: str, text2: str) -> float:
        """Calculate simple word overlap similarity."""
        if not text1 or not text2:
            return 0.0

        words1 = set(text1.lower().split())
        words2 = set(text2.lower().split())

        if not words1 or not words2:
            return 0.0

        intersection = words1 & words2
        union = words1 | words2

        return len(intersection) / len(union)

    def _merge_gap(
        self,
        existing: GeneralizedGap,
        analysis: RootCauseAnalysis,
        save_to_registry: bool,
    ) -> GeneralizedGap:
        """Merge a new analysis into an existing gap."""
        # Add new pattern/root cause IDs
        if analysis.pattern_id not in existing.pattern_ids:
            existing.pattern_ids.append(analysis.pattern_id)
        if analysis.pattern_id not in existing.root_cause_ids:
            existing.root_cause_ids.append(analysis.pattern_id)

        # Merge affected stories
        pattern = self.analyzer.clusterer.get_pattern_by_id(analysis.pattern_id)
        if pattern:
            for story in pattern.affected_stories:
                if story not in existing.affected_stories:
                    existing.affected_stories.append(story)

        # Recalculate scores based on merged data
        # Frequency increases with more patterns
        existing.frequency_score = min(1.0, existing.frequency_score + 0.1)

        # Impact increases with more affected stories
        story_count = len(existing.affected_stories)
        if story_count >= 5:
            existing.impact_score = 1.0
        elif story_count >= 4:
            existing.impact_score = max(existing.impact_score, 0.85)
        elif story_count >= 3:
            existing.impact_score = max(existing.impact_score, 0.7)

        # Recalculate priority
        existing.priority_score = (
            existing.frequency_score * 0.35 +
            existing.impact_score * 0.40 +
            existing.feasibility_score * 0.25
        ) * 100

        # Update timestamp
        existing.updated_at = datetime.now().isoformat()

        # Recalculate projections
        existing.estimated_future_failures = self._estimate_future_failures(
            existing.frequency_score, existing.impact_score
        )
        existing.improvement_benefit = self._generate_improvement_benefit(
            existing.category, existing.frequency_score, existing.impact_score
        )

        if save_to_registry:
            self._save_registry()

        return existing

    def generalize_by_pattern_id(
        self,
        pattern_id: str,
        save_to_registry: bool = True,
    ) -> GeneralizedGap | None:
        """
        Generalize a gap from a pattern ID.

        First looks up or creates the root cause analysis, then generalizes.
        """
        # Get or create root cause analysis
        analysis = self.analyzer.analyze_by_pattern_id(pattern_id)

        if not analysis:
            return None

        return self.generalize_gap(analysis, save_to_registry=save_to_registry)

    def batch_generalize(self, min_occurrences: int = 3) -> list[GeneralizedGap]:
        """
        Generalize all patterns meeting minimum occurrence threshold.

        Returns:
            List of GeneralizedGap objects
        """
        analyses = self.analyzer.batch_analyze(min_occurrences=min_occurrences)

        gaps = []
        for analysis in analyses:
            gap = self.generalize_gap(analysis, save_to_registry=True)
            gaps.append(gap)

        return gaps

    def get_registry(self) -> list[GeneralizedGap]:
        """Get all gaps in the registry."""
        return list(self._registry.values())

    def get_gap_by_id(self, gap_id: str) -> GeneralizedGap | None:
        """Get a specific gap by ID."""
        return self._registry.get(gap_id)

    def get_prioritized_gaps(
        self,
        status: str | None = "active",
        limit: int | None = None,
    ) -> list[GeneralizedGap]:
        """
        Get gaps sorted by priority score.

        Args:
            status: Filter by status (None for all)
            limit: Maximum number of gaps to return

        Returns:
            List of gaps sorted by priority (highest first)
        """
        gaps = [
            gap for gap in self._registry.values()
            if status is None or gap.status == status
        ]

        gaps.sort(key=lambda g: g.priority_score, reverse=True)

        if limit:
            gaps = gaps[:limit]

        return gaps

    def get_gaps_by_category(self, category: str) -> list[GeneralizedGap]:
        """Get all gaps in a specific category."""
        return [
            gap for gap in self._registry.values()
            if gap.category == category
        ]

    def mark_gap_resolved(
        self,
        gap_id: str,
        resolution: str = "",
    ) -> bool:
        """Mark a gap as resolved."""
        gap = self._registry.get(gap_id)
        if not gap:
            return False

        gap.status = "resolved"
        gap.updated_at = datetime.now().isoformat()
        if resolution:
            gap.improvement_benefit = f"Resolved: {resolution}"

        self._save_registry()
        return True

    def mark_gap_deferred(
        self,
        gap_id: str,
        reason: str = "",
    ) -> bool:
        """Mark a gap as deferred (will address later)."""
        gap = self._registry.get(gap_id)
        if not gap:
            return False

        gap.status = "deferred"
        gap.updated_at = datetime.now().isoformat()
        if reason:
            gap.improvement_benefit = f"Deferred: {reason}"

        self._save_registry()
        return True

    def get_summary(self) -> dict[str, Any]:
        """Get summary statistics of all gaps."""
        active_gaps = [g for g in self._registry.values() if g.status == "active"]
        resolved_gaps = [g for g in self._registry.values() if g.status == "resolved"]
        deferred_gaps = [g for g in self._registry.values() if g.status == "deferred"]

        # Count by category
        by_category: dict[str, int] = {}
        for gap in active_gaps:
            by_category[gap.category] = by_category.get(gap.category, 0) + 1

        # Get top priority gaps
        top_priorities = self.get_prioritized_gaps(limit=5)

        return {
            "total_gaps": len(self._registry),
            "active_gaps": len(active_gaps),
            "resolved_gaps": len(resolved_gaps),
            "deferred_gaps": len(deferred_gaps),
            "by_category": by_category,
            "top_priority_gaps": [
                {"gap_id": g.gap_id, "priority": g.priority_score, "category": g.category}
                for g in top_priorities
            ],
            "total_affected_stories": len(set(
                story
                for gap in active_gaps
                for story in gap.affected_stories
            )),
            "average_priority": (
                sum(g.priority_score for g in active_gaps) / len(active_gaps)
                if active_gaps else 0
            ),
        }


# ============================================================================
# CLI Interface
# ============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Capability Gap Generalizer for claude-loop",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python lib/gap-generalizer.py generalize PAT-12345678
    python lib/gap-generalizer.py generalize PAT-12345678 --json
    python lib/gap-generalizer.py list
    python lib/gap-generalizer.py show GAP-ABCD1234
    python lib/gap-generalizer.py registry
    python lib/gap-generalizer.py prioritize
    python lib/gap-generalizer.py batch-generalize
    python lib/gap-generalizer.py categories
    python lib/gap-generalizer.py mark-resolved GAP-ABCD1234 "Fixed by SI-006"
        """,
    )

    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # generalize command
    gen_parser = subparsers.add_parser(
        "generalize", help="Generalize a pattern to a capability gap"
    )
    gen_parser.add_argument(
        "pattern_id",
        type=str,
        help="Pattern ID to generalize (e.g., PAT-12345678)",
    )
    gen_parser.add_argument(
        "--json", action="store_true",
        help="Output as JSON",
    )
    gen_parser.add_argument(
        "--no-save", action="store_true",
        help="Don't save to registry",
    )

    # list command
    list_parser = subparsers.add_parser(
        "list", help="List all capability gaps"
    )
    list_parser.add_argument(
        "--status",
        choices=["active", "resolved", "deferred", "all"],
        default="active",
        help="Filter by status (default: active)",
    )
    list_parser.add_argument(
        "--json", action="store_true",
        help="Output as JSON",
    )

    # show command
    show_parser = subparsers.add_parser(
        "show", help="Show details of a specific gap"
    )
    show_parser.add_argument(
        "gap_id",
        type=str,
        help="Gap ID to show (e.g., GAP-ABCD1234)",
    )
    show_parser.add_argument(
        "--json", action="store_true",
        help="Output as JSON",
    )

    # registry command
    registry_parser = subparsers.add_parser(
        "registry", help="Show registry summary"
    )
    registry_parser.add_argument(
        "--json", action="store_true",
        help="Output as JSON",
    )

    # prioritize command
    prioritize_parser = subparsers.add_parser(
        "prioritize", help="Show gaps sorted by priority"
    )
    prioritize_parser.add_argument(
        "--limit",
        type=int,
        default=10,
        help="Number of gaps to show (default: 10)",
    )
    prioritize_parser.add_argument(
        "--json", action="store_true",
        help="Output as JSON",
    )

    # batch-generalize command
    batch_parser = subparsers.add_parser(
        "batch-generalize", help="Generalize all patterns"
    )
    batch_parser.add_argument(
        "--min-occurrences",
        type=int,
        default=3,
        help="Minimum pattern occurrences (default: 3)",
    )
    batch_parser.add_argument(
        "--json", action="store_true",
        help="Output as JSON",
    )

    # categories command
    cat_parser = subparsers.add_parser(
        "categories", help="List all capability categories"
    )
    cat_parser.add_argument(
        "--json", action="store_true",
        help="Output as JSON",
    )

    # mark-resolved command
    resolved_parser = subparsers.add_parser(
        "mark-resolved", help="Mark a gap as resolved"
    )
    resolved_parser.add_argument(
        "gap_id",
        type=str,
        help="Gap ID to mark as resolved",
    )
    resolved_parser.add_argument(
        "resolution",
        type=str,
        nargs="?",
        default="",
        help="Description of the resolution",
    )

    # mark-deferred command
    deferred_parser = subparsers.add_parser(
        "mark-deferred", help="Mark a gap as deferred"
    )
    deferred_parser.add_argument(
        "gap_id",
        type=str,
        help="Gap ID to mark as deferred",
    )
    deferred_parser.add_argument(
        "reason",
        type=str,
        nargs="?",
        default="",
        help="Reason for deferring",
    )

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    # Initialize generalizer
    project_root = Path(__file__).parent.parent
    generalizer = GapGeneralizer(project_root=project_root)

    if args.command == "generalize":
        save_to_registry = not args.no_save
        gap = generalizer.generalize_by_pattern_id(
            args.pattern_id,
            save_to_registry=save_to_registry,
        )

        if not gap:
            print(f"Error: Pattern '{args.pattern_id}' not found")
            print("\nUse 'pattern-clusterer.py list' to see available patterns")
            sys.exit(1)

        if args.json:
            print(json.dumps(gap.to_dict(), indent=2))
        else:
            print(f"=== Generalized Gap: {gap.gap_id} ===\n")
            print(f"Category: {gap.category}")
            print(f"Priority Score: {gap.priority_score:.1f}/100")
            print(f"Status: {gap.status}")
            print()
            print(f"Description:")
            print(f"  {gap.description}")
            print()
            print(f"Component Scores:")
            print(f"  Frequency:   {gap.frequency_score:.0%}")
            print(f"  Impact:      {gap.impact_score:.0%}")
            print(f"  Feasibility: {gap.feasibility_score:.0%}")
            print()
            print(f"Affected Task Types:")
            for task_type in gap.affected_task_types:
                print(f"  - {task_type}")
            print()
            print(f"Estimated Future Failures: {gap.estimated_future_failures:.0f} (next 30 days)")
            print()
            print(f"Improvement Benefit:")
            print(f"  {gap.improvement_benefit}")
            print()
            print(f"Affected Stories ({len(gap.affected_stories)}):")
            for story in gap.affected_stories[:5]:
                print(f"  - {story}")
            if len(gap.affected_stories) > 5:
                print(f"  ... and {len(gap.affected_stories) - 5} more")

    elif args.command == "list":
        status = None if args.status == "all" else args.status
        gaps = [
            gap for gap in generalizer.get_registry()
            if status is None or gap.status == status
        ]
        gaps.sort(key=lambda g: g.priority_score, reverse=True)

        if args.json:
            print(json.dumps([g.to_dict() for g in gaps], indent=2))
        else:
            if not gaps:
                print(f"No {args.status} gaps found.")
                return

            print(f"{'Gap ID':<15} {'Priority':>8}  {'Category':<20}  Status")
            print("-" * 70)
            for gap in gaps:
                print(f"{gap.gap_id:<15} {gap.priority_score:>7.1f}  {gap.category:<20}  {gap.status}")

    elif args.command == "show":
        gap = generalizer.get_gap_by_id(args.gap_id)

        if not gap:
            print(f"Error: Gap '{args.gap_id}' not found")
            print("\nUse 'gap-generalizer.py list' to see available gaps")
            sys.exit(1)

        if args.json:
            print(json.dumps(gap.to_dict(), indent=2))
        else:
            print(f"=== Gap: {gap.gap_id} ===\n")
            print(f"Category: {gap.category}")
            print(f"Status: {gap.status}")
            print(f"Priority Score: {gap.priority_score:.1f}/100")
            print(f"Created: {gap.created_at[:19] if gap.created_at else 'N/A'}")
            print(f"Updated: {gap.updated_at[:19] if gap.updated_at else 'N/A'}")
            print()
            print(f"Description:")
            print(f"  {gap.description}")
            print()
            print(f"Component Scores:")
            print(f"  Frequency:   {gap.frequency_score:.0%}")
            print(f"  Impact:      {gap.impact_score:.0%}")
            print(f"  Feasibility: {gap.feasibility_score:.0%}")
            print()
            print(f"Affected Task Types:")
            for task_type in gap.affected_task_types:
                print(f"  - {task_type}")
            print()
            print(f"Root Cause IDs: {', '.join(gap.root_cause_ids) or 'N/A'}")
            print(f"Pattern IDs: {', '.join(gap.pattern_ids) or 'N/A'}")
            print()
            print(f"Affected Stories ({len(gap.affected_stories)}):")
            for story in gap.affected_stories:
                print(f"  - {story}")
            print()
            print(f"Estimated Future Failures: {gap.estimated_future_failures:.0f}")
            print()
            print(f"Improvement Benefit:")
            print(f"  {gap.improvement_benefit}")

    elif args.command == "registry":
        summary = generalizer.get_summary()

        if args.json:
            print(json.dumps(summary, indent=2))
        else:
            print("=== Capability Gaps Registry ===\n")
            print(f"Total Gaps: {summary['total_gaps']}")
            print(f"  Active:   {summary['active_gaps']}")
            print(f"  Resolved: {summary['resolved_gaps']}")
            print(f"  Deferred: {summary['deferred_gaps']}")
            print()
            print(f"Affected Stories: {summary['total_affected_stories']}")
            print(f"Average Priority: {summary['average_priority']:.1f}")
            print()
            print("By Category:")
            for cat, count in summary.get('by_category', {}).items():
                print(f"  {cat}: {count}")
            print()
            if summary['top_priority_gaps']:
                print("Top Priority Gaps:")
                for gap_info in summary['top_priority_gaps']:
                    print(f"  {gap_info['gap_id']}: {gap_info['priority']:.1f} ({gap_info['category']})")

    elif args.command == "prioritize":
        gaps = generalizer.get_prioritized_gaps(limit=args.limit)

        if args.json:
            print(json.dumps([g.to_dict() for g in gaps], indent=2))
        else:
            if not gaps:
                print("No active gaps found.")
                return

            print(f"=== Top {len(gaps)} Priority Gaps ===\n")
            print(f"{'#':>3}  {'Gap ID':<15} {'Score':>6}  {'Category':<20}  Est. Failures")
            print("-" * 75)
            for i, gap in enumerate(gaps, 1):
                print(f"{i:>3}  {gap.gap_id:<15} {gap.priority_score:>5.1f}  {gap.category:<20}  {gap.estimated_future_failures:.0f}")

    elif args.command == "batch-generalize":
        gaps = generalizer.batch_generalize(min_occurrences=args.min_occurrences)

        if args.json:
            print(json.dumps([g.to_dict() for g in gaps], indent=2))
        else:
            if not gaps:
                print("No patterns to generalize.")
                print(f"\nNote: Patterns require at least {args.min_occurrences} occurrences.")
                return

            print(f"=== Batch Generalization ===\n")
            print(f"Generalized {len(gaps)} patterns:\n")

            for gap in sorted(gaps, key=lambda g: g.priority_score, reverse=True):
                print(f"[{gap.gap_id}] {gap.category}")
                print(f"  Priority: {gap.priority_score:.1f}")
                print(f"  {gap.description[:70]}...")
                print()

    elif args.command == "categories":
        categories = CapabilityCategory.all_categories()

        if args.json:
            output = {
                cat: {
                    "keywords": CAPABILITY_KEYWORDS.get(cat, []),
                    "task_families": TASK_FAMILIES.get(cat, []),
                    "feasibility": FEASIBILITY_SCORES.get(cat, 0.5),
                }
                for cat in categories
            }
            print(json.dumps(output, indent=2))
        else:
            print("=== Capability Categories ===\n")
            for cat in categories:
                if cat == CapabilityCategory.UNKNOWN:
                    continue
                feasibility = FEASIBILITY_SCORES.get(cat, 0.5)
                task_families = TASK_FAMILIES.get(cat, [])
                print(f"{cat}")
                print(f"  Feasibility: {feasibility:.0%}")
                print(f"  Task Families: {', '.join(task_families[:3])}")
                print()

    elif args.command == "mark-resolved":
        success = generalizer.mark_gap_resolved(args.gap_id, args.resolution)
        if success:
            print(f"Gap {args.gap_id} marked as resolved.")
        else:
            print(f"Error: Gap '{args.gap_id}' not found")
            sys.exit(1)

    elif args.command == "mark-deferred":
        success = generalizer.mark_gap_deferred(args.gap_id, args.reason)
        if success:
            print(f"Gap {args.gap_id} marked as deferred.")
        else:
            print(f"Error: Gap '{args.gap_id}' not found")
            sys.exit(1)


if __name__ == "__main__":
    main()
