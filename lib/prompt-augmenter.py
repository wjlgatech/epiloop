#!/usr/bin/env python3
# pylint: disable=broad-except
"""
prompt-augmenter.py - Experience-Augmented Prompts with Domain Context

Enhances Claude Code iteration prompts with relevant past experiences filtered
by domain context. Uses the experience retrieval system to find solutions from
similar projects that have proven helpful.

Features:
- Automatic domain detection before retrieval
- Domain-filtered experience retrieval
- Quality gating (only experiences with helpful_rate > 30%)
- Formatted output for prompt inclusion
- Execution logging for retrieval tracking
- CLI flag support for disabling augmentation

Usage:
    # Get augmented section for a project
    python3 lib/prompt-augmenter.py augment "Error: UI element not found"

    # With explicit domain
    python3 lib/prompt-augmenter.py augment "Build failed" --domain unity_game

    # From project path (auto-detect domain)
    python3 lib/prompt-augmenter.py augment "Test failure" --project-path /path/to/project

    # Check if augmentation would be useful (dry-run)
    python3 lib/prompt-augmenter.py check "Import error in module"

CLI Options:
    --db-dir DIR         Database directory (default: .claude-loop/experiences)
    --project-path PATH  Project path for domain detection (default: .)
    --domain DOMAIN      Explicit domain type (overrides auto-detection)
    --min-helpful-rate   Minimum helpful rate for inclusion (default: 0.30)
    --max-experiences    Maximum experiences to include (default: 3)
    --json               Output as JSON
    --verbose            Enable verbose output
"""

import argparse
import json
import sys
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

# Import from experience-retriever using importlib (handles hyphenated filename)
import importlib.util


def _import_module(module_name: str, file_path: Path) -> Any:
    """Import a module from a file path."""
    if not file_path.exists():
        return None
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    if not spec or not spec.loader:
        return None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# Import required modules
_lib_dir = Path(__file__).parent
_retriever_module = _import_module("experience_retriever", _lib_dir / "experience-retriever.py")
_detector_module = _import_module("domain_detector", _lib_dir / "domain-detector.py")
_store_module = _import_module("experience_store", _lib_dir / "experience-store.py")

# Get classes from modules
if _retriever_module:
    ExperienceRetriever = _retriever_module.ExperienceRetriever
    RetrievalResult = _retriever_module.RetrievalResult
else:
    ExperienceRetriever = None  # type: ignore
    RetrievalResult = None  # type: ignore

if _detector_module:
    DomainDetector = _detector_module.DomainDetector
    DetectionResult = _detector_module.DetectionResult
else:
    DomainDetector = None  # type: ignore
    DetectionResult = None  # type: ignore

if _store_module:
    DomainContext = _store_module.DomainContext
    ExperienceEntry = _store_module.ExperienceEntry
    DEFAULT_DB_DIR = _store_module.DEFAULT_DB_DIR
    DOMAIN_TYPES = _store_module.DOMAIN_TYPES
else:
    DomainContext = None  # type: ignore
    ExperienceEntry = None  # type: ignore
    DEFAULT_DB_DIR = ".claude-loop/experiences"
    DOMAIN_TYPES = ["other"]


# ============================================================================
# Constants
# ============================================================================

MIN_HELPFUL_RATE = 0.30  # Only include experiences with helpful_rate > 30%
MAX_EXPERIENCES = 3  # Maximum experiences to include in prompt
EXECUTION_LOG_FILE = ".claude-loop/execution_log.jsonl"


# ============================================================================
# Data Classes
# ============================================================================

@dataclass
class AugmentedExperience:
    """An experience formatted for prompt inclusion."""
    experience_id: str
    problem_summary: str
    solution_approach: str
    success_rate: float
    helpful_rate: float
    similarity_score: float
    domain: str

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class AugmentationResult:
    """Result of prompt augmentation."""
    experiences: List[AugmentedExperience]
    domain_detected: str
    domain_confidence: str
    augmented: bool
    formatted_section: str
    retrieval_count: int
    filtered_count: int  # How many were filtered by helpful_rate

    def to_dict(self) -> dict:
        return {
            'experiences': [e.to_dict() for e in self.experiences],
            'domain_detected': self.domain_detected,
            'domain_confidence': self.domain_confidence,
            'augmented': self.augmented,
            'formatted_section': self.formatted_section,
            'retrieval_count': self.retrieval_count,
            'filtered_count': self.filtered_count,
        }


# ============================================================================
# Prompt Augmenter Class
# ============================================================================

class PromptAugmenter:
    """
    Augments iteration prompts with relevant past experiences.

    Detects project domain, retrieves similar experiences, filters by quality,
    and formats them for inclusion in Claude Code iteration prompts.
    """

    def __init__(
        self,
        db_dir: str = DEFAULT_DB_DIR,
        project_path: str = ".",
        min_helpful_rate: float = MIN_HELPFUL_RATE,
        max_experiences: int = MAX_EXPERIENCES,
        use_embeddings: bool = True,
    ):
        """Initialize the prompt augmenter.

        Args:
            db_dir: Directory for experience database
            project_path: Path for domain detection
            min_helpful_rate: Minimum helpful rate for inclusion (default 0.30)
            max_experiences: Maximum experiences to include (default 3)
            use_embeddings: Whether to use sentence-transformer embeddings
        """
        self.project_path = Path(project_path).resolve()
        self.min_helpful_rate = min_helpful_rate
        self.max_experiences = max_experiences

        # Initialize retriever
        if ExperienceRetriever:
            self.retriever = ExperienceRetriever(
                db_dir=db_dir,
                use_embeddings=use_embeddings,
            )
        else:
            self.retriever = None

        # Initialize detector
        if DomainDetector:
            self.detector = DomainDetector(str(self.project_path))
        else:
            self.detector = None

        # Cache detected domain
        self._cached_domain: Optional[DetectionResult] = None

    def detect_domain(self, force: bool = False) -> Optional[DetectionResult]:
        """Detect domain for the project.

        Args:
            force: Force re-detection even if cached

        Returns:
            DetectionResult or None if detection unavailable
        """
        if not self.detector:
            return None

        if self._cached_domain is None or force:
            self._cached_domain = self.detector.detect()

        return self._cached_domain

    def augment_prompt(
        self,
        problem: str,
        domain_type: Optional[str] = None,
    ) -> AugmentationResult:
        """Augment prompt with relevant past experiences.

        Detects domain, retrieves similar experiences filtered by domain,
        filters by helpful_rate, and formats for prompt inclusion.

        Args:
            problem: Problem description or query text
            domain_type: Optional explicit domain type (overrides auto-detection)

        Returns:
            AugmentationResult with formatted section and metadata
        """
        # Detect domain if not provided
        domain_context = None
        domain_detected = "other"
        domain_confidence = "low"

        if domain_type:
            domain_detected = domain_type
            domain_confidence = "explicit"
            if DomainContext:
                domain_context = DomainContext(project_type=domain_type)
        else:
            detection = self.detect_domain()
            if detection:
                domain_detected = detection.project_type
                domain_confidence = detection.confidence
                domain_context = detection.to_domain_context() if hasattr(detection, 'to_domain_context') else None

        # Check if retriever is available
        if not self.retriever:
            return AugmentationResult(
                experiences=[],
                domain_detected=domain_detected,
                domain_confidence=domain_confidence,
                augmented=False,
                formatted_section="",
                retrieval_count=0,
                filtered_count=0,
            )

        # Retrieve similar experiences with domain filtering
        raw_results = self.retriever.retrieve_similar(
            problem=problem,
            domain_context=domain_context,
            k=self.max_experiences * 2,  # Fetch extra to filter by helpful_rate
        )

        # Filter by helpful_rate
        filtered_results: List[Any] = []
        filtered_count = 0

        for result in raw_results:
            # For new experiences (no retrievals yet), use a default helpful_rate of 0.5
            helpful_rate = result.helpful_rate if result.helpful_rate > 0 else 0.5

            if helpful_rate >= self.min_helpful_rate:
                filtered_results.append(result)
            else:
                filtered_count += 1

        # Limit to max_experiences
        filtered_results = filtered_results[:self.max_experiences]

        # Convert to AugmentedExperience objects
        experiences = []
        for result in filtered_results:
            exp = result.experience
            experiences.append(AugmentedExperience(
                experience_id=exp.id,
                problem_summary=self._summarize_text(exp.problem_signature, 100),
                solution_approach=self._summarize_text(exp.solution_approach, 200),
                success_rate=exp.success_count / max(exp.retrieval_count, 1) if exp.retrieval_count > 0 else 1.0,
                helpful_rate=result.helpful_rate if result.helpful_rate > 0 else 0.5,
                similarity_score=result.similarity_score,
                domain=exp.domain_context.project_type,
            ))

        # Format for prompt inclusion
        formatted_section = self._format_experiences_section(experiences, domain_detected)

        return AugmentationResult(
            experiences=experiences,
            domain_detected=domain_detected,
            domain_confidence=domain_confidence,
            augmented=len(experiences) > 0,
            formatted_section=formatted_section,
            retrieval_count=len(raw_results),
            filtered_count=filtered_count,
        )

    def _summarize_text(self, text: str, max_length: int) -> str:
        """Summarize text to max length."""
        text = text.strip()
        if len(text) <= max_length:
            return text
        return text[:max_length - 3] + "..."

    def _format_experiences_section(
        self,
        experiences: List["AugmentedExperience"],
        domain: str,
    ) -> str:
        """Format experiences as a markdown section for prompt inclusion.

        Args:
            experiences: List of experiences to format
            domain: Detected domain for the section header

        Returns:
            Formatted markdown string or empty string if no experiences
        """
        if not experiences:
            return ""

        lines = [
            f"## Relevant Past Experiences (from similar {domain} projects)",
            "",
            "The following solutions have worked well in similar situations:",
            "",
        ]

        for i, exp in enumerate(experiences, 1):
            lines.append(f"### Experience {i}")
            lines.append(f"**Problem**: {exp.problem_summary}")
            lines.append(f"**Solution**: {exp.solution_approach}")
            lines.append(f"**Success Rate**: {exp.success_rate:.0%} | **Helpful Rate**: {exp.helpful_rate:.0%} | **Similarity**: {exp.similarity_score:.0%}")
            lines.append("")

        lines.append("---")
        lines.append("")

        return "\n".join(lines)

    def check_augmentation_available(self, problem: str) -> Dict[str, Any]:
        """Check if augmentation would be useful for a problem.

        Performs retrieval without formatting to show what would be included.

        Args:
            problem: Problem description

        Returns:
            Dict with availability info and preview
        """
        result = self.augment_prompt(problem)

        return {
            'available': result.augmented,
            'domain': result.domain_detected,
            'domain_confidence': result.domain_confidence,
            'experience_count': len(result.experiences),
            'retrieval_count': result.retrieval_count,
            'filtered_by_quality': result.filtered_count,
            'experiences_preview': [
                {
                    'id': e.experience_id,
                    'problem': e.problem_summary[:50],
                    'helpful_rate': e.helpful_rate,
                    'similarity': e.similarity_score,
                }
                for e in result.experiences
            ],
        }

    def log_augmentation(
        self,
        result: AugmentationResult,
        story_id: str,
        success: Optional[bool] = None,
    ) -> None:
        """Log augmentation to execution log for tracking.

        Args:
            result: The augmentation result
            story_id: Story ID this augmentation was for
            success: Optional success flag (can be updated later)
        """
        log_file = Path(EXECUTION_LOG_FILE)
        log_file.parent.mkdir(parents=True, exist_ok=True)

        log_entry = {
            'type': 'experience_augmentation',
            'timestamp': datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
            'story_id': story_id,
            'experience_augmented': result.augmented,
            'experiences_retrieved': result.retrieval_count,
            'experiences_included': len(result.experiences),
            'experiences_filtered': result.filtered_count,
            'domain_detected': result.domain_detected,
            'domain_confidence': result.domain_confidence,
            'experience_ids': [e.experience_id for e in result.experiences],
            'success': success,
        }

        try:
            with open(log_file, 'a') as f:
                f.write(json.dumps(log_entry) + '\n')
        except IOError as e:
            print(f"Warning: Failed to log augmentation: {e}", file=sys.stderr)


# ============================================================================
# CLI Interface
# ============================================================================

def cmd_augment(args: argparse.Namespace) -> int:
    """Generate augmented prompt section."""
    augmenter = PromptAugmenter(
        db_dir=args.db_dir,
        project_path=args.project_path,
        min_helpful_rate=args.min_helpful_rate,
        max_experiences=args.max_experiences,
        use_embeddings=not args.no_embeddings,
    )

    # Get domain override if provided
    domain_type = getattr(args, 'domain', None)

    result = augmenter.augment_prompt(args.problem, domain_type)

    if args.json:
        print(json.dumps(result.to_dict(), indent=2))
    else:
        if result.augmented:
            print(result.formatted_section)
        else:
            if args.verbose:
                print("No relevant experiences found for augmentation", file=sys.stderr)
                print(f"  Domain: {result.domain_detected} ({result.domain_confidence})", file=sys.stderr)
                print(f"  Retrieved: {result.retrieval_count}", file=sys.stderr)
                print(f"  Filtered (low quality): {result.filtered_count}", file=sys.stderr)

    return 0


def cmd_check(args: argparse.Namespace) -> int:
    """Check if augmentation would be useful."""
    augmenter = PromptAugmenter(
        db_dir=args.db_dir,
        project_path=args.project_path,
        min_helpful_rate=args.min_helpful_rate,
        max_experiences=args.max_experiences,
        use_embeddings=not args.no_embeddings,
    )

    result = augmenter.check_augmentation_available(args.problem)

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        if result['available']:
            print(f"Augmentation available: {result['experience_count']} experience(s)")
            print(f"  Domain: {result['domain']} ({result['domain_confidence']})")
            print(f"  Retrieved: {result['retrieval_count']}, Filtered: {result['filtered_by_quality']}")
            print("\nExperience Preview:")
            for exp in result['experiences_preview']:
                print(f"  - [{exp['id'][:8]}] {exp['problem']}... (helpful: {exp['helpful_rate']:.0%})")
        else:
            print("No experiences available for augmentation")
            print(f"  Domain: {result['domain']} ({result['domain_confidence']})")
            print(f"  Retrieved: {result['retrieval_count']}, Filtered: {result['filtered_by_quality']}")

    return 0 if result['available'] else 1


def cmd_detect_domain(args: argparse.Namespace) -> int:
    """Detect domain for a project."""
    if not DomainDetector:
        print("Error: Domain detector not available", file=sys.stderr)
        return 1

    detector = DomainDetector(args.project_path)
    result = detector.detect()

    if args.json:
        print(json.dumps(result.to_dict(), indent=2))
    else:
        print(f"Domain: {result.project_type}")
        print(f"Confidence: {result.confidence} ({result.confidence_score:.0%})")
        print(f"Language: {result.language or 'unknown'}")
        if result.frameworks:
            print(f"Frameworks: {', '.join(result.frameworks[:5])}")

    return 0


def create_parser() -> argparse.ArgumentParser:
    """Create argument parser."""
    # Parent parser with shared options
    parent_parser = argparse.ArgumentParser(add_help=False)
    parent_parser.add_argument(
        "--db-dir",
        default=DEFAULT_DB_DIR,
        help=f"Database directory (default: {DEFAULT_DB_DIR})",
    )
    parent_parser.add_argument(
        "--project-path",
        default=".",
        help="Project path for domain detection (default: .)",
    )
    parent_parser.add_argument(
        "--min-helpful-rate",
        type=float,
        default=MIN_HELPFUL_RATE,
        help=f"Minimum helpful rate for inclusion (default: {MIN_HELPFUL_RATE})",
    )
    parent_parser.add_argument(
        "--max-experiences",
        type=int,
        default=MAX_EXPERIENCES,
        help=f"Maximum experiences to include (default: {MAX_EXPERIENCES})",
    )
    parent_parser.add_argument(
        "--no-embeddings",
        action="store_true",
        help="Use hash-based embeddings (skip sentence-transformers)",
    )
    parent_parser.add_argument(
        "--json",
        action="store_true",
        help="Output as JSON",
    )
    parent_parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose output",
    )

    # Main parser
    parser = argparse.ArgumentParser(
        description="Experience-Augmented Prompts with Domain Context",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        parents=[parent_parser],
    )

    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # augment command
    augment_parser = subparsers.add_parser(
        "augment",
        help="Generate augmented prompt section",
        parents=[parent_parser],
    )
    augment_parser.add_argument(
        "problem",
        help="Problem description or query text",
    )
    augment_parser.add_argument(
        "--domain",
        choices=DOMAIN_TYPES if DOMAIN_TYPES else ["other"],
        help="Explicit domain type (overrides auto-detection)",
    )

    # check command
    check_parser = subparsers.add_parser(
        "check",
        help="Check if augmentation would be useful",
        parents=[parent_parser],
    )
    check_parser.add_argument(
        "problem",
        help="Problem description",
    )

    # detect-domain command
    subparsers.add_parser(
        "detect-domain",
        help="Detect domain for a project",
        parents=[parent_parser],
    )

    return parser


def main() -> int:
    """Main entry point."""
    parser = create_parser()
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    # Dispatch to command handler
    commands = {
        "augment": cmd_augment,
        "check": cmd_check,
        "detect-domain": cmd_detect_domain,
    }

    handler = commands.get(args.command)
    if handler:
        return handler(args)

    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
