#!/usr/bin/env python3
"""
Confidence Scorer - Scores research confidence based on multiple factors

This module provides confidence scoring based on:
1. Number of sources
2. Source agreement
3. Source recency
4. Source authority
5. Domain-specific weighting
"""

from dataclasses import dataclass
from typing import List, Dict, Optional
from datetime import datetime
from urllib.parse import urlparse


@dataclass
class ConfidenceScore:
    """Represents a confidence score with breakdown."""
    score: int  # 0-100
    explanation: str
    breakdown: Dict[str, float]  # Factor -> contribution

    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            'score': self.score,
            'explanation': self.explanation,
            'breakdown': self.breakdown
        }


class ConfidenceScorer:
    """Scores research confidence based on multiple weighted factors."""

    # Domain-specific weight configurations
    DOMAIN_WEIGHTS = {
        'ai-ml': {
            'source_count': 0.20,
            'source_agreement': 0.25,
            'recency': 0.25,
            'authority': 0.30
        },
        'investment': {
            'source_count': 0.15,
            'source_agreement': 0.20,
            'recency': 0.30,
            'authority': 0.35
        },
        'general': {
            'source_count': 0.25,
            'source_agreement': 0.25,
            'recency': 0.20,
            'authority': 0.30
        }
    }

    # Authority scores for known domains
    DOMAIN_AUTHORITY = {
        # Academic/Research (high authority)
        'arxiv.org': 0.95,
        'scholar.google.com': 0.90,
        'nature.com': 0.95,
        'science.org': 0.95,
        'acm.org': 0.90,
        'ieee.org': 0.90,
        'pubmed.ncbi.nlm.nih.gov': 0.95,

        # Technical documentation (high authority)
        'docs.python.org': 0.90,
        'developer.mozilla.org': 0.90,
        'docs.microsoft.com': 0.85,
        'cloud.google.com': 0.85,
        'aws.amazon.com': 0.85,

        # Reputable tech sources
        'github.com': 0.75,
        'stackoverflow.com': 0.70,
        'medium.com': 0.50,
        'dev.to': 0.50,

        # News/General
        'wikipedia.org': 0.70,
        'reuters.com': 0.80,
        'bloomberg.com': 0.80,
        'nytimes.com': 0.75,

        # AI-specific
        'openai.com': 0.90,
        'anthropic.com': 0.90,
        'huggingface.co': 0.85,
        'deepmind.google': 0.90,

        # Default for unknown domains
        '_default': 0.50
    }

    def __init__(self, domain: str = 'general'):
        """
        Initialize the confidence scorer.

        Args:
            domain: Research domain for weight selection (ai-ml, investment, general)
        """
        self.domain = domain
        self.weights = self.DOMAIN_WEIGHTS.get(domain, self.DOMAIN_WEIGHTS['general'])

    def score(
        self,
        sources: List[Dict],
        gaps: int = 0,
        conflicts: int = 0
    ) -> ConfidenceScore:
        """
        Calculate confidence score based on sources and context.

        Args:
            sources: List of source dictionaries with url, date, relevance
            gaps: Number of identified gaps (reduces confidence)
            conflicts: Number of unresolved conflicts (reduces confidence)

        Returns:
            ConfidenceScore with score, explanation, and breakdown
        """
        breakdown = {}

        # Calculate each factor score (0-100)
        source_count_score = self._score_source_count(sources)
        agreement_score = self._score_source_agreement(sources)
        recency_score = self._score_recency(sources)
        authority_score = self._score_authority(sources)

        breakdown['source_count'] = source_count_score
        breakdown['source_agreement'] = agreement_score
        breakdown['recency'] = recency_score
        breakdown['authority'] = authority_score

        # Calculate weighted score
        weighted_score = (
            source_count_score * self.weights['source_count'] +
            agreement_score * self.weights['source_agreement'] +
            recency_score * self.weights['recency'] +
            authority_score * self.weights['authority']
        )

        # Apply penalties for gaps and conflicts
        gap_penalty = min(gaps * 5, 25)  # Max 25 point penalty
        conflict_penalty = min(conflicts * 10, 30)  # Max 30 point penalty

        breakdown['gap_penalty'] = -gap_penalty
        breakdown['conflict_penalty'] = -conflict_penalty

        final_score = max(0, min(100, int(weighted_score - gap_penalty - conflict_penalty)))

        # Generate explanation
        explanation = self._generate_explanation(
            final_score, breakdown, len(sources), gaps, conflicts
        )

        return ConfidenceScore(
            score=final_score,
            explanation=explanation,
            breakdown=breakdown
        )

    def score_single_source(self, source: Dict) -> float:
        """
        Score a single source for quality.

        Args:
            source: Source dictionary with url, date, etc.

        Returns:
            Score from 0.0 to 1.0
        """
        authority = self._get_domain_authority(source.get('url', ''))
        recency = self._calculate_recency_score(source.get('date'))
        relevance = source.get('relevance', 0.5)

        return (authority * 0.4 + recency * 0.3 + relevance * 0.3)

    def _score_source_count(self, sources: List[Dict]) -> float:
        """
        Score based on number of sources.

        More sources generally means higher confidence, with diminishing returns.

        Args:
            sources: List of sources

        Returns:
            Score from 0 to 100
        """
        count = len(sources)

        if count == 0:
            return 0
        elif count == 1:
            return 30
        elif count == 2:
            return 50
        elif count <= 4:
            return 70
        elif count <= 7:
            return 85
        else:
            return min(100, 85 + (count - 7) * 2)  # Diminishing returns

    def _score_source_agreement(self, sources: List[Dict]) -> float:
        """
        Score based on how well sources agree.

        This is a simplified version - a real implementation would
        analyze content similarity.

        Args:
            sources: List of sources

        Returns:
            Score from 0 to 100
        """
        if len(sources) <= 1:
            return 50  # Can't measure agreement with one source

        # Use agent diversity as a proxy for independent verification
        agents = set(s.get('agent', 'unknown') for s in sources)

        if len(agents) >= 3:
            return 90  # Multiple perspectives agree
        elif len(agents) == 2:
            return 75  # Two perspectives
        else:
            # Same agent multiple times - check URL diversity
            urls = set(s.get('url', '') for s in sources)
            if len(urls) >= 3:
                return 70
            else:
                return 50

    def _score_recency(self, sources: List[Dict]) -> float:
        """
        Score based on how recent the sources are.

        Args:
            sources: List of sources with optional date field

        Returns:
            Score from 0 to 100
        """
        if not sources:
            return 50

        recency_scores = []
        for source in sources:
            date_str = source.get('date')
            score = self._calculate_recency_score(date_str)
            recency_scores.append(score)

        # Average recency score
        return sum(recency_scores) / len(recency_scores) if recency_scores else 50

    def _calculate_recency_score(self, date_str: Optional[str]) -> float:
        """
        Calculate recency score for a single date.

        Args:
            date_str: ISO format date string or None

        Returns:
            Score from 0 to 100
        """
        if not date_str:
            return 50  # Unknown date

        try:
            # Parse date
            if date_str.endswith('Z'):
                date_str = date_str[:-1] + '+00:00'
            source_date = datetime.fromisoformat(date_str)
            now = datetime.now(source_date.tzinfo) if source_date.tzinfo else datetime.now()

            age_days = (now - source_date).days

            if age_days < 30:
                return 100  # Very recent
            elif age_days < 90:
                return 90
            elif age_days < 180:
                return 80
            elif age_days < 365:
                return 70
            elif age_days < 730:  # 2 years
                return 55
            else:
                return max(20, 55 - (age_days - 730) // 365 * 10)
        except (ValueError, TypeError):
            return 50  # Can't parse date

    def _score_authority(self, sources: List[Dict]) -> float:
        """
        Score based on source authority/credibility.

        Args:
            sources: List of sources

        Returns:
            Score from 0 to 100
        """
        if not sources:
            return 0

        authority_scores = []
        for source in sources:
            url = source.get('url', '')
            authority = self._get_domain_authority(url)
            authority_scores.append(authority * 100)

        return sum(authority_scores) / len(authority_scores)

    def _get_domain_authority(self, url: str) -> float:
        """
        Get authority score for a URL's domain.

        Args:
            url: Source URL

        Returns:
            Authority score from 0.0 to 1.0
        """
        if not url:
            return self.DOMAIN_AUTHORITY['_default']

        try:
            parsed = urlparse(url)
            domain = parsed.netloc.lower()

            # Remove www. prefix
            if domain.startswith('www.'):
                domain = domain[4:]

            # Check for exact match
            if domain in self.DOMAIN_AUTHORITY:
                return self.DOMAIN_AUTHORITY[domain]

            # Check for subdomain match (e.g., blog.example.com -> example.com)
            parts = domain.split('.')
            if len(parts) > 2:
                parent_domain = '.'.join(parts[-2:])
                if parent_domain in self.DOMAIN_AUTHORITY:
                    return self.DOMAIN_AUTHORITY[parent_domain]

            return self.DOMAIN_AUTHORITY['_default']
        except Exception:
            return self.DOMAIN_AUTHORITY['_default']

    def _generate_explanation(
        self,
        score: int,
        breakdown: Dict[str, float],
        source_count: int,
        gaps: int,
        conflicts: int
    ) -> str:
        """
        Generate human-readable explanation of the score.

        Args:
            score: Final confidence score
            breakdown: Score breakdown by factor
            source_count: Number of sources
            gaps: Number of gaps
            conflicts: Number of conflicts

        Returns:
            Explanation string
        """
        parts = []

        # Overall assessment
        if score >= 90:
            parts.append("Very high confidence.")
        elif score >= 75:
            parts.append("High confidence.")
        elif score >= 60:
            parts.append("Moderate confidence.")
        elif score >= 40:
            parts.append("Low confidence.")
        else:
            parts.append("Very low confidence.")

        # Source count
        if source_count == 0:
            parts.append("No sources found.")
        elif source_count == 1:
            parts.append("Only one source available.")
        else:
            parts.append(f"Based on {source_count} sources.")

        # Key factors
        if breakdown.get('authority', 0) >= 80:
            parts.append("Sources are highly authoritative.")
        elif breakdown.get('authority', 0) < 50:
            parts.append("Source authority is limited.")

        if breakdown.get('recency', 0) >= 80:
            parts.append("Information is recent.")
        elif breakdown.get('recency', 0) < 50:
            parts.append("Some information may be outdated.")

        # Issues
        if gaps > 0:
            parts.append(f"{gaps} gap(s) identified.")
        if conflicts > 0:
            parts.append(f"{conflicts} conflict(s) unresolved.")

        return ' '.join(parts)

    def get_weights(self) -> Dict[str, float]:
        """
        Get current domain weights.

        Returns:
            Dictionary of factor weights
        """
        return self.weights.copy()

    def set_custom_weights(self, weights: Dict[str, float]):
        """
        Set custom weights for scoring factors.

        Args:
            weights: Dictionary with source_count, source_agreement, recency, authority keys

        Raises:
            ValueError: If weights don't sum to 1.0 or missing keys
        """
        required_keys = {'source_count', 'source_agreement', 'recency', 'authority'}
        if not required_keys.issubset(weights.keys()):
            raise ValueError(f"Weights must include all keys: {required_keys}")

        total = sum(weights[k] for k in required_keys)
        if abs(total - 1.0) > 0.01:
            raise ValueError(f"Weights must sum to 1.0, got {total}")

        self.weights = {k: weights[k] for k in required_keys}


def main():
    """CLI demo for confidence scorer."""
    import json

    print("Confidence Scorer Demo")
    print("=" * 40)

    # Demo sources
    sources = [
        {
            'url': 'https://arxiv.org/abs/2301.12345',
            'date': '2024-06-15T00:00:00Z',
            'relevance': 0.95,
            'agent': 'academic-scanner'
        },
        {
            'url': 'https://github.com/example/repo',
            'date': '2024-08-01T00:00:00Z',
            'relevance': 0.80,
            'agent': 'technical-diver'
        },
        {
            'url': 'https://medium.com/article',
            'date': '2024-07-20T00:00:00Z',
            'relevance': 0.70,
            'agent': 'technical-diver'
        }
    ]

    # Test different domains
    for domain in ['ai-ml', 'investment', 'general']:
        print(f"\nDomain: {domain}")
        print("-" * 30)

        scorer = ConfidenceScorer(domain=domain)
        result = scorer.score(sources, gaps=1, conflicts=0)

        print(f"Score: {result.score}/100")
        print(f"Explanation: {result.explanation}")
        print(f"Breakdown: {json.dumps(result.breakdown, indent=2)}")


if __name__ == '__main__':
    main()
