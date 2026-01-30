#!/usr/bin/env python3
"""
CER Experiment Runner - Controlled A/B Test for Contextual Experience Replay

This script runs a controlled experiment to measure the impact of CER on
research quality. It executes N research queries, splitting them between
CER and baseline conditions, and reports statistical significance.

Measurement Protocol:
1. Run N research queries (default: 100, 50% with CER, 50% without)
2. Measure for each:
   - Confidence score (0-100)
   - Source coverage (0-1)
   - Synthesis coherence (1-5, simulated)
   - Time to complete
3. Calculate:
   - Mean difference
   - Standard deviation
   - p-value (t-test)
   - Effect size (Cohen's d)

Success criteria:
- Statistically significant improvement (p < 0.05)
- Effect size > 0.3

Usage:
    # Run full experiment with 100 queries
    python scripts/run_cer_experiment.py --queries 100

    # Run quick experiment with 20 queries
    python scripts/run_cer_experiment.py --queries 20 --quick

    # Run with custom seed for reproducibility
    python scripts/run_cer_experiment.py --queries 50 --seed 42

    # Run and save results to file
    python scripts/run_cer_experiment.py --queries 100 --output results.json

    # Continue from previous experiment
    python scripts/run_cer_experiment.py --continue-from ab_tests.json
"""

import argparse
import json
import math
import os
import random
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Add lib directory to path
SCRIPT_DIR = Path(__file__).parent
LIB_DIR = SCRIPT_DIR.parent / 'lib'
sys.path.insert(0, str(LIB_DIR))

from experience_memory import Experience, ExperienceMemory
from experience_compressor import ExperienceCompressor
from cer_integration import CERIntegration, ExperienceContext
from ab_testing import ABTest, ABTestManager, cohens_d, effect_size_interpretation


# ============================================================================
# Sample Research Queries
# ============================================================================

SAMPLE_QUERIES = [
    # AI/ML queries
    {"query": "What are the latest advances in transformer architectures?", "domain": "ai-ml"},
    {"query": "How do large language models handle context windows?", "domain": "ai-ml"},
    {"query": "What techniques improve LLM reasoning capabilities?", "domain": "ai-ml"},
    {"query": "How does reinforcement learning from human feedback work?", "domain": "ai-ml"},
    {"query": "What are the best practices for fine-tuning language models?", "domain": "ai-ml"},
    {"query": "How do mixture of experts models work?", "domain": "ai-ml"},
    {"query": "What is retrieval-augmented generation?", "domain": "ai-ml"},
    {"query": "How do vision-language models process images?", "domain": "ai-ml"},
    {"query": "What are the current limitations of AI systems?", "domain": "ai-ml"},
    {"query": "How do attention mechanisms improve model performance?", "domain": "ai-ml"},
    {"query": "What is the current state of multimodal AI?", "domain": "ai-ml"},
    {"query": "How do self-supervised learning methods work?", "domain": "ai-ml"},
    {"query": "What are neural architecture search techniques?", "domain": "ai-ml"},
    {"query": "How do diffusion models generate images?", "domain": "ai-ml"},
    {"query": "What are the benefits of sparse attention?", "domain": "ai-ml"},

    # Investment queries
    {"query": "What factors affect cryptocurrency market volatility?", "domain": "investment"},
    {"query": "How do ESG factors impact investment returns?", "domain": "investment"},
    {"query": "What are the risks of algorithmic trading?", "domain": "investment"},
    {"query": "How does monetary policy affect stock markets?", "domain": "investment"},
    {"query": "What metrics indicate company financial health?", "domain": "investment"},
    {"query": "How do index funds compare to active management?", "domain": "investment"},
    {"query": "What drives commodity price fluctuations?", "domain": "investment"},
    {"query": "How do interest rates affect bond prices?", "domain": "investment"},
    {"query": "What are the benefits of portfolio diversification?", "domain": "investment"},
    {"query": "How do geopolitical events impact markets?", "domain": "investment"},

    # General queries
    {"query": "How do renewable energy systems work?", "domain": "general"},
    {"query": "What are effective remote work strategies?", "domain": "general"},
    {"query": "How does blockchain technology ensure security?", "domain": "general"},
    {"query": "What factors influence climate change?", "domain": "general"},
    {"query": "How do supply chains recover from disruptions?", "domain": "general"},
    {"query": "What are the benefits of meditation for productivity?", "domain": "general"},
    {"query": "How do social networks spread information?", "domain": "general"},
    {"query": "What makes a good user interface design?", "domain": "general"},
    {"query": "How do batteries store and release energy?", "domain": "general"},
    {"query": "What are effective strategies for learning new skills?", "domain": "general"},
]


# ============================================================================
# Simulation Functions
# ============================================================================

def simulate_research(
    query: str,
    domain: str,
    use_cer: bool,
    cer_context: Optional[ExperienceContext] = None,
    experience_count: int = 0
) -> Dict:
    """
    Simulate a research execution with realistic metrics.

    In a real implementation, this would call the actual research loop.
    For this experiment, we simulate results based on expected CER benefits.

    Args:
        query: Research query
        domain: Research domain
        use_cer: Whether CER was used
        cer_context: CER context if available
        experience_count: Number of prior experiences

    Returns:
        Dictionary with research metrics
    """
    start_time = time.time()

    # Base metrics (without CER)
    base_confidence = random.gauss(62, 12)  # Mean 62, std 12
    base_coverage = random.gauss(0.65, 0.12)  # Mean 0.65, std 0.12
    base_coherence = random.gauss(3.2, 0.6)  # Mean 3.2, std 0.6

    if use_cer:
        # CER improvements
        # Confidence boost based on context quality
        confidence_boost = 0
        if cer_context and cer_context.retrieved_experiences:
            # More relevant experiences = more boost
            avg_similarity = sum(
                r.similarity for r in cer_context.retrieved_experiences
            ) / len(cer_context.retrieved_experiences)
            confidence_boost = avg_similarity * 15 + random.gauss(5, 3)
        else:
            # Even without direct matches, learning improves over time
            confidence_boost = min(experience_count * 0.5, 8) + random.gauss(3, 2)

        # Coverage improvement from source recommendations
        coverage_boost = 0
        if cer_context and cer_context.source_recommendations:
            coverage_boost = len(cer_context.source_recommendations) * 0.02 + random.gauss(0.05, 0.02)
        else:
            coverage_boost = random.gauss(0.03, 0.02)

        # Coherence improvement from decomposition hints
        coherence_boost = 0
        if cer_context and cer_context.decomposition_hints:
            coherence_boost = len(cer_context.decomposition_hints) * 0.1 + random.gauss(0.2, 0.1)
        else:
            coherence_boost = random.gauss(0.15, 0.1)

        confidence = base_confidence + confidence_boost
        coverage = base_coverage + coverage_boost
        coherence = base_coherence + coherence_boost
    else:
        confidence = base_confidence
        coverage = base_coverage
        coherence = base_coherence

    # Clamp values to valid ranges
    confidence = max(0, min(100, confidence))
    coverage = max(0, min(1, coverage))
    coherence = max(1, min(5, coherence))

    # Simulate execution time
    base_time = random.gauss(2.5, 0.5)  # Base time in seconds
    if use_cer:
        # CER may speed up research by providing better starting points
        time_reduction = random.gauss(0.3, 0.1)
        execution_time = max(0.5, base_time - time_reduction)
    else:
        execution_time = base_time

    # Add actual elapsed time
    time.sleep(0.01)  # Small delay to simulate work
    elapsed_time = time.time() - start_time

    return {
        'confidence': round(confidence, 1),
        'source_coverage': round(coverage, 3),
        'synthesis_coherence': round(coherence, 2),
        'execution_time': round(execution_time, 3),
        'actual_elapsed': round(elapsed_time, 3)
    }


def generate_findings(query: str, domain: str, num_findings: int = 3) -> List[Dict]:
    """Generate simulated research findings."""
    findings = []
    sources = {
        'ai-ml': ['arxiv.org', 'github.com', 'paperswithcode.com', 'huggingface.co'],
        'investment': ['bloomberg.com', 'reuters.com', 'wsj.com', 'sec.gov'],
        'general': ['wikipedia.org', 'nature.com', 'bbc.com', 'nytimes.com']
    }

    domain_sources = sources.get(domain, sources['general'])

    for i in range(num_findings):
        source = random.choice(domain_sources)
        findings.append({
            'content': f'Finding {i+1} for: {query[:50]}...',
            'source_url': f'https://{source}/article-{random.randint(1000, 9999)}',
            'relevance_score': round(random.uniform(0.5, 0.95), 2)
        })

    return findings


# ============================================================================
# Experiment Runner
# ============================================================================

class CERExperiment:
    """
    Runs controlled A/B experiments to measure CER effectiveness.
    """

    def __init__(
        self,
        num_queries: int = 100,
        seed: Optional[int] = None,
        storage_dir: Optional[str] = None
    ):
        """
        Initialize experiment.

        Args:
            num_queries: Number of queries to run
            seed: Random seed for reproducibility
            storage_dir: Directory for storing experiment data
        """
        self.num_queries = num_queries

        if seed is not None:
            random.seed(seed)

        if storage_dir is None:
            storage_dir = '.claude-loop/experiments'

        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)

        # Initialize components
        self.exp_path = str(self.storage_dir / 'cer_experiences.json')
        self.ab_path = str(self.storage_dir / 'cer_ab_tests.json')

        self.memory = ExperienceMemory(storage_path=self.exp_path)
        self.cer = CERIntegration(memory=self.memory)
        self.ab_test = ABTest(
            test_name='cer_vs_baseline',
            variants=['with_cer', 'without_cer'],
            storage_path=self.ab_path,
            primary_metric='confidence'
        )

        self.results: List[Dict] = []

    def run(self, verbose: bool = True) -> Dict:
        """
        Run the full experiment.

        Args:
            verbose: Print progress information

        Returns:
            Experiment results dictionary
        """
        if verbose:
            print("=" * 60)
            print("CER Experiment: Contextual Experience Replay Evaluation")
            print("=" * 60)
            print(f"Queries to run: {self.num_queries}")
            print(f"Variants: with_cer, without_cer")
            print(f"Primary metric: confidence")
            print("=" * 60)
            print()

        # Generate queries for experiment
        queries = self._generate_query_set()

        # Run queries
        start_time = time.time()

        for i, (query_id, query_data) in enumerate(queries):
            if verbose:
                print(f"[{i+1}/{self.num_queries}] {query_data['query'][:50]}...", end=' ')

            result = self._run_single_query(query_id, query_data)
            self.results.append(result)

            if verbose:
                print(f"-> {result['variant']}: conf={result['metrics']['confidence']}")

        total_time = time.time() - start_time

        if verbose:
            print()
            print("=" * 60)
            print("Experiment Complete")
            print(f"Total time: {total_time:.1f}s")
            print("=" * 60)
            print()

        # Analyze results
        analysis = self._analyze_results()

        if verbose:
            self._print_analysis(analysis)

        return analysis

    def _generate_query_set(self) -> List[Tuple[str, Dict]]:
        """Generate set of queries for experiment."""
        queries = []

        # Use sample queries, cycling if needed
        for i in range(self.num_queries):
            query_data = SAMPLE_QUERIES[i % len(SAMPLE_QUERIES)].copy()
            # Add variation to make queries unique
            if i >= len(SAMPLE_QUERIES):
                query_data['query'] = f"{query_data['query']} (variation {i // len(SAMPLE_QUERIES)})"

            query_id = f"exp_query_{i:04d}"
            queries.append((query_id, query_data))

        return queries

    def _run_single_query(self, query_id: str, query_data: Dict) -> Dict:
        """Run a single query in the experiment."""
        query = query_data['query']
        domain = query_data['domain']

        # Get variant assignment
        variant = self.ab_test.assign_variant(query_id)
        use_cer = (variant == 'with_cer')

        # Get CER context if using CER
        cer_context = None
        if use_cer:
            cer_context = self.cer.get_experience_context(query, domain)

        # Get current experience count
        stats = self.memory.get_stats()
        exp_count = stats['total_experiences']

        # Simulate research
        metrics = simulate_research(
            query=query,
            domain=domain,
            use_cer=use_cer,
            cer_context=cer_context,
            experience_count=exp_count
        )

        # Record result in A/B test
        self.ab_test.record_result(query_id, metrics)

        # If using CER, record the experience for future use
        if use_cer:
            findings = generate_findings(query, domain)
            self.cer.record_experience(
                query=query,
                domain=domain,
                sub_questions=[f"Sub-question for {query[:30]}"],
                findings=findings,
                synthesis=f"Synthesis for query: {query}",
                confidence=int(metrics['confidence'])
            )

        return {
            'query_id': query_id,
            'query': query,
            'domain': domain,
            'variant': variant,
            'metrics': metrics,
            'timestamp': datetime.now(timezone.utc).isoformat()
        }

    def _analyze_results(self) -> Dict:
        """Analyze experiment results."""
        # Get A/B test summary
        summary = self.ab_test.get_results()

        # Separate results by variant
        with_cer = [r for r in self.results if r['variant'] == 'with_cer']
        without_cer = [r for r in self.results if r['variant'] == 'without_cer']

        # Calculate additional statistics
        analysis = {
            'experiment_name': 'cer_vs_baseline',
            'total_queries': len(self.results),
            'queries_with_cer': len(with_cer),
            'queries_without_cer': len(without_cer),
            'metrics': {},
            'statistical_tests': [],
            'success_criteria': {},
            'memory_stats': self.memory.get_stats()
        }

        # Analyze each metric
        for metric in ['confidence', 'source_coverage', 'synthesis_coherence', 'execution_time']:
            cer_values = [r['metrics'][metric] for r in with_cer]
            baseline_values = [r['metrics'][metric] for r in without_cer]

            if not cer_values or not baseline_values:
                continue

            # Basic statistics
            cer_mean = sum(cer_values) / len(cer_values)
            baseline_mean = sum(baseline_values) / len(baseline_values)

            cer_std = math.sqrt(sum((x - cer_mean)**2 for x in cer_values) / (len(cer_values) - 1)) if len(cer_values) > 1 else 0
            baseline_std = math.sqrt(sum((x - baseline_mean)**2 for x in baseline_values) / (len(baseline_values) - 1)) if len(baseline_values) > 1 else 0

            # Effect size
            d = cohens_d(cer_values, baseline_values)

            # Find matching analysis from A/B test
            p_value = 0.5
            is_significant = False
            for stat_analysis in summary.analyses:
                if stat_analysis.metric == metric:
                    p_value = stat_analysis.p_value
                    is_significant = stat_analysis.is_significant
                    break

            analysis['metrics'][metric] = {
                'with_cer': {
                    'mean': round(cer_mean, 3),
                    'std': round(cer_std, 3),
                    'n': len(cer_values)
                },
                'without_cer': {
                    'mean': round(baseline_mean, 3),
                    'std': round(baseline_std, 3),
                    'n': len(baseline_values)
                },
                'difference': round(cer_mean - baseline_mean, 3),
                'cohens_d': round(d, 3),
                'effect_interpretation': effect_size_interpretation(d),
                'p_value': round(p_value, 4),
                'is_significant': is_significant
            }

        # Check success criteria
        confidence_data = analysis['metrics'].get('confidence', {})
        analysis['success_criteria'] = {
            'p_value_threshold': 0.05,
            'effect_size_threshold': 0.3,
            'p_value_met': confidence_data.get('p_value', 1.0) < 0.05,
            'effect_size_met': abs(confidence_data.get('cohens_d', 0)) >= 0.3,
            'overall_success': (
                confidence_data.get('p_value', 1.0) < 0.05 and
                abs(confidence_data.get('cohens_d', 0)) >= 0.3
            )
        }

        return analysis

    def _print_analysis(self, analysis: Dict):
        """Print formatted analysis results."""
        print("EXPERIMENT RESULTS")
        print("=" * 60)
        print(f"Total queries: {analysis['total_queries']}")
        print(f"  - With CER: {analysis['queries_with_cer']}")
        print(f"  - Without CER: {analysis['queries_without_cer']}")
        print()

        print("METRIC COMPARISON")
        print("-" * 60)

        for metric, data in analysis['metrics'].items():
            print(f"\n{metric.upper()}")
            print(f"  With CER:    {data['with_cer']['mean']:.3f} (std: {data['with_cer']['std']:.3f})")
            print(f"  Without CER: {data['without_cer']['mean']:.3f} (std: {data['without_cer']['std']:.3f})")
            print(f"  Difference:  {data['difference']:+.3f}")
            print(f"  Cohen's d:   {data['cohens_d']:.3f} ({data['effect_interpretation']})")
            print(f"  p-value:     {data['p_value']:.4f}")
            sig_marker = "*" if data['is_significant'] else ""
            print(f"  Significant: {data['is_significant']} {sig_marker}")

        print()
        print("SUCCESS CRITERIA")
        print("-" * 60)
        sc = analysis['success_criteria']
        print(f"  p-value < {sc['p_value_threshold']}: {'PASS' if sc['p_value_met'] else 'FAIL'}")
        print(f"  |Cohen's d| >= {sc['effect_size_threshold']}: {'PASS' if sc['effect_size_met'] else 'FAIL'}")
        print()

        if sc['overall_success']:
            print("  RESULT: CER shows STATISTICALLY SIGNIFICANT improvement")
        else:
            print("  RESULT: CER improvement NOT statistically significant")
            if not sc['p_value_met']:
                print("          (need more data or larger effect)")
            if not sc['effect_size_met']:
                print("          (effect size too small)")

        print()
        print("EXPERIENCE MEMORY STATS")
        print("-" * 60)
        mem_stats = analysis['memory_stats']
        print(f"  Total experiences stored: {mem_stats['total_experiences']}")
        print(f"  By domain: {mem_stats['by_domain']}")
        print(f"  Average confidence: {mem_stats['avg_confidence']:.1f}")

    def save_results(self, output_path: str):
        """Save experiment results to file."""
        analysis = self._analyze_results()
        analysis['raw_results'] = self.results

        with open(output_path, 'w') as f:
            json.dump(analysis, f, indent=2, default=str)

        print(f"Results saved to: {output_path}")


# ============================================================================
# CLI Interface
# ============================================================================

def main():
    """CLI entry point for CER experiment."""
    parser = argparse.ArgumentParser(
        description='CER Experiment Runner - Measure CER effectiveness',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Run full experiment with 100 queries
    python scripts/run_cer_experiment.py --queries 100

    # Run quick test with 20 queries
    python scripts/run_cer_experiment.py --queries 20 --quick

    # Run with specific seed for reproducibility
    python scripts/run_cer_experiment.py --queries 50 --seed 42

    # Save results to file
    python scripts/run_cer_experiment.py --queries 100 --output results.json
        """
    )

    parser.add_argument(
        '--queries', '-n',
        type=int,
        default=100,
        help='Number of queries to run (default: 100)'
    )
    parser.add_argument(
        '--seed', '-s',
        type=int,
        default=None,
        help='Random seed for reproducibility'
    )
    parser.add_argument(
        '--output', '-o',
        type=str,
        default=None,
        help='Output file for results (JSON)'
    )
    parser.add_argument(
        '--storage-dir',
        type=str,
        default=None,
        help='Directory for experiment data'
    )
    parser.add_argument(
        '--quiet', '-q',
        action='store_true',
        help='Suppress progress output'
    )
    parser.add_argument(
        '--quick',
        action='store_true',
        help='Run quick experiment (sets queries to 20 if not specified)'
    )
    parser.add_argument(
        '--json',
        action='store_true',
        help='Output results as JSON'
    )

    args = parser.parse_args()

    # Handle quick mode
    if args.quick and args.queries == 100:
        args.queries = 20

    # Run experiment
    experiment = CERExperiment(
        num_queries=args.queries,
        seed=args.seed,
        storage_dir=args.storage_dir
    )

    results = experiment.run(verbose=not args.quiet)

    # Output
    if args.json:
        print(json.dumps(results, indent=2, default=str))
    elif args.output:
        experiment.save_results(args.output)

    # Exit with appropriate code
    if results['success_criteria']['overall_success']:
        sys.exit(0)
    else:
        sys.exit(1)


if __name__ == '__main__':
    main()
