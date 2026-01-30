#!/usr/bin/env python3
"""
Integration test for Stage 2: WebSocket + Event Bus + Progress Streaming

Tests the full flow:
1. Start WebSocket server
2. Connect client
3. Emit events through progress streamer
4. Verify events received by client
"""

import pytest
import asyncio
from unittest.mock import AsyncMock

try:
    import socketio
    from lib.websocket_server import ClaudeLoopWebSocketServer
    from lib.event_bus import EventBus
    from lib.progress_streamer import ProgressStreamer
    HAS_DEPS = True
except ImportError:
    HAS_DEPS = False

pytestmark = pytest.mark.skipif(not HAS_DEPS, reason="dependencies not available")


@pytest.mark.asyncio
async def test_full_integration_flow():
    """Test complete flow from event emission to client reception"""
    # Start WebSocket server
    server = ClaudeLoopWebSocketServer(port=18791)  # Different port for testing
    await server.start()

    # Create progress streamer
    event_bus = EventBus()
    streamer = ProgressStreamer(ws_server=server, event_bus=event_bus)

    # Connect client
    client = socketio.AsyncClient()
    received_events = []

    @client.event
    async def event(data):
        received_events.append(data)

    try:
        # Connect
        await client.connect(f'http://127.0.0.1:18791')
        await asyncio.sleep(0.2)  # Allow connection to establish

        # Subscribe to PRD
        await client.emit('subscribe_prd', {'prd_id': 'PRD-TEST'})
        await asyncio.sleep(0.1)

        # Emit story lifecycle events
        await streamer.story_started('PRD-TEST', 'US-001', priority=1)
        await asyncio.sleep(0.1)

        await streamer.test_run('PRD-TEST', 'US-001', passed=10, failed=0)
        await asyncio.sleep(0.1)

        await streamer.commit_created('PRD-TEST', 'US-001', commit_hash='abc123')
        await asyncio.sleep(0.1)

        await streamer.story_completed('PRD-TEST', 'US-001', success=True)
        await asyncio.sleep(0.2)

        # Verify events received
        assert len(received_events) >= 4, f"Expected 4+ events, got {len(received_events)}"

        # Check event types
        event_types = [e['type'] for e in received_events]
        assert 'story.started' in event_types
        assert 'test.run' in event_types
        assert 'commit.created' in event_types
        assert 'story.completed' in event_types

        # Check PRD IDs
        for event in received_events:
            assert event['prd_id'] == 'PRD-TEST'

    finally:
        # Cleanup
        await client.disconnect()
        await server.stop()


@pytest.mark.asyncio
async def test_multiple_clients():
    """Test multiple clients receiving same events"""
    server = ClaudeLoopWebSocketServer(port=18792)
    await server.start()

    event_bus = EventBus()
    streamer = ProgressStreamer(ws_server=server, event_bus=event_bus)

    # Create two clients
    client1_events = []
    client2_events = []

    client1 = socketio.AsyncClient()
    client2 = socketio.AsyncClient()

    @client1.event
    async def event(data):
        client1_events.append(data)

    @client2.event
    async def event(data):
        client2_events.append(data)

    try:
        # Connect both clients
        await client1.connect(f'http://127.0.0.1:18792')
        await client2.connect(f'http://127.0.0.1:18792')
        await asyncio.sleep(0.2)

        # Subscribe to same PRD
        await client1.emit('subscribe_prd', {'prd_id': 'PRD-MULTI'})
        await client2.emit('subscribe_prd', {'prd_id': 'PRD-MULTI'})
        await asyncio.sleep(0.1)

        # Emit event
        await streamer.story_started('PRD-MULTI', 'US-001')
        await asyncio.sleep(0.2)

        # Both should receive event
        assert len(client1_events) >= 1
        assert len(client2_events) >= 1

        assert client1_events[0]['type'] == 'story.started'
        assert client2_events[0]['type'] == 'story.started'

    finally:
        await client1.disconnect()
        await client2.disconnect()
        await server.stop()


@pytest.mark.asyncio
async def test_prd_filtering():
    """Test that clients only receive events for subscribed PRDs"""
    server = ClaudeLoopWebSocketServer(port=18793)
    await server.start()

    event_bus = EventBus()
    streamer = ProgressStreamer(ws_server=server, event_bus=event_bus)

    client = socketio.AsyncClient()
    received_events = []

    @client.event
    async def event(data):
        received_events.append(data)

    try:
        await client.connect(f'http://127.0.0.1:18793')
        await asyncio.sleep(0.2)

        # Subscribe to PRD-001 only
        await client.emit('subscribe_prd', {'prd_id': 'PRD-001'})
        await asyncio.sleep(0.1)

        # Emit events for different PRDs
        await streamer.story_started('PRD-001', 'US-001')
        await streamer.story_started('PRD-002', 'US-002')
        await streamer.story_started('PRD-001', 'US-003')
        await asyncio.sleep(0.3)

        # Should only receive PRD-001 events
        prd_ids = [e['prd_id'] for e in received_events]
        assert all(prd == 'PRD-001' for prd in prd_ids), f"Got PRDs: {prd_ids}"

    finally:
        await client.disconnect()
        await server.stop()


@pytest.mark.asyncio
async def test_event_bus_priority():
    """Test that high priority handlers execute first"""
    from lib.event_bus import EventPriority

    event_bus = EventBus()
    call_order = []

    async def high_priority(event):
        call_order.append('high')

    async def normal_priority(event):
        call_order.append('normal')

    async def low_priority(event):
        call_order.append('low')

    # Register in reverse order
    event_bus.subscribe('test', low_priority, priority=EventPriority.LOW.value)
    event_bus.subscribe('test', normal_priority, priority=EventPriority.NORMAL.value)
    event_bus.subscribe('test', high_priority, priority=EventPriority.HIGH.value)

    # Emit event
    await event_bus.emit('test', {})

    # Verify priority order
    assert call_order == ['high', 'normal', 'low']


@pytest.mark.asyncio
async def test_error_isolation():
    """Test that errors in one handler don't affect others"""
    event_bus = EventBus()
    results = []

    async def failing_handler(event):
        raise ValueError("Test error")

    async def working_handler(event):
        results.append('success')

    event_bus.subscribe('test', failing_handler)
    event_bus.subscribe('test', working_handler)

    # Emit event
    await event_bus.emit('test', {})

    # Working handler should still execute
    assert len(results) == 1
    assert results[0] == 'success'


def test_session_lock_basic():
    """Test basic session lock functionality"""
    from lib.session_lock import SessionLock

    lock1 = SessionLock('test-integration-lock', timeout=5)
    lock2 = SessionLock('test-integration-lock', timeout=1)

    # Acquire first lock
    assert lock1.acquire()

    # Second lock should fail (non-blocking)
    assert not lock2.acquire(blocking=False)

    # Release first lock
    lock1.release()

    # Now second should succeed
    assert lock2.acquire(blocking=False)
    lock2.release()


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
