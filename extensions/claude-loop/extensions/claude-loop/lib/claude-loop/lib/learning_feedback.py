#!/usr/bin/env python3
"""
Learning Feedback - Feed learnings back to improve research-loop system.

Analyzes patterns in predictions, updates source credibility, and generates
actionable insights from historical outcomes.
"""

import argparse
import json
import sys
from collections import defaultdict
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path

from prediction_tracker import PredictionTracker, Prediction
from outcome_tracker import OutcomeTracker, Outcome


@dataclass
class SourceCredibility:
    """Credibility score for a data source."""
    source_name: str
    credibility_score: float  # 0-100
    total_predictions: int
    successful_predictions: int
    avg_return: float
    last_updated: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        data = asdict(self)
        data['last_updated'] = self.last_updated.isoformat()
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'SourceCredibility':
        """Create from dictionary."""
        data = data.copy()
        data['last_updated'] = datetime.fromisoformat(data['last_updated'])
        return cls(**data)


class LearningFeedback:
    """Analyze patterns and generate learnings from prediction outcomes."""

    def __init__(
        self,
        predictions_path: str = "data/predictions.json",
        outcomes_path: str = "data/outcomes.json",
        credibility_path: str = "data/source_credibility.json"
    ):
        """Initialize with data paths."""
        self.predictions_path = predictions_path
        self.outcomes_path = outcomes_path
        self.credibility_path = Path(credibility_path)

        self.prediction_tracker = PredictionTracker(predictions_path)
        self.outcome_tracker = OutcomeTracker(outcomes_path, predictions_path)
        self.source_credibility: Dict[str, SourceCredibility] = {}

        self._load_credibility()

    def _load_credibility(self) -> None:
        """Load source credibility scores."""
        if self.credibility_path.exists():
            try:
                with open(self.credibility_path, 'r') as f:
                    data = json.load(f)
                    self.source_credibility = {
                        k: SourceCredibility.from_dict(v)
                        for k, v in data.get('sources', {}).items()
                    }
            except (json.JSONDecodeError, KeyError):
                self.source_credibility = {}
        else:
            self.source_credibility = {}

    def _save_credibility(self) -> None:
        """Save source credibility scores."""
        self.credibility_path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            'sources': {k: v.to_dict() for k, v in self.source_credibility.items()},
            'last_updated': datetime.now().isoformat()
        }
        with open(self.credibility_path, 'w') as f:
            json.dump(data, f, indent=2)

    def analyze_patterns(self) -> Dict[str, Any]:
        """
        Identify patterns in successful vs failed predictions.

        Returns:
            Dictionary containing identified patterns.
        """
        outcomes = self.outcome_tracker.get_all()
        if not outcomes:
            return {'status': 'insufficient_data', 'patterns': []}

        winners = [o for o in outcomes if o.actual_return > 0]
        losers = [o for o in outcomes if o.actual_return <= 0]

        patterns = []

        # Pattern 1: Confidence vs Success
        if outcomes:
            winner_confidence = [o.confidence for o in winners if o.confidence is not None]
            loser_confidence = [o.confidence for o in losers if o.confidence is not None]

            if winner_confidence and loser_confidence:
                avg_winner_conf = sum(winner_confidence) / len(winner_confidence)
                avg_loser_conf = sum(loser_confidence) / len(loser_confidence)

                patterns.append({
                    'type': 'confidence_correlation',
                    'description': f"Average confidence for winners: {avg_winner_conf:.1f}%, losers: {avg_loser_conf:.1f}%",
                    'insight': 'Higher confidence correlates with success' if avg_winner_conf > avg_loser_conf else 'Confidence does not correlate with success',
                    'data': {
                        'winner_avg_confidence': round(avg_winner_conf, 1),
                        'loser_avg_confidence': round(avg_loser_conf, 1)
                    }
                })

        # Pattern 2: Holding Period Analysis
        if winners and losers:
            avg_winner_days = sum(o.days_held for o in winners) / len(winners)
            avg_loser_days = sum(o.days_held for o in losers) / len(losers)

            patterns.append({
                'type': 'holding_period',
                'description': f"Winners held avg {avg_winner_days:.1f} days, losers {avg_loser_days:.1f} days",
                'insight': 'Winners are held longer' if avg_winner_days > avg_loser_days else 'Losers are held longer (cut losses faster)',
                'data': {
                    'winner_avg_days': round(avg_winner_days, 1),
                    'loser_avg_days': round(avg_loser_days, 1)
                }
            })

        # Pattern 3: Asset Type Performance
        asset_type_performance = defaultdict(lambda: {'wins': 0, 'losses': 0, 'returns': []})
        for outcome in outcomes:
            if outcome.asset_type:
                if outcome.actual_return > 0:
                    asset_type_performance[outcome.asset_type]['wins'] += 1
                else:
                    asset_type_performance[outcome.asset_type]['losses'] += 1
                asset_type_performance[outcome.asset_type]['returns'].append(outcome.actual_return)

        best_asset_type = None
        best_hit_rate = 0
        for asset_type, data in asset_type_performance.items():
            total = data['wins'] + data['losses']
            if total >= 3:  # Minimum sample size
                hit_rate = (data['wins'] / total) * 100
                if hit_rate > best_hit_rate:
                    best_hit_rate = hit_rate
                    best_asset_type = asset_type

        if best_asset_type:
            patterns.append({
                'type': 'asset_type_edge',
                'description': f"Best performing asset type: {best_asset_type} ({best_hit_rate:.1f}% hit rate)",
                'insight': f"Consider focusing on {best_asset_type} predictions",
                'data': {
                    'best_asset_type': best_asset_type,
                    'hit_rate': round(best_hit_rate, 1)
                }
            })

        # Pattern 4: Exit Reason Analysis
        exit_performance = defaultdict(list)
        for outcome in outcomes:
            exit_performance[outcome.exit_reason].append(outcome.actual_return)

        for reason, returns in exit_performance.items():
            avg_return = sum(returns) / len(returns)
            patterns.append({
                'type': 'exit_analysis',
                'description': f"'{reason}' exits: {len(returns)} trades, avg return {avg_return:+.2f}%",
                'insight': f"{'Good' if avg_return > 0 else 'Poor'} performance when {reason}",
                'data': {
                    'exit_reason': reason,
                    'count': len(returns),
                    'avg_return': round(avg_return, 2)
                }
            })

        # Pattern 5: Source Performance
        source_performance = self.outcome_tracker.calculate_source_metrics()
        if source_performance:
            best_source = max(source_performance.items(), key=lambda x: x[1]['avg_return'])
            worst_source = min(source_performance.items(), key=lambda x: x[1]['avg_return'])

            if best_source[1]['total_predictions'] >= 2:
                patterns.append({
                    'type': 'source_edge',
                    'description': f"Best source: {best_source[0]} ({best_source[1]['avg_return']:+.2f}% avg)",
                    'insight': f"Prioritize signals from {best_source[0]}",
                    'data': best_source[1]
                })

            if worst_source[1]['total_predictions'] >= 2 and worst_source[0] != best_source[0]:
                patterns.append({
                    'type': 'source_warning',
                    'description': f"Worst source: {worst_source[0]} ({worst_source[1]['avg_return']:+.2f}% avg)",
                    'insight': f"Be cautious with signals from {worst_source[0]}",
                    'data': worst_source[1]
                })

        return {
            'status': 'success',
            'total_analyzed': len(outcomes),
            'winners': len(winners),
            'losers': len(losers),
            'patterns': patterns
        }

    def update_source_credibility(self, outcomes: Optional[List[Outcome]] = None) -> Dict[str, SourceCredibility]:
        """
        Adjust source credibility based on prediction accuracy.

        Args:
            outcomes: List of outcomes to analyze (defaults to all)

        Returns:
            Updated source credibility scores
        """
        if outcomes is None:
            outcomes = self.outcome_tracker.get_all()

        # Aggregate by source
        source_stats: Dict[str, Dict[str, Any]] = defaultdict(
            lambda: {'total': 0, 'successes': 0, 'returns': []}
        )

        for outcome in outcomes:
            if outcome.sources:
                for source in outcome.sources:
                    source_stats[source]['total'] += 1
                    if outcome.actual_return > 0:
                        source_stats[source]['successes'] += 1
                    source_stats[source]['returns'].append(outcome.actual_return)

        # Calculate credibility scores
        for source, stats in source_stats.items():
            if stats['total'] == 0:
                continue

            hit_rate = (stats['successes'] / stats['total']) * 100
            avg_return = sum(stats['returns']) / len(stats['returns'])

            # Credibility score: weighted combination of hit rate and return
            # Base score from hit rate (0-60 points)
            # Bonus/penalty from average return (-40 to +40 points)
            base_score = hit_rate * 0.6
            return_modifier = min(40, max(-40, avg_return * 2))
            credibility = max(0, min(100, base_score + return_modifier + 20))

            self.source_credibility[source] = SourceCredibility(
                source_name=source,
                credibility_score=round(credibility, 1),
                total_predictions=stats['total'],
                successful_predictions=stats['successes'],
                avg_return=round(avg_return, 2)
            )

        self._save_credibility()
        return self.source_credibility

    def get_source_credibility(self, source: str) -> Optional[SourceCredibility]:
        """Get credibility score for a specific source."""
        return self.source_credibility.get(source)

    def get_all_credibility(self) -> Dict[str, SourceCredibility]:
        """Get all source credibility scores."""
        return self.source_credibility.copy()

    def generate_insights(self) -> str:
        """
        Generate actionable insights from outcomes.

        Returns:
            Formatted string with insights and recommendations.
        """
        insights = []

        # Get metrics
        metrics = self.outcome_tracker.calculate_metrics()
        patterns = self.analyze_patterns()
        calibration = self.outcome_tracker.calculate_confidence_calibration()

        # Overall performance insight
        if metrics['total_trades'] > 0:
            insights.append("=== OVERALL PERFORMANCE ===")
            if metrics['hit_rate'] >= 50:
                insights.append(f"+ Positive hit rate: {metrics['hit_rate']}%")
            else:
                insights.append(f"- Below 50% hit rate: {metrics['hit_rate']}%")

            if metrics['profit_factor'] > 1:
                insights.append(f"+ Profitable system (profit factor: {metrics['profit_factor']})")
            else:
                insights.append(f"- Unprofitable system (profit factor: {metrics['profit_factor']})")

            if metrics['sharpe_ratio'] > 1:
                insights.append(f"+ Good risk-adjusted returns (Sharpe: {metrics['sharpe_ratio']})")
            elif metrics['sharpe_ratio'] > 0:
                insights.append(f"  Modest risk-adjusted returns (Sharpe: {metrics['sharpe_ratio']})")
            else:
                insights.append(f"- Poor risk-adjusted returns (Sharpe: {metrics['sharpe_ratio']})")

        # Calibration insights
        if calibration['buckets']:
            insights.append("\n=== CONFIDENCE CALIBRATION ===")
            cal_error = calibration['calibration_error']
            if cal_error < 10:
                insights.append(f"+ Well-calibrated confidence (error: {cal_error}%)")
            elif cal_error < 20:
                insights.append(f"  Moderately calibrated (error: {cal_error}%)")
            else:
                insights.append(f"- Poorly calibrated confidence (error: {cal_error}%)")

            # Check for systematic over/under confidence
            overconfident_buckets = 0
            underconfident_buckets = 0
            for bucket, data in calibration['buckets'].items():
                if data['difference'] < -5:
                    overconfident_buckets += 1
                elif data['difference'] > 5:
                    underconfident_buckets += 1

            if overconfident_buckets > underconfident_buckets:
                insights.append("  Tendency: Overconfident - reduce confidence levels")
            elif underconfident_buckets > overconfident_buckets:
                insights.append("  Tendency: Underconfident - increase confidence levels")

        # Pattern-based insights
        if patterns['patterns']:
            insights.append("\n=== KEY PATTERNS ===")
            for pattern in patterns['patterns']:
                if pattern['type'] in ['source_edge', 'asset_type_edge']:
                    insights.append(f"+ {pattern['description']}")
                    insights.append(f"  -> {pattern['insight']}")
                elif pattern['type'] == 'source_warning':
                    insights.append(f"- {pattern['description']}")
                    insights.append(f"  -> {pattern['insight']}")

        # Source credibility insights
        self.update_source_credibility()
        if self.source_credibility:
            insights.append("\n=== SOURCE CREDIBILITY ===")
            sorted_sources = sorted(
                self.source_credibility.values(),
                key=lambda x: x.credibility_score,
                reverse=True
            )

            for sc in sorted_sources[:5]:  # Top 5 sources
                emoji = "+" if sc.credibility_score >= 60 else "-" if sc.credibility_score < 40 else " "
                insights.append(f"{emoji} {sc.source_name}: {sc.credibility_score}/100 ({sc.total_predictions} predictions)")

        # Actionable recommendations
        insights.append("\n=== RECOMMENDATIONS ===")

        # Based on exit reasons
        if metrics.get('by_exit_reason'):
            target_data = metrics['by_exit_reason'].get('target_hit', {})
            stop_data = metrics['by_exit_reason'].get('stop_loss', {})

            if target_data and stop_data:
                if stop_data.get('count', 0) > target_data.get('count', 0):
                    insights.append("1. Too many stop-outs - consider wider stops or better entry timing")
                else:
                    insights.append("1. Good target hit ratio - current strategy working")

        # Based on Sharpe
        if metrics['sharpe_ratio'] < 0.5 and metrics['total_trades'] >= 10:
            insights.append("2. Improve risk management to increase Sharpe ratio")

        # Based on calibration
        if calibration['calibration_error'] > 15:
            insights.append("3. Recalibrate confidence estimates based on historical accuracy")

        return "\n".join(insights)

    def get_calibration_report(self) -> str:
        """
        Compare predicted vs actual confidence.

        Returns:
            Formatted calibration report.
        """
        calibration = self.outcome_tracker.calculate_confidence_calibration()

        lines = ["=== CONFIDENCE CALIBRATION REPORT ==="]
        lines.append(f"\nOverall Calibration Error: {calibration['calibration_error']}%")
        lines.append("(Lower is better - 0% means perfect calibration)")

        lines.append("\n--- Breakdown by Confidence Bucket ---")

        for bucket, data in calibration['buckets'].items():
            lines.append(f"\nConfidence {bucket}%:")
            lines.append(f"  Predictions: {data['count']}")
            lines.append(f"  Expected Success Rate: {data['expected_success']}%")
            lines.append(f"  Actual Success Rate: {data['actual_success']}%")
            diff = data['difference']
            if abs(diff) <= 5:
                assessment = "Well calibrated"
            elif diff < -5:
                assessment = f"Overconfident by {abs(diff):.1f}%"
            else:
                assessment = f"Underconfident by {diff:.1f}%"
            lines.append(f"  Assessment: {assessment}")

        # Recommendations
        lines.append("\n--- Recommendations ---")
        if calibration['calibration_error'] < 10:
            lines.append("Your confidence estimates are well-calibrated. Continue current approach.")
        elif calibration['calibration_error'] < 20:
            lines.append("Room for improvement in confidence calibration.")
            # Find worst calibrated bucket
            worst = max(calibration['buckets'].items(), key=lambda x: abs(x[1]['difference']))
            lines.append(f"Focus on improving {worst[0]}% confidence predictions.")
        else:
            lines.append("Significant calibration issues detected.")
            lines.append("Consider using historical hit rates to guide confidence levels.")

        return "\n".join(lines)

    def get_source_recommendations(self) -> List[Tuple[str, str, float]]:
        """
        Get recommendations for each source based on credibility.

        Returns:
            List of (source, recommendation, credibility_score) tuples.
        """
        self.update_source_credibility()

        recommendations = []
        for source, cred in self.source_credibility.items():
            if cred.credibility_score >= 70:
                rec = "HIGH PRIORITY - Actively seek signals from this source"
            elif cred.credibility_score >= 50:
                rec = "MODERATE - Continue monitoring, moderate position sizes"
            elif cred.credibility_score >= 30:
                rec = "CAUTIOUS - Reduce weight, require confirmation from other sources"
            else:
                rec = "AVOID - Historical performance suggests ignoring this source"

            recommendations.append((source, rec, cred.credibility_score))

        return sorted(recommendations, key=lambda x: x[2], reverse=True)


def main():
    """CLI interface for learning feedback."""
    parser = argparse.ArgumentParser(description='Generate learning feedback')
    subparsers = parser.add_subparsers(dest='command', help='Commands')

    # Insights command
    insights_parser = subparsers.add_parser('insights', help='Generate insights')
    insights_parser.add_argument('--predictions-store', default='data/predictions.json')
    insights_parser.add_argument('--outcomes-store', default='data/outcomes.json')
    insights_parser.add_argument('--credibility-store', default='data/source_credibility.json')

    # Patterns command
    patterns_parser = subparsers.add_parser('patterns', help='Analyze patterns')
    patterns_parser.add_argument('--predictions-store', default='data/predictions.json')
    patterns_parser.add_argument('--outcomes-store', default='data/outcomes.json')
    patterns_parser.add_argument('--credibility-store', default='data/source_credibility.json')

    # Calibration command
    cal_parser = subparsers.add_parser('calibration', help='Calibration report')
    cal_parser.add_argument('--predictions-store', default='data/predictions.json')
    cal_parser.add_argument('--outcomes-store', default='data/outcomes.json')
    cal_parser.add_argument('--credibility-store', default='data/source_credibility.json')

    # Credibility command
    cred_parser = subparsers.add_parser('credibility', help='Update source credibility')
    cred_parser.add_argument('--predictions-store', default='data/predictions.json')
    cred_parser.add_argument('--outcomes-store', default='data/outcomes.json')
    cred_parser.add_argument('--credibility-store', default='data/source_credibility.json')

    # Recommendations command
    rec_parser = subparsers.add_parser('recommendations', help='Source recommendations')
    rec_parser.add_argument('--predictions-store', default='data/predictions.json')
    rec_parser.add_argument('--outcomes-store', default='data/outcomes.json')
    rec_parser.add_argument('--credibility-store', default='data/source_credibility.json')

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    feedback = LearningFeedback(
        args.predictions_store,
        args.outcomes_store,
        args.credibility_store
    )

    if args.command == 'insights':
        print(feedback.generate_insights())

    elif args.command == 'patterns':
        patterns = feedback.analyze_patterns()
        print(f"Analyzed {patterns['total_analyzed']} outcomes")
        print(f"Winners: {patterns['winners']}, Losers: {patterns['losers']}")
        print("\nIdentified Patterns:")
        for pattern in patterns['patterns']:
            print(f"\n[{pattern['type'].upper()}]")
            print(f"  {pattern['description']}")
            print(f"  Insight: {pattern['insight']}")

    elif args.command == 'calibration':
        print(feedback.get_calibration_report())

    elif args.command == 'credibility':
        credibility = feedback.update_source_credibility()
        print("Source Credibility Scores:")
        for source, cred in sorted(credibility.items(), key=lambda x: x[1].credibility_score, reverse=True):
            print(f"\n{source}:")
            print(f"  Score: {cred.credibility_score}/100")
            print(f"  Hit Rate: {(cred.successful_predictions / cred.total_predictions * 100):.1f}%")
            print(f"  Avg Return: {cred.avg_return:+.2f}%")
            print(f"  Total Predictions: {cred.total_predictions}")

    elif args.command == 'recommendations':
        recommendations = feedback.get_source_recommendations()
        if not recommendations:
            print("No source data available for recommendations")
            sys.exit(0)

        print("Source Recommendations:\n")
        for source, rec, score in recommendations:
            print(f"{source} (Score: {score}/100)")
            print(f"  {rec}")
            print()


if __name__ == '__main__':
    main()
