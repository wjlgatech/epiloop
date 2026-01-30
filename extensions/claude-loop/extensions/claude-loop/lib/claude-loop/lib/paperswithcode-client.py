#!/usr/bin/env python3
"""
Papers With Code API Client

Provides Python interface to Papers With Code API for tracking SOTA benchmarks,
datasets, and ML paper implementations.

API Documentation: https://paperswithcode.com/api/v1/docs/
"""

import urllib.request
import urllib.parse
import json
import sys
import time
from dataclasses import dataclass
from typing import List, Optional, Dict, Any


@dataclass
class PaperResult:
    """Paper metadata from Papers With Code."""
    paper_id: str
    title: str
    arxiv_id: Optional[str]
    url_abs: Optional[str]
    url_pdf: Optional[str]
    published: Optional[str]
    authors: List[str]
    abstract: Optional[str]
    conference: Optional[str]
    tasks: List[str]  # ML tasks (e.g., "Image Classification", "Language Modeling")


@dataclass
class BenchmarkResult:
    """SOTA benchmark result."""
    paper_id: str
    paper_title: str
    task: str
    dataset: str
    metric_name: str
    metric_value: float
    rank: int
    published_date: Optional[str]
    arxiv_id: Optional[str]
    github_url: Optional[str]


@dataclass
class MethodInfo:
    """ML method/technique information."""
    name: str
    description: str
    paper_count: int
    introduced_by: Optional[str]  # Paper title that introduced it
    categories: List[str]


class PapersWithCodeClient:
    """Client for Papers With Code API."""

    BASE_URL = "https://paperswithcode.com/api/v1"

    def __init__(self, rate_limit_seconds: float = 0.5):
        """
        Initialize Papers With Code client.

        Args:
            rate_limit_seconds: Minimum seconds between requests
        """
        self.rate_limit_seconds = rate_limit_seconds
        self.last_request_time = 0.0

    def _rate_limit(self):
        """Enforce rate limiting between requests."""
        elapsed = time.time() - self.last_request_time
        if elapsed < self.rate_limit_seconds:
            time.sleep(self.rate_limit_seconds - elapsed)
        self.last_request_time = time.time()

    def _request(self, endpoint: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Make API request.

        Args:
            endpoint: API endpoint (e.g., "/papers/")
            params: URL parameters

        Returns:
            Parsed JSON response

        Raises:
            PapersWithCodeError: If request fails
        """
        url = f"{self.BASE_URL}{endpoint}"
        if params:
            url = f"{url}?{urllib.parse.urlencode(params)}"

        self._rate_limit()

        try:
            request = urllib.request.Request(url)
            request.add_header("User-Agent", "research-loop/1.0")

            with urllib.request.urlopen(request, timeout=10) as response:
                data = json.loads(response.read().decode('utf-8'))
                return data

        except urllib.error.HTTPError as e:
            raise PapersWithCodeError(f"HTTP {e.code}: {e.reason}")
        except Exception as e:
            raise PapersWithCodeError(f"Request failed: {e}")

    def search_papers(
        self,
        query: Optional[str] = None,
        arxiv_id: Optional[str] = None,
        max_results: int = 20
    ) -> List[PaperResult]:
        """
        Search papers.

        Args:
            query: Search query (searches titles)
            arxiv_id: Filter by arXiv ID
            max_results: Maximum results to return

        Returns:
            List of PaperResult objects
        """
        params = {}
        if arxiv_id:
            params["arxiv_id"] = arxiv_id
        if query:
            params["q"] = query

        try:
            # Papers With Code API returns paginated results
            data = self._request("/papers/", params)

            papers = []
            results = data.get("results", [])[:max_results]

            for item in results:
                paper = PaperResult(
                    paper_id=item.get("id", ""),
                    title=item.get("title", ""),
                    arxiv_id=item.get("arxiv_id"),
                    url_abs=item.get("url_abs"),
                    url_pdf=item.get("url_pdf"),
                    published=item.get("published"),
                    authors=item.get("authors", []),
                    abstract=item.get("abstract"),
                    conference=item.get("conference"),
                    tasks=item.get("tasks", [])
                )
                papers.append(paper)

            return papers

        except Exception as e:
            raise PapersWithCodeError(f"Failed to search papers: {e}")

    def get_sota_benchmarks(
        self,
        task: Optional[str] = None,
        dataset: Optional[str] = None,
        max_results: int = 20
    ) -> List[BenchmarkResult]:
        """
        Get state-of-the-art benchmark results.

        Args:
            task: Filter by task name (e.g., "Image Classification")
            dataset: Filter by dataset name (e.g., "ImageNet")
            max_results: Maximum results to return

        Returns:
            List of BenchmarkResult objects
        """
        # Build endpoint
        if task and dataset:
            # Get specific task+dataset SOTA
            endpoint = f"/tasks/{urllib.parse.quote(task)}/datasets/{urllib.parse.quote(dataset)}/sota/"
        elif task:
            # Get all datasets for task
            endpoint = f"/tasks/{urllib.parse.quote(task)}/datasets/"
        else:
            # Get all benchmarks
            endpoint = "/benchmarks/"

        try:
            data = self._request(endpoint)

            benchmarks = []
            results = data.get("results", [])[:max_results]

            for item in results:
                # Structure varies by endpoint
                if "rows" in item:
                    # Specific task+dataset SOTA
                    for row in item.get("rows", [])[:max_results]:
                        paper_title = row.get("paper_title", "")
                        paper_url = row.get("paper_url", "")
                        arxiv_id = self._extract_arxiv_id(paper_url)

                        benchmark = BenchmarkResult(
                            paper_id=row.get("paper_id", ""),
                            paper_title=paper_title,
                            task=task or "",
                            dataset=dataset or "",
                            metric_name=row.get("metric_name", ""),
                            metric_value=float(row.get("metric_value", 0)),
                            rank=row.get("rank", 0),
                            published_date=row.get("published_date"),
                            arxiv_id=arxiv_id,
                            github_url=row.get("code_url")
                        )
                        benchmarks.append(benchmark)
                else:
                    # Dataset listing
                    dataset_name = item.get("dataset", "")
                    # Note: Would need additional request to get actual SOTA for each dataset
                    # For now, just return dataset info

            return benchmarks

        except Exception as e:
            raise PapersWithCodeError(f"Failed to get SOTA benchmarks: {e}")

    def get_methods(
        self,
        query: Optional[str] = None,
        max_results: int = 20
    ) -> List[MethodInfo]:
        """
        Get ML methods/techniques.

        Args:
            query: Search query (searches method names)
            max_results: Maximum results to return

        Returns:
            List of MethodInfo objects
        """
        params = {}
        if query:
            params["q"] = query

        try:
            data = self._request("/methods/", params)

            methods = []
            results = data.get("results", [])[:max_results]

            for item in results:
                method = MethodInfo(
                    name=item.get("name", ""),
                    description=item.get("description", ""),
                    paper_count=item.get("paper_count", 0),
                    introduced_by=item.get("introduced_by"),
                    categories=item.get("categories", [])
                )
                methods.append(method)

            return methods

        except Exception as e:
            raise PapersWithCodeError(f"Failed to get methods: {e}")

    def get_paper_code(self, paper_id: str) -> Optional[str]:
        """
        Get GitHub repository URL for paper.

        Args:
            paper_id: Paper ID from Papers With Code

        Returns:
            GitHub URL or None if not available
        """
        try:
            endpoint = f"/papers/{paper_id}/repositories/"
            data = self._request(endpoint)

            repos = data.get("results", [])
            if repos:
                return repos[0].get("url")

            return None

        except Exception:
            return None

    @staticmethod
    def _extract_arxiv_id(url: Optional[str]) -> Optional[str]:
        """Extract arXiv ID from URL."""
        if not url:
            return None

        if "arxiv.org" in url:
            parts = url.rstrip("/").split("/")
            return parts[-1] if parts else None

        return None


class PapersWithCodeError(Exception):
    """Exception for Papers With Code client errors."""
    pass


def main():
    """CLI interface for Papers With Code client."""
    import argparse

    parser = argparse.ArgumentParser(description="Query Papers With Code for SOTA benchmarks")
    subparsers = parser.add_subparsers(dest="command", help="Command to execute")

    # Search papers
    search_parser = subparsers.add_parser("search", help="Search papers")
    search_parser.add_argument("query", help="Search query")
    search_parser.add_argument("--max-results", type=int, default=10, help="Maximum results")
    search_parser.add_argument("--json", action="store_true", help="Output as JSON")

    # Get SOTA
    sota_parser = subparsers.add_parser("sota", help="Get SOTA benchmark results")
    sota_parser.add_argument("--task", help="Task name (e.g., 'Image Classification')")
    sota_parser.add_argument("--dataset", help="Dataset name (e.g., 'ImageNet')")
    sota_parser.add_argument("--max-results", type=int, default=10, help="Maximum results")
    sota_parser.add_argument("--json", action="store_true", help="Output as JSON")

    # Get methods
    methods_parser = subparsers.add_parser("methods", help="Get ML methods")
    methods_parser.add_argument("query", nargs="?", help="Search query")
    methods_parser.add_argument("--max-results", type=int, default=10, help="Maximum results")
    methods_parser.add_argument("--json", action="store_true", help="Output as JSON")

    args = parser.parse_args()

    client = PapersWithCodeClient()

    try:
        if args.command == "search":
            results = client.search_papers(query=args.query, max_results=args.max_results)
            if args.json:
                output = [vars(r) for r in results]
                print(json.dumps(output, indent=2))
            else:
                for i, paper in enumerate(results, 1):
                    print(f"\n{i}. {paper.title}")
                    print(f"   arXiv: {paper.arxiv_id or 'N/A'}")
                    print(f"   Tasks: {', '.join(paper.tasks) if paper.tasks else 'N/A'}")
                    print(f"   URL: {paper.url_abs or 'N/A'}")

        elif args.command == "sota":
            results = client.get_sota_benchmarks(
                task=args.task,
                dataset=args.dataset,
                max_results=args.max_results
            )
            if args.json:
                output = [vars(r) for r in results]
                print(json.dumps(output, indent=2))
            else:
                for i, bench in enumerate(results, 1):
                    print(f"\n{i}. {bench.paper_title}")
                    print(f"   Task: {bench.task}")
                    print(f"   Dataset: {bench.dataset}")
                    print(f"   Metric: {bench.metric_name} = {bench.metric_value}")
                    print(f"   Rank: #{bench.rank}")

        elif args.command == "methods":
            results = client.get_methods(query=args.query, max_results=args.max_results)
            if args.json:
                output = [vars(r) for r in results]
                print(json.dumps(output, indent=2))
            else:
                for i, method in enumerate(results, 1):
                    print(f"\n{i}. {method.name}")
                    print(f"   Papers: {method.paper_count}")
                    print(f"   Introduced by: {method.introduced_by or 'N/A'}")
                    print(f"   Description: {method.description[:150]}...")

        else:
            parser.print_help()
            return 1

        return 0

    except PapersWithCodeError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
