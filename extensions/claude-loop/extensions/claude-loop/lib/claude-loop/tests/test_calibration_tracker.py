#!/usr/bin/env python3
"""
Unit tests for calibration-tracker.py

Tests the calibration tracking system including:
- Decision normalization and loading
- Calibration metrics calculation
- Disagreement analysis
- History tracking
- Weekly report generation
- Autonomous mode eligibility
"""

import json
import runpy
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

# Import module using runpy (handles hyphenated filename)
MODULE_PATH = Path(__file__).parent.parent / "lib" / "calibration-tracker.py"
calibration_module = runpy.run_path(str(MODULE_PATH))

# Extract classes and functions
CalibrationTracker = calibration_module["CalibrationTracker"]
CalibrationMetrics = calibration_module["CalibrationMetrics"]
CalibrationSnapshot = calibration_module["CalibrationSnapshot"]
NormalizedDecision = calibration_module["NormalizedDecision"]
Disagreement = calibration_module["Disagreement"]
WeeklyReport = calibration_module["WeeklyReport"]
CalibrationStatus = calibration_module["CalibrationStatus"]
DecisionSource = calibration_module["DecisionSource"]

# Constants
AGREEMENT_THRESHOLD = calibration_module["AGREEMENT_THRESHOLD"]
MIN_DECISIONS = calibration_module["MIN_DECISIONS"]
MIN_EVALUATION_DAYS = calibration_module["MIN_EVALUATION_DAYS"]


class TestNormalizedDecision(unittest.TestCase):
    """Test NormalizedDecision dataclass."""

    def test_create_decision(self):
        """Test creating a normalized decision."""
        decision = NormalizedDecision(
            decision_id="improvement:IMP-12345678",
            source="improvement",
            original_id="IMP-12345678",
            system_recommendation="approve",
            human_decision="approve",
            agreement=True,
            timestamp="2026-01-01T10:00:00Z"
        )

        self.assertEqual(decision.decision_id, "improvement:IMP-12345678")
        self.assertEqual(decision.source, "improvement")
        self.assertTrue(decision.agreement)

    def test_to_dict(self):
        """Test conversion to dictionary."""
        decision = NormalizedDecision(
            decision_id="clustering:CLU-1",
            source="clustering",
            original_id="CLU-1",
            system_recommendation="reject",
            human_decision="reject",
            agreement=True,
            timestamp="2026-01-01T10:00:00Z",
            confidence=0.7
        )

        d = decision.to_dict()
        self.assertEqual(d["decision_id"], "clustering:CLU-1")
        self.assertEqual(d["confidence"], 0.7)

    def test_from_dict(self):
        """Test creation from dictionary."""
        data = {
            "decision_id": "promotion:PRO-1",
            "source": "promotion",
            "original_id": "PRO-1",
            "system_recommendation": "approve",
            "human_decision": "reject",
            "agreement": False,
            "timestamp": "2026-01-01T10:00:00Z"
        }

        decision = NormalizedDecision.from_dict(data)
        self.assertEqual(decision.decision_id, "promotion:PRO-1")
        self.assertFalse(decision.agreement)


class TestCalibrationMetrics(unittest.TestCase):
    """Test CalibrationMetrics dataclass."""

    def test_default_values(self):
        """Test default metric values."""
        metrics = CalibrationMetrics()

        self.assertEqual(metrics.total_decisions, 0)
        self.assertEqual(metrics.agreement_rate, 0.0)
        self.assertEqual(metrics.status, CalibrationStatus.CALIBRATING.value)
        self.assertFalse(metrics.autonomous_eligible)

    def test_to_dict(self):
        """Test conversion to dictionary."""
        metrics = CalibrationMetrics(
            total_decisions=100,
            agreement_count=95,
            agreement_rate=0.95,
            status=CalibrationStatus.QUALIFIED.value,
            autonomous_eligible=True
        )

        d = metrics.to_dict()
        self.assertEqual(d["total_decisions"], 100)
        self.assertEqual(d["agreement_rate"], 0.95)
        self.assertTrue(d["autonomous_eligible"])


class TestCalibrationTracker(unittest.TestCase):
    """Test CalibrationTracker class."""

    def setUp(self):
        """Set up test fixtures."""
        self.test_dir = tempfile.mkdtemp()
        self.claude_loop_dir = Path(self.test_dir) / ".claude-loop"
        self.claude_loop_dir.mkdir(parents=True)
        self.tracker = CalibrationTracker(base_dir=Path(self.test_dir))

    def tearDown(self):
        """Clean up test directory."""
        import shutil
        shutil.rmtree(self.test_dir)

    def _write_decisions(self, filename: str, decisions: list[dict[str, Any]]) -> None:
        """Helper to write decision files."""
        filepath = self.claude_loop_dir / filename
        with open(filepath, "w") as f:
            for decision in decisions:
                f.write(json.dumps(decision) + "\n")

    def test_empty_state(self):
        """Test metrics with no decisions."""
        metrics = self.tracker.calculate_metrics()

        self.assertEqual(metrics.total_decisions, 0)
        self.assertEqual(metrics.status, CalibrationStatus.CALIBRATING.value)
        self.assertFalse(metrics.autonomous_eligible)

    def test_load_improvement_decisions(self):
        """Test loading improvement queue decisions."""
        decisions = [
            {
                "proposal_id": "IMP-12345678",
                "decision_type": "approve",
                "system_recommendation": "approve",
                "human_decision": "approve",
                "timestamp": "2026-01-01T10:00:00Z"
            },
            {
                "proposal_id": "IMP-23456789",
                "decision_type": "reject",
                "system_recommendation": "review",
                "human_decision": "reject",
                "reasoning": "Too broad",
                "timestamp": "2026-01-01T11:00:00Z"
            }
        ]
        self._write_decisions("improvement_decisions.jsonl", decisions)

        loaded = self.tracker.load_all_decisions()

        self.assertEqual(len(loaded), 2)
        self.assertEqual(loaded[0].source, "improvement")
        self.assertEqual(loaded[0].original_id, "IMP-12345678")

    def test_load_cluster_decisions(self):
        """Test loading cluster decisions."""
        decisions = [
            {
                "cluster_id": "CLU-1",
                "decision_type": "approve",
                "system_confidence": 0.85,
                "human_decision": "approve",
                "timestamp": "2026-01-01T10:00:00Z"
            },
            {
                "cluster_id": "CLU-2",
                "decision_type": "reject",
                "system_confidence": 0.6,
                "human_decision": "reject",
                "timestamp": "2026-01-01T11:00:00Z"
            }
        ]
        self._write_decisions("cluster_decisions.jsonl", decisions)

        loaded = self.tracker.load_all_decisions()

        self.assertEqual(len(loaded), 2)
        self.assertEqual(loaded[0].source, "clustering")
        # High confidence -> system expects approval
        self.assertEqual(loaded[0].system_recommendation, "approve")
        # Low confidence -> system expects rejection
        self.assertEqual(loaded[1].system_recommendation, "reject")

    def test_agreement_calculation(self):
        """Test agreement rate calculation."""
        # 8 agreements, 2 disagreements = 80% agreement
        decisions = []
        for i in range(8):
            decisions.append({
                "proposal_id": f"IMP-A{i}",
                "system_recommendation": "approve",
                "human_decision": "approve",
                "timestamp": f"2026-01-01T{10+i:02d}:00:00Z"
            })
        for i in range(2):
            decisions.append({
                "proposal_id": f"IMP-B{i}",
                "system_recommendation": "approve",
                "human_decision": "reject",
                "timestamp": f"2026-01-01T{18+i}:00:00Z"
            })

        self._write_decisions("improvement_decisions.jsonl", decisions)

        metrics = self.tracker.calculate_metrics()

        self.assertEqual(metrics.total_decisions, 10)
        self.assertEqual(metrics.agreement_count, 8)
        self.assertAlmostEqual(metrics.agreement_rate, 0.8, places=2)

    def test_false_positive_rate(self):
        """Test false positive rate calculation."""
        # System approved, human rejected = false positive
        decisions = [
            {
                "proposal_id": "IMP-FP1",
                "system_recommendation": "approve",
                "human_decision": "reject",
                "timestamp": "2026-01-01T10:00:00Z"
            },
            {
                "proposal_id": "IMP-FP2",
                "system_recommendation": "approve",
                "human_decision": "reject",
                "timestamp": "2026-01-01T11:00:00Z"
            },
            {
                "proposal_id": "IMP-OK1",
                "system_recommendation": "approve",
                "human_decision": "approve",
                "timestamp": "2026-01-01T12:00:00Z"
            },
            {
                "proposal_id": "IMP-OK2",
                "system_recommendation": "approve",
                "human_decision": "approve",
                "timestamp": "2026-01-01T13:00:00Z"
            }
        ]
        self._write_decisions("improvement_decisions.jsonl", decisions)

        metrics = self.tracker.calculate_metrics()

        # 2 FP out of 4 total = 50% FP rate
        self.assertEqual(metrics.total_decisions, 4)
        self.assertAlmostEqual(metrics.false_positive_rate, 0.5, places=2)

    def test_false_negative_rate(self):
        """Test false negative rate calculation."""
        # System rejected, human approved = false negative
        decisions = [
            {
                "proposal_id": "IMP-FN1",
                "system_recommendation": "reject",
                "human_decision": "approve",
                "timestamp": "2026-01-01T10:00:00Z"
            },
            {
                "proposal_id": "IMP-OK1",
                "system_recommendation": "reject",
                "human_decision": "reject",
                "timestamp": "2026-01-01T11:00:00Z"
            },
            {
                "proposal_id": "IMP-OK2",
                "system_recommendation": "reject",
                "human_decision": "reject",
                "timestamp": "2026-01-01T12:00:00Z"
            },
            {
                "proposal_id": "IMP-OK3",
                "system_recommendation": "reject",
                "human_decision": "reject",
                "timestamp": "2026-01-01T13:00:00Z"
            }
        ]
        self._write_decisions("improvement_decisions.jsonl", decisions)

        metrics = self.tracker.calculate_metrics()

        # 1 FN out of 4 total = 25% FN rate
        self.assertEqual(metrics.total_decisions, 4)
        self.assertAlmostEqual(metrics.false_negative_rate, 0.25, places=2)

    def test_by_source_breakdown(self):
        """Test metrics breakdown by source."""
        imp_decisions = [
            {
                "proposal_id": f"IMP-{i}",
                "system_recommendation": "approve",
                "human_decision": "approve",
                "timestamp": f"2026-01-01T{10+i:02d}:00:00Z"
            }
            for i in range(5)
        ]
        cluster_decisions = [
            {
                "cluster_id": f"CLU-{i}",
                "system_confidence": 0.9,
                "human_decision": "approve",
                "timestamp": f"2026-01-02T{10+i:02d}:00:00Z"
            }
            for i in range(3)
        ]

        self._write_decisions("improvement_decisions.jsonl", imp_decisions)
        self._write_decisions("cluster_decisions.jsonl", cluster_decisions)

        metrics = self.tracker.calculate_metrics()

        self.assertEqual(metrics.total_decisions, 8)
        self.assertIn("improvement", metrics.by_source)
        self.assertIn("clustering", metrics.by_source)
        self.assertEqual(metrics.by_source["improvement"]["total"], 5)
        self.assertEqual(metrics.by_source["clustering"]["total"], 3)

    def test_calibration_status_calibrating(self):
        """Test status is CALIBRATING with few decisions."""
        decisions = [
            {
                "proposal_id": "IMP-1",
                "system_recommendation": "approve",
                "human_decision": "approve",
                "timestamp": "2026-01-01T10:00:00Z"
            }
        ]
        self._write_decisions("improvement_decisions.jsonl", decisions)

        metrics = self.tracker.calculate_metrics()

        self.assertEqual(metrics.status, CalibrationStatus.CALIBRATING.value)
        self.assertFalse(metrics.autonomous_eligible)
        self.assertIn(f"Need {MIN_DECISIONS} decisions", metrics.blocking_reasons[0])

    def test_calibration_status_at_risk(self):
        """Test status is AT_RISK with low agreement."""
        # Create 60 decisions with 88% agreement (below 95% but above 85%)
        decisions = []
        for i in range(53):  # 53 agreements
            decisions.append({
                "proposal_id": f"IMP-A{i}",
                "system_recommendation": "approve",
                "human_decision": "approve",
                "timestamp": f"2026-01-01T{i%24:02d}:00:00Z"
            })
        for i in range(7):  # 7 disagreements
            decisions.append({
                "proposal_id": f"IMP-D{i}",
                "system_recommendation": "approve",
                "human_decision": "reject",
                "timestamp": f"2026-01-02T{i:02d}:00:00Z"
            })

        self._write_decisions("improvement_decisions.jsonl", decisions)

        metrics = self.tracker.calculate_metrics()

        self.assertEqual(metrics.total_decisions, 60)
        self.assertAlmostEqual(metrics.agreement_rate, 53/60, places=2)
        self.assertEqual(metrics.status, CalibrationStatus.AT_RISK.value)

    def test_calibration_status_failing(self):
        """Test status is FAILING with very low agreement."""
        # Create 60 decisions with 50% agreement (below 85%)
        decisions = []
        for i in range(30):  # 30 agreements
            decisions.append({
                "proposal_id": f"IMP-A{i}",
                "system_recommendation": "approve",
                "human_decision": "approve",
                "timestamp": f"2026-01-01T{i%24:02d}:00:00Z"
            })
        for i in range(30):  # 30 disagreements
            decisions.append({
                "proposal_id": f"IMP-D{i}",
                "system_recommendation": "approve",
                "human_decision": "reject",
                "timestamp": f"2026-01-02T{i%24:02d}:00:00Z"
            })

        self._write_decisions("improvement_decisions.jsonl", decisions)

        metrics = self.tracker.calculate_metrics()

        self.assertEqual(metrics.status, CalibrationStatus.FAILING.value)

    def test_get_disagreements(self):
        """Test getting disagreement list."""
        decisions = [
            {
                "proposal_id": "IMP-OK",
                "system_recommendation": "approve",
                "human_decision": "approve",
                "timestamp": "2026-01-01T10:00:00Z"
            },
            {
                "proposal_id": "IMP-FP",
                "system_recommendation": "approve",
                "human_decision": "reject",
                "timestamp": "2026-01-01T11:00:00Z"
            },
            {
                "proposal_id": "IMP-FN",
                "system_recommendation": "reject",
                "human_decision": "approve",
                "timestamp": "2026-01-01T12:00:00Z"
            }
        ]
        self._write_decisions("improvement_decisions.jsonl", decisions)
        self.tracker.load_all_decisions()

        disagreements = self.tracker.get_disagreements()

        self.assertEqual(len(disagreements), 2)
        types = {d.disagreement_type for d in disagreements}
        self.assertIn("false_positive", types)
        self.assertIn("false_negative", types)

    def test_get_disagreements_filter_by_type(self):
        """Test filtering disagreements by type."""
        decisions = [
            {
                "proposal_id": "IMP-FP1",
                "system_recommendation": "approve",
                "human_decision": "reject",
                "timestamp": "2026-01-01T10:00:00Z"
            },
            {
                "proposal_id": "IMP-FP2",
                "system_recommendation": "approve",
                "human_decision": "reject",
                "timestamp": "2026-01-01T11:00:00Z"
            },
            {
                "proposal_id": "IMP-FN1",
                "system_recommendation": "reject",
                "human_decision": "approve",
                "timestamp": "2026-01-01T12:00:00Z"
            }
        ]
        self._write_decisions("improvement_decisions.jsonl", decisions)
        self.tracker.load_all_decisions()

        fp_only = self.tracker.get_disagreements(disagreement_type="false_positive")
        fn_only = self.tracker.get_disagreements(disagreement_type="false_negative")

        self.assertEqual(len(fp_only), 2)
        self.assertEqual(len(fn_only), 1)

    def test_autonomous_eligibility_not_eligible(self):
        """Test autonomous eligibility check when not eligible."""
        # Few decisions = not eligible
        decisions = [
            {
                "proposal_id": f"IMP-{i}",
                "system_recommendation": "approve",
                "human_decision": "approve",
                "timestamp": f"2026-01-01T{i:02d}:00:00Z"
            }
            for i in range(10)
        ]
        self._write_decisions("improvement_decisions.jsonl", decisions)

        result = self.tracker.check_autonomous_eligibility()

        self.assertFalse(result["eligible"])
        self.assertIn("Need", result["message"])

    def test_save_snapshot(self):
        """Test saving calibration snapshot."""
        decisions = [
            {
                "proposal_id": f"IMP-{i}",
                "system_recommendation": "approve",
                "human_decision": "approve",
                "timestamp": f"2026-01-01T{i:02d}:00:00Z"
            }
            for i in range(10)
        ]
        self._write_decisions("improvement_decisions.jsonl", decisions)

        snapshot = self.tracker.save_snapshot()

        self.assertIsNotNone(snapshot.timestamp)
        self.assertEqual(snapshot.total_decisions, 10)
        self.assertAlmostEqual(snapshot.agreement_rate, 1.0, places=2)

        # Verify it's persisted
        history = self.tracker.get_history(days=30)
        self.assertEqual(len(history), 1)

    def test_get_history(self):
        """Test getting calibration history."""
        # Save multiple snapshots
        decisions = [
            {
                "proposal_id": f"IMP-{i}",
                "system_recommendation": "approve",
                "human_decision": "approve",
                "timestamp": f"2026-01-01T{i:02d}:00:00Z"
            }
            for i in range(10)
        ]
        self._write_decisions("improvement_decisions.jsonl", decisions)

        self.tracker.save_snapshot()
        self.tracker.save_snapshot()
        self.tracker.save_snapshot()

        history = self.tracker.get_history(days=30)

        self.assertEqual(len(history), 3)

    def test_generate_weekly_report(self):
        """Test weekly report generation."""
        decisions = [
            {
                "proposal_id": f"IMP-{i}",
                "system_recommendation": "approve",
                "human_decision": "approve" if i < 8 else "reject",
                "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
            }
            for i in range(10)
        ]
        self._write_decisions("improvement_decisions.jsonl", decisions)

        report = self.tracker.generate_weekly_report()

        self.assertIsNotNone(report.report_id)
        self.assertIn("CAL-", report.report_id)
        self.assertEqual(report.metrics.total_decisions, 10)
        self.assertGreater(len(report.recommendations), 0)
        self.assertIn("Calibration Status:", report.status_summary)

    def test_list_weekly_reports(self):
        """Test listing weekly reports."""
        # Generate a report
        decisions = [
            {
                "proposal_id": "IMP-1",
                "system_recommendation": "approve",
                "human_decision": "approve",
                "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
            }
        ]
        self._write_decisions("improvement_decisions.jsonl", decisions)
        self.tracker.generate_weekly_report()

        reports = self.tracker.list_weekly_reports()

        self.assertGreater(len(reports), 0)
        self.assertTrue(reports[0].startswith("calibration_report_"))

    def test_get_weekly_report(self):
        """Test retrieving specific weekly report."""
        decisions = [
            {
                "proposal_id": "IMP-1",
                "system_recommendation": "approve",
                "human_decision": "approve",
                "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
            }
        ]
        self._write_decisions("improvement_decisions.jsonl", decisions)
        generated = self.tracker.generate_weekly_report()

        reports = self.tracker.list_weekly_reports()
        loaded = self.tracker.get_weekly_report(reports[0])

        self.assertIsNotNone(loaded)
        self.assertEqual(loaded.report_id, generated.report_id)

    def test_recent_trend(self):
        """Test recent trend calculation."""
        # Create old decisions (35 days ago)
        old_date = datetime.now(timezone.utc) - timedelta(days=35)
        old_decisions = [
            {
                "proposal_id": f"IMP-OLD-{i}",
                "system_recommendation": "approve",
                "human_decision": "approve",
                "timestamp": old_date.isoformat().replace("+00:00", "Z")
            }
            for i in range(5)
        ]

        # Create recent decisions (5 days ago) with lower agreement
        recent_date = datetime.now(timezone.utc) - timedelta(days=5)
        recent_decisions = [
            {
                "proposal_id": f"IMP-NEW-{i}",
                "system_recommendation": "approve",
                "human_decision": "approve" if i < 3 else "reject",
                "timestamp": recent_date.isoformat().replace("+00:00", "Z")
            }
            for i in range(5)
        ]

        self._write_decisions("improvement_decisions.jsonl", old_decisions + recent_decisions)

        metrics = self.tracker.calculate_metrics()

        # Recent trend should be 60% (3/5 agreements in recent period)
        self.assertAlmostEqual(metrics.recent_trend, 0.6, places=1)

    def test_by_confidence_breakdown(self):
        """Test metrics breakdown by confidence level."""
        decisions = [
            # High confidence
            {
                "cluster_id": "CLU-H1",
                "system_confidence": 0.9,
                "human_decision": "approve",
                "timestamp": "2026-01-01T10:00:00Z"
            },
            {
                "cluster_id": "CLU-H2",
                "system_confidence": 0.85,
                "human_decision": "approve",
                "timestamp": "2026-01-01T11:00:00Z"
            },
            # Medium confidence
            {
                "cluster_id": "CLU-M1",
                "system_confidence": 0.65,
                "human_decision": "reject",
                "timestamp": "2026-01-01T12:00:00Z"
            },
            # Low confidence
            {
                "cluster_id": "CLU-L1",
                "system_confidence": 0.3,
                "human_decision": "reject",
                "timestamp": "2026-01-01T13:00:00Z"
            }
        ]
        self._write_decisions("cluster_decisions.jsonl", decisions)

        metrics = self.tracker.calculate_metrics()

        self.assertIn("high", metrics.by_confidence)
        self.assertIn("medium", metrics.by_confidence)
        self.assertIn("low", metrics.by_confidence)
        self.assertEqual(metrics.by_confidence["high"]["total"], 2)
        self.assertEqual(metrics.by_confidence["medium"]["total"], 1)
        self.assertEqual(metrics.by_confidence["low"]["total"], 1)

    def test_disagreement_impact_level(self):
        """Test disagreement impact level assignment."""
        decisions = [
            {
                "cluster_id": "CLU-HIGH",
                "system_confidence": 0.95,
                "human_decision": "reject",  # Disagreement with high confidence
                "timestamp": "2026-01-01T10:00:00Z"
            },
            {
                "cluster_id": "CLU-MED",
                "system_confidence": 0.75,
                "human_decision": "approve",  # Disagreement with medium confidence
                "timestamp": "2026-01-01T11:00:00Z"
            },
            {
                "cluster_id": "CLU-LOW",
                "system_confidence": 0.5,
                "human_decision": "approve",  # Disagreement with low confidence
                "timestamp": "2026-01-01T12:00:00Z"
            }
        ]
        self._write_decisions("cluster_decisions.jsonl", decisions)
        self.tracker.load_all_decisions()

        disagreements = self.tracker.get_disagreements()

        impacts = {d.decision.original_id: d.impact for d in disagreements}
        self.assertEqual(impacts["CLU-HIGH"], "high")
        self.assertEqual(impacts["CLU-MED"], "medium")
        self.assertEqual(impacts["CLU-LOW"], "low")

    def test_recommendation_normalization(self):
        """Test various recommendation values are normalized correctly."""
        decisions = [
            {
                "proposal_id": "IMP-1",
                "system_recommendation": "recommend",  # Should normalize to approve
                "human_decision": "approve",
                "timestamp": "2026-01-01T10:00:00Z"
            },
            {
                "proposal_id": "IMP-2",
                "system_recommendation": "not_recommended",  # Should normalize to reject
                "human_decision": "reject",
                "timestamp": "2026-01-01T11:00:00Z"
            },
            {
                "proposal_id": "IMP-3",
                "system_recommendation": "blocked",  # Should normalize to reject
                "human_decision": "reject",
                "timestamp": "2026-01-01T12:00:00Z"
            }
        ]
        self._write_decisions("improvement_decisions.jsonl", decisions)

        loaded = self.tracker.load_all_decisions()

        recs = {d.original_id: d.system_recommendation for d in loaded}
        self.assertEqual(recs["IMP-1"], "approve")
        self.assertEqual(recs["IMP-2"], "reject")
        self.assertEqual(recs["IMP-3"], "reject")

    def test_state_persistence(self):
        """Test calibration state is persisted."""
        decisions = [
            {
                "proposal_id": "IMP-1",
                "system_recommendation": "approve",
                "human_decision": "approve",
                "timestamp": "2026-01-01T10:00:00Z"
            }
        ]
        self._write_decisions("improvement_decisions.jsonl", decisions)

        # Load decisions to set first_decision_at
        self.tracker.load_all_decisions()

        # Create new tracker instance
        new_tracker = CalibrationTracker(base_dir=Path(self.test_dir))

        # State should be persisted
        self.assertIsNotNone(new_tracker._state.get("first_decision_at"))


class TestWeeklyReport(unittest.TestCase):
    """Test WeeklyReport dataclass."""

    def test_auto_id_generation(self):
        """Test report ID is auto-generated."""
        report = WeeklyReport(
            report_id="",
            period_start="2026-01-01T00:00:00Z",
            period_end="2026-01-07T23:59:59Z",
            generated_at="",
            metrics=CalibrationMetrics()
        )

        self.assertIn("CAL-", report.report_id)
        self.assertIsNotNone(report.generated_at)

    def test_to_dict(self):
        """Test conversion to dictionary."""
        report = WeeklyReport(
            report_id="CAL-12345678",
            period_start="2026-01-01T00:00:00Z",
            period_end="2026-01-07T23:59:59Z",
            generated_at="2026-01-08T00:00:00Z",
            metrics=CalibrationMetrics(total_decisions=50),
            new_decisions=10,
            recommendations=["Review disagreements"]
        )

        d = report.to_dict()

        self.assertEqual(d["report_id"], "CAL-12345678")
        self.assertEqual(d["metrics"]["total_decisions"], 50)
        self.assertEqual(d["new_decisions"], 10)
        self.assertEqual(len(d["recommendations"]), 1)


class TestCalibrationSnapshot(unittest.TestCase):
    """Test CalibrationSnapshot dataclass."""

    def test_to_dict(self):
        """Test conversion to dictionary."""
        snapshot = CalibrationSnapshot(
            timestamp="2026-01-01T10:00:00Z",
            total_decisions=100,
            agreement_rate=0.95,
            false_positive_rate=0.03,
            false_negative_rate=0.02,
            recent_trend=0.96,
            status=CalibrationStatus.QUALIFIED.value,
            autonomous_eligible=True
        )

        d = snapshot.to_dict()

        self.assertEqual(d["total_decisions"], 100)
        self.assertEqual(d["agreement_rate"], 0.95)
        self.assertTrue(d["autonomous_eligible"])

    def test_from_dict(self):
        """Test creation from dictionary."""
        data = {
            "timestamp": "2026-01-01T10:00:00Z",
            "total_decisions": 60,
            "agreement_rate": 0.88,
            "false_positive_rate": 0.07,
            "false_negative_rate": 0.05,
            "recent_trend": 0.90,
            "status": CalibrationStatus.AT_RISK.value,
            "autonomous_eligible": False
        }

        snapshot = CalibrationSnapshot.from_dict(data)

        self.assertEqual(snapshot.total_decisions, 60)
        self.assertAlmostEqual(snapshot.agreement_rate, 0.88)
        self.assertEqual(snapshot.status, CalibrationStatus.AT_RISK.value)


class TestDisagreement(unittest.TestCase):
    """Test Disagreement dataclass."""

    def test_to_dict(self):
        """Test conversion to dictionary."""
        decision = NormalizedDecision(
            decision_id="test:1",
            source="improvement",
            original_id="1",
            system_recommendation="approve",
            human_decision="reject",
            agreement=False,
            timestamp="2026-01-01T10:00:00Z"
        )

        disagreement = Disagreement(
            decision=decision,
            disagreement_type="false_positive",
            impact="high",
            resolution_notes="Reviewed and updated model",
            learned_from=True
        )

        d = disagreement.to_dict()

        self.assertEqual(d["disagreement_type"], "false_positive")
        self.assertEqual(d["impact"], "high")
        self.assertTrue(d["learned_from"])
        self.assertIn("decision", d)


class TestConstants(unittest.TestCase):
    """Test module constants."""

    def test_thresholds(self):
        """Test threshold values are reasonable."""
        self.assertGreater(AGREEMENT_THRESHOLD, 0.5)
        self.assertLessEqual(AGREEMENT_THRESHOLD, 1.0)
        self.assertGreater(MIN_DECISIONS, 0)
        self.assertGreater(MIN_EVALUATION_DAYS, 0)

    def test_agreement_threshold(self):
        """Test agreement threshold is 95%."""
        self.assertEqual(AGREEMENT_THRESHOLD, 0.95)

    def test_min_decisions(self):
        """Test minimum decisions is 50."""
        self.assertEqual(MIN_DECISIONS, 50)

    def test_min_evaluation_days(self):
        """Test minimum evaluation days is 180."""
        self.assertEqual(MIN_EVALUATION_DAYS, 180)


if __name__ == "__main__":
    unittest.main()
