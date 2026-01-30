#!/usr/bin/env python3
"""
Report Generator - Generate research reports from synthesized findings

This module provides functionality to:
1. Generate full research reports from synthesis results
2. Create executive summaries with key findings
3. Format inline citations with links
4. Add visual confidence indicators (badges)
5. Generate investment-specific reports with disclaimers
6. Support multiple output formats (markdown, with hooks for HTML/PDF)
"""

import sys
import re
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any
from datetime import datetime
from pathlib import Path

# Add lib directory to path for imports
SCRIPT_DIR = Path(__file__).parent
sys.path.insert(0, str(SCRIPT_DIR))

from research_synthesizer import Synthesis, Finding, Gap, Conflict
from confidence_scorer import ConfidenceScore


@dataclass
class ReportConfig:
    """Configuration for report generation."""
    format: str = "markdown"  # markdown, html, pdf
    include_executive_summary: bool = True
    include_confidence_scores: bool = True
    include_citations: bool = True
    include_risk_section: bool = True  # For investment reports
    max_length: Optional[int] = None  # Max characters for report

    # Template customization
    template_path: Optional[str] = None
    custom_sections: Optional[List[str]] = None

    # Output settings
    output_dir: str = "research-outputs"
    filename_prefix: str = "report"

    def to_dict(self) -> Dict:
        """Convert config to dictionary."""
        return {
            'format': self.format,
            'include_executive_summary': self.include_executive_summary,
            'include_confidence_scores': self.include_confidence_scores,
            'include_citations': self.include_citations,
            'include_risk_section': self.include_risk_section,
            'max_length': self.max_length,
            'template_path': self.template_path,
            'custom_sections': self.custom_sections,
            'output_dir': self.output_dir,
            'filename_prefix': self.filename_prefix
        }


class ReportGenerator:
    """Generates research reports from synthesis results."""

    # Executive summary word limit
    EXECUTIVE_SUMMARY_MAX_WORDS = 200

    # Confidence badge thresholds
    CONFIDENCE_HIGH = 75
    CONFIDENCE_MEDIUM = 50
    CONFIDENCE_LOW = 25

    # Investment disclaimer (mandatory for investment reports)
    INVESTMENT_DISCLAIMER = """
---

## Disclaimer

**IMPORTANT: This report is for informational purposes only and does not constitute financial advice, investment recommendations, or an offer to buy or sell any securities.**

- Past performance is not indicative of future results
- All investments carry risk, including potential loss of principal
- The information presented may not be accurate, complete, or current
- Consult a qualified financial advisor before making investment decisions
- The authors and generators of this report are not responsible for any investment decisions made based on this information

---
"""

    def __init__(self, config: Optional[ReportConfig] = None):
        """
        Initialize the report generator.

        Args:
            config: Report configuration options
        """
        self.config = config or ReportConfig()
        self._citation_map: Dict[str, int] = {}
        self._citation_counter = 0

    def generate(self, synthesis: Synthesis, domain: str = "general") -> str:
        """
        Generate full report from synthesis.

        Args:
            synthesis: The synthesis object containing findings
            domain: Research domain (general, investment, ai-ml)

        Returns:
            Generated report as string
        """
        # Reset citation tracking for new report
        self._citation_map = {}
        self._citation_counter = 0

        # Choose report type based on domain
        if domain == "investment":
            return self.generate_investment_report(synthesis)

        return self._generate_general_report(synthesis, domain)

    def _generate_general_report(self, synthesis: Synthesis, domain: str) -> str:
        """Generate a general research report."""
        sections = []

        # Header
        sections.append(self._generate_header(synthesis))

        # Executive Summary
        if self.config.include_executive_summary:
            sections.append(self.generate_executive_summary(synthesis))

        # Key Findings
        sections.append(self._generate_key_findings(synthesis))

        # Detailed Analysis
        sections.append(self._generate_detailed_analysis(synthesis))

        # Sources/Citations
        if self.config.include_citations:
            sections.append(self.format_citations(synthesis.sources))

        # Gaps & Limitations
        sections.append(self._generate_gaps_section(synthesis))

        # Confidence Assessment
        if self.config.include_confidence_scores:
            sections.append(self._generate_confidence_assessment(synthesis))

        # Join all sections
        report = "\n\n".join(sections)

        # Apply max length if configured
        if self.config.max_length and len(report) > self.config.max_length:
            report = report[:self.config.max_length] + "\n\n...[Report truncated]"

        return report

    def _generate_header(self, synthesis: Synthesis) -> str:
        """Generate report header."""
        timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")

        header = f"""# Research Report

**Question:** {synthesis.question}

**Generated:** {timestamp}

**Sources:** {len(synthesis.sources)} | **Confidence:** {synthesis.confidence.score}/100
"""
        return header

    def generate_executive_summary(self, synthesis: Synthesis) -> str:
        """
        Generate 2-3 paragraph summary of key findings.

        Limited to 200 words as per requirements.

        Args:
            synthesis: The synthesis object

        Returns:
            Executive summary string
        """
        # Build summary from synthesis data
        finding_count = len(synthesis.key_findings)
        source_count = len(synthesis.sources)
        gap_count = len(synthesis.gaps)
        conflict_count = len([c for c in synthesis.conflicts if not c.resolved])

        # First paragraph - overview
        confidence_level = self._get_confidence_level(synthesis.confidence.score)
        para1 = (
            f"This research addresses the question: \"{synthesis.question}\". "
            f"Analysis of {source_count} sources yielded {finding_count} key findings. "
            f"Overall confidence is {confidence_level} ({synthesis.confidence.score}/100)."
        )

        # Second paragraph - key findings summary
        top_findings = synthesis.key_findings[:3]
        if top_findings:
            finding_summaries = []
            for f in top_findings:
                # Truncate finding content for summary
                summary = f.content[:100] + "..." if len(f.content) > 100 else f.content
                finding_summaries.append(summary)
            para2 = "Key findings include: " + "; ".join(finding_summaries)
        else:
            para2 = "No key findings were identified in the available sources."

        # Third paragraph - limitations
        if gap_count > 0 or conflict_count > 0:
            limitations = []
            if gap_count > 0:
                limitations.append(f"{gap_count} gap(s) in coverage")
            if conflict_count > 0:
                limitations.append(f"{conflict_count} unresolved conflict(s)")
            para3 = f"Limitations: {', '.join(limitations)}. Further research may be needed."
        else:
            para3 = "No significant gaps or conflicts were identified."

        # Combine and enforce word limit
        full_summary = f"{para1}\n\n{para2}\n\n{para3}"
        words = full_summary.split()
        if len(words) > self.EXECUTIVE_SUMMARY_MAX_WORDS:
            words = words[:self.EXECUTIVE_SUMMARY_MAX_WORDS]
            full_summary = ' '.join(words) + "..."

        return f"## Executive Summary\n\n{full_summary}"

    def _generate_key_findings(self, synthesis: Synthesis) -> str:
        """Generate key findings section with confidence badges."""
        lines = ["## Key Findings\n"]

        if not synthesis.key_findings:
            lines.append("*No key findings were identified.*\n")
            return '\n'.join(lines)

        for i, finding in enumerate(synthesis.key_findings, 1):
            # Add finding with confidence badge
            badge = self.add_confidence_badge(finding) if self.config.include_confidence_scores else ""
            citation = self._get_citation_reference(finding.source_url) if self.config.include_citations else ""

            lines.append(f"### {i}. {finding.id}")
            if badge:
                lines.append(f"**Confidence:** {badge}")
            lines.append(f"\n{finding.content}{citation}\n")

            if finding.source_title:
                lines.append(f"*Source: {finding.source_title}*\n")

        return '\n'.join(lines)

    def _generate_detailed_analysis(self, synthesis: Synthesis) -> str:
        """Generate detailed analysis by sub-question."""
        lines = ["## Detailed Analysis\n"]

        # Group findings by sub-question
        findings_by_sq: Dict[str, List[Finding]] = {}
        uncategorized: List[Finding] = []

        for finding in synthesis.key_findings:
            if finding.sub_question_id:
                if finding.sub_question_id not in findings_by_sq:
                    findings_by_sq[finding.sub_question_id] = []
                findings_by_sq[finding.sub_question_id].append(finding)
            else:
                uncategorized.append(finding)

        # Output by sub-question
        for sq_id, findings in findings_by_sq.items():
            lines.append(f"### Sub-question: {sq_id}\n")
            for f in findings:
                citation = self._get_citation_reference(f.source_url) if self.config.include_citations else ""
                lines.append(f"- {f.content}{citation}")
            lines.append("")

        # Uncategorized findings
        if uncategorized:
            lines.append("### General Findings\n")
            for f in uncategorized:
                citation = self._get_citation_reference(f.source_url) if self.config.include_citations else ""
                lines.append(f"- {f.content}{citation}")
            lines.append("")

        return '\n'.join(lines)

    def format_citations(self, sources: List[Dict]) -> str:
        """
        Format inline citations with links.

        Args:
            sources: List of source dictionaries

        Returns:
            Formatted citations/bibliography section
        """
        lines = ["## Sources\n"]

        if not sources:
            lines.append("*No sources available.*\n")
            return '\n'.join(lines)

        for i, source in enumerate(sources, 1):
            url = source.get('url', '')
            title = source.get('title', url or 'Unknown Source')
            agent = source.get('agent', '')
            relevance = source.get('relevance', 0)

            # Store citation mapping
            if url:
                self._citation_map[url] = i

            # Format citation entry
            citation_entry = f"[{i}] "
            if url:
                citation_entry += f"[{title}]({url})"
            else:
                citation_entry += title

            if agent:
                citation_entry += f" *(via {agent})*"

            if relevance > 0:
                citation_entry += f" - Relevance: {relevance:.0%}"

            lines.append(citation_entry)

        return '\n'.join(lines)

    def _get_citation_reference(self, url: Optional[str]) -> str:
        """Get inline citation reference for a URL."""
        if not url:
            return ""

        # Check if already mapped
        if url in self._citation_map:
            return f" [{self._citation_map[url]}]"

        # Create new mapping
        self._citation_counter += 1
        self._citation_map[url] = self._citation_counter
        return f" [{self._citation_counter}]"

    def add_confidence_badge(self, finding: Finding) -> str:
        """
        Add visual confidence indicator for a finding.

        Args:
            finding: The finding to badge

        Returns:
            Confidence badge string
        """
        # Use relevance score as proxy for confidence
        score = int(finding.relevance_score * 100)

        if score >= self.CONFIDENCE_HIGH:
            return f"HIGH ({score}%)"
        elif score >= self.CONFIDENCE_MEDIUM:
            return f"MEDIUM ({score}%)"
        elif score >= self.CONFIDENCE_LOW:
            return f"LOW ({score}%)"
        else:
            return f"VERY LOW ({score}%)"

    def _generate_gaps_section(self, synthesis: Synthesis) -> str:
        """Generate gaps and limitations section."""
        lines = ["## Gaps & Limitations\n"]

        if not synthesis.gaps:
            lines.append("*No significant gaps identified.*\n")
        else:
            # Group by severity
            critical = [g for g in synthesis.gaps if g.severity == 'critical']
            high = [g for g in synthesis.gaps if g.severity == 'high']
            medium = [g for g in synthesis.gaps if g.severity == 'medium']
            low = [g for g in synthesis.gaps if g.severity == 'low']

            if critical:
                lines.append("### Critical Gaps\n")
                for g in critical:
                    lines.append(f"- **{g.id}**: {g.description}")
                    if g.recommendation:
                        lines.append(f"  - *Recommendation: {g.recommendation}*")
                lines.append("")

            if high:
                lines.append("### High Priority Gaps\n")
                for g in high:
                    lines.append(f"- **{g.id}**: {g.description}")
                    if g.recommendation:
                        lines.append(f"  - *Recommendation: {g.recommendation}*")
                lines.append("")

            if medium:
                lines.append("### Medium Priority Gaps\n")
                for g in medium:
                    lines.append(f"- {g.description}")
                lines.append("")

            if low:
                lines.append("### Low Priority Gaps\n")
                for g in low:
                    lines.append(f"- {g.description}")
                lines.append("")

        # Add conflicts if any
        unresolved = [c for c in synthesis.conflicts if not c.resolved]
        if unresolved:
            lines.append("### Conflicting Information\n")
            for c in unresolved:
                lines.append(f"- **{c.id}**: {c.description}")
            lines.append("")

        return '\n'.join(lines)

    def _generate_confidence_assessment(self, synthesis: Synthesis) -> str:
        """Generate confidence assessment section."""
        conf = synthesis.confidence

        lines = ["## Confidence Assessment\n"]
        lines.append(f"**Overall Score:** {conf.score}/100 - {self._get_confidence_level(conf.score)}\n")
        lines.append(f"**Explanation:** {conf.explanation}\n")

        # Breakdown if available
        if conf.breakdown:
            lines.append("### Score Breakdown\n")
            lines.append("| Factor | Score |")
            lines.append("|--------|-------|")
            for factor, score in conf.breakdown.items():
                if not factor.endswith('_penalty'):
                    lines.append(f"| {factor.replace('_', ' ').title()} | {score:.0f} |")

            # Show penalties separately
            penalties = {k: v for k, v in conf.breakdown.items() if k.endswith('_penalty')}
            if penalties:
                lines.append("\n### Penalties Applied\n")
                for factor, penalty in penalties.items():
                    if penalty != 0:
                        lines.append(f"- {factor.replace('_', ' ').title()}: {penalty:.0f} points")

        return '\n'.join(lines)

    def _get_confidence_level(self, score: int) -> str:
        """Get human-readable confidence level."""
        if score >= 90:
            return "Very High"
        elif score >= 75:
            return "High"
        elif score >= 60:
            return "Moderate"
        elif score >= 40:
            return "Low"
        else:
            return "Very Low"

    def generate_investment_report(self, synthesis: Synthesis) -> str:
        """
        Generate investment-specific report with disclaimers.

        Investment reports MUST include:
        - Risk warning in executive summary
        - Risk assessment section
        - Scenario analysis (bull/base/bear)
        - Full disclaimer

        Args:
            synthesis: The synthesis object

        Returns:
            Investment report as string
        """
        # Reset citation tracking
        self._citation_map = {}
        self._citation_counter = 0

        sections = []

        # Header with risk warning
        sections.append(self._generate_investment_header(synthesis))

        # Executive summary with risk warning
        sections.append(self._generate_investment_executive_summary(synthesis))

        # Opportunity Overview
        sections.append(self._generate_opportunity_overview(synthesis))

        # Fundamental Analysis
        sections.append(self._generate_fundamental_analysis(synthesis))

        # Technical Analysis
        sections.append(self._generate_technical_analysis(synthesis))

        # Risk Assessment (MANDATORY)
        sections.append(self._generate_risk_assessment(synthesis))

        # Scenario Analysis
        sections.append(self._generate_scenario_analysis(synthesis))

        # Action Plan
        sections.append(self._generate_action_plan(synthesis))

        # Sources
        if self.config.include_citations:
            sections.append(self.format_citations(synthesis.sources))

        # Confidence Assessment
        if self.config.include_confidence_scores:
            sections.append(self._generate_confidence_assessment(synthesis))

        # Full Disclaimer (MANDATORY)
        sections.append(self.INVESTMENT_DISCLAIMER)

        return "\n\n".join(sections)

    def _generate_investment_header(self, synthesis: Synthesis) -> str:
        """Generate investment report header with risk warning."""
        timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")

        return f"""# Investment Research Report

**Subject:** {synthesis.question}

**Generated:** {timestamp}

**Confidence:** {synthesis.confidence.score}/100 | **Sources:** {len(synthesis.sources)}

> **RISK WARNING:** This report is for informational purposes only and does not constitute investment advice. All investments carry risk. Past performance is not indicative of future results.
"""

    def _generate_investment_executive_summary(self, synthesis: Synthesis) -> str:
        """Generate executive summary with risk emphasis."""
        base_summary = self.generate_executive_summary(synthesis)

        # Add risk reminder
        risk_reminder = (
            "\n\n> **Note:** This analysis involves uncertainty. "
            "See Risk Assessment section for detailed risk factors."
        )

        return base_summary + risk_reminder

    def _generate_opportunity_overview(self, synthesis: Synthesis) -> str:
        """Generate opportunity overview section."""
        lines = ["## Opportunity Overview\n"]

        # Extract relevant findings
        relevant = [f for f in synthesis.key_findings if f.relevance_score >= 0.7]

        if relevant:
            lines.append("### Key Investment Thesis\n")
            for f in relevant[:3]:
                citation = self._get_citation_reference(f.source_url)
                lines.append(f"- {f.content}{citation}")
        else:
            lines.append("*Insufficient data to establish investment thesis.*")

        lines.append("")
        return '\n'.join(lines)

    def _generate_fundamental_analysis(self, synthesis: Synthesis) -> str:
        """Generate fundamental analysis section."""
        lines = ["## Fundamental Analysis\n"]

        # Look for findings related to fundamentals
        fundamental_keywords = ['revenue', 'earnings', 'growth', 'market', 'valuation',
                               'profit', 'margin', 'cash', 'debt', 'balance']

        fundamental_findings = []
        for f in synthesis.key_findings:
            content_lower = f.content.lower()
            if any(kw in content_lower for kw in fundamental_keywords):
                fundamental_findings.append(f)

        if fundamental_findings:
            for f in fundamental_findings:
                citation = self._get_citation_reference(f.source_url)
                lines.append(f"- {f.content}{citation}")
        else:
            lines.append("*No fundamental analysis data available in sources.*")

        lines.append("")
        return '\n'.join(lines)

    def _generate_technical_analysis(self, synthesis: Synthesis) -> str:
        """Generate technical analysis section."""
        lines = ["## Technical Analysis\n"]

        # Look for findings related to technicals
        technical_keywords = ['price', 'trend', 'support', 'resistance', 'volume',
                             'momentum', 'moving average', 'indicator', 'chart']

        technical_findings = []
        for f in synthesis.key_findings:
            content_lower = f.content.lower()
            if any(kw in content_lower for kw in technical_keywords):
                technical_findings.append(f)

        if technical_findings:
            for f in technical_findings:
                citation = self._get_citation_reference(f.source_url)
                lines.append(f"- {f.content}{citation}")
        else:
            lines.append("*No technical analysis data available in sources.*")

        lines.append("")
        return '\n'.join(lines)

    def _generate_risk_assessment(self, synthesis: Synthesis) -> str:
        """Generate risk assessment section (MANDATORY for investment reports)."""
        lines = ["## Risk Assessment\n"]
        lines.append("> **This section is mandatory and must not be skipped.**\n")

        # Categorize risks
        lines.append("### Identified Risks\n")

        # Extract risk-related findings
        risk_keywords = ['risk', 'concern', 'warning', 'threat', 'challenge',
                        'uncertainty', 'volatile', 'decline', 'loss', 'negative']

        risk_findings = []
        for f in synthesis.key_findings:
            content_lower = f.content.lower()
            if any(kw in content_lower for kw in risk_keywords):
                risk_findings.append(f)

        if risk_findings:
            for f in risk_findings:
                citation = self._get_citation_reference(f.source_url)
                lines.append(f"- **Risk:** {f.content}{citation}")

        # Add gaps as risks
        if synthesis.gaps:
            lines.append("\n### Information Gaps (Additional Risk)\n")
            for g in synthesis.gaps:
                lines.append(f"- {g.description}")

        # Add conflicts as uncertainty
        unresolved = [c for c in synthesis.conflicts if not c.resolved]
        if unresolved:
            lines.append("\n### Conflicting Information (Uncertainty)\n")
            for c in unresolved:
                lines.append(f"- {c.description}")

        # Standard risk disclaimer
        lines.append("\n### Standard Risk Factors\n")
        lines.append("- Market risk: General market conditions may impact performance")
        lines.append("- Liquidity risk: May not be able to exit position at desired price")
        lines.append("- Information risk: Analysis based on potentially incomplete or inaccurate data")
        lines.append("- Timing risk: Entry/exit timing significantly impacts returns")

        lines.append("")
        return '\n'.join(lines)

    def _generate_scenario_analysis(self, synthesis: Synthesis) -> str:
        """Generate scenario analysis (bull/base/bear cases)."""
        confidence = synthesis.confidence.score

        lines = ["## Scenario Analysis\n"]

        lines.append("### Bull Case (Optimistic)\n")
        if confidence >= 70:
            lines.append("- Strong evidence supports positive thesis")
            lines.append("- Multiple corroborating sources")
        else:
            lines.append("- Upside potential exists but evidence is limited")
        lines.append("")

        lines.append("### Base Case (Expected)\n")
        if 40 <= confidence < 70:
            lines.append("- Moderate confidence in current analysis")
            lines.append("- Some gaps in information should be considered")
        elif confidence >= 70:
            lines.append("- High confidence scenario based on available data")
        else:
            lines.append("- Low confidence - base case highly uncertain")
        lines.append("")

        lines.append("### Bear Case (Pessimistic)\n")
        lines.append("- Consider all identified risks materializing")
        if synthesis.gaps:
            lines.append(f"- {len(synthesis.gaps)} information gap(s) could reveal negative factors")
        if synthesis.conflicts:
            lines.append(f"- {len(synthesis.conflicts)} conflicting information point(s) suggest uncertainty")
        lines.append("")

        return '\n'.join(lines)

    def _generate_action_plan(self, synthesis: Synthesis) -> str:
        """Generate action plan section."""
        confidence = synthesis.confidence.score

        lines = ["## Action Plan\n"]

        if confidence >= 75:
            lines.append("### Recommended Actions (High Confidence)\n")
            lines.append("1. Review full analysis and risk assessment")
            lines.append("2. Consult with financial advisor")
            lines.append("3. Consider position sizing based on risk tolerance")
            lines.append("4. Set entry/exit criteria before acting")
        elif confidence >= 50:
            lines.append("### Recommended Actions (Moderate Confidence)\n")
            lines.append("1. Conduct additional research to fill gaps")
            lines.append("2. Wait for more information before acting")
            lines.append("3. If proceeding, use smaller position sizes")
            lines.append("4. Consult with financial advisor")
        else:
            lines.append("### Recommended Actions (Low Confidence)\n")
            lines.append("1. **Do not act on this analysis alone**")
            lines.append("2. Significant additional research required")
            lines.append("3. Seek multiple independent analyses")
            lines.append("4. Consult with qualified financial advisor")

        lines.append("\n> **Reminder:** Always consult a qualified financial advisor before making investment decisions.")
        lines.append("")

        return '\n'.join(lines)

    def save_report(self, report: str, filename: Optional[str] = None) -> Path:
        """
        Save report to research-outputs directory.

        Args:
            report: The report content
            filename: Optional filename (auto-generated if not provided)

        Returns:
            Path to saved report
        """
        # Ensure output directory exists
        output_dir = Path(self.config.output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        # Generate filename if not provided
        if not filename:
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            extension = self._get_extension()
            filename = f"{self.config.filename_prefix}_{timestamp}.{extension}"

        # Write report
        output_path = output_dir / filename
        output_path.write_text(report, encoding='utf-8')

        return output_path

    def _get_extension(self) -> str:
        """Get file extension based on format."""
        extensions = {
            'markdown': 'md',
            'html': 'html',
            'pdf': 'pdf'
        }
        return extensions.get(self.config.format, 'md')


def main():
    """CLI demo for report generator."""
    import json

    print("Report Generator Demo")
    print("=" * 40)

    # Create sample synthesis data
    from research_synthesizer import ResearchSynthesizer, Finding

    # Create sample findings
    findings_by_agent = {
        'academic-scanner': [
            Finding(
                id='F-001',
                content='Recent research shows significant market growth potential in AI sector.',
                source_url='https://arxiv.org/abs/example1',
                source_title='AI Market Analysis 2024',
                agent='academic-scanner',
                sub_question_id='SQ-001',
                relevance_score=0.9
            )
        ],
        'market-analyst': [
            Finding(
                id='F-002',
                content='Technical indicators suggest bullish momentum with strong support levels.',
                source_url='https://example.com/analysis',
                source_title='Technical Analysis Report',
                agent='market-analyst',
                sub_question_id='SQ-002',
                relevance_score=0.85
            ),
            Finding(
                id='F-003',
                content='Risk factors include market volatility and regulatory uncertainty.',
                source_url='https://example.com/risks',
                source_title='Risk Assessment',
                agent='market-analyst',
                sub_question_id='SQ-003',
                relevance_score=0.75
            )
        ]
    }

    sub_questions = [
        {'id': 'SQ-001', 'question': 'What is the growth potential?'},
        {'id': 'SQ-002', 'question': 'What do technical indicators show?'},
        {'id': 'SQ-003', 'question': 'What are the key risks?'}
    ]

    # Run synthesis
    synthesizer = ResearchSynthesizer(domain='investment')
    synthesis = synthesizer.synthesize(
        question="Should I invest in AI companies?",
        findings_by_agent=findings_by_agent,
        sub_questions=sub_questions
    )

    # Generate general report
    print("\n--- General Report ---\n")
    config = ReportConfig(format='markdown')
    generator = ReportGenerator(config)
    report = generator.generate(synthesis, domain='general')
    print(report[:2000] + "...\n")

    # Generate investment report
    print("\n--- Investment Report ---\n")
    investment_config = ReportConfig(
        format='markdown',
        include_risk_section=True
    )
    investment_generator = ReportGenerator(investment_config)
    investment_report = investment_generator.generate(synthesis, domain='investment')
    print(investment_report[:3000] + "...\n")

    # Save reports
    print("\nSaving reports...")
    general_path = generator.save_report(report, "demo_general_report.md")
    print(f"General report saved to: {general_path}")

    investment_path = investment_generator.save_report(investment_report, "demo_investment_report.md")
    print(f"Investment report saved to: {investment_path}")


if __name__ == '__main__':
    main()
