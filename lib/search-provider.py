#!/usr/bin/env python3
"""
Search Provider Abstraction

Provides unified interface for multiple search backends with automatic fallback.
Primary: Tavily API (https://tavily.com)
Fallbacks: DuckDuckGo, SerpAPI

Supports structured results with relevance scoring and caching.
"""

import os
import sys
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Optional
from datetime import datetime
import json


@dataclass
class SearchResult:
    """Structured search result with metadata."""
    title: str
    url: str
    snippet: str
    relevance_score: float  # 0.0-1.0
    source: str  # Provider name (e.g., "tavily", "duckduckgo")
    published_date: Optional[str] = None
    domain: Optional[str] = None


class SearchProvider(ABC):
    """Abstract base class for search providers."""

    def __init__(self, max_results: int = 10):
        self.max_results = max_results
        self.name = self.__class__.__name__.replace("Provider", "").lower()

    @abstractmethod
    def search(self, query: str, max_results: Optional[int] = None) -> List[SearchResult]:
        """
        Execute search query and return structured results.

        Args:
            query: Search query string
            max_results: Maximum results to return (None = use self.max_results)

        Returns:
            List of SearchResult objects ordered by relevance

        Raises:
            SearchProviderError: If search fails
        """
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """Check if provider is configured and available."""
        pass


class SearchProviderError(Exception):
    """Base exception for search provider errors."""
    pass


class TavilyProvider(SearchProvider):
    """Tavily search API provider (primary)."""

    def __init__(self, api_key: Optional[str] = None, max_results: int = 10):
        super().__init__(max_results)
        self.api_key = api_key or os.getenv("TAVILY_API_KEY")

    def is_available(self) -> bool:
        """Check if Tavily API key is configured."""
        return bool(self.api_key)

    def search(self, query: str, max_results: Optional[int] = None) -> List[SearchResult]:
        """
        Execute search using Tavily API.

        Args:
            query: Search query string
            max_results: Maximum results to return

        Returns:
            List of SearchResult objects

        Raises:
            SearchProviderError: If API call fails
        """
        if not self.is_available():
            raise SearchProviderError("Tavily API key not configured")

        limit = max_results or self.max_results

        try:
            # Import tavily only when needed
            try:
                from tavily import TavilyClient
            except ImportError:
                raise SearchProviderError("tavily package not installed. Run: pip install tavily-python")

            client = TavilyClient(api_key=self.api_key)
            response = client.search(query=query, max_results=limit)

            results = []
            for idx, item in enumerate(response.get("results", [])):
                # Tavily provides relevance scores
                score = item.get("score", 0.5)

                # Extract domain from URL
                from urllib.parse import urlparse
                domain = urlparse(item.get("url", "")).netloc

                result = SearchResult(
                    title=item.get("title", ""),
                    url=item.get("url", ""),
                    snippet=item.get("content", ""),
                    relevance_score=float(score),
                    source="tavily",
                    published_date=item.get("published_date"),
                    domain=domain
                )
                results.append(result)

            return results

        except Exception as e:
            raise SearchProviderError(f"Tavily search failed: {str(e)}")


class DuckDuckGoProvider(SearchProvider):
    """DuckDuckGo search provider (fallback)."""

    def is_available(self) -> bool:
        """DuckDuckGo is always available (no API key needed)."""
        return True

    def search(self, query: str, max_results: Optional[int] = None) -> List[SearchResult]:
        """
        Execute search using DuckDuckGo.

        Args:
            query: Search query string
            max_results: Maximum results to return

        Returns:
            List of SearchResult objects

        Raises:
            SearchProviderError: If search fails
        """
        limit = max_results or self.max_results

        try:
            # Import duckduckgo_search only when needed
            try:
                from duckduckgo_search import DDGS
            except ImportError:
                raise SearchProviderError("duckduckgo-search package not installed. Run: pip install duckduckgo-search")

            with DDGS() as ddgs:
                search_results = list(ddgs.text(query, max_results=limit))

            results = []
            for idx, item in enumerate(search_results):
                # DuckDuckGo doesn't provide scores, estimate based on rank
                score = 1.0 - (idx * 0.1)  # Decaying score: 1.0, 0.9, 0.8...
                score = max(score, 0.1)  # Floor at 0.1

                # Extract domain from URL
                from urllib.parse import urlparse
                domain = urlparse(item.get("href", "")).netloc

                result = SearchResult(
                    title=item.get("title", ""),
                    url=item.get("href", ""),
                    snippet=item.get("body", ""),
                    relevance_score=score,
                    source="duckduckgo",
                    domain=domain
                )
                results.append(result)

            return results

        except Exception as e:
            raise SearchProviderError(f"DuckDuckGo search failed: {str(e)}")


class SerpAPIProvider(SearchProvider):
    """SerpAPI search provider (fallback)."""

    def __init__(self, api_key: Optional[str] = None, max_results: int = 10):
        super().__init__(max_results)
        self.api_key = api_key or os.getenv("SERPAPI_API_KEY")

    def is_available(self) -> bool:
        """Check if SerpAPI key is configured."""
        return bool(self.api_key)

    def search(self, query: str, max_results: Optional[int] = None) -> List[SearchResult]:
        """
        Execute search using SerpAPI (Google).

        Args:
            query: Search query string
            max_results: Maximum results to return

        Returns:
            List of SearchResult objects

        Raises:
            SearchProviderError: If API call fails
        """
        if not self.is_available():
            raise SearchProviderError("SerpAPI key not configured")

        limit = max_results or self.max_results

        try:
            # Import serpapi only when needed
            try:
                from serpapi import GoogleSearch
            except ImportError:
                raise SearchProviderError("google-search-results package not installed. Run: pip install google-search-results")

            params = {
                "q": query,
                "api_key": self.api_key,
                "num": limit
            }

            search = GoogleSearch(params)
            response = search.get_dict()

            results = []
            for idx, item in enumerate(response.get("organic_results", [])):
                # SerpAPI doesn't provide scores, estimate based on rank
                score = 1.0 - (idx * 0.08)  # Decaying score
                score = max(score, 0.2)  # Floor at 0.2

                # Extract domain from URL
                from urllib.parse import urlparse
                domain = urlparse(item.get("link", "")).netloc

                result = SearchResult(
                    title=item.get("title", ""),
                    url=item.get("link", ""),
                    snippet=item.get("snippet", ""),
                    relevance_score=score,
                    source="serpapi",
                    domain=domain
                )
                results.append(result)

            return results

        except Exception as e:
            raise SearchProviderError(f"SerpAPI search failed: {str(e)}")


class ExaProvider(SearchProvider):
    """
    Exa.ai neural search provider.

    Provides semantic search with support for:
    - General web search
    - Academic paper search
    - News search with date filtering

    Features rate limiting, caching, and retry logic.
    """

    def __init__(self, api_key: Optional[str] = None, max_results: int = 10):
        super().__init__(max_results)
        self.api_key = api_key or os.getenv("EXA_API_KEY")
        self._client = None

    def _get_client(self):
        """Get or create ExaSearchClient instance."""
        if self._client is None:
            # Import exa_search module
            try:
                import importlib.util
                exa_path = os.path.join(os.path.dirname(__file__), "exa_search.py")
                spec = importlib.util.spec_from_file_location("exa_search", exa_path)
                exa_module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(exa_module)
                self._client = exa_module.ExaSearchClient(api_key=self.api_key)
            except Exception as e:
                raise SearchProviderError(f"Failed to load exa_search module: {str(e)}")
        return self._client

    def is_available(self) -> bool:
        """Check if Exa API key is configured."""
        return bool(self.api_key)

    def search(self, query: str, max_results: Optional[int] = None) -> List[SearchResult]:
        """
        Execute search using Exa.ai neural search.

        Args:
            query: Search query string
            max_results: Maximum results to return

        Returns:
            List of SearchResult objects

        Raises:
            SearchProviderError: If API call fails
        """
        if not self.is_available():
            raise SearchProviderError("EXA_API_KEY not configured")

        limit = max_results or self.max_results

        try:
            client = self._get_client()
            exa_results = client.search(query, num_results=limit)

            # Convert Exa results to SearchResult format
            results = []
            for item in exa_results:
                # Extract domain from URL
                from urllib.parse import urlparse
                domain = urlparse(item.url).netloc

                result = SearchResult(
                    title=item.title,
                    url=item.url,
                    snippet=item.snippet,
                    relevance_score=item.score,
                    source="exa",
                    published_date=item.published_date,
                    domain=domain
                )
                results.append(result)

            return results

        except Exception as e:
            raise SearchProviderError(f"Exa search failed: {str(e)}")

    def search_academic(self, query: str, max_results: Optional[int] = None) -> List[SearchResult]:
        """
        Search for academic papers using Exa neural search.

        Args:
            query: Search query optimized for academic content
            max_results: Maximum results to return

        Returns:
            List of SearchResult objects for academic content

        Raises:
            SearchProviderError: If search fails
        """
        if not self.is_available():
            raise SearchProviderError("EXA_API_KEY not configured")

        limit = max_results or self.max_results

        try:
            client = self._get_client()
            exa_results = client.search_academic(query, num_results=limit)

            results = []
            for item in exa_results:
                from urllib.parse import urlparse
                domain = urlparse(item.url).netloc

                result = SearchResult(
                    title=item.title,
                    url=item.url,
                    snippet=item.snippet,
                    relevance_score=item.score,
                    source="exa",
                    published_date=item.published_date,
                    domain=domain
                )
                results.append(result)

            return results

        except Exception as e:
            raise SearchProviderError(f"Exa academic search failed: {str(e)}")

    def search_news(self, query: str, days_back: int = 7, max_results: Optional[int] = None) -> List[SearchResult]:
        """
        Search for recent news using Exa.

        Args:
            query: Search query for news content
            days_back: Number of days to look back (default: 7)
            max_results: Maximum results to return

        Returns:
            List of SearchResult objects for news articles

        Raises:
            SearchProviderError: If search fails
        """
        if not self.is_available():
            raise SearchProviderError("EXA_API_KEY not configured")

        limit = max_results or self.max_results

        try:
            client = self._get_client()
            exa_results = client.search_news(query, days_back=days_back, num_results=limit)

            results = []
            for item in exa_results:
                from urllib.parse import urlparse
                domain = urlparse(item.url).netloc

                result = SearchResult(
                    title=item.title,
                    url=item.url,
                    snippet=item.snippet,
                    relevance_score=item.score,
                    source="exa",
                    published_date=item.published_date,
                    domain=domain
                )
                results.append(result)

            return results

        except Exception as e:
            raise SearchProviderError(f"Exa news search failed: {str(e)}")


class SemanticScholarProvider(SearchProvider):
    """
    Semantic Scholar academic search provider.

    Provides academic paper search using the Semantic Scholar API.
    Serves as backup for Exa.ai academic search with:
    - Paper search by keyword
    - Rate limiting (100 req/5min without key, 1000 with key)
    - Caching with 24-hour TTL

    Features direct integration with semantic_scholar.py module.
    """

    def __init__(self, api_key: Optional[str] = None, max_results: int = 10):
        super().__init__(max_results)
        self.api_key = api_key or os.getenv("SEMANTIC_SCHOLAR_API_KEY")
        self._client = None

    def _get_client(self):
        """Get or create SemanticScholarClient instance."""
        if self._client is None:
            try:
                import importlib.util
                s2_path = os.path.join(os.path.dirname(__file__), "semantic_scholar.py")
                spec = importlib.util.spec_from_file_location("semantic_scholar", s2_path)
                s2_module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(s2_module)
                self._client = s2_module.SemanticScholarClient(api_key=self.api_key)
            except Exception as e:
                raise SearchProviderError(f"Failed to load semantic_scholar module: {str(e)}")
        return self._client

    def is_available(self) -> bool:
        """
        Check if Semantic Scholar is available.

        Note: Semantic Scholar works without API key (just lower rate limits).
        Returns True always since basic access is available.
        """
        return True

    def search(self, query: str, max_results: Optional[int] = None) -> List[SearchResult]:
        """
        Execute academic paper search using Semantic Scholar.

        Args:
            query: Search query string
            max_results: Maximum results to return

        Returns:
            List of SearchResult objects

        Raises:
            SearchProviderError: If API call fails
        """
        limit = max_results or self.max_results

        try:
            client = self._get_client()
            papers = client.search_papers(query, limit=limit)

            # Convert Paper objects to SearchResult format
            results = []
            for idx, paper in enumerate(papers):
                # Build author string
                author_str = ""
                if paper.authors:
                    author_names = [a.name for a in paper.authors[:3]]
                    author_str = ", ".join(author_names)
                    if len(paper.authors) > 3:
                        author_str += " et al."

                # Build snippet from abstract and metadata
                snippet_parts = []
                if paper.abstract:
                    snippet_parts.append(paper.abstract[:300])
                if author_str:
                    snippet_parts.append(f"Authors: {author_str}")
                if paper.venue:
                    snippet_parts.append(f"Venue: {paper.venue}")
                snippet = " | ".join(snippet_parts) if snippet_parts else "No abstract available"

                # Calculate relevance score based on position (S2 doesn't provide scores)
                # Use citation count as a factor if available
                base_score = 1.0 - (idx * 0.05)
                if paper.citation_count and paper.citation_count > 0:
                    # Boost score slightly based on citations (log scale)
                    import math
                    citation_boost = min(0.2, math.log10(paper.citation_count + 1) / 20)
                    base_score = min(1.0, base_score + citation_boost)
                score = max(0.1, base_score)

                # Extract domain from URL
                domain = None
                if paper.url:
                    from urllib.parse import urlparse
                    domain = urlparse(paper.url).netloc

                result = SearchResult(
                    title=paper.title,
                    url=paper.url or f"https://www.semanticscholar.org/paper/{paper.paper_id}",
                    snippet=snippet,
                    relevance_score=score,
                    source="semanticscholar",
                    published_date=str(paper.year) if paper.year else None,
                    domain=domain or "semanticscholar.org"
                )
                results.append(result)

            return results

        except Exception as e:
            raise SearchProviderError(f"Semantic Scholar search failed: {str(e)}")

    def search_academic(self, query: str, max_results: Optional[int] = None) -> List[SearchResult]:
        """
        Search for academic papers (alias for search).

        Semantic Scholar is inherently academic, so this is the same as search().

        Args:
            query: Search query string
            max_results: Maximum results to return

        Returns:
            List of SearchResult objects for academic content

        Raises:
            SearchProviderError: If search fails
        """
        return self.search(query, max_results=max_results)


class SearchProviderManager:
    """
    Manages multiple search providers with automatic fallback.

    Tries providers in order:
    1. Exa (primary - neural search)
    2. Tavily (fallback 1)
    3. DuckDuckGo (fallback 2)
    4. SerpAPI (fallback 3)
    5. Semantic Scholar (academic backup - always available)
    """

    def __init__(self, max_results: int = 10):
        self.max_results = max_results
        self.providers = [
            ExaProvider(max_results=max_results),
            TavilyProvider(max_results=max_results),
            DuckDuckGoProvider(max_results=max_results),
            SerpAPIProvider(max_results=max_results),
            SemanticScholarProvider(max_results=max_results)
        ]

    def search(self, query: str, max_results: Optional[int] = None) -> List[SearchResult]:
        """
        Execute search with automatic fallback between providers.

        Args:
            query: Search query string
            max_results: Maximum results to return

        Returns:
            List of SearchResult objects

        Raises:
            SearchProviderError: If all providers fail
        """
        limit = max_results or self.max_results
        errors = []

        for provider in self.providers:
            if not provider.is_available():
                errors.append(f"{provider.name}: not available")
                continue

            try:
                results = provider.search(query, max_results=limit)
                if results:
                    return results
                errors.append(f"{provider.name}: no results")
            except SearchProviderError as e:
                errors.append(f"{provider.name}: {str(e)}")
                continue

        # All providers failed
        error_msg = "All search providers failed:\n" + "\n".join(f"  - {e}" for e in errors)
        raise SearchProviderError(error_msg)

    def get_available_providers(self) -> List[str]:
        """Return list of available provider names."""
        return [p.name for p in self.providers if p.is_available()]


# CLI interface
def main():
    """Command-line interface for search-provider."""
    import argparse

    parser = argparse.ArgumentParser(description="Search Provider CLI")
    parser.add_argument("command", choices=["search", "providers"], help="Command to execute")
    parser.add_argument("query", nargs="?", help="Search query (for 'search' command)")
    parser.add_argument("--max-results", type=int, default=10, help="Maximum results to return")
    parser.add_argument("--provider", choices=["exa", "tavily", "duckduckgo", "serpapi", "semanticscholar"], help="Force specific provider")
    parser.add_argument("--json", action="store_true", help="Output as JSON")

    args = parser.parse_args()

    if args.command == "providers":
        # List available providers
        manager = SearchProviderManager()
        available = manager.get_available_providers()

        if args.json:
            print(json.dumps({"available_providers": available}, indent=2))
        else:
            print("Available search providers:")
            for provider in available:
                print(f"  - {provider}")
        return 0

    elif args.command == "search":
        if not args.query:
            print("Error: query required for 'search' command", file=sys.stderr)
            return 1

        try:
            if args.provider:
                # Use specific provider
                provider_map = {
                    "exa": ExaProvider,
                    "tavily": TavilyProvider,
                    "duckduckgo": DuckDuckGoProvider,
                    "serpapi": SerpAPIProvider,
                    "semanticscholar": SemanticScholarProvider
                }
                provider = provider_map[args.provider](max_results=args.max_results)

                if not provider.is_available():
                    print(f"Error: {args.provider} provider not available", file=sys.stderr)
                    return 1

                results = provider.search(args.query, max_results=args.max_results)
            else:
                # Use manager with fallback
                manager = SearchProviderManager(max_results=args.max_results)
                results = manager.search(args.query, max_results=args.max_results)

            if args.json:
                output = {
                    "query": args.query,
                    "count": len(results),
                    "results": [
                        {
                            "title": r.title,
                            "url": r.url,
                            "snippet": r.snippet,
                            "relevance_score": r.relevance_score,
                            "source": r.source,
                            "domain": r.domain
                        }
                        for r in results
                    ]
                }
                print(json.dumps(output, indent=2))
            else:
                print(f"\nSearch results for: {args.query}")
                print(f"Found {len(results)} results\n")

                for idx, result in enumerate(results, 1):
                    print(f"{idx}. {result.title}")
                    print(f"   URL: {result.url}")
                    print(f"   Snippet: {result.snippet[:150]}...")
                    print(f"   Score: {result.relevance_score:.2f} | Source: {result.source}")
                    print()

            return 0

        except SearchProviderError as e:
            print(f"Error: {str(e)}", file=sys.stderr)
            return 1


if __name__ == "__main__":
    sys.exit(main())
