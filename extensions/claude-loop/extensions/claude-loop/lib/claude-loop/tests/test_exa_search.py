#!/usr/bin/env python3
"""
Tests for Exa.ai Search Integration

Comprehensive tests for ExaSearchClient including:
- Search methods (general, academic, news)
- Content extraction
- Rate limiting
- Caching
- Retry logic
- Error handling

Uses mocked API responses to avoid real API calls.
"""

import os
import sys
import json
import time
import unittest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta
import threading

# Add lib to path
lib_path = os.path.join(os.path.dirname(__file__), "..", "lib")
sys.path.insert(0, lib_path)

# Import with explicit path handling
import importlib.util

spec = importlib.util.spec_from_file_location(
    "exa_search",
    os.path.join(lib_path, "exa_search.py")
)
exa_search = importlib.util.module_from_spec(spec)
spec.loader.exec_module(exa_search)

SearchResult = exa_search.SearchResult
DocumentContent = exa_search.DocumentContent
ExaSearchClient = exa_search.ExaSearchClient
ExaSearchError = exa_search.ExaSearchError
RateLimiter = exa_search.RateLimiter
ResultCache = exa_search.ResultCache


class TestSearchResult(unittest.TestCase):
    """Test SearchResult dataclass."""

    def test_create_search_result(self):
        """Test creating SearchResult with all fields."""
        result = SearchResult(
            title="Test Title",
            url="https://example.com/test",
            snippet="This is a test snippet",
            score=0.95,
            published_date="2026-01-15",
            author="Test Author",
            highlights=["highlight 1", "highlight 2"],
            source="exa"
        )

        self.assertEqual(result.title, "Test Title")
        self.assertEqual(result.url, "https://example.com/test")
        self.assertEqual(result.snippet, "This is a test snippet")
        self.assertEqual(result.score, 0.95)
        self.assertEqual(result.published_date, "2026-01-15")
        self.assertEqual(result.author, "Test Author")
        self.assertEqual(result.highlights, ["highlight 1", "highlight 2"])
        self.assertEqual(result.source, "exa")

    def test_search_result_optional_fields(self):
        """Test SearchResult with only required fields."""
        result = SearchResult(
            title="Title",
            url="https://example.com",
            snippet="Snippet",
            score=0.8
        )

        self.assertIsNone(result.published_date)
        self.assertIsNone(result.author)
        self.assertEqual(result.highlights, [])
        self.assertEqual(result.source, "exa")

    def test_search_result_to_dict(self):
        """Test converting SearchResult to dictionary."""
        result = SearchResult(
            title="Test",
            url="https://example.com",
            snippet="Snippet",
            score=0.9,
            author="Author"
        )

        data = result.to_dict()

        self.assertEqual(data["title"], "Test")
        self.assertEqual(data["url"], "https://example.com")
        self.assertEqual(data["snippet"], "Snippet")
        self.assertEqual(data["score"], 0.9)
        self.assertEqual(data["author"], "Author")
        self.assertEqual(data["source"], "exa")

    def test_search_result_from_dict(self):
        """Test creating SearchResult from dictionary."""
        data = {
            "title": "Test",
            "url": "https://example.com",
            "snippet": "Snippet",
            "score": 0.85,
            "published_date": "2026-01-01",
            "author": "Test Author",
            "highlights": ["h1", "h2"],
            "source": "exa"
        }

        result = SearchResult.from_dict(data)

        self.assertEqual(result.title, "Test")
        self.assertEqual(result.url, "https://example.com")
        self.assertEqual(result.score, 0.85)
        self.assertEqual(result.author, "Test Author")


class TestDocumentContent(unittest.TestCase):
    """Test DocumentContent dataclass."""

    def test_create_document_content(self):
        """Test creating DocumentContent."""
        content = DocumentContent(
            url="https://example.com/article",
            title="Test Article",
            text="This is the article content.",
            author="John Doe",
            published_date="2026-01-10"
        )

        self.assertEqual(content.url, "https://example.com/article")
        self.assertEqual(content.title, "Test Article")
        self.assertEqual(content.text, "This is the article content.")
        self.assertEqual(content.author, "John Doe")
        self.assertEqual(content.published_date, "2026-01-10")

    def test_document_content_to_dict(self):
        """Test converting DocumentContent to dictionary."""
        content = DocumentContent(
            url="https://example.com",
            title="Title",
            text="Text content"
        )

        data = content.to_dict()

        self.assertEqual(data["url"], "https://example.com")
        self.assertEqual(data["title"], "Title")
        self.assertEqual(data["text"], "Text content")
        self.assertIsNone(data["author"])

    def test_document_content_from_dict(self):
        """Test creating DocumentContent from dictionary."""
        data = {
            "url": "https://example.com",
            "title": "Article",
            "text": "Content text",
            "author": "Author Name"
        }

        content = DocumentContent.from_dict(data)

        self.assertEqual(content.url, "https://example.com")
        self.assertEqual(content.title, "Article")
        self.assertEqual(content.author, "Author Name")


class TestRateLimiter(unittest.TestCase):
    """Test RateLimiter class."""

    def test_rate_limiter_initialization(self):
        """Test rate limiter initialization."""
        limiter = RateLimiter(rate=5.0)
        self.assertEqual(limiter.rate, 5.0)

    def test_acquire_within_limit(self):
        """Test acquiring tokens within rate limit."""
        limiter = RateLimiter(rate=10.0)

        # First acquisition should be instant
        wait_time = limiter.acquire()
        self.assertEqual(wait_time, 0.0)

    def test_acquire_token_refill(self):
        """Test token refill after time passes."""
        limiter = RateLimiter(rate=10.0)

        # Exhaust all tokens
        for _ in range(10):
            limiter.acquire()

        # Wait for tokens to refill
        time.sleep(0.2)

        # Should have some tokens now
        wait_time = limiter.acquire()
        # May need small wait or none
        self.assertLessEqual(wait_time, 0.1)

    def test_wait_method(self):
        """Test wait method blocks appropriately."""
        limiter = RateLimiter(rate=100.0)  # High rate for fast testing

        start = time.monotonic()
        limiter.wait()
        elapsed = time.monotonic() - start

        # Should complete quickly
        self.assertLess(elapsed, 0.1)

    def test_thread_safety(self):
        """Test rate limiter is thread-safe."""
        limiter = RateLimiter(rate=100.0)
        acquired = []

        def acquire_token():
            wait_time = limiter.acquire()
            acquired.append(wait_time)

        threads = [threading.Thread(target=acquire_token) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # All threads should complete
        self.assertEqual(len(acquired), 10)


class TestResultCache(unittest.TestCase):
    """Test ResultCache class."""

    def setUp(self):
        """Create cache instance for each test."""
        self.cache = ResultCache(ttl_seconds=60, max_entries=100)

    def test_cache_miss(self):
        """Test cache miss for non-existent entry."""
        result = self.cache.get("search", "nonexistent query")
        self.assertIsNone(result)

        stats = self.cache.get_stats()
        self.assertEqual(stats["misses"], 1)
        self.assertEqual(stats["hits"], 0)

    def test_cache_hit(self):
        """Test cache hit for stored entry."""
        test_data = [{"title": "Test", "url": "https://example.com"}]

        self.cache.set("search", "test query", test_data)
        cached = self.cache.get("search", "test query")

        self.assertEqual(cached, test_data)

        stats = self.cache.get_stats()
        self.assertEqual(stats["hits"], 1)

    def test_cache_key_normalization(self):
        """Test cache key normalization (case-insensitive)."""
        test_data = [{"title": "Test"}]

        self.cache.set("search", "Test Query", test_data)

        # Should match despite different case
        cached1 = self.cache.get("search", "test query")
        cached2 = self.cache.get("search", "  TEST QUERY  ")

        self.assertEqual(cached1, test_data)
        self.assertEqual(cached2, test_data)

    def test_cache_with_params(self):
        """Test cache differentiation by parameters."""
        test_data1 = [{"title": "Result 1"}]
        test_data2 = [{"title": "Result 2"}]

        self.cache.set("search", "query", test_data1, params={"num_results": 5})
        self.cache.set("search", "query", test_data2, params={"num_results": 10})

        cached1 = self.cache.get("search", "query", params={"num_results": 5})
        cached2 = self.cache.get("search", "query", params={"num_results": 10})

        self.assertEqual(cached1, test_data1)
        self.assertEqual(cached2, test_data2)

    def test_cache_expiration(self):
        """Test cache entry expiration."""
        # Create cache with very short TTL
        short_cache = ResultCache(ttl_seconds=0.1, max_entries=100)

        test_data = [{"title": "Test"}]
        short_cache.set("search", "query", test_data)

        # Wait for expiration
        time.sleep(0.15)

        cached = short_cache.get("search", "query")
        self.assertIsNone(cached)

    def test_cache_max_entries_eviction(self):
        """Test LRU eviction when max entries reached."""
        small_cache = ResultCache(ttl_seconds=3600, max_entries=3)

        small_cache.set("search", "query1", [{"title": "1"}])
        small_cache.set("search", "query2", [{"title": "2"}])
        small_cache.set("search", "query3", [{"title": "3"}])

        # Adding 4th entry should evict oldest
        small_cache.set("search", "query4", [{"title": "4"}])

        stats = small_cache.get_stats()
        self.assertLessEqual(stats["entry_count"], 3)

    def test_cache_clear(self):
        """Test clearing cache."""
        self.cache.set("search", "query1", [{"title": "1"}])
        self.cache.set("search", "query2", [{"title": "2"}])

        self.cache.clear()

        stats = self.cache.get_stats()
        self.assertEqual(stats["entry_count"], 0)
        self.assertEqual(stats["hits"], 0)
        self.assertEqual(stats["misses"], 0)

    def test_cache_stats(self):
        """Test cache statistics."""
        self.cache.set("search", "query1", [{"title": "1"}])
        self.cache.get("search", "query1")  # Hit
        self.cache.get("search", "query2")  # Miss

        stats = self.cache.get_stats()

        self.assertEqual(stats["hits"], 1)
        self.assertEqual(stats["misses"], 1)
        self.assertAlmostEqual(stats["hit_rate"], 0.5, places=1)
        self.assertEqual(stats["entry_count"], 1)


class TestExaSearchClient(unittest.TestCase):
    """Test ExaSearchClient class."""

    def setUp(self):
        """Create client instance for each test."""
        self.client = ExaSearchClient(api_key="test-api-key")

    def test_is_available_with_api_key(self):
        """Test client is available with API key."""
        self.assertTrue(self.client.is_available())

    def test_is_available_without_api_key(self):
        """Test client is not available without API key."""
        with patch.dict(os.environ, {}, clear=True):
            client = ExaSearchClient(api_key=None)
            self.assertFalse(client.is_available())

    @patch('requests.Session.post')
    def test_search_success(self, mock_post):
        """Test successful search."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "results": [
                {
                    "title": "Result 1",
                    "url": "https://example.com/1",
                    "text": "This is the first result content",
                    "score": 0.95,
                    "publishedDate": "2026-01-15",
                    "author": "Author 1",
                    "highlights": ["highlight one", "highlight two"]
                },
                {
                    "title": "Result 2",
                    "url": "https://example.com/2",
                    "text": "This is the second result content",
                    "score": 0.85,
                    "highlights": []
                }
            ]
        }
        mock_post.return_value = mock_response

        results = self.client.search("test query", num_results=2)

        self.assertEqual(len(results), 2)
        self.assertEqual(results[0].title, "Result 1")
        self.assertEqual(results[0].url, "https://example.com/1")
        self.assertEqual(results[0].score, 0.95)
        self.assertEqual(results[0].published_date, "2026-01-15")
        self.assertEqual(results[0].author, "Author 1")
        self.assertEqual(results[0].source, "exa")

        # Check that neural search was used
        call_args = mock_post.call_args
        payload = call_args[1]["json"]
        self.assertEqual(payload["type"], "neural")
        self.assertEqual(payload["query"], "test query")

    @patch('requests.Session.post')
    def test_search_academic(self, mock_post):
        """Test academic search with domain filtering."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "results": [
                {
                    "title": "Research Paper",
                    "url": "https://arxiv.org/abs/1234.5678",
                    "text": "Abstract of the research paper",
                    "score": 0.92,
                    "publishedDate": "2026-01-10",
                    "author": "Researcher Name"
                }
            ]
        }
        mock_post.return_value = mock_response

        results = self.client.search_academic(
            "machine learning optimization",
            num_results=5
        )

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].title, "Research Paper")
        self.assertIn("arxiv.org", results[0].url)

        # Check that academic domains were included
        call_args = mock_post.call_args
        payload = call_args[1]["json"]
        self.assertIn("includeDomains", payload)
        self.assertIn("arxiv.org", payload["includeDomains"])

    @patch('requests.Session.post')
    def test_search_academic_with_date_filter(self, mock_post):
        """Test academic search with date filtering."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"results": []}
        mock_post.return_value = mock_response

        self.client.search_academic(
            "quantum computing",
            start_published_date="2025-01-01",
            end_published_date="2026-01-01"
        )

        call_args = mock_post.call_args
        payload = call_args[1]["json"]
        self.assertEqual(payload["startPublishedDate"], "2025-01-01")
        self.assertEqual(payload["endPublishedDate"], "2026-01-01")

    @patch('requests.Session.post')
    def test_search_news(self, mock_post):
        """Test news search with date range."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "results": [
                {
                    "title": "Breaking News",
                    "url": "https://reuters.com/article/1",
                    "text": "News article content",
                    "score": 0.88,
                    "publishedDate": "2026-01-17"
                }
            ]
        }
        mock_post.return_value = mock_response

        results = self.client.search_news("technology news", days_back=3)

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].title, "Breaking News")

        # Check that date range was set correctly
        call_args = mock_post.call_args
        payload = call_args[1]["json"]
        self.assertIn("startPublishedDate", payload)
        self.assertIn("endPublishedDate", payload)
        self.assertIn("includeDomains", payload)
        self.assertIn("reuters.com", payload["includeDomains"])

    @patch('requests.Session.post')
    def test_get_contents(self, mock_post):
        """Test content extraction from URLs."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "results": [
                {
                    "url": "https://example.com/article1",
                    "title": "Article 1",
                    "text": "Full article text content here",
                    "author": "Author Name",
                    "publishedDate": "2026-01-12"
                },
                {
                    "url": "https://example.com/article2",
                    "title": "Article 2",
                    "text": "Another article content",
                    "author": None
                }
            ]
        }
        mock_post.return_value = mock_response

        contents = self.client.get_contents([
            "https://example.com/article1",
            "https://example.com/article2"
        ])

        self.assertEqual(len(contents), 2)
        self.assertEqual(contents[0].title, "Article 1")
        self.assertEqual(contents[0].text, "Full article text content here")
        self.assertEqual(contents[0].author, "Author Name")
        self.assertEqual(contents[1].title, "Article 2")
        self.assertIsNone(contents[1].author)

    def test_get_contents_empty_urls(self):
        """Test get_contents with empty URL list."""
        contents = self.client.get_contents([])
        self.assertEqual(contents, [])

    @patch('requests.Session.post')
    def test_caching(self, mock_post):
        """Test that results are cached and reused."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "results": [{"title": "Result", "url": "https://example.com", "score": 0.9}]
        }
        mock_post.return_value = mock_response

        # First call - should hit API
        results1 = self.client.search("cached query")
        self.assertEqual(mock_post.call_count, 1)

        # Second call - should use cache
        results2 = self.client.search("cached query")
        self.assertEqual(mock_post.call_count, 1)  # Still 1, no new API call

        # Results should be equal
        self.assertEqual(results1[0].title, results2[0].title)

        # Cache stats should show hit
        stats = self.client.get_cache_stats()
        self.assertEqual(stats["hits"], 1)

    @patch('requests.Session.post')
    def test_retry_on_server_error(self, mock_post):
        """Test retry logic on server errors."""
        # First call fails, second succeeds
        mock_response_fail = Mock()
        mock_response_fail.status_code = 500

        mock_response_success = Mock()
        mock_response_success.status_code = 200
        mock_response_success.json.return_value = {
            "results": [{"title": "Result", "url": "https://example.com", "score": 0.9}]
        }

        mock_post.side_effect = [mock_response_fail, mock_response_success]

        # Create client with fast retry for testing
        client = ExaSearchClient(api_key="test-key", max_retries=3)

        # Patch sleep to avoid waiting
        with patch('time.sleep'):
            results = client.search("retry test")

        self.assertEqual(len(results), 1)
        self.assertEqual(mock_post.call_count, 2)

    @patch('requests.Session.post')
    def test_retry_on_rate_limit(self, mock_post):
        """Test retry on rate limit (429) response."""
        mock_response_429 = Mock()
        mock_response_429.status_code = 429
        mock_response_429.headers = {"Retry-After": "1"}

        mock_response_success = Mock()
        mock_response_success.status_code = 200
        mock_response_success.json.return_value = {"results": []}

        mock_post.side_effect = [mock_response_429, mock_response_success]

        client = ExaSearchClient(api_key="test-key", max_retries=3)

        with patch('time.sleep'):
            results = client.search("rate limit test")

        self.assertEqual(results, [])
        self.assertEqual(mock_post.call_count, 2)

    @patch('requests.Session.post')
    def test_client_error_no_retry(self, mock_post):
        """Test that client errors (4xx) don't retry."""
        mock_response = Mock()
        mock_response.status_code = 400
        mock_response.text = "Bad request"
        mock_response.json.return_value = {"error": "Invalid query"}
        mock_post.return_value = mock_response

        with self.assertRaises(ExaSearchError) as cm:
            self.client.search("bad query")

        self.assertIn("400", str(cm.exception))
        self.assertEqual(mock_post.call_count, 1)  # No retry

    @patch('requests.Session.post')
    def test_timeout_retry(self, mock_post):
        """Test retry on timeout."""
        import requests

        mock_response_success = Mock()
        mock_response_success.status_code = 200
        mock_response_success.json.return_value = {"results": []}

        mock_post.side_effect = [
            requests.exceptions.Timeout("timeout"),
            mock_response_success
        ]

        client = ExaSearchClient(api_key="test-key", max_retries=3)

        with patch('time.sleep'):
            results = client.search("timeout test")

        self.assertEqual(results, [])
        self.assertEqual(mock_post.call_count, 2)

    @patch('requests.Session.post')
    def test_max_retries_exceeded(self, mock_post):
        """Test error when max retries exceeded."""
        mock_response = Mock()
        mock_response.status_code = 500
        mock_post.return_value = mock_response

        client = ExaSearchClient(api_key="test-key", max_retries=2)

        with patch('time.sleep'):
            with self.assertRaises(ExaSearchError) as cm:
                client.search("failing query")

        self.assertIn("retries", str(cm.exception).lower())
        self.assertEqual(mock_post.call_count, 2)

    def test_search_without_api_key(self):
        """Test search fails without API key."""
        with patch.dict(os.environ, {}, clear=True):
            client = ExaSearchClient(api_key=None)
            with self.assertRaises(ExaSearchError) as cm:
                client.search("test")

        self.assertIn("EXA_API_KEY", str(cm.exception))

    def test_clear_cache(self):
        """Test clearing the client cache."""
        # Add something to cache
        self.client.cache.set("search", "query", [{"title": "Test"}])

        stats_before = self.client.get_cache_stats()
        self.assertEqual(stats_before["entry_count"], 1)

        self.client.clear_cache()

        stats_after = self.client.get_cache_stats()
        self.assertEqual(stats_after["entry_count"], 0)

    @patch('requests.Session.post')
    def test_parse_results_with_missing_fields(self, mock_post):
        """Test parsing results with missing optional fields."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "results": [
                {
                    "url": "https://example.com",
                    # Missing title, text, score, etc.
                }
            ]
        }
        mock_post.return_value = mock_response

        results = self.client.search("sparse results")

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].url, "https://example.com")
        self.assertEqual(results[0].title, "")
        self.assertEqual(results[0].score, 0.0)


class TestExaSearchIntegration(unittest.TestCase):
    """Integration tests for ExaSearchClient."""

    @patch('requests.Session.post')
    def test_full_research_workflow(self, mock_post):
        """Test a complete research workflow: search -> get contents."""
        # Mock search response
        mock_search_response = Mock()
        mock_search_response.status_code = 200
        mock_search_response.json.return_value = {
            "results": [
                {
                    "title": "AI Research Paper",
                    "url": "https://arxiv.org/abs/2026.12345",
                    "text": "Abstract about AI",
                    "score": 0.95
                }
            ]
        }

        # Mock contents response
        mock_contents_response = Mock()
        mock_contents_response.status_code = 200
        mock_contents_response.json.return_value = {
            "results": [
                {
                    "url": "https://arxiv.org/abs/2026.12345",
                    "title": "AI Research Paper",
                    "text": "Full paper content..."
                }
            ]
        }

        mock_post.side_effect = [mock_search_response, mock_contents_response]

        client = ExaSearchClient(api_key="test-key")

        # Step 1: Search for papers
        results = client.search_academic("artificial intelligence")
        self.assertEqual(len(results), 1)

        # Step 2: Get full content
        urls = [r.url for r in results]
        contents = client.get_contents(urls)
        self.assertEqual(len(contents), 1)
        self.assertIn("Full paper content", contents[0].text)

    @patch('requests.Session.post')
    def test_mixed_cache_and_api_calls(self, mock_post):
        """Test mixed cached and fresh API calls."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "results": [{"title": "Result", "url": "https://example.com", "score": 0.9}]
        }
        mock_post.return_value = mock_response

        client = ExaSearchClient(api_key="test-key")

        # First query - API call
        client.search("query 1")
        self.assertEqual(mock_post.call_count, 1)

        # Same query - cached
        client.search("query 1")
        self.assertEqual(mock_post.call_count, 1)

        # Different query - API call
        client.search("query 2")
        self.assertEqual(mock_post.call_count, 2)

        # First query again - still cached
        client.search("query 1")
        self.assertEqual(mock_post.call_count, 2)


def run_tests():
    """Run all tests."""
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromModule(sys.modules[__name__])
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(run_tests())
