#!/usr/bin/env python3
"""
Progress Streamer - Integration between claude-loop and WebSocket server

Automatically sends progress events to WebSocket clients when stories execute.
Works with coordinator and worker to provide real-time updates.

Usage:
    from lib.progress_streamer import ProgressStreamer, start_streaming

    # Initialize (call once at startup)
    streamer = start_streaming()

    # Events are automatically sent when using the functions below:
    await streamer.story_started('PRD-001', 'US-001')
    await streamer.story_completed('PRD-001', 'US-001', success=True)
    await streamer.test_run('PRD-001', 'US-001', passed=10, failed=2)
    await streamer.commit_created('PRD-001', 'US-001', commit_hash='abc123')
    await streamer.error_occurred('PRD-001', 'US-001', error='Test failed')
"""

import asyncio
import json
import logging
from typing import Optional, Dict, Any
from pathlib import Path

try:
    from lib.websocket_server import ClaudeLoopWebSocketServer
    from lib.event_bus import EventBus, Event, EventPriority
    HAS_DEPS = True
except ImportError:
    HAS_DEPS = False


logger = logging.getLogger(__name__)


class ProgressStreamer:
    """Streams progress events to WebSocket clients"""

    def __init__(self, ws_server: Optional['ClaudeLoopWebSocketServer'] = None, event_bus: Optional[EventBus] = None):
        """
        Initialize progress streamer

        Args:
            ws_server: WebSocket server instance (creates if None)
            event_bus: Event bus instance (creates if None)
        """
        if not HAS_DEPS:
            logger.warning("WebSocket dependencies not available, streaming disabled")
            self.enabled = False
            return

        self.enabled = True
        self.ws_server = ws_server
        self.event_bus = event_bus or EventBus()

        # Subscribe to events if we have WebSocket server
        if self.ws_server:
            self._setup_event_forwarding()

    def _setup_event_forwarding(self):
        """Forward event bus events to WebSocket clients"""

        async def forward_to_websocket(event: Event):
            """Forward event to WebSocket subscribers"""
            if event.prd_id:
                await self.ws_server.send_to_prd_subscribers(
                    event.prd_id,
                    event.type,
                    event.data
                )
            else:
                await self.ws_server.broadcast(event.type, event.data)

        # Subscribe to all events with low priority (let others handle first)
        self.event_bus.subscribe(
            '*',
            forward_to_websocket,
            priority=EventPriority.BACKGROUND.value,
            name='websocket_forwarder'
        )

    async def story_started(self, prd_id: str, story_id: str, **kwargs):
        """Emit story started event"""
        if not self.enabled:
            return

        await self.event_bus.emit(
            'story.started',
            {
                'story_id': story_id,
                'status': 'in_progress',
                **kwargs
            },
            prd_id=prd_id,
            story_id=story_id
        )

    async def story_completed(self, prd_id: str, story_id: str, success: bool = True, **kwargs):
        """Emit story completed event"""
        if not self.enabled:
            return

        await self.event_bus.emit(
            'story.completed',
            {
                'story_id': story_id,
                'success': success,
                'status': 'completed' if success else 'failed',
                **kwargs
            },
            prd_id=prd_id,
            story_id=story_id
        )

    async def test_run(self, prd_id: str, story_id: str, passed: int, failed: int, **kwargs):
        """Emit test run event"""
        if not self.enabled:
            return

        await self.event_bus.emit(
            'test.run',
            {
                'story_id': story_id,
                'passed': passed,
                'failed': failed,
                'total': passed + failed,
                **kwargs
            },
            prd_id=prd_id,
            story_id=story_id
        )

    async def commit_created(self, prd_id: str, story_id: str, commit_hash: str, **kwargs):
        """Emit commit created event"""
        if not self.enabled:
            return

        await self.event_bus.emit(
            'commit.created',
            {
                'story_id': story_id,
                'commit_hash': commit_hash,
                **kwargs
            },
            prd_id=prd_id,
            story_id=story_id
        )

    async def error_occurred(self, prd_id: str, story_id: str, error: str, **kwargs):
        """Emit error event"""
        if not self.enabled:
            return

        await self.event_bus.emit(
            'error.occurred',
            {
                'story_id': story_id,
                'error': error,
                **kwargs
            },
            prd_id=prd_id,
            story_id=story_id
        )

    async def prd_started(self, prd_id: str, **kwargs):
        """Emit PRD started event"""
        if not self.enabled:
            return

        await self.event_bus.emit(
            'prd.started',
            {
                'status': 'running',
                **kwargs
            },
            prd_id=prd_id
        )

    async def prd_completed(self, prd_id: str, success: bool = True, **kwargs):
        """Emit PRD completed event"""
        if not self.enabled:
            return

        await self.event_bus.emit(
            'prd.completed',
            {
                'success': success,
                'status': 'completed' if success else 'failed',
                **kwargs
            },
            prd_id=prd_id
        )

    async def log_message(self, prd_id: str, story_id: Optional[str], level: str, message: str):
        """Emit log message event"""
        if not self.enabled:
            return

        await self.event_bus.emit(
            'log.message',
            {
                'level': level,
                'message': message,
                'story_id': story_id
            },
            prd_id=prd_id,
            story_id=story_id
        )

    def emit_sync(self, event_type: str, prd_id: str, data: Dict[str, Any], story_id: Optional[str] = None):
        """
        Emit event synchronously (for use in non-async code)

        Args:
            event_type: Event type
            prd_id: PRD identifier
            data: Event data
            story_id: Optional story identifier
        """
        if not self.enabled:
            return

        self.event_bus.emit_sync(event_type, data, prd_id=prd_id, story_id=story_id)


# Global streamer instance
_global_streamer: Optional[ProgressStreamer] = None


def get_progress_streamer() -> ProgressStreamer:
    """Get global progress streamer instance"""
    global _global_streamer
    if _global_streamer is None:
        _global_streamer = ProgressStreamer()
    return _global_streamer


def start_streaming(ws_port: int = 18790) -> ProgressStreamer:
    """
    Start progress streaming with WebSocket server

    Args:
        ws_port: WebSocket server port

    Returns:
        ProgressStreamer instance
    """
    if not HAS_DEPS:
        logger.warning("Cannot start streaming: dependencies not available")
        return ProgressStreamer()

    # Create WebSocket server
    ws_server = ClaudeLoopWebSocketServer(port=ws_port)

    # Start server in background
    asyncio.create_task(ws_server.start())

    # Create streamer with server
    global _global_streamer
    _global_streamer = ProgressStreamer(ws_server=ws_server)

    logger.info(f"Progress streaming started on ws://127.0.0.1:{ws_port}")

    return _global_streamer


# Convenience functions for synchronous code
def emit_story_started(prd_id: str, story_id: str, **kwargs):
    """Emit story started (sync)"""
    streamer = get_progress_streamer()
    streamer.emit_sync('story.started', prd_id, {'story_id': story_id, **kwargs}, story_id)


def emit_story_completed(prd_id: str, story_id: str, success: bool = True, **kwargs):
    """Emit story completed (sync)"""
    streamer = get_progress_streamer()
    streamer.emit_sync('story.completed', prd_id, {'story_id': story_id, 'success': success, **kwargs}, story_id)


def emit_test_run(prd_id: str, story_id: str, passed: int, failed: int, **kwargs):
    """Emit test run (sync)"""
    streamer = get_progress_streamer()
    streamer.emit_sync('test.run', prd_id, {'story_id': story_id, 'passed': passed, 'failed': failed, **kwargs}, story_id)


def emit_commit_created(prd_id: str, story_id: str, commit_hash: str, **kwargs):
    """Emit commit created (sync)"""
    streamer = get_progress_streamer()
    streamer.emit_sync('commit.created', prd_id, {'story_id': story_id, 'commit_hash': commit_hash, **kwargs}, story_id)


def emit_error(prd_id: str, story_id: str, error: str, **kwargs):
    """Emit error (sync)"""
    streamer = get_progress_streamer()
    streamer.emit_sync('error.occurred', prd_id, {'story_id': story_id, 'error': error, **kwargs}, story_id)


if __name__ == '__main__':
    # Example usage
    async def example():
        # Start streaming
        streamer = start_streaming()

        # Emit events
        await streamer.prd_started('PRD-001', total_stories=3)
        await streamer.story_started('PRD-001', 'US-001')
        await asyncio.sleep(1)
        await streamer.test_run('PRD-001', 'US-001', passed=10, failed=0)
        await asyncio.sleep(1)
        await streamer.commit_created('PRD-001', 'US-001', commit_hash='abc123')
        await asyncio.sleep(1)
        await streamer.story_completed('PRD-001', 'US-001', success=True)
        await asyncio.sleep(1)
        await streamer.prd_completed('PRD-001', success=True)

        # Keep server running
        await asyncio.sleep(10)

    asyncio.run(example())
