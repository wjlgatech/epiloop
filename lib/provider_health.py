#!/usr/bin/env python3
"""
Provider Health Monitor

Monitors LLM provider availability, performance, and health.
Tracks latency, success rates, and errors per provider.
Implements automatic failover when providers become unhealthy.
Supports periodic health checks and recovery detection.
"""

import json
import sqlite3
import threading
import time
import urllib.request
from dataclasses import dataclass, asdict
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional, Dict, List, Callable
from enum import Enum

from lib.llm_config import LLMConfigManager
from lib.llm_provider import LLMProvider


class ProviderStatus(str, Enum):
    """Provider health status"""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


@dataclass
class HealthCheckResult:
    """Result of a single health check"""
    provider: str
    timestamp: str
    latency_ms: float
    success: bool
    error_message: Optional[str] = None
    status_code: Optional[int] = None


@dataclass
class ProviderHealth:
    """Health metrics for a provider"""
    provider: str
    status: ProviderStatus
    latency_avg_ms: float
    latency_p95_ms: float
    success_rate: float
    total_checks: int
    consecutive_failures: int
    last_error: Optional[str]
    last_check: str
    last_success: Optional[str]
    is_enabled: bool
    failover_count: int


@dataclass
class HealthAlert:
    """Alert for provider health issues"""
    alert_id: str
    provider: str
    alert_type: str  # unhealthy, degraded, failover, recovery
    message: str
    timestamp: str
    acknowledged: bool = False


class HealthMonitor:
    """
    Provider health monitoring and failover management.

    Tracks provider availability and performance:
    - Periodic health checks
    - Latency and success rate tracking
    - Automatic failover on consecutive failures
    - Recovery detection and restoration
    """

    def __init__(self, config_manager: Optional[LLMConfigManager] = None,
                 db_path: Optional[str] = None,
                 check_interval: int = 300,
                 failover_threshold: int = 3):
        """
        Initialize health monitor.

        Args:
            config_manager: LLM configuration manager
            db_path: Path to health database (default: ~/.claude-loop/health.db)
            check_interval: Health check interval in seconds (default: 300 = 5 minutes)
            failover_threshold: Consecutive failures before failover (default: 3)
        """
        self.config_manager = config_manager or LLMConfigManager()

        # Database setup
        if db_path is None:
            db_path = str(Path.home() / ".claude-loop" / "health.db")
        self.db_path = db_path
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

        # Configuration
        self.check_interval = check_interval
        self.failover_threshold = failover_threshold

        # Monitoring state
        self._monitoring = False
        self._monitor_thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()

        # Failover state (provider -> is_disabled)
        self._failover_state: Dict[str, bool] = {}

        # Alert callbacks
        self._alert_callbacks: List[Callable[[HealthAlert], None]] = []

    def _init_db(self):
        """Initialize health database tables"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS health_checks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    provider TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    latency_ms REAL NOT NULL,
                    success INTEGER NOT NULL,
                    error_message TEXT,
                    status_code INTEGER
                )
            """)

            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_health_provider_time
                ON health_checks(provider, timestamp DESC)
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS health_alerts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    alert_id TEXT UNIQUE NOT NULL,
                    provider TEXT NOT NULL,
                    alert_type TEXT NOT NULL,
                    message TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    acknowledged INTEGER DEFAULT 0
                )
            """)

            conn.commit()

    def check_provider_health(self, provider: str) -> HealthCheckResult:
        """
        Perform a health check on a provider.

        Args:
            provider: Provider name to check

        Returns:
            HealthCheckResult with check outcome
        """
        timestamp = datetime.now(timezone.utc).isoformat()

        # Get provider config
        try:
            provider_config = self.config_manager.get_provider(provider)
            if provider_config is None:
                return HealthCheckResult(
                    provider=provider,
                    timestamp=timestamp,
                    latency_ms=0,
                    success=False,
                    error_message="Provider config not found"
                )
            if not provider_config.enabled:
                return HealthCheckResult(
                    provider=provider,
                    timestamp=timestamp,
                    latency_ms=0,
                    success=False,
                    error_message="Provider is disabled"
                )
        except Exception as e:
            return HealthCheckResult(
                provider=provider,
                timestamp=timestamp,
                latency_ms=0,
                success=False,
                error_message=f"Config error: {str(e)}"
            )

        # Perform lightweight health check (simple API call)
        start_time = time.time()
        try:
            # Use a minimal request to check availability
            from lib.providers.openai_provider import OpenAIProvider
            from lib.providers.gemini_provider import GeminiProvider
            from lib.providers.deepseek_provider import DeepSeekProvider

            # Create provider instance
            provider_instance: Optional[LLMProvider] = None
            if provider == "openai":
                provider_instance = OpenAIProvider(provider_config)
            elif provider == "gemini":
                provider_instance = GeminiProvider(provider_config)
            elif provider == "deepseek":
                provider_instance = DeepSeekProvider(provider_config)
            else:
                raise ValueError(f"Unsupported provider: {provider}")

            # Test connection
            success, error = provider_instance.test_connection()
            latency_ms = (time.time() - start_time) * 1000

            if success:
                return HealthCheckResult(
                    provider=provider,
                    timestamp=timestamp,
                    latency_ms=latency_ms,
                    success=True
                )
            else:
                return HealthCheckResult(
                    provider=provider,
                    timestamp=timestamp,
                    latency_ms=latency_ms,
                    success=False,
                    error_message=error
                )

        except Exception as e:
            latency_ms = (time.time() - start_time) * 1000
            return HealthCheckResult(
                provider=provider,
                timestamp=timestamp,
                latency_ms=latency_ms,
                success=False,
                error_message=str(e)
            )

    def record_health_check(self, result: HealthCheckResult):
        """Record health check result to database"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO health_checks
                (provider, timestamp, latency_ms, success, error_message, status_code)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                result.provider,
                result.timestamp,
                result.latency_ms,
                1 if result.success else 0,
                result.error_message,
                result.status_code
            ))
            conn.commit()

    def get_provider_health(self, provider: str, window_hours: int = 24) -> ProviderHealth:
        """
        Get health metrics for a provider.

        Args:
            provider: Provider name
            window_hours: Time window for metrics (default: 24 hours)

        Returns:
            ProviderHealth with current metrics
        """
        cutoff_time = (datetime.now(timezone.utc) - timedelta(hours=window_hours)).isoformat()

        with sqlite3.connect(self.db_path) as conn:
            # Get check statistics
            stats = conn.execute("""
                SELECT
                    COUNT(*) as total_checks,
                    AVG(latency_ms) as avg_latency,
                    SUM(CASE WHEN success = 1 THEN 1 ELSE 0 END) as successes
                FROM health_checks
                WHERE provider = ? AND timestamp >= ?
            """, (provider, cutoff_time)).fetchone()

            # Get latency percentiles
            latencies = conn.execute("""
                SELECT latency_ms FROM health_checks
                WHERE provider = ? AND timestamp >= ? AND success = 1
                ORDER BY latency_ms
            """, (provider, cutoff_time)).fetchall()

            # Get consecutive failures
            recent_checks = conn.execute("""
                SELECT success FROM health_checks
                WHERE provider = ?
                ORDER BY timestamp DESC
                LIMIT 10
            """, (provider,)).fetchall()

            # Get last error
            last_error_row = conn.execute("""
                SELECT error_message FROM health_checks
                WHERE provider = ? AND success = 0
                ORDER BY timestamp DESC
                LIMIT 1
            """, (provider,)).fetchone()

            # Get last check and last success
            last_check_row = conn.execute("""
                SELECT timestamp FROM health_checks
                WHERE provider = ?
                ORDER BY timestamp DESC
                LIMIT 1
            """, (provider,)).fetchone()

            last_success_row = conn.execute("""
                SELECT timestamp FROM health_checks
                WHERE provider = ? AND success = 1
                ORDER BY timestamp DESC
                LIMIT 1
            """, (provider,)).fetchone()

        # Calculate metrics
        total_checks = stats[0] if stats else 0
        avg_latency = stats[1] if stats and stats[1] else 0.0
        successes = stats[2] if stats else 0
        success_rate = (successes / total_checks) if total_checks > 0 else 0.0

        # Calculate p95 latency
        p95_latency = 0.0
        if latencies:
            p95_index = int(len(latencies) * 0.95)
            p95_latency = latencies[min(p95_index, len(latencies) - 1)][0]

        # Count consecutive failures
        consecutive_failures = 0
        for check in recent_checks:
            if check[0] == 0:  # failure
                consecutive_failures += 1
            else:
                break

        # Determine status
        if total_checks == 0:
            status = ProviderStatus.UNKNOWN
        elif consecutive_failures >= self.failover_threshold:
            status = ProviderStatus.UNHEALTHY
        elif success_rate < 0.8:
            status = ProviderStatus.DEGRADED
        else:
            status = ProviderStatus.HEALTHY

        # Check if provider is enabled
        is_enabled = False
        try:
            provider_config = self.config_manager.get_provider(provider)
            if provider_config is not None:
                is_enabled = provider_config.enabled and not self._failover_state.get(provider, False)
        except (AttributeError, KeyError, TypeError) as e:
            # SAFETY: Catch specific exceptions instead of bare except
            # If provider config retrieval fails, use default is_enabled=True
            pass

        # Get failover count
        failover_count = sum(1 for v in self._failover_state.values() if v)

        return ProviderHealth(
            provider=provider,
            status=status,
            latency_avg_ms=avg_latency,
            latency_p95_ms=p95_latency,
            success_rate=success_rate,
            total_checks=total_checks,
            consecutive_failures=consecutive_failures,
            last_error=last_error_row[0] if last_error_row else None,
            last_check=last_check_row[0] if last_check_row else datetime.now(timezone.utc).isoformat(),
            last_success=last_success_row[0] if last_success_row else None,
            is_enabled=is_enabled,
            failover_count=failover_count
        )

    def check_and_handle_failover(self, provider: str):
        """
        Check provider health and handle failover if needed.

        Automatically disables provider if consecutive failures exceed threshold.
        Sends alerts when failover occurs.
        """
        health = self.get_provider_health(provider, window_hours=1)

        # Check if failover needed
        if health.consecutive_failures >= self.failover_threshold and health.is_enabled:
            with self._lock:
                self._failover_state[provider] = True

            # Create alert
            alert = HealthAlert(
                alert_id=f"{provider}-failover-{int(time.time())}",
                provider=provider,
                alert_type="failover",
                message=f"Provider {provider} disabled after {health.consecutive_failures} consecutive failures",
                timestamp=datetime.now(timezone.utc).isoformat()
            )
            self._record_alert(alert)
            self._notify_alert(alert)

        # Check for recovery
        elif health.status == ProviderStatus.HEALTHY and not health.is_enabled:
            if self._failover_state.get(provider, False):
                with self._lock:
                    self._failover_state[provider] = False

                # Create recovery alert
                alert = HealthAlert(
                    alert_id=f"{provider}-recovery-{int(time.time())}",
                    provider=provider,
                    alert_type="recovery",
                    message=f"Provider {provider} recovered and re-enabled",
                    timestamp=datetime.now(timezone.utc).isoformat()
                )
                self._record_alert(alert)
                self._notify_alert(alert)

    def _record_alert(self, alert: HealthAlert):
        """Record alert to database"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO health_alerts
                (alert_id, provider, alert_type, message, timestamp, acknowledged)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                alert.alert_id,
                alert.provider,
                alert.alert_type,
                alert.message,
                alert.timestamp,
                1 if alert.acknowledged else 0
            ))
            conn.commit()

    def _notify_alert(self, alert: HealthAlert):
        """Notify alert callbacks"""
        for callback in self._alert_callbacks:
            try:
                callback(alert)
            except Exception as e:
                print(f"Alert callback error: {e}")

    def add_alert_callback(self, callback: Callable[[HealthAlert], None]):
        """Add an alert notification callback"""
        self._alert_callbacks.append(callback)

    def send_webhook_alert(self, webhook_url: str, alert: HealthAlert):
        """
        Send alert to webhook URL.

        Args:
            webhook_url: Webhook endpoint URL
            alert: Alert to send
        """
        try:
            payload = json.dumps(asdict(alert)).encode('utf-8')
            req = urllib.request.Request(
                webhook_url,
                data=payload,
                headers={'Content-Type': 'application/json'},
                method='POST'
            )
            with urllib.request.urlopen(req, timeout=10) as response:
                response.read()
        except Exception as e:
            print(f"Webhook alert failed: {e}")

    def start_monitoring(self):
        """Start periodic health monitoring in background thread"""
        if self._monitoring:
            return

        self._monitoring = True
        self._monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._monitor_thread.start()

    def stop_monitoring(self):
        """Stop periodic health monitoring"""
        self._monitoring = False
        if self._monitor_thread:
            self._monitor_thread.join(timeout=5)

    def _monitor_loop(self):
        """Background monitoring loop"""
        while self._monitoring:
            try:
                # Check all configured providers
                for provider_name in ["openai", "gemini", "deepseek"]:
                    try:
                        provider_config = self.config_manager.get_provider(provider_name)
                        if provider_config is None:
                            continue
                        if provider_config.enabled:
                            result = self.check_provider_health(provider_name)
                            self.record_health_check(result)
                            self.check_and_handle_failover(provider_name)
                    except Exception as e:
                        print(f"Health check error for {provider_name}: {e}")

                # Sleep until next check
                time.sleep(self.check_interval)

            except Exception as e:
                print(f"Monitor loop error: {e}")
                time.sleep(60)  # Wait a minute before retrying

    def get_all_provider_health(self, window_hours: int = 24) -> Dict[str, ProviderHealth]:
        """Get health metrics for all providers"""
        health_map = {}
        for provider in ["openai", "gemini", "deepseek"]:
            try:
                health_map[provider] = self.get_provider_health(provider, window_hours)
            except Exception as e:
                print(f"Error getting health for {provider}: {e}")
        return health_map

    def get_alerts(self, acknowledged: Optional[bool] = None,
                   provider: Optional[str] = None) -> List[HealthAlert]:
        """
        Get health alerts.

        Args:
            acknowledged: Filter by acknowledged status (None = all)
            provider: Filter by provider (None = all)

        Returns:
            List of matching alerts
        """
        query = "SELECT alert_id, provider, alert_type, message, timestamp, acknowledged FROM health_alerts WHERE 1=1"
        params = []

        if acknowledged is not None:
            query += " AND acknowledged = ?"
            params.append(1 if acknowledged else 0)

        if provider is not None:
            query += " AND provider = ?"
            params.append(provider)

        query += " ORDER BY timestamp DESC"

        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(query, params).fetchall()

        return [
            HealthAlert(
                alert_id=row[0],
                provider=row[1],
                alert_type=row[2],
                message=row[3],
                timestamp=row[4],
                acknowledged=bool(row[5])
            )
            for row in rows
        ]

    def acknowledge_alert(self, alert_id: str):
        """Acknowledge an alert"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                UPDATE health_alerts
                SET acknowledged = 1
                WHERE alert_id = ?
            """, (alert_id,))
            conn.commit()

    def get_health_history(self, provider: str, hours: int = 24) -> List[HealthCheckResult]:
        """
        Get health check history for a provider.

        Args:
            provider: Provider name
            hours: Hours of history to retrieve

        Returns:
            List of health check results
        """
        cutoff_time = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()

        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute("""
                SELECT provider, timestamp, latency_ms, success, error_message, status_code
                FROM health_checks
                WHERE provider = ? AND timestamp >= ?
                ORDER BY timestamp DESC
            """, (provider, cutoff_time)).fetchall()

        return [
            HealthCheckResult(
                provider=row[0],
                timestamp=row[1],
                latency_ms=row[2],
                success=bool(row[3]),
                error_message=row[4],
                status_code=row[5]
            )
            for row in rows
        ]


def main():
    """CLI interface for health monitoring"""
    import argparse

    parser = argparse.ArgumentParser(description="Provider Health Monitor")
    subparsers = parser.add_subparsers(dest='command', help='Commands')

    # Status command
    status_parser = subparsers.add_parser('status', help='Show provider health status')
    status_parser.add_argument('--json', action='store_true', help='Output as JSON')
    status_parser.add_argument('--window', type=int, default=24, help='Time window in hours')

    # History command
    history_parser = subparsers.add_parser('history', help='Show health check history')
    history_parser.add_argument('provider', help='Provider name')
    history_parser.add_argument('--hours', type=int, default=24, help='Hours of history')
    history_parser.add_argument('--json', action='store_true', help='Output as JSON')

    # Alerts command
    alerts_parser = subparsers.add_parser('alerts', help='Show health alerts')
    alerts_parser.add_argument('--provider', help='Filter by provider')
    alerts_parser.add_argument('--unacknowledged', action='store_true', help='Show only unacknowledged')
    alerts_parser.add_argument('--json', action='store_true', help='Output as JSON')

    # Check command
    check_parser = subparsers.add_parser('check', help='Perform health check')
    check_parser.add_argument('provider', help='Provider to check')
    check_parser.add_argument('--json', action='store_true', help='Output as JSON')

    # Monitor command
    monitor_parser = subparsers.add_parser('monitor', help='Start monitoring daemon')
    monitor_parser.add_argument('--interval', type=int, default=300, help='Check interval in seconds')
    monitor_parser.add_argument('--webhook', help='Webhook URL for alerts')

    args = parser.parse_args()

    if args.command == 'status':
        monitor = HealthMonitor()
        health_map = monitor.get_all_provider_health(args.window)

        if args.json:
            print(json.dumps({k: asdict(v) for k, v in health_map.items()}, indent=2))
        else:
            print(f"\nProvider Health Status (last {args.window} hours):")
            print("=" * 80)
            for provider, health in health_map.items():
                status_icon = "✓" if health.status == ProviderStatus.HEALTHY else "✗"
                enabled_text = "enabled" if health.is_enabled else "DISABLED"
                print(f"\n{status_icon} {provider.upper()} ({health.status.value}) - {enabled_text}")
                print(f"  Success Rate: {health.success_rate*100:.1f}%")
                print(f"  Avg Latency: {health.latency_avg_ms:.0f}ms (p95: {health.latency_p95_ms:.0f}ms)")
                print(f"  Total Checks: {health.total_checks}")
                print(f"  Consecutive Failures: {health.consecutive_failures}")
                if health.last_error:
                    print(f"  Last Error: {health.last_error}")
                print(f"  Last Check: {health.last_check}")

    elif args.command == 'history':
        monitor = HealthMonitor()
        history = monitor.get_health_history(args.provider, args.hours)

        if args.json:
            print(json.dumps([asdict(h) for h in history], indent=2))
        else:
            print(f"\nHealth Check History for {args.provider} (last {args.hours} hours):")
            print("=" * 80)
            for check in history[:20]:  # Show last 20
                status = "✓" if check.success else "✗"
                print(f"{status} {check.timestamp} - {check.latency_ms:.0f}ms", end="")
                if check.error_message:
                    print(f" - {check.error_message}")
                else:
                    print()

    elif args.command == 'alerts':
        monitor = HealthMonitor()
        acknowledged = False if args.unacknowledged else None
        alerts = monitor.get_alerts(acknowledged=acknowledged, provider=args.provider)

        if args.json:
            print(json.dumps([asdict(a) for a in alerts], indent=2))
        else:
            print(f"\nHealth Alerts:")
            print("=" * 80)
            for alert in alerts:
                ack_text = "✓" if alert.acknowledged else "!"
                print(f"{ack_text} [{alert.alert_type}] {alert.provider}: {alert.message}")
                print(f"   {alert.timestamp} (ID: {alert.alert_id})")

    elif args.command == 'check':
        monitor = HealthMonitor()
        result = monitor.check_provider_health(args.provider)
        monitor.record_health_check(result)

        if args.json:
            print(json.dumps(asdict(result), indent=2))
        else:
            status = "SUCCESS" if result.success else "FAILED"
            print(f"\nHealth Check: {result.provider} - {status}")
            print(f"Latency: {result.latency_ms:.0f}ms")
            if result.error_message:
                print(f"Error: {result.error_message}")

    elif args.command == 'monitor':
        monitor = HealthMonitor(check_interval=args.interval)

        # Add webhook callback if provided
        if args.webhook:
            monitor.add_alert_callback(lambda alert: monitor.send_webhook_alert(args.webhook, alert))

        print(f"Starting health monitoring (interval: {args.interval}s)")
        if args.webhook:
            print(f"Alerts will be sent to: {args.webhook}")

        monitor.start_monitoring()

        try:
            # Keep running until interrupted
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\nStopping health monitoring...")
            monitor.stop_monitoring()

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
