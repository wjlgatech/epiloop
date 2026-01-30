#!/usr/bin/env python3
"""
Cost Tracking Dashboard for Multi-LLM Support

Tracks and displays costs across all LLM providers with budget alerts
and aggregation capabilities.
"""

import sqlite3
import json
import os
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, List, Any


@dataclass
class CostEntry:
    """Individual cost entry for a request"""
    id: Optional[int] = None
    timestamp: str = ""
    provider: str = ""
    model: str = ""
    project: str = ""
    input_tokens: int = 0
    output_tokens: int = 0
    cost: float = 0.0
    story_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return asdict(self)


@dataclass
class BudgetConfig:
    """Budget configuration"""
    period: str = "month"  # day, week, month
    limit: float = 0.0
    warn_threshold: float = 0.8  # 80%
    stop_threshold: float = 1.0  # 100%

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return asdict(self)


@dataclass
class AggregatedCost:
    """Aggregated cost summary"""
    period: str
    group_by: str
    group_value: str
    total_cost: float
    total_input_tokens: int
    total_output_tokens: int
    request_count: int

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return asdict(self)


class CostTracker:
    """
    Cost tracker for multi-LLM usage with SQLite persistence,
    budget alerts, and aggregation.
    """

    def __init__(self, db_path: Optional[str] = None):
        """
        Initialize cost tracker

        Args:
            db_path: Path to SQLite database (default: ~/.claude-loop/costs.db)
        """
        if db_path is None:
            home = os.path.expanduser("~")
            claude_loop_dir = os.path.join(home, ".claude-loop")
            os.makedirs(claude_loop_dir, exist_ok=True)
            db_path = os.path.join(claude_loop_dir, "costs.db")

        self.db_path = db_path
        self._init_database()

    def _init_database(self) -> None:
        """Initialize database schema"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Create costs table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS costs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                provider TEXT NOT NULL,
                model TEXT NOT NULL,
                project TEXT NOT NULL,
                input_tokens INTEGER NOT NULL,
                output_tokens INTEGER NOT NULL,
                cost REAL NOT NULL,
                story_id TEXT
            )
        """)

        # Create index on timestamp for faster queries
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_timestamp ON costs(timestamp)
        """)

        # Create index on provider for aggregation
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_provider ON costs(provider)
        """)

        # Create budget table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS budget (
                period TEXT PRIMARY KEY,
                limit_amount REAL NOT NULL,
                warn_threshold REAL NOT NULL,
                stop_threshold REAL NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)

        conn.commit()
        conn.close()

    def track_request(
        self,
        provider: str,
        model: str,
        input_tokens: int,
        output_tokens: int,
        cost: float,
        project: str = "default",
        story_id: Optional[str] = None
    ) -> CostEntry:
        """
        Track a single request

        Args:
            provider: Provider name (openai, gemini, deepseek, etc.)
            model: Model name
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens
            cost: Cost in USD
            project: Project name
            story_id: Optional story ID

        Returns:
            CostEntry with ID assigned
        """
        timestamp = datetime.now(timezone.utc).isoformat()

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO costs (timestamp, provider, model, project, input_tokens, output_tokens, cost, story_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (timestamp, provider, model, project, input_tokens, output_tokens, cost, story_id))

        entry_id = cursor.lastrowid
        conn.commit()
        conn.close()

        return CostEntry(
            id=entry_id,
            timestamp=timestamp,
            provider=provider,
            model=model,
            project=project,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost=cost,
            story_id=story_id
        )

    def aggregate_by(
        self,
        group_by: str,
        period: str = "all",
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> List[AggregatedCost]:
        """
        Aggregate costs by dimension

        Args:
            group_by: Dimension to group by (provider, model, project, day, week, month)
            period: Time period (day, week, month, all)
            start_date: Optional start date filter (ISO format)
            end_date: Optional end date filter (ISO format)

        Returns:
            List of aggregated cost summaries
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Build WHERE clause for date filtering
        where_clauses = []
        params = []

        if period != "all":
            # Calculate start date based on period
            now = datetime.now(timezone.utc)
            if period == "day":
                start = now - timedelta(days=1)
            elif period == "week":
                start = now - timedelta(weeks=1)
            elif period == "month":
                start = now - timedelta(days=30)
            else:
                raise ValueError(f"Invalid period: {period}")

            where_clauses.append("timestamp >= ?")
            params.append(start.isoformat())

        if start_date:
            where_clauses.append("timestamp >= ?")
            params.append(start_date)

        if end_date:
            where_clauses.append("timestamp <= ?")
            params.append(end_date)

        where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""

        # Build GROUP BY clause
        if group_by in ["provider", "model", "project"]:
            group_col = group_by
        elif group_by == "day":
            group_col = "DATE(timestamp)"
        elif group_by == "week":
            group_col = "strftime('%Y-%W', timestamp)"
        elif group_by == "month":
            group_col = "strftime('%Y-%m', timestamp)"
        else:
            raise ValueError(f"Invalid group_by: {group_by}")

        query = f"""
            SELECT
                {group_col} as group_value,
                SUM(cost) as total_cost,
                SUM(input_tokens) as total_input_tokens,
                SUM(output_tokens) as total_output_tokens,
                COUNT(*) as request_count
            FROM costs
            {where_sql}
            GROUP BY {group_col}
            ORDER BY total_cost DESC
        """

        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()

        return [
            AggregatedCost(
                period=period,
                group_by=group_by,
                group_value=str(row[0]),
                total_cost=row[1],
                total_input_tokens=row[2],
                total_output_tokens=row[3],
                request_count=row[4]
            )
            for row in rows
        ]

    def set_budget(self, period: str, limit: float, warn_threshold: float = 0.8, stop_threshold: float = 1.0) -> None:
        """
        Set budget limit for a period

        Args:
            period: Time period (day, week, month)
            limit: Budget limit in USD
            warn_threshold: Warning threshold (0.0-1.0)
            stop_threshold: Stop threshold (0.0-1.0)
        """
        if period not in ["day", "week", "month"]:
            raise ValueError(f"Invalid period: {period}. Must be day, week, or month")

        if warn_threshold < 0 or warn_threshold > 1:
            raise ValueError("warn_threshold must be between 0 and 1")

        if stop_threshold < 0 or stop_threshold > 1:
            raise ValueError("stop_threshold must be between 0 and 1")

        updated_at = datetime.now(timezone.utc).isoformat()

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            INSERT OR REPLACE INTO budget (period, limit_amount, warn_threshold, stop_threshold, updated_at)
            VALUES (?, ?, ?, ?, ?)
        """, (period, limit, warn_threshold, stop_threshold, updated_at))

        conn.commit()
        conn.close()

    def get_budget(self, period: str) -> Optional[BudgetConfig]:
        """
        Get budget configuration for a period

        Args:
            period: Time period (day, week, month)

        Returns:
            BudgetConfig or None if not set
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT period, limit_amount, warn_threshold, stop_threshold
            FROM budget
            WHERE period = ?
        """, (period,))

        row = cursor.fetchone()
        conn.close()

        if not row:
            return None

        return BudgetConfig(
            period=row[0],
            limit=row[1],
            warn_threshold=row[2],
            stop_threshold=row[3]
        )

    def check_budget(self, period: str) -> Dict[str, Any]:
        """
        Check budget status for a period

        Args:
            period: Time period (day, week, month)

        Returns:
            Dictionary with budget status:
            {
                "period": "month",
                "limit": 100.0,
                "spent": 75.0,
                "remaining": 25.0,
                "percentage": 75.0,
                "status": "warning|ok|exceeded",
                "warn_threshold": 0.8,
                "stop_threshold": 1.0
            }
        """
        budget = self.get_budget(period)

        if not budget:
            return {
                "period": period,
                "limit": None,
                "spent": 0.0,
                "remaining": None,
                "percentage": 0.0,
                "status": "no_budget",
                "warn_threshold": None,
                "stop_threshold": None
            }

        # Calculate spent in period
        aggregated = self.aggregate_by("provider", period=period)
        spent = sum(agg.total_cost for agg in aggregated)

        remaining = budget.limit - spent
        percentage = (spent / budget.limit * 100) if budget.limit > 0 else 0

        # Determine status
        if spent >= budget.limit * budget.stop_threshold:
            status = "exceeded"
        elif spent >= budget.limit * budget.warn_threshold:
            status = "warning"
        else:
            status = "ok"

        return {
            "period": period,
            "limit": budget.limit,
            "spent": spent,
            "remaining": remaining,
            "percentage": percentage,
            "status": status,
            "warn_threshold": budget.warn_threshold,
            "stop_threshold": budget.stop_threshold
        }

    def export_data(self, start_date: Optional[str] = None, end_date: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Export cost data as list of dictionaries

        Args:
            start_date: Optional start date filter (ISO format)
            end_date: Optional end date filter (ISO format)

        Returns:
            List of cost entries as dictionaries
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        where_clauses = []
        params = []

        if start_date:
            where_clauses.append("timestamp >= ?")
            params.append(start_date)

        if end_date:
            where_clauses.append("timestamp <= ?")
            params.append(end_date)

        where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""

        query = f"""
            SELECT id, timestamp, provider, model, project, input_tokens, output_tokens, cost, story_id
            FROM costs
            {where_sql}
            ORDER BY timestamp DESC
        """

        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()

        return [
            {
                "id": row[0],
                "timestamp": row[1],
                "provider": row[2],
                "model": row[3],
                "project": row[4],
                "input_tokens": row[5],
                "output_tokens": row[6],
                "cost": row[7],
                "story_id": row[8]
            }
            for row in rows
        ]


def generate_ascii_chart(data: List[AggregatedCost], width: int = 50) -> str:
    """
    Generate ASCII bar chart from aggregated cost data

    Args:
        data: List of aggregated costs
        width: Chart width in characters

    Returns:
        ASCII chart as string
    """
    if not data:
        return "No data to display"

    max_cost = max(item.total_cost for item in data)
    if max_cost == 0:
        return "No costs to display"

    chart = []
    chart.append(f"\n{'='*60}")
    chart.append(f"Cost Distribution by {data[0].group_by.capitalize()}")
    chart.append(f"{'='*60}")

    for item in data:
        bar_length = int((item.total_cost / max_cost) * width)
        bar = "█" * bar_length
        label = item.group_value[:20].ljust(20)
        cost_str = f"${item.total_cost:.4f}".rjust(12)
        requests = f"({item.request_count} req)".rjust(12)
        chart.append(f"{label} {bar} {cost_str} {requests}")

    chart.append(f"{'='*60}")
    total_cost = sum(item.total_cost for item in data)
    total_requests = sum(item.request_count for item in data)
    chart.append(f"Total: ${total_cost:.4f} ({total_requests} requests)")
    chart.append(f"{'='*60}\n")

    return "\n".join(chart)


def main():
    """CLI interface for cost tracker"""
    import argparse

    parser = argparse.ArgumentParser(description="Cost Tracking Dashboard for Multi-LLM Support")
    subparsers = parser.add_subparsers(dest="command", help="Command to execute")

    # report command
    report_parser = subparsers.add_parser("report", help="Generate cost report")
    report_parser.add_argument("--period", choices=["day", "week", "month", "all"], default="all", help="Time period")
    report_parser.add_argument("--by", dest="group_by", choices=["provider", "model", "project", "day", "week", "month"], default="provider", help="Group by dimension")
    report_parser.add_argument("--json", action="store_true", help="Output as JSON")
    report_parser.add_argument("--start-date", help="Start date (ISO format)")
    report_parser.add_argument("--end-date", help="End date (ISO format)")

    # set-budget command
    budget_parser = subparsers.add_parser("set-budget", help="Set budget limit")
    budget_parser.add_argument("amount", type=float, help="Budget limit in USD")
    budget_parser.add_argument("--period", choices=["day", "week", "month"], default="month", help="Budget period")
    budget_parser.add_argument("--warn", type=float, default=0.8, help="Warning threshold (0.0-1.0)")
    budget_parser.add_argument("--stop", type=float, default=1.0, help="Stop threshold (0.0-1.0)")

    # status command
    status_parser = subparsers.add_parser("status", help="Check budget status")
    status_parser.add_argument("--period", choices=["day", "week", "month"], default="month", help="Budget period")
    status_parser.add_argument("--json", action="store_true", help="Output as JSON")

    # export command
    export_parser = subparsers.add_parser("export", help="Export cost data")
    export_parser.add_argument("--start-date", help="Start date (ISO format)")
    export_parser.add_argument("--end-date", help="End date (ISO format)")
    export_parser.add_argument("--output", help="Output file (default: stdout)")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    tracker = CostTracker()

    if args.command == "report":
        data = tracker.aggregate_by(
            group_by=args.group_by,
            period=args.period,
            start_date=args.start_date,
            end_date=args.end_date
        )

        if args.json:
            print(json.dumps([item.to_dict() for item in data], indent=2))
        else:
            print(generate_ascii_chart(data))

    elif args.command == "set-budget":
        tracker.set_budget(args.period, args.amount, args.warn, args.stop)
        print(f"Budget set: ${args.amount} per {args.period}")
        print(f"Warning at {args.warn*100}%, Stop at {args.stop*100}%")

    elif args.command == "status":
        status = tracker.check_budget(args.period)

        if args.json:
            print(json.dumps(status, indent=2))
        else:
            if status["status"] == "no_budget":
                print(f"No budget set for {args.period}")
            else:
                print(f"\n{'='*60}")
                print(f"Budget Status - {args.period.capitalize()}")
                print(f"{'='*60}")
                print(f"Limit:     ${status['limit']:.2f}")
                print(f"Spent:     ${status['spent']:.2f} ({status['percentage']:.1f}%)")
                print(f"Remaining: ${status['remaining']:.2f}")
                print(f"Status:    {status['status'].upper()}")

                if status['status'] == 'exceeded':
                    print(f"\n⛔ BUDGET EXCEEDED! Stop threshold reached.")
                elif status['status'] == 'warning':
                    print(f"\n⚠️  WARNING! {status['warn_threshold']*100}% threshold reached.")
                else:
                    print(f"\n✓ Budget OK")
                print(f"{'='*60}\n")

    elif args.command == "export":
        data = tracker.export_data(args.start_date, args.end_date)
        json_output = json.dumps(data, indent=2)

        if args.output:
            with open(args.output, 'w') as f:
                f.write(json_output)
            print(f"Exported {len(data)} entries to {args.output}")
        else:
            print(json_output)


if __name__ == "__main__":
    main()
