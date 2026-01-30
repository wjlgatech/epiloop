#!/usr/bin/env python3
"""Tests for progress_streamer.py"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch

try:
    from lib.progress_streamer import (
        ProgressStreamer,
        get_progress_streamer,
        start_streaming,
        emit_story_started,
        emit_story_completed,
        emit_test_run,
        emit_commit_created,
        emit_error
    )
    from lib.event_bus import EventBus
    from lib.websocket_server import ClaudeLoopWebSocketServer
    HAS_DEPS = True
except ImportError:
    HAS_DEPS = False

pytestmark = pytest.mark.skipif(not HAS_DEPS, reason="dependencies not available")


@pytest.fixture
def event_bus():
    """Create test event bus"""
    return EventBus()


@pytest.fixture
def mock_ws_server():
    """Create mock WebSocket server"""
    server = Mock(spec=ClaudeLoopWebSocketServer)
    server.broadcast = AsyncMock()
    server.send_to_prd_subscribers = AsyncMock()
    return server


@pytest.fixture
def streamer(event_bus, mock_ws_server):
    """Create test progress streamer"""
    return ProgressStreamer(ws_server=mock_ws_server, event_bus=event_bus)


@pytest.mark.asyncio
async def test_story_started(streamer, mock_ws_server):
    """Test story started event"""
    await streamer.story_started('PRD-001', 'US-001', extra='data')

    # Verify WebSocket was called
    await asyncio.sleep(0.1)  # Allow event forwarding
    assert mock_ws_server.send_to_prd_subscribers.called


@pytest.mark.asyncio
async def test_story_completed(streamer, mock_ws_server):
    """Test story completed event"""
    await streamer.story_completed('PRD-001', 'US-001', success=True)

    await asyncio.sleep(0.1)
    assert mock_ws_server.send_to_prd_subscribers.called


@pytest.mark.asyncio
async def test_test_run(streamer, mock_ws_server):
    """Test test run event"""
    await streamer.test_run('PRD-001', 'US-001', passed=10, failed=2)

    await asyncio.sleep(0.1)
    assert mock_ws_server.send_to_prd_subscribers.called


@pytest.mark.asyncio
async def test_commit_created(streamer, mock_ws_server):
    """Test commit created event"""
    await streamer.commit_created('PRD-001', 'US-001', commit_hash='abc123')

    await asyncio.sleep(0.1)
    assert mock_ws_server.send_to_prd_subscribers.called


@pytest.mark.asyncio
async def test_error_occurred(streamer, mock_ws_server):
    """Test error event"""
    await streamer.error_occurred('PRD-001', 'US-001', error='Test failed')

    await asyncio.sleep(0.1)
    assert mock_ws_server.send_to_prd_subscribers.called


@pytest.mark.asyncio
async def test_prd_started(streamer, mock_ws_server):
    """Test PRD started event"""
    await streamer.prd_started('PRD-001', total_stories=5)

    await asyncio.sleep(0.1)
    assert mock_ws_server.send_to_prd_subscribers.called


@pytest.mark.asyncio
async def test_prd_completed(streamer, mock_ws_server):
    """Test PRD completed event"""
    await streamer.prd_completed('PRD-001', success=True)

    await asyncio.sleep(0.1)
    assert mock_ws_server.send_to_prd_subscribers.called


@pytest.mark.asyncio
async def test_log_message(streamer, mock_ws_server):
    """Test log message event"""
    await streamer.log_message('PRD-001', 'US-001', 'info', 'Test message')

    await asyncio.sleep(0.1)
    assert mock_ws_server.send_to_prd_subscribers.called


def test_emit_sync(streamer, mock_ws_server):
    """Test synchronous event emission"""
    streamer.emit_sync('test.event', 'PRD-001', {'message': 'sync'}, story_id='US-001')

    # Check event was added to history
    history = streamer.event_bus.get_history()
    assert len(history) > 0
    assert history[0].type == 'test.event'


@pytest.mark.asyncio
async def test_event_forwarding(event_bus, mock_ws_server):
    """Test automatic event forwarding to WebSocket"""
    streamer = ProgressStreamer(ws_server=mock_ws_server, event_bus=event_bus)

    # Emit event through event bus
    await event_bus.emit('custom.event', {'data': 'test'}, prd_id='PRD-001')

    # Allow forwarding
    await asyncio.sleep(0.1)

    # Verify WebSocket was called
    assert mock_ws_server.send_to_prd_subscribers.called


@pytest.mark.asyncio
async def test_broadcast_for_no_prd_id(event_bus, mock_ws_server):
    """Test events without PRD ID are broadcast"""
    streamer = ProgressStreamer(ws_server=mock_ws_server, event_bus=event_bus)

    # Emit event without PRD ID
    await event_bus.emit('global.event', {'data': 'test'})

    await asyncio.sleep(0.1)

    # Should broadcast instead of send to subscribers
    assert mock_ws_server.broadcast.called


def test_disabled_when_no_deps():
    """Test graceful degradation without dependencies"""
    with patch('lib.progress_streamer.HAS_DEPS', False):
        from lib.progress_streamer import ProgressStreamer
        streamer = ProgressStreamer()
        assert not streamer.enabled


def test_sync_convenience_functions():
    """Test synchronous convenience functions"""
    # These should not raise errors even if WebSocket not running
    emit_story_started('PRD-001', 'US-001')
    emit_story_completed('PRD-001', 'US-001', success=True)
    emit_test_run('PRD-001', 'US-001', passed=5, failed=1)
    emit_commit_created('PRD-001', 'US-001', commit_hash='abc123')
    emit_error('PRD-001', 'US-001', error='Test error')


def test_get_global_streamer():
    """Test global streamer singleton"""
    streamer1 = get_progress_streamer()
    streamer2 = get_progress_streamer()

    assert streamer1 is streamer2


@pytest.mark.asyncio
async def test_event_data_structure(streamer, mock_ws_server):
    """Test event data contains expected fields"""
    received_events = []

    async def capture_event(prd_id, event_type, data):
        received_events.append({'prd_id': prd_id, 'type': event_type, 'data': data})

    mock_ws_server.send_to_prd_subscribers = capture_event

    await streamer.story_started('PRD-001', 'US-001', priority=1)
    await asyncio.sleep(0.1)

    assert len(received_events) > 0
    event = received_events[0]
    assert event['prd_id'] == 'PRD-001'
    assert event['type'] == 'story.started'
    assert event['data']['story_id'] == 'US-001'
    assert event['data']['status'] == 'in_progress'
    assert event['data']['priority'] == 1


@pytest.mark.asyncio
async def test_streamer_without_ws_server(event_bus):
    """Test streamer works without WebSocket server"""
    streamer = ProgressStreamer(event_bus=event_bus)

    # Should not raise errors
    await streamer.story_started('PRD-001', 'US-001')
    await streamer.story_completed('PRD-001', 'US-001', success=True)

    # Events should be in event bus history
    history = event_bus.get_history()
    assert len(history) >= 2


@pytest.mark.asyncio
async def test_multiple_events_in_sequence(streamer, mock_ws_server):
    """Test emitting multiple events in sequence"""
    events = [
        ('story.started', lambda: streamer.story_started('PRD-001', 'US-001')),
        ('test.run', lambda: streamer.test_run('PRD-001', 'US-001', passed=10, failed=0)),
        ('commit.created', lambda: streamer.commit_created('PRD-001', 'US-001', commit_hash='abc')),
        ('story.completed', lambda: streamer.story_completed('PRD-001', 'US-001', success=True))
    ]

    for event_type, emitter in events:
        await emitter()

    await asyncio.sleep(0.1)

    # All events should have been forwarded
    assert mock_ws_server.send_to_prd_subscribers.call_count >= len(events)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
