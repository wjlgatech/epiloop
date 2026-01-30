#!/usr/bin/env python3
"""Tests for Basic Hook System"""

import pytest
import asyncio
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'lib'))

from hooks import (
    HookRegistry,
    HookType,
    HookContext,
    Hook,
    register_hook,
    unregister_hook,
    run_hooks,
    get_registry
)


class TestHookContext:
    """Test hook context functionality."""

    def test_initialization(self):
        """Should initialize with default values."""
        context = HookContext()

        assert context.story_id is None
        assert context.prd_data is None
        assert context.session_id is None
        assert context.iteration == 0
        assert context.metadata == {}

    def test_initialization_with_values(self):
        """Should initialize with provided values."""
        context = HookContext(
            story_id="US-001",
            prd_data={"project": "test"},
            session_id="session-123",
            iteration=5
        )

        assert context.story_id == "US-001"
        assert context.prd_data == {"project": "test"}
        assert context.session_id == "session-123"
        assert context.iteration == 5

    def test_update_existing_field(self):
        """Should update existing fields."""
        context = HookContext(story_id="US-001")
        context.update(story_id="US-002")

        assert context.story_id == "US-002"

    def test_update_metadata(self):
        """Should add new fields to metadata."""
        context = HookContext()
        context.update(custom_field="value")

        assert context.metadata["custom_field"] == "value"

    def test_update_returns_self(self):
        """Update should return context for chaining."""
        context = HookContext()
        result = context.update(story_id="US-001")

        assert result is context


class TestHookRegistry:
    """Test hook registry functionality."""

    def test_initialization(self):
        """Should initialize with empty hooks."""
        registry = HookRegistry()

        for hook_type in HookType:
            assert len(registry.get_hooks(hook_type)) == 0

    def test_register_hook(self):
        """Should register a hook."""
        registry = HookRegistry()

        def my_hook(context):
            return context

        name = registry.register(HookType.BEFORE_STORY_START, my_hook)

        assert name == "my_hook"
        hooks = registry.get_hooks(HookType.BEFORE_STORY_START)
        assert len(hooks) == 1
        assert hooks[0].name == "my_hook"

    def test_register_with_custom_name(self):
        """Should register hook with custom name."""
        registry = HookRegistry()

        def my_hook(context):
            return context

        name = registry.register(HookType.BEFORE_STORY_START, my_hook, name="custom_name")

        assert name == "custom_name"
        hooks = registry.get_hooks(HookType.BEFORE_STORY_START)
        assert hooks[0].name == "custom_name"

    def test_register_with_priority(self):
        """Should register hook with priority."""
        registry = HookRegistry()

        def hook1(context):
            return context

        def hook2(context):
            return context

        registry.register(HookType.BEFORE_STORY_START, hook1, priority=50)
        registry.register(HookType.BEFORE_STORY_START, hook2, priority=100)

        hooks = registry.get_hooks(HookType.BEFORE_STORY_START)
        # Higher priority comes first
        assert hooks[0].name == "hook2"
        assert hooks[1].name == "hook1"

    def test_unregister_hook(self):
        """Should unregister a hook."""
        registry = HookRegistry()

        def my_hook(context):
            return context

        registry.register(HookType.BEFORE_STORY_START, my_hook)
        assert len(registry.get_hooks(HookType.BEFORE_STORY_START)) == 1

        removed = registry.unregister(HookType.BEFORE_STORY_START, "my_hook")

        assert removed
        assert len(registry.get_hooks(HookType.BEFORE_STORY_START)) == 0

    def test_unregister_nonexistent_hook(self):
        """Should return False for nonexistent hook."""
        registry = HookRegistry()

        removed = registry.unregister(HookType.BEFORE_STORY_START, "nonexistent")

        assert not removed

    def test_clear_specific_hook_type(self):
        """Should clear hooks for specific type."""
        registry = HookRegistry()

        def hook1(context):
            return context

        def hook2(context):
            return context

        registry.register(HookType.BEFORE_STORY_START, hook1)
        registry.register(HookType.AFTER_STORY_COMPLETE, hook2)

        registry.clear(HookType.BEFORE_STORY_START)

        assert len(registry.get_hooks(HookType.BEFORE_STORY_START)) == 0
        assert len(registry.get_hooks(HookType.AFTER_STORY_COMPLETE)) == 1

    def test_clear_all_hooks(self):
        """Should clear all hooks."""
        registry = HookRegistry()

        def hook(context):
            return context

        registry.register(HookType.BEFORE_STORY_START, hook)
        registry.register(HookType.AFTER_STORY_COMPLETE, hook)

        registry.clear()

        assert registry.count() == 0

    def test_count_specific_type(self):
        """Should count hooks for specific type."""
        registry = HookRegistry()

        def hook(context):
            return context

        registry.register(HookType.BEFORE_STORY_START, hook)
        registry.register(HookType.BEFORE_STORY_START, hook, name="hook2")

        assert registry.count(HookType.BEFORE_STORY_START) == 2

    def test_count_all_hooks(self):
        """Should count all hooks."""
        registry = HookRegistry()

        def hook(context):
            return context

        registry.register(HookType.BEFORE_STORY_START, hook)
        registry.register(HookType.AFTER_STORY_COMPLETE, hook, name="hook2")

        assert registry.count() == 2


class TestHookExecution:
    """Test hook execution."""

    def test_run_single_hook(self):
        """Should execute a single hook."""
        registry = HookRegistry()
        call_count = {'count': 0}

        def my_hook(context):
            call_count['count'] += 1
            return context

        registry.register(HookType.BEFORE_STORY_START, my_hook)
        context = HookContext(story_id="US-001")

        result = registry.run_hooks(HookType.BEFORE_STORY_START, context)

        assert call_count['count'] == 1
        assert result.story_id == "US-001"

    def test_run_multiple_hooks_in_priority_order(self):
        """Should execute hooks in priority order."""
        registry = HookRegistry()
        execution_order = []

        def hook1(context):
            execution_order.append(1)
            return context

        def hook2(context):
            execution_order.append(2)
            return context

        def hook3(context):
            execution_order.append(3)
            return context

        registry.register(HookType.BEFORE_STORY_START, hook1, priority=50)
        registry.register(HookType.BEFORE_STORY_START, hook2, priority=100)  # Highest
        registry.register(HookType.BEFORE_STORY_START, hook3, priority=75)

        context = HookContext()
        registry.run_hooks(HookType.BEFORE_STORY_START, context)

        # Should execute in priority order: 100, 75, 50
        assert execution_order == [2, 3, 1]

    def test_hook_can_modify_context(self):
        """Hooks should be able to modify context."""
        registry = HookRegistry()

        def modifier_hook(context):
            context.update(story_id="MODIFIED")
            return context

        registry.register(HookType.BEFORE_STORY_START, modifier_hook)
        context = HookContext(story_id="ORIGINAL")

        result = registry.run_hooks(HookType.BEFORE_STORY_START, context)

        assert result.story_id == "MODIFIED"

    def test_hook_context_flows_through_chain(self):
        """Context modifications should flow through hook chain."""
        registry = HookRegistry()

        def hook1(context):
            context.update(value=1)
            return context

        def hook2(context):
            context.update(value=context.metadata['value'] + 1)
            return context

        registry.register(HookType.BEFORE_STORY_START, hook1, priority=100)
        registry.register(HookType.BEFORE_STORY_START, hook2, priority=50)

        context = HookContext()
        result = registry.run_hooks(HookType.BEFORE_STORY_START, context)

        assert result.metadata['value'] == 2

    def test_error_isolation(self):
        """Failed hook should not prevent other hooks from running."""
        registry = HookRegistry()
        execution_order = []

        def good_hook1(context):
            execution_order.append(1)
            return context

        def failing_hook(context):
            execution_order.append(2)
            raise Exception("Hook failed!")

        def good_hook2(context):
            execution_order.append(3)
            return context

        registry.register(HookType.BEFORE_STORY_START, good_hook1, priority=100)
        registry.register(HookType.BEFORE_STORY_START, failing_hook, priority=75)
        registry.register(HookType.BEFORE_STORY_START, good_hook2, priority=50)

        context = HookContext()
        # Should not raise despite failing_hook error
        result = registry.run_hooks(HookType.BEFORE_STORY_START, context)

        # All hooks should have executed
        assert execution_order == [1, 2, 3]

    def test_hook_returning_none(self):
        """Hook returning None should not break chain."""
        registry = HookRegistry()

        def hook1(context):
            context.update(value=1)
            return context

        def hook_returning_none(context):
            # Doesn't return anything
            pass

        def hook2(context):
            context.update(value=context.metadata['value'] + 1)
            return context

        registry.register(HookType.BEFORE_STORY_START, hook1, priority=100)
        registry.register(HookType.BEFORE_STORY_START, hook_returning_none, priority=75)
        registry.register(HookType.BEFORE_STORY_START, hook2, priority=50)

        context = HookContext()
        result = registry.run_hooks(HookType.BEFORE_STORY_START, context)

        # Context should still flow through
        assert result.metadata['value'] == 2

    def test_no_hooks_registered(self):
        """Running hooks with none registered should return context unchanged."""
        registry = HookRegistry()
        context = HookContext(story_id="US-001")

        result = registry.run_hooks(HookType.BEFORE_STORY_START, context)

        assert result.story_id == "US-001"


class TestAsyncHooks:
    """Test async hook support."""

    def test_register_async_hook(self):
        """Should register async hook."""
        registry = HookRegistry()

        async def async_hook(context):
            return context

        registry.register(HookType.BEFORE_STORY_START, async_hook, async_hook=True)

        hooks = registry.get_hooks(HookType.BEFORE_STORY_START)
        assert hooks[0].async_hook

    def test_run_async_hook_in_sync_context(self):
        """Should run async hook in sync context."""
        registry = HookRegistry()
        call_count = {'count': 0}

        async def async_hook(context):
            call_count['count'] += 1
            return context

        registry.register(HookType.BEFORE_STORY_START, async_hook, async_hook=True)
        context = HookContext()

        result = registry.run_hooks(HookType.BEFORE_STORY_START, context)

        assert call_count['count'] == 1

    @pytest.mark.asyncio
    async def test_run_hooks_async(self):
        """Should run hooks asynchronously."""
        registry = HookRegistry()
        call_count = {'count': 0}

        async def async_hook(context):
            call_count['count'] += 1
            await asyncio.sleep(0.01)
            return context

        registry.register(HookType.BEFORE_STORY_START, async_hook, async_hook=True)
        context = HookContext()

        result = await registry.run_hooks_async(HookType.BEFORE_STORY_START, context)

        assert call_count['count'] == 1

    @pytest.mark.asyncio
    async def test_mix_sync_and_async_hooks(self):
        """Should handle mix of sync and async hooks."""
        registry = HookRegistry()
        execution_order = []

        def sync_hook(context):
            execution_order.append('sync')
            return context

        async def async_hook(context):
            execution_order.append('async')
            return context

        registry.register(HookType.BEFORE_STORY_START, sync_hook, priority=100)
        registry.register(HookType.BEFORE_STORY_START, async_hook, priority=50, async_hook=True)

        context = HookContext()
        result = await registry.run_hooks_async(HookType.BEFORE_STORY_START, context)

        assert execution_order == ['sync', 'async']


class TestGlobalRegistry:
    """Test global registry functions."""

    def test_register_to_global_registry(self):
        """Should register to global registry."""
        # Clear global registry first
        get_registry().clear()

        def my_hook(context):
            return context

        name = register_hook(HookType.BEFORE_STORY_START, my_hook)

        assert name == "my_hook"
        assert get_registry().count(HookType.BEFORE_STORY_START) == 1

    def test_unregister_from_global_registry(self):
        """Should unregister from global registry."""
        get_registry().clear()

        def my_hook(context):
            return context

        register_hook(HookType.BEFORE_STORY_START, my_hook)
        removed = unregister_hook(HookType.BEFORE_STORY_START, "my_hook")

        assert removed
        assert get_registry().count(HookType.BEFORE_STORY_START) == 0

    def test_run_global_hooks(self):
        """Should run hooks from global registry."""
        get_registry().clear()
        call_count = {'count': 0}

        def my_hook(context):
            call_count['count'] += 1
            return context

        register_hook(HookType.BEFORE_STORY_START, my_hook)
        context = HookContext()

        result = run_hooks(HookType.BEFORE_STORY_START, context)

        assert call_count['count'] == 1


class TestAllHookTypes:
    """Test all lifecycle hook types."""

    def test_all_hook_types_available(self):
        """All hook types should be available."""
        expected_types = {
            HookType.BEFORE_STORY_START,
            HookType.AFTER_STORY_COMPLETE,
            HookType.BEFORE_TOOL_CALL,
            HookType.AFTER_TOOL_CALL,
            HookType.ON_ERROR,
            HookType.ON_SESSION_END
        }

        assert set(HookType) == expected_types

    def test_register_all_hook_types(self):
        """Should be able to register to all hook types."""
        registry = HookRegistry()

        def my_hook(context):
            return context

        for hook_type in HookType:
            registry.register(hook_type, my_hook, name=f"hook_{hook_type.value}")

        assert registry.count() == len(HookType)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
