#!/usr/bin/env python3
"""Tests for retry_handler.py"""

import json
import pytest
import tempfile
from pathlib import Path
from lib.retry_handler import (
    RetryHandler,
    RetryPolicy,
    RetryDecision
)


@pytest.fixture
def temp_retries_log():
    """Create temporary retries log"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False) as f:
        yield Path(f.name)
    Path(f.name).unlink(missing_ok=True)


@pytest.fixture
def handler(temp_retries_log):
    """Create retry handler with temp log"""
    return RetryHandler(retries_log=temp_retries_log)


def test_should_retry_api_error(handler):
    """Test retry decision for API error"""
    decision = handler.should_retry(
        prd_id="PRD-001",
        failure_type="api_error",
        attempt=0
    )

    assert decision.should_retry is True
    assert decision.backoff_seconds == 60.0  # Base backoff
    assert decision.attempts_remaining == 2


def test_should_retry_exponential_backoff(handler):
    """Test exponential backoff calculation"""
    # First attempt: 60s
    decision1 = handler.should_retry("PRD-001", "api_error", attempt=0)
    assert decision1.backoff_seconds == 60.0

    # Second attempt: 120s
    decision2 = handler.should_retry("PRD-001", "api_error", attempt=1)
    assert decision2.backoff_seconds == 120.0

    # Third attempt: 240s
    decision3 = handler.should_retry("PRD-001", "api_error", attempt=2)
    assert decision3.backoff_seconds == 240.0


def test_should_retry_max_retries_exceeded(handler):
    """Test no retry after max attempts"""
    decision = handler.should_retry(
        prd_id="PRD-001",
        failure_type="api_error",
        attempt=3  # Max is 3
    )

    assert decision.should_retry is False
    assert "Maximum retries" in decision.reason


def test_should_not_retry_logic_error(handler):
    """Test no retry for logic errors"""
    decision = handler.should_retry(
        prd_id="PRD-001",
        failure_type="logic_error",
        attempt=0
    )

    assert decision.should_retry is False
    assert "manual intervention" in decision.reason


def test_should_not_retry_quality_gate_failure(handler):
    """Test no retry for quality gate failures"""
    decision = handler.should_retry(
        prd_id="PRD-001",
        failure_type="quality_gate_failure",
        attempt=0
    )

    assert decision.should_retry is False


def test_should_retry_timeout(handler):
    """Test retry for timeout"""
    decision = handler.should_retry(
        prd_id="PRD-001",
        failure_type="timeout",
        attempt=0
    )

    assert decision.should_retry is True


def test_should_retry_resource_exhaustion(handler):
    """Test retry for resource exhaustion"""
    decision = handler.should_retry(
        prd_id="PRD-001",
        failure_type="resource_exhaustion",
        attempt=0
    )

    assert decision.should_retry is True


def test_should_retry_unknown(handler):
    """Test retry for unknown failures (conservative)"""
    decision = handler.should_retry(
        prd_id="PRD-001",
        failure_type="unknown",
        attempt=0
    )

    assert decision.should_retry is True


def test_record_no_retry(handler, temp_retries_log):
    """Test recording no-retry decision"""
    handler.record_no_retry(
        prd_id="PRD-001",
        failure_type="logic_error",
        reason="Test failure requires manual fix",
        error_message="Test error"
    )

    # Should log to file
    with open(temp_retries_log) as f:
        lines = f.readlines()
        assert len(lines) == 1
        record = json.loads(lines[0])
        assert record['will_retry'] is False


def test_retry_count_tracking(handler):
    """Test retry count increments"""
    assert handler.get_retry_count("PRD-001") == 0

    handler.should_retry("PRD-001", "api_error", attempt=0)
    assert handler.get_retry_count("PRD-001") == 1

    handler.should_retry("PRD-001", "api_error", attempt=1)
    assert handler.get_retry_count("PRD-001") == 2


def test_reset_retry_count(handler):
    """Test resetting retry count"""
    handler.should_retry("PRD-001", "api_error", attempt=0)
    assert handler.get_retry_count("PRD-001") == 1

    handler.reset_retry_count("PRD-001")
    assert handler.get_retry_count("PRD-001") == 0


def test_get_retry_stats(handler):
    """Test getting retry statistics"""
    handler.should_retry("PRD-001", "api_error", attempt=0)
    handler.should_retry("PRD-001", "api_error", attempt=1)
    handler.should_retry("PRD-002", "timeout", attempt=0)

    stats = handler.get_retry_stats()

    assert stats['total_retries'] == 3
    assert stats['by_prd']['PRD-001'] == 2
    assert stats['by_prd']['PRD-002'] == 1
    assert stats['by_failure_type']['api_error'] == 2
    assert stats['by_failure_type']['timeout'] == 1


def test_custom_retry_config():
    """Test custom retry configuration"""
    handler = RetryHandler(
        max_retries=5,
        backoff_multiplier=3.0,
        base_backoff_seconds=30.0
    )

    decision = handler.should_retry("PRD-001", "api_error", attempt=0)

    assert decision.should_retry is True
    assert decision.backoff_seconds == 30.0
    assert decision.attempts_remaining == 4  # 5 max - 1 used


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
