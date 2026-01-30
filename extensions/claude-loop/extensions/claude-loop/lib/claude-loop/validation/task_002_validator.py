#!/usr/bin/env python3
"""
Validator for TASK-002: LLM Provider Health Check
Checks if API health check functionality is implemented
"""

import sys
import os
import json
from pathlib import Path


def validate_task_002(workspace_path: str) -> dict:
    """
    Validate TASK-002 acceptance criteria

    Returns:
        dict: {ac_id: score (0.0-1.0)}
    """
    scores = {}

    # AC1: Makes real API call to test provider (weight: 0.35)
    scores['AC1'] = check_real_api_call(workspace_path)

    # AC2: Validates API key is functional (weight: 0.25)
    scores['AC2'] = check_api_key_validation(workspace_path)

    # AC3: Handles provider-specific errors gracefully (weight: 0.20)
    scores['AC3'] = check_error_handling(workspace_path)

    # AC4: Returns structured response with details (weight: 0.15)
    scores['AC4'] = check_structured_response(workspace_path)

    # AC5: Completes within reasonable timeout (weight: 0.05)
    scores['AC5'] = check_timeout_handling(workspace_path)

    return scores


def check_real_api_call(workspace: str) -> float:
    """Check if real API calls are made"""
    llm_config_file = Path(workspace) / "project" / "lib" / "llm_config.py"

    if not llm_config_file.exists():
        return 0.0

    with open(llm_config_file, 'r') as f:
        content = f.read()

    # Check if TODO comment is removed/updated
    if 'TODO: Implement actual API test calls' in content:
        return 0.0  # TODO still present

    # Check for API call implementation
    api_indicators = [
        'llm.complete',
        'LLMProvider',
        'response =',
        'test_prompt',
        'API.*call'
    ]

    import re
    found = sum(1 for pattern in api_indicators if re.search(pattern, content, re.IGNORECASE))

    return min(found / len(api_indicators), 1.0)


def check_api_key_validation(workspace: str) -> float:
    """Check if API key validation is implemented"""
    llm_config_file = Path(workspace) / "project" / "lib" / "llm_config.py"

    if not llm_config_file.exists():
        return 0.0

    with open(llm_config_file, 'r') as f:
        content = f.read()

    # Check for authentication error handling
    auth_indicators = [
        'AuthenticationError',
        'Invalid API key',
        'authentication',
        'API.*key.*valid'
    ]

    import re
    found = sum(1 for pattern in auth_indicators if re.search(pattern, content, re.IGNORECASE))

    return min(found / len(auth_indicators), 1.0)


def check_error_handling(workspace: str) -> float:
    """Check if error handling is comprehensive"""
    llm_config_file = Path(workspace) / "project" / "lib" / "llm_config.py"

    if not llm_config_file.exists():
        return 0.0

    with open(llm_config_file, 'r') as f:
        content = f.read()

    # Check for various error handlers
    error_types = [
        'TimeoutError',
        'AuthenticationError',
        'except.*Exception',
        'try:',
        'error.*message'
    ]

    import re
    found = sum(1 for pattern in error_types if re.search(pattern, content, re.IGNORECASE))

    return min(found / len(error_types), 1.0)


def check_structured_response(workspace: str) -> float:
    """Check if responses are structured (tuple/dict)"""
    llm_config_file = Path(workspace) / "project" / "lib" / "llm_config.py"

    if not llm_config_file.exists():
        return 0.0

    with open(llm_config_file, 'r') as f:
        content = f.read()

    # Check for structured return
    response_indicators = [
        'return.*,.*,.*',  # Tuple return
        'Tuple\\[bool.*str.*dict\\]',  # Type hint
        'details',
        'success.*message',
        '{.*:.*}'  # Dict construction
    ]

    import re
    found = sum(1 for pattern in response_indicators if re.search(pattern, content))

    return min(found / len(response_indicators), 1.0)


def check_timeout_handling(workspace: str) -> float:
    """Check if timeout is configured"""
    llm_config_file = Path(workspace) / "project" / "lib" / "llm_config.py"

    if not llm_config_file.exists():
        return 0.0

    with open(llm_config_file, 'r') as f:
        content = f.read()

    # Check for timeout configuration
    timeout_indicators = [
        'timeout.*=.*5',
        'timeout',
        'TimeoutError',
        'max.*wait'
    ]

    import re
    found = sum(1 for pattern in timeout_indicators if re.search(pattern, content, re.IGNORECASE))

    return min(found / len(timeout_indicators), 1.0)


def main():
    if len(sys.argv) != 2:
        print("Usage: task_002_validator.py <workspace_path>")
        sys.exit(1)

    workspace = sys.argv[1]
    scores = validate_task_002(workspace)

    print("TASK-002 Validation Results:")
    print("=" * 50)
    for ac_id, score in scores.items():
        status = "✓ PASS" if score > 0.7 else "✗ FAIL"
        print(f"{ac_id}: {score:.2f} {status}")

    overall = sum(scores.values()) / len(scores)
    print(f"\nOverall Score: {overall:.2f}")

    sys.exit(0 if overall > 0.7 else 1)


if __name__ == "__main__":
    main()
