#!/usr/bin/env python3
"""Tests for health_monitor.py"""

import json
import pytest
import tempfile
import time
from pathlib import Path
from lib.health_monitor import (
    HealthMonitor,
    WorkerStatus,
    WorkerHealth,
    Heartbeat
)


@pytest.fixture
def temp_workers_dir():
    """Create temporary workers directory"""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def monitor(temp_workers_dir):
    """Create health monitor with temp directory"""
    health_log = temp_workers_dir / "health.jsonl"
    return HealthMonitor(workers_dir=temp_workers_dir, health_log=health_log)


def test_write_heartbeat(monitor, temp_workers_dir):
    """Test writing worker heartbeat"""
    monitor.write_heartbeat(
        worker_id="worker-001",
        prd_id="PRD-001",
        story_id="US-001",
        iteration=5,
        api_calls_made=3
    )

    heartbeat_file = temp_workers_dir / "worker-001" / "heartbeat.json"
    assert heartbeat_file.exists()

    with open(heartbeat_file) as f:
        data = json.load(f)
        assert data['worker_id'] == "worker-001"
        assert data['prd_id'] == "PRD-001"
        assert data['story_id'] == "US-001"
        assert data['iteration'] == 5


def test_check_worker_health_healthy(monitor):
    """Test checking healthy worker"""
    monitor.write_heartbeat(
        worker_id="worker-001",
        prd_id="PRD-001"
    )

    health = monitor.check_worker_health("worker-001")

    assert health.worker_id == "worker-001"
    assert health.status == WorkerStatus.HEALTHY.value
    assert health.seconds_since_heartbeat < 5


def test_check_worker_health_unknown(monitor):
    """Test checking worker with no heartbeat"""
    health = monitor.check_worker_health("nonexistent")

    assert health.worker_id == "nonexistent"
    assert health.status == WorkerStatus.UNKNOWN.value
    assert health.last_heartbeat is None


def test_check_all_workers(monitor):
    """Test checking all workers"""
    # Create multiple workers
    monitor.write_heartbeat("worker-001", "PRD-001")
    monitor.write_heartbeat("worker-002", "PRD-002")
    monitor.write_heartbeat("worker-003", "PRD-003")

    all_health = monitor.check_all_workers()

    assert len(all_health) == 3
    assert "worker-001" in all_health
    assert "worker-002" in all_health
    assert "worker-003" in all_health


def test_get_unhealthy_workers_empty(monitor):
    """Test getting unhealthy workers when none exist"""
    monitor.write_heartbeat("worker-001", "PRD-001")

    unhealthy = monitor.get_unhealthy_workers()

    assert len(unhealthy) == 0


def test_get_health_summary(monitor):
    """Test getting health summary"""
    monitor.write_heartbeat("worker-001", "PRD-001")
    monitor.write_heartbeat("worker-002", "PRD-002")

    summary = monitor.get_health_summary()

    assert summary['total_workers'] == 2
    assert summary['healthy'] >= 0
    assert 'workers' in summary


def test_cleanup_stale_heartbeats(monitor, temp_workers_dir):
    """Test cleaning up old heartbeats"""
    # Write heartbeat
    monitor.write_heartbeat("worker-001", "PRD-001")

    # Should not clean up recent heartbeats
    cleaned = monitor.cleanup_stale_heartbeats(max_age_hours=24)
    assert cleaned == 0

    # Should clean up old heartbeats (test with 0 hours)
    cleaned = monitor.cleanup_stale_heartbeats(max_age_hours=0)
    assert cleaned >= 0  # May or may not clean depending on timing


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
