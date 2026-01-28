#!/usr/bin/env python3
"""
CER Integration - Contextual Experience Replay Integration with Research Synthesizer

This module integrates the CER system with the research synthesizer to:
1. Retrieve relevant past experiences before synthesis
2. Inject experience context into prompts
3. Track which experiences were used and their effectiveness

Usage:
    from cer_integration import CERIntegration

    cer = CERIntegration()

    # Before synthesis, get experience context
    context = cer.get_experience_context(query, domain, sub_questions)

    # After synthesis, record the experience
    exp_id = cer.record_experience(query, domain, sub_questions, findings, synthesis, confidence)

    # Mark experience as helpful
    cer.mark_experience_helpful(exp_id)
"""

import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Add lib directory to path for imports
SCRIPT_DIR = Path(__file__).parent
sys.path.insert(0, str(SCRIPT_DIR))

from experience_memory import Experience, ExperienceMemory, RetrievalResult
from experience_compressor import ExperienceCompressor, CompressedExperience


# ============================================================================
# Data Classes
# ============================================================================

@dataclass
class ExperienceContext:
    """Context derived from past experiences for prompt injection."""
    query: str
    domain: str
    retrieved_experiences: List[RetrievalResult]
    compressed_patterns: List[CompressedExperience]
    prompt_injection: str
    source_recommendations: List[str]
    decomposition_hints: List[str]
    confidence_baseline: Optional[float] = None
    used_experience_ids: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            'query': self.query,
            'domain': self.domain,
            'num_experiences': len(self.retrieved_experiences),
            'prompt_injection': self.prompt_injection,
            'source_recommendations': self.source_recommendations,
            'decomposition_hints': self.decomposition_hints,
            'confidence_baseline': self.confidence_baseline,
            'used_experience_ids': self.used_experience_ids
        }


@dataclass
class CERUsageRecord:
    """Record of CER usage for tracking effectiveness."""
    query_id: str
    query: str
    domain: str
    used_cer: bool
    experience_ids_used: List[str]
    final_confidence: int
    source_coverage: float
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            'query_id': self.query_id,
            'query': self.query,
            'domain': self.domain,
            'used_cer': self.used_cer,
            'experience_ids_used': self.experience_ids_used,
            'final_confidence': self.final_confidence,
            'source_coverage': self.source_coverage,
            'timestamp': self.timestamp
        }


# ============================================================================
# CER Integration Class
# ============================================================================

class CERIntegration:
    """
    Integrates Contextual Experience Replay with the research synthesizer.

    Provides methods to:
    - Retrieve relevant past experiences before synthesis
    - Generate prompt context from experiences
    - Record new experiences after synthesis
    - Track effectiveness of experience usage
    """

    def __init__(
        self,
        memory: Optional[ExperienceMemory] = None,
        compressor: Optional[ExperienceCompressor] = None,
        min_similarity: float = 0.4,
        max_experiences: int = 5
    ):
        """
        Initialize CER integration.

        Args:
            memory: ExperienceMemory instance (created if not provided)
            compressor: ExperienceCompressor instance (created if not provided)
            min_similarity: Minimum similarity threshold for retrieval
            max_experiences: Maximum number of experiences to retrieve
        """
        self.memory = memory or ExperienceMemory()
        self.compressor = compressor or ExperienceCompressor()
        self.min_similarity = min_similarity
        self.max_experiences = max_experiences
        self._usage_records: List[CERUsageRecord] = []

    def get_experience_context(
        self,
        query: str,
        domain: str,
        sub_questions: Optional[List[str]] = None
    ) -> ExperienceContext:
        """
        Get experience context for a research query.

        Retrieves relevant past experiences and generates context
        that can be injected into the research prompt.

        Args:
            query: The research query
            domain: Research domain (ai-ml, investment, general)
            sub_questions: Optional list of sub-questions

        Returns:
            ExperienceContext with prompt injection and recommendations
        """
        # Retrieve similar experiences
        results = self.memory.retrieve(
            query=query,
            domain=domain,
            k=self.max_experiences,
            min_similarity=self.min_similarity
        )

        # Compress experiences for pattern extraction
        compressed = []
        for result in results:
            comp = self.compressor.extract_pattern(result.experience)
            compressed.append(comp)

        # Generate prompt injection
        prompt_injection = self._generate_prompt_injection(results, compressed)

        # Extract source recommendations
        source_recommendations = self._extract_source_recommendations(compressed)

        # Extract decomposition hints
        decomposition_hints = self._extract_decomposition_hints(
            compressed, sub_questions
        )

        # Calculate confidence baseline
        confidence_baseline = self._calculate_confidence_baseline(results)

        # Track used experience IDs
        used_ids = [r.experience.id for r in results]

        return ExperienceContext(
            query=query,
            domain=domain,
            retrieved_experiences=results,
            compressed_patterns=compressed,
            prompt_injection=prompt_injection,
            source_recommendations=source_recommendations,
            decomposition_hints=decomposition_hints,
            confidence_baseline=confidence_baseline,
            used_experience_ids=used_ids
        )

    def _generate_prompt_injection(
        self,
        results: List[RetrievalResult],
        compressed: List[CompressedExperience]
    ) -> str:
        """
        Generate prompt text to inject experience context.

        Args:
            results: Retrieved experience results
            compressed: Compressed experience patterns

        Returns:
            Prompt injection text
        """
        if not results:
            return ""

        lines = [
            "Based on similar past research experiences:",
            ""
        ]

        # Add top experience summaries
        for i, (result, comp) in enumerate(zip(results[:3], compressed[:3]), 1):
            exp = result.experience
            similarity_pct = int(result.similarity * 100)

            lines.append(f"{i}. Similar query ({similarity_pct}% match): \"{exp.query[:100]}...\"")
            lines.append(f"   - Domain: {exp.domain}, Confidence achieved: {exp.confidence}%")

            if comp.search_pattern:
                sources = ', '.join(comp.search_pattern.source_types[:3])
                lines.append(f"   - Effective sources: {sources}")

            if comp.key_learnings:
                lines.append(f"   - Key learning: {comp.key_learnings[0]}")

            lines.append("")

        # Add general recommendations
        if compressed:
            lines.append("Recommendations from past experiences:")

            # Source recommendations
            all_sources = []
            for comp in compressed:
                if comp.search_pattern:
                    all_sources.extend(comp.search_pattern.source_types)

            if all_sources:
                from collections import Counter
                top_sources = [s for s, _ in Counter(all_sources).most_common(3)]
                lines.append(f"- Prioritize these source types: {', '.join(top_sources)}")

            # Confidence insight
            avg_confidence = sum(r.experience.confidence for r in results) / len(results)
            if avg_confidence >= 70:
                lines.append(f"- Similar queries achieved {avg_confidence:.0f}% average confidence")
            else:
                lines.append(f"- Similar queries had moderate confidence ({avg_confidence:.0f}%); "
                           "consider broader source coverage")

        return '\n'.join(lines)

    def _extract_source_recommendations(
        self,
        compressed: List[CompressedExperience]
    ) -> List[str]:
        """
        Extract source recommendations from compressed experiences.

        Args:
            compressed: List of compressed experiences

        Returns:
            List of recommended source types/domains
        """
        recommendations = []

        # Collect all source patterns
        source_scores: Dict[str, List[float]] = {}
        for comp in compressed:
            for sp in comp.source_patterns:
                if sp.source_domain not in source_scores:
                    source_scores[sp.source_domain] = []
                source_scores[sp.source_domain].append(sp.avg_relevance)

        # Calculate average scores and sort
        avg_scores = {
            domain: sum(scores) / len(scores)
            for domain, scores in source_scores.items()
        }

        sorted_sources = sorted(avg_scores.items(), key=lambda x: x[1], reverse=True)

        for domain, score in sorted_sources[:5]:
            if score >= 0.6:
                recommendations.append(f"{domain} (avg relevance: {score:.2f})")

        return recommendations

    def _extract_decomposition_hints(
        self,
        compressed: List[CompressedExperience],
        current_sub_questions: Optional[List[str]]
    ) -> List[str]:
        """
        Extract decomposition hints from past experiences.

        Args:
            compressed: List of compressed experiences
            current_sub_questions: Current sub-questions for comparison

        Returns:
            List of decomposition hints
        """
        hints = []

        # Analyze successful decomposition patterns
        successful_patterns = [
            comp.decomposition_pattern
            for comp in compressed
            if comp.decomposition_pattern and comp.decomposition_pattern.effectiveness_score >= 0.6
        ]

        if successful_patterns:
            # Average number of sub-questions in successful research
            avg_questions = sum(p.num_sub_questions for p in successful_patterns) / len(successful_patterns)
            hints.append(f"Similar queries used {avg_questions:.1f} sub-questions on average")

            # Most common question types
            all_types = []
            for p in successful_patterns:
                all_types.extend(p.sub_question_types)

            if all_types:
                from collections import Counter
                type_counts = Counter(all_types)
                top_types = [t for t, _ in type_counts.most_common(3)]
                hints.append(f"Common question types: {', '.join(top_types)}")

        # Compare with current decomposition
        if current_sub_questions and successful_patterns:
            current_count = len(current_sub_questions)
            if current_count < avg_questions - 1:
                hints.append(f"Consider adding more sub-questions (current: {current_count})")
            elif current_count > avg_questions + 2:
                hints.append(f"Consider focusing sub-questions (current: {current_count})")

        return hints

    def _calculate_confidence_baseline(
        self,
        results: List[RetrievalResult]
    ) -> Optional[float]:
        """
        Calculate expected confidence baseline from past experiences.

        Args:
            results: Retrieved experience results

        Returns:
            Expected confidence baseline or None
        """
        if not results:
            return None

        # Weight by similarity
        total_weight = sum(r.similarity for r in results)
        if total_weight == 0:
            return None

        weighted_confidence = sum(
            r.experience.confidence * r.similarity
            for r in results
        )

        return weighted_confidence / total_weight

    def record_experience(
        self,
        query: str,
        domain: str,
        sub_questions: List[str],
        findings: List[Dict],
        synthesis: str,
        confidence: int,
        outcome: Optional[str] = None
    ) -> str:
        """
        Record a new research experience.

        Args:
            query: The research query
            domain: Research domain
            sub_questions: How the query was decomposed
            findings: Research findings
            synthesis: Final synthesis text
            confidence: Confidence score (0-100)
            outcome: Optional outcome for learning

        Returns:
            Experience ID
        """
        # Create experience
        experience = Experience(
            id='',  # Will be generated
            query=query,
            domain=domain,
            sub_questions=sub_questions,
            findings=findings,
            synthesis=synthesis,
            confidence=confidence,
            outcome=outcome
        )

        # Compress patterns
        self.memory.compress(experience)

        # Store experience
        exp_id = self.memory.store(experience)

        return exp_id

    def record_usage(
        self,
        query_id: str,
        query: str,
        domain: str,
        used_cer: bool,
        experience_ids_used: List[str],
        final_confidence: int,
        source_coverage: float
    ) -> CERUsageRecord:
        """
        Record CER usage for tracking effectiveness.

        Args:
            query_id: Unique query identifier
            query: The research query
            domain: Research domain
            used_cer: Whether CER was used
            experience_ids_used: List of experience IDs used
            final_confidence: Final confidence score
            source_coverage: Source coverage metric (0.0-1.0)

        Returns:
            CERUsageRecord
        """
        record = CERUsageRecord(
            query_id=query_id,
            query=query,
            domain=domain,
            used_cer=used_cer,
            experience_ids_used=experience_ids_used,
            final_confidence=final_confidence,
            source_coverage=source_coverage
        )

        self._usage_records.append(record)

        # Mark used experiences as helpful if confidence was high
        if used_cer and final_confidence >= 70:
            for exp_id in experience_ids_used:
                self.memory.mark_helpful(exp_id)

        return record

    def mark_experience_helpful(self, experience_id: str) -> bool:
        """
        Mark an experience as helpful.

        Args:
            experience_id: Experience ID to mark

        Returns:
            True if marked, False if not found
        """
        return self.memory.mark_helpful(experience_id)

    def get_usage_stats(self) -> Dict:
        """
        Get CER usage statistics.

        Returns:
            Dictionary with usage statistics
        """
        if not self._usage_records:
            return {
                'total_queries': 0,
                'cer_used': 0,
                'cer_not_used': 0,
                'avg_confidence_with_cer': 0,
                'avg_confidence_without_cer': 0,
                'avg_coverage_with_cer': 0,
                'avg_coverage_without_cer': 0
            }

        cer_records = [r for r in self._usage_records if r.used_cer]
        no_cer_records = [r for r in self._usage_records if not r.used_cer]

        def avg_or_zero(records, attr):
            if not records:
                return 0
            return sum(getattr(r, attr) for r in records) / len(records)

        return {
            'total_queries': len(self._usage_records),
            'cer_used': len(cer_records),
            'cer_not_used': len(no_cer_records),
            'avg_confidence_with_cer': avg_or_zero(cer_records, 'final_confidence'),
            'avg_confidence_without_cer': avg_or_zero(no_cer_records, 'final_confidence'),
            'avg_coverage_with_cer': avg_or_zero(cer_records, 'source_coverage'),
            'avg_coverage_without_cer': avg_or_zero(no_cer_records, 'source_coverage')
        }


# ============================================================================
# Enhanced Research Synthesizer Integration
# ============================================================================

class CEREnhancedSynthesizer:
    """
    Wrapper that adds CER capabilities to the research synthesizer.

    Use this class instead of ResearchSynthesizer directly to get
    automatic experience retrieval and recording.
    """

    def __init__(
        self,
        domain: str = 'general',
        cer_integration: Optional[CERIntegration] = None,
        use_cer: bool = True
    ):
        """
        Initialize CER-enhanced synthesizer.

        Args:
            domain: Research domain
            cer_integration: CERIntegration instance (created if not provided)
            use_cer: Whether to use CER (can be toggled for A/B testing)
        """
        # Import here to avoid circular imports
        from research_synthesizer import ResearchSynthesizer

        self.domain = domain
        self.base_synthesizer = ResearchSynthesizer(domain=domain)
        self.cer = cer_integration or CERIntegration()
        self.use_cer = use_cer
        self._current_context: Optional[ExperienceContext] = None

    def prepare_synthesis(
        self,
        question: str,
        sub_questions: Optional[List[Dict]] = None
    ) -> Optional[ExperienceContext]:
        """
        Prepare for synthesis by retrieving relevant experiences.

        Call this before synthesize() to get experience context.

        Args:
            question: The research question
            sub_questions: List of sub-questions

        Returns:
            ExperienceContext if CER is enabled, None otherwise
        """
        if not self.use_cer:
            return None

        sq_list = [sq.get('question', '') for sq in (sub_questions or [])]
        self._current_context = self.cer.get_experience_context(
            query=question,
            domain=self.domain,
            sub_questions=sq_list
        )

        return self._current_context

    def get_prompt_injection(self) -> str:
        """
        Get the prompt injection text from current context.

        Returns:
            Prompt injection text or empty string
        """
        if self._current_context:
            return self._current_context.prompt_injection
        return ""

    def synthesize(
        self,
        question: str,
        findings_by_agent: Dict[str, List],
        sub_questions: List[Dict],
        expected_perspectives: Optional[List[str]] = None
    ):
        """
        Perform synthesis with CER enhancement.

        Args:
            question: The main research question
            findings_by_agent: Findings grouped by agent
            sub_questions: List of sub-questions
            expected_perspectives: Expected agent perspectives

        Returns:
            Synthesis object
        """
        # Prepare CER context if not already done
        if self.use_cer and self._current_context is None:
            self.prepare_synthesis(question, sub_questions)

        # Run base synthesis
        synthesis = self.base_synthesizer.synthesize(
            question=question,
            findings_by_agent=findings_by_agent,
            sub_questions=sub_questions,
            expected_perspectives=expected_perspectives
        )

        # Record experience if CER is enabled
        if self.use_cer:
            # Convert findings for storage
            all_findings = []
            for agent, findings in findings_by_agent.items():
                for f in findings:
                    finding_dict = f.to_dict() if hasattr(f, 'to_dict') else f
                    all_findings.append(finding_dict)

            sq_list = [sq.get('question', '') for sq in sub_questions]

            self.cer.record_experience(
                query=question,
                domain=self.domain,
                sub_questions=sq_list,
                findings=all_findings,
                synthesis=synthesis.summary,
                confidence=synthesis.confidence.score
            )

            # Record usage
            self.cer.record_usage(
                query_id=synthesis.created_at,  # Use timestamp as ID
                query=question,
                domain=self.domain,
                used_cer=True,
                experience_ids_used=self._current_context.used_experience_ids if self._current_context else [],
                final_confidence=synthesis.confidence.score,
                source_coverage=len(synthesis.sources) / max(len(sub_questions), 1)
            )

        # Clear context for next query
        self._current_context = None

        return synthesis


# ============================================================================
# CLI Interface
# ============================================================================

def main():
    """CLI entry point for CER integration."""
    import argparse
    import json

    parser = argparse.ArgumentParser(description='CER Integration for Research Synthesizer')

    parser.add_argument('--json', '-j', action='store_true', help='Output as JSON')

    subparsers = parser.add_subparsers(dest='command', help='Commands')

    # Context command
    ctx_parser = subparsers.add_parser('context', help='Get experience context')
    ctx_parser.add_argument('--query', '-q', required=True, help='Research query')
    ctx_parser.add_argument('--domain', '-d', default='general', help='Domain')

    # Record command
    rec_parser = subparsers.add_parser('record', help='Record experience')
    rec_parser.add_argument('--query', '-q', required=True, help='Research query')
    rec_parser.add_argument('--domain', '-d', default='general', help='Domain')
    rec_parser.add_argument('--findings', '-f', required=True, help='Findings JSON')
    rec_parser.add_argument('--synthesis', required=True, help='Synthesis text')
    rec_parser.add_argument('--confidence', '-c', type=int, default=50, help='Confidence')
    rec_parser.add_argument('--sub-questions', help='Sub-questions JSON')

    # Stats command
    subparsers.add_parser('stats', help='Get usage statistics')

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    cer = CERIntegration()

    def output(data: Any):
        """Output data in appropriate format."""
        if args.json:
            print(json.dumps(data, indent=2, default=str))
        else:
            if isinstance(data, dict):
                for k, v in data.items():
                    print(f"{k}: {v}")
            else:
                print(data)

    if args.command == 'context':
        context = cer.get_experience_context(args.query, args.domain)
        output(context.to_dict())

        if not args.json:
            print("\n--- Prompt Injection ---")
            print(context.prompt_injection)

    elif args.command == 'record':
        # Parse findings
        try:
            findings = json.loads(args.findings)
            if not isinstance(findings, list):
                findings = [findings]
        except json.JSONDecodeError:
            findings = [{'content': args.findings}]

        # Parse sub-questions
        sub_questions = []
        if args.sub_questions:
            try:
                sub_questions = json.loads(args.sub_questions)
            except json.JSONDecodeError:
                sub_questions = [args.sub_questions]

        exp_id = cer.record_experience(
            query=args.query,
            domain=args.domain,
            sub_questions=sub_questions,
            findings=findings,
            synthesis=args.synthesis,
            confidence=args.confidence
        )

        output({'id': exp_id, 'status': 'recorded'})

    elif args.command == 'stats':
        stats = cer.get_usage_stats()
        output(stats)


if __name__ == '__main__':
    main()
