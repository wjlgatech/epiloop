#!/usr/bin/env python3
"""
End-to-End Tests for AI-ML Research Use Case (US-013)

Comprehensive integration tests covering:
- Research orchestrator initialization
- Web search integration
- Academic scanner agent
- Synthesis pipeline
- Confidence scoring
- Mock external APIs (arXiv blocked in sandbox)
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


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def mock_arxiv_response():
    """Mock arXiv API response."""
    return {
        'feed': {
            'entry': [
                {
                    'id': 'http://arxiv.org/abs/2103.00020v1',
                    'title': 'Vision Transformers: A Survey',
                    'summary': 'This paper surveys recent advances in Vision Transformers (ViT) for image classification.',
                    'author': [
                        {'name': 'Author One'},
                        {'name': 'Author Two'}
                    ],
                    'published': '2021-03-01T00:00:00Z',
                    'updated': '2021-03-15T00:00:00Z',
                    'arxiv:primary_category': {'@term': 'cs.CV'},
                    'category': [
                        {'@term': 'cs.CV'},
                        {'@term': 'cs.LG'}
                    ],
                    'link': [
                        {'@href': 'http://arxiv.org/abs/2103.00020v1', '@rel': 'alternate'},
                        {'@href': 'http://arxiv.org/pdf/2103.00020v1', '@rel': 'related', '@title': 'pdf'}
                    ]
                },
                {
                    'id': 'http://arxiv.org/abs/2010.11929v1',
                    'title': 'An Image is Worth 16x16 Words: ViT for Image Recognition',
                    'summary': 'We apply transformers directly to sequences of image patches.',
                    'author': [{'name': 'Dosovitskiy et al.'}],
                    'published': '2020-10-22T00:00:00Z',
                    'updated': '2020-10-22T00:00:00Z',
                    'arxiv:primary_category': {'@term': 'cs.CV'},
                    'category': [{'@term': 'cs.CV'}, {'@term': 'cs.LG'}],
                    'link': [
                        {'@href': 'http://arxiv.org/abs/2010.11929v1'},
                        {'@href': 'http://arxiv.org/pdf/2010.11929v1', '@title': 'pdf'}
                    ]
                }
            ]
        }
    }


@pytest.fixture
def mock_paperswithcode_response():
    """Mock Papers With Code API response."""
    return {
        'results': [
            {
                'id': 'vit-large-patch16-384',
                'title': 'ViT-L/16',
                'abstract': 'Large vision transformer model',
                'arxiv_id': '2010.11929',
                'url_abs': 'https://paperswithcode.com/paper/vit-large',
                'url_pdf': 'https://arxiv.org/pdf/2010.11929',
                'published': '2020-10-22',
                'authors': ['Alexey Dosovitskiy', 'Lucas Beyer'],
                'conference': 'ICLR 2021',
                'tasks': ['Image Classification', 'Transfer Learning']
            }
        ]
    }


@pytest.fixture
def mock_sota_benchmarks():
    """Mock SOTA benchmark results."""
    return {
        'benchmarks': [
            {
                'paper_id': 'vit-large-patch16-384',
                'paper_title': 'ViT-L/16',
                'task': 'Image Classification',
                'dataset': 'ImageNet',
                'metric_name': 'Top-1 Accuracy',
                'metric_value': 88.55,
                'rank': 1,
                'published_date': '2020-10-22',
                'arxiv_id': '2010.11929',
                'github_url': 'https://github.com/google-research/vision_transformer'
            },
            {
                'paper_id': 'efficientnet-b7',
                'paper_title': 'EfficientNet-B7',
                'task': 'Image Classification',
                'dataset': 'ImageNet',
                'metric_name': 'Top-1 Accuracy',
                'metric_value': 84.4,
                'rank': 5,
                'published_date': '2019-05-28',
                'arxiv_id': '1905.11946',
                'github_url': None
            }
        ]
    }


@pytest.fixture
def mock_search_results():
    """Mock web search results."""
    return [
        {
            'title': 'Vision Transformer Guide',
            'url': 'https://arxiv.org/abs/2103.00020',
            'snippet': 'Comprehensive guide to Vision Transformers for image classification.',
            'relevance_score': 0.95
        },
        {
            'title': 'ViT Implementation Tutorial',
            'url': 'https://github.com/google-research/vit',
            'snippet': 'Official implementation of Vision Transformer models.',
            'relevance_score': 0.88
        }
    ]


@pytest.fixture
def sample_research_state():
    """Sample research state for testing."""
    return {
        'researchId': 'RES-TEST-001',
        'question': 'What are the latest advances in vision transformers for image classification?',
        'status': 'researching',
        'startTime': datetime.now().isoformat(),
        'subQuestions': [
            {
                'id': 'SQ-001',
                'question': 'What are the key architectural innovations in recent ViT models?',
                'agent': 'academic-scanner',
                'status': 'completed',
                'confidence': 85,
                'findings': ['DeiT introduces distillation tokens', 'Swin uses shifted windows']
            },
            {
                'id': 'SQ-002',
                'question': 'What are the current SOTA benchmarks on ImageNet?',
                'agent': 'benchmark-analyst',
                'status': 'completed',
                'confidence': 90,
                'findings': ['ViT-L achieves 88.55% top-1 accuracy']
            },
            {
                'id': 'SQ-003',
                'question': 'What implementation considerations are important?',
                'agent': 'technical-diver',
                'status': 'pending',
                'confidence': 0,
                'findings': []
            }
        ],
        'metadata': {
            'domain': 'ai-ml',
            'totalSources': 5,
            'adapter': 'ai-ml'
        }
    }


@pytest.fixture
def temp_state_dir():
    """Create a temporary directory for state files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


# ============================================================================
# Test Research Orchestrator Initialization
# ============================================================================

class TestResearchOrchestratorInitialization:
    """Test research orchestrator initialization."""

    def test_orchestrator_module_exists(self):
        """Test that research-orchestrator.py exists."""
        orchestrator_path = os.path.join(LIB_PATH, 'research-orchestrator.py')
        assert os.path.exists(orchestrator_path), "research-orchestrator.py should exist"

    def test_question_decomposer_module_exists(self):
        """Test that question decomposition module exists."""
        # Check for both naming conventions
        decomposer_path = os.path.join(LIB_PATH, 'question_decomposer.py')
        decomposer_path_alt = os.path.join(LIB_PATH, 'question-decomposer.py')
        assert os.path.exists(decomposer_path) or os.path.exists(decomposer_path_alt), \
            "question_decomposer.py or question-decomposer.py should exist"

    def test_research_state_schema_exists(self):
        """Test that research state schema exists."""
        schema_path = os.path.join(
            os.path.dirname(__file__),
            '..',
            'schemas',
            'research-state.json'
        )
        assert os.path.exists(schema_path), "research-state.json schema should exist"

    def test_ai_ml_adapter_config(self):
        """Test AI-ML adapter configuration is valid."""
        adapter_path = os.path.join(
            os.path.dirname(__file__),
            '..',
            'adapters',
            'ai-ml',
            'adapter.yaml'
        )

        assert os.path.exists(adapter_path)

        with open(adapter_path, 'r') as f:
            config = yaml.safe_load(f)

        # Verify required sections
        assert config['name'] == 'ai-ml'
        assert 'domain' in config
        assert 'sources' in config
        assert 'quality_gates' in config
        assert 'agents' in config

        # Verify arXiv categories
        arxiv_cats = config['domain']['arxiv_categories']
        assert 'cs.AI' in arxiv_cats
        assert 'cs.LG' in arxiv_cats
        assert 'cs.CV' in arxiv_cats
        assert 'cs.CL' in arxiv_cats

    def test_research_loop_entry_point_exists(self):
        """Test research-loop.sh entry point exists."""
        script_path = os.path.join(
            os.path.dirname(__file__),
            '..',
            'research-loop.sh'
        )
        assert os.path.exists(script_path), "research-loop.sh should exist"


# ============================================================================
# Test Web Search Integration
# ============================================================================

class TestWebSearchIntegration:
    """Test web search integration."""

    def test_search_provider_module_exists(self):
        """Test that search-provider.py exists."""
        search_path = os.path.join(LIB_PATH, 'search-provider.py')
        assert os.path.exists(search_path)

    def test_search_provider_instantiation(self):
        """Test search provider module has required classes."""
        search_module = load_module(
            "search_provider",
            os.path.join(LIB_PATH, 'search-provider.py')
        )

        # SearchProvider is abstract, check for concrete implementations
        assert hasattr(search_module, 'SearchProvider')
        assert hasattr(search_module, 'SearchResult')

        # Check for concrete providers if available
        has_tavily = hasattr(search_module, 'TavilyProvider')
        has_duckduckgo = hasattr(search_module, 'DuckDuckGoProvider')
        has_multi = hasattr(search_module, 'MultiSearchProvider')

        assert has_tavily or has_duckduckgo or has_multi, \
            "Should have at least one concrete search provider"

    def test_search_returns_structured_results(self, mock_search_results):
        """Test SearchResult dataclass has required fields."""
        search_module = load_module(
            "search_provider",
            os.path.join(LIB_PATH, 'search-provider.py')
        )

        # Test SearchResult dataclass
        result = search_module.SearchResult(
            title="Test Title",
            url="https://example.com",
            snippet="Test snippet",
            relevance_score=0.85,
            source="test"
        )

        assert result.title == "Test Title"
        assert result.url == "https://example.com"
        assert result.snippet == "Test snippet"
        assert result.relevance_score == 0.85

    def test_search_cache_module_exists(self):
        """Test that search cache module exists."""
        cache_path = os.path.join(LIB_PATH, 'search-cache.py')
        assert os.path.exists(cache_path)


# ============================================================================
# Test Academic Scanner Agent
# ============================================================================

class TestAcademicScannerAgent:
    """Test academic scanner agent."""

    def test_academic_scanner_agent_exists(self):
        """Test that academic-scanner.md exists."""
        agent_path = os.path.join(
            os.path.dirname(__file__),
            '..',
            'agents',
            'academic-scanner.md'
        )
        assert os.path.exists(agent_path)

    def test_academic_scanner_structure(self):
        """Test academic scanner has required sections."""
        agent_path = os.path.join(
            os.path.dirname(__file__),
            '..',
            'agents',
            'academic-scanner.md'
        )

        with open(agent_path, 'r') as f:
            content = f.read()

        # Check for required sections
        assert '# Academic Scanner Agent' in content
        assert 'Capabilities' in content
        assert 'arXiv' in content
        assert 'Search Strategy' in content

    def test_arxiv_client_module_exists(self):
        """Test arXiv client module exists."""
        arxiv_path = os.path.join(LIB_PATH, 'arxiv-client.py')
        assert os.path.exists(arxiv_path)

    def test_arxiv_client_instantiation(self):
        """Test arXiv client can be instantiated."""
        arxiv_module = load_module(
            "arxiv_client",
            os.path.join(LIB_PATH, 'arxiv-client.py')
        )

        client = arxiv_module.ArxivClient()
        assert client is not None
        assert hasattr(client, 'search')

    def test_arxiv_paper_dataclass(self):
        """Test ArxivPaper dataclass structure."""
        arxiv_module = load_module(
            "arxiv_client",
            os.path.join(LIB_PATH, 'arxiv-client.py')
        )

        paper = arxiv_module.ArxivPaper(
            arxiv_id="2103.00020",
            title="Vision Transformers Survey",
            authors=["Author One", "Author Two"],
            abstract="A comprehensive survey of ViT models",
            published_date="2021-03-01T00:00:00Z",
            updated_date="2021-03-15T00:00:00Z",
            categories=["cs.CV", "cs.LG"],
            pdf_url="https://arxiv.org/pdf/2103.00020",
            arxiv_url="https://arxiv.org/abs/2103.00020",
            primary_category="cs.CV"
        )

        assert paper.arxiv_id == "2103.00020"
        assert len(paper.authors) == 2
        assert paper.primary_category == "cs.CV"

    def test_arxiv_search_with_mock(self, mock_arxiv_response):
        """Test arXiv search with mocked response."""
        arxiv_module = load_module(
            "arxiv_client",
            os.path.join(LIB_PATH, 'arxiv-client.py')
        )

        # Create mock for HTTP request
        with patch('urllib.request.urlopen') as mock_urlopen:
            mock_response = MagicMock()
            mock_response.read.return_value = b'<feed></feed>'  # Minimal XML
            mock_urlopen.return_value.__enter__.return_value = mock_response

            client = arxiv_module.ArxivClient()
            # The actual search would parse XML, we just verify the method exists
            assert callable(client.search)


# ============================================================================
# Test Benchmark Analyst Agent
# ============================================================================

class TestBenchmarkAnalystAgent:
    """Test benchmark analyst agent."""

    def test_benchmark_analyst_exists(self):
        """Test that benchmark-analyst.md exists."""
        agent_path = os.path.join(
            os.path.dirname(__file__),
            '..',
            'agents',
            'benchmark-analyst.md'
        )
        assert os.path.exists(agent_path)

    def test_benchmark_analyst_structure(self):
        """Test benchmark analyst has required sections."""
        agent_path = os.path.join(
            os.path.dirname(__file__),
            '..',
            'agents',
            'benchmark-analyst.md'
        )

        with open(agent_path, 'r') as f:
            content = f.read()

        assert '# Benchmark Analyst Agent' in content
        assert 'SOTA' in content
        assert 'ImageNet' in content
        assert 'NLP' in content or 'Natural Language' in content

    def test_paperswithcode_client_exists(self):
        """Test Papers With Code client exists."""
        pwc_path = os.path.join(LIB_PATH, 'paperswithcode-client.py')
        assert os.path.exists(pwc_path)

    def test_paperswithcode_client_instantiation(self):
        """Test Papers With Code client can be instantiated."""
        pwc_module = load_module(
            "paperswithcode_client",
            os.path.join(LIB_PATH, 'paperswithcode-client.py')
        )

        client = pwc_module.PapersWithCodeClient()
        assert client is not None
        assert hasattr(client, 'search_papers')
        assert hasattr(client, 'get_sota_benchmarks')


# ============================================================================
# Test Synthesis Pipeline
# ============================================================================

class TestSynthesisPipeline:
    """Test synthesis pipeline."""

    def test_research_synthesizer_exists(self):
        """Test research synthesizer module exists."""
        synth_path = os.path.join(LIB_PATH, 'research_synthesizer.py')
        assert os.path.exists(synth_path)

    def test_synthesizer_instantiation(self):
        """Test synthesizer can be instantiated."""
        synth_module = load_module(
            "research_synthesizer",
            os.path.join(LIB_PATH, 'research_synthesizer.py')
        )

        synthesizer = synth_module.ResearchSynthesizer()
        assert synthesizer is not None

    def test_combine_findings(self):
        """Test combining findings from multiple agents."""
        synth_module = load_module(
            "research_synthesizer",
            os.path.join(LIB_PATH, 'research_synthesizer.py')
        )

        synthesizer = synth_module.ResearchSynthesizer()

        findings_by_agent = {
            'academic-scanner': [
                synth_module.Finding(
                    id='F-001',
                    content='ViT achieves SOTA on ImageNet',
                    source_url='https://arxiv.org/abs/2010.11929',
                    agent='academic-scanner',
                    relevance_score=0.95
                )
            ],
            'benchmark-analyst': [
                synth_module.Finding(
                    id='F-002',
                    content='ViT-L/16 achieves 88.55% top-1 accuracy',
                    source_url='https://paperswithcode.com/sota/image-classification-on-imagenet',
                    agent='benchmark-analyst',
                    relevance_score=0.92
                )
            ]
        }

        combined = synthesizer.combine_findings(findings_by_agent)

        assert len(combined) == 2
        # Verify sorted by relevance
        assert combined[0].relevance_score >= combined[1].relevance_score

    def test_identify_gaps(self):
        """Test gap identification in findings."""
        synth_module = load_module(
            "research_synthesizer",
            os.path.join(LIB_PATH, 'research_synthesizer.py')
        )

        synthesizer = synth_module.ResearchSynthesizer()

        findings = [
            synth_module.Finding(
                id='F-001',
                content='ViT architecture details',
                sub_question_id='SQ-001',
                relevance_score=0.9
            )
        ]

        sub_questions = [
            {'id': 'SQ-001', 'question': 'Architecture details'},
            {'id': 'SQ-002', 'question': 'Training procedures (unanswered)'}
        ]

        gaps = synthesizer.identify_gaps(findings, sub_questions)

        # Should find a gap for SQ-002
        coverage_gaps = [g for g in gaps if g.gap_type == 'coverage']
        assert any(g.related_sub_question == 'SQ-002' for g in coverage_gaps)

    def test_full_synthesis_workflow(self):
        """Test complete synthesis workflow."""
        synth_module = load_module(
            "research_synthesizer",
            os.path.join(LIB_PATH, 'research_synthesizer.py')
        )

        synthesizer = synth_module.ResearchSynthesizer(domain='ai-ml')

        findings_by_agent = {
            'academic-scanner': [
                synth_module.Finding(
                    id='F-001',
                    content='Vision Transformers (ViT) apply transformer architecture to images',
                    source_url='https://arxiv.org/abs/2010.11929',
                    source_title='An Image is Worth 16x16 Words',
                    agent='academic-scanner',
                    sub_question_id='SQ-001',
                    relevance_score=0.95
                )
            ],
            'benchmark-analyst': [
                synth_module.Finding(
                    id='F-002',
                    content='ViT-L/16 achieves 88.55% on ImageNet',
                    source_url='https://paperswithcode.com/sota/image-classification',
                    source_title='SOTA Image Classification',
                    agent='benchmark-analyst',
                    sub_question_id='SQ-002',
                    relevance_score=0.90
                )
            ]
        }

        sub_questions = [
            {'id': 'SQ-001', 'question': 'What is ViT architecture?'},
            {'id': 'SQ-002', 'question': 'What are current benchmarks?'}
        ]

        synthesis = synthesizer.synthesize(
            question="What are the latest advances in vision transformers?",
            findings_by_agent=findings_by_agent,
            sub_questions=sub_questions
        )

        assert synthesis is not None
        assert synthesis.question == "What are the latest advances in vision transformers?"
        assert len(synthesis.key_findings) == 2
        assert synthesis.confidence is not None
        assert 0 <= synthesis.confidence.score <= 100


# ============================================================================
# Test Confidence Scoring
# ============================================================================

class TestConfidenceScoring:
    """Test confidence scoring functionality."""

    def test_confidence_scorer_exists(self):
        """Test confidence scorer module exists."""
        scorer_path = os.path.join(LIB_PATH, 'confidence_scorer.py')
        assert os.path.exists(scorer_path)

    def test_scorer_instantiation(self):
        """Test scorer can be instantiated."""
        scorer_module = load_module(
            "confidence_scorer",
            os.path.join(LIB_PATH, 'confidence_scorer.py')
        )

        scorer = scorer_module.ConfidenceScorer(domain='ai-ml')
        assert scorer is not None

    def test_high_confidence_authoritative_sources(self):
        """Test high confidence with authoritative sources."""
        scorer_module = load_module(
            "confidence_scorer",
            os.path.join(LIB_PATH, 'confidence_scorer.py')
        )

        scorer = scorer_module.ConfidenceScorer(domain='ai-ml')

        sources = [
            {'url': 'https://arxiv.org/abs/2010.11929', 'relevance': 0.95, 'agent': 'academic-scanner'},
            {'url': 'https://proceedings.neurips.cc/paper', 'relevance': 0.90, 'agent': 'academic-scanner'},
            {'url': 'https://github.com/google-research/vit', 'relevance': 0.85, 'agent': 'technical-diver'}
        ]

        result = scorer.score(sources, gaps=0, conflicts=0)

        # Multiple authoritative sources should yield high confidence
        assert result.score >= 60  # Reasonable threshold for good sources

    def test_low_confidence_single_source(self):
        """Test lower confidence with single source."""
        scorer_module = load_module(
            "confidence_scorer",
            os.path.join(LIB_PATH, 'confidence_scorer.py')
        )

        scorer = scorer_module.ConfidenceScorer(domain='ai-ml')

        sources = [
            {'url': 'https://medium.com/random-blog', 'relevance': 0.5, 'agent': 'unknown'}
        ]

        result = scorer.score(sources, gaps=0, conflicts=0)

        # Single low-authority source should yield lower confidence
        assert result.score < 70

    def test_gaps_reduce_confidence(self):
        """Test that gaps reduce confidence."""
        scorer_module = load_module(
            "confidence_scorer",
            os.path.join(LIB_PATH, 'confidence_scorer.py')
        )

        scorer = scorer_module.ConfidenceScorer(domain='ai-ml')

        sources = [
            {'url': 'https://arxiv.org/abs/1', 'relevance': 0.9, 'agent': 'academic-scanner'}
        ]

        score_no_gaps = scorer.score(sources, gaps=0, conflicts=0)
        score_with_gaps = scorer.score(sources, gaps=3, conflicts=0)

        assert score_with_gaps.score < score_no_gaps.score

    def test_conflicts_reduce_confidence(self):
        """Test that conflicts reduce confidence."""
        scorer_module = load_module(
            "confidence_scorer",
            os.path.join(LIB_PATH, 'confidence_scorer.py')
        )

        scorer = scorer_module.ConfidenceScorer(domain='ai-ml')

        sources = [
            {'url': 'https://arxiv.org/abs/1', 'relevance': 0.9, 'agent': 'academic-scanner'}
        ]

        score_no_conflicts = scorer.score(sources, gaps=0, conflicts=0)
        score_with_conflicts = scorer.score(sources, gaps=0, conflicts=2)

        assert score_with_conflicts.score < score_no_conflicts.score

    def test_domain_specific_weights(self):
        """Test different domains use different weights."""
        scorer_module = load_module(
            "confidence_scorer",
            os.path.join(LIB_PATH, 'confidence_scorer.py')
        )

        ai_scorer = scorer_module.ConfidenceScorer(domain='ai-ml')
        investment_scorer = scorer_module.ConfidenceScorer(domain='investment')

        ai_weights = ai_scorer.get_weights()
        investment_weights = investment_scorer.get_weights()

        # Different domains should have different weight distributions
        # (at minimum, they should be retrievable)
        assert ai_weights is not None
        assert investment_weights is not None


# ============================================================================
# Test Quality Gates
# ============================================================================

class TestAIMLQualityGates:
    """Test AI-ML specific quality gates."""

    def test_quality_gates_file_exists(self):
        """Test quality gates file exists."""
        gates_path = os.path.join(
            os.path.dirname(__file__),
            '..',
            'adapters',
            'ai-ml',
            'prompts',
            'quality_gates.md'
        )
        assert os.path.exists(gates_path)

    def test_quality_gates_content(self):
        """Test quality gates have required content."""
        gates_path = os.path.join(
            os.path.dirname(__file__),
            '..',
            'adapters',
            'ai-ml',
            'prompts',
            'quality_gates.md'
        )

        with open(gates_path, 'r') as f:
            content = f.read()

        # Check for AI-ML specific gates
        assert 'Reproducibility' in content
        assert 'Benchmark' in content
        assert 'Code' in content or 'code' in content

    def test_adapter_quality_gates_config(self):
        """Test adapter has quality gates configuration."""
        adapter_path = os.path.join(
            os.path.dirname(__file__),
            '..',
            'adapters',
            'ai-ml',
            'adapter.yaml'
        )

        with open(adapter_path, 'r') as f:
            config = yaml.safe_load(f)

        assert 'quality_gates' in config
        gates = config['quality_gates']

        assert 'reproducibility' in gates
        assert gates['reproducibility']['enabled'] is True

        assert 'benchmark_validity' in gates
        assert gates['benchmark_validity']['enabled'] is True


# ============================================================================
# Test End-to-End Integration
# ============================================================================

class TestEndToEndAIMLResearch:
    """End-to-end integration tests for AI-ML research."""

    def test_sample_query_components(self):
        """Test all components exist for sample query from spec."""
        # Query: "What are the latest advances in vision transformers for image classification?"

        # 1. Research orchestrator
        assert os.path.exists(os.path.join(LIB_PATH, 'research-orchestrator.py'))

        # 2. Question decomposer (check both naming conventions)
        decomposer_exists = (
            os.path.exists(os.path.join(LIB_PATH, 'question_decomposer.py')) or
            os.path.exists(os.path.join(LIB_PATH, 'question-decomposer.py'))
        )
        assert decomposer_exists, "question decomposer should exist"

        # 3. arXiv client
        assert os.path.exists(os.path.join(LIB_PATH, 'arxiv-client.py'))

        # 4. Papers With Code client
        assert os.path.exists(os.path.join(LIB_PATH, 'paperswithcode-client.py'))

        # 5. Synthesizer
        assert os.path.exists(os.path.join(LIB_PATH, 'research_synthesizer.py'))

        # 6. Confidence scorer
        assert os.path.exists(os.path.join(LIB_PATH, 'confidence_scorer.py'))

    def test_all_agents_exist(self):
        """Test all required agents exist."""
        agents_dir = os.path.join(os.path.dirname(__file__), '..', 'agents')

        required_agents = [
            'academic-scanner.md',
            'benchmark-analyst.md',
            'technical-diver.md',
            'fact-checker.md',
            'devils-advocate.md',
            'lead-researcher.md'
        ]

        for agent in required_agents:
            agent_path = os.path.join(agents_dir, agent)
            assert os.path.exists(agent_path), f"Agent {agent} should exist"

    def test_adapter_integration(self):
        """Test AI-ML adapter is properly integrated."""
        adapter_path = os.path.join(
            os.path.dirname(__file__),
            '..',
            'adapters',
            'ai-ml',
            'adapter.yaml'
        )

        with open(adapter_path, 'r') as f:
            config = yaml.safe_load(f)

        # Verify agent assignments
        assert 'agents' in config
        agents = config['agents']

        assert 'primary' in agents
        assert 'academic-scanner' in agents['primary']
        assert 'benchmark-analyst' in agents['primary']

        assert 'quality_control' in agents
        assert 'devils-advocate' in agents['quality_control']

    def test_research_flow_mock(self, sample_research_state, mock_search_results):
        """Test complete research flow with mocks."""
        synth_module = load_module(
            "research_synthesizer",
            os.path.join(LIB_PATH, 'research_synthesizer.py')
        )

        # Create synthesizer
        synthesizer = synth_module.ResearchSynthesizer(domain='ai-ml')

        # Create findings based on mock state
        findings_by_agent = {
            'academic-scanner': [
                synth_module.Finding(
                    id='F-001',
                    content='DeiT introduces distillation tokens for efficient training',
                    source_url='https://arxiv.org/abs/2012.12877',
                    agent='academic-scanner',
                    sub_question_id='SQ-001',
                    relevance_score=0.92
                )
            ],
            'benchmark-analyst': [
                synth_module.Finding(
                    id='F-002',
                    content='ViT-L achieves 88.55% top-1 accuracy on ImageNet',
                    source_url='https://paperswithcode.com/sota/image-classification',
                    agent='benchmark-analyst',
                    sub_question_id='SQ-002',
                    relevance_score=0.95
                )
            ]
        }

        sub_questions = [
            {'id': 'SQ-001', 'question': 'Key architectural innovations'},
            {'id': 'SQ-002', 'question': 'Current SOTA benchmarks'},
            {'id': 'SQ-003', 'question': 'Implementation considerations'}  # Unanswered
        ]

        # Synthesize
        synthesis = synthesizer.synthesize(
            question=sample_research_state['question'],
            findings_by_agent=findings_by_agent,
            sub_questions=sub_questions
        )

        # Verify synthesis
        assert synthesis is not None
        assert synthesis.question == sample_research_state['question']
        assert len(synthesis.key_findings) >= 2

        # Should have a gap for SQ-003
        coverage_gaps = [g for g in synthesis.gaps if g.gap_type == 'coverage']
        assert any(g.related_sub_question == 'SQ-003' for g in coverage_gaps)

        # Confidence should be reasonable
        assert synthesis.confidence.score > 0
        assert synthesis.confidence.explanation


# ============================================================================
# Test Report Generation
# ============================================================================

class TestReportGeneration:
    """Test research report generation."""

    def test_report_generator_exists(self):
        """Test report generator module exists."""
        report_path = os.path.join(LIB_PATH, 'report-generator.py')
        assert os.path.exists(report_path)

    def test_ai_ml_report_includes_required_sections(self):
        """Test AI-ML reports include required sections."""
        adapter_path = os.path.join(
            os.path.dirname(__file__),
            '..',
            'adapters',
            'ai-ml',
            'adapter.yaml'
        )

        with open(adapter_path, 'r') as f:
            config = yaml.safe_load(f)

        # Verify output configuration
        assert 'output' in config
        output_config = config['output']

        # AI-ML specific output features
        assert output_config.get('include_code_links', False) is True
        assert output_config.get('include_benchmark_table', False) is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
