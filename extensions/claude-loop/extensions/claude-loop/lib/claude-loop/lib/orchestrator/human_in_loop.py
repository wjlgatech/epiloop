#!/usr/bin/env python3
"""
Human-in-the-Loop Rules and Approval Gates

Manages approval gates for essential decisions while automating routine decisions.
Logs user overrides and learns from patterns to improve future recommendations.
"""

import sys
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict
from enum import Enum

# Import orchestrator types
sys.path.insert(0, str(Path(__file__).parent))
from diagnosis import DiagnosisResult
from decision_engine import DecisionResult
from transparency import TransparencyLayer, TransparencyLevel, Explanation


class DecisionCategory(str, Enum):
    """Category of decision for approval classification"""
    ESSENTIAL = "essential"      # Requires human approval
    ROUTINE = "routine"          # Automatic approval


class ApprovalAction(str, Enum):
    """User's response to approval request"""
    APPROVE = "approve"
    REJECT = "reject"
    EXPLAIN = "explain"  # Request full audit before deciding


@dataclass
class ApprovalRequest:
    """Request for human approval"""
    request_id: str
    category: DecisionCategory
    reason: str                    # Why approval is needed
    decisions: DecisionResult
    explanation: Explanation       # Detailed explanation (Level 2)
    timestamp: str


@dataclass
class ApprovalResponse:
    """User's response to approval request"""
    request_id: str
    action: ApprovalAction
    notes: Optional[str] = None    # User's reason for reject/override
    timestamp: Optional[str] = None


@dataclass
class Override:
    """Record of user override (rejection)"""
    request_id: str
    timestamp: str
    user_request: str
    rejected_components: List[str]  # Components user rejected
    reason: str                     # User's reason
    alternative_taken: Optional[str] = None  # What user did instead


class ApprovalGate:
    """
    Manages approval gates for essential decisions.

    Essential Decisions (require approval):
    - Destructive operations (git force push, rm -rf, data deletion)
    - Production deployments
    - Architectural decisions with multiple valid approaches
    - Budget/cost thresholds exceeded

    Routine Decisions (automatic):
    - Agent selection
    - Skill invocation
    - Code quality decisions
    - Test execution
    - File operations (read/write/edit)
    """

    def __init__(self, overrides_log: str = None):
        """
        Initialize approval gate.

        Args:
            overrides_log: Path to log file for user overrides
                          Default: .claude-loop/orchestrator-overrides.jsonl
        """
        if overrides_log is None:
            script_dir = Path(__file__).parent.parent.parent
            log_dir = script_dir / ".claude-loop"
            log_dir.mkdir(exist_ok=True)
            overrides_log = log_dir / "orchestrator-overrides.jsonl"

        self.overrides_log = Path(overrides_log)
        self.overrides_log.parent.mkdir(parents=True, exist_ok=True)

        self.transparency = TransparencyLayer()

    def classify_decision(
        self,
        diagnosis: DiagnosisResult,
        decisions: DecisionResult
    ) -> Tuple[DecisionCategory, str]:
        """
        Classify decision as essential or routine.

        Args:
            diagnosis: Situation diagnosis
            decisions: Routing decisions

        Returns:
            (category, reason) tuple

        Essential Decisions:
        1. Destructive operations
        2. Production deployments
        3. Architectural decisions (complexity >= 7)
        4. Budget thresholds exceeded

        Routine Decisions:
        - Everything else
        """
        # Check if decision engine already flagged as essential
        if decisions.human_approval_required:
            return DecisionCategory.ESSENTIAL, decisions.approval_reason

        # Additional checks for essential decisions
        # (decision engine might not catch everything)

        # Check for architectural decisions (high complexity)
        if diagnosis.complexity >= 7:
            return DecisionCategory.ESSENTIAL, f"High complexity architectural decision ({diagnosis.complexity}/10)"

        # Check for multiple high-priority agents (indicates complex situation)
        high_priority_agents = [
            d for d in decisions.decisions
            if d.component_type == "agent" and d.priority.value <= 2
        ]

        if len(high_priority_agents) >= 3:
            return DecisionCategory.ESSENTIAL, f"Complex situation requiring {len(high_priority_agents)} high-priority agents"

        # Otherwise, it's routine
        return DecisionCategory.ROUTINE, "Standard operation"

    def request_approval(
        self,
        user_request: str,
        diagnosis: DiagnosisResult,
        decisions: DecisionResult,
        request_id: str = None
    ) -> ApprovalRequest:
        """
        Create approval request for essential decision.

        Args:
            user_request: Original user request
            diagnosis: Situation diagnosis
            decisions: Routing decisions
            request_id: Optional request ID

        Returns:
            ApprovalRequest object
        """
        if request_id is None:
            import uuid
            request_id = str(uuid.uuid4())[:8]

        # Classify decision
        category, reason = self.classify_decision(diagnosis, decisions)

        # Generate detailed explanation (Level 2)
        explanation = self.transparency.explain(
            user_request,
            diagnosis,
            decisions,
            level=TransparencyLevel.DETAILED
        )

        return ApprovalRequest(
            request_id=request_id,
            category=category,
            reason=reason,
            decisions=decisions,
            explanation=explanation,
            timestamp=datetime.utcnow().isoformat() + "Z"
        )

    def process_approval(
        self,
        approval_request: ApprovalRequest,
        action: ApprovalAction,
        notes: Optional[str] = None
    ) -> ApprovalResponse:
        """
        Process user's approval response.

        Args:
            approval_request: Original approval request
            action: User's action (approve/reject/explain)
            notes: Optional notes from user

        Returns:
            ApprovalResponse object
        """
        response = ApprovalResponse(
            request_id=approval_request.request_id,
            action=action,
            notes=notes,
            timestamp=datetime.utcnow().isoformat() + "Z"
        )

        # If user rejected, log as override
        if action == ApprovalAction.REJECT:
            self._log_override(approval_request, response)

        return response

    def explain_before_approval(
        self,
        user_request: str,
        diagnosis: DiagnosisResult,
        decisions: DecisionResult
    ) -> Explanation:
        """
        Generate full audit explanation (Level 3) for approval request.

        Used when user requests 'explain' before making decision.

        Args:
            user_request: Original user request
            diagnosis: Situation diagnosis
            decisions: Routing decisions

        Returns:
            Full audit explanation (Level 3)
        """
        return self.transparency.explain(
            user_request,
            diagnosis,
            decisions,
            level=TransparencyLevel.FULL_AUDIT
        )

    def get_override_statistics(self) -> Dict:
        """
        Get statistics about user overrides.

        Returns:
            Dict with statistics:
            - total_overrides: Total number of rejections
            - most_rejected_components: Components users reject most often
            - rejection_rate_by_category: Rejection rate per decision category
            - common_rejection_reasons: Most common reasons for rejection
        """
        overrides = self._read_overrides()

        total = len(overrides)

        # Count rejected components
        component_counts = {}
        for override in overrides:
            for component in override["rejected_components"]:
                component_counts[component] = component_counts.get(component, 0) + 1

        most_rejected = sorted(
            component_counts.items(),
            key=lambda x: x[1],
            reverse=True
        )[:10]

        # Rejection reasons
        reason_counts = {}
        for override in overrides:
            reason = override.get("reason", "No reason given")
            reason_counts[reason] = reason_counts.get(reason, 0) + 1

        common_reasons = sorted(
            reason_counts.items(),
            key=lambda x: x[1],
            reverse=True
        )[:5]

        return {
            "total_overrides": total,
            "most_rejected_components": [
                {"component": comp, "count": count}
                for comp, count in most_rejected
            ],
            "common_rejection_reasons": [
                {"reason": reason, "count": count}
                for reason, count in common_reasons
            ]
        }

    def learn_from_overrides(self) -> Dict[str, float]:
        """
        Analyze user overrides to suggest confidence adjustments.

        Returns:
            Dict mapping component names to suggested confidence multipliers:
            - <0.8 = frequently rejected (decrease confidence)
            - 0.8-1.2 = acceptable (no change needed)
            - >1.2 = never rejected (consider increasing confidence)

        Algorithm:
            1. Count how often each component is rejected
            2. Calculate rejection rate per component
            3. Suggest confidence adjustments based on rejection rate
        """
        overrides = self._read_overrides()

        if not overrides:
            return {}

        # Count total times each component was recommended
        # (would need to track this in decision logs for accurate calculation)
        # For now, estimate based on rejection counts

        # Count rejections per component
        component_rejections = {}
        for override in overrides:
            for component in override["rejected_components"]:
                component_rejections[component] = component_rejections.get(component, 0) + 1

        # Suggest adjustments
        # High rejection rate (>30%) → decrease confidence
        # Medium rejection rate (10-30%) → slight decrease
        # Low rejection rate (<10%) → no change
        adjustments = {}

        for component, rejection_count in component_rejections.items():
            # Assume component was recommended rejection_count + successful_count times
            # Without full tracking, estimate successful_count = rejection_count * 3
            # (assumes 25% rejection rate for components that appear in overrides)
            estimated_recommendations = rejection_count * 4
            rejection_rate = rejection_count / estimated_recommendations

            if rejection_rate > 0.3:
                # High rejection rate → decrease confidence significantly
                multiplier = 0.7
            elif rejection_rate > 0.15:
                # Medium rejection rate → decrease confidence moderately
                multiplier = 0.85
            else:
                # Low rejection rate → slight decrease or no change
                multiplier = 0.95

            adjustments[component] = multiplier

        return adjustments

    def _log_override(
        self,
        approval_request: ApprovalRequest,
        response: ApprovalResponse
    ):
        """Log user override (rejection) to file"""
        override = Override(
            request_id=approval_request.request_id,
            timestamp=response.timestamp,
            user_request=approval_request.explanation.summary,
            rejected_components=approval_request.decisions.execution_order,
            reason=response.notes or "No reason given",
            alternative_taken=None  # Could be filled in later
        )

        # Append to log file
        with open(self.overrides_log, "a") as f:
            f.write(json.dumps(asdict(override), default=str) + "\n")

    def _read_overrides(self) -> List[Dict]:
        """Read all overrides from log file"""
        if not self.overrides_log.exists():
            return []

        overrides = []
        with open(self.overrides_log, "r") as f:
            for line in f:
                line = line.strip()
                if line:
                    overrides.append(json.loads(line))

        return overrides


def main():
    """CLI interface for testing"""
    from argparse import ArgumentParser
    from diagnosis import SituationDiagnosis
    from decision_engine import DecisionEngine

    parser = ArgumentParser(description="Human-in-the-Loop Approval Gate CLI")
    parser.add_argument("command", choices=["classify", "approve", "stats", "learn"], help="Command to run")
    parser.add_argument("request", nargs="?", help="User request text")
    parser.add_argument("--action", choices=["approve", "reject", "explain"], help="Approval action")
    parser.add_argument("--notes", help="Notes for rejection")
    parser.add_argument("--overrides-log", help="Path to overrides log file")

    args = parser.parse_args()

    gate = ApprovalGate(overrides_log=args.overrides_log)

    if args.command == "classify":
        if not args.request:
            print("Error: request required for classify command")
            sys.exit(1)

        # Diagnose and decide
        diagnoser = SituationDiagnosis()
        diagnosis = diagnoser.diagnose(args.request)

        engine = DecisionEngine()
        decisions = engine.decide(diagnosis)

        # Classify
        category, reason = gate.classify_decision(diagnosis, decisions)

        print(f"\nDecision Category: {category.value.upper()}")
        print(f"Reason: {reason}")

        if category == DecisionCategory.ESSENTIAL:
            print("\n⚠️  This decision requires human approval")
        else:
            print("\n✓ This decision can be executed automatically")

    elif args.command == "approve":
        if not args.request:
            print("Error: request required for approve command")
            sys.exit(1)

        # Diagnose and decide
        diagnoser = SituationDiagnosis()
        diagnosis = diagnoser.diagnose(args.request)

        engine = DecisionEngine()
        decisions = engine.decide(diagnosis)

        # Create approval request
        approval_request = gate.request_approval(args.request, diagnosis, decisions)

        # Show explanation
        formatted = gate.transparency.format_explanation(approval_request.explanation)
        print(formatted)

        # Simulate user action
        if args.action:
            action = ApprovalAction(args.action)
            response = gate.process_approval(approval_request, action, args.notes)
            print(f"\n{'='*60}")
            print(f"Action: {response.action.value.upper()}")
            if response.notes:
                print(f"Notes: {response.notes}")

    elif args.command == "stats":
        stats = gate.get_override_statistics()
        print(f"\n{'='*60}")
        print("OVERRIDE STATISTICS")
        print(f"{'='*60}\n")
        print(f"Total Overrides: {stats['total_overrides']}")
        print(f"\nMost Rejected Components:")
        for item in stats['most_rejected_components']:
            print(f"  {item['component']}: {item['count']}")
        print(f"\nCommon Rejection Reasons:")
        for item in stats['common_rejection_reasons']:
            print(f"  {item['reason']}: {item['count']}")
        print(f"\n{'='*60}\n")

    elif args.command == "learn":
        adjustments = gate.learn_from_overrides()
        print(f"\n{'='*60}")
        print("LEARNING FROM OVERRIDES")
        print(f"{'='*60}\n")

        if not adjustments:
            print("No override data available for learning")
        else:
            for component, multiplier in sorted(adjustments.items(), key=lambda x: x[1]):
                action = "DECREASE" if multiplier < 0.9 else "OK"
                print(f"{component}: {multiplier:.2f}x ({action})")

        print(f"\n{'='*60}\n")


if __name__ == "__main__":
    main()
