#!/usr/bin/env python3
"""
Validator for TASK-003: Scheduler Duplicate Jobs Bug Fix
Checks if duplicate job execution bug is fixed
"""

import sys
import os
from pathlib import Path


def validate_task_003(workspace_path: str) -> dict:
    """
    Validate TASK-003 acceptance criteria

    Returns:
        dict: {ac_id: score (0.0-1.0)}
    """
    scores = {}

    # AC1: Jobs execute exactly once per interval (weight: 0.40)
    scores['AC1'] = check_duplicate_prevention(workspace_path)

    # AC2: Works correctly with SLEEP_TIME < 60s (weight: 0.25)
    scores['AC2'] = check_fast_polling_support(workspace_path)

    # AC3: No race conditions or state corruption (weight: 0.20)
    scores['AC3'] = check_thread_safety(workspace_path)

    # AC4: Existing scheduled jobs still work (weight: 0.10)
    scores['AC4'] = check_backwards_compatibility(workspace_path)

    # AC5: TODO comment removed/updated (weight: 0.05)
    scores['AC5'] = check_todo_resolved(workspace_path)

    return scores


def check_duplicate_prevention(workspace: str) -> float:
    """Check if duplicate prevention logic is implemented"""
    job_loop_file = Path(workspace) / "project" / "python" / "helpers" / "job_loop.py"

    if not job_loop_file.exists():
        return 0.0

    with open(job_loop_file, 'r') as f:
        content = f.read()

    # Check for duplicate prevention mechanisms
    prevention_indicators = [
        'last_execution',
        'last_run',
        'timestamp',
        'job_id',
        'executed.*minute',
        'already.*run'
    ]

    import re
    found = sum(1 for pattern in prevention_indicators if re.search(pattern, content, re.IGNORECASE))

    return min(found / len(prevention_indicators), 1.0)


def check_fast_polling_support(workspace: str) -> float:
    """Check if fast polling (SLEEP_TIME < 60s) is supported"""
    job_loop_file = Path(workspace) / "project" / "python" / "helpers" / "job_loop.py"

    if not job_loop_file.exists():
        return 0.0

    with open(job_loop_file, 'r') as f:
        content = f.read()

    # Check if TODO comment is removed (indicating fix)
    if 'TODO' in content and '5min job multiple times' in content:
        return 0.0  # TODO still present, not fixed

    # Check for interval tracking
    interval_indicators = [
        'interval',
        'job.interval',
        'time.*elapsed',
        'since.*last'
    ]

    import re
    found = sum(1 for pattern in interval_indicators if re.search(pattern, content, re.IGNORECASE))

    return min(found / len(interval_indicators), 1.0)


def check_thread_safety(workspace: str) -> float:
    """Check for thread safety / state management"""
    job_loop_file = Path(workspace) / "project" / "python" / "helpers" / "job_loop.py"

    if not job_loop_file.exists():
        return 0.0

    with open(job_loop_file, 'r') as f:
        content = f.read()

    # Check for state management
    state_indicators = [
        'dict',
        'last_execution_times',
        'job_state',
        '{.*}',
        'tracking'
    ]

    import re
    found = sum(1 for pattern in state_indicators if re.search(pattern, content))

    # Check for async safety
    if 'async' in content and 'await' in content:
        found += 1

    return min(found / (len(state_indicators) + 1), 1.0)


def check_backwards_compatibility(workspace: str) -> float:
    """Check if existing functionality is preserved"""
    job_loop_file = Path(workspace) / "project" / "python" / "helpers" / "job_loop.py"

    if not job_loop_file.exists():
        return 0.0

    try:
        # Check if file compiles
        with open(job_loop_file, 'r') as f:
            content = f.read()

        compile(content, job_loop_file, 'exec')

        # Check if main functions still exist
        essential_functions = ['job_loop', 'scheduler_tick']
        found = sum(1 for func in essential_functions if f'def {func}' in content or f'async def {func}' in content)

        return found / len(essential_functions)
    except SyntaxError:
        return 0.0


def check_todo_resolved(workspace: str) -> float:
    """Check if TODO comment is removed or updated"""
    job_loop_file = Path(workspace) / "project" / "python" / "helpers" / "job_loop.py"

    if not job_loop_file.exists():
        return 0.0

    with open(job_loop_file, 'r') as f:
        content = f.read()

    # Original TODO
    original_todo = 'TODO! - if we lower it under 1min, it can run a 5min job multiple times'

    if original_todo in content:
        return 0.0  # TODO still present exactly as before

    # Check if line was modified
    if 'SLEEP_TIME' in content and 'asyncio.sleep' in content:
        # TODO was addressed (line still exists but modified)
        return 1.0

    return 0.5  # Partial credit


def main():
    if len(sys.argv) != 2:
        print("Usage: task_003_validator.py <workspace_path>")
        sys.exit(1)

    workspace = sys.argv[1]
    scores = validate_task_003(workspace)

    print("TASK-003 Validation Results:")
    print("=" * 50)
    for ac_id, score in scores.items():
        status = "✓ PASS" if score > 0.7 else "✗ FAIL"
        print(f"{ac_id}: {score:.2f} {status}")

    overall = sum(scores.values()) / len(scores)
    print(f"\nOverall Score: {overall:.2f}")

    sys.exit(0 if overall > 0.7 else 1)


if __name__ == "__main__":
    main()
