#!/usr/bin/env python3
"""
Event Bus for Claude-Loop Event-Driven Architecture

Provides in-memory pub/sub event bus for decoupled components.
Supports event filtering, async handlers, and priority-based dispatch.

Usage:
    from lib.event_bus import EventBus, Event

    bus = EventBus()

    # Subscribe to events
    bus.subscribe('story.started', my_handler, priority=10)
    bus.subscribe('story.*', wildcard_handler)  # Wildcard support

    # Emit events
    await bus.emit('story.started', {
        'prd_id': 'PRD-001',
        'story_id': 'US-001'
    })
"""

import asyncio
import fnmatch
import logging
from collections import defaultdict
from dataclasses import dataclass, asdict, field
from datetime import datetime
from typing import Dict, List, Callable, Any, Optional, Set
from enum import Enum


logger = logging.getLogger(__name__)


class EventPriority(Enum):
    """Event handler priorities"""
    CRITICAL = 100
    HIGH = 75
    NORMAL = 50
    LOW = 25
    BACKGROUND = 0


@dataclass
class Event:
    """Event data structure"""
    type: str
    data: Dict[str, Any]
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat() + 'Z')
    source: str = 'claude-loop'
    prd_id: Optional[str] = None
    story_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return asdict(self)


@dataclass
class EventHandler:
    """Event handler registration"""
    event_pattern: str
    callback: Callable
    priority: int
    name: Optional[str] = None
    filter_func: Optional[Callable] = None

    def matches(self, event_type: str) -> bool:
        """Check if handler matches event type"""
        return fnmatch.fnmatch(event_type, self.event_pattern)

    def should_handle(self, event: Event) -> bool:
        """Check if handler should handle this event"""
        if not self.matches(event.type):
            return False
        if self.filter_func and not self.filter_func(event):
            return False
        return True


class EventBus:
    """In-memory pub/sub event bus"""

    def __init__(self):
        """Initialize event bus"""
        self.handlers: List[EventHandler] = []
        self.event_history: List[Event] = []
        self.max_history = 1000  # Keep last 1000 events
        self.stats: Dict[str, int] = defaultdict(int)

    def subscribe(
        self,
        event_pattern: str,
        callback: Callable,
        priority: int = EventPriority.NORMAL.value,
        name: Optional[str] = None,
        filter_func: Optional[Callable] = None
    ) -> str:
        """
        Subscribe to events

        Args:
            event_pattern: Event pattern (supports wildcards: 'story.*', '*')
            callback: Async function to call when event occurs
            priority: Handler priority (higher = called first)
            name: Optional handler name for identification
            filter_func: Optional filter function (return True to handle)

        Returns:
            Handler ID for later unsubscribe
        """
        handler = EventHandler(
            event_pattern=event_pattern,
            callback=callback,
            priority=priority,
            name=name or f"handler_{len(self.handlers)}",
            filter_func=filter_func
        )

        self.handlers.append(handler)

        # Sort by priority (highest first)
        self.handlers.sort(key=lambda h: h.priority, reverse=True)

        logger.debug(f"Subscribed handler '{handler.name}' to '{event_pattern}' (priority={priority})")

        return handler.name

    def unsubscribe(self, handler_name: str) -> bool:
        """
        Unsubscribe handler by name

        Args:
            handler_name: Handler name returned from subscribe

        Returns:
            True if handler was found and removed
        """
        for i, handler in enumerate(self.handlers):
            if handler.name == handler_name:
                self.handlers.pop(i)
                logger.debug(f"Unsubscribed handler '{handler_name}'")
                return True
        return False

    async def emit(
        self,
        event_type: str,
        data: Dict[str, Any],
        prd_id: Optional[str] = None,
        story_id: Optional[str] = None,
        wait: bool = True
    ) -> Event:
        """
        Emit an event

        Args:
            event_type: Event type (e.g., 'story.started')
            data: Event data
            prd_id: Optional PRD identifier
            story_id: Optional story identifier
            wait: If True, wait for all handlers to complete

        Returns:
            The emitted event
        """
        event = Event(
            type=event_type,
            data=data,
            prd_id=prd_id,
            story_id=story_id
        )

        # Add to history
        self.event_history.append(event)
        if len(self.event_history) > self.max_history:
            self.event_history.pop(0)

        # Update stats
        self.stats[event_type] += 1
        self.stats['total'] += 1

        # Find matching handlers
        matching_handlers = [
            h for h in self.handlers
            if h.should_handle(event)
        ]

        if not matching_handlers:
            logger.debug(f"No handlers for event '{event_type}'")
            return event

        logger.debug(f"Emitting '{event_type}' to {len(matching_handlers)} handlers")

        # Call handlers
        tasks = []
        for handler in matching_handlers:
            try:
                task = asyncio.create_task(handler.callback(event))
                tasks.append(task)
            except Exception as e:
                logger.error(f"Error calling handler '{handler.name}': {e}")

        # Wait for handlers if requested
        if wait and tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

        return event

    def emit_sync(
        self,
        event_type: str,
        data: Dict[str, Any],
        prd_id: Optional[str] = None,
        story_id: Optional[str] = None
    ) -> Event:
        """
        Emit event synchronously (creates event loop if needed)

        Args:
            event_type: Event type
            data: Event data
            prd_id: Optional PRD identifier
            story_id: Optional story identifier

        Returns:
            The emitted event
        """
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        return loop.run_until_complete(
            self.emit(event_type, data, prd_id, story_id)
        )

    def get_handlers(self, event_type: Optional[str] = None) -> List[EventHandler]:
        """
        Get registered handlers

        Args:
            event_type: Optional event type to filter by

        Returns:
            List of handlers
        """
        if event_type:
            return [h for h in self.handlers if h.matches(event_type)]
        return self.handlers.copy()

    def get_history(
        self,
        event_type: Optional[str] = None,
        limit: int = 100
    ) -> List[Event]:
        """
        Get event history

        Args:
            event_type: Optional event type to filter by
            limit: Maximum number of events to return

        Returns:
            List of events (most recent first)
        """
        events = self.event_history

        if event_type:
            events = [e for e in events if e.type == event_type]

        return list(reversed(events[-limit:]))

    def get_stats(self) -> Dict[str, Any]:
        """Get event statistics"""
        return {
            'total_events': self.stats['total'],
            'by_type': {k: v for k, v in self.stats.items() if k != 'total'},
            'handlers': len(self.handlers),
            'history_size': len(self.event_history)
        }

    def clear_history(self):
        """Clear event history"""
        self.event_history.clear()

    def reset_stats(self):
        """Reset statistics"""
        self.stats.clear()


# Global event bus instance
_global_bus: Optional[EventBus] = None


def get_event_bus() -> EventBus:
    """Get global event bus instance"""
    global _global_bus
    if _global_bus is None:
        _global_bus = EventBus()
    return _global_bus


# Convenience functions
async def emit(event_type: str, data: Dict[str, Any], **kwargs):
    """Emit event on global bus"""
    bus = get_event_bus()
    return await bus.emit(event_type, data, **kwargs)


def subscribe(event_pattern: str, callback: Callable, **kwargs) -> str:
    """Subscribe on global bus"""
    bus = get_event_bus()
    return bus.subscribe(event_pattern, callback, **kwargs)


def unsubscribe(handler_name: str) -> bool:
    """Unsubscribe from global bus"""
    bus = get_event_bus()
    return bus.unsubscribe(handler_name)


if __name__ == '__main__':
    # Example usage
    async def example():
        bus = EventBus()

        # Subscribe to specific event
        async def handle_story_start(event: Event):
            print(f"Story started: {event.data['story_id']}")

        bus.subscribe('story.started', handle_story_start)

        # Subscribe to wildcard
        async def handle_all_story_events(event: Event):
            print(f"Story event: {event.type}")

        bus.subscribe('story.*', handle_all_story_events, priority=EventPriority.LOW.value)

        # Emit events
        await bus.emit('story.started', {'story_id': 'US-001'})
        await bus.emit('story.completed', {'story_id': 'US-001'})

        # Get stats
        print(bus.get_stats())

    asyncio.run(example())
