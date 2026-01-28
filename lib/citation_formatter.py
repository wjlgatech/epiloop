#!/usr/bin/env python3
"""
Citation Formatter - Utilities for formatting research citations

This module provides functionality to:
1. Format inline citations ([1], [2], etc.)
2. Generate bibliographies from sources
3. Validate URLs
4. Extract metadata from source URLs
5. Handle various citation styles
"""

import re
import sys
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple, Any
from datetime import datetime
from urllib.parse import urlparse, parse_qs
from pathlib import Path

# Add lib directory to path for imports
SCRIPT_DIR = Path(__file__).parent
sys.path.insert(0, str(SCRIPT_DIR))


@dataclass
class Citation:
    """Represents a single citation with metadata."""
    number: int
    url: Optional[str] = None
    title: Optional[str] = None
    author: Optional[str] = None
    date: Optional[str] = None
    domain: Optional[str] = None
    agent: Optional[str] = None
    relevance: float = 0.5
    accessed_at: Optional[str] = None

    def to_dict(self) -> Dict:
        """Convert citation to dictionary."""
        return {
            'number': self.number,
            'url': self.url,
            'title': self.title,
            'author': self.author,
            'date': self.date,
            'domain': self.domain,
            'agent': self.agent,
            'relevance': self.relevance,
            'accessed_at': self.accessed_at
        }

    @classmethod
    def from_dict(cls, data: Dict) -> 'Citation':
        """Create citation from dictionary."""
        return cls(
            number=data.get('number', 0),
            url=data.get('url'),
            title=data.get('title'),
            author=data.get('author'),
            date=data.get('date'),
            domain=data.get('domain'),
            agent=data.get('agent'),
            relevance=data.get('relevance', 0.5),
            accessed_at=data.get('accessed_at')
        )


@dataclass
class Bibliography:
    """Represents a complete bibliography."""
    citations: List[Citation] = field(default_factory=list)
    style: str = "numeric"  # numeric, author-date, footnote
    generated_at: str = field(default_factory=lambda: datetime.utcnow().isoformat() + 'Z')

    def to_dict(self) -> Dict:
        """Convert bibliography to dictionary."""
        return {
            'citations': [c.to_dict() for c in self.citations],
            'style': self.style,
            'generated_at': self.generated_at
        }


class CitationFormatter:
    """Formats citations and generates bibliographies."""

    # Known domain patterns for metadata extraction
    DOMAIN_PATTERNS = {
        'arxiv.org': {
            'type': 'academic',
            'title_pattern': r'/abs/(\d+\.\d+)',
            'author_hint': 'arxiv'
        },
        'github.com': {
            'type': 'repository',
            'title_pattern': r'github\.com/([^/]+/[^/]+)',
            'author_hint': 'github'
        },
        'scholar.google.com': {
            'type': 'academic',
            'title_pattern': None,
            'author_hint': 'google scholar'
        },
        'medium.com': {
            'type': 'blog',
            'title_pattern': r'medium\.com/[^/]+/([^?]+)',
            'author_hint': 'medium'
        },
        'stackoverflow.com': {
            'type': 'qa',
            'title_pattern': r'/questions/\d+/([^?]+)',
            'author_hint': 'stack overflow'
        },
        'wikipedia.org': {
            'type': 'encyclopedia',
            'title_pattern': r'/wiki/([^?]+)',
            'author_hint': 'wikipedia'
        }
    }

    # URL validation patterns
    URL_PATTERN = re.compile(
        r'^https?://'  # http:// or https://
        r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|'  # domain
        r'localhost|'  # localhost
        r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'  # or ip
        r'(?::\d+)?'  # optional port
        r'(?:/?|[/?]\S+)$', re.IGNORECASE
    )

    def __init__(self, style: str = "numeric"):
        """
        Initialize the citation formatter.

        Args:
            style: Citation style (numeric, author-date, footnote)
        """
        self.style = style
        self._citation_counter = 0
        self._citations: Dict[str, Citation] = {}  # URL -> Citation mapping

    def format_inline(self, url_or_number: Any) -> str:
        """
        Format an inline citation reference.

        Args:
            url_or_number: URL string or citation number

        Returns:
            Formatted inline citation (e.g., "[1]")
        """
        if isinstance(url_or_number, int):
            return f"[{url_or_number}]"

        # It's a URL - get or create citation
        url = str(url_or_number)
        if url in self._citations:
            return f"[{self._citations[url].number}]"

        # Create new citation
        self._citation_counter += 1
        citation = Citation(
            number=self._citation_counter,
            url=url,
            domain=self._extract_domain(url),
            accessed_at=datetime.utcnow().isoformat() + 'Z'
        )
        self._citations[url] = citation
        return f"[{citation.number}]"

    def format_multiple(self, urls_or_numbers: List[Any]) -> str:
        """
        Format multiple inline citations.

        Args:
            urls_or_numbers: List of URLs or citation numbers

        Returns:
            Formatted inline citations (e.g., "[1, 2, 3]")
        """
        numbers = []
        for item in urls_or_numbers:
            inline = self.format_inline(item)
            # Extract number from [N] format
            match = re.search(r'\[(\d+)\]', inline)
            if match:
                numbers.append(int(match.group(1)))

        # Sort and format
        numbers = sorted(set(numbers))

        # Compress consecutive ranges: [1, 2, 3, 5] -> "[1-3, 5]"
        if len(numbers) > 2:
            ranges = []
            start = numbers[0]
            end = start
            for n in numbers[1:]:
                if n == end + 1:
                    end = n
                else:
                    if end > start:
                        ranges.append(f"{start}-{end}")
                    else:
                        ranges.append(str(start))
                    start = end = n
            # Don't forget the last range
            if end > start:
                ranges.append(f"{start}-{end}")
            else:
                ranges.append(str(start))
            return f"[{', '.join(ranges)}]"

        return f"[{', '.join(str(n) for n in numbers)}]"

    def add_citation(
        self,
        url: str,
        title: Optional[str] = None,
        author: Optional[str] = None,
        date: Optional[str] = None,
        agent: Optional[str] = None,
        relevance: float = 0.5
    ) -> Citation:
        """
        Add a citation to the formatter.

        Args:
            url: Source URL
            title: Optional title
            author: Optional author
            date: Optional publication date
            agent: Optional agent that found the source
            relevance: Relevance score (0-1)

        Returns:
            The created Citation object
        """
        if url in self._citations:
            # Update existing citation with new info
            citation = self._citations[url]
            if title:
                citation.title = title
            if author:
                citation.author = author
            if date:
                citation.date = date
            if agent:
                citation.agent = agent
            citation.relevance = max(citation.relevance, relevance)
            return citation

        # Create new citation
        self._citation_counter += 1
        citation = Citation(
            number=self._citation_counter,
            url=url,
            title=title or self._extract_title_from_url(url),
            author=author,
            date=date,
            domain=self._extract_domain(url),
            agent=agent,
            relevance=relevance,
            accessed_at=datetime.utcnow().isoformat() + 'Z'
        )
        self._citations[url] = citation
        return citation

    def add_citations_from_sources(self, sources: List[Dict]) -> List[Citation]:
        """
        Add multiple citations from source dictionaries.

        Args:
            sources: List of source dictionaries with url, title, etc.

        Returns:
            List of created Citation objects
        """
        citations = []
        for source in sources:
            citation = self.add_citation(
                url=source.get('url', ''),
                title=source.get('title'),
                author=source.get('author'),
                date=source.get('date'),
                agent=source.get('agent'),
                relevance=source.get('relevance', 0.5)
            )
            citations.append(citation)
        return citations

    def generate_bibliography(self, format: str = "markdown") -> str:
        """
        Generate a complete bibliography from all citations.

        Args:
            format: Output format (markdown, html, plain)

        Returns:
            Formatted bibliography string
        """
        if not self._citations:
            return "*No sources available.*"

        # Sort citations by number
        sorted_citations = sorted(
            self._citations.values(),
            key=lambda c: c.number
        )

        if format == "markdown":
            return self._generate_markdown_bibliography(sorted_citations)
        elif format == "html":
            return self._generate_html_bibliography(sorted_citations)
        else:
            return self._generate_plain_bibliography(sorted_citations)

    def _generate_markdown_bibliography(self, citations: List[Citation]) -> str:
        """Generate markdown formatted bibliography."""
        lines = ["## Sources\n"]

        for citation in citations:
            entry = f"[{citation.number}] "

            # Format title with link
            title = citation.title or citation.url or "Unknown Source"
            if citation.url:
                entry += f"[{title}]({citation.url})"
            else:
                entry += title

            # Add metadata
            meta_parts = []
            if citation.author:
                meta_parts.append(citation.author)
            if citation.date:
                meta_parts.append(citation.date)
            if citation.agent:
                meta_parts.append(f"via {citation.agent}")

            if meta_parts:
                entry += f" *({', '.join(meta_parts)})*"

            # Add relevance
            if citation.relevance > 0:
                entry += f" - Relevance: {citation.relevance:.0%}"

            lines.append(entry)

        return '\n'.join(lines)

    def _generate_html_bibliography(self, citations: List[Citation]) -> str:
        """Generate HTML formatted bibliography."""
        lines = ["<h2>Sources</h2>", "<ol class='bibliography'>"]

        for citation in citations:
            title = citation.title or citation.url or "Unknown Source"
            if citation.url:
                link = f'<a href="{citation.url}">{title}</a>'
            else:
                link = title

            meta = ""
            if citation.author or citation.date or citation.agent:
                parts = []
                if citation.author:
                    parts.append(citation.author)
                if citation.date:
                    parts.append(citation.date)
                if citation.agent:
                    parts.append(f"via {citation.agent}")
                meta = f" <em>({', '.join(parts)})</em>"

            lines.append(f'  <li value="{citation.number}">{link}{meta}</li>')

        lines.append("</ol>")
        return '\n'.join(lines)

    def _generate_plain_bibliography(self, citations: List[Citation]) -> str:
        """Generate plain text bibliography."""
        lines = ["Sources", "=" * 40, ""]

        for citation in citations:
            title = citation.title or citation.url or "Unknown Source"
            entry = f"[{citation.number}] {title}"

            if citation.url:
                entry += f"\n    URL: {citation.url}"
            if citation.author:
                entry += f"\n    Author: {citation.author}"
            if citation.date:
                entry += f"\n    Date: {citation.date}"
            if citation.agent:
                entry += f"\n    Found by: {citation.agent}"

            lines.append(entry)
            lines.append("")

        return '\n'.join(lines)

    def validate_url(self, url: str) -> Tuple[bool, Optional[str]]:
        """
        Validate a URL.

        Args:
            url: URL to validate

        Returns:
            Tuple of (is_valid, error_message)
        """
        if not url:
            return False, "URL is empty"

        if not self.URL_PATTERN.match(url):
            return False, "Invalid URL format"

        try:
            parsed = urlparse(url)
            if not parsed.scheme or not parsed.netloc:
                return False, "URL missing scheme or domain"
        except Exception as e:
            return False, f"URL parsing error: {str(e)}"

        return True, None

    def validate_urls(self, urls: List[str]) -> Dict[str, Tuple[bool, Optional[str]]]:
        """
        Validate multiple URLs.

        Args:
            urls: List of URLs to validate

        Returns:
            Dictionary mapping URLs to (is_valid, error_message) tuples
        """
        return {url: self.validate_url(url) for url in urls}

    def extract_source_metadata(self, url: str) -> Dict[str, Any]:
        """
        Extract metadata from a source URL.

        Args:
            url: Source URL

        Returns:
            Dictionary with extracted metadata
        """
        metadata = {
            'url': url,
            'domain': None,
            'type': 'unknown',
            'title_hint': None,
            'author_hint': None
        }

        if not url:
            return metadata

        try:
            parsed = urlparse(url)
            domain = parsed.netloc.lower()

            # Remove www. prefix
            if domain.startswith('www.'):
                domain = domain[4:]

            metadata['domain'] = domain

            # Check known domain patterns
            for pattern_domain, pattern_info in self.DOMAIN_PATTERNS.items():
                if pattern_domain in domain:
                    metadata['type'] = pattern_info['type']
                    metadata['author_hint'] = pattern_info['author_hint']

                    # Try to extract title from URL
                    if pattern_info['title_pattern']:
                        match = re.search(pattern_info['title_pattern'], url)
                        if match:
                            title = match.group(1)
                            # Clean up title
                            title = title.replace('-', ' ').replace('_', ' ')
                            metadata['title_hint'] = title.title()
                    break

            # Extract path-based hints
            path = parsed.path
            if path and path != '/':
                # Last meaningful segment might be title
                segments = [s for s in path.split('/') if s and not s.startswith('?')]
                if segments:
                    last_segment = segments[-1]
                    # Remove file extensions
                    last_segment = re.sub(r'\.(html?|php|aspx?|jsp)$', '', last_segment)
                    if not metadata['title_hint'] and len(last_segment) > 3:
                        title = last_segment.replace('-', ' ').replace('_', ' ')
                        metadata['title_hint'] = title.title()

        except Exception:
            pass

        return metadata

    def _extract_domain(self, url: str) -> Optional[str]:
        """Extract domain from URL."""
        try:
            parsed = urlparse(url)
            domain = parsed.netloc.lower()
            if domain.startswith('www.'):
                domain = domain[4:]
            return domain
        except Exception:
            return None

    def _extract_title_from_url(self, url: str) -> Optional[str]:
        """Try to extract a title from URL."""
        metadata = self.extract_source_metadata(url)
        return metadata.get('title_hint')

    def get_citation_by_number(self, number: int) -> Optional[Citation]:
        """
        Get a citation by its number.

        Args:
            number: Citation number

        Returns:
            Citation object or None
        """
        for citation in self._citations.values():
            if citation.number == number:
                return citation
        return None

    def get_citation_by_url(self, url: str) -> Optional[Citation]:
        """
        Get a citation by its URL.

        Args:
            url: Citation URL

        Returns:
            Citation object or None
        """
        return self._citations.get(url)

    def get_all_citations(self) -> List[Citation]:
        """
        Get all citations sorted by number.

        Returns:
            List of all Citation objects
        """
        return sorted(self._citations.values(), key=lambda c: c.number)

    def reset(self):
        """Reset the formatter, clearing all citations."""
        self._citation_counter = 0
        self._citations = {}

    def to_bibliography(self) -> Bibliography:
        """
        Convert current citations to a Bibliography object.

        Returns:
            Bibliography object
        """
        return Bibliography(
            citations=self.get_all_citations(),
            style=self.style
        )


def main():
    """CLI demo for citation formatter."""
    print("Citation Formatter Demo")
    print("=" * 40)

    formatter = CitationFormatter()

    # Add some sample citations
    sources = [
        {
            'url': 'https://arxiv.org/abs/2301.12345',
            'title': 'Advanced Machine Learning Techniques',
            'author': 'Smith et al.',
            'date': '2024-06',
            'agent': 'academic-scanner',
            'relevance': 0.95
        },
        {
            'url': 'https://github.com/example/ml-library',
            'title': 'ML Library Repository',
            'agent': 'technical-diver',
            'relevance': 0.85
        },
        {
            'url': 'https://medium.com/@author/understanding-llms-abc123',
            'title': 'Understanding LLMs: A Practical Guide',
            'date': '2024-07',
            'agent': 'market-analyst',
            'relevance': 0.70
        },
        {
            'url': 'https://stackoverflow.com/questions/123456/how-to-train-model',
            'title': 'How to Train a Model Efficiently',
            'agent': 'technical-diver',
            'relevance': 0.65
        }
    ]

    print("\nAdding citations from sources...")
    formatter.add_citations_from_sources(sources)

    # Test inline formatting
    print("\n--- Inline Citation Tests ---")
    print(f"Single citation: {formatter.format_inline(sources[0]['url'])}")
    print(f"Citation by number: {formatter.format_inline(2)}")
    print(f"Multiple citations: {formatter.format_multiple([1, 2, 3, 4])}")

    # Test URL validation
    print("\n--- URL Validation Tests ---")
    test_urls = [
        'https://example.com/page',
        'http://localhost:8000/api',
        'not-a-url',
        '',
        'ftp://files.example.com/file.pdf'
    ]
    for url in test_urls:
        is_valid, error = formatter.validate_url(url)
        status = "Valid" if is_valid else f"Invalid: {error}"
        print(f"  {url[:40]:40} - {status}")

    # Test metadata extraction
    print("\n--- Metadata Extraction Tests ---")
    for source in sources[:2]:
        metadata = formatter.extract_source_metadata(source['url'])
        print(f"  URL: {source['url']}")
        print(f"    Domain: {metadata['domain']}")
        print(f"    Type: {metadata['type']}")
        print(f"    Title hint: {metadata['title_hint']}")
        print()

    # Generate bibliography
    print("\n--- Markdown Bibliography ---")
    print(formatter.generate_bibliography("markdown"))

    print("\n--- HTML Bibliography ---")
    print(formatter.generate_bibliography("html"))

    print("\n--- Plain Text Bibliography ---")
    print(formatter.generate_bibliography("plain"))


if __name__ == '__main__':
    main()
