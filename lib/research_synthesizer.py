#!/usr/bin/env python3
"""
Research Synthesizer - Combines findings from multiple agents

This module provides functionality to:
1. Combine findings from multiple specialist agents
2. Identify gaps in collected information
3. Score confidence based on source agreement and coverage
4. Handle conflicting findings
5. Output structured synthesis with citations
"""

import sys
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple
from datetime import datetime
from pathlib import Path

# Add lib directory to path for imports
SCRIPT_DIR = Path(__file__).parent
sys.path.insert(0, str(SCRIPT_DIR))

from confidence_scorer import ConfidenceScorer, ConfidenceScore


@dataclass
class Finding:
    """Represents a single research finding from an agent."""
    id: str
    content: str
    source_url: Optional[str] = None
    source_title: Optional[str] = None
    agent: str = "unknown"
    sub_question_id: Optional[str] = None
    timestamp: Optional[str] = None
    relevance_score: float = 0.5  # 0.0-1.0

    def to_dict(self) -> Dict:
        """Convert finding to dictionary."""
        return {
            'id': self.id,
            'content': self.content,
            'source_url': self.source_url,
            'source_title': self.source_title,
            'agent': self.agent,
            'sub_question_id': self.sub_question_id,
            'timestamp': self.timestamp,
            'relevance_score': self.relevance_score
        }


@dataclass
class Gap:
    """Represents an identified gap in research findings."""
    id: str
    description: str
    gap_type: str  # coverage, depth, recency, perspective, conflict
    severity: str  # critical, high, medium, low
    related_sub_question: Optional[str] = None
    recommendation: Optional[str] = None

    def to_dict(self) -> Dict:
        """Convert gap to dictionary."""
        return {
            'id': self.id,
            'description': self.description,
            'gap_type': self.gap_type,
            'severity': self.severity,
            'related_sub_question': self.related_sub_question,
            'recommendation': self.recommendation
        }


@dataclass
class Conflict:
    """Represents a conflict between findings."""
    id: str
    finding_ids: List[str]
    description: str
    resolution: Optional[str] = None
    resolved: bool = False

    def to_dict(self) -> Dict:
        """Convert conflict to dictionary."""
        return {
            'id': self.id,
            'finding_ids': self.finding_ids,
            'description': self.description,
            'resolution': self.resolution,
            'resolved': self.resolved
        }


@dataclass
class Synthesis:
    """Represents the synthesized research output."""
    question: str
    summary: str
    key_findings: List[Finding]
    gaps: List[Gap]
    conflicts: List[Conflict]
    confidence: ConfidenceScore
    sources: List[Dict]
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat() + 'Z')

    def to_dict(self) -> Dict:
        """Convert synthesis to dictionary."""
        return {
            'question': self.question,
            'summary': self.summary,
            'key_findings': [f.to_dict() for f in self.key_findings],
            'gaps': [g.to_dict() for g in self.gaps],
            'conflicts': [c.to_dict() for c in self.conflicts],
            'confidence': self.confidence.to_dict(),
            'sources': self.sources,
            'created_at': self.created_at
        }


class ResearchSynthesizer:
    """Synthesizes findings from multiple research agents."""

    # Gap type definitions
    GAP_TYPES = ['coverage', 'depth', 'recency', 'perspective', 'conflict']

    # Severity levels
    SEVERITY_LEVELS = ['critical', 'high', 'medium', 'low']

    def __init__(self, domain: str = 'general'):
        """
        Initialize the research synthesizer.

        Args:
            domain: Research domain for confidence scoring (ai-ml, investment, general)
        """
        self.domain = domain
        self.confidence_scorer = ConfidenceScorer(domain=domain)

    def combine_findings(
        self,
        findings_by_agent: Dict[str, List[Finding]],
        sub_questions: Optional[List[Dict]] = None
    ) -> List[Finding]:
        """
        Combine findings from multiple agents into a unified list.

        Args:
            findings_by_agent: Dictionary mapping agent names to their findings
            sub_questions: Optional list of sub-questions for context

        Returns:
            Combined and deduplicated list of findings
        """
        combined = []
        seen_contents = set()

        # Flatten all findings
        for agent_name, findings in findings_by_agent.items():
            for finding in findings:
                # Ensure agent is set
                if finding.agent == "unknown":
                    finding.agent = agent_name

                # Deduplicate by content similarity
                content_key = self._normalize_content(finding.content)
                if content_key not in seen_contents:
                    seen_contents.add(content_key)
                    combined.append(finding)

        # Sort by relevance score (highest first)
        combined.sort(key=lambda f: f.relevance_score, reverse=True)

        return combined

    def identify_gaps(
        self,
        findings: List[Finding],
        sub_questions: List[Dict],
        expected_perspectives: Optional[List[str]] = None
    ) -> List[Gap]:
        """
        Identify gaps in the collected findings.

        Args:
            findings: List of combined findings
            sub_questions: List of sub-questions that should be answered
            expected_perspectives: List of expected agent perspectives

        Returns:
            List of identified gaps
        """
        gaps = []
        gap_counter = 0

        if expected_perspectives is None:
            expected_perspectives = ['academic-scanner', 'technical-diver', 'market-analyst']

        # Check coverage gaps - which sub-questions lack findings
        answered_sq_ids = set(f.sub_question_id for f in findings if f.sub_question_id)

        for sq in sub_questions:
            sq_id = sq.get('id')
            if sq_id and sq_id not in answered_sq_ids:
                gap_counter += 1
                gaps.append(Gap(
                    id=f"GAP-{gap_counter:03d}",
                    description=f"Sub-question '{sq.get('question', sq_id)}' has no findings",
                    gap_type='coverage',
                    severity='high',
                    related_sub_question=sq_id,
                    recommendation=f"Investigate: {sq.get('question', 'the sub-question')}"
                ))

        # Check perspective gaps - which expected agents provided no findings
        agents_with_findings = set(f.agent for f in findings)

        for perspective in expected_perspectives:
            if perspective not in agents_with_findings:
                gap_counter += 1
                gaps.append(Gap(
                    id=f"GAP-{gap_counter:03d}",
                    description=f"No findings from {perspective} perspective",
                    gap_type='perspective',
                    severity='medium',
                    recommendation=f"Consider delegating relevant questions to {perspective}"
                ))

        # Check depth gaps - sub-questions with only one finding
        sq_finding_counts = {}
        for f in findings:
            if f.sub_question_id:
                sq_finding_counts[f.sub_question_id] = sq_finding_counts.get(f.sub_question_id, 0) + 1

        for sq in sub_questions:
            sq_id = sq.get('id')
            if sq_id and sq_finding_counts.get(sq_id, 0) == 1:
                gap_counter += 1
                gaps.append(Gap(
                    id=f"GAP-{gap_counter:03d}",
                    description=f"Sub-question '{sq.get('question', sq_id)}' has only one source",
                    gap_type='depth',
                    severity='low',
                    related_sub_question=sq_id,
                    recommendation="Additional sources would increase confidence"
                ))

        # Check recency gaps - old timestamps
        for f in findings:
            if f.timestamp:
                try:
                    finding_date = datetime.fromisoformat(f.timestamp.replace('Z', '+00:00'))
                    age_days = (datetime.now(finding_date.tzinfo) - finding_date).days
                    if age_days > 365:
                        gap_counter += 1
                        gaps.append(Gap(
                            id=f"GAP-{gap_counter:03d}",
                            description=f"Finding '{f.id}' is over a year old",
                            gap_type='recency',
                            severity='medium',
                            recommendation="Verify information is still current"
                        ))
                except (ValueError, TypeError):
                    pass  # Skip if timestamp can't be parsed

        return gaps

    def detect_conflicts(self, findings: List[Finding]) -> List[Conflict]:
        """
        Detect conflicting claims among findings.

        Args:
            findings: List of findings to check for conflicts

        Returns:
            List of detected conflicts
        """
        conflicts = []
        conflict_counter = 0

        # Simple keyword-based conflict detection
        # In a real implementation, this would use NLP/semantic analysis
        conflict_indicators = [
            ('increase', 'decrease'),
            ('improvement', 'decline'),
            ('improve', 'decline'),
            ('better', 'worse'),
            ('success', 'failure'),
            ('growth', 'decline'),
            ('yes', 'no'),
            ('true', 'false'),
            ('positive', 'negative'),
            ('support', 'oppose'),
            ('recommend', 'avoid'),
        ]

        # Compare pairs of findings
        for i, f1 in enumerate(findings):
            for f2 in findings[i + 1:]:
                # Skip findings from the same sub-question context
                if f1.sub_question_id and f1.sub_question_id == f2.sub_question_id:
                    content1_lower = f1.content.lower()
                    content2_lower = f2.content.lower()

                    for pos_word, neg_word in conflict_indicators:
                        if ((pos_word in content1_lower and neg_word in content2_lower) or
                            (neg_word in content1_lower and pos_word in content2_lower)):
                            conflict_counter += 1
                            conflicts.append(Conflict(
                                id=f"CONF-{conflict_counter:03d}",
                                finding_ids=[f1.id, f2.id],
                                description=f"Potential conflict: '{f1.id}' and '{f2.id}' may have contradicting claims",
                                resolved=False
                            ))
                            break  # Only report one conflict per pair

        return conflicts

    def resolve_conflict(self, conflict: Conflict, findings: List[Finding], resolution: str) -> Conflict:
        """
        Resolve a detected conflict with an explanation.

        Args:
            conflict: The conflict to resolve
            findings: List of all findings for context
            resolution: Explanation of how the conflict is resolved

        Returns:
            Updated conflict with resolution
        """
        conflict.resolution = resolution
        conflict.resolved = True
        return conflict

    def score_confidence(self, findings: List[Finding], gaps: List[Gap], conflicts: List[Conflict]) -> ConfidenceScore:
        """
        Score overall confidence in the synthesis.

        Args:
            findings: List of combined findings
            gaps: List of identified gaps
            conflicts: List of detected conflicts

        Returns:
            ConfidenceScore with score and explanation
        """
        # Prepare sources for scoring
        sources = []
        for f in findings:
            source = {
                'url': f.source_url,
                'title': f.source_title,
                'relevance': f.relevance_score,
                'agent': f.agent
            }
            if f.timestamp:
                source['date'] = f.timestamp
            sources.append(source)

        # Calculate base score
        confidence = self.confidence_scorer.score(
            sources=sources,
            gaps=len(gaps),
            conflicts=len([c for c in conflicts if not c.resolved])
        )

        return confidence

    def extract_sources(self, findings: List[Finding]) -> List[Dict]:
        """
        Extract unique sources from findings.

        Args:
            findings: List of findings

        Returns:
            List of unique source dictionaries
        """
        sources = []
        seen_urls = set()

        for f in findings:
            if f.source_url and f.source_url not in seen_urls:
                seen_urls.add(f.source_url)
                sources.append({
                    'url': f.source_url,
                    'title': f.source_title or f.source_url,
                    'agent': f.agent,
                    'relevance': f.relevance_score
                })

        # Sort by relevance
        sources.sort(key=lambda s: s.get('relevance', 0), reverse=True)

        return sources

    def synthesize(
        self,
        question: str,
        findings_by_agent: Dict[str, List[Finding]],
        sub_questions: List[Dict],
        expected_perspectives: Optional[List[str]] = None
    ) -> Synthesis:
        """
        Perform full synthesis of research findings.

        Args:
            question: The main research question
            findings_by_agent: Findings grouped by agent
            sub_questions: List of sub-questions
            expected_perspectives: Expected agent perspectives

        Returns:
            Complete Synthesis object
        """
        # Step 1: Combine findings
        combined_findings = self.combine_findings(findings_by_agent, sub_questions)

        # Step 2: Identify gaps
        gaps = self.identify_gaps(combined_findings, sub_questions, expected_perspectives)

        # Step 3: Detect conflicts
        conflicts = self.detect_conflicts(combined_findings)

        # Step 4: Score confidence
        confidence = self.score_confidence(combined_findings, gaps, conflicts)

        # Step 5: Extract sources
        sources = self.extract_sources(combined_findings)

        # Step 6: Generate summary
        summary = self._generate_summary(question, combined_findings, gaps, confidence)

        return Synthesis(
            question=question,
            summary=summary,
            key_findings=combined_findings,
            gaps=gaps,
            conflicts=conflicts,
            confidence=confidence,
            sources=sources
        )

    def _normalize_content(self, content: str) -> str:
        """
        Normalize content for deduplication comparison.

        Args:
            content: Raw content string

        Returns:
            Normalized content string
        """
        # Simple normalization - lowercase and remove extra whitespace
        return ' '.join(content.lower().split())[:200]

    def _generate_summary(
        self,
        question: str,
        findings: List[Finding],
        gaps: List[Gap],
        confidence: ConfidenceScore
    ) -> str:
        """
        Generate a summary of the synthesis.

        Args:
            question: The research question
            findings: Combined findings
            gaps: Identified gaps
            confidence: Confidence score

        Returns:
            Summary string
        """
        finding_count = len(findings)
        source_count = len(set(f.source_url for f in findings if f.source_url))
        gap_count = len(gaps)
        critical_gaps = len([g for g in gaps if g.severity == 'critical'])

        summary_parts = [
            f"Research on '{question}' yielded {finding_count} findings from {source_count} sources."
        ]

        if confidence.score >= 75:
            summary_parts.append(f"Confidence is high ({confidence.score}/100).")
        elif confidence.score >= 50:
            summary_parts.append(f"Confidence is moderate ({confidence.score}/100).")
        else:
            summary_parts.append(f"Confidence is low ({confidence.score}/100).")

        if critical_gaps > 0:
            summary_parts.append(f"There are {critical_gaps} critical gaps requiring attention.")
        elif gap_count > 0:
            summary_parts.append(f"Identified {gap_count} gaps in coverage.")

        return ' '.join(summary_parts)


def main():
    """CLI for research synthesizer (demo)."""
    import json

    # Demo usage
    print("Research Synthesizer Demo")
    print("=" * 40)

    # Create sample findings
    findings_by_agent = {
        'academic-scanner': [
            Finding(
                id='F-001',
                content='Recent research shows LLM performance improves with chain-of-thought prompting.',
                source_url='https://arxiv.org/abs/example1',
                source_title='Chain-of-Thought Paper',
                agent='academic-scanner',
                sub_question_id='SQ-001',
                relevance_score=0.9
            )
        ],
        'technical-diver': [
            Finding(
                id='F-002',
                content='Implementation requires careful prompt engineering and temperature tuning.',
                source_url='https://github.com/example/repo',
                source_title='Implementation Guide',
                agent='technical-diver',
                sub_question_id='SQ-002',
                relevance_score=0.85
            )
        ]
    }

    sub_questions = [
        {'id': 'SQ-001', 'question': 'What does research say about LLM prompting?'},
        {'id': 'SQ-002', 'question': 'How do you implement effective prompting?'},
        {'id': 'SQ-003', 'question': 'What are the costs involved?'}
    ]

    # Run synthesis
    synthesizer = ResearchSynthesizer(domain='ai-ml')
    synthesis = synthesizer.synthesize(
        question="How can we improve LLM reasoning capabilities?",
        findings_by_agent=findings_by_agent,
        sub_questions=sub_questions
    )

    print(f"\nSummary: {synthesis.summary}")
    print(f"\nConfidence: {synthesis.confidence.score}/100")
    print(f"Explanation: {synthesis.confidence.explanation}")
    print(f"\nGaps found: {len(synthesis.gaps)}")
    for gap in synthesis.gaps:
        print(f"  - [{gap.severity}] {gap.description}")

    print(f"\nFull synthesis (JSON):")
    print(json.dumps(synthesis.to_dict(), indent=2))


if __name__ == '__main__':
    main()
