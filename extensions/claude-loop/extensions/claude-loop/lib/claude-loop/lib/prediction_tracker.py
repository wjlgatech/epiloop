#!/usr/bin/env python3
"""
Prediction Tracker - Track investment predictions for research-loop.

Records predictions with entry price, targets, stop-loss, and tracks
their status through resolution.
"""

import argparse
import json
import os
import sys
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import List, Optional, Dict, Any
from pathlib import Path


@dataclass
class Prediction:
    """Investment prediction with entry, targets, and metadata."""
    id: str
    research_id: str
    asset: str  # ticker or token
    asset_type: str  # stock, crypto, option
    entry_price: float
    entry_date: datetime
    targets: List[float]  # Price targets
    stop_loss: float
    timeframe_days: int
    thesis: str
    confidence: int  # 1-100
    sources: List[str]
    status: str = "active"  # active, hit_target, stopped_out, expired
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    exit_price: Optional[float] = None
    exit_date: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        data = asdict(self)
        data['entry_date'] = self.entry_date.isoformat()
        data['created_at'] = self.created_at.isoformat()
        data['updated_at'] = self.updated_at.isoformat()
        if self.exit_date:
            data['exit_date'] = self.exit_date.isoformat()
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Prediction':
        """Create Prediction from dictionary."""
        data = data.copy()
        data['entry_date'] = datetime.fromisoformat(data['entry_date'])
        data['created_at'] = datetime.fromisoformat(data['created_at'])
        data['updated_at'] = datetime.fromisoformat(data['updated_at'])
        if data.get('exit_date'):
            data['exit_date'] = datetime.fromisoformat(data['exit_date'])
        return cls(**data)

    def is_expired(self) -> bool:
        """Check if prediction has exceeded its timeframe."""
        if self.status != "active":
            return False
        days_elapsed = (datetime.now() - self.entry_date).days
        return days_elapsed > self.timeframe_days

    def check_price(self, current_price: float) -> Optional[str]:
        """
        Check if current price triggers target or stop-loss.
        Returns new status if triggered, None otherwise.
        """
        if self.status != "active":
            return None

        # Check stop-loss (assuming long position)
        if current_price <= self.stop_loss:
            return "stopped_out"

        # Check targets (any target hit counts)
        for target in self.targets:
            if current_price >= target:
                return "hit_target"

        # Check expiry
        if self.is_expired():
            return "expired"

        return None


class PredictionTracker:
    """Track and manage investment predictions."""

    def __init__(self, store_path: str = "data/predictions.json"):
        """Initialize tracker with storage path."""
        self.store_path = Path(store_path)
        self.predictions: Dict[str, Prediction] = {}
        self._load()

    def _load(self) -> None:
        """Load predictions from JSON file."""
        if self.store_path.exists():
            try:
                with open(self.store_path, 'r') as f:
                    data = json.load(f)
                    self.predictions = {
                        k: Prediction.from_dict(v)
                        for k, v in data.get('predictions', {}).items()
                    }
            except (json.JSONDecodeError, KeyError) as e:
                print(f"Warning: Error loading predictions: {e}")
                self.predictions = {}
        else:
            self.predictions = {}

    def _save(self) -> None:
        """Save predictions to JSON file."""
        self.store_path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            'predictions': {k: v.to_dict() for k, v in self.predictions.items()},
            'last_updated': datetime.now().isoformat()
        }
        with open(self.store_path, 'w') as f:
            json.dump(data, f, indent=2)

    def _generate_id(self) -> str:
        """Generate unique prediction ID."""
        existing_ids = set(self.predictions.keys())
        counter = len(self.predictions) + 1
        while True:
            new_id = f"PRED-{counter:04d}"
            if new_id not in existing_ids:
                return new_id
            counter += 1

    def record(self, prediction: Prediction) -> str:
        """
        Record a new prediction.

        Args:
            prediction: Prediction object to record

        Returns:
            The prediction ID
        """
        if not prediction.id:
            prediction.id = self._generate_id()

        prediction.created_at = datetime.now()
        prediction.updated_at = datetime.now()

        self.predictions[prediction.id] = prediction
        self._save()
        return prediction.id

    def get(self, prediction_id: str) -> Optional[Prediction]:
        """Get a prediction by ID."""
        return self.predictions.get(prediction_id)

    def get_all(self) -> List[Prediction]:
        """Get all predictions."""
        return list(self.predictions.values())

    def get_active(self) -> List[Prediction]:
        """Get all active predictions."""
        return [p for p in self.predictions.values() if p.status == "active"]

    def get_by_status(self, status: str) -> List[Prediction]:
        """Get predictions by status."""
        return [p for p in self.predictions.values() if p.status == status]

    def update_status(
        self,
        prediction_id: str,
        status: str,
        exit_price: float,
        exit_date: Optional[datetime] = None
    ) -> bool:
        """
        Update prediction status when resolved.

        Args:
            prediction_id: ID of prediction to update
            status: New status (hit_target, stopped_out, expired)
            exit_price: Price at exit
            exit_date: Date of exit (defaults to now)

        Returns:
            True if updated successfully, False if prediction not found
        """
        if prediction_id not in self.predictions:
            return False

        prediction = self.predictions[prediction_id]
        prediction.status = status
        prediction.exit_price = exit_price
        prediction.exit_date = exit_date or datetime.now()
        prediction.updated_at = datetime.now()

        self._save()
        return True

    def get_by_asset(self, asset: str) -> List[Prediction]:
        """Get all predictions for a specific asset."""
        asset_upper = asset.upper()
        return [
            p for p in self.predictions.values()
            if p.asset.upper() == asset_upper
        ]

    def get_by_asset_type(self, asset_type: str) -> List[Prediction]:
        """Get all predictions for a specific asset type."""
        return [
            p for p in self.predictions.values()
            if p.asset_type.lower() == asset_type.lower()
        ]

    def get_by_source(self, source: str) -> List[Prediction]:
        """Get all predictions that used a specific source."""
        source_lower = source.lower()
        return [
            p for p in self.predictions.values()
            if any(source_lower in s.lower() for s in p.sources)
        ]

    def get_by_research_id(self, research_id: str) -> List[Prediction]:
        """Get all predictions for a specific research session."""
        return [
            p for p in self.predictions.values()
            if p.research_id == research_id
        ]

    def check_and_update_expirations(self) -> List[str]:
        """
        Check all active predictions for expiration and update status.

        Returns:
            List of prediction IDs that were expired
        """
        expired_ids = []
        for pred in self.get_active():
            if pred.is_expired():
                self.update_status(
                    pred.id,
                    "expired",
                    pred.entry_price  # Use entry price as "exit" for expired
                )
                expired_ids.append(pred.id)
        return expired_ids

    def get_statistics(self) -> Dict[str, Any]:
        """Get summary statistics of predictions."""
        all_preds = self.get_all()
        active = self.get_active()

        by_status = {}
        for pred in all_preds:
            by_status[pred.status] = by_status.get(pred.status, 0) + 1

        by_asset_type = {}
        for pred in all_preds:
            by_asset_type[pred.asset_type] = by_asset_type.get(pred.asset_type, 0) + 1

        avg_confidence = 0
        if all_preds:
            avg_confidence = sum(p.confidence for p in all_preds) / len(all_preds)

        return {
            'total': len(all_preds),
            'active': len(active),
            'by_status': by_status,
            'by_asset_type': by_asset_type,
            'avg_confidence': round(avg_confidence, 1)
        }


def main():
    """CLI interface for prediction tracker."""
    parser = argparse.ArgumentParser(description='Track investment predictions')
    subparsers = parser.add_subparsers(dest='command', help='Commands')

    # Record command
    record_parser = subparsers.add_parser('record', help='Record a new prediction')
    record_parser.add_argument('--asset', required=True, help='Asset ticker/token')
    record_parser.add_argument('--type', dest='asset_type', default='stock',
                               choices=['stock', 'crypto', 'option'],
                               help='Asset type')
    record_parser.add_argument('--entry', type=float, required=True,
                               help='Entry price')
    record_parser.add_argument('--target', type=float, required=True, nargs='+',
                               help='Price target(s)')
    record_parser.add_argument('--stop', type=float, required=True,
                               help='Stop-loss price')
    record_parser.add_argument('--timeframe', type=int, default=30,
                               help='Timeframe in days')
    record_parser.add_argument('--thesis', default='',
                               help='Investment thesis')
    record_parser.add_argument('--confidence', type=int, default=50,
                               help='Confidence level (1-100)')
    record_parser.add_argument('--sources', nargs='*', default=[],
                               help='Information sources')
    record_parser.add_argument('--research-id', default='',
                               help='Associated research ID')
    record_parser.add_argument('--store', default='data/predictions.json',
                               help='Path to predictions store')

    # List command
    list_parser = subparsers.add_parser('list', help='List predictions')
    list_parser.add_argument('--status', help='Filter by status')
    list_parser.add_argument('--asset', help='Filter by asset')
    list_parser.add_argument('--type', dest='asset_type', help='Filter by asset type')
    list_parser.add_argument('--store', default='data/predictions.json',
                             help='Path to predictions store')

    # Update command
    update_parser = subparsers.add_parser('update', help='Update prediction status')
    update_parser.add_argument('--prediction-id', required=True,
                               help='Prediction ID to update')
    update_parser.add_argument('--status', required=True,
                               choices=['hit_target', 'stopped_out', 'expired'],
                               help='New status')
    update_parser.add_argument('--exit-price', type=float, required=True,
                               help='Exit price')
    update_parser.add_argument('--store', default='data/predictions.json',
                               help='Path to predictions store')

    # Stats command
    stats_parser = subparsers.add_parser('stats', help='Show statistics')
    stats_parser.add_argument('--store', default='data/predictions.json',
                              help='Path to predictions store')

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    tracker = PredictionTracker(args.store)

    if args.command == 'record':
        prediction = Prediction(
            id='',
            research_id=args.research_id,
            asset=args.asset.upper(),
            asset_type=args.asset_type,
            entry_price=args.entry,
            entry_date=datetime.now(),
            targets=args.target,
            stop_loss=args.stop,
            timeframe_days=args.timeframe,
            thesis=args.thesis,
            confidence=args.confidence,
            sources=args.sources
        )
        pred_id = tracker.record(prediction)
        print(f"Recorded prediction: {pred_id}")
        print(f"  Asset: {prediction.asset} ({prediction.asset_type})")
        print(f"  Entry: ${prediction.entry_price:,.2f}")
        print(f"  Targets: {[f'${t:,.2f}' for t in prediction.targets]}")
        print(f"  Stop-loss: ${prediction.stop_loss:,.2f}")
        print(f"  Timeframe: {prediction.timeframe_days} days")
        print(f"  Confidence: {prediction.confidence}%")

    elif args.command == 'list':
        predictions = tracker.get_all()

        if args.status:
            predictions = [p for p in predictions if p.status == args.status]
        if args.asset:
            predictions = [p for p in predictions if p.asset.upper() == args.asset.upper()]
        if args.asset_type:
            predictions = [p for p in predictions if p.asset_type == args.asset_type]

        if not predictions:
            print("No predictions found matching criteria.")
            sys.exit(0)

        print(f"Found {len(predictions)} predictions:\n")
        for pred in predictions:
            print(f"{pred.id}: {pred.asset} ({pred.asset_type})")
            print(f"  Status: {pred.status}")
            print(f"  Entry: ${pred.entry_price:,.2f} on {pred.entry_date.strftime('%Y-%m-%d')}")
            print(f"  Targets: {[f'${t:,.2f}' for t in pred.targets]}")
            print(f"  Stop: ${pred.stop_loss:,.2f}")
            print(f"  Confidence: {pred.confidence}%")
            if pred.exit_price:
                print(f"  Exit: ${pred.exit_price:,.2f}")
            print()

    elif args.command == 'update':
        success = tracker.update_status(
            args.prediction_id,
            args.status,
            args.exit_price
        )
        if success:
            print(f"Updated {args.prediction_id} to {args.status} at ${args.exit_price:,.2f}")
        else:
            print(f"Prediction {args.prediction_id} not found")
            sys.exit(1)

    elif args.command == 'stats':
        stats = tracker.get_statistics()
        print("Prediction Statistics:")
        print(f"  Total: {stats['total']}")
        print(f"  Active: {stats['active']}")
        print(f"  Average Confidence: {stats['avg_confidence']}%")
        print(f"\nBy Status:")
        for status, count in stats['by_status'].items():
            print(f"  {status}: {count}")
        print(f"\nBy Asset Type:")
        for atype, count in stats['by_asset_type'].items():
            print(f"  {atype}: {count}")


if __name__ == '__main__':
    main()
