#!/usr/bin/env python3
"""
arXiv API Client

Provides Python interface to arXiv API for searching and retrieving ML/AI papers.
Supports filtering by category (cs.AI, cs.LG, cs.CL, cs.CV, etc.) and structured results.

API Documentation: https://info.arxiv.org/help/api/index.html
"""

import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from typing import List, Optional
from datetime import datetime
import time
import json
import sys


@dataclass
class ArxivPaper:
    """Structured arXiv paper metadata."""
    arxiv_id: str
    title: str
    authors: List[str]
    abstract: str
    published_date: str  # ISO format
    updated_date: str  # ISO format
    categories: List[str]  # e.g., ["cs.AI", "cs.LG"]
    pdf_url: str
    arxiv_url: str
    primary_category: str
    comment: Optional[str] = None
    journal_ref: Optional[str] = None
    doi: Optional[str] = None


class ArxivClient:
    """Client for searching arXiv papers via API."""

    BASE_URL = "http://export.arxiv.org/api/query"
    NAMESPACE = {"atom": "http://www.w3.org/2005/Atom"}

    def __init__(self, max_results: int = 20, rate_limit_seconds: float = 1.0):
        """
        Initialize arXiv client.

        Args:
            max_results: Maximum results per query
            rate_limit_seconds: Minimum seconds between requests
        """
        self.max_results = max_results
        self.rate_limit_seconds = rate_limit_seconds
        self.last_request_time = 0.0

    def _rate_limit(self):
        """Enforce rate limiting between requests."""
        elapsed = time.time() - self.last_request_time
        if elapsed < self.rate_limit_seconds:
            time.sleep(self.rate_limit_seconds - elapsed)
        self.last_request_time = time.time()

    def search(
        self,
        query: str,
        categories: Optional[List[str]] = None,
        max_results: Optional[int] = None,
        sort_by: str = "relevance",
        sort_order: str = "descending"
    ) -> List[ArxivPaper]:
        """
        Search arXiv papers.

        Args:
            query: Search query string (searches titles and abstracts)
            categories: Filter by arXiv categories (e.g., ["cs.AI", "cs.LG"])
            max_results: Maximum results to return (None = use self.max_results)
            sort_by: Sort criterion ("relevance", "lastUpdatedDate", "submittedDate")
            sort_order: "ascending" or "descending"

        Returns:
            List of ArxivPaper objects

        Example:
            >>> client = ArxivClient()
            >>> papers = client.search("transformers", categories=["cs.LG", "cs.CL"])
            >>> print(papers[0].title)
        """
        limit = max_results or self.max_results

        # Build search query
        search_query = query
        if categories:
            # Add category filter
            cat_query = " OR ".join([f"cat:{cat}" for cat in categories])
            search_query = f"({query}) AND ({cat_query})"

        # Build URL parameters
        params = {
            "search_query": search_query,
            "start": 0,
            "max_results": limit,
            "sortBy": sort_by,
            "sortOrder": sort_order
        }

        url = f"{self.BASE_URL}?{urllib.parse.urlencode(params)}"

        # Rate limit
        self._rate_limit()

        # Make request
        try:
            with urllib.request.urlopen(url, timeout=10) as response:
                xml_data = response.read().decode('utf-8')
        except Exception as e:
            raise ArxivClientError(f"Failed to fetch from arXiv API: {e}")

        # Parse XML
        try:
            root = ET.fromstring(xml_data)
            papers = self._parse_results(root)
            return papers
        except ET.ParseError as e:
            raise ArxivClientError(f"Failed to parse arXiv API response: {e}")

    def get_by_id(self, arxiv_id: str) -> Optional[ArxivPaper]:
        """
        Get specific paper by arXiv ID.

        Args:
            arxiv_id: arXiv ID (e.g., "2103.00020" or "arXiv:2103.00020")

        Returns:
            ArxivPaper or None if not found
        """
        # Clean ID (remove "arXiv:" prefix if present)
        clean_id = arxiv_id.replace("arXiv:", "")

        params = {
            "id_list": clean_id
        }

        url = f"{self.BASE_URL}?{urllib.parse.urlencode(params)}"

        self._rate_limit()

        try:
            with urllib.request.urlopen(url, timeout=10) as response:
                xml_data = response.read().decode('utf-8')

            root = ET.fromstring(xml_data)
            papers = self._parse_results(root)
            return papers[0] if papers else None

        except Exception as e:
            raise ArxivClientError(f"Failed to fetch paper {arxiv_id}: {e}")

    def search_by_category(
        self,
        category: str,
        max_results: Optional[int] = None,
        sort_by: str = "submittedDate"
    ) -> List[ArxivPaper]:
        """
        Get recent papers from specific category.

        Args:
            category: arXiv category (e.g., "cs.AI", "cs.LG")
            max_results: Maximum results to return
            sort_by: Sort criterion (default: most recent submissions)

        Returns:
            List of ArxivPaper objects
        """
        limit = max_results or self.max_results

        params = {
            "search_query": f"cat:{category}",
            "start": 0,
            "max_results": limit,
            "sortBy": sort_by,
            "sortOrder": "descending"
        }

        url = f"{self.BASE_URL}?{urllib.parse.urlencode(params)}"

        self._rate_limit()

        try:
            with urllib.request.urlopen(url, timeout=10) as response:
                xml_data = response.read().decode('utf-8')

            root = ET.fromstring(xml_data)
            return self._parse_results(root)

        except Exception as e:
            raise ArxivClientError(f"Failed to fetch category {category}: {e}")

    def _parse_results(self, root: ET.Element) -> List[ArxivPaper]:
        """Parse XML response into ArxivPaper objects."""
        papers = []

        for entry in root.findall("atom:entry", self.NAMESPACE):
            try:
                # Extract fields
                arxiv_id = entry.find("atom:id", self.NAMESPACE).text.split("/")[-1]
                title = entry.find("atom:title", self.NAMESPACE).text.strip().replace("\n", " ")
                abstract = entry.find("atom:summary", self.NAMESPACE).text.strip().replace("\n", " ")

                # Authors
                authors = []
                for author in entry.findall("atom:author", self.NAMESPACE):
                    name = author.find("atom:name", self.NAMESPACE).text
                    authors.append(name)

                # Dates
                published = entry.find("atom:published", self.NAMESPACE).text
                updated = entry.find("atom:updated", self.NAMESPACE).text

                # Categories
                categories = []
                primary_category = None
                for cat in entry.findall("atom:category", self.NAMESPACE):
                    term = cat.get("term")
                    categories.append(term)
                    if cat.get("scheme") == "http://arxiv.org/schemas/atom":
                        primary_category = term

                # Use first category as primary if not found
                if not primary_category and categories:
                    primary_category = categories[0]

                # Links
                pdf_url = None
                arxiv_url = None
                for link in entry.findall("atom:link", self.NAMESPACE):
                    if link.get("title") == "pdf":
                        pdf_url = link.get("href")
                    elif link.get("rel") == "alternate":
                        arxiv_url = link.get("href")

                # Optional fields
                comment_elem = entry.find("arxiv:comment", {"arxiv": "http://arxiv.org/schemas/atom"})
                comment = comment_elem.text if comment_elem is not None else None

                journal_ref_elem = entry.find("arxiv:journal_ref", {"arxiv": "http://arxiv.org/schemas/atom"})
                journal_ref = journal_ref_elem.text if journal_ref_elem is not None else None

                doi_elem = entry.find("arxiv:doi", {"arxiv": "http://arxiv.org/schemas/atom"})
                doi = doi_elem.text if doi_elem is not None else None

                paper = ArxivPaper(
                    arxiv_id=arxiv_id,
                    title=title,
                    authors=authors,
                    abstract=abstract,
                    published_date=published,
                    updated_date=updated,
                    categories=categories,
                    pdf_url=pdf_url,
                    arxiv_url=arxiv_url,
                    primary_category=primary_category,
                    comment=comment,
                    journal_ref=journal_ref,
                    doi=doi
                )
                papers.append(paper)

            except Exception as e:
                # Skip malformed entries
                print(f"Warning: Failed to parse entry: {e}", file=sys.stderr)
                continue

        return papers


class ArxivClientError(Exception):
    """Exception for arXiv client errors."""
    pass


def main():
    """CLI interface for arXiv client."""
    import argparse

    parser = argparse.ArgumentParser(description="Search arXiv papers for ML/AI research")
    subparsers = parser.add_subparsers(dest="command", help="Command to execute")

    # Search command
    search_parser = subparsers.add_parser("search", help="Search papers")
    search_parser.add_argument("query", help="Search query")
    search_parser.add_argument("--categories", nargs="+", help="Filter by categories (e.g., cs.AI cs.LG)")
    search_parser.add_argument("--max-results", type=int, default=10, help="Maximum results")
    search_parser.add_argument("--json", action="store_true", help="Output as JSON")

    # Get by ID command
    get_parser = subparsers.add_parser("get", help="Get paper by ID")
    get_parser.add_argument("arxiv_id", help="arXiv ID (e.g., 2103.00020)")
    get_parser.add_argument("--json", action="store_true", help="Output as JSON")

    # Category command
    cat_parser = subparsers.add_parser("category", help="Get recent papers from category")
    cat_parser.add_argument("category", help="arXiv category (e.g., cs.AI)")
    cat_parser.add_argument("--max-results", type=int, default=10, help="Maximum results")
    cat_parser.add_argument("--json", action="store_true", help="Output as JSON")

    args = parser.parse_args()

    client = ArxivClient()

    try:
        if args.command == "search":
            papers = client.search(args.query, categories=args.categories, max_results=args.max_results)
        elif args.command == "get":
            paper = client.get_by_id(args.arxiv_id)
            papers = [paper] if paper else []
        elif args.command == "category":
            papers = client.search_by_category(args.category, max_results=args.max_results)
        else:
            parser.print_help()
            return 1

        # Output
        if args.json:
            output = []
            for paper in papers:
                output.append({
                    "arxiv_id": paper.arxiv_id,
                    "title": paper.title,
                    "authors": paper.authors,
                    "abstract": paper.abstract,
                    "published_date": paper.published_date,
                    "updated_date": paper.updated_date,
                    "categories": paper.categories,
                    "primary_category": paper.primary_category,
                    "pdf_url": paper.pdf_url,
                    "arxiv_url": paper.arxiv_url,
                    "comment": paper.comment,
                    "journal_ref": paper.journal_ref,
                    "doi": paper.doi
                })
            print(json.dumps(output, indent=2))
        else:
            for i, paper in enumerate(papers, 1):
                print(f"\n{i}. {paper.title}")
                print(f"   Authors: {', '.join(paper.authors[:3])}{'...' if len(paper.authors) > 3 else ''}")
                print(f"   Categories: {', '.join(paper.categories)}")
                print(f"   Published: {paper.published_date[:10]}")
                print(f"   URL: {paper.arxiv_url}")
                print(f"   Abstract: {paper.abstract[:200]}...")

        return 0

    except ArxivClientError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
