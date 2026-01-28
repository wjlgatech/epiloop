#!/usr/bin/env python3
"""
Claim Verifier - Extract and verify claims from research text

This module provides:
- Claim extraction from text documents
- Search for supporting/contradicting evidence
- Verification status with sources
- Batch verification capabilities

Usage:
    python3 claim-verifier.py extract --file <path> [--json]
    python3 claim-verifier.py verify --claim "<text>" [--json]
    python3 claim-verifier.py verify-batch --claims <file> [--output <file>]
    python3 claim-verifier.py status --verification-id <id>
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


class VerificationStatus(str, Enum):
    """Claim verification status."""
    VERIFIED = "verified"       # 90-100% confidence
    LIKELY = "likely"           # 70-89% confidence
    UNCERTAIN = "uncertain"     # 50-69% confidence
    DISPUTED = "disputed"       # 30-49% confidence, conflicting sources
    UNVERIFIED = "unverified"   # 0-29% confidence


class ClaimType(str, Enum):
    """Types of factual claims."""
    STATISTICAL = "statistical"      # Numbers, percentages
    CAUSAL = "causal"               # X causes Y
    TEMPORAL = "temporal"           # Dates, timelines
    ATTRIBUTIVE = "attributive"     # Someone said X
    DEFINITIONAL = "definitional"   # Technical definitions
    COMPARATIVE = "comparative"     # A vs B comparisons
    GENERAL = "general"             # General factual claims


@dataclass
class Claim:
    """Extracted claim with metadata."""
    id: str
    text: str
    claim_type: ClaimType
    source_text: str  # Original text containing the claim
    source_location: str  # File/section where found
    importance: str  # critical, high, medium, low
    extracted_at: str = ""

    def to_dict(self) -> Dict:
        result = asdict(self)
        result["claim_type"] = self.claim_type.value
        return result


@dataclass
class VerificationSource:
    """A source used for verification."""
    url: str
    title: str
    snippet: str
    credibility_score: int
    supports_claim: bool  # True = supports, False = contradicts
    relevance_score: float  # 0.0-1.0

    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class VerificationResult:
    """Result of claim verification."""
    claim_id: str
    claim_text: str
    status: VerificationStatus
    confidence: int  # 0-100
    sources: List[VerificationSource]
    supporting_count: int
    contradicting_count: int
    notes: str = ""
    verified_at: str = ""

    @property
    def is_verified(self) -> bool:
        return self.status == VerificationStatus.VERIFIED

    @property
    def needs_attention(self) -> bool:
        return self.status in [VerificationStatus.UNVERIFIED, VerificationStatus.DISPUTED]

    def to_dict(self) -> Dict:
        result = asdict(self)
        result["status"] = self.status.value
        result["sources"] = [s.to_dict() if hasattr(s, 'to_dict') else s for s in self.sources]
        return result


class ClaimExtractor:
    """Extracts claims from text documents."""

    # Patterns that indicate factual claims
    CLAIM_PATTERNS = [
        # Statistical claims
        (r'\b(\d+(?:\.\d+)?)\s*(?:percent|%|million|billion|thousand)\b', ClaimType.STATISTICAL),
        (r'\b(?:increased|decreased|grew|fell|rose|dropped)\s+(?:by\s+)?(\d+(?:\.\d+)?)\s*%', ClaimType.STATISTICAL),
        (r'\b(?:approximately|about|nearly|over|under|more than|less than)\s+(\d+)', ClaimType.STATISTICAL),

        # Causal claims
        (r'\b(?:causes?|leads?\s+to|results?\s+in|due\s+to|because\s+of)\b', ClaimType.CAUSAL),
        (r'\b(?:effect|impact|influence)\s+(?:of|on)\b', ClaimType.CAUSAL),

        # Temporal claims
        (r'\b(?:in\s+)?(?:19|20)\d{2}\b', ClaimType.TEMPORAL),
        (r'\b(?:first|earliest|latest|recently|originally)\b', ClaimType.TEMPORAL),

        # Attributive claims
        (r'\b(?:according\s+to|said|stated|claimed|reported|announced)\b', ClaimType.ATTRIBUTIVE),
        (r'[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\s+(?:said|stated|argued)', ClaimType.ATTRIBUTIVE),

        # Comparative claims
        (r'\b(?:better|worse|faster|slower|more|less|higher|lower)\s+than\b', ClaimType.COMPARATIVE),
        (r'\b(?:outperform|exceed|surpass)\b', ClaimType.COMPARATIVE),

        # Definitional claims
        (r'\b(?:is\s+defined\s+as|refers\s+to|means|is\s+a\s+type\s+of)\b', ClaimType.DEFINITIONAL),
    ]

    # Words that typically don't indicate verifiable claims
    OPINION_INDICATORS = [
        'believe', 'think', 'feel', 'suggest', 'might', 'may', 'could',
        'probably', 'possibly', 'perhaps', 'seems', 'appears', 'opinion'
    ]

    def __init__(self):
        self.claims: List[Claim] = []

    def extract_from_text(self, text: str, source_location: str = "unknown") -> List[Claim]:
        """
        Extract claims from text.

        Args:
            text: Text to analyze
            source_location: Location identifier for the source

        Returns:
            List of extracted Claims
        """
        claims = []
        sentences = self._split_sentences(text)

        for sentence in sentences:
            # Skip sentences that are clearly opinions
            if self._is_opinion(sentence):
                continue

            # Check for claim patterns
            claim_type = self._detect_claim_type(sentence)
            if claim_type:
                importance = self._assess_importance(sentence, claim_type)
                claim = Claim(
                    id=self._generate_claim_id(sentence),
                    text=sentence.strip(),
                    claim_type=claim_type,
                    source_text=sentence,
                    source_location=source_location,
                    importance=importance,
                    extracted_at=datetime.utcnow().isoformat() + "Z"
                )
                claims.append(claim)

        self.claims = claims
        return claims

    def extract_from_file(self, file_path: Path) -> List[Claim]:
        """Extract claims from a file."""
        with open(file_path, 'r') as f:
            if file_path.suffix == '.json':
                data = json.load(f)
                # Handle research findings format
                if isinstance(data, dict) and 'findings' in data:
                    text = '\n'.join(str(f) for f in data['findings'])
                else:
                    text = json.dumps(data)
            else:
                text = f.read()

        return self.extract_from_text(text, str(file_path))

    def _split_sentences(self, text: str) -> List[str]:
        """Split text into sentences."""
        # Simple sentence splitting (can be enhanced with NLP)
        sentences = re.split(r'(?<=[.!?])\s+', text)
        return [s.strip() for s in sentences if s.strip()]

    def _is_opinion(self, text: str) -> bool:
        """Check if text appears to be an opinion rather than a fact."""
        text_lower = text.lower()
        return any(indicator in text_lower for indicator in self.OPINION_INDICATORS)

    def _detect_claim_type(self, text: str) -> Optional[ClaimType]:
        """Detect the type of claim in text."""
        text_lower = text.lower()

        for pattern, claim_type in self.CLAIM_PATTERNS:
            if re.search(pattern, text, re.IGNORECASE):
                return claim_type

        # Check if it's a general factual statement
        if self._looks_like_fact(text):
            return ClaimType.GENERAL

        return None

    def _looks_like_fact(self, text: str) -> bool:
        """Check if text looks like a factual statement."""
        # Has a subject and predicate
        if len(text.split()) < 4:
            return False

        # Contains assertion words
        assertion_words = ['is', 'are', 'was', 'were', 'has', 'have', 'had']
        return any(word in text.lower().split() for word in assertion_words)

    def _assess_importance(self, text: str, claim_type: ClaimType) -> str:
        """Assess the importance of a claim."""
        # Statistical and causal claims are typically more important
        if claim_type in [ClaimType.STATISTICAL, ClaimType.CAUSAL]:
            return "high"
        elif claim_type in [ClaimType.COMPARATIVE]:
            return "medium"
        elif claim_type in [ClaimType.TEMPORAL, ClaimType.ATTRIBUTIVE]:
            return "medium"
        else:
            return "low"

    def _generate_claim_id(self, text: str) -> str:
        """Generate a unique ID for a claim."""
        hash_input = text.strip().lower()
        return f"CLM-{hashlib.sha256(hash_input.encode()).hexdigest()[:8]}"


class ClaimVerifier:
    """Verifies claims against multiple sources."""

    # Minimum sources required for verification
    MIN_SOURCES_REQUIRED = 2

    def __init__(self, search_provider=None):
        """
        Initialize the claim verifier.

        Args:
            search_provider: Optional SearchProviderManager instance
        """
        self.search_provider = search_provider
        self.verifications: Dict[str, VerificationResult] = {}

    def verify(self, claim: Claim) -> VerificationResult:
        """
        Verify a claim by searching for evidence.

        Args:
            claim: Claim to verify

        Returns:
            VerificationResult with status and sources
        """
        # Generate search queries
        queries = self._generate_search_queries(claim)

        # Collect sources (in real implementation, would use search_provider)
        sources = self._search_for_evidence(claim, queries)

        # Analyze sources
        supporting = [s for s in sources if s.supports_claim]
        contradicting = [s for s in sources if not s.supports_claim]

        # Calculate confidence
        confidence, status = self._calculate_confidence(supporting, contradicting, claim.importance)

        result = VerificationResult(
            claim_id=claim.id,
            claim_text=claim.text,
            status=status,
            confidence=confidence,
            sources=sources,
            supporting_count=len(supporting),
            contradicting_count=len(contradicting),
            verified_at=datetime.utcnow().isoformat() + "Z"
        )

        self.verifications[claim.id] = result
        return result

    def verify_batch(self, claims: List[Claim]) -> List[VerificationResult]:
        """Verify multiple claims."""
        return [self.verify(claim) for claim in claims]

    def _generate_search_queries(self, claim: Claim) -> List[str]:
        """Generate search queries for verifying a claim."""
        queries = []

        # Base query from claim text
        base_query = claim.text[:100]  # Limit length
        queries.append(base_query)

        # Add fact-check query
        queries.append(f"{base_query} fact check")

        # Add type-specific queries
        if claim.claim_type == ClaimType.STATISTICAL:
            queries.append(f"{base_query} statistics data")
        elif claim.claim_type == ClaimType.CAUSAL:
            queries.append(f"{base_query} study research evidence")

        return queries

    def _search_for_evidence(self, claim: Claim, queries: List[str]) -> List[VerificationSource]:
        """
        Search for evidence supporting or contradicting the claim.

        This is a placeholder that would integrate with search-provider.py
        """
        sources = []

        if self.search_provider:
            try:
                for query in queries[:2]:  # Limit queries
                    results = self.search_provider.search(query, max_results=5)
                    for result in results:
                        # Analyze if result supports or contradicts
                        supports = self._analyze_support(claim.text, result.snippet)

                        source = VerificationSource(
                            url=result.url,
                            title=result.title,
                            snippet=result.snippet,
                            credibility_score=int(result.relevance_score * 100),
                            supports_claim=supports,
                            relevance_score=result.relevance_score
                        )
                        sources.append(source)
            except Exception as e:
                print(f"Search error: {e}", file=sys.stderr)

        return sources

    def _analyze_support(self, claim: str, evidence: str) -> bool:
        """
        Analyze if evidence supports the claim.

        Simple heuristic - would be enhanced with NLP in production.
        """
        claim_lower = claim.lower()
        evidence_lower = evidence.lower()

        # Check for contradiction indicators
        contradiction_words = ['false', 'incorrect', 'wrong', 'myth', 'debunked', 'not true']
        for word in contradiction_words:
            if word in evidence_lower and any(
                kw in evidence_lower
                for kw in claim_lower.split()[:5]
            ):
                return False

        return True

    def _calculate_confidence(
        self,
        supporting: List[VerificationSource],
        contradicting: List[VerificationSource],
        importance: str
    ) -> Tuple[int, VerificationStatus]:
        """
        Calculate confidence score and status.

        Args:
            supporting: Sources supporting the claim
            contradicting: Sources contradicting the claim
            importance: Claim importance level

        Returns:
            Tuple of (confidence_score, VerificationStatus)
        """
        # Weight by credibility
        support_score = sum(s.credibility_score * s.relevance_score for s in supporting)
        contradict_score = sum(s.credibility_score * s.relevance_score for s in contradicting)

        # Calculate base confidence
        total_sources = len(supporting) + len(contradicting)
        if total_sources == 0:
            return 20, VerificationStatus.UNVERIFIED

        # High credibility supporting sources
        high_cred_support = len([s for s in supporting if s.credibility_score >= 70])

        if len(contradicting) > 0 and len(supporting) > 0:
            # Conflicting evidence
            if support_score > contradict_score * 2:
                confidence = 60 + min(20, high_cred_support * 5)
                status = VerificationStatus.LIKELY
            elif contradict_score > support_score * 2:
                confidence = 30
                status = VerificationStatus.DISPUTED
            else:
                confidence = 45
                status = VerificationStatus.DISPUTED
        elif len(supporting) >= self.MIN_SOURCES_REQUIRED and high_cred_support >= 1:
            # Multiple supporting sources with at least one high credibility
            confidence = 85 + min(15, (high_cred_support - 1) * 5)
            status = VerificationStatus.VERIFIED
        elif len(supporting) >= 1:
            # Some support but not enough
            confidence = 60 + min(20, len(supporting) * 10)
            status = VerificationStatus.LIKELY if len(supporting) >= 2 else VerificationStatus.UNCERTAIN
        elif len(contradicting) > 0:
            confidence = 25
            status = VerificationStatus.DISPUTED
        else:
            confidence = 20
            status = VerificationStatus.UNVERIFIED

        return min(100, confidence), status

    def get_verification_summary(self) -> Dict:
        """Get summary of all verifications."""
        if not self.verifications:
            return {"total": 0, "by_status": {}}

        by_status = {}
        for result in self.verifications.values():
            status = result.status.value
            by_status[status] = by_status.get(status, 0) + 1

        return {
            "total": len(self.verifications),
            "by_status": by_status,
            "verified_percentage": (by_status.get("verified", 0) / len(self.verifications)) * 100,
            "needs_attention": sum(1 for r in self.verifications.values() if r.needs_attention)
        }


def format_verification_report(
    claims: List[Claim],
    results: List[VerificationResult],
    source_file: str
) -> str:
    """Format a verification report."""
    lines = [
        "## Fact Check Report",
        "",
        "### Document Analyzed",
        f"- **File**: {source_file}",
        f"- **Date**: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}",
        f"- **Claims Found**: {len(claims)}",
        "",
        "### Verification Summary",
        "| Status | Count | Percentage |",
        "|--------|-------|------------|",
    ]

    # Count by status
    status_counts = {}
    for result in results:
        status = result.status.value
        status_counts[status] = status_counts.get(status, 0) + 1

    for status in VerificationStatus:
        count = status_counts.get(status.value, 0)
        pct = (count / len(results) * 100) if results else 0
        lines.append(f"| {status.value.title()} | {count} | {pct:.1f}% |")

    lines.extend(["", "### Detailed Findings", ""])

    # Verified claims
    verified = [r for r in results if r.status == VerificationStatus.VERIFIED]
    if verified:
        lines.append("#### Verified Claims")
        for i, result in enumerate(verified, 1):
            lines.append(f"{i}. **Claim**: \"{result.claim_text[:100]}...\"")
            lines.append(f"   - **Confidence**: {result.confidence}%")
            lines.append(f"   - **Sources**: {result.supporting_count} supporting")
            lines.append("")

    # Flagged claims
    flagged = [r for r in results if r.needs_attention]
    if flagged:
        lines.append("#### Flagged Claims (Unverified/Disputed)")
        for i, result in enumerate(flagged, 1):
            lines.append(f"{i}. **Claim**: \"{result.claim_text[:100]}...\"")
            lines.append(f"   - **Status**: {result.status.value.title()}")
            lines.append(f"   - **Confidence**: {result.confidence}%")
            if result.contradicting_count > 0:
                lines.append(f"   - **Contradicting Sources**: {result.contradicting_count}")
            lines.append("")

    # Overall confidence
    avg_confidence = sum(r.confidence for r in results) / len(results) if results else 0
    lines.extend([
        "### Confidence Impact on Research",
        "",
        f"**Overall Research Confidence**: {avg_confidence:.1f}%",
        ""
    ])

    if flagged:
        lines.append("**Key Concerns**:")
        for i, result in enumerate(flagged[:3], 1):
            lines.append(f"{i}. {result.status.value.title()} claim: \"{result.claim_text[:50]}...\"")
        lines.append("")

    return "\n".join(lines)


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Claim Verifier for research-loop",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    claim-verifier.py extract --file findings.json
    claim-verifier.py verify --claim "AI market will reach $100B by 2025"
    claim-verifier.py verify-batch --claims claims.json --output verification.json
"""
    )

    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # extract command
    extract_parser = subparsers.add_parser("extract", help="Extract claims from text")
    extract_parser.add_argument("--file", required=True, help="File to extract claims from")
    extract_parser.add_argument("--json", action="store_true", help="Output as JSON")

    # verify command
    verify_parser = subparsers.add_parser("verify", help="Verify a single claim")
    verify_parser.add_argument("--claim", required=True, help="Claim text to verify")
    verify_parser.add_argument("--importance", default="medium", choices=["critical", "high", "medium", "low"])
    verify_parser.add_argument("--json", action="store_true", help="Output as JSON")

    # verify-batch command
    batch_parser = subparsers.add_parser("verify-batch", help="Verify multiple claims")
    batch_parser.add_argument("--claims", required=True, help="JSON file with claims")
    batch_parser.add_argument("--output", help="Output file for results")
    batch_parser.add_argument("--json", action="store_true", help="Output as JSON")

    # status command
    status_parser = subparsers.add_parser("status", help="Get verification status")
    status_parser.add_argument("--verification-id", help="Verification ID to check")
    status_parser.add_argument("--json", action="store_true", help="Output as JSON")

    args = parser.parse_args()

    if args.command == "extract":
        extractor = ClaimExtractor()
        file_path = Path(args.file)

        if not file_path.exists():
            print(f"Error: File not found: {args.file}", file=sys.stderr)
            return 1

        claims = extractor.extract_from_file(file_path)

        if args.json:
            output = [c.to_dict() for c in claims]
            print(json.dumps(output, indent=2))
        else:
            print(f"\nExtracted {len(claims)} claims from {args.file}")
            print()
            for i, claim in enumerate(claims, 1):
                print(f"{i}. [{claim.claim_type.value}] {claim.text[:80]}...")
                print(f"   Importance: {claim.importance}")
                print()

        return 0

    elif args.command == "verify":
        extractor = ClaimExtractor()
        verifier = ClaimVerifier()

        # Create a claim object
        claim = Claim(
            id=extractor._generate_claim_id(args.claim),
            text=args.claim,
            claim_type=extractor._detect_claim_type(args.claim) or ClaimType.GENERAL,
            source_text=args.claim,
            source_location="cli",
            importance=args.importance,
            extracted_at=datetime.utcnow().isoformat() + "Z"
        )

        result = verifier.verify(claim)

        if args.json:
            print(json.dumps(result.to_dict(), indent=2))
        else:
            print(f"\nVerification Result for: \"{args.claim[:60]}...\"")
            print(f"  Status: {result.status.value.upper()}")
            print(f"  Confidence: {result.confidence}%")
            print(f"  Supporting Sources: {result.supporting_count}")
            print(f"  Contradicting Sources: {result.contradicting_count}")
            if result.needs_attention:
                print(f"\n  WARNING: This claim needs attention (unverified/disputed)")

        return 0 if result.is_verified else 1

    elif args.command == "verify-batch":
        claims_file = Path(args.claims)
        if not claims_file.exists():
            print(f"Error: File not found: {args.claims}", file=sys.stderr)
            return 1

        with open(claims_file, 'r') as f:
            claims_data = json.load(f)

        # Convert to Claim objects
        claims = []
        for c in claims_data:
            claim = Claim(
                id=c.get("id", f"CLM-{len(claims):04d}"),
                text=c.get("text", c.get("claim", "")),
                claim_type=ClaimType(c.get("claim_type", "general")),
                source_text=c.get("source_text", ""),
                source_location=c.get("source_location", "batch"),
                importance=c.get("importance", "medium"),
                extracted_at=c.get("extracted_at", datetime.utcnow().isoformat() + "Z")
            )
            claims.append(claim)

        verifier = ClaimVerifier()
        results = verifier.verify_batch(claims)

        if args.output:
            output = [r.to_dict() for r in results]
            with open(args.output, 'w') as f:
                json.dump(output, f, indent=2)
            print(f"Results written to {args.output}")
        elif args.json:
            output = [r.to_dict() for r in results]
            print(json.dumps(output, indent=2))
        else:
            report = format_verification_report(claims, results, args.claims)
            print(report)

        summary = verifier.get_verification_summary()
        return 0 if summary.get("needs_attention", 0) == 0 else 1

    elif args.command == "status":
        print("Status checking requires a running verification session")
        return 1

    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main())
