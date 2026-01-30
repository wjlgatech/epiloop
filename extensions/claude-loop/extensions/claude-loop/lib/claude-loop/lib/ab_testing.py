#!/usr/bin/env python3
"""
A/B Testing Framework for CER Evaluation

This module provides statistical A/B testing capabilities to measure the
effectiveness of Contextual Experience Replay (CER) in the research loop.

Features:
- Random variant assignment with deterministic replay
- Metric recording and aggregation
- Statistical analysis (t-test, effect size)
- Significance testing with configurable confidence levels
- Multiple metric support

Usage:
    from ab_testing import ABTest

    # Create a test
    test = ABTest("cer_vs_baseline", ["with_cer", "without_cer"])

    # Assign variant for a query
    variant = test.assign_variant(query_id)

    # Run research based on variant
    if variant == "with_cer":
        # Use CER
        pass
    else:
        # Baseline without CER
        pass

    # Record results
    test.record_result(query_id, {"confidence": 75, "source_coverage": 0.8})

    # Get statistical analysis
    results = test.get_results()
    print(f"Significant: {test.is_significant()}")

CLI:
    python lib/ab_testing.py results --test cer_vs_baseline
    python lib/ab_testing.py analyze --test cer_vs_baseline --metric confidence
"""

import argparse
import hashlib
import json
import math
import random
import sys
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


# ============================================================================
# Constants
# ============================================================================

DEFAULT_STORAGE_PATH = ".claude-loop/data/ab_tests.json"


# ============================================================================
# Statistical Utilities
# ============================================================================

def mean(values: List[float]) -> float:
    """Calculate mean of values."""
    if not values:
        return 0.0
    return sum(values) / len(values)


def variance(values: List[float]) -> float:
    """Calculate sample variance of values."""
    if len(values) < 2:
        return 0.0
    m = mean(values)
    return sum((x - m) ** 2 for x in values) / (len(values) - 1)


def std_dev(values: List[float]) -> float:
    """Calculate sample standard deviation of values."""
    return math.sqrt(variance(values))


def pooled_std_dev(values1: List[float], values2: List[float]) -> float:
    """Calculate pooled standard deviation for two samples."""
    n1, n2 = len(values1), len(values2)
    if n1 + n2 < 4:
        return 0.0

    var1 = variance(values1)
    var2 = variance(values2)

    pooled_var = ((n1 - 1) * var1 + (n2 - 1) * var2) / (n1 + n2 - 2)
    return math.sqrt(pooled_var)


def t_statistic(values1: List[float], values2: List[float]) -> float:
    """
    Calculate t-statistic for independent samples t-test.

    Args:
        values1: First sample values
        values2: Second sample values

    Returns:
        t-statistic value
    """
    n1, n2 = len(values1), len(values2)
    if n1 < 2 or n2 < 2:
        return 0.0

    mean1, mean2 = mean(values1), mean(values2)
    var1, var2 = variance(values1), variance(values2)

    # Welch's t-test (unequal variances)
    se = math.sqrt(var1 / n1 + var2 / n2)
    if se == 0:
        return 0.0

    return (mean1 - mean2) / se


def degrees_of_freedom_welch(values1: List[float], values2: List[float]) -> float:
    """
    Calculate degrees of freedom for Welch's t-test.

    Uses Welch-Satterthwaite equation.
    """
    n1, n2 = len(values1), len(values2)
    if n1 < 2 or n2 < 2:
        return 0.0

    var1, var2 = variance(values1), variance(values2)
    if var1 == 0 and var2 == 0:
        return n1 + n2 - 2

    numerator = (var1 / n1 + var2 / n2) ** 2
    denominator = (var1 / n1) ** 2 / (n1 - 1) + (var2 / n2) ** 2 / (n2 - 1)

    if denominator == 0:
        return n1 + n2 - 2

    return numerator / denominator


def t_to_p_value(t: float, df: float) -> float:
    """
    Approximate p-value from t-statistic and degrees of freedom.

    Uses approximation since we don't want scipy dependency.
    This is accurate for df > 3.
    """
    if df <= 0:
        return 1.0

    # Use approximation based on normal distribution for large df
    if df > 100:
        # For large df, t-distribution approaches normal
        # Use error function approximation
        x = abs(t)
        # Simple approximation: P(|T| > t) ≈ 2 * (1 - Φ(t)) for large df
        # Using logistic approximation to normal CDF
        z = x / math.sqrt(1 + 0.044715 * x * x)
        p = 2 * (1 - 1 / (1 + math.exp(-1.702 * z)))
        return max(0.0001, min(1.0, p))

    # For smaller df, use approximation
    # This is less accurate but avoids scipy dependency
    t_abs = abs(t)

    # Critical values for common significance levels (two-tailed)
    # These are approximate for df=30 and scaled
    scale = 1 + 2 / df if df > 0 else 2

    if t_abs > 3.5 * scale:
        return 0.001
    elif t_abs > 2.75 * scale:
        return 0.01
    elif t_abs > 2.0 * scale:
        return 0.05
    elif t_abs > 1.7 * scale:
        return 0.1
    elif t_abs > 1.3 * scale:
        return 0.2
    else:
        return 0.5


def cohens_d(values1: List[float], values2: List[float]) -> float:
    """
    Calculate Cohen's d effect size.

    Args:
        values1: First sample (treatment)
        values2: Second sample (control)

    Returns:
        Cohen's d effect size
    """
    if len(values1) < 2 or len(values2) < 2:
        return 0.0

    mean_diff = mean(values1) - mean(values2)
    pooled_sd = pooled_std_dev(values1, values2)

    if pooled_sd == 0:
        return 0.0

    return mean_diff / pooled_sd


def effect_size_interpretation(d: float) -> str:
    """
    Interpret Cohen's d effect size.

    Args:
        d: Cohen's d value

    Returns:
        Interpretation string
    """
    d_abs = abs(d)
    if d_abs < 0.2:
        return "negligible"
    elif d_abs < 0.5:
        return "small"
    elif d_abs < 0.8:
        return "medium"
    else:
        return "large"


# ============================================================================
# Data Classes
# ============================================================================

@dataclass
class ABTestResult:
    """Result of a single A/B test observation."""
    query_id: str
    variant: str
    metrics: Dict[str, float]
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict:
        return {
            'query_id': self.query_id,
            'variant': self.variant,
            'metrics': self.metrics,
            'timestamp': self.timestamp
        }

    @classmethod
    def from_dict(cls, data: Dict) -> 'ABTestResult':
        return cls(
            query_id=data['query_id'],
            variant=data['variant'],
            metrics=data.get('metrics', {}),
            timestamp=data.get('timestamp', datetime.now(timezone.utc).isoformat())
        )


@dataclass
class StatisticalAnalysis:
    """Statistical analysis of A/B test results."""
    metric: str
    variant_a: str
    variant_b: str
    n_a: int
    n_b: int
    mean_a: float
    mean_b: float
    std_a: float
    std_b: float
    mean_diff: float
    t_statistic: float
    degrees_of_freedom: float
    p_value: float
    cohens_d: float
    effect_interpretation: str
    is_significant: bool
    confidence_level: float

    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class ABTestSummary:
    """Summary of A/B test results."""
    test_name: str
    variants: List[str]
    total_observations: int
    observations_by_variant: Dict[str, int]
    metrics_analyzed: List[str]
    analyses: List[StatisticalAnalysis]
    created_at: str
    overall_significant: bool
    primary_metric_improvement: Optional[float]

    def to_dict(self) -> Dict:
        return {
            'test_name': self.test_name,
            'variants': self.variants,
            'total_observations': self.total_observations,
            'observations_by_variant': self.observations_by_variant,
            'metrics_analyzed': self.metrics_analyzed,
            'analyses': [a.to_dict() for a in self.analyses],
            'created_at': self.created_at,
            'overall_significant': self.overall_significant,
            'primary_metric_improvement': self.primary_metric_improvement
        }


# ============================================================================
# A/B Test Class
# ============================================================================

class ABTest:
    """
    A/B Testing framework for comparing variants.

    Supports:
    - Multiple variants (not just A/B)
    - Multiple metrics
    - Statistical significance testing
    - Effect size calculation
    - Persistent storage
    """

    def __init__(
        self,
        test_name: str,
        variants: List[str],
        storage_path: Optional[str] = None,
        primary_metric: str = "confidence"
    ):
        """
        Initialize A/B test.

        Args:
            test_name: Unique name for this test
            variants: List of variant names (e.g., ["with_cer", "without_cer"])
            storage_path: Path to JSON storage file
            primary_metric: Primary metric for overall significance
        """
        self.test_name = test_name
        self.variants = variants
        self.primary_metric = primary_metric

        if storage_path is None:
            storage_path = DEFAULT_STORAGE_PATH

        self.storage_path = Path(storage_path)
        self.results: List[ABTestResult] = []
        self._assignments: Dict[str, str] = {}
        self._loaded = False

    def _ensure_loaded(self):
        """Ensure test data is loaded from disk."""
        if not self._loaded:
            self._load()

    def _load(self):
        """Load test data from JSON file."""
        if self.storage_path.exists():
            try:
                with open(self.storage_path, 'r') as f:
                    data = json.load(f)

                # Find our test in the data
                tests = data.get('tests', {})
                if self.test_name in tests:
                    test_data = tests[self.test_name]
                    self.results = [
                        ABTestResult.from_dict(r)
                        for r in test_data.get('results', [])
                    ]
                    self._assignments = test_data.get('assignments', {})
            except (json.JSONDecodeError, KeyError):
                pass

        self._loaded = True

    def _save(self):
        """Save test data to JSON file."""
        # Load existing data
        all_data = {'tests': {}}
        if self.storage_path.exists():
            try:
                with open(self.storage_path, 'r') as f:
                    all_data = json.load(f)
            except (json.JSONDecodeError, KeyError):
                pass

        # Update our test
        all_data['tests'][self.test_name] = {
            'variants': self.variants,
            'primary_metric': self.primary_metric,
            'results': [r.to_dict() for r in self.results],
            'assignments': self._assignments,
            'updated_at': datetime.now(timezone.utc).isoformat()
        }

        # Ensure directory exists
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)

        with open(self.storage_path, 'w') as f:
            json.dump(all_data, f, indent=2)

    def assign_variant(self, query_id: str, deterministic: bool = True) -> str:
        """
        Assign a variant for a query.

        Args:
            query_id: Unique identifier for the query
            deterministic: If True, same query_id always gets same variant

        Returns:
            Assigned variant name
        """
        self._ensure_loaded()

        # Check for existing assignment
        if query_id in self._assignments:
            return self._assignments[query_id]

        if deterministic:
            # Use hash for deterministic assignment
            hash_val = int(hashlib.sha256(
                f"{self.test_name}:{query_id}".encode()
            ).hexdigest(), 16)
            variant_idx = hash_val % len(self.variants)
        else:
            # Random assignment
            variant_idx = random.randint(0, len(self.variants) - 1)

        variant = self.variants[variant_idx]
        self._assignments[query_id] = variant
        self._save()

        return variant

    def record_result(self, query_id: str, metrics: Dict[str, float]) -> ABTestResult:
        """
        Record result for a query.

        Args:
            query_id: Query identifier (must have been assigned a variant)
            metrics: Dictionary of metric name to value

        Returns:
            ABTestResult record
        """
        self._ensure_loaded()

        # Get variant assignment
        variant = self._assignments.get(query_id)
        if variant is None:
            # Auto-assign if not already assigned
            variant = self.assign_variant(query_id)

        # Create result
        result = ABTestResult(
            query_id=query_id,
            variant=variant,
            metrics=metrics
        )

        self.results.append(result)
        self._save()

        return result

    def get_results(self) -> ABTestSummary:
        """
        Get comprehensive test results with statistical analysis.

        Returns:
            ABTestSummary with all analyses
        """
        self._ensure_loaded()

        # Group results by variant
        by_variant: Dict[str, List[ABTestResult]] = {v: [] for v in self.variants}
        for result in self.results:
            if result.variant in by_variant:
                by_variant[result.variant].append(result)

        # Get all metrics
        all_metrics = set()
        for result in self.results:
            all_metrics.update(result.metrics.keys())

        # Analyze each metric for each variant pair
        analyses = []
        if len(self.variants) >= 2:
            # Compare first two variants (A vs B)
            var_a, var_b = self.variants[0], self.variants[1]

            for metric in sorted(all_metrics):
                analysis = self._analyze_metric(
                    metric=metric,
                    results_a=by_variant[var_a],
                    results_b=by_variant[var_b],
                    var_a=var_a,
                    var_b=var_b
                )
                analyses.append(analysis)

        # Determine overall significance from primary metric
        overall_significant = False
        primary_improvement = None

        for analysis in analyses:
            if analysis.metric == self.primary_metric:
                overall_significant = analysis.is_significant
                primary_improvement = analysis.mean_diff

        return ABTestSummary(
            test_name=self.test_name,
            variants=self.variants,
            total_observations=len(self.results),
            observations_by_variant={v: len(by_variant[v]) for v in self.variants},
            metrics_analyzed=list(sorted(all_metrics)),
            analyses=analyses,
            created_at=datetime.now(timezone.utc).isoformat(),
            overall_significant=overall_significant,
            primary_metric_improvement=primary_improvement
        )

    def _analyze_metric(
        self,
        metric: str,
        results_a: List[ABTestResult],
        results_b: List[ABTestResult],
        var_a: str,
        var_b: str,
        confidence: float = 0.95
    ) -> StatisticalAnalysis:
        """
        Perform statistical analysis for a single metric.

        Args:
            metric: Metric name
            results_a: Results for variant A
            results_b: Results for variant B
            var_a: Variant A name
            var_b: Variant B name
            confidence: Confidence level for significance testing

        Returns:
            StatisticalAnalysis results
        """
        # Extract metric values
        values_a = [r.metrics.get(metric, 0) for r in results_a if metric in r.metrics]
        values_b = [r.metrics.get(metric, 0) for r in results_b if metric in r.metrics]

        # Calculate statistics
        mean_a = mean(values_a)
        mean_b = mean(values_b)
        std_a = std_dev(values_a)
        std_b = std_dev(values_b)

        # Statistical tests
        t_stat = t_statistic(values_a, values_b)
        df = degrees_of_freedom_welch(values_a, values_b)
        p_val = t_to_p_value(t_stat, df)
        d = cohens_d(values_a, values_b)

        # Determine significance
        alpha = 1 - confidence
        is_significant = p_val < alpha and abs(d) >= 0.3

        return StatisticalAnalysis(
            metric=metric,
            variant_a=var_a,
            variant_b=var_b,
            n_a=len(values_a),
            n_b=len(values_b),
            mean_a=mean_a,
            mean_b=mean_b,
            std_a=std_a,
            std_b=std_b,
            mean_diff=mean_a - mean_b,
            t_statistic=t_stat,
            degrees_of_freedom=df,
            p_value=p_val,
            cohens_d=d,
            effect_interpretation=effect_size_interpretation(d),
            is_significant=is_significant,
            confidence_level=confidence
        )

    def is_significant(self, confidence: float = 0.95) -> bool:
        """
        Check if the test shows significant improvement.

        Args:
            confidence: Confidence level (default 0.95 = 95%)

        Returns:
            True if primary metric shows significant improvement
        """
        results = self.get_results()

        for analysis in results.analyses:
            if analysis.metric == self.primary_metric:
                alpha = 1 - confidence
                # Check both statistical significance and effect size
                return analysis.p_value < alpha and abs(analysis.cohens_d) >= 0.3

        return False

    def get_power_analysis(self, effect_size: float = 0.5, alpha: float = 0.05) -> Dict:
        """
        Get power analysis for the current sample size.

        Args:
            effect_size: Expected effect size (Cohen's d)
            alpha: Significance level

        Returns:
            Dictionary with power analysis
        """
        self._ensure_loaded()

        # Get sample sizes
        by_variant = {v: 0 for v in self.variants}
        for result in self.results:
            if result.variant in by_variant:
                by_variant[result.variant] += 1

        n_per_group = min(by_variant.values()) if by_variant else 0

        # Approximate power calculation
        # Power ≈ 1 - Φ(z_α - d√(n/2)) for two-group comparison
        if n_per_group < 2:
            estimated_power = 0.0
        else:
            # Simplified power approximation
            z_alpha = 1.96 if alpha == 0.05 else 2.58
            ncp = effect_size * math.sqrt(n_per_group / 2)
            estimated_power = min(0.99, max(0.01, 1 - 1 / (1 + math.exp(ncp - z_alpha))))

        # Calculate required sample size for 80% power
        target_power = 0.80
        # n ≈ 2 * ((z_α + z_β) / d)^2
        z_beta = 0.84  # For 80% power
        z_alpha = 1.96
        required_n = int(2 * ((z_alpha + z_beta) / effect_size) ** 2) if effect_size > 0 else 1000

        return {
            'current_n_per_group': n_per_group,
            'estimated_power': estimated_power,
            'target_power': target_power,
            'required_n_per_group': required_n,
            'additional_n_needed': max(0, required_n - n_per_group),
            'assumed_effect_size': effect_size,
            'alpha': alpha
        }

    def clear(self) -> int:
        """
        Clear all test results.

        Returns:
            Number of results cleared
        """
        self._ensure_loaded()
        count = len(self.results)
        self.results = []
        self._assignments = {}
        self._save()
        return count


# ============================================================================
# Test Manager for Multiple Tests
# ============================================================================

class ABTestManager:
    """
    Manager for multiple A/B tests.

    Provides centralized access to all tests and aggregate reporting.
    """

    def __init__(self, storage_path: Optional[str] = None):
        """
        Initialize test manager.

        Args:
            storage_path: Path to JSON storage file
        """
        if storage_path is None:
            storage_path = DEFAULT_STORAGE_PATH

        self.storage_path = Path(storage_path)
        self._tests: Dict[str, ABTest] = {}

    def get_test(
        self,
        test_name: str,
        variants: Optional[List[str]] = None,
        primary_metric: str = "confidence"
    ) -> ABTest:
        """
        Get or create an A/B test.

        Args:
            test_name: Name of the test
            variants: Variants (required for new tests)
            primary_metric: Primary metric name

        Returns:
            ABTest instance
        """
        if test_name not in self._tests:
            if variants is None:
                variants = ["with_cer", "without_cer"]

            self._tests[test_name] = ABTest(
                test_name=test_name,
                variants=variants,
                storage_path=str(self.storage_path),
                primary_metric=primary_metric
            )

        return self._tests[test_name]

    def list_tests(self) -> List[str]:
        """
        List all test names.

        Returns:
            List of test names
        """
        if self.storage_path.exists():
            try:
                with open(self.storage_path, 'r') as f:
                    data = json.load(f)
                return list(data.get('tests', {}).keys())
            except (json.JSONDecodeError, KeyError):
                pass

        return []

    def get_all_results(self) -> Dict[str, ABTestSummary]:
        """
        Get results for all tests.

        Returns:
            Dictionary mapping test name to summary
        """
        results = {}
        for test_name in self.list_tests():
            test = self.get_test(test_name)
            results[test_name] = test.get_results()
        return results


# ============================================================================
# CLI Interface
# ============================================================================

def main():
    """CLI entry point for A/B testing."""
    parser = argparse.ArgumentParser(description='A/B Testing Framework for CER')

    parser.add_argument(
        '--storage', '-s',
        default=DEFAULT_STORAGE_PATH,
        help='Path to storage file'
    )
    parser.add_argument(
        '--json', '-j',
        action='store_true',
        help='Output as JSON'
    )

    subparsers = parser.add_subparsers(dest='command', help='Commands')

    # Results command
    results_parser = subparsers.add_parser('results', help='Get test results')
    results_parser.add_argument('--test', '-t', required=True, help='Test name')

    # Analyze command
    analyze_parser = subparsers.add_parser('analyze', help='Analyze specific metric')
    analyze_parser.add_argument('--test', '-t', required=True, help='Test name')
    analyze_parser.add_argument('--metric', '-m', required=True, help='Metric name')

    # Power command
    power_parser = subparsers.add_parser('power', help='Power analysis')
    power_parser.add_argument('--test', '-t', required=True, help='Test name')
    power_parser.add_argument('--effect-size', '-e', type=float, default=0.5, help='Expected effect size')

    # List command
    subparsers.add_parser('list', help='List all tests')

    # Assign command
    assign_parser = subparsers.add_parser('assign', help='Assign variant')
    assign_parser.add_argument('--test', '-t', required=True, help='Test name')
    assign_parser.add_argument('--query-id', '-q', required=True, help='Query ID')
    assign_parser.add_argument('--variants', '-v', nargs='+', default=['with_cer', 'without_cer'], help='Variants')

    # Record command
    record_parser = subparsers.add_parser('record', help='Record result')
    record_parser.add_argument('--test', '-t', required=True, help='Test name')
    record_parser.add_argument('--query-id', '-q', required=True, help='Query ID')
    record_parser.add_argument('--metrics', '-m', required=True, help='Metrics JSON')

    # Clear command
    clear_parser = subparsers.add_parser('clear', help='Clear test results')
    clear_parser.add_argument('--test', '-t', required=True, help='Test name')
    clear_parser.add_argument('--confirm', action='store_true', required=True, help='Confirm clear')

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    manager = ABTestManager(args.storage)

    def output(data: Any):
        """Output data in appropriate format."""
        if args.json:
            print(json.dumps(data, indent=2, default=str))
        else:
            if isinstance(data, dict):
                for k, v in data.items():
                    if isinstance(v, dict):
                        print(f"\n{k}:")
                        for k2, v2 in v.items():
                            print(f"  {k2}: {v2}")
                    else:
                        print(f"{k}: {v}")
            elif isinstance(data, list):
                for item in data:
                    print(item)
            else:
                print(data)

    if args.command == 'results':
        test = manager.get_test(args.test)
        summary = test.get_results()

        if args.json:
            output(summary.to_dict())
        else:
            print(f"\n{'='*60}")
            print(f"A/B Test Results: {summary.test_name}")
            print(f"{'='*60}")
            print(f"Total observations: {summary.total_observations}")
            print(f"By variant: {summary.observations_by_variant}")
            print(f"Overall significant: {summary.overall_significant}")

            if summary.primary_metric_improvement is not None:
                print(f"Primary metric improvement: {summary.primary_metric_improvement:.2f}")

            print(f"\n{'='*60}")
            print("Statistical Analyses:")
            print(f"{'='*60}")

            for analysis in summary.analyses:
                print(f"\nMetric: {analysis.metric}")
                print(f"  {analysis.variant_a}: mean={analysis.mean_a:.2f}, std={analysis.std_a:.2f}, n={analysis.n_a}")
                print(f"  {analysis.variant_b}: mean={analysis.mean_b:.2f}, std={analysis.std_b:.2f}, n={analysis.n_b}")
                print(f"  Difference: {analysis.mean_diff:.2f}")
                print(f"  t-statistic: {analysis.t_statistic:.3f}")
                print(f"  p-value: {analysis.p_value:.4f}")
                print(f"  Cohen's d: {analysis.cohens_d:.3f} ({analysis.effect_interpretation})")
                print(f"  Significant: {analysis.is_significant}")

    elif args.command == 'analyze':
        test = manager.get_test(args.test)
        summary = test.get_results()

        for analysis in summary.analyses:
            if analysis.metric == args.metric:
                output(analysis.to_dict())
                break
        else:
            print(f"Metric '{args.metric}' not found", file=sys.stderr)
            sys.exit(1)

    elif args.command == 'power':
        test = manager.get_test(args.test)
        power = test.get_power_analysis(effect_size=args.effect_size)
        output(power)

    elif args.command == 'list':
        tests = manager.list_tests()
        if tests:
            output(tests)
        else:
            print("No tests found")

    elif args.command == 'assign':
        test = manager.get_test(args.test, variants=args.variants)
        variant = test.assign_variant(args.query_id)
        output({'query_id': args.query_id, 'variant': variant})

    elif args.command == 'record':
        test = manager.get_test(args.test)

        try:
            metrics = json.loads(args.metrics)
        except json.JSONDecodeError:
            print("Invalid metrics JSON", file=sys.stderr)
            sys.exit(1)

        result = test.record_result(args.query_id, metrics)
        output({'query_id': args.query_id, 'variant': result.variant, 'status': 'recorded'})

    elif args.command == 'clear':
        test = manager.get_test(args.test)
        count = test.clear()
        output({'cleared': count, 'status': 'cleared'})


if __name__ == '__main__':
    main()
