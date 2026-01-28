#!/usr/bin/env python3
"""
Auto-Compaction with Memory Flush

Automatically triggers memory preservation when approaching context limits,
ensuring important learnings are saved before compaction occurs.

Inspired by clawdbot's memory management system.
"""

import os
import json
import logging
from typing import Dict, List, Optional
from dataclasses import dataclass
from datetime import datetime

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


@dataclass
class TokenUsage:
    """Track token usage for a session."""
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_creation_tokens: int = 0

    @property
    def total_tokens(self) -> int:
        """Total tokens used (input + output, excluding cache)."""
        return self.input_tokens + self.output_tokens

    @property
    def effective_tokens(self) -> int:
        """Effective tokens counting cache benefits."""
        return self.input_tokens - self.cache_read_tokens + self.output_tokens


class AutoCompaction:
    """
    Manages automatic compaction with memory flush.

    Monitors token usage and triggers memory preservation before
    hitting context limits.
    """

    def __init__(self,
                 context_limit: int = 200000,
                 threshold_pct: float = 0.90,
                 memory_file: str = "workspace/MEMORY.md",
                 session_file: str = ".claude-loop/sessions/current/state.json"):
        """
        Initialize auto-compaction manager.

        Args:
            context_limit: Maximum context window size
            threshold_pct: Trigger memory flush at this % of limit (default: 90%)
            memory_file: Path to memory file
            session_file: Path to session state file
        """
        self.context_limit = context_limit
        self.threshold = int(context_limit * threshold_pct)
        self.memory_file = memory_file
        self.session_file = session_file
        self.current_usage = TokenUsage()
        self.memory_flushed = False

    def update_usage(self, input_tokens: int, output_tokens: int,
                    cache_read: int = 0, cache_creation: int = 0):
        """
        Update token usage counters.

        Args:
            input_tokens: Tokens in prompt
            output_tokens: Tokens in response
            cache_read: Tokens read from cache
            cache_creation: Tokens used to create cache
        """
        self.current_usage.input_tokens += input_tokens
        self.current_usage.output_tokens += output_tokens
        self.current_usage.cache_read_tokens += cache_read
        self.current_usage.cache_creation_tokens += cache_creation

        logger.debug(f"Token usage updated: {self.current_usage.total_tokens}/{self.context_limit}")

    def should_flush_memory(self) -> bool:
        """
        Check if we should trigger memory flush.

        Returns:
            True if approaching context limit and not yet flushed
        """
        if self.memory_flushed:
            return False  # Only flush once per session

        total = self.current_usage.total_tokens
        return total >= self.threshold

    def get_memory_flush_prompt(self) -> str:
        """
        Get prompt for memory flush turn.

        Returns:
            Prompt asking agent to write important notes to MEMORY.md
        """
        return """INTERNAL: Approaching context limit. Write important notes to MEMORY.md.

Review the conversation so far and identify:
1. Key learnings and insights
2. Important decisions made
3. Patterns or approaches that worked well
4. Things to avoid or watch out for

Write these to MEMORY.md using append mode. Be concise but specific.

If there's nothing significant to record, reply with exactly: NO_REPLY"""

    def parse_response(self, response: str) -> bool:
        """
        Parse agent response to memory flush prompt.

        Args:
            response: Agent's response text

        Returns:
            True if agent wrote to memory, False if NO_REPLY
        """
        return "NO_REPLY" not in response.strip()

    def ensure_memory_file(self):
        """Ensure memory file and directory exist."""
        os.makedirs(os.path.dirname(self.memory_file), exist_ok=True)

        if not os.path.exists(self.memory_file):
            with open(self.memory_file, 'w') as f:
                f.write(f"# Memory Log\n\nGenerated: {datetime.now().isoformat()}\n\n")
                f.write("This file contains important learnings and insights from autonomous sessions.\n\n")
                f.write("---\n\n")

    def append_memory_entry(self, content: str, metadata: Optional[Dict] = None):
        """
        Append entry to memory file.

        Args:
            content: Memory content to append
            metadata: Optional metadata (story_id, timestamp, etc.)
        """
        self.ensure_memory_file()

        with open(self.memory_file, 'a') as f:
            f.write(f"\n## Entry: {datetime.now().isoformat()}\n\n")

            if metadata:
                f.write("**Metadata:**\n")
                for key, value in metadata.items():
                    f.write(f"- {key}: {value}\n")
                f.write("\n")

            f.write(content)
            f.write("\n\n---\n")

        logger.info(f"Appended memory entry to {self.memory_file}")

    def mark_flushed(self):
        """Mark that memory has been flushed for this session."""
        self.memory_flushed = True
        logger.info("Memory flush completed, will not trigger again this session")

    def reset(self):
        """Reset compaction state for new session."""
        self.current_usage = TokenUsage()
        self.memory_flushed = False

    def get_usage_stats(self) -> Dict:
        """
        Get current usage statistics.

        Returns:
            Dictionary with token usage stats
        """
        total = self.current_usage.total_tokens
        effective = self.current_usage.effective_tokens

        return {
            "total_tokens": total,
            "effective_tokens": effective,
            "context_limit": self.context_limit,
            "threshold": self.threshold,
            "usage_pct": (total / self.context_limit) * 100,
            "remaining": self.context_limit - total,
            "memory_flushed": self.memory_flushed,
            "breakdown": {
                "input": self.current_usage.input_tokens,
                "output": self.current_usage.output_tokens,
                "cache_read": self.current_usage.cache_read_tokens,
                "cache_creation": self.current_usage.cache_creation_tokens
            }
        }

    def load_session_state(self) -> Dict:
        """
        Load token usage from session state file.

        Returns:
            Session state dict
        """
        if not os.path.exists(self.session_file):
            return {}

        with open(self.session_file, 'r') as f:
            return json.load(f)

    def save_session_state(self, additional_data: Optional[Dict] = None):
        """
        Save current usage to session state.

        Args:
            additional_data: Additional session data to save
        """
        os.makedirs(os.path.dirname(self.session_file), exist_ok=True)

        state = {
            "timestamp": datetime.now().isoformat(),
            "token_usage": {
                "input_tokens": self.current_usage.input_tokens,
                "output_tokens": self.current_usage.output_tokens,
                "cache_read_tokens": self.current_usage.cache_read_tokens,
                "cache_creation_tokens": self.current_usage.cache_creation_tokens,
                "total": self.current_usage.total_tokens
            },
            "compaction": {
                "memory_flushed": self.memory_flushed,
                "threshold": self.threshold,
                "context_limit": self.context_limit
            }
        }

        if additional_data:
            state.update(additional_data)

        with open(self.session_file, 'w') as f:
            json.dump(state, f, indent=2)


# Utility function for easy integration
def check_and_flush_memory(compaction_manager: AutoCompaction,
                          execute_turn: callable,
                          story_id: str) -> bool:
    """
    Check if memory flush is needed and execute if necessary.

    Args:
        compaction_manager: AutoCompaction instance
        execute_turn: Function to execute a turn (prompt -> response)
        story_id: Current story ID for metadata

    Returns:
        True if memory was flushed, False otherwise
    """
    if not compaction_manager.should_flush_memory():
        return False

    logger.info("Approaching context limit, triggering memory flush")

    # Get flush prompt
    prompt = compaction_manager.get_memory_flush_prompt()

    # Execute silent turn
    try:
        response = execute_turn(prompt)

        # Parse response
        wrote_memory = compaction_manager.parse_response(response)

        if wrote_memory:
            logger.info("Agent wrote important notes to memory")
            # Memory content is in MEMORY.md (agent wrote it)
        else:
            logger.info("Agent reported nothing significant to record")

        # Mark as flushed
        compaction_manager.mark_flushed()

        return True

    except Exception as e:
        logger.error(f"Memory flush failed: {e}")
        # Still mark as flushed to avoid infinite retry
        compaction_manager.mark_flushed()
        return False


# Example usage
if __name__ == "__main__":
    # Create compaction manager
    compaction = AutoCompaction(
        context_limit=200000,
        threshold_pct=0.90
    )

    # Simulate token usage
    compaction.update_usage(input_tokens=50000, output_tokens=10000)
    compaction.update_usage(input_tokens=60000, output_tokens=15000)
    compaction.update_usage(input_tokens=50000, output_tokens=10000)

    # Check stats
    stats = compaction.get_usage_stats()
    print(f"Usage: {stats['total_tokens']}/{stats['context_limit']} ({stats['usage_pct']:.1f}%)")

    # Check if should flush
    if compaction.should_flush_memory():
        print("Should trigger memory flush!")
        print(f"Prompt: {compaction.get_memory_flush_prompt()[:100]}...")
