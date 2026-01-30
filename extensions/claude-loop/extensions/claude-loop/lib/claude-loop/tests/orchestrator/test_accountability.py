#!/usr/bin/env python3
"""
Comprehensive test suite for Accountability Layer with Decision Logging

Tests decision logging, outcome tracking, query interface, and learning algorithm.
"""

import sys
import json
import tempfile
from pathlib import Path
from datetime import datetime, timedelta

# Add lib/orchestrator to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "lib" / "orchestrator"))

from accountability import AccountabilityLogger, Outcome, OutcomeType, DecisionLog
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


def test_log_decision():
    """Test 1: Log a decision and verify format"""
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".jsonl") as f:
        log_file = f.name

    try:
        logger = AccountabilityLogger(log_file=log_file)

        # Log a decision
        diagnosis = create_test_diagnosis()
        decisions = create_test_decisions()

        request_id = logger.log_decision(
            user_request="build authentication system",
            diagnosis=diagnosis,
            decisions=decisions
        )

        assert request_id, "Should return request_id"

        # Read log file and verify
        with open(log_file, "r") as f:
            line = f.readline()
            entry = json.loads(line)

        assert entry["request_id"] == request_id, "Request ID should match"
        assert entry["user_request"] == "build authentication system", "User request should match"
        assert "timestamp" in entry, "Should have timestamp"
        assert "diagnosis" in entry, "Should have diagnosis"
        assert "decisions" in entry, "Should have decisions"
        assert entry["outcome"] is None, "Outcome should be None initially"

        print("✅ Test 1: Log decision and verify format")

    finally:
        Path(log_file).unlink(missing_ok=True)


def test_log_outcome():
    """Test 2: Log outcome for a decision"""
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".jsonl") as f:
        log_file = f.name

    try:
        logger = AccountabilityLogger(log_file=log_file)

        # Log decision
        diagnosis = create_test_diagnosis()
        decisions = create_test_decisions()
        request_id = logger.log_decision("test request", diagnosis, decisions)

        # Log outcome
        outcome = Outcome(
            outcome_type=OutcomeType.SUCCESS,
            time_taken_seconds=5.2,
            issues_found=[],
            tests_passed=True,
            quality_score=0.95
        )

        success = logger.log_outcome(request_id, outcome)
        assert success, "Should successfully log outcome"

        # Verify outcome was logged
        entries = logger.query_decisions(request_id=request_id)
        assert len(entries) == 1, "Should find one entry"
        assert entries[0].outcome is not None, "Should have outcome"
        assert entries[0].outcome["outcome_type"] == "success", "Outcome type should match"
        assert entries[0].outcome["time_taken_seconds"] == 5.2, "Time should match"

        print("✅ Test 2: Log outcome for decision")

    finally:
        Path(log_file).unlink(missing_ok=True)


def test_log_outcome_nonexistent():
    """Test 3: Log outcome for nonexistent request_id"""
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".jsonl") as f:
        log_file = f.name

    try:
        logger = AccountabilityLogger(log_file=log_file)

        outcome = Outcome(
            outcome_type=OutcomeType.SUCCESS,
            time_taken_seconds=5.2,
            issues_found=[]
        )

        success = logger.log_outcome("nonexistent-id", outcome)
        assert not success, "Should return False for nonexistent request_id"

        print("✅ Test 3: Log outcome for nonexistent request_id")

    finally:
        Path(log_file).unlink(missing_ok=True)


def test_query_by_request_id():
    """Test 4: Query decisions by request_id"""
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".jsonl") as f:
        log_file = f.name

    try:
        logger = AccountabilityLogger(log_file=log_file)

        # Log multiple decisions
        diagnosis = create_test_diagnosis()
        decisions = create_test_decisions()

        request_id_1 = logger.log_decision("request 1", diagnosis, decisions)
        request_id_2 = logger.log_decision("request 2", diagnosis, decisions)
        request_id_3 = logger.log_decision("request 3", diagnosis, decisions)

        # Query specific request_id
        results = logger.query_decisions(request_id=request_id_2)
        assert len(results) == 1, "Should find exactly one entry"
        assert results[0].request_id == request_id_2, "Should match request_id"
        assert results[0].user_request == "request 2", "Should match user request"

        print("✅ Test 4: Query by request_id")

    finally:
        Path(log_file).unlink(missing_ok=True)


def test_query_by_time_range():
    """Test 5: Query decisions by time range"""
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".jsonl") as f:
        log_file = f.name

    try:
        logger = AccountabilityLogger(log_file=log_file)

        # Log decisions
        diagnosis = create_test_diagnosis()
        decisions = create_test_decisions()

        for i in range(5):
            logger.log_decision(f"request {i}", diagnosis, decisions)

        # Query last hour
        start_time = datetime.utcnow() - timedelta(hours=1)
        results = logger.query_decisions(start_time=start_time)

        assert len(results) == 5, "Should find all 5 entries from last hour"

        # Query future (should find nothing)
        start_time = datetime.utcnow() + timedelta(hours=1)
        results = logger.query_decisions(start_time=start_time)
        assert len(results) == 0, "Should find no entries in future"

        print("✅ Test 5: Query by time range")

    finally:
        Path(log_file).unlink(missing_ok=True)


def test_query_by_outcome_type():
    """Test 6: Query decisions by outcome type"""
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".jsonl") as f:
        log_file = f.name

    try:
        logger = AccountabilityLogger(log_file=log_file)

        diagnosis = create_test_diagnosis()
        decisions = create_test_decisions()

        # Log 3 successful, 2 failures
        for i in range(3):
            req_id = logger.log_decision(f"success {i}", diagnosis, decisions)
            logger.log_outcome(req_id, Outcome(
                outcome_type=OutcomeType.SUCCESS,
                time_taken_seconds=5.0,
                issues_found=[]
            ))

        for i in range(2):
            req_id = logger.log_decision(f"failure {i}", diagnosis, decisions)
            logger.log_outcome(req_id, Outcome(
                outcome_type=OutcomeType.FAILURE,
                time_taken_seconds=10.0,
                issues_found=["test failed"]
            ))

        # Query successes
        results = logger.query_decisions(outcome_type=OutcomeType.SUCCESS)
        assert len(results) == 3, "Should find 3 successes"

        # Query failures
        results = logger.query_decisions(outcome_type=OutcomeType.FAILURE)
        assert len(results) == 2, "Should find 2 failures"

        print("✅ Test 6: Query by outcome type")

    finally:
        Path(log_file).unlink(missing_ok=True)


def test_query_has_outcome():
    """Test 7: Query decisions with/without outcomes"""
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".jsonl") as f:
        log_file = f.name

    try:
        logger = AccountabilityLogger(log_file=log_file)

        diagnosis = create_test_diagnosis()
        decisions = create_test_decisions()

        # Log 3 with outcomes, 2 without
        for i in range(3):
            req_id = logger.log_decision(f"with outcome {i}", diagnosis, decisions)
            logger.log_outcome(req_id, Outcome(
                outcome_type=OutcomeType.SUCCESS,
                time_taken_seconds=5.0,
                issues_found=[]
            ))

        for i in range(2):
            logger.log_decision(f"without outcome {i}", diagnosis, decisions)

        # Query with outcomes
        results = logger.query_decisions(has_outcome=True)
        assert len(results) == 3, "Should find 3 with outcomes"

        # Query without outcomes
        results = logger.query_decisions(has_outcome=False)
        assert len(results) == 2, "Should find 2 without outcomes"

        print("✅ Test 7: Query with/without outcomes")

    finally:
        Path(log_file).unlink(missing_ok=True)


def test_query_limit():
    """Test 8: Query with limit"""
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".jsonl") as f:
        log_file = f.name

    try:
        logger = AccountabilityLogger(log_file=log_file)

        diagnosis = create_test_diagnosis()
        decisions = create_test_decisions()

        # Log 10 decisions
        for i in range(10):
            logger.log_decision(f"request {i}", diagnosis, decisions)

        # Query with limit=5
        results = logger.query_decisions(limit=5)
        assert len(results) == 5, "Should respect limit"

        # Query with limit=100 (more than available)
        results = logger.query_decisions(limit=100)
        assert len(results) == 10, "Should return all available"

        print("✅ Test 8: Query with limit")

    finally:
        Path(log_file).unlink(missing_ok=True)


def test_get_statistics():
    """Test 9: Get decision statistics"""
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".jsonl") as f:
        log_file = f.name

    try:
        logger = AccountabilityLogger(log_file=log_file)

        diagnosis = create_test_diagnosis()
        decisions = create_test_decisions()

        # Log 7 successful, 3 failures
        for i in range(7):
            req_id = logger.log_decision(f"success {i}", diagnosis, decisions)
            logger.log_outcome(req_id, Outcome(
                outcome_type=OutcomeType.SUCCESS,
                time_taken_seconds=5.0 + i,
                issues_found=[]
            ))

        for i in range(3):
            req_id = logger.log_decision(f"failure {i}", diagnosis, decisions)
            logger.log_outcome(req_id, Outcome(
                outcome_type=OutcomeType.FAILURE,
                time_taken_seconds=10.0,
                issues_found=["error"]
            ))

        # Get statistics
        stats = logger.get_decision_statistics()

        assert stats["total_decisions"] == 10, "Should have 10 total decisions"
        assert stats["decisions_with_outcomes"] == 10, "All should have outcomes"
        assert stats["success_rate"] == 70.0, "Success rate should be 70%"
        assert stats["avg_time_seconds"] > 0, "Should have average time"
        assert "most_common_components" in stats, "Should have component stats"
        assert "confidence_accuracy" in stats, "Should have confidence accuracy"

        print("✅ Test 9: Get decision statistics")

    finally:
        Path(log_file).unlink(missing_ok=True)


def test_learn_from_outcomes():
    """Test 10: Learn from outcomes (confidence adjustments)"""
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".jsonl") as f:
        log_file = f.name

    try:
        logger = AccountabilityLogger(log_file=log_file)

        diagnosis = create_test_diagnosis()

        # Component A: Always succeeds (5 times)
        decisions_a = DecisionResult(
            decisions=[
                RoutingDecision(
                    component_type="agent",
                    component_name="component-a",
                    rationale="Test",
                    confidence=0.8,
                    priority=Priority.DOMAIN_BASED,
                    rule_applied="test"
                )
            ],
            total_confidence=0.8,
            execution_order=["agent:component-a"],
            human_approval_required=False,
            approval_reason=""
        )

        for i in range(5):
            req_id = logger.log_decision(f"component-a {i}", diagnosis, decisions_a)
            logger.log_outcome(req_id, Outcome(
                outcome_type=OutcomeType.SUCCESS,
                time_taken_seconds=5.0,
                issues_found=[]
            ))

        # Component B: Always fails (5 times)
        decisions_b = DecisionResult(
            decisions=[
                RoutingDecision(
                    component_type="agent",
                    component_name="component-b",
                    rationale="Test",
                    confidence=0.8,
                    priority=Priority.DOMAIN_BASED,
                    rule_applied="test"
                )
            ],
            total_confidence=0.8,
            execution_order=["agent:component-b"],
            human_approval_required=False,
            approval_reason=""
        )

        for i in range(5):
            req_id = logger.log_decision(f"component-b {i}", diagnosis, decisions_b)
            logger.log_outcome(req_id, Outcome(
                outcome_type=OutcomeType.FAILURE,
                time_taken_seconds=5.0,
                issues_found=["error"]
            ))

        # Learn from outcomes
        adjustments = logger.learn_from_outcomes()

        assert "agent:component-a" in adjustments, "Should have adjustment for component-a"
        assert "agent:component-b" in adjustments, "Should have adjustment for component-b"
        assert adjustments["agent:component-a"] > 1.0, "Component-a should get confidence boost"
        assert adjustments["agent:component-b"] < 1.0, "Component-b should get confidence reduction"

        print("✅ Test 10: Learn from outcomes")

    finally:
        Path(log_file).unlink(missing_ok=True)


def test_logging_performance():
    """Test 11: Verify logging overhead <10ms"""
    import time

    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".jsonl") as f:
        log_file = f.name

    try:
        logger = AccountabilityLogger(log_file=log_file)

        diagnosis = create_test_diagnosis()
        decisions = create_test_decisions()

        # Time 10 log operations
        start = time.time()
        for i in range(10):
            logger.log_decision(f"request {i}", diagnosis, decisions)
        elapsed = (time.time() - start) * 1000  # Convert to ms

        avg_time = elapsed / 10
        assert avg_time < 10, f"Logging should be <10ms, got {avg_time:.2f}ms"

        print(f"✅ Test 11: Logging performance ({avg_time:.2f}ms avg)")

    finally:
        Path(log_file).unlink(missing_ok=True)


def test_json_lines_format():
    """Test 12: Verify JSON Lines format (one JSON object per line)"""
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".jsonl") as f:
        log_file = f.name

    try:
        logger = AccountabilityLogger(log_file=log_file)

        diagnosis = create_test_diagnosis()
        decisions = create_test_decisions()

        # Log 3 decisions
        for i in range(3):
            logger.log_decision(f"request {i}", diagnosis, decisions)

        # Verify format: each line is valid JSON
        with open(log_file, "r") as f:
            lines = f.readlines()

        assert len(lines) == 3, "Should have 3 lines"

        for line in lines:
            line = line.strip()
            assert line, "Line should not be empty"
            entry = json.loads(line)  # Should not raise exception
            assert "request_id" in entry, "Each line should be a DecisionLog"
            assert "timestamp" in entry, "Each line should have timestamp"

        print("✅ Test 12: JSON Lines format")

    finally:
        Path(log_file).unlink(missing_ok=True)


def test_empty_log_file():
    """Test 13: Handle empty log file gracefully"""
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".jsonl") as f:
        log_file = f.name

    try:
        logger = AccountabilityLogger(log_file=log_file)

        # Query empty log
        results = logger.query_decisions()
        assert len(results) == 0, "Should return empty list for empty log"

        # Get statistics for empty log
        stats = logger.get_decision_statistics()
        assert stats["total_decisions"] == 0, "Should have 0 decisions"
        assert stats["success_rate"] == 0.0, "Success rate should be 0"

        # Learn from empty log
        adjustments = logger.learn_from_outcomes()
        assert len(adjustments) == 0, "Should return empty dict"

        print("✅ Test 13: Handle empty log file")

    finally:
        Path(log_file).unlink(missing_ok=True)


def test_confidence_accuracy_calculation():
    """Test 14: Confidence accuracy correlation calculation"""
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".jsonl") as f:
        log_file = f.name

    try:
        logger = AccountabilityLogger(log_file=log_file)

        diagnosis = create_test_diagnosis()

        # High confidence → mostly success
        for i in range(5):
            decisions = DecisionResult(
                decisions=[],
                total_confidence=0.95,  # High confidence
                execution_order=["test"],
                human_approval_required=False,
                approval_reason=""
            )
            req_id = logger.log_decision(f"high-conf {i}", diagnosis, decisions)
            # 80% success rate for high confidence
            outcome_type = OutcomeType.SUCCESS if i < 4 else OutcomeType.FAILURE
            logger.log_outcome(req_id, Outcome(
                outcome_type=outcome_type,
                time_taken_seconds=5.0,
                issues_found=[]
            ))

        # Low confidence → mostly failure
        for i in range(5):
            decisions = DecisionResult(
                decisions=[],
                total_confidence=0.55,  # Low confidence
                execution_order=["test"],
                human_approval_required=False,
                approval_reason=""
            )
            req_id = logger.log_decision(f"low-conf {i}", diagnosis, decisions)
            # 20% success rate for low confidence
            outcome_type = OutcomeType.SUCCESS if i < 1 else OutcomeType.FAILURE
            logger.log_outcome(req_id, Outcome(
                outcome_type=outcome_type,
                time_taken_seconds=5.0,
                issues_found=[]
            ))

        stats = logger.get_decision_statistics()
        # Should show positive correlation (high confidence → success)
        assert stats["confidence_accuracy"] > 0.3, "Should show positive correlation"

        print("✅ Test 14: Confidence accuracy calculation")

    finally:
        Path(log_file).unlink(missing_ok=True)


def test_custom_request_id():
    """Test 15: Support custom request_id"""
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".jsonl") as f:
        log_file = f.name

    try:
        logger = AccountabilityLogger(log_file=log_file)

        diagnosis = create_test_diagnosis()
        decisions = create_test_decisions()

        # Log with custom request_id
        custom_id = "my-custom-id-123"
        returned_id = logger.log_decision(
            "test request",
            diagnosis,
            decisions,
            request_id=custom_id
        )

        assert returned_id == custom_id, "Should return custom request_id"

        # Query by custom ID
        results = logger.query_decisions(request_id=custom_id)
        assert len(results) == 1, "Should find entry with custom ID"
        assert results[0].request_id == custom_id, "Should match custom ID"

        print("✅ Test 15: Support custom request_id")

    finally:
        Path(log_file).unlink(missing_ok=True)


def run_all_tests():
    """Run all 15 test cases"""
    tests = [
        test_log_decision,
        test_log_outcome,
        test_log_outcome_nonexistent,
        test_query_by_request_id,
        test_query_by_time_range,
        test_query_by_outcome_type,
        test_query_has_outcome,
        test_query_limit,
        test_get_statistics,
        test_learn_from_outcomes,
        test_logging_performance,
        test_json_lines_format,
        test_empty_log_file,
        test_confidence_accuracy_calculation,
        test_custom_request_id,
    ]

    print("\n" + "="*60)
    print("ACCOUNTABILITY LAYER TEST SUITE")
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
