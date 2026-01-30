#!/usr/bin/env python3
"""
Complexity Detector for Claude-Loop

Automatically detects project complexity (Level 0-4) from user input and PRD content
without requiring user to specify. Part of the Invisible Intelligence system.

Complexity Levels:
- Level 0 (micro): Single file change, bug fix, typo
- Level 1 (small): Few files, simple feature, < 3 stories
- Level 2 (medium): Multiple files, standard feature, 3-7 stories
- Level 3 (large): Many files, complex feature, 8-15 stories, architecture needed
- Level 4 (enterprise): Cross-team, compliance, security, > 15 stories

Scoring Algorithm:
Each signal contributes to a weighted score:
- Story count: 25% weight
- Security keywords: 20% weight
- Infrastructure keywords: 15% weight
- Integration keywords: 15% weight
- Compliance keywords: 15% weight
- File scope breadth: 10% weight

Final score mapped to levels:
- 0-15: Level 0 (micro)
- 16-30: Level 1 (small)
- 31-50: Level 2 (medium)
- 51-75: Level 3 (large)
- 76-100: Level 4 (enterprise)
"""

import argparse
import json
import os
import re
import sys
from dataclasses import dataclass, asdict, field
from typing import Optional

# Try to import yaml, fall back to basic parsing if not available
try:
    import yaml
    YAML_AVAILABLE = True
except ImportError:
    YAML_AVAILABLE = False


# Complexity level definitions
COMPLEXITY_LEVELS = {
    0: {
        "name": "micro",
        "description": "Single file change, bug fix, typo correction",
        "typical_stories": "0-1",
        "typical_duration": "minutes to 1 hour",
    },
    1: {
        "name": "small",
        "description": "Few files, simple feature addition",
        "typical_stories": "1-2",
        "typical_duration": "1-4 hours",
    },
    2: {
        "name": "medium",
        "description": "Multiple files, standard feature implementation",
        "typical_stories": "3-7",
        "typical_duration": "4-16 hours",
    },
    3: {
        "name": "large",
        "description": "Many files, complex feature requiring architecture",
        "typical_stories": "8-15",
        "typical_duration": "1-3 days",
    },
    4: {
        "name": "enterprise",
        "description": "Cross-team coordination, compliance, security-critical",
        "typical_stories": "15+",
        "typical_duration": "1+ weeks",
    },
}

# Keyword categories with weights
SECURITY_KEYWORDS = [
    "authentication", "auth", "oauth", "jwt", "token", "credential",
    "password", "secret", "encrypt", "decrypt", "hash", "salt",
    "permission", "role", "rbac", "acl", "authorization",
    "xss", "csrf", "sql injection", "injection", "sanitize",
    "vulnerability", "security", "audit", "penetration", "pentest",
    "ssl", "tls", "https", "certificate", "key management",
    "owasp", "cve", "security scan", "secret detection",
]

INFRASTRUCTURE_KEYWORDS = [
    "kubernetes", "k8s", "docker", "container", "pod", "deployment",
    "terraform", "ansible", "cloudformation", "infrastructure",
    "aws", "gcp", "azure", "cloud", "serverless", "lambda",
    "vpc", "subnet", "firewall", "load balancer", "cdn",
    "ci/cd", "pipeline", "jenkins", "github actions", "gitlab ci",
    "monitoring", "logging", "prometheus", "grafana", "elk",
    "database", "postgres", "mysql", "redis", "mongodb", "dynamodb",
    "message queue", "kafka", "rabbitmq", "sqs", "sns",
    "microservice", "service mesh", "istio", "envoy",
]

INTEGRATION_KEYWORDS = [
    "api", "rest", "graphql", "grpc", "webhook", "websocket",
    "integration", "third-party", "external", "sdk", "client library",
    "oauth provider", "saml", "sso", "ldap", "active directory",
    "payment", "stripe", "paypal", "billing", "subscription",
    "email", "smtp", "sendgrid", "ses", "notification",
    "sms", "twilio", "push notification", "fcm", "apns",
    "analytics", "tracking", "segment", "mixpanel", "amplitude",
    "search", "elasticsearch", "algolia", "solr",
    "storage", "s3", "blob", "file upload", "cdn",
]

COMPLIANCE_KEYWORDS = [
    "gdpr", "ccpa", "hipaa", "pci", "pci-dss", "soc2", "soc 2",
    "compliance", "regulation", "regulatory", "audit", "audit trail",
    "data protection", "privacy", "consent", "data retention",
    "encryption at rest", "encryption in transit",
    "access control", "least privilege", "separation of duties",
    "logging", "audit log", "immutable log",
    "backup", "disaster recovery", "business continuity",
    "iso 27001", "fedramp", "nist", "cis benchmark",
    "data residency", "data sovereignty", "cross-border",
]


@dataclass
class ComplexityResult:
    """Result of complexity detection."""
    level: int
    level_name: str
    level_description: str
    score: float
    signals: dict
    confidence: float
    reasoning: str


@dataclass
class QualityGates:
    """Quality gate configuration."""
    tests: bool = True
    lint: bool = False
    type_check: bool = False
    security_scan: bool = False
    coverage_check: bool = False
    coverage_threshold: int = 0


@dataclass
class ApprovalConfig:
    """Approval requirements configuration."""
    required: bool = False
    reviewers: int = 0
    checkpoint_phases: list = field(default_factory=list)


@dataclass
class TrackConfig:
    """Track configuration with quality gates and requirements."""
    name: str
    description: str
    complexity_levels: list
    quality_gates: QualityGates
    adr_required: bool
    architecture_doc: bool
    approval: ApprovalConfig
    max_iterations: int
    model_preference: str
    parallel_enabled: bool


# Default track configurations (used when YAML file not available)
DEFAULT_TRACK_CONFIGS = {
    "quick": TrackConfig(
        name="Quick",
        description="Fast implementation for simple changes",
        complexity_levels=[0, 1],
        quality_gates=QualityGates(tests=True),
        adr_required=False,
        architecture_doc=False,
        approval=ApprovalConfig(),
        max_iterations=5,
        model_preference="haiku",
        parallel_enabled=True,
    ),
    "standard": TrackConfig(
        name="Standard",
        description="Balanced approach for typical features",
        complexity_levels=[2, 3],
        quality_gates=QualityGates(tests=True, lint=True, type_check=True),
        adr_required=False,
        architecture_doc=False,
        approval=ApprovalConfig(),
        max_iterations=10,
        model_preference="sonnet",
        parallel_enabled=True,
    ),
    "enterprise": TrackConfig(
        name="Enterprise",
        description="Rigorous process for critical, cross-team initiatives",
        complexity_levels=[4],
        quality_gates=QualityGates(
            tests=True, lint=True, type_check=True,
            security_scan=True, coverage_check=True, coverage_threshold=80
        ),
        adr_required=True,
        architecture_doc=True,
        approval=ApprovalConfig(required=True, reviewers=2, checkpoint_phases=["analysis", "solutioning"]),
        max_iterations=20,
        model_preference="opus",
        parallel_enabled=False,
    ),
}

# Cache for loaded track config
_track_config_cache: Optional[dict] = None


def get_track_config_path() -> str:
    """Get path to track-config.yaml."""
    return os.path.join(os.path.dirname(__file__), "track-config.yaml")


def load_track_config() -> dict:
    """
    Load track configuration from YAML file.

    Returns:
        Dictionary with track configurations
    """
    global _track_config_cache

    if _track_config_cache is not None:
        return _track_config_cache

    config_path = get_track_config_path()

    if not os.path.exists(config_path):
        _track_config_cache = {"tracks": {}}
        return _track_config_cache

    if not YAML_AVAILABLE:
        print("Warning: PyYAML not installed, using default track configs", file=sys.stderr)
        _track_config_cache = {"tracks": {}}
        return _track_config_cache

    try:
        with open(config_path, 'r') as f:
            _track_config_cache = yaml.safe_load(f)
        return _track_config_cache
    except Exception as e:
        print(f"Warning: Could not load track config: {e}", file=sys.stderr)
        _track_config_cache = {"tracks": {}}
        return _track_config_cache


def get_track_config(track_name: str) -> TrackConfig:
    """
    Get configuration for a specific track.

    Args:
        track_name: Name of track (quick, standard, enterprise)

    Returns:
        TrackConfig with quality gates and requirements
    """
    config = load_track_config()
    tracks = config.get("tracks", {})

    if track_name in tracks:
        track_data = tracks[track_name]
        quality_gates_data = track_data.get("quality_gates", {})
        approval_data = track_data.get("approval", {})

        return TrackConfig(
            name=track_data.get("name", track_name.title()),
            description=track_data.get("description", ""),
            complexity_levels=track_data.get("complexity_levels", []),
            quality_gates=QualityGates(
                tests=quality_gates_data.get("tests", True),
                lint=quality_gates_data.get("lint", False),
                type_check=quality_gates_data.get("type_check", False),
                security_scan=quality_gates_data.get("security_scan", False),
                coverage_check=quality_gates_data.get("coverage_check", False),
                coverage_threshold=quality_gates_data.get("coverage_threshold", 0),
            ),
            adr_required=track_data.get("adr_required", False),
            architecture_doc=track_data.get("architecture_doc", False),
            approval=ApprovalConfig(
                required=approval_data.get("required", False),
                reviewers=approval_data.get("reviewers", 0),
                checkpoint_phases=approval_data.get("checkpoint_phases", []),
            ),
            max_iterations=track_data.get("max_iterations", 10),
            model_preference=track_data.get("model_preference", "sonnet"),
            parallel_enabled=track_data.get("parallel_enabled", True),
        )

    # Fall back to default configs
    if track_name in DEFAULT_TRACK_CONFIGS:
        return DEFAULT_TRACK_CONFIGS[track_name]

    # Unknown track, return standard defaults
    return DEFAULT_TRACK_CONFIGS["standard"]


def count_keyword_matches(text: str, keywords: list[str]) -> int:
    """Count how many keywords from the list appear in the text."""
    text_lower = text.lower()
    matches = 0
    for keyword in keywords:
        # Use word boundary matching for more accurate detection
        pattern = r'\b' + re.escape(keyword.lower()) + r'\b'
        if re.search(pattern, text_lower):
            matches += 1
    return matches


def estimate_story_count(text: str, prd_data: Optional[dict] = None) -> int:
    """Estimate the number of user stories from text or PRD data."""
    if prd_data and "userStories" in prd_data:
        return len(prd_data["userStories"])

    # Heuristics for estimating from text
    story_indicators = [
        r"user story",
        r"as a\s+\w+,?\s+i\s+want",
        r"acceptance criteria",
        r"\bus-\d+\b",
        r"\bstory\s*\d+\b",
        r"(?:^|\n)\s*[-*]\s*\w+",  # Bullet points (rough estimate)
    ]

    count = 0
    text_lower = text.lower()
    for pattern in story_indicators[:5]:  # Skip bullet point pattern for initial count
        count += len(re.findall(pattern, text_lower, re.IGNORECASE))

    # If we have bullet points but no explicit stories, estimate from bullets
    if count == 0:
        bullets = re.findall(r"(?:^|\n)\s*[-*]\s*\w+", text)
        count = min(len(bullets) // 2, 5)  # Conservative estimate

    return max(1, count)


def estimate_file_scope(text: str, prd_data: Optional[dict] = None) -> int:
    """Estimate the number of files that will be affected."""
    if prd_data and "userStories" in prd_data:
        files = set()
        for story in prd_data["userStories"]:
            if "fileScope" in story:
                files.update(story["fileScope"])
        if files:
            return len(files)

    # Heuristics from text
    file_patterns = [
        r"\.py\b", r"\.js\b", r"\.ts\b", r"\.tsx\b", r"\.jsx\b",
        r"\.java\b", r"\.go\b", r"\.rs\b", r"\.rb\b", r"\.php\b",
        r"\.sh\b", r"\.yaml\b", r"\.yml\b", r"\.json\b", r"\.toml\b",
        r"\.md\b", r"\.html\b", r"\.css\b", r"\.scss\b",
    ]

    files_mentioned = 0
    for pattern in file_patterns:
        files_mentioned += len(re.findall(pattern, text))

    # Also look for directory mentions
    dir_patterns = [r"/\w+/", r"src/", r"lib/", r"tests?/", r"docs?/"]
    dirs_mentioned = sum(len(re.findall(p, text)) for p in dir_patterns)

    return max(1, files_mentioned + dirs_mentioned // 2)


def calculate_complexity_score(
    story_count: int,
    security_matches: int,
    infra_matches: int,
    integration_matches: int,
    compliance_matches: int,
    file_scope: int,
) -> float:
    """
    Calculate weighted complexity score (0-100).

    Weights:
    - Story count: 25%
    - Security keywords: 20%
    - Infrastructure keywords: 15%
    - Integration keywords: 15%
    - Compliance keywords: 15%
    - File scope: 10%
    """
    # Normalize each signal to 0-100 scale
    story_score = min(100, story_count * 6)  # 15+ stories = 100
    security_score = min(100, security_matches * 15)  # 7+ matches = 100
    infra_score = min(100, infra_matches * 12)  # 8+ matches = 100
    integration_score = min(100, integration_matches * 12)  # 8+ matches = 100
    compliance_score = min(100, compliance_matches * 20)  # 5+ matches = 100
    file_score = min(100, file_scope * 5)  # 20+ files = 100

    # Apply weights
    weighted_score = (
        story_score * 0.25 +
        security_score * 0.20 +
        infra_score * 0.15 +
        integration_score * 0.15 +
        compliance_score * 0.15 +
        file_score * 0.10
    )

    return round(weighted_score, 2)


def score_to_level(score: float) -> int:
    """Map complexity score (0-100) to level (0-4)."""
    if score <= 15:
        return 0
    elif score <= 30:
        return 1
    elif score <= 50:
        return 2
    elif score <= 75:
        return 3
    else:
        return 4


def calculate_confidence(signals: dict) -> float:
    """Calculate confidence in the complexity assessment."""
    # Higher confidence when we have more signals
    # Filter out non-numeric values (like story_count_source)
    numeric_signals = [v for v in signals.values() if isinstance(v, (int, float))]
    signal_count = sum(1 for v in numeric_signals if v > 0)

    # Story count from actual PRD is more reliable
    prd_bonus = 0.1 if signals.get("story_count_source") == "prd" else 0

    base_confidence = 0.5 + (signal_count * 0.08) + prd_bonus
    return min(0.95, round(base_confidence, 2))


def generate_reasoning(level: int, signals: dict, score: float) -> str:
    """Generate human-readable reasoning for the complexity assessment."""
    reasons = []

    story_count = signals.get("story_count", 0)
    if story_count <= 2:
        reasons.append(f"small scope ({story_count} stories)")
    elif story_count <= 7:
        reasons.append(f"moderate scope ({story_count} stories)")
    elif story_count <= 15:
        reasons.append(f"large scope ({story_count} stories)")
    else:
        reasons.append(f"enterprise scope ({story_count} stories)")

    if signals.get("security_matches", 0) > 3:
        reasons.append("significant security requirements")
    if signals.get("infra_matches", 0) > 3:
        reasons.append("infrastructure complexity")
    if signals.get("integration_matches", 0) > 3:
        reasons.append("multiple integrations")
    if signals.get("compliance_matches", 0) > 2:
        reasons.append("compliance requirements")
    if signals.get("file_scope", 0) > 10:
        reasons.append("broad file scope")

    level_info = COMPLEXITY_LEVELS[level]
    return f"Level {level} ({level_info['name']}): {', '.join(reasons)}. Score: {score}/100"


def detect_complexity(
    text: str,
    prd_path: Optional[str] = None,
) -> ComplexityResult:
    """
    Detect project complexity from text and/or PRD file.

    Args:
        text: Feature description or PRD content as text
        prd_path: Optional path to PRD JSON file

    Returns:
        ComplexityResult with level, score, signals, and reasoning
    """
    prd_data = None
    combined_text = text

    # Load PRD if provided
    if prd_path:
        try:
            with open(prd_path, 'r') as f:
                prd_data = json.load(f)
            # Add PRD content to text for keyword analysis
            combined_text += " " + json.dumps(prd_data)
        except (json.JSONDecodeError, FileNotFoundError) as e:
            print(f"Warning: Could not load PRD file: {e}", file=sys.stderr)

    # Analyze signals
    story_count = estimate_story_count(combined_text, prd_data)
    security_matches = count_keyword_matches(combined_text, SECURITY_KEYWORDS)
    infra_matches = count_keyword_matches(combined_text, INFRASTRUCTURE_KEYWORDS)
    integration_matches = count_keyword_matches(combined_text, INTEGRATION_KEYWORDS)
    compliance_matches = count_keyword_matches(combined_text, COMPLIANCE_KEYWORDS)
    file_scope = estimate_file_scope(combined_text, prd_data)

    signals = {
        "story_count": story_count,
        "story_count_source": "prd" if prd_data and "userStories" in prd_data else "estimated",
        "security_matches": security_matches,
        "infra_matches": infra_matches,
        "integration_matches": integration_matches,
        "compliance_matches": compliance_matches,
        "file_scope": file_scope,
    }

    # Calculate score and level
    score = calculate_complexity_score(
        story_count,
        security_matches,
        infra_matches,
        integration_matches,
        compliance_matches,
        file_scope,
    )
    level = score_to_level(score)

    # Get level info
    level_info = COMPLEXITY_LEVELS[level]

    return ComplexityResult(
        level=level,
        level_name=level_info["name"],
        level_description=level_info["description"],
        score=score,
        signals=signals,
        confidence=calculate_confidence(signals),
        reasoning=generate_reasoning(level, signals, score),
    )


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Detect project complexity from text or PRD file",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Complexity Levels:
  0 (micro):      Single file change, bug fix, typo
  1 (small):      Few files, simple feature, < 3 stories
  2 (medium):     Multiple files, standard feature, 3-7 stories
  3 (large):      Many files, complex feature, 8-15 stories
  4 (enterprise): Cross-team, compliance, security, > 15 stories

Examples:
  complexity-detector.py detect "Add user authentication with OAuth"
  complexity-detector.py detect --prd prd.json
  complexity-detector.py detect "Add logging" --prd prd.json --json
  complexity-detector.py levels
""",
    )

    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # detect command
    detect_parser = subparsers.add_parser("detect", help="Detect complexity from text or PRD")
    detect_parser.add_argument(
        "text",
        nargs="?",
        default="",
        help="Feature description text",
    )
    detect_parser.add_argument(
        "--prd",
        type=str,
        help="Path to PRD JSON file",
    )
    detect_parser.add_argument(
        "--json",
        action="store_true",
        help="Output as JSON",
    )
    detect_parser.add_argument(
        "--show-track",
        action="store_true",
        help="Also show recommended track",
    )
    detect_parser.add_argument(
        "--show-phases",
        action="store_true",
        help="Also show recommended phases",
    )

    # levels command
    levels_parser = subparsers.add_parser("levels", help="Show complexity level definitions")
    levels_parser.add_argument(
        "--json",
        action="store_true",
        help="Output as JSON",
    )

    args = parser.parse_args()

    if args.command == "detect":
        if not args.text and not args.prd:
            parser.error("Either text or --prd must be provided")

        # Load PRD text if provided
        text = args.text
        if args.prd and not text:
            try:
                with open(args.prd, 'r') as f:
                    prd_data = json.load(f)
                text = prd_data.get("description", "")
            except Exception as e:
                parser.error(f"Could not load PRD: {e}")

        result = detect_complexity(text, args.prd)

        if args.json:
            output = asdict(result)
            if args.show_track:
                track = get_track(result.level)
                track_config = get_track_config(track)
                output["track"] = track
                output["track_config"] = asdict(track_config)
            if args.show_phases:
                output["phases"] = get_phases(result.level)
            print(json.dumps(output, indent=2))
        else:
            print(f"Complexity Level: {result.level} ({result.level_name})")
            print(f"Description: {result.level_description}")
            print(f"Score: {result.score}/100")
            print(f"Confidence: {result.confidence * 100:.0f}%")
            print(f"\nSignals:")
            print(f"  Story count: {result.signals['story_count']} ({result.signals['story_count_source']})")
            print(f"  Security keywords: {result.signals['security_matches']}")
            print(f"  Infrastructure keywords: {result.signals['infra_matches']}")
            print(f"  Integration keywords: {result.signals['integration_matches']}")
            print(f"  Compliance keywords: {result.signals['compliance_matches']}")
            print(f"  File scope: {result.signals['file_scope']}")
            print(f"\nReasoning: {result.reasoning}")

            if args.show_track:
                track = get_track(result.level)
                track_config = get_track_config(track)
                print(f"\nRecommended Track: {track}")
                print(f"  Description: {track_config.description}")
                print(f"  Quality Gates:")
                print(f"    - Tests: {'required' if track_config.quality_gates.tests else 'not required'}")
                print(f"    - Lint: {'required' if track_config.quality_gates.lint else 'not required'}")
                print(f"    - Type Check: {'required' if track_config.quality_gates.type_check else 'not required'}")
                print(f"    - Security Scan: {'required' if track_config.quality_gates.security_scan else 'not required'}")
                if track_config.quality_gates.coverage_check:
                    print(f"    - Coverage: required (>={track_config.quality_gates.coverage_threshold}%)")
                else:
                    print(f"    - Coverage: not required")
                print(f"  ADR Required: {'yes' if track_config.adr_required else 'no'}")
                print(f"  Architecture Doc: {'yes' if track_config.architecture_doc else 'no'}")
                print(f"  Approval: {'required ({} reviewers)'.format(track_config.approval.reviewers) if track_config.approval.required else 'not required'}")
                print(f"  Model Preference: {track_config.model_preference}")

            if args.show_phases:
                phases = get_phases(result.level)
                print(f"\nRequired Phases: {' -> '.join(phases)}")

    elif args.command == "levels":
        if args.json:
            print(json.dumps(COMPLEXITY_LEVELS, indent=2))
        else:
            print("Complexity Level Definitions:")
            print("-" * 50)
            for level, info in COMPLEXITY_LEVELS.items():
                print(f"\nLevel {level} ({info['name']}):")
                print(f"  Description: {info['description']}")
                print(f"  Typical stories: {info['typical_stories']}")
                print(f"  Typical duration: {info['typical_duration']}")

    else:
        parser.print_help()
        sys.exit(1)


# Track selection function (for INV-002)
def get_track(complexity: int) -> str:
    """
    Get implementation track based on complexity level.

    - Level 0-1 -> quick track
    - Level 2-3 -> standard track
    - Level 4 -> enterprise track
    """
    if complexity <= 1:
        return "quick"
    elif complexity <= 3:
        return "standard"
    else:
        return "enterprise"


# Phase selection function (for INV-003)
def get_phases(complexity: int) -> list[str]:
    """
    Get required phases based on complexity level.

    - Level 0-1: implementation only
    - Level 2: planning + implementation
    - Level 3: planning + solutioning + implementation
    - Level 4: analysis + planning + solutioning + implementation
    """
    if complexity <= 1:
        return ["implementation"]
    elif complexity == 2:
        return ["planning", "implementation"]
    elif complexity == 3:
        return ["planning", "solutioning", "implementation"]
    else:
        return ["analysis", "planning", "solutioning", "implementation"]


if __name__ == "__main__":
    main()
