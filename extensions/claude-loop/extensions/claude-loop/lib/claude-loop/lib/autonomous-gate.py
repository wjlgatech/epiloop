#!/usr/bin/env python3
"""
autonomous-gate.py - Autonomous Mode Gate for claude-loop (SI-014)

Implements safeguards before enabling fully autonomous self-improvement.
Checks multiple gate criteria that must all pass before autonomous mode
can be enabled.

Gate Criteria:
1. Classification accuracy >80% (from accuracy_history.jsonl)
2. At least 3 successful improvement cycles completed (improvement_history.jsonl)
3. Zero rollbacks in last 5 improvements (rollback_history.jsonl)
4. Explicit user opt-in via config.json (autonomous_enabled: true)

Usage:
    python lib/autonomous-gate.py status      # Show all gate status
    python lib/autonomous-gate.py check       # Run all gate checks
    python lib/autonomous-gate.py approve <prd>  # Auto-approve if allowed
    python lib/autonomous-gate.py enable      # Enable autonomous mode
    python lib/autonomous-gate.py disable     # Disable autonomous mode
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any


# ============================================================================
# Configuration
# ============================================================================

# Gate thresholds
ACCURACY_THRESHOLD = 0.80  # 80% classification accuracy required
MIN_SUCCESSFUL_CYCLES = 3  # At least 3 successful improvement cycles
ROLLBACK_LOOKBACK = 5  # Check last 5 improvements for rollbacks
DEFAULT_RISK_THRESHOLD = 5  # Only auto-approve priority < 5 (low-risk)

# File paths (relative to project root)
CONFIG_FILE = "config.json"
CLAUDE_LOOP_DIR = ".claude-loop"
ACCURACY_HISTORY_FILE = f"{CLAUDE_LOOP_DIR}/accuracy_history.jsonl"
IMPROVEMENT_HISTORY_FILE = f"{CLAUDE_LOOP_DIR}/improvement_history.jsonl"
ROLLBACK_HISTORY_FILE = f"{CLAUDE_LOOP_DIR}/rollback_history.jsonl"
AUTONOMOUS_DECISIONS_FILE = f"{CLAUDE_LOOP_DIR}/autonomous_decisions.jsonl"
IMPROVEMENTS_DIR = f"{CLAUDE_LOOP_DIR}/improvements"


class GateCriteria(Enum):
    """Gate criteria identifiers."""

    CLASSIFICATION_ACCURACY = "classification_accuracy"
    SUCCESSFUL_CYCLES = "successful_cycles"
    ZERO_ROLLBACKS = "zero_rollbacks"
    USER_OPT_IN = "user_opt_in"


@dataclass
class GateCheckResult:
    """Result of a single gate check."""

    criteria: GateCriteria
    passed: bool
    current_value: Any
    required_value: Any
    message: str
    recommendation: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "criteria": self.criteria.value,
            "passed": self.passed,
            "current_value": self.current_value,
            "required_value": self.required_value,
            "message": self.message,
            "recommendation": self.recommendation,
        }


@dataclass
class GateResult:
    """Result of all gate checks."""

    all_passed: bool
    checks: list[GateCheckResult]
    autonomous_ready: bool
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"))
    risk_threshold: int = DEFAULT_RISK_THRESHOLD

    def to_dict(self) -> dict[str, Any]:
        return {
            "all_passed": self.all_passed,
            "autonomous_ready": self.autonomous_ready,
            "timestamp": self.timestamp,
            "risk_threshold": self.risk_threshold,
            "checks": [c.to_dict() for c in self.checks],
            "summary": self._generate_summary(),
        }

    def _generate_summary(self) -> str:
        """Generate a summary of gate status."""
        passed = sum(1 for c in self.checks if c.passed)
        total = len(self.checks)

        if self.all_passed:
            return f"All {total} gates passed. Autonomous mode ready."
        else:
            failed = [c for c in self.checks if not c.passed]
            failed_names = [c.criteria.value for c in failed]
            return f"{passed}/{total} gates passed. Failed: {', '.join(failed_names)}"


@dataclass
class ApprovalDecision:
    """Result of an autonomous approval decision."""

    prd_name: str
    approved: bool
    auto_approved: bool
    reason: str
    risk_level: str  # low, medium, high
    priority: int
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"))

    def to_dict(self) -> dict[str, Any]:
        return {
            "prd_name": self.prd_name,
            "approved": self.approved,
            "auto_approved": self.auto_approved,
            "reason": self.reason,
            "risk_level": self.risk_level,
            "priority": self.priority,
            "timestamp": self.timestamp,
        }


class AutonomousGate:
    """
    Gate controller for autonomous mode.

    Checks all criteria before enabling autonomous self-improvement.
    """

    def __init__(self, project_root: Path | None = None):
        """
        Initialize the gate controller.

        Args:
            project_root: Path to project root. If None, uses parent of lib/.
        """
        if project_root is None:
            project_root = Path(__file__).parent.parent

        self.project_root = project_root
        self.config_file = project_root / CONFIG_FILE
        self.accuracy_history_file = project_root / ACCURACY_HISTORY_FILE
        self.improvement_history_file = project_root / IMPROVEMENT_HISTORY_FILE
        self.rollback_history_file = project_root / ROLLBACK_HISTORY_FILE
        self.autonomous_decisions_file = project_root / AUTONOMOUS_DECISIONS_FILE
        self.improvements_dir = project_root / IMPROVEMENTS_DIR

        # Ensure directories exist
        (project_root / CLAUDE_LOOP_DIR).mkdir(exist_ok=True)

    # ============================================================================
    # Configuration Management
    # ============================================================================

    def _load_config(self) -> dict[str, Any]:
        """Load config.json."""
        if not self.config_file.exists():
            return {}

        with open(self.config_file) as f:
            return json.load(f)

    def _save_config(self, config: dict[str, Any]) -> None:
        """Save config.json."""
        with open(self.config_file, "w") as f:
            json.dump(config, f, indent=2)

    def is_autonomous_enabled(self) -> bool:
        """Check if autonomous mode is enabled in config."""
        config = self._load_config()
        return config.get("autonomous_enabled", False)

    def get_risk_threshold(self) -> int:
        """Get the risk threshold for auto-approval."""
        config = self._load_config()
        return config.get("autonomous_risk_threshold", DEFAULT_RISK_THRESHOLD)

    def enable_autonomous(self) -> bool:
        """
        Enable autonomous mode.

        Returns:
            True if enabled successfully, False if gates don't pass.
        """
        # Check all gates first
        result = self.check_all_gates()

        if not result.all_passed:
            return False

        # Update config
        config = self._load_config()
        config["autonomous_enabled"] = True
        config["autonomous_enabled_at"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        self._save_config(config)

        # Log decision
        self._log_autonomous_decision(
            prd_name="system",
            approved=True,
            auto_approved=False,
            reason="Autonomous mode enabled by user",
            risk_level="system",
            priority=0,
        )

        return True

    def disable_autonomous(self) -> None:
        """Disable autonomous mode."""
        config = self._load_config()
        config["autonomous_enabled"] = False
        config["autonomous_disabled_at"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        self._save_config(config)

        # Log decision
        self._log_autonomous_decision(
            prd_name="system",
            approved=False,
            auto_approved=False,
            reason="Autonomous mode disabled by user",
            risk_level="system",
            priority=0,
        )

    # ============================================================================
    # Gate Checks
    # ============================================================================

    def check_classification_accuracy(self) -> GateCheckResult:
        """
        Check if classification accuracy meets threshold.

        Reads from .claude-loop/accuracy_history.jsonl and checks if
        the most recent accuracy value is >= 80%.
        """
        if not self.accuracy_history_file.exists():
            return GateCheckResult(
                criteria=GateCriteria.CLASSIFICATION_ACCURACY,
                passed=False,
                current_value=None,
                required_value=ACCURACY_THRESHOLD,
                message="No accuracy history found",
                recommendation=(
                    "Run classification validation tests: "
                    "./claude-loop.sh --validate-classifier"
                ),
            )

        # Read the most recent accuracy entry
        latest_accuracy = None
        with open(self.accuracy_history_file) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    latest_accuracy = data.get("accuracy", 0)
                except json.JSONDecodeError:
                    continue

        if latest_accuracy is None:
            return GateCheckResult(
                criteria=GateCriteria.CLASSIFICATION_ACCURACY,
                passed=False,
                current_value=None,
                required_value=ACCURACY_THRESHOLD,
                message="No valid accuracy data found",
                recommendation=(
                    "Run classification validation tests: "
                    "./claude-loop.sh --validate-classifier"
                ),
            )

        passed = latest_accuracy >= ACCURACY_THRESHOLD

        return GateCheckResult(
            criteria=GateCriteria.CLASSIFICATION_ACCURACY,
            passed=passed,
            current_value=latest_accuracy,
            required_value=ACCURACY_THRESHOLD,
            message=(
                f"Classification accuracy: {latest_accuracy:.1%} "
                f"({'meets' if passed else 'below'} {ACCURACY_THRESHOLD:.0%} threshold)"
            ),
            recommendation="" if passed else (
                "Improve classifier accuracy by adding more patterns or "
                "updating heuristics in lib/failure-classifier.py"
            ),
        )

    def check_successful_cycles(self) -> GateCheckResult:
        """
        Check if at least 3 successful improvement cycles have completed.

        Reads from .claude-loop/improvement_history.jsonl and counts
        entries with action="completed" or action="execution_completed" with success.
        """
        if not self.improvement_history_file.exists():
            return GateCheckResult(
                criteria=GateCriteria.SUCCESSFUL_CYCLES,
                passed=False,
                current_value=0,
                required_value=MIN_SUCCESSFUL_CYCLES,
                message="No improvement history found",
                recommendation=(
                    "Complete improvement cycles using: "
                    "./claude-loop.sh --execute-improvement <prd_name>"
                ),
            )

        # Count successful completions
        successful_count = 0
        completed_prds = set()

        with open(self.improvement_history_file) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    action = data.get("action", "")
                    prd_name = data.get("prd_name", "")
                    details = data.get("details", "")

                    # Count unique PRD completions
                    if action == "completed" or (
                        action == "execution_completed" and "success" in details.lower()
                    ):
                        if prd_name and prd_name not in completed_prds:
                            completed_prds.add(prd_name)
                            successful_count += 1

                except json.JSONDecodeError:
                    continue

        passed = successful_count >= MIN_SUCCESSFUL_CYCLES

        return GateCheckResult(
            criteria=GateCriteria.SUCCESSFUL_CYCLES,
            passed=passed,
            current_value=successful_count,
            required_value=MIN_SUCCESSFUL_CYCLES,
            message=(
                f"Successful improvement cycles: {successful_count} "
                f"({'meets' if passed else 'below'} {MIN_SUCCESSFUL_CYCLES} minimum)"
            ),
            recommendation="" if passed else (
                f"Complete {MIN_SUCCESSFUL_CYCLES - successful_count} more "
                "improvement cycles before enabling autonomous mode"
            ),
        )

    def check_zero_rollbacks(self) -> GateCheckResult:
        """
        Check that there are zero rollbacks in the last 5 improvements.

        Reads from .claude-loop/rollback_history.jsonl and checks
        if any rollbacks occurred in the most recent improvements.
        """
        if not self.rollback_history_file.exists():
            # No rollback history = no rollbacks = pass
            return GateCheckResult(
                criteria=GateCriteria.ZERO_ROLLBACKS,
                passed=True,
                current_value=0,
                required_value=0,
                message="No rollback history found (no rollbacks recorded)",
                recommendation="",
            )

        # Get all rollbacks
        rollbacks = []
        with open(self.rollback_history_file) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    if data.get("action") == "rolled_back":
                        rollbacks.append(data)
                except json.JSONDecodeError:
                    continue

        # Count rollbacks in the lookback window
        # We need to compare with improvement history to get the last N improvements
        recent_improvements = self._get_recent_improvements(ROLLBACK_LOOKBACK)
        recent_prd_names = {imp.get("prd_name") for imp in recent_improvements}

        rollbacks_in_window = [
            r for r in rollbacks
            if r.get("prd_name") in recent_prd_names
        ]

        rollback_count = len(rollbacks_in_window)
        passed = rollback_count == 0

        return GateCheckResult(
            criteria=GateCriteria.ZERO_ROLLBACKS,
            passed=passed,
            current_value=rollback_count,
            required_value=0,
            message=(
                f"Rollbacks in last {ROLLBACK_LOOKBACK} improvements: {rollback_count} "
                f"({'none' if passed else 'has rollbacks'})"
            ),
            recommendation="" if passed else (
                f"Resolve {rollback_count} rollback(s) before enabling autonomous mode. "
                "Investigate root causes and improve validation."
            ),
        )

    def _get_recent_improvements(self, count: int) -> list[dict]:
        """Get the most recent N improvement entries."""
        if not self.improvement_history_file.exists():
            return []

        # Read all entries, get the last N unique PRDs that were started/completed
        entries = []
        with open(self.improvement_history_file) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    continue

        # Get unique PRD names from recent entries (in order)
        seen_prds = []
        for entry in reversed(entries):
            prd_name = entry.get("prd_name", "")
            if prd_name and prd_name not in seen_prds:
                seen_prds.append(prd_name)
                if len(seen_prds) >= count:
                    break

        # Return entries for these PRDs
        return [
            {"prd_name": prd}
            for prd in seen_prds[:count]
        ]

    def check_user_opt_in(self) -> GateCheckResult:
        """
        Check if user has explicitly opted in via config.json.

        Looks for autonomous_enabled: true in config.json.
        """
        config = self._load_config()
        enabled = config.get("autonomous_enabled", False)

        return GateCheckResult(
            criteria=GateCriteria.USER_OPT_IN,
            passed=enabled,
            current_value=enabled,
            required_value=True,
            message=(
                f"User opt-in: {'enabled' if enabled else 'not enabled'}"
            ),
            recommendation="" if enabled else (
                "Enable autonomous mode with: "
                "python lib/autonomous-gate.py enable"
            ),
        )

    def check_all_gates(self, include_opt_in: bool = True) -> GateResult:
        """
        Run all gate checks and return combined result.

        Args:
            include_opt_in: Whether to include user opt-in check.
                           Set to False when checking readiness before enabling.

        Returns:
            GateResult with all check results and overall status.
        """
        checks = [
            self.check_classification_accuracy(),
            self.check_successful_cycles(),
            self.check_zero_rollbacks(),
        ]

        if include_opt_in:
            checks.append(self.check_user_opt_in())

        all_passed = all(c.passed for c in checks)

        # Autonomous ready only if all gates pass
        autonomous_ready = all_passed

        return GateResult(
            all_passed=all_passed,
            checks=checks,
            autonomous_ready=autonomous_ready,
            risk_threshold=self.get_risk_threshold(),
        )

    # ============================================================================
    # Autonomous Approval
    # ============================================================================

    def _get_prd_priority(self, prd_name: str) -> int | None:
        """Get the priority of a PRD from its file."""
        prd_file = self.improvements_dir / f"{prd_name}.json"

        if not prd_file.exists():
            return None

        with open(prd_file) as f:
            prd_data = json.load(f)

        # Priority can be in different places depending on PRD structure
        priority = prd_data.get("priority")
        if priority is not None:
            return int(priority)

        # Try to get average priority of user stories
        stories = prd_data.get("userStories", [])
        if stories:
            priorities = [s.get("priority", 10) for s in stories]
            return min(priorities)  # Use lowest (highest priority)

        return None

    def _get_risk_level(self, priority: int) -> str:
        """Determine risk level from priority."""
        if priority <= 3:
            return "low"
        elif priority <= 7:
            return "medium"
        else:
            return "high"

    def can_auto_approve(self, prd_name: str) -> tuple[bool, str]:
        """
        Check if a PRD can be auto-approved.

        Returns:
            Tuple of (can_approve, reason)
        """
        # Check if autonomous mode is enabled
        if not self.is_autonomous_enabled():
            return False, "Autonomous mode is not enabled"

        # Check all gates
        gate_result = self.check_all_gates()
        if not gate_result.all_passed:
            failed = [c for c in gate_result.checks if not c.passed]
            failed_names = [c.criteria.value for c in failed]
            return False, f"Gate checks failed: {', '.join(failed_names)}"

        # Get PRD priority
        priority = self._get_prd_priority(prd_name)
        if priority is None:
            return False, f"PRD not found: {prd_name}"

        # Check against risk threshold
        risk_threshold = self.get_risk_threshold()
        if priority >= risk_threshold:
            return False, (
                f"PRD priority ({priority}) exceeds risk threshold ({risk_threshold}). "
                "Manual approval required."
            )

        return True, "PRD meets auto-approval criteria"

    def auto_approve(self, prd_name: str) -> ApprovalDecision:
        """
        Attempt to auto-approve a PRD.

        Args:
            prd_name: Name of the PRD to approve

        Returns:
            ApprovalDecision with result
        """
        can_approve, reason = self.can_auto_approve(prd_name)

        priority = self._get_prd_priority(prd_name) or 10
        risk_level = self._get_risk_level(priority)

        decision = ApprovalDecision(
            prd_name=prd_name,
            approved=can_approve,
            auto_approved=can_approve,
            reason=reason,
            risk_level=risk_level,
            priority=priority,
        )

        # Log the decision
        self._log_autonomous_decision(
            prd_name=prd_name,
            approved=decision.approved,
            auto_approved=decision.auto_approved,
            reason=decision.reason,
            risk_level=decision.risk_level,
            priority=decision.priority,
        )

        return decision

    def _log_autonomous_decision(
        self,
        prd_name: str,
        approved: bool,
        auto_approved: bool,
        reason: str,
        risk_level: str,
        priority: int,
    ) -> None:
        """Log an autonomous decision to the audit file."""
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "prd_name": prd_name,
            "approved": approved,
            "auto_approved": auto_approved,
            "reason": reason,
            "risk_level": risk_level,
            "priority": priority,
        }

        with open(self.autonomous_decisions_file, "a") as f:
            f.write(json.dumps(entry) + "\n")

    def get_decision_history(self, limit: int = 20) -> list[dict]:
        """Get recent autonomous decisions."""
        if not self.autonomous_decisions_file.exists():
            return []

        decisions = []
        with open(self.autonomous_decisions_file) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    decisions.append(json.loads(line))
                except json.JSONDecodeError:
                    continue

        return decisions[-limit:]


# ============================================================================
# CLI Interface
# ============================================================================

def print_gate_status(gate: AutonomousGate, output_json: bool = False) -> None:
    """Print current gate status."""
    result = gate.check_all_gates(include_opt_in=True)

    if output_json:
        print(json.dumps(result.to_dict(), indent=2))
        return

    print("=" * 70)
    print("AUTONOMOUS MODE GATE STATUS")
    print("=" * 70)
    print()

    for check in result.checks:
        status = "[PASS]" if check.passed else "[FAIL]"
        print(f"{status} {check.criteria.value}")
        print(f"       Current: {check.current_value}")
        print(f"       Required: {check.required_value}")
        print(f"       {check.message}")
        if not check.passed and check.recommendation:
            print(f"       Recommendation: {check.recommendation}")
        print()

    print("-" * 70)
    print(f"Overall: {result._generate_summary()}")
    print(f"Risk Threshold: priority < {result.risk_threshold}")
    print()


def main():
    parser = argparse.ArgumentParser(
        description="Autonomous Mode Gate for claude-loop",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python lib/autonomous-gate.py status        # Show all gate status
    python lib/autonomous-gate.py check         # Check if ready for autonomous mode
    python lib/autonomous-gate.py approve <prd> # Auto-approve if allowed
    python lib/autonomous-gate.py enable        # Enable autonomous mode
    python lib/autonomous-gate.py disable       # Disable autonomous mode
    python lib/autonomous-gate.py history       # Show approval history
        """,
    )

    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # status command
    status_parser = subparsers.add_parser(
        "status", help="Show current gate status"
    )
    status_parser.add_argument(
        "--json", action="store_true", help="Output as JSON"
    )

    # check command
    check_parser = subparsers.add_parser(
        "check", help="Check if ready for autonomous mode"
    )
    check_parser.add_argument(
        "--json", action="store_true", help="Output as JSON"
    )

    # approve command
    approve_parser = subparsers.add_parser(
        "approve", help="Auto-approve a PRD if allowed"
    )
    approve_parser.add_argument(
        "prd_name", help="Name of the PRD to approve"
    )
    approve_parser.add_argument(
        "--json", action="store_true", help="Output as JSON"
    )

    # enable command
    enable_parser = subparsers.add_parser(
        "enable", help="Enable autonomous mode"
    )
    enable_parser.add_argument(
        "--force", action="store_true",
        help="Force enable even if gates don't pass (not recommended)"
    )

    # disable command
    subparsers.add_parser(
        "disable", help="Disable autonomous mode"
    )

    # history command
    history_parser = subparsers.add_parser(
        "history", help="Show autonomous decision history"
    )
    history_parser.add_argument(
        "--limit", type=int, default=20,
        help="Number of entries to show (default: 20)"
    )
    history_parser.add_argument(
        "--json", action="store_true", help="Output as JSON"
    )

    # set-threshold command
    threshold_parser = subparsers.add_parser(
        "set-threshold", help="Set the risk threshold for auto-approval"
    )
    threshold_parser.add_argument(
        "threshold", type=int,
        help="Priority threshold (PRDs with priority >= this require manual approval)"
    )

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    # Initialize gate
    script_dir = Path(__file__).parent
    project_root = script_dir.parent
    gate = AutonomousGate(project_root=project_root)

    if args.command == "status":
        print_gate_status(gate, output_json=args.json)

    elif args.command == "check":
        # Check readiness without requiring opt-in
        result = gate.check_all_gates(include_opt_in=False)

        if args.json:
            output = result.to_dict()
            output["ready_to_enable"] = result.all_passed
            print(json.dumps(output, indent=2))
        else:
            print("=" * 70)
            print("AUTONOMOUS MODE READINESS CHECK")
            print("=" * 70)
            print()

            for check in result.checks:
                status = "[PASS]" if check.passed else "[FAIL]"
                print(f"{status} {check.criteria.value}: {check.message}")

            print()
            if result.all_passed:
                print("[OK] All criteria met. Ready to enable autonomous mode.")
                print("     Run: python lib/autonomous-gate.py enable")
            else:
                print("[NOT READY] Some criteria not met.")
                failed = [c for c in result.checks if not c.passed]
                print("     Fix these issues first:")
                for c in failed:
                    if c.recommendation:
                        print(f"     - {c.recommendation}")

        sys.exit(0 if result.all_passed else 1)

    elif args.command == "approve":
        decision = gate.auto_approve(args.prd_name)

        if args.json:
            print(json.dumps(decision.to_dict(), indent=2))
        else:
            if decision.approved:
                print(f"[APPROVED] PRD '{args.prd_name}' auto-approved")
                print(f"           Risk level: {decision.risk_level}")
                print(f"           Priority: {decision.priority}")
            else:
                print(f"[NOT APPROVED] PRD '{args.prd_name}'")
                print(f"               Reason: {decision.reason}")

        sys.exit(0 if decision.approved else 1)

    elif args.command == "enable":
        if args.force:
            # Force enable without gate checks
            config = gate._load_config()
            config["autonomous_enabled"] = True
            config["autonomous_enabled_at"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
            config["autonomous_force_enabled"] = True
            gate._save_config(config)
            print("[WARNING] Autonomous mode force-enabled without gate checks")
            print("          This is not recommended for production use.")
        else:
            # Check gates first
            result = gate.check_all_gates(include_opt_in=False)
            if not result.all_passed:
                print("[ERROR] Cannot enable autonomous mode - gate checks failed")
                print()
                for check in result.checks:
                    if not check.passed:
                        print(f"        - {check.message}")
                        if check.recommendation:
                            print(f"          {check.recommendation}")
                print()
                print("        Use --force to override (not recommended)")
                sys.exit(1)

            # Enable autonomous mode
            config = gate._load_config()
            config["autonomous_enabled"] = True
            config["autonomous_enabled_at"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
            gate._save_config(config)

            print("[OK] Autonomous mode enabled")
            print(f"     Risk threshold: priority < {gate.get_risk_threshold()}")
            print("     Use 'disable' command to turn off")

    elif args.command == "disable":
        gate.disable_autonomous()
        print("[OK] Autonomous mode disabled")
        print("     All improvements will require manual approval")

    elif args.command == "history":
        decisions = gate.get_decision_history(limit=args.limit)

        if args.json:
            print(json.dumps(decisions, indent=2))
        else:
            if not decisions:
                print("No autonomous decisions recorded")
                return

            print("=" * 80)
            print("AUTONOMOUS DECISION HISTORY")
            print("=" * 80)
            print()
            print(f"{'Timestamp':<25} {'PRD Name':<35} {'Result':<12} {'Risk':<8}")
            print("-" * 80)

            for d in decisions:
                timestamp = d.get("timestamp", "")[:19].replace("T", " ")
                prd_name = d.get("prd_name", "")[:33]
                result = "APPROVED" if d.get("approved") else "DENIED"
                risk = d.get("risk_level", "?")
                auto = " (auto)" if d.get("auto_approved") else ""

                print(f"{timestamp:<25} {prd_name:<35} {result + auto:<12} {risk:<8}")

    elif args.command == "set-threshold":
        config = gate._load_config()
        config["autonomous_risk_threshold"] = args.threshold
        gate._save_config(config)
        print(f"[OK] Risk threshold set to {args.threshold}")
        print(f"     PRDs with priority >= {args.threshold} will require manual approval")


if __name__ == "__main__":
    main()
