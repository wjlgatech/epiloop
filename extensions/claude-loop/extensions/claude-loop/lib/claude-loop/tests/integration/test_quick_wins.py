#!/usr/bin/env python3
"""
Integration Tests for Quick Wins

Tests all four Quick Wins features working together:
- Tool Result Sanitization
- Model Failover
- Auto-Compaction with Memory Flush
- Basic Hook System
"""

import pytest
import sys
import os
import tempfile
from unittest.mock import Mock, patch

# Add lib to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'lib'))

from tool_sanitizer import ToolSanitizer, sanitize_tool_result
from model_failover import ModelFailover, ProviderConfig, Provider
from auto_compaction import AutoCompaction, check_and_flush_memory
from hooks import HookRegistry, HookType, HookContext


class TestToolSanitizationIntegration:
    """Integration tests for tool sanitization."""

    def test_sanitize_large_file_read(self):
        """Should sanitize large file reads effectively."""
        # Simulate large file content (>10KB)
        large_content = "Line of text " * 1000  # ~13KB

        sanitizer = ToolSanitizer(max_chars=8000)
        result = sanitizer.sanitize(large_content)

        # Should be truncated
        assert len(result) < len(large_content)
        assert "truncated" in result
        assert len(result) < 8200  # Max chars + marker

    def test_sanitize_nested_tool_results(self):
        """Should handle nested tool results from multiple tools."""
        # Simulate multiple tool results
        tool_results = {
            "read_file": {
                "content": "X" * 10000,
                "size": 10000
            },
            "git_diff": {
                "diff": "+" * 5000 + "\n-" * 5000,
                "files_changed": 10
            },
            "test_output": {
                "stdout": "." * 3000,
                "stderr": "Error " * 500
            }
        }

        sanitizer = ToolSanitizer(max_chars=1000)
        sanitized = sanitizer.sanitize_dict(tool_results)

        # All large values should be truncated
        assert "truncated" in sanitized["read_file"]["content"]
        assert "truncated" in sanitized["git_diff"]["diff"]
        assert "truncated" in sanitized["test_output"]["stdout"]
        assert "truncated" in sanitized["test_output"]["stderr"]

        # Numeric values are converted to strings by sanitizer
        assert sanitized["read_file"]["size"] == "10000"
        assert sanitized["git_diff"]["files_changed"] == "10"

    def test_sanitization_performance(self):
        """Sanitization should be fast even for very large inputs."""
        import time

        # 1MB of data
        large_data = "X" * (1024 * 1024)

        sanitizer = ToolSanitizer(max_chars=8000)

        start = time.time()
        result = sanitizer.sanitize(large_data)
        duration = time.time() - start

        # Should complete quickly (< 100ms)
        assert duration < 0.1
        assert "truncated" in result


class TestModelFailoverIntegration:
    """Integration tests for model failover."""

    def test_failover_with_multiple_providers(self):
        """Should failover through provider chain on failures."""
        providers = [
            ProviderConfig(Provider.ANTHROPIC, api_keys=["key1"]),
            ProviderConfig(Provider.OPENAI, api_keys=["key2"]),
            ProviderConfig(Provider.GOOGLE, api_keys=["key3"])
        ]

        failover = ModelFailover(providers=providers, backoff_base=0.01)

        call_count = {'count': 0}
        providers_tried = []

        def mock_api_call(api_key, model, provider_config):
            call_count['count'] += 1
            providers_tried.append(provider_config.provider)

            # First two providers fail
            if call_count['count'] < 3:
                error = Exception("Provider unavailable")
                error.status_code = 503
                raise error

            # Third succeeds
            return f"Success from {provider_config.provider.value}"

        result = failover.execute_with_failover(mock_api_call)

        # Should have tried all 3 providers
        assert Provider.ANTHROPIC in providers_tried
        assert Provider.OPENAI in providers_tried
        assert Provider.GOOGLE in providers_tried

        assert "google" in result.lower()

    def test_api_key_rotation_on_rate_limits(self):
        """Should rotate API keys on rate limit errors."""
        providers = [
            ProviderConfig(Provider.ANTHROPIC, api_keys=["key1", "key2", "key3"])
        ]

        failover = ModelFailover(providers=providers, backoff_base=0.01)

        call_count = {'count': 0}
        keys_tried = []

        def mock_api_call(api_key, model, provider_config):
            call_count['count'] += 1
            keys_tried.append(api_key)

            # First two keys hit rate limit
            if call_count['count'] < 3:
                error = Exception("Rate limit exceeded")
                error.status_code = 429
                raise error

            return "Success"

        result = failover.execute_with_failover(mock_api_call)

        # Should have tried multiple keys
        assert len(set(keys_tried)) >= 2
        assert result == "Success"


class TestAutoCompactionIntegration:
    """Integration tests for auto-compaction."""

    def test_memory_flush_workflow(self):
        """Should trigger memory flush when approaching limit."""
        with tempfile.TemporaryDirectory() as tmpdir:
            memory_file = os.path.join(tmpdir, "MEMORY.md")
            compaction = AutoCompaction(
                context_limit=100000,
                threshold_pct=0.90,
                memory_file=memory_file
            )

            # Simulate token usage approaching limit
            compaction.update_usage(input_tokens=80000, output_tokens=15000)

            # Should trigger flush
            assert compaction.should_flush_memory()

            # Mock execute_turn
            def mock_execute_turn(prompt):
                # Agent writes to memory
                assert "MEMORY.md" in prompt
                return "I've recorded important notes about error handling patterns"

            # Execute flush
            flushed = check_and_flush_memory(compaction, mock_execute_turn, "US-001")

            assert flushed
            assert compaction.memory_flushed

            # Should not trigger again
            assert not compaction.should_flush_memory()

    def test_session_state_persistence(self):
        """Should persist and restore session state."""
        with tempfile.TemporaryDirectory() as tmpdir:
            session_file = os.path.join(tmpdir, "state.json")

            # Create and use compaction
            compaction = AutoCompaction(session_file=session_file)
            compaction.update_usage(input_tokens=50000, output_tokens=10000)

            # Save state
            compaction.save_session_state(additional_data={'story_id': 'US-001'})

            # Load state
            state = compaction.load_session_state()

            assert state['token_usage']['total'] == 60000
            assert state['story_id'] == 'US-001'
            assert not state['compaction']['memory_flushed']


class TestHookSystemIntegration:
    """Integration tests for hook system."""

    def test_multiple_hooks_execution_order(self):
        """Should execute multiple hooks in priority order."""
        registry = HookRegistry()
        execution_log = []

        def hook1(context):
            execution_log.append(('hook1', context.story_id))
            return context

        def hook2(context):
            execution_log.append(('hook2', context.story_id))
            context.update(modified_by_hook2=True)
            return context

        def hook3(context):
            execution_log.append(('hook3', context.story_id))
            # Access data from hook2
            assert context.metadata.get('modified_by_hook2')
            return context

        # Register with different priorities
        registry.register(HookType.BEFORE_STORY_START, hook1, priority=100)
        registry.register(HookType.BEFORE_STORY_START, hook2, priority=75)
        registry.register(HookType.BEFORE_STORY_START, hook3, priority=50)

        context = HookContext(story_id="US-TEST")
        result = registry.run_hooks(HookType.BEFORE_STORY_START, context)

        # Should execute in priority order
        assert execution_log == [
            ('hook1', 'US-TEST'),
            ('hook2', 'US-TEST'),
            ('hook3', 'US-TEST')
        ]

    def test_hook_error_isolation(self):
        """Failed hooks should not prevent other hooks from running."""
        registry = HookRegistry()
        execution_log = []

        def working_hook1(context):
            execution_log.append('hook1')
            return context

        def failing_hook(context):
            execution_log.append('failing')
            raise Exception("Hook failed!")

        def working_hook2(context):
            execution_log.append('hook2')
            return context

        registry.register(HookType.BEFORE_STORY_START, working_hook1, priority=100)
        registry.register(HookType.BEFORE_STORY_START, failing_hook, priority=75)
        registry.register(HookType.BEFORE_STORY_START, working_hook2, priority=50)

        context = HookContext()
        result = registry.run_hooks(HookType.BEFORE_STORY_START, context)

        # All hooks should have executed despite failure
        assert execution_log == ['hook1', 'failing', 'hook2']


class TestQuickWinsIntegration:
    """Integration tests combining multiple Quick Wins features."""

    def test_tool_sanitization_with_hooks(self):
        """Hooks should be able to sanitize tool results."""
        registry = HookRegistry()

        def sanitize_tool_result_hook(context: HookContext) -> HookContext:
            """Hook to sanitize tool results after execution."""
            if context.tool_result:
                sanitizer = ToolSanitizer(max_chars=1000)
                sanitized = sanitizer.sanitize(str(context.tool_result))
                context.tool_result = sanitized

            return context

        registry.register(
            HookType.AFTER_TOOL_CALL,
            sanitize_tool_result_hook,
            priority=50
        )

        # Simulate tool execution
        context = HookContext(
            tool_name="read_file",
            tool_result="X" * 10000  # Large result
        )

        result = registry.run_hooks(HookType.AFTER_TOOL_CALL, context)

        # Result should be sanitized
        assert len(result.tool_result) < 1100
        assert "truncated" in result.tool_result

    def test_compaction_with_hooks(self):
        """Hooks should run on compaction events."""
        with tempfile.TemporaryDirectory() as tmpdir:
            memory_file = os.path.join(tmpdir, "MEMORY.md")
            compaction = AutoCompaction(
                context_limit=100000,
                threshold_pct=0.90,
                memory_file=memory_file
            )

            registry = HookRegistry()
            hook_called = {'called': False}

            def compaction_hook(context: HookContext) -> HookContext:
                """Hook triggered on high token usage."""
                if context.metadata.get('approaching_limit'):
                    hook_called['called'] = True
                return context

            registry.register(HookType.BEFORE_STORY_START, compaction_hook)

            # Simulate high usage
            compaction.update_usage(input_tokens=90000, output_tokens=5000)

            # Create context indicating high usage
            context = HookContext(story_id="US-001")
            if compaction.should_flush_memory():
                context.update(approaching_limit=True)

            registry.run_hooks(HookType.BEFORE_STORY_START, context)

            assert hook_called['called']

    def test_failover_with_sanitization(self):
        """Model failover should work with result sanitization."""
        providers = [
            ProviderConfig(Provider.ANTHROPIC, api_keys=["key1"])
        ]

        failover = ModelFailover(providers=providers)

        def mock_api_call_with_large_response(api_key, model, provider_config):
            # Return large response
            return "Response line\n" * 1000  # Large output

        result = failover.execute_with_failover(mock_api_call_with_large_response)

        # Sanitize the result
        sanitized = sanitize_tool_result(result, max_chars=5000)

        assert len(sanitized) < len(result)
        assert "truncated" in sanitized

    def test_full_story_lifecycle_with_all_features(self):
        """Test complete story lifecycle using all Quick Wins."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Setup
            memory_file = os.path.join(tmpdir, "MEMORY.md")
            compaction = AutoCompaction(memory_file=memory_file, context_limit=50000)
            registry = HookRegistry()
            sanitizer = ToolSanitizer(max_chars=5000)

            events = []

            # Register lifecycle hooks
            def before_story(ctx):
                events.append('story_start')
                return ctx

            def after_story(ctx):
                events.append('story_complete')
                return ctx

            def after_tool(ctx):
                events.append('tool_call')
                # Sanitize tool result
                if ctx.tool_result:
                    ctx.tool_result = sanitizer.sanitize(str(ctx.tool_result))
                return ctx

            registry.register(HookType.BEFORE_STORY_START, before_story, priority=100)
            registry.register(HookType.AFTER_STORY_COMPLETE, after_story, priority=50)
            registry.register(HookType.AFTER_TOOL_CALL, after_tool, priority=50)

            # Simulate story execution
            context = HookContext(story_id="US-001", iteration=1)

            # 1. Story start
            context = registry.run_hooks(HookType.BEFORE_STORY_START, context)

            # 2. Tool calls with sanitization
            for i in range(5):
                context.tool_name = f"tool_{i}"
                context.tool_result = "Result " * 2000  # Large result
                context = registry.run_hooks(HookType.AFTER_TOOL_CALL, context)

                # Verify sanitization
                assert len(str(context.tool_result)) < 5200

                # Track token usage - higher to trigger memory flush
                compaction.update_usage(input_tokens=9000, output_tokens=2000)

            # 3. Check if compaction needed
            if compaction.should_flush_memory():
                events.append('memory_flush')

            # 4. Story complete
            context = registry.run_hooks(HookType.AFTER_STORY_COMPLETE, context)

            # Verify full lifecycle
            assert events == [
                'story_start',
                'tool_call',
                'tool_call',
                'tool_call',
                'tool_call',
                'tool_call',
                'memory_flush',
                'story_complete'
            ]


class TestPerformanceIntegration:
    """Performance tests for Quick Wins working together."""

    def test_combined_overhead(self):
        """All features together should have minimal overhead."""
        import time

        # Setup all features
        compaction = AutoCompaction()
        registry = HookRegistry()
        sanitizer = ToolSanitizer()

        def fast_hook(ctx):
            return ctx

        registry.register(HookType.BEFORE_STORY_START, fast_hook)
        registry.register(HookType.AFTER_STORY_COMPLETE, fast_hook)

        # Measure overhead
        start = time.time()

        for i in range(100):
            # Story lifecycle
            context = HookContext(story_id=f"US-{i}")

            # Hooks
            context = registry.run_hooks(HookType.BEFORE_STORY_START, context)

            # Sanitization
            result = sanitizer.sanitize("X" * 10000)

            # Compaction check
            compaction.update_usage(input_tokens=1000, output_tokens=500)

            # Hooks
            context = registry.run_hooks(HookType.AFTER_STORY_COMPLETE, context)

        duration = time.time() - start

        # 100 iterations should complete quickly (< 1 second)
        assert duration < 1.0
        print(f"100 iterations completed in {duration:.3f}s")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
