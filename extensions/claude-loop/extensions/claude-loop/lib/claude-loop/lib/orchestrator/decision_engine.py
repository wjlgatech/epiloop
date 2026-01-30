#!/usr/bin/env python3
"""
Decision Engine with Routing Rules

Routes requests to the right agents, skills, and workflows based on situation
diagnosis and configurable routing rules.
"""

import json
import yaml
import re
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict
from pathlib import Path
from enum import Enum

# Import diagnosis types
import sys
sys.path.insert(0, str(Path(__file__).parent))
from diagnosis import DiagnosisResult, Domain, OperationType, RiskLevel


class Priority(int, Enum):
    """Priority levels for routing decisions"""
    MANDATORY = 1
    RISK_BASED = 2
    DOMAIN_BASED = 3
    SEQUENTIAL = 4
    SUPPORTING = 5


@dataclass
class RoutingDecision:
    """A single routing decision"""
    component_type: str  # skill, agent, workflow
    component_name: str
    rationale: str
    confidence: float  # 0.0-1.0
    priority: Priority
    timing: Optional[str] = None  # before_implementation, after_implementation, etc.
    alternatives_considered: List[str] = None
    rule_applied: str = ""

    def __post_init__(self):
        if self.alternatives_considered is None:
            self.alternatives_considered = []

    def to_dict(self) -> Dict:
        """Convert to dictionary"""
        return asdict(self)


@dataclass
class DecisionResult:
    """Result of decision engine"""
    decisions: List[RoutingDecision]
    total_confidence: float  # Average confidence across all decisions
    execution_order: List[str]  # Ordered list of components to execute
    human_approval_required: bool
    approval_reason: str = ""

    def to_dict(self) -> Dict:
        """Convert to dictionary"""
        return {
            "decisions": [d.to_dict() for d in self.decisions],
            "total_confidence": self.total_confidence,
            "execution_order": self.execution_order,
            "human_approval_required": self.human_approval_required,
            "approval_reason": self.approval_reason,
        }

    def to_json(self) -> str:
        """Convert to JSON string"""
        return json.dumps(self.to_dict(), indent=2)


class DecisionEngine:
    """
    Decision engine that routes requests to agents, skills, and workflows
    based on situation diagnosis and routing rules.
    """

    def __init__(self, rules_file: str = None):
        """
        Initialize decision engine.

        Args:
            rules_file: Path to orchestrator-rules.yaml (default: config/orchestrator-rules.yaml)
        """
        if rules_file is None:
            # Default to config/orchestrator-rules.yaml
            script_dir = Path(__file__).parent.parent.parent
            rules_file = script_dir / "config" / "orchestrator-rules.yaml"

        self.rules_file = Path(rules_file)
        self.rules = self._load_rules()

    def _load_rules(self) -> Dict:
        """Load routing rules from YAML file"""
        if not self.rules_file.exists():
            raise FileNotFoundError(f"Rules file not found: {self.rules_file}")

        with open(self.rules_file) as f:
            return yaml.safe_load(f)

    def decide(self, diagnosis: DiagnosisResult) -> DecisionResult:
        """
        Make routing decisions based on diagnosis.

        Args:
            diagnosis: DiagnosisResult from situation diagnosis engine

        Returns:
            DecisionResult with routing decisions and execution order
        """
        decisions = []

        # Apply rules in priority order
        # 1. Mandatory skills
        skill_decisions = self._apply_skill_rules(diagnosis)
        decisions.extend(skill_decisions)

        # 2. Risk-based agents
        risk_agent_decisions = self._apply_risk_based_agent_rules(diagnosis)
        decisions.extend(risk_agent_decisions)

        # 3. Domain-based agents
        domain_agent_decisions = self._apply_domain_based_agent_rules(diagnosis)
        decisions.extend(domain_agent_decisions)

        # 4. Sequential workflows
        workflow_decisions = self._apply_workflow_rules(diagnosis)
        decisions.extend(workflow_decisions)

        # Deduplicate decisions (same component)
        decisions = self._deduplicate_decisions(decisions)

        # Sort by priority and timing
        execution_order = self._determine_execution_order(decisions)

        # Check if human approval is needed
        human_approval_required, approval_reason = self._check_human_approval_needed(diagnosis)

        # Calculate average confidence
        total_confidence = sum(d.confidence for d in decisions) / len(decisions) if decisions else 1.0

        return DecisionResult(
            decisions=decisions,
            total_confidence=total_confidence,
            execution_order=execution_order,
            human_approval_required=human_approval_required,
            approval_reason=approval_reason,
        )

    def _apply_skill_rules(self, diagnosis: DiagnosisResult) -> List[RoutingDecision]:
        """Apply skill routing rules"""
        decisions = []
        skill_rules = self.rules.get("skills", {})

        for skill_name, rule in skill_rules.items():
            # Check if skill should be invoked
            should_invoke, confidence, matched_condition = self._evaluate_conditions(
                rule.get("when", []), diagnosis
            )

            if should_invoke:
                # Check if skill is implemented (not in note as TODO)
                note = rule.get("note", "")
                if "TODO" in note and "not yet implemented" in note:
                    # Skip unimplemented skills
                    continue

                decisions.append(RoutingDecision(
                    component_type="skill",
                    component_name=skill_name,
                    rationale=rule.get("rationale", ""),
                    confidence=confidence,
                    priority=Priority.MANDATORY if rule.get("mandatory") else Priority.SUPPORTING,
                    timing=rule.get("timing"),
                    rule_applied=f"skills.{skill_name}.when[{matched_condition}]",
                ))

        return decisions

    def _apply_risk_based_agent_rules(self, diagnosis: DiagnosisResult) -> List[RoutingDecision]:
        """Apply agent rules based on risk assessment"""
        decisions = []
        agent_rules = self.rules.get("agents", {})

        for agent_name, rule in agent_rules.items():
            # Check conditions
            should_invoke, confidence, matched_condition = self._evaluate_conditions(
                rule.get("when", []), diagnosis
            )

            if should_invoke:
                # Check if the MATCHED condition is risk-based (HIGH risk)
                when_conditions = rule.get("when", [])
                if matched_condition >= 0 and matched_condition < len(when_conditions):
                    matched_cond_str = when_conditions[matched_condition].get("condition", "")
                    is_risk_based = "risks contains" in matched_cond_str and "with level HIGH" in matched_cond_str
                else:
                    is_risk_based = False

                if is_risk_based:
                    decisions.append(RoutingDecision(
                        component_type="agent",
                        component_name=agent_name,
                        rationale=rule.get("rationale", ""),
                        confidence=confidence,
                        priority=Priority.RISK_BASED,
                        timing=rule.get("timing"),
                        rule_applied=f"agents.{agent_name}.when[{matched_condition}]",
                    ))

        return decisions

    def _apply_domain_based_agent_rules(self, diagnosis: DiagnosisResult) -> List[RoutingDecision]:
        """Apply agent rules based on domain or other non-risk conditions"""
        decisions = []
        agent_rules = self.rules.get("agents", {})

        for agent_name, rule in agent_rules.items():
            # Check conditions
            should_invoke, confidence, matched_condition = self._evaluate_conditions(
                rule.get("when", []), diagnosis
            )

            if should_invoke:
                # Check if the MATCHED condition is risk-based (HIGH risk)
                when_conditions = rule.get("when", [])
                if matched_condition >= 0 and matched_condition < len(when_conditions):
                    matched_cond_str = when_conditions[matched_condition].get("condition", "")
                    is_risk_based = "risks contains" in matched_cond_str and "with level HIGH" in matched_cond_str
                else:
                    is_risk_based = False

                # Only add if the matched condition is NOT risk-based
                if not is_risk_based:
                    decisions.append(RoutingDecision(
                        component_type="agent",
                        component_name=agent_name,
                        rationale=rule.get("rationale", ""),
                        confidence=confidence,
                        priority=Priority.DOMAIN_BASED,
                        timing=rule.get("timing"),
                        rule_applied=f"agents.{agent_name}.when[{matched_condition}]",
                    ))

        return decisions

    def _apply_workflow_rules(self, diagnosis: DiagnosisResult) -> List[RoutingDecision]:
        """Apply workflow routing rules"""
        decisions = []
        workflow_rules = self.rules.get("workflows", {})

        for workflow_name, rule in workflow_rules.items():
            # Check conditions
            should_invoke, confidence, matched_condition = self._evaluate_conditions(
                rule.get("when", []), diagnosis
            )

            if should_invoke:
                decisions.append(RoutingDecision(
                    component_type="workflow",
                    component_name=workflow_name,
                    rationale=rule.get("rationale", ""),
                    confidence=confidence,
                    priority=Priority.SEQUENTIAL,
                    timing=rule.get("timing"),
                    rule_applied=f"workflows.{workflow_name}.when[{matched_condition}]",
                ))

        return decisions

    def _evaluate_conditions(
        self, conditions: List[Dict], diagnosis: DiagnosisResult
    ) -> Tuple[bool, float, int]:
        """
        Evaluate conditions against diagnosis.

        Returns:
            (should_invoke, confidence, matched_condition_index)
        """
        if not conditions:
            return False, 0.0, -1

        for idx, condition_rule in enumerate(conditions):
            condition = condition_rule.get("condition", "")
            base_confidence = condition_rule.get("confidence", 1.0)

            # Evaluate condition
            if self._evaluate_single_condition(condition, diagnosis):
                return True, base_confidence, idx

        return False, 0.0, -1

    def _evaluate_single_condition(self, condition: str, diagnosis: DiagnosisResult) -> bool:
        """Evaluate a single condition string against diagnosis"""

        # Complexity conditions
        if "complexity >=" in condition:
            threshold = int(re.search(r"complexity >= (\d+)", condition).group(1))
            return diagnosis.complexity >= threshold

        if "complexity <" in condition:
            threshold = int(re.search(r"complexity < (\d+)", condition).group(1))
            return diagnosis.complexity < threshold

        # Operation type conditions
        if "operation_type ==" in condition:
            op_type = re.search(r"operation_type == ['\"](\w+)['\"]", condition).group(1)
            return diagnosis.operation_type.value == op_type

        if "operation_type in" in condition:
            op_types = re.findall(r"['\"](\w+)['\"]", condition)
            return diagnosis.operation_type.value in op_types

        # Domain conditions
        if "primary_domain ==" in condition:
            domain = re.search(r"primary_domain == ['\"](\w+)['\"]", condition).group(1)
            return diagnosis.primary_domain.value == domain

        if "domains contains" in condition or "secondary_domains contains" in condition:
            domains = re.findall(r"['\"](\w+)['\"]", condition)
            all_domains = [diagnosis.primary_domain.value] + [d.value for d in diagnosis.secondary_domains]
            return any(d in all_domains for d in domains)

        # Risk conditions
        if "risks contains" in condition:
            risk_category = re.search(r"risks contains ['\"](\w+)['\"]", condition).group(1)

            # Check if risk exists
            matching_risks = [r for r in diagnosis.risks if r.category == risk_category]
            if not matching_risks:
                return False

            # Check risk level if specified
            if "with level HIGH" in condition:
                return any(r.level == RiskLevel.HIGH for r in matching_risks)

            return True

        # Keywords conditions
        if "keywords contains" in condition:
            keywords = re.findall(r"['\"]([^'\"]+)['\"]", condition)
            return any(kw.lower() in [k.lower() for k in diagnosis.keywords_detected] for kw in keywords)

        # Skill mandatory condition (special case)
        if "skill is mandatory" in condition:
            skill_name = re.search(r"['\"]?([a-z-]+)['\"]? skill is mandatory", condition).group(1)
            # Check if skill appears in capabilities_needed
            return skill_name in diagnosis.capabilities_needed

        return False

    def _deduplicate_decisions(self, decisions: List[RoutingDecision]) -> List[RoutingDecision]:
        """Remove duplicate decisions, keeping highest priority version"""
        # Group by component
        component_decisions = {}

        for decision in decisions:
            key = (decision.component_type, decision.component_name)
            if key not in component_decisions:
                component_decisions[key] = decision
            else:
                # Keep the one with higher priority (lower enum value)
                if decision.priority < component_decisions[key].priority:
                    component_decisions[key] = decision

        return list(component_decisions.values())

    def _determine_execution_order(self, decisions: List[RoutingDecision]) -> List[str]:
        """Determine execution order based on priority and timing"""
        # Group by timing
        before_impl = []
        during_impl = []
        after_impl = []

        for decision in decisions:
            component_id = f"{decision.component_type}:{decision.component_name}"
            timing = decision.timing or "during"

            if timing == "before_implementation":
                before_impl.append((decision.priority, component_id))
            elif timing == "after_implementation":
                after_impl.append((decision.priority, component_id))
            else:
                during_impl.append((decision.priority, component_id))

        # Sort each group by priority
        before_impl.sort(key=lambda x: x[0])
        during_impl.sort(key=lambda x: x[0])
        after_impl.sort(key=lambda x: x[0])

        # Combine: before → during → after
        execution_order = (
            [comp for _, comp in before_impl] +
            [comp for _, comp in during_impl] +
            [comp for _, comp in after_impl]
        )

        return execution_order

    def _check_human_approval_needed(self, diagnosis: DiagnosisResult) -> Tuple[bool, str]:
        """Check if human approval is required based on diagnosis"""
        human_in_loop_rules = self.rules.get("human_in_loop", {})
        essential_decisions = human_in_loop_rules.get("essential_decisions", [])

        # Check for destructive operations
        for decision_rule in essential_decisions:
            if decision_rule.get("category") == "destructive_operations":
                patterns = decision_rule.get("patterns", [])
                for pattern in patterns:
                    if any(pattern.lower() in kw.lower() for kw in diagnosis.keywords_detected):
                        return True, f"Destructive operation detected: {pattern}"

            # Check for production deployments
            if decision_rule.get("category") == "production_deployments":
                patterns = decision_rule.get("patterns", [])
                for pattern in patterns:
                    if any(pattern.lower() in kw.lower() for kw in diagnosis.keywords_detected):
                        return True, f"Production deployment detected: {pattern}"

            # Check for architectural decisions
            if decision_rule.get("category") == "architectural_decisions":
                # Architectural decisions typically have high complexity
                if diagnosis.complexity >= 7:
                    return True, "High complexity architectural decision"

        return False, ""


def main():
    """CLI interface for testing"""
    import sys

    if len(sys.argv) < 2:
        print("Usage: python3 decision_engine.py '<diagnosis_json>' [--rules <rules_file>]")
        print("\nExample:")
        print('  python3 diagnosis.py "build auth" --json | python3 decision_engine.py -')
        sys.exit(1)

    diagnosis_json = sys.argv[1]

    # Read diagnosis from stdin if '-'
    if diagnosis_json == "-":
        import sys
        diagnosis_json = sys.stdin.read()
    # Otherwise read from file
    elif Path(diagnosis_json).exists():
        with open(diagnosis_json) as f:
            diagnosis_json = f.read()

    # Parse diagnosis
    diagnosis_dict = json.loads(diagnosis_json)

    # Reconstruct DiagnosisResult (simplified for CLI)
    from diagnosis import DiagnosisResult, Domain, OperationType, Risk, RiskLevel

    diagnosis = DiagnosisResult(
        complexity=diagnosis_dict["complexity"],
        complexity_confidence=diagnosis_dict["complexity_confidence"],
        primary_domain=Domain(diagnosis_dict["primary_domain"]),
        secondary_domains=[Domain(d) for d in diagnosis_dict["secondary_domains"]],
        domain_confidence=diagnosis_dict["domain_confidence"],
        operation_type=OperationType(diagnosis_dict["operation_type"]),
        operation_confidence=diagnosis_dict["operation_confidence"],
        risks=[
            Risk(
                category=r["category"],
                level=RiskLevel(r["level"]),
                confidence=r["confidence"],
                reasoning=r["reasoning"]
            )
            for r in diagnosis_dict["risks"]
        ],
        capabilities_needed=diagnosis_dict["capabilities_needed"],
        keywords_detected=diagnosis_dict["keywords_detected"],
        word_count=diagnosis_dict["word_count"],
    )

    # Get rules file
    rules_file = None
    if "--rules" in sys.argv:
        rules_idx = sys.argv.index("--rules")
        rules_file = sys.argv[rules_idx + 1]

    # Run decision engine
    engine = DecisionEngine(rules_file=rules_file)
    result = engine.decide(diagnosis)

    # Print results
    print(f"\n{'='*60}")
    print("DECISION ENGINE RESULTS")
    print(f"{'='*60}\n")
    print(f"Total Confidence: {result.total_confidence:.2f}")
    print(f"Human Approval Required: {result.human_approval_required}")
    if result.approval_reason:
        print(f"Approval Reason: {result.approval_reason}")

    print(f"\nDecisions ({len(result.decisions)}):")
    for decision in result.decisions:
        print(f"\n  {decision.component_type.upper()}: {decision.component_name}")
        print(f"    Priority: {decision.priority.name}")
        print(f"    Confidence: {decision.confidence:.2f}")
        print(f"    Rationale: {decision.rationale}")
        if decision.timing:
            print(f"    Timing: {decision.timing}")
        print(f"    Rule: {decision.rule_applied}")

    print(f"\nExecution Order:")
    for idx, component in enumerate(result.execution_order, 1):
        print(f"  {idx}. {component}")

    print(f"\n{'='*60}\n")


if __name__ == "__main__":
    main()
