#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
lib/dependency-graph.py - Dependency Graph Builder and Execution Planner

Builds a dependency graph from prd.json and creates an optimal execution plan
that groups independent stories into parallel batches.

Features:
- Topological sort for execution ordering
- Parallel batch grouping for independent stories
- Circular dependency detection with detailed error reporting
- Execution plan visualization

Usage:
    python3 lib/dependency-graph.py [command] [options]

Commands:
    plan [prd_file]           - Generate and display execution plan
    check-cycles [prd_file]   - Check for circular dependencies
    batches [prd_file]        - Output parallel batches as JSON
    visualize [prd_file]      - Show ASCII visualization of graph

Options:
    --json                    - Output in JSON format
    --incomplete-only         - Only include incomplete stories (passes=false)
    --verbose                 - Show detailed output
"""

import json
import sys
from collections import defaultdict, deque
from typing import Any


class DependencyGraph:
    """Manages story dependencies and execution planning."""

    def __init__(self, prd_data: dict):
        """Initialize graph from PRD data."""
        self.prd = prd_data
        self.stories = {s["id"]: s for s in prd_data.get("userStories", [])}
        self.graph: dict[str, list[str]] = {}  # story_id -> dependencies
        self.reverse_graph: dict[str, list[str]] = defaultdict(list)  # story_id -> dependents
        self._build_graph()

    def _build_graph(self) -> None:
        """Build adjacency lists for dependencies."""
        for story_id, story in self.stories.items():
            deps = story.get("dependencies", [])
            self.graph[story_id] = deps
            for dep in deps:
                self.reverse_graph[dep].append(story_id)

    def detect_cycles(self) -> list[list[str]] | None:
        """
        Detect circular dependencies using DFS with coloring.

        Returns:
            None if no cycles, otherwise a list of cycles found.
            Each cycle is a list of story IDs forming the cycle.
        """
        WHITE, GRAY, BLACK = 0, 1, 2
        color = {node: WHITE for node in self.graph}
        cycles = []

        def dfs(node: str, path: list[str]) -> None:
            color[node] = GRAY
            path.append(node)

            for neighbor in self.graph.get(node, []):
                if neighbor not in self.graph:
                    # Skip invalid dependencies
                    continue
                if color[neighbor] == GRAY:
                    # Found cycle
                    cycle_start = path.index(neighbor)
                    cycles.append(path[cycle_start:] + [neighbor])
                elif color[neighbor] == WHITE:
                    dfs(neighbor, path)

            color[node] = BLACK
            path.pop()

        for node in self.graph:
            if color[node] == WHITE:
                dfs(node, [])

        return cycles if cycles else None

    def topological_sort(self, incomplete_only: bool = False) -> list[str]:
        """
        Perform topological sort using Kahn's algorithm.

        Args:
            incomplete_only: If True, only include stories with passes=false

        Returns:
            List of story IDs in execution order

        Raises:
            ValueError: If circular dependency detected
        """
        # Filter stories if needed
        if incomplete_only:
            story_ids = {
                sid for sid, story in self.stories.items()
                if not story.get("passes", False)
            }
        else:
            story_ids = set(self.stories.keys())

        # Build in-degree map for filtered stories
        in_degree: dict[str, int] = {sid: 0 for sid in story_ids}
        for sid in story_ids:
            for dep in self.graph.get(sid, []):
                if dep in story_ids:
                    in_degree[sid] += 1

        # Start with nodes that have no dependencies (in filtered set)
        queue = deque([sid for sid, deg in in_degree.items() if deg == 0])
        result = []

        while queue:
            # Sort by priority to get deterministic order
            queue = deque(sorted(queue, key=lambda x: self.stories[x].get("priority", 999)))
            node = queue.popleft()
            result.append(node)

            # Reduce in-degree of dependents
            for dependent in self.reverse_graph.get(node, []):
                if dependent in story_ids:
                    in_degree[dependent] -= 1
                    if in_degree[dependent] == 0:
                        queue.append(dependent)

        if len(result) != len(story_ids):
            # Cycle detected
            remaining = story_ids - set(result)
            raise ValueError(f"Circular dependency detected involving: {remaining}")

        return result

    def get_parallel_batches(self, incomplete_only: bool = False) -> list[list[str]]:
        """
        Group stories into parallel execution batches.

        Stories in the same batch have no dependencies on each other
        and can be executed in parallel.

        Args:
            incomplete_only: If True, only include stories with passes=false

        Returns:
            List of batches, where each batch is a list of story IDs
            that can be executed in parallel.
        """
        # Filter stories if needed
        if incomplete_only:
            story_ids = {
                sid for sid, story in self.stories.items()
                if not story.get("passes", False)
            }
        else:
            story_ids = set(self.stories.keys())

        if not story_ids:
            return []

        # Build in-degree map for incomplete stories only
        in_degree: dict[str, int] = {}
        for sid in story_ids:
            # Count only dependencies that are in our working set
            deps_in_set = [d for d in self.graph.get(sid, []) if d in story_ids]
            in_degree[sid] = len(deps_in_set)

        batches: list[list[str]] = []
        remaining = set(story_ids)

        while remaining:
            # Find all stories with no remaining dependencies
            ready = [sid for sid in remaining if in_degree[sid] == 0]

            if not ready:
                # Shouldn't happen if no cycles, but handle gracefully
                raise ValueError(f"Circular dependency detected involving: {remaining}")

            # Sort by priority for deterministic ordering
            ready.sort(key=lambda x: self.stories[x].get("priority", 999))
            batches.append(ready)

            # Remove ready stories from remaining and update in-degrees
            for sid in ready:
                remaining.remove(sid)
                for dependent in self.reverse_graph.get(sid, []):
                    if dependent in remaining:
                        in_degree[dependent] -= 1

        return batches

    def get_execution_plan(self, incomplete_only: bool = True) -> dict[str, Any]:
        """
        Generate a complete execution plan.

        Returns:
            Dictionary with execution plan details including:
            - batches: List of parallel batches
            - total_stories: Total number of stories
            - sequential_steps: Number of sequential steps needed
            - max_parallelism: Maximum stories that can run in parallel
            - story_details: Details for each story in execution order
        """
        batches = self.get_parallel_batches(incomplete_only=incomplete_only)

        # Build story details
        story_details = []
        for batch_num, batch in enumerate(batches, 1):
            for story_id in batch:
                story = self.stories[story_id]
                story_details.append({
                    "id": story_id,
                    "title": story.get("title", ""),
                    "batch": batch_num,
                    "dependencies": story.get("dependencies", []),
                    "fileScope": story.get("fileScope", []),
                    "estimatedComplexity": story.get("estimatedComplexity", "medium"),
                    "suggestedModel": story.get("suggestedModel", "sonnet"),
                    "priority": story.get("priority", 999),
                })

        return {
            "batches": batches,
            "total_stories": sum(len(b) for b in batches),
            "sequential_steps": len(batches),
            "max_parallelism": max(len(b) for b in batches) if batches else 0,
            "story_details": story_details,
        }

    def visualize(self, incomplete_only: bool = False) -> str:
        """
        Generate ASCII visualization of the dependency graph.

        Args:
            incomplete_only: If True, only show incomplete stories

        Returns:
            ASCII art representation of the graph
        """
        batches = self.get_parallel_batches(incomplete_only=incomplete_only)

        if not batches:
            return "No stories to display."

        lines = []
        lines.append("Execution Plan Visualization")
        lines.append("=" * 60)
        lines.append("")

        for batch_num, batch in enumerate(batches, 1):
            lines.append(f"Batch {batch_num} (can run in parallel):")
            lines.append("-" * 40)

            for story_id in batch:
                story = self.stories[story_id]
                title = story.get("title", "Untitled")[:35]
                complexity = story.get("estimatedComplexity", "medium")
                model = story.get("suggestedModel", "sonnet")
                deps = story.get("dependencies", [])

                status = "[x]" if story.get("passes", False) else "[ ]"
                lines.append(f"  {status} {story_id}: {title}")
                lines.append(f"      Model: {model} | Complexity: {complexity}")
                if deps:
                    lines.append(f"      Depends on: {', '.join(deps)}")

            lines.append("")

        # Summary
        total = sum(len(b) for b in batches)
        max_par = max(len(b) for b in batches) if batches else 0
        lines.append("=" * 60)
        lines.append(f"Total: {total} stories in {len(batches)} sequential batches")
        lines.append(f"Max parallelism: {max_par} concurrent stories")
        lines.append(f"Speedup potential: {total / len(batches):.1f}x vs sequential")

        return "\n".join(lines)


def load_prd(prd_file: str) -> dict:
    """Load and parse PRD JSON file."""
    try:
        with open(prd_file, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"Error: PRD file not found: {prd_file}", file=sys.stderr)
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON in PRD file: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_plan(prd_file: str, json_output: bool = False,
             incomplete_only: bool = True, verbose: bool = False) -> None:
    """Generate and display execution plan."""
    prd = load_prd(prd_file)
    graph = DependencyGraph(prd)

    # Check for cycles first
    cycles = graph.detect_cycles()
    if cycles:
        print("Error: Circular dependencies detected:", file=sys.stderr)
        for cycle in cycles:
            print(f"  {' -> '.join(cycle)}", file=sys.stderr)
        sys.exit(1)

    plan = graph.get_execution_plan(incomplete_only=incomplete_only)

    if json_output:
        print(json.dumps(plan, indent=2))
    else:
        print(graph.visualize(incomplete_only=incomplete_only))
        if verbose:
            print("\nJSON Plan:")
            print(json.dumps(plan, indent=2))


def cmd_check_cycles(prd_file: str, json_output: bool = False) -> None:
    """Check for circular dependencies."""
    prd = load_prd(prd_file)
    graph = DependencyGraph(prd)

    cycles = graph.detect_cycles()

    if json_output:
        result = {"has_cycles": cycles is not None, "cycles": cycles or []}
        print(json.dumps(result, indent=2))
    else:
        if cycles:
            print("Circular dependencies detected:")
            for cycle in cycles:
                print(f"  {' -> '.join(cycle)}")
            sys.exit(1)
        else:
            print("No circular dependencies found.")


def cmd_batches(prd_file: str, incomplete_only: bool = True) -> None:
    """Output parallel batches as JSON."""
    prd = load_prd(prd_file)
    graph = DependencyGraph(prd)

    # Check for cycles first
    cycles = graph.detect_cycles()
    if cycles:
        print("Error: Circular dependencies detected:", file=sys.stderr)
        for cycle in cycles:
            print(f"  {' -> '.join(cycle)}", file=sys.stderr)
        sys.exit(1)

    batches = graph.get_parallel_batches(incomplete_only=incomplete_only)
    print(json.dumps(batches, indent=2))


def cmd_visualize(prd_file: str, incomplete_only: bool = False) -> None:
    """Show ASCII visualization of graph."""
    prd = load_prd(prd_file)
    graph = DependencyGraph(prd)
    print(graph.visualize(incomplete_only=incomplete_only))


def main():
    """Main entry point."""
    args = sys.argv[1:]

    if not args or args[0] in ["-h", "--help"]:
        print(__doc__)
        sys.exit(0)

    command = args[0]
    prd_file = "prd.json"
    json_output = False
    incomplete_only = False
    verbose = False

    # Parse remaining args
    i = 1
    while i < len(args):
        arg = args[i]
        if arg == "--json":
            json_output = True
        elif arg == "--incomplete-only":
            incomplete_only = True
        elif arg == "--verbose":
            verbose = True
        elif not arg.startswith("-"):
            prd_file = arg
        i += 1

    if command == "plan":
        # Default to incomplete_only=True for plan command
        cmd_plan(prd_file, json_output, incomplete_only=True, verbose=verbose)
    elif command == "check-cycles":
        cmd_check_cycles(prd_file, json_output)
    elif command == "batches":
        cmd_batches(prd_file, incomplete_only=incomplete_only)
    elif command == "visualize":
        cmd_visualize(prd_file, incomplete_only=incomplete_only)
    else:
        print(f"Unknown command: {command}", file=sys.stderr)
        print("Use --help for usage information.", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
