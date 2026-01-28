#!/usr/bin/env python3
"""
Comprehensive Failure Logger for Claude-Loop

Logs all worker process failures with context for debugging and learning.
Captures exit codes, signals, stack traces, system resources, and recent output.

Usage:
    from lib.failure_logger import FailureLogger, FailureType

    logger = FailureLogger()
    logger.log_failure(
        prd_id="PRD-001",
        story_id="US-001",
        failure_type=FailureType.API_ERROR,
        error_message="Rate limit exceeded",
        exit_code=1,
        stack_trace="...",
        context={"provider": "anthropic"}
    )
"""

import json
import os
import sys
import traceback
from dataclasses import dataclass, asdict
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Optional, Dict, Any, List

try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False


class FailureType(Enum):
    """Categories of failures for pattern detection"""
    BUG = "bug"                              # Code bugs, logic errors
    RESOURCE_EXHAUSTION = "resource_exhaustion"  # OOM, disk full, etc
    TIMEOUT = "timeout"                      # Story/worker timeout
    API_ERROR = "api_error"                  # LLM API failures
    UNKNOWN = "unknown"                      # Unclassified failures
    COORDINATOR_ERROR = "coordinator_error"  # Coordinator bugs
    QUALITY_GATE_FAILURE = "quality_gate_failure"  # Tests/lint/type check failed


@dataclass
class FailureRecord:
    """Structure for failure log entries"""
    timestamp: str
    prd_id: str
    story_id: Optional[str]
    failure_type: str
    error_message: str
    exit_code: Optional[int]
    signal: Optional[str]
    stack_trace: Optional[str]
    last_output_lines: List[str]
    system_resources: Dict[str, Any]
    context: Dict[str, Any]
    worker_id: Optional[str]


class FailureLogger:
    """Logs worker process failures for debugging and learning"""

    def __init__(self, failures_file: Optional[Path] = None):
        """
        Initialize failure logger

        Args:
            failures_file: Path to failures.jsonl (default: .claude-loop/failures.jsonl)
        """
        if failures_file is None:
            claude_loop_dir = Path.home() / ".claude-loop"
            claude_loop_dir.mkdir(exist_ok=True)
            failures_file = claude_loop_dir / "failures.jsonl"

        self.failures_file = Path(failures_file)
        self.failures_file.parent.mkdir(parents=True, exist_ok=True)

    def log_failure(
        self,
        prd_id: str,
        failure_type: FailureType,
        error_message: str,
        story_id: Optional[str] = None,
        exit_code: Optional[int] = None,
        signal: Optional[str] = None,
        stack_trace: Optional[str] = None,
        last_output_lines: Optional[List[str]] = None,
        context: Optional[Dict[str, Any]] = None,
        worker_id: Optional[str] = None
    ) -> None:
        """
        Log a failure event

        Args:
            prd_id: PRD identifier
            failure_type: Category of failure
            error_message: Human-readable error message
            story_id: Story identifier (if applicable)
            exit_code: Process exit code
            signal: Signal that killed process (SIGTERM, SIGKILL, etc)
            stack_trace: Full stack trace
            last_output_lines: Last N lines of stdout/stderr
            context: Additional context (provider, model, etc)
            worker_id: Worker process identifier
        """
        record = FailureRecord(
            timestamp=datetime.utcnow().isoformat() + "Z",
            prd_id=prd_id,
            story_id=story_id,
            failure_type=failure_type.value,
            error_message=error_message,
            exit_code=exit_code,
            signal=signal,
            stack_trace=stack_trace,
            last_output_lines=last_output_lines or [],
            system_resources=self._get_system_resources(),
            context=context or {},
            worker_id=worker_id
        )

        # Append to JSONL file
        with open(self.failures_file, 'a') as f:
            f.write(json.dumps(asdict(record)) + '\n')

    def log_exception(
        self,
        prd_id: str,
        failure_type: FailureType,
        exception: Exception,
        story_id: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        worker_id: Optional[str] = None
    ) -> None:
        """
        Log a failure from an exception

        Args:
            prd_id: PRD identifier
            failure_type: Category of failure
            exception: The exception object
            story_id: Story identifier (if applicable)
            context: Additional context
            worker_id: Worker process identifier
        """
        self.log_failure(
            prd_id=prd_id,
            failure_type=failure_type,
            error_message=str(exception),
            story_id=story_id,
            stack_trace=''.join(traceback.format_exception(
                type(exception), exception, exception.__traceback__
            )),
            context=context,
            worker_id=worker_id
        )

    def get_recent_failures(
        self,
        limit: int = 10,
        prd_id: Optional[str] = None,
        failure_type: Optional[FailureType] = None
    ) -> List[Dict[str, Any]]:
        """
        Get recent failures with optional filtering

        Args:
            limit: Maximum number of failures to return
            prd_id: Filter by PRD ID
            failure_type: Filter by failure type

        Returns:
            List of failure records (most recent first)
        """
        if not self.failures_file.exists():
            return []

        failures = []
        with open(self.failures_file, 'r') as f:
            for line in f:
                if line.strip():
                    failures.append(json.loads(line))

        # Filter
        if prd_id:
            failures = [f for f in failures if f['prd_id'] == prd_id]
        if failure_type:
            failures = [f for f in failures if f['failure_type'] == failure_type.value]

        # Return most recent first (last N items in reversed order)
        return list(reversed(failures[-limit:]))

    def get_failure_stats(self) -> Dict[str, Any]:
        """
        Get failure statistics

        Returns:
            Dictionary with failure counts by type, PRD, etc
        """
        if not self.failures_file.exists():
            return {
                'total': 0,
                'by_type': {},
                'by_prd': {},
                'recent': []
            }

        failures = []
        with open(self.failures_file, 'r') as f:
            for line in f:
                if line.strip():
                    failures.append(json.loads(line))

        by_type = {}
        by_prd = {}
        for failure in failures:
            # Count by type
            ftype = failure['failure_type']
            by_type[ftype] = by_type.get(ftype, 0) + 1

            # Count by PRD
            prd = failure['prd_id']
            by_prd[prd] = by_prd.get(prd, 0) + 1

        return {
            'total': len(failures),
            'by_type': by_type,
            'by_prd': by_prd,
            'recent': list(reversed(failures))[-10:]
        }

    @staticmethod
    def _get_system_resources() -> Dict[str, Any]:
        """Get current system resource usage"""
        if not HAS_PSUTIL:
            return {}

        try:
            process = psutil.Process()
            return {
                'memory_mb': process.memory_info().rss / 1024 / 1024,
                'cpu_percent': process.cpu_percent(),
                'system_memory_percent': psutil.virtual_memory().percent,
                'disk_usage_percent': psutil.disk_usage('/').percent
            }
        except Exception:
            return {}

    @staticmethod
    def classify_failure_from_error(error_message: str, exit_code: Optional[int] = None) -> FailureType:
        """
        Automatically classify failure type from error message

        Args:
            error_message: Error message to classify
            exit_code: Process exit code

        Returns:
            Classified failure type
        """
        error_lower = error_message.lower()

        # API errors
        if any(term in error_lower for term in ['rate limit', '429', 'api', 'quota', 'authentication']):
            return FailureType.API_ERROR

        # Resource exhaustion
        if any(term in error_lower for term in ['memory', 'oom', 'disk', 'space', 'resource']):
            return FailureType.RESOURCE_EXHAUSTION

        # Timeouts
        if any(term in error_lower for term in ['timeout', 'timed out', 'deadline']):
            return FailureType.TIMEOUT

        # Quality gate failures
        if any(term in error_lower for term in ['test failed', 'lint', 'type check', 'coverage']):
            return FailureType.QUALITY_GATE_FAILURE

        # Coordinator errors
        if any(term in error_lower for term in ['coordinator', 'registry', 'lock']):
            return FailureType.COORDINATOR_ERROR

        # Exit codes
        if exit_code == 137:  # SIGKILL
            return FailureType.RESOURCE_EXHAUSTION
        elif exit_code == 124:  # timeout command
            return FailureType.TIMEOUT

        return FailureType.UNKNOWN


def read_last_n_lines(file_path: Path, n: int = 100) -> List[str]:
    """
    Read last N lines from a file efficiently

    Args:
        file_path: Path to file
        n: Number of lines to read

    Returns:
        List of last N lines
    """
    if not file_path.exists():
        return []

    try:
        with open(file_path, 'rb') as f:
            # Seek to end
            f.seek(0, os.SEEK_END)
            file_size = f.tell()

            # Read last ~10KB (should contain >100 lines)
            chunk_size = min(10240, file_size)
            f.seek(max(0, file_size - chunk_size))

            lines = f.read().decode('utf-8', errors='ignore').splitlines()
            return lines[-n:]
    except Exception:
        return []


if __name__ == '__main__':
    # CLI interface for viewing failures
    import argparse

    parser = argparse.ArgumentParser(description='View claude-loop failures')
    parser.add_argument('--limit', type=int, default=10, help='Number of failures to show')
    parser.add_argument('--prd', help='Filter by PRD ID')
    parser.add_argument('--type', help='Filter by failure type')
    parser.add_argument('--stats', action='store_true', help='Show failure statistics')

    args = parser.parse_args()

    logger = FailureLogger()

    if args.stats:
        stats = logger.get_failure_stats()
        print(json.dumps(stats, indent=2))
    else:
        failure_type = FailureType(args.type) if args.type else None
        failures = logger.get_recent_failures(
            limit=args.limit,
            prd_id=args.prd,
            failure_type=failure_type
        )

        for failure in failures:
            print(json.dumps(failure, indent=2))
            print('---')
