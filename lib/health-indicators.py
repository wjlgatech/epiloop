#!/usr/bin/env python3
"""
health-indicators.py - Leading Indicator Metrics for claude-loop

Provides early warning indicators to predict problems before they manifest.
Unlike lagging metrics (failure counts, cost totals), leading indicators
identify concerning trends that predict future issues.

Leading Indicators:
- proposal_rate_change: >2x spike in improvement proposals = something wrong
- cluster_concentration: are failures spreading or concentrating in one area?
- retrieval_miss_rate: how often does experience store return nothing useful?
- domain_drift: is the system seeing new domains it wasn't trained for?

Each indicator has:
- Current value
- Historical trend
- RAG status (Red/Amber/Green)
- Alert threshold configuration

Usage:
    # Show all indicators with RAG status
    python3 lib/health-indicators.py status

    # Show trend over time
    python3 lib/health-indicators.py history --days 30

    # Show active alerts
    python3 lib/health-indicators.py alerts

    # Configure thresholds
    python3 lib/health-indicators.py thresholds --show
    python3 lib/health-indicators.py thresholds --set proposal_rate_change.amber 1.5

    # Run health check (JSON output for monitoring)
    python3 lib/health-indicators.py check --json

CLI Options:
    --json              Output as JSON
    --verbose           Enable verbose output
    --base-dir DIR      Base directory for .claude-loop data
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone, timedelta
from enum import Enum
from pathlib import Path
from typing import Any


# ============================================================================
# Constants
# ============================================================================

BASE_DIR = Path.cwd()
DEFAULT_DATA_DIR = ".claude-loop"
IMPROVEMENT_QUEUE_FILE = "improvement_queue.json"
RETRIEVAL_LOG_FILE = "retrieval_outcomes.jsonl"
EXPERIENCE_DB_DIR = "experiences"
EXECUTION_LOG_FILE = "execution_log.jsonl"
HEALTH_HISTORY_FILE = "health_history.jsonl"
HEALTH_ALERTS_FILE = "health_alerts.json"
HEALTH_CONFIG_FILE = "health_config.json"

# Default thresholds for RAG status
DEFAULT_THRESHOLDS = {
    "proposal_rate_change": {
        "green_max": 1.5,      # Up to 50% increase is green
        "amber_max": 2.0,      # 50-100% increase is amber
        "red_min": 2.0,        # >100% increase is red
        "description": "Ratio of proposals this period vs baseline period",
    },
    "cluster_concentration": {
        "green_max": 0.4,      # <40% in one cluster is green
        "amber_max": 0.6,      # 40-60% in one cluster is amber
        "red_min": 0.6,        # >60% in one cluster is red
        "description": "Fraction of failures in most common failure pattern",
    },
    "retrieval_miss_rate": {
        "green_max": 0.3,      # <30% miss rate is green
        "amber_max": 0.5,      # 30-50% miss rate is amber
        "red_min": 0.5,        # >50% miss rate is red
        "description": "Fraction of retrievals returning no useful results",
    },
    "domain_drift": {
        "green_max": 0.2,      # <20% unknown domains is green
        "amber_max": 0.4,      # 20-40% unknown domains is amber
        "red_min": 0.4,        # >40% unknown domains is red
        "description": "Fraction of work in domains not seen in training data",
    },
}

# Lookback period for baseline (in days)
BASELINE_PERIOD_DAYS = 14
CURRENT_PERIOD_DAYS = 7


# ============================================================================
# Enums
# ============================================================================

class HealthStatus(str, Enum):
    """RAG health status for indicators."""
    GREEN = "green"     # Normal operation
    AMBER = "amber"     # Warning - needs attention
    RED = "red"         # Critical - action required
    UNKNOWN = "unknown" # Insufficient data

    def __str__(self) -> str:
        return self.value


class AlertSeverity(str, Enum):
    """Alert severity levels."""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"

    def __str__(self) -> str:
        return self.value


# ============================================================================
# Data Classes
# ============================================================================

@dataclass
class IndicatorValue:
    """Value for a single leading indicator at a point in time.

    Attributes:
        name: Indicator name
        value: Current numeric value
        status: RAG status (green/amber/red)
        trend: Direction of change (improving/stable/degrading)
        message: Human-readable description
        details: Additional details for debugging
        timestamp: When this value was computed
    """
    name: str
    value: float
    status: str  # HealthStatus value
    trend: str = "stable"  # improving, stable, degrading
    message: str = ""
    details: dict[str, Any] = field(default_factory=dict)
    timestamp: str = ""

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "IndicatorValue":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class HealthSnapshot:
    """Complete health status at a point in time.

    Attributes:
        timestamp: When snapshot was taken
        indicators: All indicator values
        overall_status: Worst status among all indicators
        active_alerts: Number of active alerts
        message: Summary message
    """
    timestamp: str
    indicators: dict[str, IndicatorValue]
    overall_status: str  # HealthStatus value
    active_alerts: int = 0
    message: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "indicators": {k: v.to_dict() for k, v in self.indicators.items()},
            "overall_status": self.overall_status,
            "active_alerts": self.active_alerts,
            "message": self.message,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "HealthSnapshot":
        indicators = {
            k: IndicatorValue.from_dict(v)
            for k, v in data.get("indicators", {}).items()
        }
        return cls(
            timestamp=data["timestamp"],
            indicators=indicators,
            overall_status=data["overall_status"],
            active_alerts=data.get("active_alerts", 0),
            message=data.get("message", ""),
        )


@dataclass
class HealthAlert:
    """An active health alert.

    Attributes:
        id: Unique alert ID
        indicator: Which indicator triggered this
        severity: info/warning/critical
        message: Alert description
        value: The value that triggered the alert
        threshold: The threshold that was crossed
        created_at: When alert was created
        acknowledged: Whether human has acknowledged
        resolved_at: When alert was resolved (if applicable)
    """
    id: str
    indicator: str
    severity: str  # AlertSeverity value
    message: str
    value: float
    threshold: float
    created_at: str = ""
    acknowledged: bool = False
    resolved_at: str = ""

    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        if not self.id:
            import hashlib
            hash_input = f"{self.indicator}:{self.created_at}"
            self.id = f"ALERT-{hashlib.sha256(hash_input.encode()).hexdigest()[:8].upper()}"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "HealthAlert":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


# ============================================================================
# Health Indicators Manager
# ============================================================================

class HealthIndicatorsManager:
    """
    Manager for computing and tracking leading indicator metrics.

    Provides early warning indicators that predict problems before they
    manifest as failures or increased costs.
    """

    def __init__(self, base_dir: Path | None = None):
        """Initialize the health indicators manager.

        Args:
            base_dir: Base directory for .claude-loop data
        """
        self.base_dir = base_dir or BASE_DIR
        self.data_dir = self.base_dir / DEFAULT_DATA_DIR
        self.thresholds = self._load_thresholds()
        self._ensure_dirs()

    def _ensure_dirs(self) -> None:
        """Create necessary directories."""
        self.data_dir.mkdir(parents=True, exist_ok=True)

    def _load_thresholds(self) -> dict[str, dict[str, Any]]:
        """Load thresholds from config or use defaults."""
        config_file = self.data_dir / HEALTH_CONFIG_FILE
        if config_file.exists():
            try:
                with open(config_file) as f:
                    config = json.load(f)
                    return config.get("thresholds", DEFAULT_THRESHOLDS.copy())
            except (json.JSONDecodeError, IOError):
                pass
        return DEFAULT_THRESHOLDS.copy()

    def _save_thresholds(self) -> None:
        """Save thresholds to config file."""
        config_file = self.data_dir / HEALTH_CONFIG_FILE
        config = {"thresholds": self.thresholds}
        with open(config_file, "w") as f:
            json.dump(config, f, indent=2)

    def _get_status(self, indicator: str, value: float) -> HealthStatus:
        """Determine RAG status for an indicator value.

        Args:
            indicator: Indicator name
            value: Current value

        Returns:
            HealthStatus (GREEN, AMBER, RED, or UNKNOWN)
        """
        thresholds = self.thresholds.get(indicator, {})
        green_max = thresholds.get("green_max", float('inf'))
        amber_max = thresholds.get("amber_max", float('inf'))

        if value <= green_max:
            return HealthStatus.GREEN
        elif value <= amber_max:
            return HealthStatus.AMBER
        else:
            return HealthStatus.RED

    def _load_jsonl(self, filename: str) -> list[dict[str, Any]]:
        """Load records from a JSONL file."""
        file_path = self.data_dir / filename
        records = []
        if file_path.exists():
            with open(file_path) as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            records.append(json.loads(line))
                        except json.JSONDecodeError:
                            continue
        return records

    def _load_json(self, filename: str) -> dict[str, Any] | list[Any] | None:
        """Load data from a JSON file."""
        file_path = self.data_dir / filename
        if file_path.exists():
            try:
                with open(file_path) as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                pass
        return None

    def _get_date_range(
        self, days: int, end_date: datetime | None = None
    ) -> tuple[datetime, datetime]:
        """Get start and end datetime for a date range."""
        end = end_date or datetime.now(timezone.utc)
        start = end - timedelta(days=days)
        return start, end

    def _filter_by_date(
        self,
        records: list[dict[str, Any]],
        start: datetime,
        end: datetime,
        date_field: str = "timestamp",
    ) -> list[dict[str, Any]]:
        """Filter records to those within a date range."""
        filtered = []
        for record in records:
            ts_str = record.get(date_field, "")
            if ts_str:
                try:
                    ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                    if start <= ts <= end:
                        filtered.append(record)
                except (ValueError, TypeError):
                    continue
        return filtered

    # ========================================================================
    # Indicator Calculations
    # ========================================================================

    def calculate_proposal_rate_change(self) -> IndicatorValue:
        """Calculate proposal rate change indicator.

        Compares the number of improvement proposals in the current period
        vs the baseline period. A >2x spike suggests something is wrong.

        Returns:
            IndicatorValue with rate change ratio
        """
        queue_data = self._load_json(IMPROVEMENT_QUEUE_FILE)
        if not queue_data or "proposals" not in queue_data:
            return IndicatorValue(
                name="proposal_rate_change",
                value=0.0,
                status=HealthStatus.UNKNOWN.value,
                message="No proposal data available",
            )

        # queue_data is a dict
        if not isinstance(queue_data, dict):
            return IndicatorValue(
                name="proposal_rate_change",
                value=0.0,
                status=HealthStatus.UNKNOWN.value,
                message="Invalid proposal data format",
            )

        proposals = queue_data.get("proposals", [])
        if not isinstance(proposals, list):
            proposals = []

        # Current period
        current_start, current_end = self._get_date_range(CURRENT_PERIOD_DAYS)
        current_proposals = self._filter_by_date(
            proposals, current_start, current_end, "created_at"
        )
        current_count = len(current_proposals)

        # Baseline period (before current period)
        baseline_end = current_start
        baseline_start = baseline_end - timedelta(days=BASELINE_PERIOD_DAYS)
        baseline_proposals = self._filter_by_date(
            proposals, baseline_start, baseline_end, "created_at"
        )

        # Normalize baseline to same period length
        if BASELINE_PERIOD_DAYS != CURRENT_PERIOD_DAYS:
            baseline_count = len(baseline_proposals) * (
                CURRENT_PERIOD_DAYS / BASELINE_PERIOD_DAYS
            )
        else:
            baseline_count = len(baseline_proposals)

        # Calculate rate change
        if baseline_count > 0:
            rate_change = current_count / baseline_count
        elif current_count > 0:
            rate_change = float('inf')  # Spike from zero
        else:
            rate_change = 1.0  # No proposals in either period

        # Handle infinity
        if rate_change == float('inf'):
            rate_change = 10.0  # Cap for display

        status = self._get_status("proposal_rate_change", rate_change)

        # Determine trend
        if rate_change > 1.5:
            trend = "degrading"
        elif rate_change < 0.8:
            trend = "improving"
        else:
            trend = "stable"

        return IndicatorValue(
            name="proposal_rate_change",
            value=round(rate_change, 2),
            status=status.value,
            trend=trend,
            message=f"{current_count} proposals in last {CURRENT_PERIOD_DAYS} days "
                    f"(vs {int(baseline_count)} baseline)",
            details={
                "current_count": current_count,
                "baseline_count": int(baseline_count),
                "current_period_days": CURRENT_PERIOD_DAYS,
                "baseline_period_days": BASELINE_PERIOD_DAYS,
            },
        )

    def calculate_cluster_concentration(self) -> IndicatorValue:
        """Calculate cluster concentration indicator.

        Measures whether failures are spreading across categories or
        concentrating in one area. High concentration suggests a
        systemic issue in that area.

        Returns:
            IndicatorValue with concentration ratio
        """
        # Load execution log to analyze failure patterns
        execution_log = self._load_jsonl(EXECUTION_LOG_FILE)
        if not execution_log:
            return IndicatorValue(
                name="cluster_concentration",
                value=0.0,
                status=HealthStatus.UNKNOWN.value,
                message="No execution data available",
            )

        # Filter to recent failures
        current_start, current_end = self._get_date_range(CURRENT_PERIOD_DAYS)
        recent_executions = self._filter_by_date(
            execution_log, current_start, current_end, "timestamp_start"
        )

        # Count failures by error_type
        error_counts: dict[str, int] = defaultdict(int)
        total_failures = 0
        for record in recent_executions:
            status = record.get("status", "success")
            if status not in ("success", "complete"):
                error_type = record.get("error_type", "unknown")
                error_counts[error_type] += 1
                total_failures += 1

        if total_failures == 0:
            return IndicatorValue(
                name="cluster_concentration",
                value=0.0,
                status=HealthStatus.GREEN.value,
                trend="stable",
                message="No failures in recent period",
                details={"total_failures": 0},
            )

        # Find most common error type
        max_count = max(error_counts.values())
        most_common = [k for k, v in error_counts.items() if v == max_count][0]
        concentration = max_count / total_failures

        status = self._get_status("cluster_concentration", concentration)

        # Determine trend (would need historical data for proper trend)
        if concentration > 0.6:
            trend = "degrading"
        elif concentration < 0.3:
            trend = "improving"
        else:
            trend = "stable"

        return IndicatorValue(
            name="cluster_concentration",
            value=round(concentration, 2),
            status=status.value,
            trend=trend,
            message=f"{round(concentration * 100)}% of {total_failures} failures "
                    f"are '{most_common}' errors",
            details={
                "total_failures": total_failures,
                "most_common_error": most_common,
                "most_common_count": max_count,
                "error_distribution": dict(error_counts),
            },
        )

    def calculate_retrieval_miss_rate(self) -> IndicatorValue:
        """Calculate retrieval miss rate indicator.

        Measures how often experience retrieval returns nothing useful.
        High miss rate suggests the experience store isn't covering
        the problems being encountered.

        Returns:
            IndicatorValue with miss rate (0-1)
        """
        retrieval_log = self._load_jsonl(RETRIEVAL_LOG_FILE)
        if not retrieval_log:
            return IndicatorValue(
                name="retrieval_miss_rate",
                value=0.0,
                status=HealthStatus.UNKNOWN.value,
                message="No retrieval data available",
            )

        # Filter to recent retrievals
        current_start, current_end = self._get_date_range(CURRENT_PERIOD_DAYS)
        recent_retrievals = self._filter_by_date(
            retrieval_log, current_start, current_end, "timestamp"
        )

        if not recent_retrievals:
            return IndicatorValue(
                name="retrieval_miss_rate",
                value=0.0,
                status=HealthStatus.UNKNOWN.value,
                message="No retrievals in recent period",
            )

        # Count outcomes
        total = len(recent_retrievals)
        ignored_or_hurt = sum(
            1 for r in recent_retrievals
            if r.get("outcome") in ("ignored", "hurt")
        )

        miss_rate = ignored_or_hurt / total if total > 0 else 0.0
        status = self._get_status("retrieval_miss_rate", miss_rate)

        # Trend
        if miss_rate > 0.5:
            trend = "degrading"
        elif miss_rate < 0.2:
            trend = "improving"
        else:
            trend = "stable"

        return IndicatorValue(
            name="retrieval_miss_rate",
            value=round(miss_rate, 2),
            status=status.value,
            trend=trend,
            message=f"{ignored_or_hurt}/{total} retrievals were not useful "
                    f"({round(miss_rate * 100)}% miss rate)",
            details={
                "total_retrievals": total,
                "ignored_count": sum(
                    1 for r in recent_retrievals if r.get("outcome") == "ignored"
                ),
                "hurt_count": sum(
                    1 for r in recent_retrievals if r.get("outcome") == "hurt"
                ),
                "used_count": sum(
                    1 for r in recent_retrievals if r.get("outcome") == "used"
                ),
                "helped_count": sum(
                    1 for r in recent_retrievals if r.get("outcome") == "helped"
                ),
            },
        )

    def calculate_domain_drift(self) -> IndicatorValue:
        """Calculate domain drift indicator.

        Measures the fraction of work being done in domains that the
        system hasn't seen before or has limited experience with.
        High drift suggests the system may not perform well.

        Returns:
            IndicatorValue with drift ratio (0-1)
        """
        # Known domain types from experience store
        known_domains = {
            "web_frontend", "web_backend", "unity_game", "unity_xr",
            "isaac_sim", "ml_training", "ml_inference", "data_pipeline",
            "cli_tool", "robotics", "other",
        }

        # Load execution log to see what domains are being used
        execution_log = self._load_jsonl(EXECUTION_LOG_FILE)
        if not execution_log:
            return IndicatorValue(
                name="domain_drift",
                value=0.0,
                status=HealthStatus.UNKNOWN.value,
                message="No execution data available",
            )

        # Filter to recent executions
        current_start, current_end = self._get_date_range(CURRENT_PERIOD_DAYS)
        recent_executions = self._filter_by_date(
            execution_log, current_start, current_end, "timestamp_start"
        )

        if not recent_executions:
            return IndicatorValue(
                name="domain_drift",
                value=0.0,
                status=HealthStatus.UNKNOWN.value,
                message="No executions in recent period",
            )

        # Count domains encountered
        domain_counts: dict[str, int] = defaultdict(int)
        total_with_domain = 0
        unknown_count = 0

        for record in recent_executions:
            context = record.get("context", {})
            if isinstance(context, str):
                try:
                    context = json.loads(context)
                except (json.JSONDecodeError, TypeError):
                    context = {}

            domain = context.get("project_type", context.get("domain", ""))
            if domain:
                total_with_domain += 1
                domain_counts[domain] += 1
                if domain not in known_domains and domain != "":
                    unknown_count += 1

        if total_with_domain == 0:
            return IndicatorValue(
                name="domain_drift",
                value=0.0,
                status=HealthStatus.UNKNOWN.value,
                message="No domain context in recent executions",
                details={"total_executions": len(recent_executions)},
            )

        drift_rate = unknown_count / total_with_domain
        status = self._get_status("domain_drift", drift_rate)

        # Trend
        if drift_rate > 0.4:
            trend = "degrading"
        elif drift_rate < 0.1:
            trend = "improving"
        else:
            trend = "stable"

        return IndicatorValue(
            name="domain_drift",
            value=round(drift_rate, 2),
            status=status.value,
            trend=trend,
            message=f"{unknown_count}/{total_with_domain} executions in "
                    f"unknown domains ({round(drift_rate * 100)}%)",
            details={
                "total_with_domain": total_with_domain,
                "unknown_count": unknown_count,
                "domain_distribution": dict(domain_counts),
                "known_domains": list(known_domains),
            },
        )

    # ========================================================================
    # Health Snapshot and Alerts
    # ========================================================================

    def get_health_snapshot(self) -> HealthSnapshot:
        """Get current health status for all indicators.

        Returns:
            HealthSnapshot with all indicator values
        """
        indicators = {
            "proposal_rate_change": self.calculate_proposal_rate_change(),
            "cluster_concentration": self.calculate_cluster_concentration(),
            "retrieval_miss_rate": self.calculate_retrieval_miss_rate(),
            "domain_drift": self.calculate_domain_drift(),
        }

        # Determine overall status (worst case)
        statuses = [i.status for i in indicators.values()]
        if HealthStatus.RED.value in statuses:
            overall = HealthStatus.RED.value
        elif HealthStatus.AMBER.value in statuses:
            overall = HealthStatus.AMBER.value
        elif all(s == HealthStatus.UNKNOWN.value for s in statuses):
            overall = HealthStatus.UNKNOWN.value
        else:
            overall = HealthStatus.GREEN.value

        # Count active alerts
        alerts = self.get_active_alerts()

        # Generate summary message
        red_indicators = [k for k, v in indicators.items() if v.status == HealthStatus.RED.value]
        amber_indicators = [k for k, v in indicators.items() if v.status == HealthStatus.AMBER.value]

        if red_indicators:
            message = f"CRITICAL: {', '.join(red_indicators)} require attention"
        elif amber_indicators:
            message = f"WARNING: {', '.join(amber_indicators)} need review"
        else:
            message = "All indicators healthy"

        timestamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

        snapshot = HealthSnapshot(
            timestamp=timestamp,
            indicators=indicators,
            overall_status=overall,
            active_alerts=len(alerts),
            message=message,
        )

        # Save to history
        self._save_snapshot(snapshot)

        # Check for alerts
        self._check_alerts(indicators)

        return snapshot

    def _save_snapshot(self, snapshot: HealthSnapshot) -> None:
        """Save snapshot to history file."""
        history_file = self.data_dir / HEALTH_HISTORY_FILE
        with open(history_file, "a") as f:
            f.write(json.dumps(snapshot.to_dict()) + "\n")

    def _check_alerts(self, indicators: dict[str, IndicatorValue]) -> None:
        """Check indicators and create/resolve alerts as needed."""
        alerts = self._load_alerts()
        now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

        for name, indicator in indicators.items():
            # Check for existing alert for this indicator
            existing = next(
                (a for a in alerts if a.indicator == name and not a.resolved_at),
                None
            )

            if indicator.status == HealthStatus.RED.value:
                # Create alert if none exists
                if not existing:
                    threshold = self.thresholds.get(name, {}).get("red_min", 0)
                    alert = HealthAlert(
                        id="",  # Will be generated
                        indicator=name,
                        severity=AlertSeverity.CRITICAL.value,
                        message=f"Critical: {indicator.message}",
                        value=indicator.value,
                        threshold=threshold,
                    )
                    alerts.append(alert)
            elif indicator.status == HealthStatus.AMBER.value:
                # Create warning alert if none exists
                if not existing:
                    threshold = self.thresholds.get(name, {}).get("amber_max", 0)
                    alert = HealthAlert(
                        id="",
                        indicator=name,
                        severity=AlertSeverity.WARNING.value,
                        message=f"Warning: {indicator.message}",
                        value=indicator.value,
                        threshold=threshold,
                    )
                    alerts.append(alert)
            elif indicator.status == HealthStatus.GREEN.value:
                # Resolve existing alert
                if existing:
                    existing.resolved_at = now

        self._save_alerts(alerts)

    def _load_alerts(self) -> list[HealthAlert]:
        """Load alerts from file."""
        alerts_file = self.data_dir / HEALTH_ALERTS_FILE
        if alerts_file.exists():
            try:
                with open(alerts_file) as f:
                    data = json.load(f)
                    return [HealthAlert.from_dict(a) for a in data]
            except (json.JSONDecodeError, IOError):
                pass
        return []

    def _save_alerts(self, alerts: list[HealthAlert]) -> None:
        """Save alerts to file."""
        alerts_file = self.data_dir / HEALTH_ALERTS_FILE
        with open(alerts_file, "w") as f:
            json.dump([a.to_dict() for a in alerts], f, indent=2)

    def get_active_alerts(self) -> list[HealthAlert]:
        """Get all active (non-resolved) alerts."""
        alerts = self._load_alerts()
        return [a for a in alerts if not a.resolved_at]

    def acknowledge_alert(self, alert_id: str) -> bool:
        """Acknowledge an alert.

        Args:
            alert_id: ID of alert to acknowledge

        Returns:
            True if alert was found and acknowledged
        """
        alerts = self._load_alerts()
        for alert in alerts:
            if alert.id == alert_id:
                alert.acknowledged = True
                self._save_alerts(alerts)
                return True
        return False

    def get_history(
        self,
        days: int = 30,
        indicator: str | None = None,
    ) -> list[dict[str, Any]]:
        """Get health history over time.

        Args:
            days: Number of days to look back
            indicator: Filter to specific indicator (optional)

        Returns:
            List of historical snapshots/values
        """
        history_file = self.data_dir / HEALTH_HISTORY_FILE
        if not history_file.exists():
            return []

        start, end = self._get_date_range(days)
        records = []

        with open(history_file) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    snapshot = json.loads(line)
                    ts_str = snapshot.get("timestamp", "")
                    if ts_str:
                        ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                        if start <= ts <= end:
                            if indicator:
                                # Extract just the specific indicator
                                ind = snapshot.get("indicators", {}).get(indicator)
                                if ind:
                                    records.append({
                                        "timestamp": ts_str,
                                        "value": ind.get("value"),
                                        "status": ind.get("status"),
                                    })
                            else:
                                records.append(snapshot)
                except (json.JSONDecodeError, ValueError, TypeError):
                    continue

        return records

    def set_threshold(
        self,
        indicator: str,
        level: str,
        value: float,
    ) -> bool:
        """Set a threshold value.

        Args:
            indicator: Indicator name
            level: Threshold level (green_max, amber_max, red_min)
            value: New threshold value

        Returns:
            True if threshold was set successfully
        """
        if indicator not in self.thresholds:
            return False
        if level not in ("green_max", "amber_max", "red_min"):
            return False

        self.thresholds[indicator][level] = value
        self._save_thresholds()
        return True

    def get_thresholds(self) -> dict[str, dict[str, Any]]:
        """Get all threshold configurations."""
        return self.thresholds


# ============================================================================
# CLI Interface
# ============================================================================

def format_status_display(snapshot: HealthSnapshot) -> str:
    """Format health snapshot for terminal display."""
    lines = []

    # Header
    status_emoji = {
        HealthStatus.GREEN.value: "[GREEN]",
        HealthStatus.AMBER.value: "[AMBER]",
        HealthStatus.RED.value: "[RED]",
        HealthStatus.UNKNOWN.value: "[???]",
    }

    lines.append("=" * 60)
    lines.append(f"HEALTH STATUS: {status_emoji.get(snapshot.overall_status, '')} "
                 f"{snapshot.overall_status.upper()}")
    lines.append(f"Time: {snapshot.timestamp}")
    if snapshot.active_alerts > 0:
        lines.append(f"Active Alerts: {snapshot.active_alerts}")
    lines.append("=" * 60)
    lines.append("")

    # Indicators
    lines.append("LEADING INDICATORS:")
    lines.append("-" * 40)

    for name, indicator in snapshot.indicators.items():
        emoji = status_emoji.get(indicator.status, "")
        trend_emoji = {"improving": "(^)", "degrading": "(v)", "stable": "(-)"}
        trend_str = trend_emoji.get(indicator.trend, "")

        lines.append(f"  {name}:")
        lines.append(f"    Value: {indicator.value} {emoji} {trend_str}")
        lines.append(f"    {indicator.message}")
        lines.append("")

    # Summary
    if snapshot.message:
        lines.append("-" * 40)
        lines.append(f"Summary: {snapshot.message}")

    return "\n".join(lines)


def format_alerts_display(alerts: list[HealthAlert]) -> str:
    """Format alerts for terminal display."""
    if not alerts:
        return "No active alerts."

    lines = []
    lines.append("ACTIVE ALERTS:")
    lines.append("-" * 50)

    for alert in alerts:
        ack = "[ACK]" if alert.acknowledged else "[NEW]"
        severity = alert.severity.upper()
        lines.append(f"  {ack} {alert.id} ({severity})")
        lines.append(f"      Indicator: {alert.indicator}")
        lines.append(f"      Message: {alert.message}")
        lines.append(f"      Value: {alert.value} (threshold: {alert.threshold})")
        lines.append(f"      Created: {alert.created_at}")
        lines.append("")

    return "\n".join(lines)


def format_history_display(history: list[dict[str, Any]], indicator: str | None = None) -> str:
    """Format history for terminal display."""
    if not history:
        return "No history data available."

    lines = []
    lines.append(f"HEALTH HISTORY (last {len(history)} snapshots):")
    lines.append("-" * 50)

    for record in history[:20]:  # Limit display
        if indicator:
            lines.append(f"  {record['timestamp']}: {record['value']} [{record['status']}]")
        else:
            overall = record.get("overall_status", "unknown")
            lines.append(f"  {record['timestamp']}: {overall.upper()}")

    if len(history) > 20:
        lines.append(f"  ... and {len(history) - 20} more")

    return "\n".join(lines)


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Leading indicator metrics for claude-loop health monitoring",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    # Global options
    parser.add_argument(
        "--json", action="store_true",
        help="Output as JSON",
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true",
        help="Enable verbose output",
    )
    parser.add_argument(
        "--base-dir",
        type=Path,
        default=None,
        help="Base directory for .claude-loop data",
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # status command
    status_parser = subparsers.add_parser(
        "status",
        help="Show all indicators with RAG status",
    )

    # history command
    history_parser = subparsers.add_parser(
        "history",
        help="Show trend over time",
    )
    history_parser.add_argument(
        "--days", type=int, default=30,
        help="Number of days to look back (default: 30)",
    )
    history_parser.add_argument(
        "--indicator",
        help="Filter to specific indicator",
    )

    # alerts command
    alerts_parser = subparsers.add_parser(
        "alerts",
        help="Show active alerts",
    )

    # acknowledge command
    ack_parser = subparsers.add_parser(
        "acknowledge",
        help="Acknowledge an alert",
    )
    ack_parser.add_argument(
        "alert_id",
        help="Alert ID to acknowledge",
    )

    # thresholds command
    thresholds_parser = subparsers.add_parser(
        "thresholds",
        help="View or set thresholds",
    )
    thresholds_parser.add_argument(
        "--show", action="store_true",
        help="Show all thresholds",
    )
    thresholds_parser.add_argument(
        "--set",
        help="Set threshold: indicator.level=value (e.g., proposal_rate_change.amber_max=1.8)",
    )

    # check command (for monitoring integration)
    check_parser = subparsers.add_parser(
        "check",
        help="Run health check (returns non-zero on RED)",
    )

    # indicator-specific commands
    for indicator_name in DEFAULT_THRESHOLDS.keys():
        ind_parser = subparsers.add_parser(
            indicator_name.replace("_", "-"),
            help=f"Show {indicator_name} indicator details",
        )

    args = parser.parse_args()

    # Initialize manager
    manager = HealthIndicatorsManager(base_dir=args.base_dir)

    # Handle commands
    if args.command == "status" or args.command is None:
        snapshot = manager.get_health_snapshot()
        if args.json:
            print(json.dumps(snapshot.to_dict(), indent=2))
        else:
            print(format_status_display(snapshot))

    elif args.command == "history":
        history = manager.get_history(days=args.days, indicator=args.indicator)
        if args.json:
            print(json.dumps(history, indent=2))
        else:
            print(format_history_display(history, args.indicator))

    elif args.command == "alerts":
        alerts = manager.get_active_alerts()
        if args.json:
            print(json.dumps([a.to_dict() for a in alerts], indent=2))
        else:
            print(format_alerts_display(alerts))

    elif args.command == "acknowledge":
        success = manager.acknowledge_alert(args.alert_id)
        if success:
            print(f"Alert {args.alert_id} acknowledged.")
        else:
            print(f"Alert {args.alert_id} not found.")
            sys.exit(1)

    elif args.command == "thresholds":
        if args.set:
            # Parse: indicator.level=value
            try:
                path, value = args.set.split("=")
                indicator, level = path.split(".")
                success = manager.set_threshold(indicator, level, float(value))
                if success:
                    print(f"Set {indicator}.{level} = {value}")
                else:
                    print(f"Invalid indicator or level: {path}")
                    sys.exit(1)
            except ValueError:
                print("Invalid format. Use: indicator.level=value")
                sys.exit(1)
        else:
            thresholds = manager.get_thresholds()
            if args.json:
                print(json.dumps(thresholds, indent=2))
            else:
                print("THRESHOLDS:")
                print("-" * 50)
                for indicator, config in thresholds.items():
                    print(f"\n{indicator}:")
                    print(f"  Description: {config.get('description', '')}")
                    print(f"  Green (max): {config.get('green_max', 'N/A')}")
                    print(f"  Amber (max): {config.get('amber_max', 'N/A')}")
                    print(f"  Red (min):   {config.get('red_min', 'N/A')}")

    elif args.command == "check":
        snapshot = manager.get_health_snapshot()
        if args.json:
            print(json.dumps(snapshot.to_dict(), indent=2))
        else:
            print(format_status_display(snapshot))

        # Exit code based on status
        if snapshot.overall_status == HealthStatus.RED.value:
            sys.exit(2)  # Critical
        elif snapshot.overall_status == HealthStatus.AMBER.value:
            sys.exit(1)  # Warning
        else:
            sys.exit(0)  # OK

    elif args.command in [k.replace("_", "-") for k in DEFAULT_THRESHOLDS.keys()]:
        # Show specific indicator
        indicator_name = args.command.replace("-", "_")
        method_name = f"calculate_{indicator_name}"
        if hasattr(manager, method_name):
            indicator = getattr(manager, method_name)()
            if args.json:
                print(json.dumps(indicator.to_dict(), indent=2))
            else:
                status_emoji = {
                    HealthStatus.GREEN.value: "[GREEN]",
                    HealthStatus.AMBER.value: "[AMBER]",
                    HealthStatus.RED.value: "[RED]",
                    HealthStatus.UNKNOWN.value: "[???]",
                }
                print(f"{indicator.name}: {indicator.value} {status_emoji.get(indicator.status, '')}")
                print(f"  Status: {indicator.status}")
                print(f"  Trend: {indicator.trend}")
                print(f"  {indicator.message}")
                if args.verbose and indicator.details:
                    print(f"  Details: {json.dumps(indicator.details, indent=4)}")

    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
