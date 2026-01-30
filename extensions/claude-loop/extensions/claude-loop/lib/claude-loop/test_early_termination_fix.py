#!/usr/bin/env python3
"""
Quick test to validate early termination fix.
Tests TASK-003 and TASK-010 with 5 runs each (10 total).
"""

from benchmark_parallel import ParallelBenchmarkRunner
import json

def main():
    print("\n" + "="*80)
    print("TESTING EARLY TERMINATION FIX")
    print("="*80)
    print("\nTarget: TASK-003 and TASK-010 (40% failure rate before fix)")
    print("Expected: 90%+ success rate after fix")
    print("="*80 + "\n")

    # Create runner with 2 parallel workers
    runner = ParallelBenchmarkRunner(max_workers=2, runs_per_task=5)

    # Filter to only problem tasks
    runner.tasks = [t for t in runner.tasks if t['id'] in ['TASK-003', 'TASK-010']]

    print(f"Running {len(runner.tasks)} tasks × 5 runs = {len(runner.tasks) * 5} total")
    print(f"Tasks: {', '.join([t['id'] for t in runner.tasks])}\n")

    # Run benchmark
    runner.run_parallel_benchmark()

    # Analyze results
    print("\n" + "="*80)
    print("RESULTS ANALYSIS")
    print("="*80)

    results_by_task = {}
    for result in runner.results:
        task_id = result['task_id']
        if task_id not in results_by_task:
            results_by_task[task_id] = {'success': 0, 'failure': 0, 'durations': []}

        if result['success']:
            results_by_task[task_id]['success'] += 1
        else:
            results_by_task[task_id]['failure'] += 1

        results_by_task[task_id]['durations'].append(result['elapsed_time'])

    for task_id, stats in sorted(results_by_task.items()):
        success_rate = (stats['success'] / (stats['success'] + stats['failure'])) * 100
        avg_duration = sum(stats['durations']) / len(stats['durations'])

        status = "✅ FIXED" if success_rate >= 80 else "❌ STILL BROKEN"
        print(f"\n{task_id}: {stats['success']}/{stats['success'] + stats['failure']} success ({success_rate:.0f}%) {status}")
        print(f"  Average duration: {avg_duration:.1f}s")
        print(f"  Duration range: {min(stats['durations']):.1f}s - {max(stats['durations']):.1f}s")

    # Overall assessment
    total_success = sum(stats['success'] for stats in results_by_task.values())
    total_runs = sum(stats['success'] + stats['failure'] for stats in results_by_task.values())
    overall_rate = (total_success / total_runs) * 100

    print("\n" + "="*80)
    print(f"OVERALL: {total_success}/{total_runs} success ({overall_rate:.0f}%)")

    if overall_rate >= 80:
        print("✅ FIX VALIDATED - Early termination issue resolved!")
    else:
        print("❌ FIX INEFFECTIVE - Further investigation needed")

    print("="*80 + "\n")

if __name__ == "__main__":
    main()
