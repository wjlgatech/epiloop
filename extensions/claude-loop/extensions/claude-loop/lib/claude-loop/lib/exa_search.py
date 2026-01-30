#!/usr/bin/env python3
"""
Exa.ai Search Integration

Provides neural search capabilities via Exa.ai API.
Features:
- Neural search for semantic similarity
- Academic paper search optimization
- News search with date filtering
- Content extraction from URLs
- Rate limiting and retry logic
- Result caching with TTL
"""

import os
import sys
import time
import json
import hashlib
import threading
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from urllib.parse import urlparse
import requests


@dataclass
class SearchResult:
    """Structured search result from Exa.ai."""
    title: str
    url: str
    snippet: str
    score: float  # Relevance score from Exa (0.0-1.0)
    published_date: Optional[str] = None
    author: Optional[str] = None
    highlights: List[str] = field(default_factory=list)
    source: str = "exa"

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "title": self.title,
            "url": self.url,
            "snippet": self.snippet,
            "score": self.score,
            "published_date": self.published_date,
            "author": self.author,
            "highlights": self.highlights,
            "source": self.source
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SearchResult":
        """Create SearchResult from dictionary."""
        return cls(
            title=data.get("title", ""),
            url=data.get("url", ""),
            snippet=data.get("snippet", ""),
            score=data.get("score", 0.0),
            published_date=data.get("published_date"),
            author=data.get("author"),
            highlights=data.get("highlights", []),
            source=data.get("source", "exa")
        )


@dataclass
class DocumentContent:
    """Content extracted from a URL via Exa."""
    url: str
    title: str
    text: str
    author: Optional[str] = None
    published_date: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "url": self.url,
            "title": self.title,
            "text": self.text,
            "author": self.author,
            "published_date": self.published_date
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DocumentContent":
        """Create DocumentContent from dictionary."""
        return cls(
            url=data.get("url", ""),
            title=data.get("title", ""),
            text=data.get("text", ""),
            author=data.get("author"),
            published_date=data.get("published_date")
        )


class ExaSearchError(Exception):
    """Exception for Exa search errors."""
    pass


class RateLimiter:
    """
    Token bucket rate limiter for API requests.

    Allows up to `rate` requests per second with burst capability.
    """

    def __init__(self, rate: float = 10.0):
        """
        Initialize rate limiter.

        Args:
            rate: Maximum requests per second (default: 10)
        """
        self.rate = rate
        self.tokens = rate
        self.last_update = time.monotonic()
        self.lock = threading.Lock()

    def acquire(self) -> float:
        """
        Acquire a token, blocking if necessary.

        Returns:
            Wait time in seconds (0 if no wait needed)
        """
        with self.lock:
            now = time.monotonic()
            elapsed = now - self.last_update
            self.tokens = min(self.rate, self.tokens + elapsed * self.rate)
            self.last_update = now

            if self.tokens >= 1:
                self.tokens -= 1
                return 0.0

            # Need to wait
            wait_time = (1 - self.tokens) / self.rate
            self.tokens = 0
            return wait_time

    def wait(self):
        """Wait for a token to become available."""
        wait_time = self.acquire()
        if wait_time > 0:
            time.sleep(wait_time)


class ResultCache:
    """
    In-memory cache for search results with TTL expiration.

    Uses LRU eviction when max size is reached.
    """

    def __init__(self, ttl_seconds: int = 3600, max_entries: int = 1000):
        """
        Initialize result cache.

        Args:
            ttl_seconds: Time-to-live for cache entries (default: 1 hour)
            max_entries: Maximum number of cached entries (default: 1000)
        """
        self.ttl_seconds = ttl_seconds
        self.max_entries = max_entries
        self.cache: Dict[str, tuple] = {}  # key -> (value, timestamp)
        self.lock = threading.Lock()
        self.stats = {"hits": 0, "misses": 0}

    def _make_key(self, method: str, query: str, params: Optional[Dict] = None) -> str:
        """Generate cache key from method, query, and parameters."""
        key_input = f"{method}:{query.lower().strip()}"
        if params:
            sorted_params = sorted(params.items())
            key_input += f":{json.dumps(sorted_params, sort_keys=True)}"
        return hashlib.sha256(key_input.encode()).hexdigest()[:32]

    def get(self, method: str, query: str, params: Optional[Dict] = None) -> Optional[Any]:
        """
        Retrieve cached result.

        Args:
            method: Search method name
            query: Search query
            params: Additional parameters

        Returns:
            Cached value or None if not found/expired
        """
        key = self._make_key(method, query, params)

        with self.lock:
            if key not in self.cache:
                self.stats["misses"] += 1
                return None

            value, timestamp = self.cache[key]

            # Check expiration
            if time.time() - timestamp > self.ttl_seconds:
                del self.cache[key]
                self.stats["misses"] += 1
                return None

            self.stats["hits"] += 1
            return value

    def set(self, method: str, query: str, value: Any, params: Optional[Dict] = None):
        """
        Store result in cache.

        Args:
            method: Search method name
            query: Search query
            value: Value to cache
            params: Additional parameters
        """
        key = self._make_key(method, query, params)

        with self.lock:
            # Evict oldest entries if at capacity
            if len(self.cache) >= self.max_entries:
                # Find and remove oldest entry
                oldest_key = min(self.cache, key=lambda k: self.cache[k][1])
                del self.cache[oldest_key]

            self.cache[key] = (value, time.time())

    def clear(self):
        """Clear all cached entries."""
        with self.lock:
            self.cache.clear()
            self.stats = {"hits": 0, "misses": 0}

    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        with self.lock:
            total = self.stats["hits"] + self.stats["misses"]
            hit_rate = self.stats["hits"] / total if total > 0 else 0.0
            return {
                "hits": self.stats["hits"],
                "misses": self.stats["misses"],
                "hit_rate": round(hit_rate, 3),
                "entry_count": len(self.cache),
                "max_entries": self.max_entries,
                "ttl_seconds": self.ttl_seconds
            }


class ExaSearchClient:
    """
    Client for Exa.ai search API.

    Provides neural search with support for:
    - General web search
    - Academic paper search
    - News search with date filtering
    - Content extraction from URLs

    Features:
    - Rate limiting (10 requests/second)
    - Exponential backoff retry logic
    - Result caching (1 hour TTL)
    """

    BASE_URL = "https://api.exa.ai"

    def __init__(
        self,
        api_key: Optional[str] = None,
        rate_limit: float = 10.0,
        cache_ttl: int = 3600,
        max_retries: int = 3,
        timeout: int = 30
    ):
        """
        Initialize Exa search client.

        Args:
            api_key: Exa API key (default: from EXA_API_KEY env var)
            rate_limit: Max requests per second (default: 10)
            cache_ttl: Cache TTL in seconds (default: 3600 = 1 hour)
            max_retries: Maximum retry attempts (default: 3)
            timeout: Request timeout in seconds (default: 30)
        """
        self.api_key = api_key or os.getenv("EXA_API_KEY")
        self.rate_limiter = RateLimiter(rate=rate_limit)
        self.cache = ResultCache(ttl_seconds=cache_ttl)
        self.max_retries = max_retries
        self.timeout = timeout
        self.session = requests.Session()

    def is_available(self) -> bool:
        """Check if Exa API key is configured."""
        return bool(self.api_key)

    def _get_headers(self) -> Dict[str, str]:
        """Get request headers with authentication."""
        return {
            "Content-Type": "application/json",
            "x-api-key": self.api_key or ""
        }

    def _request_with_retry(
        self,
        endpoint: str,
        payload: Dict[str, Any],
        method: str = "POST"
    ) -> Dict[str, Any]:
        """
        Make API request with rate limiting and retry logic.

        Args:
            endpoint: API endpoint path
            payload: Request payload
            method: HTTP method (default: POST)

        Returns:
            API response as dictionary

        Raises:
            ExaSearchError: If request fails after retries
        """
        if not self.api_key:
            raise ExaSearchError("EXA_API_KEY not configured")

        url = f"{self.BASE_URL}{endpoint}"
        headers = self._get_headers()

        last_error = None

        for attempt in range(self.max_retries):
            # Apply rate limiting
            self.rate_limiter.wait()

            try:
                if method.upper() == "POST":
                    response = self.session.post(
                        url,
                        json=payload,
                        headers=headers,
                        timeout=self.timeout
                    )
                else:
                    response = self.session.get(
                        url,
                        params=payload,
                        headers=headers,
                        timeout=self.timeout
                    )

                # Check for rate limit response
                if response.status_code == 429:
                    retry_after = int(response.headers.get("Retry-After", 5))
                    time.sleep(retry_after)
                    continue

                # Check for server errors (retry)
                if response.status_code >= 500:
                    last_error = f"Server error: {response.status_code}"
                    # Exponential backoff
                    time.sleep(2 ** attempt)
                    continue

                # Check for client errors (don't retry)
                if response.status_code >= 400:
                    error_msg = response.text
                    try:
                        error_data = response.json()
                        error_msg = error_data.get("error", error_msg)
                    except json.JSONDecodeError:
                        pass
                    raise ExaSearchError(f"API error {response.status_code}: {error_msg}")

                return response.json()

            except requests.exceptions.Timeout:
                last_error = "Request timeout"
                # Exponential backoff
                time.sleep(2 ** attempt)
            except requests.exceptions.RequestException as e:
                last_error = str(e)
                # Exponential backoff
                time.sleep(2 ** attempt)

        raise ExaSearchError(f"Request failed after {self.max_retries} retries: {last_error}")

    def _parse_results(self, response: Dict[str, Any]) -> List[SearchResult]:
        """
        Parse API response into SearchResult objects.

        Args:
            response: API response dictionary

        Returns:
            List of SearchResult objects
        """
        results = []

        for item in response.get("results", []):
            # Extract domain from URL
            url = item.get("url", "")

            # Build snippet from text or highlights
            text = item.get("text", "")
            highlights = item.get("highlights", [])
            snippet = text[:500] if text else (highlights[0] if highlights else "")

            result = SearchResult(
                title=item.get("title", ""),
                url=url,
                snippet=snippet,
                score=float(item.get("score", 0.0)),
                published_date=item.get("publishedDate"),
                author=item.get("author"),
                highlights=highlights,
                source="exa"
            )
            results.append(result)

        return results

    def search(
        self,
        query: str,
        num_results: int = 10,
        use_autoprompt: bool = True,
        type: str = "neural"
    ) -> List[SearchResult]:
        """
        Execute neural search query.

        Args:
            query: Search query string
            num_results: Maximum results to return (default: 10)
            use_autoprompt: Let Exa optimize query (default: True)
            type: Search type - "neural" or "keyword" (default: "neural")

        Returns:
            List of SearchResult objects ordered by relevance

        Raises:
            ExaSearchError: If search fails
        """
        # Check cache first
        cache_params = {"num_results": num_results, "type": type}
        cached = self.cache.get("search", query, cache_params)
        if cached is not None:
            return [SearchResult.from_dict(r) for r in cached]

        payload = {
            "query": query,
            "numResults": num_results,
            "useAutoprompt": use_autoprompt,
            "type": type,
            "contents": {
                "text": {"maxCharacters": 1000},
                "highlights": {"numSentences": 3}
            }
        }

        response = self._request_with_retry("/search", payload)
        results = self._parse_results(response)

        # Cache results
        self.cache.set("search", query, [r.to_dict() for r in results], cache_params)

        return results

    def search_academic(
        self,
        query: str,
        num_results: int = 10,
        start_published_date: Optional[str] = None,
        end_published_date: Optional[str] = None
    ) -> List[SearchResult]:
        """
        Search for academic papers using neural search.

        Optimized for finding research papers, preprints, and scholarly articles.

        Args:
            query: Search query (optimized for academic content)
            num_results: Maximum results to return (default: 10)
            start_published_date: Filter by start date (YYYY-MM-DD)
            end_published_date: Filter by end date (YYYY-MM-DD)

        Returns:
            List of SearchResult objects for academic content

        Raises:
            ExaSearchError: If search fails
        """
        # Check cache first
        cache_params = {
            "num_results": num_results,
            "type": "academic",
            "start_date": start_published_date,
            "end_date": end_published_date
        }
        cached = self.cache.get("search_academic", query, cache_params)
        if cached is not None:
            return [SearchResult.from_dict(r) for r in cached]

        # Academic domains to prioritize
        academic_domains = [
            "arxiv.org",
            "scholar.google.com",
            "semanticscholar.org",
            "pubmed.ncbi.nlm.nih.gov",
            "ieee.org",
            "acm.org",
            "nature.com",
            "science.org",
            "springer.com",
            "wiley.com",
            "researchgate.net",
            "biorxiv.org",
            "medrxiv.org"
        ]

        payload = {
            "query": query,
            "numResults": num_results,
            "useAutoprompt": True,
            "type": "neural",
            "includeDomains": academic_domains,
            "contents": {
                "text": {"maxCharacters": 1500},
                "highlights": {"numSentences": 5}
            }
        }

        if start_published_date:
            payload["startPublishedDate"] = start_published_date
        if end_published_date:
            payload["endPublishedDate"] = end_published_date

        response = self._request_with_retry("/search", payload)
        results = self._parse_results(response)

        # Cache results
        self.cache.set("search_academic", query, [r.to_dict() for r in results], cache_params)

        return results

    def search_news(
        self,
        query: str,
        days_back: int = 7,
        num_results: int = 10
    ) -> List[SearchResult]:
        """
        Search for recent news articles.

        Args:
            query: Search query for news content
            days_back: Number of days to look back (default: 7)
            num_results: Maximum results to return (default: 10)

        Returns:
            List of SearchResult objects for news articles

        Raises:
            ExaSearchError: If search fails
        """
        # Calculate date range
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days_back)

        start_str = start_date.strftime("%Y-%m-%d")
        end_str = end_date.strftime("%Y-%m-%d")

        # Check cache first
        cache_params = {
            "num_results": num_results,
            "type": "news",
            "days_back": days_back
        }
        cached = self.cache.get("search_news", query, cache_params)
        if cached is not None:
            return [SearchResult.from_dict(r) for r in cached]

        # News domains to prioritize
        news_domains = [
            "reuters.com",
            "apnews.com",
            "bbc.com",
            "cnn.com",
            "nytimes.com",
            "washingtonpost.com",
            "theguardian.com",
            "techcrunch.com",
            "wired.com",
            "arstechnica.com",
            "theverge.com",
            "bloomberg.com"
        ]

        payload = {
            "query": query,
            "numResults": num_results,
            "useAutoprompt": True,
            "type": "neural",
            "includeDomains": news_domains,
            "startPublishedDate": start_str,
            "endPublishedDate": end_str,
            "contents": {
                "text": {"maxCharacters": 1000},
                "highlights": {"numSentences": 3}
            }
        }

        response = self._request_with_retry("/search", payload)
        results = self._parse_results(response)

        # Cache results
        self.cache.set("search_news", query, [r.to_dict() for r in results], cache_params)

        return results

    def get_contents(self, urls: List[str]) -> List[DocumentContent]:
        """
        Extract content from URLs.

        Args:
            urls: List of URLs to extract content from

        Returns:
            List of DocumentContent objects

        Raises:
            ExaSearchError: If extraction fails
        """
        if not urls:
            return []

        # Check cache for each URL
        cached_contents = []
        uncached_urls = []

        for url in urls:
            cached = self.cache.get("get_contents", url)
            if cached is not None:
                cached_contents.append(DocumentContent.from_dict(cached))
            else:
                uncached_urls.append(url)

        if not uncached_urls:
            return cached_contents

        payload = {
            "urls": uncached_urls,
            "text": {"maxCharacters": 5000}
        }

        response = self._request_with_retry("/contents", payload)

        contents = []
        for item in response.get("results", []):
            content = DocumentContent(
                url=item.get("url", ""),
                title=item.get("title", ""),
                text=item.get("text", ""),
                author=item.get("author"),
                published_date=item.get("publishedDate")
            )
            contents.append(content)

            # Cache individual content
            self.cache.set("get_contents", content.url, content.to_dict())

        return cached_contents + contents

    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        return self.cache.get_stats()

    def clear_cache(self):
        """Clear result cache."""
        self.cache.clear()


# CLI interface
def main():
    """Command-line interface for Exa search."""
    import argparse

    parser = argparse.ArgumentParser(description="Exa.ai Search CLI")
    parser.add_argument("command", choices=["search", "academic", "news", "contents", "stats"],
                        help="Command to execute")
    parser.add_argument("query", nargs="?", help="Search query or URL")
    parser.add_argument("--num-results", "-n", type=int, default=10,
                        help="Maximum results to return")
    parser.add_argument("--days-back", "-d", type=int, default=7,
                        help="Days back for news search")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    parser.add_argument("--urls", nargs="+", help="URLs for contents command")

    args = parser.parse_args()

    client = ExaSearchClient()

    if not client.is_available() and args.command != "stats":
        print("Error: EXA_API_KEY environment variable not set", file=sys.stderr)
        return 1

    try:
        if args.command == "search":
            if not args.query:
                print("Error: query required for 'search' command", file=sys.stderr)
                return 1

            results = client.search(args.query, num_results=args.num_results)

            if args.json:
                output = {
                    "query": args.query,
                    "count": len(results),
                    "results": [r.to_dict() for r in results]
                }
                print(json.dumps(output, indent=2))
            else:
                print(f"\nExa Search Results for: {args.query}")
                print(f"Found {len(results)} results\n")

                for idx, result in enumerate(results, 1):
                    print(f"{idx}. {result.title}")
                    print(f"   URL: {result.url}")
                    print(f"   Score: {result.score:.3f}")
                    print(f"   Snippet: {result.snippet[:150]}...")
                    if result.published_date:
                        print(f"   Published: {result.published_date}")
                    print()

        elif args.command == "academic":
            if not args.query:
                print("Error: query required for 'academic' command", file=sys.stderr)
                return 1

            results = client.search_academic(args.query, num_results=args.num_results)

            if args.json:
                output = {
                    "query": args.query,
                    "type": "academic",
                    "count": len(results),
                    "results": [r.to_dict() for r in results]
                }
                print(json.dumps(output, indent=2))
            else:
                print(f"\nAcademic Search Results for: {args.query}")
                print(f"Found {len(results)} results\n")

                for idx, result in enumerate(results, 1):
                    print(f"{idx}. {result.title}")
                    print(f"   URL: {result.url}")
                    print(f"   Score: {result.score:.3f}")
                    if result.author:
                        print(f"   Author: {result.author}")
                    if result.published_date:
                        print(f"   Published: {result.published_date}")
                    print()

        elif args.command == "news":
            if not args.query:
                print("Error: query required for 'news' command", file=sys.stderr)
                return 1

            results = client.search_news(args.query, days_back=args.days_back,
                                         num_results=args.num_results)

            if args.json:
                output = {
                    "query": args.query,
                    "type": "news",
                    "days_back": args.days_back,
                    "count": len(results),
                    "results": [r.to_dict() for r in results]
                }
                print(json.dumps(output, indent=2))
            else:
                print(f"\nNews Search Results for: {args.query}")
                print(f"Found {len(results)} results (last {args.days_back} days)\n")

                for idx, result in enumerate(results, 1):
                    print(f"{idx}. {result.title}")
                    print(f"   URL: {result.url}")
                    if result.published_date:
                        print(f"   Published: {result.published_date}")
                    print(f"   Snippet: {result.snippet[:150]}...")
                    print()

        elif args.command == "contents":
            urls = args.urls or ([args.query] if args.query else [])
            if not urls:
                print("Error: URLs required for 'contents' command", file=sys.stderr)
                return 1

            contents = client.get_contents(urls)

            if args.json:
                output = {
                    "urls": urls,
                    "count": len(contents),
                    "contents": [c.to_dict() for c in contents]
                }
                print(json.dumps(output, indent=2))
            else:
                print(f"\nExtracted Content from {len(urls)} URLs\n")

                for content in contents:
                    print(f"Title: {content.title}")
                    print(f"URL: {content.url}")
                    if content.author:
                        print(f"Author: {content.author}")
                    print(f"Text: {content.text[:500]}...")
                    print()

        elif args.command == "stats":
            stats = client.get_cache_stats()

            if args.json:
                print(json.dumps(stats, indent=2))
            else:
                print("\nExa Search Cache Statistics")
                print("=" * 40)
                print(f"Hits:          {stats['hits']}")
                print(f"Misses:        {stats['misses']}")
                print(f"Hit Rate:      {stats['hit_rate']:.1%}")
                print(f"Entry Count:   {stats['entry_count']}")
                print(f"Max Entries:   {stats['max_entries']}")
                print(f"TTL:           {stats['ttl_seconds']} seconds")
                print()

        return 0

    except ExaSearchError as e:
        print(f"Error: {str(e)}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
