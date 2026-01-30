#!/usr/bin/env python3
"""
Transparency Layer with Explanations

Provides 4 levels of transparency for orchestrator decisions:
- Level 0 (Silent): No notification for obvious decisions
- Level 1 (Brief): One-line notification for automatic significant decisions
- Level 2 (Detailed): Full rationale with alternatives for essential decisions
- Level 3 (Full Audit): Complete decision log with all rules evaluated
"""

import sys
from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass
from enum import Enum

# Import orchestrator types
sys.path.insert(0, str(Path(__file__).parent))
from diagnosis import DiagnosisResult
from decision_engine import DecisionResult, RoutingDecision


class TransparencyLevel(int, Enum):
    """Transparency levels for decision explanations"""
    SILENT = 0      # No notification (obvious decisions)
    BRIEF = 1       # One-line notification (automatic significant)
    DETAILED = 2    # Full rationale (essential decisions)
    FULL_AUDIT = 3  # Complete decision log (on demand via --explain)


@dataclass
class Explanation:
    """Explanation of a routing decision"""
    level: TransparencyLevel
    summary: str                          # Brief summary
    rationale: Optional[str] = None       # Why this decision was made
    alternatives: Optional[List[str]] = None  # Other options considered
    confidence: Optional[float] = None    # Confidence score
    rules_evaluated: Optional[List[Dict]] = None  # All rules checked (Level 3 only)
    recommendations: Optional[str] = None  # What to do next


class TransparencyLayer:
    """
    Generates explanations for orchestrator decisions at different transparency levels.

    Levels:
    - Silent (0): No explanation (obvious decisions like selecting code-reviewer for code review)
    - Brief (1): One-line explanation (e.g., "Using brainstorming skill (complexity: 7/10)")
    - Detailed (2): Full explanation with rationale, alternatives, confidence
    - Full Audit (3): Complete log with all rules evaluated, confidence calculations
    """

    def __init__(self):
        """Initialize transparency layer"""
        pass

    def explain(
        self,
        user_request: str,
        diagnosis: DiagnosisResult,
        decisions: DecisionResult,
        level: TransparencyLevel = TransparencyLevel.BRIEF
    ) -> Explanation:
        """
        Generate explanation at specified transparency level.

        Args:
            user_request: Original user request
            diagnosis: Situation diagnosis
            decisions: Routing decisions
            level: Transparency level (0-3)

        Returns:
            Explanation object with appropriate detail level
        """
        if level == TransparencyLevel.SILENT:
            return self._explain_silent(decisions)
        elif level == TransparencyLevel.BRIEF:
            return self._explain_brief(user_request, diagnosis, decisions)
        elif level == TransparencyLevel.DETAILED:
            return self._explain_detailed(user_request, diagnosis, decisions)
        elif level == TransparencyLevel.FULL_AUDIT:
            return self._explain_full_audit(user_request, diagnosis, decisions)
        else:
            raise ValueError(f"Invalid transparency level: {level}")

    def should_notify(
        self,
        decisions: DecisionResult,
        user_expertise_level: str = "intermediate"
    ) -> TransparencyLevel:
        """
        Determine appropriate transparency level based on decision significance.

        Args:
            decisions: Routing decisions
            user_expertise_level: "beginner", "intermediate", "expert"

        Returns:
            Recommended transparency level

        Decision Logic:
        - Silent (0): Obvious/routine decisions (code-reviewer for code review)
        - Brief (1): Significant automatic decisions (brainstorming, security-auditor)
        - Detailed (2): Essential decisions requiring approval
        - Full Audit (3): Only on explicit --explain flag
        """
        # Essential decisions requiring approval → Detailed (Level 2)
        if decisions.human_approval_required:
            return TransparencyLevel.DETAILED

        # Check if any mandatory skills or high-priority agents
        has_mandatory = any(
            d.component_type == "skill" and d.priority.value == 1
            for d in decisions.decisions
        )

        has_high_priority_agent = any(
            d.component_type == "agent" and d.priority.value <= 2
            for d in decisions.decisions
        )

        # Significant decisions → Brief (Level 1)
        if has_mandatory or has_high_priority_agent:
            # Experts prefer less notification
            if user_expertise_level == "expert":
                return TransparencyLevel.SILENT
            return TransparencyLevel.BRIEF

        # Routine decisions → Silent (Level 0)
        return TransparencyLevel.SILENT

    def format_explanation(self, explanation: Explanation) -> str:
        """
        Format explanation for display.

        Args:
            explanation: Explanation object

        Returns:
            Formatted string for display
        """
        if explanation.level == TransparencyLevel.SILENT:
            return ""  # No output

        if explanation.level == TransparencyLevel.BRIEF:
            return f"ℹ️  {explanation.summary}"

        if explanation.level == TransparencyLevel.DETAILED:
            lines = [
                "=" * 60,
                "ORCHESTRATOR DECISION",
                "=" * 60,
                "",
                f"Summary: {explanation.summary}",
                ""
            ]

            if explanation.rationale:
                lines.extend([
                    "Rationale:",
                    f"  {explanation.rationale}",
                    ""
                ])

            if explanation.alternatives:
                lines.extend([
                    "Alternatives Considered:",
                    *[f"  • {alt}" for alt in explanation.alternatives],
                    ""
                ])

            if explanation.confidence:
                lines.extend([
                    f"Confidence: {explanation.confidence:.0%}",
                    ""
                ])

            if explanation.recommendations:
                lines.extend([
                    "Recommendations:",
                    f"  {explanation.recommendations}",
                    ""
                ])

            lines.append("=" * 60)
            return "\n".join(lines)

        if explanation.level == TransparencyLevel.FULL_AUDIT:
            lines = [
                "=" * 60,
                "FULL ORCHESTRATOR AUDIT",
                "=" * 60,
                "",
                f"Summary: {explanation.summary}",
                ""
            ]

            if explanation.rationale:
                lines.extend([
                    "Decision Rationale:",
                    f"  {explanation.rationale}",
                    ""
                ])

            if explanation.rules_evaluated:
                lines.extend([
                    "Rules Evaluated:",
                    ""
                ])
                for rule in explanation.rules_evaluated:
                    lines.extend([
                        f"  Rule: {rule['rule_name']}",
                        f"  Matched: {rule['matched']}",
                        f"  Confidence: {rule['confidence']:.2f}",
                        ""
                    ])

            if explanation.alternatives:
                lines.extend([
                    "Alternatives Considered:",
                    *[f"  • {alt}" for alt in explanation.alternatives],
                    ""
                ])

            if explanation.confidence:
                lines.extend([
                    f"Overall Confidence: {explanation.confidence:.0%}",
                    ""
                ])

            if explanation.recommendations:
                lines.extend([
                    "Recommendations:",
                    f"  {explanation.recommendations}",
                    ""
                ])

            lines.append("=" * 60)
            return "\n".join(lines)

        return str(explanation)

    def _explain_silent(self, decisions: DecisionResult) -> Explanation:
        """Level 0: Silent - no explanation needed"""
        return Explanation(
            level=TransparencyLevel.SILENT,
            summary="Routine decision - no notification needed"
        )

    def _explain_brief(
        self,
        user_request: str,
        diagnosis: DiagnosisResult,
        decisions: DecisionResult
    ) -> Explanation:
        """Level 1: Brief - one-line notification"""
        # Build summary from decisions
        components = []

        for decision in decisions.decisions:
            if decision.component_type == "skill":
                # e.g., "Using brainstorming skill (complexity: 7/10)"
                if decision.component_name == "brainstorming":
                    components.append(f"Using brainstorming skill (complexity: {diagnosis.complexity}/10)")
                else:
                    components.append(f"Using {decision.component_name} skill")

            elif decision.component_type == "agent":
                # e.g., "Using security-auditor agent (security risk detected)"
                if decision.component_name == "security-auditor":
                    risk_reason = "security risk detected" if diagnosis.risks else "security domain"
                    components.append(f"Using security-auditor agent ({risk_reason})")
                else:
                    components.append(f"Using {decision.component_name} agent")

            elif decision.component_type == "workflow":
                components.append(f"Using {decision.component_name} workflow")

        summary = "; ".join(components) if components else "No significant decisions"

        return Explanation(
            level=TransparencyLevel.BRIEF,
            summary=summary
        )

    def _explain_detailed(
        self,
        user_request: str,
        diagnosis: DiagnosisResult,
        decisions: DecisionResult
    ) -> Explanation:
        """Level 2: Detailed - full rationale with alternatives"""
        # Build comprehensive summary
        component_list = [
            f"{d.component_type}:{d.component_name}"
            for d in decisions.decisions
        ]
        summary = f"Routing to {len(component_list)} components: {', '.join(component_list)}"

        # Build rationale from decisions
        rationale_parts = []
        for decision in decisions.decisions:
            rationale_parts.append(
                f"• {decision.component_type.capitalize()} '{decision.component_name}': "
                f"{decision.rationale} (confidence: {decision.confidence:.0%})"
            )

        rationale = "\n  ".join(rationale_parts)

        # Generate alternatives (what we didn't choose)
        alternatives = self._generate_alternatives(diagnosis, decisions)

        # Recommendations
        if decisions.human_approval_required:
            recommendations = f"Approval required: {decisions.approval_reason}"
        else:
            recommendations = "Proceed with execution"

        return Explanation(
            level=TransparencyLevel.DETAILED,
            summary=summary,
            rationale=rationale,
            alternatives=alternatives,
            confidence=decisions.total_confidence,
            recommendations=recommendations
        )

    def _explain_full_audit(
        self,
        user_request: str,
        diagnosis: DiagnosisResult,
        decisions: DecisionResult
    ) -> Explanation:
        """Level 3: Full Audit - complete decision log"""
        # Build detailed summary
        summary = (
            f"Request: '{user_request}' → "
            f"Complexity: {diagnosis.complexity}/10, "
            f"Domain: {diagnosis.primary_domain.value}, "
            f"Operation: {diagnosis.operation_type.value} → "
            f"{len(decisions.decisions)} routing decisions"
        )

        # Build comprehensive rationale
        rationale_parts = [
            f"Situation Diagnosis:",
            f"  • Complexity: {diagnosis.complexity}/10 (confidence: {diagnosis.complexity_confidence:.0%})",
            f"  • Primary Domain: {diagnosis.primary_domain.value} (confidence: {diagnosis.domain_confidence:.0%})",
            f"  • Operation Type: {diagnosis.operation_type.value} (confidence: {diagnosis.operation_confidence:.0%})",
            f"  • Risks: {len(diagnosis.risks)} detected",
            "",
            "Routing Decisions:"
        ]

        for decision in decisions.decisions:
            rationale_parts.extend([
                f"  {decision.component_type.upper()}: {decision.component_name}",
                f"    Priority: {decision.priority.name} ({decision.priority.value})",
                f"    Confidence: {decision.confidence:.0%}",
                f"    Rationale: {decision.rationale}",
                f"    Rule: {decision.rule_applied}",
                ""
            ])

        rationale = "\n".join(rationale_parts)

        # Rules evaluated (simulate - in real implementation, would track all rules checked)
        rules_evaluated = []
        for decision in decisions.decisions:
            rules_evaluated.append({
                "rule_name": decision.rule_applied,
                "matched": True,
                "confidence": decision.confidence
            })

        # Add some unmatched rules (examples)
        if diagnosis.complexity < 5:
            rules_evaluated.append({
                "rule_name": "skills.brainstorming.when[0] (complexity >= 5)",
                "matched": False,
                "confidence": 0.0
            })

        # Generate alternatives
        alternatives = self._generate_alternatives(diagnosis, decisions)

        # Recommendations
        if decisions.human_approval_required:
            recommendations = (
                f"⚠️  APPROVAL REQUIRED: {decisions.approval_reason}\n"
                f"  • Review the decisions above\n"
                f"  • Consider alternatives if needed\n"
                f"  • Approve or reject this routing plan"
            )
        else:
            recommendations = (
                "✓ Automatic execution approved\n"
                f"  • {len(decisions.decisions)} components will be invoked\n"
                f"  • Overall confidence: {decisions.total_confidence:.0%}\n"
                f"  • Execution order: {' → '.join(decisions.execution_order)}"
            )

        return Explanation(
            level=TransparencyLevel.FULL_AUDIT,
            summary=summary,
            rationale=rationale,
            alternatives=alternatives,
            confidence=decisions.total_confidence,
            rules_evaluated=rules_evaluated,
            recommendations=recommendations
        )

    def _generate_alternatives(
        self,
        diagnosis: DiagnosisResult,
        decisions: DecisionResult
    ) -> List[str]:
        """Generate list of alternatives that were considered but not chosen"""
        alternatives = []

        # Check what we didn't trigger
        chosen_components = {
            f"{d.component_type}:{d.component_name}"
            for d in decisions.decisions
        }

        # Skills we didn't choose
        if "skill:brainstorming" not in chosen_components and diagnosis.complexity < 5:
            alternatives.append("brainstorming skill (complexity too low: {diagnosis.complexity}/10)")

        # Agents we didn't choose
        if "agent:security-auditor" not in chosen_components:
            if diagnosis.primary_domain.value != "security" and not diagnosis.risks:
                alternatives.append("security-auditor agent (no security risks detected)")

        if "agent:test-runner" not in chosen_components:
            if diagnosis.primary_domain.value != "testing":
                alternatives.append("test-runner agent (not a testing task)")

        # Workflows we didn't choose
        if "workflow:two-stage-review" not in chosen_components:
            if diagnosis.operation_type.value not in ["creation", "modification"]:
                alternatives.append("two-stage-review workflow (not a creation/modification task)")

        # If no alternatives found, provide generic message
        if not alternatives:
            alternatives.append("All relevant components were selected based on diagnosis")

        return alternatives


def main():
    """CLI interface for testing"""
    import json
    from diagnosis import SituationDiagnosis
    from decision_engine import DecisionEngine

    if len(sys.argv) < 2:
        print("Usage: python3 transparency.py '<request>' [--level <0-3>]")
        print("\nExample:")
        print("  python3 transparency.py 'build auth system' --level 2")
        sys.exit(1)

    user_request = sys.argv[1]
    level = TransparencyLevel.BRIEF

    # Parse --level flag
    if "--level" in sys.argv:
        level_idx = sys.argv.index("--level")
        level_value = int(sys.argv[level_idx + 1])
        level = TransparencyLevel(level_value)

    # Diagnose situation
    diagnoser = SituationDiagnosis()
    diagnosis = diagnoser.diagnose(user_request)

    # Make routing decisions
    engine = DecisionEngine()
    decisions = engine.decide(diagnosis)

    # Generate explanation
    transparency = TransparencyLayer()
    explanation = transparency.explain(user_request, diagnosis, decisions, level=level)

    # Format and print
    formatted = transparency.format_explanation(explanation)
    if formatted:
        print(formatted)
    else:
        print("(No explanation - silent mode)")


if __name__ == "__main__":
    main()
