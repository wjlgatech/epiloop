#!/usr/bin/env python3
"""
Experience Compressor - Pattern Extraction for CER

This module extracts reusable patterns from research experiences to enable
efficient knowledge transfer to future research sessions.

Pattern Types:
1. Search Strategy Patterns - What sources/methods worked well
2. Question Decomposition Patterns - How to break down complex questions
3. Source Quality Patterns - Which sources are reliable for which domains
4. Synthesis Patterns - How findings were effectively combined

Usage:
    from experience_compressor import ExperienceCompressor

    compressor = ExperienceCompressor()
    pattern = compressor.extract_pattern(experience)
    snippets = compressor.get_reusable_snippets(experience)
"""

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set
from collections import Counter


# ============================================================================
# Pattern Data Classes
# ============================================================================

@dataclass
class SearchStrategyPattern:
    """Pattern describing successful search strategies."""
    domain: str
    source_types: List[str]  # arxiv, github, news, etc.
    search_terms: List[str]  # Effective search terms
    success_rate: float  # 0.0-1.0
    avg_relevance: float  # 0.0-1.0

    def to_dict(self) -> Dict:
        return {
            'type': 'search_strategy',
            'domain': self.domain,
            'source_types': self.source_types,
            'search_terms': self.search_terms,
            'success_rate': self.success_rate,
            'avg_relevance': self.avg_relevance
        }


@dataclass
class DecompositionPattern:
    """Pattern for question decomposition."""
    domain: str
    original_type: str  # research, technical, market
    sub_question_types: List[str]
    num_sub_questions: int
    effectiveness_score: float  # Based on coverage

    def to_dict(self) -> Dict:
        return {
            'type': 'decomposition',
            'domain': self.domain,
            'original_type': self.original_type,
            'sub_question_types': self.sub_question_types,
            'num_sub_questions': self.num_sub_questions,
            'effectiveness_score': self.effectiveness_score
        }


@dataclass
class SourceQualityPattern:
    """Pattern for source quality assessment."""
    domain: str
    source_domain: str  # arxiv.org, github.com, etc.
    avg_relevance: float
    frequency: int
    typical_content_types: List[str]

    def to_dict(self) -> Dict:
        return {
            'type': 'source_quality',
            'domain': self.domain,
            'source_domain': self.source_domain,
            'avg_relevance': self.avg_relevance,
            'frequency': self.frequency,
            'typical_content_types': self.typical_content_types
        }


@dataclass
class SynthesisPattern:
    """Pattern for synthesis approach."""
    domain: str
    num_sources: int
    confidence_achieved: int
    gap_types_found: List[str]
    conflict_resolution_used: bool
    synthesis_length: int  # Approximate tokens

    def to_dict(self) -> Dict:
        return {
            'type': 'synthesis',
            'domain': self.domain,
            'num_sources': self.num_sources,
            'confidence_achieved': self.confidence_achieved,
            'gap_types_found': self.gap_types_found,
            'conflict_resolution_used': self.conflict_resolution_used,
            'synthesis_length': self.synthesis_length
        }


@dataclass
class CompressedExperience:
    """Fully compressed experience with all extracted patterns."""
    experience_id: str
    domain: str
    search_pattern: Optional[SearchStrategyPattern] = None
    decomposition_pattern: Optional[DecompositionPattern] = None
    source_patterns: List[SourceQualityPattern] = field(default_factory=list)
    synthesis_pattern: Optional[SynthesisPattern] = None
    key_learnings: List[str] = field(default_factory=list)
    compressed_text: str = ""

    def to_dict(self) -> Dict:
        return {
            'experience_id': self.experience_id,
            'domain': self.domain,
            'search_pattern': self.search_pattern.to_dict() if self.search_pattern else None,
            'decomposition_pattern': self.decomposition_pattern.to_dict() if self.decomposition_pattern else None,
            'source_patterns': [sp.to_dict() for sp in self.source_patterns],
            'synthesis_pattern': self.synthesis_pattern.to_dict() if self.synthesis_pattern else None,
            'key_learnings': self.key_learnings,
            'compressed_text': self.compressed_text
        }


# ============================================================================
# Experience Compressor
# ============================================================================

class ExperienceCompressor:
    """
    Extracts reusable patterns from research experiences.

    Compresses experiences into structured patterns that can be
    injected into future research prompts for improved performance.
    """

    # Keywords for categorizing questions
    QUESTION_TYPE_KEYWORDS = {
        'technical': ['how', 'implement', 'code', 'build', 'create', 'setup', 'configure'],
        'academic': ['research', 'study', 'paper', 'theory', 'analysis', 'evidence'],
        'market': ['market', 'cost', 'price', 'trend', 'competition', 'industry'],
        'comparison': ['compare', 'difference', 'versus', 'vs', 'better', 'best'],
        'definition': ['what is', 'what are', 'define', 'explain', 'meaning'],
        'evaluation': ['evaluate', 'assess', 'review', 'pros', 'cons', 'advantages']
    }

    # Source domain patterns
    SOURCE_PATTERNS = {
        'arxiv': r'arxiv\.org',
        'github': r'github\.com',
        'stackoverflow': r'stackoverflow\.com',
        'docs': r'(docs\.|documentation|readthedocs)',
        'news': r'(news\.|blog\.|medium\.com|techcrunch)',
        'wiki': r'(wikipedia\.org|wiki\.)',
        'academic': r'(scholar\.google|ieee\.org|acm\.org|springer\.com)',
        'corporate': r'(\.com/blog|press-release|newsroom)'
    }

    def __init__(self):
        """Initialize the experience compressor."""
        pass

    def extract_pattern(self, experience: Any) -> CompressedExperience:
        """
        Extract all patterns from an experience.

        Args:
            experience: Experience object to compress

        Returns:
            CompressedExperience with all extracted patterns
        """
        compressed = CompressedExperience(
            experience_id=experience.id,
            domain=experience.domain
        )

        # Extract search strategy pattern
        compressed.search_pattern = self._extract_search_pattern(experience)

        # Extract decomposition pattern
        compressed.decomposition_pattern = self._extract_decomposition_pattern(experience)

        # Extract source quality patterns
        compressed.source_patterns = self._extract_source_patterns(experience)

        # Extract synthesis pattern
        compressed.synthesis_pattern = self._extract_synthesis_pattern(experience)

        # Generate key learnings
        compressed.key_learnings = self._extract_key_learnings(experience)

        # Generate compressed text representation
        compressed.compressed_text = self._generate_compressed_text(compressed)

        return compressed

    def _extract_search_pattern(self, experience: Any) -> Optional[SearchStrategyPattern]:
        """Extract search strategy patterns from experience."""
        if not experience.findings:
            return None

        # Analyze source types
        source_types = []
        relevance_scores = []

        for finding in experience.findings:
            url = finding.get('source_url', '')
            relevance = finding.get('relevance_score', finding.get('relevance', 0.5))
            relevance_scores.append(relevance)

            for source_type, pattern in self.SOURCE_PATTERNS.items():
                if re.search(pattern, url, re.IGNORECASE):
                    source_types.append(source_type)
                    break
            else:
                source_types.append('web')

        # Extract search terms from query
        search_terms = self._extract_search_terms(experience.query)

        # Calculate metrics
        source_type_counts = Counter(source_types)
        top_sources = [s for s, _ in source_type_counts.most_common(3)]
        avg_relevance = sum(relevance_scores) / len(relevance_scores) if relevance_scores else 0.5

        # Success rate based on confidence
        success_rate = experience.confidence / 100.0

        return SearchStrategyPattern(
            domain=experience.domain,
            source_types=top_sources,
            search_terms=search_terms,
            success_rate=success_rate,
            avg_relevance=avg_relevance
        )

    def _extract_decomposition_pattern(self, experience: Any) -> Optional[DecompositionPattern]:
        """Extract question decomposition patterns."""
        if not experience.sub_questions:
            return None

        # Categorize original question
        original_type = self._categorize_question(experience.query)

        # Categorize sub-questions
        sub_types = [self._categorize_question(sq) for sq in experience.sub_questions]
        sub_type_counts = Counter(sub_types)

        # Calculate effectiveness based on confidence
        effectiveness = experience.confidence / 100.0

        return DecompositionPattern(
            domain=experience.domain,
            original_type=original_type,
            sub_question_types=[t for t, _ in sub_type_counts.most_common()],
            num_sub_questions=len(experience.sub_questions),
            effectiveness_score=effectiveness
        )

    def _extract_source_patterns(self, experience: Any) -> List[SourceQualityPattern]:
        """Extract source quality patterns."""
        if not experience.findings:
            return []

        # Group findings by source domain
        source_groups: Dict[str, List[Dict]] = {}

        for finding in experience.findings:
            url = finding.get('source_url', '')
            domain = self._extract_domain(url)
            if domain:
                if domain not in source_groups:
                    source_groups[domain] = []
                source_groups[domain].append(finding)

        # Create patterns for each source domain
        patterns = []
        for source_domain, findings in source_groups.items():
            relevance_scores = [
                f.get('relevance_score', f.get('relevance', 0.5))
                for f in findings
            ]
            avg_relevance = sum(relevance_scores) / len(relevance_scores)

            # Determine content types
            content_types = self._infer_content_types(source_domain, findings)

            patterns.append(SourceQualityPattern(
                domain=experience.domain,
                source_domain=source_domain,
                avg_relevance=avg_relevance,
                frequency=len(findings),
                typical_content_types=content_types
            ))

        # Sort by relevance
        patterns.sort(key=lambda p: p.avg_relevance, reverse=True)

        return patterns[:5]  # Top 5 source patterns

    def _extract_synthesis_pattern(self, experience: Any) -> Optional[SynthesisPattern]:
        """Extract synthesis patterns."""
        num_sources = len(experience.findings) if experience.findings else 0

        # Infer gap types from synthesis text
        gap_types = []
        synthesis_lower = experience.synthesis.lower() if experience.synthesis else ''

        if 'coverage' in synthesis_lower or 'missing' in synthesis_lower:
            gap_types.append('coverage')
        if 'conflict' in synthesis_lower or 'contradict' in synthesis_lower:
            gap_types.append('conflict')
        if 'depth' in synthesis_lower or 'shallow' in synthesis_lower:
            gap_types.append('depth')
        if 'recent' in synthesis_lower or 'outdated' in synthesis_lower:
            gap_types.append('recency')

        # Check for conflict resolution
        conflict_resolution = 'however' in synthesis_lower or 'although' in synthesis_lower

        return SynthesisPattern(
            domain=experience.domain,
            num_sources=num_sources,
            confidence_achieved=experience.confidence,
            gap_types_found=gap_types,
            conflict_resolution_used=conflict_resolution,
            synthesis_length=len(experience.synthesis.split()) if experience.synthesis else 0
        )

    def _extract_key_learnings(self, experience: Any) -> List[str]:
        """Extract key learnings from experience."""
        learnings = []

        # Learning from confidence level
        if experience.confidence >= 75:
            learnings.append(f"High confidence ({experience.confidence}%) achieved with current approach")
        elif experience.confidence < 50:
            learnings.append(f"Low confidence ({experience.confidence}%) - consider different sources")

        # Learning from source diversity
        if experience.findings:
            unique_domains = set()
            for f in experience.findings:
                domain = self._extract_domain(f.get('source_url', ''))
                if domain:
                    unique_domains.add(domain)

            if len(unique_domains) >= 3:
                learnings.append(f"Good source diversity: {len(unique_domains)} different domains")
            elif len(unique_domains) == 1:
                learnings.append("Consider diversifying sources beyond single domain")

        # Learning from decomposition
        if experience.sub_questions:
            if len(experience.sub_questions) >= 5:
                learnings.append(f"Comprehensive decomposition: {len(experience.sub_questions)} sub-questions")
            elif len(experience.sub_questions) <= 2:
                learnings.append("Consider more thorough question decomposition")

        return learnings

    def _generate_compressed_text(self, compressed: CompressedExperience) -> str:
        """Generate human-readable compressed text."""
        parts = []

        parts.append(f"Domain: {compressed.domain}")

        if compressed.search_pattern:
            sp = compressed.search_pattern
            parts.append(f"Sources: {', '.join(sp.source_types)} (avg relevance: {sp.avg_relevance:.2f})")

        if compressed.decomposition_pattern:
            dp = compressed.decomposition_pattern
            parts.append(f"Decomposition: {dp.num_sub_questions} questions ({', '.join(dp.sub_question_types)})")

        if compressed.synthesis_pattern:
            sp = compressed.synthesis_pattern
            parts.append(f"Synthesis: {sp.num_sources} sources -> {sp.confidence_achieved}% confidence")

        if compressed.key_learnings:
            parts.append(f"Learnings: {'; '.join(compressed.key_learnings[:2])}")

        return " | ".join(parts)

    def get_reusable_snippets(self, experience: Any) -> List[Dict]:
        """
        Get reusable snippets for prompt injection.

        Args:
            experience: Experience to extract snippets from

        Returns:
            List of snippet dictionaries with type and content
        """
        snippets = []

        # Add search strategy snippet
        if experience.findings:
            successful_sources = [
                f.get('source_url', '')
                for f in experience.findings
                if f.get('relevance_score', f.get('relevance', 0.5)) >= 0.7
            ]
            if successful_sources:
                snippets.append({
                    'type': 'search_strategy',
                    'content': f"For {experience.domain} research, high-relevance sources included: "
                               f"{', '.join(self._extract_domain(s) for s in successful_sources[:3])}"
                })

        # Add decomposition snippet
        if experience.sub_questions and experience.confidence >= 60:
            snippets.append({
                'type': 'decomposition',
                'content': f"Effective decomposition pattern: {len(experience.sub_questions)} sub-questions "
                           f"covering {self._categorize_question(experience.query)} aspects"
            })

        # Add synthesis approach snippet
        if experience.synthesis and experience.confidence >= 70:
            # Extract first sentence as approach
            first_sentence = experience.synthesis.split('.')[0] + '.'
            if len(first_sentence) < 200:
                snippets.append({
                    'type': 'synthesis_approach',
                    'content': f"Previous successful synthesis approach: {first_sentence}"
                })

        return snippets

    def _extract_search_terms(self, query: str) -> List[str]:
        """Extract meaningful search terms from query."""
        # Remove common words
        stop_words = {
            'what', 'how', 'why', 'when', 'where', 'is', 'are', 'the', 'a', 'an',
            'to', 'for', 'of', 'in', 'on', 'with', 'and', 'or', 'but', 'can', 'do'
        }

        words = query.lower().split()
        terms = [w for w in words if w not in stop_words and len(w) > 2]

        return terms[:5]

    def _categorize_question(self, question: str) -> str:
        """Categorize a question by type."""
        question_lower = question.lower()

        for category, keywords in self.QUESTION_TYPE_KEYWORDS.items():
            if any(kw in question_lower for kw in keywords):
                return category

        return 'general'

    def _extract_domain(self, url: str) -> Optional[str]:
        """Extract domain from URL."""
        if not url:
            return None

        # Simple domain extraction
        match = re.search(r'(?:https?://)?(?:www\.)?([^/]+)', url)
        if match:
            return match.group(1)

        return None

    def _infer_content_types(self, source_domain: str, findings: List[Dict]) -> List[str]:
        """Infer content types from source domain and findings."""
        content_types = []

        if 'arxiv' in source_domain:
            content_types = ['research_paper', 'preprint']
        elif 'github' in source_domain:
            content_types = ['code', 'documentation']
        elif 'stackoverflow' in source_domain:
            content_types = ['q_and_a', 'code_snippets']
        elif 'wikipedia' in source_domain:
            content_types = ['encyclopedic', 'overview']
        elif any(news in source_domain for news in ['news', 'blog', 'medium']):
            content_types = ['news', 'opinion', 'tutorial']
        else:
            content_types = ['general']

        return content_types


# ============================================================================
# Batch Compression Utilities
# ============================================================================

def compress_experiences(experiences: List[Any]) -> Dict:
    """
    Compress multiple experiences and aggregate patterns.

    Args:
        experiences: List of Experience objects

    Returns:
        Dictionary with aggregated patterns and insights
    """
    compressor = ExperienceCompressor()

    # Compress each experience
    compressed_list = [compressor.extract_pattern(exp) for exp in experiences]

    # Aggregate search patterns by domain
    search_patterns_by_domain: Dict[str, List[SearchStrategyPattern]] = {}
    for c in compressed_list:
        if c.search_pattern:
            domain = c.domain
            if domain not in search_patterns_by_domain:
                search_patterns_by_domain[domain] = []
            search_patterns_by_domain[domain].append(c.search_pattern)

    # Find most successful patterns per domain
    best_patterns = {}
    for domain, patterns in search_patterns_by_domain.items():
        patterns.sort(key=lambda p: p.success_rate, reverse=True)
        if patterns:
            best_patterns[domain] = patterns[0].to_dict()

    # Aggregate source quality
    source_quality: Dict[str, List[float]] = {}
    for c in compressed_list:
        for sp in c.source_patterns:
            if sp.source_domain not in source_quality:
                source_quality[sp.source_domain] = []
            source_quality[sp.source_domain].append(sp.avg_relevance)

    avg_source_quality = {
        domain: sum(scores) / len(scores)
        for domain, scores in source_quality.items()
    }

    # Collect all learnings
    all_learnings = []
    for c in compressed_list:
        all_learnings.extend(c.key_learnings)

    # Find most common learnings
    learning_counts = Counter(all_learnings)
    top_learnings = [l for l, _ in learning_counts.most_common(5)]

    return {
        'total_experiences': len(experiences),
        'best_search_patterns': best_patterns,
        'source_quality_ranking': dict(sorted(
            avg_source_quality.items(),
            key=lambda x: x[1],
            reverse=True
        )[:10]),
        'top_learnings': top_learnings,
        'compressed_experiences': [c.to_dict() for c in compressed_list]
    }


# ============================================================================
# CLI Interface
# ============================================================================

def main():
    """CLI entry point for experience compressor."""
    import argparse
    import json
    import sys

    parser = argparse.ArgumentParser(description='Experience Compressor - Pattern Extraction for CER')

    parser.add_argument('--json', '-j', action='store_true', help='Output as JSON')

    subparsers = parser.add_subparsers(dest='command', help='Commands')

    # Compress command
    compress_parser = subparsers.add_parser('compress', help='Compress an experience')
    compress_parser.add_argument('--experience', '-e', required=True, help='Experience JSON')

    # Snippets command
    snippets_parser = subparsers.add_parser('snippets', help='Get reusable snippets')
    snippets_parser.add_argument('--experience', '-e', required=True, help='Experience JSON')

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    compressor = ExperienceCompressor()

    if args.command == 'compress':
        # Parse experience
        try:
            exp_data = json.loads(args.experience)
        except json.JSONDecodeError:
            print("Invalid JSON", file=sys.stderr)
            sys.exit(1)

        # Create mock experience object
        class MockExperience:
            pass

        exp = MockExperience()
        for key, value in exp_data.items():
            setattr(exp, key, value)

        compressed = compressor.extract_pattern(exp)

        if args.json:
            print(json.dumps(compressed.to_dict(), indent=2))
        else:
            print(compressed.compressed_text)

    elif args.command == 'snippets':
        # Parse experience
        try:
            exp_data = json.loads(args.experience)
        except json.JSONDecodeError:
            print("Invalid JSON", file=sys.stderr)
            sys.exit(1)

        # Create mock experience object
        class MockExperience:
            pass

        exp = MockExperience()
        for key, value in exp_data.items():
            setattr(exp, key, value)

        snippets = compressor.get_reusable_snippets(exp)

        if args.json:
            print(json.dumps(snippets, indent=2))
        else:
            for snippet in snippets:
                print(f"[{snippet['type']}] {snippet['content']}")


if __name__ == '__main__':
    main()
