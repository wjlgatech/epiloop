#!/usr/bin/env python3
"""
Situation Diagnosis Engine

Analyzes user requests to understand complexity, domain, operation type, risks,
and required capabilities for intelligent routing.
"""

import json
import re
from typing import Dict, List, Set, Tuple
from dataclasses import dataclass, asdict
from enum import Enum


class Domain(str, Enum):
    """Primary domains for classification"""
    FRONTEND = "frontend"
    BACKEND = "backend"
    SECURITY = "security"
    INFRASTRUCTURE = "infrastructure"
    TESTING = "testing"
    DOCUMENTATION = "documentation"
    PLANNING = "planning"


class OperationType(str, Enum):
    """Operation type classification"""
    CREATION = "creation"
    MODIFICATION = "modification"
    DEBUGGING = "debugging"
    ANALYSIS = "analysis"
    PLANNING = "planning"


class RiskLevel(str, Enum):
    """Risk level assessment"""
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


@dataclass
class Risk:
    """Risk assessment for a specific risk type"""
    category: str
    level: RiskLevel
    confidence: float  # 0.0-1.0
    reasoning: str


@dataclass
class DiagnosisResult:
    """Result of situation diagnosis"""
    # Core metrics
    complexity: int  # 1-10
    complexity_confidence: float  # 0.0-1.0

    # Domain classification
    primary_domain: Domain
    secondary_domains: List[Domain]
    domain_confidence: float  # 0.0-1.0

    # Operation type
    operation_type: OperationType
    operation_confidence: float  # 0.0-1.0

    # Risk assessment
    risks: List[Risk]

    # Required capabilities
    capabilities_needed: List[str]

    # Supporting metadata
    keywords_detected: List[str]
    word_count: int

    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization"""
        return asdict(self)

    def to_json(self) -> str:
        """Convert to JSON string"""
        return json.dumps(self.to_dict(), indent=2)


class SituationDiagnosis:
    """
    Situation diagnosis engine that analyzes user requests to determine:
    - Complexity (1-10 scale)
    - Primary and secondary domains
    - Operation type (creation, modification, debugging, etc.)
    - Risk assessment (security, breaking changes, data loss)
    - Required capabilities (skills, agents, workflows needed)
    """

    # Domain detection patterns
    DOMAIN_PATTERNS = {
        Domain.FRONTEND: [
            r'\b(ui|ux|component|react|vue|angular|frontend|interface|design|responsive|css|styling|layout|button|form|page|screen)\b',
            r'\b(accessibility|a11y|wcag|user\s+experience|user\s+interface)\b',
        ],
        Domain.BACKEND: [
            r'\b(api|endpoint|server|backend|database|db|model|service|controller|middleware)\b',
            r'\b(authentication|auth|jwt|session|token|query|crud|rest|graphql)\b',
        ],
        Domain.SECURITY: [
            r'\b(security|vulnerability|auth|authentication|authorization|permission|encryption|audit|compliance|threat)\b',
            r'\b(owasp|xss|sql\s+injection|csrf|sanitize|escape|secure)\b',
        ],
        Domain.INFRASTRUCTURE: [
            r'\b(deploy|deployment|docker|k8s|kubernetes|ci/cd|infrastructure|devops|monitoring|logging)\b',
            r'\b(container|orchestration|scaling|load\s+balancer|cloud|aws|gcp|azure)\b',
        ],
        Domain.TESTING: [
            r'\b(test|testing|unit\s+test|integration\s+test|e2e|end-to-end|tdd|coverage|pytest|jest)\b',
            r'\b(mock|stub|fixture|assertion|validation|verify)\b',
        ],
        Domain.DOCUMENTATION: [
            r'\b(document|documentation|docs|readme|guide|manual|wiki|comment|explain)\b',
            r'\b(api\s+spec|openapi|swagger|changelog|release\s+notes)\b',
        ],
        Domain.PLANNING: [
            r'\b(plan|design|architect|brainstorm|requirements|spec|prd|user\s+story)\b',
            r'\b(roadmap|milestone|epic|feature|refactor|rethink)\b',
        ],
    }

    # Operation type patterns
    OPERATION_PATTERNS = {
        OperationType.CREATION: [
            r'\b(create|add|build|implement|generate|new|develop|write)\b',
            r'\b(setup|initialize|construct|make)\b',
        ],
        OperationType.MODIFICATION: [
            r'\b(modify|update|change|edit|refactor|improve|optimize|enhance)\b',
            r'\b(upgrade|migrate|transform|adjust|tweak)\b',
        ],
        OperationType.DEBUGGING: [
            r'\b(debug|fix|bug|issue|error|failure|broken|problem|crash)\b',
            r'\b(troubleshoot|diagnose|investigate|resolve)\b',
        ],
        OperationType.ANALYSIS: [
            r'\b(analyze|review|audit|inspect|examine|check|evaluate)\b',
            r'\b(assess|measure|profile|trace|understand)\b',
        ],
        OperationType.PLANNING: [
            r'\b(plan|design|architect|brainstorm|explore|research)\b',
            r'\b(prototype|poc|proof-of-concept|spike)\b',
        ],
    }

    # Complexity indicators (keyword → complexity weight)
    COMPLEXITY_KEYWORDS = {
        # High complexity (5-8)
        r'\b(architecture|system|enterprise|scalable|distributed|microservice)\b': 7,
        r'\b(refactor|migrate|modernize|redesign)\b': 6,
        r'\b(real-time|websocket|streaming|async|concurrent)\b': 6,
        r'\b(multi-tenant|multi-user|collaborative)\b': 5,

        # Medium complexity (3-5)
        r'\b(authentication|authorization|security)\b': 5,
        r'\b(database|api|integration|workflow)\b': 4,
        r'\b(feature|functionality|component|module)\b': 3,

        # Low complexity (1-2)
        r'\b(simple|basic|quick|small|minor|fix|bug)\b': 2,
        r'\b(typo|formatting|styling|comment)\b': 1,
    }

    # Risk patterns
    RISK_PATTERNS = {
        "security": [
            r'\b(authentication|authorization|password|token|secret|key|credential)\b',
            r'\b(permission|access\s+control|role|security|audit)\b',
        ],
        "breaking_changes": [
            r'\b(breaking|incompatible|migration|major\s+change|rework)\b',
            r'\b(deprecate|remove|delete|drop)\b',
        ],
        "data_loss": [
            r'\b(delete|drop|truncate|remove|clear|wipe|reset)\b',
            r'\b(production|prod|live|database)\b',
        ],
    }

    def __init__(self):
        """Initialize diagnosis engine"""
        pass

    def diagnose(self, user_request: str, context: Dict = None) -> DiagnosisResult:
        """
        Analyze user request and return comprehensive diagnosis.

        Args:
            user_request: The user's request text
            context: Optional context (PRD info, project state, etc.)

        Returns:
            DiagnosisResult with all analysis fields populated
        """
        user_request = user_request.lower()
        words = user_request.split()
        word_count = len(words)

        # Extract keywords
        keywords = self._extract_keywords(user_request)

        # Analyze complexity
        complexity, complexity_confidence = self._analyze_complexity(
            user_request, word_count, keywords, context
        )

        # Detect domains
        primary_domain, secondary_domains, domain_confidence = self._detect_domains(user_request)

        # Classify operation type
        operation_type, operation_confidence = self._classify_operation(user_request)

        # Assess risks
        risks = self._assess_risks(user_request, primary_domain, operation_type)

        # Determine required capabilities
        capabilities = self._determine_capabilities(
            complexity, primary_domain, secondary_domains, operation_type, risks
        )

        return DiagnosisResult(
            complexity=complexity,
            complexity_confidence=complexity_confidence,
            primary_domain=primary_domain,
            secondary_domains=secondary_domains,
            domain_confidence=domain_confidence,
            operation_type=operation_type,
            operation_confidence=operation_confidence,
            risks=risks,
            capabilities_needed=capabilities,
            keywords_detected=keywords,
            word_count=word_count,
        )

    def _extract_keywords(self, text: str) -> List[str]:
        """Extract significant keywords from text"""
        # Simple keyword extraction - can be enhanced with NLP
        stop_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by'}
        words = re.findall(r'\b\w+\b', text.lower())
        keywords = [w for w in words if w not in stop_words and len(w) > 3]
        return list(set(keywords))[:20]  # Top 20 unique keywords

    def _analyze_complexity(
        self, text: str, word_count: int, keywords: List[str], context: Dict = None
    ) -> Tuple[int, float]:
        """
        Analyze request complexity on 1-10 scale.

        Factors:
        - Word count (longer = more complex)
        - Complexity keywords
        - Number of domains involved
        - Context from PRD
        """
        # Base complexity from word count
        if word_count < 10:
            base_complexity = 1
        elif word_count < 20:
            base_complexity = 2
        elif word_count < 50:
            base_complexity = 3
        elif word_count < 100:
            base_complexity = 5
        else:
            base_complexity = 7

        # Adjust based on complexity keywords
        keyword_weight = 0
        matches = 0
        for pattern, weight in self.COMPLEXITY_KEYWORDS.items():
            if re.search(pattern, text):
                keyword_weight += weight
                matches += 1

        if matches > 0:
            keyword_weight = keyword_weight / matches  # Average weight
            complexity = int((base_complexity + keyword_weight) / 2)
        else:
            complexity = base_complexity

        # Context adjustment
        if context and context.get("story_count", 0) > 5:
            complexity = min(10, complexity + 1)

        # Clamp to 1-10
        complexity = max(1, min(10, complexity))

        # Confidence based on matches
        confidence = 0.7 + (0.3 * min(matches, 3) / 3)

        return complexity, confidence

    def _detect_domains(self, text: str) -> Tuple[Domain, List[Domain], float]:
        """
        Detect primary and secondary domains.

        Returns:
            (primary_domain, secondary_domains, confidence)
        """
        domain_scores = {}

        for domain, patterns in self.DOMAIN_PATTERNS.items():
            score = 0
            for pattern in patterns:
                matches = len(re.findall(pattern, text))
                score += matches
            domain_scores[domain] = score

        # Sort by score
        sorted_domains = sorted(domain_scores.items(), key=lambda x: x[1], reverse=True)

        # Primary domain is highest score
        primary_domain = sorted_domains[0][0] if sorted_domains[0][1] > 0 else Domain.PLANNING

        # Secondary domains are any with score > 0 (excluding primary)
        secondary_domains = [d for d, s in sorted_domains[1:] if s > 0][:2]  # Max 2 secondary

        # Confidence based on score gap
        if sorted_domains[0][1] > 0:
            total_score = sum(s for _, s in sorted_domains)
            primary_score = sorted_domains[0][1]
            confidence = primary_score / total_score if total_score > 0 else 0.5
        else:
            confidence = 0.5  # Uncertain - default to planning

        return primary_domain, secondary_domains, confidence

    def _classify_operation(self, text: str) -> Tuple[OperationType, float]:
        """
        Classify operation type.

        Returns:
            (operation_type, confidence)
        """
        operation_scores = {}

        for operation, patterns in self.OPERATION_PATTERNS.items():
            score = 0
            for pattern in patterns:
                matches = len(re.findall(pattern, text))
                score += matches
            operation_scores[operation] = score

        # Sort by score
        sorted_operations = sorted(operation_scores.items(), key=lambda x: x[1], reverse=True)

        # Primary operation is highest score
        operation_type = sorted_operations[0][0] if sorted_operations[0][1] > 0 else OperationType.PLANNING

        # Confidence
        if sorted_operations[0][1] > 0:
            total_score = sum(s for _, s in sorted_operations)
            primary_score = sorted_operations[0][1]
            confidence = primary_score / total_score if total_score > 0 else 0.5
        else:
            confidence = 0.5

        return operation_type, confidence

    def _assess_risks(
        self, text: str, primary_domain: Domain, operation_type: OperationType
    ) -> List[Risk]:
        """
        Assess potential risks.

        Returns:
            List of Risk objects
        """
        risks = []

        # Security risk
        security_matches = sum(
            len(re.findall(pattern, text))
            for pattern in self.RISK_PATTERNS["security"]
        )
        if security_matches > 0 or primary_domain == Domain.SECURITY:
            level = RiskLevel.HIGH if security_matches >= 2 else RiskLevel.MEDIUM
            confidence = min(1.0, 0.6 + (security_matches * 0.2))
            risks.append(Risk(
                category="security",
                level=level,
                confidence=confidence,
                reasoning=f"Security-related keywords detected ({security_matches} matches) or security domain"
            ))

        # Breaking changes risk
        breaking_matches = sum(
            len(re.findall(pattern, text))
            for pattern in self.RISK_PATTERNS["breaking_changes"]
        )
        if breaking_matches > 0:
            level = RiskLevel.HIGH if breaking_matches >= 2 else RiskLevel.MEDIUM
            confidence = min(1.0, 0.6 + (breaking_matches * 0.2))
            risks.append(Risk(
                category="breaking_changes",
                level=level,
                confidence=confidence,
                reasoning=f"Breaking change keywords detected ({breaking_matches} matches)"
            ))

        # Data loss risk
        data_loss_matches = sum(
            len(re.findall(pattern, text))
            for pattern in self.RISK_PATTERNS["data_loss"]
        )
        if data_loss_matches >= 2:  # Need both delete keyword AND production keyword
            level = RiskLevel.HIGH
            confidence = min(1.0, 0.7 + (data_loss_matches * 0.15))
            risks.append(Risk(
                category="data_loss",
                level=level,
                confidence=confidence,
                reasoning=f"Data loss keywords detected in production context ({data_loss_matches} matches)"
            ))

        return risks

    def _determine_capabilities(
        self,
        complexity: int,
        primary_domain: Domain,
        secondary_domains: List[Domain],
        operation_type: OperationType,
        risks: List[Risk],
    ) -> List[str]:
        """
        Determine required capabilities (skills, agents, workflows).

        Returns:
            List of capability names
        """
        capabilities = []

        # Skills based on complexity and operation
        if complexity >= 5:
            capabilities.append("brainstorming")

        if operation_type == OperationType.CREATION:
            capabilities.append("test-driven-development")  # TODO: not yet implemented

        if operation_type == OperationType.DEBUGGING:
            capabilities.append("systematic-debugging")  # TODO: not yet implemented

        # Agents based on domain
        if primary_domain == Domain.SECURITY or any(r.category == "security" for r in risks):
            capabilities.append("security-auditor")

        if primary_domain == Domain.TESTING:
            capabilities.append("test-runner")

        if operation_type in [OperationType.CREATION, OperationType.MODIFICATION]:
            capabilities.append("code-reviewer")

        # Workflows based on operation
        if operation_type in [OperationType.CREATION, OperationType.MODIFICATION]:
            capabilities.append("two-stage-review")

        return capabilities


def main():
    """CLI interface for testing"""
    import sys

    if len(sys.argv) < 2:
        print("Usage: python3 diagnosis.py '<user_request>' [--json]")
        print("\nExample:")
        print('  python3 diagnosis.py "build user authentication with JWT"')
        print('  python3 diagnosis.py "fix bug in login flow" --json')
        sys.exit(1)

    user_request = sys.argv[1]
    json_output = "--json" in sys.argv

    # Run diagnosis
    engine = SituationDiagnosis()
    result = engine.diagnose(user_request)

    if json_output:
        print(result.to_json())
    else:
        print(f"\n{'='*60}")
        print("SITUATION DIAGNOSIS")
        print(f"{'='*60}\n")
        print(f"Request: {user_request}")
        print(f"\nComplexity: {result.complexity}/10 (confidence: {result.complexity_confidence:.2f})")
        print(f"Primary Domain: {result.primary_domain.value}")
        if result.secondary_domains:
            print(f"Secondary Domains: {', '.join(d.value for d in result.secondary_domains)}")
        print(f"Operation Type: {result.operation_type.value} (confidence: {result.operation_confidence:.2f})")

        if result.risks:
            print(f"\nRisks Detected:")
            for risk in result.risks:
                print(f"  - {risk.category.upper()}: {risk.level.value} (confidence: {risk.confidence:.2f})")
                print(f"    Reasoning: {risk.reasoning}")

        if result.capabilities_needed:
            print(f"\nCapabilities Needed:")
            for cap in result.capabilities_needed:
                print(f"  - {cap}")

        print(f"\nKeywords: {', '.join(result.keywords_detected[:10])}")
        print(f"Word Count: {result.word_count}")
        print(f"\n{'='*60}\n")


if __name__ == "__main__":
    main()
