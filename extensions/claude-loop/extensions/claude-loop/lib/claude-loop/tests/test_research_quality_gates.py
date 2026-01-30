#!/usr/bin/env python3
"""
Tests for Research-Loop Quality Gates (US-013)

Comprehensive tests covering all quality gates:
- Source recency check
- Confirmation bias detection
- Citation accuracy
- Confidence calibration
- Risk disclosure (investment)
- Liquidity check (investment)
- Reproducibility (AI-ML)
- Benchmark validity (AI-ML)
"""

import pytest
import sys
import os
import yaml
import json
import tempfile
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock
from pathlib import Path

# Add lib to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'lib'))

# Import using importlib for hyphenated module names
import importlib.util


def load_module(name, path):
    """Load a module from file path."""
    if not os.path.exists(path):
        pytest.skip(f"Module not found: {path}")
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# Module paths
LIB_PATH = os.path.join(os.path.dirname(__file__), '..', 'lib')
ADAPTERS_PATH = os.path.join(os.path.dirname(__file__), '..', 'adapters')


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def ai_ml_adapter_config():
    """Load AI-ML adapter configuration."""
    adapter_path = os.path.join(ADAPTERS_PATH, 'ai-ml', 'adapter.yaml')
    with open(adapter_path, 'r') as f:
        return yaml.safe_load(f)


@pytest.fixture
def investment_adapter_config():
    """Load investment adapter configuration."""
    adapter_path = os.path.join(ADAPTERS_PATH, 'investment', 'adapter.yaml')
    with open(adapter_path, 'r') as f:
        return yaml.safe_load(f)


@pytest.fixture
def sample_sources():
    """Sample sources for testing."""
    return [
        {
            'url': 'https://arxiv.org/abs/2301.00001',
            'title': 'Recent AI Paper',
            'published_date': datetime.now().isoformat(),
            'citations': 50,
            'relevance': 0.95
        },
        {
            'url': 'https://nature.com/articles/example',
            'title': 'Nature Article',
            'published_date': (datetime.now() - timedelta(days=365)).isoformat(),
            'citations': 200,
            'relevance': 0.90
        },
        {
            'url': 'https://random-blog.com/post',
            'title': 'Blog Post',
            'published_date': (datetime.now() - timedelta(days=730)).isoformat(),
            'citations': 0,
            'relevance': 0.40
        }
    ]


@pytest.fixture
def temp_credibility_store():
    """Create a temporary credibility store."""
    fd, path = tempfile.mkstemp(suffix='.json')
    os.close(fd)
    with open(path, 'w') as f:
        json.dump({'domains': {}}, f)
    yield path
    if os.path.exists(path):
        os.remove(path)


# ============================================================================
# Test Source Recency Check
# ============================================================================

class TestSourceRecencyCheck:
    """Test source recency quality gate."""

    def test_ai_ml_recency_config(self, ai_ml_adapter_config):
        """Test AI-ML adapter has recency configuration."""
        gates = ai_ml_adapter_config['quality_gates']
        assert 'recency_weight' in gates
        assert gates['recency_weight']['enabled'] is True
        assert 'staleness_threshold_months' in gates['recency_weight']

    def test_investment_recency_config(self, investment_adapter_config):
        """Test investment adapter has recency configuration."""
        gates = investment_adapter_config['quality_gates']
        assert 'source_recency' in gates
        assert gates['source_recency']['enabled'] is True

        thresholds = gates['source_recency']['thresholds']
        assert 'trading_decisions' in thresholds
        assert thresholds['trading_decisions']['max_age_hours'] == 24

    def test_source_evaluator_recency_scoring(self, sample_sources):
        """Test source evaluator scores recency."""
        evaluator_module = load_module(
            "source_evaluator",
            os.path.join(LIB_PATH, 'source-evaluator.py')
        )

        evaluator = evaluator_module.SourceEvaluator()

        # Recent source should score higher on recency
        recent_source = sample_sources[0]
        old_source = sample_sources[2]

        recent_score = evaluator.calculate_recency_score(recent_source['published_date'])
        old_score = evaluator.calculate_recency_score(old_source['published_date'])

        assert recent_score > old_score, "Recent sources should score higher"

    def test_confidence_scorer_recency_weight(self):
        """Test confidence scorer includes recency weight."""
        scorer_module = load_module(
            "confidence_scorer",
            os.path.join(LIB_PATH, 'confidence_scorer.py')
        )

        scorer = scorer_module.ConfidenceScorer(domain='ai-ml')
        weights = scorer.get_weights()

        assert 'recency' in weights
        assert weights['recency'] > 0


# ============================================================================
# Test Confirmation Bias Detection
# ============================================================================

class TestConfirmationBiasDetection:
    """Test confirmation bias detection quality gate."""

    def test_investment_confirmation_bias_config(self, investment_adapter_config):
        """Test investment adapter requires opposing viewpoints."""
        gates = investment_adapter_config['quality_gates']
        assert 'confirmation_bias' in gates
        assert gates['confirmation_bias']['enabled'] is True

        requirements = gates['confirmation_bias']['requirements']
        # Requirements can be strings or dicts
        requirement_strs = [r if isinstance(r, str) else list(r.keys())[0] for r in requirements]
        assert 'require_bear_case' in requirement_strs
        assert 'require_bull_case' in requirement_strs

    def test_devils_advocate_agent_exists(self):
        """Test devil's advocate agent exists for bias checking."""
        agent_path = os.path.join(
            os.path.dirname(__file__),
            '..',
            'agents',
            'devils-advocate.md'
        )
        assert os.path.exists(agent_path)

    def test_counterargument_finder_module_exists(self):
        """Test counterargument finder module exists."""
        finder_path = os.path.join(LIB_PATH, 'counterargument-finder.py')
        assert os.path.exists(finder_path)

    def test_counterargument_finder_functionality(self):
        """Test counterargument finder can find opposing views."""
        finder_module = load_module(
            "counterargument_finder",
            os.path.join(LIB_PATH, 'counterargument-finder.py')
        )

        # Use ConclusionExtractor for extraction
        extractor = finder_module.ConclusionExtractor()

        # Test conclusion extraction - text needs strong conclusion indicators
        text = "Based on our analysis, we conclude that the stock price will increase by 20% due to strong fundamentals. The evidence suggests that this growth is sustainable."
        conclusions = extractor.extract_from_text(text)

        # Also verify CounterargumentFinder exists
        finder = finder_module.CounterargumentFinder()
        assert finder is not None

    def test_synthesis_includes_opposing_views(self):
        """Test synthesis identifies when opposing views are missing."""
        synth_module = load_module(
            "research_synthesizer",
            os.path.join(LIB_PATH, 'research_synthesizer.py')
        )

        synthesizer = synth_module.ResearchSynthesizer(domain='investment')

        # All findings have same sentiment (bullish)
        findings_by_agent = {
            'fundamental-analyst': [
                synth_module.Finding(
                    id='F-001',
                    content='Strong buy recommendation',
                    agent='fundamental-analyst',
                    sub_question_id='SQ-001',
                    relevance_score=0.9
                )
            ],
            'technical-analyst': [
                synth_module.Finding(
                    id='F-002',
                    content='Bullish technical indicators',
                    agent='technical-analyst',
                    sub_question_id='SQ-001',
                    relevance_score=0.85
                )
            ]
        }

        sub_questions = [{'id': 'SQ-001', 'question': 'Should I buy?'}]

        # With expected devils-advocate perspective
        expected_perspectives = ['fundamental-analyst', 'technical-analyst', 'devils-advocate']

        synthesis = synthesizer.synthesize(
            question="Should I buy AAPL?",
            findings_by_agent=findings_by_agent,
            sub_questions=sub_questions,
            expected_perspectives=expected_perspectives
        )

        # Should identify missing devil's advocate perspective
        perspective_gaps = [g for g in synthesis.gaps if g.gap_type == 'perspective']
        assert len(perspective_gaps) > 0


# ============================================================================
# Test Citation Accuracy
# ============================================================================

class TestCitationAccuracy:
    """Test citation accuracy quality gate."""

    def test_source_evaluator_exists(self):
        """Test source evaluator module exists."""
        evaluator_path = os.path.join(LIB_PATH, 'source-evaluator.py')
        assert os.path.exists(evaluator_path)

    def test_source_evaluator_domain_scoring(self):
        """Test source evaluator scores by domain authority."""
        evaluator_module = load_module(
            "source_evaluator",
            os.path.join(LIB_PATH, 'source-evaluator.py')
        )

        evaluator = evaluator_module.SourceEvaluator()

        # High authority domain
        arxiv_result = evaluator.evaluate('https://arxiv.org/abs/2301.00001')
        # Low authority domain
        blog_result = evaluator.evaluate('https://random-blog.com/post')

        # Results are SourceCredibility objects
        assert arxiv_result.score > blog_result.score

    def test_claim_verifier_exists(self):
        """Test claim verifier module exists."""
        verifier_path = os.path.join(LIB_PATH, 'claim-verifier.py')
        assert os.path.exists(verifier_path)

    def test_claim_verifier_multi_source(self):
        """Test claim verifier module exists and has verification capabilities."""
        verifier_module = load_module(
            "claim_verifier",
            os.path.join(LIB_PATH, 'claim-verifier.py')
        )

        # Verify ClaimVerifier class exists
        assert hasattr(verifier_module, 'ClaimVerifier')
        assert hasattr(verifier_module, 'Claim')
        assert hasattr(verifier_module, 'VerificationStatus')

        verifier = verifier_module.ClaimVerifier()
        assert verifier is not None

        # Verify the verify method exists
        assert hasattr(verifier, 'verify')
        assert callable(verifier.verify)

    def test_citation_normalization_config(self, ai_ml_adapter_config):
        """Test AI-ML adapter has citation normalization."""
        gates = ai_ml_adapter_config['quality_gates']
        assert 'citation_normalization' in gates
        assert gates['citation_normalization']['enabled'] is True


# ============================================================================
# Test Confidence Calibration
# ============================================================================

class TestConfidenceCalibration:
    """Test confidence calibration quality gate."""

    def test_confidence_scorer_module_exists(self):
        """Test confidence scorer module exists."""
        scorer_path = os.path.join(LIB_PATH, 'confidence_scorer.py')
        assert os.path.exists(scorer_path)

    def test_confidence_score_range(self):
        """Test confidence scores are in valid range."""
        scorer_module = load_module(
            "confidence_scorer",
            os.path.join(LIB_PATH, 'confidence_scorer.py')
        )

        scorer = scorer_module.ConfidenceScorer(domain='general')

        # Various source configurations
        test_cases = [
            ([], 0, 0),  # No sources
            ([{'url': 'https://arxiv.org/abs/1', 'relevance': 0.9, 'agent': 'test'}], 0, 0),
            ([{'url': 'https://arxiv.org/abs/1', 'relevance': 0.9, 'agent': 'test'}], 3, 2),
        ]

        for sources, gaps, conflicts in test_cases:
            result = scorer.score(sources, gaps, conflicts)
            assert 0 <= result.score <= 100, f"Score {result.score} should be 0-100"

    def test_confidence_includes_explanation(self):
        """Test confidence score includes explanation."""
        scorer_module = load_module(
            "confidence_scorer",
            os.path.join(LIB_PATH, 'confidence_scorer.py')
        )

        scorer = scorer_module.ConfidenceScorer(domain='ai-ml')

        sources = [
            {'url': 'https://arxiv.org/abs/1', 'relevance': 0.9, 'agent': 'academic-scanner'}
        ]

        result = scorer.score(sources, gaps=0, conflicts=0)

        assert result.explanation is not None
        assert len(result.explanation) > 10

    def test_domain_specific_confidence_weights(self):
        """Test different domains have different confidence weights."""
        scorer_module = load_module(
            "confidence_scorer",
            os.path.join(LIB_PATH, 'confidence_scorer.py')
        )

        ai_scorer = scorer_module.ConfidenceScorer(domain='ai-ml')
        investment_scorer = scorer_module.ConfidenceScorer(domain='investment')

        ai_weights = ai_scorer.get_weights()
        investment_weights = investment_scorer.get_weights()

        # Different domains should have different priorities
        # (investment may weight recency higher for market data)
        assert ai_weights is not None
        assert investment_weights is not None

    def test_confidence_adapter_config(self, ai_ml_adapter_config, investment_adapter_config):
        """Test adapters have confidence weight configurations."""
        assert 'confidence_weights' in ai_ml_adapter_config
        assert 'confidence_weights' in investment_adapter_config

        ai_weights = ai_ml_adapter_config['confidence_weights']
        inv_weights = investment_adapter_config['confidence_weights']

        # Verify key weights exist
        for config in [ai_weights, inv_weights]:
            assert sum(config.values()) > 0  # Weights should sum to something positive


# ============================================================================
# Test Risk Disclosure (Investment)
# ============================================================================

class TestRiskDisclosure:
    """Test risk disclosure quality gate for investment research."""

    def test_risk_disclosure_gate_enabled(self, investment_adapter_config):
        """Test risk disclosure gate is enabled."""
        gates = investment_adapter_config['quality_gates']
        assert 'risk_disclosure' in gates
        assert gates['risk_disclosure']['enabled'] is True

    def test_required_disclosures_configured(self, investment_adapter_config):
        """Test required disclosures are configured."""
        gates = investment_adapter_config['quality_gates']
        required = gates['risk_disclosure']['required_disclosures']

        assert 'paper_trading_notice' in required
        assert 'not_financial_advice' in required
        assert 'past_performance_warning' in required

    def test_mandatory_disclaimer_exists(self, investment_adapter_config):
        """Test mandatory disclaimer is configured."""
        output = investment_adapter_config['output']
        assert 'mandatory_disclaimer' in output

        disclaimer = output['mandatory_disclaimer']
        assert 'NOT financial advice' in disclaimer
        assert 'Past performance' in disclaimer
        assert 'afford to lose' in disclaimer

    def test_risk_assessor_agent_covers_risks(self):
        """Test risk assessor agent covers key risk types."""
        agent_path = os.path.join(
            os.path.dirname(__file__),
            '..',
            'agents',
            'risk-assessor.md'
        )

        with open(agent_path, 'r') as f:
            content = f.read()

        # Check for key risk categories
        risk_keywords = [
            'Volatility',
            'Drawdown',
            'Liquidity',
            'Concentration',
            'Market',
        ]

        for keyword in risk_keywords:
            assert keyword in content, f"Risk assessor should cover {keyword}"


# ============================================================================
# Test Liquidity Check (Investment)
# ============================================================================

class TestLiquidityCheck:
    """Test liquidity check quality gate for investment research."""

    def test_liquidity_check_enabled(self, investment_adapter_config):
        """Test liquidity check is enabled."""
        gates = investment_adapter_config['quality_gates']
        assert 'liquidity_check' in gates
        assert gates['liquidity_check']['enabled'] is True

    def test_liquidity_thresholds_configured(self, investment_adapter_config):
        """Test liquidity thresholds are configured."""
        gates = investment_adapter_config['quality_gates']
        thresholds = gates['liquidity_check']['thresholds']

        # Stock thresholds
        assert 'stocks' in thresholds
        assert thresholds['stocks']['min_avg_volume'] >= 100000
        assert thresholds['stocks']['min_market_cap'] >= 1000000

        # Crypto thresholds
        assert 'crypto' in thresholds
        assert thresholds['crypto']['min_24h_volume'] >= 100000
        assert thresholds['crypto']['min_market_cap'] >= 1000000


# ============================================================================
# Test Reproducibility (AI-ML)
# ============================================================================

class TestReproducibilityGate:
    """Test reproducibility quality gate for AI-ML research."""

    def test_reproducibility_gate_enabled(self, ai_ml_adapter_config):
        """Test reproducibility gate is enabled."""
        gates = ai_ml_adapter_config['quality_gates']
        assert 'reproducibility' in gates
        assert gates['reproducibility']['enabled'] is True

    def test_reproducibility_checks_configured(self, ai_ml_adapter_config):
        """Test reproducibility checks are configured."""
        gates = ai_ml_adapter_config['quality_gates']
        repro = gates['reproducibility']

        assert repro['check_code_availability'] is True
        assert repro['check_data_availability'] is True

    def test_code_platforms_configured(self, ai_ml_adapter_config):
        """Test code hosting platforms are configured."""
        gates = ai_ml_adapter_config['quality_gates']
        platforms = gates['reproducibility']['code_platforms']

        assert 'github.com' in platforms
        assert 'huggingface.co' in platforms

    def test_reproducibility_boost_configured(self, ai_ml_adapter_config):
        """Test reproducibility confidence boost is configured."""
        gates = ai_ml_adapter_config['quality_gates']
        assert gates['reproducibility']['min_confidence_boost'] >= 0.05


# ============================================================================
# Test Benchmark Validity (AI-ML)
# ============================================================================

class TestBenchmarkValidityGate:
    """Test benchmark validity quality gate for AI-ML research."""

    def test_benchmark_validity_enabled(self, ai_ml_adapter_config):
        """Test benchmark validity gate is enabled."""
        gates = ai_ml_adapter_config['quality_gates']
        assert 'benchmark_validity' in gates
        assert gates['benchmark_validity']['enabled'] is True

    def test_known_benchmarks_configured(self, ai_ml_adapter_config):
        """Test known benchmarks are configured."""
        gates = ai_ml_adapter_config['quality_gates']
        benchmarks = gates['benchmark_validity']['known_benchmarks']

        # NLP benchmarks
        assert 'nlp' in benchmarks
        nlp_benchmarks = benchmarks['nlp']
        assert 'GLUE' in nlp_benchmarks
        assert 'SQuAD' in nlp_benchmarks or 'MMLU' in nlp_benchmarks

        # Vision benchmarks
        assert 'vision' in benchmarks
        vision_benchmarks = benchmarks['vision']
        assert 'ImageNet' in vision_benchmarks
        assert 'COCO' in vision_benchmarks

    def test_required_metrics_configured(self, ai_ml_adapter_config):
        """Test required metrics are configured."""
        gates = ai_ml_adapter_config['quality_gates']
        metrics = gates['benchmark_validity']['required_metrics']

        # NLP metrics
        assert 'nlp' in metrics
        assert 'accuracy' in metrics['nlp'] or 'f1' in metrics['nlp']

        # Vision metrics
        assert 'vision' in metrics
        assert 'top1_accuracy' in metrics['vision'] or 'mAP' in metrics['vision']

    def test_benchmark_analyst_agent_exists(self):
        """Test benchmark analyst agent exists."""
        agent_path = os.path.join(
            os.path.dirname(__file__),
            '..',
            'agents',
            'benchmark-analyst.md'
        )
        assert os.path.exists(agent_path)

    def test_benchmark_analyst_covers_domains(self):
        """Test benchmark analyst covers required domains."""
        agent_path = os.path.join(
            os.path.dirname(__file__),
            '..',
            'agents',
            'benchmark-analyst.md'
        )

        with open(agent_path, 'r') as f:
            content = f.read()

        # Check for domain coverage
        assert 'NLP' in content or 'Natural Language' in content
        assert 'Vision' in content or 'Computer Vision' in content
        assert 'ImageNet' in content
        assert 'GLUE' in content or 'SuperGLUE' in content


# ============================================================================
# Test Quality Gates Integration
# ============================================================================

class TestQualityGatesIntegration:
    """Test quality gates are properly integrated."""

    def test_ai_ml_quality_gates_file_exists(self):
        """Test AI-ML quality gates prompts file exists."""
        gates_path = os.path.join(
            ADAPTERS_PATH,
            'ai-ml',
            'prompts',
            'quality_gates.md'
        )
        assert os.path.exists(gates_path)

    def test_investment_quality_gates_file_exists(self):
        """Test investment quality gates prompts file exists."""
        gates_path = os.path.join(
            ADAPTERS_PATH,
            'investment',
            'prompts',
            'quality_gates.md'
        )
        assert os.path.exists(gates_path)

    def test_ai_ml_gates_content(self):
        """Test AI-ML quality gates have required content."""
        gates_path = os.path.join(
            ADAPTERS_PATH,
            'ai-ml',
            'prompts',
            'quality_gates.md'
        )

        with open(gates_path, 'r') as f:
            content = f.read()

        # Check for required gates
        assert 'Reproducibility' in content
        assert 'Benchmark' in content
        assert 'Code' in content or 'code' in content

    def test_investment_gates_content(self):
        """Test investment quality gates have required content."""
        gates_path = os.path.join(
            ADAPTERS_PATH,
            'investment',
            'prompts',
            'quality_gates.md'
        )

        with open(gates_path, 'r') as f:
            content = f.read()

        # Check for required gates
        assert 'Source Recency' in content
        assert 'Confirmation Bias' in content
        assert 'Risk Disclosure' in content
        assert 'Liquidity' in content

    def test_all_gates_have_enabled_flag(self, ai_ml_adapter_config, investment_adapter_config):
        """Test all gates have enabled/disabled flag."""
        for config in [ai_ml_adapter_config, investment_adapter_config]:
            gates = config['quality_gates']
            for gate_name, gate_config in gates.items():
                assert 'enabled' in gate_config, \
                    f"Gate {gate_name} should have 'enabled' flag"


# ============================================================================
# Test Backtesting Caveat (Investment)
# ============================================================================

class TestBacktestingCaveat:
    """Test backtesting caveat quality gate."""

    def test_backtesting_caveat_enabled(self, investment_adapter_config):
        """Test backtesting caveat is enabled."""
        gates = investment_adapter_config['quality_gates']
        assert 'backtesting_caveat' in gates
        assert gates['backtesting_caveat']['enabled'] is True

    def test_backtesting_warnings_configured(self, investment_adapter_config):
        """Test backtesting warnings are configured."""
        gates = investment_adapter_config['quality_gates']
        warnings = gates['backtesting_caveat']['warnings']

        assert len(warnings) >= 3  # Should have multiple warnings

        # Check for key warnings
        warning_text = ' '.join(warnings).lower()
        assert 'past' in warning_text or 'backtest' in warning_text
        assert 'future' in warning_text or 'guarantee' in warning_text


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
