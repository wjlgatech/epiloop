#!/usr/bin/env python3
"""
Checkpoint Logger - Audit logging for human checkpoints

Provides persistent logging of all checkpoint decisions for audit,
compliance, and analysis purposes.

Usage:
    from checkpoint_logger import CheckpointLogger

    logger = CheckpointLogger()
    logger.log_decision(decision, summary, feedback)
    history = logger.query_decisions(research_id="RES-123")
"""

import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Optional, Any
from enum import Enum


class CheckpointLogger:
    """
    Audit logger for checkpoint decisions.

    Stores all checkpoint decisions with timestamps, summaries,
    and user feedback for audit trail.
    """

    def __init__(self, log_path: Optional[str] = None):
        """
        Initialize checkpoint logger.

        Args:
            log_path: Path to log file (defaults to data/checkpoint_log.json)
        """
        if log_path:
            self.log_path = Path(log_path)
        else:
            # Default to data directory in project root
            script_dir = Path(__file__).parent
            project_root = script_dir.parent
            self.log_path = project_root / "data" / "checkpoint_log.json"

        # Ensure directory exists
        self.log_path.parent.mkdir(parents=True, exist_ok=True)

        # Initialize log file if doesn't exist
        if not self.log_path.exists():
            self._initialize_log()

    def _initialize_log(self) -> None:
        """Initialize empty log file"""
        initial_data = {
            "version": "1.0",
            "created_at": datetime.utcnow().isoformat() + 'Z',
            "decisions": []
        }
        self._write_log(initial_data)

    def _read_log(self) -> Dict[str, Any]:
        """Read log file"""
        try:
            with open(self.log_path, 'r') as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            self._initialize_log()
            with open(self.log_path, 'r') as f:
                return json.load(f)

    def _write_log(self, data: Dict[str, Any]) -> None:
        """Write log file"""
        with open(self.log_path, 'w') as f:
            json.dump(data, f, indent=2)

    def log_decision(self, decision: 'Enum', summary: Any,
                     feedback: Optional[str] = None) -> str:
        """
        Log a checkpoint decision.

        Args:
            decision: The decision made (CheckpointDecision enum)
            summary: CheckpointSummary or dict with summary data
            feedback: Optional user feedback or additional data

        Returns:
            Log entry ID
        """
        log_data = self._read_log()

        # Generate entry ID
        entry_id = f"LOG-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}-{len(log_data['decisions']) + 1:04d}"

        # Convert summary to dict if needed
        if hasattr(summary, 'to_dict'):
            summary_dict = summary.to_dict()
        elif isinstance(summary, dict):
            summary_dict = summary
        else:
            summary_dict = {'raw': str(summary)}

        # Create log entry
        entry = {
            "id": entry_id,
            "timestamp": datetime.utcnow().isoformat() + 'Z',
            "research_id": summary_dict.get('research_id', 'UNKNOWN'),
            "decision": decision.value if hasattr(decision, 'value') else str(decision),
            "summary": summary_dict,
            "feedback": feedback,
            "metadata": {
                "domain": summary_dict.get('domain', 'general'),
                "confidence": summary_dict.get('confidence', 0),
                "risks_count": len(summary_dict.get('risks', [])),
                "sources_count": summary_dict.get('sources_count', 0)
            }
        }

        log_data['decisions'].append(entry)
        log_data['last_updated'] = datetime.utcnow().isoformat() + 'Z'

        self._write_log(log_data)

        return entry_id

    def log_feedback(self, research_id: str, feedback: str,
                     feedback_type: str = "general") -> str:
        """
        Log user feedback for a research session.

        Args:
            research_id: Research ID
            feedback: User feedback text
            feedback_type: Type of feedback (general, quality, accuracy, etc.)

        Returns:
            Feedback entry ID
        """
        log_data = self._read_log()

        entry_id = f"FB-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"

        entry = {
            "id": entry_id,
            "timestamp": datetime.utcnow().isoformat() + 'Z',
            "research_id": research_id,
            "decision": "feedback",
            "summary": None,
            "feedback": feedback,
            "metadata": {
                "feedback_type": feedback_type
            }
        }

        log_data['decisions'].append(entry)
        log_data['last_updated'] = datetime.utcnow().isoformat() + 'Z'

        self._write_log(log_data)

        return entry_id

    def query_decisions(self, research_id: Optional[str] = None,
                        decision_type: Optional[str] = None,
                        domain: Optional[str] = None,
                        since: Optional[datetime] = None,
                        limit: int = 100) -> List[Dict[str, Any]]:
        """
        Query past checkpoint decisions.

        Args:
            research_id: Filter by research ID
            decision_type: Filter by decision type (approve, cancel, etc.)
            domain: Filter by domain (investment, ai-ml, etc.)
            since: Filter for decisions since this datetime
            limit: Maximum number of results

        Returns:
            List of matching decision entries
        """
        log_data = self._read_log()
        decisions = log_data.get('decisions', [])

        # Apply filters
        filtered = []
        for entry in decisions:
            # Research ID filter
            if research_id and entry.get('research_id') != research_id:
                continue

            # Decision type filter
            if decision_type and entry.get('decision') != decision_type:
                continue

            # Domain filter
            metadata = entry.get('metadata', {})
            if domain and metadata.get('domain') != domain:
                continue

            # Time filter
            if since:
                entry_time = datetime.fromisoformat(entry['timestamp'].replace('Z', '+00:00'))
                if entry_time < since.replace(tzinfo=entry_time.tzinfo):
                    continue

            filtered.append(entry)

        # Apply limit (most recent first)
        filtered = sorted(filtered, key=lambda x: x['timestamp'], reverse=True)
        return filtered[:limit]

    def get_decision_by_id(self, entry_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a specific decision by entry ID.

        Args:
            entry_id: Log entry ID

        Returns:
            Decision entry or None if not found
        """
        log_data = self._read_log()

        for entry in log_data.get('decisions', []):
            if entry.get('id') == entry_id:
                return entry

        return None

    def get_stats(self, since: Optional[datetime] = None) -> Dict[str, Any]:
        """
        Get statistics on checkpoint decisions.

        Args:
            since: Only include decisions since this datetime

        Returns:
            Statistics dictionary
        """
        decisions = self.query_decisions(since=since, limit=10000)

        stats = {
            "total_decisions": len(decisions),
            "by_decision": {},
            "by_domain": {},
            "avg_confidence": 0,
            "with_feedback": 0,
            "time_range": {
                "earliest": None,
                "latest": None
            }
        }

        if not decisions:
            return stats

        # Count by decision type
        for entry in decisions:
            decision = entry.get('decision', 'unknown')
            stats['by_decision'][decision] = stats['by_decision'].get(decision, 0) + 1

            domain = entry.get('metadata', {}).get('domain', 'unknown')
            stats['by_domain'][domain] = stats['by_domain'].get(domain, 0) + 1

            if entry.get('feedback'):
                stats['with_feedback'] += 1

        # Calculate average confidence
        confidences = [e.get('metadata', {}).get('confidence', 0) for e in decisions]
        stats['avg_confidence'] = sum(confidences) / len(confidences) if confidences else 0

        # Time range
        timestamps = [e['timestamp'] for e in decisions if 'timestamp' in e]
        if timestamps:
            stats['time_range']['earliest'] = min(timestamps)
            stats['time_range']['latest'] = max(timestamps)

        return stats

    def get_research_history(self, research_id: str) -> List[Dict[str, Any]]:
        """
        Get complete checkpoint history for a research session.

        Args:
            research_id: Research ID

        Returns:
            List of all checkpoint entries for this research
        """
        return self.query_decisions(research_id=research_id, limit=1000)

    def cleanup_old_entries(self, days: int = 90) -> int:
        """
        Clean up log entries older than specified days.

        Args:
            days: Remove entries older than this many days

        Returns:
            Number of entries removed
        """
        log_data = self._read_log()
        cutoff = datetime.utcnow() - timedelta(days=days)

        original_count = len(log_data.get('decisions', []))
        log_data['decisions'] = [
            entry for entry in log_data.get('decisions', [])
            if datetime.fromisoformat(entry['timestamp'].replace('Z', '+00:00')) > cutoff.replace(tzinfo=None)
        ]

        removed = original_count - len(log_data['decisions'])

        if removed > 0:
            log_data['last_cleanup'] = datetime.utcnow().isoformat() + 'Z'
            log_data['entries_removed'] = removed
            self._write_log(log_data)

        return removed

    def export_to_jsonl(self, output_path: str,
                        since: Optional[datetime] = None) -> int:
        """
        Export decisions to JSONL format for analysis.

        Args:
            output_path: Path to output file
            since: Only export decisions since this datetime

        Returns:
            Number of entries exported
        """
        decisions = self.query_decisions(since=since, limit=100000)

        with open(output_path, 'w') as f:
            for entry in decisions:
                f.write(json.dumps(entry) + '\n')

        return len(decisions)


class AuditReport:
    """Generate audit reports from checkpoint logs"""

    def __init__(self, logger: CheckpointLogger):
        """
        Initialize audit report generator.

        Args:
            logger: CheckpointLogger instance
        """
        self.logger = logger

    def generate_summary_report(self, days: int = 30) -> str:
        """
        Generate a summary report of checkpoint activity.

        Args:
            days: Number of days to include

        Returns:
            Formatted report string
        """
        since = datetime.utcnow() - timedelta(days=days)
        stats = self.logger.get_stats(since=since)

        report = []
        report.append("=" * 60)
        report.append("CHECKPOINT AUDIT REPORT")
        report.append(f"Period: Last {days} days")
        report.append(f"Generated: {datetime.utcnow().isoformat()}")
        report.append("=" * 60)
        report.append("")

        report.append(f"Total Decisions: {stats['total_decisions']}")
        report.append(f"Average Confidence: {stats['avg_confidence']:.1f}%")
        report.append(f"Decisions with Feedback: {stats['with_feedback']}")
        report.append("")

        report.append("Decisions by Type:")
        for decision, count in sorted(stats['by_decision'].items()):
            report.append(f"  - {decision}: {count}")
        report.append("")

        report.append("Decisions by Domain:")
        for domain, count in sorted(stats['by_domain'].items()):
            report.append(f"  - {domain}: {count}")
        report.append("")

        if stats['time_range']['earliest']:
            report.append(f"Earliest: {stats['time_range']['earliest']}")
            report.append(f"Latest: {stats['time_range']['latest']}")

        report.append("=" * 60)

        return '\n'.join(report)

    def generate_investment_report(self, days: int = 30) -> str:
        """
        Generate a report focused on investment domain checkpoints.

        Args:
            days: Number of days to include

        Returns:
            Formatted report string
        """
        since = datetime.utcnow() - timedelta(days=days)
        decisions = self.logger.query_decisions(domain='investment', since=since)

        report = []
        report.append("=" * 60)
        report.append("INVESTMENT CHECKPOINT REPORT")
        report.append(f"Period: Last {days} days")
        report.append("=" * 60)
        report.append("")

        if not decisions:
            report.append("No investment checkpoints in this period.")
            return '\n'.join(report)

        report.append(f"Total Investment Checkpoints: {len(decisions)}")
        report.append("")

        # Group by decision
        by_decision = {}
        for entry in decisions:
            d = entry.get('decision', 'unknown')
            by_decision[d] = by_decision.get(d, 0) + 1

        report.append("Decision Distribution:")
        for decision, count in sorted(by_decision.items()):
            pct = (count / len(decisions)) * 100
            report.append(f"  - {decision}: {count} ({pct:.1f}%)")
        report.append("")

        # Risk analysis
        total_risks = sum(e.get('metadata', {}).get('risks_count', 0) for e in decisions)
        avg_risks = total_risks / len(decisions) if decisions else 0
        report.append(f"Average Risks per Checkpoint: {avg_risks:.1f}")

        # Confidence analysis
        confidences = [e.get('metadata', {}).get('confidence', 0) for e in decisions]
        avg_conf = sum(confidences) / len(confidences) if confidences else 0
        low_conf = sum(1 for c in confidences if c < 50)
        report.append(f"Average Confidence: {avg_conf:.1f}%")
        report.append(f"Low Confidence Checkpoints: {low_conf}")

        report.append("")
        report.append("=" * 60)

        return '\n'.join(report)


def main():
    """CLI entry point for checkpoint logger"""
    import argparse

    parser = argparse.ArgumentParser(description='Checkpoint Logger CLI')
    parser.add_argument('--query', action='store_true', help='Query decisions')
    parser.add_argument('--stats', action='store_true', help='Show statistics')
    parser.add_argument('--research-id', help='Filter by research ID')
    parser.add_argument('--domain', help='Filter by domain')
    parser.add_argument('--days', type=int, default=30, help='Days to include')
    parser.add_argument('--report', choices=['summary', 'investment'], help='Generate report')
    parser.add_argument('--export', metavar='FILE', help='Export to JSONL')
    parser.add_argument('--cleanup', type=int, metavar='DAYS', help='Cleanup entries older than N days')

    args = parser.parse_args()

    logger = CheckpointLogger()

    if args.stats:
        since = datetime.utcnow() - timedelta(days=args.days)
        stats = logger.get_stats(since=since)
        print(json.dumps(stats, indent=2))
        return 0

    if args.query:
        since = datetime.utcnow() - timedelta(days=args.days) if args.days else None
        decisions = logger.query_decisions(
            research_id=args.research_id,
            domain=args.domain,
            since=since
        )
        for d in decisions:
            print(f"[{d['timestamp']}] {d['research_id']}: {d['decision']}")
            if d.get('feedback'):
                print(f"  Feedback: {d['feedback']}")
        return 0

    if args.report:
        report_gen = AuditReport(logger)
        if args.report == 'summary':
            print(report_gen.generate_summary_report(days=args.days))
        elif args.report == 'investment':
            print(report_gen.generate_investment_report(days=args.days))
        return 0

    if args.export:
        since = datetime.utcnow() - timedelta(days=args.days) if args.days else None
        count = logger.export_to_jsonl(args.export, since=since)
        print(f"Exported {count} entries to {args.export}")
        return 0

    if args.cleanup:
        removed = logger.cleanup_old_entries(days=args.cleanup)
        print(f"Removed {removed} entries older than {args.cleanup} days")
        return 0

    parser.print_help()
    return 1


if __name__ == '__main__':
    import sys
    sys.exit(main())
