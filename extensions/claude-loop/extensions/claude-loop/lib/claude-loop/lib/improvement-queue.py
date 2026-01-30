#!/usr/bin/env python3
"""
improvement-queue.py - Human-Gated Improvement Queue for claude-loop

All improvement proposals are queued for human review, not auto-executed.
This ensures human oversight until the system demonstrates 95% alignment
with human decisions.

Features:
- ImprovementProposal dataclass with full lifecycle
- Status lifecycle: proposed -> reviewed -> approved/rejected -> implemented/archived
- NO automatic implementation - all proposals require human approval
- Queue persisted in .claude-loop/improvement_queue.json
- Weekly digest of pending proposals
- Decision tracking for calibration measurement

Usage:
    # List all pending proposals
    python lib/improvement-queue.py queue list

    # Review a specific proposal
    python lib/improvement-queue.py queue review <id>

    # Approve a proposal
    python lib/improvement-queue.py queue approve <id> --notes "Looks good"

    # Reject a proposal
    python lib/improvement-queue.py queue reject <id> --reason "Too broad scope"

    # Generate weekly digest
    python lib/improvement-queue.py digest

    # Show proposal statistics
    python lib/improvement-queue.py stats
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

DEFAULT_QUEUE_FILE = ".claude-loop/improvement_queue.json"
DEFAULT_DECISIONS_FILE = ".claude-loop/improvement_decisions.jsonl"
BASE_DIR = Path.cwd()


# ============================================================================
# Enums
# ============================================================================

class ProposalStatus(str, Enum):
    """Status lifecycle for improvement proposals.

    Workflow:
        proposed -> reviewed -> approved -> implemented
                             -> rejected -> archived
    """
    PROPOSED = "proposed"
    REVIEWED = "reviewed"
    APPROVED = "approved"
    REJECTED = "rejected"
    IMPLEMENTED = "implemented"
    ARCHIVED = "archived"

    def __str__(self) -> str:
        return self.value


class DecisionType(str, Enum):
    """Types of reviewer decisions for calibration tracking."""
    APPROVE = "approve"
    REJECT = "reject"
    DEFER = "defer"
    MODIFY = "modify"

    def __str__(self) -> str:
        return self.value


# ============================================================================
# Data Classes
# ============================================================================

@dataclass
class ImprovementProposal:
    """A proposed improvement awaiting human review.

    Attributes:
        id: Unique identifier (IMP-XXXXXXXX)
        problem_pattern: The recurring problem this addresses
        proposed_solution: Detailed solution approach
        affected_domains: Which domains this applies to
        confidence: System confidence in this proposal (0.0-1.0)
        evidence_count: Number of failure instances supporting this
        created_at: ISO timestamp of creation
        status: Current lifecycle status
        reviewed_at: ISO timestamp when reviewed (if applicable)
        reviewer_notes: Human reviewer's notes
        implemented_at: ISO timestamp when implemented (if applicable)
        implementation_prd: Link to generated PRD (if approved)
        source_patterns: Pattern IDs that triggered this proposal
        source_gap_id: Gap ID if derived from gap analysis
        priority_score: Computed priority (0-100)
        estimated_impact: High/Medium/Low
        tags: Searchable tags
    """
    id: str
    problem_pattern: str
    proposed_solution: str
    affected_domains: list[str] = field(default_factory=list)
    confidence: float = 0.5
    evidence_count: int = 1
    created_at: str = ""
    status: str = ProposalStatus.PROPOSED.value
    reviewed_at: str = ""
    reviewer_notes: str = ""
    implemented_at: str = ""
    implementation_prd: str = ""
    source_patterns: list[str] = field(default_factory=list)
    source_gap_id: str = ""
    priority_score: float = 0.0
    estimated_impact: str = "medium"
    tags: list[str] = field(default_factory=list)

    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        if not self.id:
            self.id = self._generate_id()
        if self.priority_score == 0.0:
            self.priority_score = self._calculate_priority()

    def _generate_id(self) -> str:
        """Generate unique ID from problem pattern hash."""
        hash_input = f"{self.problem_pattern}:{self.created_at}"
        hash_hex = hashlib.sha256(hash_input.encode()).hexdigest()[:8].upper()
        return f"IMP-{hash_hex}"

    def _calculate_priority(self) -> float:
        """Calculate priority score based on confidence and evidence."""
        # Base score from confidence (40%)
        confidence_score = self.confidence * 40

        # Evidence score (30%) - capped at 10 instances
        evidence_score = min(self.evidence_count / 10, 1.0) * 30

        # Impact multiplier (30%)
        impact_multiplier = {"high": 1.0, "medium": 0.6, "low": 0.3}.get(
            self.estimated_impact.lower(), 0.5
        )
        impact_score = impact_multiplier * 30

        return round(confidence_score + evidence_score + impact_score, 1)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ImprovementProposal":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})

    def is_actionable(self) -> bool:
        """Check if proposal is in a state that allows action."""
        return self.status in (ProposalStatus.PROPOSED.value, ProposalStatus.REVIEWED.value)


@dataclass
class ReviewerDecision:
    """Record of a reviewer decision for calibration tracking.

    Attributes:
        proposal_id: Which proposal was decided
        decision_type: approve/reject/defer/modify
        system_recommendation: What the system recommended
        human_decision: What the human decided
        agreement: Whether system and human agreed
        reasoning: Human's reasoning for the decision
        timestamp: When the decision was made
        reviewer_id: Identifier for the reviewer (optional)
    """
    proposal_id: str
    decision_type: str
    system_recommendation: str = ""
    human_decision: str = ""
    agreement: bool = True
    reasoning: str = ""
    timestamp: str = ""
    reviewer_id: str = ""

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        # Calculate agreement
        if self.system_recommendation and self.human_decision:
            self.agreement = self.system_recommendation == self.human_decision

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ReviewerDecision":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


# ============================================================================
# Improvement Queue Manager
# ============================================================================

class ImprovementQueueManager:
    """Manages the human-gated improvement queue.

    All proposals go through human review before implementation.
    Tracks reviewer decisions for calibration measurement.
    """

    def __init__(
        self,
        queue_file: str = DEFAULT_QUEUE_FILE,
        decisions_file: str = DEFAULT_DECISIONS_FILE,
        base_dir: Path | None = None
    ):
        self.base_dir = base_dir or BASE_DIR
        self.queue_file = self.base_dir / queue_file
        self.decisions_file = self.base_dir / decisions_file
        self._queue: dict[str, ImprovementProposal] = {}
        self._load_queue()

    def _ensure_dir(self) -> None:
        """Ensure the queue directory exists."""
        self.queue_file.parent.mkdir(parents=True, exist_ok=True)

    def _load_queue(self) -> None:
        """Load queue from disk."""
        if self.queue_file.exists():
            try:
                data = json.loads(self.queue_file.read_text())
                self._queue = {
                    k: ImprovementProposal.from_dict(v)
                    for k, v in data.get("proposals", {}).items()
                }
            except (json.JSONDecodeError, KeyError) as e:
                print(f"Warning: Failed to load queue: {e}", file=sys.stderr)
                self._queue = {}
        else:
            self._queue = {}

    def _save_queue(self) -> None:
        """Persist queue to disk."""
        self._ensure_dir()
        data = {
            "version": "1.0",
            "updated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "proposals": {k: v.to_dict() for k, v in self._queue.items()}
        }
        self.queue_file.write_text(json.dumps(data, indent=2))

    def _log_decision(self, decision: ReviewerDecision) -> None:
        """Append decision to decisions log for calibration tracking."""
        self._ensure_dir()
        with open(self.decisions_file, "a") as f:
            f.write(json.dumps(decision.to_dict()) + "\n")

    # =========================================================================
    # Queue Operations
    # =========================================================================

    def propose(
        self,
        problem_pattern: str,
        proposed_solution: str,
        affected_domains: list[str] | None = None,
        confidence: float = 0.5,
        evidence_count: int = 1,
        source_patterns: list[str] | None = None,
        source_gap_id: str = "",
        estimated_impact: str = "medium",
        tags: list[str] | None = None
    ) -> ImprovementProposal:
        """Create a new improvement proposal.

        The proposal is created in PROPOSED status and awaits human review.
        NO automatic implementation occurs.

        Args:
            problem_pattern: Description of the recurring problem
            proposed_solution: Detailed solution approach
            affected_domains: Which domains this applies to
            confidence: System confidence (0.0-1.0)
            evidence_count: Number of supporting failure instances
            source_patterns: Pattern IDs that triggered this
            source_gap_id: Gap ID if derived from gap analysis
            estimated_impact: High/Medium/Low
            tags: Searchable tags

        Returns:
            The created ImprovementProposal
        """
        proposal = ImprovementProposal(
            id="",  # Will be generated
            problem_pattern=problem_pattern,
            proposed_solution=proposed_solution,
            affected_domains=affected_domains or [],
            confidence=confidence,
            evidence_count=evidence_count,
            source_patterns=source_patterns or [],
            source_gap_id=source_gap_id,
            estimated_impact=estimated_impact,
            tags=tags or []
        )

        # Check for duplicates (same problem pattern)
        for existing in self._queue.values():
            if (existing.problem_pattern == problem_pattern
                and existing.status in (ProposalStatus.PROPOSED.value, ProposalStatus.REVIEWED.value)):
                # Update evidence count instead of creating duplicate
                existing.evidence_count += evidence_count
                existing.priority_score = existing._calculate_priority()
                self._save_queue()
                return existing

        self._queue[proposal.id] = proposal
        self._save_queue()
        return proposal

    def get(self, proposal_id: str) -> ImprovementProposal | None:
        """Get a proposal by ID."""
        return self._queue.get(proposal_id)

    def list_proposals(
        self,
        status: str | None = None,
        domain: str | None = None,
        min_priority: float = 0.0
    ) -> list[ImprovementProposal]:
        """List proposals with optional filters.

        Args:
            status: Filter by status (e.g., 'proposed', 'approved')
            domain: Filter by affected domain
            min_priority: Minimum priority score

        Returns:
            List of matching proposals sorted by priority (descending)
        """
        results = []
        for proposal in self._queue.values():
            if status and proposal.status != status:
                continue
            if domain and domain not in proposal.affected_domains:
                continue
            if proposal.priority_score < min_priority:
                continue
            results.append(proposal)

        return sorted(results, key=lambda p: p.priority_score, reverse=True)

    def list_pending(self) -> list[ImprovementProposal]:
        """List all proposals awaiting human review."""
        return self.list_proposals(status=ProposalStatus.PROPOSED.value)

    def review(self, proposal_id: str) -> ImprovementProposal | None:
        """Mark a proposal as reviewed (human has looked at it).

        This is an intermediate state before approve/reject.
        """
        proposal = self.get(proposal_id)
        if proposal and proposal.status == ProposalStatus.PROPOSED.value:
            proposal.status = ProposalStatus.REVIEWED.value
            proposal.reviewed_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
            self._save_queue()
        return proposal

    def approve(
        self,
        proposal_id: str,
        notes: str = "",
        reviewer_id: str = ""
    ) -> ImprovementProposal | None:
        """Approve a proposal for implementation.

        Records the decision for calibration tracking.
        Does NOT automatically implement - generates PRD for execution.

        Args:
            proposal_id: ID of the proposal to approve
            notes: Reviewer notes explaining approval
            reviewer_id: Optional reviewer identifier

        Returns:
            The approved proposal or None if not found/invalid state
        """
        proposal = self.get(proposal_id)
        if not proposal or not proposal.is_actionable():
            return None

        proposal.status = ProposalStatus.APPROVED.value
        proposal.reviewed_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        proposal.reviewer_notes = notes
        self._save_queue()

        # Log decision for calibration
        decision = ReviewerDecision(
            proposal_id=proposal_id,
            decision_type=DecisionType.APPROVE.value,
            system_recommendation="approve" if proposal.confidence >= 0.7 else "review",
            human_decision="approve",
            reasoning=notes,
            reviewer_id=reviewer_id
        )
        self._log_decision(decision)

        return proposal

    def reject(
        self,
        proposal_id: str,
        reason: str,
        reviewer_id: str = ""
    ) -> ImprovementProposal | None:
        """Reject a proposal with reason.

        Records the decision for calibration tracking.

        Args:
            proposal_id: ID of the proposal to reject
            reason: Required reason for rejection
            reviewer_id: Optional reviewer identifier

        Returns:
            The rejected proposal or None if not found/invalid state
        """
        if not reason:
            raise ValueError("Rejection reason is required")

        proposal = self.get(proposal_id)
        if not proposal or not proposal.is_actionable():
            return None

        proposal.status = ProposalStatus.REJECTED.value
        proposal.reviewed_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        proposal.reviewer_notes = reason
        self._save_queue()

        # Log decision for calibration
        decision = ReviewerDecision(
            proposal_id=proposal_id,
            decision_type=DecisionType.REJECT.value,
            system_recommendation="approve" if proposal.confidence >= 0.7 else "review",
            human_decision="reject",
            reasoning=reason,
            reviewer_id=reviewer_id
        )
        self._log_decision(decision)

        return proposal

    def mark_implemented(
        self,
        proposal_id: str,
        prd_name: str = ""
    ) -> ImprovementProposal | None:
        """Mark an approved proposal as implemented.

        Args:
            proposal_id: ID of the proposal
            prd_name: Name of the PRD that implemented this

        Returns:
            The updated proposal or None if not found/invalid state
        """
        proposal = self.get(proposal_id)
        if not proposal or proposal.status != ProposalStatus.APPROVED.value:
            return None

        proposal.status = ProposalStatus.IMPLEMENTED.value
        proposal.implemented_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        proposal.implementation_prd = prd_name
        self._save_queue()

        return proposal

    def archive(self, proposal_id: str) -> ImprovementProposal | None:
        """Archive a rejected proposal.

        Keeps it for historical reference but removes from active queue.
        """
        proposal = self.get(proposal_id)
        if not proposal or proposal.status != ProposalStatus.REJECTED.value:
            return None

        proposal.status = ProposalStatus.ARCHIVED.value
        self._save_queue()

        return proposal

    # =========================================================================
    # Digest and Statistics
    # =========================================================================

    def generate_digest(self, days: int = 7) -> dict[str, Any]:
        """Generate a weekly digest of pending proposals.

        Args:
            days: Number of days to include (default: 7)

        Returns:
            Digest summary with pending proposals, stats, and recommendations
        """
        cutoff = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=days)
        pending = self.list_pending()

        # Filter to those created in the period
        recent_pending = [
            p for p in pending
            if datetime.fromisoformat(p.created_at.rstrip("Z")) >= cutoff
        ]

        # Group by impact
        by_impact = {"high": [], "medium": [], "low": []}
        for p in pending:
            impact = p.estimated_impact.lower()
            if impact in by_impact:
                by_impact[impact].append(p.id)

        # Group by domain
        by_domain: dict[str, list[str]] = {}
        for p in pending:
            for domain in p.affected_domains:
                if domain not in by_domain:
                    by_domain[domain] = []
                by_domain[domain].append(p.id)

        # Recommendations
        recommendations = []
        high_priority = [p for p in pending if p.priority_score >= 70]
        if high_priority:
            recommendations.append(
                f"Review {len(high_priority)} high-priority proposals first"
            )

        old_proposals = [
            p for p in pending
            if (datetime.now(timezone.utc).replace(tzinfo=None) - datetime.fromisoformat(p.created_at.rstrip("Z"))).days > 14
        ]
        if old_proposals:
            recommendations.append(
                f"{len(old_proposals)} proposals are over 2 weeks old - consider review"
            )

        return {
            "period_days": days,
            "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "total_pending": len(pending),
            "new_this_period": len(recent_pending),
            "by_impact": {k: len(v) for k, v in by_impact.items()},
            "by_domain": {k: len(v) for k, v in by_domain.items()},
            "top_priority": [
                {"id": p.id, "problem": p.problem_pattern[:100], "priority": p.priority_score}
                for p in sorted(pending, key=lambda x: x.priority_score, reverse=True)[:5]
            ],
            "recommendations": recommendations
        }

    def get_statistics(self) -> dict[str, Any]:
        """Get queue statistics for monitoring.

        Returns:
            Statistics including counts by status, decision rates, etc.
        """
        by_status: dict[str, int] = {}
        total_priority = 0.0

        for proposal in self._queue.values():
            status = proposal.status
            by_status[status] = by_status.get(status, 0) + 1
            total_priority += proposal.priority_score

        # Load decision history
        decisions = self._load_decisions()
        agreement_count = sum(1 for d in decisions if d.agreement)
        total_decisions = len(decisions)

        return {
            "total_proposals": len(self._queue),
            "by_status": by_status,
            "average_priority": round(total_priority / max(len(self._queue), 1), 1),
            "decision_count": total_decisions,
            "agreement_rate": round(agreement_count / max(total_decisions, 1), 3),
            "pending_count": by_status.get(ProposalStatus.PROPOSED.value, 0),
            "approved_count": by_status.get(ProposalStatus.APPROVED.value, 0),
            "rejected_count": by_status.get(ProposalStatus.REJECTED.value, 0),
            "implemented_count": by_status.get(ProposalStatus.IMPLEMENTED.value, 0)
        }

    def _load_decisions(self) -> list[ReviewerDecision]:
        """Load all decisions from the decisions log."""
        decisions = []
        if self.decisions_file.exists():
            for line in self.decisions_file.read_text().splitlines():
                if line.strip():
                    try:
                        decisions.append(ReviewerDecision.from_dict(json.loads(line)))
                    except (json.JSONDecodeError, KeyError):
                        continue
        return decisions

    def get_calibration_metrics(self) -> dict[str, Any]:
        """Get calibration metrics for system-human alignment.

        Used to measure whether the system recommendations align with
        human decisions over time.

        Returns:
            Calibration metrics including agreement rates
        """
        decisions = self._load_decisions()
        if not decisions:
            return {
                "total_decisions": 0,
                "agreement_rate": 0.0,
                "message": "No decisions recorded yet"
            }

        agreements = sum(1 for d in decisions if d.agreement)
        approvals = sum(1 for d in decisions if d.human_decision == "approve")
        rejections = sum(1 for d in decisions if d.human_decision == "reject")

        # System recommendations that matched
        system_approve_human_approve = sum(
            1 for d in decisions
            if d.system_recommendation == "approve" and d.human_decision == "approve"
        )
        system_review_human_reject = sum(
            1 for d in decisions
            if d.system_recommendation == "review" and d.human_decision == "reject"
        )

        total = len(decisions)

        return {
            "total_decisions": total,
            "agreement_rate": round(agreements / total, 3),
            "approval_rate": round(approvals / total, 3),
            "rejection_rate": round(rejections / total, 3),
            "system_accuracy": {
                "high_confidence_correct": system_approve_human_approve,
                "low_confidence_correct": system_review_human_reject,
            },
            "autonomous_threshold_met": agreements / total >= 0.95 if total >= 50 else False,
            "message": (
                f"System-human agreement: {agreements}/{total} ({round(agreements/total*100, 1)}%). "
                f"Need 95% agreement over 50+ decisions for autonomous mode."
            )
        }


# ============================================================================
# CLI Interface
# ============================================================================

def create_parser() -> argparse.ArgumentParser:
    """Create argument parser for CLI."""
    parser = argparse.ArgumentParser(
        description="Human-Gated Improvement Queue for claude-loop",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # List all pending proposals
    python lib/improvement-queue.py queue list

    # Review a specific proposal
    python lib/improvement-queue.py queue review IMP-ABC12345

    # Approve a proposal
    python lib/improvement-queue.py queue approve IMP-ABC12345 --notes "Good solution"

    # Reject a proposal
    python lib/improvement-queue.py queue reject IMP-ABC12345 --reason "Too broad"

    # Generate weekly digest
    python lib/improvement-queue.py digest

    # Show calibration metrics
    python lib/improvement-queue.py calibration
"""
    )

    # Global options
    parser.add_argument(
        "--base-dir", "-d",
        type=Path,
        default=Path.cwd(),
        help="Base directory for queue files (default: current directory)"
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

    # queue subcommand
    queue_parser = subparsers.add_parser("queue", help="Queue operations")
    queue_subparsers = queue_parser.add_subparsers(dest="queue_command", help="Queue commands")

    # queue list
    list_parser = queue_subparsers.add_parser("list", help="List proposals")
    list_parser.add_argument("--status", "-s", help="Filter by status")
    list_parser.add_argument("--domain", help="Filter by domain")
    list_parser.add_argument("--min-priority", type=float, default=0.0, help="Minimum priority")

    # queue review
    review_parser = queue_subparsers.add_parser("review", help="Review a proposal")
    review_parser.add_argument("id", help="Proposal ID to review")

    # queue approve
    approve_parser = queue_subparsers.add_parser("approve", help="Approve a proposal")
    approve_parser.add_argument("id", help="Proposal ID to approve")
    approve_parser.add_argument("--notes", "-n", default="", help="Approval notes")
    approve_parser.add_argument("--reviewer", "-r", default="", help="Reviewer ID")

    # queue reject
    reject_parser = queue_subparsers.add_parser("reject", help="Reject a proposal")
    reject_parser.add_argument("id", help="Proposal ID to reject")
    reject_parser.add_argument("--reason", "-r", required=True, help="Rejection reason (required)")
    reject_parser.add_argument("--reviewer", default="", help="Reviewer ID")

    # propose subcommand (for creating proposals programmatically)
    propose_parser = subparsers.add_parser("propose", help="Create a new proposal")
    propose_parser.add_argument("problem", help="Problem pattern description")
    propose_parser.add_argument("solution", help="Proposed solution")
    propose_parser.add_argument("--domains", nargs="+", default=[], help="Affected domains")
    propose_parser.add_argument("--confidence", type=float, default=0.5, help="Confidence (0-1)")
    propose_parser.add_argument("--evidence", type=int, default=1, help="Evidence count")
    propose_parser.add_argument("--impact", choices=["high", "medium", "low"], default="medium")
    propose_parser.add_argument("--tags", nargs="+", default=[], help="Tags")
    propose_parser.add_argument("--gap-id", default="", help="Source gap ID")

    # digest subcommand
    digest_parser = subparsers.add_parser("digest", help="Generate weekly digest")
    digest_parser.add_argument("--days", type=int, default=7, help="Number of days (default: 7)")

    # stats subcommand
    subparsers.add_parser("stats", help="Show queue statistics")

    # calibration subcommand
    subparsers.add_parser("calibration", help="Show calibration metrics")

    return parser


def format_proposal(proposal: ImprovementProposal, verbose: bool = False) -> str:
    """Format a proposal for display."""
    lines = [
        f"ID: {proposal.id}",
        f"Status: {proposal.status}",
        f"Priority: {proposal.priority_score}",
        f"Impact: {proposal.estimated_impact}",
        f"Confidence: {proposal.confidence}",
        f"Evidence: {proposal.evidence_count} instance(s)",
        "",
        f"Problem Pattern:",
        f"  {proposal.problem_pattern}",
        "",
        f"Proposed Solution:",
        f"  {proposal.proposed_solution}",
    ]

    if proposal.affected_domains:
        lines.extend(["", f"Affected Domains: {', '.join(proposal.affected_domains)}"])

    if proposal.tags:
        lines.extend(["", f"Tags: {', '.join(proposal.tags)}"])

    if verbose:
        lines.extend([
            "",
            f"Created: {proposal.created_at}",
        ])
        if proposal.reviewed_at:
            lines.append(f"Reviewed: {proposal.reviewed_at}")
        if proposal.reviewer_notes:
            lines.append(f"Reviewer Notes: {proposal.reviewer_notes}")
        if proposal.source_gap_id:
            lines.append(f"Source Gap: {proposal.source_gap_id}")
        if proposal.source_patterns:
            lines.append(f"Source Patterns: {', '.join(proposal.source_patterns)}")

    return "\n".join(lines)


def main() -> int:
    """Main entry point for CLI."""
    parser = create_parser()
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    manager = ImprovementQueueManager(base_dir=args.base_dir)

    # Handle commands
    if args.command == "queue":
        if not args.queue_command:
            parser.parse_args(["queue", "--help"])
            return 1

        if args.queue_command == "list":
            proposals = manager.list_proposals(
                status=args.status,
                domain=args.domain,
                min_priority=args.min_priority
            )

            if args.json:
                print(json.dumps([p.to_dict() for p in proposals], indent=2))
            else:
                if not proposals:
                    print("No proposals found matching criteria.")
                else:
                    print(f"Found {len(proposals)} proposal(s):\n")
                    for p in proposals:
                        print(f"[{p.id}] {p.status.upper()} - Priority: {p.priority_score}")
                        print(f"  {p.problem_pattern[:80]}...")
                        print()
            return 0

        elif args.queue_command == "review":
            proposal = manager.get(args.id)
            if not proposal:
                print(f"Proposal {args.id} not found.", file=sys.stderr)
                return 1

            if args.json:
                print(json.dumps(proposal.to_dict(), indent=2))
            else:
                print(format_proposal(proposal, verbose=args.verbose))
                print()
                print("-" * 60)
                if proposal.is_actionable():
                    print("Actions available:")
                    print(f"  Approve: python lib/improvement-queue.py queue approve {args.id} --notes 'reason'")
                    print(f"  Reject:  python lib/improvement-queue.py queue reject {args.id} --reason 'reason'")
                else:
                    print(f"No actions available (status: {proposal.status})")

            # Mark as reviewed
            manager.review(args.id)
            return 0

        elif args.queue_command == "approve":
            proposal = manager.approve(args.id, notes=args.notes, reviewer_id=args.reviewer)
            if not proposal:
                print(f"Cannot approve {args.id} - not found or not actionable.", file=sys.stderr)
                return 1

            if args.json:
                print(json.dumps(proposal.to_dict(), indent=2))
            else:
                print(f"Proposal {args.id} APPROVED")
                if args.notes:
                    print(f"Notes: {args.notes}")
                print("\nNext steps:")
                print("  1. Generate PRD: python lib/improvement-prd-generator.py generate <gap_id>")
                print("  2. Execute: ./claude-loop.sh --execute-improvement <prd_name>")
            return 0

        elif args.queue_command == "reject":
            proposal = manager.reject(args.id, reason=args.reason, reviewer_id=args.reviewer)
            if not proposal:
                print(f"Cannot reject {args.id} - not found or not actionable.", file=sys.stderr)
                return 1

            if args.json:
                print(json.dumps(proposal.to_dict(), indent=2))
            else:
                print(f"Proposal {args.id} REJECTED")
                print(f"Reason: {args.reason}")
            return 0

    elif args.command == "propose":
        proposal = manager.propose(
            problem_pattern=args.problem,
            proposed_solution=args.solution,
            affected_domains=args.domains,
            confidence=args.confidence,
            evidence_count=args.evidence,
            estimated_impact=args.impact,
            tags=args.tags,
            source_gap_id=args.gap_id
        )

        if args.json:
            print(json.dumps(proposal.to_dict(), indent=2))
        else:
            print(f"Created proposal: {proposal.id}")
            print(f"Priority: {proposal.priority_score}")
            print(f"Status: {proposal.status}")
            print("\nAwaiting human review. No automatic implementation will occur.")
        return 0

    elif args.command == "digest":
        digest = manager.generate_digest(days=args.days)

        if args.json:
            print(json.dumps(digest, indent=2))
        else:
            print(f"=== Improvement Queue Digest ({args.days} days) ===")
            print(f"Generated: {digest['generated_at']}")
            print()
            print(f"Total Pending: {digest['total_pending']}")
            print(f"New This Period: {digest['new_this_period']}")
            print()
            print("By Impact:")
            for impact, count in digest['by_impact'].items():
                print(f"  {impact.capitalize()}: {count}")
            print()
            if digest['by_domain']:
                print("By Domain:")
                for domain, count in digest['by_domain'].items():
                    print(f"  {domain}: {count}")
                print()
            if digest['top_priority']:
                print("Top Priority Proposals:")
                for p in digest['top_priority']:
                    print(f"  [{p['id']}] {p['priority']:.1f} - {p['problem'][:50]}...")
                print()
            if digest['recommendations']:
                print("Recommendations:")
                for rec in digest['recommendations']:
                    print(f"  - {rec}")
        return 0

    elif args.command == "stats":
        stats = manager.get_statistics()

        if args.json:
            print(json.dumps(stats, indent=2))
        else:
            print("=== Queue Statistics ===")
            print(f"Total Proposals: {stats['total_proposals']}")
            print(f"Average Priority: {stats['average_priority']}")
            print()
            print("By Status:")
            for status, count in stats['by_status'].items():
                print(f"  {status}: {count}")
            print()
            print(f"Decisions Made: {stats['decision_count']}")
            print(f"Agreement Rate: {stats['agreement_rate']*100:.1f}%")
        return 0

    elif args.command == "calibration":
        metrics = manager.get_calibration_metrics()

        if args.json:
            print(json.dumps(metrics, indent=2))
        else:
            print("=== Calibration Metrics ===")
            print(metrics['message'])
            print()
            if metrics['total_decisions'] > 0:
                print(f"Total Decisions: {metrics['total_decisions']}")
                print(f"Agreement Rate: {metrics['agreement_rate']*100:.1f}%")
                print(f"Approval Rate: {metrics['approval_rate']*100:.1f}%")
                print(f"Rejection Rate: {metrics['rejection_rate']*100:.1f}%")
                print()
                print("System Accuracy:")
                acc = metrics['system_accuracy']
                print(f"  High-confidence proposals approved: {acc['high_confidence_correct']}")
                print(f"  Low-confidence proposals rejected: {acc['low_confidence_correct']}")
                print()
                if metrics['autonomous_threshold_met']:
                    print("STATUS: Autonomous threshold MET (95%+ over 50+ decisions)")
                else:
                    print("STATUS: Autonomous threshold NOT met (need 95%+ over 50+ decisions)")
        return 0

    return 0


if __name__ == "__main__":
    sys.exit(main())
