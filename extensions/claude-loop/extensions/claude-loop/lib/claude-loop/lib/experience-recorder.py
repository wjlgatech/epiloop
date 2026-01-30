#!/usr/bin/env python3
# pylint: disable=broad-except
"""
experience-recorder.py - Automatic Experience Recording for claude-loop

Records successful solutions with auto-detected domain context. Hooks into
story completion to capture problem signatures and solution approaches.

Features:
- Auto-detects domain context from project structure
- Extracts problem signature from story + error context
- Extracts solution approach from git diff summary
- Skips trivial changes (<10 lines, config-only, test-only)
- Deduplicates against existing experiences (>0.9 similarity)
- Records domain confidence scores for quality tracking

Usage:
    # Detect domain for current project
    python3 lib/experience-recorder.py detect-domain

    # Record from a completed story (called by claude-loop on success)
    python3 lib/experience-recorder.py record-story <story_id> --prd prd.json

    # Record from an execution log entry
    python3 lib/experience-recorder.py record-from-log <log_entry_index>

    # Manual recording with auto-detected domain
    python3 lib/experience-recorder.py record "problem description" "solution approach"
"""

import argparse
import json
import re
import subprocess
import sys
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Import from experience-store using importlib
import importlib.util

_lib_path = Path(__file__).parent

_store_path = _lib_path / "experience-store.py"
_spec = importlib.util.spec_from_file_location("experience_store", _store_path)
_experience_store_module = importlib.util.module_from_spec(_spec)  # type: ignore
_spec.loader.exec_module(_experience_store_module)  # type: ignore

ExperienceStore = _experience_store_module.ExperienceStore
DomainContext = _experience_store_module.DomainContext
DOMAIN_TYPES = _experience_store_module.DOMAIN_TYPES
DEFAULT_DB_DIR = _experience_store_module.DEFAULT_DB_DIR

_detector_path = _lib_path / "domain-detector.py"
_detector_spec = importlib.util.spec_from_file_location("domain_detector", _detector_path)
_domain_detector_module = importlib.util.module_from_spec(_detector_spec)  # type: ignore
_detector_spec.loader.exec_module(_domain_detector_module)  # type: ignore

DomainDetector = _domain_detector_module.DomainDetector
DetectionResult = _domain_detector_module.DetectionResult


# ============================================================================
# Constants
# ============================================================================

MIN_LINES_CHANGED = 10  # Skip experiences with fewer changed lines
MAX_DIFF_LINES_FOR_SUMMARY = 500  # Summarize longer diffs
SIMILARITY_THRESHOLD_DEDUP = 0.9  # Threshold for deduplication
EXECUTION_LOG_FILE = ".claude-loop/execution_log.jsonl"
DEFAULT_SIMILARITY_THRESHOLD = 0.75


# ============================================================================
# Data Classes
# ============================================================================

@dataclass
class RecordingDecision:
    """Decision about whether to record an experience."""
    should_record: bool
    reason: str
    problem_signature: str
    solution_approach: str
    domain_context: Optional[DomainContext]
    domain_confidence: str  # 'high', 'medium', 'low'
    lines_changed: int
    is_duplicate: bool
    duplicate_id: Optional[str]

    def to_dict(self) -> dict:
        data = asdict(self)
        if self.domain_context:
            data['domain_context'] = self.domain_context.to_dict()
        return data


@dataclass
class StoryContext:
    """Context extracted from a completed story."""
    story_id: str
    title: str
    description: str
    acceptance_criteria: List[str]
    error_context: str  # Error messages if any
    files_changed: List[str]
    lines_added: int
    lines_removed: int


# ============================================================================
# Helper Functions
# ============================================================================

def run_git_command(args: List[str], cwd: Optional[str] = None) -> Tuple[bool, str]:
    """Run a git command and return (success, output)."""
    try:
        result = subprocess.run(
            ["git"] + args,
            capture_output=True,
            text=True,
            cwd=cwd,
            timeout=30,
        )
        return result.returncode == 0, result.stdout.strip()
    except subprocess.TimeoutExpired:
        return False, "Git command timed out"
    except FileNotFoundError:
        return False, "Git not found"


def get_git_diff_stats(ref: str = "HEAD~1", cwd: Optional[str] = None) -> Tuple[int, int, List[str]]:
    """Get diff statistics from last commit.

    Returns:
        Tuple of (lines_added, lines_removed, files_changed)
    """
    # Get file list
    success, files_output = run_git_command(["diff", "--name-only", ref], cwd)
    files = files_output.split('\n') if success and files_output else []

    # Get numstat for line counts
    success, stat_output = run_git_command(["diff", "--numstat", ref], cwd)
    if not success:
        return 0, 0, files

    added = 0
    removed = 0
    for line in stat_output.split('\n'):
        if line:
            parts = line.split('\t')
            if len(parts) >= 2:
                try:
                    added += int(parts[0]) if parts[0] != '-' else 0
                    removed += int(parts[1]) if parts[1] != '-' else 0
                except ValueError:
                    pass

    return added, removed, [f for f in files if f]


def get_git_diff_summary(ref: str = "HEAD~1", max_lines: int = MAX_DIFF_LINES_FOR_SUMMARY, cwd: Optional[str] = None) -> str:
    """Get a summary of the git diff.

    Returns a concise summary suitable for solution_approach.
    """
    success, diff = run_git_command(["diff", "--stat", ref], cwd)
    if not success:
        return ""

    lines = diff.split('\n')
    if len(lines) > max_lines:
        # Truncate and add summary
        lines = lines[:max_lines]
        lines.append(f"... truncated ({len(lines)} files changed)")

    return '\n'.join(lines)


def is_config_only_change(files: List[str]) -> bool:
    """Check if changes are config-only (not worth recording)."""
    config_patterns = [
        r'\.gitignore$', r'\.env', r'\.editorconfig$',
        r'package-lock\.json$', r'yarn\.lock$', r'pnpm-lock\.yaml$',
        r'Cargo\.lock$', r'poetry\.lock$', r'Pipfile\.lock$',
        r'\.prettierrc', r'\.eslintrc', r'tsconfig\.json$',
        r'\.vscode/', r'\.idea/',
    ]

    for file in files:
        is_config = False
        for pattern in config_patterns:
            if re.search(pattern, file):
                is_config = True
                break
        if not is_config:
            return False

    return True


def is_test_only_change(files: List[str]) -> bool:
    """Check if changes are test-only (may or may not be worth recording)."""
    test_patterns = [
        r'test[s]?/', r'__tests__/', r'spec/', r'_test\.py$',
        r'\.test\.[jt]sx?$', r'\.spec\.[jt]sx?$', r'_test\.go$',
    ]

    for file in files:
        is_test = False
        for pattern in test_patterns:
            if re.search(pattern, file):
                is_test = True
                break
        if not is_test:
            return False

    return True


def extract_problem_signature(story: StoryContext, error_context: str = "") -> str:
    """Extract problem signature from story context.

    Creates a concise description of the problem that can be matched
    against future similar problems.
    """
    parts = []

    # Start with story title
    parts.append(story.title)

    # Add first acceptance criterion if available
    if story.acceptance_criteria:
        parts.append(f"Goal: {story.acceptance_criteria[0]}")

    # Add error context if present (truncated)
    if error_context:
        error_preview = error_context[:200]
        if len(error_context) > 200:
            error_preview += "..."
        parts.append(f"Error: {error_preview}")

    return " | ".join(parts)


def extract_solution_approach(story: StoryContext, diff_summary: str) -> str:
    """Extract solution approach from completed story.

    Creates a description of how the problem was solved.
    """
    parts = []

    # Summarize files changed
    file_types: Dict[str, int] = {}
    for file in story.files_changed[:10]:  # Limit to first 10
        ext = Path(file).suffix or "no-extension"
        file_types[ext] = file_types.get(ext, 0) + 1

    if file_types:
        file_summary = ", ".join(f"{count} {ext}" for ext, count in file_types.items())
        parts.append(f"Changed: {file_summary}")

    # Add line count summary
    parts.append(f"Lines: +{story.lines_added}/-{story.lines_removed}")

    # Add diff summary (truncated)
    if diff_summary:
        summary_preview = diff_summary[:300]
        if len(diff_summary) > 300:
            summary_preview += "\n..."
        parts.append(f"Changes:\n{summary_preview}")

    return "\n".join(parts)


# ============================================================================
# Experience Recorder Class
# ============================================================================

class ExperienceRecorder:
    """Records experiences with auto-detected domain context."""

    def __init__(
        self,
        project_path: str = ".",
        db_dir: str = DEFAULT_DB_DIR,
        use_embeddings: bool = True,
    ):
        """Initialize recorder.

        Args:
            project_path: Path to project root
            db_dir: Experience database directory
            use_embeddings: Whether to use sentence-transformer embeddings
        """
        self.project_path = Path(project_path).resolve()
        self.store = ExperienceStore(db_dir=db_dir, use_embeddings=use_embeddings)
        self._domain_cache: Optional[DetectionResult] = None

    def detect_domain(self, force_refresh: bool = False) -> DetectionResult:
        """Detect domain for the current project.

        Args:
            force_refresh: Force re-detection even if cached

        Returns:
            DetectionResult with domain information
        """
        if self._domain_cache is None or force_refresh:
            detector = DomainDetector(str(self.project_path))
            self._domain_cache = detector.detect()
        return self._domain_cache

    def check_duplicate(
        self,
        problem: str,
        domain_context: DomainContext,
    ) -> Tuple[bool, Optional[str]]:
        """Check if a similar experience already exists.

        Args:
            problem: Problem signature
            domain_context: Domain context for filtering

        Returns:
            Tuple of (is_duplicate, existing_experience_id)
        """
        results = self.store.search_similar(
            problem=problem,
            domain_context=domain_context,
            k=1,
            similarity_threshold=SIMILARITY_THRESHOLD_DEDUP,
        )

        if results:
            existing_exp, similarity = results[0]
            if similarity >= SIMILARITY_THRESHOLD_DEDUP:
                return True, existing_exp.id

        return False, None

    def should_record_story(
        self,
        story: StoryContext,
        error_context: str = "",
    ) -> RecordingDecision:
        """Decide whether to record a completed story as an experience.

        Implements the following skip rules:
        - Skip if <10 lines changed
        - Skip if purely config change
        - Skip if test-only change
        - Skip if >0.9 similarity with existing experience (increment instead)

        Args:
            story: Context from completed story
            error_context: Any error messages from execution

        Returns:
            RecordingDecision with reason and prepared data
        """
        # Detect domain
        domain_result = self.detect_domain()
        domain_context = domain_result.to_domain_context()

        total_lines = story.lines_added + story.lines_removed

        # Check minimum lines
        if total_lines < MIN_LINES_CHANGED:
            return RecordingDecision(
                should_record=False,
                reason=f"Too few lines changed ({total_lines} < {MIN_LINES_CHANGED})",
                problem_signature="",
                solution_approach="",
                domain_context=domain_context,
                domain_confidence=domain_result.confidence,
                lines_changed=total_lines,
                is_duplicate=False,
                duplicate_id=None,
            )

        # Check config-only
        if is_config_only_change(story.files_changed):
            return RecordingDecision(
                should_record=False,
                reason="Config-only change (not worth recording)",
                problem_signature="",
                solution_approach="",
                domain_context=domain_context,
                domain_confidence=domain_result.confidence,
                lines_changed=total_lines,
                is_duplicate=False,
                duplicate_id=None,
            )

        # Check test-only
        if is_test_only_change(story.files_changed):
            return RecordingDecision(
                should_record=False,
                reason="Test-only change (not worth recording)",
                problem_signature="",
                solution_approach="",
                domain_context=domain_context,
                domain_confidence=domain_result.confidence,
                lines_changed=total_lines,
                is_duplicate=False,
                duplicate_id=None,
            )

        # Extract problem and solution
        problem_signature = extract_problem_signature(story, error_context)
        diff_summary = get_git_diff_summary(cwd=str(self.project_path))
        solution_approach = extract_solution_approach(story, diff_summary)

        # Check for duplicates
        is_dup, dup_id = self.check_duplicate(problem_signature, domain_context)
        if is_dup:
            return RecordingDecision(
                should_record=False,
                reason=f"Duplicate of existing experience {dup_id} (>90% similar)",
                problem_signature=problem_signature,
                solution_approach=solution_approach,
                domain_context=domain_context,
                domain_confidence=domain_result.confidence,
                lines_changed=total_lines,
                is_duplicate=True,
                duplicate_id=dup_id,
            )

        return RecordingDecision(
            should_record=True,
            reason="Meets recording criteria",
            problem_signature=problem_signature,
            solution_approach=solution_approach,
            domain_context=domain_context,
            domain_confidence=domain_result.confidence,
            lines_changed=total_lines,
            is_duplicate=False,
            duplicate_id=None,
        )

    def record_experience(
        self,
        problem: str,
        solution: str,
        domain_context: Optional[DomainContext] = None,
        category: str = "",
        tags: Optional[List[str]] = None,
    ) -> Tuple[str, bool]:
        """Record an experience to the store.

        Args:
            problem: Problem signature
            solution: Solution approach
            domain_context: Domain context (auto-detected if None)
            category: Category for the experience
            tags: Tags for categorization

        Returns:
            Tuple of (experience_id, success)
        """
        if domain_context is None:
            domain_result = self.detect_domain()
            domain_context = domain_result.to_domain_context()

        return self.store.record_experience(
            problem=problem,
            solution=solution,
            domain_context=domain_context,
            category=category,
            tags=tags or [],
        )

    def record_from_story(
        self,
        story: StoryContext,
        error_context: str = "",
    ) -> Tuple[str, bool, str]:
        """Record an experience from a completed story.

        Checks recording decision and either:
        - Records new experience
        - Increments existing experience success count
        - Skips recording

        Args:
            story: Context from completed story
            error_context: Any error messages

        Returns:
            Tuple of (experience_id_or_empty, success, reason)
        """
        decision = self.should_record_story(story, error_context)

        if not decision.should_record:
            if decision.is_duplicate and decision.duplicate_id:
                # Increment success count of existing experience
                self.store.update_success_count(decision.duplicate_id)
                return decision.duplicate_id, True, f"Incremented existing experience (was duplicate)"

            return "", False, decision.reason

        exp_id, success = self.record_experience(
            problem=decision.problem_signature,
            solution=decision.solution_approach,
            domain_context=decision.domain_context,
            category="auto-recorded",
            tags=[f"story:{story.story_id}"],
        )

        if success:
            return exp_id, True, "Recorded new experience"
        else:
            return "", False, "Failed to store experience"

    def record_from_log_entry(self, entry: dict) -> Tuple[str, bool, str]:
        """Record experience from an execution log entry.

        Args:
            entry: JSON entry from execution_log.jsonl

        Returns:
            Tuple of (experience_id, success, reason)
        """
        story_id = entry.get('story_id', '')
        story_title = entry.get('story_title', '')
        error_msg = entry.get('error_message', '')

        # Get file changes from git
        added, removed, files = get_git_diff_stats(cwd=str(self.project_path))

        story = StoryContext(
            story_id=story_id,
            title=story_title,
            description="",
            acceptance_criteria=[],
            error_context=error_msg,
            files_changed=files,
            lines_added=added,
            lines_removed=removed,
        )

        return self.record_from_story(story, error_msg)


# ============================================================================
# PRD Parsing
# ============================================================================

def load_story_from_prd(prd_path: str, story_id: str) -> Optional[StoryContext]:
    """Load story context from a PRD file.

    Args:
        prd_path: Path to prd.json file
        story_id: Story ID to load

    Returns:
        StoryContext or None if not found
    """
    try:
        with open(prd_path, 'r') as f:
            prd = json.load(f)

        for story in prd.get('userStories', []):
            if story.get('id') == story_id:
                # Get file changes from git
                added, removed, files = get_git_diff_stats()

                return StoryContext(
                    story_id=story_id,
                    title=story.get('title', ''),
                    description=story.get('description', ''),
                    acceptance_criteria=story.get('acceptanceCriteria', []),
                    error_context="",
                    files_changed=files,
                    lines_added=added,
                    lines_removed=removed,
                )

        return None
    except (IOError, json.JSONDecodeError) as e:
        print(f"Error loading PRD: {e}", file=sys.stderr)
        return None


# ============================================================================
# CLI Interface
# ============================================================================

def cmd_detect_domain(args: argparse.Namespace) -> int:
    """Detect domain for current project."""
    recorder = ExperienceRecorder(
        project_path=args.path,
        use_embeddings=not args.no_embeddings,
    )
    result = recorder.detect_domain()

    if args.json:
        output = result.to_dict()
        output['domain_context'] = result.to_domain_context().to_dict()
        print(json.dumps(output, indent=2))
    else:
        print(f"Domain Detection:")
        print(f"  Project Type: {result.project_type}")
        print(f"  Language:     {result.language}")
        print(f"  Confidence:   {result.confidence} ({result.confidence_score:.0%})")
        if result.frameworks:
            print(f"  Frameworks:   {', '.join(result.frameworks[:5])}")

    return 0


def cmd_record_story(args: argparse.Namespace) -> int:
    """Record experience from a completed story."""
    story_id = args.story_id
    prd_path = args.prd or "prd.json"

    story = load_story_from_prd(prd_path, story_id)
    if not story:
        print(f"Story {story_id} not found in {prd_path}", file=sys.stderr)
        return 1

    recorder = ExperienceRecorder(
        project_path=args.path,
        db_dir=args.db_dir,
        use_embeddings=not args.no_embeddings,
    )

    exp_id, success, reason = recorder.record_from_story(story)

    if args.json:
        result = {
            "story_id": story_id,
            "experience_id": exp_id,
            "success": success,
            "reason": reason,
        }
        print(json.dumps(result, indent=2))
    else:
        if success:
            print(f"Experience recorded: {exp_id}")
            print(f"  Reason: {reason}")
        else:
            print(f"Not recorded: {reason}")

    return 0 if success else 1


def cmd_record_from_log(args: argparse.Namespace) -> int:
    """Record experience from an execution log entry."""
    log_file = Path(args.log_file)
    if not log_file.exists():
        print(f"Log file not found: {log_file}", file=sys.stderr)
        return 1

    try:
        with open(log_file, 'r') as f:
            lines = f.readlines()

        if args.index < 0 or args.index >= len(lines):
            print(f"Invalid log entry index: {args.index} (max: {len(lines) - 1})", file=sys.stderr)
            return 1

        entry = json.loads(lines[args.index])
    except (IOError, json.JSONDecodeError) as e:
        print(f"Error reading log: {e}", file=sys.stderr)
        return 1

    recorder = ExperienceRecorder(
        project_path=args.path,
        db_dir=args.db_dir,
        use_embeddings=not args.no_embeddings,
    )

    exp_id, success, reason = recorder.record_from_log_entry(entry)

    if args.json:
        result = {
            "log_index": args.index,
            "experience_id": exp_id,
            "success": success,
            "reason": reason,
        }
        print(json.dumps(result, indent=2))
    else:
        if success:
            print(f"Experience recorded: {exp_id}")
            print(f"  Reason: {reason}")
        else:
            print(f"Not recorded: {reason}")

    return 0


def cmd_record(args: argparse.Namespace) -> int:
    """Record an experience manually with auto-detected domain."""
    recorder = ExperienceRecorder(
        project_path=args.path,
        db_dir=args.db_dir,
        use_embeddings=not args.no_embeddings,
    )

    # Parse domain context if provided
    domain_context = None
    if args.domain:
        try:
            domain_data = json.loads(args.domain)
            domain_context = DomainContext(
                project_type=domain_data.get('project_type', 'other'),
                language=domain_data.get('language', ''),
                frameworks=domain_data.get('frameworks', []),
                tools_used=domain_data.get('tools_used', []),
            )
        except json.JSONDecodeError:
            print("Warning: Invalid domain JSON, using auto-detection", file=sys.stderr)

    exp_id, success = recorder.record_experience(
        problem=args.problem,
        solution=args.solution,
        domain_context=domain_context,
        category=args.category or "",
        tags=args.tags.split(',') if args.tags else None,
    )

    if args.json:
        result = {
            "experience_id": exp_id,
            "success": success,
        }
        print(json.dumps(result, indent=2))
    else:
        if success:
            print(f"Experience recorded: {exp_id}")
        else:
            print("Failed to record experience", file=sys.stderr)
            return 1

    return 0


def cmd_check_should_record(args: argparse.Namespace) -> int:
    """Check if a story should be recorded (dry-run)."""
    story_id = args.story_id
    prd_path = args.prd or "prd.json"

    story = load_story_from_prd(prd_path, story_id)
    if not story:
        print(f"Story {story_id} not found in {prd_path}", file=sys.stderr)
        return 1

    recorder = ExperienceRecorder(
        project_path=args.path,
        db_dir=args.db_dir,
        use_embeddings=not args.no_embeddings,
    )

    decision = recorder.should_record_story(story)

    if args.json:
        print(json.dumps(decision.to_dict(), indent=2))
    else:
        print(f"Recording Decision for {story_id}:")
        print(f"  Should Record: {decision.should_record}")
        print(f"  Reason:        {decision.reason}")
        print(f"  Lines Changed: {decision.lines_changed}")
        print(f"  Domain:        {decision.domain_context.project_type if decision.domain_context else 'unknown'}")
        print(f"  Confidence:    {decision.domain_confidence}")
        if decision.is_duplicate:
            print(f"  Duplicate Of:  {decision.duplicate_id}")

    return 0


def create_parser() -> argparse.ArgumentParser:
    """Create argument parser."""
    parent_parser = argparse.ArgumentParser(add_help=False)
    parent_parser.add_argument(
        "--path",
        default=".",
        help="Project path (default: current directory)",
    )
    parent_parser.add_argument(
        "--db-dir",
        default=DEFAULT_DB_DIR,
        help=f"Database directory (default: {DEFAULT_DB_DIR})",
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
    parent_parser.add_argument(
        "--no-embeddings",
        action="store_true",
        help="Use hash-based embeddings instead of sentence-transformers",
    )

    parser = argparse.ArgumentParser(
        description="Automatic Experience Recording for claude-loop",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        parents=[parent_parser],
    )

    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # detect-domain command
    subparsers.add_parser(
        "detect-domain",
        help="Detect domain for current project",
        parents=[parent_parser],
    )

    # record-story command
    story_parser = subparsers.add_parser(
        "record-story",
        help="Record experience from a completed story",
        parents=[parent_parser],
    )
    story_parser.add_argument("story_id", help="Story ID")
    story_parser.add_argument("--prd", help="Path to prd.json (default: prd.json)")

    # record-from-log command
    log_parser = subparsers.add_parser(
        "record-from-log",
        help="Record experience from execution log entry",
        parents=[parent_parser],
    )
    log_parser.add_argument("index", type=int, help="Log entry index (0-based)")
    log_parser.add_argument(
        "--log-file",
        default=EXECUTION_LOG_FILE,
        help=f"Execution log file (default: {EXECUTION_LOG_FILE})",
    )

    # record command
    record_parser = subparsers.add_parser(
        "record",
        help="Record an experience manually",
        parents=[parent_parser],
    )
    record_parser.add_argument("problem", help="Problem description")
    record_parser.add_argument("solution", help="Solution approach")
    record_parser.add_argument("--domain", help="Domain context as JSON")
    record_parser.add_argument("--category", help="Category for the experience")
    record_parser.add_argument("--tags", help="Comma-separated tags")

    # check command
    check_parser = subparsers.add_parser(
        "check",
        help="Check if a story should be recorded (dry-run)",
        parents=[parent_parser],
    )
    check_parser.add_argument("story_id", help="Story ID")
    check_parser.add_argument("--prd", help="Path to prd.json (default: prd.json)")

    return parser


def main() -> int:
    """Main entry point."""
    parser = create_parser()
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    commands = {
        "detect-domain": cmd_detect_domain,
        "record-story": cmd_record_story,
        "record-from-log": cmd_record_from_log,
        "record": cmd_record,
        "check": cmd_check_should_record,
    }

    handler = commands.get(args.command)
    if handler:
        return handler(args)

    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
