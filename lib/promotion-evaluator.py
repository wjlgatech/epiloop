#!/usr/bin/env python3
"""
promotion-evaluator.py - Comprehensive Promotion Criteria Evaluator for claude-loop

Evaluates improvement proposals for promotion using multiple criteria beyond
just usage metrics. Includes maintenance cost, dependency risk, reversibility,
and conflict potential.

Key principle: Usage count is necessary but not sufficient. Promotion decisions
must consider long-term maintenance burden and system health.

Features:
- PromotionCriteria dataclass with comprehensive metrics
- Maintenance cost estimation based on complexity analysis
- Dependency risk assessment for external APIs/tools
- Reversibility score for clean removal capability
- Conflict potential detection with existing improvements
- Weighted scoring combining all factors
- CLI for evaluation and comparison

Usage:
    # Evaluate a single proposal
    python lib/promotion-evaluator.py evaluate IMP-12345678

    # Compare two proposals
    python lib/promotion-evaluator.py compare IMP-12345678 IMP-87654321

    # Show criteria thresholds
    python lib/promotion-evaluator.py thresholds
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

# Import from improvement-queue
try:
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "improvement_queue",
        Path(__file__).parent / "improvement-queue.py"
    )
    if spec and spec.loader:
        improvement_queue = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(improvement_queue)
        ImprovementProposal = improvement_queue.ImprovementProposal
        ImprovementQueueManager = improvement_queue.ImprovementQueueManager
except Exception:
    # Fallback: define minimal stub
    ImprovementProposal = None
    ImprovementQueueManager = None


# ============================================================================
# Constants
# ============================================================================

DEFAULT_QUEUE_FILE = ".claude-loop/improvement_queue.json"
DEFAULT_LIFECYCLE_FILE = ".claude-loop/improvement_lifecycle.json"
DEFAULT_EVALUATION_FILE = ".claude-loop/promotion_evaluations.json"
BASE_DIR = Path.cwd()

# Promotion thresholds (all must be met for automatic recommendation)
PROMOTION_THRESHOLDS = {
    "usage_count": 10,           # Minimum usage instances
    "success_rate": 0.80,        # Minimum success rate (80%)
    "domain_spread": 2,          # Minimum number of different domains
    "maintenance_cost": 0.70,    # Maximum maintenance cost (lower is better)
    "dependency_risk": 0.40,     # Maximum dependency risk (lower is better)
    "reversibility": 0.60,       # Minimum reversibility score (higher is better)
    "conflict_potential": 0.30,  # Maximum conflict potential (lower is better)
}

# Weight factors for combined score
SCORE_WEIGHTS = {
    "usage_count": 0.15,
    "success_rate": 0.20,
    "domain_spread": 0.10,
    "maintenance_cost": 0.20,
    "dependency_risk": 0.15,
    "reversibility": 0.10,
    "conflict_potential": 0.10,
}

# Keywords indicating external dependencies
EXTERNAL_DEPENDENCY_KEYWORDS = [
    # Cloud services
    "aws", "azure", "gcp", "google cloud", "firebase",
    # API patterns
    "api.github", "api.openai", "api.anthropic",
    "rest api", "graphql", "webhook",
    # Package managers (external)
    "npm install", "pip install", "cargo add",
    # External tools
    "docker", "kubernetes", "terraform",
    # Third-party services
    "stripe", "twilio", "sendgrid", "slack api",
]

# Keywords indicating unstable APIs
UNSTABLE_API_PATTERNS = [
    r"beta",
    r"alpha",
    r"experimental",
    r"deprecated",
    r"preview",
    r"unstable",
    r"v0\.",  # Version 0.x
    r"-rc\d+",  # Release candidates
]

# Keywords indicating complex code
COMPLEXITY_INDICATORS = [
    "async", "await", "threading", "multiprocessing",
    "recursion", "callback", "promise",
    "state machine", "event loop", "mutex", "semaphore",
    "regex", "parser", "compiler",
]


# ============================================================================
# Enums
# ============================================================================

class PromotionRecommendation(str, Enum):
    """Recommendation levels for promotion."""
    RECOMMEND = "recommend"           # All criteria met
    CONDITIONAL = "conditional"       # Most criteria met, minor concerns
    NOT_RECOMMENDED = "not_recommended"  # Significant criteria failures
    BLOCKED = "blocked"               # Critical issues prevent promotion

    def __str__(self) -> str:
        return self.value


class RiskLevel(str, Enum):
    """Risk assessment levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

    def __str__(self) -> str:
        return self.value


# ============================================================================
# Data Classes
# ============================================================================

@dataclass
class MaintenanceCostEstimate:
    """Breakdown of maintenance cost factors.

    Attributes:
        code_complexity: Complexity score (0-1, higher = more complex)
        external_dependencies: Number of external dependencies
        update_frequency_estimate: Estimated updates needed per year
        test_coverage_required: Estimated test coverage effort (0-1)
        documentation_burden: Documentation maintenance effort (0-1)
        total_score: Combined maintenance cost (0-1, lower is better)
        reasoning: Explanation of cost factors
    """
    code_complexity: float = 0.0
    external_dependencies: int = 0
    update_frequency_estimate: float = 0.0
    test_coverage_required: float = 0.0
    documentation_burden: float = 0.0
    total_score: float = 0.0
    reasoning: str = ""

    def calculate_total(self) -> float:
        """Calculate total maintenance cost score."""
        # Weight the factors
        complexity_weight = 0.35
        dependency_weight = 0.25
        update_weight = 0.20
        test_weight = 0.10
        doc_weight = 0.10

        # Normalize dependency count (assume 5+ is max complexity)
        dep_score = min(self.external_dependencies / 5, 1.0)

        # Normalize update frequency (assume 12+ updates/year is max)
        update_score = min(self.update_frequency_estimate / 12, 1.0)

        self.total_score = (
            self.code_complexity * complexity_weight +
            dep_score * dependency_weight +
            update_score * update_weight +
            self.test_coverage_required * test_weight +
            self.documentation_burden * doc_weight
        )
        return self.total_score

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class DependencyRiskAssessment:
    """Assessment of dependency-related risks.

    Attributes:
        external_apis: List of external APIs detected
        unstable_apis: List of potentially unstable APIs
        version_constraints: List of specific version requirements
        breaking_change_likelihood: Likelihood of breaking changes (0-1)
        total_score: Combined dependency risk (0-1, lower is better)
        risk_level: Categorical risk level
        reasoning: Explanation of risks
    """
    external_apis: list[str] = field(default_factory=list)
    unstable_apis: list[str] = field(default_factory=list)
    version_constraints: list[str] = field(default_factory=list)
    breaking_change_likelihood: float = 0.0
    total_score: float = 0.0
    risk_level: str = RiskLevel.LOW.value
    reasoning: str = ""

    def calculate_total(self) -> float:
        """Calculate total dependency risk score."""
        # Base score from number of external APIs (0.1 per API, max 0.5)
        api_score = min(len(self.external_apis) * 0.1, 0.5)

        # Unstable API penalty (0.15 per unstable API, max 0.45)
        unstable_score = min(len(self.unstable_apis) * 0.15, 0.45)

        # Version constraint risk (0.05 per constraint, max 0.2)
        version_score = min(len(self.version_constraints) * 0.05, 0.2)

        # Breaking change likelihood
        breaking_score = self.breaking_change_likelihood * 0.3

        self.total_score = min(api_score + unstable_score + version_score + breaking_score, 1.0)

        # Set risk level
        if self.total_score < 0.25:
            self.risk_level = RiskLevel.LOW.value
        elif self.total_score < 0.50:
            self.risk_level = RiskLevel.MEDIUM.value
        elif self.total_score < 0.75:
            self.risk_level = RiskLevel.HIGH.value
        else:
            self.risk_level = RiskLevel.CRITICAL.value

        return self.total_score

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ReversibilityAssessment:
    """Assessment of how cleanly an improvement can be removed.

    Attributes:
        isolated_changes: Are changes isolated or spread across codebase?
        state_modifications: Does it modify persistent state?
        api_changes: Does it change public APIs?
        database_migrations: Does it require database changes?
        config_changes: Does it modify configuration?
        total_score: Reversibility score (0-1, higher is better)
        reasoning: Explanation of reversibility factors
    """
    isolated_changes: bool = True
    state_modifications: bool = False
    api_changes: bool = False
    database_migrations: bool = False
    config_changes: bool = False
    total_score: float = 1.0
    reasoning: str = ""

    def calculate_total(self) -> float:
        """Calculate total reversibility score."""
        # Start with perfect reversibility
        score = 1.0

        # Penalties for various factors
        if not self.isolated_changes:
            score -= 0.25  # Spread changes are harder to revert

        if self.state_modifications:
            score -= 0.30  # State changes are risky

        if self.api_changes:
            score -= 0.20  # API changes may break consumers

        if self.database_migrations:
            score -= 0.35  # DB migrations are hardest to reverse

        if self.config_changes:
            score -= 0.10  # Config changes are usually easy to revert

        self.total_score = max(score, 0.0)
        return self.total_score

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ConflictAssessment:
    """Assessment of potential conflicts with existing improvements.

    Attributes:
        behavioral_conflicts: List of behavioral contradictions
        scope_overlaps: List of scope overlap issues
        resource_contentions: List of resource contention issues
        similar_improvements: List of similar existing improvements
        total_score: Conflict potential score (0-1, lower is better)
        blocking_conflicts: Conflicts that must be resolved before promotion
        reasoning: Explanation of conflicts
    """
    behavioral_conflicts: list[str] = field(default_factory=list)
    scope_overlaps: list[str] = field(default_factory=list)
    resource_contentions: list[str] = field(default_factory=list)
    similar_improvements: list[str] = field(default_factory=list)
    total_score: float = 0.0
    blocking_conflicts: list[str] = field(default_factory=list)
    reasoning: str = ""

    def calculate_total(self) -> float:
        """Calculate total conflict potential score."""
        # Behavioral conflicts are most serious (0.25 each, max 0.5)
        behavioral_score = min(len(self.behavioral_conflicts) * 0.25, 0.5)

        # Scope overlaps (0.15 each, max 0.3)
        overlap_score = min(len(self.scope_overlaps) * 0.15, 0.3)

        # Resource contentions (0.1 each, max 0.2)
        resource_score = min(len(self.resource_contentions) * 0.1, 0.2)

        # Similar improvements (0.05 each, max 0.15) - may indicate duplication
        similar_score = min(len(self.similar_improvements) * 0.05, 0.15)

        self.total_score = min(behavioral_score + overlap_score + resource_score + similar_score, 1.0)

        # Mark blocking conflicts
        self.blocking_conflicts = self.behavioral_conflicts.copy()
        if len(self.scope_overlaps) >= 3:
            self.blocking_conflicts.extend(self.scope_overlaps[:2])

        return self.total_score

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class PromotionCriteria:
    """Comprehensive promotion criteria for an improvement.

    Attributes:
        proposal_id: ID of the proposal being evaluated
        usage_count: Number of times this improvement was used
        success_rate: Success rate when applied (0-1)
        domain_spread: Number of different domains where used
        maintenance_cost: Maintenance cost assessment
        dependency_risk: Dependency risk assessment
        reversibility: Reversibility assessment
        conflict_potential: Conflict assessment
        combined_score: Weighted combination of all criteria (0-100)
        recommendation: Final promotion recommendation
        meets_all_thresholds: Whether all thresholds are met
        failing_criteria: List of criteria that failed thresholds
        evaluation_timestamp: When this evaluation was performed
        notes: Additional notes or concerns
    """
    proposal_id: str
    usage_count: int = 0
    success_rate: float = 0.0
    domain_spread: int = 0
    maintenance_cost: MaintenanceCostEstimate = field(default_factory=MaintenanceCostEstimate)
    dependency_risk: DependencyRiskAssessment = field(default_factory=DependencyRiskAssessment)
    reversibility: ReversibilityAssessment = field(default_factory=ReversibilityAssessment)
    conflict_potential: ConflictAssessment = field(default_factory=ConflictAssessment)
    combined_score: float = 0.0
    recommendation: str = PromotionRecommendation.NOT_RECOMMENDED.value
    meets_all_thresholds: bool = False
    failing_criteria: list[str] = field(default_factory=list)
    evaluation_timestamp: str = ""
    notes: str = ""

    def __post_init__(self):
        if not self.evaluation_timestamp:
            self.evaluation_timestamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    def calculate_combined_score(self) -> float:
        """Calculate weighted combined score.

        Returns:
            Combined score from 0-100
        """
        # Normalize usage_count (assume 20+ is excellent)
        usage_normalized = min(self.usage_count / 20, 1.0)

        # Domain spread normalized (assume 5+ is excellent)
        domain_normalized = min(self.domain_spread / 5, 1.0)

        # Maintenance cost is inverted (lower is better)
        maintenance_normalized = 1.0 - self.maintenance_cost.total_score

        # Dependency risk is inverted (lower is better)
        dependency_normalized = 1.0 - self.dependency_risk.total_score

        # Conflict potential is inverted (lower is better)
        conflict_normalized = 1.0 - self.conflict_potential.total_score

        # Calculate weighted score
        score = (
            usage_normalized * SCORE_WEIGHTS["usage_count"] +
            self.success_rate * SCORE_WEIGHTS["success_rate"] +
            domain_normalized * SCORE_WEIGHTS["domain_spread"] +
            maintenance_normalized * SCORE_WEIGHTS["maintenance_cost"] +
            dependency_normalized * SCORE_WEIGHTS["dependency_risk"] +
            self.reversibility.total_score * SCORE_WEIGHTS["reversibility"] +
            conflict_normalized * SCORE_WEIGHTS["conflict_potential"]
        )

        self.combined_score = round(score * 100, 1)
        return self.combined_score

    def check_thresholds(self) -> bool:
        """Check if all promotion thresholds are met.

        Returns:
            True if all thresholds are met
        """
        self.failing_criteria = []

        if self.usage_count < PROMOTION_THRESHOLDS["usage_count"]:
            self.failing_criteria.append(
                f"usage_count ({self.usage_count}) < {PROMOTION_THRESHOLDS['usage_count']}"
            )

        if self.success_rate < PROMOTION_THRESHOLDS["success_rate"]:
            self.failing_criteria.append(
                f"success_rate ({self.success_rate:.0%}) < {PROMOTION_THRESHOLDS['success_rate']:.0%}"
            )

        if self.domain_spread < PROMOTION_THRESHOLDS["domain_spread"]:
            self.failing_criteria.append(
                f"domain_spread ({self.domain_spread}) < {PROMOTION_THRESHOLDS['domain_spread']}"
            )

        if self.maintenance_cost.total_score > PROMOTION_THRESHOLDS["maintenance_cost"]:
            self.failing_criteria.append(
                f"maintenance_cost ({self.maintenance_cost.total_score:.2f}) > {PROMOTION_THRESHOLDS['maintenance_cost']}"
            )

        if self.dependency_risk.total_score > PROMOTION_THRESHOLDS["dependency_risk"]:
            self.failing_criteria.append(
                f"dependency_risk ({self.dependency_risk.total_score:.2f}) > {PROMOTION_THRESHOLDS['dependency_risk']}"
            )

        if self.reversibility.total_score < PROMOTION_THRESHOLDS["reversibility"]:
            self.failing_criteria.append(
                f"reversibility ({self.reversibility.total_score:.2f}) < {PROMOTION_THRESHOLDS['reversibility']}"
            )

        if self.conflict_potential.total_score > PROMOTION_THRESHOLDS["conflict_potential"]:
            self.failing_criteria.append(
                f"conflict_potential ({self.conflict_potential.total_score:.2f}) > {PROMOTION_THRESHOLDS['conflict_potential']}"
            )

        self.meets_all_thresholds = len(self.failing_criteria) == 0
        return self.meets_all_thresholds

    def determine_recommendation(self) -> str:
        """Determine promotion recommendation based on all criteria.

        Returns:
            Recommendation level
        """
        # Check for blocking issues
        if self.conflict_potential.blocking_conflicts:
            self.recommendation = PromotionRecommendation.BLOCKED.value
            return self.recommendation

        if self.dependency_risk.risk_level == RiskLevel.CRITICAL.value:
            self.recommendation = PromotionRecommendation.BLOCKED.value
            return self.recommendation

        # Check thresholds
        self.check_thresholds()

        if self.meets_all_thresholds:
            self.recommendation = PromotionRecommendation.RECOMMEND.value
        elif len(self.failing_criteria) <= 2:
            # Minor failures - conditional recommendation
            self.recommendation = PromotionRecommendation.CONDITIONAL.value
        else:
            self.recommendation = PromotionRecommendation.NOT_RECOMMENDED.value

        return self.recommendation

    def to_dict(self) -> dict[str, Any]:
        return {
            "proposal_id": self.proposal_id,
            "usage_count": self.usage_count,
            "success_rate": self.success_rate,
            "domain_spread": self.domain_spread,
            "maintenance_cost": self.maintenance_cost.to_dict(),
            "dependency_risk": self.dependency_risk.to_dict(),
            "reversibility": self.reversibility.to_dict(),
            "conflict_potential": self.conflict_potential.to_dict(),
            "combined_score": self.combined_score,
            "recommendation": self.recommendation,
            "meets_all_thresholds": self.meets_all_thresholds,
            "failing_criteria": self.failing_criteria,
            "evaluation_timestamp": self.evaluation_timestamp,
            "notes": self.notes,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PromotionCriteria":
        """Create from dictionary."""
        # Handle nested dataclasses
        maintenance = MaintenanceCostEstimate(**data.get("maintenance_cost", {}))
        dependency = DependencyRiskAssessment(**data.get("dependency_risk", {}))
        reversibility = ReversibilityAssessment(**data.get("reversibility", {}))
        conflict = ConflictAssessment(**data.get("conflict_potential", {}))

        return cls(
            proposal_id=data.get("proposal_id", ""),
            usage_count=data.get("usage_count", 0),
            success_rate=data.get("success_rate", 0.0),
            domain_spread=data.get("domain_spread", 0),
            maintenance_cost=maintenance,
            dependency_risk=dependency,
            reversibility=reversibility,
            conflict_potential=conflict,
            combined_score=data.get("combined_score", 0.0),
            recommendation=data.get("recommendation", ""),
            meets_all_thresholds=data.get("meets_all_thresholds", False),
            failing_criteria=data.get("failing_criteria", []),
            evaluation_timestamp=data.get("evaluation_timestamp", ""),
            notes=data.get("notes", ""),
        )


# ============================================================================
# Promotion Evaluator
# ============================================================================

class PromotionEvaluator:
    """Evaluates improvement proposals for promotion eligibility.

    Provides comprehensive analysis beyond usage metrics, including
    maintenance cost, dependency risk, reversibility, and conflict potential.
    """

    def __init__(
        self,
        queue_file: str = DEFAULT_QUEUE_FILE,
        lifecycle_file: str = DEFAULT_LIFECYCLE_FILE,
        evaluation_file: str = DEFAULT_EVALUATION_FILE,
        base_dir: Path | None = None
    ):
        self.base_dir = base_dir or BASE_DIR
        self.queue_file = self.base_dir / queue_file
        self.lifecycle_file = self.base_dir / lifecycle_file
        self.evaluation_file = self.base_dir / evaluation_file
        self._evaluations: dict[str, PromotionCriteria] = {}
        self._load_evaluations()

    def _ensure_dir(self) -> None:
        """Ensure directories exist."""
        self.evaluation_file.parent.mkdir(parents=True, exist_ok=True)

    def _load_evaluations(self) -> None:
        """Load cached evaluations from disk."""
        if self.evaluation_file.exists():
            try:
                data = json.loads(self.evaluation_file.read_text())
                self._evaluations = {
                    k: PromotionCriteria.from_dict(v)
                    for k, v in data.get("evaluations", {}).items()
                }
            except (json.JSONDecodeError, KeyError):
                self._evaluations = {}
        else:
            self._evaluations = {}

    def _save_evaluations(self) -> None:
        """Persist evaluations to disk."""
        self._ensure_dir()
        data = {
            "version": "1.0",
            "updated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "evaluations": {k: v.to_dict() for k, v in self._evaluations.items()}
        }
        self.evaluation_file.write_text(json.dumps(data, indent=2))

    def _get_proposal(self, proposal_id: str) -> Any | None:
        """Get proposal from queue."""
        if ImprovementQueueManager is None:
            return None
        try:
            manager = ImprovementQueueManager(base_dir=self.base_dir)
            return manager.get(proposal_id)
        except Exception:
            return None

    def _get_lifecycle_data(self, proposal_id: str) -> dict[str, Any]:
        """Get lifecycle data for a proposal."""
        if not self.lifecycle_file.exists():
            return {}
        try:
            data = json.loads(self.lifecycle_file.read_text())
            return data.get("improvements", {}).get(proposal_id, {})
        except (json.JSONDecodeError, KeyError):
            return {}

    def _get_all_proposals(self) -> list[Any]:
        """Get all proposals from queue."""
        if ImprovementQueueManager is None:
            return []
        try:
            manager = ImprovementQueueManager(base_dir=self.base_dir)
            return manager.list_proposals()
        except Exception:
            return []

    # =========================================================================
    # Cost and Risk Estimation Methods
    # =========================================================================

    def estimate_maintenance_cost(
        self,
        proposal: Any | None = None,
        solution_text: str = ""
    ) -> MaintenanceCostEstimate:
        """Estimate maintenance cost for an improvement.

        Args:
            proposal: ImprovementProposal to analyze
            solution_text: Raw solution text if proposal not available

        Returns:
            MaintenanceCostEstimate with breakdown
        """
        estimate = MaintenanceCostEstimate()
        text = solution_text or (proposal.proposed_solution if proposal else "")
        text_lower = text.lower()
        reasons = []

        # Code complexity analysis
        complexity_score = 0.0
        complexity_factors = []

        for indicator in COMPLEXITY_INDICATORS:
            if indicator.lower() in text_lower:
                complexity_score += 0.1
                complexity_factors.append(indicator)

        # Check for multiple languages/technologies
        tech_count = sum(1 for tech in ["python", "javascript", "typescript", "bash", "sql"]
                         if tech in text_lower)
        if tech_count > 1:
            complexity_score += 0.15 * (tech_count - 1)
            complexity_factors.append(f"{tech_count} technologies")

        estimate.code_complexity = min(complexity_score, 1.0)
        if complexity_factors:
            reasons.append(f"Complexity factors: {', '.join(complexity_factors)}")

        # External dependencies
        dep_count = 0
        detected_deps = []
        for dep in EXTERNAL_DEPENDENCY_KEYWORDS:
            if dep.lower() in text_lower:
                dep_count += 1
                detected_deps.append(dep)

        estimate.external_dependencies = dep_count
        if detected_deps:
            reasons.append(f"External dependencies: {', '.join(detected_deps[:5])}")

        # Update frequency estimate based on external dependencies
        if dep_count >= 3:
            estimate.update_frequency_estimate = 6.0  # 6 updates/year
            reasons.append("High update frequency expected due to external dependencies")
        elif dep_count >= 1:
            estimate.update_frequency_estimate = 3.0  # 3 updates/year
        else:
            estimate.update_frequency_estimate = 1.0  # Annual maintenance

        # Test coverage required
        if estimate.code_complexity > 0.5 or dep_count >= 2:
            estimate.test_coverage_required = 0.8
            reasons.append("High test coverage required")
        else:
            estimate.test_coverage_required = 0.4

        # Documentation burden
        if len(text) > 1000 or estimate.code_complexity > 0.5:
            estimate.documentation_burden = 0.6
            reasons.append("Significant documentation needed")
        else:
            estimate.documentation_burden = 0.3

        estimate.calculate_total()
        estimate.reasoning = "; ".join(reasons) if reasons else "Standard maintenance expected"

        return estimate

    def assess_dependency_risk(
        self,
        proposal: Any | None = None,
        solution_text: str = ""
    ) -> DependencyRiskAssessment:
        """Assess dependency-related risks.

        Args:
            proposal: ImprovementProposal to analyze
            solution_text: Raw solution text if proposal not available

        Returns:
            DependencyRiskAssessment with breakdown
        """
        assessment = DependencyRiskAssessment()
        text = solution_text or (proposal.proposed_solution if proposal else "")
        text_lower = text.lower()
        reasons = []

        # Detect external APIs
        for keyword in EXTERNAL_DEPENDENCY_KEYWORDS:
            if keyword.lower() in text_lower:
                assessment.external_apis.append(keyword)

        if assessment.external_apis:
            reasons.append(f"External APIs detected: {', '.join(assessment.external_apis[:3])}")

        # Detect unstable APIs
        for pattern in UNSTABLE_API_PATTERNS:
            matches = re.findall(pattern, text_lower)
            if matches:
                assessment.unstable_apis.extend(matches)

        if assessment.unstable_apis:
            reasons.append(f"Unstable API patterns: {', '.join(set(assessment.unstable_apis))}")

        # Detect version constraints
        version_pattern = r'[=<>]=?\s*[\d\.]+|~[\d\.]+'
        versions = re.findall(version_pattern, text)
        assessment.version_constraints = versions[:5]  # Limit to 5

        if assessment.version_constraints:
            reasons.append(f"Version constraints: {len(assessment.version_constraints)} found")

        # Breaking change likelihood
        if assessment.unstable_apis:
            assessment.breaking_change_likelihood = 0.7
            reasons.append("High breaking change likelihood due to unstable APIs")
        elif assessment.external_apis:
            assessment.breaking_change_likelihood = 0.3
            reasons.append("Moderate breaking change likelihood due to external APIs")
        else:
            assessment.breaking_change_likelihood = 0.1

        assessment.calculate_total()
        assessment.reasoning = "; ".join(reasons) if reasons else "Low dependency risk"

        return assessment

    def assess_reversibility(
        self,
        proposal: Any | None = None,
        solution_text: str = ""
    ) -> ReversibilityAssessment:
        """Assess how cleanly an improvement can be removed.

        Args:
            proposal: ImprovementProposal to analyze
            solution_text: Raw solution text if proposal not available

        Returns:
            ReversibilityAssessment with breakdown
        """
        assessment = ReversibilityAssessment()
        text = solution_text or (proposal.proposed_solution if proposal else "")
        text_lower = text.lower()
        reasons = []

        # Check for isolated changes
        spread_indicators = [
            "across", "multiple files", "codebase-wide",
            "refactor", "global", "throughout"
        ]
        if any(ind in text_lower for ind in spread_indicators):
            assessment.isolated_changes = False
            reasons.append("Changes appear spread across codebase")
        else:
            reasons.append("Changes appear isolated")

        # Check for state modifications
        state_indicators = [
            "database", "migration", "schema",
            "persistent", "storage", "cache",
            "session", "state"
        ]
        if any(ind in text_lower for ind in state_indicators):
            assessment.state_modifications = True
            reasons.append("Modifies persistent state")

        # Check for API changes
        api_indicators = [
            "api change", "endpoint", "breaking change",
            "public interface", "signature change"
        ]
        if any(ind in text_lower for ind in api_indicators):
            assessment.api_changes = True
            reasons.append("Changes public API")

        # Check for database migrations
        db_indicators = [
            "migration", "alter table", "add column",
            "schema change", "database update"
        ]
        if any(ind in text_lower for ind in db_indicators):
            assessment.database_migrations = True
            reasons.append("Requires database migration")

        # Check for config changes
        config_indicators = [
            "config", "settings", "environment",
            ".env", "configuration"
        ]
        if any(ind in text_lower for ind in config_indicators):
            assessment.config_changes = True
            reasons.append("Modifies configuration")

        assessment.calculate_total()
        assessment.reasoning = "; ".join(reasons)

        return assessment

    def assess_conflict_potential(
        self,
        proposal: Any | None = None,
        solution_text: str = "",
        problem_pattern: str = ""
    ) -> ConflictAssessment:
        """Assess potential conflicts with existing improvements.

        Args:
            proposal: ImprovementProposal to analyze
            solution_text: Raw solution text if proposal not available
            problem_pattern: Problem pattern text

        Returns:
            ConflictAssessment with breakdown
        """
        assessment = ConflictAssessment()
        text = solution_text or (proposal.proposed_solution if proposal else "")
        text_lower = text.lower()
        problem = problem_pattern or (proposal.problem_pattern if proposal else "")
        problem_lower = problem.lower()
        reasons = []

        # Get existing proposals
        existing_proposals = self._get_all_proposals()

        # Check for behavioral conflicts
        # Look for contradictory patterns
        contradiction_pairs = [
            ("always retry", "never retry"),
            ("synchronous", "asynchronous"),
            ("cache", "no-cache"),
            ("strict", "lenient"),
            ("fail fast", "retry"),
            ("validate", "skip validation"),
        ]

        for term1, term2 in contradiction_pairs:
            if term1 in text_lower:
                # Check if any existing proposal uses the opposite
                for existing in existing_proposals:
                    if existing and hasattr(existing, 'proposed_solution'):
                        existing_solution = existing.proposed_solution.lower()
                        if term2 in existing_solution:
                            conflict = f"'{term1}' conflicts with existing '{term2}'"
                            assessment.behavioral_conflicts.append(conflict)
                            reasons.append(conflict)
                            break

        # Check for scope overlaps with existing proposals
        if proposal and hasattr(proposal, 'affected_domains'):
            for existing in existing_proposals:
                if (existing and
                    hasattr(existing, 'affected_domains') and
                    hasattr(existing, 'id') and
                    existing.id != (proposal.id if hasattr(proposal, 'id') else None)):

                    overlap = set(proposal.affected_domains) & set(existing.affected_domains)
                    if overlap:
                        overlap_str = f"Scope overlap with {existing.id}: {', '.join(overlap)}"
                        assessment.scope_overlaps.append(overlap_str)

        if assessment.scope_overlaps:
            reasons.append(f"{len(assessment.scope_overlaps)} scope overlaps detected")

        # Check for similar improvements (potential duplication)
        proposal_id = getattr(proposal, 'id', None) if proposal else None
        for existing in existing_proposals:
            if (existing and
                hasattr(existing, 'problem_pattern') and
                hasattr(existing, 'id') and
                existing.id != proposal_id):

                existing_problem = existing.problem_pattern.lower()
                # Simple similarity check
                words_current = set(problem_lower.split())
                words_existing = set(existing_problem.split())
                if len(words_current) > 0:
                    overlap = len(words_current & words_existing) / len(words_current)
                    if overlap > 0.5:
                        assessment.similar_improvements.append(
                            f"Similar to {existing.id} ({overlap:.0%} overlap)"
                        )

        if assessment.similar_improvements:
            reasons.append(f"{len(assessment.similar_improvements)} similar improvements found")

        assessment.calculate_total()
        assessment.reasoning = "; ".join(reasons) if reasons else "No conflicts detected"

        return assessment

    # =========================================================================
    # Main Evaluation Method
    # =========================================================================

    def evaluate(
        self,
        proposal_id: str,
        usage_count: int | None = None,
        success_rate: float | None = None,
        domain_spread: int | None = None,
        force_refresh: bool = False
    ) -> PromotionCriteria:
        """Evaluate a proposal for promotion eligibility.

        Args:
            proposal_id: ID of the proposal to evaluate
            usage_count: Override usage count (otherwise from lifecycle)
            success_rate: Override success rate (otherwise from lifecycle)
            domain_spread: Override domain spread (otherwise from lifecycle)
            force_refresh: Force re-evaluation even if cached

        Returns:
            PromotionCriteria with full analysis
        """
        # Check cache
        if not force_refresh and proposal_id in self._evaluations:
            return self._evaluations[proposal_id]

        # Get proposal
        proposal = self._get_proposal(proposal_id)

        # Get lifecycle data
        lifecycle = self._get_lifecycle_data(proposal_id)

        # Create criteria
        criteria = PromotionCriteria(proposal_id=proposal_id)

        # Usage metrics (from lifecycle or overrides)
        criteria.usage_count = usage_count if usage_count is not None else lifecycle.get("usage_count", 0)
        criteria.success_rate = success_rate if success_rate is not None else lifecycle.get("success_rate", 0.0)
        criteria.domain_spread = domain_spread if domain_spread is not None else lifecycle.get("domain_spread", 0)

        # Get solution text for analysis
        solution_text = proposal.proposed_solution if proposal else ""
        problem_pattern = proposal.problem_pattern if proposal else ""

        # Run assessments
        criteria.maintenance_cost = self.estimate_maintenance_cost(proposal, solution_text)
        criteria.dependency_risk = self.assess_dependency_risk(proposal, solution_text)
        criteria.reversibility = self.assess_reversibility(proposal, solution_text)
        criteria.conflict_potential = self.assess_conflict_potential(
            proposal, solution_text, problem_pattern
        )

        # Calculate combined score and recommendation
        criteria.calculate_combined_score()
        criteria.determine_recommendation()

        # Cache result
        self._evaluations[proposal_id] = criteria
        self._save_evaluations()

        return criteria

    def compare(
        self,
        proposal_id_1: str,
        proposal_id_2: str
    ) -> dict[str, Any]:
        """Compare two proposals side-by-side.

        Args:
            proposal_id_1: First proposal ID
            proposal_id_2: Second proposal ID

        Returns:
            Comparison data with both evaluations and differences
        """
        eval1 = self.evaluate(proposal_id_1)
        eval2 = self.evaluate(proposal_id_2)

        # Calculate differences
        differences = {
            "usage_count": eval1.usage_count - eval2.usage_count,
            "success_rate": eval1.success_rate - eval2.success_rate,
            "domain_spread": eval1.domain_spread - eval2.domain_spread,
            "maintenance_cost": eval1.maintenance_cost.total_score - eval2.maintenance_cost.total_score,
            "dependency_risk": eval1.dependency_risk.total_score - eval2.dependency_risk.total_score,
            "reversibility": eval1.reversibility.total_score - eval2.reversibility.total_score,
            "conflict_potential": eval1.conflict_potential.total_score - eval2.conflict_potential.total_score,
            "combined_score": eval1.combined_score - eval2.combined_score,
        }

        # Determine winner for each criterion
        winners = {}
        for key, diff in differences.items():
            # For some metrics, lower is better
            lower_is_better = key in ["maintenance_cost", "dependency_risk", "conflict_potential"]
            if lower_is_better:
                winners[key] = proposal_id_1 if diff < 0 else (proposal_id_2 if diff > 0 else "tie")
            else:
                winners[key] = proposal_id_1 if diff > 0 else (proposal_id_2 if diff < 0 else "tie")

        # Overall winner
        wins_1 = sum(1 for w in winners.values() if w == proposal_id_1)
        wins_2 = sum(1 for w in winners.values() if w == proposal_id_2)

        return {
            "proposal_1": {
                "id": proposal_id_1,
                "evaluation": eval1.to_dict(),
                "wins": wins_1,
            },
            "proposal_2": {
                "id": proposal_id_2,
                "evaluation": eval2.to_dict(),
                "wins": wins_2,
            },
            "differences": differences,
            "winners": winners,
            "overall_winner": proposal_id_1 if wins_1 > wins_2 else (proposal_id_2 if wins_2 > wins_1 else "tie"),
            "comparison_timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        }

    def get_thresholds(self) -> dict[str, Any]:
        """Get current promotion thresholds and weights.

        Returns:
            Dictionary with thresholds and weights
        """
        return {
            "thresholds": PROMOTION_THRESHOLDS.copy(),
            "weights": SCORE_WEIGHTS.copy(),
            "description": {
                "usage_count": "Minimum number of times improvement was used",
                "success_rate": "Minimum success rate when applied (0-1)",
                "domain_spread": "Minimum number of different domains where used",
                "maintenance_cost": "Maximum maintenance cost score (0-1, lower is better)",
                "dependency_risk": "Maximum dependency risk score (0-1, lower is better)",
                "reversibility": "Minimum reversibility score (0-1, higher is better)",
                "conflict_potential": "Maximum conflict potential score (0-1, lower is better)",
            }
        }


# ============================================================================
# CLI Interface
# ============================================================================

def create_parser() -> argparse.ArgumentParser:
    """Create argument parser for CLI."""
    parser = argparse.ArgumentParser(
        description="Comprehensive Promotion Criteria Evaluator for claude-loop",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Evaluate a proposal
    python lib/promotion-evaluator.py evaluate IMP-12345678

    # Evaluate with custom metrics
    python lib/promotion-evaluator.py evaluate IMP-12345678 --usage 15 --success-rate 0.9

    # Compare two proposals
    python lib/promotion-evaluator.py compare IMP-12345678 IMP-87654321

    # Show thresholds
    python lib/promotion-evaluator.py thresholds
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

    # evaluate command
    eval_parser = subparsers.add_parser("evaluate", help="Evaluate a proposal")
    eval_parser.add_argument("id", help="Proposal ID to evaluate")
    eval_parser.add_argument("--usage", type=int, help="Override usage count")
    eval_parser.add_argument("--success-rate", type=float, help="Override success rate (0-1)")
    eval_parser.add_argument("--domain-spread", type=int, help="Override domain spread")
    eval_parser.add_argument("--refresh", action="store_true", help="Force re-evaluation")

    # compare command
    compare_parser = subparsers.add_parser("compare", help="Compare two proposals")
    compare_parser.add_argument("id1", help="First proposal ID")
    compare_parser.add_argument("id2", help="Second proposal ID")

    # thresholds command
    subparsers.add_parser("thresholds", help="Show promotion thresholds")

    # list command
    list_parser = subparsers.add_parser("list", help="List cached evaluations")
    list_parser.add_argument(
        "--recommendation",
        choices=["recommend", "conditional", "not_recommended", "blocked"],
        help="Filter by recommendation"
    )

    return parser


def format_evaluation(criteria: PromotionCriteria, verbose: bool = False) -> str:
    """Format evaluation for display."""
    lines = [
        f"=== Promotion Evaluation: {criteria.proposal_id} ===",
        "",
        f"RECOMMENDATION: {criteria.recommendation.upper()}",
        f"Combined Score: {criteria.combined_score}/100",
        f"Meets All Thresholds: {'Yes' if criteria.meets_all_thresholds else 'No'}",
        "",
        "--- Usage Metrics ---",
        f"  Usage Count: {criteria.usage_count}",
        f"  Success Rate: {criteria.success_rate:.1%}",
        f"  Domain Spread: {criteria.domain_spread}",
        "",
        "--- Maintenance Cost ---",
        f"  Total Score: {criteria.maintenance_cost.total_score:.2f} (lower is better)",
        f"  Code Complexity: {criteria.maintenance_cost.code_complexity:.2f}",
        f"  External Dependencies: {criteria.maintenance_cost.external_dependencies}",
        f"  Update Frequency Est.: {criteria.maintenance_cost.update_frequency_estimate:.1f}/year",
    ]

    if verbose and criteria.maintenance_cost.reasoning:
        lines.append(f"  Reasoning: {criteria.maintenance_cost.reasoning}")

    lines.extend([
        "",
        "--- Dependency Risk ---",
        f"  Total Score: {criteria.dependency_risk.total_score:.2f} (lower is better)",
        f"  Risk Level: {criteria.dependency_risk.risk_level.upper()}",
        f"  External APIs: {len(criteria.dependency_risk.external_apis)}",
        f"  Unstable APIs: {len(criteria.dependency_risk.unstable_apis)}",
    ])

    if verbose and criteria.dependency_risk.reasoning:
        lines.append(f"  Reasoning: {criteria.dependency_risk.reasoning}")

    lines.extend([
        "",
        "--- Reversibility ---",
        f"  Total Score: {criteria.reversibility.total_score:.2f} (higher is better)",
        f"  Isolated Changes: {'Yes' if criteria.reversibility.isolated_changes else 'No'}",
        f"  State Modifications: {'Yes' if criteria.reversibility.state_modifications else 'No'}",
        f"  API Changes: {'Yes' if criteria.reversibility.api_changes else 'No'}",
        f"  Database Migrations: {'Yes' if criteria.reversibility.database_migrations else 'No'}",
    ])

    if verbose and criteria.reversibility.reasoning:
        lines.append(f"  Reasoning: {criteria.reversibility.reasoning}")

    lines.extend([
        "",
        "--- Conflict Potential ---",
        f"  Total Score: {criteria.conflict_potential.total_score:.2f} (lower is better)",
        f"  Behavioral Conflicts: {len(criteria.conflict_potential.behavioral_conflicts)}",
        f"  Scope Overlaps: {len(criteria.conflict_potential.scope_overlaps)}",
        f"  Similar Improvements: {len(criteria.conflict_potential.similar_improvements)}",
    ])

    if verbose and criteria.conflict_potential.reasoning:
        lines.append(f"  Reasoning: {criteria.conflict_potential.reasoning}")

    if criteria.failing_criteria:
        lines.extend([
            "",
            "--- Failing Criteria ---",
        ])
        for fc in criteria.failing_criteria:
            lines.append(f"  - {fc}")

    if criteria.conflict_potential.blocking_conflicts:
        lines.extend([
            "",
            "--- BLOCKING CONFLICTS ---",
        ])
        for bc in criteria.conflict_potential.blocking_conflicts:
            lines.append(f"  ! {bc}")

    if criteria.notes:
        lines.extend([
            "",
            f"Notes: {criteria.notes}"
        ])

    lines.extend([
        "",
        f"Evaluated: {criteria.evaluation_timestamp}"
    ])

    return "\n".join(lines)


def format_comparison(comparison: dict[str, Any], verbose: bool = False) -> str:
    """Format comparison for display.

    Args:
        comparison: Comparison data from evaluator.compare()
        verbose: Show additional details (reserved for future use)
    """
    _ = verbose  # Reserved for future use
    p1 = comparison["proposal_1"]
    p2 = comparison["proposal_2"]
    winners = comparison["winners"]

    lines = [
        f"=== Comparison: {p1['id']} vs {p2['id']} ===",
        "",
        f"Overall Winner: {comparison['overall_winner']}",
        f"  {p1['id']}: {p1['wins']} wins",
        f"  {p2['id']}: {p2['wins']} wins",
        "",
        "--- Criteria Comparison ---",
        "",
        f"{'Criterion':<20} {p1['id']:<15} {p2['id']:<15} {'Winner':<10}",
        "-" * 60,
    ]

    e1 = p1["evaluation"]
    e2 = p2["evaluation"]

    rows = [
        ("Usage Count", e1["usage_count"], e2["usage_count"], "usage_count"),
        ("Success Rate", f"{e1['success_rate']:.1%}", f"{e2['success_rate']:.1%}", "success_rate"),
        ("Domain Spread", e1["domain_spread"], e2["domain_spread"], "domain_spread"),
        ("Maintenance Cost", f"{e1['maintenance_cost']['total_score']:.2f}", f"{e2['maintenance_cost']['total_score']:.2f}", "maintenance_cost"),
        ("Dependency Risk", f"{e1['dependency_risk']['total_score']:.2f}", f"{e2['dependency_risk']['total_score']:.2f}", "dependency_risk"),
        ("Reversibility", f"{e1['reversibility']['total_score']:.2f}", f"{e2['reversibility']['total_score']:.2f}", "reversibility"),
        ("Conflict Potential", f"{e1['conflict_potential']['total_score']:.2f}", f"{e2['conflict_potential']['total_score']:.2f}", "conflict_potential"),
        ("Combined Score", f"{e1['combined_score']:.1f}", f"{e2['combined_score']:.1f}", "combined_score"),
    ]

    for label, v1, v2, key in rows:
        w = winners.get(key, "tie")
        w_display = p1["id"][:8] if w == p1["id"] else (p2["id"][:8] if w == p2["id"] else "tie")
        lines.append(f"{label:<20} {str(v1):<15} {str(v2):<15} {w_display:<10}")

    lines.extend([
        "",
        "--- Recommendations ---",
        f"  {p1['id']}: {e1['recommendation'].upper()}",
        f"  {p2['id']}: {e2['recommendation'].upper()}",
        "",
        f"Compared: {comparison['comparison_timestamp']}"
    ])

    return "\n".join(lines)


def main() -> int:
    """Main entry point for CLI."""
    parser = create_parser()
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    evaluator = PromotionEvaluator(base_dir=args.base_dir)

    if args.command == "evaluate":
        criteria = evaluator.evaluate(
            args.id,
            usage_count=args.usage,
            success_rate=args.success_rate,
            domain_spread=args.domain_spread,
            force_refresh=args.refresh
        )

        if args.json:
            print(json.dumps(criteria.to_dict(), indent=2))
        else:
            print(format_evaluation(criteria, verbose=args.verbose))

        # Exit code based on recommendation
        if criteria.recommendation == PromotionRecommendation.BLOCKED.value:
            return 2
        elif criteria.recommendation == PromotionRecommendation.NOT_RECOMMENDED.value:
            return 1
        return 0

    elif args.command == "compare":
        comparison = evaluator.compare(args.id1, args.id2)

        if args.json:
            print(json.dumps(comparison, indent=2))
        else:
            print(format_comparison(comparison, verbose=args.verbose))
        return 0

    elif args.command == "thresholds":
        thresholds = evaluator.get_thresholds()

        if args.json:
            print(json.dumps(thresholds, indent=2))
        else:
            print("=== Promotion Thresholds ===")
            print()
            print(f"{'Criterion':<20} {'Threshold':<15} {'Description'}")
            print("-" * 80)
            for key, value in thresholds["thresholds"].items():
                desc = thresholds["description"].get(key, "")
                print(f"{key:<20} {str(value):<15} {desc}")
            print()
            print("=== Score Weights ===")
            print()
            for key, weight in thresholds["weights"].items():
                print(f"  {key}: {weight:.0%}")
        return 0

    elif args.command == "list":
        evaluations = list(evaluator._evaluations.values())

        if args.recommendation:
            evaluations = [e for e in evaluations if e.recommendation == args.recommendation]

        # Sort by combined score
        evaluations.sort(key=lambda e: e.combined_score, reverse=True)

        if args.json:
            print(json.dumps([e.to_dict() for e in evaluations], indent=2))
        else:
            if not evaluations:
                print("No evaluations found.")
            else:
                print(f"Found {len(evaluations)} evaluation(s):")
                print()
                for e in evaluations:
                    status = "+" if e.meets_all_thresholds else "-"
                    print(f"[{status}] {e.proposal_id}: {e.recommendation.upper()} (Score: {e.combined_score})")
        return 0

    return 0


if __name__ == "__main__":
    sys.exit(main())
