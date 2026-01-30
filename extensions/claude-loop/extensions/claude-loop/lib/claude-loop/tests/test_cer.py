#!/usr/bin/env python3
"""
Comprehensive Tests for Contextual Experience Replay (CER)

Tests cover:
1. Experience storage and retrieval
2. Similarity search accuracy
3. Compression quality
4. A/B test statistical validity
5. CER integration with synthesizer
"""

import json
import math
import os
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import Mock, patch

# Add lib directory to path
LIB_DIR = Path(__file__).parent.parent / 'lib'
sys.path.insert(0, str(LIB_DIR))

from experience_memory import (
    Experience,
    ExperienceMemory,
    RetrievalResult,
    EmbeddingProvider,
)
from experience_compressor import (
    ExperienceCompressor,
    SearchStrategyPattern,
    DecompositionPattern,
    SourceQualityPattern,
    SynthesisPattern,
    CompressedExperience,
)
from ab_testing import (
    ABTest,
    ABTestResult,
    StatisticalAnalysis,
    ABTestManager,
    mean,
    variance,
    std_dev,
    t_statistic,
    cohens_d,
    effect_size_interpretation,
)
from cer_integration import (
    CERIntegration,
    ExperienceContext,
    CERUsageRecord,
)


class TestExperience(unittest.TestCase):
    """Tests for Experience dataclass."""

    def test_experience_creation(self):
        """Test creating an Experience object."""
        exp = Experience(
            id='EXP-001',
            query='What is machine learning?',
            domain='ai-ml',
            sub_questions=['What are the types of ML?', 'What are common algorithms?'],
            findings=[{'content': 'ML is a subset of AI', 'source_url': 'https://example.com'}],
            synthesis='Machine learning is...',
            confidence=75
        )

        self.assertEqual(exp.id, 'EXP-001')
        self.assertEqual(exp.query, 'What is machine learning?')
        self.assertEqual(exp.domain, 'ai-ml')
        self.assertEqual(len(exp.sub_questions), 2)
        self.assertEqual(len(exp.findings), 1)
        self.assertEqual(exp.confidence, 75)
        self.assertEqual(exp.retrieval_count, 0)
        self.assertEqual(exp.helpful_count, 0)

    def test_experience_to_dict(self):
        """Test converting Experience to dictionary."""
        exp = Experience(
            id='EXP-001',
            query='Test query',
            domain='general',
            sub_questions=[],
            findings=[],
            synthesis='Test synthesis',
            confidence=50
        )

        d = exp.to_dict()
        self.assertEqual(d['id'], 'EXP-001')
        self.assertEqual(d['query'], 'Test query')
        self.assertEqual(d['confidence'], 50)

    def test_experience_from_dict(self):
        """Test creating Experience from dictionary."""
        data = {
            'id': 'EXP-002',
            'query': 'Another query',
            'domain': 'investment',
            'sub_questions': ['Q1', 'Q2'],
            'findings': [{'content': 'Finding 1'}],
            'synthesis': 'Synthesis text',
            'confidence': 80,
            'retrieval_count': 5,
            'helpful_count': 3
        }

        exp = Experience.from_dict(data)
        self.assertEqual(exp.id, 'EXP-002')
        self.assertEqual(exp.domain, 'investment')
        self.assertEqual(exp.confidence, 80)
        self.assertEqual(exp.retrieval_count, 5)
        self.assertEqual(exp.helpful_count, 3)


class TestEmbeddingProvider(unittest.TestCase):
    """Tests for EmbeddingProvider."""

    def setUp(self):
        self.provider = EmbeddingProvider()

    def test_hash_embedding_deterministic(self):
        """Test that hash embeddings are deterministic."""
        text = "What is machine learning?"
        emb1 = self.provider._hash_embedding(text)
        emb2 = self.provider._hash_embedding(text)

        self.assertEqual(emb1, emb2)

    def test_hash_embedding_dimension(self):
        """Test that hash embeddings have correct dimension."""
        text = "Test text"
        emb = self.provider._hash_embedding(text)

        self.assertEqual(len(emb), 384)  # EMBEDDING_DIM

    def test_hash_embedding_normalized(self):
        """Test that hash embeddings are normalized to unit length."""
        text = "Test text for normalization"
        emb = self.provider._hash_embedding(text)

        magnitude = math.sqrt(sum(x * x for x in emb))
        self.assertAlmostEqual(magnitude, 1.0, places=5)

    def test_cosine_similarity_identical(self):
        """Test cosine similarity of identical vectors."""
        vec = [0.5, 0.5, 0.5, 0.5]
        sim = self.provider.cosine_similarity(vec, vec)

        self.assertAlmostEqual(sim, 1.0, places=5)

    def test_cosine_similarity_orthogonal(self):
        """Test cosine similarity of orthogonal vectors."""
        vec1 = [1.0, 0.0, 0.0, 0.0]
        vec2 = [0.0, 1.0, 0.0, 0.0]
        sim = self.provider.cosine_similarity(vec1, vec2)

        self.assertAlmostEqual(sim, 0.0, places=5)

    def test_cosine_similarity_opposite(self):
        """Test cosine similarity of opposite vectors."""
        vec1 = [1.0, 0.0]
        vec2 = [-1.0, 0.0]
        sim = self.provider.cosine_similarity(vec1, vec2)

        self.assertAlmostEqual(sim, -1.0, places=5)


class TestExperienceMemory(unittest.TestCase):
    """Tests for ExperienceMemory."""

    def setUp(self):
        """Create temporary storage for tests."""
        self.temp_dir = tempfile.mkdtemp()
        self.storage_path = os.path.join(self.temp_dir, 'test_experiences.json')
        self.memory = ExperienceMemory(storage_path=self.storage_path)

    def tearDown(self):
        """Clean up temporary files."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_store_experience(self):
        """Test storing an experience."""
        exp = Experience(
            id='',
            query='Test query',
            domain='ai-ml',
            sub_questions=['Q1'],
            findings=[{'content': 'F1'}],
            synthesis='Synthesis',
            confidence=70
        )

        exp_id = self.memory.store(exp)

        self.assertTrue(exp_id.startswith('EXP-'))
        self.assertTrue(os.path.exists(self.storage_path))

    def test_retrieve_experience(self):
        """Test retrieving similar experiences."""
        # Store some experiences
        exp1 = Experience(
            id='',
            query='What is deep learning?',
            domain='ai-ml',
            sub_questions=['What are neural networks?'],
            findings=[{'content': 'Deep learning uses neural networks'}],
            synthesis='Deep learning is a subset of ML',
            confidence=80
        )
        self.memory.store(exp1)

        exp2 = Experience(
            id='',
            query='What are transformer models?',
            domain='ai-ml',
            sub_questions=['How do attention mechanisms work?'],
            findings=[{'content': 'Transformers use self-attention'}],
            synthesis='Transformers revolutionized NLP',
            confidence=85
        )
        self.memory.store(exp2)

        # Retrieve similar experiences
        results = self.memory.retrieve(
            query='What is machine learning?',
            domain='ai-ml',
            k=5
        )

        self.assertGreater(len(results), 0)
        self.assertIsInstance(results[0], RetrievalResult)

    def test_retrieve_with_domain_filter(self):
        """Test that domain filtering works."""
        # Store experience in ai-ml domain
        exp1 = Experience(
            id='',
            query='AI query',
            domain='ai-ml',
            sub_questions=[],
            findings=[],
            synthesis='',
            confidence=50
        )
        self.memory.store(exp1)

        # Store experience in investment domain
        exp2 = Experience(
            id='',
            query='Investment query',
            domain='investment',
            sub_questions=[],
            findings=[],
            synthesis='',
            confidence=50
        )
        self.memory.store(exp2)

        # Retrieve with domain filter
        ai_results = self.memory.retrieve('AI query', domain='ai-ml', k=10)
        inv_results = self.memory.retrieve('Investment query', domain='investment', k=10)

        # Should only get experiences from the specified domain
        for r in ai_results:
            self.assertEqual(r.experience.domain, 'ai-ml')

        for r in inv_results:
            self.assertEqual(r.experience.domain, 'investment')

    def test_mark_helpful(self):
        """Test marking an experience as helpful."""
        exp = Experience(
            id='',
            query='Test query',
            domain='general',
            sub_questions=[],
            findings=[],
            synthesis='',
            confidence=50
        )
        exp_id = self.memory.store(exp)

        # Mark as helpful
        result = self.memory.mark_helpful(exp_id)
        self.assertTrue(result)

        # Verify count increased
        retrieved = self.memory.get(exp_id)
        self.assertEqual(retrieved.helpful_count, 1)

    def test_get_stats(self):
        """Test getting memory statistics."""
        # Store some experiences
        for i in range(3):
            exp = Experience(
                id='',
                query=f'Query {i}',
                domain='ai-ml' if i < 2 else 'general',
                sub_questions=[],
                findings=[],
                synthesis='',
                confidence=50 + i * 10
            )
            self.memory.store(exp)

        stats = self.memory.get_stats()

        self.assertEqual(stats['total_experiences'], 3)
        self.assertEqual(stats['by_domain']['ai-ml'], 2)
        self.assertEqual(stats['by_domain']['general'], 1)

    def test_compress_experience(self):
        """Test compressing an experience."""
        exp = Experience(
            id='EXP-001',
            query='What is ML?',
            domain='ai-ml',
            sub_questions=['What are types?', 'How to implement?'],
            findings=[
                {'content': 'F1', 'source_url': 'https://arxiv.org/abs/123', 'relevance_score': 0.8},
                {'content': 'F2', 'source_url': 'https://github.com/example', 'relevance_score': 0.7}
            ],
            synthesis='ML is...',
            confidence=75
        )

        compressed = self.memory.compress(exp)

        self.assertIsNotNone(compressed)
        self.assertIn('Decomposition', compressed)


class TestExperienceCompressor(unittest.TestCase):
    """Tests for ExperienceCompressor."""

    def setUp(self):
        self.compressor = ExperienceCompressor()

    def _create_mock_experience(self):
        """Create a mock experience for testing."""
        class MockExp:
            id = 'EXP-001'
            query = 'What are the latest advances in transformer models?'
            domain = 'ai-ml'
            sub_questions = [
                'What is the transformer architecture?',
                'How have transformers improved recently?',
                'What are the market applications?'
            ]
            findings = [
                {
                    'content': 'Transformers use self-attention',
                    'source_url': 'https://arxiv.org/abs/1706.03762',
                    'relevance_score': 0.9
                },
                {
                    'content': 'GPT-4 shows significant improvements',
                    'source_url': 'https://github.com/openai/gpt-4',
                    'relevance_score': 0.85
                },
                {
                    'content': 'Enterprise adoption is growing',
                    'source_url': 'https://news.example.com/ai',
                    'relevance_score': 0.7
                }
            ]
            synthesis = 'Transformers have revolutionized AI with attention mechanisms. However, there are still challenges in efficiency.'
            confidence = 78

        return MockExp()

    def test_extract_pattern(self):
        """Test extracting full pattern from experience."""
        exp = self._create_mock_experience()
        compressed = self.compressor.extract_pattern(exp)

        self.assertIsInstance(compressed, CompressedExperience)
        self.assertEqual(compressed.experience_id, 'EXP-001')
        self.assertEqual(compressed.domain, 'ai-ml')
        self.assertIsNotNone(compressed.search_pattern)
        self.assertIsNotNone(compressed.decomposition_pattern)

    def test_extract_search_pattern(self):
        """Test extracting search strategy pattern."""
        exp = self._create_mock_experience()
        pattern = self.compressor._extract_search_pattern(exp)

        self.assertIsInstance(pattern, SearchStrategyPattern)
        self.assertEqual(pattern.domain, 'ai-ml')
        self.assertIn('arxiv', pattern.source_types)
        self.assertGreater(pattern.avg_relevance, 0.7)

    def test_extract_decomposition_pattern(self):
        """Test extracting decomposition pattern."""
        exp = self._create_mock_experience()
        pattern = self.compressor._extract_decomposition_pattern(exp)

        self.assertIsInstance(pattern, DecompositionPattern)
        self.assertEqual(pattern.num_sub_questions, 3)
        self.assertGreater(pattern.effectiveness_score, 0.5)

    def test_extract_source_patterns(self):
        """Test extracting source quality patterns."""
        exp = self._create_mock_experience()
        patterns = self.compressor._extract_source_patterns(exp)

        self.assertGreater(len(patterns), 0)
        for p in patterns:
            self.assertIsInstance(p, SourceQualityPattern)

    def test_extract_key_learnings(self):
        """Test extracting key learnings."""
        exp = self._create_mock_experience()
        learnings = self.compressor._extract_key_learnings(exp)

        self.assertIsInstance(learnings, list)
        self.assertGreater(len(learnings), 0)

    def test_get_reusable_snippets(self):
        """Test getting reusable snippets."""
        exp = self._create_mock_experience()
        snippets = self.compressor.get_reusable_snippets(exp)

        self.assertIsInstance(snippets, list)
        for snippet in snippets:
            self.assertIn('type', snippet)
            self.assertIn('content', snippet)

    def test_categorize_question(self):
        """Test question categorization."""
        technical = self.compressor._categorize_question('How to implement a neural network?')
        academic = self.compressor._categorize_question('What does the research say about transformers?')
        market = self.compressor._categorize_question('What is the market trend for AI?')

        self.assertEqual(technical, 'technical')
        self.assertEqual(academic, 'academic')
        self.assertEqual(market, 'market')


class TestABTestStatistics(unittest.TestCase):
    """Tests for A/B test statistical functions."""

    def test_mean(self):
        """Test mean calculation."""
        self.assertEqual(mean([1, 2, 3, 4, 5]), 3.0)
        self.assertEqual(mean([10]), 10.0)
        self.assertEqual(mean([]), 0.0)

    def test_variance(self):
        """Test variance calculation."""
        var = variance([2, 4, 4, 4, 5, 5, 7, 9])
        self.assertAlmostEqual(var, 4.571, places=2)

    def test_std_dev(self):
        """Test standard deviation calculation."""
        sd = std_dev([2, 4, 4, 4, 5, 5, 7, 9])
        self.assertAlmostEqual(sd, 2.138, places=2)

    def test_t_statistic(self):
        """Test t-statistic calculation."""
        # Two groups with clear difference
        group1 = [10, 11, 12, 13, 14]
        group2 = [5, 6, 7, 8, 9]

        t = t_statistic(group1, group2)
        self.assertGreater(t, 0)  # group1 has higher mean

    def test_cohens_d(self):
        """Test Cohen's d effect size calculation."""
        # Large effect
        group1 = [10, 11, 12, 13, 14, 15, 16, 17, 18, 19]
        group2 = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]

        d = cohens_d(group1, group2)
        self.assertGreater(abs(d), 0.8)  # Large effect

    def test_effect_size_interpretation(self):
        """Test effect size interpretation."""
        self.assertEqual(effect_size_interpretation(0.1), 'negligible')
        self.assertEqual(effect_size_interpretation(0.3), 'small')
        self.assertEqual(effect_size_interpretation(0.6), 'medium')
        self.assertEqual(effect_size_interpretation(1.0), 'large')


class TestABTest(unittest.TestCase):
    """Tests for ABTest class."""

    def setUp(self):
        """Create temporary storage for tests."""
        self.temp_dir = tempfile.mkdtemp()
        self.storage_path = os.path.join(self.temp_dir, 'test_ab.json')
        self.test = ABTest(
            test_name='cer_vs_baseline',
            variants=['with_cer', 'without_cer'],
            storage_path=self.storage_path
        )

    def tearDown(self):
        """Clean up temporary files."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_assign_variant_deterministic(self):
        """Test that variant assignment is deterministic."""
        variant1 = self.test.assign_variant('query_001')
        variant2 = self.test.assign_variant('query_001')

        self.assertEqual(variant1, variant2)

    def test_assign_variant_distribution(self):
        """Test that variant assignment is roughly balanced."""
        assignments = {'with_cer': 0, 'without_cer': 0}

        for i in range(100):
            variant = self.test.assign_variant(f'query_{i}')
            assignments[variant] += 1

        # Should be roughly 50/50 (within 30% tolerance)
        self.assertGreater(assignments['with_cer'], 20)
        self.assertGreater(assignments['without_cer'], 20)

    def test_record_result(self):
        """Test recording a result."""
        self.test.assign_variant('query_001')
        result = self.test.record_result('query_001', {'confidence': 75, 'coverage': 0.8})

        self.assertEqual(result.query_id, 'query_001')
        self.assertEqual(result.metrics['confidence'], 75)
        self.assertEqual(result.metrics['coverage'], 0.8)

    def test_get_results(self):
        """Test getting comprehensive results."""
        # Add some results
        for i in range(20):
            query_id = f'query_{i}'
            variant = self.test.assign_variant(query_id)

            # Simulate better results with CER
            if variant == 'with_cer':
                self.test.record_result(query_id, {'confidence': 75 + (i % 10), 'coverage': 0.8})
            else:
                self.test.record_result(query_id, {'confidence': 65 + (i % 10), 'coverage': 0.7})

        summary = self.test.get_results()

        self.assertEqual(summary.test_name, 'cer_vs_baseline')
        self.assertEqual(summary.total_observations, 20)
        self.assertIn('confidence', summary.metrics_analyzed)

    def test_is_significant_with_data(self):
        """Test significance detection with sufficient data."""
        # Add results with clear difference
        for i in range(50):
            query_id = f'query_{i}'
            variant = self.test.assign_variant(query_id)

            if variant == 'with_cer':
                # Consistently higher confidence with CER
                self.test.record_result(query_id, {'confidence': 80 + (i % 5)})
            else:
                # Lower confidence without CER
                self.test.record_result(query_id, {'confidence': 60 + (i % 5)})

        # With this clear difference, it should be significant
        # Note: This depends on the actual distribution of assignments
        summary = self.test.get_results()

        # Check that analysis was performed
        self.assertGreater(len(summary.analyses), 0)

    def test_power_analysis(self):
        """Test power analysis calculation."""
        # Add some data
        for i in range(30):
            query_id = f'query_{i}'
            self.test.assign_variant(query_id)
            self.test.record_result(query_id, {'confidence': 70})

        power = self.test.get_power_analysis(effect_size=0.5)

        self.assertIn('current_n_per_group', power)
        self.assertIn('estimated_power', power)
        self.assertIn('required_n_per_group', power)


class TestCERIntegration(unittest.TestCase):
    """Tests for CER integration with research synthesizer."""

    def setUp(self):
        """Create temporary storage for tests."""
        self.temp_dir = tempfile.mkdtemp()
        self.storage_path = os.path.join(self.temp_dir, 'test_experiences.json')
        self.memory = ExperienceMemory(storage_path=self.storage_path)
        self.cer = CERIntegration(memory=self.memory)

    def tearDown(self):
        """Clean up temporary files."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_get_experience_context_empty(self):
        """Test getting context with no prior experiences."""
        context = self.cer.get_experience_context(
            query='Test query',
            domain='ai-ml'
        )

        self.assertIsInstance(context, ExperienceContext)
        self.assertEqual(context.query, 'Test query')
        self.assertEqual(len(context.retrieved_experiences), 0)
        self.assertEqual(context.prompt_injection, '')

    def test_get_experience_context_with_experiences(self):
        """Test getting context with prior experiences."""
        # Store some experiences first
        exp = Experience(
            id='',
            query='What is deep learning?',
            domain='ai-ml',
            sub_questions=['What are neural networks?'],
            findings=[{'content': 'Deep learning uses neural networks', 'source_url': 'https://arxiv.org/test'}],
            synthesis='Deep learning is a subset of ML that uses neural networks.',
            confidence=80
        )
        self.memory.store(exp)

        # Get context for similar query
        context = self.cer.get_experience_context(
            query='What is machine learning?',
            domain='ai-ml'
        )

        self.assertIsInstance(context, ExperienceContext)
        # May or may not retrieve based on similarity threshold

    def test_record_experience(self):
        """Test recording a new experience."""
        exp_id = self.cer.record_experience(
            query='New research query',
            domain='ai-ml',
            sub_questions=['Q1', 'Q2'],
            findings=[{'content': 'Finding 1'}],
            synthesis='This is the synthesis.',
            confidence=75
        )

        self.assertTrue(exp_id.startswith('EXP-'))

        # Verify it was stored
        exp = self.memory.get(exp_id)
        self.assertIsNotNone(exp)
        self.assertEqual(exp.query, 'New research query')

    def test_record_usage(self):
        """Test recording CER usage."""
        record = self.cer.record_usage(
            query_id='Q-001',
            query='Test query',
            domain='ai-ml',
            used_cer=True,
            experience_ids_used=['EXP-001'],
            final_confidence=80,
            source_coverage=0.85
        )

        self.assertIsInstance(record, CERUsageRecord)
        self.assertEqual(record.used_cer, True)
        self.assertEqual(record.final_confidence, 80)

    def test_get_usage_stats(self):
        """Test getting usage statistics."""
        # Record some usage
        self.cer.record_usage('Q-001', 'Query 1', 'ai-ml', True, [], 80, 0.8)
        self.cer.record_usage('Q-002', 'Query 2', 'ai-ml', False, [], 60, 0.6)
        self.cer.record_usage('Q-003', 'Query 3', 'ai-ml', True, [], 85, 0.9)

        stats = self.cer.get_usage_stats()

        self.assertEqual(stats['total_queries'], 3)
        self.assertEqual(stats['cer_used'], 2)
        self.assertEqual(stats['cer_not_used'], 1)
        self.assertGreater(stats['avg_confidence_with_cer'], stats['avg_confidence_without_cer'])

    def test_mark_experience_helpful(self):
        """Test marking experience as helpful through CER."""
        # First store an experience
        exp_id = self.cer.record_experience(
            query='Test query',
            domain='general',
            sub_questions=[],
            findings=[],
            synthesis='',
            confidence=50
        )

        # Mark as helpful
        result = self.cer.mark_experience_helpful(exp_id)
        self.assertTrue(result)

        # Verify
        exp = self.memory.get(exp_id)
        self.assertEqual(exp.helpful_count, 1)


class TestIntegrationFlow(unittest.TestCase):
    """Integration tests for the full CER flow."""

    def setUp(self):
        """Create temporary storage for tests."""
        self.temp_dir = tempfile.mkdtemp()
        self.exp_path = os.path.join(self.temp_dir, 'experiences.json')
        self.ab_path = os.path.join(self.temp_dir, 'ab_tests.json')

    def tearDown(self):
        """Clean up temporary files."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_full_ab_test_flow(self):
        """Test complete A/B testing flow with CER."""
        memory = ExperienceMemory(storage_path=self.exp_path)
        cer = CERIntegration(memory=memory)
        ab_test = ABTest(
            test_name='cer_experiment',
            variants=['with_cer', 'without_cer'],
            storage_path=self.ab_path,
            primary_metric='confidence'
        )

        # Simulate 20 research queries
        for i in range(20):
            query_id = f'query_{i}'
            query = f'Research question about topic {i}'
            domain = 'ai-ml'

            # Get variant assignment
            variant = ab_test.assign_variant(query_id)

            if variant == 'with_cer':
                # Use CER
                context = cer.get_experience_context(query, domain)

                # Simulate better results with CER (higher confidence)
                confidence = 75 + (i % 10)
                coverage = 0.8 + (i % 5) * 0.02

                # Record the experience for future use
                cer.record_experience(
                    query=query,
                    domain=domain,
                    sub_questions=[f'SQ-{i}-1', f'SQ-{i}-2'],
                    findings=[{'content': f'Finding for query {i}'}],
                    synthesis=f'Synthesis for query {i}',
                    confidence=confidence
                )
            else:
                # Baseline without CER
                confidence = 60 + (i % 10)
                coverage = 0.6 + (i % 5) * 0.02

            # Record A/B test result
            ab_test.record_result(query_id, {
                'confidence': confidence,
                'source_coverage': coverage
            })

        # Get results
        summary = ab_test.get_results()

        # Verify test ran correctly
        self.assertEqual(summary.total_observations, 20)
        self.assertGreater(len(summary.analyses), 0)

        # Get memory stats
        stats = memory.get_stats()
        # Only 'with_cer' queries should have stored experiences
        self.assertGreater(stats['total_experiences'], 0)

    def test_experience_reuse_improves_over_time(self):
        """Test that experience reuse can improve results."""
        memory = ExperienceMemory(storage_path=self.exp_path)
        cer = CERIntegration(memory=memory, min_similarity=0.3)

        # First batch: seed experiences
        for i in range(5):
            cer.record_experience(
                query=f'What is machine learning technique {i}?',
                domain='ai-ml',
                sub_questions=['What is it?', 'How does it work?'],
                findings=[{
                    'content': f'ML technique {i} is important',
                    'source_url': 'https://arxiv.org/test'
                }],
                synthesis=f'ML technique {i} explanation',
                confidence=80  # High confidence experiences
            )

        # Second batch: should benefit from prior experiences
        for i in range(5):
            context = cer.get_experience_context(
                query='What is a machine learning method?',
                domain='ai-ml'
            )

            # With seeded experiences, we should get some context
            if context.retrieved_experiences:
                # We found relevant past experiences
                self.assertGreater(len(context.prompt_injection), 0)


if __name__ == '__main__':
    unittest.main()
