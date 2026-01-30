#!/usr/bin/env python3
"""Tests for event_bus.py"""

import pytest
import asyncio
from lib.event_bus import EventBus, Event, EventPriority


@pytest.fixture
def bus():
    """Create test event bus"""
    return EventBus()


@pytest.mark.asyncio
async def test_subscribe_and_emit(bus):
    """Test basic subscribe and emit"""
    received = []

    async def handler(event: Event):
        received.append(event)

    bus.subscribe('test.event', handler)

    await bus.emit('test.event', {'message': 'hello'})

    assert len(received) == 1
    assert received[0].type == 'test.event'
    assert received[0].data['message'] == 'hello'


@pytest.mark.asyncio
async def test_wildcard_subscription(bus):
    """Test wildcard event subscriptions"""
    received = []

    async def handler(event: Event):
        received.append(event.type)

    bus.subscribe('story.*', handler)

    await bus.emit('story.started', {'story_id': 'US-001'})
    await bus.emit('story.completed', {'story_id': 'US-001'})
    await bus.emit('test.run', {'passed': 10})  # Should not match

    assert len(received) == 2
    assert 'story.started' in received
    assert 'story.completed' in received
    assert 'test.run' not in received


@pytest.mark.asyncio
async def test_priority_ordering(bus):
    """Test handlers called in priority order"""
    call_order = []

    async def high_priority(event: Event):
        call_order.append('high')

    async def low_priority(event: Event):
        call_order.append('low')

    async def normal_priority(event: Event):
        call_order.append('normal')

    # Register in random order
    bus.subscribe('test', normal_priority, priority=EventPriority.NORMAL.value)
    bus.subscribe('test', high_priority, priority=EventPriority.HIGH.value)
    bus.subscribe('test', low_priority, priority=EventPriority.LOW.value)

    await bus.emit('test', {})

    assert call_order == ['high', 'normal', 'low']


@pytest.mark.asyncio
async def test_filter_function(bus):
    """Test event filtering"""
    received = []

    async def handler(event: Event):
        received.append(event.prd_id)

    # Only handle events for PRD-001
    def filter_prd(event: Event):
        return event.prd_id == 'PRD-001'

    bus.subscribe('story.started', handler, filter_func=filter_prd)

    await bus.emit('story.started', {}, prd_id='PRD-001')
    await bus.emit('story.started', {}, prd_id='PRD-002')
    await bus.emit('story.started', {}, prd_id='PRD-001')

    assert len(received) == 2
    assert all(prd_id == 'PRD-001' for prd_id in received)


@pytest.mark.asyncio
async def test_unsubscribe(bus):
    """Test unsubscribing handlers"""
    received = []

    async def handler(event: Event):
        received.append(event)

    handler_id = bus.subscribe('test', handler)

    await bus.emit('test', {'count': 1})
    assert len(received) == 1

    bus.unsubscribe(handler_id)

    await bus.emit('test', {'count': 2})
    assert len(received) == 1  # No new events


@pytest.mark.asyncio
async def test_event_history(bus):
    """Test event history tracking"""
    await bus.emit('event1', {})
    await bus.emit('event2', {})
    await bus.emit('event3', {})

    history = bus.get_history()
    assert len(history) == 3
    assert history[0].type == 'event3'  # Most recent first
    assert history[-1].type == 'event1'


@pytest.mark.asyncio
async def test_event_history_filtered(bus):
    """Test filtered event history"""
    await bus.emit('story.started', {})
    await bus.emit('test.run', {})
    await bus.emit('story.completed', {})

    story_history = bus.get_history(event_type='story.started')
    assert len(story_history) == 1
    assert story_history[0].type == 'story.started'


def test_get_stats(bus):
    """Test event statistics"""
    async def run():
        await bus.emit('event1', {})
        await bus.emit('event1', {})
        await bus.emit('event2', {})

        stats = bus.get_stats()
        assert stats['total_events'] == 3
        assert stats['by_type']['event1'] == 2
        assert stats['by_type']['event2'] == 1

    asyncio.run(run())


@pytest.mark.asyncio
async def test_handler_exception_isolation(bus):
    """Test that handler exceptions don't affect other handlers"""
    results = []

    async def failing_handler(event: Event):
        raise ValueError("Handler error")

    async def working_handler(event: Event):
        results.append('success')

    bus.subscribe('test', failing_handler)
    bus.subscribe('test', working_handler)

    await bus.emit('test', {})

    # Working handler should still be called
    assert len(results) == 1


def test_sync_emit():
    """Test synchronous emit"""
    bus = EventBus()
    received = []

    async def handler(event: Event):
        received.append(event)

    bus.subscribe('test', handler)

    # Use sync emit
    event = bus.emit_sync('test', {'message': 'sync'})

    assert len(received) == 1
    assert event.type == 'test'


@pytest.mark.asyncio
async def test_no_handlers(bus):
    """Test emitting with no handlers doesn't error"""
    event = await bus.emit('no_handler', {})
    assert event.type == 'no_handler'


@pytest.mark.asyncio
async def test_get_handlers(bus):
    """Test getting registered handlers"""
    async def handler1(event: Event):
        pass

    async def handler2(event: Event):
        pass

    bus.subscribe('story.*', handler1)
    bus.subscribe('test.*', handler2)

    story_handlers = bus.get_handlers('story.started')
    assert len(story_handlers) == 1

    all_handlers = bus.get_handlers()
    assert len(all_handlers) == 2


def test_clear_history(bus):
    """Test clearing event history"""
    async def run():
        await bus.emit('event1', {})
        await bus.emit('event2', {})

        assert len(bus.get_history()) == 2

        bus.clear_history()

        assert len(bus.get_history()) == 0

    asyncio.run(run())


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
