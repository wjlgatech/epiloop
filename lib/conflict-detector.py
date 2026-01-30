#!/usr/bin/env python3
"""
conflict-detector.py - Conflict Detection System for claude-loop Improvements

Detects conflicts between improvement proposals before promotion to prevent
contradictory behaviors and scope overlaps in the system.

Key principle: All improvement proposals must declare their scope explicitly.
Conflicts must be resolved before promotion - human decision required.

Conflict Types:
- behavioral_contradiction: Two improvements contradict each other
  Example: 'always retry' vs 'never retry idempotent'
- scope_overlap: Two improvements affect the same scope
  Example: Both modify error handling in the same domain
- dependency_conflict: One improvement's preconditions conflict with another's effects
  Example: A requires X enabled, B disables X
- resource_contention: Both improvements need exclusive access to same resource
  Example: Both try to modify the same configuration file

Usage:
    # Check conflicts for a specific improvement
    python lib/conflict-detector.py conflicts <id>

    # Show/edit scope declaration for an improvement
    python lib/conflict-detector.py scope <id>

    # Add scope to an improvement
    python lib/conflict-detector.py scope add <id> --preconditions "..."
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from difflib import SequenceMatcher
from enum import Enum
from pathlib import Path
from typing import Any


# ============================================================================
# Constants
# ============================================================================

DEFAULT_QUEUE_FILE = ".claude-loop/improvement_queue.json"
DEFAULT_SCOPE_FILE = ".claude-loop/improvement_scopes.json"
DEFAULT_CONFLICTS_FILE = ".claude-loop/detected_conflicts.json"
BASE_DIR = Path.cwd()

# Behavioral contradiction patterns - pairs that conflict
CONTRADICTION_PATTERNS = [
    # Retry behavior
    ("always retry", "never retry"),
    ("retry on failure", "fail fast"),
    ("retry", "no retry"),
    ("retry all", "retry only idempotent"),
    # Sync behavior
    ("synchronous", "asynchronous"),
    ("sync", "async"),
    ("blocking", "non-blocking"),
    # Caching
    ("cache", "no-cache"),
    ("cache always", "never cache"),
    ("enable cache", "disable cache"),
    # Validation
    ("strict validation", "lenient validation"),
    ("strict", "permissive"),
    ("validate", "skip validation"),
    ("validate all", "validate none"),
    # Error handling
    ("fail fast", "graceful degradation"),
    ("throw exception", "return error"),
    ("log and continue", "stop on error"),
    # Authentication
    ("require auth", "allow anonymous"),
    ("authenticated", "unauthenticated"),
    # Ordering
    ("sequential", "parallel"),
    ("ordered", "unordered"),
    ("fifo", "lifo"),
]

# Resource types that can have contention
RESOURCE_TYPES = [
    "config_file",
    "database_table",
    "api_endpoint",
    "cache_key",
    "lock_file",
    "log_file",
    "environment_variable",
    "shared_state",
]


# ============================================================================
# Enums
# ============================================================================

class ConflictType(str, Enum):
    """Types of conflicts between improvements."""
    BEHAVIORAL_CONTRADICTION = "behavioral_contradiction"
    SCOPE_OVERLAP = "scope_overlap"
    DEPENDENCY_CONFLICT = "dependency_conflict"
    RESOURCE_CONTENTION = "resource_contention"

    def __str__(self) -> str:
        return self.value


class ConflictSeverity(str, Enum):
    """Severity levels for detected conflicts."""
    BLOCKING = "blocking"     # Must be resolved before promotion
    WARNING = "warning"       # Should be reviewed but may proceed
    INFO = "info"            # Informational only

    def __str__(self) -> str:
        return self.value


class ResolutionStrategy(str, Enum):
    """Strategies for resolving conflicts."""
    SCOPE_NARROWING = "scope_narrowing"          # Reduce scope of one or both
    CONDITIONAL_APPLICATION = "conditional"      # Apply based on conditions
    MERGE = "merge"                              # Combine into single improvement
    PRIORITIZE = "prioritize"                    # Choose one over the other
    DOMAIN_SPLIT = "domain_split"                # Split by domain
    MANUAL_REVIEW = "manual_review"              # Requires human decision

    def __str__(self) -> str:
        return self.value


# ============================================================================
# Data Classes
# ============================================================================

@dataclass
class ImprovementScope:
    """Scope declaration for an improvement proposal.

    Every improvement must declare its scope to enable conflict detection.

    Attributes:
        improvement_id: ID of the improvement this scope belongs to
        preconditions: Conditions that must be true for this improvement to apply
            Example: ["cache enabled", "database available"]
        affected_behaviors: Behaviors this improvement modifies
            Example: ["error handling", "retry logic", "caching"]
        domain_applicability: Domains where this improvement applies
            Example: ["web_backend", "api_service"]
        exclusions: Explicit exclusions where this improvement should NOT apply
            Example: ["batch jobs", "async workers"]
        resources_used: Resources this improvement accesses/modifies
            Example: [{"type": "config_file", "name": "settings.json"}]
        effects: Side effects of applying this improvement
            Example: ["disables retry", "enables caching"]
        created_at: When scope was first declared
        updated_at: Last update timestamp
    """
    improvement_id: str
    preconditions: list[str] = field(default_factory=list)
    affected_behaviors: list[str] = field(default_factory=list)
    domain_applicability: list[str] = field(default_factory=list)
    exclusions: list[str] = field(default_factory=list)
    resources_used: list[dict[str, str]] = field(default_factory=list)
    effects: list[str] = field(default_factory=list)
    created_at: str = ""
    updated_at: str = ""

    def __post_init__(self):
        now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        if not self.created_at:
            self.created_at = now
        if not self.updated_at:
            self.updated_at = now

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ImprovementScope":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})

    def is_complete(self) -> bool:
        """Check if scope declaration is complete enough for conflict detection."""
        return bool(
            self.affected_behaviors or
            self.domain_applicability or
            self.effects
        )

    def get_normalized_behaviors(self) -> set[str]:
        """Get normalized set of affected behaviors for comparison."""
        return {b.lower().strip() for b in self.affected_behaviors}

    def get_normalized_domains(self) -> set[str]:
        """Get normalized set of applicable domains."""
        return {d.lower().strip() for d in self.domain_applicability}


@dataclass
class Conflict:
    """A detected conflict between two improvements.

    Attributes:
        conflict_id: Unique identifier for this conflict
        conflict_type: Type of conflict detected
        severity: How serious is this conflict
        improvement_a: First improvement involved
        improvement_b: Second improvement involved
        description: Human-readable description of the conflict
        evidence: Specific evidence that caused this detection
        resolution_suggestions: Suggested ways to resolve
        detected_at: When conflict was detected
        resolved: Whether this conflict has been resolved
        resolution_notes: How it was resolved (if resolved)
    """
    conflict_id: str
    conflict_type: str
    severity: str
    improvement_a: str
    improvement_b: str
    description: str
    evidence: list[str] = field(default_factory=list)
    resolution_suggestions: list[dict[str, str]] = field(default_factory=list)
    detected_at: str = ""
    resolved: bool = False
    resolution_notes: str = ""

    def __post_init__(self):
        if not self.conflict_id:
            # Generate ID from conflict content
            hash_input = f"{self.improvement_a}:{self.improvement_b}:{self.conflict_type}"
            self.conflict_id = f"CONF-{hashlib.sha256(hash_input.encode()).hexdigest()[:8].upper()}"
        if not self.detected_at:
            self.detected_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Conflict":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})

    def is_blocking(self) -> bool:
        """Check if this conflict blocks promotion."""
        return self.severity == ConflictSeverity.BLOCKING.value and not self.resolved


@dataclass
class ConflictReport:
    """Summary report of conflicts for an improvement.

    Attributes:
        improvement_id: The improvement being analyzed
        total_conflicts: Total number of conflicts found
        blocking_conflicts: Number of blocking conflicts
        warning_conflicts: Number of warning conflicts
        conflicts: List of all detected conflicts
        can_promote: Whether promotion is allowed
        blocking_reasons: List of reasons blocking promotion
        generated_at: When report was generated
    """
    improvement_id: str
    total_conflicts: int = 0
    blocking_conflicts: int = 0
    warning_conflicts: int = 0
    conflicts: list[Conflict] = field(default_factory=list)
    can_promote: bool = True
    blocking_reasons: list[str] = field(default_factory=list)
    generated_at: str = ""

    def __post_init__(self):
        if not self.generated_at:
            self.generated_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["conflicts"] = [c.to_dict() if hasattr(c, "to_dict") else c for c in self.conflicts]
        return result


# ============================================================================
# Conflict Detector
# ============================================================================

class ConflictDetector:
    """Detects and manages conflicts between improvement proposals.

    Enforces scope declarations and identifies conflicts before promotion.
    """

    def __init__(
        self,
        queue_file: str = DEFAULT_QUEUE_FILE,
        scope_file: str = DEFAULT_SCOPE_FILE,
        conflicts_file: str = DEFAULT_CONFLICTS_FILE,
        base_dir: Path | None = None
    ):
        self.base_dir = base_dir or BASE_DIR
        self.queue_file = self.base_dir / queue_file
        self.scope_file = self.base_dir / scope_file
        self.conflicts_file = self.base_dir / conflicts_file
        self._scopes: dict[str, ImprovementScope] = {}
        self._conflicts: dict[str, Conflict] = {}
        self._load_scopes()
        self._load_conflicts()

    def _ensure_dir(self) -> None:
        """Ensure directories exist."""
        self.scope_file.parent.mkdir(parents=True, exist_ok=True)

    def _load_scopes(self) -> None:
        """Load scope declarations from disk."""
        if self.scope_file.exists():
            try:
                data = json.loads(self.scope_file.read_text())
                self._scopes = {
                    k: ImprovementScope.from_dict(v)
                    for k, v in data.get("scopes", {}).items()
                }
            except (json.JSONDecodeError, KeyError):
                self._scopes = {}
        else:
            self._scopes = {}

    def _save_scopes(self) -> None:
        """Persist scope declarations to disk."""
        self._ensure_dir()
        data = {
            "version": "1.0",
            "updated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "scopes": {k: v.to_dict() for k, v in self._scopes.items()}
        }
        self.scope_file.write_text(json.dumps(data, indent=2))

    def _load_conflicts(self) -> None:
        """Load detected conflicts from disk."""
        if self.conflicts_file.exists():
            try:
                data = json.loads(self.conflicts_file.read_text())
                self._conflicts = {
                    k: Conflict.from_dict(v)
                    for k, v in data.get("conflicts", {}).items()
                }
            except (json.JSONDecodeError, KeyError):
                self._conflicts = {}
        else:
            self._conflicts = {}

    def _save_conflicts(self) -> None:
        """Persist detected conflicts to disk."""
        self._ensure_dir()
        data = {
            "version": "1.0",
            "updated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "conflicts": {k: v.to_dict() for k, v in self._conflicts.items()}
        }
        self.conflicts_file.write_text(json.dumps(data, indent=2))

    def _get_proposal(self, proposal_id: str) -> dict[str, Any] | None:
        """Get proposal data from queue file."""
        if not self.queue_file.exists():
            return None
        try:
            data = json.loads(self.queue_file.read_text())
            proposals = data.get("proposals", {})
            return proposals.get(proposal_id)
        except (json.JSONDecodeError, KeyError):
            return None

    def _get_all_proposals(self) -> dict[str, dict[str, Any]]:
        """Get all proposals from queue file."""
        if not self.queue_file.exists():
            return {}
        try:
            data = json.loads(self.queue_file.read_text())
            return data.get("proposals", {})
        except (json.JSONDecodeError, KeyError):
            return {}

    # =========================================================================
    # Scope Management
    # =========================================================================

    def set_scope(
        self,
        improvement_id: str,
        preconditions: list[str] | None = None,
        affected_behaviors: list[str] | None = None,
        domain_applicability: list[str] | None = None,
        exclusions: list[str] | None = None,
        resources_used: list[dict[str, str]] | None = None,
        effects: list[str] | None = None
    ) -> ImprovementScope:
        """Set or update scope declaration for an improvement.

        Args:
            improvement_id: ID of the improvement
            preconditions: Conditions required for this improvement
            affected_behaviors: Behaviors this improvement modifies
            domain_applicability: Domains where applicable
            exclusions: Explicit exclusions
            resources_used: Resources accessed/modified
            effects: Side effects

        Returns:
            Updated ImprovementScope
        """
        existing = self._scopes.get(improvement_id)
        now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

        if existing:
            # Update existing scope
            if preconditions is not None:
                existing.preconditions = preconditions
            if affected_behaviors is not None:
                existing.affected_behaviors = affected_behaviors
            if domain_applicability is not None:
                existing.domain_applicability = domain_applicability
            if exclusions is not None:
                existing.exclusions = exclusions
            if resources_used is not None:
                existing.resources_used = resources_used
            if effects is not None:
                existing.effects = effects
            existing.updated_at = now
            scope = existing
        else:
            # Create new scope
            scope = ImprovementScope(
                improvement_id=improvement_id,
                preconditions=preconditions or [],
                affected_behaviors=affected_behaviors or [],
                domain_applicability=domain_applicability or [],
                exclusions=exclusions or [],
                resources_used=resources_used or [],
                effects=effects or [],
            )
            self._scopes[improvement_id] = scope

        self._save_scopes()
        return scope

    def get_scope(self, improvement_id: str) -> ImprovementScope | None:
        """Get scope declaration for an improvement."""
        return self._scopes.get(improvement_id)

    def has_scope(self, improvement_id: str) -> bool:
        """Check if an improvement has a scope declaration."""
        scope = self._scopes.get(improvement_id)
        return scope is not None and scope.is_complete()

    def infer_scope(self, improvement_id: str) -> ImprovementScope:
        """Infer scope from improvement proposal content.

        Automatically extracts scope information from the proposal's
        problem pattern and proposed solution.

        Args:
            improvement_id: ID of the improvement

        Returns:
            Inferred ImprovementScope (not saved automatically)
        """
        proposal = self._get_proposal(improvement_id)
        if not proposal:
            return ImprovementScope(improvement_id=improvement_id)

        problem = proposal.get("problem_pattern", "").lower()
        solution = proposal.get("proposed_solution", "").lower()
        text = f"{problem} {solution}"
        domains = proposal.get("affected_domains", [])

        # Infer affected behaviors from keywords
        behaviors = []
        behavior_keywords = {
            "error handling": ["error", "exception", "failure", "crash"],
            "retry logic": ["retry", "attempt", "backoff"],
            "caching": ["cache", "memoize", "store"],
            "logging": ["log", "trace", "debug", "audit"],
            "validation": ["validate", "check", "verify", "sanitize"],
            "authentication": ["auth", "login", "credential", "token"],
            "rate limiting": ["rate limit", "throttle", "quota"],
            "timeout": ["timeout", "deadline", "wait"],
        }

        for behavior, keywords in behavior_keywords.items():
            if any(kw in text for kw in keywords):
                behaviors.append(behavior)

        # Infer preconditions
        preconditions = []
        precondition_patterns = [
            (r"requires? (\w+)", "requires {}"),
            (r"when (\w+) is enabled", "{} enabled"),
            (r"if (\w+) available", "{} available"),
        ]

        for pattern, template in precondition_patterns:
            matches = re.findall(pattern, text)
            for match in matches:
                preconditions.append(template.format(match))

        # Infer effects
        effects = []
        effect_keywords = {
            "disables retry": ["no retry", "don't retry", "never retry"],
            "enables caching": ["add cache", "enable cache", "cache response"],
            "adds validation": ["add validation", "validate input"],
            "changes timeout": ["increase timeout", "reduce timeout", "set timeout"],
        }

        for effect, keywords in effect_keywords.items():
            if any(kw in text for kw in keywords):
                effects.append(effect)

        return ImprovementScope(
            improvement_id=improvement_id,
            preconditions=preconditions,
            affected_behaviors=behaviors,
            domain_applicability=domains,
            effects=effects,
        )

    def list_scopes(self, incomplete_only: bool = False) -> list[ImprovementScope]:
        """List all scope declarations.

        Args:
            incomplete_only: Only return incomplete scope declarations

        Returns:
            List of ImprovementScope objects
        """
        scopes = list(self._scopes.values())
        if incomplete_only:
            scopes = [s for s in scopes if not s.is_complete()]
        return scopes

    # =========================================================================
    # Conflict Detection
    # =========================================================================

    def detect_conflicts(
        self,
        improvement_a: str,
        improvement_b: str
    ) -> list[Conflict]:
        """Detect conflicts between two improvements.

        Args:
            improvement_a: First improvement ID
            improvement_b: Second improvement ID

        Returns:
            List of detected Conflict objects
        """
        conflicts: list[Conflict] = []

        # Get scopes (infer if not declared)
        scope_a = self.get_scope(improvement_a) or self.infer_scope(improvement_a)
        scope_b = self.get_scope(improvement_b) or self.infer_scope(improvement_b)

        # Get proposal data
        proposal_a = self._get_proposal(improvement_a) or {}
        proposal_b = self._get_proposal(improvement_b) or {}

        # 1. Check behavioral contradictions
        behavioral_conflicts = self._detect_behavioral_contradictions(
            improvement_a, improvement_b,
            proposal_a, proposal_b,
            scope_a, scope_b
        )
        conflicts.extend(behavioral_conflicts)

        # 2. Check scope overlaps
        scope_conflicts = self._detect_scope_overlaps(
            improvement_a, improvement_b,
            scope_a, scope_b
        )
        conflicts.extend(scope_conflicts)

        # 3. Check dependency conflicts
        dependency_conflicts = self._detect_dependency_conflicts(
            improvement_a, improvement_b,
            scope_a, scope_b
        )
        conflicts.extend(dependency_conflicts)

        # 4. Check resource contentions
        resource_conflicts = self._detect_resource_contentions(
            improvement_a, improvement_b,
            scope_a, scope_b
        )
        conflicts.extend(resource_conflicts)

        # Save detected conflicts
        for conflict in conflicts:
            self._conflicts[conflict.conflict_id] = conflict
        self._save_conflicts()

        return conflicts

    def _detect_behavioral_contradictions(
        self,
        imp_a: str,
        imp_b: str,
        proposal_a: dict[str, Any],
        proposal_b: dict[str, Any],
        scope_a: ImprovementScope,
        scope_b: ImprovementScope
    ) -> list[Conflict]:
        """Detect behavioral contradictions between improvements."""
        conflicts = []

        # Combine all text for analysis
        text_a = f"{proposal_a.get('problem_pattern', '')} {proposal_a.get('proposed_solution', '')} {' '.join(scope_a.effects)}"
        text_b = f"{proposal_b.get('problem_pattern', '')} {proposal_b.get('proposed_solution', '')} {' '.join(scope_b.effects)}"
        text_a_lower = text_a.lower()
        text_b_lower = text_b.lower()

        # Check each contradiction pattern
        for term1, term2 in CONTRADICTION_PATTERNS:
            # Check if A has term1 and B has term2
            if term1 in text_a_lower and term2 in text_b_lower:
                conflict = Conflict(
                    conflict_id="",
                    conflict_type=ConflictType.BEHAVIORAL_CONTRADICTION.value,
                    severity=ConflictSeverity.BLOCKING.value,
                    improvement_a=imp_a,
                    improvement_b=imp_b,
                    description=f"Behavioral contradiction: '{term1}' in {imp_a} conflicts with '{term2}' in {imp_b}",
                    evidence=[
                        f"{imp_a} uses '{term1}'",
                        f"{imp_b} uses '{term2}'",
                    ],
                    resolution_suggestions=self._get_resolution_suggestions(
                        ConflictType.BEHAVIORAL_CONTRADICTION
                    ),
                )
                conflicts.append(conflict)

            # Check the reverse
            if term2 in text_a_lower and term1 in text_b_lower:
                conflict = Conflict(
                    conflict_id="",
                    conflict_type=ConflictType.BEHAVIORAL_CONTRADICTION.value,
                    severity=ConflictSeverity.BLOCKING.value,
                    improvement_a=imp_a,
                    improvement_b=imp_b,
                    description=f"Behavioral contradiction: '{term2}' in {imp_a} conflicts with '{term1}' in {imp_b}",
                    evidence=[
                        f"{imp_a} uses '{term2}'",
                        f"{imp_b} uses '{term1}'",
                    ],
                    resolution_suggestions=self._get_resolution_suggestions(
                        ConflictType.BEHAVIORAL_CONTRADICTION
                    ),
                )
                conflicts.append(conflict)

        return conflicts

    def _detect_scope_overlaps(
        self,
        imp_a: str,
        imp_b: str,
        scope_a: ImprovementScope,
        scope_b: ImprovementScope
    ) -> list[Conflict]:
        """Detect scope overlaps between improvements."""
        conflicts = []

        # Check behavior overlap
        behaviors_a = scope_a.get_normalized_behaviors()
        behaviors_b = scope_b.get_normalized_behaviors()
        behavior_overlap = behaviors_a & behaviors_b

        # Check domain overlap
        domains_a = scope_a.get_normalized_domains()
        domains_b = scope_b.get_normalized_domains()
        domain_overlap = domains_a & domains_b

        # If there's both behavior AND domain overlap, it's a significant scope overlap
        if behavior_overlap and domain_overlap:
            conflict = Conflict(
                conflict_id="",
                conflict_type=ConflictType.SCOPE_OVERLAP.value,
                severity=ConflictSeverity.WARNING.value,
                improvement_a=imp_a,
                improvement_b=imp_b,
                description=f"Scope overlap: both affect {', '.join(behavior_overlap)} in domains {', '.join(domain_overlap)}",
                evidence=[
                    f"Shared behaviors: {', '.join(behavior_overlap)}",
                    f"Shared domains: {', '.join(domain_overlap)}",
                ],
                resolution_suggestions=self._get_resolution_suggestions(
                    ConflictType.SCOPE_OVERLAP
                ),
            )
            conflicts.append(conflict)

        # Check if one's exclusions overlap with other's applicability
        if scope_a.exclusions and scope_b.domain_applicability:
            exclusion_overlap = set(e.lower() for e in scope_a.exclusions) & \
                              set(d.lower() for d in scope_b.domain_applicability)
            if exclusion_overlap:
                conflict = Conflict(
                    conflict_id="",
                    conflict_type=ConflictType.SCOPE_OVERLAP.value,
                    severity=ConflictSeverity.INFO.value,
                    improvement_a=imp_a,
                    improvement_b=imp_b,
                    description=f"Scope boundary: {imp_a} excludes {', '.join(exclusion_overlap)} where {imp_b} applies",
                    evidence=[
                        f"{imp_a} exclusions: {', '.join(scope_a.exclusions)}",
                        f"{imp_b} applies to: {', '.join(scope_b.domain_applicability)}",
                    ],
                    resolution_suggestions=self._get_resolution_suggestions(
                        ConflictType.SCOPE_OVERLAP
                    ),
                )
                conflicts.append(conflict)

        return conflicts

    def _detect_dependency_conflicts(
        self,
        imp_a: str,
        imp_b: str,
        scope_a: ImprovementScope,
        scope_b: ImprovementScope
    ) -> list[Conflict]:
        """Detect dependency conflicts (A's preconditions vs B's effects)."""
        conflicts = []

        # Check if A's preconditions are negated by B's effects
        for precond in scope_a.preconditions:
            precond_lower = precond.lower()
            for effect in scope_b.effects:
                effect_lower = effect.lower()

                # Check for direct negation
                if self._are_contradictory(precond_lower, effect_lower):
                    conflict = Conflict(
                        conflict_id="",
                        conflict_type=ConflictType.DEPENDENCY_CONFLICT.value,
                        severity=ConflictSeverity.BLOCKING.value,
                        improvement_a=imp_a,
                        improvement_b=imp_b,
                        description=f"Dependency conflict: {imp_a} requires '{precond}' but {imp_b} effect is '{effect}'",
                        evidence=[
                            f"{imp_a} precondition: {precond}",
                            f"{imp_b} effect: {effect}",
                        ],
                        resolution_suggestions=self._get_resolution_suggestions(
                            ConflictType.DEPENDENCY_CONFLICT
                        ),
                    )
                    conflicts.append(conflict)

        # Check the reverse
        for precond in scope_b.preconditions:
            precond_lower = precond.lower()
            for effect in scope_a.effects:
                effect_lower = effect.lower()

                if self._are_contradictory(precond_lower, effect_lower):
                    conflict = Conflict(
                        conflict_id="",
                        conflict_type=ConflictType.DEPENDENCY_CONFLICT.value,
                        severity=ConflictSeverity.BLOCKING.value,
                        improvement_a=imp_a,
                        improvement_b=imp_b,
                        description=f"Dependency conflict: {imp_b} requires '{precond}' but {imp_a} effect is '{effect}'",
                        evidence=[
                            f"{imp_b} precondition: {precond}",
                            f"{imp_a} effect: {effect}",
                        ],
                        resolution_suggestions=self._get_resolution_suggestions(
                            ConflictType.DEPENDENCY_CONFLICT
                        ),
                    )
                    conflicts.append(conflict)

        return conflicts

    def _detect_resource_contentions(
        self,
        imp_a: str,
        imp_b: str,
        scope_a: ImprovementScope,
        scope_b: ImprovementScope
    ) -> list[Conflict]:
        """Detect resource contentions between improvements."""
        conflicts = []

        resources_a = {(r.get("type", ""), r.get("name", "")) for r in scope_a.resources_used}
        resources_b = {(r.get("type", ""), r.get("name", "")) for r in scope_b.resources_used}

        shared_resources = resources_a & resources_b
        shared_resources = {r for r in shared_resources if r[0] and r[1]}  # Filter empty

        if shared_resources:
            for resource in shared_resources:
                resource_type, resource_name = resource
                conflict = Conflict(
                    conflict_id="",
                    conflict_type=ConflictType.RESOURCE_CONTENTION.value,
                    severity=ConflictSeverity.WARNING.value,
                    improvement_a=imp_a,
                    improvement_b=imp_b,
                    description=f"Resource contention: both access {resource_type} '{resource_name}'",
                    evidence=[
                        f"Resource type: {resource_type}",
                        f"Resource name: {resource_name}",
                    ],
                    resolution_suggestions=self._get_resolution_suggestions(
                        ConflictType.RESOURCE_CONTENTION
                    ),
                )
                conflicts.append(conflict)

        return conflicts

    def _are_contradictory(self, text1: str, text2: str) -> bool:
        """Check if two text strings express contradictory concepts."""
        negation_patterns = [
            ("enable", "disable"),
            ("enabled", "disabled"),
            ("add", "remove"),
            ("require", "skip"),
            ("required", "optional"),
            ("always", "never"),
            ("with", "without"),
        ]

        for pos, neg in negation_patterns:
            # Check if one has positive and other has negative form
            if pos in text1 and neg in text2:
                # Compare the subject of the operation
                subject1 = text1.replace(pos, "").strip()
                subject2 = text2.replace(neg, "").strip()
                if self._text_similarity(subject1, subject2) > 0.6:
                    return True
            if neg in text1 and pos in text2:
                subject1 = text1.replace(neg, "").strip()
                subject2 = text2.replace(pos, "").strip()
                if self._text_similarity(subject1, subject2) > 0.6:
                    return True

        return False

    def _text_similarity(self, text1: str, text2: str) -> float:
        """Calculate text similarity using SequenceMatcher."""
        return SequenceMatcher(None, text1, text2).ratio()

    def _get_resolution_suggestions(
        self,
        conflict_type: ConflictType
    ) -> list[dict[str, str]]:
        """Get resolution suggestions for a conflict type."""
        suggestions: list[dict[str, str]] = []

        if conflict_type == ConflictType.BEHAVIORAL_CONTRADICTION:
            suggestions = [
                {
                    "strategy": ResolutionStrategy.CONDITIONAL_APPLICATION.value,
                    "description": "Apply each improvement conditionally based on specific criteria (e.g., endpoint type, request source)",
                },
                {
                    "strategy": ResolutionStrategy.PRIORITIZE.value,
                    "description": "Choose one behavior as the default and use the other only when explicitly requested",
                },
                {
                    "strategy": ResolutionStrategy.DOMAIN_SPLIT.value,
                    "description": "Apply different behaviors to different domains (e.g., retry for web, fail-fast for batch)",
                },
            ]

        elif conflict_type == ConflictType.SCOPE_OVERLAP:
            suggestions = [
                {
                    "strategy": ResolutionStrategy.SCOPE_NARROWING.value,
                    "description": "Narrow the scope of one or both improvements to reduce overlap",
                },
                {
                    "strategy": ResolutionStrategy.MERGE.value,
                    "description": "Merge both improvements into a single, unified improvement",
                },
                {
                    "strategy": ResolutionStrategy.DOMAIN_SPLIT.value,
                    "description": "Split application by domain to avoid overlap",
                },
            ]

        elif conflict_type == ConflictType.DEPENDENCY_CONFLICT:
            suggestions = [
                {
                    "strategy": ResolutionStrategy.CONDITIONAL_APPLICATION.value,
                    "description": "Apply improvements in a specific order or based on system state",
                },
                {
                    "strategy": ResolutionStrategy.SCOPE_NARROWING.value,
                    "description": "Modify effects or preconditions to remove the conflict",
                },
                {
                    "strategy": ResolutionStrategy.MANUAL_REVIEW.value,
                    "description": "Requires human decision on which improvement takes precedence",
                },
            ]

        elif conflict_type == ConflictType.RESOURCE_CONTENTION:
            suggestions = [
                {
                    "strategy": ResolutionStrategy.CONDITIONAL_APPLICATION.value,
                    "description": "Apply improvements at different times or with locking mechanism",
                },
                {
                    "strategy": ResolutionStrategy.MERGE.value,
                    "description": "Merge improvements to coordinate resource access",
                },
                {
                    "strategy": ResolutionStrategy.SCOPE_NARROWING.value,
                    "description": "Modify one improvement to use a different resource",
                },
            ]

        return suggestions

    # =========================================================================
    # Conflict Analysis
    # =========================================================================

    def analyze_improvement(self, improvement_id: str) -> ConflictReport:
        """Analyze an improvement for conflicts with all other improvements.

        Args:
            improvement_id: ID of the improvement to analyze

        Returns:
            ConflictReport with all detected conflicts
        """
        all_conflicts: list[Conflict] = []

        # Get all other proposals
        all_proposals = self._get_all_proposals()

        for other_id in all_proposals:
            if other_id == improvement_id:
                continue

            # Check if the other proposal is in an active state
            other = all_proposals[other_id]
            status = other.get("status", "proposed")
            if status in ("rejected", "archived"):
                continue

            # Detect conflicts with this proposal
            conflicts = self.detect_conflicts(improvement_id, other_id)
            all_conflicts.extend(conflicts)

        # Build report
        blocking = [c for c in all_conflicts if c.is_blocking()]
        warnings = [c for c in all_conflicts if c.severity == ConflictSeverity.WARNING.value]

        report = ConflictReport(
            improvement_id=improvement_id,
            total_conflicts=len(all_conflicts),
            blocking_conflicts=len(blocking),
            warning_conflicts=len(warnings),
            conflicts=all_conflicts,
            can_promote=len(blocking) == 0,
            blocking_reasons=[c.description for c in blocking],
        )

        return report

    def get_conflict(self, conflict_id: str) -> Conflict | None:
        """Get a specific conflict by ID."""
        return self._conflicts.get(conflict_id)

    def resolve_conflict(
        self,
        conflict_id: str,
        resolution_notes: str
    ) -> Conflict | None:
        """Mark a conflict as resolved.

        Args:
            conflict_id: ID of the conflict to resolve
            resolution_notes: Notes describing how it was resolved

        Returns:
            Updated Conflict or None if not found
        """
        conflict = self._conflicts.get(conflict_id)
        if not conflict:
            return None

        conflict.resolved = True
        conflict.resolution_notes = resolution_notes
        self._save_conflicts()

        return conflict

    def list_conflicts(
        self,
        improvement_id: str | None = None,
        unresolved_only: bool = True,
        conflict_type: str | None = None
    ) -> list[Conflict]:
        """List conflicts with optional filters.

        Args:
            improvement_id: Filter to conflicts involving this improvement
            unresolved_only: Only return unresolved conflicts
            conflict_type: Filter by conflict type

        Returns:
            List of matching Conflict objects
        """
        conflicts = list(self._conflicts.values())

        if improvement_id:
            conflicts = [
                c for c in conflicts
                if c.improvement_a == improvement_id or c.improvement_b == improvement_id
            ]

        if unresolved_only:
            conflicts = [c for c in conflicts if not c.resolved]

        if conflict_type:
            conflicts = [c for c in conflicts if c.conflict_type == conflict_type]

        # Sort by severity (blocking first) then detection time
        severity_order = {
            ConflictSeverity.BLOCKING.value: 0,
            ConflictSeverity.WARNING.value: 1,
            ConflictSeverity.INFO.value: 2,
        }
        conflicts.sort(key=lambda c: (severity_order.get(c.severity, 99), c.detected_at))

        return conflicts

    def can_promote(self, improvement_id: str) -> tuple[bool, list[str]]:
        """Check if an improvement can be promoted.

        Args:
            improvement_id: ID of the improvement to check

        Returns:
            Tuple of (can_promote, list of blocking reasons)
        """
        report = self.analyze_improvement(improvement_id)
        return report.can_promote, report.blocking_reasons


# ============================================================================
# CLI Interface
# ============================================================================

def create_parser() -> argparse.ArgumentParser:
    """Create argument parser for CLI."""
    parser = argparse.ArgumentParser(
        description="Conflict Detection System for claude-loop Improvements",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Check conflicts for a specific improvement
    python lib/conflict-detector.py conflicts IMP-12345678

    # Show scope for an improvement
    python lib/conflict-detector.py scope IMP-12345678

    # Add scope declaration
    python lib/conflict-detector.py scope add IMP-12345678 \\
        --behaviors "error handling" "retry logic" \\
        --domains "web_backend" \\
        --effects "disables retry"

    # Infer scope from proposal content
    python lib/conflict-detector.py scope infer IMP-12345678

    # Check if improvement can be promoted
    python lib/conflict-detector.py can-promote IMP-12345678

    # List all unresolved conflicts
    python lib/conflict-detector.py list

    # Resolve a conflict
    python lib/conflict-detector.py resolve CONF-ABCD1234 --notes "Applied domain split"
"""
    )

    # Global options
    parser.add_argument(
        "--base-dir", "-d",
        type=Path,
        default=Path.cwd(),
        help="Base directory for files (default: current directory)"
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output as JSON"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose output"
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # conflicts command
    conflicts_parser = subparsers.add_parser("conflicts", help="Check conflicts for an improvement")
    conflicts_parser.add_argument("id", help="Improvement ID to analyze")

    # scope command with subcommands
    scope_parser = subparsers.add_parser("scope", help="Manage scope declarations")
    scope_subparsers = scope_parser.add_subparsers(dest="scope_command", help="Scope commands")

    # scope show
    scope_show = scope_subparsers.add_parser("show", help="Show scope for an improvement")
    scope_show.add_argument("id", help="Improvement ID")

    # scope add
    scope_add = scope_subparsers.add_parser("add", help="Add/update scope declaration")
    scope_add.add_argument("id", help="Improvement ID")
    scope_add.add_argument("--preconditions", nargs="+", default=[], help="Preconditions")
    scope_add.add_argument("--behaviors", nargs="+", default=[], help="Affected behaviors")
    scope_add.add_argument("--domains", nargs="+", default=[], help="Domain applicability")
    scope_add.add_argument("--exclusions", nargs="+", default=[], help="Exclusions")
    scope_add.add_argument("--effects", nargs="+", default=[], help="Effects")

    # scope infer
    scope_infer = scope_subparsers.add_parser("infer", help="Infer scope from proposal")
    scope_infer.add_argument("id", help="Improvement ID")
    scope_infer.add_argument("--save", action="store_true", help="Save inferred scope")

    # scope list
    scope_list = scope_subparsers.add_parser("list", help="List all scopes")
    scope_list.add_argument("--incomplete", action="store_true", help="Only incomplete scopes")

    # can-promote command
    promote_parser = subparsers.add_parser("can-promote", help="Check if improvement can be promoted")
    promote_parser.add_argument("id", help="Improvement ID to check")

    # list command
    list_parser = subparsers.add_parser("list", help="List conflicts")
    list_parser.add_argument("--improvement", help="Filter by improvement ID")
    list_parser.add_argument("--all", action="store_true", help="Include resolved conflicts")
    list_parser.add_argument(
        "--type",
        choices=[t.value for t in ConflictType],
        help="Filter by conflict type"
    )

    # resolve command
    resolve_parser = subparsers.add_parser("resolve", help="Resolve a conflict")
    resolve_parser.add_argument("id", help="Conflict ID to resolve")
    resolve_parser.add_argument("--notes", "-n", required=True, help="Resolution notes")

    # detect command (for manual detection between two specific improvements)
    detect_parser = subparsers.add_parser("detect", help="Detect conflicts between two improvements")
    detect_parser.add_argument("id1", help="First improvement ID")
    detect_parser.add_argument("id2", help="Second improvement ID")

    return parser


def format_scope(scope: ImprovementScope, verbose: bool = False) -> str:
    """Format scope for display."""
    lines = [
        f"=== Scope: {scope.improvement_id} ===",
        "",
        f"Complete: {'Yes' if scope.is_complete() else 'No - needs more detail'}",
        "",
    ]

    if scope.preconditions:
        lines.append("Preconditions:")
        for p in scope.preconditions:
            lines.append(f"  - {p}")
        lines.append("")

    if scope.affected_behaviors:
        lines.append("Affected Behaviors:")
        for b in scope.affected_behaviors:
            lines.append(f"  - {b}")
        lines.append("")

    if scope.domain_applicability:
        lines.append("Domain Applicability:")
        for d in scope.domain_applicability:
            lines.append(f"  - {d}")
        lines.append("")

    if scope.exclusions:
        lines.append("Exclusions:")
        for e in scope.exclusions:
            lines.append(f"  - {e}")
        lines.append("")

    if scope.resources_used:
        lines.append("Resources Used:")
        for r in scope.resources_used:
            lines.append(f"  - {r.get('type', 'unknown')}: {r.get('name', 'unknown')}")
        lines.append("")

    if scope.effects:
        lines.append("Effects:")
        for e in scope.effects:
            lines.append(f"  - {e}")
        lines.append("")

    if verbose:
        lines.append(f"Created: {scope.created_at}")
        lines.append(f"Updated: {scope.updated_at}")

    return "\n".join(lines)


def format_conflict(conflict: Conflict, verbose: bool = False) -> str:
    """Format conflict for display."""
    severity_icons = {
        ConflictSeverity.BLOCKING.value: "[BLOCKING]",
        ConflictSeverity.WARNING.value: "[WARNING]",
        ConflictSeverity.INFO.value: "[INFO]",
    }

    lines = [
        f"=== Conflict: {conflict.conflict_id} ===",
        "",
        f"Type: {conflict.conflict_type}",
        f"Severity: {severity_icons.get(conflict.severity, conflict.severity)}",
        f"Status: {'RESOLVED' if conflict.resolved else 'UNRESOLVED'}",
        "",
        f"Between: {conflict.improvement_a} <-> {conflict.improvement_b}",
        "",
        f"Description: {conflict.description}",
        "",
    ]

    if conflict.evidence:
        lines.append("Evidence:")
        for e in conflict.evidence:
            lines.append(f"  - {e}")
        lines.append("")

    if conflict.resolution_suggestions:
        lines.append("Resolution Suggestions:")
        for s in conflict.resolution_suggestions:
            lines.append(f"  [{s['strategy']}] {s['description']}")
        lines.append("")

    if conflict.resolved:
        lines.append(f"Resolution Notes: {conflict.resolution_notes}")
        lines.append("")

    if verbose:
        lines.append(f"Detected: {conflict.detected_at}")

    return "\n".join(lines)


def format_report(report: ConflictReport, verbose: bool = False) -> str:
    """Format conflict report for display."""
    lines = [
        f"=== Conflict Report: {report.improvement_id} ===",
        "",
        f"Total Conflicts: {report.total_conflicts}",
        f"  Blocking: {report.blocking_conflicts}",
        f"  Warnings: {report.warning_conflicts}",
        "",
        f"Can Promote: {'YES' if report.can_promote else 'NO'}",
        "",
    ]

    if report.blocking_reasons:
        lines.append("Blocking Reasons:")
        for r in report.blocking_reasons:
            lines.append(f"  ! {r}")
        lines.append("")

    if report.conflicts and verbose:
        lines.append("--- Conflicts ---")
        for conflict in report.conflicts:
            lines.append("")
            lines.append(format_conflict(conflict, verbose=False))

    lines.append(f"Generated: {report.generated_at}")

    return "\n".join(lines)


def main() -> int:
    """Main entry point for CLI."""
    parser = create_parser()
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    detector = ConflictDetector(base_dir=args.base_dir)

    if args.command == "conflicts":
        report = detector.analyze_improvement(args.id)

        if args.json:
            print(json.dumps(report.to_dict(), indent=2))
        else:
            print(format_report(report, verbose=args.verbose))

        # Exit code: 2 if blocking conflicts, 1 if any conflicts, 0 if none
        if report.blocking_conflicts > 0:
            return 2
        elif report.total_conflicts > 0:
            return 1
        return 0

    elif args.command == "scope":
        if not args.scope_command:
            parser.parse_args(["scope", "--help"])
            return 1

        if args.scope_command == "show":
            scope = detector.get_scope(args.id)
            if not scope:
                # Try to infer
                scope = detector.infer_scope(args.id)
                print("Note: No declared scope found. Showing inferred scope:\n")

            if args.json:
                print(json.dumps(scope.to_dict(), indent=2))
            else:
                print(format_scope(scope, verbose=args.verbose))
            return 0

        elif args.scope_command == "add":
            scope = detector.set_scope(
                improvement_id=args.id,
                preconditions=args.preconditions,
                affected_behaviors=args.behaviors,
                domain_applicability=args.domains,
                exclusions=args.exclusions,
                effects=args.effects,
            )

            if args.json:
                print(json.dumps(scope.to_dict(), indent=2))
            else:
                print(f"Scope updated for {args.id}")
                print()
                print(format_scope(scope, verbose=args.verbose))
            return 0

        elif args.scope_command == "infer":
            scope = detector.infer_scope(args.id)

            if args.save:
                detector.set_scope(
                    improvement_id=args.id,
                    preconditions=scope.preconditions,
                    affected_behaviors=scope.affected_behaviors,
                    domain_applicability=scope.domain_applicability,
                    exclusions=scope.exclusions,
                    effects=scope.effects,
                )
                print(f"Inferred scope saved for {args.id}")
                print()

            if args.json:
                print(json.dumps(scope.to_dict(), indent=2))
            else:
                print(format_scope(scope, verbose=args.verbose))
            return 0

        elif args.scope_command == "list":
            scopes = detector.list_scopes(incomplete_only=args.incomplete)

            if args.json:
                print(json.dumps([s.to_dict() for s in scopes], indent=2))
            else:
                if not scopes:
                    print("No scope declarations found.")
                else:
                    print(f"Found {len(scopes)} scope declaration(s):")
                    print()
                    for s in scopes:
                        complete = "+" if s.is_complete() else "-"
                        behaviors = ", ".join(s.affected_behaviors[:3]) or "none"
                        print(f"[{complete}] {s.improvement_id}: {behaviors}")
            return 0

    elif args.command == "can-promote":
        can_promote, reasons = detector.can_promote(args.id)

        if args.json:
            print(json.dumps({
                "improvement_id": args.id,
                "can_promote": can_promote,
                "blocking_reasons": reasons,
            }, indent=2))
        else:
            if can_promote:
                print(f"[OK] {args.id} can be promoted - no blocking conflicts")
            else:
                print(f"[BLOCKED] {args.id} cannot be promoted")
                print()
                print("Blocking reasons:")
                for r in reasons:
                    print(f"  ! {r}")

        return 0 if can_promote else 1

    elif args.command == "list":
        conflicts = detector.list_conflicts(
            improvement_id=args.improvement,
            unresolved_only=not args.all,
            conflict_type=args.type,
        )

        if args.json:
            print(json.dumps([c.to_dict() for c in conflicts], indent=2))
        else:
            if not conflicts:
                print("No conflicts found.")
            else:
                print(f"Found {len(conflicts)} conflict(s):")
                print()
                for c in conflicts:
                    status = "[R]" if c.resolved else "[U]"
                    severity = {
                        ConflictSeverity.BLOCKING.value: "!",
                        ConflictSeverity.WARNING.value: "~",
                        ConflictSeverity.INFO.value: "i",
                    }.get(c.severity, "?")
                    print(f"{status}[{severity}] {c.conflict_id}: {c.improvement_a} <-> {c.improvement_b}")
                    print(f"    {c.conflict_type}: {c.description[:60]}...")
                    print()
        return 0

    elif args.command == "resolve":
        conflict = detector.resolve_conflict(args.id, args.notes)

        if not conflict:
            print(f"Conflict {args.id} not found.", file=sys.stderr)
            return 1

        if args.json:
            print(json.dumps(conflict.to_dict(), indent=2))
        else:
            print(f"Conflict {args.id} marked as RESOLVED")
            print(f"Notes: {args.notes}")
        return 0

    elif args.command == "detect":
        conflicts = detector.detect_conflicts(args.id1, args.id2)

        if args.json:
            print(json.dumps([c.to_dict() for c in conflicts], indent=2))
        else:
            if not conflicts:
                print(f"No conflicts detected between {args.id1} and {args.id2}")
            else:
                print(f"Detected {len(conflicts)} conflict(s):")
                print()
                for c in conflicts:
                    print(format_conflict(c, verbose=args.verbose))
                    print()
        return 0 if not conflicts else 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
