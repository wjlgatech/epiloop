#!/usr/bin/env python3
"""Tests for websocket_server.py"""

import pytest
import asyncio
from pathlib import Path

try:
    import socketio
    from lib.websocket_server import ClaudeLoopWebSocketServer, Event
    HAS_DEPS = True
except ImportError:
    HAS_DEPS = False

pytestmark = pytest.mark.skipif(not HAS_DEPS, reason="socketio not available")


@pytest.fixture
async def server():
    """Create test server"""
    srv = ClaudeLoopWebSocketServer(port=18791)  # Use different port for tests
    await srv.start()
    yield srv
    await srv.stop()


@pytest.fixture
async def client():
    """Create test client"""
    sio = socketio.AsyncClient()
    yield sio
    await sio.disconnect()


@pytest.mark.asyncio
async def test_server_starts(server):
    """Test server starts successfully"""
    assert server.port == 18791
    assert len(server.clients) == 0


@pytest.mark.asyncio
async def test_client_connects(server, client):
    """Test client can connect"""
    connected = asyncio.Event()

    @client.event
    async def connected_event(data):
        connected.set()

    await client.connect(f'http://127.0.0.1:{server.port}')
    await asyncio.wait_for(connected.wait(), timeout=2)

    assert len(server.clients) == 1


@pytest.mark.asyncio
async def test_broadcast_event(server, client):
    """Test broadcasting events"""
    received_event = asyncio.Event()
    received_data = {}

    @client.event
    async def event(data):
        nonlocal received_data
        received_data = data
        received_event.set()

    await client.connect(f'http://127.0.0.1:{server.port}')
    await asyncio.sleep(0.1)

    # Broadcast event
    await server.broadcast('test_event', {'message': 'hello'})

    await asyncio.wait_for(received_event.wait(), timeout=2)
    assert received_data['type'] == 'test_event'
    assert received_data['data']['message'] == 'hello'


@pytest.mark.asyncio
async def test_subscribe_to_prd(server, client):
    """Test subscribing to PRD updates"""
    received_event = asyncio.Event()
    received_data = {}

    @client.event
    async def event(data):
        nonlocal received_data
        received_data = data
        received_event.set()

    @client.event
    async def subscribed(data):
        pass

    await client.connect(f'http://127.0.0.1:{server.port}')
    await asyncio.sleep(0.1)

    # Subscribe to PRD
    await client.emit('subscribe_prd', {'prd_id': 'PRD-001'})
    await asyncio.sleep(0.1)

    # Send event to PRD subscribers
    await server.send_to_prd_subscribers('PRD-001', 'story_start', {'story_id': 'US-001'})

    await asyncio.wait_for(received_event.wait(), timeout=2)
    assert received_data['prd_id'] == 'PRD-001'


@pytest.mark.asyncio
async def test_multiple_clients(server):
    """Test multiple clients can connect"""
    clients = []

    for i in range(3):
        client = socketio.AsyncClient()
        await client.connect(f'http://127.0.0.1:{server.port}')
        clients.append(client)

    assert len(server.clients) == 3

    # Cleanup
    for client in clients:
        await client.disconnect()


@pytest.mark.asyncio
async def test_health_endpoint(server):
    """Test health check endpoint"""
    import aiohttp

    async with aiohttp.ClientSession() as session:
        async with session.get(f'http://127.0.0.1:{server.port}/health') as resp:
            assert resp.status == 200
            data = await resp.json()
            assert data['status'] == 'healthy'


@pytest.mark.asyncio
async def test_event_structure():
    """Test event dataclass"""
    event = Event(
        type='story.started',
        prd_id='PRD-001',
        timestamp='2026-01-26T12:00:00Z',
        data={'story_id': 'US-001'},
        story_id='US-001'
    )

    assert event.type == 'story.started'
    assert event.prd_id == 'PRD-001'
    assert event.story_id == 'US-001'


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
