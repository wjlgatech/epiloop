#!/usr/bin/env python3
"""
Outcome Tracker - Track actual outcomes of predictions for research-loop.

Records outcomes with actual returns, drawdown, and calculates performance metrics.
"""

import argparse
import json
import math
import os
import sys
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import List, Optional, Dict, Any
from pathlib import Path

from prediction_tracker import PredictionTracker, Prediction


@dataclass
class Outcome:
    """Actual outcome of a prediction."""
    prediction_id: str
    actual_return: float  # Percentage
    max_drawdown: float  # Percentage (negative)
    days_held: int
    exit_reason: str  # target_hit, stop_loss, manual, expired
    lessons_learned: Optional[str] = None
    recorded_at: datetime = field(default_factory=datetime.now)

    # Additional metadata from prediction (populated on load)
    asset: Optional[str] = None
    asset_type: Optional[str] = None
    confidence: Optional[int] = None
    sources: Optional[List[str]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        data = asdict(self)
        data['recorded_at'] = self.recorded_at.isoformat()
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Outcome':
        """Create Outcome from dictionary."""
        data = data.copy()
        data['recorded_at'] = datetime.fromisoformat(data['recorded_at'])
        return cls(**data)


class OutcomeTracker:
    """Track and analyze prediction outcomes."""

    def __init__(
        self,
        store_path: str = "data/outcomes.json",
        predictions_path: str = "data/predictions.json"
    ):
        """Initialize tracker with storage paths."""
        self.store_path = Path(store_path)
        self.predictions_path = predictions_path
        self.outcomes: List[Outcome] = []
        self._load()

    def _load(self) -> None:
        """Load outcomes from JSON file."""
        if self.store_path.exists():
            try:
                with open(self.store_path, 'r') as f:
                    data = json.load(f)
                    self.outcomes = [
                        Outcome.from_dict(o)
                        for o in data.get('outcomes', [])
                    ]
            except (json.JSONDecodeError, KeyError) as e:
                print(f"Warning: Error loading outcomes: {e}")
                self.outcomes = []
        else:
            self.outcomes = []

    def _save(self) -> None:
        """Save outcomes to JSON file."""
        self.store_path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            'outcomes': [o.to_dict() for o in self.outcomes],
            'last_updated': datetime.now().isoformat()
        }
        with open(self.store_path, 'w') as f:
            json.dump(data, f, indent=2)

    def _get_prediction(self, prediction_id: str) -> Optional[Prediction]:
        """Get prediction details from prediction tracker."""
        try:
            tracker = PredictionTracker(self.predictions_path)
            return tracker.get(prediction_id)
        except Exception:
            return None

    def record(self, outcome: Outcome) -> None:
        """
        Record a new outcome.

        Args:
            outcome: Outcome object to record
        """
        # Enrich with prediction data if available
        prediction = self._get_prediction(outcome.prediction_id)
        if prediction:
            outcome.asset = prediction.asset
            outcome.asset_type = prediction.asset_type
            outcome.confidence = prediction.confidence
            outcome.sources = prediction.sources

        outcome.recorded_at = datetime.now()
        self.outcomes.append(outcome)
        self._save()

    def record_from_prediction(
        self,
        prediction_id: str,
        exit_price: float,
        exit_reason: str,
        max_drawdown: Optional[float] = None,
        lessons_learned: Optional[str] = None
    ) -> Optional[Outcome]:
        """
        Record outcome by calculating from prediction data.

        Args:
            prediction_id: ID of the prediction
            exit_price: Price at exit
            exit_reason: Reason for exit
            max_drawdown: Maximum drawdown during hold (optional)
            lessons_learned: Any lessons from this trade

        Returns:
            Created Outcome or None if prediction not found
        """
        prediction = self._get_prediction(prediction_id)
        if not prediction:
            return None

        # Calculate return
        actual_return = ((exit_price - prediction.entry_price) /
                         prediction.entry_price) * 100

        # Calculate days held
        exit_date = prediction.exit_date or datetime.now()
        days_held = (exit_date - prediction.entry_date).days

        # Estimate max drawdown if not provided
        if max_drawdown is None:
            if actual_return < 0:
                max_drawdown = actual_return
            else:
                max_drawdown = 0.0

        outcome = Outcome(
            prediction_id=prediction_id,
            actual_return=actual_return,
            max_drawdown=max_drawdown,
            days_held=days_held,
            exit_reason=exit_reason,
            lessons_learned=lessons_learned,
            asset=prediction.asset,
            asset_type=prediction.asset_type,
            confidence=prediction.confidence,
            sources=prediction.sources
        )

        self.record(outcome)
        return outcome

    def get_all(self) -> List[Outcome]:
        """Get all recorded outcomes."""
        return self.outcomes.copy()

    def get_by_prediction_id(self, prediction_id: str) -> Optional[Outcome]:
        """Get outcome for a specific prediction."""
        for outcome in self.outcomes:
            if outcome.prediction_id == prediction_id:
                return outcome
        return None

    def get_by_source(self, source: str) -> List[Outcome]:
        """Find outcomes where a specific source was used."""
        source_lower = source.lower()
        return [
            o for o in self.outcomes
            if o.sources and any(source_lower in s.lower() for s in o.sources)
        ]

    def get_by_asset_type(self, asset_type: str) -> List[Outcome]:
        """Get outcomes for a specific asset type."""
        return [
            o for o in self.outcomes
            if o.asset_type and o.asset_type.lower() == asset_type.lower()
        ]

    def get_by_exit_reason(self, exit_reason: str) -> List[Outcome]:
        """Get outcomes by exit reason."""
        return [
            o for o in self.outcomes
            if o.exit_reason == exit_reason
        ]

    def calculate_metrics(self) -> Dict[str, Any]:
        """
        Calculate comprehensive performance metrics.

        Returns:
            Dictionary with hit rate, average return, Sharpe ratio, etc.
        """
        if not self.outcomes:
            return {
                'total_trades': 0,
                'hit_rate': 0.0,
                'avg_return': 0.0,
                'total_return': 0.0,
                'sharpe_ratio': 0.0,
                'max_drawdown': 0.0,
                'avg_days_held': 0.0,
                'win_loss_ratio': 0.0,
                'profit_factor': 0.0
            }

        returns = [o.actual_return for o in self.outcomes]
        winning_trades = [r for r in returns if r > 0]
        losing_trades = [r for r in returns if r <= 0]

        # Basic metrics
        total_trades = len(returns)
        hit_rate = (len(winning_trades) / total_trades) * 100 if total_trades > 0 else 0
        avg_return = sum(returns) / total_trades if total_trades > 0 else 0
        total_return = sum(returns)

        # Sharpe Ratio (assuming risk-free rate of 0 for simplicity)
        if len(returns) > 1:
            std_dev = math.sqrt(
                sum((r - avg_return) ** 2 for r in returns) / (len(returns) - 1)
            )
            sharpe_ratio = (avg_return / std_dev) if std_dev > 0 else 0
        else:
            sharpe_ratio = 0

        # Max drawdown
        max_drawdown = min(o.max_drawdown for o in self.outcomes) if self.outcomes else 0

        # Average days held
        avg_days_held = sum(o.days_held for o in self.outcomes) / total_trades if total_trades > 0 else 0

        # Win/Loss ratio
        avg_win = sum(winning_trades) / len(winning_trades) if winning_trades else 0
        avg_loss = abs(sum(losing_trades) / len(losing_trades)) if losing_trades else 1
        win_loss_ratio = avg_win / avg_loss if avg_loss > 0 else float('inf')

        # Profit factor
        gross_profit = sum(winning_trades) if winning_trades else 0
        gross_loss = abs(sum(losing_trades)) if losing_trades else 1
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')

        # Metrics by exit reason
        by_exit_reason = {}
        for reason in ['target_hit', 'stop_loss', 'manual', 'expired']:
            reason_outcomes = self.get_by_exit_reason(reason)
            if reason_outcomes:
                reason_returns = [o.actual_return for o in reason_outcomes]
                by_exit_reason[reason] = {
                    'count': len(reason_outcomes),
                    'avg_return': sum(reason_returns) / len(reason_returns)
                }

        return {
            'total_trades': total_trades,
            'winning_trades': len(winning_trades),
            'losing_trades': len(losing_trades),
            'hit_rate': round(hit_rate, 2),
            'avg_return': round(avg_return, 2),
            'total_return': round(total_return, 2),
            'sharpe_ratio': round(sharpe_ratio, 3),
            'max_drawdown': round(max_drawdown, 2),
            'avg_days_held': round(avg_days_held, 1),
            'win_loss_ratio': round(win_loss_ratio, 2),
            'profit_factor': round(profit_factor, 2),
            'by_exit_reason': by_exit_reason
        }

    def calculate_source_metrics(self) -> Dict[str, Dict[str, Any]]:
        """
        Calculate metrics grouped by source.

        Returns:
            Dictionary mapping source names to their performance metrics.
        """
        source_outcomes: Dict[str, List[Outcome]] = {}

        for outcome in self.outcomes:
            if outcome.sources:
                for source in outcome.sources:
                    if source not in source_outcomes:
                        source_outcomes[source] = []
                    source_outcomes[source].append(outcome)

        source_metrics = {}
        for source, outcomes in source_outcomes.items():
            returns = [o.actual_return for o in outcomes]
            winning = len([r for r in returns if r > 0])

            source_metrics[source] = {
                'total_predictions': len(outcomes),
                'hit_rate': round((winning / len(outcomes)) * 100, 2) if outcomes else 0,
                'avg_return': round(sum(returns) / len(returns), 2) if returns else 0,
                'total_return': round(sum(returns), 2),
            }

        return source_metrics

    def calculate_confidence_calibration(self) -> Dict[str, Any]:
        """
        Calculate how well confidence predicts actual success.

        Returns:
            Calibration metrics comparing predicted vs actual.
        """
        if not self.outcomes:
            return {'buckets': {}, 'calibration_error': 0}

        # Group by confidence buckets
        buckets = {
            '0-20': [],
            '21-40': [],
            '41-60': [],
            '61-80': [],
            '81-100': []
        }

        for outcome in self.outcomes:
            if outcome.confidence is None:
                continue
            conf = outcome.confidence
            if conf <= 20:
                buckets['0-20'].append(outcome)
            elif conf <= 40:
                buckets['21-40'].append(outcome)
            elif conf <= 60:
                buckets['41-60'].append(outcome)
            elif conf <= 80:
                buckets['61-80'].append(outcome)
            else:
                buckets['81-100'].append(outcome)

        calibration_data = {}
        total_error = 0
        bucket_count = 0

        for bucket_name, outcomes in buckets.items():
            if not outcomes:
                continue

            # Expected success rate (midpoint of bucket)
            bucket_midpoints = {
                '0-20': 10,
                '21-40': 30,
                '41-60': 50,
                '61-80': 70,
                '81-100': 90
            }
            expected = bucket_midpoints[bucket_name]

            # Actual success rate
            successes = len([o for o in outcomes if o.actual_return > 0])
            actual = (successes / len(outcomes)) * 100

            calibration_data[bucket_name] = {
                'count': len(outcomes),
                'expected_success': expected,
                'actual_success': round(actual, 1),
                'difference': round(actual - expected, 1)
            }

            total_error += abs(actual - expected)
            bucket_count += 1

        avg_calibration_error = total_error / bucket_count if bucket_count > 0 else 0

        return {
            'buckets': calibration_data,
            'calibration_error': round(avg_calibration_error, 2)
        }


def main():
    """CLI interface for outcome tracker."""
    parser = argparse.ArgumentParser(description='Track prediction outcomes')
    subparsers = parser.add_subparsers(dest='command', help='Commands')

    # Record command
    record_parser = subparsers.add_parser('record', help='Record an outcome')
    record_parser.add_argument('--prediction-id', required=True,
                               help='Prediction ID')
    record_parser.add_argument('--exit-price', type=float, required=True,
                               help='Exit price')
    record_parser.add_argument('--reason', required=True,
                               choices=['target_hit', 'stop_loss', 'manual', 'expired'],
                               help='Exit reason')
    record_parser.add_argument('--max-drawdown', type=float,
                               help='Maximum drawdown during hold')
    record_parser.add_argument('--lessons', help='Lessons learned')
    record_parser.add_argument('--store', default='data/outcomes.json',
                               help='Path to outcomes store')
    record_parser.add_argument('--predictions-store', default='data/predictions.json',
                               help='Path to predictions store')

    # Metrics command
    metrics_parser = subparsers.add_parser('metrics', help='Calculate metrics')
    metrics_parser.add_argument('--store', default='data/outcomes.json',
                                help='Path to outcomes store')
    metrics_parser.add_argument('--predictions-store', default='data/predictions.json',
                                help='Path to predictions store')

    # Source analysis command
    source_parser = subparsers.add_parser('sources', help='Analyze sources')
    source_parser.add_argument('--store', default='data/outcomes.json',
                               help='Path to outcomes store')
    source_parser.add_argument('--predictions-store', default='data/predictions.json',
                               help='Path to predictions store')

    # Calibration command
    cal_parser = subparsers.add_parser('calibration', help='Check confidence calibration')
    cal_parser.add_argument('--store', default='data/outcomes.json',
                            help='Path to outcomes store')
    cal_parser.add_argument('--predictions-store', default='data/predictions.json',
                            help='Path to predictions store')

    # List command
    list_parser = subparsers.add_parser('list', help='List outcomes')
    list_parser.add_argument('--source', help='Filter by source')
    list_parser.add_argument('--reason', help='Filter by exit reason')
    list_parser.add_argument('--store', default='data/outcomes.json',
                             help='Path to outcomes store')
    list_parser.add_argument('--predictions-store', default='data/predictions.json',
                             help='Path to predictions store')

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    tracker = OutcomeTracker(args.store, args.predictions_store)

    if args.command == 'record':
        outcome = tracker.record_from_prediction(
            prediction_id=args.prediction_id,
            exit_price=args.exit_price,
            exit_reason=args.reason,
            max_drawdown=args.max_drawdown,
            lessons_learned=args.lessons
        )

        if outcome:
            print(f"Recorded outcome for {args.prediction_id}:")
            print(f"  Asset: {outcome.asset}")
            print(f"  Return: {outcome.actual_return:+.2f}%")
            print(f"  Max Drawdown: {outcome.max_drawdown:.2f}%")
            print(f"  Days Held: {outcome.days_held}")
            print(f"  Exit Reason: {outcome.exit_reason}")
        else:
            print(f"Prediction {args.prediction_id} not found")
            sys.exit(1)

    elif args.command == 'metrics':
        metrics = tracker.calculate_metrics()
        print("Performance Metrics:")
        print(f"  Total Trades: {metrics['total_trades']}")
        print(f"  Winning: {metrics['winning_trades']}, Losing: {metrics['losing_trades']}")
        print(f"  Hit Rate: {metrics['hit_rate']}%")
        print(f"  Average Return: {metrics['avg_return']:+.2f}%")
        print(f"  Total Return: {metrics['total_return']:+.2f}%")
        print(f"  Sharpe Ratio: {metrics['sharpe_ratio']}")
        print(f"  Max Drawdown: {metrics['max_drawdown']:.2f}%")
        print(f"  Avg Days Held: {metrics['avg_days_held']}")
        print(f"  Win/Loss Ratio: {metrics['win_loss_ratio']}")
        print(f"  Profit Factor: {metrics['profit_factor']}")

        if metrics['by_exit_reason']:
            print("\nBy Exit Reason:")
            for reason, data in metrics['by_exit_reason'].items():
                print(f"  {reason}: {data['count']} trades, {data['avg_return']:+.2f}% avg")

    elif args.command == 'sources':
        source_metrics = tracker.calculate_source_metrics()
        if not source_metrics:
            print("No source data available")
            sys.exit(0)

        print("Source Analysis:")
        # Sort by avg return
        sorted_sources = sorted(
            source_metrics.items(),
            key=lambda x: x[1]['avg_return'],
            reverse=True
        )
        for source, metrics in sorted_sources:
            print(f"\n{source}:")
            print(f"  Predictions: {metrics['total_predictions']}")
            print(f"  Hit Rate: {metrics['hit_rate']}%")
            print(f"  Avg Return: {metrics['avg_return']:+.2f}%")
            print(f"  Total Return: {metrics['total_return']:+.2f}%")

    elif args.command == 'calibration':
        cal = tracker.calculate_confidence_calibration()
        print("Confidence Calibration:")
        print(f"  Average Calibration Error: {cal['calibration_error']}%")
        print("\nBy Confidence Bucket:")
        for bucket, data in cal['buckets'].items():
            print(f"  {bucket}%: {data['count']} predictions")
            print(f"    Expected: {data['expected_success']}%, Actual: {data['actual_success']}%")
            diff = data['difference']
            direction = "overconfident" if diff < 0 else "underconfident"
            print(f"    Difference: {diff:+.1f}% ({direction})")

    elif args.command == 'list':
        outcomes = tracker.get_all()

        if args.source:
            outcomes = tracker.get_by_source(args.source)
        if args.reason:
            outcomes = [o for o in outcomes if o.exit_reason == args.reason]

        if not outcomes:
            print("No outcomes found")
            sys.exit(0)

        print(f"Found {len(outcomes)} outcomes:\n")
        for outcome in outcomes:
            print(f"{outcome.prediction_id}: {outcome.asset or 'N/A'}")
            print(f"  Return: {outcome.actual_return:+.2f}%")
            print(f"  Days Held: {outcome.days_held}")
            print(f"  Exit Reason: {outcome.exit_reason}")
            if outcome.lessons_learned:
                print(f"  Lessons: {outcome.lessons_learned}")
            print()


if __name__ == '__main__':
    main()
