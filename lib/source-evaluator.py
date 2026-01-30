#!/usr/bin/env python3
"""
Source Evaluator - Source credibility scoring for research-loop

This module evaluates source credibility based on multiple factors:
- Domain authority (known reputable sources)
- Author credentials (when available)
- Publication date (recency scoring)
- Citation count (academic influence)

Maintains a credibility store for learning from corrections.

Usage:
    python3 source-evaluator.py score <url> [--json]
    python3 source-evaluator.py batch <urls_file> [--json]
    python3 source-evaluator.py update <domain> <score> [--reason <reason>]
    python3 source-evaluator.py list [--low-credibility]
"""

import argparse
import json
import os
import re
import sys
from dataclasses import dataclass, asdict, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from urllib.parse import urlparse


# Default paths
SCRIPT_DIR = Path(__file__).parent
DATA_DIR = SCRIPT_DIR.parent / "data"
DEFAULT_STORE_PATH = DATA_DIR / "source-credibility-store.json"


class CredibilityLevel(str, Enum):
    """Credibility level classifications."""
    HIGH = "high"           # Score >= 80
    MEDIUM = "medium"       # Score 50-79
    LOW = "low"             # Score < 50
    UNKNOWN = "unknown"     # No data available


@dataclass
class SourceCredibility:
    """Credibility assessment for a source."""
    domain: str
    score: int  # 0-100
    level: CredibilityLevel
    domain_authority: int  # 0-100
    recency_score: int  # 0-100
    citation_score: int  # 0-100 (if available)
    author_score: int  # 0-100 (if available)
    flags: List[str] = field(default_factory=list)
    notes: str = ""
    last_updated: str = ""

    @property
    def is_low_credibility(self) -> bool:
        return self.score < 50

    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class CredibilityCorrection:
    """Record of a credibility correction for learning."""
    domain: str
    old_score: int
    new_score: int
    reason: str
    timestamp: str
    corrected_by: str = "user"


class SourceEvaluator:
    """
    Evaluates source credibility with persistent learning.

    The evaluator uses a combination of:
    1. Pre-defined domain authority scores
    2. Publication date analysis
    3. Citation counting (when available)
    4. User corrections for continuous learning
    """

    # Domain category authority scores (base scores)
    DOMAIN_CATEGORIES = {
        # Academic & Research (high authority)
        "academic": {
            "base_score": 85,
            "domains": [
                "arxiv.org", "scholar.google.com", "pubmed.ncbi.nlm.nih.gov",
                "ncbi.nlm.nih.gov", "nature.com", "science.org", "cell.com",
                "pnas.org", "ieee.org", "acm.org", "springer.com",
                "sciencedirect.com", "wiley.com", "jstor.org", "researchgate.net"
            ]
        },
        # Government & Institutional (high authority)
        "government": {
            "base_score": 80,
            "domains": [
                "gov", "edu", "mil", "who.int", "un.org", "europa.eu",
                "nist.gov", "cdc.gov", "nih.gov", "fda.gov", "epa.gov",
                "nasa.gov", "nsf.gov"
            ]
        },
        # Major News Organizations (medium-high authority)
        "major_news": {
            "base_score": 70,
            "domains": [
                "reuters.com", "apnews.com", "bbc.com", "bbc.co.uk",
                "nytimes.com", "washingtonpost.com", "wsj.com",
                "economist.com", "theguardian.com", "ft.com"
            ]
        },
        # Tech & Industry Publications (medium authority)
        "tech_publications": {
            "base_score": 65,
            "domains": [
                "techcrunch.com", "wired.com", "arstechnica.com",
                "theverge.com", "zdnet.com", "cnet.com", "engadget.com",
                "hbr.org", "mitsloan.mit.edu", "forbes.com"
            ]
        },
        # Reference & Documentation (high for facts)
        "reference": {
            "base_score": 75,
            "domains": [
                "wikipedia.org", "britannica.com", "merriam-webster.com",
                "docs.python.org", "developer.mozilla.org", "w3.org",
                "rfc-editor.org", "stackoverflow.com"
            ]
        },
        # Social & User-Generated (lower authority)
        "social": {
            "base_score": 35,
            "domains": [
                "reddit.com", "twitter.com", "x.com", "facebook.com",
                "medium.com", "quora.com", "linkedin.com"
            ]
        },
        # Blogs & Personal (variable authority)
        "blogs": {
            "base_score": 40,
            "domains": [
                "blogspot.com", "wordpress.com", "substack.com",
                "ghost.io", "tumblr.com"
            ]
        }
    }

    # Known low-credibility indicators
    LOW_CREDIBILITY_INDICATORS = [
        "fake", "satire", "conspiracy", "clickbait",
        "sponsored", "advertisement", "press-release"
    ]

    def __init__(self, store_path: Optional[Path] = None):
        """
        Initialize the source evaluator.

        Args:
            store_path: Path to credibility store JSON file
        """
        self.store_path = store_path or DEFAULT_STORE_PATH
        self.store: Dict = self._load_store()
        self.corrections: List[CredibilityCorrection] = []

    def _load_store(self) -> Dict:
        """Load credibility store from file."""
        if self.store_path.exists():
            try:
                with open(self.store_path, 'r') as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError) as e:
                print(f"Warning: Could not load store: {e}", file=sys.stderr)

        return {
            "domains": {},
            "corrections": [],
            "metadata": {
                "version": "1.0",
                "last_updated": datetime.utcnow().isoformat() + "Z"
            }
        }

    def save_store(self):
        """Save credibility store to file."""
        self.store["metadata"]["last_updated"] = datetime.utcnow().isoformat() + "Z"

        # Ensure data directory exists
        self.store_path.parent.mkdir(parents=True, exist_ok=True)

        with open(self.store_path, 'w') as f:
            json.dump(self.store, f, indent=2)

    def extract_domain(self, url: str) -> str:
        """Extract domain from URL."""
        try:
            parsed = urlparse(url)
            domain = parsed.netloc.lower()
            # Remove www. prefix
            if domain.startswith("www."):
                domain = domain[4:]
            return domain
        except Exception:
            return url.lower()

    def get_domain_category(self, domain: str) -> Tuple[Optional[str], int]:
        """
        Get the category and base score for a domain.

        Args:
            domain: Domain name

        Returns:
            Tuple of (category_name, base_score) or (None, 50) if unknown
        """
        # Check for exact domain match
        for category, data in self.DOMAIN_CATEGORIES.items():
            if domain in data["domains"]:
                return category, data["base_score"]

        # Check for TLD-based matching (e.g., .edu, .gov)
        for category, data in self.DOMAIN_CATEGORIES.items():
            for cat_domain in data["domains"]:
                if not "." in cat_domain:  # It's a TLD
                    if domain.endswith(f".{cat_domain}"):
                        return category, data["base_score"]

        # Check if domain is a subdomain of a known domain
        for category, data in self.DOMAIN_CATEGORIES.items():
            for cat_domain in data["domains"]:
                if domain.endswith(f".{cat_domain}"):
                    return category, data["base_score"] - 5  # Slight penalty for subdomains

        return None, 50  # Unknown domain, neutral score

    def calculate_recency_score(self, publication_date: Optional[str]) -> int:
        """
        Calculate recency score based on publication date.

        Args:
            publication_date: ISO format date string or None

        Returns:
            Score 0-100 (100 = very recent, 0 = very old)
        """
        if not publication_date:
            return 50  # Unknown date, neutral score

        try:
            # Parse various date formats
            pub_date = None
            for fmt in ["%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d", "%Y"]:
                try:
                    # Try exact format match first, then prefix match for year-only
                    if fmt == "%Y":
                        pub_date = datetime.strptime(publication_date[:4], fmt)
                    else:
                        pub_date = datetime.strptime(publication_date, fmt)
                    break
                except ValueError:
                    continue

            if not pub_date:
                return 50

            days_old = (datetime.utcnow() - pub_date).days

            # Scoring based on age
            if days_old < 30:
                return 100  # Less than a month old
            elif days_old < 90:
                return 90   # Less than 3 months
            elif days_old < 180:
                return 80   # Less than 6 months
            elif days_old < 365:
                return 70   # Less than a year
            elif days_old < 730:
                return 60   # 1-2 years
            elif days_old < 1825:
                return 50   # 2-5 years
            else:
                return max(30, 50 - (days_old - 1825) // 365 * 5)  # Older

        except Exception:
            return 50

    def calculate_citation_score(self, citation_count: Optional[int]) -> int:
        """
        Calculate citation score based on citation count.

        Args:
            citation_count: Number of citations or None

        Returns:
            Score 0-100
        """
        if citation_count is None:
            return 50  # Unknown, neutral score

        if citation_count >= 1000:
            return 100
        elif citation_count >= 500:
            return 90
        elif citation_count >= 100:
            return 80
        elif citation_count >= 50:
            return 70
        elif citation_count >= 10:
            return 60
        elif citation_count >= 1:
            return 55
        else:
            return 50

    def calculate_author_score(self, author_info: Optional[Dict]) -> int:
        """
        Calculate author credibility score.

        Args:
            author_info: Dictionary with author information

        Returns:
            Score 0-100
        """
        if not author_info:
            return 50  # Unknown author, neutral score

        score = 50

        # Check for institutional affiliation
        if author_info.get("affiliation"):
            affiliation = author_info["affiliation"].lower()
            if any(term in affiliation for term in ["university", "institute", "research", "lab"]):
                score += 20

        # Check for verified credentials
        if author_info.get("verified"):
            score += 15

        # Check for publication history
        pub_count = author_info.get("publication_count", 0)
        if pub_count > 50:
            score += 15
        elif pub_count > 10:
            score += 10
        elif pub_count > 0:
            score += 5

        return min(100, score)

    def check_low_credibility_indicators(self, url: str, content: Optional[str] = None) -> List[str]:
        """
        Check for low credibility indicators.

        Args:
            url: Source URL
            content: Optional content to analyze

        Returns:
            List of flagged indicators
        """
        flags = []
        url_lower = url.lower()

        for indicator in self.LOW_CREDIBILITY_INDICATORS:
            if indicator in url_lower:
                flags.append(f"url_contains_{indicator}")

        if content:
            content_lower = content.lower()
            for indicator in self.LOW_CREDIBILITY_INDICATORS:
                if indicator in content_lower:
                    flags.append(f"content_contains_{indicator}")

        return flags

    def evaluate(
        self,
        url: str,
        publication_date: Optional[str] = None,
        citation_count: Optional[int] = None,
        author_info: Optional[Dict] = None,
        content: Optional[str] = None
    ) -> SourceCredibility:
        """
        Evaluate source credibility.

        Args:
            url: Source URL
            publication_date: Publication date (ISO format)
            citation_count: Number of citations
            author_info: Author information dictionary
            content: Optional content for analysis

        Returns:
            SourceCredibility assessment
        """
        domain = self.extract_domain(url)

        # Check if we have a stored override
        if domain in self.store.get("domains", {}):
            stored = self.store["domains"][domain]
            domain_authority = stored.get("score", 50)
        else:
            _, domain_authority = self.get_domain_category(domain)

        # Calculate component scores
        recency_score = self.calculate_recency_score(publication_date)
        citation_score = self.calculate_citation_score(citation_count)
        author_score = self.calculate_author_score(author_info)

        # Check for low credibility indicators
        flags = self.check_low_credibility_indicators(url, content)

        # Calculate weighted overall score
        # Domain authority: 40%, Recency: 20%, Citations: 25%, Author: 15%
        overall_score = int(
            domain_authority * 0.40 +
            recency_score * 0.20 +
            citation_score * 0.25 +
            author_score * 0.15
        )

        # Apply penalty for low credibility flags
        flag_penalty = len(flags) * 10
        overall_score = max(0, overall_score - flag_penalty)

        # Determine credibility level
        if overall_score >= 80:
            level = CredibilityLevel.HIGH
        elif overall_score >= 50:
            level = CredibilityLevel.MEDIUM
        else:
            level = CredibilityLevel.LOW

        return SourceCredibility(
            domain=domain,
            score=overall_score,
            level=level,
            domain_authority=domain_authority,
            recency_score=recency_score,
            citation_score=citation_score,
            author_score=author_score,
            flags=flags,
            notes="",
            last_updated=datetime.utcnow().isoformat() + "Z"
        )

    def update_domain_credibility(
        self,
        domain: str,
        new_score: int,
        reason: str,
        corrected_by: str = "user"
    ):
        """
        Update domain credibility score (learning from corrections).

        Args:
            domain: Domain to update
            new_score: New credibility score (0-100)
            reason: Reason for the update
            corrected_by: Who made the correction
        """
        # Get old score
        old_score = self.store.get("domains", {}).get(domain, {}).get("score", 50)

        # Record correction for learning
        correction = {
            "domain": domain,
            "old_score": old_score,
            "new_score": new_score,
            "reason": reason,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "corrected_by": corrected_by
        }

        if "corrections" not in self.store:
            self.store["corrections"] = []
        self.store["corrections"].append(correction)

        # Update domain score
        if "domains" not in self.store:
            self.store["domains"] = {}

        self.store["domains"][domain] = {
            "score": new_score,
            "reason": reason,
            "last_updated": datetime.utcnow().isoformat() + "Z"
        }

        self.save_store()

    def get_low_credibility_sources(self) -> List[Dict]:
        """
        Get all sources flagged as low credibility.

        Returns:
            List of low credibility domain records
        """
        low_cred = []
        for domain, data in self.store.get("domains", {}).items():
            if data.get("score", 50) < 50:
                low_cred.append({
                    "domain": domain,
                    **data
                })
        return low_cred

    def batch_evaluate(self, urls: List[str]) -> List[SourceCredibility]:
        """
        Evaluate multiple URLs.

        Args:
            urls: List of URLs to evaluate

        Returns:
            List of SourceCredibility assessments
        """
        return [self.evaluate(url) for url in urls]


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Source Credibility Evaluator for research-loop",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    source-evaluator.py score https://arxiv.org/abs/2301.00001
    source-evaluator.py score https://example.com/article --json
    source-evaluator.py update example.com 30 --reason "Known unreliable source"
    source-evaluator.py list --low-credibility
"""
    )

    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # score command
    score_parser = subparsers.add_parser("score", help="Score a URL's credibility")
    score_parser.add_argument("url", help="URL to evaluate")
    score_parser.add_argument("--publication-date", help="Publication date (ISO format)")
    score_parser.add_argument("--citations", type=int, help="Citation count")
    score_parser.add_argument("--json", action="store_true", help="Output as JSON")

    # batch command
    batch_parser = subparsers.add_parser("batch", help="Score multiple URLs from file")
    batch_parser.add_argument("urls_file", help="File with URLs (one per line)")
    batch_parser.add_argument("--json", action="store_true", help="Output as JSON")

    # update command
    update_parser = subparsers.add_parser("update", help="Update domain credibility score")
    update_parser.add_argument("domain", help="Domain to update")
    update_parser.add_argument("score", type=int, help="New score (0-100)")
    update_parser.add_argument("--reason", required=True, help="Reason for update")

    # list command
    list_parser = subparsers.add_parser("list", help="List credibility data")
    list_parser.add_argument("--low-credibility", action="store_true", help="Show only low credibility sources")
    list_parser.add_argument("--json", action="store_true", help="Output as JSON")

    args = parser.parse_args()
    evaluator = SourceEvaluator()

    if args.command == "score":
        result = evaluator.evaluate(
            args.url,
            publication_date=getattr(args, 'publication_date', None),
            citation_count=getattr(args, 'citations', None)
        )

        if args.json:
            print(json.dumps(result.to_dict(), indent=2))
        else:
            print(f"\nCredibility Assessment for: {args.url}")
            print(f"  Domain: {result.domain}")
            print(f"  Overall Score: {result.score}/100 ({result.level.value.upper()})")
            print(f"  Domain Authority: {result.domain_authority}/100")
            print(f"  Recency Score: {result.recency_score}/100")
            print(f"  Citation Score: {result.citation_score}/100")
            print(f"  Author Score: {result.author_score}/100")
            if result.flags:
                print(f"  Flags: {', '.join(result.flags)}")
            if result.is_low_credibility:
                print(f"\n  WARNING: Low credibility source (score < 50)")

        return 0 if not result.is_low_credibility else 1

    elif args.command == "batch":
        with open(args.urls_file, 'r') as f:
            urls = [line.strip() for line in f if line.strip()]

        results = evaluator.batch_evaluate(urls)

        if args.json:
            output = [r.to_dict() for r in results]
            print(json.dumps(output, indent=2))
        else:
            low_count = sum(1 for r in results if r.is_low_credibility)
            print(f"\nEvaluated {len(results)} URLs")
            print(f"Low credibility: {low_count}")
            print()
            for result in results:
                status = "LOW" if result.is_low_credibility else "OK"
                print(f"  [{status}] {result.domain}: {result.score}/100")

        return 0

    elif args.command == "update":
        if not 0 <= args.score <= 100:
            print("Error: Score must be between 0 and 100", file=sys.stderr)
            return 1

        evaluator.update_domain_credibility(args.domain, args.score, args.reason)
        print(f"Updated {args.domain} credibility to {args.score}/100")
        print(f"Reason: {args.reason}")
        return 0

    elif args.command == "list":
        if args.low_credibility:
            sources = evaluator.get_low_credibility_sources()

            if args.json:
                print(json.dumps(sources, indent=2))
            else:
                if not sources:
                    print("No low credibility sources flagged")
                else:
                    print(f"\nLow Credibility Sources ({len(sources)}):")
                    for source in sources:
                        print(f"  {source['domain']}: {source.get('score', 'N/A')}/100")
                        if source.get('reason'):
                            print(f"    Reason: {source['reason']}")
        else:
            if args.json:
                print(json.dumps(evaluator.store, indent=2))
            else:
                domains = evaluator.store.get("domains", {})
                print(f"\nCredibility Store: {len(domains)} domains")
                for domain, data in domains.items():
                    print(f"  {domain}: {data.get('score', 'N/A')}/100")

        return 0

    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main())
