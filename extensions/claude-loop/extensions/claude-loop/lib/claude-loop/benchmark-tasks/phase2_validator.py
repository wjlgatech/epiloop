#!/usr/bin/env python3
"""
Phase 2 Validation Runner

Executes benchmark tasks with different Phase 2 feature configurations:
- Phase 1 Baseline (all Phase 2 features disabled)
- Phase 2 with MCP
- Phase 2 with Multi-Provider
- Phase 2 with Delegation
- Phase 2 with All Features

Collects metrics for each configuration and generates comparison report.
"""

import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass, asdict, field
from pathlib import Path
from typing import Dict, List, Optional, Any
import tempfile
import shutil
import yaml
from datetime import datetime


@dataclass
class Phase2Metrics:
    """Metrics collected from a single task execution with Phase 2 features."""
    success: bool
    wall_clock_seconds: float
    total_tokens: int
    estimated_cost_usd: float
    criteria_scores: Dict[str, float]  # AC_ID -> 0.0-1.0
    configuration: str  # "phase1", "mcp", "multi-provider", "delegation", "all"
    features_used: List[str]  # Which features were actually used
    error_message: Optional[str] = None
    overall_score: float = 0.0
    delegation_depth: int = 0  # Max delegation depth reached
    provider_breakdown: Dict[str, int] = field(default_factory=dict)  # provider -> token count
    mcp_tools_used: List[str] = field(default_factory=list)  # MCP tools invoked

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
    complexity: str  # simple, medium, complex
    estimated_hours: float
    context: Optional[Dict[str, Any]] = None
    fileScope: Optional[List[str]] = None


class Phase2Executor:
    """
    Executor for running tasks with different Phase 2 feature configurations.
    """

    def __init__(self, working_dir: Optional[Path] = None):
        """
        Initialize the Phase2Executor.

        Args:
            working_dir: Directory for task execution. If None, uses temp directory.
        """
        self.working_dir = working_dir or Path(tempfile.mkdtemp(prefix="phase2_validation_"))
        self.claude_loop_path = Path(__file__).parent.parent / "claude-loop.sh"

        if not self.claude_loop_path.exists():
            raise RuntimeError(f"claude-loop.sh not found at {self.claude_loop_path}")

    def execute_task(
        self,
        task: TaskDefinition,
        configuration: str,
        timeout_seconds: int = 600
    ) -> Phase2Metrics:
        """
        Execute a task with specified Phase 2 configuration.

        Args:
            task: Task definition to execute
            configuration: One of: "phase1", "mcp", "multi-provider", "delegation", "all"
            timeout_seconds: Maximum execution time

        Returns:
            Phase2Metrics with execution results
        """
        print(f"\n{'='*80}")
        print(f"Executing {task.task_id} with configuration: {configuration}")
        print(f"Title: {task.title}")
        print(f"Complexity: {task.complexity}")
        print(f"{'='*80}\n")

        # Create task-specific working directory
        task_dir = self.working_dir / f"{task.task_id}_{configuration}"
        task_dir.mkdir(parents=True, exist_ok=True)

        # Build command with feature flags
        cmd = self._build_command(task, configuration, task_dir)

        # Execute task
        start_time = time.time()
        try:
            result = subprocess.run(
                cmd,
                cwd=task_dir,
                capture_output=True,
                text=True,
                timeout=timeout_seconds
            )
            wall_clock_seconds = time.time() - start_time
            success = result.returncode == 0

            # Extract metrics from output
            metrics = self._extract_metrics(
                result.stdout,
                result.stderr,
                task,
                configuration,
                wall_clock_seconds,
                success
            )

            # Save execution log
            self._save_execution_log(task_dir, task, configuration, result, metrics)

            return metrics

        except subprocess.TimeoutExpired:
            wall_clock_seconds = timeout_seconds
            return Phase2Metrics(
                success=False,
                wall_clock_seconds=wall_clock_seconds,
                total_tokens=0,
                estimated_cost_usd=0.0,
                criteria_scores={},
                configuration=configuration,
                features_used=[],
                error_message=f"Timeout after {timeout_seconds} seconds"
            )

        except Exception as e:
            wall_clock_seconds = time.time() - start_time
            return Phase2Metrics(
                success=False,
                wall_clock_seconds=wall_clock_seconds,
                total_tokens=0,
                estimated_cost_usd=0.0,
                criteria_scores={},
                configuration=configuration,
                features_used=[],
                error_message=str(e)
            )

    def _build_command(
        self,
        task: TaskDefinition,
        configuration: str,
        task_dir: Path
    ) -> List[str]:
        """Build claude-loop command with appropriate feature flags."""

        # Create minimal PRD for the task
        prd = self._create_task_prd(task, task_dir)

        cmd = [str(self.claude_loop_path), "--prd", str(prd)]

        # Add feature flags based on configuration
        if configuration == "phase1":
            # All Phase 2 features disabled (default)
            pass
        elif configuration == "mcp":
            cmd.extend(["--enable-mcp"])
        elif configuration == "multi-provider":
            cmd.extend(["--enable-multi-provider"])
        elif configuration == "delegation":
            cmd.extend(["--enable-delegation"])
        elif configuration == "all":
            cmd.extend([
                "--enable-mcp",
                "--enable-multi-provider",
                "--enable-delegation"
            ])
        else:
            raise ValueError(f"Unknown configuration: {configuration}")

        return cmd

    def _create_task_prd(self, task: TaskDefinition, task_dir: Path) -> Path:
        """Create a PRD file for the task."""
        prd_path = task_dir / "prd.json"

        prd = {
            "project": task.task_id.lower(),
            "branchName": f"feature/{task.task_id.lower()}",
            "description": task.description,
            "userStories": [
                {
                    "id": "US-001",
                    "title": task.title,
                    "description": task.description,
                    "acceptanceCriteria": task.acceptance_criteria,
                    "priority": 1,
                    "estimatedComplexity": task.complexity,
                    "fileScope": task.fileScope or [],
                    "passes": False,
                    "notes": ""
                }
            ]
        }

        with open(prd_path, 'w') as f:
            json.dump(prd, f, indent=2)

        return prd_path

    def _extract_metrics(
        self,
        stdout: str,
        stderr: str,
        task: TaskDefinition,
        configuration: str,
        wall_clock_seconds: float,
        success: bool
    ) -> Phase2Metrics:
        """Extract metrics from execution output."""

        # Parse token usage
        total_tokens = self._extract_token_count(stdout + stderr)

        # Estimate cost (using Sonnet pricing as baseline)
        # TODO: Parse actual provider usage for accurate costs
        cost_per_1k_tokens = 0.003  # Sonnet baseline
        estimated_cost_usd = (total_tokens / 1000.0) * cost_per_1k_tokens

        # Extract features used
        features_used = self._extract_features_used(stdout + stderr, configuration)

        # Extract delegation depth
        delegation_depth = self._extract_delegation_depth(stdout + stderr)

        # Extract MCP tools used
        mcp_tools_used = self._extract_mcp_tools(stdout + stderr)

        # Extract provider breakdown
        provider_breakdown = self._extract_provider_breakdown(stdout + stderr)

        # For now, assume all criteria met if success=True
        # TODO: Implement proper validation
        criteria_scores = {
            f"AC-{i+1:03d}": 1.0 if success else 0.0
            for i in range(len(task.acceptance_criteria))
        }

        return Phase2Metrics(
            success=success,
            wall_clock_seconds=wall_clock_seconds,
            total_tokens=total_tokens,
            estimated_cost_usd=estimated_cost_usd,
            criteria_scores=criteria_scores,
            configuration=configuration,
            features_used=features_used,
            delegation_depth=delegation_depth,
            provider_breakdown=provider_breakdown,
            mcp_tools_used=mcp_tools_used
        )

    def _extract_token_count(self, output: str) -> int:
        """Extract total token count from output."""
        # Look for patterns like "tokens: 1234" or "1234 tokens"
        import re
        patterns = [
            r'total[_\s]+tokens[:\s]+(\d+)',
            r'(\d+)\s+tokens',
            r'tokens[:\s]+(\d+)'
        ]

        for pattern in patterns:
            match = re.search(pattern, output, re.IGNORECASE)
            if match:
                return int(match.group(1))

        return 0

    def _extract_features_used(self, output: str, configuration: str) -> List[str]:
        """Extract which Phase 2 features were actually used."""
        features = []

        if "mcp" in configuration.lower() or configuration == "all":
            if "MCP tool" in output or "[use-mcp:" in output:
                features.append("mcp")

        if "multi-provider" in configuration or configuration == "all":
            if any(p in output for p in ["GPT-4", "Claude", "Gemini", "DeepSeek"]):
                features.append("multi-provider")

        if "delegation" in configuration or configuration == "all":
            if "[delegate:" in output or "delegation depth" in output:
                features.append("delegation")

        return features

    def _extract_delegation_depth(self, output: str) -> int:
        """Extract maximum delegation depth reached."""
        import re
        match = re.search(r'delegation depth[:\s]+(\d+)', output, re.IGNORECASE)
        if match:
            return int(match.group(1))
        return 0

    def _extract_mcp_tools(self, output: str) -> List[str]:
        """Extract list of MCP tools used."""
        import re
        tools = re.findall(r'\[use-mcp:([^:]+):', output)
        return list(set(tools))

    def _extract_provider_breakdown(self, output: str) -> Dict[str, int]:
        """Extract token breakdown by provider."""
        # TODO: Implement provider usage parsing
        return {}

    def _save_execution_log(
        self,
        task_dir: Path,
        task: TaskDefinition,
        configuration: str,
        result: subprocess.CompletedProcess,
        metrics: Phase2Metrics
    ):
        """Save execution details to log file."""
        log_path = task_dir / "execution.log"

        with open(log_path, 'w') as f:
            f.write(f"Task: {task.task_id} - {task.title}\n")
            f.write(f"Configuration: {configuration}\n")
            f.write(f"Timestamp: {datetime.now().isoformat()}\n")
            f.write(f"\n{'='*80}\n")
            f.write(f"STDOUT:\n")
            f.write(f"{'='*80}\n")
            f.write(result.stdout)
            f.write(f"\n{'='*80}\n")
            f.write(f"STDERR:\n")
            f.write(f"{'='*80}\n")
            f.write(result.stderr)
            f.write(f"\n{'='*80}\n")
            f.write(f"METRICS:\n")
            f.write(f"{'='*80}\n")
            f.write(json.dumps(asdict(metrics), indent=2))

    def cleanup(self):
        """Clean up temporary working directory."""
        if self.working_dir.exists():
            shutil.rmtree(self.working_dir)


def load_task_definition(task_path: Path) -> TaskDefinition:
    """Load task definition from YAML file."""
    with open(task_path, 'r') as f:
        data = yaml.safe_load(f)

    return TaskDefinition(
        task_id=data['task_id'],
        title=data['title'],
        description=data['description'],
        acceptance_criteria=data['acceptance_criteria'],
        complexity=data.get('complexity', 'medium'),
        estimated_hours=data.get('estimated_hours', 4.0),
        context=data.get('context'),
        fileScope=data.get('fileScope')
    )


def run_validation_suite(
    tasks_dir: Path,
    output_dir: Path,
    configurations: List[str],
    runs_per_config: int = 3
):
    """
    Run full Phase 2 validation suite.

    Args:
        tasks_dir: Directory containing task YAML files
        output_dir: Directory for results
        configurations: List of configurations to test
        runs_per_config: Number of runs per configuration (for statistical significance)
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    # Load all tasks
    task_files = sorted(tasks_dir.glob("PHASE2-TASK-*.yaml"))
    tasks = [load_task_definition(f) for f in task_files]

    print(f"\nFound {len(tasks)} tasks to validate")
    print(f"Configurations: {', '.join(configurations)}")
    print(f"Runs per configuration: {runs_per_config}")
    print(f"Total executions: {len(tasks) * len(configurations) * runs_per_config}\n")

    # Results storage
    all_results = []

    # Execute tasks
    executor = Phase2Executor()

    try:
        for task in tasks:
            for configuration in configurations:
                for run in range(runs_per_config):
                    print(f"\n[Run {run+1}/{runs_per_config}]")
                    metrics = executor.execute_task(task, configuration, timeout_seconds=600)

                    result = {
                        "task_id": task.task_id,
                        "configuration": configuration,
                        "run": run + 1,
                        "timestamp": datetime.now().isoformat(),
                        "metrics": asdict(metrics)
                    }

                    all_results.append(result)

                    # Save intermediate results
                    results_path = output_dir / "validation_results.jsonl"
                    with open(results_path, 'a') as f:
                        f.write(json.dumps(result) + '\n')

                    # Print summary
                    print(f"✓ Completed: {task.task_id} [{configuration}]")
                    print(f"  Success: {metrics.success}")
                    print(f"  Time: {metrics.wall_clock_seconds:.1f}s")
                    print(f"  Tokens: {metrics.total_tokens}")
                    print(f"  Cost: ${metrics.estimated_cost_usd:.4f}")

                    if metrics.features_used:
                        print(f"  Features: {', '.join(metrics.features_used)}")

    finally:
        executor.cleanup()

    # Generate summary report
    generate_summary_report(all_results, output_dir)


def generate_summary_report(results: List[Dict], output_dir: Path):
    """Generate summary report from validation results."""

    summary = {
        "timestamp": datetime.now().isoformat(),
        "total_executions": len(results),
        "by_configuration": {},
        "by_complexity": {},
        "cost_comparison": {},
        "feature_usage": {}
    }

    # Aggregate by configuration
    for config in ["phase1", "mcp", "multi-provider", "delegation", "all"]:
        config_results = [r for r in results if r["configuration"] == config]
        if not config_results:
            continue

        success_count = sum(1 for r in config_results if r["metrics"]["success"])
        total_cost = sum(r["metrics"]["estimated_cost_usd"] for r in config_results)
        avg_time = sum(r["metrics"]["wall_clock_seconds"] for r in config_results) / len(config_results)
        total_tokens = sum(r["metrics"]["total_tokens"] for r in config_results)

        summary["by_configuration"][config] = {
            "total_runs": len(config_results),
            "success_count": success_count,
            "success_rate": success_count / len(config_results),
            "total_cost_usd": total_cost,
            "avg_time_seconds": avg_time,
            "total_tokens": total_tokens
        }

    # Save summary
    summary_path = output_dir / "validation_summary.json"
    with open(summary_path, 'w') as f:
        json.dump(summary, f, indent=2)

    print(f"\n{'='*80}")
    print("VALIDATION SUMMARY")
    print(f"{'='*80}\n")
    print(json.dumps(summary, indent=2))
    print(f"\nResults saved to: {output_dir}")


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Phase 2 Validation Runner")
    parser.add_argument(
        "--tasks-dir",
        type=Path,
        default=Path(__file__).parent / "tasks",
        help="Directory containing task YAML files"
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(__file__).parent / "validation",
        help="Output directory for results"
    )
    parser.add_argument(
        "--configurations",
        nargs="+",
        default=["phase1", "mcp", "multi-provider", "delegation", "all"],
        help="Configurations to test"
    )
    parser.add_argument(
        "--runs",
        type=int,
        default=3,
        help="Number of runs per configuration"
    )

    args = parser.parse_args()

    run_validation_suite(
        args.tasks_dir,
        args.output_dir,
        args.configurations,
        args.runs
    )


if __name__ == "__main__":
    main()
