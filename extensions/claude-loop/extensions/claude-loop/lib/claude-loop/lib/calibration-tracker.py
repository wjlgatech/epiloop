#!/usr/bin/env python3
"""
calibration-tracker.py - Calibration Tracking System for claude-loop

Measures system alignment with human decisions over time to determine
when autonomous promotion can be enabled.

Key principle: Earn autonomy through demonstrated calibration, not assumption.
- 95% agreement threshold over 50+ decisions
- 6-month minimum parallel evaluation period
- Blocking autonomous mode until threshold met

Data sources:
- .claude-loop/improvement_decisions.jsonl (improvement queue decisions)
- .claude-loop/cluster_decisions.jsonl (pattern clustering decisions)
- .claude-loop/promotion_decisions.jsonl (promotion decisions)

Usage:
    # Show current calibration status
    python lib/calibration-tracker.py status

    # Show calibration history
    python lib/calibration-tracker.py history --days 30

    # Show disagreements
    python lib/calibration-tracker.py disagreements

    # Check if autonomous mode is allowed
    python lib/calibration-tracker.py autonomous-check

    # Generate weekly report
    python lib/calibration-tracker.py weekly-report
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta, timezone
from enum import Enum
from pathlib import Path
from typing import Any


# ============================================================================
# Constants
# ============================================================================

BASE_DIR = Path.cwd()
CALIBRATION_DIR = ".claude-loop"

# Decision sources
IMPROVEMENT_DECISIONS_FILE = "improvement_decisions.jsonl"
CLUSTER_DECISIONS_FILE = "cluster_decisions.jsonl"
PROMOTION_DECISIONS_FILE = "promotion_decisions.jsonl"

# Calibration state
CALIBRATION_STATE_FILE = "calibration_state.json"
CALIBRATION_HISTORY_FILE = "calibration_history.jsonl"
WEEKLY_REPORTS_DIR = "calibration_reports"

# Thresholds for autonomous mode
AGREEMENT_THRESHOLD = 0.95  # 95% agreement required
MIN_DECISIONS = 50  # Minimum 50 decisions
MIN_EVALUATION_DAYS = 180  # 6 months minimum parallel evaluation
AUTONOMOUS_CHECK_INTERVAL_DAYS = 7  # Check weekly

# Decision type normalization
APPROVE_DECISIONS = {"approve", "recommend", "accept"}
REJECT_DECISIONS = {"reject", "not_recommended", "block", "blocked", "split", "modify"}


# ============================================================================
# Enums
# ============================================================================

class CalibrationStatus(str, Enum):
    """Overall calibration status."""
    CALIBRATING = "calibrating"  # Building history, not enough data
    ON_TRACK = "on_track"  # Meeting threshold, building history
    AT_RISK = "at_risk"  # Below threshold, may recover
    FAILING = "failing"  # Consistently below threshold
    QUALIFIED = "qualified"  # Meets all requirements for autonomous mode

    def __str__(self) -> str:
        return self.value


class DecisionSource(str, Enum):
    """Source of decision data."""
    IMPROVEMENT = "improvement"
    CLUSTERING = "clustering"
    PROMOTION = "promotion"

    def __str__(self) -> str:
        return self.value


# ============================================================================
# Data Classes
# ============================================================================

@dataclass
class NormalizedDecision:
    """A normalized decision from any source.

    Attributes:
        decision_id: Unique identifier (source_type:original_id)
        source: improvement/clustering/promotion
        original_id: Original decision/proposal ID
        system_recommendation: What the system recommended (approve/reject)
        human_decision: What the human decided (approve/reject)
        agreement: Whether system and human agreed
        timestamp: When the decision was made
        domain: Affected domain (if known)
        confidence: System confidence in recommendation (0.0-1.0)
        reasoning: Human's reasoning for the decision
        details: Additional context
    """
    decision_id: str
    source: str
    original_id: str
    system_recommendation: str
    human_decision: str
    agreement: bool
    timestamp: str
    domain: str = ""
    confidence: float = 0.5
    reasoning: str = ""
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "NormalizedDecision":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class CalibrationMetrics:
    """Comprehensive calibration metrics.

    Attributes:
        total_decisions: Total number of decisions analyzed
        agreement_count: Number of agreements
        agreement_rate: Overall agreement rate (0.0-1.0)
        false_positive_rate: System said approve, human rejected
        false_negative_rate: System said reject, human approved
        by_source: Metrics broken down by source
        by_domain: Metrics broken down by domain
        by_confidence: Metrics broken down by confidence level
        recent_trend: Recent agreement rate (last 30 days)
        evaluation_period_days: Days since first decision
        earliest_decision: Timestamp of first decision
        latest_decision: Timestamp of most recent decision
        status: Current calibration status
        autonomous_eligible: Whether autonomous mode is allowed
        blocking_reasons: Reasons blocking autonomous mode
    """
    total_decisions: int = 0
    agreement_count: int = 0
    agreement_rate: float = 0.0
    false_positive_rate: float = 0.0
    false_negative_rate: float = 0.0
    by_source: dict[str, dict[str, Any]] = field(default_factory=dict)
    by_domain: dict[str, dict[str, Any]] = field(default_factory=dict)
    by_confidence: dict[str, dict[str, Any]] = field(default_factory=dict)
    recent_trend: float = 0.0
    evaluation_period_days: int = 0
    earliest_decision: str = ""
    latest_decision: str = ""
    status: str = CalibrationStatus.CALIBRATING.value
    autonomous_eligible: bool = False
    blocking_reasons: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CalibrationMetrics":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class CalibrationSnapshot:
    """Point-in-time calibration snapshot for history tracking.

    Attributes:
        timestamp: When snapshot was taken
        total_decisions: Total decisions at this point
        agreement_rate: Agreement rate at this point
        false_positive_rate: FP rate at this point
        false_negative_rate: FN rate at this point
        recent_trend: Recent trend at this point
        status: Calibration status at this point
        autonomous_eligible: Whether autonomous was eligible
    """
    timestamp: str
    total_decisions: int
    agreement_rate: float
    false_positive_rate: float
    false_negative_rate: float
    recent_trend: float
    status: str
    autonomous_eligible: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CalibrationSnapshot":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class Disagreement:
    """A case where system and human disagreed.

    Attributes:
        decision: The normalized decision
        disagreement_type: false_positive or false_negative
        impact: Severity of disagreement (high/medium/low)
        resolution_notes: Notes on how this was resolved
        learned_from: Whether system has been updated
    """
    decision: NormalizedDecision
    disagreement_type: str
    impact: str = "medium"
    resolution_notes: str = ""
    learned_from: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "decision": self.decision.to_dict(),
            "disagreement_type": self.disagreement_type,
            "impact": self.impact,
            "resolution_notes": self.resolution_notes,
            "learned_from": self.learned_from
        }


@dataclass
class WeeklyReport:
    """Weekly calibration report.

    Attributes:
        report_id: Unique report identifier
        period_start: Start of reporting period
        period_end: End of reporting period
        generated_at: When report was generated
        metrics: Calibration metrics for the period
        new_decisions: Number of new decisions in period
        new_disagreements: List of new disagreements
        trend_change: Change in agreement rate from previous week
        recommendations: Action recommendations
        status_summary: Human-readable status summary
    """
    report_id: str
    period_start: str
    period_end: str
    generated_at: str
    metrics: CalibrationMetrics
    new_decisions: int = 0
    new_disagreements: list[Disagreement] = field(default_factory=list)
    trend_change: float = 0.0
    recommendations: list[str] = field(default_factory=list)
    status_summary: str = ""

    def __post_init__(self):
        if not self.report_id:
            hash_input = f"{self.period_start}:{self.period_end}"
            self.report_id = f"CAL-{hashlib.sha256(hash_input.encode()).hexdigest()[:8].upper()}"
        if not self.generated_at:
            self.generated_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    def to_dict(self) -> dict[str, Any]:
        return {
            "report_id": self.report_id,
            "period_start": self.period_start,
            "period_end": self.period_end,
            "generated_at": self.generated_at,
            "metrics": self.metrics.to_dict(),
            "new_decisions": self.new_decisions,
            "new_disagreements": [d.to_dict() for d in self.new_disagreements],
            "trend_change": self.trend_change,
            "recommendations": self.recommendations,
            "status_summary": self.status_summary
        }


# ============================================================================
# Calibration Tracker
# ============================================================================

class CalibrationTracker:
    """Tracks calibration between system recommendations and human decisions.

    Consolidates decisions from multiple sources and provides comprehensive
    alignment metrics to determine when autonomous mode can be enabled.
    """

    def __init__(self, base_dir: Path | None = None):
        self.base_dir = base_dir or BASE_DIR
        self.calibration_dir = self.base_dir / CALIBRATION_DIR
        self._decisions: list[NormalizedDecision] = []
        self._state: dict[str, Any] = {}
        self._load_state()

    def _ensure_dir(self) -> None:
        """Ensure calibration directory exists."""
        self.calibration_dir.mkdir(parents=True, exist_ok=True)
        (self.calibration_dir / WEEKLY_REPORTS_DIR).mkdir(exist_ok=True)

    def _load_state(self) -> None:
        """Load calibration state from disk."""
        state_file = self.calibration_dir / CALIBRATION_STATE_FILE
        if state_file.exists():
            try:
                self._state = json.loads(state_file.read_text())
            except json.JSONDecodeError:
                self._state = {}
        else:
            self._state = {
                "first_decision_at": None,
                "last_snapshot_at": None,
                "autonomous_enabled": False,
                "autonomous_enabled_at": None
            }

    def _save_state(self) -> None:
        """Persist calibration state to disk."""
        self._ensure_dir()
        state_file = self.calibration_dir / CALIBRATION_STATE_FILE
        self._state["last_updated"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        state_file.write_text(json.dumps(self._state, indent=2))

    # =========================================================================
    # Decision Loading
    # =========================================================================

    def _normalize_recommendation(self, rec: str) -> str:
        """Normalize a recommendation to approve/reject."""
        rec_lower = rec.lower().strip()
        if rec_lower in APPROVE_DECISIONS:
            return "approve"
        elif rec_lower in REJECT_DECISIONS:
            return "reject"
        # For pattern clustering low confidence -> system expects rejection/modification
        elif rec_lower in ("review", ""):
            return "review"  # Uncertain - not counted in FP/FN
        return rec_lower

    def _load_improvement_decisions(self) -> list[NormalizedDecision]:
        """Load decisions from improvement queue."""
        decisions = []
        decisions_file = self.calibration_dir / IMPROVEMENT_DECISIONS_FILE
        if not decisions_file.exists():
            return decisions

        for line in decisions_file.read_text().splitlines():
            if not line.strip():
                continue
            try:
                data = json.loads(line)
                sys_rec = self._normalize_recommendation(
                    data.get("system_recommendation", "")
                )
                human_dec = self._normalize_recommendation(
                    data.get("human_decision", data.get("decision_type", ""))
                )

                # Skip uncertain system recommendations for FP/FN calculation
                if sys_rec == "review":
                    agreement = True  # Uncertain recommendations don't count as disagreement
                else:
                    agreement = sys_rec == human_dec

                decision = NormalizedDecision(
                    decision_id=f"improvement:{data.get('proposal_id', '')}",
                    source=DecisionSource.IMPROVEMENT.value,
                    original_id=data.get("proposal_id", ""),
                    system_recommendation=sys_rec,
                    human_decision=human_dec,
                    agreement=agreement,
                    timestamp=data.get("timestamp", ""),
                    reasoning=data.get("reasoning", ""),
                    details=data
                )
                decisions.append(decision)
            except (json.JSONDecodeError, KeyError):
                continue

        return decisions

    def _load_cluster_decisions(self) -> list[NormalizedDecision]:
        """Load decisions from pattern clustering."""
        decisions = []
        decisions_file = self.calibration_dir / CLUSTER_DECISIONS_FILE
        if not decisions_file.exists():
            return decisions

        for line in decisions_file.read_text().splitlines():
            if not line.strip():
                continue
            try:
                data = json.loads(line)
                confidence = data.get("system_confidence", 0.5)
                human_dec = self._normalize_recommendation(
                    data.get("human_decision", data.get("decision_type", ""))
                )

                # For clustering, high confidence means system expects approval
                # Low confidence means system expects rejection/modification
                if confidence >= 0.8:
                    sys_rec = "approve"
                else:
                    sys_rec = "reject"

                agreement = data.get("agreement", sys_rec == human_dec)

                decision = NormalizedDecision(
                    decision_id=f"clustering:{data.get('cluster_id', '')}",
                    source=DecisionSource.CLUSTERING.value,
                    original_id=data.get("cluster_id", ""),
                    system_recommendation=sys_rec,
                    human_decision=human_dec,
                    agreement=agreement,
                    timestamp=data.get("timestamp", ""),
                    confidence=confidence,
                    reasoning=data.get("reasoning", ""),
                    details=data
                )
                decisions.append(decision)
            except (json.JSONDecodeError, KeyError):
                continue

        return decisions

    def _load_promotion_decisions(self) -> list[NormalizedDecision]:
        """Load decisions from promotion evaluations."""
        decisions = []
        decisions_file = self.calibration_dir / PROMOTION_DECISIONS_FILE
        if not decisions_file.exists():
            return decisions

        for line in decisions_file.read_text().splitlines():
            if not line.strip():
                continue
            try:
                data = json.loads(line)
                sys_rec = self._normalize_recommendation(
                    data.get("system_recommendation", "")
                )
                human_dec = self._normalize_recommendation(
                    data.get("human_decision", "")
                )
                agreement = data.get("agreement", sys_rec == human_dec)

                decision = NormalizedDecision(
                    decision_id=f"promotion:{data.get('proposal_id', '')}",
                    source=DecisionSource.PROMOTION.value,
                    original_id=data.get("proposal_id", ""),
                    system_recommendation=sys_rec,
                    human_decision=human_dec,
                    agreement=agreement,
                    timestamp=data.get("timestamp", ""),
                    domain=data.get("domain", ""),
                    reasoning=data.get("reasoning", ""),
                    details=data
                )
                decisions.append(decision)
            except (json.JSONDecodeError, KeyError):
                continue

        return decisions

    def load_all_decisions(self) -> list[NormalizedDecision]:
        """Load and consolidate decisions from all sources.

        Returns:
            List of normalized decisions sorted by timestamp
        """
        self._decisions = []
        self._decisions.extend(self._load_improvement_decisions())
        self._decisions.extend(self._load_cluster_decisions())
        self._decisions.extend(self._load_promotion_decisions())

        # Sort by timestamp
        self._decisions.sort(key=lambda d: d.timestamp if d.timestamp else "")

        # Update state with first decision timestamp
        if self._decisions and not self._state.get("first_decision_at"):
            self._state["first_decision_at"] = self._decisions[0].timestamp
            self._save_state()

        return self._decisions

    # =========================================================================
    # Metrics Calculation
    # =========================================================================

    def calculate_metrics(self, since: datetime | None = None) -> CalibrationMetrics:
        """Calculate comprehensive calibration metrics.

        Args:
            since: Only include decisions after this timestamp

        Returns:
            CalibrationMetrics with all calculated values
        """
        if not self._decisions:
            self.load_all_decisions()

        # Filter by time if specified
        decisions = self._decisions
        if since:
            since_str = since.isoformat().replace("+00:00", "Z")
            decisions = [d for d in decisions if d.timestamp >= since_str]

        if not decisions:
            return CalibrationMetrics(
                status=CalibrationStatus.CALIBRATING.value,
                blocking_reasons=["No decisions recorded yet"]
            )

        # Basic counts
        total = len(decisions)
        agreements = sum(1 for d in decisions if d.agreement)

        # False positives: system said approve, human rejected
        false_positives = sum(
            1 for d in decisions
            if d.system_recommendation == "approve" and d.human_decision == "reject"
        )

        # False negatives: system said reject, human approved
        false_negatives = sum(
            1 for d in decisions
            if d.system_recommendation == "reject" and d.human_decision == "approve"
        )

        # By source
        by_source: dict[str, dict[str, Any]] = {}
        for source in DecisionSource:
            source_decisions = [d for d in decisions if d.source == source.value]
            if source_decisions:
                source_agreements = sum(1 for d in source_decisions if d.agreement)
                by_source[source.value] = {
                    "total": len(source_decisions),
                    "agreements": source_agreements,
                    "agreement_rate": round(source_agreements / len(source_decisions), 3)
                }

        # By domain
        by_domain: dict[str, dict[str, Any]] = {}
        domains = set(d.domain for d in decisions if d.domain)
        for domain in domains:
            domain_decisions = [d for d in decisions if d.domain == domain]
            domain_agreements = sum(1 for d in domain_decisions if d.agreement)
            by_domain[domain] = {
                "total": len(domain_decisions),
                "agreements": domain_agreements,
                "agreement_rate": round(domain_agreements / len(domain_decisions), 3)
            }

        # By confidence level
        by_confidence: dict[str, dict[str, Any]] = {}
        confidence_levels = [
            ("high", 0.8, 1.1),
            ("medium", 0.5, 0.8),
            ("low", 0.0, 0.5)
        ]
        for level, low, high in confidence_levels:
            level_decisions = [d for d in decisions if low <= d.confidence < high]
            if level_decisions:
                level_agreements = sum(1 for d in level_decisions if d.agreement)
                by_confidence[level] = {
                    "total": len(level_decisions),
                    "agreements": level_agreements,
                    "agreement_rate": round(level_agreements / len(level_decisions), 3)
                }

        # Recent trend (last 30 days)
        recent_cutoff = datetime.now(timezone.utc) - timedelta(days=30)
        recent_cutoff_str = recent_cutoff.isoformat().replace("+00:00", "Z")
        recent_decisions = [d for d in decisions if d.timestamp >= recent_cutoff_str]
        recent_trend = 0.0
        if recent_decisions:
            recent_agreements = sum(1 for d in recent_decisions if d.agreement)
            recent_trend = round(recent_agreements / len(recent_decisions), 3)

        # Evaluation period
        timestamps = [d.timestamp for d in decisions if d.timestamp]
        earliest = min(timestamps) if timestamps else ""
        latest = max(timestamps) if timestamps else ""

        evaluation_days = 0
        if earliest and latest:
            try:
                earliest_dt = datetime.fromisoformat(earliest.rstrip("Z"))
                latest_dt = datetime.fromisoformat(latest.rstrip("Z"))
                evaluation_days = (latest_dt - earliest_dt).days
            except ValueError:
                pass

        # Calculate rates
        agreement_rate = round(agreements / total, 3)
        fp_rate = round(false_positives / total, 3) if total > 0 else 0.0
        fn_rate = round(false_negatives / total, 3) if total > 0 else 0.0

        # Determine status and eligibility
        blocking_reasons = []

        if total < MIN_DECISIONS:
            blocking_reasons.append(
                f"Need {MIN_DECISIONS} decisions, have {total}"
            )

        if evaluation_days < MIN_EVALUATION_DAYS:
            blocking_reasons.append(
                f"Need {MIN_EVALUATION_DAYS} days evaluation, have {evaluation_days}"
            )

        if agreement_rate < AGREEMENT_THRESHOLD:
            blocking_reasons.append(
                f"Need {AGREEMENT_THRESHOLD*100}% agreement, have {agreement_rate*100:.1f}%"
            )

        # Determine status
        if total < MIN_DECISIONS:
            status = CalibrationStatus.CALIBRATING.value
        elif agreement_rate >= AGREEMENT_THRESHOLD:
            if evaluation_days >= MIN_EVALUATION_DAYS and total >= MIN_DECISIONS:
                status = CalibrationStatus.QUALIFIED.value
            else:
                status = CalibrationStatus.ON_TRACK.value
        elif agreement_rate >= 0.85:
            status = CalibrationStatus.AT_RISK.value
        else:
            status = CalibrationStatus.FAILING.value

        autonomous_eligible = (
            status == CalibrationStatus.QUALIFIED.value and
            len(blocking_reasons) == 0
        )

        return CalibrationMetrics(
            total_decisions=total,
            agreement_count=agreements,
            agreement_rate=agreement_rate,
            false_positive_rate=fp_rate,
            false_negative_rate=fn_rate,
            by_source=by_source,
            by_domain=by_domain,
            by_confidence=by_confidence,
            recent_trend=recent_trend,
            evaluation_period_days=evaluation_days,
            earliest_decision=earliest,
            latest_decision=latest,
            status=status,
            autonomous_eligible=autonomous_eligible,
            blocking_reasons=blocking_reasons
        )

    def get_disagreements(
        self,
        since: datetime | None = None,
        disagreement_type: str | None = None
    ) -> list[Disagreement]:
        """Get all disagreements between system and human.

        Args:
            since: Only include disagreements after this timestamp
            disagreement_type: Filter by type (false_positive/false_negative)

        Returns:
            List of Disagreement objects
        """
        if not self._decisions:
            self.load_all_decisions()

        disagreements = []
        for decision in self._decisions:
            if decision.agreement:
                continue

            if since:
                since_str = since.isoformat().replace("+00:00", "Z")
                if decision.timestamp < since_str:
                    continue

            # Determine disagreement type
            if decision.system_recommendation == "approve" and decision.human_decision == "reject":
                dtype = "false_positive"
            elif decision.system_recommendation == "reject" and decision.human_decision == "approve":
                dtype = "false_negative"
            else:
                dtype = "other"

            if disagreement_type and dtype != disagreement_type:
                continue

            # Determine impact based on confidence
            if decision.confidence >= 0.9:
                impact = "high"
            elif decision.confidence >= 0.7:
                impact = "medium"
            else:
                impact = "low"

            disagreements.append(Disagreement(
                decision=decision,
                disagreement_type=dtype,
                impact=impact
            ))

        return disagreements

    def check_autonomous_eligibility(self) -> dict[str, Any]:
        """Check if autonomous mode can be enabled.

        Returns:
            Dict with eligibility status and details
        """
        metrics = self.calculate_metrics()

        return {
            "eligible": metrics.autonomous_eligible,
            "status": metrics.status,
            "agreement_rate": metrics.agreement_rate,
            "total_decisions": metrics.total_decisions,
            "evaluation_days": metrics.evaluation_period_days,
            "blocking_reasons": metrics.blocking_reasons,
            "requirements": {
                "agreement_threshold": AGREEMENT_THRESHOLD,
                "min_decisions": MIN_DECISIONS,
                "min_evaluation_days": MIN_EVALUATION_DAYS
            },
            "progress": {
                "decisions_progress": min(metrics.total_decisions / MIN_DECISIONS, 1.0),
                "days_progress": min(metrics.evaluation_period_days / MIN_EVALUATION_DAYS, 1.0),
                "agreement_progress": min(metrics.agreement_rate / AGREEMENT_THRESHOLD, 1.0)
            },
            "message": (
                "AUTONOMOUS MODE ELIGIBLE" if metrics.autonomous_eligible
                else f"NOT ELIGIBLE: {'; '.join(metrics.blocking_reasons)}"
            )
        }

    # =========================================================================
    # History Tracking
    # =========================================================================

    def save_snapshot(self) -> CalibrationSnapshot:
        """Save current calibration state as a snapshot.

        Returns:
            The created snapshot
        """
        metrics = self.calculate_metrics()

        snapshot = CalibrationSnapshot(
            timestamp=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            total_decisions=metrics.total_decisions,
            agreement_rate=metrics.agreement_rate,
            false_positive_rate=metrics.false_positive_rate,
            false_negative_rate=metrics.false_negative_rate,
            recent_trend=metrics.recent_trend,
            status=metrics.status,
            autonomous_eligible=metrics.autonomous_eligible
        )

        # Append to history
        self._ensure_dir()
        history_file = self.calibration_dir / CALIBRATION_HISTORY_FILE
        with open(history_file, "a") as f:
            f.write(json.dumps(snapshot.to_dict()) + "\n")

        # Update state
        self._state["last_snapshot_at"] = snapshot.timestamp
        self._save_state()

        return snapshot

    def get_history(self, days: int = 30) -> list[CalibrationSnapshot]:
        """Get calibration history for the specified period.

        Args:
            days: Number of days of history to retrieve

        Returns:
            List of CalibrationSnapshot objects
        """
        history_file = self.calibration_dir / CALIBRATION_HISTORY_FILE
        if not history_file.exists():
            return []

        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        cutoff_str = cutoff.isoformat().replace("+00:00", "Z")

        snapshots = []
        for line in history_file.read_text().splitlines():
            if not line.strip():
                continue
            try:
                data = json.loads(line)
                if data.get("timestamp", "") >= cutoff_str:
                    snapshots.append(CalibrationSnapshot.from_dict(data))
            except (json.JSONDecodeError, KeyError):
                continue

        return sorted(snapshots, key=lambda s: s.timestamp)

    # =========================================================================
    # Weekly Reports
    # =========================================================================

    def generate_weekly_report(self) -> WeeklyReport:
        """Generate a weekly calibration report.

        Returns:
            WeeklyReport with period metrics and recommendations
        """
        now = datetime.now(timezone.utc)
        period_end = now
        period_start = now - timedelta(days=7)

        # Get current metrics
        metrics = self.calculate_metrics()

        # Get decisions from this week
        if not self._decisions:
            self.load_all_decisions()

        start_str = period_start.isoformat().replace("+00:00", "Z")
        end_str = period_end.isoformat().replace("+00:00", "Z")
        week_decisions = [
            d for d in self._decisions
            if start_str <= d.timestamp <= end_str
        ]
        new_decisions = len(week_decisions)

        # Get disagreements from this week
        new_disagreements = self.get_disagreements(since=period_start)

        # Calculate trend change from previous week
        history = self.get_history(days=14)
        trend_change = 0.0
        if len(history) >= 2:
            # Find snapshot from ~7 days ago
            week_ago = now - timedelta(days=7)
            week_ago_str = week_ago.isoformat().replace("+00:00", "Z")
            older_snapshots = [s for s in history if s.timestamp <= week_ago_str]
            if older_snapshots:
                prev_rate = older_snapshots[-1].agreement_rate
                trend_change = round(metrics.agreement_rate - prev_rate, 3)

        # Generate recommendations
        recommendations = []

        if metrics.status == CalibrationStatus.FAILING.value:
            recommendations.append(
                "CRITICAL: Agreement rate is below 85%. Review recent disagreements."
            )

        if metrics.false_positive_rate > 0.1:
            recommendations.append(
                "High false positive rate. Consider raising confidence thresholds."
            )

        if metrics.false_negative_rate > 0.1:
            recommendations.append(
                "High false negative rate. Consider lowering confidence thresholds."
            )

        if new_disagreements:
            recommendations.append(
                f"Review {len(new_disagreements)} new disagreement(s) from this week."
            )

        if metrics.status == CalibrationStatus.ON_TRACK.value:
            days_remaining = MIN_EVALUATION_DAYS - metrics.evaluation_period_days
            if days_remaining > 0:
                recommendations.append(
                    f"On track for autonomous mode. {days_remaining} days remaining in evaluation period."
                )

        if not recommendations:
            recommendations.append("No action required. Continue monitoring.")

        # Status summary
        status_summary = (
            f"Calibration Status: {metrics.status.upper()}\n"
            f"Agreement Rate: {metrics.agreement_rate*100:.1f}% (target: {AGREEMENT_THRESHOLD*100}%)\n"
            f"Total Decisions: {metrics.total_decisions} (minimum: {MIN_DECISIONS})\n"
            f"Evaluation Period: {metrics.evaluation_period_days} days (minimum: {MIN_EVALUATION_DAYS})\n"
            f"Autonomous Eligible: {'Yes' if metrics.autonomous_eligible else 'No'}"
        )

        report = WeeklyReport(
            report_id="",  # Will be generated
            period_start=period_start.isoformat().replace("+00:00", "Z"),
            period_end=period_end.isoformat().replace("+00:00", "Z"),
            generated_at="",  # Will be set by __post_init__
            metrics=metrics,
            new_decisions=new_decisions,
            new_disagreements=new_disagreements,
            trend_change=trend_change,
            recommendations=recommendations,
            status_summary=status_summary
        )

        # Save report
        self._save_weekly_report(report)

        return report

    def _save_weekly_report(self, report: WeeklyReport) -> None:
        """Save weekly report to disk."""
        self._ensure_dir()
        reports_dir = self.calibration_dir / WEEKLY_REPORTS_DIR
        reports_dir.mkdir(exist_ok=True)

        # Use period end date in filename
        period_end = report.period_end.split("T")[0]
        filename = f"calibration_report_{period_end}.json"
        report_file = reports_dir / filename
        report_file.write_text(json.dumps(report.to_dict(), indent=2))

    def list_weekly_reports(self) -> list[str]:
        """List available weekly reports.

        Returns:
            List of report filenames
        """
        reports_dir = self.calibration_dir / WEEKLY_REPORTS_DIR
        if not reports_dir.exists():
            return []

        return sorted([f.name for f in reports_dir.glob("calibration_report_*.json")])

    def get_weekly_report(self, filename: str) -> WeeklyReport | None:
        """Load a specific weekly report.

        Args:
            filename: Report filename

        Returns:
            WeeklyReport or None if not found
        """
        reports_dir = self.calibration_dir / WEEKLY_REPORTS_DIR
        report_file = reports_dir / filename

        if not report_file.exists():
            return None

        try:
            data = json.loads(report_file.read_text())
            metrics = CalibrationMetrics.from_dict(data.get("metrics", {}))
            disagreements = [
                Disagreement(
                    decision=NormalizedDecision.from_dict(d["decision"]),
                    disagreement_type=d["disagreement_type"],
                    impact=d.get("impact", "medium"),
                    resolution_notes=d.get("resolution_notes", ""),
                    learned_from=d.get("learned_from", False)
                )
                for d in data.get("new_disagreements", [])
            ]

            return WeeklyReport(
                report_id=data.get("report_id", ""),
                period_start=data.get("period_start", ""),
                period_end=data.get("period_end", ""),
                generated_at=data.get("generated_at", ""),
                metrics=metrics,
                new_decisions=data.get("new_decisions", 0),
                new_disagreements=disagreements,
                trend_change=data.get("trend_change", 0.0),
                recommendations=data.get("recommendations", []),
                status_summary=data.get("status_summary", "")
            )
        except (json.JSONDecodeError, KeyError):
            return None


# ============================================================================
# CLI Interface
# ============================================================================

def create_parser() -> argparse.ArgumentParser:
    """Create argument parser for CLI."""
    parser = argparse.ArgumentParser(
        description="Calibration Tracking System for claude-loop",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Show current calibration status
    python lib/calibration-tracker.py status

    # Show calibration history
    python lib/calibration-tracker.py history --days 30

    # Show disagreements
    python lib/calibration-tracker.py disagreements

    # Check if autonomous mode is allowed
    python lib/calibration-tracker.py autonomous-check

    # Generate weekly report
    python lib/calibration-tracker.py weekly-report
"""
    )

    parser.add_argument(
        "--base-dir", "-d",
        type=Path,
        default=Path.cwd(),
        help="Base directory (default: current directory)"
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

    # status
    subparsers.add_parser("status", help="Show current calibration status")

    # history
    history_parser = subparsers.add_parser("history", help="Show calibration history")
    history_parser.add_argument("--days", type=int, default=30, help="Days of history")

    # disagreements
    disagreements_parser = subparsers.add_parser("disagreements", help="Show disagreements")
    disagreements_parser.add_argument(
        "--type", "-t",
        choices=["false_positive", "false_negative"],
        help="Filter by disagreement type"
    )
    disagreements_parser.add_argument("--days", type=int, default=90, help="Days to look back")

    # autonomous-check
    subparsers.add_parser("autonomous-check", help="Check autonomous mode eligibility")

    # weekly-report
    weekly_parser = subparsers.add_parser("weekly-report", help="Generate weekly report")
    weekly_parser.add_argument("--list", action="store_true", help="List available reports")
    weekly_parser.add_argument("--show", help="Show specific report by filename")

    # snapshot
    subparsers.add_parser("snapshot", help="Save current state snapshot")

    return parser


def format_metrics(metrics: CalibrationMetrics, verbose: bool = False) -> str:
    """Format metrics for display."""
    lines = [
        "=== Calibration Status ===",
        "",
        f"Status: {metrics.status.upper()}",
        f"Autonomous Eligible: {'Yes' if metrics.autonomous_eligible else 'No'}",
        "",
        "--- Agreement Metrics ---",
        f"Total Decisions: {metrics.total_decisions}",
        f"Agreement Rate: {metrics.agreement_rate*100:.1f}%",
        f"False Positive Rate: {metrics.false_positive_rate*100:.1f}%",
        f"False Negative Rate: {metrics.false_negative_rate*100:.1f}%",
        f"Recent Trend (30d): {metrics.recent_trend*100:.1f}%",
        "",
        f"Evaluation Period: {metrics.evaluation_period_days} days",
    ]

    if metrics.blocking_reasons:
        lines.extend([
            "",
            "--- Blocking Reasons ---"
        ])
        for reason in metrics.blocking_reasons:
            lines.append(f"  - {reason}")

    if verbose:
        if metrics.by_source:
            lines.extend([
                "",
                "--- By Source ---"
            ])
            for source, data in metrics.by_source.items():
                lines.append(
                    f"  {source}: {data['agreement_rate']*100:.1f}% "
                    f"({data['agreements']}/{data['total']})"
                )

        if metrics.by_confidence:
            lines.extend([
                "",
                "--- By Confidence Level ---"
            ])
            for level, data in metrics.by_confidence.items():
                lines.append(
                    f"  {level}: {data['agreement_rate']*100:.1f}% "
                    f"({data['agreements']}/{data['total']})"
                )

        if metrics.by_domain:
            lines.extend([
                "",
                "--- By Domain ---"
            ])
            for domain, data in metrics.by_domain.items():
                lines.append(
                    f"  {domain}: {data['agreement_rate']*100:.1f}% "
                    f"({data['agreements']}/{data['total']})"
                )

    return "\n".join(lines)


def format_disagreement(disagreement: Disagreement) -> str:
    """Format a disagreement for display."""
    d = disagreement.decision
    return (
        f"[{disagreement.disagreement_type.upper()}] {d.decision_id}\n"
        f"  Source: {d.source}\n"
        f"  System said: {d.system_recommendation}\n"
        f"  Human said: {d.human_decision}\n"
        f"  Confidence: {d.confidence:.2f}\n"
        f"  Impact: {disagreement.impact}\n"
        f"  Timestamp: {d.timestamp}\n"
        f"  Reasoning: {d.reasoning or 'N/A'}"
    )


def main() -> int:
    """Main entry point for CLI."""
    parser = create_parser()
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    tracker = CalibrationTracker(base_dir=args.base_dir)

    if args.command == "status":
        metrics = tracker.calculate_metrics()

        if args.json:
            print(json.dumps(metrics.to_dict(), indent=2))
        else:
            print(format_metrics(metrics, verbose=args.verbose))
        return 0

    elif args.command == "history":
        history = tracker.get_history(days=args.days)

        if args.json:
            print(json.dumps([s.to_dict() for s in history], indent=2))
        else:
            if not history:
                print(f"No calibration history found for the last {args.days} days.")
                print("Run 'calibration-tracker.py snapshot' to save current state.")
            else:
                print(f"=== Calibration History (last {args.days} days) ===\n")
                for snapshot in history:
                    status_icon = "+" if snapshot.autonomous_eligible else "-"
                    print(
                        f"[{status_icon}] {snapshot.timestamp[:10]} | "
                        f"Agreement: {snapshot.agreement_rate*100:.1f}% | "
                        f"Decisions: {snapshot.total_decisions} | "
                        f"Status: {snapshot.status}"
                    )
        return 0

    elif args.command == "disagreements":
        since = None
        if args.days:
            since = datetime.now(timezone.utc) - timedelta(days=args.days)

        disagreements = tracker.get_disagreements(
            since=since,
            disagreement_type=args.type
        )

        if args.json:
            print(json.dumps([d.to_dict() for d in disagreements], indent=2))
        else:
            if not disagreements:
                print("No disagreements found.")
            else:
                print(f"=== Disagreements ({len(disagreements)} found) ===\n")
                for d in disagreements:
                    print(format_disagreement(d))
                    print()
        return 0

    elif args.command == "autonomous-check":
        result = tracker.check_autonomous_eligibility()

        if args.json:
            print(json.dumps(result, indent=2))
        else:
            print("=== Autonomous Mode Eligibility Check ===\n")
            print(result["message"])
            print()
            print("--- Requirements ---")
            reqs = result["requirements"]
            print(f"  Agreement Threshold: {reqs['agreement_threshold']*100}%")
            print(f"  Minimum Decisions: {reqs['min_decisions']}")
            print(f"  Minimum Evaluation Days: {reqs['min_evaluation_days']}")
            print()
            print("--- Progress ---")
            prog = result["progress"]
            print(f"  Decisions: {result['total_decisions']} ({prog['decisions_progress']*100:.0f}%)")
            print(f"  Days: {result['evaluation_days']} ({prog['days_progress']*100:.0f}%)")
            print(f"  Agreement: {result['agreement_rate']*100:.1f}% ({prog['agreement_progress']*100:.0f}%)")

        return 0 if result["eligible"] else 1

    elif args.command == "weekly-report":
        if args.list:
            reports = tracker.list_weekly_reports()
            if args.json:
                print(json.dumps(reports))
            else:
                if not reports:
                    print("No weekly reports found.")
                else:
                    print("=== Available Weekly Reports ===\n")
                    for r in reports:
                        print(f"  {r}")
            return 0

        if args.show:
            report = tracker.get_weekly_report(args.show)
            if not report:
                print(f"Report not found: {args.show}", file=sys.stderr)
                return 1
        else:
            report = tracker.generate_weekly_report()

        if args.json:
            print(json.dumps(report.to_dict(), indent=2))
        else:
            print(f"=== Weekly Calibration Report ===")
            print(f"Report ID: {report.report_id}")
            print(f"Period: {report.period_start[:10]} to {report.period_end[:10]}")
            print(f"Generated: {report.generated_at}")
            print()
            print(report.status_summary)
            print()
            print(f"--- This Week ---")
            print(f"New Decisions: {report.new_decisions}")
            print(f"New Disagreements: {len(report.new_disagreements)}")
            print(f"Trend Change: {report.trend_change*100:+.1f}%")
            print()
            print("--- Recommendations ---")
            for rec in report.recommendations:
                print(f"  - {rec}")
        return 0

    elif args.command == "snapshot":
        snapshot = tracker.save_snapshot()

        if args.json:
            print(json.dumps(snapshot.to_dict(), indent=2))
        else:
            print(f"Snapshot saved: {snapshot.timestamp}")
            print(f"Agreement Rate: {snapshot.agreement_rate*100:.1f}%")
            print(f"Status: {snapshot.status}")
        return 0

    return 0


if __name__ == "__main__":
    sys.exit(main())
