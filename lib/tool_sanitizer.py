#!/usr/bin/env python3
"""
Tool Result Sanitizer

Prevents context overflow by truncating large tool outputs while preserving
useful information at both the beginning and end of the content.

Inspired by clawdbot's tool result sanitization approach.
"""

import sys
from typing import Union, Any


class ToolSanitizer:
    """Sanitizes tool results to prevent token explosion."""

    def __init__(self, max_chars: int = 8000, head_chars: int = 7500, tail_chars: int = 500):
        """
        Initialize the sanitizer.

        Args:
            max_chars: Maximum total characters to allow
            head_chars: Characters to preserve from the beginning
            tail_chars: Characters to preserve from the end
        """
        self.max_chars = max_chars

        # Adjust head/tail if they exceed max_chars
        total_preserve = head_chars + tail_chars
        if total_preserve > max_chars:
            # Scale proportionally, leaving room for truncation marker (~40 chars)
            ratio = (max_chars - 40) / total_preserve
            self.head_chars = int(head_chars * ratio)
            self.tail_chars = int(tail_chars * ratio)
        else:
            self.head_chars = head_chars
            self.tail_chars = tail_chars

    def sanitize(self, result: Any) -> str:
        """
        Sanitize a tool result.

        Args:
            result: Tool result (string, bytes, or other type)

        Returns:
            Sanitized string representation
        """
        # Handle None
        if result is None:
            return "null"

        # Handle binary data
        if isinstance(result, bytes):
            size_kb = len(result) / 1024
            return f"[Binary data: {size_kb:.2f} KB]"

        # Convert to string
        if not isinstance(result, str):
            result = str(result)

        # Check if truncation needed
        if len(result) <= self.max_chars:
            return result

        # Calculate truncation
        truncated_chars = len(result) - self.max_chars
        head = result[: self.head_chars]
        tail = result[-self.tail_chars :]

        # Create truncation marker
        marker = f"\n\n[... truncated {truncated_chars:,} chars ...]\n\n"

        return head + marker + tail

    def sanitize_dict(self, result_dict: dict) -> dict:
        """
        Sanitize all values in a dictionary (e.g., tool result with metadata).

        Args:
            result_dict: Dictionary of results

        Returns:
            Dictionary with sanitized values
        """
        sanitized = {}
        for key, value in result_dict.items():
            if isinstance(value, dict):
                sanitized[key] = self.sanitize_dict(value)
            elif isinstance(value, list):
                sanitized[key] = [self.sanitize(item) for item in value]
            else:
                sanitized[key] = self.sanitize(value)
        return sanitized


# Default instance for convenience
default_sanitizer = ToolSanitizer()


def sanitize_tool_result(result: Any, max_chars: int = 8000) -> str:
    """
    Convenience function to sanitize a tool result.

    Args:
        result: Tool result to sanitize
        max_chars: Maximum characters to allow

    Returns:
        Sanitized string
    """
    sanitizer = ToolSanitizer(max_chars=max_chars)
    return sanitizer.sanitize(result)


def main():
    """CLI interface for testing."""
    if len(sys.argv) < 2:
        print("Usage: tool-sanitizer.py <input_file> [max_chars]")
        print("       echo 'text' | tool-sanitizer.py - [max_chars]")
        sys.exit(1)

    max_chars = int(sys.argv[2]) if len(sys.argv) > 2 else 8000

    # Read input
    if sys.argv[1] == "-":
        content = sys.stdin.read()
    else:
        with open(sys.argv[1], "r", encoding="utf-8", errors="replace") as f:
            content = f.read()

    # Sanitize and output
    sanitized = sanitize_tool_result(content, max_chars=max_chars)
    print(sanitized)


if __name__ == "__main__":
    main()
