#!/usr/bin/env python3
"""
Test suite for Transparency Layer with 4 explanation levels

Tests explanation generation at all transparency levels and formatting.
"""

import sys
from pathlib import Path

# Add lib/orchestrator to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "lib" / "orchestrator"))

from transparency import TransparencyLayer, TransparencyLevel, Explanation
from diagnosis import DiagnosisResult, Domain, OperationType, Risk, RiskLevel
from decision_engine import DecisionEngine, DecisionResult, RoutingDecision, Priority


def create_test_diagnosis(complexity=5, primary_domain=Domain.BACKEND):
    """Helper to create test diagnosis"""
    return DiagnosisResult(
        complexity=complexity,
        complexity_confidence=0.9,
        primary_domain=primary_domain,
        secondary_domains=[],
        domain_confidence=0.9,
        operation_type=OperationType.CREATION,
        operation_confidence=0.9,
        risks=[],
        capabilities_needed=[],
        keywords_detected=["test"],
        word_count=50
    )


def create_test_decisions():
    """Helper to create test decisions"""
    decisions = [
        RoutingDecision(
            component_type="skill",
            component_name="brainstorming",
            rationale="High complexity detected",
            confidence=0.95,
            priority=Priority.MANDATORY,
            rule_applied="skills.brainstorming.when[0]"
        )
    ]

    return DecisionResult(
        decisions=decisions,
        total_confidence=0.95,
        execution_order=["skill:brainstorming"],
        human_approval_required=False,
        approval_reason=""
    )


def test_explain_silent():
    """Test 1: Silent level (Level 0) - no explanation"""
    transparency = TransparencyLayer()
    decisions = create_test_decisions()

    explanation = transparency.explain(
        "test request",
        create_test_diagnosis(),
        decisions,
        level=TransparencyLevel.SILENT
    )

    assert explanation.level == TransparencyLevel.SILENT
    assert explanation.summary is not None
    assert explanation.rationale is None
    assert explanation.alternatives is None

    # Formatted output should be empty
    formatted = transparency.format_explanation(explanation)
    assert formatted == ""

    print("✅ Test 1: Silent level generates no output")


def test_explain_brief():
    """Test 2: Brief level (Level 1) - one-line notification"""
    transparency = TransparencyLayer()
    diagnosis = create_test_diagnosis(complexity=7)
    decisions = create_test_decisions()

    explanation = transparency.explain(
        "build authentication system",
        diagnosis,
        decisions,
        level=TransparencyLevel.BRIEF
    )

    assert explanation.level == TransparencyLevel.BRIEF
    assert explanation.summary is not None
    assert "brainstorming" in explanation.summary
    assert "complexity" in explanation.summary or "7" in explanation.summary

    # Formatted output should be one line with emoji
    formatted = transparency.format_explanation(explanation)
    assert formatted.startswith("ℹ️")
    assert len(formatted.split("\n")) == 1

    print("✅ Test 2: Brief level generates one-line notification")


def test_explain_detailed():
    """Test 3: Detailed level (Level 2) - full rationale"""
    transparency = TransparencyLayer()
    diagnosis = create_test_diagnosis(complexity=7)
    decisions = create_test_decisions()

    explanation = transparency.explain(
        "build authentication system",
        diagnosis,
        decisions,
        level=TransparencyLevel.DETAILED
    )

    assert explanation.level == TransparencyLevel.DETAILED
    assert explanation.summary is not None
    assert explanation.rationale is not None
    assert explanation.alternatives is not None
    assert explanation.confidence is not None
    assert explanation.recommendations is not None

    # Formatted output should have multiple sections
    formatted = transparency.format_explanation(explanation)
    assert "Summary:" in formatted
    assert "Rationale:" in formatted
    assert "Alternatives Considered:" in formatted
    assert "Confidence:" in formatted
    assert "Recommendations:" in formatted

    print("✅ Test 3: Detailed level generates full rationale")


def test_explain_full_audit():
    """Test 4: Full Audit level (Level 3) - complete decision log"""
    transparency = TransparencyLayer()
    diagnosis = create_test_diagnosis(complexity=7)
    decisions = create_test_decisions()

    explanation = transparency.explain(
        "build authentication system",
        diagnosis,
        decisions,
        level=TransparencyLevel.FULL_AUDIT
    )

    assert explanation.level == TransparencyLevel.FULL_AUDIT
    assert explanation.summary is not None
    assert explanation.rationale is not None
    assert explanation.alternatives is not None
    assert explanation.confidence is not None
    assert explanation.rules_evaluated is not None
    assert len(explanation.rules_evaluated) > 0

    # Formatted output should have all sections including rules
    formatted = transparency.format_explanation(explanation)
    assert "FULL ORCHESTRATOR AUDIT" in formatted
    assert "Decision Rationale:" in formatted
    assert "Rules Evaluated:" in formatted
    assert "Alternatives Considered:" in formatted

    print("✅ Test 4: Full Audit level generates complete log")


def test_should_notify_essential():
    """Test 5: should_notify detects essential decisions (Detailed)"""
    transparency = TransparencyLayer()

    # Create decision requiring approval
    decisions = DecisionResult(
        decisions=[],
        total_confidence=0.95,
        execution_order=[],
        human_approval_required=True,
        approval_reason="Production deployment"
    )

    level = transparency.should_notify(decisions)
    assert level == TransparencyLevel.DETAILED

    print("✅ Test 5: should_notify detects essential decisions")


def test_should_notify_significant():
    """Test 6: should_notify detects significant decisions (Brief)"""
    transparency = TransparencyLayer()

    # Create decision with mandatory skill
    decisions = DecisionResult(
        decisions=[
            RoutingDecision(
                component_type="skill",
                component_name="brainstorming",
                rationale="Test",
                confidence=0.95,
                priority=Priority.MANDATORY,
                rule_applied="test"
            )
        ],
        total_confidence=0.95,
        execution_order=["skill:brainstorming"],
        human_approval_required=False,
        approval_reason=""
    )

    level = transparency.should_notify(decisions)
    assert level == TransparencyLevel.BRIEF

    print("✅ Test 6: should_notify detects significant decisions")


def test_should_notify_routine():
    """Test 7: should_notify detects routine decisions (Silent)"""
    transparency = TransparencyLayer()

    # Create routine decision (code-reviewer only)
    decisions = DecisionResult(
        decisions=[
            RoutingDecision(
                component_type="agent",
                component_name="code-reviewer",
                rationale="Test",
                confidence=0.90,
                priority=Priority.DOMAIN_BASED,
                rule_applied="test"
            )
        ],
        total_confidence=0.90,
        execution_order=["agent:code-reviewer"],
        human_approval_required=False,
        approval_reason=""
    )

    level = transparency.should_notify(decisions)
    assert level == TransparencyLevel.SILENT

    print("✅ Test 7: should_notify detects routine decisions")


def test_should_notify_expert_user():
    """Test 8: should_notify adjusts for expert users (Silent)"""
    transparency = TransparencyLayer()

    # Create significant decision
    decisions = DecisionResult(
        decisions=[
            RoutingDecision(
                component_type="skill",
                component_name="brainstorming",
                rationale="Test",
                confidence=0.95,
                priority=Priority.MANDATORY,
                rule_applied="test"
            )
        ],
        total_confidence=0.95,
        execution_order=["skill:brainstorming"],
        human_approval_required=False,
        approval_reason=""
    )

    # For intermediate users, should be Brief
    level_intermediate = transparency.should_notify(decisions, user_expertise_level="intermediate")
    assert level_intermediate == TransparencyLevel.BRIEF

    # For expert users, should be Silent
    level_expert = transparency.should_notify(decisions, user_expertise_level="expert")
    assert level_expert == TransparencyLevel.SILENT

    print("✅ Test 8: should_notify adjusts for expert users")


def test_format_brief():
    """Test 9: format_explanation for Brief level"""
    transparency = TransparencyLayer()

    explanation = Explanation(
        level=TransparencyLevel.BRIEF,
        summary="Using brainstorming skill (complexity: 7/10)"
    )

    formatted = transparency.format_explanation(explanation)
    assert formatted.startswith("ℹ️")
    assert "brainstorming" in formatted
    assert len(formatted.split("\n")) == 1

    print("✅ Test 9: format_explanation for Brief level")


def test_format_detailed():
    """Test 10: format_explanation for Detailed level"""
    transparency = TransparencyLayer()

    explanation = Explanation(
        level=TransparencyLevel.DETAILED,
        summary="Test summary",
        rationale="Test rationale",
        alternatives=["Alternative 1", "Alternative 2"],
        confidence=0.95,
        recommendations="Test recommendations"
    )

    formatted = transparency.format_explanation(explanation)
    assert "ORCHESTRATOR DECISION" in formatted
    assert "Summary: Test summary" in formatted
    assert "Rationale:" in formatted
    assert "Alternatives Considered:" in formatted
    assert "Alternative 1" in formatted
    assert "Confidence: 95%" in formatted
    assert "Recommendations:" in formatted

    print("✅ Test 10: format_explanation for Detailed level")


def test_format_full_audit():
    """Test 11: format_explanation for Full Audit level"""
    transparency = TransparencyLayer()

    explanation = Explanation(
        level=TransparencyLevel.FULL_AUDIT,
        summary="Test summary",
        rationale="Test rationale",
        alternatives=["Alternative 1"],
        confidence=0.95,
        rules_evaluated=[
            {"rule_name": "test.rule", "matched": True, "confidence": 0.9}
        ],
        recommendations="Test recommendations"
    )

    formatted = transparency.format_explanation(explanation)
    assert "FULL ORCHESTRATOR AUDIT" in formatted
    assert "Decision Rationale:" in formatted
    assert "Rules Evaluated:" in formatted
    assert "test.rule" in formatted
    assert "Matched: True" in formatted

    print("✅ Test 11: format_explanation for Full Audit level")


def test_generate_alternatives():
    """Test 12: _generate_alternatives creates relevant alternatives"""
    transparency = TransparencyLayer()

    # Diagnosis with low complexity (won't trigger brainstorming)
    diagnosis = create_test_diagnosis(complexity=3)

    # Decisions without brainstorming
    decisions = DecisionResult(
        decisions=[],
        total_confidence=0.90,
        execution_order=[],
        human_approval_required=False,
        approval_reason=""
    )

    alternatives = transparency._generate_alternatives(diagnosis, decisions)
    assert len(alternatives) > 0

    print("✅ Test 12: _generate_alternatives creates relevant alternatives")


def test_multiple_components_brief():
    """Test 13: Brief explanation with multiple components"""
    transparency = TransparencyLayer()

    diagnosis = create_test_diagnosis(complexity=7, primary_domain=Domain.SECURITY)

    # Multiple decisions
    decisions = DecisionResult(
        decisions=[
            RoutingDecision(
                component_type="skill",
                component_name="brainstorming",
                rationale="High complexity",
                confidence=0.95,
                priority=Priority.MANDATORY,
                rule_applied="test"
            ),
            RoutingDecision(
                component_type="agent",
                component_name="security-auditor",
                rationale="Security domain",
                confidence=0.95,
                priority=Priority.RISK_BASED,
                rule_applied="test"
            )
        ],
        total_confidence=0.95,
        execution_order=["skill:brainstorming", "agent:security-auditor"],
        human_approval_required=False,
        approval_reason=""
    )

    explanation = transparency.explain(
        "build auth system",
        diagnosis,
        decisions,
        level=TransparencyLevel.BRIEF
    )

    assert "brainstorming" in explanation.summary
    assert "security-auditor" in explanation.summary

    print("✅ Test 13: Brief explanation with multiple components")


def test_approval_required_recommendations():
    """Test 14: Recommendations mention approval requirement"""
    transparency = TransparencyLayer()

    diagnosis = create_test_diagnosis(complexity=8)

    decisions = DecisionResult(
        decisions=[],
        total_confidence=0.95,
        execution_order=[],
        human_approval_required=True,
        approval_reason="High complexity"
    )

    explanation = transparency.explain(
        "test",
        diagnosis,
        decisions,
        level=TransparencyLevel.DETAILED
    )

    assert explanation.recommendations is not None
    assert "Approval required" in explanation.recommendations

    print("✅ Test 14: Recommendations mention approval requirement")


def test_transparency_level_enum():
    """Test 15: TransparencyLevel enum values"""
    assert TransparencyLevel.SILENT == 0
    assert TransparencyLevel.BRIEF == 1
    assert TransparencyLevel.DETAILED == 2
    assert TransparencyLevel.FULL_AUDIT == 3

    # Can be constructed from int
    assert TransparencyLevel(0) == TransparencyLevel.SILENT
    assert TransparencyLevel(3) == TransparencyLevel.FULL_AUDIT

    print("✅ Test 15: TransparencyLevel enum values correct")


def run_all_tests():
    """Run all 15 test cases"""
    tests = [
        test_explain_silent,
        test_explain_brief,
        test_explain_detailed,
        test_explain_full_audit,
        test_should_notify_essential,
        test_should_notify_significant,
        test_should_notify_routine,
        test_should_notify_expert_user,
        test_format_brief,
        test_format_detailed,
        test_format_full_audit,
        test_generate_alternatives,
        test_multiple_components_brief,
        test_approval_required_recommendations,
        test_transparency_level_enum,
    ]

    print("\n" + "="*60)
    print("TRANSPARENCY LAYER TEST SUITE")
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
