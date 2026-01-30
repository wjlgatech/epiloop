#!/usr/bin/env python3
"""
Benchmark Runner for Tier 1 Validation

Executes tasks across multiple subjects (baseline, claude-loop, agent-zero)
and collects comprehensive metrics for comparison.
"""

import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, List, Optional, Any
import tempfile
import shutil
import re


@dataclass
class BenchmarkMetrics:
    """Metrics collected from a single task execution."""
    success: bool
    wall_clock_seconds: float
    total_tokens: int
    estimated_cost_usd: float
    criteria_scores: Dict[str, float]  # AC_ID -> 0.0-1.0
    error_message: Optional[str] = None
    overall_score: float = 0.0

    def __post_init__(self):
        """Calculate overall score as weighted average of criteria scores."""
        if self.criteria_scores:
            self.overall_score = sum(self.criteria_scores.values()) / len(self.criteria_scores)
        else:
            self.overall_score = 1.0 if self.success else 0.0


@dataclass
class TaskDefinition:
    """Definition of a benchmark task."""
    task_id: str
    title: str
    description: str
    acceptance_criteria: List[str]
    # Additional fields from YAML
    context: Optional[Dict[str, Any]] = None
    fileScope: Optional[List[str]] = None


class BaselineAdapter:
    """
    Adapter for executing tasks using raw Claude Code CLI (baseline).

    This adapter invokes Claude Code directly via subprocess and captures
    metrics for comparison with other approaches.
    """

    def __init__(self, working_dir: Optional[Path] = None):
        """
        Initialize the BaselineAdapter.

        Args:
            working_dir: Directory for task execution. If None, uses temp directory.
        """
        self.working_dir = working_dir or Path(tempfile.mkdtemp(prefix="baseline_"))
        self.claude_code_path = self._find_claude_code_cli()

    def _find_claude_code_cli(self) -> str:
        """
        Find the Claude Code CLI executable.

        Returns:
            Path to Claude Code CLI

        Raises:
            RuntimeError: If Claude Code CLI is not found
        """
        # Try common locations
        candidates = [
            "claude",  # In PATH
            "/usr/local/bin/claude",
            "~/bin/claude",
        ]

        for candidate in candidates:
            try:
                result = subprocess.run(
                    [candidate, "--version"],
                    capture_output=True,
                    timeout=5,
                    check=False
                )
                if result.returncode == 0:
                    return candidate
            except (FileNotFoundError, subprocess.TimeoutExpired):
                continue

        raise RuntimeError(
            "Claude Code CLI not found. Please install Claude Code CLI first.\n"
            "Installation: https://github.com/anthropics/claude-code"
        )

    def execute_task(
        self,
        task: TaskDefinition,
        timeout_seconds: int = 300
    ) -> BenchmarkMetrics:
        """
        Execute a task using Claude Code CLI and capture metrics.

        Args:
            task: The task definition to execute
            timeout_seconds: Maximum execution time

        Returns:
            BenchmarkMetrics with captured performance data
        """
        print(f"\n{'='*60}")
        print(f"Executing {task.task_id}: {task.title}")
        print(f"{'='*60}\n")

        start_time = time.time()
        success = False
        error_message = None
        total_tokens = 0
        estimated_cost_usd = 0.0

        try:
            # Prepare task prompt from description + acceptance criteria
            prompt = self._format_task_prompt(task)

            # Execute Claude Code CLI
            result = subprocess.run(
                [
                    self.claude_code_path,
                    "chat",
                    "--message", prompt,
                    "--yes"  # Auto-accept prompts
                ],
                cwd=self.working_dir,
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
                check=False
            )

            elapsed_time = time.time() - start_time

            # Parse output for metrics
            stdout = result.stdout
            stderr = result.stderr

            # Extract token usage from output
            total_tokens = self._extract_token_usage(stdout + stderr)

            # Estimate cost (Sonnet 4.5 pricing: $3/M input, $15/M output)
            # Assume 50/50 split for baseline estimation
            estimated_cost_usd = (total_tokens / 1_000_000) * 9.0  # Average of $3 and $15

            # Check for success indicators in output
            if result.returncode == 0:
                success = True
            else:
                error_message = f"Command exited with code {result.returncode}"
                if stderr:
                    error_message += f": {stderr[:500]}"

            # Validate acceptance criteria
            criteria_scores = self._validate_acceptance_criteria(
                task,
                self.working_dir,
                stdout
            )

            # Consider task successful only if execution succeeded AND
            # acceptance criteria are met (>0.8 average)
            overall_score = sum(criteria_scores.values()) / len(criteria_scores) if criteria_scores else 0.0
            if overall_score < 0.8:
                success = False
                error_message = f"Acceptance criteria not met (score: {overall_score:.2f})"

            return BenchmarkMetrics(
                success=success,
                wall_clock_seconds=elapsed_time,
                total_tokens=total_tokens,
                estimated_cost_usd=estimated_cost_usd,
                criteria_scores=criteria_scores,
                error_message=error_message
            )

        except subprocess.TimeoutExpired:
            elapsed_time = time.time() - start_time
            return BenchmarkMetrics(
                success=False,
                wall_clock_seconds=elapsed_time,
                total_tokens=total_tokens,
                estimated_cost_usd=estimated_cost_usd,
                criteria_scores={},
                error_message=f"Task timed out after {timeout_seconds}s"
            )

        except Exception as e:
            elapsed_time = time.time() - start_time
            return BenchmarkMetrics(
                success=False,
                wall_clock_seconds=elapsed_time,
                total_tokens=total_tokens,
                estimated_cost_usd=estimated_cost_usd,
                criteria_scores={},
                error_message=f"Unexpected error: {str(e)}"
            )

    def _format_task_prompt(self, task: TaskDefinition) -> str:
        """
        Format task definition into a prompt for Claude Code.

        Args:
            task: The task definition

        Returns:
            Formatted prompt string
        """
        prompt = f"{task.description}\n\n"
        prompt += "Acceptance Criteria:\n"
        for i, criterion in enumerate(task.acceptance_criteria, 1):
            prompt += f"{i}. {criterion}\n"

        return prompt

    def _extract_token_usage(self, output: str) -> int:
        """
        Extract token usage from Claude Code output.

        Args:
            output: stdout/stderr from Claude Code CLI

        Returns:
            Total token count (0 if not found)
        """
        # Look for token usage patterns in output
        # Claude Code typically outputs something like "Tokens: 1234" or "1234 tokens"
        patterns = [
            r'(\d+)\s+tokens',
            r'tokens:\s*(\d+)',
            r'total.*?(\d+)',
        ]

        for pattern in patterns:
            match = re.search(pattern, output, re.IGNORECASE)
            if match:
                try:
                    return int(match.group(1))
                except (ValueError, IndexError):
                    continue

        # If no token usage found, estimate based on output length
        # Rough estimate: 1 token ≈ 4 characters
        return len(output) // 4

    def _validate_acceptance_criteria(
        self,
        task: TaskDefinition,
        working_dir: Path,
        output: str
    ) -> Dict[str, float]:
        """
        Validate acceptance criteria for the task.

        Args:
            task: The task definition
            working_dir: Directory where task was executed
            output: stdout from execution

        Returns:
            Dictionary mapping AC_ID to score (0.0-1.0)
        """
        scores = {}

        # For baseline implementation, use simple heuristics
        # Each task will have a dedicated validator script later (US-004)
        for i, criterion in enumerate(task.acceptance_criteria, 1):
            ac_id = f"AC-{i:03d}"

            # Default: assume criterion is met if execution succeeded
            # This is a placeholder - will be replaced by proper validators
            scores[ac_id] = 1.0

        return scores

    def cleanup(self):
        """Clean up temporary working directory."""
        if self.working_dir and self.working_dir.exists():
            if self.working_dir.name.startswith("baseline_"):
                shutil.rmtree(self.working_dir)


def load_task_definition(task_path: Path) -> TaskDefinition:
    """
    Load a task definition from YAML or JSON file.

    Args:
        task_path: Path to task definition file

    Returns:
        TaskDefinition object
    """
    import yaml

    with open(task_path, 'r') as f:
        if task_path.suffix in ['.yaml', '.yml']:
            data = yaml.safe_load(f)
        else:
            data = json.load(f)

    return TaskDefinition(
        task_id=data['task_id'],
        title=data['title'],
        description=data['description'],
        acceptance_criteria=data['acceptance_criteria'],
        context=data.get('context'),
        fileScope=data.get('fileScope')
    )


def save_results(
    task_id: str,
    subject: str,
    metrics: BenchmarkMetrics,
    output_dir: Path
):
    """
    Save benchmark results to JSON file.

    Args:
        task_id: Task identifier
        subject: Subject name (baseline, claude-loop, agent-zero)
        metrics: Captured metrics
        output_dir: Directory to save results
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    result_file = output_dir / f"{task_id}_{subject}.json"

    result_data = {
        "task_id": task_id,
        "subject": subject,
        "timestamp": time.time(),
        "metrics": asdict(metrics)
    }

    with open(result_file, 'w') as f:
        json.dump(result_data, f, indent=2)

    print(f"\nResults saved to: {result_file}")


def main():
    """Main entry point for benchmark runner."""
    # Parse command line arguments
    import argparse

    parser = argparse.ArgumentParser(description="Benchmark Runner for Tier 1 Validation")
    parser.add_argument("--task", help="Path to task definition file")
    parser.add_argument("--subject", choices=["baseline", "claude-loop", "agent-zero"],
                       default="baseline", help="Subject to test")
    parser.add_argument("--output-dir", type=Path, default=Path("benchmark-results"),
                       help="Output directory for results")
    parser.add_argument("--timeout", type=int, default=300,
                       help="Timeout in seconds")
    parser.add_argument("--real-execution", action="store_true",
                       help="Execute all tasks from benchmark-tasks/tasks/")

    args = parser.parse_args()

    if args.real_execution:
        # Execute all tasks
        tasks_dir = Path("benchmark-tasks/tasks")
        if not tasks_dir.exists():
            print(f"Error: Tasks directory not found: {tasks_dir}")
            sys.exit(1)

        task_files = sorted(tasks_dir.glob("*.yaml")) + sorted(tasks_dir.glob("*.json"))
        if not task_files:
            print(f"Error: No task files found in {tasks_dir}")
            sys.exit(1)

        print(f"\nExecuting {len(task_files)} tasks with subject: {args.subject}\n")

        for task_file in task_files:
            try:
                task = load_task_definition(task_file)

                if args.subject == "baseline":
                    adapter = BaselineAdapter()
                    metrics = adapter.execute_task(task, timeout_seconds=args.timeout)
                    adapter.cleanup()
                else:
                    print(f"Subject '{args.subject}' not yet implemented")
                    continue

                save_results(task.task_id, args.subject, metrics, args.output_dir)

                # Print summary
                print(f"\nSummary for {task.task_id}:")
                print(f"  Success: {metrics.success}")
                print(f"  Time: {metrics.wall_clock_seconds:.2f}s")
                print(f"  Tokens: {metrics.total_tokens}")
                print(f"  Cost: ${metrics.estimated_cost_usd:.4f}")
                print(f"  Score: {metrics.overall_score:.2f}")
                if metrics.error_message:
                    print(f"  Error: {metrics.error_message}")

            except Exception as e:
                print(f"Error processing {task_file}: {e}")
                continue

    elif args.task:
        # Execute single task
        task = load_task_definition(Path(args.task))

        if args.subject == "baseline":
            adapter = BaselineAdapter()
            metrics = adapter.execute_task(task, timeout_seconds=args.timeout)
            adapter.cleanup()
        else:
            print(f"Subject '{args.subject}' not yet implemented")
            sys.exit(1)

        save_results(task.task_id, args.subject, metrics, args.output_dir)

        # Print results
        print("\n" + "="*60)
        print("BENCHMARK RESULTS")
        print("="*60)
        print(json.dumps(asdict(metrics), indent=2))

    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
