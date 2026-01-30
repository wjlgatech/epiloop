#!/usr/bin/env python3
"""
Comprehensive test suite for Decision Engine with Routing Rules

Tests routing logic, rule evaluation, execution ordering, and human-in-the-loop detection.
"""

import sys
import json
from pathlib import Path

# Add lib/orchestrator to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "lib" / "orchestrator"))

from decision_engine import DecisionEngine, Priority, RoutingDecision, DecisionResult
from diagnosis import DiagnosisResult, Domain, OperationType, Risk, RiskLevel


def create_diagnosis(
    complexity=5,
    primary_domain=Domain.BACKEND,
    operation_type=OperationType.CREATION,
    risks=None,
    keywords=None,
    capabilities=None
):
    """Helper to create DiagnosisResult for testing"""
    if risks is None:
        risks = []
    if keywords is None:
        keywords = []
    if capabilities is None:
        capabilities = []

    return DiagnosisResult(
        complexity=complexity,
        complexity_confidence=0.9,
        primary_domain=primary_domain,
        secondary_domains=[],
        domain_confidence=0.9,
        operation_type=operation_type,
        operation_confidence=0.9,
        risks=risks,
        capabilities_needed=capabilities,
        keywords_detected=keywords,
        word_count=50,
    )


def test_brainstorming_skill_complexity():
    """Test 1: Brainstorming skill triggered by high complexity"""
    engine = DecisionEngine()
    diagnosis = create_diagnosis(complexity=7, keywords=["build", "feature"])

    result = engine.decide(diagnosis)

    # Check brainstorming is in decisions
    brainstorm_decisions = [d for d in result.decisions if d.component_name == "brainstorming"]
    assert len(brainstorm_decisions) == 1, "Brainstorming should be triggered by complexity >= 5"
    assert brainstorm_decisions[0].priority == Priority.MANDATORY, "Brainstorming should be mandatory"
    print("✅ Test 1: Brainstorming triggered by complexity")


def test_brainstorming_skill_keywords():
    """Test 2: Brainstorming skill triggered by design keywords"""
    engine = DecisionEngine()
    diagnosis = create_diagnosis(complexity=3, keywords=["design", "architect"])

    result = engine.decide(diagnosis)

    brainstorm_decisions = [d for d in result.decisions if d.component_name == "brainstorming"]
    assert len(brainstorm_decisions) == 1, "Brainstorming should be triggered by design keywords"
    print("✅ Test 2: Brainstorming triggered by keywords")


def test_security_agent_domain():
    """Test 3: Security agent triggered by security domain"""
    engine = DecisionEngine()
    diagnosis = create_diagnosis(primary_domain=Domain.SECURITY)

    result = engine.decide(diagnosis)

    security_decisions = [d for d in result.decisions if d.component_name == "security-auditor"]
    assert len(security_decisions) == 1, "Security agent should be triggered by security domain"
    assert security_decisions[0].priority == Priority.DOMAIN_BASED, "Should be domain-based priority"
    print("✅ Test 3: Security agent triggered by domain")


def test_security_agent_high_risk():
    """Test 4: Security agent triggered by HIGH security risk"""
    engine = DecisionEngine()
    risks = [Risk(category="security", level=RiskLevel.HIGH, confidence=0.9, reasoning="Authentication vulnerability")]
    diagnosis = create_diagnosis(primary_domain=Domain.BACKEND, risks=risks)

    result = engine.decide(diagnosis)

    security_decisions = [d for d in result.decisions if d.component_name == "security-auditor"]
    assert len(security_decisions) == 1, "Security agent should be triggered by HIGH security risk"
    assert security_decisions[0].priority == Priority.RISK_BASED, "Should be risk-based priority"
    print("✅ Test 4: Security agent triggered by HIGH risk")


def test_code_reviewer_creation():
    """Test 5: Code reviewer triggered by creation operation"""
    engine = DecisionEngine()
    diagnosis = create_diagnosis(operation_type=OperationType.CREATION)

    result = engine.decide(diagnosis)

    reviewer_decisions = [d for d in result.decisions if d.component_name == "code-reviewer"]
    assert len(reviewer_decisions) == 1, "Code reviewer should be triggered by creation"
    assert reviewer_decisions[0].timing == "after_implementation", "Should run after implementation"
    print("✅ Test 5: Code reviewer triggered by creation")


def test_code_reviewer_modification():
    """Test 6: Code reviewer triggered by modification operation"""
    engine = DecisionEngine()
    diagnosis = create_diagnosis(operation_type=OperationType.MODIFICATION)

    result = engine.decide(diagnosis)

    reviewer_decisions = [d for d in result.decisions if d.component_name == "code-reviewer"]
    assert len(reviewer_decisions) == 1, "Code reviewer should be triggered by modification"
    print("✅ Test 6: Code reviewer triggered by modification")


def test_test_runner_domain():
    """Test 7: Test runner triggered by testing domain"""
    engine = DecisionEngine()
    diagnosis = create_diagnosis(primary_domain=Domain.TESTING)

    result = engine.decide(diagnosis)

    test_runner_decisions = [d for d in result.decisions if d.component_name == "test-runner"]
    assert len(test_runner_decisions) == 1, "Test runner should be triggered by testing domain"
    print("✅ Test 7: Test runner triggered by testing domain")


def test_test_runner_keywords():
    """Test 8: Test runner triggered by test keywords"""
    engine = DecisionEngine()
    diagnosis = create_diagnosis(keywords=["test", "coverage"])

    result = engine.decide(diagnosis)

    test_runner_decisions = [d for d in result.decisions if d.component_name == "test-runner"]
    assert len(test_runner_decisions) == 1, "Test runner should be triggered by test keywords"
    print("✅ Test 8: Test runner triggered by test keywords")


def test_debugger_debugging():
    """Test 9: Debugger triggered by debugging operation"""
    engine = DecisionEngine()
    diagnosis = create_diagnosis(operation_type=OperationType.DEBUGGING)

    result = engine.decide(diagnosis)

    debugger_decisions = [d for d in result.decisions if d.component_name == "debugger"]
    assert len(debugger_decisions) == 1, "Debugger should be triggered by debugging operation"
    print("✅ Test 9: Debugger triggered by debugging")


def test_debugger_testing_domain():
    """Test 10: Debugger triggered by testing domain"""
    engine = DecisionEngine()
    diagnosis = create_diagnosis(primary_domain=Domain.TESTING)

    result = engine.decide(diagnosis)

    debugger_decisions = [d for d in result.decisions if d.component_name == "debugger"]
    assert len(debugger_decisions) == 1, "Debugger should be triggered by testing domain"
    print("✅ Test 10: Debugger triggered by testing domain")


def test_git_workflow_keywords():
    """Test 11: Git workflow triggered by git keywords"""
    engine = DecisionEngine()
    diagnosis = create_diagnosis(keywords=["commit", "merge", "branch"])

    result = engine.decide(diagnosis)

    git_decisions = [d for d in result.decisions if d.component_name == "git-workflow"]
    assert len(git_decisions) == 1, "Git workflow should be triggered by git keywords"
    print("✅ Test 11: Git workflow triggered by keywords")


def test_two_stage_review_creation():
    """Test 12: Two-stage review triggered by creation"""
    engine = DecisionEngine()
    diagnosis = create_diagnosis(operation_type=OperationType.CREATION)

    result = engine.decide(diagnosis)

    review_decisions = [d for d in result.decisions if d.component_name == "two-stage-review"]
    assert len(review_decisions) == 1, "Two-stage review should be triggered by creation"
    assert review_decisions[0].priority == Priority.SEQUENTIAL, "Should be sequential priority"
    print("✅ Test 12: Two-stage review triggered by creation")


def test_two_stage_review_modification():
    """Test 13: Two-stage review triggered by modification"""
    engine = DecisionEngine()
    diagnosis = create_diagnosis(operation_type=OperationType.MODIFICATION)

    result = engine.decide(diagnosis)

    review_decisions = [d for d in result.decisions if d.component_name == "two-stage-review"]
    assert len(review_decisions) == 1, "Two-stage review should be triggered by modification"
    print("✅ Test 13: Two-stage review triggered by modification")


def test_tdd_enforcement_creation():
    """Test 14: TDD enforcement triggered by creation"""
    engine = DecisionEngine()
    diagnosis = create_diagnosis(operation_type=OperationType.CREATION)

    result = engine.decide(diagnosis)

    tdd_decisions = [d for d in result.decisions if d.component_name == "tdd-enforcement"]
    assert len(tdd_decisions) == 1, "TDD enforcement should be triggered by creation"
    assert tdd_decisions[0].timing == "before_implementation", "Should run before implementation"
    print("✅ Test 14: TDD enforcement triggered by creation")


def test_execution_order_timing():
    """Test 15: Execution order respects timing (before/during/after)"""
    engine = DecisionEngine()
    diagnosis = create_diagnosis(operation_type=OperationType.CREATION)

    result = engine.decide(diagnosis)

    # tdd-enforcement should be first (before_implementation)
    # code-reviewer should be last (after_implementation)
    assert "tdd-enforcement" in result.execution_order[0], "TDD should be first (before implementation)"

    # Find code-reviewer position
    reviewer_idx = next(i for i, comp in enumerate(result.execution_order) if "code-reviewer" in comp)
    tdd_idx = next(i for i, comp in enumerate(result.execution_order) if "tdd-enforcement" in comp)
    assert reviewer_idx > tdd_idx, "Code reviewer (after) should come after TDD (before)"

    print("✅ Test 15: Execution order respects timing")


def test_execution_order_priority():
    """Test 16: Execution order respects priority (mandatory > risk > domain)"""
    engine = DecisionEngine()
    risks = [Risk(category="security", level=RiskLevel.HIGH, confidence=0.9, reasoning="Vulnerability")]
    diagnosis = create_diagnosis(
        complexity=7,
        primary_domain=Domain.SECURITY,
        risks=risks,
        keywords=["design", "security"]
    )

    result = engine.decide(diagnosis)

    # brainstorming (mandatory) should come before security-auditor (risk-based)
    decisions_dict = {d.component_name: d for d in result.decisions}

    if "brainstorming" in decisions_dict and "security-auditor" in decisions_dict:
        brainstorm_priority = decisions_dict["brainstorming"].priority
        security_priority = decisions_dict["security-auditor"].priority
        assert brainstorm_priority < security_priority, "Mandatory should have lower priority value than risk-based"

    print("✅ Test 16: Execution order respects priority")


def test_deduplication():
    """Test 17: Duplicate decisions are removed"""
    engine = DecisionEngine()
    # Security domain + HIGH security risk should both trigger security-auditor
    # But should only appear once in decisions
    risks = [Risk(category="security", level=RiskLevel.HIGH, confidence=0.9, reasoning="Vulnerability")]
    diagnosis = create_diagnosis(primary_domain=Domain.SECURITY, risks=risks)

    result = engine.decide(diagnosis)

    security_count = sum(1 for d in result.decisions if d.component_name == "security-auditor")
    assert security_count == 1, "Security agent should only appear once despite multiple triggers"
    print("✅ Test 17: Duplicate decisions removed")


def test_human_approval_destructive():
    """Test 18: Human approval required for destructive operations"""
    engine = DecisionEngine()
    diagnosis = create_diagnosis(keywords=["git push --force", "delete production data"])

    result = engine.decide(diagnosis)

    assert result.human_approval_required, "Human approval should be required for destructive operations"
    assert "Destructive operation detected" in result.approval_reason
    print("✅ Test 18: Human approval for destructive operations")


def test_human_approval_production():
    """Test 19: Human approval required for production deployments"""
    engine = DecisionEngine()
    diagnosis = create_diagnosis(keywords=["deploy to production", "release to prod"])

    result = engine.decide(diagnosis)

    assert result.human_approval_required, "Human approval should be required for production deployments"
    assert "Production deployment detected" in result.approval_reason
    print("✅ Test 19: Human approval for production deployments")


def test_human_approval_architectural():
    """Test 20: Human approval required for high complexity architectural decisions"""
    engine = DecisionEngine()
    diagnosis = create_diagnosis(complexity=8)

    result = engine.decide(diagnosis)

    assert result.human_approval_required, "Human approval should be required for high complexity"
    assert "High complexity architectural decision" in result.approval_reason
    print("✅ Test 20: Human approval for architectural decisions")


def test_no_human_approval_routine():
    """Test 21: No human approval for routine operations"""
    engine = DecisionEngine()
    diagnosis = create_diagnosis(complexity=5, operation_type=OperationType.MODIFICATION)

    result = engine.decide(diagnosis)

    assert not result.human_approval_required, "Routine operations should not require approval"
    print("✅ Test 21: No approval for routine operations")


def test_confidence_scoring():
    """Test 22: Total confidence is calculated correctly"""
    engine = DecisionEngine()
    diagnosis = create_diagnosis(complexity=7, operation_type=OperationType.CREATION)

    result = engine.decide(diagnosis)

    assert 0.0 <= result.total_confidence <= 1.0, "Confidence should be between 0 and 1"
    # Average confidence should be reasonable
    assert result.total_confidence > 0.8, "Average confidence should be high for clear rules"
    print("✅ Test 22: Confidence scoring calculated")


def test_rule_applied_tracking():
    """Test 23: Each decision tracks which rule was applied"""
    engine = DecisionEngine()
    diagnosis = create_diagnosis(complexity=7)

    result = engine.decide(diagnosis)

    for decision in result.decisions:
        assert decision.rule_applied, f"Decision {decision.component_name} should track rule applied"
        assert "." in decision.rule_applied, "Rule should have format 'category.name.when[idx]'"

    print("✅ Test 23: Rule tracking on decisions")


def test_skill_unimplemented_skipped():
    """Test 24: Unimplemented skills are skipped (have TODO note)"""
    engine = DecisionEngine()
    # test-driven-development skill has TODO note, should be skipped
    diagnosis = create_diagnosis(
        operation_type=OperationType.CREATION,
        primary_domain=Domain.BACKEND
    )

    result = engine.decide(diagnosis)

    # test-driven-development should NOT be in decisions (marked as TODO)
    tdd_skill_decisions = [d for d in result.decisions if d.component_name == "test-driven-development"]
    assert len(tdd_skill_decisions) == 0, "Unimplemented skills should be skipped"
    print("✅ Test 24: Unimplemented skills skipped")


def test_systematic_debugging_skipped():
    """Test 25: Systematic debugging skill skipped (TODO)"""
    engine = DecisionEngine()
    diagnosis = create_diagnosis(operation_type=OperationType.DEBUGGING)

    result = engine.decide(diagnosis)

    # systematic-debugging should NOT be in decisions (marked as TODO)
    debug_skill_decisions = [d for d in result.decisions if d.component_name == "systematic-debugging"]
    assert len(debug_skill_decisions) == 0, "Systematic-debugging skill should be skipped (TODO)"
    print("✅ Test 25: Systematic debugging skill skipped")


def test_multiple_domains():
    """Test 26: Multiple secondary domains trigger appropriate agents"""
    engine = DecisionEngine()
    diagnosis = create_diagnosis(
        primary_domain=Domain.BACKEND,
        operation_type=OperationType.CREATION
    )
    diagnosis.secondary_domains = [Domain.SECURITY, Domain.TESTING]

    result = engine.decide(diagnosis)

    # Security should be triggered by secondary domain
    security_decisions = [d for d in result.decisions if d.component_name == "security-auditor"]
    assert len(security_decisions) == 1, "Security agent should be triggered by secondary domain"
    print("✅ Test 26: Secondary domains trigger agents")


def test_complex_scenario_integration():
    """Test 27: Complex scenario with multiple triggers"""
    engine = DecisionEngine()
    risks = [Risk(category="security", level=RiskLevel.HIGH, confidence=0.9, reasoning="Auth vulnerability")]
    diagnosis = create_diagnosis(
        complexity=8,
        primary_domain=Domain.SECURITY,
        operation_type=OperationType.CREATION,
        risks=risks,
        keywords=["design", "architect", "authentication", "test"]
    )

    result = engine.decide(diagnosis)

    # Should trigger multiple components
    component_names = [d.component_name for d in result.decisions]

    assert "brainstorming" in component_names, "Should trigger brainstorming (high complexity + design keywords)"
    assert "security-auditor" in component_names, "Should trigger security-auditor (domain + risk)"
    assert "code-reviewer" in component_names, "Should trigger code-reviewer (creation)"
    assert "two-stage-review" in component_names, "Should trigger two-stage-review (creation)"
    assert "tdd-enforcement" in component_names, "Should trigger tdd-enforcement (creation)"

    # Should require human approval (high complexity)
    assert result.human_approval_required, "High complexity should require approval"

    print("✅ Test 27: Complex scenario integration")


def test_analysis_operation_no_workflows():
    """Test 28: Analysis operations don't trigger creation/modification workflows"""
    engine = DecisionEngine()
    diagnosis = create_diagnosis(operation_type=OperationType.ANALYSIS)

    result = engine.decide(diagnosis)

    # Should NOT trigger two-stage-review or tdd-enforcement
    component_names = [d.component_name for d in result.decisions]
    assert "two-stage-review" not in component_names, "Analysis should not trigger two-stage-review"
    assert "tdd-enforcement" not in component_names, "Analysis should not trigger tdd-enforcement"
    print("✅ Test 28: Analysis doesn't trigger creation workflows")


def test_planning_operation_characteristics():
    """Test 29: Planning operations have appropriate routing"""
    engine = DecisionEngine()
    diagnosis = create_diagnosis(
        complexity=7,
        operation_type=OperationType.PLANNING,
        keywords=["design", "architect", "plan"]
    )

    result = engine.decide(diagnosis)

    component_names = [d.component_name for d in result.decisions]

    # Should trigger brainstorming (design keywords)
    assert "brainstorming" in component_names, "Planning with design keywords should trigger brainstorming"

    # Should NOT trigger implementation workflows
    assert "code-reviewer" not in component_names, "Planning should not trigger code reviewer"
    print("✅ Test 29: Planning operation routing")


def test_empty_diagnosis():
    """Test 30: Empty/minimal diagnosis handled gracefully"""
    engine = DecisionEngine()
    diagnosis = create_diagnosis(complexity=1, keywords=[])

    result = engine.decide(diagnosis)

    # Should still work, just with minimal decisions
    assert isinstance(result, DecisionResult), "Should return valid DecisionResult"
    assert isinstance(result.decisions, list), "Should return list of decisions"
    assert isinstance(result.execution_order, list), "Should return execution order"
    assert isinstance(result.total_confidence, float), "Should calculate confidence"
    print("✅ Test 30: Empty diagnosis handled gracefully")


def run_all_tests():
    """Run all 30 test cases"""
    tests = [
        test_brainstorming_skill_complexity,
        test_brainstorming_skill_keywords,
        test_security_agent_domain,
        test_security_agent_high_risk,
        test_code_reviewer_creation,
        test_code_reviewer_modification,
        test_test_runner_domain,
        test_test_runner_keywords,
        test_debugger_debugging,
        test_debugger_testing_domain,
        test_git_workflow_keywords,
        test_two_stage_review_creation,
        test_two_stage_review_modification,
        test_tdd_enforcement_creation,
        test_execution_order_timing,
        test_execution_order_priority,
        test_deduplication,
        test_human_approval_destructive,
        test_human_approval_production,
        test_human_approval_architectural,
        test_no_human_approval_routine,
        test_confidence_scoring,
        test_rule_applied_tracking,
        test_skill_unimplemented_skipped,
        test_systematic_debugging_skipped,
        test_multiple_domains,
        test_complex_scenario_integration,
        test_analysis_operation_no_workflows,
        test_planning_operation_characteristics,
        test_empty_diagnosis,
    ]

    print("\n" + "="*60)
    print("DECISION ENGINE TEST SUITE")
    print("="*60 + "\n")

    passed = 0
    failed = 0

    for test in tests:
        try:
            test()
            passed += 1
        except AssertionError as e:
            failed += 1
            print(f"❌ {test.__name__}: {e}")
        except Exception as e:
            failed += 1
            print(f"❌ {test.__name__}: Unexpected error: {e}")

    print("\n" + "="*60)
    print(f"RESULTS: {passed}/{len(tests)} tests passed")
    if failed > 0:
        print(f"❌ {failed} tests failed")
        sys.exit(1)
    else:
        print("✅ All tests passed!")
        print("="*60 + "\n")
        sys.exit(0)


if __name__ == "__main__":
    run_all_tests()
