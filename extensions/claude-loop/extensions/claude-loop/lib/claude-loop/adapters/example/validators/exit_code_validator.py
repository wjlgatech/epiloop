#!/usr/bin/env python3
"""
Exit Code Validator for CLI Tools

Validates that CLI commands return appropriate exit codes.
"""

from typing import Dict, Any, List, Tuple


def validate_exit_code(
    exit_code: int,
    expected_success: bool = True
) -> Tuple[bool, str]:
    """
    Validate a CLI exit code.

    Args:
        exit_code: The exit code to validate
        expected_success: Whether success (0) was expected

    Returns:
        Tuple of (is_valid, message)
    """
    if expected_success:
        if exit_code == 0:
            return True, "Command succeeded as expected"
        else:
            return False, f"Command failed with exit code {exit_code}"
    else:
        if exit_code != 0:
            return True, f"Command failed as expected with exit code {exit_code}"
        else:
            return False, "Command succeeded but failure was expected"


def validate_output_format(
    output: str,
    expected_format: str = "text"
) -> Tuple[bool, str]:
    """
    Validate CLI output format.

    Args:
        output: The command output
        expected_format: Expected format (text, json, csv)

    Returns:
        Tuple of (is_valid, message)
    """
    if expected_format == "json":
        import json as json_module
        try:
            json_module.loads(output)
            return True, "Valid JSON output"
        except json_module.JSONDecodeError as e:
            return False, f"Invalid JSON: {e}"

    elif expected_format == "csv":
        lines = output.strip().split("\n")
        if not lines:
            return False, "Empty output"
        header_cols = len(lines[0].split(","))
        for i, line in enumerate(lines[1:], 2):
            if len(line.split(",")) != header_cols:
                return False, f"CSV column mismatch at line {i}"
        return True, "Valid CSV output"

    else:  # text
        if output.strip():
            return True, "Non-empty text output"
        return True, "Empty text output (may be valid)"


def get_validators() -> List[Dict[str, Any]]:
    """Return list of validators provided by this module."""
    return [
        {
            "name": "exit_code",
            "function": validate_exit_code,
            "description": "Validates CLI exit codes"
        },
        {
            "name": "output_format",
            "function": validate_output_format,
            "description": "Validates CLI output format (text, json, csv)"
        },
    ]
