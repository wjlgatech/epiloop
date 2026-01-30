#!/usr/bin/env python3
"""
Tests for lib/report_generator.py - Research Report Generator

Comprehensive tests covering:
- Report generation from sample synthesis
- Executive summary quality and word limits
- Citation formatting
- Investment reports with disclaimers
- Template rendering
- Confidence badges
"""

import json
import sys
import tempfile
import unittest
import shutil
from pathlib import Path
from datetime import datetime

# Add lib to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "lib"))

from report_generator import ReportConfig, ReportGenerator
from research_synthesizer import Synthesis, Finding, Gap, Conflict
from confidence_scorer import ConfidenceScore
from citation_formatter import CitationFormatter, Citation, Bibliography


class TestReportConfig(unittest.TestCase):
    """Tests for ReportConfig dataclass."""

    def test_default_config(self):
        """Default config should have sensible defaults."""
        config = ReportConfig()
        self.assertEqual(config.format, "markdown")
        self.assertTrue(config.include_executive_summary)
        self.assertTrue(config.include_confidence_scores)
        self.assertTrue(config.include_citations)
        self.assertTrue(config.include_risk_section)
        self.assertIsNone(config.max_length)
        self.assertEqual(config.output_dir, "research-outputs")

    def test_custom_config(self):
        """Should accept custom configuration values."""
        config = ReportConfig(
            format="html",
            include_executive_summary=False,
            max_length=5000,
            output_dir="custom-outputs"
        )
        self.assertEqual(config.format, "html")
        self.assertFalse(config.include_executive_summary)
        self.assertEqual(config.max_length, 5000)
        self.assertEqual(config.output_dir, "custom-outputs")

    def test_config_to_dict(self):
        """Config should serialize to dictionary."""
        config = ReportConfig(format="markdown", max_length=1000)
        data = config.to_dict()
        self.assertEqual(data['format'], "markdown")
        self.assertEqual(data['max_length'], 1000)
        self.assertIn('include_executive_summary', data)


class TestReportGenerator(unittest.TestCase):
    """Tests for ReportGenerator class."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.config = ReportConfig(output_dir=self.temp_dir)
        self.generator = ReportGenerator(self.config)

        # Create sample synthesis for testing
        self.sample_synthesis = self._create_sample_synthesis()

    def tearDown(self):
        """Clean up temp directory."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _create_sample_synthesis(self) -> Synthesis:
        """Create a sample synthesis for testing."""
        findings = [
            Finding(
                id='F-001',
                content='AI research shows significant progress in language models.',
                source_url='https://arxiv.org/abs/example1',
                source_title='AI Progress Paper',
                agent='academic-scanner',
                sub_question_id='SQ-001',
                relevance_score=0.9
            ),
            Finding(
                id='F-002',
                content='Implementation requires careful engineering practices.',
                source_url='https://github.com/example/repo',
                source_title='Implementation Guide',
                agent='technical-diver',
                sub_question_id='SQ-002',
                relevance_score=0.85
            ),
            Finding(
                id='F-003',
                content='Market analysis indicates growing demand for AI solutions.',
                source_url='https://example.com/market',
                source_title='Market Analysis Report',
                agent='market-analyst',
                sub_question_id='SQ-003',
                relevance_score=0.75
            )
        ]

        gaps = [
            Gap(
                id='GAP-001',
                description='No findings for cost analysis',
                gap_type='coverage',
                severity='medium',
                related_sub_question='SQ-004',
                recommendation='Research cost factors'
            ),
            Gap(
                id='GAP-002',
                description='Limited academic sources',
                gap_type='depth',
                severity='low',
                recommendation='Add more academic sources'
            )
        ]

        conflicts = [
            Conflict(
                id='CONF-001',
                finding_ids=['F-001', 'F-003'],
                description='Potential disagreement on timeline',
                resolved=False
            )
        ]

        confidence = ConfidenceScore(
            score=72,
            explanation='Moderate confidence based on 3 sources with some gaps.',
            breakdown={
                'source_count': 70,
                'source_agreement': 75,
                'recency': 80,
                'authority': 65,
                'gap_penalty': -10,
                'conflict_penalty': -5
            }
        )

        sources = [
            {
                'url': 'https://arxiv.org/abs/example1',
                'title': 'AI Progress Paper',
                'agent': 'academic-scanner',
                'relevance': 0.9
            },
            {
                'url': 'https://github.com/example/repo',
                'title': 'Implementation Guide',
                'agent': 'technical-diver',
                'relevance': 0.85
            },
            {
                'url': 'https://example.com/market',
                'title': 'Market Analysis Report',
                'agent': 'market-analyst',
                'relevance': 0.75
            }
        ]

        return Synthesis(
            question='What is the current state of AI research?',
            summary='Research on AI state yielded 3 findings from 3 sources.',
            key_findings=findings,
            gaps=gaps,
            conflicts=conflicts,
            confidence=confidence,
            sources=sources
        )

    def test_generate_general_report(self):
        """Should generate a complete general report."""
        report = self.generator.generate(self.sample_synthesis, domain='general')

        # Check report contains key sections
        self.assertIn('# Research Report', report)
        self.assertIn('## Executive Summary', report)
        self.assertIn('## Key Findings', report)
        self.assertIn('## Sources', report)
        self.assertIn('## Gaps & Limitations', report)
        self.assertIn('## Confidence Assessment', report)

        # Check question is in report
        self.assertIn('What is the current state of AI research?', report)

        # Check findings are included
        self.assertIn('F-001', report)
        self.assertIn('AI research shows significant progress', report)

    def test_generate_investment_report(self):
        """Should generate investment report with mandatory sections."""
        report = self.generator.generate(self.sample_synthesis, domain='investment')

        # Check mandatory investment sections
        self.assertIn('# Investment Research Report', report)
        self.assertIn('RISK WARNING', report)
        self.assertIn('## Risk Assessment', report)
        self.assertIn('## Scenario Analysis', report)
        self.assertIn('## Disclaimer', report)

        # Check disclaimer content
        self.assertIn('does not constitute financial advice', report)
        self.assertIn('Past performance is not indicative', report)

    def test_executive_summary_word_limit(self):
        """Executive summary should be limited to 200 words."""
        summary = self.generator.generate_executive_summary(self.sample_synthesis)

        # Extract just the summary text (remove header)
        summary_text = summary.replace('## Executive Summary\n\n', '')
        word_count = len(summary_text.split())

        self.assertLessEqual(word_count, 210)  # Allow small margin

    def test_executive_summary_content(self):
        """Executive summary should contain key information."""
        summary = self.generator.generate_executive_summary(self.sample_synthesis)

        # Should mention the question (case insensitive)
        self.assertIn('ai research', summary.lower())

        # Should mention source count
        self.assertIn('3', summary)  # 3 sources

        # Should mention confidence
        self.assertIn('72', summary)

    def test_inline_citations(self):
        """Report should have inline citations."""
        report = self.generator.generate(self.sample_synthesis, domain='general')

        # Check for citation markers
        self.assertRegex(report, r'\[\d+\]')

        # Check sources section has numbered entries
        self.assertIn('[1]', report)

    def test_confidence_badges(self):
        """Should add appropriate confidence badges."""
        # Test high confidence
        high_finding = Finding(
            id='F-HIGH',
            content='High confidence finding',
            relevance_score=0.9
        )
        badge = self.generator.add_confidence_badge(high_finding)
        self.assertIn('HIGH', badge)
        self.assertIn('90%', badge)

        # Test medium confidence
        medium_finding = Finding(
            id='F-MED',
            content='Medium confidence finding',
            relevance_score=0.6
        )
        badge = self.generator.add_confidence_badge(medium_finding)
        self.assertIn('MEDIUM', badge)

        # Test low confidence
        low_finding = Finding(
            id='F-LOW',
            content='Low confidence finding',
            relevance_score=0.3
        )
        badge = self.generator.add_confidence_badge(low_finding)
        self.assertIn('LOW', badge)

    def test_format_citations(self):
        """Should format citations with links."""
        sources = [
            {'url': 'https://example.com/1', 'title': 'Source 1', 'agent': 'test', 'relevance': 0.9},
            {'url': 'https://example.com/2', 'title': 'Source 2', 'agent': 'test', 'relevance': 0.8}
        ]
        citations = self.generator.format_citations(sources)

        # Should have markdown links
        self.assertIn('[Source 1](https://example.com/1)', citations)
        self.assertIn('[Source 2](https://example.com/2)', citations)

        # Should have numbered references
        self.assertIn('[1]', citations)
        self.assertIn('[2]', citations)

    def test_gaps_section(self):
        """Should include gaps organized by severity."""
        report = self.generator.generate(self.sample_synthesis, domain='general')

        # Check gap descriptions are included
        self.assertIn('No findings for cost analysis', report)
        self.assertIn('Limited academic sources', report)

    def test_conflicts_section(self):
        """Should include unresolved conflicts."""
        report = self.generator.generate(self.sample_synthesis, domain='general')

        # Check conflict is mentioned
        self.assertIn('CONF-001', report)
        self.assertIn('disagreement', report.lower())

    def test_confidence_assessment_section(self):
        """Should include confidence score breakdown."""
        report = self.generator.generate(self.sample_synthesis, domain='general')

        # Check confidence score
        self.assertIn('72/100', report)

        # Check breakdown factors
        self.assertIn('Source Count', report)
        self.assertIn('Authority', report)

    def test_save_report(self):
        """Should save report to file."""
        report = self.generator.generate(self.sample_synthesis, domain='general')
        path = self.generator.save_report(report, 'test_report.md')

        self.assertTrue(path.exists())
        content = path.read_text()
        self.assertEqual(content, report)

    def test_save_report_auto_filename(self):
        """Should auto-generate filename if not provided."""
        report = self.generator.generate(self.sample_synthesis, domain='general')
        path = self.generator.save_report(report)

        self.assertTrue(path.exists())
        self.assertTrue(path.name.startswith('report_'))
        self.assertTrue(path.name.endswith('.md'))

    def test_max_length_truncation(self):
        """Should truncate report if max_length is set."""
        config = ReportConfig(max_length=500, output_dir=self.temp_dir)
        generator = ReportGenerator(config)

        report = generator.generate(self.sample_synthesis, domain='general')

        self.assertLessEqual(len(report), 550)  # Allow for truncation message
        self.assertIn('[Report truncated]', report)

    def test_disabled_sections(self):
        """Should respect disabled section configuration."""
        config = ReportConfig(
            include_executive_summary=False,
            include_confidence_scores=False,
            include_citations=False,
            output_dir=self.temp_dir
        )
        generator = ReportGenerator(config)

        report = generator.generate(self.sample_synthesis, domain='general')

        # Executive summary should be missing
        self.assertNotIn('## Executive Summary', report)

        # Confidence badges should be missing
        self.assertNotIn('**Confidence:** HIGH', report)


class TestInvestmentReport(unittest.TestCase):
    """Tests specific to investment reports."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.config = ReportConfig(output_dir=self.temp_dir)
        self.generator = ReportGenerator(self.config)

        # Create investment-focused synthesis
        self.investment_synthesis = self._create_investment_synthesis()

    def tearDown(self):
        """Clean up temp directory."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _create_investment_synthesis(self) -> Synthesis:
        """Create investment-focused synthesis."""
        findings = [
            Finding(
                id='F-001',
                content='Revenue growth of 25% year-over-year shows strong fundamentals.',
                source_url='https://example.com/financials',
                source_title='Financial Report',
                agent='market-analyst',
                sub_question_id='SQ-001',
                relevance_score=0.9
            ),
            Finding(
                id='F-002',
                content='Technical indicators show bullish momentum with RSI at 65.',
                source_url='https://example.com/technicals',
                source_title='Technical Analysis',
                agent='market-analyst',
                sub_question_id='SQ-002',
                relevance_score=0.85
            ),
            Finding(
                id='F-003',
                content='Market volatility and regulatory uncertainty pose significant risks.',
                source_url='https://example.com/risks',
                source_title='Risk Assessment',
                agent='market-analyst',
                sub_question_id='SQ-003',
                relevance_score=0.8
            )
        ]

        confidence = ConfidenceScore(
            score=68,
            explanation='Moderate confidence with some risk factors.',
            breakdown={
                'source_count': 70,
                'source_agreement': 70,
                'recency': 75,
                'authority': 60,
                'gap_penalty': -5,
                'conflict_penalty': 0
            }
        )

        sources = [
            {'url': 'https://example.com/financials', 'title': 'Financial Report', 'agent': 'market-analyst', 'relevance': 0.9},
            {'url': 'https://example.com/technicals', 'title': 'Technical Analysis', 'agent': 'market-analyst', 'relevance': 0.85},
            {'url': 'https://example.com/risks', 'title': 'Risk Assessment', 'agent': 'market-analyst', 'relevance': 0.8}
        ]

        return Synthesis(
            question='Should I invest in TechCorp stock?',
            summary='Investment research on TechCorp yielded 3 findings.',
            key_findings=findings,
            gaps=[],
            conflicts=[],
            confidence=confidence,
            sources=sources
        )

    def test_investment_disclaimer_mandatory(self):
        """Investment report MUST include disclaimer."""
        report = self.generator.generate_investment_report(self.investment_synthesis)

        # Disclaimer must be present
        self.assertIn('## Disclaimer', report)
        self.assertIn('does not constitute financial advice', report)
        self.assertIn('investment recommendations', report)
        self.assertIn('loss of principal', report)

    def test_risk_assessment_mandatory(self):
        """Investment report MUST include risk assessment."""
        report = self.generator.generate_investment_report(self.investment_synthesis)

        self.assertIn('## Risk Assessment', report)
        self.assertIn('mandatory', report.lower())
        self.assertIn('Standard Risk Factors', report)

    def test_risk_warning_in_header(self):
        """Investment report should have risk warning in header."""
        report = self.generator.generate_investment_report(self.investment_synthesis)

        # Risk warning should appear early in report
        risk_warning_pos = report.find('RISK WARNING')
        executive_summary_pos = report.find('## Executive Summary')

        self.assertGreater(executive_summary_pos, risk_warning_pos)

    def test_scenario_analysis(self):
        """Investment report should have scenario analysis."""
        report = self.generator.generate_investment_report(self.investment_synthesis)

        self.assertIn('## Scenario Analysis', report)
        self.assertIn('Bull Case', report)
        self.assertIn('Base Case', report)
        self.assertIn('Bear Case', report)

    def test_fundamental_analysis(self):
        """Should extract fundamental analysis from findings."""
        report = self.generator.generate_investment_report(self.investment_synthesis)

        self.assertIn('## Fundamental Analysis', report)
        self.assertIn('revenue', report.lower())
        self.assertIn('growth', report.lower())

    def test_technical_analysis(self):
        """Should extract technical analysis from findings."""
        report = self.generator.generate_investment_report(self.investment_synthesis)

        self.assertIn('## Technical Analysis', report)
        self.assertIn('momentum', report.lower())

    def test_action_plan(self):
        """Should include action plan based on confidence."""
        report = self.generator.generate_investment_report(self.investment_synthesis)

        self.assertIn('## Action Plan', report)
        self.assertIn('financial advisor', report.lower())

    def test_action_plan_low_confidence(self):
        """Low confidence should recommend against action."""
        # Create low confidence synthesis
        low_conf_synthesis = self.investment_synthesis
        low_conf_synthesis.confidence = ConfidenceScore(
            score=35,
            explanation='Low confidence.',
            breakdown={}
        )

        report = self.generator.generate_investment_report(low_conf_synthesis)

        self.assertIn('Do not act on this analysis alone', report)


class TestCitationFormatter(unittest.TestCase):
    """Tests for citation formatting utilities."""

    def setUp(self):
        """Set up test fixtures."""
        self.formatter = CitationFormatter()

    def test_format_inline_citation(self):
        """Should format inline citations."""
        url = 'https://example.com/article'
        citation = self.formatter.format_inline(url)

        self.assertRegex(citation, r'\[\d+\]')

    def test_format_inline_by_number(self):
        """Should format by number directly."""
        citation = self.formatter.format_inline(5)
        self.assertEqual(citation, '[5]')

    def test_format_multiple_citations(self):
        """Should format multiple citations."""
        self.formatter.add_citation('https://example.com/1', 'Source 1')
        self.formatter.add_citation('https://example.com/2', 'Source 2')
        self.formatter.add_citation('https://example.com/3', 'Source 3')

        result = self.formatter.format_multiple([1, 2, 3])
        self.assertEqual(result, '[1-3]')

    def test_format_multiple_non_consecutive(self):
        """Should format non-consecutive citations."""
        self.formatter.add_citation('https://example.com/1', 'Source 1')
        self.formatter.add_citation('https://example.com/2', 'Source 2')
        self.formatter.add_citation('https://example.com/3', 'Source 3')
        self.formatter.add_citation('https://example.com/5', 'Source 5')

        result = self.formatter.format_multiple([1, 2, 5])
        self.assertIn('1', result)
        self.assertIn('2', result)
        self.assertIn('5', result)

    def test_add_citation(self):
        """Should add citation with metadata."""
        citation = self.formatter.add_citation(
            url='https://arxiv.org/abs/123',
            title='Research Paper',
            author='Smith et al.',
            date='2024-06',
            agent='academic-scanner',
            relevance=0.95
        )

        self.assertEqual(citation.title, 'Research Paper')
        self.assertEqual(citation.author, 'Smith et al.')
        self.assertEqual(citation.relevance, 0.95)

    def test_add_citations_from_sources(self):
        """Should add multiple citations from source list."""
        sources = [
            {'url': 'https://example.com/1', 'title': 'Source 1', 'relevance': 0.9},
            {'url': 'https://example.com/2', 'title': 'Source 2', 'relevance': 0.8}
        ]

        citations = self.formatter.add_citations_from_sources(sources)

        self.assertEqual(len(citations), 2)
        self.assertEqual(citations[0].title, 'Source 1')
        self.assertEqual(citations[1].title, 'Source 2')

    def test_generate_markdown_bibliography(self):
        """Should generate markdown bibliography."""
        self.formatter.add_citation('https://example.com/1', 'Source 1', agent='test', relevance=0.9)
        self.formatter.add_citation('https://example.com/2', 'Source 2', agent='test', relevance=0.8)

        bibliography = self.formatter.generate_bibliography("markdown")

        self.assertIn('## Sources', bibliography)
        self.assertIn('[Source 1](https://example.com/1)', bibliography)
        self.assertIn('[1]', bibliography)
        self.assertIn('[2]', bibliography)

    def test_generate_html_bibliography(self):
        """Should generate HTML bibliography."""
        self.formatter.add_citation('https://example.com/1', 'Source 1')

        bibliography = self.formatter.generate_bibliography("html")

        self.assertIn('<h2>Sources</h2>', bibliography)
        self.assertIn('<a href="https://example.com/1">', bibliography)
        self.assertIn('<ol class=\'bibliography\'>', bibliography)

    def test_validate_url_valid(self):
        """Should validate valid URLs."""
        valid_urls = [
            'https://example.com',
            'http://localhost:8000',
            'https://sub.domain.example.com/path?query=1',
            'http://192.168.1.1:3000/api'
        ]

        for url in valid_urls:
            is_valid, error = self.formatter.validate_url(url)
            self.assertTrue(is_valid, f"URL should be valid: {url}")

    def test_validate_url_invalid(self):
        """Should reject invalid URLs."""
        invalid_urls = [
            '',
            'not-a-url',
            'ftp://files.example.com',  # Non-http scheme
            'example.com',  # Missing scheme
        ]

        for url in invalid_urls:
            is_valid, error = self.formatter.validate_url(url)
            self.assertFalse(is_valid, f"URL should be invalid: {url}")
            self.assertIsNotNone(error)

    def test_extract_source_metadata_arxiv(self):
        """Should extract metadata from arxiv URLs."""
        metadata = self.formatter.extract_source_metadata('https://arxiv.org/abs/2301.12345')

        self.assertEqual(metadata['domain'], 'arxiv.org')
        self.assertEqual(metadata['type'], 'academic')

    def test_extract_source_metadata_github(self):
        """Should extract metadata from github URLs."""
        metadata = self.formatter.extract_source_metadata('https://github.com/user/repo')

        self.assertEqual(metadata['domain'], 'github.com')
        self.assertEqual(metadata['type'], 'repository')

    def test_extract_source_metadata_medium(self):
        """Should extract metadata from medium URLs."""
        metadata = self.formatter.extract_source_metadata('https://medium.com/@user/article-title-abc123')

        self.assertEqual(metadata['domain'], 'medium.com')
        self.assertEqual(metadata['type'], 'blog')

    def test_get_citation_by_number(self):
        """Should retrieve citation by number."""
        self.formatter.add_citation('https://example.com/1', 'Source 1')
        self.formatter.add_citation('https://example.com/2', 'Source 2')

        citation = self.formatter.get_citation_by_number(2)

        self.assertIsNotNone(citation)
        self.assertEqual(citation.title, 'Source 2')

    def test_get_citation_by_url(self):
        """Should retrieve citation by URL."""
        self.formatter.add_citation('https://example.com/1', 'Source 1')

        citation = self.formatter.get_citation_by_url('https://example.com/1')

        self.assertIsNotNone(citation)
        self.assertEqual(citation.title, 'Source 1')

    def test_reset_formatter(self):
        """Should reset all citations."""
        self.formatter.add_citation('https://example.com/1', 'Source 1')
        self.formatter.reset()

        citations = self.formatter.get_all_citations()
        self.assertEqual(len(citations), 0)


class TestTemplateRendering(unittest.TestCase):
    """Tests for template-based rendering."""

    def test_general_template_exists(self):
        """General report template should exist."""
        template_path = Path(__file__).parent.parent / 'templates' / 'report-template.md'
        self.assertTrue(template_path.exists())

    def test_investment_template_exists(self):
        """Investment report template should exist."""
        template_path = Path(__file__).parent.parent / 'templates' / 'investment-report-template.md'
        self.assertTrue(template_path.exists())

    def test_general_template_contains_required_sections(self):
        """General template should have all required sections."""
        template_path = Path(__file__).parent.parent / 'templates' / 'report-template.md'
        content = template_path.read_text()

        required_sections = [
            'Executive Summary',
            'Key Findings',
            'Detailed Analysis',
            'Sources',
            'Gaps & Limitations',
            'Confidence Assessment'
        ]

        for section in required_sections:
            self.assertIn(section, content)

    def test_investment_template_contains_mandatory_sections(self):
        """Investment template should have mandatory sections."""
        template_path = Path(__file__).parent.parent / 'templates' / 'investment-report-template.md'
        content = template_path.read_text()

        mandatory_sections = [
            'Risk Assessment',
            'Disclaimer',
            'Scenario Analysis'
        ]

        for section in mandatory_sections:
            self.assertIn(section, content)


class TestEdgeCases(unittest.TestCase):
    """Tests for edge cases and error handling."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.config = ReportConfig(output_dir=self.temp_dir)
        self.generator = ReportGenerator(self.config)

    def tearDown(self):
        """Clean up temp directory."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_empty_findings(self):
        """Should handle synthesis with no findings."""
        synthesis = Synthesis(
            question='Empty research question',
            summary='No findings',
            key_findings=[],
            gaps=[],
            conflicts=[],
            confidence=ConfidenceScore(score=0, explanation='No data', breakdown={}),
            sources=[]
        )

        report = self.generator.generate(synthesis, domain='general')

        self.assertIn('No key findings were identified', report)
        self.assertIn('No sources available', report)

    def test_empty_sources(self):
        """Should handle synthesis with no sources."""
        synthesis = Synthesis(
            question='Research without sources',
            summary='Test',
            key_findings=[
                Finding(id='F-001', content='Finding without source')
            ],
            gaps=[],
            conflicts=[],
            confidence=ConfidenceScore(score=20, explanation='Low confidence', breakdown={}),
            sources=[]
        )

        report = self.generator.generate(synthesis, domain='general')

        self.assertIn('No sources available', report)

    def test_special_characters_in_question(self):
        """Should handle special characters in question."""
        synthesis = Synthesis(
            question='What about "special" characters & <html>?',
            summary='Test',
            key_findings=[],
            gaps=[],
            conflicts=[],
            confidence=ConfidenceScore(score=50, explanation='Test', breakdown={}),
            sources=[]
        )

        report = self.generator.generate(synthesis, domain='general')

        # Should not crash and should include the question
        self.assertIn('special', report)

    def test_very_long_finding_content(self):
        """Should handle very long finding content."""
        long_content = 'A' * 5000

        synthesis = Synthesis(
            question='Test',
            summary='Test',
            key_findings=[
                Finding(id='F-001', content=long_content)
            ],
            gaps=[],
            conflicts=[],
            confidence=ConfidenceScore(score=50, explanation='Test', breakdown={}),
            sources=[]
        )

        report = self.generator.generate(synthesis, domain='general')

        # Should include the content (or truncated version)
        self.assertIn('AAA', report)


if __name__ == '__main__':
    unittest.main()
