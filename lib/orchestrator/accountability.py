#!/usr/bin/env python3
"""
Accountability Layer with Decision Logging

Logs all orchestrator decisions with rationale and outcomes for learning and transparency.
Tracks decision → outcome correlations to improve future routing decisions.
"""

import json
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict
from enum import Enum

# Import orchestrator types
import sys
sys.path.insert(0, str(Path(__file__).parent))
from diagnosis import DiagnosisResult
from decision_engine import DecisionResult, RoutingDecision


class OutcomeType(str, Enum):
    """Outcome of executing routing decisions"""
    SUCCESS = "success"
    FAILURE = "failure"
    PARTIAL = "partial"
    CANCELLED = "cancelled"


@dataclass
class Outcome:
    """Tracks the result of executing routing decisions"""
    outcome_type: OutcomeType
    time_taken_seconds: float
    issues_found: List[str]
    tests_passed: Optional[bool] = None
    quality_score: Optional[float] = None  # 0.0-1.0
    notes: str = ""

    def to_dict(self) -> Dict:
        """Convert to dictionary"""
        return asdict(self)


@dataclass
class DecisionLog:
    """Complete log entry for a routing decision"""
    request_id: str
    timestamp: str  # ISO 8601 format
    user_request: str
    diagnosis: Dict  # DiagnosisResult as dict
    decisions: Dict  # DecisionResult as dict
    outcome: Optional[Dict] = None  # Outcome as dict (filled in later)
    logged_at: Optional[str] = None  # When outcome was logged

    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization"""
        return asdict(self)

    def to_json(self) -> str:
        """Convert to JSON string"""
        return json.dumps(self.to_dict(), default=str)


class AccountabilityLogger:
    """
    Logs orchestrator decisions and outcomes for learning and transparency.

    Maintains a JSON Lines log file with:
    - All routing decisions with rationale
    - Diagnosis that led to decisions
    - Outcomes (success/failure, time, issues)
    - Learning data for confidence tuning
    """

    def __init__(self, log_file: str = None):
        """
        Initialize accountability logger.

        Args:
            log_file: Path to log file (default: .claude-loop/orchestrator-decisions.jsonl)
        """
        if log_file is None:
            # Default to .claude-loop/orchestrator-decisions.jsonl
            script_dir = Path(__file__).parent.parent.parent
            log_dir = script_dir / ".claude-loop"
            log_dir.mkdir(exist_ok=True)
            log_file = log_dir / "orchestrator-decisions.jsonl"

        self.log_file = Path(log_file)
        self.log_file.parent.mkdir(parents=True, exist_ok=True)

    def log_decision(
        self,
        user_request: str,
        diagnosis: DiagnosisResult,
        decisions: DecisionResult,
        request_id: str = None
    ) -> str:
        """
        Log a routing decision.

        Args:
            user_request: Original user request text
            diagnosis: DiagnosisResult from situation diagnosis
            decisions: DecisionResult from decision engine
            request_id: Optional request ID (generated if not provided)

        Returns:
            request_id for this decision (use for logging outcome later)

        Performance: <10ms
        """
        if request_id is None:
            request_id = str(uuid.uuid4())[:8]

        # Create log entry
        log_entry = DecisionLog(
            request_id=request_id,
            timestamp=datetime.utcnow().isoformat() + "Z",
            user_request=user_request,
            diagnosis=self._diagnosis_to_dict(diagnosis),
            decisions=self._decisions_to_dict(decisions),
            outcome=None,  # Filled in later with log_outcome()
            logged_at=None
        )

        # Append to log file (JSON Lines format)
        with open(self.log_file, "a") as f:
            f.write(log_entry.to_json() + "\n")

        return request_id

    def log_outcome(
        self,
        request_id: str,
        outcome: Outcome
    ) -> bool:
        """
        Log the outcome of executing routing decisions.

        Args:
            request_id: Request ID from log_decision()
            outcome: Outcome object with results

        Returns:
            True if outcome was logged, False if request_id not found

        Performance: <50ms (reads entire log file)
        """
        # Read all log entries
        entries = self._read_log_entries()

        # Find entry with matching request_id
        updated = False
        for entry in entries:
            if entry["request_id"] == request_id:
                entry["outcome"] = outcome.to_dict()
                entry["logged_at"] = datetime.utcnow().isoformat() + "Z"
                updated = True
                break

        if not updated:
            return False

        # Rewrite log file with updated entry
        with open(self.log_file, "w") as f:
            for entry in entries:
                f.write(json.dumps(entry, default=str) + "\n")

        return True

    def query_decisions(
        self,
        request_id: str = None,
        start_time: datetime = None,
        end_time: datetime = None,
        outcome_type: OutcomeType = None,
        has_outcome: bool = None,
        limit: int = 100
    ) -> List[DecisionLog]:
        """
        Query logged decisions with filters.

        Args:
            request_id: Filter by specific request ID
            start_time: Filter by timestamp >= start_time
            end_time: Filter by timestamp <= end_time
            outcome_type: Filter by outcome type (SUCCESS/FAILURE/PARTIAL/CANCELLED)
            has_outcome: Filter by whether outcome has been logged
            limit: Maximum number of results to return

        Returns:
            List of DecisionLog objects matching filters

        Performance: <100ms for typical log sizes (<1000 entries)
        """
        entries = self._read_log_entries()
        results = []

        for entry_dict in entries:
            # Apply filters
            if request_id and entry_dict.get("request_id") != request_id:
                continue

            if start_time:
                entry_time = datetime.fromisoformat(entry_dict["timestamp"].replace("Z", "+00:00"))
                # Remove timezone info for comparison if start_time is naive
                if start_time.tzinfo is None:
                    entry_time = entry_time.replace(tzinfo=None)
                if entry_time < start_time:
                    continue

            if end_time:
                entry_time = datetime.fromisoformat(entry_dict["timestamp"].replace("Z", "+00:00"))
                # Remove timezone info for comparison if end_time is naive
                if end_time.tzinfo is None:
                    entry_time = entry_time.replace(tzinfo=None)
                if entry_time > end_time:
                    continue

            if has_outcome is not None:
                if has_outcome and entry_dict.get("outcome") is None:
                    continue
                if not has_outcome and entry_dict.get("outcome") is not None:
                    continue

            if outcome_type and entry_dict.get("outcome"):
                if entry_dict["outcome"].get("outcome_type") != outcome_type.value:
                    continue

            # Convert dict to DecisionLog
            log_entry = DecisionLog(**entry_dict)
            results.append(log_entry)

            if len(results) >= limit:
                break

        return results

    def get_decision_statistics(self) -> Dict:
        """
        Get statistics about logged decisions.

        Returns:
            Dict with statistics:
            - total_decisions: Total number of logged decisions
            - decisions_with_outcomes: Number with outcomes logged
            - success_rate: Percentage of successful outcomes
            - avg_time_seconds: Average time taken for successful decisions
            - most_common_components: List of most frequently used components
            - confidence_accuracy: Correlation between confidence and success
        """
        entries = self._read_log_entries()

        total = len(entries)
        with_outcomes = sum(1 for e in entries if e.get("outcome"))

        # Success rate
        outcomes = [e["outcome"] for e in entries if e.get("outcome")]
        successes = sum(1 for o in outcomes if o["outcome_type"] == "success")
        success_rate = (successes / with_outcomes * 100) if with_outcomes > 0 else 0.0

        # Average time for successful outcomes
        success_times = [
            o["time_taken_seconds"]
            for o in outcomes
            if o["outcome_type"] == "success"
        ]
        avg_time = sum(success_times) / len(success_times) if success_times else 0.0

        # Most common components
        component_counts = {}
        for entry in entries:
            if "decisions" in entry and "execution_order" in entry["decisions"]:
                for component in entry["decisions"]["execution_order"]:
                    component_counts[component] = component_counts.get(component, 0) + 1

        most_common = sorted(
            component_counts.items(),
            key=lambda x: x[1],
            reverse=True
        )[:10]

        # Confidence accuracy (correlation between confidence and success)
        confidence_accuracy = self._calculate_confidence_accuracy(entries)

        return {
            "total_decisions": total,
            "decisions_with_outcomes": with_outcomes,
            "success_rate": round(success_rate, 2),
            "avg_time_seconds": round(avg_time, 2),
            "most_common_components": [
                {"component": comp, "count": count} for comp, count in most_common
            ],
            "confidence_accuracy": round(confidence_accuracy, 2)
        }

    def learn_from_outcomes(self) -> Dict[str, float]:
        """
        Analyze decision → outcome correlations to suggest confidence adjustments.

        Returns:
            Dict mapping component names to suggested confidence multipliers:
            - 1.0 = no change
            - >1.0 = should increase confidence (consistently successful)
            - <1.0 = should decrease confidence (frequently fails)

        Algorithm:
            1. Group outcomes by component
            2. Calculate success rate for each component
            3. Compare to overall success rate
            4. Suggest confidence adjustments based on deviation
        """
        entries = self._read_log_entries()

        # Filter entries with outcomes
        entries_with_outcomes = [e for e in entries if e.get("outcome")]

        if not entries_with_outcomes:
            return {}

        # Overall success rate
        total_successes = sum(
            1 for e in entries_with_outcomes
            if e["outcome"]["outcome_type"] == "success"
        )
        overall_success_rate = total_successes / len(entries_with_outcomes)

        # Success rate by component
        component_outcomes = {}  # component -> list of outcome types

        for entry in entries_with_outcomes:
            if "decisions" not in entry or "execution_order" not in entry["decisions"]:
                continue

            outcome_type = entry["outcome"]["outcome_type"]
            for component in entry["decisions"]["execution_order"]:
                if component not in component_outcomes:
                    component_outcomes[component] = []
                component_outcomes[component].append(outcome_type)

        # Calculate confidence adjustments
        confidence_adjustments = {}

        for component, outcomes in component_outcomes.items():
            if len(outcomes) < 3:  # Need at least 3 samples
                continue

            component_success_rate = sum(1 for o in outcomes if o == "success") / len(outcomes)

            # Calculate adjustment multiplier
            # If component_success_rate > overall: increase confidence
            # If component_success_rate < overall: decrease confidence
            if overall_success_rate > 0:
                multiplier = component_success_rate / overall_success_rate
                # Clamp to reasonable range (0.7 - 1.3)
                multiplier = max(0.7, min(1.3, multiplier))
                confidence_adjustments[component] = multiplier

        return confidence_adjustments

    def _read_log_entries(self) -> List[Dict]:
        """Read all log entries from file"""
        if not self.log_file.exists():
            return []

        entries = []
        with open(self.log_file, "r") as f:
            for line in f:
                line = line.strip()
                if line:
                    entries.append(json.loads(line))

        return entries

    def _diagnosis_to_dict(self, diagnosis: DiagnosisResult) -> Dict:
        """Convert DiagnosisResult to dict for JSON serialization"""
        return {
            "complexity": diagnosis.complexity,
            "complexity_confidence": diagnosis.complexity_confidence,
            "primary_domain": diagnosis.primary_domain.value,
            "secondary_domains": [d.value for d in diagnosis.secondary_domains],
            "domain_confidence": diagnosis.domain_confidence,
            "operation_type": diagnosis.operation_type.value,
            "operation_confidence": diagnosis.operation_confidence,
            "risks": [
                {
                    "category": r.category,
                    "level": r.level.value,
                    "confidence": r.confidence,
                    "reasoning": r.reasoning
                }
                for r in diagnosis.risks
            ],
            "capabilities_needed": diagnosis.capabilities_needed,
            "keywords_detected": diagnosis.keywords_detected,
            "word_count": diagnosis.word_count
        }

    def _decisions_to_dict(self, decisions: DecisionResult) -> Dict:
        """Convert DecisionResult to dict for JSON serialization"""
        return {
            "decisions": [
                {
                    "component_type": d.component_type,
                    "component_name": d.component_name,
                    "rationale": d.rationale,
                    "confidence": d.confidence,
                    "priority": d.priority.value,
                    "timing": d.timing,
                    "rule_applied": d.rule_applied
                }
                for d in decisions.decisions
            ],
            "total_confidence": decisions.total_confidence,
            "execution_order": decisions.execution_order,
            "human_approval_required": decisions.human_approval_required,
            "approval_reason": decisions.approval_reason
        }

    def _calculate_confidence_accuracy(self, entries: List[Dict]) -> float:
        """
        Calculate correlation between confidence and success rate.

        Returns:
            Correlation coefficient (0.0-1.0):
            - 1.0 = perfect correlation (high confidence → success)
            - 0.5 = random (confidence doesn't predict success)
            - 0.0 = no correlation or insufficient data
        """
        # Filter entries with outcomes
        entries_with_outcomes = [e for e in entries if e.get("outcome")]

        if len(entries_with_outcomes) < 5:  # Need at least 5 samples
            return 0.0

        # Group by confidence bins (0.0-0.6, 0.6-0.8, 0.8-1.0)
        bins = {
            "low": {"successes": 0, "total": 0},      # 0.0-0.6
            "medium": {"successes": 0, "total": 0},   # 0.6-0.8
            "high": {"successes": 0, "total": 0}      # 0.8-1.0
        }

        for entry in entries_with_outcomes:
            if "decisions" not in entry or "total_confidence" not in entry["decisions"]:
                continue

            confidence = entry["decisions"]["total_confidence"]
            is_success = entry["outcome"]["outcome_type"] == "success"

            # Determine bin
            if confidence < 0.6:
                bin_name = "low"
            elif confidence < 0.8:
                bin_name = "medium"
            else:
                bin_name = "high"

            bins[bin_name]["total"] += 1
            if is_success:
                bins[bin_name]["successes"] += 1

        # Calculate success rates for each bin
        success_rates = {}  # bin_name -> success_rate
        for bin_name, bin_data in bins.items():
            if bin_data["total"] > 0:
                rate = bin_data["successes"] / bin_data["total"]
                success_rates[bin_name] = rate

        # Check if success rate increases with confidence
        if len(success_rates) == 0:
            return 0.0

        # Perfect correlation: high > medium > low
        if "low" in success_rates and "medium" in success_rates and "high" in success_rates:
            if success_rates["high"] > success_rates["medium"] > success_rates["low"]:
                return (success_rates["low"] + success_rates["medium"] + success_rates["high"]) / 3
            elif success_rates["high"] > success_rates["low"]:
                return (success_rates["low"] + success_rates["high"]) / 4
            else:
                return 0.0

        # Partial correlation: high > low (no medium data)
        if "low" in success_rates and "high" in success_rates:
            if success_rates["high"] > success_rates["low"]:
                # Return average as correlation indicator
                return (success_rates["low"] + success_rates["high"]) / 3
            else:
                return 0.0

        # Only one bin has data
        return 0.0


def main():
    """CLI interface for testing"""
    import sys
    from argparse import ArgumentParser

    parser = ArgumentParser(description="Accountability Logger CLI")
    parser.add_argument("command", choices=["stats", "query", "learn"], help="Command to run")
    parser.add_argument("--log-file", help="Path to log file")
    parser.add_argument("--request-id", help="Filter by request ID")
    parser.add_argument("--outcome", choices=["success", "failure", "partial", "cancelled"], help="Filter by outcome type")
    parser.add_argument("--last", type=int, default=24, help="Last N hours (default: 24)")
    parser.add_argument("--limit", type=int, default=100, help="Maximum results (default: 100)")

    args = parser.parse_args()

    # Initialize logger
    logger = AccountabilityLogger(log_file=args.log_file)

    if args.command == "stats":
        # Show statistics
        stats = logger.get_decision_statistics()
        print("\n" + "="*60)
        print("DECISION STATISTICS")
        print("="*60 + "\n")
        print(f"Total Decisions: {stats['total_decisions']}")
        print(f"With Outcomes: {stats['decisions_with_outcomes']}")
        print(f"Success Rate: {stats['success_rate']}%")
        print(f"Avg Time (success): {stats['avg_time_seconds']}s")
        print(f"Confidence Accuracy: {stats['confidence_accuracy']}")
        print(f"\nMost Common Components:")
        for item in stats['most_common_components'][:5]:
            print(f"  {item['component']}: {item['count']}")
        print("\n" + "="*60 + "\n")

    elif args.command == "query":
        # Query decisions
        start_time = datetime.utcnow() - timedelta(hours=args.last)
        outcome_type = OutcomeType(args.outcome) if args.outcome else None

        results = logger.query_decisions(
            request_id=args.request_id,
            start_time=start_time,
            outcome_type=outcome_type,
            limit=args.limit
        )

        print("\n" + "="*60)
        print(f"QUERY RESULTS ({len(results)} entries)")
        print("="*60 + "\n")

        for entry in results:
            print(f"Request ID: {entry.request_id}")
            print(f"Timestamp: {entry.timestamp}")
            print(f"Request: {entry.user_request[:60]}...")
            print(f"Components: {', '.join(entry.decisions['execution_order'][:3])}")
            if entry.outcome:
                print(f"Outcome: {entry.outcome['outcome_type']} ({entry.outcome['time_taken_seconds']}s)")
            else:
                print("Outcome: Not logged yet")
            print()

    elif args.command == "learn":
        # Show learning recommendations
        adjustments = logger.learn_from_outcomes()
        print("\n" + "="*60)
        print("CONFIDENCE ADJUSTMENT RECOMMENDATIONS")
        print("="*60 + "\n")

        if not adjustments:
            print("Insufficient data for learning (need at least 3 outcomes per component)")
        else:
            for component, multiplier in sorted(adjustments.items(), key=lambda x: x[1]):
                action = "DECREASE" if multiplier < 1.0 else "INCREASE" if multiplier > 1.0 else "OK"
                print(f"{component}: {multiplier:.2f}x ({action})")

        print("\n" + "="*60 + "\n")


if __name__ == "__main__":
    main()
