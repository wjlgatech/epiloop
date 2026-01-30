#!/usr/bin/env python3
"""
progress-dashboard.py - Visual Progress Dashboard for Claude-Loop

Displays a visual progress dashboard showing phases and stories with completion status.
Part of the Invisible Intelligence system (INV-006).

Features:
- Phase progress bar (e.g., 'Solutioning [=====>    ] 60%')
- Story list with status indicators (✓ complete, ▶ running, ○ pending)
- Auto-detected complexity level and track display
- Terminal color support with --no-color flag
- Updates after each story completion

Usage:
    python lib/progress-dashboard.py --prd prd.json
    python lib/progress-dashboard.py --prd prd.json --current-story US-001
    python lib/progress-dashboard.py --prd prd.json --no-color
    python lib/progress-dashboard.py --prd prd.json --json
"""

import argparse
import json
import os
import sys
from dataclasses import dataclass
from typing import Optional

# Try to import complexity detector
try:
    from importlib.util import spec_from_file_location, module_from_spec
    spec = spec_from_file_location(
        "complexity_detector",
        os.path.join(os.path.dirname(__file__), "complexity-detector.py")
    )
    if spec is not None and spec.loader is not None:
        complexity_detector = module_from_spec(spec)
        spec.loader.exec_module(complexity_detector)
        COMPLEXITY_DETECTOR_AVAILABLE = True
    else:
        COMPLEXITY_DETECTOR_AVAILABLE = False
        complexity_detector = None  # type: ignore
except Exception:
    COMPLEXITY_DETECTOR_AVAILABLE = False
    complexity_detector = None  # type: ignore


# ============================================================================
# Configuration
# ============================================================================

# Status indicators
STATUS_COMPLETE = "✓"
STATUS_RUNNING = "▶"
STATUS_PENDING = "○"
STATUS_FAILED = "✗"

# Progress bar characters
BAR_FILLED = "█"
BAR_ACTIVE = "▓"
BAR_EMPTY = "░"

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
class StoryStatus:
    """Status of a single story."""
    id: str
    title: str
    status: str  # pending, running, complete, failed
    priority: int
    notes: str = ""


@dataclass
class PhaseProgress:
    """Progress within a phase."""
    name: str
    stories_total: int
    stories_complete: int
    stories_running: int = 0
    is_current: bool = False

    @property
    def progress_percent(self) -> float:
        if self.stories_total == 0:
            return 0.0
        return (self.stories_complete / self.stories_total) * 100

    @property
    def is_complete(self) -> bool:
        return self.stories_complete >= self.stories_total


@dataclass
class DashboardData:
    """Complete dashboard data."""
    project_name: str
    branch_name: str
    complexity_level: int
    complexity_name: str
    track: str
    phases: list[PhaseProgress]
    stories: list[StoryStatus]
    current_phase: str = ""
    current_story: str = ""
    total_stories: int = 0
    complete_stories: int = 0
    running_stories: int = 0


# ============================================================================
# Dashboard Functions
# ============================================================================

def load_prd(prd_path: str) -> dict:
    """Load PRD JSON file."""
    with open(prd_path, 'r') as f:
        return json.load(f)


def get_story_status(story: dict, current_story_id: Optional[str] = None) -> str:
    """Determine story status."""
    if story.get("passes", False):
        return "complete"
    elif current_story_id and story.get("id") == current_story_id:
        return "running"
    else:
        return "pending"


def analyze_prd(prd_data: dict, current_story_id: Optional[str] = None) -> DashboardData:
    """Analyze PRD and build dashboard data."""

    project_name = prd_data.get("project", "Unknown Project")
    branch_name = prd_data.get("branchName", "")
    user_stories = prd_data.get("userStories", [])

    # Detect complexity
    complexity_level = 2
    complexity_name = "medium"
    track = "standard"
    phases = ["implementation"]

    if COMPLEXITY_DETECTOR_AVAILABLE and complexity_detector is not None:
        prd_text = prd_data.get("description", "") + " " + json.dumps(user_stories)
        result = complexity_detector.detect_complexity(prd_text)
        complexity_level = result.level
        complexity_name = result.level_name
        track = complexity_detector.get_track(complexity_level)
        phases = complexity_detector.get_phases(complexity_level)

    # Build story statuses
    stories = []
    complete_count = 0
    running_count = 0

    for story in user_stories:
        status = get_story_status(story, current_story_id)
        stories.append(StoryStatus(
            id=story.get("id", ""),
            title=story.get("title", ""),
            status=status,
            priority=story.get("priority", 99),
            notes=story.get("notes", ""),
        ))
        if status == "complete":
            complete_count += 1
        elif status == "running":
            running_count += 1

    # Sort stories by priority
    stories.sort(key=lambda s: s.priority)

    # Calculate phase progress
    # For simplicity, we distribute stories evenly across phases
    # In a more sophisticated implementation, stories could be tagged with phases
    total_stories = len(stories)
    phase_progress_list = []

    if len(phases) == 1:
        # Single phase (implementation only)
        phase_progress_list.append(PhaseProgress(
            name=phases[0],
            stories_total=total_stories,
            stories_complete=complete_count,
            stories_running=running_count,
            is_current=True,
        ))
    else:
        # Multiple phases - distribute stories proportionally
        # For simplicity: all stories are in implementation phase
        # Other phases have artificial progress based on completion ratio
        for i, phase_name in enumerate(phases):
            if phase_name == "implementation":
                # Implementation phase tracks actual stories
                phase_progress_list.append(PhaseProgress(
                    name=phase_name,
                    stories_total=total_stories,
                    stories_complete=complete_count,
                    stories_running=running_count,
                    is_current=running_count > 0 or (complete_count < total_stories and complete_count > 0),
                ))
            else:
                # Pre-implementation phases are complete if any implementation started
                is_complete = complete_count > 0 or running_count > 0
                phase_progress_list.append(PhaseProgress(
                    name=phase_name,
                    stories_total=1,
                    stories_complete=1 if is_complete else 0,
                    stories_running=0 if is_complete else (1 if i == 0 and complete_count == 0 else 0),
                    is_current=not is_complete and i == len(phases) - 2,
                ))

    # Determine current phase
    current_phase = ""
    for phase in phase_progress_list:
        if phase.is_current:
            current_phase = phase.name
            break
    if not current_phase and phase_progress_list:
        # Default to last incomplete phase
        for phase in phase_progress_list:
            if not phase.is_complete:
                current_phase = phase.name
                break
        if not current_phase:
            current_phase = phase_progress_list[-1].name

    return DashboardData(
        project_name=project_name,
        branch_name=branch_name,
        complexity_level=complexity_level,
        complexity_name=complexity_name,
        track=track,
        phases=phase_progress_list,
        stories=stories,
        current_phase=current_phase,
        current_story=current_story_id or "",
        total_stories=total_stories,
        complete_stories=complete_count,
        running_stories=running_count,
    )


def render_progress_bar(
    progress_percent: float,
    width: int = 30,
    filled_char: str = BAR_FILLED,
    active_char: str = BAR_ACTIVE,
    empty_char: str = BAR_EMPTY,
    is_active: bool = False,
) -> str:
    """Render a progress bar string."""
    filled = int(progress_percent * width / 100)
    active = 1 if is_active and filled < width else 0
    empty = width - filled - active

    bar = filled_char * filled + active_char * active + empty_char * empty
    return f"[{bar}]"


def render_dashboard(
    data: DashboardData,
    colors: dict = COLORS,
    show_stories: bool = True,
    max_stories: int = 15,
) -> str:
    """Render the dashboard as a string."""
    lines = []
    c = colors  # Shorthand

    # Header
    lines.append("")
    lines.append(f"{c['cyan']}{'═' * 65}{c['reset']}")
    lines.append(f"{c['cyan']}{'CLAUDE-LOOP PROGRESS DASHBOARD':^65}{c['reset']}")
    lines.append(f"{c['cyan']}{'═' * 65}{c['reset']}")
    lines.append("")

    # Project info
    lines.append(f"  {c['bold']}Project:{c['reset']}    {data.project_name}")
    if data.branch_name:
        lines.append(f"  {c['bold']}Branch:{c['reset']}     {data.branch_name}")

    # Complexity and track info
    level_color = c['green'] if data.complexity_level <= 1 else (c['yellow'] if data.complexity_level <= 2 else c['red'])
    lines.append(f"  {c['bold']}Complexity:{c['reset']} {level_color}Level {data.complexity_level} ({data.complexity_name}){c['reset']}")
    lines.append(f"  {c['bold']}Track:{c['reset']}      {c['magenta']}{data.track.title()}{c['reset']}")

    lines.append("")

    # Phase progress
    lines.append(f"  {c['bold']}Phases:{c['reset']}")
    for phase in data.phases:
        status_indicator = STATUS_COMPLETE if phase.is_complete else (STATUS_RUNNING if phase.is_current else STATUS_PENDING)
        status_color = c['green'] if phase.is_complete else (c['yellow'] if phase.is_current else c['dim'])

        bar = render_progress_bar(phase.progress_percent, width=20, is_active=phase.is_current)
        percent_str = f"{phase.progress_percent:.0f}%"

        lines.append(
            f"    {status_color}{status_indicator}{c['reset']} {phase.name.title():15} {bar} {percent_str:>4}"
        )

    lines.append("")

    # Overall progress
    overall_percent = (data.complete_stories / data.total_stories * 100) if data.total_stories > 0 else 0
    overall_bar = render_progress_bar(overall_percent, width=30, is_active=data.running_stories > 0)

    lines.append(f"  {c['bold']}Overall Progress:{c['reset']}")
    lines.append(f"    {overall_bar} {overall_percent:.0f}%")
    lines.append(f"    {c['green']}{data.complete_stories}{c['reset']}/{data.total_stories} stories complete")
    if data.running_stories > 0:
        lines.append(f"    {c['yellow']}{data.running_stories}{c['reset']} story running")

    lines.append("")

    # Story list
    if show_stories and data.stories:
        lines.append(f"  {c['bold']}Stories:{c['reset']}")

        displayed = 0
        for story in data.stories:
            if displayed >= max_stories:
                remaining = len(data.stories) - displayed
                lines.append(f"    {c['dim']}... and {remaining} more{c['reset']}")
                break

            if story.status == "complete":
                indicator = f"{c['green']}{STATUS_COMPLETE}{c['reset']}"
                title_color = c['dim']
            elif story.status == "running":
                indicator = f"{c['yellow']}{STATUS_RUNNING}{c['reset']}"
                title_color = c['bold']
            elif story.status == "failed":
                indicator = f"{c['red']}{STATUS_FAILED}{c['reset']}"
                title_color = c['red']
            else:
                indicator = f"{c['dim']}{STATUS_PENDING}{c['reset']}"
                title_color = ""

            # Truncate title if too long
            title = story.title[:40] + "..." if len(story.title) > 43 else story.title

            lines.append(f"    {indicator} {story.id:10} {title_color}{title}{c['reset']}")
            displayed += 1

    lines.append("")
    lines.append(f"{c['cyan']}{'═' * 65}{c['reset']}")
    lines.append("")

    return "\n".join(lines)


def render_compact(data: DashboardData, colors: dict = COLORS) -> str:
    """Render a compact single-line progress indicator."""
    c = colors

    overall_percent = (data.complete_stories / data.total_stories * 100) if data.total_stories > 0 else 0
    bar = render_progress_bar(overall_percent, width=20, is_active=data.running_stories > 0)

    status = f"{c['cyan']}[PROGRESS]{c['reset']} "
    status += f"{bar} "
    status += f"{data.complete_stories}/{data.total_stories} "

    if data.running_stories > 0:
        status += f"| {c['yellow']}▶ {data.current_story}{c['reset']}"
    elif data.complete_stories >= data.total_stories:
        status += f"| {c['green']}COMPLETE{c['reset']}"

    return status


def to_json(data: DashboardData) -> str:
    """Convert dashboard data to JSON."""
    output = {
        "project_name": data.project_name,
        "branch_name": data.branch_name,
        "complexity": {
            "level": data.complexity_level,
            "name": data.complexity_name,
        },
        "track": data.track,
        "phases": [
            {
                "name": p.name,
                "stories_total": p.stories_total,
                "stories_complete": p.stories_complete,
                "stories_running": p.stories_running,
                "progress_percent": p.progress_percent,
                "is_current": p.is_current,
                "is_complete": p.is_complete,
            }
            for p in data.phases
        ],
        "stories": [
            {
                "id": s.id,
                "title": s.title,
                "status": s.status,
                "priority": s.priority,
            }
            for s in data.stories
        ],
        "summary": {
            "total_stories": data.total_stories,
            "complete_stories": data.complete_stories,
            "running_stories": data.running_stories,
            "progress_percent": (data.complete_stories / data.total_stories * 100) if data.total_stories > 0 else 0,
            "current_phase": data.current_phase,
            "current_story": data.current_story,
        },
    }
    return json.dumps(output, indent=2)


# ============================================================================
# CLI
# ============================================================================

def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Display visual progress dashboard for claude-loop",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  progress-dashboard.py --prd prd.json
  progress-dashboard.py --prd prd.json --current-story US-001
  progress-dashboard.py --prd prd.json --no-color
  progress-dashboard.py --prd prd.json --compact
  progress-dashboard.py --prd prd.json --json
""",
    )

    parser.add_argument(
        "--prd",
        required=True,
        help="Path to PRD JSON file",
    )
    parser.add_argument(
        "--current-story",
        help="ID of currently running story",
    )
    parser.add_argument(
        "--no-color",
        action="store_true",
        help="Disable terminal colors",
    )
    parser.add_argument(
        "--compact",
        action="store_true",
        help="Show compact single-line progress",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output as JSON",
    )
    parser.add_argument(
        "--max-stories",
        type=int,
        default=15,
        help="Maximum stories to display (default: 15)",
    )
    parser.add_argument(
        "--no-stories",
        action="store_true",
        help="Hide individual story list",
    )

    args = parser.parse_args()

    # Load PRD
    try:
        prd_data = load_prd(args.prd)
    except FileNotFoundError:
        print(f"Error: PRD file not found: {args.prd}", file=sys.stderr)
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON in PRD file: {e}", file=sys.stderr)
        sys.exit(1)

    # Analyze PRD
    dashboard_data = analyze_prd(prd_data, args.current_story)

    # Select output format
    if args.json:
        print(to_json(dashboard_data))
    elif args.compact:
        colors = NO_COLORS if args.no_color else COLORS
        print(render_compact(dashboard_data, colors))
    else:
        colors = NO_COLORS if args.no_color else COLORS
        print(render_dashboard(
            dashboard_data,
            colors,
            show_stories=not args.no_stories,
            max_stories=args.max_stories,
        ))


if __name__ == "__main__":
    main()
