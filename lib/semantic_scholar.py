#!/usr/bin/env python3
"""
Semantic Scholar API Integration

Provides academic paper search and metadata retrieval via Semantic Scholar API.
Features:
- Paper search by keyword/query
- Paper details by ID (S2 ID, DOI, arXiv ID, etc.)
- Citation and reference traversal
- Author information and papers
- Rate limiting (100 req/5min without key, 1000 with key)
- Caching with 24-hour TTL

This serves as a backup academic search provider after Exa.ai.
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
from urllib.parse import quote
import requests


@dataclass
class Author:
    """Semantic Scholar author data."""
    author_id: str
    name: str
    affiliation: Optional[str] = None
    h_index: Optional[int] = None
    paper_count: Optional[int] = None
    citation_count: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "author_id": self.author_id,
            "name": self.name,
            "affiliation": self.affiliation,
            "h_index": self.h_index,
            "paper_count": self.paper_count,
            "citation_count": self.citation_count
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Author":
        """Create Author from dictionary."""
        return cls(
            author_id=data.get("author_id", data.get("authorId", "")),
            name=data.get("name", ""),
            affiliation=data.get("affiliation"),
            h_index=data.get("h_index", data.get("hIndex")),
            paper_count=data.get("paper_count", data.get("paperCount")),
            citation_count=data.get("citation_count", data.get("citationCount"))
        )

    @classmethod
    def from_api_response(cls, data: Dict[str, Any]) -> "Author":
        """Create Author from Semantic Scholar API response."""
        return cls(
            author_id=data.get("authorId", ""),
            name=data.get("name", ""),
            affiliation=data.get("affiliations", [None])[0] if data.get("affiliations") else None,
            h_index=data.get("hIndex"),
            paper_count=data.get("paperCount"),
            citation_count=data.get("citationCount")
        )


@dataclass
class Paper:
    """Semantic Scholar paper data."""
    paper_id: str
    title: str
    abstract: Optional[str] = None
    authors: List[Author] = field(default_factory=list)
    year: Optional[int] = None
    citation_count: Optional[int] = None
    venue: Optional[str] = None
    url: Optional[str] = None
    fields_of_study: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "paper_id": self.paper_id,
            "title": self.title,
            "abstract": self.abstract,
            "authors": [a.to_dict() for a in self.authors],
            "year": self.year,
            "citation_count": self.citation_count,
            "venue": self.venue,
            "url": self.url,
            "fields_of_study": self.fields_of_study
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Paper":
        """Create Paper from dictionary."""
        authors = [Author.from_dict(a) for a in data.get("authors", [])]
        return cls(
            paper_id=data.get("paper_id", data.get("paperId", "")),
            title=data.get("title", ""),
            abstract=data.get("abstract"),
            authors=authors,
            year=data.get("year"),
            citation_count=data.get("citation_count", data.get("citationCount")),
            venue=data.get("venue"),
            url=data.get("url"),
            fields_of_study=data.get("fields_of_study", data.get("fieldsOfStudy", []))
        )

    @classmethod
    def from_api_response(cls, data: Dict[str, Any]) -> "Paper":
        """Create Paper from Semantic Scholar API response."""
        # Parse authors
        authors = []
        for author_data in data.get("authors", []):
            authors.append(Author(
                author_id=author_data.get("authorId", ""),
                name=author_data.get("name", "")
            ))

        return cls(
            paper_id=data.get("paperId", ""),
            title=data.get("title", ""),
            abstract=data.get("abstract"),
            authors=authors,
            year=data.get("year"),
            citation_count=data.get("citationCount"),
            venue=data.get("venue"),
            url=data.get("url"),
            fields_of_study=data.get("fieldsOfStudy") or []
        )


class SemanticScholarError(Exception):
    """Exception for Semantic Scholar API errors."""
    pass


class RateLimiter:
    """
    Sliding window rate limiter for Semantic Scholar API.

    Limits:
    - Without API key: 100 requests per 5 minutes
    - With API key: 1000 requests per 5 minutes
    """

    def __init__(self, has_api_key: bool = False):
        """
        Initialize rate limiter.

        Args:
            has_api_key: Whether API key is configured (higher limits)
        """
        self.window_seconds = 300  # 5 minutes
        self.max_requests = 1000 if has_api_key else 100
        self.requests: List[float] = []
        self.lock = threading.Lock()

    def acquire(self) -> float:
        """
        Acquire permission to make a request.

        Returns:
            Wait time in seconds (0 if no wait needed)
        """
        with self.lock:
            now = time.monotonic()

            # Remove requests outside the window
            cutoff = now - self.window_seconds
            self.requests = [t for t in self.requests if t > cutoff]

            if len(self.requests) < self.max_requests:
                self.requests.append(now)
                return 0.0

            # Need to wait until oldest request falls out of window
            oldest = min(self.requests)
            wait_time = oldest + self.window_seconds - now
            return max(0.0, wait_time)

    def wait(self):
        """Wait for permission to make a request."""
        wait_time = self.acquire()
        if wait_time > 0:
            time.sleep(wait_time)
            # Re-acquire after waiting
            self.acquire()


class ResultCache:
    """
    In-memory cache for Semantic Scholar results with TTL expiration.

    Uses 24-hour TTL by default (as academic data changes slowly).
    """

    def __init__(self, ttl_seconds: int = 86400, max_entries: int = 1000):
        """
        Initialize result cache.

        Args:
            ttl_seconds: Time-to-live for cache entries (default: 24 hours)
            max_entries: Maximum number of cached entries (default: 1000)
        """
        self.ttl_seconds = ttl_seconds
        self.max_entries = max_entries
        self.cache: Dict[str, tuple] = {}  # key -> (value, timestamp)
        self.lock = threading.Lock()
        self.stats = {"hits": 0, "misses": 0}

    def _make_key(self, method: str, identifier: str, params: Optional[Dict] = None) -> str:
        """Generate cache key from method, identifier, and parameters."""
        key_input = f"{method}:{identifier}"
        if params:
            sorted_params = sorted(params.items())
            key_input += f":{json.dumps(sorted_params, sort_keys=True)}"
        return hashlib.sha256(key_input.encode()).hexdigest()[:32]

    def get(self, method: str, identifier: str, params: Optional[Dict] = None) -> Optional[Any]:
        """
        Retrieve cached result.

        Args:
            method: API method name
            identifier: Query or ID
            params: Additional parameters

        Returns:
            Cached value or None if not found/expired
        """
        key = self._make_key(method, identifier, params)

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

    def set(self, method: str, identifier: str, value: Any, params: Optional[Dict] = None):
        """
        Store result in cache.

        Args:
            method: API method name
            identifier: Query or ID
            value: Value to cache
            params: Additional parameters
        """
        key = self._make_key(method, identifier, params)

        with self.lock:
            # Evict oldest entries if at capacity
            if len(self.cache) >= self.max_entries:
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


class SemanticScholarClient:
    """
    Client for Semantic Scholar API.

    Provides academic paper search and metadata retrieval with:
    - Paper search by keyword
    - Paper details by various IDs (S2, DOI, arXiv, etc.)
    - Citation and reference traversal
    - Author information

    Features:
    - Rate limiting (respects API limits)
    - Exponential backoff retry logic
    - Result caching (24 hour TTL)
    """

    BASE_URL = "https://api.semanticscholar.org/graph/v1"

    # Fields to request for papers
    PAPER_FIELDS = [
        "paperId", "title", "abstract", "authors", "year",
        "citationCount", "venue", "url", "fieldsOfStudy"
    ]

    # Fields to request for authors
    AUTHOR_FIELDS = [
        "authorId", "name", "affiliations", "hIndex",
        "paperCount", "citationCount"
    ]

    def __init__(
        self,
        api_key: Optional[str] = None,
        cache_ttl: int = 86400,
        max_retries: int = 3,
        timeout: int = 30
    ):
        """
        Initialize Semantic Scholar client.

        Args:
            api_key: API key (default: from SEMANTIC_SCHOLAR_API_KEY env var)
            cache_ttl: Cache TTL in seconds (default: 86400 = 24 hours)
            max_retries: Maximum retry attempts (default: 3)
            timeout: Request timeout in seconds (default: 30)
        """
        self.api_key = api_key or os.getenv("SEMANTIC_SCHOLAR_API_KEY")
        self.rate_limiter = RateLimiter(has_api_key=bool(self.api_key))
        self.cache = ResultCache(ttl_seconds=cache_ttl)
        self.max_retries = max_retries
        self.timeout = timeout
        self.session = requests.Session()

    def is_available(self) -> bool:
        """
        Check if client is available.

        Note: Semantic Scholar API works without a key, just with lower rate limits.
        Returns True always since basic access is available.
        """
        return True

    def has_api_key(self) -> bool:
        """Check if API key is configured (for higher rate limits)."""
        return bool(self.api_key)

    def _get_headers(self) -> Dict[str, str]:
        """Get request headers with optional authentication."""
        headers = {
            "Content-Type": "application/json"
        }
        if self.api_key:
            headers["x-api-key"] = self.api_key
        return headers

    def _request_with_retry(
        self,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        method: str = "GET"
    ) -> Dict[str, Any]:
        """
        Make API request with rate limiting and retry logic.

        Args:
            endpoint: API endpoint path
            params: Query parameters
            method: HTTP method (default: GET)

        Returns:
            API response as dictionary

        Raises:
            SemanticScholarError: If request fails after retries
        """
        url = f"{self.BASE_URL}{endpoint}"
        headers = self._get_headers()

        last_error = None

        for attempt in range(self.max_retries):
            # Apply rate limiting
            self.rate_limiter.wait()

            try:
                if method.upper() == "GET":
                    response = self.session.get(
                        url,
                        params=params,
                        headers=headers,
                        timeout=self.timeout
                    )
                else:
                    response = self.session.post(
                        url,
                        json=params,
                        headers=headers,
                        timeout=self.timeout
                    )

                # Check for rate limit response
                if response.status_code == 429:
                    retry_after = int(response.headers.get("Retry-After", 60))
                    time.sleep(retry_after)
                    continue

                # Check for server errors (retry)
                if response.status_code >= 500:
                    last_error = f"Server error: {response.status_code}"
                    time.sleep(2 ** attempt)
                    continue

                # Check for not found
                if response.status_code == 404:
                    raise SemanticScholarError("Resource not found")

                # Check for client errors (don't retry)
                if response.status_code >= 400:
                    error_msg = response.text
                    try:
                        error_data = response.json()
                        error_msg = error_data.get("message", error_msg)
                    except json.JSONDecodeError:
                        pass
                    raise SemanticScholarError(f"API error {response.status_code}: {error_msg}")

                return response.json()

            except requests.exceptions.Timeout:
                last_error = "Request timeout"
                time.sleep(2 ** attempt)
            except requests.exceptions.RequestException as e:
                last_error = str(e)
                time.sleep(2 ** attempt)

        raise SemanticScholarError(f"Request failed after {self.max_retries} retries: {last_error}")

    def search_papers(self, query: str, limit: int = 10) -> List[Paper]:
        """
        Search for papers by keyword query.

        Args:
            query: Search query string
            limit: Maximum results to return (default: 10, max: 100)

        Returns:
            List of Paper objects ordered by relevance

        Raises:
            SemanticScholarError: If search fails
        """
        limit = min(limit, 100)  # API maximum

        # Check cache
        cache_params = {"limit": limit}
        cached = self.cache.get("search_papers", query, cache_params)
        if cached is not None:
            return [Paper.from_dict(p) for p in cached]

        params = {
            "query": query,
            "limit": limit,
            "fields": ",".join(self.PAPER_FIELDS)
        }

        response = self._request_with_retry("/paper/search", params)

        papers = []
        for item in response.get("data", []):
            papers.append(Paper.from_api_response(item))

        # Cache results
        self.cache.set("search_papers", query, [p.to_dict() for p in papers], cache_params)

        return papers

    def get_paper(self, paper_id: str) -> Paper:
        """
        Get paper details by ID.

        Supports various ID formats:
        - Semantic Scholar ID: "649def34f8be52c8b66281af98ae884c09aef38b"
        - DOI: "DOI:10.1038/nrn3241"
        - arXiv: "arXiv:1705.10311"
        - PMID: "PMID:19872477"
        - ACL: "ACL:P18-1144"

        Args:
            paper_id: Paper identifier

        Returns:
            Paper object with full details

        Raises:
            SemanticScholarError: If paper not found or request fails
        """
        # Check cache
        cached = self.cache.get("get_paper", paper_id)
        if cached is not None:
            return Paper.from_dict(cached)

        params = {
            "fields": ",".join(self.PAPER_FIELDS)
        }

        # URL-encode the paper ID for DOI and other IDs with special chars
        encoded_id = quote(paper_id, safe="")
        response = self._request_with_retry(f"/paper/{encoded_id}", params)

        paper = Paper.from_api_response(response)

        # Cache result
        self.cache.set("get_paper", paper_id, paper.to_dict())

        return paper

    def get_citations(self, paper_id: str, limit: int = 100) -> List[Paper]:
        """
        Get papers that cite the given paper.

        Args:
            paper_id: Paper identifier
            limit: Maximum results to return (default: 100, max: 1000)

        Returns:
            List of Paper objects that cite this paper

        Raises:
            SemanticScholarError: If paper not found or request fails
        """
        limit = min(limit, 1000)  # API maximum

        # Check cache
        cache_params = {"limit": limit}
        cached = self.cache.get("get_citations", paper_id, cache_params)
        if cached is not None:
            return [Paper.from_dict(p) for p in cached]

        params = {
            "limit": limit,
            "fields": ",".join([f"citingPaper.{f}" for f in self.PAPER_FIELDS])
        }

        encoded_id = quote(paper_id, safe="")
        response = self._request_with_retry(f"/paper/{encoded_id}/citations", params)

        papers = []
        for item in response.get("data", []):
            citing_paper = item.get("citingPaper", {})
            if citing_paper:
                papers.append(Paper.from_api_response(citing_paper))

        # Cache results
        self.cache.set("get_citations", paper_id, [p.to_dict() for p in papers], cache_params)

        return papers

    def get_references(self, paper_id: str, limit: int = 100) -> List[Paper]:
        """
        Get papers referenced by the given paper.

        Args:
            paper_id: Paper identifier
            limit: Maximum results to return (default: 100, max: 1000)

        Returns:
            List of Paper objects referenced by this paper

        Raises:
            SemanticScholarError: If paper not found or request fails
        """
        limit = min(limit, 1000)  # API maximum

        # Check cache
        cache_params = {"limit": limit}
        cached = self.cache.get("get_references", paper_id, cache_params)
        if cached is not None:
            return [Paper.from_dict(p) for p in cached]

        params = {
            "limit": limit,
            "fields": ",".join([f"citedPaper.{f}" for f in self.PAPER_FIELDS])
        }

        encoded_id = quote(paper_id, safe="")
        response = self._request_with_retry(f"/paper/{encoded_id}/references", params)

        papers = []
        for item in response.get("data", []):
            cited_paper = item.get("citedPaper", {})
            if cited_paper:
                papers.append(Paper.from_api_response(cited_paper))

        # Cache results
        self.cache.set("get_references", paper_id, [p.to_dict() for p in papers], cache_params)

        return papers

    def get_author(self, author_id: str) -> Author:
        """
        Get author details by ID.

        Args:
            author_id: Semantic Scholar author ID

        Returns:
            Author object with full details

        Raises:
            SemanticScholarError: If author not found or request fails
        """
        # Check cache
        cached = self.cache.get("get_author", author_id)
        if cached is not None:
            return Author.from_dict(cached)

        params = {
            "fields": ",".join(self.AUTHOR_FIELDS)
        }

        response = self._request_with_retry(f"/author/{author_id}", params)

        author = Author.from_api_response(response)

        # Cache result
        self.cache.set("get_author", author_id, author.to_dict())

        return author

    def search_by_author(self, author_name: str, limit: int = 100) -> List[Paper]:
        """
        Search for papers by author name.

        Uses the paper search API with author filter.

        Args:
            author_name: Author name to search for
            limit: Maximum results to return (default: 100)

        Returns:
            List of Paper objects by the author

        Raises:
            SemanticScholarError: If search fails
        """
        # First search for the author
        author_query = f"author:{author_name}"
        return self.search_papers(author_query, limit=limit)

    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        return self.cache.get_stats()

    def clear_cache(self):
        """Clear result cache."""
        self.cache.clear()


# CLI interface
def main():
    """Command-line interface for Semantic Scholar search."""
    import argparse

    parser = argparse.ArgumentParser(description="Semantic Scholar API CLI")
    parser.add_argument("command", choices=["search", "paper", "citations", "references", "author", "stats"],
                        help="Command to execute")
    parser.add_argument("query", nargs="?", help="Search query or ID")
    parser.add_argument("--limit", "-n", type=int, default=10,
                        help="Maximum results to return")
    parser.add_argument("--json", action="store_true", help="Output as JSON")

    args = parser.parse_args()

    client = SemanticScholarClient()

    try:
        if args.command == "search":
            if not args.query:
                print("Error: query required for 'search' command", file=sys.stderr)
                return 1

            papers = client.search_papers(args.query, limit=args.limit)

            if args.json:
                output = {
                    "query": args.query,
                    "count": len(papers),
                    "papers": [p.to_dict() for p in papers]
                }
                print(json.dumps(output, indent=2))
            else:
                print(f"\nSemantic Scholar Search Results for: {args.query}")
                print(f"Found {len(papers)} papers\n")

                for idx, paper in enumerate(papers, 1):
                    print(f"{idx}. {paper.title}")
                    if paper.authors:
                        authors = ", ".join(a.name for a in paper.authors[:3])
                        if len(paper.authors) > 3:
                            authors += f" et al."
                        print(f"   Authors: {authors}")
                    if paper.year:
                        print(f"   Year: {paper.year}")
                    if paper.citation_count is not None:
                        print(f"   Citations: {paper.citation_count}")
                    if paper.venue:
                        print(f"   Venue: {paper.venue}")
                    if paper.url:
                        print(f"   URL: {paper.url}")
                    print()

        elif args.command == "paper":
            if not args.query:
                print("Error: paper ID required for 'paper' command", file=sys.stderr)
                return 1

            paper = client.get_paper(args.query)

            if args.json:
                print(json.dumps(paper.to_dict(), indent=2))
            else:
                print(f"\nPaper: {paper.title}")
                print("=" * 60)
                if paper.authors:
                    authors = ", ".join(a.name for a in paper.authors)
                    print(f"Authors: {authors}")
                if paper.year:
                    print(f"Year: {paper.year}")
                if paper.venue:
                    print(f"Venue: {paper.venue}")
                if paper.citation_count is not None:
                    print(f"Citations: {paper.citation_count}")
                if paper.fields_of_study:
                    print(f"Fields: {', '.join(paper.fields_of_study)}")
                if paper.url:
                    print(f"URL: {paper.url}")
                if paper.abstract:
                    print(f"\nAbstract:\n{paper.abstract}")
                print()

        elif args.command == "citations":
            if not args.query:
                print("Error: paper ID required for 'citations' command", file=sys.stderr)
                return 1

            papers = client.get_citations(args.query, limit=args.limit)

            if args.json:
                output = {
                    "paper_id": args.query,
                    "citation_count": len(papers),
                    "citations": [p.to_dict() for p in papers]
                }
                print(json.dumps(output, indent=2))
            else:
                print(f"\nCitations for paper: {args.query}")
                print(f"Found {len(papers)} citing papers\n")

                for idx, paper in enumerate(papers, 1):
                    print(f"{idx}. {paper.title} ({paper.year or 'N/A'})")
                    if paper.authors:
                        print(f"   Authors: {paper.authors[0].name if paper.authors else 'Unknown'}")
                    print()

        elif args.command == "references":
            if not args.query:
                print("Error: paper ID required for 'references' command", file=sys.stderr)
                return 1

            papers = client.get_references(args.query, limit=args.limit)

            if args.json:
                output = {
                    "paper_id": args.query,
                    "reference_count": len(papers),
                    "references": [p.to_dict() for p in papers]
                }
                print(json.dumps(output, indent=2))
            else:
                print(f"\nReferences for paper: {args.query}")
                print(f"Found {len(papers)} referenced papers\n")

                for idx, paper in enumerate(papers, 1):
                    print(f"{idx}. {paper.title} ({paper.year or 'N/A'})")
                    if paper.authors:
                        print(f"   Authors: {paper.authors[0].name if paper.authors else 'Unknown'}")
                    print()

        elif args.command == "author":
            if not args.query:
                print("Error: author ID required for 'author' command", file=sys.stderr)
                return 1

            author = client.get_author(args.query)

            if args.json:
                print(json.dumps(author.to_dict(), indent=2))
            else:
                print(f"\nAuthor: {author.name}")
                print("=" * 60)
                if author.affiliation:
                    print(f"Affiliation: {author.affiliation}")
                if author.h_index is not None:
                    print(f"h-index: {author.h_index}")
                if author.paper_count is not None:
                    print(f"Papers: {author.paper_count}")
                if author.citation_count is not None:
                    print(f"Citations: {author.citation_count}")
                print()

        elif args.command == "stats":
            stats = client.get_cache_stats()

            if args.json:
                print(json.dumps(stats, indent=2))
            else:
                print("\nSemantic Scholar Cache Statistics")
                print("=" * 40)
                print(f"Hits:          {stats['hits']}")
                print(f"Misses:        {stats['misses']}")
                print(f"Hit Rate:      {stats['hit_rate']:.1%}")
                print(f"Entry Count:   {stats['entry_count']}")
                print(f"Max Entries:   {stats['max_entries']}")
                print(f"TTL:           {stats['ttl_seconds']} seconds")
                print(f"API Key:       {'Configured' if client.has_api_key() else 'Not configured'}")
                print()

        return 0

    except SemanticScholarError as e:
        print(f"Error: {str(e)}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
