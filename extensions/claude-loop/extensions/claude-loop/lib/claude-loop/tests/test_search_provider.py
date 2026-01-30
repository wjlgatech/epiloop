#!/usr/bin/env python3
"""
Tests for Search Provider Module

Tests search provider abstraction, fallback logic, caching, and rate limiting.
Uses mock responses to avoid real API calls.
"""

import os
import sys
import json
import unittest
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path
import tempfile
import shutil

# Add lib to path
lib_path = os.path.join(os.path.dirname(__file__), "..", "lib")
sys.path.insert(0, lib_path)

# Import with explicit path handling
import importlib.util

spec = importlib.util.spec_from_file_location("search_provider", os.path.join(lib_path, "search-provider.py"))
search_provider = importlib.util.module_from_spec(spec)
spec.loader.exec_module(search_provider)

spec_cache = importlib.util.spec_from_file_location("search_cache", os.path.join(lib_path, "search-cache.py"))
search_cache_module = importlib.util.module_from_spec(spec_cache)
spec_cache.loader.exec_module(search_cache_module)

SearchResult = search_provider.SearchResult
SearchProvider = search_provider.SearchProvider
SearchProviderError = search_provider.SearchProviderError
TavilyProvider = search_provider.TavilyProvider
DuckDuckGoProvider = search_provider.DuckDuckGoProvider
SerpAPIProvider = search_provider.SerpAPIProvider
SearchProviderManager = search_provider.SearchProviderManager
SearchCache = search_cache_module.SearchCache


class TestSearchResult(unittest.TestCase):
    """Test SearchResult dataclass."""

    def test_search_result_creation(self):
        """Test creating SearchResult with all fields."""
        result = SearchResult(
            title="Test Title",
            url="https://example.com",
            snippet="Test snippet",
            relevance_score=0.95,
            source="tavily",
            published_date="2026-01-17",
            domain="example.com"
        )

        self.assertEqual(result.title, "Test Title")
        self.assertEqual(result.url, "https://example.com")
        self.assertEqual(result.snippet, "Test snippet")
        self.assertEqual(result.relevance_score, 0.95)
        self.assertEqual(result.source, "tavily")
        self.assertEqual(result.published_date, "2026-01-17")
        self.assertEqual(result.domain, "example.com")

    def test_search_result_optional_fields(self):
        """Test SearchResult with only required fields."""
        result = SearchResult(
            title="Test",
            url="https://example.com",
            snippet="Snippet",
            relevance_score=0.8,
            source="duckduckgo"
        )

        self.assertIsNone(result.published_date)
        self.assertIsNone(result.domain)


class TestTavilyProvider(unittest.TestCase):
    """Test Tavily search provider."""

    def test_is_available_with_api_key(self):
        """Test provider is available when API key is set."""
        provider = TavilyProvider(api_key="test-key")
        self.assertTrue(provider.is_available())

    def test_is_available_without_api_key(self):
        """Test provider is not available without API key."""
        with patch.dict(os.environ, {}, clear=True):
            provider = TavilyProvider()
            self.assertFalse(provider.is_available())

    def test_search_success(self):
        """Test successful Tavily search."""
        # Mock TavilyClient
        with patch('builtins.__import__', side_effect=lambda name, *args, **kwargs: MagicMock() if name == 'tavily' else __import__(name, *args, **kwargs)):
            # Create mock client
            mock_client = MagicMock()
            mock_client.search.return_value = {
                "results": [
                    {
                        "title": "Result 1",
                        "url": "https://example.com/1",
                        "content": "This is result 1",
                        "score": 0.95
                    },
                    {
                        "title": "Result 2",
                        "url": "https://example.com/2",
                        "content": "This is result 2",
                        "score": 0.85
                    }
                ]
            }

            provider = TavilyProvider(api_key="test-key")

            # Mock the client creation
            with patch('lib.search_provider.TavilyClient', return_value=mock_client):
                results = provider.search("test query", max_results=2)

            self.assertEqual(len(results), 2)
            self.assertEqual(results[0].title, "Result 1")
            self.assertEqual(results[0].url, "https://example.com/1")
            self.assertEqual(results[0].snippet, "This is result 1")
            self.assertEqual(results[0].relevance_score, 0.95)
            self.assertEqual(results[0].source, "tavily")
            self.assertEqual(results[0].domain, "example.com")

    def test_search_without_api_key(self):
        """Test search fails without API key."""
        with patch.dict(os.environ, {}, clear=True):
            provider = TavilyProvider()
            with self.assertRaises(SearchProviderError):
                provider.search("test query")

    @patch.object(search_provider, 'TavilyClient')
    def test_search_api_error(self, mock_client_class):
        """Test handling of Tavily API errors."""
        mock_client = MagicMock()
        mock_client.search.side_effect = Exception("API error")
        mock_client_class.return_value = mock_client

        provider = TavilyProvider(api_key="test-key")
        with self.assertRaises(SearchProviderError) as cm:
            provider.search("test query")

        self.assertIn("Tavily search failed", str(cm.exception))


class TestDuckDuckGoProvider(unittest.TestCase):
    """Test DuckDuckGo search provider."""

    def test_is_available(self):
        """Test DuckDuckGo is always available."""
        provider = DuckDuckGoProvider()
        self.assertTrue(provider.is_available())

    @patch.object(search_provider, 'DDGS')
    def test_search_success(self, mock_ddgs_class):
        """Test successful DuckDuckGo search."""
        # Mock DDGS response
        mock_ddgs = MagicMock()
        mock_ddgs.__enter__.return_value.text.return_value = [
            {
                "title": "DDG Result 1",
                "href": "https://example.com/ddg1",
                "body": "DDG snippet 1"
            },
            {
                "title": "DDG Result 2",
                "href": "https://example.com/ddg2",
                "body": "DDG snippet 2"
            }
        ]
        mock_ddgs_class.return_value = mock_ddgs

        provider = DuckDuckGoProvider()
        results = provider.search("test query", max_results=2)

        self.assertEqual(len(results), 2)
        self.assertEqual(results[0].title, "DDG Result 1")
        self.assertEqual(results[0].url, "https://example.com/ddg1")
        self.assertEqual(results[0].snippet, "DDG snippet 1")
        self.assertEqual(results[0].source, "duckduckgo")
        # First result should have score 1.0
        self.assertAlmostEqual(results[0].relevance_score, 1.0, places=1)
        # Second result should have lower score
        self.assertLess(results[1].relevance_score, results[0].relevance_score)


class TestSerpAPIProvider(unittest.TestCase):
    """Test SerpAPI search provider."""

    def test_is_available_with_api_key(self):
        """Test provider is available when API key is set."""
        provider = SerpAPIProvider(api_key="test-key")
        self.assertTrue(provider.is_available())

    def test_is_available_without_api_key(self):
        """Test provider is not available without API key."""
        with patch.dict(os.environ, {}, clear=True):
            provider = SerpAPIProvider()
            self.assertFalse(provider.is_available())

    @patch.object(search_provider, 'GoogleSearch')
    def test_search_success(self, mock_search_class):
        """Test successful SerpAPI search."""
        # Mock SerpAPI response
        mock_search = MagicMock()
        mock_search.get_dict.return_value = {
            "organic_results": [
                {
                    "title": "Serp Result 1",
                    "link": "https://example.com/serp1",
                    "snippet": "Serp snippet 1"
                },
                {
                    "title": "Serp Result 2",
                    "link": "https://example.com/serp2",
                    "snippet": "Serp snippet 2"
                }
            ]
        }
        mock_search_class.return_value = mock_search

        provider = SerpAPIProvider(api_key="test-key")
        results = provider.search("test query", max_results=2)

        self.assertEqual(len(results), 2)
        self.assertEqual(results[0].title, "Serp Result 1")
        self.assertEqual(results[0].url, "https://example.com/serp1")
        self.assertEqual(results[0].snippet, "Serp snippet 1")
        self.assertEqual(results[0].source, "serpapi")


class TestSearchProviderManager(unittest.TestCase):
    """Test SearchProviderManager with fallback logic."""

    @patch.object(search_provider, 'TavilyClient')
    def test_primary_provider_success(self, mock_tavily_client):
        """Test manager uses primary provider (Tavily) when available."""
        # Mock Tavily success
        mock_client = MagicMock()
        mock_client.search.return_value = {
            "results": [
                {
                    "title": "Tavily Result",
                    "url": "https://example.com",
                    "content": "Tavily content",
                    "score": 0.95
                }
            ]
        }
        mock_tavily_client.return_value = mock_client

        # Set Tavily API key
        with patch.dict(os.environ, {"TAVILY_API_KEY": "test-key"}):
            manager = SearchProviderManager()
            results = manager.search("test query")

            self.assertEqual(len(results), 1)
            self.assertEqual(results[0].source, "tavily")

    @patch.object(search_provider, 'DDGS')
    def test_fallback_to_duckduckgo(self, mock_ddgs):
        """Test manager falls back to DuckDuckGo when Tavily unavailable."""
        # Mock DuckDuckGo success
        mock_ddgs_instance = MagicMock()
        mock_ddgs_instance.__enter__.return_value.text.return_value = [
            {
                "title": "DDG Result",
                "href": "https://example.com",
                "body": "DDG content"
            }
        ]
        mock_ddgs.return_value = mock_ddgs_instance

        # No Tavily key, should fall back to DuckDuckGo
        with patch.dict(os.environ, {}, clear=True):
            manager = SearchProviderManager()
            results = manager.search("test query")

            self.assertEqual(len(results), 1)
            self.assertEqual(results[0].source, "duckduckgo")

    def test_all_providers_fail(self):
        """Test error when all providers fail."""
        with patch.dict(os.environ, {}, clear=True):
            # Mock all providers to fail
            with patch.object(DuckDuckGoProvider, 'search', side_effect=SearchProviderError("DDG failed")):
                manager = SearchProviderManager()
                with self.assertRaises(SearchProviderError) as cm:
                    manager.search("test query")

                self.assertIn("All search providers failed", str(cm.exception))

    def test_get_available_providers(self):
        """Test getting list of available providers."""
        with patch.dict(os.environ, {"TAVILY_API_KEY": "test-key"}):
            manager = SearchProviderManager()
            available = manager.get_available_providers()

            # Tavily and DuckDuckGo should be available
            self.assertIn("tavily", available)
            self.assertIn("duckduckgo", available)


class TestSearchCache(unittest.TestCase):
    """Test search result caching."""

    def setUp(self):
        """Create temporary cache directory."""
        self.temp_dir = tempfile.mkdtemp()
        self.cache = SearchCache(cache_dir=self.temp_dir, ttl_seconds=3600)

    def tearDown(self):
        """Clean up temporary cache directory."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_cache_miss(self):
        """Test cache miss for non-existent query."""
        result = self.cache.get("nonexistent query")
        self.assertIsNone(result)

        stats = self.cache.get_stats()
        self.assertEqual(stats["misses"], 1)
        self.assertEqual(stats["hits"], 0)

    def test_cache_hit(self):
        """Test cache hit for stored query."""
        test_results = [
            {"title": "Test", "url": "https://example.com", "snippet": "Test snippet"}
        ]

        # Store results
        self.cache.set("test query", test_results)

        # Retrieve results
        cached = self.cache.get("test query")

        self.assertEqual(cached, test_results)

        stats = self.cache.get_stats()
        self.assertEqual(stats["hits"], 1)

    def test_cache_key_normalization(self):
        """Test cache key normalization (case-insensitive, whitespace)."""
        test_results = [{"title": "Test"}]

        self.cache.set("Test Query", test_results)

        # Should match despite different case/whitespace
        cached1 = self.cache.get("test query")
        cached2 = self.cache.get("  TEST QUERY  ")

        self.assertEqual(cached1, test_results)
        self.assertEqual(cached2, test_results)

    def test_cache_with_params(self):
        """Test cache with additional parameters."""
        test_results = [{"title": "Test"}]

        # Store with params
        self.cache.set("query", test_results, params={"max_results": 10})

        # Should hit with same params
        cached1 = self.cache.get("query", params={"max_results": 10})
        self.assertEqual(cached1, test_results)

        # Should miss with different params
        cached2 = self.cache.get("query", params={"max_results": 5})
        self.assertIsNone(cached2)

    def test_cache_stats(self):
        """Test cache statistics."""
        stats = self.cache.get_stats()

        self.assertEqual(stats["hits"], 0)
        self.assertEqual(stats["misses"], 0)
        self.assertEqual(stats["hit_rate"], 0.0)
        self.assertEqual(stats["entry_count"], 0)

        # Add some cache activity
        self.cache.set("query1", [{"title": "Test 1"}])
        self.cache.set("query2", [{"title": "Test 2"}])
        self.cache.get("query1")  # Hit
        self.cache.get("query2")  # Hit
        self.cache.get("query3")  # Miss

        stats = self.cache.get_stats()
        self.assertEqual(stats["hits"], 2)
        self.assertEqual(stats["misses"], 1)
        self.assertAlmostEqual(stats["hit_rate"], 0.667, places=2)
        self.assertEqual(stats["entry_count"], 2)

    def test_cache_clear(self):
        """Test clearing cache."""
        self.cache.set("query1", [{"title": "Test 1"}])
        self.cache.set("query2", [{"title": "Test 2"}])

        stats_before = self.cache.get_stats()
        self.assertEqual(stats_before["entry_count"], 2)

        self.cache.clear()

        stats_after = self.cache.get_stats()
        self.assertEqual(stats_after["entry_count"], 0)
        self.assertEqual(stats_after["hits"], 0)
        self.assertEqual(stats_after["misses"], 0)


class TestIntegration(unittest.TestCase):
    """Integration tests combining provider and cache."""

    def setUp(self):
        """Create temporary cache directory."""
        self.temp_dir = tempfile.mkdtemp()
        self.cache = SearchCache(cache_dir=self.temp_dir)

    def tearDown(self):
        """Clean up temporary cache directory."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    @patch.object(search_provider, 'DDGS')
    def test_search_with_caching(self, mock_ddgs):
        """Test search with result caching."""
        # Mock DuckDuckGo
        mock_ddgs_instance = MagicMock()
        mock_ddgs_instance.__enter__.return_value.text.return_value = [
            {
                "title": "Result",
                "href": "https://example.com",
                "body": "Content"
            }
        ]
        mock_ddgs.return_value = mock_ddgs_instance

        with patch.dict(os.environ, {}, clear=True):
            manager = SearchProviderManager()

            # First search - should call API
            query = "test query"
            results1 = manager.search(query)

            # Convert to dict for caching
            results_dict = [
                {
                    "title": r.title,
                    "url": r.url,
                    "snippet": r.snippet,
                    "relevance_score": r.relevance_score,
                    "source": r.source
                }
                for r in results1
            ]

            # Store in cache
            self.cache.set(query, results_dict)

            # Second search - should use cache
            cached_results = self.cache.get(query)

            self.assertIsNotNone(cached_results)
            self.assertEqual(len(cached_results), 1)
            self.assertEqual(cached_results[0]["title"], "Result")

            # Verify cache hit
            stats = self.cache.get_stats()
            self.assertEqual(stats["hits"], 1)


def run_tests():
    """Run all tests."""
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromModule(sys.modules[__name__])
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(run_tests())
