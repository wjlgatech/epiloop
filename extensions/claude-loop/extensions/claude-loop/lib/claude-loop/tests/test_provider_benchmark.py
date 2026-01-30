#!/usr/bin/env python3
"""
Tests for provider_benchmark.py
"""

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from lib.provider_benchmark import (
    Benchmarker,
    BenchmarkComparison,
    BenchmarkResult,
)
from lib.llm_config import LLMConfigManager, ProviderConfig
from lib.llm_provider import LLMResponse, Message, MessageRole, TokenUsage


class TestBenchmarker(unittest.TestCase):
    """Test Benchmarker class"""

    def setUp(self):
        """Set up test fixtures"""
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, "test_benchmarks.db")
        self.config_manager = MagicMock(spec=LLMConfigManager)

        # Mock provider configs
        self.openai_config = ProviderConfig(
            name="openai",
            enabled=True,
            api_key="test-key",
            base_url="https://api.openai.com/v1",
            timeout=120,
            max_tokens=4096,
            default_model="gpt-4o",
            available_models=["gpt-4o"],
            input_cost_per_1k=2.5,
            output_cost_per_1k=10.0,
            extra_settings={}
        )

        self.gemini_config = ProviderConfig(
            name="gemini",
            enabled=True,
            api_key="test-key",
            base_url="https://generativelanguage.googleapis.com/v1beta",
            timeout=120,
            max_tokens=4096,
            default_model="gemini-2.0-flash",
            available_models=["gemini-2.0-flash"],
            input_cost_per_1k=0.075,
            output_cost_per_1k=0.30,
            extra_settings={}
        )

        self.benchmarker = Benchmarker(
            config_manager=self.config_manager,
            db_path=self.db_path
        )

    def tearDown(self):
        """Clean up test fixtures"""
        import shutil
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    def test_init_database(self):
        """Test database initialization"""
        self.assertTrue(os.path.exists(self.db_path))

        # Verify tables exist
        import sqlite3
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='benchmarks'")
        result = cursor.fetchone()
        conn.close()

        self.assertIsNotNone(result)
        self.assertEqual(result[0], "benchmarks")

    @patch('lib.providers.openai_provider.OpenAIProvider')
    @patch('lib.providers.gemini_provider.GeminiProvider')
    def test_run_benchmark_single_provider(self, mock_gemini, mock_openai):
        """Test running benchmark on a single provider"""
        # Mock config manager
        self.config_manager.list_providers.return_value = [self.openai_config]
        self.config_manager.get_provider.return_value = self.openai_config

        # Mock provider response
        mock_provider = Mock()
        mock_openai.return_value = mock_provider

        mock_response = LLMResponse(
            content="Test response",
            model="gpt-4o",
            usage=TokenUsage(input_tokens=10, output_tokens=20, total_tokens=30),
            cost=0.001,
            provider="openai"
        )
        mock_provider.complete.return_value = mock_response

        # Run benchmark
        results = self.benchmarker.run_benchmark(
            prompt="Test prompt",
            task_type="general",
            providers=["openai"]
        )

        self.assertEqual(len(results), 1)
        result = results[0]

        self.assertEqual(result.provider, "openai")
        self.assertEqual(result.model, "gpt-4o")
        self.assertEqual(result.prompt, "Test prompt")
        self.assertEqual(result.task_type, "general")
        self.assertEqual(result.response, "Test response")
        self.assertEqual(result.input_tokens, 10)
        self.assertEqual(result.output_tokens, 20)
        self.assertEqual(result.cost, 0.001)
        self.assertIsNone(result.error)
        self.assertGreater(result.latency_ms, 0)

    @patch('lib.providers.openai_provider.OpenAIProvider')
    @patch('lib.providers.gemini_provider.GeminiProvider')
    def test_run_benchmark_multiple_providers(self, mock_gemini, mock_openai):
        """Test running benchmark on multiple providers"""
        # Mock config manager
        self.config_manager.list_providers.return_value = [
            self.openai_config,
            self.gemini_config
        ]

        # Return appropriate config for each provider
        def get_provider_side_effect(name):
            if name == "openai":
                return self.openai_config
            elif name == "gemini":
                return self.gemini_config
            return None

        self.config_manager.get_provider.side_effect = get_provider_side_effect

        # Mock OpenAI provider
        mock_openai_instance = Mock()
        mock_openai.return_value = mock_openai_instance
        mock_openai_instance.complete.return_value = LLMResponse(
            content="OpenAI response",
            model="gpt-4o",
            usage=TokenUsage(input_tokens=10, output_tokens=20, total_tokens=30),
            cost=0.001,
            provider="openai"
        )

        # Mock Gemini provider
        mock_gemini_instance = Mock()
        mock_gemini.return_value = mock_gemini_instance
        mock_gemini_instance.complete.return_value = LLMResponse(
            content="Gemini response",
            model="gemini-2.0-flash",
            usage=TokenUsage(input_tokens=10, output_tokens=20, total_tokens=30),
            cost=0.0002,
            provider="gemini"
        )

        # Run benchmark
        results = self.benchmarker.run_benchmark(
            prompt="Test prompt",
            task_type="general",
            providers=["openai", "gemini"]
        )

        self.assertEqual(len(results), 2)

        # Check OpenAI result
        openai_result = next(r for r in results if r.provider == "openai")
        self.assertEqual(openai_result.response, "OpenAI response")
        self.assertEqual(openai_result.cost, 0.001)

        # Check Gemini result
        gemini_result = next(r for r in results if r.provider == "gemini")
        self.assertEqual(gemini_result.response, "Gemini response")
        self.assertEqual(gemini_result.cost, 0.0002)

    @patch('lib.providers.openai_provider.OpenAIProvider')
    def test_run_benchmark_with_error(self, mock_openai):
        """Test benchmark with provider error"""
        # Mock config manager
        self.config_manager.get_provider.return_value = self.openai_config

        # Mock provider to raise error
        mock_provider = Mock()
        mock_openai.return_value = mock_provider
        mock_provider.complete.side_effect = Exception("API Error")

        # Run benchmark
        results = self.benchmarker.run_benchmark(
            prompt="Test prompt",
            task_type="general",
            providers=["openai"]
        )

        self.assertEqual(len(results), 1)
        result = results[0]

        self.assertEqual(result.provider, "openai")
        self.assertIsNotNone(result.error)
        if result.error:
            self.assertIn("API Error", result.error)
        self.assertEqual(result.latency_ms, 0.0)
        self.assertEqual(result.cost, 0.0)

    @patch('lib.providers.openai_provider.OpenAIProvider')
    def test_store_and_retrieve_result(self, mock_openai):
        """Test storing and retrieving benchmark results"""
        # Mock config manager
        self.config_manager.get_provider.return_value = self.openai_config

        # Mock provider
        mock_provider = Mock()
        mock_openai.return_value = mock_provider
        mock_provider.complete.return_value = LLMResponse(
            content="Test response",
            model="gpt-4o",
            usage=TokenUsage(input_tokens=10, output_tokens=20, total_tokens=30),
            cost=0.001,
            provider="openai"
        )

        # Run benchmark
        results = self.benchmarker.run_benchmark(
            prompt="Test prompt",
            task_type="general",
            providers=["openai"]
        )

        # Get comparison
        comparisons = self.benchmarker.get_comparison()
        self.assertEqual(len(comparisons), 1)

        comparison = comparisons[0]
        self.assertEqual(comparison.task_type, "general")
        self.assertEqual(comparison.prompt, "Test prompt")
        self.assertEqual(len(comparison.results), 1)
        self.assertEqual(comparison.fastest_provider, "openai")
        self.assertEqual(comparison.cheapest_provider, "openai")

    def test_set_quality_rating(self):
        """Test setting quality rating"""
        # Create a benchmark result manually
        result = BenchmarkResult(
            benchmark_id="test-123",
            provider="openai",
            model="gpt-4o",
            prompt="Test",
            task_type="general",
            response="Response",
            latency_ms=100.0,
            input_tokens=10,
            output_tokens=20,
            cost=0.001,
            quality_rating=None,
            timestamp="2026-01-12T00:00:00Z"
        )

        self.benchmarker._store_result(result)

        # Set rating
        self.benchmarker.set_quality_rating("test-123", 8.5)

        # Retrieve and verify
        import sqlite3
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT quality_rating FROM benchmarks WHERE benchmark_id = ?", ("test-123",))
        rating = cursor.fetchone()[0]
        conn.close()

        self.assertEqual(rating, 8.5)

    def test_set_quality_rating_invalid(self):
        """Test setting invalid quality rating"""
        with self.assertRaises(ValueError):
            self.benchmarker.set_quality_rating("test-123", -1)

        with self.assertRaises(ValueError):
            self.benchmarker.set_quality_rating("test-123", 11)

    @patch('lib.providers.openai_provider.OpenAIProvider')
    @patch('lib.providers.gemini_provider.GeminiProvider')
    def test_get_provider_stats(self, mock_gemini, mock_openai):
        """Test getting provider statistics"""
        # Mock config manager
        def get_provider_side_effect(name):
            if name == "openai":
                return self.openai_config
            elif name == "gemini":
                return self.gemini_config
            return None

        self.config_manager.get_provider.side_effect = get_provider_side_effect

        # Mock OpenAI provider
        mock_openai_instance = Mock()
        mock_openai.return_value = mock_openai_instance
        mock_openai_instance.complete.return_value = LLMResponse(
            content="OpenAI response",
            model="gpt-4o",
            usage=TokenUsage(input_tokens=10, output_tokens=20, total_tokens=30),
            cost=0.001,
            provider="openai"
        )

        # Mock Gemini provider
        mock_gemini_instance = Mock()
        mock_gemini.return_value = mock_gemini_instance
        mock_gemini_instance.complete.return_value = LLMResponse(
            content="Gemini response",
            model="gemini-2.0-flash",
            usage=TokenUsage(input_tokens=10, output_tokens=20, total_tokens=30),
            cost=0.0002,
            provider="gemini"
        )

        # Run benchmarks
        self.benchmarker.run_benchmark(
            prompt="Test prompt 1",
            task_type="general",
            providers=["openai", "gemini"]
        )

        self.benchmarker.run_benchmark(
            prompt="Test prompt 2",
            task_type="coding",
            providers=["openai"]
        )

        # Get stats for all providers
        stats = self.benchmarker.get_provider_stats()
        self.assertEqual(len(stats), 2)
        self.assertIn("openai", stats)
        self.assertIn("gemini", stats)

        # Check OpenAI stats
        openai_stats = stats["openai"]
        self.assertEqual(openai_stats["count"], 2)
        self.assertGreater(openai_stats["avg_latency_ms"], 0)
        self.assertEqual(openai_stats["avg_cost"], 0.001)
        self.assertEqual(openai_stats["success_rate"], 100.0)

        # Check Gemini stats
        gemini_stats = stats["gemini"]
        self.assertEqual(gemini_stats["count"], 1)
        self.assertEqual(gemini_stats["avg_cost"], 0.0002)

        # Get stats for specific provider
        openai_only_stats = self.benchmarker.get_provider_stats(provider="openai")
        self.assertEqual(len(openai_only_stats), 1)
        self.assertIn("openai", openai_only_stats)

    @patch('lib.providers.openai_provider.OpenAIProvider')
    def test_export_to_csv(self, mock_openai):
        """Test exporting results to CSV"""
        # Mock config manager
        self.config_manager.get_provider.return_value = self.openai_config

        # Mock provider
        mock_provider = Mock()
        mock_openai.return_value = mock_provider
        mock_provider.complete.return_value = LLMResponse(
            content="Test response",
            model="gpt-4o",
            usage=TokenUsage(input_tokens=10, output_tokens=20, total_tokens=30),
            cost=0.001,
            provider="openai"
        )

        # Run benchmark
        self.benchmarker.run_benchmark(
            prompt="Test prompt",
            task_type="general",
            providers=["openai"]
        )

        # Export to CSV
        output_path = os.path.join(self.temp_dir, "results.csv")
        self.benchmarker.export_to_csv(output_path)

        # Verify CSV file
        self.assertTrue(os.path.exists(output_path))

        import csv
        with open(output_path, 'r') as f:
            reader = csv.reader(f)
            rows = list(reader)

        self.assertEqual(len(rows), 2)  # Header + 1 result
        self.assertEqual(rows[0][0], "benchmark_id")
        self.assertEqual(rows[1][1], "openai")  # provider column

    @patch('lib.providers.openai_provider.OpenAIProvider')
    def test_export_to_json(self, mock_openai):
        """Test exporting results to JSON"""
        # Mock config manager
        self.config_manager.get_provider.return_value = self.openai_config

        # Mock provider
        mock_provider = Mock()
        mock_openai.return_value = mock_provider
        mock_provider.complete.return_value = LLMResponse(
            content="Test response",
            model="gpt-4o",
            usage=TokenUsage(input_tokens=10, output_tokens=20, total_tokens=30),
            cost=0.001,
            provider="openai"
        )

        # Run benchmark
        self.benchmarker.run_benchmark(
            prompt="Test prompt",
            task_type="general",
            providers=["openai"]
        )

        # Export to JSON
        output_path = os.path.join(self.temp_dir, "results.json")
        self.benchmarker.export_to_json(output_path)

        # Verify JSON file
        self.assertTrue(os.path.exists(output_path))

        with open(output_path, 'r') as f:
            data = json.load(f)

        self.assertEqual(data["task_type"], "all")
        self.assertEqual(len(data["comparisons"]), 1)
        self.assertEqual(data["comparisons"][0]["fastest_provider"], "openai")

    @patch('lib.providers.openai_provider.OpenAIProvider')
    def test_get_comparison_by_task_type(self, mock_openai):
        """Test getting comparisons filtered by task type"""
        # Mock config manager
        self.config_manager.get_provider.return_value = self.openai_config

        # Mock provider
        mock_provider = Mock()
        mock_openai.return_value = mock_provider
        mock_provider.complete.return_value = LLMResponse(
            content="Test response",
            model="gpt-4o",
            usage=TokenUsage(input_tokens=10, output_tokens=20, total_tokens=30),
            cost=0.001,
            provider="openai"
        )

        # Run benchmarks with different task types
        self.benchmarker.run_benchmark(
            prompt="Test prompt 1",
            task_type="general",
            providers=["openai"]
        )

        self.benchmarker.run_benchmark(
            prompt="Test prompt 2",
            task_type="coding",
            providers=["openai"]
        )

        # Get comparisons for specific task type
        general_comparisons = self.benchmarker.get_comparison(task_type="general")
        self.assertEqual(len(general_comparisons), 1)
        self.assertEqual(general_comparisons[0].task_type, "general")

        coding_comparisons = self.benchmarker.get_comparison(task_type="coding")
        self.assertEqual(len(coding_comparisons), 1)
        self.assertEqual(coding_comparisons[0].task_type, "coding")

        # Get all comparisons
        all_comparisons = self.benchmarker.get_comparison()
        self.assertEqual(len(all_comparisons), 2)

    @patch('lib.providers.openai_provider.OpenAIProvider')
    def test_benchmark_with_custom_parameters(self, mock_openai):
        """Test benchmark with custom temperature and max_tokens"""
        # Mock config manager
        self.config_manager.get_provider.return_value = self.openai_config

        # Mock provider
        mock_provider = Mock()
        mock_openai.return_value = mock_provider
        mock_provider.complete.return_value = LLMResponse(
            content="Test response",
            model="gpt-4o",
            usage=TokenUsage(input_tokens=10, output_tokens=20, total_tokens=30),
            cost=0.001,
            provider="openai"
        )

        # Run benchmark with custom parameters
        results = self.benchmarker.run_benchmark(
            prompt="Test prompt",
            task_type="general",
            providers=["openai"],
            temperature=0.5,
            max_tokens=1000
        )

        # Verify provider.complete was called with correct parameters
        mock_provider.complete.assert_called_once()
        call_kwargs = mock_provider.complete.call_args[1]
        self.assertEqual(call_kwargs["temperature"], 0.5)
        self.assertEqual(call_kwargs["max_tokens"], 1000)

    @patch('lib.providers.openai_provider.OpenAIProvider')
    def test_benchmark_all_providers(self, mock_openai):
        """Test benchmarking all enabled providers"""
        # Mock config manager to return multiple enabled providers
        self.config_manager.list_providers.return_value = [
            self.openai_config,
            self.gemini_config
        ]

        self.config_manager.get_provider.side_effect = lambda name: {
            "openai": self.openai_config,
            "gemini": self.gemini_config
        }.get(name)

        # Mock provider
        mock_provider = Mock()
        mock_openai.return_value = mock_provider
        mock_provider.complete.return_value = LLMResponse(
            content="Test response",
            model="gpt-4o",
            usage=TokenUsage(input_tokens=10, output_tokens=20, total_tokens=30),
            cost=0.001,
            provider="openai"
        )

        # Run benchmark with providers=None (should use all enabled)
        with patch('lib.providers.gemini_provider.GeminiProvider') as mock_gemini:
            mock_gemini_instance = Mock()
            mock_gemini.return_value = mock_gemini_instance
            mock_gemini_instance.complete.return_value = LLMResponse(
                content="Gemini response",
                model="gemini-2.0-flash",
                usage=TokenUsage(input_tokens=10, output_tokens=20, total_tokens=30),
                cost=0.0002,
                provider="gemini"
            )

            results = self.benchmarker.run_benchmark(
                prompt="Test prompt",
                task_type="general",
                providers=None  # Should use all enabled providers
            )

            # Should have benchmarked both providers
            self.assertEqual(len(results), 2)
            provider_names = [r.provider for r in results]
            self.assertIn("openai", provider_names)
            self.assertIn("gemini", provider_names)


if __name__ == "__main__":
    unittest.main()
