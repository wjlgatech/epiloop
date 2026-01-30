#!/usr/bin/env python3
"""
Unit tests for claim-verifier.py

Tests the claim verification functionality:
- Claim extraction from text
- Claim type detection
- Verification status and confidence
- Batch verification
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
spec = importlib.util.spec_from_file_location("claim_verifier", os.path.join(LIB_DIR, "claim-verifier.py"))
claim_verifier = importlib.util.module_from_spec(spec)
spec.loader.exec_module(claim_verifier)

# Extract what we need from the module
ClaimExtractor = claim_verifier.ClaimExtractor
ClaimVerifier = claim_verifier.ClaimVerifier
Claim = claim_verifier.Claim
ClaimType = claim_verifier.ClaimType
VerificationStatus = claim_verifier.VerificationStatus
VerificationResult = claim_verifier.VerificationResult
VerificationSource = claim_verifier.VerificationSource
format_verification_report = claim_verifier.format_verification_report


class TestClaimExtraction:
    """Test claim extraction from text."""

    def test_extract_statistical_claim(self):
        """Test extracting statistical claims."""
        extractor = ClaimExtractor()
        text = "The market grew by 25% in 2024. Many companies reported increased revenue."
        claims = extractor.extract_from_text(text)

        # Should find the statistical claim
        statistical_claims = [c for c in claims if c.claim_type == ClaimType.STATISTICAL]
        assert len(statistical_claims) >= 1

    def test_extract_causal_claim(self):
        """Test extracting causal claims."""
        extractor = ClaimExtractor()
        text = "Climate change causes rising sea levels. This leads to coastal erosion."
        claims = extractor.extract_from_text(text)

        causal_claims = [c for c in claims if c.claim_type == ClaimType.CAUSAL]
        assert len(causal_claims) >= 1

    def test_extract_temporal_claim(self):
        """Test extracting temporal claims."""
        extractor = ClaimExtractor()
        text = "The company was founded in 1995. They launched their first product in 2001."
        claims = extractor.extract_from_text(text)

        temporal_claims = [c for c in claims if c.claim_type == ClaimType.TEMPORAL]
        assert len(temporal_claims) >= 1

    def test_extract_attributive_claim(self):
        """Test extracting attributive claims."""
        extractor = ClaimExtractor()
        text = "According to the CEO, profits will double next year. John Smith stated the results exceeded expectations."
        claims = extractor.extract_from_text(text)

        attributive_claims = [c for c in claims if c.claim_type == ClaimType.ATTRIBUTIVE]
        assert len(attributive_claims) >= 1

    def test_extract_comparative_claim(self):
        """Test extracting comparative claims."""
        extractor = ClaimExtractor()
        text = "This method is faster than traditional approaches. The new system outperforms the old one."
        claims = extractor.extract_from_text(text)

        comparative_claims = [c for c in claims if c.claim_type == ClaimType.COMPARATIVE]
        assert len(comparative_claims) >= 1

    def test_skip_opinion_statements(self):
        """Test that opinion statements are skipped."""
        extractor = ClaimExtractor()
        text = "I believe the market will grow. I think this might work. This seems possible."
        claims = extractor.extract_from_text(text)

        # Should extract fewer claims from opinion text
        assert len(claims) < 3

    def test_extract_from_file(self):
        """Test extracting claims from a file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir) / "test.txt"
            file_path.write_text("Revenue increased by 50% in 2024. The study shows a correlation.")

            extractor = ClaimExtractor()
            claims = extractor.extract_from_file(file_path)

            assert len(claims) >= 1

    def test_extract_from_json_file(self):
        """Test extracting claims from a JSON file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir) / "findings.json"
            data = {
                "findings": [
                    "The market grew by 30% last year.",
                    "AI adoption causes productivity improvements."
                ]
            }
            file_path.write_text(json.dumps(data))

            extractor = ClaimExtractor()
            claims = extractor.extract_from_file(file_path)

            assert len(claims) >= 1


class TestClaimTypeDetection:
    """Test claim type detection."""

    def test_detect_statistical_type(self):
        """Test detecting statistical claim type."""
        extractor = ClaimExtractor()
        claim_type = extractor._detect_claim_type("The company reported a 25% increase in revenue.")
        assert claim_type == ClaimType.STATISTICAL

    def test_detect_causal_type(self):
        """Test detecting causal claim type."""
        extractor = ClaimExtractor()
        claim_type = extractor._detect_claim_type("Poor diet causes health problems.")
        assert claim_type == ClaimType.CAUSAL

    def test_detect_temporal_type(self):
        """Test detecting temporal claim type."""
        extractor = ClaimExtractor()
        claim_type = extractor._detect_claim_type("The event occurred in 2020.")
        assert claim_type == ClaimType.TEMPORAL

    def test_detect_attributive_type(self):
        """Test detecting attributive claim type."""
        extractor = ClaimExtractor()
        claim_type = extractor._detect_claim_type("According to experts, this is correct.")
        assert claim_type == ClaimType.ATTRIBUTIVE

    def test_detect_comparative_type(self):
        """Test detecting comparative claim type."""
        extractor = ClaimExtractor()
        claim_type = extractor._detect_claim_type("This approach is better than the alternative.")
        assert claim_type == ClaimType.COMPARATIVE

    def test_detect_general_type(self):
        """Test detecting general factual claim type."""
        extractor = ClaimExtractor()
        claim_type = extractor._detect_claim_type("The Earth is round and orbits the sun.")
        assert claim_type == ClaimType.GENERAL


class TestClaimImportance:
    """Test claim importance assessment."""

    def test_statistical_claims_high_importance(self):
        """Test that statistical claims get high importance."""
        extractor = ClaimExtractor()
        text = "Revenue grew by 50%."
        claims = extractor.extract_from_text(text)

        statistical = [c for c in claims if c.claim_type == ClaimType.STATISTICAL]
        if statistical:
            assert statistical[0].importance == "high"

    def test_causal_claims_high_importance(self):
        """Test that causal claims get high importance."""
        extractor = ClaimExtractor()
        text = "Smoking causes cancer."
        claims = extractor.extract_from_text(text)

        causal = [c for c in claims if c.claim_type == ClaimType.CAUSAL]
        if causal:
            assert causal[0].importance == "high"


class TestClaimGeneration:
    """Test claim ID generation."""

    def test_unique_claim_ids(self):
        """Test that different claims get unique IDs."""
        extractor = ClaimExtractor()
        id1 = extractor._generate_claim_id("Claim one about something.")
        id2 = extractor._generate_claim_id("Claim two about something else.")
        assert id1 != id2

    def test_same_claim_same_id(self):
        """Test that same claim text gets same ID."""
        extractor = ClaimExtractor()
        id1 = extractor._generate_claim_id("This is the same claim.")
        id2 = extractor._generate_claim_id("This is the same claim.")
        assert id1 == id2

    def test_id_format(self):
        """Test that IDs have expected format."""
        extractor = ClaimExtractor()
        claim_id = extractor._generate_claim_id("Test claim")
        assert claim_id.startswith("CLM-")


class TestVerificationResult:
    """Test VerificationResult dataclass."""

    def test_is_verified_property(self):
        """Test is_verified property."""
        verified_result = VerificationResult(
            claim_id="CLM-001",
            claim_text="Test claim",
            status=VerificationStatus.VERIFIED,
            confidence=95,
            sources=[],
            supporting_count=2,
            contradicting_count=0
        )
        assert verified_result.is_verified is True

        unverified_result = VerificationResult(
            claim_id="CLM-002",
            claim_text="Test claim",
            status=VerificationStatus.UNVERIFIED,
            confidence=20,
            sources=[],
            supporting_count=0,
            contradicting_count=0
        )
        assert unverified_result.is_verified is False

    def test_needs_attention_property(self):
        """Test needs_attention property."""
        disputed_result = VerificationResult(
            claim_id="CLM-001",
            claim_text="Test claim",
            status=VerificationStatus.DISPUTED,
            confidence=40,
            sources=[],
            supporting_count=1,
            contradicting_count=1
        )
        assert disputed_result.needs_attention is True

        verified_result = VerificationResult(
            claim_id="CLM-002",
            claim_text="Test claim",
            status=VerificationStatus.VERIFIED,
            confidence=95,
            sources=[],
            supporting_count=2,
            contradicting_count=0
        )
        assert verified_result.needs_attention is False

    def test_to_dict(self):
        """Test to_dict serialization."""
        result = VerificationResult(
            claim_id="CLM-001",
            claim_text="Test claim",
            status=VerificationStatus.LIKELY,
            confidence=75,
            sources=[],
            supporting_count=1,
            contradicting_count=0
        )
        d = result.to_dict()
        assert d["claim_id"] == "CLM-001"
        assert d["status"] == "likely"
        assert d["confidence"] == 75


class TestClaimVerifier:
    """Test ClaimVerifier class."""

    def test_verify_claim_no_sources(self):
        """Test verifying a claim without search provider."""
        verifier = ClaimVerifier()
        claim = Claim(
            id="CLM-001",
            text="The market grew by 25%",
            claim_type=ClaimType.STATISTICAL,
            source_text="The market grew by 25%",
            source_location="test",
            importance="high"
        )

        result = verifier.verify(claim)

        # Without search provider, should return low confidence
        assert result.status in [VerificationStatus.UNVERIFIED, VerificationStatus.UNCERTAIN]
        assert result.confidence <= 50

    def test_verify_batch(self):
        """Test batch verification."""
        verifier = ClaimVerifier()
        claims = [
            Claim(
                id="CLM-001",
                text="Claim one",
                claim_type=ClaimType.GENERAL,
                source_text="",
                source_location="test",
                importance="medium"
            ),
            Claim(
                id="CLM-002",
                text="Claim two",
                claim_type=ClaimType.GENERAL,
                source_text="",
                source_location="test",
                importance="medium"
            )
        ]

        results = verifier.verify_batch(claims)

        assert len(results) == 2
        assert all(isinstance(r, VerificationResult) for r in results)

    def test_get_verification_summary(self):
        """Test getting verification summary."""
        verifier = ClaimVerifier()
        claim = Claim(
            id="CLM-001",
            text="Test claim",
            claim_type=ClaimType.GENERAL,
            source_text="",
            source_location="test",
            importance="medium"
        )

        verifier.verify(claim)
        summary = verifier.get_verification_summary()

        assert "total" in summary
        assert "by_status" in summary
        assert summary["total"] == 1


class TestConfidenceCalculation:
    """Test confidence calculation logic."""

    def test_confidence_with_supporting_sources(self):
        """Test confidence increases with supporting sources."""
        verifier = ClaimVerifier()

        # Simulate sources
        supporting = [
            VerificationSource(
                url="https://example.com/1",
                title="Source 1",
                snippet="Supporting evidence",
                credibility_score=80,
                supports_claim=True,
                relevance_score=0.9
            ),
            VerificationSource(
                url="https://example.com/2",
                title="Source 2",
                snippet="More evidence",
                credibility_score=75,
                supports_claim=True,
                relevance_score=0.8
            )
        ]

        confidence, status = verifier._calculate_confidence(supporting, [], "high")

        assert confidence >= 70
        assert status in [VerificationStatus.VERIFIED, VerificationStatus.LIKELY]

    def test_confidence_with_contradicting_sources(self):
        """Test confidence decreases with contradicting sources."""
        verifier = ClaimVerifier()

        contradicting = [
            VerificationSource(
                url="https://example.com/1",
                title="Counter Source",
                snippet="Contradicting evidence",
                credibility_score=80,
                supports_claim=False,
                relevance_score=0.9
            )
        ]

        confidence, status = verifier._calculate_confidence([], contradicting, "high")

        assert confidence < 50
        assert status == VerificationStatus.DISPUTED

    def test_confidence_with_mixed_sources(self):
        """Test confidence with mixed supporting and contradicting sources."""
        verifier = ClaimVerifier()

        supporting = [
            VerificationSource(
                url="https://example.com/1",
                title="Source 1",
                snippet="Supporting",
                credibility_score=70,
                supports_claim=True,
                relevance_score=0.8
            )
        ]

        contradicting = [
            VerificationSource(
                url="https://example.com/2",
                title="Source 2",
                snippet="Contradicting",
                credibility_score=70,
                supports_claim=False,
                relevance_score=0.8
            )
        ]

        confidence, status = verifier._calculate_confidence(supporting, contradicting, "medium")

        assert status == VerificationStatus.DISPUTED
        assert 30 <= confidence <= 60


class TestSearchQueryGeneration:
    """Test search query generation."""

    def test_generate_queries_statistical(self):
        """Test query generation for statistical claims."""
        verifier = ClaimVerifier()
        claim = Claim(
            id="CLM-001",
            text="The market grew by 25%",
            claim_type=ClaimType.STATISTICAL,
            source_text="",
            source_location="test",
            importance="high"
        )

        queries = verifier._generate_search_queries(claim)

        assert len(queries) >= 2
        assert any("statistic" in q.lower() or "data" in q.lower() for q in queries)

    def test_generate_queries_causal(self):
        """Test query generation for causal claims."""
        verifier = ClaimVerifier()
        claim = Claim(
            id="CLM-001",
            text="Smoking causes cancer",
            claim_type=ClaimType.CAUSAL,
            source_text="",
            source_location="test",
            importance="high"
        )

        queries = verifier._generate_search_queries(claim)

        assert len(queries) >= 2
        assert any("study" in q.lower() or "research" in q.lower() or "evidence" in q.lower() for q in queries)


class TestReportFormatting:
    """Test verification report formatting."""

    def test_format_report_basic(self):
        """Test basic report formatting."""
        claims = [
            Claim(
                id="CLM-001",
                text="Test claim one",
                claim_type=ClaimType.GENERAL,
                source_text="",
                source_location="test.txt",
                importance="medium"
            )
        ]

        results = [
            VerificationResult(
                claim_id="CLM-001",
                claim_text="Test claim one",
                status=VerificationStatus.VERIFIED,
                confidence=90,
                sources=[],
                supporting_count=2,
                contradicting_count=0
            )
        ]

        report = format_verification_report(claims, results, "test.txt")

        assert "## Fact Check Report" in report
        assert "test.txt" in report
        assert "Claims Found" in report

    def test_format_report_with_flagged(self):
        """Test report formatting with flagged claims."""
        claims = [
            Claim(
                id="CLM-001",
                text="Unverified claim",
                claim_type=ClaimType.GENERAL,
                source_text="",
                source_location="test.txt",
                importance="high"
            )
        ]

        results = [
            VerificationResult(
                claim_id="CLM-001",
                claim_text="Unverified claim",
                status=VerificationStatus.UNVERIFIED,
                confidence=20,
                sources=[],
                supporting_count=0,
                contradicting_count=0
            )
        ]

        report = format_verification_report(claims, results, "test.txt")

        assert "Flagged Claims" in report or "Unverified" in report


class TestClaimDataclass:
    """Test Claim dataclass."""

    def test_claim_to_dict(self):
        """Test Claim to_dict serialization."""
        claim = Claim(
            id="CLM-001",
            text="Test claim",
            claim_type=ClaimType.STATISTICAL,
            source_text="Original text",
            source_location="test.txt",
            importance="high",
            extracted_at="2024-01-01T00:00:00Z"
        )

        d = claim.to_dict()

        assert d["id"] == "CLM-001"
        assert d["claim_type"] == "statistical"
        assert d["importance"] == "high"


class TestVerificationSource:
    """Test VerificationSource dataclass."""

    def test_source_to_dict(self):
        """Test VerificationSource to_dict serialization."""
        source = VerificationSource(
            url="https://example.com",
            title="Example",
            snippet="Test snippet",
            credibility_score=80,
            supports_claim=True,
            relevance_score=0.9
        )

        d = source.to_dict()

        assert d["url"] == "https://example.com"
        assert d["credibility_score"] == 80
        assert d["supports_claim"] is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
