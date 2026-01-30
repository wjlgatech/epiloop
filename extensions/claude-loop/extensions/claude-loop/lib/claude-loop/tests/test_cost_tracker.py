#!/usr/bin/env python3
"""
Unit tests for cost_tracker.py
"""

import unittest
import os
import tempfile
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from lib.cost_tracker import (
    CostTracker,
    CostEntry,
    BudgetConfig,
    AggregatedCost,
    generate_ascii_chart
)


class TestCostTracker(unittest.TestCase):
    """Test CostTracker class"""

    def setUp(self):
        """Set up test database"""
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, "test_costs.db")
        self.tracker = CostTracker(db_path=self.db_path)

    def tearDown(self):
        """Clean up test database"""
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

        # Clean up .claude-loop directory if it exists (from test_init_default_path)
        claude_loop_dir = os.path.join(self.temp_dir, ".claude-loop")
        if os.path.exists(claude_loop_dir):
            costs_db = os.path.join(claude_loop_dir, "costs.db")
            if os.path.exists(costs_db):
                os.remove(costs_db)
            os.rmdir(claude_loop_dir)

        os.rmdir(self.temp_dir)

    def test_init_default_path(self):
        """Test initialization with default path"""
        with patch('os.path.expanduser') as mock_expanduser:
            mock_expanduser.return_value = self.temp_dir
            tracker = CostTracker()
            expected_path = os.path.join(self.temp_dir, ".claude-loop", "costs.db")
            self.assertEqual(tracker.db_path, expected_path)

    def test_database_schema(self):
        """Test database schema creation"""
        import sqlite3
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Check costs table
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='costs'")
        self.assertIsNotNone(cursor.fetchone())

        # Check budget table
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='budget'")
        self.assertIsNotNone(cursor.fetchone())

        # Check indexes
        cursor.execute("SELECT name FROM sqlite_master WHERE type='index' AND name='idx_timestamp'")
        self.assertIsNotNone(cursor.fetchone())

        cursor.execute("SELECT name FROM sqlite_master WHERE type='index' AND name='idx_provider'")
        self.assertIsNotNone(cursor.fetchone())

        conn.close()

    def test_track_request(self):
        """Test tracking a single request"""
        entry = self.tracker.track_request(
            provider="openai",
            model="gpt-4o",
            input_tokens=1000,
            output_tokens=500,
            cost=0.05,
            project="test-project",
            story_id="US-001"
        )

        self.assertIsNotNone(entry.id)
        self.assertEqual(entry.provider, "openai")
        self.assertEqual(entry.model, "gpt-4o")
        self.assertEqual(entry.input_tokens, 1000)
        self.assertEqual(entry.output_tokens, 500)
        self.assertEqual(entry.cost, 0.05)
        self.assertEqual(entry.project, "test-project")
        self.assertEqual(entry.story_id, "US-001")
        self.assertIsNotNone(entry.timestamp)

    def test_track_multiple_requests(self):
        """Test tracking multiple requests"""
        self.tracker.track_request("openai", "gpt-4o", 1000, 500, 0.05)
        self.tracker.track_request("gemini", "gemini-2.0-flash", 2000, 1000, 0.02)
        self.tracker.track_request("deepseek", "deepseek-chat", 3000, 1500, 0.001)

        data = self.tracker.export_data()
        self.assertEqual(len(data), 3)

    def test_aggregate_by_provider(self):
        """Test aggregation by provider"""
        self.tracker.track_request("openai", "gpt-4o", 1000, 500, 0.05)
        self.tracker.track_request("openai", "gpt-4o-mini", 2000, 1000, 0.02)
        self.tracker.track_request("gemini", "gemini-2.0-flash", 3000, 1500, 0.01)

        results = self.tracker.aggregate_by("provider", period="all")

        self.assertEqual(len(results), 2)

        # Check OpenAI aggregation
        openai_result = next(r for r in results if r.group_value == "openai")
        self.assertEqual(openai_result.total_cost, 0.07)
        self.assertEqual(openai_result.total_input_tokens, 3000)
        self.assertEqual(openai_result.total_output_tokens, 1500)
        self.assertEqual(openai_result.request_count, 2)

        # Check Gemini aggregation
        gemini_result = next(r for r in results if r.group_value == "gemini")
        self.assertEqual(gemini_result.total_cost, 0.01)
        self.assertEqual(gemini_result.request_count, 1)

    def test_aggregate_by_model(self):
        """Test aggregation by model"""
        self.tracker.track_request("openai", "gpt-4o", 1000, 500, 0.05)
        self.tracker.track_request("openai", "gpt-4o", 1000, 500, 0.05)
        self.tracker.track_request("openai", "gpt-4o-mini", 2000, 1000, 0.02)

        results = self.tracker.aggregate_by("model", period="all")

        self.assertEqual(len(results), 2)

        gpt4o_result = next(r for r in results if r.group_value == "gpt-4o")
        self.assertEqual(gpt4o_result.total_cost, 0.10)
        self.assertEqual(gpt4o_result.request_count, 2)

    def test_aggregate_by_project(self):
        """Test aggregation by project"""
        self.tracker.track_request("openai", "gpt-4o", 1000, 500, 0.05, project="project-a")
        self.tracker.track_request("openai", "gpt-4o", 1000, 500, 0.05, project="project-a")
        self.tracker.track_request("gemini", "gemini-2.0-flash", 2000, 1000, 0.02, project="project-b")

        results = self.tracker.aggregate_by("project", period="all")

        self.assertEqual(len(results), 2)

        project_a_result = next(r for r in results if r.group_value == "project-a")
        self.assertEqual(project_a_result.total_cost, 0.10)
        self.assertEqual(project_a_result.request_count, 2)

    def test_aggregate_by_day(self):
        """Test aggregation by day"""
        # Use mock to control timestamps
        base_time = datetime.now(timezone.utc)

        with patch('lib.cost_tracker.datetime') as mock_datetime:
            # First day
            mock_datetime.now.return_value = base_time
            self.tracker.track_request("openai", "gpt-4o", 1000, 500, 0.05)

            # Second day
            mock_datetime.now.return_value = base_time + timedelta(days=1)
            self.tracker.track_request("openai", "gpt-4o", 1000, 500, 0.05)

        results = self.tracker.aggregate_by("day", period="all")
        self.assertEqual(len(results), 2)

    def test_aggregate_by_week(self):
        """Test aggregation by week"""
        # Track requests across different weeks
        self.tracker.track_request("openai", "gpt-4o", 1000, 500, 0.05)
        self.tracker.track_request("openai", "gpt-4o", 1000, 500, 0.05)

        results = self.tracker.aggregate_by("week", period="all")
        self.assertGreaterEqual(len(results), 1)

    def test_aggregate_by_month(self):
        """Test aggregation by month"""
        self.tracker.track_request("openai", "gpt-4o", 1000, 500, 0.05)
        self.tracker.track_request("openai", "gpt-4o", 1000, 500, 0.05)

        results = self.tracker.aggregate_by("month", period="all")
        self.assertGreaterEqual(len(results), 1)

    def test_aggregate_with_period_filter(self):
        """Test aggregation with period filter"""
        now = datetime.now(timezone.utc)

        with patch('lib.cost_tracker.datetime') as mock_datetime:
            # Old request (2 days ago)
            mock_datetime.now.return_value = now - timedelta(days=2)
            self.tracker.track_request("openai", "gpt-4o", 1000, 500, 0.05)

            # Recent request (now)
            mock_datetime.now.return_value = now
            self.tracker.track_request("openai", "gpt-4o", 1000, 500, 0.05)

            # Query for last day only
            mock_datetime.now.return_value = now
            results = self.tracker.aggregate_by("provider", period="day")

            # Should only include recent request
            self.assertEqual(len(results), 1)
            self.assertEqual(results[0].total_cost, 0.05)

    def test_aggregate_with_date_range(self):
        """Test aggregation with custom date range"""
        start = datetime(2025, 1, 1, tzinfo=timezone.utc).isoformat()
        end = datetime(2025, 1, 31, tzinfo=timezone.utc).isoformat()

        with patch('lib.cost_tracker.datetime') as mock_datetime:
            # Within range
            mock_datetime.now.return_value = datetime(2025, 1, 15, tzinfo=timezone.utc)
            self.tracker.track_request("openai", "gpt-4o", 1000, 500, 0.05)

            # Outside range
            mock_datetime.now.return_value = datetime(2025, 2, 1, tzinfo=timezone.utc)
            self.tracker.track_request("openai", "gpt-4o", 1000, 500, 0.05)

        results = self.tracker.aggregate_by("provider", start_date=start, end_date=end)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].total_cost, 0.05)

    def test_aggregate_invalid_group_by(self):
        """Test aggregation with invalid group_by"""
        with self.assertRaises(ValueError):
            self.tracker.aggregate_by("invalid")

    def test_aggregate_invalid_period(self):
        """Test aggregation with invalid period"""
        with self.assertRaises(ValueError):
            self.tracker.aggregate_by("provider", period="invalid")

    def test_set_budget(self):
        """Test setting budget"""
        self.tracker.set_budget("month", 100.0, 0.8, 1.0)

        budget = self.tracker.get_budget("month")
        self.assertIsNotNone(budget)
        self.assertEqual(budget.period, "month")
        self.assertEqual(budget.limit, 100.0)
        self.assertEqual(budget.warn_threshold, 0.8)
        self.assertEqual(budget.stop_threshold, 1.0)

    def test_set_budget_invalid_period(self):
        """Test setting budget with invalid period"""
        with self.assertRaises(ValueError):
            self.tracker.set_budget("invalid", 100.0)

    def test_set_budget_invalid_warn_threshold(self):
        """Test setting budget with invalid warn threshold"""
        with self.assertRaises(ValueError):
            self.tracker.set_budget("month", 100.0, warn_threshold=1.5)

    def test_set_budget_invalid_stop_threshold(self):
        """Test setting budget with invalid stop threshold"""
        with self.assertRaises(ValueError):
            self.tracker.set_budget("month", 100.0, stop_threshold=-0.1)

    def test_get_budget_not_set(self):
        """Test getting budget that is not set"""
        budget = self.tracker.get_budget("month")
        self.assertIsNone(budget)

    def test_update_budget(self):
        """Test updating existing budget"""
        self.tracker.set_budget("month", 100.0)
        self.tracker.set_budget("month", 200.0)

        budget = self.tracker.get_budget("month")
        self.assertEqual(budget.limit, 200.0)

    def test_check_budget_ok(self):
        """Test budget check when OK"""
        self.tracker.set_budget("month", 100.0, 0.8, 1.0)
        self.tracker.track_request("openai", "gpt-4o", 1000, 500, 50.0)  # 50% of budget

        status = self.tracker.check_budget("month")

        self.assertEqual(status["status"], "ok")
        self.assertEqual(status["limit"], 100.0)
        self.assertEqual(status["spent"], 50.0)
        self.assertEqual(status["remaining"], 50.0)
        self.assertEqual(status["percentage"], 50.0)

    def test_check_budget_warning(self):
        """Test budget check when at warning threshold"""
        self.tracker.set_budget("month", 100.0, 0.8, 1.0)
        self.tracker.track_request("openai", "gpt-4o", 1000, 500, 85.0)  # 85% of budget

        status = self.tracker.check_budget("month")

        self.assertEqual(status["status"], "warning")
        self.assertEqual(status["spent"], 85.0)
        self.assertGreaterEqual(status["percentage"], 80.0)

    def test_check_budget_exceeded(self):
        """Test budget check when exceeded"""
        self.tracker.set_budget("month", 100.0, 0.8, 1.0)
        self.tracker.track_request("openai", "gpt-4o", 1000, 500, 105.0)  # 105% of budget

        status = self.tracker.check_budget("month")

        self.assertEqual(status["status"], "exceeded")
        self.assertEqual(status["spent"], 105.0)
        self.assertGreaterEqual(status["percentage"], 100.0)

    def test_check_budget_no_budget_set(self):
        """Test budget check when no budget is set"""
        status = self.tracker.check_budget("month")

        self.assertEqual(status["status"], "no_budget")
        self.assertIsNone(status["limit"])
        self.assertIsNone(status["remaining"])

    def test_export_data(self):
        """Test exporting data"""
        self.tracker.track_request("openai", "gpt-4o", 1000, 500, 0.05, story_id="US-001")
        self.tracker.track_request("gemini", "gemini-2.0-flash", 2000, 1000, 0.02, story_id="US-002")

        data = self.tracker.export_data()

        self.assertEqual(len(data), 2)
        self.assertIn("id", data[0])
        self.assertIn("timestamp", data[0])
        self.assertIn("provider", data[0])
        self.assertIn("model", data[0])
        self.assertIn("cost", data[0])
        self.assertIn("story_id", data[0])

    def test_export_data_with_date_range(self):
        """Test exporting data with date range"""
        start = datetime(2025, 1, 1, tzinfo=timezone.utc).isoformat()
        end = datetime(2025, 1, 31, tzinfo=timezone.utc).isoformat()

        with patch('lib.cost_tracker.datetime') as mock_datetime:
            # Within range
            mock_datetime.now.return_value = datetime(2025, 1, 15, tzinfo=timezone.utc)
            self.tracker.track_request("openai", "gpt-4o", 1000, 500, 0.05)

            # Outside range
            mock_datetime.now.return_value = datetime(2025, 2, 1, tzinfo=timezone.utc)
            self.tracker.track_request("openai", "gpt-4o", 1000, 500, 0.05)

        data = self.tracker.export_data(start_date=start, end_date=end)
        self.assertEqual(len(data), 1)


class TestCostEntry(unittest.TestCase):
    """Test CostEntry dataclass"""

    def test_cost_entry_creation(self):
        """Test creating cost entry"""
        entry = CostEntry(
            id=1,
            timestamp="2025-01-01T00:00:00",
            provider="openai",
            model="gpt-4o",
            project="test",
            input_tokens=1000,
            output_tokens=500,
            cost=0.05,
            story_id="US-001"
        )

        self.assertEqual(entry.id, 1)
        self.assertEqual(entry.provider, "openai")
        self.assertEqual(entry.cost, 0.05)

    def test_cost_entry_to_dict(self):
        """Test converting cost entry to dict"""
        entry = CostEntry(
            id=1,
            timestamp="2025-01-01T00:00:00",
            provider="openai",
            model="gpt-4o",
            project="test",
            input_tokens=1000,
            output_tokens=500,
            cost=0.05
        )

        d = entry.to_dict()
        self.assertIsInstance(d, dict)
        self.assertEqual(d["provider"], "openai")
        self.assertEqual(d["cost"], 0.05)


class TestBudgetConfig(unittest.TestCase):
    """Test BudgetConfig dataclass"""

    def test_budget_config_creation(self):
        """Test creating budget config"""
        config = BudgetConfig(
            period="month",
            limit=100.0,
            warn_threshold=0.8,
            stop_threshold=1.0
        )

        self.assertEqual(config.period, "month")
        self.assertEqual(config.limit, 100.0)

    def test_budget_config_to_dict(self):
        """Test converting budget config to dict"""
        config = BudgetConfig(period="month", limit=100.0)
        d = config.to_dict()

        self.assertIsInstance(d, dict)
        self.assertEqual(d["period"], "month")
        self.assertEqual(d["limit"], 100.0)


class TestAggregatedCost(unittest.TestCase):
    """Test AggregatedCost dataclass"""

    def test_aggregated_cost_creation(self):
        """Test creating aggregated cost"""
        agg = AggregatedCost(
            period="month",
            group_by="provider",
            group_value="openai",
            total_cost=50.0,
            total_input_tokens=10000,
            total_output_tokens=5000,
            request_count=10
        )

        self.assertEqual(agg.group_by, "provider")
        self.assertEqual(agg.total_cost, 50.0)

    def test_aggregated_cost_to_dict(self):
        """Test converting aggregated cost to dict"""
        agg = AggregatedCost(
            period="month",
            group_by="provider",
            group_value="openai",
            total_cost=50.0,
            total_input_tokens=10000,
            total_output_tokens=5000,
            request_count=10
        )

        d = agg.to_dict()
        self.assertIsInstance(d, dict)
        self.assertEqual(d["group_by"], "provider")
        self.assertEqual(d["total_cost"], 50.0)


class TestASCIIChart(unittest.TestCase):
    """Test ASCII chart generation"""

    def test_generate_ascii_chart(self):
        """Test generating ASCII chart"""
        data = [
            AggregatedCost("month", "provider", "openai", 50.0, 10000, 5000, 10),
            AggregatedCost("month", "provider", "gemini", 20.0, 8000, 4000, 8),
            AggregatedCost("month", "provider", "deepseek", 1.0, 5000, 2500, 5)
        ]

        chart = generate_ascii_chart(data)

        self.assertIn("openai", chart)
        self.assertIn("gemini", chart)
        self.assertIn("deepseek", chart)
        self.assertIn("$50.0000", chart)
        self.assertIn("Total:", chart)

    def test_generate_ascii_chart_empty(self):
        """Test generating ASCII chart with empty data"""
        chart = generate_ascii_chart([])
        self.assertEqual(chart, "No data to display")

    def test_generate_ascii_chart_zero_cost(self):
        """Test generating ASCII chart with zero cost"""
        data = [
            AggregatedCost("month", "provider", "openai", 0.0, 0, 0, 1)
        ]

        chart = generate_ascii_chart(data)
        self.assertEqual(chart, "No costs to display")


if __name__ == "__main__":
    unittest.main()
