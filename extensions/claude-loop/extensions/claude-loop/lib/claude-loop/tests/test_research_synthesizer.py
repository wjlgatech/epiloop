#!/usr/bin/env python3
"""
Tests for research synthesizer functionality

Tests that research-synthesizer.py correctly:
1. Combines findings from multiple agents
2. Identifies gaps in coverage
3. Scores confidence based on sources
4. Handles conflicting findings
"""

import sys
import pytest
from pathlib import Path

# Add lib directory to path
LIB_DIR = Path(__file__).parent.parent / 'lib'
sys.path.insert(0, str(LIB_DIR))

from research_synthesizer import (
    ResearchSynthesizer,
    Finding,
    Gap,
    Conflict,
    Synthesis
)
from confidence_scorer import ConfidenceScorer, ConfidenceScore


class TestCombineFindings:
    """Tests for combining findings from multiple agents."""

    def test_combine_single_agent_findings(self):
        """Test combining findings from a single agent."""
        synthesizer = ResearchSynthesizer()

        findings_by_agent = {
            'academic-scanner': [
                Finding(
                    id='F-001',
                    content='Finding one about AI research',
                    source_url='https://arxiv.org/abs/1',
                    agent='academic-scanner',
                    relevance_score=0.9
                ),
                Finding(
                    id='F-002',
                    content='Finding two about neural networks',
                    source_url='https://arxiv.org/abs/2',
                    agent='academic-scanner',
                    relevance_score=0.8
                )
            ]
        }

        combined = synthesizer.combine_findings(findings_by_agent)

        assert len(combined) == 2
        assert combined[0].id == 'F-001'  # Higher relevance first
        assert combined[1].id == 'F-002'

    def test_combine_multiple_agent_findings(self):
        """Test combining findings from multiple agents."""
        synthesizer = ResearchSynthesizer()

        findings_by_agent = {
            'academic-scanner': [
                Finding(
                    id='F-001',
                    content='Academic finding',
                    source_url='https://arxiv.org/abs/1',
                    agent='academic-scanner',
                    relevance_score=0.9
                )
            ],
            'technical-diver': [
                Finding(
                    id='F-002',
                    content='Technical finding',
                    source_url='https://github.com/example',
                    agent='technical-diver',
                    relevance_score=0.85
                )
            ],
            'market-analyst': [
                Finding(
                    id='F-003',
                    content='Market finding',
                    source_url='https://bloomberg.com/article',
                    agent='market-analyst',
                    relevance_score=0.75
                )
            ]
        }

        combined = synthesizer.combine_findings(findings_by_agent)

        assert len(combined) == 3
        # Check sorted by relevance
        assert combined[0].relevance_score == 0.9
        assert combined[1].relevance_score == 0.85
        assert combined[2].relevance_score == 0.75
        # Check different agents
        agents = set(f.agent for f in combined)
        assert 'academic-scanner' in agents
        assert 'technical-diver' in agents
        assert 'market-analyst' in agents

    def test_combine_deduplicates_similar_content(self):
        """Test that similar content is deduplicated."""
        synthesizer = ResearchSynthesizer()

        findings_by_agent = {
            'agent-1': [
                Finding(
                    id='F-001',
                    content='This is a finding about machine learning models',
                    source_url='https://example.com/1',
                    relevance_score=0.9
                )
            ],
            'agent-2': [
                Finding(
                    id='F-002',
                    content='This is a finding about machine learning models',  # Duplicate
                    source_url='https://example.com/2',
                    relevance_score=0.8
                )
            ]
        }

        combined = synthesizer.combine_findings(findings_by_agent)

        # Should deduplicate identical content
        assert len(combined) == 1

    def test_combine_empty_findings(self):
        """Test combining when no findings exist."""
        synthesizer = ResearchSynthesizer()

        findings_by_agent = {}
        combined = synthesizer.combine_findings(findings_by_agent)

        assert len(combined) == 0


class TestGapIdentification:
    """Tests for identifying gaps in research findings."""

    def test_identify_coverage_gap(self):
        """Test identification of coverage gaps (unanswered sub-questions)."""
        synthesizer = ResearchSynthesizer()

        findings = [
            Finding(
                id='F-001',
                content='Answer to first question',
                sub_question_id='SQ-001',
                relevance_score=0.9
            )
        ]

        sub_questions = [
            {'id': 'SQ-001', 'question': 'First question'},
            {'id': 'SQ-002', 'question': 'Second question (unanswered)'},
            {'id': 'SQ-003', 'question': 'Third question (unanswered)'}
        ]

        gaps = synthesizer.identify_gaps(findings, sub_questions)

        # Should find gaps for SQ-002 and SQ-003
        coverage_gaps = [g for g in gaps if g.gap_type == 'coverage']
        assert len(coverage_gaps) == 2
        gap_sq_ids = [g.related_sub_question for g in coverage_gaps]
        assert 'SQ-002' in gap_sq_ids
        assert 'SQ-003' in gap_sq_ids

    def test_identify_perspective_gap(self):
        """Test identification of missing agent perspectives."""
        synthesizer = ResearchSynthesizer()

        findings = [
            Finding(
                id='F-001',
                content='Academic finding',
                agent='academic-scanner',
                sub_question_id='SQ-001',
                relevance_score=0.9
            )
        ]

        sub_questions = [{'id': 'SQ-001', 'question': 'Question one'}]
        expected_perspectives = ['academic-scanner', 'technical-diver', 'market-analyst']

        gaps = synthesizer.identify_gaps(findings, sub_questions, expected_perspectives)

        # Should find gaps for technical-diver and market-analyst
        perspective_gaps = [g for g in gaps if g.gap_type == 'perspective']
        assert len(perspective_gaps) == 2

    def test_identify_depth_gap(self):
        """Test identification of depth gaps (single source sub-questions)."""
        synthesizer = ResearchSynthesizer()

        findings = [
            Finding(
                id='F-001',
                content='Only one finding for this question',
                agent='academic-scanner',
                sub_question_id='SQ-001',
                relevance_score=0.9
            )
        ]

        sub_questions = [{'id': 'SQ-001', 'question': 'Question one'}]

        gaps = synthesizer.identify_gaps(findings, sub_questions, expected_perspectives=[])

        # Should find a depth gap
        depth_gaps = [g for g in gaps if g.gap_type == 'depth']
        assert len(depth_gaps) == 1
        assert depth_gaps[0].related_sub_question == 'SQ-001'

    def test_no_gaps_when_complete(self):
        """Test that no gaps are found when coverage is complete."""
        synthesizer = ResearchSynthesizer()

        findings = [
            Finding(
                id='F-001',
                content='Finding one',
                agent='academic-scanner',
                sub_question_id='SQ-001',
                relevance_score=0.9
            ),
            Finding(
                id='F-002',
                content='Finding two',
                agent='technical-diver',
                sub_question_id='SQ-001',
                relevance_score=0.85
            )
        ]

        sub_questions = [{'id': 'SQ-001', 'question': 'Question one'}]
        expected_perspectives = ['academic-scanner', 'technical-diver']

        gaps = synthesizer.identify_gaps(findings, sub_questions, expected_perspectives)

        # Should have no coverage or perspective gaps
        coverage_gaps = [g for g in gaps if g.gap_type == 'coverage']
        perspective_gaps = [g for g in gaps if g.gap_type == 'perspective']
        assert len(coverage_gaps) == 0
        assert len(perspective_gaps) == 0


class TestConfidenceScoring:
    """Tests for confidence scoring functionality."""

    def test_high_confidence_multiple_authoritative_sources(self):
        """Test high confidence with multiple authoritative agreeing sources."""
        scorer = ConfidenceScorer(domain='ai-ml')

        sources = [
            {'url': 'https://arxiv.org/abs/1', 'relevance': 0.95, 'agent': 'academic-scanner'},
            {'url': 'https://nature.com/article', 'relevance': 0.90, 'agent': 'academic-scanner'},
            {'url': 'https://openai.com/research', 'relevance': 0.85, 'agent': 'technical-diver'}
        ]

        result = scorer.score(sources, gaps=0, conflicts=0)

        assert result.score >= 70  # Should be high confidence
        assert 'source_count' in result.breakdown
        assert 'authority' in result.breakdown

    def test_low_confidence_single_low_authority_source(self):
        """Test low confidence with single low-authority source."""
        scorer = ConfidenceScorer(domain='general')

        sources = [
            {'url': 'https://random-blog.com/post', 'relevance': 0.5, 'agent': 'unknown'}
        ]

        result = scorer.score(sources, gaps=0, conflicts=0)

        assert result.score < 60  # Should be lower confidence

    def test_confidence_reduced_by_gaps(self):
        """Test that gaps reduce confidence score."""
        scorer = ConfidenceScorer(domain='general')

        sources = [
            {'url': 'https://arxiv.org/abs/1', 'relevance': 0.9, 'agent': 'academic-scanner'},
            {'url': 'https://github.com/example', 'relevance': 0.85, 'agent': 'technical-diver'}
        ]

        score_no_gaps = scorer.score(sources, gaps=0, conflicts=0)
        score_with_gaps = scorer.score(sources, gaps=3, conflicts=0)

        assert score_with_gaps.score < score_no_gaps.score

    def test_confidence_reduced_by_conflicts(self):
        """Test that unresolved conflicts reduce confidence score."""
        scorer = ConfidenceScorer(domain='general')

        sources = [
            {'url': 'https://arxiv.org/abs/1', 'relevance': 0.9, 'agent': 'academic-scanner'},
            {'url': 'https://github.com/example', 'relevance': 0.85, 'agent': 'technical-diver'}
        ]

        score_no_conflicts = scorer.score(sources, gaps=0, conflicts=0)
        score_with_conflicts = scorer.score(sources, gaps=0, conflicts=2)

        assert score_with_conflicts.score < score_no_conflicts.score

    def test_confidence_includes_explanation(self):
        """Test that confidence score includes human-readable explanation."""
        scorer = ConfidenceScorer(domain='general')

        sources = [
            {'url': 'https://arxiv.org/abs/1', 'relevance': 0.9, 'agent': 'academic-scanner'}
        ]

        result = scorer.score(sources, gaps=0, conflicts=0)

        assert result.explanation
        assert len(result.explanation) > 10

    def test_domain_specific_weights(self):
        """Test that different domains use different weights."""
        ai_scorer = ConfidenceScorer(domain='ai-ml')
        investment_scorer = ConfidenceScorer(domain='investment')

        ai_weights = ai_scorer.get_weights()
        investment_weights = investment_scorer.get_weights()

        # Weights should differ between domains
        assert ai_weights['recency'] != investment_weights['recency'] or \
               ai_weights['authority'] != investment_weights['authority']

    def test_zero_confidence_no_sources(self):
        """Test that zero sources results in low confidence."""
        scorer = ConfidenceScorer(domain='general')

        result = scorer.score(sources=[], gaps=0, conflicts=0)

        # With no sources, score should be very low (below 40)
        assert result.score < 40
        assert 'No sources' in result.explanation or result.breakdown['source_count'] == 0

    def test_custom_weights(self):
        """Test setting custom weights."""
        scorer = ConfidenceScorer(domain='general')

        custom_weights = {
            'source_count': 0.10,
            'source_agreement': 0.10,
            'recency': 0.10,
            'authority': 0.70
        }

        scorer.set_custom_weights(custom_weights)

        assert scorer.weights['authority'] == 0.70
        assert scorer.weights['source_count'] == 0.10


class TestConflictDetection:
    """Tests for detecting conflicting findings."""

    def test_detect_basic_conflict(self):
        """Test detection of basic conflicting claims."""
        synthesizer = ResearchSynthesizer()

        findings = [
            Finding(
                id='F-001',
                content='The model shows significant improvement in performance',
                agent='academic-scanner',
                sub_question_id='SQ-001',
                relevance_score=0.9
            ),
            Finding(
                id='F-002',
                content='The model shows decline in performance on benchmarks',
                agent='technical-diver',
                sub_question_id='SQ-001',
                relevance_score=0.85
            )
        ]

        conflicts = synthesizer.detect_conflicts(findings)

        # Should detect the improvement/decline conflict
        assert len(conflicts) >= 1
        conflict_finding_ids = conflicts[0].finding_ids
        assert 'F-001' in conflict_finding_ids
        assert 'F-002' in conflict_finding_ids

    def test_no_conflict_different_topics(self):
        """Test that findings on different topics don't conflict."""
        synthesizer = ResearchSynthesizer()

        findings = [
            Finding(
                id='F-001',
                content='The model improves accuracy',
                agent='academic-scanner',
                sub_question_id='SQ-001',  # Different sub-question
                relevance_score=0.9
            ),
            Finding(
                id='F-002',
                content='The cost decreases with scale',
                agent='technical-diver',
                sub_question_id='SQ-002',  # Different sub-question
                relevance_score=0.85
            )
        ]

        conflicts = synthesizer.detect_conflicts(findings)

        # Should not detect conflict - different topics
        assert len(conflicts) == 0

    def test_resolve_conflict(self):
        """Test conflict resolution."""
        synthesizer = ResearchSynthesizer()

        conflict = Conflict(
            id='CONF-001',
            finding_ids=['F-001', 'F-002'],
            description='Conflicting performance claims',
            resolved=False
        )

        findings = [
            Finding(id='F-001', content='Performance improves', relevance_score=0.9),
            Finding(id='F-002', content='Performance declines', relevance_score=0.85)
        ]

        resolution = "Both findings are correct in different contexts: F-001 refers to training, F-002 refers to inference."

        resolved = synthesizer.resolve_conflict(conflict, findings, resolution)

        assert resolved.resolved is True
        assert resolved.resolution == resolution


class TestFullSynthesis:
    """Tests for the complete synthesis workflow."""

    def test_full_synthesis_workflow(self):
        """Test complete synthesis from findings to structured output."""
        synthesizer = ResearchSynthesizer(domain='ai-ml')

        findings_by_agent = {
            'academic-scanner': [
                Finding(
                    id='F-001',
                    content='Research shows LLMs benefit from fine-tuning',
                    source_url='https://arxiv.org/abs/example',
                    source_title='Fine-tuning Paper',
                    agent='academic-scanner',
                    sub_question_id='SQ-001',
                    relevance_score=0.95
                )
            ],
            'technical-diver': [
                Finding(
                    id='F-002',
                    content='Implementation requires specific hyperparameters',
                    source_url='https://github.com/example/repo',
                    source_title='Implementation Guide',
                    agent='technical-diver',
                    sub_question_id='SQ-002',
                    relevance_score=0.85
                )
            ]
        }

        sub_questions = [
            {'id': 'SQ-001', 'question': 'What does research say about fine-tuning?'},
            {'id': 'SQ-002', 'question': 'How do you implement fine-tuning?'},
            {'id': 'SQ-003', 'question': 'What are the costs?'}  # Unanswered
        ]

        synthesis = synthesizer.synthesize(
            question="How to fine-tune LLMs effectively?",
            findings_by_agent=findings_by_agent,
            sub_questions=sub_questions
        )

        # Check structure
        assert isinstance(synthesis, Synthesis)
        assert synthesis.question == "How to fine-tune LLMs effectively?"
        assert len(synthesis.key_findings) == 2
        assert len(synthesis.sources) == 2

        # Check gaps identified (SQ-003 unanswered)
        coverage_gaps = [g for g in synthesis.gaps if g.gap_type == 'coverage']
        assert any(g.related_sub_question == 'SQ-003' for g in coverage_gaps)

        # Check confidence score
        assert 0 <= synthesis.confidence.score <= 100
        assert synthesis.confidence.explanation

        # Check summary
        assert synthesis.summary
        assert 'findings' in synthesis.summary.lower() or 'research' in synthesis.summary.lower()

    def test_synthesis_to_dict(self):
        """Test that synthesis can be serialized to dictionary."""
        synthesizer = ResearchSynthesizer()

        findings_by_agent = {
            'agent-1': [
                Finding(
                    id='F-001',
                    content='Test finding',
                    source_url='https://example.com',
                    relevance_score=0.9
                )
            ]
        }

        sub_questions = [{'id': 'SQ-001', 'question': 'Test question'}]

        synthesis = synthesizer.synthesize(
            question="Test question?",
            findings_by_agent=findings_by_agent,
            sub_questions=sub_questions,
            expected_perspectives=[]
        )

        result_dict = synthesis.to_dict()

        assert 'question' in result_dict
        assert 'summary' in result_dict
        assert 'key_findings' in result_dict
        assert 'gaps' in result_dict
        assert 'confidence' in result_dict
        assert 'sources' in result_dict
        assert 'created_at' in result_dict

    def test_extract_sources(self):
        """Test source extraction and deduplication."""
        synthesizer = ResearchSynthesizer()

        findings = [
            Finding(
                id='F-001',
                content='Finding one',
                source_url='https://example.com/1',
                source_title='Source One',
                agent='agent-1',
                relevance_score=0.9
            ),
            Finding(
                id='F-002',
                content='Finding two',
                source_url='https://example.com/2',
                source_title='Source Two',
                agent='agent-1',
                relevance_score=0.8
            ),
            Finding(
                id='F-003',
                content='Finding three from same source',
                source_url='https://example.com/1',  # Duplicate URL
                source_title='Source One',
                agent='agent-1',
                relevance_score=0.7
            )
        ]

        sources = synthesizer.extract_sources(findings)

        # Should deduplicate by URL
        assert len(sources) == 2
        urls = [s['url'] for s in sources]
        assert 'https://example.com/1' in urls
        assert 'https://example.com/2' in urls


class TestFindingDataclass:
    """Tests for the Finding dataclass."""

    def test_finding_to_dict(self):
        """Test Finding serialization."""
        finding = Finding(
            id='F-001',
            content='Test content',
            source_url='https://example.com',
            source_title='Example',
            agent='test-agent',
            sub_question_id='SQ-001',
            timestamp='2024-01-15T00:00:00Z',
            relevance_score=0.85
        )

        result = finding.to_dict()

        assert result['id'] == 'F-001'
        assert result['content'] == 'Test content'
        assert result['source_url'] == 'https://example.com'
        assert result['agent'] == 'test-agent'
        assert result['relevance_score'] == 0.85


class TestGapDataclass:
    """Tests for the Gap dataclass."""

    def test_gap_to_dict(self):
        """Test Gap serialization."""
        gap = Gap(
            id='GAP-001',
            description='Missing market analysis',
            gap_type='perspective',
            severity='medium',
            related_sub_question='SQ-002',
            recommendation='Consult market analyst'
        )

        result = gap.to_dict()

        assert result['id'] == 'GAP-001'
        assert result['gap_type'] == 'perspective'
        assert result['severity'] == 'medium'


# Allow running tests directly
if __name__ == '__main__':
    pytest.main([__file__, '-v'])
