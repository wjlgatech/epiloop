#!/usr/bin/env python3
"""
Basic Hook System

Provides lifecycle hooks for customizing behavior without modifying core code.
Supports priority-based execution, error isolation, and async hooks.

Inspired by clawdbot's plugin architecture.
"""

import logging
import asyncio
from typing import Dict, List, Callable, Any, Optional
from dataclasses import dataclass, field
from enum import Enum

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class HookType(Enum):
    """Available lifecycle hooks."""
    BEFORE_STORY_START = "before_story_start"
    AFTER_STORY_COMPLETE = "after_story_complete"
    BEFORE_TOOL_CALL = "before_tool_call"
    AFTER_TOOL_CALL = "after_tool_call"
    ON_ERROR = "on_error"
    ON_SESSION_END = "on_session_end"


@dataclass
class HookContext:
    """Context passed to all hooks."""
    story_id: Optional[str] = None
    prd_data: Optional[Dict] = None
    session_id: Optional[str] = None
    iteration: int = 0
    tool_name: Optional[str] = None
    tool_args: Optional[Dict] = None
    tool_result: Optional[Any] = None
    error: Optional[Exception] = None
    metadata: Dict = field(default_factory=dict)

    def update(self, **kwargs) -> 'HookContext':
        """Update context with new values."""
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)
            else:
                self.metadata[key] = value
        return self


@dataclass
class Hook:
    """A registered hook function."""
    name: str
    hook_type: HookType
    callback: Callable
    priority: int = 50  # Higher = runs first
    async_hook: bool = False


class HookRegistry:
    """
    Manages hook registration and execution.

    Supports:
    - Priority-based execution
    - Error isolation (failed hook doesn't crash others)
    - Async hooks
    - Context modification
    """

    def __init__(self):
        """Initialize hook registry."""
        self._hooks: Dict[HookType, List[Hook]] = {
            hook_type: [] for hook_type in HookType
        }

    def register(self,
                hook_type: HookType,
                callback: Callable,
                name: Optional[str] = None,
                priority: int = 50,
                async_hook: bool = False) -> str:
        """
        Register a hook function.

        Args:
            hook_type: Type of lifecycle hook
            callback: Function to call (context) -> context or None
            name: Optional hook name (defaults to function name)
            priority: Execution priority (higher = earlier, default: 50)
            async_hook: Whether callback is async

        Returns:
            Hook name
        """
        hook_name = name or callback.__name__

        hook = Hook(
            name=hook_name,
            hook_type=hook_type,
            callback=callback,
            priority=priority,
            async_hook=async_hook
        )

        self._hooks[hook_type].append(hook)

        # Sort by priority (descending)
        self._hooks[hook_type].sort(key=lambda h: h.priority, reverse=True)

        logger.info(f"Registered hook: {hook_name} for {hook_type.value} (priority: {priority})")

        return hook_name

    def unregister(self, hook_type: HookType, name: str) -> bool:
        """
        Unregister a hook.

        Args:
            hook_type: Type of hook
            name: Hook name

        Returns:
            True if hook was found and removed
        """
        hooks = self._hooks[hook_type]
        initial_len = len(hooks)

        self._hooks[hook_type] = [h for h in hooks if h.name != name]

        removed = len(self._hooks[hook_type]) < initial_len
        if removed:
            logger.info(f"Unregistered hook: {name} from {hook_type.value}")

        return removed

    def get_hooks(self, hook_type: HookType) -> List[Hook]:
        """Get all hooks for a type (sorted by priority)."""
        return self._hooks[hook_type].copy()

    def run_hooks(self, hook_type: HookType, context: HookContext) -> HookContext:
        """
        Execute all hooks for a type synchronously.

        Args:
            hook_type: Type of hook to execute
            context: Context to pass to hooks

        Returns:
            Modified context (hooks can update it)
        """
        hooks = self.get_hooks(hook_type)

        logger.debug(f"Running {len(hooks)} hooks for {hook_type.value}")

        for hook in hooks:
            try:
                logger.debug(f"  Executing hook: {hook.name} (priority: {hook.priority})")

                if hook.async_hook:
                    # Run async hook in sync context
                    result = asyncio.run(hook.callback(context))
                else:
                    result = hook.callback(context)

                # If hook returns context, use it
                if isinstance(result, HookContext):
                    context = result
                elif result is not None:
                    logger.warning(f"Hook {hook.name} returned {type(result)}, expected HookContext or None")

            except Exception as e:
                # Error isolation: log but continue with other hooks
                logger.error(f"Hook {hook.name} failed: {e}")
                logger.debug(f"Hook error details:", exc_info=True)
                # Don't crash - continue with next hook

        return context

    async def run_hooks_async(self, hook_type: HookType, context: HookContext) -> HookContext:
        """
        Execute all hooks for a type asynchronously.

        Args:
            hook_type: Type of hook to execute
            context: Context to pass to hooks

        Returns:
            Modified context
        """
        hooks = self.get_hooks(hook_type)

        logger.debug(f"Running {len(hooks)} hooks for {hook_type.value} (async)")

        for hook in hooks:
            try:
                logger.debug(f"  Executing hook: {hook.name} (priority: {hook.priority})")

                if hook.async_hook:
                    result = await hook.callback(context)
                else:
                    # Run sync hook in async context
                    result = hook.callback(context)

                if isinstance(result, HookContext):
                    context = result

            except Exception as e:
                logger.error(f"Hook {hook.name} failed: {e}")
                logger.debug(f"Hook error details:", exc_info=True)

        return context

    def clear(self, hook_type: Optional[HookType] = None):
        """
        Clear hooks.

        Args:
            hook_type: Specific hook type to clear (None = clear all)
        """
        if hook_type:
            self._hooks[hook_type].clear()
            logger.info(f"Cleared hooks for {hook_type.value}")
        else:
            for ht in HookType:
                self._hooks[ht].clear()
            logger.info("Cleared all hooks")

    def count(self, hook_type: Optional[HookType] = None) -> int:
        """
        Count registered hooks.

        Args:
            hook_type: Specific hook type (None = count all)

        Returns:
            Number of registered hooks
        """
        if hook_type:
            return len(self._hooks[hook_type])
        else:
            return sum(len(hooks) for hooks in self._hooks.values())


# Global registry instance
_global_registry = HookRegistry()


def register_hook(hook_type: HookType,
                 callback: Callable,
                 name: Optional[str] = None,
                 priority: int = 50,
                 async_hook: bool = False) -> str:
    """
    Register a hook in the global registry.

    Args:
        hook_type: Type of lifecycle hook
        callback: Function to call
        name: Optional hook name
        priority: Execution priority
        async_hook: Whether callback is async

    Returns:
        Hook name
    """
    return _global_registry.register(hook_type, callback, name, priority, async_hook)


def unregister_hook(hook_type: HookType, name: str) -> bool:
    """Unregister a hook from the global registry."""
    return _global_registry.unregister(hook_type, name)


def run_hooks(hook_type: HookType, context: HookContext) -> HookContext:
    """Execute hooks from the global registry."""
    return _global_registry.run_hooks(hook_type, context)


async def run_hooks_async(hook_type: HookType, context: HookContext) -> HookContext:
    """Execute hooks from the global registry (async)."""
    return await _global_registry.run_hooks_async(hook_type, context)


def get_registry() -> HookRegistry:
    """Get the global hook registry."""
    return _global_registry


# Example hooks
def example_before_story(context: HookContext) -> HookContext:
    """Example hook that runs before a story starts."""
    logger.info(f"Starting story: {context.story_id}")
    return context


def example_after_tool_call(context: HookContext) -> HookContext:
    """Example hook that logs tool calls."""
    logger.info(f"Tool called: {context.tool_name} with result: {str(context.tool_result)[:50]}")
    return context


def example_on_error(context: HookContext) -> HookContext:
    """Example error handler hook."""
    if context.error:
        logger.error(f"Error in story {context.story_id}: {context.error}")
    return context


# Example usage
if __name__ == "__main__":
    # Create registry
    registry = HookRegistry()

    # Register hooks
    registry.register(
        HookType.BEFORE_STORY_START,
        example_before_story,
        priority=100  # High priority = runs first
    )

    registry.register(
        HookType.AFTER_TOOL_CALL,
        example_after_tool_call,
        priority=50
    )

    registry.register(
        HookType.ON_ERROR,
        example_on_error,
        priority=75
    )

    # Create context
    context = HookContext(
        story_id="US-001",
        prd_data={"project": "test"},
        session_id="session-123"
    )

    # Run hooks
    context = registry.run_hooks(HookType.BEFORE_STORY_START, context)

    # Simulate tool call
    context.tool_name = "read_file"
    context.tool_result = "File contents..."
    context = registry.run_hooks(HookType.AFTER_TOOL_CALL, context)

    # Simulate error
    context.error = Exception("Test error")
    context = registry.run_hooks(HookType.ON_ERROR, context)

    print(f"\nRegistry has {registry.count()} hooks registered")
