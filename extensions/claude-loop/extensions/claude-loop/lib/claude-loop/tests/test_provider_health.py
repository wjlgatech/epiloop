#!/usr/bin/env python3
"""
Unit tests for provider_health.py
"""

import sqlite3
import tempfile
import unittest
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from lib.provider_health import (
    HealthMonitor,
    ProviderStatus,
    HealthCheckResult,
    HealthAlert
)
from lib.llm_config import ProviderConfig, LLMConfigManager


class TestHealthMonitor(unittest.TestCase):
    """Test HealthMonitor class"""

    def setUp(self):
        """Set up test fixtures"""
        # Create temporary database
        self.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        self.temp_db.close()

        # Mock config manager
        self.mock_config_manager = Mock(spec=LLMConfigManager)

        # Create health monitor
        self.monitor = HealthMonitor(
            config_manager=self.mock_config_manager,
            db_path=self.temp_db.name,
            check_interval=1,
            failover_threshold=3
        )

    def tearDown(self):
        """Clean up test fixtures"""
        # Stop monitoring if running
        if self.monitor._monitoring:
            self.monitor.stop_monitoring()

        # Remove temporary database
        Path(self.temp_db.name).unlink(missing_ok=True)

    def test_init_creates_database(self):
        """Test that initialization creates database tables"""
        with sqlite3.connect(self.temp_db.name) as conn:
            # Check health_checks table exists
            result = conn.execute("""
                SELECT name FROM sqlite_master
                WHERE type='table' AND name='health_checks'
            """).fetchone()
            self.assertIsNotNone(result)

            # Check health_alerts table exists
            result = conn.execute("""
                SELECT name FROM sqlite_master
                WHERE type='table' AND name='health_alerts'
            """).fetchone()
            self.assertIsNotNone(result)

    def test_check_provider_health_disabled_provider(self):
        """Test health check with disabled provider"""
        config = ProviderConfig(
            name="openai",
            enabled=False,
            api_key="test-key",
            default_model="gpt-4o",
            base_url="https://api.openai.com/v1"
        )
        self.mock_config_manager.get_provider.return_value = config

        result = self.monitor.check_provider_health("openai")

        self.assertEqual(result.provider, "openai")
        self.assertFalse(result.success)
        self.assertEqual(result.error_message, "Provider is disabled")

    def test_check_provider_health_config_not_found(self):
        """Test health check when config is not found"""
        self.mock_config_manager.get_provider.return_value = None

        result = self.monitor.check_provider_health("openai")

        self.assertEqual(result.provider, "openai")
        self.assertFalse(result.success)
        self.assertEqual(result.error_message, "Provider config not found")

    @patch('lib.providers.openai_provider.OpenAIProvider')
    def test_check_provider_health_success(self, mock_provider_class):
        """Test successful health check"""
        config = ProviderConfig(
            name="openai",
            enabled=True,
            api_key="test-key",
            default_model="gpt-4o",
            base_url="https://api.openai.com/v1"
        )
        self.mock_config_manager.get_provider.return_value = config

        # Mock provider instance
        mock_provider = MagicMock()
        mock_provider.test_connection.return_value = (True, None)
        mock_provider_class.return_value = mock_provider

        result = self.monitor.check_provider_health("openai")

        self.assertEqual(result.provider, "openai")
        self.assertTrue(result.success)
        self.assertIsNone(result.error_message)
        self.assertGreater(result.latency_ms, 0)

    @patch('lib.providers.openai_provider.OpenAIProvider')
    def test_check_provider_health_failure(self, mock_provider_class):
        """Test failed health check"""
        config = ProviderConfig(
            name="openai",
            enabled=True,
            api_key="test-key",
            default_model="gpt-4o",
            base_url="https://api.openai.com/v1"
        )
        self.mock_config_manager.get_provider.return_value = config

        # Mock provider instance
        mock_provider = MagicMock()
        mock_provider.test_connection.return_value = (False, "Connection error")
        mock_provider_class.return_value = mock_provider

        result = self.monitor.check_provider_health("openai")

        self.assertEqual(result.provider, "openai")
        self.assertFalse(result.success)
        self.assertEqual(result.error_message, "Connection error")

    def test_record_health_check(self):
        """Test recording health check result"""
        result = HealthCheckResult(
            provider="openai",
            timestamp=datetime.now(timezone.utc).isoformat(),
            latency_ms=123.45,
            success=True
        )

        self.monitor.record_health_check(result)

        # Verify record was stored
        with sqlite3.connect(self.temp_db.name) as conn:
            row = conn.execute("""
                SELECT provider, latency_ms, success
                FROM health_checks
                WHERE provider = ?
            """, ("openai",)).fetchone()

        self.assertIsNotNone(row)
        self.assertEqual(row[0], "openai")
        self.assertAlmostEqual(row[1], 123.45, places=2)
        self.assertEqual(row[2], 1)

    def test_get_provider_health_no_data(self):
        """Test getting health with no check data"""
        health = self.monitor.get_provider_health("openai", window_hours=24)

        self.assertEqual(health.provider, "openai")
        self.assertEqual(health.status, ProviderStatus.UNKNOWN)
        self.assertEqual(health.total_checks, 0)
        self.assertEqual(health.success_rate, 0.0)
        self.assertEqual(health.consecutive_failures, 0)

    def test_get_provider_health_with_data(self):
        """Test getting health with check data"""
        # Record some successful checks
        timestamp = datetime.now(timezone.utc)
        for i in range(5):
            result = HealthCheckResult(
                provider="openai",
                timestamp=(timestamp - timedelta(minutes=i)).isoformat(),
                latency_ms=100.0 + i * 10,
                success=True
            )
            self.monitor.record_health_check(result)

        health = self.monitor.get_provider_health("openai", window_hours=24)

        self.assertEqual(health.provider, "openai")
        self.assertEqual(health.status, ProviderStatus.HEALTHY)
        self.assertEqual(health.total_checks, 5)
        self.assertEqual(health.success_rate, 1.0)
        self.assertEqual(health.consecutive_failures, 0)
        self.assertGreater(health.latency_avg_ms, 0)

    def test_get_provider_health_consecutive_failures(self):
        """Test consecutive failure tracking"""
        # Record some failures
        timestamp = datetime.now(timezone.utc)
        for i in range(4):
            result = HealthCheckResult(
                provider="openai",
                timestamp=(timestamp - timedelta(minutes=i)).isoformat(),
                latency_ms=100.0,
                success=False,
                error_message="Connection timeout"
            )
            self.monitor.record_health_check(result)

        health = self.monitor.get_provider_health("openai", window_hours=24)

        self.assertEqual(health.provider, "openai")
        self.assertEqual(health.status, ProviderStatus.UNHEALTHY)
        self.assertEqual(health.consecutive_failures, 4)
        self.assertIsNotNone(health.last_error)

    def test_get_provider_health_degraded(self):
        """Test degraded status with low success rate"""
        # Record mixed results (70% success rate)
        timestamp = datetime.now(timezone.utc)
        for i in range(10):
            result = HealthCheckResult(
                provider="openai",
                timestamp=(timestamp - timedelta(minutes=i)).isoformat(),
                latency_ms=100.0,
                success=(i % 10) < 7  # 7 successes, 3 failures
            )
            self.monitor.record_health_check(result)

        health = self.monitor.get_provider_health("openai", window_hours=24)

        self.assertEqual(health.provider, "openai")
        self.assertEqual(health.status, ProviderStatus.DEGRADED)
        self.assertLess(health.success_rate, 0.8)

    def test_check_and_handle_failover_triggers(self):
        """Test that failover triggers after threshold failures"""
        # Record failures to trigger failover
        timestamp = datetime.now(timezone.utc)
        for i in range(3):
            result = HealthCheckResult(
                provider="openai",
                timestamp=(timestamp - timedelta(minutes=i)).isoformat(),
                latency_ms=100.0,
                success=False
            )
            self.monitor.record_health_check(result)

        # Mock provider as enabled
        config = ProviderConfig(
            name="openai",
            enabled=True,
            api_key="test-key",
            default_model="gpt-4o",
            base_url="https://api.openai.com/v1"
        )
        self.mock_config_manager.get_provider.return_value = config

        # Check and handle failover
        self.monitor.check_and_handle_failover("openai")

        # Verify failover state
        self.assertTrue(self.monitor._failover_state.get("openai", False))

        # Verify alert was created
        alerts = self.monitor.get_alerts(provider="openai")
        self.assertEqual(len(alerts), 1)
        self.assertEqual(alerts[0].alert_type, "failover")

    def test_check_and_handle_recovery(self):
        """Test recovery detection and restoration"""
        # Set initial failover state
        self.monitor._failover_state["openai"] = True

        # Record successful checks
        timestamp = datetime.now(timezone.utc)
        for i in range(5):
            result = HealthCheckResult(
                provider="openai",
                timestamp=(timestamp - timedelta(minutes=i)).isoformat(),
                latency_ms=100.0,
                success=True
            )
            self.monitor.record_health_check(result)

        # Mock provider as enabled
        config = ProviderConfig(
            name="openai",
            enabled=True,
            api_key="test-key",
            default_model="gpt-4o",
            base_url="https://api.openai.com/v1"
        )
        self.mock_config_manager.get_provider.return_value = config

        # Check and handle recovery
        self.monitor.check_and_handle_failover("openai")

        # Verify recovery
        self.assertFalse(self.monitor._failover_state.get("openai", False))

        # Verify alert was created
        alerts = self.monitor.get_alerts(provider="openai", acknowledged=False)
        recovery_alerts = [a for a in alerts if a.alert_type == "recovery"]
        self.assertGreater(len(recovery_alerts), 0)

    def test_get_alerts_filtering(self):
        """Test alert filtering"""
        # Create some alerts
        alert1 = HealthAlert(
            alert_id="alert-1",
            provider="openai",
            alert_type="failover",
            message="Test alert 1",
            timestamp=datetime.now(timezone.utc).isoformat(),
            acknowledged=False
        )
        alert2 = HealthAlert(
            alert_id="alert-2",
            provider="gemini",
            alert_type="recovery",
            message="Test alert 2",
            timestamp=datetime.now(timezone.utc).isoformat(),
            acknowledged=True
        )

        self.monitor._record_alert(alert1)
        self.monitor._record_alert(alert2)

        # Test filtering by acknowledged
        unacknowledged = self.monitor.get_alerts(acknowledged=False)
        self.assertEqual(len(unacknowledged), 1)
        self.assertEqual(unacknowledged[0].alert_id, "alert-1")

        # Test filtering by provider
        openai_alerts = self.monitor.get_alerts(provider="openai")
        self.assertEqual(len(openai_alerts), 1)
        self.assertEqual(openai_alerts[0].provider, "openai")

    def test_acknowledge_alert(self):
        """Test acknowledging alerts"""
        # Create alert
        alert = HealthAlert(
            alert_id="alert-1",
            provider="openai",
            alert_type="failover",
            message="Test alert",
            timestamp=datetime.now(timezone.utc).isoformat(),
            acknowledged=False
        )
        self.monitor._record_alert(alert)

        # Acknowledge it
        self.monitor.acknowledge_alert("alert-1")

        # Verify it's acknowledged
        alerts = self.monitor.get_alerts(acknowledged=True)
        self.assertEqual(len(alerts), 1)
        self.assertTrue(alerts[0].acknowledged)

    def test_get_health_history(self):
        """Test getting health check history"""
        # Record some checks
        timestamp = datetime.now(timezone.utc)
        for i in range(5):
            result = HealthCheckResult(
                provider="openai",
                timestamp=(timestamp - timedelta(minutes=i)).isoformat(),
                latency_ms=100.0 + i * 10,
                success=True
            )
            self.monitor.record_health_check(result)

        history = self.monitor.get_health_history("openai", hours=24)

        self.assertEqual(len(history), 5)
        for check in history:
            self.assertEqual(check.provider, "openai")
            self.assertTrue(check.success)

    def test_get_all_provider_health(self):
        """Test getting health for all providers"""
        # Record checks for multiple providers
        timestamp = datetime.now(timezone.utc)
        for provider in ["openai", "gemini", "deepseek"]:
            result = HealthCheckResult(
                provider=provider,
                timestamp=timestamp.isoformat(),
                latency_ms=100.0,
                success=True
            )
            self.monitor.record_health_check(result)

        health_map = self.monitor.get_all_provider_health(window_hours=24)

        self.assertIn("openai", health_map)
        self.assertIn("gemini", health_map)
        self.assertIn("deepseek", health_map)

    def test_alert_callback(self):
        """Test alert callback notification"""
        callback_called = []

        def test_callback(alert: HealthAlert):
            callback_called.append(alert)

        self.monitor.add_alert_callback(test_callback)

        # Create alert
        alert = HealthAlert(
            alert_id="alert-1",
            provider="openai",
            alert_type="failover",
            message="Test alert",
            timestamp=datetime.now(timezone.utc).isoformat()
        )

        self.monitor._record_alert(alert)
        self.monitor._notify_alert(alert)

        # Verify callback was called
        self.assertEqual(len(callback_called), 1)
        self.assertEqual(callback_called[0].alert_id, "alert-1")

    @patch('urllib.request.urlopen')
    def test_send_webhook_alert(self, mock_urlopen):
        """Test sending webhook alert"""
        mock_response = MagicMock()
        mock_response.read.return_value = b'{"status": "ok"}'
        mock_urlopen.return_value.__enter__.return_value = mock_response

        alert = HealthAlert(
            alert_id="alert-1",
            provider="openai",
            alert_type="failover",
            message="Test alert",
            timestamp=datetime.now(timezone.utc).isoformat()
        )

        self.monitor.send_webhook_alert("https://example.com/webhook", alert)

        # Verify webhook was called
        self.assertTrue(mock_urlopen.called)

    def test_start_stop_monitoring(self):
        """Test starting and stopping monitoring"""
        # Mock provider configs
        config = ProviderConfig(
            name="openai",
            enabled=True,
            api_key="test-key",
            default_model="gpt-4o",
            base_url="https://api.openai.com/v1"
        )
        self.mock_config_manager.get_provider.return_value = config

        # Start monitoring
        self.monitor.start_monitoring()
        self.assertTrue(self.monitor._monitoring)
        self.assertIsNotNone(self.monitor._monitor_thread)

        # Stop monitoring
        self.monitor.stop_monitoring()
        self.assertFalse(self.monitor._monitoring)

    def test_latency_percentile_calculation(self):
        """Test p95 latency calculation"""
        # Record checks with varying latencies
        timestamp = datetime.now(timezone.utc)
        for i in range(100):
            result = HealthCheckResult(
                provider="openai",
                timestamp=(timestamp - timedelta(seconds=i)).isoformat(),
                latency_ms=float(i),
                success=True
            )
            self.monitor.record_health_check(result)

        health = self.monitor.get_provider_health("openai", window_hours=24)

        # p95 should be around 95
        self.assertGreater(health.latency_p95_ms, 90)
        self.assertLess(health.latency_p95_ms, 100)


if __name__ == '__main__':
    unittest.main()
