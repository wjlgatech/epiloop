#!/usr/bin/env python3
"""
Completion Summary Generator for Claude-Loop (INV-010)

Generates comprehensive completion summary listing all generated artifacts and metrics
at the end of claude-loop execution.

Summary includes:
- Stories completed, commits made, tests added
- Generated artifacts: architecture.md, ADRs, new files
- Execution metrics: total time, iterations used, agents invoked
- Complexity level, track, and phases that were auto-selected

Usage:
    # Generate summary from PRD and session state
    python3 completion-summary.py generate --prd prd.json
    python3 completion-summary.py generate --prd prd.json --json

    # Generate summary from session state file
    python3 completion-summary.py generate --session .claude-loop/session-state.json

    # Show summary with specific run metrics
    python3 completion-summary.py generate --prd prd.json --metrics .claude-loop/runs/*/metrics.json
"""

import argparse
import importlib.util
import json
import os
import subprocess
import sys
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Optional


def _load_module(name: str, filename: str):
    """Helper to load a module from file."""
    try:
        spec = importlib.util.spec_from_file_location(
            name,
            os.path.join(os.path.dirname(__file__), filename)
        )
        if spec is not None and spec.loader is not None:
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            return module
    except Exception:
        pass
    return None


# Try to import complexity detector
complexity_detector = _load_module("complexity_detector", "complexity-detector.py")
COMPLEXITY_DETECTOR_AVAILABLE = complexity_detector is not None

# Try to import quality gates
quality_gates = _load_module("quality_gates", "quality-gates.py")
QUALITY_GATES_AVAILABLE = quality_gates is not None


# ============================================================================
# Configuration
# ============================================================================

# Terminal colors (ANSI escape codes)
COLORS = {
    "reset": "\033[0m",
    "bold": "\033[1m",
    "dim": "\033[2m",
    "red": "\033[0;31m",
    "green": "\033[0;32m",
    "yellow": "\033[1;33m",
    "blue": "\033[0;34m",
    "magenta": "\033[0;35m",
    "cyan": "\033[0;36m",
    "white": "\033[0;37m",
}

# No-color mode colors (all empty)
NO_COLORS = {key: "" for key in COLORS}


# ============================================================================
# Data Classes
# ============================================================================

@dataclass
class StoryMetrics:
    """Metrics for a completed story."""
    id: str
    title: str
    completed: bool
    commit_hash: str = ""
    tests_added: int = 0
    files_changed: int = 0


@dataclass
class ExecutionMetrics:
    """Execution performance metrics."""
    total_duration_ms: int = 0
    iterations_used: int = 0
    agents_invoked: list = field(default_factory=list)
    tokens_in: int = 0
    tokens_out: int = 0
    cost_usd: float = 0.0
    model_usage: dict = field(default_factory=dict)  # model -> count


@dataclass
class ArtifactInfo:
    """Information about a generated artifact."""
    path: str
    artifact_type: str  # architecture, adr, source, test, config
    created_at: str = ""
    size_bytes: int = 0


@dataclass
class AutoDetectionInfo:
    """Auto-detected project settings."""
    complexity_level: int = 2
    complexity_name: str = "medium"
    track: str = "standard"
    phases: list = field(default_factory=list)
    quality_gates: list = field(default_factory=list)


@dataclass
class CompletionSummary:
    """Complete summary of a claude-loop run."""
    project_name: str
    branch_name: str
    completed_at: str

    # Story metrics
    stories_total: int = 0
    stories_completed: int = 0
    stories_failed: int = 0
    story_details: list = field(default_factory=list)  # List[StoryMetrics]

    # Commit metrics
    commits_made: int = 0
    commit_hashes: list = field(default_factory=list)

    # Artifact metrics
    artifacts_generated: list = field(default_factory=list)  # List[ArtifactInfo]
    files_created: int = 0
    files_modified: int = 0
    tests_added: int = 0

    # Execution metrics
    execution: ExecutionMetrics = field(default_factory=ExecutionMetrics)

    # Auto-detection info
    auto_detection: AutoDetectionInfo = field(default_factory=AutoDetectionInfo)

    # Status
    success: bool = True
    status_message: str = ""

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "project_name": self.project_name,
            "branch_name": self.branch_name,
            "completed_at": self.completed_at,
            "stories": {
                "total": self.stories_total,
                "completed": self.stories_completed,
                "failed": self.stories_failed,
                "details": [asdict(s) for s in self.story_details] if self.story_details else [],
            },
            "commits": {
                "count": self.commits_made,
                "hashes": self.commit_hashes,
            },
            "artifacts": {
                "count": len(self.artifacts_generated),
                "files_created": self.files_created,
                "files_modified": self.files_modified,
                "tests_added": self.tests_added,
                "details": [asdict(a) for a in self.artifacts_generated] if self.artifacts_generated else [],
            },
            "execution": asdict(self.execution),
            "auto_detection": asdict(self.auto_detection),
            "success": self.success,
            "status_message": self.status_message,
        }


# ============================================================================
# Core Functions
# ============================================================================

def load_prd(prd_path: str) -> dict:
    """Load PRD JSON file."""
    with open(prd_path, 'r') as f:
        return json.load(f)


def load_session_state(session_path: str) -> dict:
    """Load session state JSON file."""
    with open(session_path, 'r') as f:
        return json.load(f)


def load_metrics(metrics_path: str) -> dict:
    """Load metrics JSON file from a run."""
    with open(metrics_path, 'r') as f:
        return json.load(f)


def get_git_commits(branch_name: str, since: Optional[str] = None) -> list[dict]:
    """Get commits made on the branch."""
    commits = []
    try:
        # Build git log command
        cmd = ["git", "log", "--format=%H|%s|%ai", branch_name]
        if since:
            cmd.append(f"--since={since}")
        cmd.append("--no-merges")

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=10,
        )

        if result.returncode == 0:
            for line in result.stdout.strip().split('\n'):
                if '|' in line:
                    parts = line.split('|')
                    if len(parts) >= 3:
                        commits.append({
                            "hash": parts[0][:8],
                            "message": parts[1],
                            "date": parts[2],
                        })
    except Exception:
        pass

    return commits


def get_files_changed_since(commit_hash: str) -> tuple[list[str], list[str]]:
    """Get files created and modified since a commit."""
    created = []
    modified = []

    try:
        result = subprocess.run(
            ["git", "diff", "--name-status", commit_hash, "HEAD"],
            capture_output=True,
            text=True,
            timeout=10,
        )

        if result.returncode == 0:
            for line in result.stdout.strip().split('\n'):
                if line:
                    parts = line.split('\t')
                    if len(parts) >= 2:
                        status, filepath = parts[0], parts[1]
                        if status == 'A':
                            created.append(filepath)
                        elif status in ('M', 'R', 'C'):
                            modified.append(filepath)
    except Exception:
        pass

    return created, modified


def detect_artifacts(project_dir: str = ".") -> list[ArtifactInfo]:
    """Detect generated artifacts in the project."""
    artifacts = []

    # Check for architecture documentation
    arch_paths = [
        "docs/architecture/architecture.md",
        "docs/architecture.md",
        "architecture.md",
        "ARCHITECTURE.md",
    ]

    for path in arch_paths:
        full_path = os.path.join(project_dir, path)
        if os.path.exists(full_path):
            stat = os.stat(full_path)
            artifacts.append(ArtifactInfo(
                path=path,
                artifact_type="architecture",
                created_at=datetime.fromtimestamp(stat.st_mtime).isoformat(),
                size_bytes=stat.st_size,
            ))

    # Check for ADRs
    adr_dirs = [
        "docs/adrs",
        "docs/adr",
        "adrs",
        "adr",
    ]

    for adr_dir in adr_dirs:
        full_dir = os.path.join(project_dir, adr_dir)
        if os.path.isdir(full_dir):
            for filename in os.listdir(full_dir):
                if filename.endswith('.md'):
                    full_path = os.path.join(full_dir, filename)
                    stat = os.stat(full_path)
                    artifacts.append(ArtifactInfo(
                        path=os.path.join(adr_dir, filename),
                        artifact_type="adr",
                        created_at=datetime.fromtimestamp(stat.st_mtime).isoformat(),
                        size_bytes=stat.st_size,
                    ))

    return artifacts


def count_tests_in_file(filepath: str) -> int:
    """Count test functions in a file."""
    test_count = 0
    try:
        with open(filepath, 'r') as f:
            content = f.read()
            # Python tests
            test_count += content.count('def test_')
            test_count += content.count('async def test_')
            # JavaScript/TypeScript tests
            test_count += content.count('it(')
            test_count += content.count('test(')
            test_count += content.count('describe(')
    except Exception:
        pass
    return test_count


def analyze_prd(prd_data: dict) -> tuple[list[StoryMetrics], int, int, int]:
    """Analyze PRD to get story metrics."""
    stories = []
    total = 0
    completed = 0
    failed = 0

    for story in prd_data.get("userStories", []):
        total += 1
        story_completed = story.get("passes", False)

        if story_completed:
            completed += 1
        else:
            failed += 1

        stories.append(StoryMetrics(
            id=story.get("id", ""),
            title=story.get("title", ""),
            completed=story_completed,
            commit_hash=story.get("notes", "").split()[-1] if story.get("notes", "").startswith("Implemented in commit") else "",
        ))

    return stories, total, completed, failed


def get_auto_detection_info(prd_data: dict) -> AutoDetectionInfo:
    """Get auto-detected project settings."""
    info = AutoDetectionInfo()

    if COMPLEXITY_DETECTOR_AVAILABLE and complexity_detector is not None:
        try:
            prd_text = prd_data.get("description", "") + " " + json.dumps(prd_data.get("userStories", []))
            result = complexity_detector.detect_complexity(prd_text)
            info.complexity_level = result.level
            info.complexity_name = result.level_name
            info.track = complexity_detector.get_track(info.complexity_level)
            info.phases = complexity_detector.get_phases(info.complexity_level)
        except Exception:
            pass

    if QUALITY_GATES_AVAILABLE and quality_gates is not None:
        try:
            gates = quality_gates.get_gates(info.complexity_level)
            info.quality_gates = [g.name for g in gates.get_enabled_gates()]
        except Exception:
            pass

    return info


def generate_completion_summary(
    prd_path: Optional[str] = None,
    session_path: Optional[str] = None,
    metrics_path: Optional[str] = None,
    project_dir: str = ".",
) -> CompletionSummary:
    """
    Generate a comprehensive completion summary.

    Args:
        prd_path: Path to PRD JSON file
        session_path: Path to session state JSON file
        metrics_path: Path to metrics JSON file
        project_dir: Project directory for artifact detection

    Returns:
        CompletionSummary with all gathered metrics
    """
    summary = CompletionSummary(
        project_name="",
        branch_name="",
        completed_at=datetime.now(timezone.utc).isoformat(),
    )

    # Load PRD data
    prd_data = {}
    if prd_path and os.path.exists(prd_path):
        prd_data = load_prd(prd_path)
        summary.project_name = prd_data.get("project", "Unknown")
        summary.branch_name = prd_data.get("branchName", "")

    # Load session state
    if session_path and os.path.exists(session_path):
        session_data = load_session_state(session_path)
        if not summary.project_name:
            summary.project_name = session_data.get("project", "Unknown")
        if not summary.branch_name:
            summary.branch_name = session_data.get("branch", "")
        summary.execution.iterations_used = session_data.get("current_iteration", 0)

    # Analyze stories
    if prd_data:
        story_details, total, completed, failed = analyze_prd(prd_data)
        summary.story_details = story_details
        summary.stories_total = total
        summary.stories_completed = completed
        summary.stories_failed = failed

    # Get commits
    if summary.branch_name:
        commits = get_git_commits(summary.branch_name)
        summary.commits_made = len(commits)
        summary.commit_hashes = [c["hash"] for c in commits[:20]]  # Limit to last 20

    # Detect artifacts
    summary.artifacts_generated = detect_artifacts(project_dir)

    # Load metrics if available
    if metrics_path and os.path.exists(metrics_path):
        metrics = load_metrics(metrics_path)

        # Parse metrics file
        if "iterations" in metrics:
            summary.execution.iterations_used = len(metrics["iterations"])

            # Aggregate from iterations
            total_tokens_in = 0
            total_tokens_out = 0
            agents_used = set()

            for iteration in metrics["iterations"]:
                total_tokens_in += iteration.get("tokens_in", 0)
                total_tokens_out += iteration.get("tokens_out", 0)
                if "agents" in iteration:
                    agents_used.update(iteration["agents"])

            summary.execution.tokens_in = total_tokens_in
            summary.execution.tokens_out = total_tokens_out
            summary.execution.agents_invoked = list(agents_used)

        if "summary" in metrics:
            metrics_summary = metrics["summary"]
            summary.execution.total_duration_ms = metrics_summary.get("total_duration_ms", 0)
            summary.execution.cost_usd = metrics_summary.get("total_cost_usd", 0.0)
            if "model_counts" in metrics_summary:
                summary.execution.model_usage = metrics_summary["model_counts"]

    # Get auto-detection info
    if prd_data:
        summary.auto_detection = get_auto_detection_info(prd_data)

    # Count files and tests
    if summary.artifacts_generated:
        for artifact in summary.artifacts_generated:
            if artifact.artifact_type in ("source", "test"):
                summary.tests_added += count_tests_in_file(
                    os.path.join(project_dir, artifact.path)
                )

    # Determine success status
    summary.success = summary.stories_completed == summary.stories_total and summary.stories_total > 0
    if summary.success:
        summary.status_message = f"All {summary.stories_total} stories completed successfully"
    elif summary.stories_total == 0:
        summary.status_message = "No stories found in PRD"
    else:
        summary.status_message = f"{summary.stories_completed}/{summary.stories_total} stories completed"

    return summary


# ============================================================================
# Rendering Functions
# ============================================================================

def format_duration(ms: int) -> str:
    """Format duration in milliseconds to human-readable string."""
    if ms < 1000:
        return f"{ms}ms"
    elif ms < 60000:
        return f"{ms / 1000:.1f}s"
    elif ms < 3600000:
        mins = ms // 60000
        secs = (ms % 60000) // 1000
        return f"{mins}m {secs}s"
    else:
        hours = ms // 3600000
        mins = (ms % 3600000) // 60000
        return f"{hours}h {mins}m"


def format_tokens(tokens: int) -> str:
    """Format token count to human-readable string."""
    if tokens < 1000:
        return str(tokens)
    elif tokens < 1000000:
        return f"{tokens / 1000:.1f}K"
    else:
        return f"{tokens / 1000000:.2f}M"


def format_cost(cost: float) -> str:
    """Format cost in USD."""
    if cost < 0.01:
        return f"${cost:.4f}"
    elif cost < 1:
        return f"${cost:.2f}"
    else:
        return f"${cost:.2f}"


def render_completion_summary(
    summary: CompletionSummary,
    colors: dict = COLORS,
    verbose: bool = False,
) -> str:
    """
    Render the completion summary as a formatted string.

    Args:
        summary: CompletionSummary to render
        colors: Color dictionary for ANSI codes
        verbose: Include detailed information

    Returns:
        Formatted string for terminal display
    """
    c = colors
    lines = []

    # Header
    lines.append("")
    lines.append(f"{c['cyan']}{'=' * 70}{c['reset']}")
    lines.append(f"{c['cyan']}{'CLAUDE-LOOP COMPLETION SUMMARY':^70}{c['reset']}")
    lines.append(f"{c['cyan']}{'=' * 70}{c['reset']}")
    lines.append("")

    # Project Info
    lines.append(f"  {c['bold']}Project:{c['reset']}     {summary.project_name}")
    if summary.branch_name:
        lines.append(f"  {c['bold']}Branch:{c['reset']}      {summary.branch_name}")
    lines.append(f"  {c['bold']}Completed:{c['reset']}   {summary.completed_at[:19].replace('T', ' ')}")

    lines.append("")
    lines.append(f"{c['cyan']}{'─' * 70}{c['reset']}")

    # Status
    status_color = c['green'] if summary.success else c['yellow']
    status_icon = "✓" if summary.success else "⚠"
    lines.append(f"  {c['bold']}Status:{c['reset']}      {status_color}{status_icon} {summary.status_message}{c['reset']}")

    lines.append("")
    lines.append(f"{c['cyan']}{'─' * 70}{c['reset']}")

    # Story Metrics
    lines.append(f"  {c['bold']}STORIES{c['reset']}")
    lines.append(f"    Total:        {summary.stories_total}")
    lines.append(f"    Completed:    {c['green']}{summary.stories_completed}{c['reset']}")
    if summary.stories_failed > 0:
        lines.append(f"    Remaining:    {c['yellow']}{summary.stories_failed}{c['reset']}")

    if verbose and summary.story_details:
        lines.append("")
        lines.append(f"    {c['dim']}Story Details:{c['reset']}")
        for story in summary.story_details[:10]:  # Limit to 10
            icon = f"{c['green']}✓{c['reset']}" if story.completed else f"{c['yellow']}○{c['reset']}"
            lines.append(f"      {icon} {story.id}: {story.title[:40]}")

    lines.append("")
    lines.append(f"{c['cyan']}{'─' * 70}{c['reset']}")

    # Commit Metrics
    lines.append(f"  {c['bold']}COMMITS{c['reset']}")
    lines.append(f"    Made:         {summary.commits_made}")
    if verbose and summary.commit_hashes:
        lines.append(f"    {c['dim']}Recent: {', '.join(summary.commit_hashes[:5])}{c['reset']}")

    lines.append("")
    lines.append(f"{c['cyan']}{'─' * 70}{c['reset']}")

    # Artifacts
    lines.append(f"  {c['bold']}ARTIFACTS{c['reset']}")
    lines.append(f"    Generated:    {len(summary.artifacts_generated)}")

    # Group artifacts by type
    artifact_types = {}
    for artifact in summary.artifacts_generated:
        artifact_types.setdefault(artifact.artifact_type, []).append(artifact)

    for atype, artifacts in artifact_types.items():
        lines.append(f"    {atype.title()}:  {len(artifacts)}")
        if verbose:
            for artifact in artifacts[:3]:
                lines.append(f"      {c['dim']}- {artifact.path}{c['reset']}")

    if summary.tests_added > 0:
        lines.append(f"    Tests Added:  {c['green']}{summary.tests_added}{c['reset']}")

    lines.append("")
    lines.append(f"{c['cyan']}{'─' * 70}{c['reset']}")

    # Execution Metrics
    lines.append(f"  {c['bold']}EXECUTION{c['reset']}")
    if summary.execution.total_duration_ms > 0:
        lines.append(f"    Duration:     {format_duration(summary.execution.total_duration_ms)}")
    lines.append(f"    Iterations:   {summary.execution.iterations_used}")

    if summary.execution.tokens_in > 0 or summary.execution.tokens_out > 0:
        lines.append(f"    Tokens:       {format_tokens(summary.execution.tokens_in)} in / {format_tokens(summary.execution.tokens_out)} out")

    if summary.execution.cost_usd > 0:
        lines.append(f"    Cost:         {format_cost(summary.execution.cost_usd)}")

    if summary.execution.agents_invoked:
        lines.append(f"    Agents Used:  {', '.join(summary.execution.agents_invoked[:5])}")
        if len(summary.execution.agents_invoked) > 5:
            lines.append(f"                  {c['dim']}...and {len(summary.execution.agents_invoked) - 5} more{c['reset']}")

    if summary.execution.model_usage:
        model_str = ", ".join(f"{k}: {v}" for k, v in summary.execution.model_usage.items())
        lines.append(f"    Models:       {model_str}")

    lines.append("")
    lines.append(f"{c['cyan']}{'─' * 70}{c['reset']}")

    # Auto-Detection Info
    lines.append(f"  {c['bold']}AUTO-DETECTION{c['reset']}")
    level_color = c['green'] if summary.auto_detection.complexity_level <= 1 else (
        c['yellow'] if summary.auto_detection.complexity_level <= 2 else c['red']
    )
    lines.append(f"    Complexity:   {level_color}Level {summary.auto_detection.complexity_level} ({summary.auto_detection.complexity_name}){c['reset']}")
    lines.append(f"    Track:        {c['magenta']}{summary.auto_detection.track.title()}{c['reset']}")

    if summary.auto_detection.phases:
        lines.append(f"    Phases:       {', '.join(p.title() for p in summary.auto_detection.phases)}")

    if summary.auto_detection.quality_gates:
        lines.append(f"    Gates:        {', '.join(summary.auto_detection.quality_gates)}")

    # Footer
    lines.append("")
    lines.append(f"{c['cyan']}{'=' * 70}{c['reset']}")
    lines.append("")

    return "\n".join(lines)


def render_completion_compact(
    summary: CompletionSummary,
    colors: dict = COLORS,
) -> str:
    """Render a compact single-line completion summary."""
    c = colors

    status_icon = "✓" if summary.success else "⚠"
    status_color = c['green'] if summary.success else c['yellow']

    parts = [
        f"{c['cyan']}[COMPLETE]{c['reset']}",
        f"{status_color}{status_icon}{c['reset']}",
        f"{summary.stories_completed}/{summary.stories_total} stories",
        f"{summary.commits_made} commits",
        f"{summary.execution.iterations_used} iterations",
    ]

    if summary.execution.total_duration_ms > 0:
        parts.append(format_duration(summary.execution.total_duration_ms))

    if summary.execution.cost_usd > 0:
        parts.append(format_cost(summary.execution.cost_usd))

    return " | ".join(parts)


# ============================================================================
# CLI
# ============================================================================

def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Generate completion summary for claude-loop runs",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  completion-summary.py generate --prd prd.json
  completion-summary.py generate --prd prd.json --json
  completion-summary.py generate --prd prd.json --verbose
  completion-summary.py generate --session .claude-loop/session-state.json
""",
    )

    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # generate command
    gen_parser = subparsers.add_parser("generate", help="Generate completion summary")
    gen_parser.add_argument(
        "--prd",
        help="Path to PRD JSON file",
    )
    gen_parser.add_argument(
        "--session",
        help="Path to session state JSON file",
    )
    gen_parser.add_argument(
        "--metrics",
        help="Path to metrics JSON file",
    )
    gen_parser.add_argument(
        "--project-dir",
        default=".",
        help="Project directory for artifact detection",
    )
    gen_parser.add_argument(
        "--json",
        action="store_true",
        help="Output as JSON",
    )
    gen_parser.add_argument(
        "--compact",
        action="store_true",
        help="Output compact single-line summary",
    )
    gen_parser.add_argument(
        "--no-color",
        action="store_true",
        help="Disable terminal colors",
    )
    gen_parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Include detailed information",
    )

    args = parser.parse_args()

    if args.command == "generate":
        # Validate inputs
        if not args.prd and not args.session:
            print("Error: At least one of --prd or --session is required", file=sys.stderr)
            sys.exit(1)

        # Generate summary
        summary = generate_completion_summary(
            prd_path=args.prd,
            session_path=args.session,
            metrics_path=args.metrics,
            project_dir=args.project_dir,
        )

        # Output
        if args.json:
            print(json.dumps(summary.to_dict(), indent=2))
        elif args.compact:
            colors = NO_COLORS if args.no_color else COLORS
            print(render_completion_compact(summary, colors))
        else:
            colors = NO_COLORS if args.no_color else COLORS
            print(render_completion_summary(summary, colors, args.verbose))

    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
