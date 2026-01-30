#!/usr/bin/env python3
"""
Comprehensive tests for prediction tracking and learning system.

Tests prediction recording, outcome tracking, metrics calculation,
source analysis, and learning feedback.
"""

import json
import os
import sys
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path

# Add lib to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'lib'))

from prediction_tracker import Prediction, PredictionTracker
from outcome_tracker import Outcome, OutcomeTracker
from learning_feedback import LearningFeedback, SourceCredibility


class TestPrediction(unittest.TestCase):
    """Tests for Prediction dataclass."""

    def test_prediction_creation(self):
        """Test creating a prediction."""
        pred = Prediction(
            id="PRED-0001",
            research_id="RES-001",
            asset="BTC",
            asset_type="crypto",
            entry_price=45000.0,
            entry_date=datetime.now(),
            targets=[50000.0, 55000.0],
            stop_loss=40000.0,
            timeframe_days=30,
            thesis="Bitcoin showing bullish pattern",
            confidence=70,
            sources=["Technical Analysis", "On-chain Metrics"]
        )

        self.assertEqual(pred.id, "PRED-0001")
        self.assertEqual(pred.asset, "BTC")
        self.assertEqual(pred.entry_price, 45000.0)
        self.assertEqual(len(pred.targets), 2)
        self.assertEqual(pred.status, "active")

    def test_prediction_to_dict_and_back(self):
        """Test serialization round-trip."""
        pred = Prediction(
            id="PRED-0001",
            research_id="RES-001",
            asset="AAPL",
            asset_type="stock",
            entry_price=150.0,
            entry_date=datetime(2024, 1, 15),
            targets=[165.0],
            stop_loss=140.0,
            timeframe_days=60,
            thesis="Strong earnings expected",
            confidence=65,
            sources=["Fundamental Analysis"]
        )

        pred_dict = pred.to_dict()
        restored = Prediction.from_dict(pred_dict)

        self.assertEqual(pred.id, restored.id)
        self.assertEqual(pred.asset, restored.asset)
        self.assertEqual(pred.entry_price, restored.entry_price)
        self.assertEqual(pred.entry_date, restored.entry_date)
        self.assertEqual(pred.targets, restored.targets)

    def test_is_expired(self):
        """Test expiration check."""
        # Not expired
        pred = Prediction(
            id="PRED-0001",
            research_id="RES-001",
            asset="ETH",
            asset_type="crypto",
            entry_price=3000.0,
            entry_date=datetime.now(),
            targets=[3500.0],
            stop_loss=2500.0,
            timeframe_days=30,
            thesis="Test",
            confidence=50,
            sources=[]
        )
        self.assertFalse(pred.is_expired())

        # Expired
        pred.entry_date = datetime.now() - timedelta(days=35)
        self.assertTrue(pred.is_expired())

        # Not expired if already closed
        pred.status = "hit_target"
        self.assertFalse(pred.is_expired())

    def test_check_price_stop_loss(self):
        """Test stop-loss trigger."""
        pred = Prediction(
            id="PRED-0001",
            research_id="RES-001",
            asset="NVDA",
            asset_type="stock",
            entry_price=500.0,
            entry_date=datetime.now(),
            targets=[600.0],
            stop_loss=450.0,
            timeframe_days=30,
            thesis="Test",
            confidence=50,
            sources=[]
        )

        # Price above stop
        self.assertIsNone(pred.check_price(480.0))

        # Price at stop
        self.assertEqual(pred.check_price(450.0), "stopped_out")

        # Price below stop
        self.assertEqual(pred.check_price(400.0), "stopped_out")

    def test_check_price_target_hit(self):
        """Test target hit trigger."""
        pred = Prediction(
            id="PRED-0001",
            research_id="RES-001",
            asset="GOOGL",
            asset_type="stock",
            entry_price=100.0,
            entry_date=datetime.now(),
            targets=[110.0, 120.0],
            stop_loss=90.0,
            timeframe_days=30,
            thesis="Test",
            confidence=50,
            sources=[]
        )

        # Below first target
        self.assertIsNone(pred.check_price(105.0))

        # At first target
        self.assertEqual(pred.check_price(110.0), "hit_target")

        # Above second target
        self.assertEqual(pred.check_price(125.0), "hit_target")


class TestPredictionTracker(unittest.TestCase):
    """Tests for PredictionTracker class."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.store_path = os.path.join(self.temp_dir, "predictions.json")
        self.tracker = PredictionTracker(self.store_path)

    def tearDown(self):
        """Clean up."""
        import shutil
        shutil.rmtree(self.temp_dir)

    def test_record_prediction(self):
        """Test recording a prediction."""
        pred = Prediction(
            id="",
            research_id="RES-001",
            asset="BTC",
            asset_type="crypto",
            entry_price=45000.0,
            entry_date=datetime.now(),
            targets=[50000.0],
            stop_loss=40000.0,
            timeframe_days=30,
            thesis="Test thesis",
            confidence=60,
            sources=["Source1"]
        )

        pred_id = self.tracker.record(pred)

        self.assertTrue(pred_id.startswith("PRED-"))
        self.assertEqual(len(self.tracker.get_all()), 1)

    def test_auto_generate_id(self):
        """Test automatic ID generation."""
        for i in range(3):
            pred = Prediction(
                id="",
                research_id=f"RES-{i}",
                asset=f"ASSET{i}",
                asset_type="stock",
                entry_price=100.0 + i,
                entry_date=datetime.now(),
                targets=[110.0],
                stop_loss=90.0,
                timeframe_days=30,
                thesis="Test",
                confidence=50,
                sources=[]
            )
            self.tracker.record(pred)

        all_preds = self.tracker.get_all()
        ids = [p.id for p in all_preds]

        # All IDs should be unique
        self.assertEqual(len(ids), len(set(ids)))

    def test_get_active_predictions(self):
        """Test filtering active predictions."""
        # Create active prediction
        active_pred = Prediction(
            id="",
            research_id="RES-001",
            asset="ACTIVE",
            asset_type="stock",
            entry_price=100.0,
            entry_date=datetime.now(),
            targets=[110.0],
            stop_loss=90.0,
            timeframe_days=30,
            thesis="Active",
            confidence=50,
            sources=[]
        )
        active_id = self.tracker.record(active_pred)

        # Create closed prediction
        closed_pred = Prediction(
            id="",
            research_id="RES-002",
            asset="CLOSED",
            asset_type="stock",
            entry_price=100.0,
            entry_date=datetime.now(),
            targets=[110.0],
            stop_loss=90.0,
            timeframe_days=30,
            thesis="Closed",
            confidence=50,
            sources=[],
            status="hit_target"
        )
        self.tracker.record(closed_pred)

        active = self.tracker.get_active()
        self.assertEqual(len(active), 1)
        self.assertEqual(active[0].asset, "ACTIVE")

    def test_update_status(self):
        """Test updating prediction status."""
        pred = Prediction(
            id="",
            research_id="RES-001",
            asset="TEST",
            asset_type="stock",
            entry_price=100.0,
            entry_date=datetime.now(),
            targets=[110.0],
            stop_loss=90.0,
            timeframe_days=30,
            thesis="Test",
            confidence=50,
            sources=[]
        )
        pred_id = self.tracker.record(pred)

        success = self.tracker.update_status(pred_id, "hit_target", 115.0)

        self.assertTrue(success)
        updated = self.tracker.get(pred_id)
        self.assertEqual(updated.status, "hit_target")
        self.assertEqual(updated.exit_price, 115.0)
        self.assertIsNotNone(updated.exit_date)

    def test_get_by_asset(self):
        """Test filtering by asset."""
        for asset in ["BTC", "ETH", "BTC"]:
            pred = Prediction(
                id="",
                research_id="RES",
                asset=asset,
                asset_type="crypto",
                entry_price=100.0,
                entry_date=datetime.now(),
                targets=[110.0],
                stop_loss=90.0,
                timeframe_days=30,
                thesis="Test",
                confidence=50,
                sources=[]
            )
            self.tracker.record(pred)

        btc_preds = self.tracker.get_by_asset("BTC")
        self.assertEqual(len(btc_preds), 2)

        eth_preds = self.tracker.get_by_asset("eth")  # Case insensitive
        self.assertEqual(len(eth_preds), 1)

    def test_persistence(self):
        """Test that predictions persist across tracker instances."""
        pred = Prediction(
            id="",
            research_id="RES-001",
            asset="PERSIST",
            asset_type="stock",
            entry_price=100.0,
            entry_date=datetime.now(),
            targets=[110.0],
            stop_loss=90.0,
            timeframe_days=30,
            thesis="Test persistence",
            confidence=50,
            sources=["Source1"]
        )
        pred_id = self.tracker.record(pred)

        # Create new tracker instance
        new_tracker = PredictionTracker(self.store_path)
        loaded = new_tracker.get(pred_id)

        self.assertIsNotNone(loaded)
        self.assertEqual(loaded.asset, "PERSIST")
        self.assertEqual(loaded.thesis, "Test persistence")

    def test_statistics(self):
        """Test statistics calculation."""
        # Add mix of predictions
        statuses = ["active", "hit_target", "stopped_out", "active"]
        asset_types = ["stock", "crypto", "stock", "option"]

        for i, (status, asset_type) in enumerate(zip(statuses, asset_types)):
            pred = Prediction(
                id="",
                research_id=f"RES-{i}",
                asset=f"ASSET{i}",
                asset_type=asset_type,
                entry_price=100.0,
                entry_date=datetime.now(),
                targets=[110.0],
                stop_loss=90.0,
                timeframe_days=30,
                thesis="Test",
                confidence=50 + i * 10,
                sources=[],
                status=status
            )
            self.tracker.record(pred)

        stats = self.tracker.get_statistics()

        self.assertEqual(stats['total'], 4)
        self.assertEqual(stats['active'], 2)
        self.assertEqual(stats['by_status']['hit_target'], 1)
        self.assertEqual(stats['by_asset_type']['stock'], 2)
        self.assertEqual(stats['avg_confidence'], 65.0)


class TestOutcome(unittest.TestCase):
    """Tests for Outcome dataclass."""

    def test_outcome_creation(self):
        """Test creating an outcome."""
        outcome = Outcome(
            prediction_id="PRED-0001",
            actual_return=15.5,
            max_drawdown=-5.2,
            days_held=25,
            exit_reason="target_hit",
            lessons_learned="Good entry timing"
        )

        self.assertEqual(outcome.prediction_id, "PRED-0001")
        self.assertEqual(outcome.actual_return, 15.5)
        self.assertEqual(outcome.exit_reason, "target_hit")

    def test_outcome_serialization(self):
        """Test outcome serialization."""
        outcome = Outcome(
            prediction_id="PRED-0001",
            actual_return=10.0,
            max_drawdown=-3.0,
            days_held=15,
            exit_reason="manual"
        )

        outcome_dict = outcome.to_dict()
        restored = Outcome.from_dict(outcome_dict)

        self.assertEqual(outcome.prediction_id, restored.prediction_id)
        self.assertEqual(outcome.actual_return, restored.actual_return)


class TestOutcomeTracker(unittest.TestCase):
    """Tests for OutcomeTracker class."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.predictions_path = os.path.join(self.temp_dir, "predictions.json")
        self.outcomes_path = os.path.join(self.temp_dir, "outcomes.json")

        # Create prediction tracker with sample data
        self.pred_tracker = PredictionTracker(self.predictions_path)
        self._create_sample_predictions()

        self.outcome_tracker = OutcomeTracker(
            self.outcomes_path,
            self.predictions_path
        )

    def tearDown(self):
        """Clean up."""
        import shutil
        shutil.rmtree(self.temp_dir)

    def _create_sample_predictions(self):
        """Create sample predictions for testing."""
        predictions_data = [
            ("BTC", "crypto", 45000.0, [50000.0], 40000.0, 70, ["Source1", "Source2"]),
            ("ETH", "crypto", 3000.0, [3500.0], 2500.0, 60, ["Source1"]),
            ("AAPL", "stock", 150.0, [165.0], 140.0, 80, ["Source2", "Source3"]),
            ("GOOGL", "stock", 100.0, [110.0], 90.0, 50, ["Source3"]),
        ]

        for asset, atype, entry, targets, stop, conf, sources in predictions_data:
            pred = Prediction(
                id="",
                research_id="RES",
                asset=asset,
                asset_type=atype,
                entry_price=entry,
                entry_date=datetime.now() - timedelta(days=30),
                targets=targets,
                stop_loss=stop,
                timeframe_days=60,
                thesis="Test",
                confidence=conf,
                sources=sources
            )
            self.pred_tracker.record(pred)

    def test_record_outcome(self):
        """Test recording an outcome."""
        outcome = Outcome(
            prediction_id="PRED-0001",
            actual_return=12.5,
            max_drawdown=-3.0,
            days_held=20,
            exit_reason="target_hit"
        )

        self.outcome_tracker.record(outcome)

        all_outcomes = self.outcome_tracker.get_all()
        self.assertEqual(len(all_outcomes), 1)
        self.assertEqual(all_outcomes[0].actual_return, 12.5)

    def test_record_from_prediction(self):
        """Test recording outcome calculated from prediction."""
        # Update prediction status first
        self.pred_tracker.update_status("PRED-0001", "hit_target", 52000.0)

        outcome = self.outcome_tracker.record_from_prediction(
            prediction_id="PRED-0001",
            exit_price=52000.0,
            exit_reason="target_hit"
        )

        self.assertIsNotNone(outcome)
        self.assertAlmostEqual(outcome.actual_return, 15.56, places=1)  # (52000-45000)/45000 * 100
        self.assertEqual(outcome.asset, "BTC")
        self.assertEqual(outcome.asset_type, "crypto")

    def test_calculate_metrics_empty(self):
        """Test metrics with no outcomes."""
        metrics = self.outcome_tracker.calculate_metrics()

        self.assertEqual(metrics['total_trades'], 0)
        self.assertEqual(metrics['hit_rate'], 0.0)
        self.assertEqual(metrics['sharpe_ratio'], 0.0)

    def test_calculate_metrics(self):
        """Test metrics calculation."""
        # Record some outcomes
        outcomes = [
            (10.0, -2.0, 15, "target_hit"),
            (20.0, -5.0, 25, "target_hit"),
            (-5.0, -8.0, 10, "stop_loss"),
            (15.0, -3.0, 20, "target_hit"),
            (-10.0, -12.0, 30, "stopped_out"),
        ]

        for ret, dd, days, reason in outcomes:
            outcome = Outcome(
                prediction_id=f"PRED-{len(self.outcome_tracker.outcomes)}",
                actual_return=ret,
                max_drawdown=dd,
                days_held=days,
                exit_reason=reason
            )
            self.outcome_tracker.record(outcome)

        metrics = self.outcome_tracker.calculate_metrics()

        self.assertEqual(metrics['total_trades'], 5)
        self.assertEqual(metrics['winning_trades'], 3)
        self.assertEqual(metrics['losing_trades'], 2)
        self.assertEqual(metrics['hit_rate'], 60.0)  # 3/5 = 60%
        self.assertEqual(metrics['avg_return'], 6.0)  # (10+20-5+15-10)/5 = 6
        self.assertGreater(metrics['sharpe_ratio'], 0)  # Positive avg return
        self.assertEqual(metrics['max_drawdown'], -12.0)

    def test_calculate_source_metrics(self):
        """Test source-level metrics."""
        # Record outcomes with source info
        predictions = self.pred_tracker.get_all()

        for pred in predictions[:3]:
            self.pred_tracker.update_status(
                pred.id,
                "hit_target",
                pred.entry_price * 1.1  # 10% gain
            )
            self.outcome_tracker.record_from_prediction(
                pred.id,
                pred.entry_price * 1.1,
                "target_hit"
            )

        # One loser
        pred = predictions[3]
        self.pred_tracker.update_status(pred.id, "stopped_out", pred.stop_loss)
        self.outcome_tracker.record_from_prediction(
            pred.id,
            pred.stop_loss,
            "stop_loss"
        )

        source_metrics = self.outcome_tracker.calculate_source_metrics()

        self.assertIn("Source1", source_metrics)
        self.assertIn("Source2", source_metrics)

        # Source1 had 2 predictions (BTC, ETH), both winners
        self.assertEqual(source_metrics["Source1"]["hit_rate"], 100.0)

    def test_confidence_calibration(self):
        """Test confidence calibration calculation."""
        # Create outcomes with different confidence levels
        test_data = [
            # (confidence, actual_return) - simulate calibration
            (20, -5.0),   # Low confidence, loss
            (30, 10.0),   # Low-med confidence, win
            (50, 5.0),    # Medium confidence, win
            (50, -3.0),   # Medium confidence, loss
            (70, 15.0),   # High confidence, win
            (80, 20.0),   # High confidence, win
            (90, 10.0),   # Very high confidence, win
        ]

        for i, (conf, ret) in enumerate(test_data):
            outcome = Outcome(
                prediction_id=f"TEST-{i}",
                actual_return=ret,
                max_drawdown=-abs(ret) if ret < 0 else -2.0,
                days_held=20,
                exit_reason="target_hit" if ret > 0 else "stop_loss",
                confidence=conf
            )
            self.outcome_tracker.outcomes.append(outcome)

        calibration = self.outcome_tracker.calculate_confidence_calibration()

        self.assertIn('buckets', calibration)
        self.assertIn('calibration_error', calibration)
        # Should have some buckets populated
        self.assertGreater(len(calibration['buckets']), 0)


class TestLearningFeedback(unittest.TestCase):
    """Tests for LearningFeedback class."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.predictions_path = os.path.join(self.temp_dir, "predictions.json")
        self.outcomes_path = os.path.join(self.temp_dir, "outcomes.json")
        self.credibility_path = os.path.join(self.temp_dir, "credibility.json")

        # Create trackers
        self.pred_tracker = PredictionTracker(self.predictions_path)
        self.outcome_tracker = OutcomeTracker(self.outcomes_path, self.predictions_path)

        self._create_test_data()

        self.feedback = LearningFeedback(
            self.predictions_path,
            self.outcomes_path,
            self.credibility_path
        )

    def tearDown(self):
        """Clean up."""
        import shutil
        shutil.rmtree(self.temp_dir)

    def _create_test_data(self):
        """Create test predictions and outcomes."""
        # Create predictions with various sources
        test_preds = [
            ("BTC", "crypto", 45000, 50000, 40000, 70, ["GoodSource", "NeutralSource"], 15.0),
            ("ETH", "crypto", 3000, 3500, 2500, 65, ["GoodSource"], 12.0),
            ("AAPL", "stock", 150, 165, 140, 75, ["GoodSource", "BadSource"], 8.0),
            ("GOOGL", "stock", 100, 110, 90, 60, ["BadSource"], -10.0),
            ("MSFT", "stock", 300, 330, 280, 55, ["BadSource", "NeutralSource"], -8.0),
            ("SOL", "crypto", 100, 120, 80, 80, ["GoodSource"], 25.0),
        ]

        for asset, atype, entry, target, stop, conf, sources, ret in test_preds:
            pred = Prediction(
                id="",
                research_id="RES",
                asset=asset,
                asset_type=atype,
                entry_price=float(entry),
                entry_date=datetime.now() - timedelta(days=30),
                targets=[float(target)],
                stop_loss=float(stop),
                timeframe_days=60,
                thesis="Test",
                confidence=conf,
                sources=sources
            )
            pred_id = self.pred_tracker.record(pred)

            # Record outcome
            exit_price = entry * (1 + ret / 100)
            exit_reason = "target_hit" if ret > 0 else "stop_loss"

            outcome = Outcome(
                prediction_id=pred_id,
                actual_return=ret,
                max_drawdown=-abs(ret) / 2 if ret > 0 else ret,
                days_held=20,
                exit_reason=exit_reason,
                asset=asset,
                asset_type=atype,
                confidence=conf,
                sources=sources
            )
            self.outcome_tracker.record(outcome)

    def test_analyze_patterns(self):
        """Test pattern analysis."""
        patterns = self.feedback.analyze_patterns()

        self.assertEqual(patterns['status'], 'success')
        self.assertGreater(len(patterns['patterns']), 0)

        # Check for expected pattern types
        pattern_types = [p['type'] for p in patterns['patterns']]
        self.assertIn('confidence_correlation', pattern_types)
        self.assertIn('holding_period', pattern_types)

    def test_update_source_credibility(self):
        """Test source credibility update."""
        credibility = self.feedback.update_source_credibility()

        self.assertIn("GoodSource", credibility)
        self.assertIn("BadSource", credibility)

        # GoodSource should have higher credibility (all winners)
        self.assertGreater(
            credibility["GoodSource"].credibility_score,
            credibility["BadSource"].credibility_score
        )

    def test_source_credibility_persistence(self):
        """Test that credibility persists."""
        self.feedback.update_source_credibility()

        # Create new feedback instance
        new_feedback = LearningFeedback(
            self.predictions_path,
            self.outcomes_path,
            self.credibility_path
        )

        cred = new_feedback.get_source_credibility("GoodSource")
        self.assertIsNotNone(cred)

    def test_generate_insights(self):
        """Test insights generation."""
        insights = self.feedback.generate_insights()

        self.assertIsInstance(insights, str)
        self.assertIn("OVERALL PERFORMANCE", insights)
        self.assertIn("RECOMMENDATIONS", insights)

    def test_get_calibration_report(self):
        """Test calibration report generation."""
        report = self.feedback.get_calibration_report()

        self.assertIsInstance(report, str)
        self.assertIn("CALIBRATION REPORT", report)
        self.assertIn("Calibration Error", report)

    def test_get_source_recommendations(self):
        """Test source recommendations."""
        recs = self.feedback.get_source_recommendations()

        self.assertIsInstance(recs, list)
        self.assertGreater(len(recs), 0)

        # Each recommendation should be (source, recommendation, score)
        for source, rec, score in recs:
            self.assertIsInstance(source, str)
            self.assertIsInstance(rec, str)
            self.assertIsInstance(score, (int, float))

    def test_empty_data_handling(self):
        """Test handling of empty data."""
        empty_feedback = LearningFeedback(
            os.path.join(self.temp_dir, "empty_pred.json"),
            os.path.join(self.temp_dir, "empty_out.json"),
            os.path.join(self.temp_dir, "empty_cred.json")
        )

        patterns = empty_feedback.analyze_patterns()
        self.assertEqual(patterns['status'], 'insufficient_data')

        insights = empty_feedback.generate_insights()
        self.assertIsInstance(insights, str)


class TestSharpeRatioCalculation(unittest.TestCase):
    """Specific tests for Sharpe ratio calculation."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.outcomes_path = os.path.join(self.temp_dir, "outcomes.json")
        self.predictions_path = os.path.join(self.temp_dir, "predictions.json")

        # Create empty predictions file
        with open(self.predictions_path, 'w') as f:
            json.dump({"predictions": {}}, f)

        self.tracker = OutcomeTracker(self.outcomes_path, self.predictions_path)

    def tearDown(self):
        """Clean up."""
        import shutil
        shutil.rmtree(self.temp_dir)

    def test_sharpe_positive_returns(self):
        """Test Sharpe with positive average returns."""
        # All positive, consistent returns
        for ret in [10.0, 12.0, 8.0, 11.0, 9.0]:
            outcome = Outcome(
                prediction_id=f"PRED-{ret}",
                actual_return=ret,
                max_drawdown=-2.0,
                days_held=20,
                exit_reason="target_hit"
            )
            self.tracker.record(outcome)

        metrics = self.tracker.calculate_metrics()
        self.assertGreater(metrics['sharpe_ratio'], 0)

    def test_sharpe_negative_returns(self):
        """Test Sharpe with negative average returns."""
        # All negative returns
        for ret in [-10.0, -12.0, -8.0, -11.0, -9.0]:
            outcome = Outcome(
                prediction_id=f"PRED-{abs(ret)}",
                actual_return=ret,
                max_drawdown=ret,
                days_held=20,
                exit_reason="stop_loss"
            )
            self.tracker.record(outcome)

        metrics = self.tracker.calculate_metrics()
        self.assertLess(metrics['sharpe_ratio'], 0)

    def test_sharpe_mixed_returns(self):
        """Test Sharpe with mixed returns."""
        # Mix of positive and negative
        for ret in [15.0, -5.0, 10.0, -3.0, 20.0]:
            outcome = Outcome(
                prediction_id=f"PRED-{hash(ret)}",
                actual_return=ret,
                max_drawdown=min(-2.0, ret),
                days_held=20,
                exit_reason="target_hit" if ret > 0 else "stop_loss"
            )
            self.tracker.record(outcome)

        metrics = self.tracker.calculate_metrics()
        # With positive average (15-5+10-3+20)/5 = 7.4, should be positive
        self.assertGreater(metrics['sharpe_ratio'], 0)


class TestHitRateCalculation(unittest.TestCase):
    """Specific tests for hit rate calculation."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.outcomes_path = os.path.join(self.temp_dir, "outcomes.json")
        self.predictions_path = os.path.join(self.temp_dir, "predictions.json")

        with open(self.predictions_path, 'w') as f:
            json.dump({"predictions": {}}, f)

        self.tracker = OutcomeTracker(self.outcomes_path, self.predictions_path)

    def tearDown(self):
        """Clean up."""
        import shutil
        shutil.rmtree(self.temp_dir)

    def test_hit_rate_all_winners(self):
        """Test hit rate with all winners."""
        for i in range(5):
            outcome = Outcome(
                prediction_id=f"PRED-{i}",
                actual_return=10.0 + i,
                max_drawdown=-2.0,
                days_held=20,
                exit_reason="target_hit"
            )
            self.tracker.record(outcome)

        metrics = self.tracker.calculate_metrics()
        self.assertEqual(metrics['hit_rate'], 100.0)

    def test_hit_rate_all_losers(self):
        """Test hit rate with all losers."""
        for i in range(5):
            outcome = Outcome(
                prediction_id=f"PRED-{i}",
                actual_return=-10.0 - i,
                max_drawdown=-15.0,
                days_held=20,
                exit_reason="stop_loss"
            )
            self.tracker.record(outcome)

        metrics = self.tracker.calculate_metrics()
        self.assertEqual(metrics['hit_rate'], 0.0)

    def test_hit_rate_mixed(self):
        """Test hit rate with 60% winners."""
        returns = [10.0, 15.0, -5.0, 8.0, -10.0]  # 3 wins, 2 losses
        for i, ret in enumerate(returns):
            outcome = Outcome(
                prediction_id=f"PRED-{i}",
                actual_return=ret,
                max_drawdown=min(-2.0, ret),
                days_held=20,
                exit_reason="target_hit" if ret > 0 else "stop_loss"
            )
            self.tracker.record(outcome)

        metrics = self.tracker.calculate_metrics()
        self.assertEqual(metrics['hit_rate'], 60.0)


if __name__ == '__main__':
    unittest.main()
