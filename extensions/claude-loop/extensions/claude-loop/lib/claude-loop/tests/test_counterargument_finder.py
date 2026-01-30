#!/usr/bin/env python3
"""
Tests for counterargument-finder.py module.

Tests cover:
- Conclusion extraction from text and files
- Counterargument generation (with and without search provider)
- Alternative interpretation generation
- Strength rating for counterarguments
- Robustness score calculation
- Report generation
"""

import json
import pytest
import sys
import tempfile
from pathlib import Path
from unittest.mock import Mock, MagicMock

# Add lib to path
sys.path.insert(0, str(Path(__file__).parent.parent / "lib"))

# Import using importlib for hyphenated module name
import importlib.util
spec = importlib.util.spec_from_file_location(
    "counterargument_finder",
    Path(__file__).parent.parent / "lib" / "counterargument-finder.py"
)
counterargument_finder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(counterargument_finder)

# Import classes
ConclusionExtractor = counterargument_finder.ConclusionExtractor
CounterargumentFinder = counterargument_finder.CounterargumentFinder
Conclusion = counterargument_finder.Conclusion
Counterargument = counterargument_finder.Counterargument
AlternativeInterpretation = counterargument_finder.AlternativeInterpretation
CounterSource = counterargument_finder.CounterSource
CounterStrength = counterargument_finder.CounterStrength
CounterType = counterargument_finder.CounterType
calculate_robustness = counterargument_finder.calculate_robustness
generate_report = counterargument_finder.generate_report
format_report_markdown = counterargument_finder.format_report_markdown


class TestConclusionExtractor:
    """Test conclusion extraction functionality."""

    def test_extract_thesis_statements(self):
        """Test extracting thesis-type conclusions."""
        text = """
        The research concludes that AI coding assistants improve developer productivity.
        Evidence suggests that developers using AI tools complete tasks 30% faster.
        """

        extractor = ConclusionExtractor()
        conclusions = extractor.extract_from_text(text)

        assert len(conclusions) >= 1
        assert any("AI" in c.text or "developer" in c.text for c in conclusions)
        assert any(c.conclusion_type == "thesis" for c in conclusions)

    def test_extract_recommendations(self):
        """Test extracting recommendation-type conclusions."""
        text = """
        We recommend implementing automated testing for all new features.
        Teams should adopt pair programming to reduce bugs.
        """

        extractor = ConclusionExtractor()
        conclusions = extractor.extract_from_text(text)

        assert len(conclusions) >= 2
        assert any("automated testing" in c.text for c in conclusions)
        assert any(c.conclusion_type == "recommendation" for c in conclusions)

    def test_extract_predictions(self):
        """Test extracting prediction-type conclusions."""
        text = """
        AI will replace 50% of software testing jobs by 2030.
        We predict that remote work will become the default.
        """

        extractor = ConclusionExtractor()
        conclusions = extractor.extract_from_text(text)

        assert len(conclusions) >= 2
        assert any("2030" in c.text or "50%" in c.text for c in conclusions)
        assert any(c.conclusion_type == "prediction" for c in conclusions)

    def test_conclusion_deduplication(self):
        """Test that duplicate conclusions are not extracted."""
        text = """
        The study shows that exercise improves health.
        The study shows that exercise improves health.
        """

        extractor = ConclusionExtractor()
        conclusions = extractor.extract_from_text(text)

        # Should only extract once
        assert len(conclusions) == 1

    def test_minimum_length_filter(self):
        """Test that very short conclusions are filtered out."""
        text = """
        We conclude that yes.
        The evidence shows it works.
        We recommend implementing comprehensive testing frameworks.
        """

        extractor = ConclusionExtractor()
        conclusions = extractor.extract_from_text(text)

        # Should only extract the longer conclusion
        assert all(len(c.text) >= 20 for c in conclusions)

    def test_extract_from_json_file(self):
        """Test extracting conclusions from JSON synthesis file."""
        synthesis_data = {
            "synthesis": "We conclude that AI tools improve productivity",
            "conclusions": [
                "Machine learning models require extensive training data",
                "Deep learning shows promise for image recognition"
            ],
            "findings": [
                "Research demonstrates effectiveness of neural networks"
            ]
        }

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(synthesis_data, f)
            temp_path = Path(f.name)

        try:
            extractor = ConclusionExtractor()
            conclusions = extractor.extract_from_file(temp_path)

            assert len(conclusions) >= 3
            assert any("AI tools" in c.text for c in conclusions)
        finally:
            temp_path.unlink()

    def test_conclusion_id_generation(self):
        """Test that conclusion IDs are generated consistently."""
        extractor = ConclusionExtractor()

        text1 = "AI will transform software development"
        text2 = "AI will transform software development"
        text3 = "Machine learning is powerful"

        id1 = extractor._generate_id(text1)
        id2 = extractor._generate_id(text2)
        id3 = extractor._generate_id(text3)

        assert id1 == id2  # Same text, same ID
        assert id1 != id3  # Different text, different ID
        assert id1.startswith("CON-")


class TestCounterargumentFinder:
    """Test counterargument finding functionality."""

    def test_extract_topic_from_conclusion(self):
        """Test extracting main topic from conclusion."""
        finder = CounterargumentFinder()

        text = "AI coding assistants will replace human developers"
        topic = finder._extract_topic(text)

        assert "coding" in topic.lower() or "assistants" in topic.lower()

    def test_extract_causal_elements(self):
        """Test extracting cause and effect from causal statements."""
        finder = CounterargumentFinder()

        text = "Automation causes job displacement"
        cause, effect = finder._extract_causal_elements(text)

        assert cause is not None
        assert effect is not None
        assert "automation" in cause.lower()
        assert "job" in effect.lower() or "displacement" in effect.lower()

    def test_generate_alternatives_causal(self):
        """Test generating alternative interpretations for causal conclusions."""
        conclusion = Conclusion(
            id="CON-test",
            text="AI automation causes job losses in manufacturing",
            conclusion_type="thesis",
            confidence=80
        )

        finder = CounterargumentFinder()
        alternatives = finder.generate_alternatives(conclusion)

        assert len(alternatives) > 0
        assert any("reverse" in alt.interpretation.lower() for alt in alternatives)

    def test_generate_alternatives_non_causal(self):
        """Test generating alternatives for non-causal conclusions."""
        conclusion = Conclusion(
            id="CON-test",
            text="Machine learning is transforming healthcare",
            conclusion_type="thesis",
            confidence=75
        )

        finder = CounterargumentFinder()
        alternatives = finder.generate_alternatives(conclusion)

        assert len(alternatives) > 0
        # Should have default alternatives even without causal structure
        assert all(alt.conclusion_id == "CON-test" for alt in alternatives)

    def test_rate_counterargument_strong(self):
        """Test rating a strong counterargument."""
        counter = Counterargument(
            id="CA-test",
            conclusion_id="CON-test",
            counter_type=CounterType.EMPIRICAL,
            strength=CounterStrength.MODERATE,  # Will be updated
            claim="Study shows opposite result",
            evidence="Large-scale peer-reviewed meta-analysis with 10,000 participants",
            sources=[
                CounterSource(
                    url="https://example.com/study",
                    title="Meta-analysis on AI impact",
                    snippet="Comprehensive study shows...",
                    credibility_score=90,
                    relevance_score=0.95
                )
            ]
        )

        finder = CounterargumentFinder()
        strength = finder.rate_counterargument(counter)

        assert strength == CounterStrength.STRONG
        assert counter.strength_score >= 70

    def test_rate_counterargument_weak(self):
        """Test rating a weak counterargument."""
        counter = Counterargument(
            id="CA-test",
            conclusion_id="CON-test",
            counter_type=CounterType.STAKEHOLDER,
            strength=CounterStrength.MODERATE,
            claim="Some people disagree",
            evidence="Blog post opinion",
            sources=[
                CounterSource(
                    url="https://example.com/blog",
                    title="My opinion on AI",
                    snippet="I think...",
                    credibility_score=20,
                    relevance_score=0.3
                )
            ]
        )

        finder = CounterargumentFinder()
        strength = finder.rate_counterargument(counter)

        assert strength == CounterStrength.WEAK
        assert counter.strength_score < 40

    def test_find_counterarguments_no_search(self):
        """Test finding counterarguments without search provider."""
        conclusion = Conclusion(
            id="CON-test",
            text="AI will replace all programmers by 2030",
            conclusion_type="prediction",
            confidence=70
        )

        finder = CounterargumentFinder(search_provider=None)
        counterarguments = finder.find_counterarguments(conclusion)

        # Should return empty list without search provider
        assert len(counterarguments) == 0

    def test_find_counterarguments_with_mock_search(self):
        """Test finding counterarguments with mocked search provider."""
        conclusion = Conclusion(
            id="CON-test",
            text="AI coding tools improve productivity by 50%",
            conclusion_type="thesis",
            confidence=80
        )

        # Mock search provider
        mock_search = Mock()
        mock_result = Mock()
        mock_result.url = "https://example.com/counter"
        mock_result.title = "Study shows mixed productivity results"
        mock_result.snippet = "AI tools show variable impact on productivity"
        mock_result.relevance_score = 0.8
        mock_search.search = Mock(return_value=[mock_result])

        finder = CounterargumentFinder(search_provider=mock_search)
        counterarguments = finder.find_counterarguments(conclusion)

        assert len(counterarguments) > 0
        assert any(counter.conclusion_id == conclusion.id for counter in counterarguments)


class TestRobustnessCalculation:
    """Test robustness score calculation."""

    def test_robustness_no_counterarguments(self):
        """Test robustness when there are no counterarguments."""
        conclusion = Conclusion(
            id="CON-test",
            text="Test conclusion",
            conclusion_type="thesis",
            confidence=85
        )

        robustness = calculate_robustness(conclusion, [])
        assert robustness == 85  # Same as original confidence

    def test_robustness_with_weak_counter(self):
        """Test robustness with weak counterarguments."""
        conclusion = Conclusion(
            id="CON-test",
            text="Test conclusion",
            conclusion_type="thesis",
            confidence=80
        )

        weak_counter = Counterargument(
            id="CA-1",
            conclusion_id="CON-test",
            counter_type=CounterType.STAKEHOLDER,
            strength=CounterStrength.WEAK,
            claim="Weak counter",
            evidence="Minimal evidence"
        )

        robustness = calculate_robustness(conclusion, [weak_counter])
        assert robustness == 77  # 80 - 3

    def test_robustness_with_moderate_counter(self):
        """Test robustness with moderate counterarguments."""
        conclusion = Conclusion(
            id="CON-test",
            text="Test conclusion",
            conclusion_type="thesis",
            confidence=80
        )

        moderate_counter = Counterargument(
            id="CA-1",
            conclusion_id="CON-test",
            counter_type=CounterType.METHODOLOGICAL,
            strength=CounterStrength.MODERATE,
            claim="Moderate counter",
            evidence="Some concerns"
        )

        robustness = calculate_robustness(conclusion, [moderate_counter])
        assert robustness == 72  # 80 - 8

    def test_robustness_with_strong_counter(self):
        """Test robustness with strong counterarguments."""
        conclusion = Conclusion(
            id="CON-test",
            text="Test conclusion",
            conclusion_type="thesis",
            confidence=80
        )

        strong_counter = Counterargument(
            id="CA-1",
            conclusion_id="CON-test",
            counter_type=CounterType.EMPIRICAL,
            strength=CounterStrength.STRONG,
            claim="Strong counter",
            evidence="Contradictory study"
        )

        robustness = calculate_robustness(conclusion, [strong_counter])
        assert robustness == 65  # 80 - 15

    def test_robustness_with_multiple_counters(self):
        """Test robustness with multiple counterarguments."""
        conclusion = Conclusion(
            id="CON-test",
            text="Test conclusion",
            conclusion_type="thesis",
            confidence=90
        )

        counters = [
            Counterargument(
                id="CA-1",
                conclusion_id="CON-test",
                counter_type=CounterType.EMPIRICAL,
                strength=CounterStrength.STRONG,
                claim="Strong counter",
                evidence="Evidence"
            ),
            Counterargument(
                id="CA-2",
                conclusion_id="CON-test",
                counter_type=CounterType.METHODOLOGICAL,
                strength=CounterStrength.MODERATE,
                claim="Moderate counter",
                evidence="Evidence"
            ),
            Counterargument(
                id="CA-3",
                conclusion_id="CON-test",
                counter_type=CounterType.STAKEHOLDER,
                strength=CounterStrength.WEAK,
                claim="Weak counter",
                evidence="Evidence"
            )
        ]

        robustness = calculate_robustness(conclusion, counters)
        assert robustness == 64  # 90 - 15 - 8 - 3

    def test_robustness_floor_at_zero(self):
        """Test that robustness doesn't go below 0."""
        conclusion = Conclusion(
            id="CON-test",
            text="Test conclusion",
            conclusion_type="thesis",
            confidence=30
        )

        strong_counters = [
            Counterargument(
                id=f"CA-{i}",
                conclusion_id="CON-test",
                counter_type=CounterType.EMPIRICAL,
                strength=CounterStrength.STRONG,
                claim="Strong counter",
                evidence="Evidence"
            )
            for i in range(5)
        ]

        robustness = calculate_robustness(conclusion, strong_counters)
        assert robustness == 0  # Floor at 0, not negative


class TestReportGeneration:
    """Test devil's advocate report generation."""

    def test_generate_report_basic(self):
        """Test basic report generation."""
        conclusions = [
            Conclusion(
                id="CON-1",
                text="AI will transform software development",
                conclusion_type="thesis",
                confidence=85
            )
        ]

        counterarguments = [
            Counterargument(
                id="CA-1",
                conclusion_id="CON-1",
                counter_type=CounterType.EMPIRICAL,
                strength=CounterStrength.MODERATE,
                claim="Mixed evidence",
                evidence="Some studies show limited impact"
            )
        ]

        alternatives = [
            AlternativeInterpretation(
                id="ALT-1",
                conclusion_id="CON-1",
                interpretation="AI augments, not replaces developers",
                plausibility="high",
                required_evidence="Longitudinal studies"
            )
        ]

        report = generate_report(
            "test-synthesis.json",
            conclusions,
            counterarguments,
            alternatives
        )

        assert report.synthesis_file == "test-synthesis.json"
        assert len(report.conclusions) == 1
        assert len(report.counterarguments) == 1
        assert len(report.alternatives) == 1
        assert "CON-1" in report.robustness_scores
        assert report.robustness_scores["CON-1"] == 77  # 85 - 8

    def test_generate_report_recommendations(self):
        """Test that report generates appropriate recommendations."""
        conclusions = [
            Conclusion(
                id="CON-1",
                text="Very robust conclusion",
                conclusion_type="thesis",
                confidence=95
            ),
            Conclusion(
                id="CON-2",
                text="Weak conclusion",
                conclusion_type="thesis",
                confidence=60
            ),
            Conclusion(
                id="CON-3",
                text="Very weak conclusion",
                conclusion_type="thesis",
                confidence=40
            )
        ]

        report = generate_report(
            "test.json",
            conclusions,
            [],
            []
        )

        # Should recommend addressing weak conclusions
        assert len(report.recommendations) >= 1
        assert any("CON-3" in rec or "Very weak" in rec for rec in report.recommendations)

    def test_format_report_markdown(self):
        """Test formatting report as markdown."""
        conclusions = [
            Conclusion(
                id="CON-1",
                text="Test conclusion for markdown formatting",
                conclusion_type="thesis",
                confidence=80
            )
        ]

        counterarguments = [
            Counterargument(
                id="CA-1",
                conclusion_id="CON-1",
                counter_type=CounterType.EMPIRICAL,
                strength=CounterStrength.STRONG,
                claim="Counter claim",
                evidence="Counter evidence",
                sources=[
                    CounterSource(
                        url="https://example.com",
                        title="Example source",
                        snippet="Snippet text",
                        credibility_score=80,
                        relevance_score=0.9
                    )
                ]
            )
        ]

        alternatives = [
            AlternativeInterpretation(
                id="ALT-1",
                conclusion_id="CON-1",
                interpretation="Alternative interpretation text",
                plausibility="medium",
                required_evidence="More research needed"
            )
        ]

        report = generate_report(
            "test.json",
            conclusions,
            counterarguments,
            alternatives
        )

        markdown = format_report_markdown(report)

        assert "## Devil's Advocate Report" in markdown
        assert "### Research Analyzed" in markdown
        assert "### Executive Summary" in markdown
        assert "### Conclusion Analysis" in markdown
        assert "**Counterarguments Found:**" in markdown
        assert "**Alternative Interpretations:**" in markdown
        assert "### Overall Research Robustness" in markdown
        assert "### Recommendations" in markdown


class TestEndToEnd:
    """End-to-end integration tests."""

    def test_full_workflow_extract_to_report(self):
        """Test complete workflow from extraction to report generation."""
        # Create test synthesis file
        synthesis_text = """
        This research concludes that remote work improves employee satisfaction.
        Evidence shows that productivity remains stable with remote work arrangements.
        We recommend companies adopt flexible work policies.
        """

        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write(synthesis_text)
            temp_path = Path(f.name)

        try:
            # Extract conclusions
            extractor = ConclusionExtractor()
            conclusions = extractor.extract_from_file(temp_path)

            assert len(conclusions) >= 2

            # Generate alternatives
            finder = CounterargumentFinder()
            all_alternatives = []
            for conclusion in conclusions:
                alts = finder.generate_alternatives(conclusion)
                all_alternatives.extend(alts)

            assert len(all_alternatives) > 0

            # Generate report (without search, so no counterarguments)
            report = generate_report(
                str(temp_path),
                conclusions,
                [],
                all_alternatives
            )

            assert report.overall_robustness > 0
            assert len(report.conclusions) == len(conclusions)

            # Format as markdown
            markdown = format_report_markdown(report)
            assert len(markdown) > 0
            assert "Devil's Advocate Report" in markdown

        finally:
            temp_path.unlink()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
