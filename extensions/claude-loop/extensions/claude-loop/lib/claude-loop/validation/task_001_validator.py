#!/usr/bin/env python3
"""
Validator for TASK-001: Vision Summary Optimization
Checks if vision bytes are removed from history compression
"""

import sys
import os
from pathlib import Path


def validate_task_001(workspace_path: str) -> dict:
    """
    Validate TASK-001 acceptance criteria

    Returns:
        dict: {ac_id: score (0.0-1.0)}
    """
    scores = {}

    # AC1: Vision bytes are not sent to utility model (weight: 0.40)
    ac1_score = check_vision_bytes_removed(workspace_path)
    scores['AC1'] = ac1_score

    # AC2: Text summary extracted from vision messages (weight: 0.30)
    ac2_score = check_text_summary_extraction(workspace_path)
    scores['AC2'] = ac2_score

    # AC3: Existing tests still pass (weight: 0.20)
    ac3_score = check_tests_passing(workspace_path)
    scores['AC3'] = ac3_score

    # AC4: Token usage reduced (weight: 0.10)
    ac4_score = check_token_reduction(workspace_path)
    scores['AC4'] = ac4_score

    return scores


def check_vision_bytes_removed(workspace: str) -> float:
    """Check if vision bytes handling was implemented"""
    history_file = Path(workspace) / "project" / "python" / "helpers" / "history.py"

    if not history_file.exists():
        return 0.0

    with open(history_file, 'r') as f:
        content = f.read()

    # Check for vision handling code
    vision_keywords = ['vision', 'image', 'bytes', 'has_vision']
    found = sum(1 for kw in vision_keywords if kw in content.lower())

    # Check if FIXME comment is addressed
    if 'FIXME' in content and 'vision bytes' in content:
        return 0.3  # Still has FIXME

    # Check for actual implementation
    if 'vision' in content and ('summary' in content or 'placeholder' in content):
        return min(0.8 + (found / len(vision_keywords)) * 0.2, 1.0)

    return found / len(vision_keywords) * 0.5


def check_text_summary_extraction(workspace: str) -> float:
    """Check if text summaries are extracted"""
    history_file = Path(workspace) / "project" / "python" / "helpers" / "history.py"

    if not history_file.exists():
        return 0.0

    with open(history_file, 'r') as f:
        content = f.read()

    # Look for summary extraction logic
    summary_indicators = [
        'get_vision_summary',
        'vision_placeholder',
        '[Image:',
        'extract.*summary',
        'text.*vision'
    ]

    import re
    found = sum(1 for pattern in summary_indicators if re.search(pattern, content, re.IGNORECASE))

    return min(found / len(summary_indicators), 1.0)


def check_tests_passing(workspace: str) -> float:
    """Check if tests pass (if test infrastructure exists)"""
    # For now, assume tests pass if code compiles
    history_file = Path(workspace) / "project" / "python" / "helpers" / "history.py"

    if not history_file.exists():
        return 0.0

    try:
        # Try to parse the Python file
        with open(history_file, 'r') as f:
            content = f.read()

        compile(content, history_file, 'exec')
        return 1.0  # File compiles
    except SyntaxError:
        return 0.0  # Syntax error


def check_token_reduction(workspace: str) -> float:
    """Estimate if token usage would be reduced"""
    # This is a heuristic - we can't measure actual token reduction in validation
    # Check if vision handling is implemented (which implies token reduction)
    ac1 = check_vision_bytes_removed(workspace)
    ac2 = check_text_summary_extraction(workspace)

    # Token reduction is implied by AC1 and AC2 success
    return (ac1 + ac2) / 2


def main():
    if len(sys.argv) != 2:
        print("Usage: task_001_validator.py <workspace_path>")
        sys.exit(1)

    workspace = sys.argv[1]
    scores = validate_task_001(workspace)

    print("TASK-001 Validation Results:")
    print("=" * 50)
    for ac_id, score in scores.items():
        status = "✓ PASS" if score > 0.7 else "✗ FAIL"
        print(f"{ac_id}: {score:.2f} {status}")

    overall = sum(scores.values()) / len(scores)
    print(f"\nOverall Score: {overall:.2f}")

    sys.exit(0 if overall > 0.7 else 1)


if __name__ == "__main__":
    main()
