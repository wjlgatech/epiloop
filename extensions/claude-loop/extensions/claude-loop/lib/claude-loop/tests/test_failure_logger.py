#!/usr/bin/env python3
"""Tests for failure_logger.py"""

import json
import pytest
import tempfile
from pathlib import Path
from lib.failure_logger import (
    FailureLogger,
    FailureType,
    FailureRecord,
    read_last_n_lines
)


@pytest.fixture
def temp_failures_file():
    """Create temporary failures file"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False) as f:
        yield Path(f.name)
    Path(f.name).unlink(missing_ok=True)


@pytest.fixture
def logger(temp_failures_file):
    """Create failure logger with temp file"""
    return FailureLogger(failures_file=temp_failures_file)


def test_log_failure_basic(logger, temp_failures_file):
    """Test basic failure logging"""
    logger.log_failure(
        prd_id="PRD-001",
        failure_type=FailureType.API_ERROR,
        error_message="Rate limit exceeded",
        story_id="US-001",
        exit_code=1
    )

    # Verify file created and contains entry
    assert temp_failures_file.exists()

    with open(temp_failures_file) as f:
        lines = f.readlines()
        assert len(lines) == 1

        record = json.loads(lines[0])
        assert record['prd_id'] == "PRD-001"
        assert record['failure_type'] == "api_error"
        assert record['error_message'] == "Rate limit exceeded"
        assert record['story_id'] == "US-001"
        assert record['exit_code'] == 1


def test_log_failure_with_context(logger, temp_failures_file):
    """Test logging with additional context"""
    logger.log_failure(
        prd_id="PRD-002",
        failure_type=FailureType.BUG,
        error_message="Unbound variable",
        context={"file": "worker.sh", "line": 123},
        worker_id="worker-001"
    )

    with open(temp_failures_file) as f:
        record = json.loads(f.readline())
        assert record['context']['file'] == "worker.sh"
        assert record['context']['line'] == 123
        assert record['worker_id'] == "worker-001"


def test_log_exception(logger, temp_failures_file):
    """Test logging from exception"""
    try:
        raise ValueError("Test error")
    except ValueError as e:
        logger.log_exception(
            prd_id="PRD-003",
            failure_type=FailureType.BUG,
            exception=e,
            story_id="US-002"
        )

    with open(temp_failures_file) as f:
        record = json.loads(f.readline())
        assert record['error_message'] == "Test error"
        assert 'ValueError' in record['stack_trace']
        assert record['failure_type'] == "bug"


def test_multiple_failures(logger, temp_failures_file):
    """Test logging multiple failures"""
    for i in range(5):
        logger.log_failure(
            prd_id=f"PRD-{i:03d}",
            failure_type=FailureType.TIMEOUT,
            error_message=f"Timeout {i}"
        )

    with open(temp_failures_file) as f:
        lines = f.readlines()
        assert len(lines) == 5


def test_get_recent_failures(logger):
    """Test retrieving recent failures"""
    # Log some failures
    for i in range(15):
        logger.log_failure(
            prd_id="PRD-001",
            failure_type=FailureType.API_ERROR,
            error_message=f"Error {i}"
        )

    # Get recent (default limit=10)
    recent = logger.get_recent_failures(limit=10)
    assert len(recent) == 10
    # Should be most recent first
    assert recent[0]['error_message'] == "Error 14"


def test_get_recent_failures_filtered_by_prd(logger):
    """Test filtering failures by PRD"""
    logger.log_failure("PRD-001", FailureType.API_ERROR, "Error 1")
    logger.log_failure("PRD-002", FailureType.API_ERROR, "Error 2")
    logger.log_failure("PRD-001", FailureType.API_ERROR, "Error 3")

    failures = logger.get_recent_failures(prd_id="PRD-001")
    assert len(failures) == 2
    assert all(f['prd_id'] == "PRD-001" for f in failures)


def test_get_recent_failures_filtered_by_type(logger):
    """Test filtering failures by type"""
    logger.log_failure("PRD-001", FailureType.API_ERROR, "API Error")
    logger.log_failure("PRD-001", FailureType.TIMEOUT, "Timeout")
    logger.log_failure("PRD-001", FailureType.API_ERROR, "API Error 2")

    failures = logger.get_recent_failures(failure_type=FailureType.API_ERROR)
    assert len(failures) == 2
    assert all(f['failure_type'] == "api_error" for f in failures)


def test_get_failure_stats(logger):
    """Test failure statistics"""
    # Log various failures
    logger.log_failure("PRD-001", FailureType.API_ERROR, "Error 1")
    logger.log_failure("PRD-001", FailureType.API_ERROR, "Error 2")
    logger.log_failure("PRD-002", FailureType.TIMEOUT, "Timeout")
    logger.log_failure("PRD-002", FailureType.BUG, "Bug")

    stats = logger.get_failure_stats()

    assert stats['total'] == 4
    assert stats['by_type']['api_error'] == 2
    assert stats['by_type']['timeout'] == 1
    assert stats['by_type']['bug'] == 1
    assert stats['by_prd']['PRD-001'] == 2
    assert stats['by_prd']['PRD-002'] == 2


def test_classify_failure_api_error():
    """Test automatic classification - API errors"""
    assert FailureLogger.classify_failure_from_error("Rate limit exceeded") == FailureType.API_ERROR
    assert FailureLogger.classify_failure_from_error("429 Too Many Requests") == FailureType.API_ERROR
    assert FailureLogger.classify_failure_from_error("Authentication failed") == FailureType.API_ERROR


def test_classify_failure_resource_exhaustion():
    """Test automatic classification - resource exhaustion"""
    assert FailureLogger.classify_failure_from_error("Out of memory") == FailureType.RESOURCE_EXHAUSTION
    assert FailureLogger.classify_failure_from_error("Disk space full") == FailureType.RESOURCE_EXHAUSTION
    assert FailureLogger.classify_failure_from_error("OOM killed", exit_code=137) == FailureType.RESOURCE_EXHAUSTION


def test_classify_failure_timeout():
    """Test automatic classification - timeouts"""
    assert FailureLogger.classify_failure_from_error("Operation timed out") == FailureType.TIMEOUT
    assert FailureLogger.classify_failure_from_error("Deadline exceeded") == FailureType.TIMEOUT
    assert FailureLogger.classify_failure_from_error("Timeout", exit_code=124) == FailureType.TIMEOUT


def test_classify_failure_quality_gate():
    """Test automatic classification - quality gate failures"""
    assert FailureLogger.classify_failure_from_error("Test failed") == FailureType.QUALITY_GATE_FAILURE
    assert FailureLogger.classify_failure_from_error("Lint errors") == FailureType.QUALITY_GATE_FAILURE
    assert FailureLogger.classify_failure_from_error("Type check failed") == FailureType.QUALITY_GATE_FAILURE


def test_classify_failure_coordinator():
    """Test automatic classification - coordinator errors"""
    assert FailureLogger.classify_failure_from_error("Coordinator error") == FailureType.COORDINATOR_ERROR
    assert FailureLogger.classify_failure_from_error("Registry lock failed") == FailureType.COORDINATOR_ERROR


def test_classify_failure_unknown():
    """Test automatic classification - unknown"""
    assert FailureLogger.classify_failure_from_error("Something went wrong") == FailureType.UNKNOWN


def test_read_last_n_lines():
    """Test reading last N lines from file"""
    with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
        for i in range(200):
            f.write(f"Line {i}\n")
        temp_file = Path(f.name)

    try:
        lines = read_last_n_lines(temp_file, n=50)
        assert len(lines) == 50
        assert lines[-1] == "Line 199"
        assert lines[0] == "Line 150"
    finally:
        temp_file.unlink()


def test_read_last_n_lines_short_file():
    """Test reading from file with fewer lines than requested"""
    with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
        for i in range(10):
            f.write(f"Line {i}\n")
        temp_file = Path(f.name)

    try:
        lines = read_last_n_lines(temp_file, n=100)
        assert len(lines) == 10
    finally:
        temp_file.unlink()


def test_read_last_n_lines_nonexistent():
    """Test reading from nonexistent file"""
    lines = read_last_n_lines(Path("/nonexistent/file.txt"))
    assert lines == []


def test_system_resources_captured(logger, temp_failures_file):
    """Test that system resources are captured"""
    logger.log_failure(
        prd_id="PRD-001",
        failure_type=FailureType.RESOURCE_EXHAUSTION,
        error_message="Out of memory"
    )

    with open(temp_failures_file) as f:
        record = json.loads(f.readline())
        resources = record['system_resources']

        # Should have some resource info (may be empty if psutil unavailable)
        assert isinstance(resources, dict)


def test_empty_failures_file_stats(temp_failures_file):
    """Test stats on empty failures file"""
    logger = FailureLogger(failures_file=temp_failures_file)
    stats = logger.get_failure_stats()

    assert stats['total'] == 0
    assert stats['by_type'] == {}
    assert stats['by_prd'] == {}
    assert stats['recent'] == []


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
