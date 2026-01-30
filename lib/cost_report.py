#!/usr/bin/env python3
"""
Cost Report Generator

Generates cost comparison reports from provider usage logs.
Shows actual costs, savings vs baseline, provider breakdown, and trends.

Usage:
    python3 lib/cost_report.py report --days 7
    python3 lib/cost_report.py report --days 30 --json
    python3 lib/cost_report.py summary
    python3 lib/cost_report.py provider-breakdown --provider litellm
"""

import sys
import os
import json
import argparse
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict
from collections import defaultdict


@dataclass
class ProviderUsageEntry:
    """Provider usage log entry"""
    timestamp: str
    story_id: str
    iteration: int
    provider: str
    model: str
    complexity: int
    input_tokens: int
    output_tokens: int
    cost_usd: float
    latency_ms: float
    success: bool
    fallback_used: bool
    error: Optional[str] = None


@dataclass
class ProviderStats:
    """Statistics for a provider"""
    provider: str
    requests: int
    successful_requests: int
    failed_requests: int
    total_cost: float
    total_input_tokens: int
    total_output_tokens: int
    avg_latency_ms: float
    success_rate: float
    fallback_used_count: int


@dataclass
class CostReport:
    """Cost comparison report"""
    period_days: int
    start_date: str
    end_date: str
    total_requests: int
    successful_requests: int
    failed_requests: int
    total_cost: float
    baseline_cost: float  # Cost if all requests used Opus
    savings: float
    savings_percent: float
    provider_stats: List[ProviderStats]
    avg_latency_ms: float
    overall_success_rate: float


class CostReportGenerator:
    """
    Generates cost reports from provider usage logs.
    """

    # Baseline pricing (Claude Opus)
    BASELINE_INPUT_COST_PER_1K = 15.00
    BASELINE_OUTPUT_COST_PER_1K = 75.00

    def __init__(self, log_path: Optional[str] = None):
        """
        Initialize cost report generator.

        Args:
            log_path: Path to provider_usage.jsonl (optional)
        """
        self.log_path = log_path or ".claude-loop/logs/provider_usage.jsonl"

    def load_entries(self, days: Optional[int] = None) -> List[ProviderUsageEntry]:
        """
        Load provider usage entries from log file.

        Args:
            days: Only load entries from last N days (optional)

        Returns:
            List of ProviderUsageEntry objects
        """
        if not os.path.exists(self.log_path):
            return []

        entries = []
        cutoff_date = None

        if days:
            # Use timezone-aware datetime
            from datetime import timezone
            cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)

        with open(self.log_path, 'r') as f:
            for line in f:
                if not line.strip():
                    continue

                try:
                    data = json.loads(line)

                    # Parse timestamp
                    timestamp = datetime.fromisoformat(data['timestamp'].replace('Z', '+00:00'))

                    # Filter by date if specified
                    if cutoff_date and timestamp < cutoff_date:
                        continue

                    entry = ProviderUsageEntry(
                        timestamp=data['timestamp'],
                        story_id=data.get('story_id', ''),
                        iteration=data.get('iteration', 0),
                        provider=data.get('provider', ''),
                        model=data.get('model', ''),
                        complexity=data.get('complexity', 0),
                        input_tokens=data.get('input_tokens', 0),
                        output_tokens=data.get('output_tokens', 0),
                        cost_usd=data.get('cost_usd', 0.0),
                        latency_ms=data.get('latency_ms', 0.0),
                        success=data.get('success', True),
                        fallback_used=data.get('fallback_used', False),
                        error=data.get('error')
                    )

                    entries.append(entry)

                except (json.JSONDecodeError, KeyError, ValueError) as e:
                    print(f"Warning: Skipping malformed log entry: {e}", file=sys.stderr)
                    continue

        return entries

    def generate_report(self, days: Optional[int] = None) -> CostReport:
        """
        Generate cost comparison report.

        Args:
            days: Report period in days (default: all time)

        Returns:
            CostReport object
        """
        entries = self.load_entries(days)

        if not entries:
            # Return empty report
            return CostReport(
                period_days=days or 0,
                start_date="",
                end_date="",
                total_requests=0,
                successful_requests=0,
                failed_requests=0,
                total_cost=0.0,
                baseline_cost=0.0,
                savings=0.0,
                savings_percent=0.0,
                provider_stats=[],
                avg_latency_ms=0.0,
                overall_success_rate=0.0
            )

        # Calculate date range
        timestamps = [datetime.fromisoformat(e.timestamp.replace('Z', '+00:00')) for e in entries]
        start_date = min(timestamps).isoformat()
        end_date = max(timestamps).isoformat()

        # Calculate overall stats
        total_requests = len(entries)
        successful_requests = sum(1 for e in entries if e.success)
        failed_requests = total_requests - successful_requests
        total_cost = sum(e.cost_usd for e in entries)

        # Calculate baseline cost (if all requests used Opus)
        baseline_cost = sum(
            self._calculate_baseline_cost(e.input_tokens, e.output_tokens)
            for e in entries
        )

        # Calculate savings
        savings = baseline_cost - total_cost
        savings_percent = (savings / baseline_cost * 100) if baseline_cost > 0 else 0.0

        # Calculate average latency
        successful_entries = [e for e in entries if e.success]
        avg_latency_ms = (
            sum(e.latency_ms for e in successful_entries) / len(successful_entries)
            if successful_entries else 0.0
        )

        # Calculate overall success rate
        overall_success_rate = (successful_requests / total_requests * 100) if total_requests > 0 else 0.0

        # Calculate provider stats
        provider_stats = self._calculate_provider_stats(entries)

        return CostReport(
            period_days=days or 0,
            start_date=start_date,
            end_date=end_date,
            total_requests=total_requests,
            successful_requests=successful_requests,
            failed_requests=failed_requests,
            total_cost=total_cost,
            baseline_cost=baseline_cost,
            savings=savings,
            savings_percent=savings_percent,
            provider_stats=provider_stats,
            avg_latency_ms=avg_latency_ms,
            overall_success_rate=overall_success_rate
        )

    def _calculate_baseline_cost(self, input_tokens: int, output_tokens: int) -> float:
        """Calculate cost if request used baseline (Opus) pricing"""
        input_cost = (input_tokens / 1000) * self.BASELINE_INPUT_COST_PER_1K
        output_cost = (output_tokens / 1000) * self.BASELINE_OUTPUT_COST_PER_1K
        return input_cost + output_cost

    def _calculate_provider_stats(self, entries: List[ProviderUsageEntry]) -> List[ProviderStats]:
        """Calculate statistics per provider"""
        # Group entries by provider
        by_provider = defaultdict(list)
        for entry in entries:
            by_provider[entry.provider].append(entry)

        # Calculate stats for each provider
        stats = []

        for provider, provider_entries in by_provider.items():
            successful = [e for e in provider_entries if e.success]
            failed = [e for e in provider_entries if not e.success]

            provider_stat = ProviderStats(
                provider=provider,
                requests=len(provider_entries),
                successful_requests=len(successful),
                failed_requests=len(failed),
                total_cost=sum(e.cost_usd for e in provider_entries),
                total_input_tokens=sum(e.input_tokens for e in provider_entries),
                total_output_tokens=sum(e.output_tokens for e in provider_entries),
                avg_latency_ms=(
                    sum(e.latency_ms for e in successful) / len(successful)
                    if successful else 0.0
                ),
                success_rate=(
                    len(successful) / len(provider_entries) * 100
                    if provider_entries else 0.0
                ),
                fallback_used_count=sum(1 for e in provider_entries if e.fallback_used)
            )

            stats.append(provider_stat)

        # Sort by total cost (descending)
        stats.sort(key=lambda s: s.total_cost, reverse=True)

        return stats

    def print_report(self, report: CostReport, verbose: bool = False):
        """Print formatted cost report to stdout"""
        print("\n" + "=" * 80)
        print("Cost Analysis Report")
        print("=" * 80)

        # Period
        if report.period_days > 0:
            print(f"Period: Last {report.period_days} days")
        else:
            print("Period: All time")

        if report.start_date and report.end_date:
            print(f"Date range: {report.start_date} to {report.end_date}")

        print()

        # Overall stats
        print(f"Total Requests: {report.total_requests}")
        print(f"Successful: {report.successful_requests} ({report.overall_success_rate:.1f}%)")
        print(f"Failed: {report.failed_requests}")
        print()

        # Provider usage
        print("Provider Usage:")
        print("-" * 80)

        for stat in report.provider_stats:
            percent = (stat.total_cost / report.total_cost * 100) if report.total_cost > 0 else 0
            fallback_note = f" ({stat.fallback_used_count} fallback)" if stat.fallback_used_count > 0 else ""
            print(f"- {stat.provider:<25} "
                  f"{stat.requests:>4} requests, "
                  f"${stat.total_cost:>8.2f} ({percent:>5.1f}%)"
                  f"{fallback_note}")

            if verbose:
                print(f"  └─ Success rate: {stat.success_rate:.1f}%, "
                      f"Avg latency: {stat.avg_latency_ms:.0f}ms, "
                      f"Tokens: {stat.total_input_tokens:,}in/{stat.total_output_tokens:,}out")

        print()

        # Cost comparison
        print("Cost Comparison:")
        print("-" * 80)
        print(f"Actual total:       ${report.total_cost:>10.2f}")
        print(f"If all Opus:        ${report.baseline_cost:>10.2f}")
        print(f"Savings:            ${report.savings:>10.2f} ({report.savings_percent:.1f}% reduction)")
        print()

        # Performance
        print(f"Avg latency: {report.avg_latency_ms:.0f}ms")
        print(f"Success rate: {report.overall_success_rate:.1f}%")
        print("=" * 80)
        print()

    def print_summary(self):
        """Print quick summary"""
        report = self.generate_report(days=7)

        if report.total_requests == 0:
            print("No provider usage data found.")
            return

        print(f"\nLast 7 days: {report.total_requests} requests, "
              f"${report.total_cost:.2f} spent, "
              f"${report.savings:.2f} saved ({report.savings_percent:.0f}%)")

    def provider_breakdown(self, provider: str, days: Optional[int] = None):
        """Print detailed breakdown for a specific provider"""
        entries = self.load_entries(days)
        provider_entries = [e for e in entries if e.provider == provider]

        if not provider_entries:
            print(f"No data found for provider: {provider}")
            return

        print(f"\nProvider: {provider}")
        print("=" * 80)
        print(f"Total requests: {len(provider_entries)}")
        print(f"Success rate: {sum(1 for e in provider_entries if e.success) / len(provider_entries) * 100:.1f}%")
        print(f"Total cost: ${sum(e.cost_usd for e in provider_entries):.2f}")
        print(f"Avg latency: {sum(e.latency_ms for e in provider_entries if e.success) / sum(1 for e in provider_entries if e.success):.0f}ms")
        print()

        # Model breakdown
        by_model = defaultdict(list)
        for entry in provider_entries:
            by_model[entry.model].append(entry)

        print("Model Breakdown:")
        print("-" * 80)
        for model, model_entries in sorted(by_model.items(), key=lambda x: len(x[1]), reverse=True):
            print(f"- {model:<35} {len(model_entries):>4} requests, "
                  f"${sum(e.cost_usd for e in model_entries):>8.2f}")

        print()


def main():
    """CLI interface for cost reporting"""
    parser = argparse.ArgumentParser(description="LLM Cost Report Generator")

    subparsers = parser.add_subparsers(dest='command', help='Commands')

    # report command
    report_parser = subparsers.add_parser('report', help='Generate cost report')
    report_parser.add_argument('--days', type=int,
                              help='Report period in days (default: all time)')
    report_parser.add_argument('--json', action='store_true',
                              help='Output as JSON')
    report_parser.add_argument('--verbose', action='store_true',
                              help='Show detailed provider stats')

    # summary command
    summary_parser = subparsers.add_parser('summary', help='Quick summary')

    # provider-breakdown command
    breakdown_parser = subparsers.add_parser('provider-breakdown',
                                            help='Detailed breakdown for provider')
    breakdown_parser.add_argument('--provider', type=str, required=True,
                                 help='Provider name')
    breakdown_parser.add_argument('--days', type=int,
                                 help='Period in days (default: all time)')

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    generator = CostReportGenerator()

    if args.command == 'report':
        report = generator.generate_report(days=args.days)

        if args.json:
            # Convert to dict and handle dataclasses
            report_dict = asdict(report)
            print(json.dumps(report_dict, indent=2))
        else:
            generator.print_report(report, verbose=args.verbose)

    elif args.command == 'summary':
        generator.print_summary()

    elif args.command == 'provider-breakdown':
        generator.provider_breakdown(args.provider, args.days)


if __name__ == '__main__':
    main()
