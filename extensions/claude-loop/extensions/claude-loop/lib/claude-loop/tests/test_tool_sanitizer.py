#!/usr/bin/env python3
"""
Tests for Tool Result Sanitizer

Tests the tool sanitization functionality to ensure large outputs
are properly truncated while preserving context.
"""

import pytest
import sys
import os

# Add lib to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'lib'))

from tool_sanitizer import ToolSanitizer, sanitize_tool_result


class TestToolSanitizer:
    """Test suite for ToolSanitizer class."""

    def test_short_content_not_truncated(self):
        """Short content should pass through unchanged."""
        sanitizer = ToolSanitizer(max_chars=8000)
        content = "Hello, world! " * 100  # ~1400 chars
        result = sanitizer.sanitize(content)
        assert result == content
        assert len(result) < 8000

    def test_long_content_truncated(self):
        """Long content should be truncated to max_chars."""
        sanitizer = ToolSanitizer(max_chars=8000, head_chars=7500, tail_chars=500)
        content = "A" * 20000  # 20K chars
        result = sanitizer.sanitize(content)

        # Should be approximately max_chars (plus marker text)
        assert len(result) < 8200  # Allow for truncation marker
        assert "truncated" in result
        assert result.startswith("A" * 100)  # Head preserved
        assert result.endswith("A" * 100)  # Tail preserved

    def test_truncation_marker_format(self):
        """Truncation marker should show number of truncated chars."""
        sanitizer = ToolSanitizer(max_chars=8000)
        content = "X" * 15000  # 15K chars
        result = sanitizer.sanitize(content)

        # Marker should show 7000 truncated chars (15000 - 8000)
        assert "[... truncated 7,000 chars ...]" in result

    def test_binary_data_handling(self):
        """Binary data should be described, not included."""
        sanitizer = ToolSanitizer()
        binary_data = b"\x00\x01\x02" * 1024  # 3KB binary
        result = sanitizer.sanitize(binary_data)

        assert "[Binary data:" in result
        assert "KB]" in result
        assert len(result) < 100  # Should be short description

    def test_none_handling(self):
        """None should be converted to 'null'."""
        sanitizer = ToolSanitizer()
        result = sanitizer.sanitize(None)
        assert result == "null"

    def test_non_string_conversion(self):
        """Non-string types should be converted to string."""
        sanitizer = ToolSanitizer()

        # Test integer
        assert sanitizer.sanitize(42) == "42"

        # Test list
        result = sanitizer.sanitize([1, 2, 3])
        assert "[1, 2, 3]" in result

        # Test dict
        result = sanitizer.sanitize({"key": "value"})
        assert "key" in result
        assert "value" in result

    def test_dict_sanitization(self):
        """Dictionary values should be recursively sanitized."""
        sanitizer = ToolSanitizer(max_chars=100)
        large_dict = {
            "small": "abc",
            "large": "X" * 1000,
            "nested": {"data": "Y" * 500},
        }

        result = sanitizer.sanitize_dict(large_dict)

        assert result["small"] == "abc"  # Small value unchanged
        assert len(result["large"]) < 150  # Large value truncated
        assert "truncated" in result["large"]
        assert len(result["nested"]["data"]) < 150  # Nested value truncated

    def test_list_in_dict_sanitization(self):
        """Lists within dictionaries should be sanitized."""
        sanitizer = ToolSanitizer(max_chars=100)
        data = {"items": ["A" * 200, "B" * 300, "short"]}

        result = sanitizer.sanitize_dict(data)

        assert isinstance(result["items"], list)
        assert len(result["items"]) == 3
        assert result["items"][2] == "short"  # Short item unchanged
        assert "truncated" in result["items"][0]  # Long items truncated
        assert "truncated" in result["items"][1]

    def test_preserve_head_and_tail(self):
        """Both head and tail content should be preserved."""
        sanitizer = ToolSanitizer(max_chars=8000, head_chars=7500, tail_chars=500)
        head_marker = "START_CONTENT_HERE"
        tail_marker = "END_CONTENT_HERE"
        content = head_marker + ("X" * 20000) + tail_marker

        result = sanitizer.sanitize(content)

        assert head_marker in result[:100]  # Head preserved
        assert tail_marker in result[-100:]  # Tail preserved

    def test_convenience_function(self):
        """Convenience function should work correctly."""
        content = "Hello " * 5000  # ~30K chars
        result = sanitize_tool_result(content, max_chars=8000)

        assert len(result) < 8200
        assert "truncated" in result

    def test_custom_max_chars(self):
        """Custom max_chars parameter should be respected."""
        sanitizer = ToolSanitizer(max_chars=1000, head_chars=900, tail_chars=100)
        content = "A" * 5000

        result = sanitizer.sanitize(content)

        assert len(result) < 1100  # Allow for marker
        assert "truncated 4,000 chars" in result

    def test_exact_max_chars_boundary(self):
        """Content exactly at max_chars should not be truncated."""
        sanitizer = ToolSanitizer(max_chars=8000)
        content = "X" * 8000

        result = sanitizer.sanitize(content)

        assert result == content  # No truncation
        assert "truncated" not in result

    def test_utf8_safety(self):
        """UTF-8 characters should be handled safely."""
        sanitizer = ToolSanitizer(max_chars=100)
        content = "Hello 世界 " * 100  # Unicode content

        result = sanitizer.sanitize(content)

        # Should not raise UnicodeError
        assert isinstance(result, str)
        assert len(result) < 150

    def test_newlines_preserved(self):
        """Newlines should be preserved in output."""
        sanitizer = ToolSanitizer(max_chars=8000)
        content = "Line 1\nLine 2\nLine 3\n" * 1000

        result = sanitizer.sanitize(content)

        assert "\n" in result
        # Truncation marker should have newlines
        if "truncated" in result:
            assert "\n\n[... truncated" in result


class TestEdgeCases:
    """Test edge cases and error conditions."""

    def test_empty_string(self):
        """Empty string should return empty string."""
        sanitizer = ToolSanitizer()
        assert sanitizer.sanitize("") == ""

    def test_very_large_content(self):
        """Very large content (>1MB) should be handled."""
        sanitizer = ToolSanitizer(max_chars=8000)
        content = "X" * (1024 * 1024 * 2)  # 2MB

        result = sanitizer.sanitize(content)

        assert len(result) < 10000
        assert "truncated" in result

    def test_zero_max_chars(self):
        """Zero max_chars should return just the marker."""
        sanitizer = ToolSanitizer(max_chars=0, head_chars=0, tail_chars=0)
        content = "Hello"

        result = sanitizer.sanitize(content)

        assert "truncated" in result
        assert len(result) < 100

    def test_nested_dict_deep(self):
        """Deeply nested dictionaries should be handled."""
        sanitizer = ToolSanitizer(max_chars=100)
        deep_dict = {"a": {"b": {"c": {"d": "X" * 1000}}}}

        result = sanitizer.sanitize_dict(deep_dict)

        # Should not raise recursion error
        assert isinstance(result, dict)
        assert "truncated" in result["a"]["b"]["c"]["d"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
