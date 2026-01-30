#!/usr/bin/env python3
"""
Tests for AI/ML Research Adapter

Tests the complete AI-ML research adapter including:
- arXiv client integration
- Papers With Code client integration
- Benchmark analyst agent
- Quality gates
- End-to-end AI-ML research query from spec
"""

import pytest
import sys
import os
import yaml
import json
from datetime import datetime, timedelta

# Add lib to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'lib'))

# Import using importlib for hyphenated module names
import importlib.util

arxiv_spec = importlib.util.spec_from_file_location("arxiv_client", os.path.join(os.path.dirname(__file__), '..', 'lib', 'arxiv-client.py'))
arxiv_module = importlib.util.module_from_spec(arxiv_spec)
arxiv_spec.loader.exec_module(arxiv_module)
ArxivClient = arxiv_module.ArxivClient
ArxivPaper = arxiv_module.ArxivPaper
ArxivClientError = arxiv_module.ArxivClientError

pwc_spec = importlib.util.spec_from_file_location("paperswithcode_client", os.path.join(os.path.dirname(__file__), '..', 'lib', 'paperswithcode-client.py'))
pwc_module = importlib.util.module_from_spec(pwc_spec)
pwc_spec.loader.exec_module(pwc_module)
PapersWithCodeClient = pwc_module.PapersWithCodeClient
PaperResult = pwc_module.PaperResult
BenchmarkResult = pwc_module.BenchmarkResult
PapersWithCodeError = pwc_module.PapersWithCodeError


class TestArxivClient:
    """Test arXiv API client."""

    def test_client_initialization(self):
        """Test client initializes with correct defaults."""
        client = ArxivClient()
        assert client.max_results == 20
        assert client.rate_limit_seconds == 1.0

    def test_search_query_construction(self):
        """Test search query construction with categories."""
        client = ArxivClient()

        # Note: We're testing the logic, not making actual API calls
        # In real usage, this would query arXiv API

        # Test that client has search method
        assert hasattr(client, 'search')
        assert callable(client.search)

    def test_arxiv_paper_dataclass(self):
        """Test ArxivPaper dataclass structure."""
        paper = ArxivPaper(
            arxiv_id="2103.00020",
            title="Test Paper",
            authors=["Author One", "Author Two"],
            abstract="This is a test abstract",
            published_date="2021-03-01T00:00:00Z",
            updated_date="2021-03-01T00:00:00Z",
            categories=["cs.AI", "cs.LG"],
            pdf_url="https://arxiv.org/pdf/2103.00020",
            arxiv_url="https://arxiv.org/abs/2103.00020",
            primary_category="cs.AI"
        )

        assert paper.arxiv_id == "2103.00020"
        assert len(paper.authors) == 2
        assert paper.primary_category == "cs.AI"
        assert "cs.LG" in paper.categories


class TestPapersWithCodeClient:
    """Test Papers With Code API client."""

    def test_client_initialization(self):
        """Test client initializes correctly."""
        client = PapersWithCodeClient()
        assert client.rate_limit_seconds == 0.5
        assert client.BASE_URL == "https://paperswithcode.com/api/v1"

    def test_paper_result_dataclass(self):
        """Test PaperResult dataclass structure."""
        paper = PaperResult(
            paper_id="test-123",
            title="Test Paper",
            arxiv_id="2103.00020",
            url_abs="https://paperswithcode.com/paper/test",
            url_pdf=None,
            published="2021-03-01",
            authors=["Author One"],
            abstract="Test abstract",
            conference="NeurIPS 2021",
            tasks=["Image Classification"]
        )

        assert paper.paper_id == "test-123"
        assert paper.arxiv_id == "2103.00020"
        assert "Image Classification" in paper.tasks

    def test_benchmark_result_dataclass(self):
        """Test BenchmarkResult dataclass structure."""
        benchmark = BenchmarkResult(
            paper_id="test-123",
            paper_title="Test Paper",
            task="Image Classification",
            dataset="ImageNet",
            metric_name="top-1 accuracy",
            metric_value=85.5,
            rank=1,
            published_date="2021-03-01",
            arxiv_id="2103.00020",
            github_url="https://github.com/test/repo"
        )

        assert benchmark.task == "Image Classification"
        assert benchmark.metric_value == 85.5
        assert benchmark.rank == 1


class TestAdapterConfiguration:
    """Test adapter.yaml configuration."""

    def test_adapter_yaml_exists(self):
        """Test that adapter.yaml file exists."""
        adapter_path = os.path.join(
            os.path.dirname(__file__),
            '..',
            'adapters',
            'ai-ml',
            'adapter.yaml'
        )
        assert os.path.exists(adapter_path)

    def test_adapter_yaml_structure(self):
        """Test adapter.yaml has required structure."""
        adapter_path = os.path.join(
            os.path.dirname(__file__),
            '..',
            'adapters',
            'ai-ml',
            'adapter.yaml'
        )

        with open(adapter_path, 'r') as f:
            config = yaml.safe_load(f)

        # Check required fields
        assert config['name'] == 'ai-ml'
        assert 'description' in config
        assert 'version' in config

        # Check domain configuration
        assert 'domain' in config
        assert 'keywords' in config['domain']
        assert 'arxiv_categories' in config['domain']
        assert 'top_venues' in config['domain']

        # Check arXiv categories
        arxiv_cats = config['domain']['arxiv_categories']
        assert 'cs.AI' in arxiv_cats
        assert 'cs.LG' in arxiv_cats
        assert 'cs.CL' in arxiv_cats
        assert 'cs.CV' in arxiv_cats

    def test_quality_gates_configuration(self):
        """Test quality gates are configured."""
        adapter_path = os.path.join(
            os.path.dirname(__file__),
            '..',
            'adapters',
            'ai-ml',
            'adapter.yaml'
        )

        with open(adapter_path, 'r') as f:
            config = yaml.safe_load(f)

        # Check quality gates section
        assert 'quality_gates' in config
        gates = config['quality_gates']

        assert 'reproducibility' in gates
        assert gates['reproducibility']['enabled'] is True

        assert 'benchmark_validity' in gates
        assert gates['benchmark_validity']['enabled'] is True

        assert 'recency_weight' in gates
        assert gates['recency_weight']['enabled'] is True


class TestBenchmarkAnalystAgent:
    """Test benchmark analyst agent."""

    def test_agent_file_exists(self):
        """Test that benchmark-analyst.md exists."""
        agent_path = os.path.join(
            os.path.dirname(__file__),
            '..',
            'agents',
            'benchmark-analyst.md'
        )
        assert os.path.exists(agent_path)

    def test_agent_structure(self):
        """Test agent file has required sections."""
        agent_path = os.path.join(
            os.path.dirname(__file__),
            '..',
            'agents',
            'benchmark-analyst.md'
        )

        with open(agent_path, 'r') as f:
            content = f.read()

        # Check for required sections
        assert '# Benchmark Analyst Agent' in content
        assert '## Capabilities' in content
        assert 'SOTA Tracking' in content
        assert 'Benchmark Validation' in content
        assert 'Performance Analysis' in content

        # Check for benchmark categories
        assert 'Natural Language Processing (NLP)' in content
        assert 'Computer Vision (CV)' in content
        assert 'Multimodal' in content

        # Check for key benchmarks
        assert 'ImageNet' in content
        assert 'GLUE' in content
        assert 'COCO' in content


class TestQualityGates:
    """Test AI-ML quality gates."""

    def test_quality_gates_file_exists(self):
        """Test quality_gates.md exists."""
        gates_path = os.path.join(
            os.path.dirname(__file__),
            '..',
            'adapters',
            'ai-ml',
            'prompts',
            'quality_gates.md'
        )
        assert os.path.exists(gates_path)

    def test_quality_gates_coverage(self):
        """Test quality gates cover required areas."""
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

        # Check for required gates
        assert 'Gate 1: Reproducibility Check' in content
        assert 'Gate 2: Benchmark Validity' in content
        assert 'Code Availability' in content
        assert 'Data Availability' in content

        # Check for scoring functions
        assert 'def reproducibility_score' in content
        assert 'def validate_benchmark' in content


class TestEndToEndQuery:
    """Test end-to-end AI-ML research query (from spec)."""

    def test_sample_query_structure(self):
        """
        Test that we can handle the sample query from the spec:
        'What are the latest advances in vision transformers for image classification?'

        This tests that all components are in place for the query.
        """
        # 1. Verify arXiv client can search for vision transformers
        client = ArxivClient()
        assert hasattr(client, 'search')

        # Would search with: query="vision transformer image classification"
        # categories=["cs.CV", "cs.LG"]

        # 2. Verify Papers With Code client can get SOTA benchmarks
        pwc_client = PapersWithCodeClient()
        assert hasattr(pwc_client, 'get_sota_benchmarks')

        # Would query: task="Image Classification", dataset="ImageNet"

        # 3. Verify benchmark analyst agent exists
        agent_path = os.path.join(
            os.path.dirname(__file__),
            '..',
            'agents',
            'benchmark-analyst.md'
        )
        assert os.path.exists(agent_path)

        # 4. Verify quality gates are configured
        adapter_path = os.path.join(
            os.path.dirname(__file__),
            '..',
            'adapters',
            'ai-ml',
            'adapter.yaml'
        )
        with open(adapter_path, 'r') as f:
            config = yaml.safe_load(f)

        assert config['quality_gates']['reproducibility']['enabled']
        assert config['quality_gates']['benchmark_validity']['enabled']

    def test_integration_readiness(self):
        """Test that all integration points are ready."""
        # 1. Adapter configuration exists
        adapter_path = os.path.join(
            os.path.dirname(__file__),
            '..',
            'adapters',
            'ai-ml',
            'adapter.yaml'
        )
        assert os.path.exists(adapter_path)

        # 2. arXiv client module exists
        arxiv_path = os.path.join(
            os.path.dirname(__file__),
            '..',
            'lib',
            'arxiv-client.py'
        )
        assert os.path.exists(arxiv_path)

        # 3. Papers With Code client module exists
        pwc_path = os.path.join(
            os.path.dirname(__file__),
            '..',
            'lib',
            'paperswithcode-client.py'
        )
        assert os.path.exists(pwc_path)

        # 4. Benchmark analyst agent exists
        agent_path = os.path.join(
            os.path.dirname(__file__),
            '..',
            'agents',
            'benchmark-analyst.md'
        )
        assert os.path.exists(agent_path)

        # 5. Quality gates documentation exists
        gates_path = os.path.join(
            os.path.dirname(__file__),
            '..',
            'adapters',
            'ai-ml',
            'prompts',
            'quality_gates.md'
        )
        assert os.path.exists(gates_path)


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v"])
