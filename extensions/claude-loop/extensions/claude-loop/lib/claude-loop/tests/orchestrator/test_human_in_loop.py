#!/usr/bin/env python3
"""
Test suite for Human-in-the-Loop Approval Gates

Tests classification of essential vs routine decisions, approval processing,
override logging, and learning from user feedback.
"""

import sys
import tempfile
from pathlib import Path

# Add lib/orchestrator to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "lib" / "orchestrator"))

from human_in_loop import ApprovalGate, DecisionCategory, ApprovalAction, ApprovalRequest
from transparency import TransparencyLevel
from diagnosis import DiagnosisResult, Domain, OperationType, Risk, RiskLevel
from decision_engine import DecisionResult, RoutingDecision, Priority


def create_test_diagnosis(complexity=5, keywords=None, risks=None):
    """Helper to create test diagnosis"""
    if keywords is None:
        keywords = []
    if risks is None:
        risks = []

    return DiagnosisResult(
        complexity=complexity,
        complexity_confidence=0.9,
        primary_domain=Domain.BACKEND,
        secondary_domains=[],
        domain_confidence=0.9,
        operation_type=OperationType.CREATION,
        operation_confidence=0.9,
        risks=risks,
        capabilities_needed=[],
        keywords_detected=keywords,
        word_count=len(" ".join(keywords))
    )


def create_test_decisions(approval_required=False, approval_reason=""):
    """Helper to create test decisions"""
    return DecisionResult(
        decisions=[],
        total_confidence=0.95,
        execution_order=["test:component"],
        human_approval_required=approval_required,
        approval_reason=approval_reason
    )


def test_classify_destructive_operation():
    """Test 1: Classify destructive operation as essential"""
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".jsonl") as f:
        log_file = f.name

    try:
        gate = ApprovalGate(overrides_log=log_file)

        # Destructive operation (flagged by decision engine)
        diagnosis = create_test_diagnosis(keywords=["git push --force"])
        decisions = create_test_decisions(
            approval_required=True,
            approval_reason="Destructive operation detected: git push --force"
        )

        category, reason = gate.classify_decision(diagnosis, decisions)

        assert category == DecisionCategory.ESSENTIAL
        assert "Destructive operation" in reason or "git push --force" in reason

        print("✅ Test 1: Destructive operation classified as essential")

    finally:
        Path(log_file).unlink(missing_ok=True)


def test_classify_production_deployment():
    """Test 2: Classify production deployment as essential"""
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".jsonl") as f:
        log_file = f.name

    try:
        gate = ApprovalGate(overrides_log=log_file)

        diagnosis = create_test_diagnosis(keywords=["deploy to production"])
        decisions = create_test_decisions(
            approval_required=True,
            approval_reason="Production deployment detected"
        )

        category, reason = gate.classify_decision(diagnosis, decisions)

        assert category == DecisionCategory.ESSENTIAL
        assert "Production deployment" in reason or "deploy" in reason

        print("✅ Test 2: Production deployment classified as essential")

    finally:
        Path(log_file).unlink(missing_ok=True)


def test_classify_high_complexity():
    """Test 3: Classify high complexity (>=7) as essential"""
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".jsonl") as f:
        log_file = f.name

    try:
        gate = ApprovalGate(overrides_log=log_file)

        diagnosis = create_test_diagnosis(complexity=8)
        decisions = create_test_decisions()

        category, reason = gate.classify_decision(diagnosis, decisions)

        assert category == DecisionCategory.ESSENTIAL
        assert "complexity" in reason.lower() or "architectural" in reason.lower()

        print("✅ Test 3: High complexity classified as essential")

    finally:
        Path(log_file).unlink(missing_ok=True)


def test_classify_multiple_high_priority_agents():
    """Test 4: Classify multiple high-priority agents as essential"""
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".jsonl") as f:
        log_file = f.name

    try:
        gate = ApprovalGate(overrides_log=log_file)

        diagnosis = create_test_diagnosis(complexity=6)

        # Create decisions with 3 high-priority agents
        decisions = DecisionResult(
            decisions=[
                RoutingDecision(
                    component_type="agent",
                    component_name="security-auditor",
                    rationale="Test",
                    confidence=0.95,
                    priority=Priority.RISK_BASED,  # Priority 2
                    rule_applied="test"
                ),
                RoutingDecision(
                    component_type="agent",
                    component_name="debugger",
                    rationale="Test",
                    confidence=0.90,
                    priority=Priority.RISK_BASED,  # Priority 2
                    rule_applied="test"
                ),
                RoutingDecision(
                    component_type="agent",
                    component_name="test-runner",
                    rationale="Test",
                    confidence=0.85,
                    priority=Priority.RISK_BASED,  # Priority 2
                    rule_applied="test"
                )
            ],
            total_confidence=0.90,
            execution_order=["agent:security-auditor", "agent:debugger", "agent:test-runner"],
            human_approval_required=False,
            approval_reason=""
        )

        category, reason = gate.classify_decision(diagnosis, decisions)

        assert category == DecisionCategory.ESSENTIAL
        assert "3" in reason or "high-priority" in reason.lower()

        print("✅ Test 4: Multiple high-priority agents classified as essential")

    finally:
        Path(log_file).unlink(missing_ok=True)


def test_classify_routine():
    """Test 5: Classify simple operation as routine"""
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".jsonl") as f:
        log_file = f.name

    try:
        gate = ApprovalGate(overrides_log=log_file)

        diagnosis = create_test_diagnosis(complexity=3)
        decisions = create_test_decisions()

        category, reason = gate.classify_decision(diagnosis, decisions)

        assert category == DecisionCategory.ROUTINE
        assert "Standard operation" in reason or "routine" in reason.lower()

        print("✅ Test 5: Simple operation classified as routine")

    finally:
        Path(log_file).unlink(missing_ok=True)


def test_request_approval():
    """Test 6: Create approval request"""
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".jsonl") as f:
        log_file = f.name

    try:
        gate = ApprovalGate(overrides_log=log_file)

        diagnosis = create_test_diagnosis(complexity=8)
        decisions = create_test_decisions()

        approval_request = gate.request_approval(
            "build authentication system",
            diagnosis,
            decisions
        )

        assert isinstance(approval_request, ApprovalRequest)
        assert approval_request.request_id is not None
        assert approval_request.category == DecisionCategory.ESSENTIAL
        assert approval_request.explanation.level == TransparencyLevel.DETAILED
        assert approval_request.timestamp is not None

        print("✅ Test 6: Create approval request")

    finally:
        Path(log_file).unlink(missing_ok=True)


def test_process_approval_approve():
    """Test 7: Process approve action"""
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".jsonl") as f:
        log_file = f.name

    try:
        gate = ApprovalGate(overrides_log=log_file)

        diagnosis = create_test_diagnosis(complexity=8)
        decisions = create_test_decisions()

        approval_request = gate.request_approval("test", diagnosis, decisions)

        # Process approval
        response = gate.process_approval(
            approval_request,
            ApprovalAction.APPROVE
        )

        assert response.request_id == approval_request.request_id
        assert response.action == ApprovalAction.APPROVE
        assert response.timestamp is not None

        # Should NOT log override for approval
        with open(log_file, "r") as f:
            content = f.read()
            assert content == ""

        print("✅ Test 7: Process approve action")

    finally:
        Path(log_file).unlink(missing_ok=True)


def test_process_approval_reject():
    """Test 8: Process reject action (logs override)"""
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".jsonl") as f:
        log_file = f.name

    try:
        gate = ApprovalGate(overrides_log=log_file)

        diagnosis = create_test_diagnosis(complexity=8)
        decisions = create_test_decisions()

        approval_request = gate.request_approval("test", diagnosis, decisions)

        # Process rejection
        response = gate.process_approval(
            approval_request,
            ApprovalAction.REJECT,
            notes="Not needed for this case"
        )

        assert response.action == ApprovalAction.REJECT
        assert response.notes == "Not needed for this case"

        # Should log override
        with open(log_file, "r") as f:
            content = f.read()
            assert content.strip() != ""
            assert "Not needed for this case" in content

        print("✅ Test 8: Process reject action logs override")

    finally:
        Path(log_file).unlink(missing_ok=True)


def test_process_approval_explain():
    """Test 9: Process explain action"""
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".jsonl") as f:
        log_file = f.name

    try:
        gate = ApprovalGate(overrides_log=log_file)

        diagnosis = create_test_diagnosis(complexity=8)
        decisions = create_test_decisions()

        approval_request = gate.request_approval("test", diagnosis, decisions)

        # Process explain
        response = gate.process_approval(
            approval_request,
            ApprovalAction.EXPLAIN
        )

        assert response.action == ApprovalAction.EXPLAIN

        # Should NOT log override for explain
        with open(log_file, "r") as f:
            content = f.read()
            assert content == ""

        print("✅ Test 9: Process explain action doesn't log override")

    finally:
        Path(log_file).unlink(missing_ok=True)


def test_explain_before_approval():
    """Test 10: Generate full audit explanation before approval"""
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".jsonl") as f:
        log_file = f.name

    try:
        gate = ApprovalGate(overrides_log=log_file)

        diagnosis = create_test_diagnosis(complexity=8)

        # Create decisions with at least one routing decision
        decisions = DecisionResult(
            decisions=[
                RoutingDecision(
                    component_type="skill",
                    component_name="brainstorming",
                    rationale="High complexity",
                    confidence=0.95,
                    priority=Priority.MANDATORY,
                    rule_applied="skills.brainstorming.when[0]"
                )
            ],
            total_confidence=0.95,
            execution_order=["skill:brainstorming"],
            human_approval_required=False,
            approval_reason=""
        )

        explanation = gate.explain_before_approval("test", diagnosis, decisions)

        assert explanation.level == TransparencyLevel.FULL_AUDIT
        assert explanation.rules_evaluated is not None
        assert len(explanation.rules_evaluated) > 0

        print("✅ Test 10: Generate full audit explanation")

    finally:
        Path(log_file).unlink(missing_ok=True)


def test_get_override_statistics_empty():
    """Test 11: Get override statistics with no overrides"""
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".jsonl") as f:
        log_file = f.name

    try:
        gate = ApprovalGate(overrides_log=log_file)

        stats = gate.get_override_statistics()

        assert stats["total_overrides"] == 0
        assert len(stats["most_rejected_components"]) == 0
        assert len(stats["common_rejection_reasons"]) == 0

        print("✅ Test 11: Get override statistics with no data")

    finally:
        Path(log_file).unlink(missing_ok=True)


def test_get_override_statistics_with_data():
    """Test 12: Get override statistics with data"""
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".jsonl") as f:
        log_file = f.name

    try:
        gate = ApprovalGate(overrides_log=log_file)

        diagnosis = create_test_diagnosis(complexity=8)
        decisions = create_test_decisions()

        # Log 3 rejections
        for i in range(3):
            approval_request = gate.request_approval(f"test {i}", diagnosis, decisions)
            gate.process_approval(
                approval_request,
                ApprovalAction.REJECT,
                notes="Not needed"
            )

        stats = gate.get_override_statistics()

        assert stats["total_overrides"] == 3
        assert len(stats["most_rejected_components"]) > 0
        assert len(stats["common_rejection_reasons"]) > 0

        print("✅ Test 12: Get override statistics with data")

    finally:
        Path(log_file).unlink(missing_ok=True)


def test_learn_from_overrides_empty():
    """Test 13: Learn from overrides with no data"""
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".jsonl") as f:
        log_file = f.name

    try:
        gate = ApprovalGate(overrides_log=log_file)

        adjustments = gate.learn_from_overrides()

        assert len(adjustments) == 0

        print("✅ Test 13: Learn from overrides with no data")

    finally:
        Path(log_file).unlink(missing_ok=True)


def test_learn_from_overrides_with_data():
    """Test 14: Learn from overrides with rejection data"""
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".jsonl") as f:
        log_file = f.name

    try:
        gate = ApprovalGate(overrides_log=log_file)

        diagnosis = create_test_diagnosis(complexity=8)

        # Reject security-auditor 5 times
        for i in range(5):
            decisions = DecisionResult(
                decisions=[],
                total_confidence=0.95,
                execution_order=["agent:security-auditor"],
                human_approval_required=False,
                approval_reason=""
            )

            approval_request = gate.request_approval(f"test {i}", diagnosis, decisions)
            gate.process_approval(
                approval_request,
                ApprovalAction.REJECT,
                notes="Not needed"
            )

        adjustments = gate.learn_from_overrides()

        assert "agent:security-auditor" in adjustments
        assert adjustments["agent:security-auditor"] < 1.0  # Should decrease confidence

        print("✅ Test 14: Learn from overrides suggests confidence decrease")

    finally:
        Path(log_file).unlink(missing_ok=True)


def test_custom_request_id():
    """Test 15: Support custom request_id in approval request"""
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".jsonl") as f:
        log_file = f.name

    try:
        gate = ApprovalGate(overrides_log=log_file)

        diagnosis = create_test_diagnosis(complexity=8)
        decisions = create_test_decisions()

        custom_id = "my-custom-id-123"
        approval_request = gate.request_approval(
            "test",
            diagnosis,
            decisions,
            request_id=custom_id
        )

        assert approval_request.request_id == custom_id

        print("✅ Test 15: Support custom request_id")

    finally:
        Path(log_file).unlink(missing_ok=True)


def run_all_tests():
    """Run all 15 test cases"""
    tests = [
        test_classify_destructive_operation,
        test_classify_production_deployment,
        test_classify_high_complexity,
        test_classify_multiple_high_priority_agents,
        test_classify_routine,
        test_request_approval,
        test_process_approval_approve,
        test_process_approval_reject,
        test_process_approval_explain,
        test_explain_before_approval,
        test_get_override_statistics_empty,
        test_get_override_statistics_with_data,
        test_learn_from_overrides_empty,
        test_learn_from_overrides_with_data,
        test_custom_request_id,
    ]

    print("\n" + "="*60)
    print("HUMAN-IN-THE-LOOP TEST SUITE")
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
