#!/usr/bin/env python3
"""
Retry Logic with Exponential Backoff for Claude-Loop

Handles automatic retry of failed PRD workers with exponential backoff.
Only retries transient failures (API errors, timeouts, resource exhaustion).
Does NOT retry logic errors or test failures (requires human intervention).

Usage:
    from lib.retry_handler import RetryHandler, RetryDecision

    handler = RetryHandler()

    # Check if should retry
    decision = handler.should_retry(
        prd_id="PRD-001",
        failure_type="api_error",
        attempt=1
    )

    if decision.should_retry:
        sleep_seconds = decision.backoff_seconds
        # Retry after backoff...
"""

import json
import time
from dataclasses import dataclass, asdict
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Optional, Dict, Any


class RetryPolicy(Enum):
    """Retry policies for different failure types"""
    RETRY = "retry"              # Should retry with backoff
    NO_RETRY = "no_retry"        # Should NOT retry
    IMMEDIATE = "immediate"      # Retry immediately (no backoff)


@dataclass
class RetryDecision:
    """Decision about whether to retry"""
    should_retry: bool
    reason: str
    backoff_seconds: float
    attempts_remaining: int


@dataclass
class RetryRecord:
    """Record of retry attempt"""
    timestamp: str
    prd_id: str
    story_id: Optional[str]
    attempt: int
    failure_type: str
    error_message: str
    backoff_seconds: float
    will_retry: bool


class RetryHandler:
    """Handles retry logic with exponential backoff"""

    # Retry policies by failure type
    RETRY_POLICIES = {
        "api_error": RetryPolicy.RETRY,
        "timeout": RetryPolicy.RETRY,
        "resource_exhaustion": RetryPolicy.RETRY,
        "coordinator_error": RetryPolicy.RETRY,
        "bug": RetryPolicy.NO_RETRY,              # Logic errors need human fix
        "logic_error": RetryPolicy.NO_RETRY,      # Logic errors need human fix
        "quality_gate_failure": RetryPolicy.NO_RETRY,  # Test/lint failures need human fix
        "unknown": RetryPolicy.RETRY,             # Conservative: retry unknowns
    }

    def __init__(
        self,
        max_retries: int = 3,
        backoff_multiplier: float = 2.0,
        base_backoff_seconds: float = 60.0,
        retries_log: Optional[Path] = None
    ):
        """
        Initialize retry handler

        Args:
            max_retries: Maximum retry attempts per PRD (default: 3)
            backoff_multiplier: Exponential backoff multiplier (default: 2.0)
            base_backoff_seconds: Base backoff in seconds (default: 60.0 = 1 min)
            retries_log: Path to retries log (default: .claude-loop/retries.jsonl)
        """
        self.max_retries = max_retries
        self.backoff_multiplier = backoff_multiplier
        self.base_backoff_seconds = base_backoff_seconds

        if retries_log is None:
            retries_log = Path.cwd() / ".claude-loop" / "retries.jsonl"

        self.retries_log = Path(retries_log)
        self.retries_log.parent.mkdir(parents=True, exist_ok=True)

        # In-memory retry counts
        self._retry_counts: Dict[str, int] = {}

    def should_retry(
        self,
        prd_id: str,
        failure_type: str,
        attempt: Optional[int] = None,
        error_message: str = "",
        story_id: Optional[str] = None
    ) -> RetryDecision:
        """
        Determine if a failed PRD should be retried

        Args:
            prd_id: PRD identifier
            failure_type: Type of failure (from FailureLogger)
            attempt: Current attempt number (None = auto-detect from history)
            error_message: Error message
            story_id: Story ID (if applicable)

        Returns:
            RetryDecision with should_retry, reason, and backoff time
        """
        # Determine attempt number
        if attempt is None:
            attempt = self._get_retry_count(prd_id)

        # Check if max retries exceeded
        if attempt >= self.max_retries:
            return RetryDecision(
                should_retry=False,
                reason=f"Maximum retries ({self.max_retries}) exceeded",
                backoff_seconds=0,
                attempts_remaining=0
            )

        # Check retry policy for this failure type
        policy = self.RETRY_POLICIES.get(failure_type, RetryPolicy.RETRY)

        if policy == RetryPolicy.NO_RETRY:
            return RetryDecision(
                should_retry=False,
                reason=f"Failure type '{failure_type}' requires manual intervention",
                backoff_seconds=0,
                attempts_remaining=0
            )

        # Calculate backoff
        backoff = self._calculate_backoff(attempt)

        # Log retry decision
        self._log_retry(
            prd_id=prd_id,
            story_id=story_id,
            attempt=attempt,
            failure_type=failure_type,
            error_message=error_message,
            backoff_seconds=backoff,
            will_retry=True
        )

        # Increment retry count
        self._increment_retry_count(prd_id)

        return RetryDecision(
            should_retry=True,
            reason=f"Transient failure, retrying with backoff",
            backoff_seconds=backoff,
            attempts_remaining=self.max_retries - attempt - 1
        )

    def record_no_retry(
        self,
        prd_id: str,
        failure_type: str,
        reason: str,
        error_message: str = "",
        story_id: Optional[str] = None
    ) -> None:
        """
        Record that a failure will NOT be retried

        Args:
            prd_id: PRD identifier
            failure_type: Type of failure
            reason: Reason for not retrying
            error_message: Error message
            story_id: Story ID (if applicable)
        """
        attempt = self._get_retry_count(prd_id)

        self._log_retry(
            prd_id=prd_id,
            story_id=story_id,
            attempt=attempt,
            failure_type=failure_type,
            error_message=error_message,
            backoff_seconds=0,
            will_retry=False
        )

    def reset_retry_count(self, prd_id: str) -> None:
        """Reset retry count for a PRD (e.g., after successful completion)"""
        if prd_id in self._retry_counts:
            del self._retry_counts[prd_id]

    def get_retry_count(self, prd_id: str) -> int:
        """Get current retry count for a PRD"""
        return self._get_retry_count(prd_id)

    def get_retry_stats(self) -> Dict[str, Any]:
        """
        Get retry statistics

        Returns:
            Statistics about retries
        """
        if not self.retries_log.exists():
            return {
                'total_retries': 0,
                'by_prd': {},
                'by_failure_type': {},
                'recent': []
            }

        retries = []
        with open(self.retries_log) as f:
            for line in f:
                if line.strip():
                    retries.append(json.loads(line))

        by_prd = {}
        by_type = {}
        for retry in retries:
            if retry['will_retry']:
                prd = retry['prd_id']
                by_prd[prd] = by_prd.get(prd, 0) + 1

                ftype = retry['failure_type']
                by_type[ftype] = by_type.get(ftype, 0) + 1

        return {
            'total_retries': len([r for r in retries if r['will_retry']]),
            'by_prd': by_prd,
            'by_failure_type': by_type,
            'recent': list(reversed(retries))[-10:]
        }

    def _calculate_backoff(self, attempt: int) -> float:
        """Calculate exponential backoff in seconds"""
        return self.base_backoff_seconds * (self.backoff_multiplier ** attempt)

    def _get_retry_count(self, prd_id: str) -> int:
        """Get current retry count from memory"""
        return self._retry_counts.get(prd_id, 0)

    def _increment_retry_count(self, prd_id: str) -> None:
        """Increment retry count"""
        self._retry_counts[prd_id] = self._get_retry_count(prd_id) + 1

    def _log_retry(
        self,
        prd_id: str,
        attempt: int,
        failure_type: str,
        error_message: str,
        backoff_seconds: float,
        will_retry: bool,
        story_id: Optional[str] = None
    ) -> None:
        """Log retry attempt"""
        record = RetryRecord(
            timestamp=datetime.utcnow().isoformat() + "Z",
            prd_id=prd_id,
            story_id=story_id,
            attempt=attempt,
            failure_type=failure_type,
            error_message=error_message,
            backoff_seconds=backoff_seconds,
            will_retry=will_retry
        )

        with open(self.retries_log, 'a') as f:
            f.write(json.dumps(asdict(record)) + '\n')


def load_retry_config(config_file: Path) -> Dict[str, Any]:
    """
    Load retry configuration from YAML config file

    Args:
        config_file: Path to config.yaml

    Returns:
        Retry configuration dictionary
    """
    try:
        import yaml
        with open(config_file) as f:
            config = yaml.safe_load(f)
            return config.get('retry', {})
    except Exception:
        # Return defaults if config doesn't exist or can't be parsed
        return {
            'max_retries': 3,
            'backoff_multiplier': 2.0,
            'base_backoff_seconds': 60.0
        }


if __name__ == '__main__':
    # CLI interface
    import argparse

    parser = argparse.ArgumentParser(description='Manage retry logic')
    parser.add_argument('--stats', action='store_true', help='Show retry statistics')
    parser.add_argument('--check', metavar='PRD_ID', help='Check retry count for PRD')
    parser.add_argument('--reset', metavar='PRD_ID', help='Reset retry count for PRD')

    args = parser.parse_args()

    handler = RetryHandler()

    if args.stats:
        stats = handler.get_retry_stats()
        print(json.dumps(stats, indent=2))
    elif args.check:
        count = handler.get_retry_count(args.check)
        print(f"Retry count for {args.check}: {count}")
    elif args.reset:
        handler.reset_retry_count(args.reset)
        print(f"Reset retry count for {args.reset}")
    else:
        parser.print_help()
