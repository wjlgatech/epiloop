#!/usr/bin/env python3
"""
Tests for Semantic Scholar API Integration

Comprehensive tests for the SemanticScholarClient, including:
- Data classes (Paper, Author)
- Search functionality
- Paper/author retrieval
- Citation and reference traversal
- Rate limiting
- Caching
- Error handling

Uses mock responses to avoid real API calls.
"""

import os
import sys
import json
import time
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

spec = importlib.util.spec_from_file_location(
    "semantic_scholar",
    os.path.join(lib_path, "semantic_scholar.py")
)
semantic_scholar = importlib.util.module_from_spec(spec)
spec.loader.exec_module(semantic_scholar)

Paper = semantic_scholar.Paper
Author = semantic_scholar.Author
SemanticScholarClient = semantic_scholar.SemanticScholarClient
SemanticScholarError = semantic_scholar.SemanticScholarError
RateLimiter = semantic_scholar.RateLimiter
ResultCache = semantic_scholar.ResultCache


class TestAuthorDataClass(unittest.TestCase):
    """Test Author dataclass."""

    def test_author_creation(self):
        """Test creating Author with all fields."""
        author = Author(
            author_id="12345",
            name="John Doe",
            affiliation="Stanford University",
            h_index=42,
            paper_count=100,
            citation_count=5000
        )

        self.assertEqual(author.author_id, "12345")
        self.assertEqual(author.name, "John Doe")
        self.assertEqual(author.affiliation, "Stanford University")
        self.assertEqual(author.h_index, 42)
        self.assertEqual(author.paper_count, 100)
        self.assertEqual(author.citation_count, 5000)

    def test_author_optional_fields(self):
        """Test Author with only required fields."""
        author = Author(
            author_id="12345",
            name="Jane Doe"
        )

        self.assertEqual(author.author_id, "12345")
        self.assertEqual(author.name, "Jane Doe")
        self.assertIsNone(author.affiliation)
        self.assertIsNone(author.h_index)
        self.assertIsNone(author.paper_count)
        self.assertIsNone(author.citation_count)

    def test_author_to_dict(self):
        """Test Author serialization to dictionary."""
        author = Author(
            author_id="12345",
            name="John Doe",
            h_index=42
        )

        author_dict = author.to_dict()

        self.assertEqual(author_dict["author_id"], "12345")
        self.assertEqual(author_dict["name"], "John Doe")
        self.assertEqual(author_dict["h_index"], 42)
        self.assertIsNone(author_dict["affiliation"])

    def test_author_from_dict(self):
        """Test Author creation from dictionary."""
        data = {
            "author_id": "12345",
            "name": "John Doe",
            "affiliation": "MIT",
            "h_index": 50
        }

        author = Author.from_dict(data)

        self.assertEqual(author.author_id, "12345")
        self.assertEqual(author.name, "John Doe")
        self.assertEqual(author.affiliation, "MIT")
        self.assertEqual(author.h_index, 50)

    def test_author_from_api_response(self):
        """Test Author creation from API response format."""
        api_response = {
            "authorId": "abc123",
            "name": "Jane Smith",
            "affiliations": ["Harvard University", "Secondary Affiliation"],
            "hIndex": 35,
            "paperCount": 75,
            "citationCount": 3000
        }

        author = Author.from_api_response(api_response)

        self.assertEqual(author.author_id, "abc123")
        self.assertEqual(author.name, "Jane Smith")
        self.assertEqual(author.affiliation, "Harvard University")
        self.assertEqual(author.h_index, 35)
        self.assertEqual(author.paper_count, 75)
        self.assertEqual(author.citation_count, 3000)


class TestPaperDataClass(unittest.TestCase):
    """Test Paper dataclass."""

    def test_paper_creation(self):
        """Test creating Paper with all fields."""
        author = Author(author_id="1", name="Test Author")
        paper = Paper(
            paper_id="paper123",
            title="Test Paper Title",
            abstract="This is a test abstract.",
            authors=[author],
            year=2023,
            citation_count=100,
            venue="Nature",
            url="https://example.com/paper",
            fields_of_study=["Computer Science", "Machine Learning"]
        )

        self.assertEqual(paper.paper_id, "paper123")
        self.assertEqual(paper.title, "Test Paper Title")
        self.assertEqual(paper.abstract, "This is a test abstract.")
        self.assertEqual(len(paper.authors), 1)
        self.assertEqual(paper.authors[0].name, "Test Author")
        self.assertEqual(paper.year, 2023)
        self.assertEqual(paper.citation_count, 100)
        self.assertEqual(paper.venue, "Nature")
        self.assertEqual(paper.url, "https://example.com/paper")
        self.assertEqual(paper.fields_of_study, ["Computer Science", "Machine Learning"])

    def test_paper_optional_fields(self):
        """Test Paper with only required fields."""
        paper = Paper(
            paper_id="paper123",
            title="Minimal Paper"
        )

        self.assertEqual(paper.paper_id, "paper123")
        self.assertEqual(paper.title, "Minimal Paper")
        self.assertIsNone(paper.abstract)
        self.assertEqual(paper.authors, [])
        self.assertIsNone(paper.year)
        self.assertIsNone(paper.citation_count)
        self.assertIsNone(paper.venue)
        self.assertIsNone(paper.url)
        self.assertEqual(paper.fields_of_study, [])

    def test_paper_to_dict(self):
        """Test Paper serialization to dictionary."""
        author = Author(author_id="1", name="Test Author")
        paper = Paper(
            paper_id="paper123",
            title="Test Paper",
            authors=[author],
            year=2023
        )

        paper_dict = paper.to_dict()

        self.assertEqual(paper_dict["paper_id"], "paper123")
        self.assertEqual(paper_dict["title"], "Test Paper")
        self.assertEqual(len(paper_dict["authors"]), 1)
        self.assertEqual(paper_dict["authors"][0]["name"], "Test Author")
        self.assertEqual(paper_dict["year"], 2023)

    def test_paper_from_dict(self):
        """Test Paper creation from dictionary."""
        data = {
            "paper_id": "paper456",
            "title": "Another Paper",
            "abstract": "Abstract text",
            "authors": [{"author_id": "1", "name": "Author One"}],
            "year": 2022,
            "citation_count": 50,
            "fields_of_study": ["Biology"]
        }

        paper = Paper.from_dict(data)

        self.assertEqual(paper.paper_id, "paper456")
        self.assertEqual(paper.title, "Another Paper")
        self.assertEqual(paper.abstract, "Abstract text")
        self.assertEqual(len(paper.authors), 1)
        self.assertEqual(paper.year, 2022)
        self.assertEqual(paper.citation_count, 50)
        self.assertEqual(paper.fields_of_study, ["Biology"])

    def test_paper_from_api_response(self):
        """Test Paper creation from API response format."""
        api_response = {
            "paperId": "s2paper789",
            "title": "Attention Is All You Need",
            "abstract": "The dominant sequence transduction models...",
            "authors": [
                {"authorId": "a1", "name": "Ashish Vaswani"},
                {"authorId": "a2", "name": "Noam Shazeer"}
            ],
            "year": 2017,
            "citationCount": 50000,
            "venue": "NeurIPS",
            "url": "https://arxiv.org/abs/1706.03762",
            "fieldsOfStudy": ["Computer Science", "Artificial Intelligence"]
        }

        paper = Paper.from_api_response(api_response)

        self.assertEqual(paper.paper_id, "s2paper789")
        self.assertEqual(paper.title, "Attention Is All You Need")
        self.assertEqual(paper.abstract, "The dominant sequence transduction models...")
        self.assertEqual(len(paper.authors), 2)
        self.assertEqual(paper.authors[0].name, "Ashish Vaswani")
        self.assertEqual(paper.year, 2017)
        self.assertEqual(paper.citation_count, 50000)
        self.assertEqual(paper.venue, "NeurIPS")
        self.assertEqual(paper.url, "https://arxiv.org/abs/1706.03762")
        self.assertEqual(paper.fields_of_study, ["Computer Science", "Artificial Intelligence"])


class TestRateLimiter(unittest.TestCase):
    """Test rate limiter functionality."""

    def test_rate_limiter_without_key(self):
        """Test rate limiter with default limits (no API key)."""
        limiter = RateLimiter(has_api_key=False)

        self.assertEqual(limiter.max_requests, 100)
        self.assertEqual(limiter.window_seconds, 300)

    def test_rate_limiter_with_key(self):
        """Test rate limiter with API key (higher limits)."""
        limiter = RateLimiter(has_api_key=True)

        self.assertEqual(limiter.max_requests, 1000)
        self.assertEqual(limiter.window_seconds, 300)

    def test_rate_limiter_acquire_no_wait(self):
        """Test acquiring when under limit requires no wait."""
        limiter = RateLimiter(has_api_key=False)

        # First request should not require waiting
        wait_time = limiter.acquire()
        self.assertEqual(wait_time, 0.0)

    def test_rate_limiter_tracks_requests(self):
        """Test that rate limiter tracks requests."""
        limiter = RateLimiter(has_api_key=False)

        # Make some requests
        for _ in range(5):
            limiter.acquire()

        self.assertEqual(len(limiter.requests), 5)


class TestResultCache(unittest.TestCase):
    """Test result cache functionality."""

    def setUp(self):
        """Create a fresh cache for each test."""
        self.cache = ResultCache(ttl_seconds=3600, max_entries=100)

    def test_cache_miss(self):
        """Test cache miss for non-existent entry."""
        result = self.cache.get("search", "nonexistent query")
        self.assertIsNone(result)

        stats = self.cache.get_stats()
        self.assertEqual(stats["misses"], 1)
        self.assertEqual(stats["hits"], 0)

    def test_cache_hit(self):
        """Test cache hit for stored entry."""
        test_data = [{"title": "Test Paper", "paper_id": "123"}]

        self.cache.set("search", "test query", test_data)
        result = self.cache.get("search", "test query")

        self.assertEqual(result, test_data)

        stats = self.cache.get_stats()
        self.assertEqual(stats["hits"], 1)

    def test_cache_with_params(self):
        """Test cache with additional parameters."""
        test_data = [{"title": "Test"}]

        self.cache.set("search", "query", test_data, params={"limit": 10})

        # Should hit with same params
        result1 = self.cache.get("search", "query", params={"limit": 10})
        self.assertEqual(result1, test_data)

        # Should miss with different params
        result2 = self.cache.get("search", "query", params={"limit": 20})
        self.assertIsNone(result2)

    def test_cache_expiration(self):
        """Test cache TTL expiration."""
        # Create cache with very short TTL
        short_cache = ResultCache(ttl_seconds=0.1)

        test_data = [{"title": "Expires Soon"}]
        short_cache.set("search", "query", test_data)

        # Should hit immediately
        result1 = short_cache.get("search", "query")
        self.assertEqual(result1, test_data)

        # Wait for expiration
        time.sleep(0.2)

        # Should miss after expiration
        result2 = short_cache.get("search", "query")
        self.assertIsNone(result2)

    def test_cache_max_entries_eviction(self):
        """Test cache evicts oldest entries when at capacity."""
        small_cache = ResultCache(max_entries=3)

        # Fill cache
        small_cache.set("method", "query1", ["data1"])
        time.sleep(0.01)
        small_cache.set("method", "query2", ["data2"])
        time.sleep(0.01)
        small_cache.set("method", "query3", ["data3"])

        # Add one more (should evict oldest)
        small_cache.set("method", "query4", ["data4"])

        # query1 should be evicted
        self.assertIsNone(small_cache.get("method", "query1"))
        self.assertEqual(small_cache.get("method", "query4"), ["data4"])

    def test_cache_clear(self):
        """Test clearing cache."""
        self.cache.set("method", "query1", ["data1"])
        self.cache.set("method", "query2", ["data2"])

        stats_before = self.cache.get_stats()
        self.assertEqual(stats_before["entry_count"], 2)

        self.cache.clear()

        stats_after = self.cache.get_stats()
        self.assertEqual(stats_after["entry_count"], 0)
        self.assertEqual(stats_after["hits"], 0)
        self.assertEqual(stats_after["misses"], 0)

    def test_cache_stats(self):
        """Test cache statistics calculation."""
        self.cache.set("method", "query1", ["data1"])
        self.cache.get("method", "query1")  # Hit
        self.cache.get("method", "query1")  # Hit
        self.cache.get("method", "nonexistent")  # Miss

        stats = self.cache.get_stats()

        self.assertEqual(stats["hits"], 2)
        self.assertEqual(stats["misses"], 1)
        self.assertAlmostEqual(stats["hit_rate"], 0.667, places=2)
        self.assertEqual(stats["entry_count"], 1)


class TestSemanticScholarClient(unittest.TestCase):
    """Test SemanticScholarClient methods."""

    def setUp(self):
        """Create client for testing."""
        # Clear any env var to test without API key
        self.original_key = os.environ.get("SEMANTIC_SCHOLAR_API_KEY")
        if "SEMANTIC_SCHOLAR_API_KEY" in os.environ:
            del os.environ["SEMANTIC_SCHOLAR_API_KEY"]

        self.client = SemanticScholarClient()

    def tearDown(self):
        """Restore environment."""
        if self.original_key:
            os.environ["SEMANTIC_SCHOLAR_API_KEY"] = self.original_key

    def test_is_available_always_true(self):
        """Test client is always available (API works without key)."""
        self.assertTrue(self.client.is_available())

    def test_has_api_key_false_without_key(self):
        """Test has_api_key returns False without key."""
        self.assertFalse(self.client.has_api_key())

    def test_has_api_key_true_with_key(self):
        """Test has_api_key returns True with key."""
        client = SemanticScholarClient(api_key="test-key")
        self.assertTrue(client.has_api_key())

    @patch("requests.Session.get")
    def test_search_papers_success(self, mock_get):
        """Test successful paper search."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": [
                {
                    "paperId": "paper1",
                    "title": "Deep Learning",
                    "abstract": "A comprehensive study...",
                    "authors": [{"authorId": "a1", "name": "Yann LeCun"}],
                    "year": 2015,
                    "citationCount": 10000,
                    "venue": "Nature",
                    "url": "https://example.com",
                    "fieldsOfStudy": ["Computer Science"]
                },
                {
                    "paperId": "paper2",
                    "title": "Reinforcement Learning",
                    "abstract": "An introduction...",
                    "authors": [{"authorId": "a2", "name": "Richard Sutton"}],
                    "year": 2018,
                    "citationCount": 5000,
                    "venue": "MIT Press",
                    "url": "https://example2.com",
                    "fieldsOfStudy": ["Artificial Intelligence"]
                }
            ]
        }
        mock_get.return_value = mock_response

        papers = self.client.search_papers("machine learning", limit=2)

        self.assertEqual(len(papers), 2)
        self.assertEqual(papers[0].paper_id, "paper1")
        self.assertEqual(papers[0].title, "Deep Learning")
        self.assertEqual(papers[0].authors[0].name, "Yann LeCun")
        self.assertEqual(papers[0].year, 2015)
        self.assertEqual(papers[0].citation_count, 10000)

        self.assertEqual(papers[1].paper_id, "paper2")
        self.assertEqual(papers[1].title, "Reinforcement Learning")

    @patch("requests.Session.get")
    def test_search_papers_caching(self, mock_get):
        """Test that search results are cached."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": [{"paperId": "p1", "title": "Test Paper"}]
        }
        mock_get.return_value = mock_response

        # First call - should make API request
        papers1 = self.client.search_papers("test query", limit=10)
        self.assertEqual(mock_get.call_count, 1)

        # Second call - should use cache
        papers2 = self.client.search_papers("test query", limit=10)
        self.assertEqual(mock_get.call_count, 1)  # Still 1 (cached)

        self.assertEqual(papers1[0].paper_id, papers2[0].paper_id)

    @patch("requests.Session.get")
    def test_get_paper_success(self, mock_get):
        """Test successful paper retrieval by ID."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "paperId": "649def34f8be52c8b66281af98ae884c09aef38b",
            "title": "Attention Is All You Need",
            "abstract": "The dominant sequence transduction models are based on...",
            "authors": [
                {"authorId": "a1", "name": "Ashish Vaswani"},
                {"authorId": "a2", "name": "Noam Shazeer"}
            ],
            "year": 2017,
            "citationCount": 50000,
            "venue": "NeurIPS",
            "url": "https://arxiv.org/abs/1706.03762",
            "fieldsOfStudy": ["Computer Science"]
        }
        mock_get.return_value = mock_response

        paper = self.client.get_paper("649def34f8be52c8b66281af98ae884c09aef38b")

        self.assertEqual(paper.paper_id, "649def34f8be52c8b66281af98ae884c09aef38b")
        self.assertEqual(paper.title, "Attention Is All You Need")
        self.assertEqual(paper.year, 2017)
        self.assertEqual(len(paper.authors), 2)

    @patch("requests.Session.get")
    def test_get_paper_by_doi(self, mock_get):
        """Test paper retrieval by DOI."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "paperId": "paper_from_doi",
            "title": "DOI Paper",
            "year": 2020
        }
        mock_get.return_value = mock_response

        paper = self.client.get_paper("DOI:10.1038/nrn3241")

        self.assertEqual(paper.paper_id, "paper_from_doi")
        # Verify DOI was URL-encoded in the request
        call_url = mock_get.call_args[0][0]
        self.assertIn("DOI%3A10.1038", call_url)

    @patch("requests.Session.get")
    def test_get_citations_success(self, mock_get):
        """Test successful citation retrieval."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": [
                {
                    "citingPaper": {
                        "paperId": "citing1",
                        "title": "Paper Citing Original",
                        "year": 2020,
                        "citationCount": 100
                    }
                },
                {
                    "citingPaper": {
                        "paperId": "citing2",
                        "title": "Another Citing Paper",
                        "year": 2021,
                        "citationCount": 50
                    }
                }
            ]
        }
        mock_get.return_value = mock_response

        citations = self.client.get_citations("original_paper_id", limit=10)

        self.assertEqual(len(citations), 2)
        self.assertEqual(citations[0].paper_id, "citing1")
        self.assertEqual(citations[0].title, "Paper Citing Original")
        self.assertEqual(citations[1].paper_id, "citing2")

    @patch("requests.Session.get")
    def test_get_references_success(self, mock_get):
        """Test successful reference retrieval."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": [
                {
                    "citedPaper": {
                        "paperId": "ref1",
                        "title": "Referenced Paper 1",
                        "year": 2010
                    }
                },
                {
                    "citedPaper": {
                        "paperId": "ref2",
                        "title": "Referenced Paper 2",
                        "year": 2012
                    }
                }
            ]
        }
        mock_get.return_value = mock_response

        references = self.client.get_references("paper_id", limit=10)

        self.assertEqual(len(references), 2)
        self.assertEqual(references[0].paper_id, "ref1")
        self.assertEqual(references[1].paper_id, "ref2")

    @patch("requests.Session.get")
    def test_get_author_success(self, mock_get):
        """Test successful author retrieval."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "authorId": "author123",
            "name": "Geoffrey Hinton",
            "affiliations": ["University of Toronto", "Google"],
            "hIndex": 150,
            "paperCount": 400,
            "citationCount": 500000
        }
        mock_get.return_value = mock_response

        author = self.client.get_author("author123")

        self.assertEqual(author.author_id, "author123")
        self.assertEqual(author.name, "Geoffrey Hinton")
        self.assertEqual(author.affiliation, "University of Toronto")
        self.assertEqual(author.h_index, 150)
        self.assertEqual(author.paper_count, 400)
        self.assertEqual(author.citation_count, 500000)

    @patch("requests.Session.get")
    def test_search_by_author_success(self, mock_get):
        """Test searching papers by author name."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": [
                {
                    "paperId": "paper1",
                    "title": "Paper by Author",
                    "authors": [{"authorId": "a1", "name": "Test Author"}],
                    "year": 2020
                }
            ]
        }
        mock_get.return_value = mock_response

        papers = self.client.search_by_author("Test Author", limit=10)

        self.assertEqual(len(papers), 1)
        self.assertEqual(papers[0].title, "Paper by Author")

    @patch("requests.Session.get")
    def test_api_error_handling(self, mock_get):
        """Test handling of API errors."""
        mock_response = Mock()
        mock_response.status_code = 400
        mock_response.text = "Bad request"
        mock_response.json.return_value = {"message": "Invalid query"}
        mock_get.return_value = mock_response

        with self.assertRaises(SemanticScholarError) as context:
            self.client.search_papers("invalid query")

        self.assertIn("API error 400", str(context.exception))

    @patch("requests.Session.get")
    def test_not_found_error(self, mock_get):
        """Test handling of 404 not found errors."""
        mock_response = Mock()
        mock_response.status_code = 404
        mock_response.text = "Not found"
        mock_get.return_value = mock_response

        with self.assertRaises(SemanticScholarError) as context:
            self.client.get_paper("nonexistent_id")

        self.assertIn("not found", str(context.exception).lower())

    @patch("requests.Session.get")
    def test_rate_limit_retry(self, mock_get):
        """Test retry on rate limit response."""
        # First call returns 429, second succeeds
        rate_limit_response = Mock()
        rate_limit_response.status_code = 429
        rate_limit_response.headers = {"Retry-After": "0"}

        success_response = Mock()
        success_response.status_code = 200
        success_response.json.return_value = {"data": []}

        mock_get.side_effect = [rate_limit_response, success_response]

        papers = self.client.search_papers("test")

        self.assertEqual(mock_get.call_count, 2)
        self.assertEqual(papers, [])

    @patch("requests.Session.get")
    def test_server_error_retry(self, mock_get):
        """Test retry on server error."""
        # First call returns 500, second succeeds
        error_response = Mock()
        error_response.status_code = 500

        success_response = Mock()
        success_response.status_code = 200
        success_response.json.return_value = {"data": []}

        mock_get.side_effect = [error_response, success_response]

        papers = self.client.search_papers("test")

        self.assertEqual(mock_get.call_count, 2)

    @patch("requests.Session.get")
    def test_timeout_retry(self, mock_get):
        """Test retry on request timeout."""
        import requests

        # First call times out, second succeeds
        mock_get.side_effect = [
            requests.exceptions.Timeout("Connection timed out"),
            Mock(status_code=200, json=Mock(return_value={"data": []}))
        ]

        papers = self.client.search_papers("test")

        self.assertEqual(mock_get.call_count, 2)

    @patch("requests.Session.get")
    def test_max_retries_exceeded(self, mock_get):
        """Test error after max retries exceeded."""
        error_response = Mock()
        error_response.status_code = 500

        mock_get.return_value = error_response

        with self.assertRaises(SemanticScholarError) as context:
            self.client.search_papers("test")

        self.assertIn("Request failed after", str(context.exception))
        self.assertEqual(mock_get.call_count, 3)  # max_retries default is 3

    def test_cache_stats(self):
        """Test getting cache statistics."""
        stats = self.client.get_cache_stats()

        self.assertIn("hits", stats)
        self.assertIn("misses", stats)
        self.assertIn("hit_rate", stats)
        self.assertIn("entry_count", stats)
        self.assertEqual(stats["ttl_seconds"], 86400)  # 24 hours

    def test_clear_cache(self):
        """Test clearing client cache."""
        # Add something to cache
        self.client.cache.set("method", "query", ["data"])

        stats_before = self.client.get_cache_stats()
        self.assertEqual(stats_before["entry_count"], 1)

        self.client.clear_cache()

        stats_after = self.client.get_cache_stats()
        self.assertEqual(stats_after["entry_count"], 0)


class TestSemanticScholarClientWithAPIKey(unittest.TestCase):
    """Test client behavior with API key."""

    def test_client_with_env_api_key(self):
        """Test client picks up API key from environment."""
        with patch.dict(os.environ, {"SEMANTIC_SCHOLAR_API_KEY": "test-key-123"}):
            client = SemanticScholarClient()
            self.assertTrue(client.has_api_key())
            self.assertEqual(client.api_key, "test-key-123")

    def test_client_with_explicit_api_key(self):
        """Test client with explicitly provided API key."""
        client = SemanticScholarClient(api_key="explicit-key")
        self.assertTrue(client.has_api_key())
        self.assertEqual(client.api_key, "explicit-key")

    def test_api_key_in_headers(self):
        """Test API key is included in request headers."""
        client = SemanticScholarClient(api_key="test-key")
        headers = client._get_headers()

        self.assertIn("x-api-key", headers)
        self.assertEqual(headers["x-api-key"], "test-key")

    def test_no_api_key_in_headers_without_key(self):
        """Test no API key header when key not configured."""
        with patch.dict(os.environ, {}, clear=True):
            client = SemanticScholarClient()
            headers = client._get_headers()

            # x-api-key should be empty string, not missing
            self.assertEqual(headers.get("x-api-key", ""), "")


class TestIntegration(unittest.TestCase):
    """Integration tests combining multiple components."""

    @patch("requests.Session.get")
    def test_full_paper_workflow(self, mock_get):
        """Test complete workflow: search -> get paper -> get citations."""
        # Mock search response
        search_response = Mock()
        search_response.status_code = 200
        search_response.json.return_value = {
            "data": [
                {
                    "paperId": "transformer_paper",
                    "title": "Attention Is All You Need",
                    "authors": [{"authorId": "a1", "name": "Ashish Vaswani"}],
                    "year": 2017,
                    "citationCount": 50000
                }
            ]
        }

        # Mock paper detail response
        paper_response = Mock()
        paper_response.status_code = 200
        paper_response.json.return_value = {
            "paperId": "transformer_paper",
            "title": "Attention Is All You Need",
            "abstract": "Full abstract here...",
            "authors": [
                {"authorId": "a1", "name": "Ashish Vaswani"},
                {"authorId": "a2", "name": "Noam Shazeer"}
            ],
            "year": 2017,
            "citationCount": 50000,
            "venue": "NeurIPS",
            "fieldsOfStudy": ["Computer Science"]
        }

        # Mock citations response
        citations_response = Mock()
        citations_response.status_code = 200
        citations_response.json.return_value = {
            "data": [
                {
                    "citingPaper": {
                        "paperId": "bert_paper",
                        "title": "BERT: Pre-training of Deep Bidirectional Transformers",
                        "year": 2018
                    }
                }
            ]
        }

        mock_get.side_effect = [search_response, paper_response, citations_response]

        client = SemanticScholarClient()

        # Search for papers
        search_results = client.search_papers("transformer attention", limit=1)
        self.assertEqual(len(search_results), 1)
        paper_id = search_results[0].paper_id

        # Get paper details
        paper = client.get_paper(paper_id)
        self.assertEqual(paper.title, "Attention Is All You Need")
        self.assertEqual(len(paper.authors), 2)

        # Get citations
        citations = client.get_citations(paper_id, limit=10)
        self.assertEqual(len(citations), 1)
        self.assertEqual(citations[0].title, "BERT: Pre-training of Deep Bidirectional Transformers")


def run_tests():
    """Run all tests."""
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromModule(sys.modules[__name__])
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(run_tests())
