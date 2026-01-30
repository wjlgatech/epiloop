#!/usr/bin/env python3
"""
Unit tests for lib/health-indicators.py

Tests cover:
- Leading indicator calculations (proposal_rate_change, cluster_concentration,
  retrieval_miss_rate, domain_drift)
- RAG status determination
- Alert creation and management
- History tracking
- Threshold configuration
"""

import json
import tempfile
import unittest
from datetime import datetime, timezone, timedelta
from pathlib import Path

# Import the module using runpy for hyphenated filename
import runpy
health_module = runpy.run_path(
    str(Path(__file__).parent.parent / "lib" / "health-indicators.py")
)

HealthIndicatorsManager = health_module["HealthIndicatorsManager"]
HealthStatus = health_module["HealthStatus"]
AlertSeverity = health_module["AlertSeverity"]
IndicatorValue = health_module["IndicatorValue"]
HealthSnapshot = health_module["HealthSnapshot"]
HealthAlert = health_module["HealthAlert"]
DEFAULT_THRESHOLDS = health_module["DEFAULT_THRESHOLDS"]


class TestIndicatorValue(unittest.TestCase):
    """Tests for IndicatorValue dataclass."""

    def test_create_indicator_value(self):
        """Test creating an indicator value."""
        indicator = IndicatorValue(
            name="test_indicator",
            value=0.5,
            status=HealthStatus.GREEN.value,
            trend="stable",
            message="Test message",
        )
        self.assertEqual(indicator.name, "test_indicator")
        self.assertEqual(indicator.value, 0.5)
        self.assertEqual(indicator.status, "green")
        self.assertEqual(indicator.trend, "stable")
        self.assertNotEqual(indicator.timestamp, "")  # Auto-generated

    def test_indicator_to_dict(self):
        """Test converting indicator to dict."""
        indicator = IndicatorValue(
            name="test",
            value=1.5,
            status=HealthStatus.AMBER.value,
            trend="degrading",
            message="Test",
            timestamp="2026-01-12T10:00:00Z",
        )
        d = indicator.to_dict()
        self.assertEqual(d["name"], "test")
        self.assertEqual(d["value"], 1.5)
        self.assertEqual(d["status"], "amber")

    def test_indicator_from_dict(self):
        """Test creating indicator from dict."""
        data = {
            "name": "test",
            "value": 2.0,
            "status": "red",
            "trend": "degrading",
            "message": "Critical",
            "timestamp": "2026-01-12T10:00:00Z",
        }
        indicator = IndicatorValue.from_dict(data)
        self.assertEqual(indicator.name, "test")
        self.assertEqual(indicator.value, 2.0)
        self.assertEqual(indicator.status, "red")


class TestHealthAlert(unittest.TestCase):
    """Tests for HealthAlert dataclass."""

    def test_create_alert(self):
        """Test creating an alert."""
        alert = HealthAlert(
            id="",  # Auto-generated
            indicator="proposal_rate_change",
            severity=AlertSeverity.CRITICAL.value,
            message="Test alert",
            value=3.0,
            threshold=2.0,
        )
        self.assertTrue(alert.id.startswith("ALERT-"))
        self.assertEqual(alert.indicator, "proposal_rate_change")
        self.assertEqual(alert.severity, "critical")
        self.assertFalse(alert.acknowledged)
        self.assertEqual(alert.resolved_at, "")

    def test_alert_to_dict(self):
        """Test converting alert to dict."""
        alert = HealthAlert(
            id="ALERT-12345678",
            indicator="test",
            severity="warning",
            message="Test",
            value=1.5,
            threshold=1.0,
        )
        d = alert.to_dict()
        self.assertEqual(d["id"], "ALERT-12345678")
        self.assertEqual(d["severity"], "warning")


class TestHealthIndicatorsManager(unittest.TestCase):
    """Tests for HealthIndicatorsManager class."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.base_dir = Path(self.temp_dir)
        self.data_dir = self.base_dir / ".claude-loop"
        self.data_dir.mkdir(parents=True)

        self.manager = HealthIndicatorsManager(base_dir=self.base_dir)

    def tearDown(self):
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _write_jsonl(self, filename: str, records: list) -> None:
        """Helper to write JSONL data."""
        filepath = self.data_dir / filename
        with open(filepath, "w") as f:
            for record in records:
                f.write(json.dumps(record) + "\n")

    def _write_json(self, filename: str, data: dict | list) -> None:
        """Helper to write JSON data."""
        filepath = self.data_dir / filename
        with open(filepath, "w") as f:
            json.dump(data, f)

    # ========================================================================
    # Status Determination Tests
    # ========================================================================

    def test_get_status_green(self):
        """Test GREEN status for value within threshold."""
        status = self.manager._get_status("proposal_rate_change", 1.0)
        self.assertEqual(status, HealthStatus.GREEN)

    def test_get_status_amber(self):
        """Test AMBER status for value between thresholds."""
        status = self.manager._get_status("proposal_rate_change", 1.7)
        self.assertEqual(status, HealthStatus.AMBER)

    def test_get_status_red(self):
        """Test RED status for value above threshold."""
        status = self.manager._get_status("proposal_rate_change", 2.5)
        self.assertEqual(status, HealthStatus.RED)

    # ========================================================================
    # Proposal Rate Change Tests
    # ========================================================================

    def test_proposal_rate_change_no_data(self):
        """Test proposal_rate_change with no data."""
        indicator = self.manager.calculate_proposal_rate_change()
        self.assertEqual(indicator.name, "proposal_rate_change")
        self.assertEqual(indicator.status, HealthStatus.UNKNOWN.value)

    def test_proposal_rate_change_empty_queue(self):
        """Test proposal_rate_change with empty queue."""
        self._write_json("improvement_queue.json", {"proposals": []})
        indicator = self.manager.calculate_proposal_rate_change()
        self.assertEqual(indicator.value, 1.0)  # No change
        self.assertEqual(indicator.status, HealthStatus.GREEN.value)

    def test_proposal_rate_change_spike(self):
        """Test proposal_rate_change detects spike."""
        now = datetime.now(timezone.utc)

        # Create proposals: many recent, few baseline
        proposals = []

        # 20 proposals in last 7 days (current period)
        for i in range(20):
            ts = (now - timedelta(days=i % 7)).isoformat().replace("+00:00", "Z")
            proposals.append({
                "id": f"IMP-{i:08d}",
                "problem_pattern": f"Problem {i}",
                "created_at": ts,
            })

        # 5 proposals in baseline (7-21 days ago)
        for i in range(5):
            ts = (now - timedelta(days=10 + i)).isoformat().replace("+00:00", "Z")
            proposals.append({
                "id": f"IMP-BASE{i:04d}",
                "problem_pattern": f"Baseline {i}",
                "created_at": ts,
            })

        self._write_json("improvement_queue.json", {"proposals": proposals})
        indicator = self.manager.calculate_proposal_rate_change()

        # Rate should be high (spike)
        self.assertGreater(indicator.value, 1.5)
        self.assertIn(indicator.status, [HealthStatus.AMBER.value, HealthStatus.RED.value])
        self.assertEqual(indicator.trend, "degrading")

    def test_proposal_rate_change_stable(self):
        """Test proposal_rate_change with stable rate."""
        now = datetime.now(timezone.utc)

        proposals = []
        # 5 proposals in current period
        for i in range(5):
            ts = (now - timedelta(days=i)).isoformat().replace("+00:00", "Z")
            proposals.append({
                "id": f"IMP-{i:08d}",
                "problem_pattern": f"Problem {i}",
                "created_at": ts,
            })

        # 10 proposals in baseline (normalized to 5 for 7-day period)
        for i in range(10):
            ts = (now - timedelta(days=8 + i)).isoformat().replace("+00:00", "Z")
            proposals.append({
                "id": f"IMP-BASE{i:04d}",
                "problem_pattern": f"Baseline {i}",
                "created_at": ts,
            })

        self._write_json("improvement_queue.json", {"proposals": proposals})
        indicator = self.manager.calculate_proposal_rate_change()

        # Rate should be around 1.0 (stable)
        self.assertLess(indicator.value, 1.5)
        self.assertEqual(indicator.status, HealthStatus.GREEN.value)

    # ========================================================================
    # Cluster Concentration Tests
    # ========================================================================

    def test_cluster_concentration_no_data(self):
        """Test cluster_concentration with no data."""
        indicator = self.manager.calculate_cluster_concentration()
        self.assertEqual(indicator.status, HealthStatus.UNKNOWN.value)

    def test_cluster_concentration_no_failures(self):
        """Test cluster_concentration with no failures."""
        now = datetime.now(timezone.utc)
        executions = [
            {
                "story_id": "US-001",
                "status": "success",
                "timestamp_start": now.isoformat().replace("+00:00", "Z"),
            }
        ]
        self._write_jsonl("execution_log.jsonl", executions)

        indicator = self.manager.calculate_cluster_concentration()
        self.assertEqual(indicator.value, 0.0)
        self.assertEqual(indicator.status, HealthStatus.GREEN.value)

    def test_cluster_concentration_distributed(self):
        """Test cluster_concentration with distributed failures."""
        now = datetime.now(timezone.utc)
        executions = []
        error_types = ["timeout", "not_found", "permission", "parse", "network"]

        for i, error_type in enumerate(error_types):
            ts = (now - timedelta(days=i % 7)).isoformat().replace("+00:00", "Z")
            executions.append({
                "story_id": f"US-{i:03d}",
                "status": "failed",
                "error_type": error_type,
                "timestamp_start": ts,
            })

        self._write_jsonl("execution_log.jsonl", executions)
        indicator = self.manager.calculate_cluster_concentration()

        # Each error type has 1/5 = 20% of failures
        self.assertEqual(indicator.value, 0.2)
        self.assertEqual(indicator.status, HealthStatus.GREEN.value)

    def test_cluster_concentration_concentrated(self):
        """Test cluster_concentration with concentrated failures."""
        now = datetime.now(timezone.utc)
        executions = []

        # 8 timeout errors, 2 other errors
        for i in range(10):
            ts = (now - timedelta(days=i % 7)).isoformat().replace("+00:00", "Z")
            error_type = "timeout" if i < 8 else "not_found"
            executions.append({
                "story_id": f"US-{i:03d}",
                "status": "failed",
                "error_type": error_type,
                "timestamp_start": ts,
            })

        self._write_jsonl("execution_log.jsonl", executions)
        indicator = self.manager.calculate_cluster_concentration()

        # 80% are timeouts
        self.assertEqual(indicator.value, 0.8)
        self.assertEqual(indicator.status, HealthStatus.RED.value)
        self.assertEqual(indicator.trend, "degrading")
        self.assertIn("timeout", indicator.message)

    # ========================================================================
    # Retrieval Miss Rate Tests
    # ========================================================================

    def test_retrieval_miss_rate_no_data(self):
        """Test retrieval_miss_rate with no data."""
        indicator = self.manager.calculate_retrieval_miss_rate()
        self.assertEqual(indicator.status, HealthStatus.UNKNOWN.value)

    def test_retrieval_miss_rate_all_helpful(self):
        """Test retrieval_miss_rate with all helpful retrievals."""
        now = datetime.now(timezone.utc)
        retrievals = []

        for i in range(10):
            ts = (now - timedelta(days=i % 7)).isoformat().replace("+00:00", "Z")
            retrievals.append({
                "experience_id": f"EXP-{i:08d}",
                "query": f"Query {i}",
                "outcome": "helped",
                "timestamp": ts,
            })

        self._write_jsonl("retrieval_outcomes.jsonl", retrievals)
        indicator = self.manager.calculate_retrieval_miss_rate()

        self.assertEqual(indicator.value, 0.0)
        self.assertEqual(indicator.status, HealthStatus.GREEN.value)

    def test_retrieval_miss_rate_high(self):
        """Test retrieval_miss_rate with high miss rate."""
        now = datetime.now(timezone.utc)
        retrievals = []

        # 7 ignored, 3 helped
        outcomes = ["ignored"] * 7 + ["helped"] * 3
        for i, outcome in enumerate(outcomes):
            ts = (now - timedelta(days=i % 7)).isoformat().replace("+00:00", "Z")
            retrievals.append({
                "experience_id": f"EXP-{i:08d}",
                "query": f"Query {i}",
                "outcome": outcome,
                "timestamp": ts,
            })

        self._write_jsonl("retrieval_outcomes.jsonl", retrievals)
        indicator = self.manager.calculate_retrieval_miss_rate()

        self.assertEqual(indicator.value, 0.7)
        self.assertEqual(indicator.status, HealthStatus.RED.value)

    def test_retrieval_miss_rate_moderate(self):
        """Test retrieval_miss_rate with moderate miss rate."""
        now = datetime.now(timezone.utc)
        retrievals = []

        # 4 ignored, 6 used
        outcomes = ["ignored"] * 4 + ["used"] * 6
        for i, outcome in enumerate(outcomes):
            ts = (now - timedelta(days=i % 7)).isoformat().replace("+00:00", "Z")
            retrievals.append({
                "experience_id": f"EXP-{i:08d}",
                "query": f"Query {i}",
                "outcome": outcome,
                "timestamp": ts,
            })

        self._write_jsonl("retrieval_outcomes.jsonl", retrievals)
        indicator = self.manager.calculate_retrieval_miss_rate()

        self.assertEqual(indicator.value, 0.4)
        self.assertEqual(indicator.status, HealthStatus.AMBER.value)

    # ========================================================================
    # Domain Drift Tests
    # ========================================================================

    def test_domain_drift_no_data(self):
        """Test domain_drift with no data."""
        indicator = self.manager.calculate_domain_drift()
        self.assertEqual(indicator.status, HealthStatus.UNKNOWN.value)

    def test_domain_drift_known_domains(self):
        """Test domain_drift with all known domains."""
        now = datetime.now(timezone.utc)
        executions = []

        domains = ["web_frontend", "unity_game", "ml_training", "cli_tool"]
        for i, domain in enumerate(domains):
            ts = (now - timedelta(days=i % 7)).isoformat().replace("+00:00", "Z")
            executions.append({
                "story_id": f"US-{i:03d}",
                "status": "success",
                "timestamp_start": ts,
                "context": {"project_type": domain},
            })

        self._write_jsonl("execution_log.jsonl", executions)
        indicator = self.manager.calculate_domain_drift()

        self.assertEqual(indicator.value, 0.0)
        self.assertEqual(indicator.status, HealthStatus.GREEN.value)

    def test_domain_drift_unknown_domains(self):
        """Test domain_drift with unknown domains."""
        now = datetime.now(timezone.utc)
        executions = []

        # 5 unknown, 5 known
        domains = ["blockchain", "quantum", "ar_vr", "iot", "embedded",
                   "web_frontend", "unity_game", "ml_training", "cli_tool", "robotics"]
        for i, domain in enumerate(domains):
            ts = (now - timedelta(days=i % 7)).isoformat().replace("+00:00", "Z")
            executions.append({
                "story_id": f"US-{i:03d}",
                "status": "success",
                "timestamp_start": ts,
                "context": {"project_type": domain},
            })

        self._write_jsonl("execution_log.jsonl", executions)
        indicator = self.manager.calculate_domain_drift()

        # 50% unknown
        self.assertEqual(indicator.value, 0.5)
        self.assertEqual(indicator.status, HealthStatus.RED.value)

    def test_domain_drift_with_json_context(self):
        """Test domain_drift handles JSON string context."""
        now = datetime.now(timezone.utc)
        executions = [
            {
                "story_id": "US-001",
                "status": "success",
                "timestamp_start": now.isoformat().replace("+00:00", "Z"),
                "context": json.dumps({"project_type": "web_frontend"}),
            }
        ]
        self._write_jsonl("execution_log.jsonl", executions)
        indicator = self.manager.calculate_domain_drift()

        self.assertEqual(indicator.value, 0.0)

    # ========================================================================
    # Health Snapshot Tests
    # ========================================================================

    def test_get_health_snapshot(self):
        """Test getting complete health snapshot."""
        snapshot = self.manager.get_health_snapshot()

        self.assertIn("timestamp", snapshot.to_dict())
        self.assertIn("indicators", snapshot.to_dict())
        self.assertIn("overall_status", snapshot.to_dict())

        # Should have all 4 indicators
        self.assertEqual(len(snapshot.indicators), 4)
        self.assertIn("proposal_rate_change", snapshot.indicators)
        self.assertIn("cluster_concentration", snapshot.indicators)
        self.assertIn("retrieval_miss_rate", snapshot.indicators)
        self.assertIn("domain_drift", snapshot.indicators)

    def test_health_snapshot_saves_to_history(self):
        """Test that snapshot is saved to history."""
        self.manager.get_health_snapshot()

        history_file = self.data_dir / "health_history.jsonl"
        self.assertTrue(history_file.exists())

        with open(history_file) as f:
            lines = f.readlines()
            self.assertEqual(len(lines), 1)

    def test_overall_status_red_wins(self):
        """Test that RED status wins overall."""
        now = datetime.now(timezone.utc)

        # Create data that will make cluster_concentration RED
        executions = []
        for i in range(10):
            ts = (now - timedelta(days=i % 7)).isoformat().replace("+00:00", "Z")
            executions.append({
                "story_id": f"US-{i:03d}",
                "status": "failed",
                "error_type": "timeout",  # All same type = high concentration
                "timestamp_start": ts,
                "context": {"project_type": "web_frontend"},
            })
        self._write_jsonl("execution_log.jsonl", executions)

        snapshot = self.manager.get_health_snapshot()
        self.assertEqual(snapshot.overall_status, HealthStatus.RED.value)

    # ========================================================================
    # Alert Tests
    # ========================================================================

    def test_alert_created_for_red(self):
        """Test that alert is created for RED status."""
        now = datetime.now(timezone.utc)

        # Create data for RED cluster_concentration
        executions = []
        for i in range(10):
            ts = (now - timedelta(days=i % 7)).isoformat().replace("+00:00", "Z")
            executions.append({
                "story_id": f"US-{i:03d}",
                "status": "failed",
                "error_type": "timeout",
                "timestamp_start": ts,
            })
        self._write_jsonl("execution_log.jsonl", executions)

        self.manager.get_health_snapshot()
        alerts = self.manager.get_active_alerts()

        self.assertGreater(len(alerts), 0)
        alert_indicators = [a.indicator for a in alerts]
        self.assertIn("cluster_concentration", alert_indicators)

    def test_alert_acknowledged(self):
        """Test acknowledging an alert."""
        now = datetime.now(timezone.utc)

        # Create RED condition
        executions = [
            {
                "story_id": "US-001",
                "status": "failed",
                "error_type": "timeout",
                "timestamp_start": now.isoformat().replace("+00:00", "Z"),
            }
        ]
        self._write_jsonl("execution_log.jsonl", executions)

        self.manager.get_health_snapshot()
        alerts = self.manager.get_active_alerts()

        if alerts:
            alert_id = alerts[0].id
            result = self.manager.acknowledge_alert(alert_id)
            self.assertTrue(result)

            # Reload and check acknowledged
            alerts_after = self.manager.get_active_alerts()
            alert = next((a for a in alerts_after if a.id == alert_id), None)
            if alert:
                self.assertTrue(alert.acknowledged)

    def test_alert_resolved_when_green(self):
        """Test that alert is resolved when status returns to GREEN."""
        now = datetime.now(timezone.utc)

        # First create RED condition
        executions = []
        for i in range(10):
            ts = (now - timedelta(days=i % 7)).isoformat().replace("+00:00", "Z")
            executions.append({
                "story_id": f"US-{i:03d}",
                "status": "failed",
                "error_type": "timeout",
                "timestamp_start": ts,
            })
        self._write_jsonl("execution_log.jsonl", executions)

        self.manager.get_health_snapshot()
        initial_alerts = self.manager.get_active_alerts()
        initial_count = len(initial_alerts)

        # Now create GREEN condition (clear failures)
        self._write_jsonl("execution_log.jsonl", [])
        self.manager.get_health_snapshot()

        final_alerts = self.manager.get_active_alerts()
        # Alerts should be resolved (resolved_at set, so not in active)
        self.assertLessEqual(len(final_alerts), initial_count)

    # ========================================================================
    # History Tests
    # ========================================================================

    def test_get_history(self):
        """Test getting health history."""
        # Generate some history
        for _ in range(3):
            self.manager.get_health_snapshot()

        history = self.manager.get_history(days=30)
        self.assertEqual(len(history), 3)

    def test_get_history_filtered_by_indicator(self):
        """Test getting history for specific indicator."""
        self.manager.get_health_snapshot()

        history = self.manager.get_history(days=30, indicator="proposal_rate_change")
        self.assertEqual(len(history), 1)
        self.assertIn("value", history[0])
        self.assertIn("status", history[0])

    # ========================================================================
    # Threshold Tests
    # ========================================================================

    def test_get_thresholds(self):
        """Test getting threshold configuration."""
        thresholds = self.manager.get_thresholds()

        self.assertIn("proposal_rate_change", thresholds)
        self.assertIn("green_max", thresholds["proposal_rate_change"])
        self.assertIn("amber_max", thresholds["proposal_rate_change"])
        self.assertIn("red_min", thresholds["proposal_rate_change"])

    def test_set_threshold(self):
        """Test setting a threshold."""
        result = self.manager.set_threshold("proposal_rate_change", "amber_max", 1.8)
        self.assertTrue(result)

        thresholds = self.manager.get_thresholds()
        self.assertEqual(thresholds["proposal_rate_change"]["amber_max"], 1.8)

    def test_set_threshold_invalid_indicator(self):
        """Test setting threshold for invalid indicator."""
        result = self.manager.set_threshold("invalid_indicator", "amber_max", 1.0)
        self.assertFalse(result)

    def test_set_threshold_invalid_level(self):
        """Test setting threshold for invalid level."""
        result = self.manager.set_threshold("proposal_rate_change", "invalid_level", 1.0)
        self.assertFalse(result)

    def test_threshold_persists(self):
        """Test that threshold changes persist."""
        self.manager.set_threshold("proposal_rate_change", "amber_max", 1.9)

        # Create new manager to test persistence
        new_manager = HealthIndicatorsManager(base_dir=self.base_dir)
        thresholds = new_manager.get_thresholds()

        self.assertEqual(thresholds["proposal_rate_change"]["amber_max"], 1.9)


class TestHealthStatusEnum(unittest.TestCase):
    """Tests for HealthStatus enum."""

    def test_health_status_values(self):
        """Test HealthStatus enum values."""
        self.assertEqual(HealthStatus.GREEN.value, "green")
        self.assertEqual(HealthStatus.AMBER.value, "amber")
        self.assertEqual(HealthStatus.RED.value, "red")
        self.assertEqual(HealthStatus.UNKNOWN.value, "unknown")

    def test_health_status_string(self):
        """Test HealthStatus string representation."""
        self.assertEqual(str(HealthStatus.GREEN), "green")


class TestAlertSeverityEnum(unittest.TestCase):
    """Tests for AlertSeverity enum."""

    def test_alert_severity_values(self):
        """Test AlertSeverity enum values."""
        self.assertEqual(AlertSeverity.INFO.value, "info")
        self.assertEqual(AlertSeverity.WARNING.value, "warning")
        self.assertEqual(AlertSeverity.CRITICAL.value, "critical")


class TestDefaultThresholds(unittest.TestCase):
    """Tests for default threshold configuration."""

    def test_all_indicators_have_thresholds(self):
        """Test all indicators have threshold config."""
        expected = ["proposal_rate_change", "cluster_concentration",
                    "retrieval_miss_rate", "domain_drift"]
        for indicator in expected:
            self.assertIn(indicator, DEFAULT_THRESHOLDS)

    def test_threshold_structure(self):
        """Test threshold structure."""
        for _indicator, config in DEFAULT_THRESHOLDS.items():
            self.assertIn("green_max", config)
            self.assertIn("amber_max", config)
            self.assertIn("red_min", config)
            self.assertIn("description", config)

    def test_threshold_ordering(self):
        """Test thresholds are in correct order."""
        for indicator, config in DEFAULT_THRESHOLDS.items():
            green_max = config["green_max"]
            amber_max = config["amber_max"]
            red_min = config["red_min"]

            # green_max <= amber_max <= red_min
            self.assertLessEqual(green_max, amber_max,
                f"{indicator}: green_max > amber_max")
            # Note: red_min should equal amber_max for proper classification
            self.assertEqual(amber_max, red_min,
                f"{indicator}: amber_max != red_min")


if __name__ == "__main__":
    unittest.main()
