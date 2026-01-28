#!/usr/bin/env python3
"""
Counterargument Finder - Find and rate counterarguments for research conclusions

This module provides:
- Conclusion extraction from synthesis documents
- Search for opposing viewpoints and contradicting evidence
- Counterargument strength rating (weak/moderate/strong)
- Structured counterargument reports

Usage:
    python3 counterargument-finder.py extract --file <path> [--json]
    python3 counterargument-finder.py find --conclusion "<text>" [--json]
    python3 counterargument-finder.py rate --counterargument "<text>" [--json]
    python3 counterargument-finder.py report --synthesis <file> [--output <file>]
"""

import argparse
import hashlib
import json
import os
import re
import sys
from dataclasses import dataclass, asdict, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Add lib directory to path for imports
SCRIPT_DIR = Path(__file__).parent
sys.path.insert(0, str(SCRIPT_DIR))


class CounterStrength(str, Enum):
    """Counterargument strength classification."""
    STRONG = "strong"       # Credible sources, clear logic, addresses core claims
    MODERATE = "moderate"   # Valid points but limited scope or evidence
    WEAK = "weak"           # Speculative or easily refutable


class CounterType(str, Enum):
    """Types of counterarguments."""
    EMPIRICAL = "empirical"           # Data contradicting conclusions
    METHODOLOGICAL = "methodological"  # Flaws in research approach
    INTERPRETIVE = "interpretive"      # Alternative readings of data
    CONTEXTUAL = "contextual"          # Situational limitations
    TEMPORAL = "temporal"              # Time-bound validity
    STAKEHOLDER = "stakeholder"        # Conflicting interests/opinions


@dataclass
class Conclusion:
    """Extracted conclusion from research synthesis."""
    id: str
    text: str
    conclusion_type: str  # thesis, claim, recommendation, prediction
    confidence: int  # 0-100 original confidence
    supporting_claims: List[str] = field(default_factory=list)
    source_location: str = ""
    extracted_at: str = ""

    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class CounterSource:
    """A source providing counterevidence."""
    url: str
    title: str
    snippet: str
    credibility_score: int  # 0-100
    relevance_score: float  # 0.0-1.0

    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class Counterargument:
    """A counterargument to a conclusion."""
    id: str
    conclusion_id: str
    counter_type: CounterType
    strength: CounterStrength
    claim: str
    evidence: str
    sources: List[CounterSource] = field(default_factory=list)
    strength_score: int = 0  # 0-100
    impact_description: str = ""
    created_at: str = ""

    def to_dict(self) -> Dict:
        result = asdict(self)
        result["counter_type"] = self.counter_type.value
        result["strength"] = self.strength.value
        result["sources"] = [s.to_dict() if hasattr(s, 'to_dict') else s for s in self.sources]
        return result


@dataclass
class AlternativeInterpretation:
    """An alternative interpretation of the same data."""
    id: str
    conclusion_id: str
    interpretation: str
    plausibility: str  # high, medium, low
    required_evidence: str  # What would support this alternative
    created_at: str = ""

    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class DevilsAdvocateReport:
    """Complete devil's advocate analysis report."""
    synthesis_file: str
    analysis_date: str
    conclusions: List[Conclusion]
    counterarguments: List[Counterargument]
    alternatives: List[AlternativeInterpretation]
    robustness_scores: Dict[str, int]  # conclusion_id -> score
    overall_robustness: int
    recommendations: List[str]

    def to_dict(self) -> Dict:
        return {
            "synthesis_file": self.synthesis_file,
            "analysis_date": self.analysis_date,
            "conclusions": [c.to_dict() for c in self.conclusions],
            "counterarguments": [c.to_dict() for c in self.counterarguments],
            "alternatives": [a.to_dict() for a in self.alternatives],
            "robustness_scores": self.robustness_scores,
            "overall_robustness": self.overall_robustness,
            "recommendations": self.recommendations
        }


class ConclusionExtractor:
    """Extracts conclusions from synthesis documents."""

    # Patterns indicating conclusions
    CONCLUSION_PATTERNS = [
        # Thesis statements
        (r'\b(?:conclude|concluded|conclusion)\s+(?:that\s+)?(.+?)(?:\.|$)', 'thesis'),
        (r'\b(?:evidence\s+)?(?:suggests?|indicates?|shows?|demonstrates?)\s+(?:that\s+)?(.+?)(?:\.|$)', 'thesis'),
        (r'\b(?:we|this\s+(?:study|research|analysis))\s+(?:find|found|argue|show)\s+(?:that\s+)?(.+?)(?:\.|$)', 'thesis'),

        # Claims
        (r'\b(?:clearly|therefore|thus|hence|consequently)\s*,?\s*(.+?)(?:\.|$)', 'claim'),
        (r'\b(?:it\s+is\s+)?(?:clear|evident|apparent)\s+that\s+(.+?)(?:\.|$)', 'claim'),

        # Recommendations
        (r'\b(?:recommend|should|must|need\s+to)\s+(.+?)(?:\.|$)', 'recommendation'),
        (r'\b(?:best\s+practice|optimal\s+approach)\s+(?:is\s+)?(.+?)(?:\.|$)', 'recommendation'),

        # Predictions
        (r'\b(?:will|expect|anticipate|predict|forecast)\s+(.+?)(?:\.|$)', 'prediction'),
        (r'\b(?:by\s+\d{4})\s*,?\s*(.+?)(?:\.|$)', 'prediction'),
    ]

    def __init__(self):
        self.conclusions: List[Conclusion] = []

    def extract_from_text(self, text: str, source_location: str = "unknown") -> List[Conclusion]:
        """
        Extract conclusions from text.

        Args:
            text: Text to analyze
            source_location: Location identifier for the source

        Returns:
            List of extracted Conclusions
        """
        conclusions = []
        seen_texts = set()

        for pattern, conclusion_type in self.CONCLUSION_PATTERNS:
            matches = re.finditer(pattern, text, re.IGNORECASE | re.MULTILINE)
            for match in matches:
                conclusion_text = match.group(1).strip()

                # Skip if too short or already seen
                if len(conclusion_text) < 20:
                    continue
                if conclusion_text.lower() in seen_texts:
                    continue

                seen_texts.add(conclusion_text.lower())

                conclusion = Conclusion(
                    id=self._generate_id(conclusion_text),
                    text=conclusion_text,
                    conclusion_type=conclusion_type,
                    confidence=70,  # Default confidence
                    supporting_claims=[],
                    source_location=source_location,
                    extracted_at=datetime.utcnow().isoformat() + "Z"
                )
                conclusions.append(conclusion)

        self.conclusions = conclusions
        return conclusions

    def extract_from_file(self, file_path: Path) -> List[Conclusion]:
        """Extract conclusions from a file."""
        with open(file_path, 'r') as f:
            if file_path.suffix == '.json':
                data = json.load(f)
                # Handle synthesis format
                if isinstance(data, dict):
                    parts = []
                    if 'conclusions' in data:
                        parts.extend(str(c) for c in data['conclusions'])
                    if 'synthesis' in data:
                        parts.append(str(data['synthesis']))
                    if 'findings' in data:
                        parts.extend(str(f) for f in data['findings'])
                    text = '\n'.join(parts) if parts else json.dumps(data)
                else:
                    text = json.dumps(data)
            else:
                text = f.read()

        return self.extract_from_text(text, str(file_path))

    def _generate_id(self, text: str) -> str:
        """Generate a unique ID for a conclusion."""
        hash_input = text.strip().lower()
        return f"CON-{hashlib.sha256(hash_input.encode()).hexdigest()[:8]}"


class CounterargumentFinder:
    """Finds and rates counterarguments for conclusions."""

    # Keywords for different counter types
    COUNTER_SEARCH_TEMPLATES = {
        CounterType.EMPIRICAL: [
            "{topic} contradicting evidence",
            "{topic} study shows different",
            "{topic} research disputes"
        ],
        CounterType.METHODOLOGICAL: [
            "{topic} methodology criticism",
            "{topic} study flaws",
            "{topic} research limitations"
        ],
        CounterType.INTERPRETIVE: [
            "{topic} alternative explanation",
            "{topic} different interpretation",
            "{topic} other perspective"
        ],
        CounterType.CONTEXTUAL: [
            "{topic} limitations scope",
            "{topic} exceptions cases",
            "{topic} when does not apply"
        ],
        CounterType.TEMPORAL: [
            "{topic} outdated research",
            "{topic} recent developments change",
            "{topic} no longer true"
        ],
        CounterType.STAKEHOLDER: [
            "{topic} critics disagree",
            "{topic} expert opposition",
            "{topic} controversy debate"
        ]
    }

    # Alternative interpretation templates
    ALTERNATIVE_TEMPLATES = [
        "Reverse causation: {effect} might cause {cause} instead",
        "Common cause: A third factor might cause both {cause} and {effect}",
        "Spurious correlation: {cause} and {effect} might be unrelated",
        "Moderated relationship: This might only apply under specific conditions",
        "Nonlinear relationship: This might only hold up to a certain threshold"
    ]

    def __init__(self, search_provider=None):
        """
        Initialize the counterargument finder.

        Args:
            search_provider: Optional SearchProviderManager instance
        """
        self.search_provider = search_provider
        self.counterarguments: List[Counterargument] = []
        self.alternatives: List[AlternativeInterpretation] = []

    def find_counterarguments(self, conclusion: Conclusion) -> List[Counterargument]:
        """
        Find counterarguments for a conclusion.

        Args:
            conclusion: Conclusion to find counters for

        Returns:
            List of Counterarguments
        """
        counterarguments = []

        # Extract key topic from conclusion
        topic = self._extract_topic(conclusion.text)

        # Search for each counter type
        for counter_type in CounterType:
            counters = self._search_for_counter_type(conclusion, topic, counter_type)
            counterarguments.extend(counters)

        self.counterarguments.extend(counterarguments)
        return counterarguments

    def generate_alternatives(self, conclusion: Conclusion) -> List[AlternativeInterpretation]:
        """
        Generate alternative interpretations for a conclusion.

        Args:
            conclusion: Conclusion to generate alternatives for

        Returns:
            List of AlternativeInterpretations
        """
        alternatives = []

        # Extract cause/effect if present
        cause, effect = self._extract_causal_elements(conclusion.text)

        for template in self.ALTERNATIVE_TEMPLATES:
            if cause and effect:
                interpretation = template.format(cause=cause, effect=effect)
            else:
                interpretation = template.format(cause="factor A", effect="factor B")
                interpretation = f"For '{conclusion.text[:50]}...': {interpretation}"

            alt = AlternativeInterpretation(
                id=f"ALT-{len(alternatives):03d}",
                conclusion_id=conclusion.id,
                interpretation=interpretation,
                plausibility="medium",  # Would be assessed with more context
                required_evidence="Additional research or analysis needed",
                created_at=datetime.utcnow().isoformat() + "Z"
            )
            alternatives.append(alt)

        self.alternatives.extend(alternatives)
        return alternatives

    def rate_counterargument(self, counterargument: Counterargument) -> CounterStrength:
        """
        Rate the strength of a counterargument.

        Args:
            counterargument: Counterargument to rate

        Returns:
            CounterStrength rating
        """
        score = self._calculate_strength_score(counterargument)
        counterargument.strength_score = score

        if score >= 70:
            strength = CounterStrength.STRONG
        elif score >= 40:
            strength = CounterStrength.MODERATE
        else:
            strength = CounterStrength.WEAK

        counterargument.strength = strength
        return strength

    def _extract_topic(self, text: str) -> str:
        """Extract the main topic from conclusion text."""
        # Simple extraction - first noun phrase or first 5 significant words
        words = text.split()
        significant = [w for w in words if len(w) > 3 and w.lower() not in
                      ['that', 'this', 'which', 'there', 'these', 'those', 'will', 'would', 'could', 'should']]
        return ' '.join(significant[:5])

    def _extract_causal_elements(self, text: str) -> Tuple[Optional[str], Optional[str]]:
        """Extract cause and effect from causal statements."""
        # Patterns for causal relationships
        patterns = [
            r'(.+?)\s+(?:causes?|leads?\s+to|results?\s+in)\s+(.+)',
            r'(.+?)\s+(?:because\s+of|due\s+to)\s+(.+)',
            r'(.+?)\s+(?:increases?|decreases?)\s+(.+)',
        ]

        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1).strip(), match.group(2).strip()

        return None, None

    def _search_for_counter_type(
        self,
        conclusion: Conclusion,
        topic: str,
        counter_type: CounterType
    ) -> List[Counterargument]:
        """Search for counterarguments of a specific type."""
        counters = []
        templates = self.COUNTER_SEARCH_TEMPLATES.get(counter_type, [])

        if self.search_provider:
            for template in templates[:1]:  # Limit searches
                query = template.format(topic=topic)
                try:
                    results = self.search_provider.search(query, max_results=3)
                    for result in results:
                        counter = Counterargument(
                            id=f"CA-{hashlib.sha256(result.url.encode()).hexdigest()[:8]}",
                            conclusion_id=conclusion.id,
                            counter_type=counter_type,
                            strength=CounterStrength.MODERATE,  # Default
                            claim=f"Counter to: {conclusion.text[:50]}...",
                            evidence=result.snippet,
                            sources=[CounterSource(
                                url=result.url,
                                title=result.title,
                                snippet=result.snippet,
                                credibility_score=int(result.relevance_score * 100),
                                relevance_score=result.relevance_score
                            )],
                            created_at=datetime.utcnow().isoformat() + "Z"
                        )
                        self.rate_counterargument(counter)
                        counters.append(counter)
                except Exception as e:
                    print(f"Search error: {e}", file=sys.stderr)

        return counters

    def _calculate_strength_score(self, counterargument: Counterargument) -> int:
        """
        Calculate strength score for a counterargument.

        Factors:
        - Source credibility (30%)
        - Logical coherence (25%)
        - Evidence quality (25%)
        - Relevance (20%)
        """
        if not counterargument.sources:
            return 30  # Base score for unsupported counter

        # Source credibility (30%)
        avg_credibility = sum(s.credibility_score for s in counterargument.sources) / len(counterargument.sources)
        source_score = avg_credibility * 0.30

        # Evidence quality (25%) - based on snippet length and source count
        evidence_score = min(25, len(counterargument.evidence) / 10 + len(counterargument.sources) * 5)

        # Relevance (20%)
        avg_relevance = sum(s.relevance_score for s in counterargument.sources) / len(counterargument.sources)
        relevance_score = avg_relevance * 20

        # Logical coherence (25%) - placeholder, would use NLP in production
        coherence_score = 15  # Default moderate coherence

        total = int(source_score + evidence_score + relevance_score + coherence_score)
        return min(100, max(0, total))


def calculate_robustness(
    conclusion: Conclusion,
    counterarguments: List[Counterargument]
) -> int:
    """
    Calculate robustness score for a conclusion.

    Args:
        conclusion: The conclusion being evaluated
        counterarguments: List of counterarguments against it

    Returns:
        Robustness score 0-100
    """
    base_score = conclusion.confidence

    # Deduct based on counterargument strength
    for counter in counterarguments:
        if counter.conclusion_id == conclusion.id:
            if counter.strength == CounterStrength.STRONG:
                base_score -= 15
            elif counter.strength == CounterStrength.MODERATE:
                base_score -= 8
            else:  # WEAK
                base_score -= 3

    return max(0, min(100, base_score))


def generate_report(
    synthesis_file: str,
    conclusions: List[Conclusion],
    counterarguments: List[Counterargument],
    alternatives: List[AlternativeInterpretation]
) -> DevilsAdvocateReport:
    """Generate a complete devil's advocate report."""
    # Calculate robustness for each conclusion
    robustness_scores = {}
    for conclusion in conclusions:
        relevant_counters = [c for c in counterarguments if c.conclusion_id == conclusion.id]
        robustness_scores[conclusion.id] = calculate_robustness(conclusion, relevant_counters)

    # Calculate overall robustness
    overall_robustness = (
        sum(robustness_scores.values()) / len(robustness_scores)
        if robustness_scores else 0
    )

    # Generate recommendations
    recommendations = []
    for conclusion in conclusions:
        score = robustness_scores.get(conclusion.id, 50)
        if score < 50:
            recommendations.append(f"Address before publishing: {conclusion.text[:50]}...")
        elif score < 70:
            recommendations.append(f"Acknowledge as limitation: {conclusion.text[:50]}...")

    return DevilsAdvocateReport(
        synthesis_file=synthesis_file,
        analysis_date=datetime.utcnow().isoformat() + "Z",
        conclusions=conclusions,
        counterarguments=counterarguments,
        alternatives=alternatives,
        robustness_scores=robustness_scores,
        overall_robustness=int(overall_robustness),
        recommendations=recommendations
    )


def format_report_markdown(report: DevilsAdvocateReport) -> str:
    """Format devil's advocate report as markdown."""
    lines = [
        "## Devil's Advocate Report",
        "",
        "### Research Analyzed",
        f"- **Document**: {report.synthesis_file}",
        f"- **Date**: {report.analysis_date}",
        f"- **Conclusions Examined**: {len(report.conclusions)}",
        "",
        "### Executive Summary",
        f"Overall Research Robustness: {report.overall_robustness}/100",
        "",
        f"- Strong counterarguments: {sum(1 for c in report.counterarguments if c.strength == CounterStrength.STRONG)}",
        f"- Moderate counterarguments: {sum(1 for c in report.counterarguments if c.strength == CounterStrength.MODERATE)}",
        f"- Weak counterarguments: {sum(1 for c in report.counterarguments if c.strength == CounterStrength.WEAK)}",
        "",
        "### Conclusion Analysis",
        ""
    ]

    for conclusion in report.conclusions:
        robustness = report.robustness_scores.get(conclusion.id, 50)
        lines.append(f"#### {conclusion.conclusion_type.title()}: \"{conclusion.text[:80]}...\"")
        lines.append(f"**Robustness Score**: {robustness}/100")
        lines.append("")

        # List counterarguments for this conclusion
        counters = [c for c in report.counterarguments if c.conclusion_id == conclusion.id]
        if counters:
            lines.append("**Counterarguments Found:**")
            for i, counter in enumerate(counters, 1):
                lines.append(f"{i}. **{counter.counter_type.value.title()}** ({counter.strength.value.upper()})")
                lines.append(f"   - Strength Score: {counter.strength_score}/100")
                if counter.sources:
                    lines.append(f"   - Source: {counter.sources[0].title[:50]}...")
                lines.append("")

        # List alternatives
        alts = [a for a in report.alternatives if a.conclusion_id == conclusion.id]
        if alts:
            lines.append("**Alternative Interpretations:**")
            for i, alt in enumerate(alts[:3], 1):  # Limit to 3
                lines.append(f"{i}. {alt.interpretation[:100]}...")
                lines.append(f"   - Plausibility: {alt.plausibility}")
            lines.append("")

        lines.append("---")
        lines.append("")

    # Overall summary
    lines.extend([
        "### Overall Research Robustness",
        "",
        "**Robustness Summary:**",
        "| Conclusion | Counter Strength | Robustness Score |",
        "|------------|-----------------|------------------|"
    ])

    for conclusion in report.conclusions:
        counters = [c for c in report.counterarguments if c.conclusion_id == conclusion.id]
        max_strength = max([c.strength.value for c in counters], default="none")
        robustness = report.robustness_scores.get(conclusion.id, 50)
        lines.append(f"| {conclusion.text[:30]}... | {max_strength.title()} | {robustness}/100 |")

    lines.extend(["", "### Recommendations", ""])
    for i, rec in enumerate(report.recommendations, 1):
        lines.append(f"{i}. {rec}")

    return "\n".join(lines)


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Counterargument Finder for research-loop",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    counterargument-finder.py extract --file synthesis.json
    counterargument-finder.py find --conclusion "AI will replace 50% of jobs"
    counterargument-finder.py rate --counterargument "Studies show automation creates new jobs"
    counterargument-finder.py report --synthesis synthesis.json --output report.md
"""
    )

    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # extract command
    extract_parser = subparsers.add_parser("extract", help="Extract conclusions from synthesis")
    extract_parser.add_argument("--file", required=True, help="Synthesis file to extract from")
    extract_parser.add_argument("--json", action="store_true", help="Output as JSON")

    # find command
    find_parser = subparsers.add_parser("find", help="Find counterarguments for a conclusion")
    find_parser.add_argument("--conclusion", required=True, help="Conclusion text to find counters for")
    find_parser.add_argument("--json", action="store_true", help="Output as JSON")

    # rate command
    rate_parser = subparsers.add_parser("rate", help="Rate counterargument strength")
    rate_parser.add_argument("--counterargument", required=True, help="Counterargument text to rate")
    rate_parser.add_argument("--evidence", default="", help="Supporting evidence")
    rate_parser.add_argument("--json", action="store_true", help="Output as JSON")

    # report command
    report_parser = subparsers.add_parser("report", help="Generate devil's advocate report")
    report_parser.add_argument("--synthesis", required=True, help="Synthesis file to analyze")
    report_parser.add_argument("--output", help="Output file for report")
    report_parser.add_argument("--json", action="store_true", help="Output as JSON")

    args = parser.parse_args()

    if args.command == "extract":
        extractor = ConclusionExtractor()
        file_path = Path(args.file)

        if not file_path.exists():
            print(f"Error: File not found: {args.file}", file=sys.stderr)
            return 1

        conclusions = extractor.extract_from_file(file_path)

        if args.json:
            output = [c.to_dict() for c in conclusions]
            print(json.dumps(output, indent=2))
        else:
            print(f"\nExtracted {len(conclusions)} conclusions from {args.file}")
            print()
            for i, conclusion in enumerate(conclusions, 1):
                print(f"{i}. [{conclusion.conclusion_type}] {conclusion.text[:80]}...")
                print()

        return 0

    elif args.command == "find":
        extractor = ConclusionExtractor()
        finder = CounterargumentFinder()

        # Create conclusion object
        conclusion = Conclusion(
            id=extractor._generate_id(args.conclusion),
            text=args.conclusion,
            conclusion_type="thesis",
            confidence=70,
            source_location="cli",
            extracted_at=datetime.utcnow().isoformat() + "Z"
        )

        counterarguments = finder.find_counterarguments(conclusion)
        alternatives = finder.generate_alternatives(conclusion)

        if args.json:
            output = {
                "conclusion": conclusion.to_dict(),
                "counterarguments": [c.to_dict() for c in counterarguments],
                "alternatives": [a.to_dict() for a in alternatives]
            }
            print(json.dumps(output, indent=2))
        else:
            print(f"\nCounterarguments for: \"{args.conclusion[:60]}...\"")
            print()

            if counterarguments:
                print("Counterarguments:")
                for i, counter in enumerate(counterarguments, 1):
                    print(f"  {i}. [{counter.counter_type.value}] ({counter.strength.value.upper()})")
                    print(f"     Score: {counter.strength_score}/100")
            else:
                print("No counterarguments found (search provider not configured)")

            print()
            print("Alternative Interpretations:")
            for i, alt in enumerate(alternatives[:3], 1):
                print(f"  {i}. {alt.interpretation[:80]}...")

        return 0

    elif args.command == "rate":
        counter = Counterargument(
            id="CA-cli",
            conclusion_id="",
            counter_type=CounterType.EMPIRICAL,
            strength=CounterStrength.MODERATE,
            claim=args.counterargument,
            evidence=args.evidence,
            sources=[],
            created_at=datetime.utcnow().isoformat() + "Z"
        )

        finder = CounterargumentFinder()
        strength = finder.rate_counterargument(counter)

        if args.json:
            print(json.dumps(counter.to_dict(), indent=2))
        else:
            print(f"\nCounterargument Rating:")
            print(f"  Text: \"{args.counterargument[:60]}...\"")
            print(f"  Strength: {strength.value.upper()}")
            print(f"  Score: {counter.strength_score}/100")

        return 0

    elif args.command == "report":
        synthesis_file = Path(args.synthesis)
        if not synthesis_file.exists():
            print(f"Error: File not found: {args.synthesis}", file=sys.stderr)
            return 1

        extractor = ConclusionExtractor()
        finder = CounterargumentFinder()

        conclusions = extractor.extract_from_file(synthesis_file)

        all_counters = []
        all_alternatives = []
        for conclusion in conclusions:
            counters = finder.find_counterarguments(conclusion)
            alternatives = finder.generate_alternatives(conclusion)
            all_counters.extend(counters)
            all_alternatives.extend(alternatives)

        report = generate_report(
            str(synthesis_file),
            conclusions,
            all_counters,
            all_alternatives
        )

        if args.output:
            output_path = Path(args.output)
            if args.json or output_path.suffix == '.json':
                with open(output_path, 'w') as f:
                    json.dump(report.to_dict(), f, indent=2)
            else:
                with open(output_path, 'w') as f:
                    f.write(format_report_markdown(report))
            print(f"Report written to {args.output}")
        elif args.json:
            print(json.dumps(report.to_dict(), indent=2))
        else:
            print(format_report_markdown(report))

        return 0

    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main())
