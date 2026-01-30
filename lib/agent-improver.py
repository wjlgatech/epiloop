#!/usr/bin/env python3
"""
agent-improver.py - Agent Improvement Suggestions for claude-loop

Analyzes progress.txt and AGENTS.md to identify patterns and generate
improvement suggestions for AI agents.

Identifies:
- Common failures and error patterns
- Missing capabilities
- Repeated manual interventions
- Performance bottlenecks
- Knowledge gaps

Usage:
    python lib/agent-improver.py <run_directory>
    python lib/agent-improver.py .claude-loop/runs/20260110_163000

Output:
    Creates improvements.json in the specified run directory
    Returns JSON with improvement suggestions
"""

import json
import os
import re
import sys
from collections import Counter
from typing import Any


def load_json_file(filepath: str) -> dict[str, Any] | None:
    """Load and parse a JSON file."""
    try:
        with open(filepath, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"Warning: Could not load {filepath}: {e}", file=sys.stderr)
        return None


def load_text_file(filepath: str) -> str:
    """Load a text file."""
    try:
        with open(filepath, "r") as f:
            return f.read()
    except FileNotFoundError:
        return ""


def parse_progress_txt(content: str) -> list[dict[str, Any]]:
    """Parse progress.txt to extract iteration history."""
    iterations = []

    # Split by iteration headers
    iteration_pattern = r"### Iteration: (.+?)\n"
    sections = re.split(iteration_pattern, content)

    # Process each iteration section
    for i in range(1, len(sections), 2):
        if i + 1 >= len(sections):
            break

        timestamp = sections[i].strip()
        section_content = sections[i + 1]

        # Extract story info
        story_match = re.search(r"\*\*Story\*\*: (.+)", section_content)
        status_match = re.search(r"\*\*Status\*\*: (.+)", section_content)

        # Extract what was implemented
        impl_match = re.search(
            r"\*\*What was implemented\*\*:\n((?:- .+\n?)+)",
            section_content
        )
        implementations = []
        if impl_match:
            implementations = [
                line.strip("- ").strip()
                for line in impl_match.group(1).strip().split("\n")
                if line.strip()
            ]

        # Extract files changed
        files_match = re.search(
            r"\*\*Files changed\*\*:\n((?:- .+\n?)+)",
            section_content
        )
        files = []
        if files_match:
            files = [
                line.strip("- ").strip()
                for line in files_match.group(1).strip().split("\n")
                if line.strip()
            ]

        # Extract learnings
        learnings_match = re.search(
            r"\*\*Learnings for future iterations\*\*:\n((?:- .+\n?)+)",
            section_content
        )
        learnings = []
        if learnings_match:
            learnings = [
                line.strip("- ").strip()
                for line in learnings_match.group(1).strip().split("\n")
                if line.strip()
            ]

        iterations.append({
            "timestamp": timestamp,
            "story": story_match.group(1) if story_match else "Unknown",
            "status": status_match.group(1) if status_match else "Unknown",
            "implementations": implementations,
            "files": files,
            "learnings": learnings,
            "raw_content": section_content,
        })

    return iterations


def parse_agents_md(content: str) -> dict[str, Any]:
    """Parse AGENTS.md to extract documented patterns."""
    patterns = {
        "commands": [],
        "gotchas": [],
        "discovered_patterns": [],
        "project_structure": "",
    }

    # Extract project structure
    structure_match = re.search(
        r"## Project Structure\s+```\n([\s\S]*?)```",
        content
    )
    if structure_match:
        patterns["project_structure"] = structure_match.group(1).strip()

    # Extract common commands
    commands_match = re.search(
        r"## Common Commands\s+```bash\n([\s\S]*?)```",
        content
    )
    if commands_match:
        patterns["commands"] = commands_match.group(1).strip().split("\n")

    # Extract gotchas
    gotchas_section = re.search(
        r"## Gotchas & Warnings\s+([\s\S]*?)(?=##|$)",
        content
    )
    if gotchas_section:
        gotcha_items = re.findall(r"- (.+)", gotchas_section.group(1))
        patterns["gotchas"] = gotcha_items

    # Extract discovered patterns
    discovered_section = re.search(
        r"## Discovered Patterns\s+([\s\S]*?)(?=##|$)",
        content
    )
    if discovered_section:
        # Find all subsections
        subsections = re.findall(
            r"### (.+?)\n([\s\S]*?)(?=###|##|$)",
            discovered_section.group(1)
        )
        for title, content_block in subsections:
            patterns["discovered_patterns"].append({
                "title": title.strip(),
                "content": content_block.strip(),
            })

    return patterns


def analyze_failure_patterns(
    iterations: list[dict[str, Any]],
    metrics: dict[str, Any] | None
) -> list[dict[str, Any]]:
    """Identify common failure patterns from iterations and metrics."""
    failures = []
    error_keywords = [
        "error", "fail", "block", "bug", "issue", "fix",
        "wrong", "incorrect", "missing", "not found", "crash"
    ]

    # Analyze iteration content for failures
    for iteration in iterations:
        status = iteration.get("status", "").lower()
        if status in ("failed", "error", "blocked"):
            failures.append({
                "story": iteration.get("story", "Unknown"),
                "status": status,
                "timestamp": iteration.get("timestamp", ""),
                "context": iteration.get("raw_content", "")[:500],
            })

        # Look for error mentions in learnings
        for learning in iteration.get("learnings", []):
            learning_lower = learning.lower()
            if any(kw in learning_lower for kw in error_keywords):
                failures.append({
                    "type": "learning_from_error",
                    "story": iteration.get("story", "Unknown"),
                    "learning": learning,
                })

    # Analyze metrics for failed iterations
    if metrics:
        metrics_iterations = metrics.get("iterations", [])
        for it in metrics_iterations:
            status = it.get("status", "").lower()
            if status in ("failed", "error", "blocked"):
                failures.append({
                    "type": "metrics_failure",
                    "story_id": it.get("story_id", "Unknown"),
                    "status": status,
                    "duration_ms": it.get("duration_ms", 0),
                    "agents_used": it.get("agents_used", ""),
                })

    return failures


def analyze_capability_gaps(
    iterations: list[dict[str, Any]],
    agents_patterns: dict[str, Any],
) -> list[dict[str, Any]]:
    """Identify missing capabilities from learnings and patterns."""
    gaps = []
    capability_keywords = [
        "couldn't", "can't", "unable to", "missing", "needed",
        "should have", "would be better", "requires", "need to"
    ]

    # Collect all learnings
    all_learnings = []
    for iteration in iterations:
        all_learnings.extend(iteration.get("learnings", []))

    # Find capability gap mentions
    for learning in all_learnings:
        learning_lower = learning.lower()
        for keyword in capability_keywords:
            if keyword in learning_lower:
                gaps.append({
                    "type": "capability_gap",
                    "description": learning,
                    "keyword_trigger": keyword,
                })
                break

    # Analyze gotchas as potential gaps
    for gotcha in agents_patterns.get("gotchas", []):
        gaps.append({
            "type": "gotcha_gap",
            "description": gotcha,
        })

    return gaps


def analyze_performance_patterns(
    metrics: dict[str, Any] | None
) -> dict[str, Any]:
    """Analyze performance patterns from metrics."""
    perf_analysis = {
        "avg_duration_ms": 0,
        "max_duration_ms": 0,
        "min_duration_ms": 0,
        "high_cost_iterations": [],
        "slow_iterations": [],
        "total_cost": 0,
        "avg_cost_per_iteration": 0,
    }

    if not metrics:
        return perf_analysis

    iterations = metrics.get("iterations", [])
    if not iterations:
        return perf_analysis

    durations = [it.get("duration_ms", 0) for it in iterations]
    costs = [it.get("cost_usd", 0) for it in iterations]

    if durations:
        perf_analysis["avg_duration_ms"] = sum(durations) / len(durations)
        perf_analysis["max_duration_ms"] = max(durations)
        perf_analysis["min_duration_ms"] = min(durations)

    if costs:
        perf_analysis["total_cost"] = sum(costs)
        perf_analysis["avg_cost_per_iteration"] = sum(costs) / len(costs)

    # Find outliers (iterations taking >2x average)
    avg_duration = perf_analysis["avg_duration_ms"]
    avg_cost = perf_analysis["avg_cost_per_iteration"]

    for it in iterations:
        if it.get("duration_ms", 0) > avg_duration * 2:
            perf_analysis["slow_iterations"].append({
                "story_id": it.get("story_id", "Unknown"),
                "duration_ms": it.get("duration_ms", 0),
                "vs_avg": it.get("duration_ms", 0) / avg_duration if avg_duration else 0,
            })
        if it.get("cost_usd", 0) > avg_cost * 2:
            perf_analysis["high_cost_iterations"].append({
                "story_id": it.get("story_id", "Unknown"),
                "cost_usd": it.get("cost_usd", 0),
                "vs_avg": it.get("cost_usd", 0) / avg_cost if avg_cost else 0,
            })

    return perf_analysis


def generate_improvement_suggestions(
    failures: list[dict[str, Any]],
    gaps: list[dict[str, Any]],
    performance: dict[str, Any],
    iterations: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Generate actionable improvement suggestions."""
    suggestions = []

    # Suggestion ID counter
    suggestion_id = 1

    # Analyze failure patterns for suggestions
    failure_count = len([f for f in failures if f.get("type") != "learning_from_error"])
    if failure_count > 0:
        suggestions.append({
            "id": f"IMP-{suggestion_id:03d}",
            "category": "reliability",
            "priority": "high",
            "title": "Add error recovery mechanisms",
            "description": f"Found {failure_count} failed/blocked iterations. Consider adding retry logic and better error handling.",
            "action_items": [
                "Implement automatic retry for transient failures",
                "Add checkpoint/resume capability for long operations",
                "Create fallback strategies for common failure modes",
            ],
        })
        suggestion_id += 1

    # Analyze capability gaps
    unique_gaps = list({g.get("description", ""): g for g in gaps}.values())
    if unique_gaps:
        suggestions.append({
            "id": f"IMP-{suggestion_id:03d}",
            "category": "capabilities",
            "priority": "medium",
            "title": "Address capability gaps",
            "description": f"Found {len(unique_gaps)} potential capability gaps in learnings.",
            "action_items": [g.get("description", "") for g in unique_gaps[:5]],  # Top 5
        })
        suggestion_id += 1

    # Analyze performance
    if performance.get("slow_iterations"):
        suggestions.append({
            "id": f"IMP-{suggestion_id:03d}",
            "category": "performance",
            "priority": "medium",
            "title": "Optimize slow iterations",
            "description": f"Found {len(performance['slow_iterations'])} iterations taking >2x average time.",
            "action_items": [
                f"Investigate {s['story_id']} ({s['duration_ms']}ms - {s['vs_avg']:.1f}x avg)"
                for s in performance.get("slow_iterations", [])[:3]
            ],
        })
        suggestion_id += 1

    if performance.get("high_cost_iterations"):
        suggestions.append({
            "id": f"IMP-{suggestion_id:03d}",
            "category": "cost",
            "priority": "medium",
            "title": "Reduce token usage in high-cost iterations",
            "description": f"Found {len(performance['high_cost_iterations'])} iterations with >2x average cost.",
            "action_items": [
                "Review context size for high-cost iterations",
                "Consider chunking large operations",
                "Optimize prompts to reduce token usage",
            ],
        })
        suggestion_id += 1

    # Analyze learnings for common themes
    all_learnings = []
    for iteration in iterations:
        all_learnings.extend(iteration.get("learnings", []))

    if all_learnings:
        # Find commonly mentioned concepts
        word_counts: Counter[str] = Counter()
        tech_keywords = [
            "python", "bash", "json", "api", "file", "error", "test",
            "import", "function", "class", "module", "install", "config",
            "database", "network", "auth", "cache", "async", "sync"
        ]
        for learning in all_learnings:
            words = learning.lower().split()
            for word in words:
                word = re.sub(r"[^a-z]", "", word)
                if word in tech_keywords:
                    word_counts[word] += 1

        common_topics = word_counts.most_common(5)
        if common_topics:
            suggestions.append({
                "id": f"IMP-{suggestion_id:03d}",
                "category": "knowledge",
                "priority": "low",
                "title": "Document frequently encountered topics",
                "description": "These topics appear frequently in learnings and may benefit from dedicated documentation.",
                "action_items": [
                    f"Create documentation for '{topic}' patterns ({count} mentions)"
                    for topic, count in common_topics
                ],
            })
            suggestion_id += 1

    # Add general best practices if few suggestions
    if len(suggestions) < 3:
        suggestions.append({
            "id": f"IMP-{suggestion_id:03d}",
            "category": "best_practice",
            "priority": "low",
            "title": "Continue following best practices",
            "description": "The current run shows good patterns. Consider these enhancements.",
            "action_items": [
                "Add more detailed acceptance criteria to user stories",
                "Include time estimates for better planning",
                "Document edge cases encountered during implementation",
            ],
        })
        suggestion_id += 1

    return suggestions


def generate_agents_md_updates(
    iterations: list[dict[str, Any]],
    current_patterns: dict[str, Any],
) -> list[dict[str, Any]]:
    """Generate suggested updates to AGENTS.md."""
    updates = []

    # Collect all learnings that might be worth adding to AGENTS.md
    all_learnings = []
    for iteration in iterations:
        all_learnings.extend(iteration.get("learnings", []))

    # Filter learnings that look like reusable patterns
    pattern_keywords = [
        "always", "never", "use", "avoid", "prefer", "must",
        "should", "works", "doesn't work", "instead of"
    ]

    for learning in all_learnings:
        learning_lower = learning.lower()
        if any(kw in learning_lower for kw in pattern_keywords):
            # Check if already in AGENTS.md
            already_documented = False
            for pattern in current_patterns.get("discovered_patterns", []):
                if learning.lower()[:30] in pattern.get("content", "").lower():
                    already_documented = True
                    break

            for gotcha in current_patterns.get("gotchas", []):
                if learning.lower()[:30] in gotcha.lower():
                    already_documented = True
                    break

            if not already_documented:
                updates.append({
                    "type": "new_pattern",
                    "content": learning,
                    "suggested_section": "Discovered Patterns"
                    if "use" in learning_lower or "prefer" in learning_lower
                    else "Gotchas & Warnings",
                })

    return updates


def main():
    """Main entry point."""
    if len(sys.argv) < 2:
        print("Usage: python lib/agent-improver.py <run_directory>")
        print("Example: python lib/agent-improver.py .claude-loop/runs/20260110_163000")
        sys.exit(1)

    run_dir = sys.argv[1]

    if not os.path.isdir(run_dir):
        print(f"Error: Run directory not found: {run_dir}", file=sys.stderr)
        sys.exit(1)

    # Load data files
    metrics_file = os.path.join(run_dir, "metrics.json")

    # Look for AGENTS.md and progress.txt in the project root
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(run_dir)))
    if not project_root:
        project_root = "."

    agents_file = os.path.join(project_root, "AGENTS.md")
    progress_file = os.path.join(project_root, "progress.txt")

    # If not found in computed root, try current directory
    if not os.path.exists(agents_file):
        agents_file = "AGENTS.md"
    if not os.path.exists(progress_file):
        progress_file = "progress.txt"

    print(f"Analyzing run directory: {run_dir}", file=sys.stderr)
    print(f"Loading metrics from: {metrics_file}", file=sys.stderr)
    print(f"Loading AGENTS.md from: {agents_file}", file=sys.stderr)
    print(f"Loading progress from: {progress_file}", file=sys.stderr)

    # Load and parse data
    metrics = load_json_file(metrics_file)
    agents_content = load_text_file(agents_file)
    progress_content = load_text_file(progress_file)

    # Parse content
    iterations = parse_progress_txt(progress_content)
    agents_patterns = parse_agents_md(agents_content)

    # Run analysis
    failures = analyze_failure_patterns(iterations, metrics)
    gaps = analyze_capability_gaps(iterations, agents_patterns)
    performance = analyze_performance_patterns(metrics)
    suggestions = generate_improvement_suggestions(
        failures, gaps, performance, iterations
    )
    agents_updates = generate_agents_md_updates(iterations, agents_patterns)

    # Build output
    output = {
        "analysis_timestamp": __import__("datetime").datetime.now().isoformat(),
        "run_directory": run_dir,
        "summary": {
            "total_iterations_analyzed": len(iterations),
            "failures_found": len(failures),
            "capability_gaps_found": len(gaps),
            "suggestions_generated": len(suggestions),
            "agents_md_updates_suggested": len(agents_updates),
        },
        "performance": {
            "avg_duration_ms": performance.get("avg_duration_ms", 0),
            "total_cost_usd": performance.get("total_cost", 0),
            "avg_cost_per_iteration": performance.get("avg_cost_per_iteration", 0),
            "slow_iterations_count": len(performance.get("slow_iterations", [])),
            "high_cost_iterations_count": len(performance.get("high_cost_iterations", [])),
        },
        "improvement_suggestions": suggestions,
        "agents_md_updates": agents_updates,
        "failure_details": failures[:10],  # Limit to first 10
        "capability_gaps": gaps[:10],  # Limit to first 10
    }

    # Save to improvements.json
    improvements_file = os.path.join(run_dir, "improvements.json")
    with open(improvements_file, "w") as f:
        json.dump(output, f, indent=2)

    print(f"\nImprovements saved: {improvements_file}", file=sys.stderr)

    # Also output to stdout for easy consumption
    print(json.dumps(output, indent=2))
    return improvements_file


if __name__ == "__main__":
    main()
