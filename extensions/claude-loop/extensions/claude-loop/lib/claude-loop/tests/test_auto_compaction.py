#!/usr/bin/env python3
"""Tests for Auto-Compaction with Memory Flush"""

import pytest
import os
import tempfile
import json
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'lib'))

from auto_compaction import AutoCompaction, TokenUsage, check_and_flush_memory


class TestTokenUsage:
    """Test token usage tracking."""

    def test_total_tokens(self):
        """Total tokens should be input + output."""
        usage = TokenUsage(input_tokens=1000, output_tokens=500)
        assert usage.total_tokens == 1500

    def test_effective_tokens_with_cache(self):
        """Effective tokens should account for cache reads."""
        usage = TokenUsage(
            input_tokens=1000,
            output_tokens=500,
            cache_read_tokens=300
        )
        # 1000 - 300 + 500 = 1200
        assert usage.effective_tokens == 1200


class TestAutoCompaction:
    """Test auto-compaction manager."""

    def test_initialization(self):
        """Should initialize with default values."""
        compaction = AutoCompaction()

        assert compaction.context_limit == 200000
        assert compaction.threshold == 180000  # 90% of 200000
        assert not compaction.memory_flushed

    def test_custom_threshold(self):
        """Should support custom threshold percentage."""
        compaction = AutoCompaction(context_limit=100000, threshold_pct=0.80)

        assert compaction.threshold == 80000  # 80% of 100000

    def test_update_usage(self):
        """Should accumulate token usage."""
        compaction = AutoCompaction()

        compaction.update_usage(input_tokens=1000, output_tokens=500)
        assert compaction.current_usage.total_tokens == 1500

        compaction.update_usage(input_tokens=2000, output_tokens=800)
        assert compaction.current_usage.total_tokens == 4300  # Accumulated

    def test_should_flush_memory_below_threshold(self):
        """Should not flush when below threshold."""
        compaction = AutoCompaction(context_limit=100000, threshold_pct=0.90)
        compaction.update_usage(input_tokens=50000, output_tokens=10000)

        # 60000 < 90000 threshold
        assert not compaction.should_flush_memory()

    def test_should_flush_memory_at_threshold(self):
        """Should flush when at or above threshold."""
        compaction = AutoCompaction(context_limit=100000, threshold_pct=0.90)
        compaction.update_usage(input_tokens=80000, output_tokens=15000)

        # 95000 >= 90000 threshold
        assert compaction.should_flush_memory()

    def test_should_not_flush_twice(self):
        """Should only flush once per session."""
        compaction = AutoCompaction(context_limit=100000, threshold_pct=0.90)
        compaction.update_usage(input_tokens=80000, output_tokens=15000)

        assert compaction.should_flush_memory()

        # Mark as flushed
        compaction.mark_flushed()

        # Should not flush again
        assert not compaction.should_flush_memory()

    def test_memory_flush_prompt(self):
        """Should generate appropriate memory flush prompt."""
        compaction = AutoCompaction()
        prompt = compaction.get_memory_flush_prompt()

        assert "INTERNAL" in prompt
        assert "MEMORY.md" in prompt
        assert "NO_REPLY" in prompt

    def test_parse_response_with_content(self):
        """Should detect when agent wrote to memory."""
        compaction = AutoCompaction()

        response = "I've written the following to MEMORY.md:\n- Key insight 1\n- Key insight 2"
        assert compaction.parse_response(response)

    def test_parse_response_no_reply(self):
        """Should detect NO_REPLY response."""
        compaction = AutoCompaction()

        assert not compaction.parse_response("NO_REPLY")
        assert not compaction.parse_response("NO_REPLY\n")

    def test_reset(self):
        """Should reset state for new session."""
        compaction = AutoCompaction()
        compaction.update_usage(input_tokens=50000, output_tokens=10000)
        compaction.mark_flushed()

        compaction.reset()

        assert compaction.current_usage.total_tokens == 0
        assert not compaction.memory_flushed


class TestMemoryFile:
    """Test memory file operations."""

    def test_ensure_memory_file_creates_file(self):
        """Should create memory file if it doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            memory_file = os.path.join(tmpdir, "workspace", "MEMORY.md")
            compaction = AutoCompaction(memory_file=memory_file)

            compaction.ensure_memory_file()

            assert os.path.exists(memory_file)

            with open(memory_file, 'r') as f:
                content = f.read()
                assert "# Memory Log" in content

    def test_append_memory_entry(self):
        """Should append entry to memory file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            memory_file = os.path.join(tmpdir, "MEMORY.md")
            compaction = AutoCompaction(memory_file=memory_file)

            compaction.append_memory_entry(
                "Important insight about error handling",
                metadata={"story_id": "US-001", "iteration": 5}
            )

            with open(memory_file, 'r') as f:
                content = f.read()
                assert "Important insight" in content
                assert "story_id: US-001" in content
                assert "iteration: 5" in content

    def test_multiple_memory_entries(self):
        """Should support multiple entries."""
        with tempfile.TemporaryDirectory() as tmpdir:
            memory_file = os.path.join(tmpdir, "MEMORY.md")
            compaction = AutoCompaction(memory_file=memory_file)

            compaction.append_memory_entry("First insight")
            compaction.append_memory_entry("Second insight")

            with open(memory_file, 'r') as f:
                content = f.read()
                assert "First insight" in content
                assert "Second insight" in content
                assert content.count("## Entry:") == 2


class TestUsageStats:
    """Test usage statistics."""

    def test_get_usage_stats(self):
        """Should return comprehensive usage stats."""
        compaction = AutoCompaction(context_limit=100000)
        compaction.update_usage(input_tokens=50000, output_tokens=10000,
                              cache_read=5000)

        stats = compaction.get_usage_stats()

        assert stats["total_tokens"] == 60000
        assert stats["context_limit"] == 100000
        assert stats["usage_pct"] == 60.0
        assert stats["remaining"] == 40000
        assert not stats["memory_flushed"]
        assert stats["breakdown"]["input"] == 50000
        assert stats["breakdown"]["output"] == 10000


class TestSessionState:
    """Test session state persistence."""

    def test_save_and_load_session_state(self):
        """Should save and load session state."""
        with tempfile.TemporaryDirectory() as tmpdir:
            session_file = os.path.join(tmpdir, "state.json")
            compaction = AutoCompaction(session_file=session_file)

            compaction.update_usage(input_tokens=50000, output_tokens=10000)
            compaction.save_session_state()

            assert os.path.exists(session_file)

            with open(session_file, 'r') as f:
                state = json.load(f)
                assert state["token_usage"]["total"] == 60000
                assert state["compaction"]["memory_flushed"] == False

    def test_save_with_additional_data(self):
        """Should save additional session data."""
        with tempfile.TemporaryDirectory() as tmpdir:
            session_file = os.path.join(tmpdir, "state.json")
            compaction = AutoCompaction(session_file=session_file)

            compaction.save_session_state(additional_data={
                "story_id": "US-001",
                "iteration": 5
            })

            with open(session_file, 'r') as f:
                state = json.load(f)
                assert state["story_id"] == "US-001"
                assert state["iteration"] == 5


class TestCheckAndFlushMemory:
    """Test the check_and_flush_memory utility."""

    def test_no_flush_below_threshold(self):
        """Should not flush when below threshold."""
        compaction = AutoCompaction(context_limit=100000, threshold_pct=0.90)
        compaction.update_usage(input_tokens=50000, output_tokens=5000)

        call_count = {'count': 0}

        def mock_execute_turn(prompt):
            call_count['count'] += 1
            return "NO_REPLY"

        flushed = check_and_flush_memory(compaction, mock_execute_turn, "US-001")

        assert not flushed
        assert call_count['count'] == 0  # Turn not executed

    def test_flush_at_threshold(self):
        """Should flush when at threshold."""
        compaction = AutoCompaction(context_limit=100000, threshold_pct=0.90)
        compaction.update_usage(input_tokens=80000, output_tokens=15000)

        call_count = {'count': 0}

        def mock_execute_turn(prompt):
            call_count['count'] += 1
            assert "INTERNAL" in prompt
            assert "MEMORY.md" in prompt
            return "I wrote important notes to memory"

        flushed = check_and_flush_memory(compaction, mock_execute_turn, "US-001")

        assert flushed
        assert call_count['count'] == 1  # Turn executed once
        assert compaction.memory_flushed

    def test_flush_handles_no_reply(self):
        """Should handle NO_REPLY response."""
        compaction = AutoCompaction(context_limit=100000, threshold_pct=0.90)
        compaction.update_usage(input_tokens=90000, output_tokens=5000)

        def mock_execute_turn(prompt):
            return "NO_REPLY"

        flushed = check_and_flush_memory(compaction, mock_execute_turn, "US-001")

        assert flushed  # Flush was attempted
        assert compaction.memory_flushed  # Marked as flushed

    def test_flush_handles_error(self):
        """Should handle errors gracefully."""
        compaction = AutoCompaction(context_limit=100000, threshold_pct=0.90)
        compaction.update_usage(input_tokens=90000, output_tokens=5000)

        def mock_execute_turn(prompt):
            raise Exception("API error")

        flushed = check_and_flush_memory(compaction, mock_execute_turn, "US-001")

        # Returns False on error, but still marks as flushed to prevent retry loop
        assert not flushed  # Error occurred
        assert compaction.memory_flushed  # Still marked to avoid retry loop


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
