#!/usr/bin/env python3
"""
Worker Health Monitoring for Claude-Loop

Monitors worker health via heartbeats and detects hung/stale processes.
Supports automatic restart of hung workers with checkpoint recovery.

Usage:
    from lib.health_monitor import HealthMonitor, WorkerHealth

    monitor = HealthMonitor()

    # Write heartbeat from worker
    monitor.write_heartbeat(
        worker_id="worker-001",
        prd_id="PRD-001",
        story_id="US-001",
        iteration=5
    )

    # Check health from coordinator
    health = monitor.check_worker_health("worker-001")
    if health.status == "hung":
        print(f"Worker hung! Last seen: {health.last_heartbeat}")
"""

import json
import os
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Optional, Dict, Any, List

try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False


class WorkerStatus(Enum):
    """Worker health statuses"""
    HEALTHY = "healthy"        # Heartbeat within expected interval
    HUNG = "hung"             # No heartbeat for >2min
    DEAD = "dead"             # Process not running
    UNKNOWN = "unknown"       # No heartbeat data yet


@dataclass
class Heartbeat:
    """Worker heartbeat data"""
    timestamp: str
    worker_id: str
    prd_id: str
    story_id: Optional[str]
    iteration: int
    memory_mb: float
    api_calls_made: int
    context: Dict[str, Any]


@dataclass
class WorkerHealth:
    """Worker health assessment"""
    worker_id: str
    status: str
    last_heartbeat: Optional[str]
    seconds_since_heartbeat: Optional[float]
    memory_mb: Optional[float]
    api_calls_made: Optional[int]
    current_story: Optional[str]
    iteration: Optional[int]
    pid: Optional[int]
    process_running: bool


class HealthMonitor:
    """Monitors worker health via heartbeats"""

    HEARTBEAT_INTERVAL_SECONDS = 30  # Workers write every 30s
    HUNG_THRESHOLD_SECONDS = 120     # No heartbeat for 2min = hung
    STALE_THRESHOLD_SECONDS = 300    # No heartbeat for 5min = likely dead

    def __init__(self, workers_dir: Optional[Path] = None, health_log: Optional[Path] = None):
        """
        Initialize health monitor

        Args:
            workers_dir: Base directory for workers (default: .claude-loop/workers)
            health_log: Path to health events log (default: .claude-loop/health.jsonl)
        """
        if workers_dir is None:
            workers_dir = Path.cwd() / ".claude-loop" / "workers"

        if health_log is None:
            health_log = Path.cwd() / ".claude-loop" / "health.jsonl"

        self.workers_dir = Path(workers_dir)
        self.health_log = Path(health_log)
        self.health_log.parent.mkdir(parents=True, exist_ok=True)

    def write_heartbeat(
        self,
        worker_id: str,
        prd_id: str,
        story_id: Optional[str] = None,
        iteration: int = 0,
        api_calls_made: int = 0,
        context: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Write heartbeat from worker process

        Args:
            worker_id: Worker identifier
            prd_id: PRD being worked on
            story_id: Current story
            iteration: Iteration count
            api_calls_made: Number of API calls made
            context: Additional context (model, tokens, etc)
        """
        worker_dir = self.workers_dir / worker_id
        worker_dir.mkdir(parents=True, exist_ok=True)

        heartbeat_file = worker_dir / "heartbeat.json"

        heartbeat = Heartbeat(
            timestamp=datetime.utcnow().isoformat() + "Z",
            worker_id=worker_id,
            prd_id=prd_id,
            story_id=story_id,
            iteration=iteration,
            memory_mb=self._get_memory_usage(),
            api_calls_made=api_calls_made,
            context=context or {}
        )

        # Write atomically
        temp_file = heartbeat_file.with_suffix('.tmp')
        with open(temp_file, 'w') as f:
            json.dump(asdict(heartbeat), f, indent=2)
        temp_file.rename(heartbeat_file)

    def check_worker_health(self, worker_id: str) -> WorkerHealth:
        """
        Check health of a specific worker

        Args:
            worker_id: Worker identifier

        Returns:
            WorkerHealth assessment
        """
        worker_dir = self.workers_dir / worker_id
        heartbeat_file = worker_dir / "heartbeat.json"

        # Check if heartbeat file exists
        if not heartbeat_file.exists():
            return WorkerHealth(
                worker_id=worker_id,
                status=WorkerStatus.UNKNOWN.value,
                last_heartbeat=None,
                seconds_since_heartbeat=None,
                memory_mb=None,
                api_calls_made=None,
                current_story=None,
                iteration=None,
                pid=None,
                process_running=False
            )

        # Read heartbeat
        try:
            with open(heartbeat_file) as f:
                heartbeat_data = json.load(f)
        except Exception:
            return self._unknown_health(worker_id)

        # Parse timestamp
        try:
            last_heartbeat = datetime.fromisoformat(
                heartbeat_data['timestamp'].replace('Z', '+00:00')
            )
            seconds_since = (datetime.utcnow() - last_heartbeat.replace(tzinfo=None)).total_seconds()
        except Exception:
            return self._unknown_health(worker_id)

        # Check if process is running
        pid = heartbeat_data.get('context', {}).get('pid')
        process_running = self._is_process_running(pid) if pid else False

        # Determine status
        if not process_running and pid:
            status = WorkerStatus.DEAD
        elif seconds_since > self.STALE_THRESHOLD_SECONDS:
            status = WorkerStatus.DEAD
        elif seconds_since > self.HUNG_THRESHOLD_SECONDS:
            status = WorkerStatus.HUNG
        else:
            status = WorkerStatus.HEALTHY

        health = WorkerHealth(
            worker_id=worker_id,
            status=status.value,
            last_heartbeat=heartbeat_data['timestamp'],
            seconds_since_heartbeat=seconds_since,
            memory_mb=heartbeat_data.get('memory_mb'),
            api_calls_made=heartbeat_data.get('api_calls_made'),
            current_story=heartbeat_data.get('story_id'),
            iteration=heartbeat_data.get('iteration'),
            pid=pid,
            process_running=process_running
        )

        # Log health event if not healthy
        if status != WorkerStatus.HEALTHY:
            self._log_health_event(health)

        return health

    def check_all_workers(self) -> Dict[str, WorkerHealth]:
        """
        Check health of all workers

        Returns:
            Dictionary mapping worker_id to WorkerHealth
        """
        if not self.workers_dir.exists():
            return {}

        health_by_worker = {}
        for worker_dir in self.workers_dir.iterdir():
            if worker_dir.is_dir():
                worker_id = worker_dir.name
                health_by_worker[worker_id] = self.check_worker_health(worker_id)

        return health_by_worker

    def get_unhealthy_workers(self) -> List[WorkerHealth]:
        """
        Get list of unhealthy workers (hung or dead)

        Returns:
            List of unhealthy WorkerHealth objects
        """
        all_health = self.check_all_workers()
        return [
            health for health in all_health.values()
            if health.status in [WorkerStatus.HUNG.value, WorkerStatus.DEAD.value]
        ]

    def cleanup_stale_heartbeats(self, max_age_hours: int = 24) -> int:
        """
        Clean up heartbeat files older than max_age_hours

        Args:
            max_age_hours: Maximum age in hours before cleanup

        Returns:
            Number of heartbeats cleaned up
        """
        if not self.workers_dir.exists():
            return 0

        cutoff_time = datetime.utcnow() - timedelta(hours=max_age_hours)
        cleaned = 0

        for worker_dir in self.workers_dir.iterdir():
            if not worker_dir.is_dir():
                continue

            heartbeat_file = worker_dir / "heartbeat.json"
            if not heartbeat_file.exists():
                continue

            try:
                with open(heartbeat_file) as f:
                    data = json.load(f)
                timestamp = datetime.fromisoformat(data['timestamp'].replace('Z', '+00:00'))

                if timestamp.replace(tzinfo=None) < cutoff_time:
                    heartbeat_file.unlink()
                    cleaned += 1
            except Exception:
                pass

        return cleaned

    def get_health_summary(self) -> Dict[str, Any]:
        """
        Get summary of worker health

        Returns:
            Summary statistics
        """
        all_health = self.check_all_workers()

        by_status = {}
        for health in all_health.values():
            status = health.status
            by_status[status] = by_status.get(status, 0) + 1

        return {
            'total_workers': len(all_health),
            'healthy': by_status.get(WorkerStatus.HEALTHY.value, 0),
            'hung': by_status.get(WorkerStatus.HUNG.value, 0),
            'dead': by_status.get(WorkerStatus.DEAD.value, 0),
            'unknown': by_status.get(WorkerStatus.UNKNOWN.value, 0),
            'workers': [asdict(h) for h in all_health.values()]
        }

    def _log_health_event(self, health: WorkerHealth) -> None:
        """Log health event to JSONL file"""
        event = {
            'timestamp': datetime.utcnow().isoformat() + "Z",
            'worker_id': health.worker_id,
            'status': health.status,
            'seconds_since_heartbeat': health.seconds_since_heartbeat,
            'current_story': health.current_story,
            'iteration': health.iteration,
            'process_running': health.process_running
        }

        with open(self.health_log, 'a') as f:
            f.write(json.dumps(event) + '\n')

    @staticmethod
    def _get_memory_usage() -> float:
        """Get current process memory usage in MB"""
        if not HAS_PSUTIL:
            return 0.0

        try:
            process = psutil.Process()
            return process.memory_info().rss / 1024 / 1024
        except Exception:
            return 0.0

    @staticmethod
    def _is_process_running(pid: Optional[int]) -> bool:
        """Check if process with given PID is running"""
        if pid is None:
            return False

        if not HAS_PSUTIL:
            # Fallback: check if PID exists (Unix only)
            try:
                os.kill(pid, 0)
                return True
            except (OSError, ProcessLookupError):
                return False

        try:
            process = psutil.Process(pid)
            return process.is_running()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            return False

    @staticmethod
    def _unknown_health(worker_id: str) -> WorkerHealth:
        """Return unknown health status"""
        return WorkerHealth(
            worker_id=worker_id,
            status=WorkerStatus.UNKNOWN.value,
            last_heartbeat=None,
            seconds_since_heartbeat=None,
            memory_mb=None,
            api_calls_made=None,
            current_story=None,
            iteration=None,
            pid=None,
            process_running=False
        )


if __name__ == '__main__':
    # CLI interface
    import argparse

    parser = argparse.ArgumentParser(description='Monitor worker health')
    parser.add_argument('--check', metavar='WORKER_ID', help='Check specific worker')
    parser.add_argument('--check-all', action='store_true', help='Check all workers')
    parser.add_argument('--unhealthy', action='store_true', help='Show unhealthy workers')
    parser.add_argument('--summary', action='store_true', help='Show health summary')
    parser.add_argument('--cleanup', type=int, metavar='HOURS', help='Clean up old heartbeats')

    args = parser.parse_args()

    monitor = HealthMonitor()

    if args.check:
        health = monitor.check_worker_health(args.check)
        print(json.dumps(asdict(health), indent=2))
    elif args.check_all:
        all_health = monitor.check_all_workers()
        for worker_id, health in all_health.items():
            print(f"\n{worker_id}:")
            print(json.dumps(asdict(health), indent=2))
    elif args.unhealthy:
        unhealthy = monitor.get_unhealthy_workers()
        print(json.dumps([asdict(h) for h in unhealthy], indent=2))
    elif args.summary:
        summary = monitor.get_health_summary()
        print(json.dumps(summary, indent=2))
    elif args.cleanup:
        cleaned = monitor.cleanup_stale_heartbeats(max_age_hours=args.cleanup)
        print(f"Cleaned up {cleaned} stale heartbeats")
    else:
        parser.print_help()
