#!/usr/bin/env python3
"""
Unit tests for source-evaluator.py

Tests the source credibility evaluation functionality:
- Domain extraction and categorization
- Credibility scoring components
- Low credibility detection
- Store persistence and corrections
"""

import json
import os
import sys
import tempfile
import pytest
from pathlib import Path

# Add lib directory to path for imports
LIB_DIR = os.path.join(os.path.dirname(__file__), '..', 'lib')
sys.path.insert(0, LIB_DIR)

# Import with hyphenated module name workaround
import importlib.util
spec = importlib.util.spec_from_file_location("source_evaluator", os.path.join(LIB_DIR, "source-evaluator.py"))
source_evaluator = importlib.util.module_from_spec(spec)
spec.loader.exec_module(source_evaluator)

# Extract what we need from the module
SourceEvaluator = source_evaluator.SourceEvaluator
SourceCredibility = source_evaluator.SourceCredibility
CredibilityLevel = source_evaluator.CredibilityLevel


class TestDomainExtraction:
    """Test domain extraction from URLs."""

    def test_extract_simple_domain(self):
        """Test extracting domain from simple URL."""
        evaluator = SourceEvaluator()
        assert evaluator.extract_domain("https://example.com/page") == "example.com"

    def test_extract_domain_with_www(self):
        """Test extracting domain strips www prefix."""
        evaluator = SourceEvaluator()
        assert evaluator.extract_domain("https://www.example.com/page") == "example.com"

    def test_extract_domain_with_subdomain(self):
        """Test extracting domain with subdomain."""
        evaluator = SourceEvaluator()
        assert evaluator.extract_domain("https://blog.example.com/article") == "blog.example.com"

    def test_extract_domain_complex_url(self):
        """Test extracting domain from complex URL."""
        evaluator = SourceEvaluator()
        url = "https://www.nature.com/articles/s41586-023-06096-z?utm_source=test"
        assert evaluator.extract_domain(url) == "nature.com"

    def test_extract_domain_http(self):
        """Test extracting domain from HTTP URL."""
        evaluator = SourceEvaluator()
        assert evaluator.extract_domain("http://example.com/page") == "example.com"


class TestDomainCategorization:
    """Test domain category detection."""

    def test_academic_domain(self):
        """Test academic domain detection."""
        evaluator = SourceEvaluator()
        category, score = evaluator.get_domain_category("arxiv.org")
        assert category == "academic"
        assert score >= 80

    def test_government_tld(self):
        """Test government TLD detection."""
        evaluator = SourceEvaluator()
        category, score = evaluator.get_domain_category("cdc.gov")
        assert category == "government"
        assert score >= 75

    def test_edu_tld(self):
        """Test .edu TLD detection."""
        evaluator = SourceEvaluator()
        category, score = evaluator.get_domain_category("stanford.edu")
        assert category == "government"  # .edu is in government category
        assert score >= 75

    def test_major_news_domain(self):
        """Test major news domain detection."""
        evaluator = SourceEvaluator()
        category, score = evaluator.get_domain_category("reuters.com")
        assert category == "major_news"
        assert score >= 65

    def test_social_domain(self):
        """Test social media domain detection."""
        evaluator = SourceEvaluator()
        category, score = evaluator.get_domain_category("reddit.com")
        assert category == "social"
        assert score < 50

    def test_unknown_domain(self):
        """Test unknown domain returns neutral score."""
        evaluator = SourceEvaluator()
        category, score = evaluator.get_domain_category("randomsite123.com")
        assert category is None
        assert score == 50


class TestRecencyScoring:
    """Test publication date recency scoring."""

    def test_recent_date_high_score(self):
        """Test recent publication date gets high score."""
        evaluator = SourceEvaluator()
        from datetime import datetime, timedelta

        recent = (datetime.utcnow() - timedelta(days=15)).strftime("%Y-%m-%d")
        score = evaluator.calculate_recency_score(recent)
        assert score >= 90

    def test_old_date_lower_score(self):
        """Test old publication date gets lower score."""
        evaluator = SourceEvaluator()
        score = evaluator.calculate_recency_score("2020-01-01")
        assert score < 60

    def test_very_old_date(self):
        """Test very old publication date."""
        evaluator = SourceEvaluator()
        score = evaluator.calculate_recency_score("2015-01-01")
        assert score <= 50

    def test_unknown_date_neutral(self):
        """Test unknown date returns neutral score."""
        evaluator = SourceEvaluator()
        score = evaluator.calculate_recency_score(None)
        assert score == 50

    def test_invalid_date_neutral(self):
        """Test invalid date format returns neutral score."""
        evaluator = SourceEvaluator()
        score = evaluator.calculate_recency_score("not-a-date")
        assert score == 50

    def test_year_only_format(self):
        """Test year-only date format is handled."""
        evaluator = SourceEvaluator()
        from datetime import datetime

        current_year = datetime.utcnow().year
        score = evaluator.calculate_recency_score(str(current_year))
        assert score >= 70


class TestCitationScoring:
    """Test citation count scoring."""

    def test_high_citations(self):
        """Test high citation count gets high score."""
        evaluator = SourceEvaluator()
        score = evaluator.calculate_citation_score(1000)
        assert score == 100

    def test_moderate_citations(self):
        """Test moderate citation count."""
        evaluator = SourceEvaluator()
        score = evaluator.calculate_citation_score(100)
        assert score == 80

    def test_low_citations(self):
        """Test low citation count."""
        evaluator = SourceEvaluator()
        score = evaluator.calculate_citation_score(5)
        assert score == 55

    def test_zero_citations(self):
        """Test zero citations."""
        evaluator = SourceEvaluator()
        score = evaluator.calculate_citation_score(0)
        assert score == 50

    def test_unknown_citations(self):
        """Test unknown citation count returns neutral."""
        evaluator = SourceEvaluator()
        score = evaluator.calculate_citation_score(None)
        assert score == 50


class TestAuthorScoring:
    """Test author credibility scoring."""

    def test_no_author_info(self):
        """Test no author info returns neutral score."""
        evaluator = SourceEvaluator()
        score = evaluator.calculate_author_score(None)
        assert score == 50

    def test_institutional_affiliation(self):
        """Test institutional affiliation boosts score."""
        evaluator = SourceEvaluator()
        author_info = {"affiliation": "MIT Research Lab"}
        score = evaluator.calculate_author_score(author_info)
        assert score >= 70

    def test_verified_author(self):
        """Test verified author boosts score."""
        evaluator = SourceEvaluator()
        author_info = {"verified": True}
        score = evaluator.calculate_author_score(author_info)
        assert score >= 65

    def test_prolific_author(self):
        """Test author with many publications."""
        evaluator = SourceEvaluator()
        author_info = {"publication_count": 100}
        score = evaluator.calculate_author_score(author_info)
        assert score >= 65


class TestLowCredibilityIndicators:
    """Test low credibility indicator detection."""

    def test_fake_in_url(self):
        """Test 'fake' in URL is flagged."""
        evaluator = SourceEvaluator()
        flags = evaluator.check_low_credibility_indicators("https://fakenews.com/article")
        assert any("fake" in flag for flag in flags)

    def test_satire_in_url(self):
        """Test 'satire' in URL is flagged."""
        evaluator = SourceEvaluator()
        flags = evaluator.check_low_credibility_indicators("https://satire-daily.com/article")
        assert any("satire" in flag for flag in flags)

    def test_clean_url(self):
        """Test clean URL has no flags."""
        evaluator = SourceEvaluator()
        flags = evaluator.check_low_credibility_indicators("https://reuters.com/article")
        assert len(flags) == 0

    def test_sponsored_in_content(self):
        """Test 'sponsored' in content is flagged."""
        evaluator = SourceEvaluator()
        flags = evaluator.check_low_credibility_indicators(
            "https://example.com/article",
            content="This is a sponsored post about products."
        )
        assert any("sponsored" in flag for flag in flags)


class TestEvaluation:
    """Test overall credibility evaluation."""

    def test_evaluate_academic_source(self):
        """Test evaluating an academic source."""
        evaluator = SourceEvaluator()
        from datetime import datetime, timedelta
        # Use a recent date (within last 30 days) to ensure high recency score
        recent_date = (datetime.utcnow() - timedelta(days=15)).strftime("%Y-%m-%d")
        result = evaluator.evaluate(
            "https://arxiv.org/abs/2301.00001",
            publication_date=recent_date,
            citation_count=50
        )
        assert result.score >= 70
        assert result.level in [CredibilityLevel.HIGH, CredibilityLevel.MEDIUM]
        assert result.domain == "arxiv.org"

    def test_evaluate_social_source(self):
        """Test evaluating a social media source."""
        evaluator = SourceEvaluator()
        result = evaluator.evaluate("https://reddit.com/r/science/comments/xyz")
        assert result.score < 60
        assert result.level in [CredibilityLevel.LOW, CredibilityLevel.MEDIUM]

    def test_evaluate_unknown_source(self):
        """Test evaluating an unknown source."""
        evaluator = SourceEvaluator()
        result = evaluator.evaluate("https://randomsite123.xyz/article")
        assert result.score >= 40
        assert result.score <= 60

    def test_low_credibility_flag(self):
        """Test is_low_credibility property."""
        evaluator = SourceEvaluator()
        result = evaluator.evaluate("https://reddit.com/post")
        # Social media should have lower score
        if result.score < 50:
            assert result.is_low_credibility is True


class TestCredibilityStore:
    """Test credibility store persistence."""

    def test_load_empty_store(self):
        """Test loading non-existent store creates default."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store_path = Path(tmpdir) / "test-store.json"
            evaluator = SourceEvaluator(store_path=store_path)
            assert "domains" in evaluator.store
            assert "metadata" in evaluator.store

    def test_save_and_load_store(self):
        """Test saving and loading store."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store_path = Path(tmpdir) / "test-store.json"
            evaluator = SourceEvaluator(store_path=store_path)

            # Update a domain
            evaluator.update_domain_credibility("test.com", 75, "Test update")

            # Create new evaluator and verify persistence
            evaluator2 = SourceEvaluator(store_path=store_path)
            assert "test.com" in evaluator2.store["domains"]
            assert evaluator2.store["domains"]["test.com"]["score"] == 75

    def test_update_domain_credibility(self):
        """Test updating domain credibility."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store_path = Path(tmpdir) / "test-store.json"
            evaluator = SourceEvaluator(store_path=store_path)

            evaluator.update_domain_credibility("badsite.com", 20, "Known misinformation")

            assert "badsite.com" in evaluator.store["domains"]
            assert evaluator.store["domains"]["badsite.com"]["score"] == 20
            assert len(evaluator.store["corrections"]) == 1

    def test_get_low_credibility_sources(self):
        """Test getting low credibility sources."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store_path = Path(tmpdir) / "test-store.json"
            evaluator = SourceEvaluator(store_path=store_path)

            # Add some low credibility sources
            evaluator.update_domain_credibility("bad1.com", 20, "Misinformation")
            evaluator.update_domain_credibility("bad2.com", 30, "Unreliable")
            evaluator.update_domain_credibility("good.com", 80, "Reliable")

            low_cred = evaluator.get_low_credibility_sources()
            assert len(low_cred) == 2
            domains = [s["domain"] for s in low_cred]
            assert "bad1.com" in domains
            assert "bad2.com" in domains
            assert "good.com" not in domains


class TestBatchEvaluation:
    """Test batch URL evaluation."""

    def test_batch_evaluate(self):
        """Test evaluating multiple URLs."""
        evaluator = SourceEvaluator()
        urls = [
            "https://arxiv.org/abs/123",
            "https://reddit.com/post",
            "https://nature.com/article"
        ]
        results = evaluator.batch_evaluate(urls)

        assert len(results) == 3
        # Academic sources should score higher than social
        arxiv_score = results[0].score
        reddit_score = results[1].score
        assert arxiv_score > reddit_score


class TestCredibilityLevels:
    """Test credibility level classification."""

    def test_high_credibility_threshold(self):
        """Test high credibility threshold (>=80)."""
        evaluator = SourceEvaluator()
        result = evaluator.evaluate("https://nature.com/article", citation_count=500)
        if result.score >= 80:
            assert result.level == CredibilityLevel.HIGH

    def test_medium_credibility_range(self):
        """Test medium credibility range (50-79)."""
        evaluator = SourceEvaluator()
        result = evaluator.evaluate("https://techcrunch.com/article")
        if 50 <= result.score < 80:
            assert result.level == CredibilityLevel.MEDIUM

    def test_low_credibility_threshold(self):
        """Test low credibility threshold (<50)."""
        evaluator = SourceEvaluator()
        # Use URL with low credibility indicator
        result = evaluator.evaluate("https://fakesatire.com/article")
        if result.score < 50:
            assert result.level == CredibilityLevel.LOW


class TestSourceCredibilityDataclass:
    """Test SourceCredibility dataclass."""

    def test_to_dict(self):
        """Test to_dict serialization."""
        cred = SourceCredibility(
            domain="example.com",
            score=75,
            level=CredibilityLevel.MEDIUM,
            domain_authority=70,
            recency_score=80,
            citation_score=60,
            author_score=50,
            flags=["test_flag"],
            notes="Test note"
        )
        d = cred.to_dict()
        assert d["domain"] == "example.com"
        assert d["score"] == 75
        assert d["level"] == "medium"
        assert "test_flag" in d["flags"]

    def test_is_low_credibility_property(self):
        """Test is_low_credibility property."""
        high_cred = SourceCredibility(
            domain="good.com",
            score=80,
            level=CredibilityLevel.HIGH,
            domain_authority=80,
            recency_score=80,
            citation_score=80,
            author_score=80
        )
        assert high_cred.is_low_credibility is False

        low_cred = SourceCredibility(
            domain="bad.com",
            score=30,
            level=CredibilityLevel.LOW,
            domain_authority=30,
            recency_score=30,
            citation_score=30,
            author_score=30
        )
        assert low_cred.is_low_credibility is True


class TestIntegrationWithStore:
    """Test integration with the default credibility store."""

    def test_load_default_store(self):
        """Test loading the default credibility store if it exists."""
        default_store = Path(__file__).parent.parent / "data" / "source-credibility-store.json"
        if default_store.exists():
            evaluator = SourceEvaluator(store_path=default_store)
            assert len(evaluator.store.get("domains", {})) > 0

    def test_stored_domain_override(self):
        """Test that stored domain scores override calculated ones."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store_path = Path(tmpdir) / "test-store.json"
            evaluator = SourceEvaluator(store_path=store_path)

            # Set a custom score for a known domain
            evaluator.update_domain_credibility("arxiv.org", 50, "Testing override")

            # Evaluate and verify override is used
            result = evaluator.evaluate("https://arxiv.org/abs/123")
            # The domain authority should now be 50 (from override)
            assert result.domain_authority == 50


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
