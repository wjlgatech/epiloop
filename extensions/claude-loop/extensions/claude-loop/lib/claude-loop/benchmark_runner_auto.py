#!/usr/bin/env python3
"""
Benchmark Runner - Claude-Loop Auto (Invisible Intelligence Test)

Tests claude-loop with default settings (features enabled automatically).
Runs in parallel with main 3-way benchmark.
"""

import sys
sys.path.insert(0, '/Users/jialiang.wu/Documents/Projects/benchmark-tasks')

from benchmark_runner import BenchmarkRunner, BenchmarkConfig, Subject
import json
from pathlib import Path

def main():
    """Run claude-loop-auto benchmark."""

    # Use same config as main benchmark
    config = BenchmarkConfig(
        tasks_dir=Path("/Users/jialiang.wu/Documents/Projects/benchmark-tasks"),
        output_dir=Path("/Users/jialiang.wu/Documents/Projects/benchmark-results"),
        subjects=["claude-loop-auto"],  # Dummy, not actually used
        runs_per_task=5,
        timeout_seconds=3600,
        claude_code_cli="claude",
        claude_loop_script="/Users/jialiang.wu/Documents/Projects/claude-loop"
    )

    runner = BenchmarkRunner(config)

    print("=" * 70)
    print("BENCHMARK RUNNER - Claude-Loop Auto (Invisible Intelligence)")
    print("=" * 70)
    print()
    print(f"Tasks: {len(runner.tasks)}")
    print(f"Subject: claude-loop-auto (features enabled)")
    print(f"Runs per task: {config.runs_per_task}")
    print(f"Total runs: {len(runner.tasks) * config.runs_per_task}")
    print()

    results = []

    for task_idx, task in enumerate(runner.tasks, 1):
        print()
        print("=" * 70)
        print(f"TASK: {task['id']} - {task['name']}")
        print(f"Tier: {task['tier']} | Difficulty: {task.get('difficulty', 'N/A')}")
        print("=" * 70)
        print()

        print(f"  Testing claude-loop-auto...")
        for run in range(1, config.runs_per_task + 1):
            print(f"    Run {run}/{config.runs_per_task}...")

            success, criteria_scores, tokens, cost, error = runner._run_claude_loop_auto(task, run)

            # Calculate average score
            avg_score = sum(criteria_scores.values()) / len(criteria_scores) if criteria_scores else 0.0

            result = {
                "task_id": task['id'],
                "subject": "claude-loop-auto",
                "run": run,
                "success": success,
                "criteria_scores": criteria_scores,
                "avg_score": avg_score,
                "tokens": tokens,
                "cost": cost,
                "error": error,
                "tier": task['tier'],
                "difficulty": task.get('difficulty', 'N/A')
            }

            results.append(result)

            # Print result
            status = "✓ PASS" if success else "✗ FAIL"
            duration_str = f"{config.timeout_seconds if error == 'Timeout exceeded' else 300}s"  # Estimate
            print(f"      {status} | {duration_str} | {tokens} tokens | ${cost:.4f} | Score: {avg_score:.2f}")
            if error:
                print(f"      Error: {error}")

    # Save results
    output_dir = Path("/Users/jialiang.wu/Documents/Projects/benchmark-results")
    output_dir.mkdir(exist_ok=True)

    output_file = output_dir / "benchmark_auto_results.json"
    with open(output_file, 'w') as f:
        json.dump({
            "config": {
                "runs_per_task": config.runs_per_task,
                "timeout_seconds": config.timeout_seconds,
                "total_runs": len(results)
            },
            "results": results
        }, f, indent=2)

    print()
    print("=" * 70)
    print("BENCHMARK COMPLETE")
    print("=" * 70)
    print(f"Results saved to: {output_file}")
    print()

    # Calculate summary
    successes = sum(1 for r in results if r["success"])
    success_rate = successes / len(results) if results else 0
    avg_score = sum(r["avg_score"] for r in results) / len(results) if results else 0
    avg_cost = sum(r["cost"] for r in results) / len(results) if results else 0

    print(f"Claude-Loop Auto Summary:")
    print(f"  Success Rate: {success_rate:.1%} ({successes}/{len(results)})")
    print(f"  Average Score: {avg_score:.2f}")
    print(f"  Average Cost: ${avg_cost:.4f}")


if __name__ == "__main__":
    main()
