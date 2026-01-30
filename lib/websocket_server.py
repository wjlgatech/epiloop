#!/usr/bin/env python3
"""
WebSocket Server for Claude-Loop Real-Time Communication

Provides WebSocket-based control plane for:
- Real-time progress streaming
- Remote PRD control (start/stop/pause)
- Live log streaming
- Multi-client support

Usage:
    python lib/websocket_server.py --port 18790

    # Or programmatically
    from lib.websocket_server import ClaudeLoopWebSocketServer

    server = ClaudeLoopWebSocketServer(port=18790)
    await server.start()

    # Broadcast event
    await server.broadcast('story_complete', {
        'prd_id': 'PRD-001',
        'story_id': 'US-001'
    })
"""

import asyncio
import json
import logging
from datetime import datetime
from typing import Dict, Set, Callable, Any, Optional
from dataclasses import dataclass, asdict
import signal
import sys

try:
    import socketio
    HAS_SOCKETIO = True
except ImportError:
    HAS_SOCKETIO = False

try:
    import aiohttp
    from aiohttp import web
    HAS_AIOHTTP = True
except ImportError:
    HAS_AIOHTTP = False


logger = logging.getLogger(__name__)


@dataclass
class Event:
    """WebSocket event"""
    type: str
    prd_id: str
    timestamp: str
    data: Dict[str, Any]
    story_id: Optional[str] = None


class ClaudeLoopWebSocketServer:
    """WebSocket server for real-time communication"""

    def __init__(self, host: str = '127.0.0.1', port: int = 18790):
        """
        Initialize WebSocket server

        Args:
            host: Host to bind to (default: 127.0.0.1 - loopback only)
            port: Port to bind to (default: 18790)
        """
        if not HAS_SOCKETIO or not HAS_AIOHTTP:
            raise ImportError(
                "socketio and aiohttp required. Install: pip install python-socketio aiohttp"
            )

        self.host = host
        self.port = port
        self.sio = socketio.AsyncServer(
            async_mode='aiohttp',
            cors_allowed_origins='*',
            logger=False,
            engineio_logger=False
        )
        self.app = web.Application()
        self.sio.attach(self.app)

        # Client management
        self.clients: Set[str] = set()
        self.subscriptions: Dict[str, Set[str]] = {}  # prd_id -> set of client sids

        # Event handlers
        self.event_handlers: Dict[str, Callable] = {}

        # Setup routes
        self._setup_routes()
        self._setup_socket_handlers()

        # Server state
        self.runner: Optional[web.AppRunner] = None
        self.site: Optional[web.TCPSite] = None

    def _setup_routes(self):
        """Setup HTTP routes"""
        self.app.router.add_get('/', self._handle_root)
        self.app.router.add_get('/health', self._handle_health)
        self.app.router.add_get('/status', self._handle_status)

    def _setup_socket_handlers(self):
        """Setup Socket.IO event handlers"""

        @self.sio.event
        async def connect(sid, environ):
            """Handle client connection"""
            self.clients.add(sid)
            logger.info(f"Client connected: {sid} (total: {len(self.clients)})")
            await self.sio.emit('connected', {'sid': sid}, room=sid)

        @self.sio.event
        async def disconnect(sid):
            """Handle client disconnection"""
            self.clients.discard(sid)

            # Remove from all subscriptions
            for prd_id, subs in list(self.subscriptions.items()):
                subs.discard(sid)
                if not subs:
                    del self.subscriptions[prd_id]

            logger.info(f"Client disconnected: {sid} (total: {len(self.clients)})")

        @self.sio.event
        async def subscribe_prd(sid, data):
            """Subscribe to PRD updates"""
            prd_id = data.get('prd_id')
            if not prd_id:
                await self.sio.emit('error', {'message': 'prd_id required'}, room=sid)
                return

            if prd_id not in self.subscriptions:
                self.subscriptions[prd_id] = set()
            self.subscriptions[prd_id].add(sid)

            await self.sio.emit('subscribed', {'prd_id': prd_id}, room=sid)
            logger.info(f"Client {sid} subscribed to PRD {prd_id}")

        @self.sio.event
        async def unsubscribe_prd(sid, data):
            """Unsubscribe from PRD updates"""
            prd_id = data.get('prd_id')
            if prd_id and prd_id in self.subscriptions:
                self.subscriptions[prd_id].discard(sid)
                if not self.subscriptions[prd_id]:
                    del self.subscriptions[prd_id]
                await self.sio.emit('unsubscribed', {'prd_id': prd_id}, room=sid)

        @self.sio.event
        async def control_prd(sid, data):
            """Control PRD execution (start/stop/pause)"""
            action = data.get('action')
            prd_id = data.get('prd_id')

            if not action or not prd_id:
                await self.sio.emit('error', {'message': 'action and prd_id required'}, room=sid)
                return

            # Call custom handler if registered
            handler = self.event_handlers.get('control_prd')
            if handler:
                result = await handler(action, prd_id)
                await self.sio.emit('control_result', {
                    'action': action,
                    'prd_id': prd_id,
                    'result': result
                }, room=sid)
            else:
                await self.sio.emit('error', {
                    'message': 'No control handler registered'
                }, room=sid)

        @self.sio.event
        async def event(sid, data):
            """Receive event from client and broadcast to all"""
            logger.info(f"Received event from {sid}: {data.get('type')}")
            logger.info(f"Broadcasting to {len(self.clients)} clients: {self.clients}")
            # Broadcast to all clients
            await self.sio.emit('event', data)
            logger.info(f"Broadcast complete")

        @self.sio.event
        async def execute_command(sid, data):
            """Execute a claude-loop command from client"""
            command = data.get('command')
            if not command:
                await self.sio.emit('command_error', {'error': 'Command required'}, room=sid)
                return

            logger.info(f"Received command from {sid}: {command}")

            # Call custom handler if registered
            handler = self.event_handlers.get('execute_command')
            if handler:
                try:
                    result = await handler(command, sid)
                    await self.sio.emit('command_started', result, room=sid)
                except Exception as e:
                    await self.sio.emit('command_error', {'error': str(e)}, room=sid)
            else:
                await self.sio.emit('command_error', {
                    'error': 'Command execution not configured yet'
                }, room=sid)

        @self.sio.event
        async def stop_execution(sid, data):
            """Stop current execution"""
            logger.info(f"Stop execution requested by {sid}")

            handler = self.event_handlers.get('stop_execution')
            if handler:
                try:
                    result = await handler(sid)
                    await self.sio.emit('command_stopped', result, room=sid)
                except Exception as e:
                    await self.sio.emit('command_error', {'error': str(e)}, room=sid)
            else:
                await self.sio.emit('command_error', {
                    'error': 'Stop execution not configured yet'
                }, room=sid)

    async def _handle_root(self, request):
        """Handle root HTTP request"""
        return web.Response(text=f"Claude-Loop WebSocket Server\nListening on ws://{self.host}:{self.port}")

    async def _handle_health(self, request):
        """Handle health check"""
        return web.json_response({
            'status': 'healthy',
            'clients': len(self.clients),
            'subscriptions': len(self.subscriptions)
        })

    async def _handle_status(self, request):
        """Handle status request"""
        return web.json_response({
            'host': self.host,
            'port': self.port,
            'clients': len(self.clients),
            'subscriptions': {
                prd_id: len(sids)
                for prd_id, sids in self.subscriptions.items()
            }
        })

    async def broadcast(self, event_type: str, data: Dict[str, Any]):
        """
        Broadcast event to all connected clients

        Args:
            event_type: Event type (e.g., 'story_complete')
            data: Event data
        """
        event = Event(
            type=event_type,
            prd_id=data.get('prd_id', ''),
            story_id=data.get('story_id'),
            timestamp=datetime.utcnow().isoformat() + 'Z',
            data=data
        )

        await self.sio.emit('event', asdict(event))

    async def send_to_prd_subscribers(self, prd_id: str, event_type: str, data: Dict[str, Any]):
        """
        Send event to all subscribers of a specific PRD

        Args:
            prd_id: PRD identifier
            event_type: Event type
            data: Event data
        """
        if prd_id not in self.subscriptions:
            return

        event = Event(
            type=event_type,
            prd_id=prd_id,
            story_id=data.get('story_id'),
            timestamp=datetime.utcnow().isoformat() + 'Z',
            data=data
        )

        for sid in self.subscriptions[prd_id]:
            await self.sio.emit('event', asdict(event), room=sid)

    async def send_to_client(self, client_id: str, event_type: str, data: Dict[str, Any]):
        """
        Send event to specific client

        Args:
            client_id: Client session ID
            event_type: Event type
            data: Event data
        """
        if client_id not in self.clients:
            return

        event = Event(
            type=event_type,
            prd_id=data.get('prd_id', ''),
            story_id=data.get('story_id'),
            timestamp=datetime.utcnow().isoformat() + 'Z',
            data=data
        )

        await self.sio.emit('event', asdict(event), room=client_id)

    def register_handler(self, event_type: str, handler: Callable):
        """
        Register custom event handler

        Args:
            event_type: Event type to handle
            handler: Async callable that handles the event
        """
        self.event_handlers[event_type] = handler

    async def start(self):
        """Start the WebSocket server"""
        self.runner = web.AppRunner(self.app)
        await self.runner.setup()
        self.site = web.TCPSite(self.runner, self.host, self.port)
        await self.site.start()

        logger.info(f"WebSocket server started on ws://{self.host}:{self.port}")
        print(f"🚀 Claude-Loop WebSocket Server")
        print(f"   Listening on ws://{self.host}:{self.port}")
        print(f"   Health check: http://{self.host}:{self.port}/health")
        print(f"   Status: http://{self.host}:{self.port}/status")

    async def stop(self):
        """Stop the WebSocket server"""
        if self.site:
            await self.site.stop()
        if self.runner:
            await self.runner.cleanup()
        logger.info("WebSocket server stopped")

    async def run_forever(self):
        """Run server until interrupted"""
        await self.start()

        # Setup signal handlers
        loop = asyncio.get_event_loop()
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(sig, lambda: asyncio.create_task(self.stop()))

        # Keep running
        try:
            while True:
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            pass
        finally:
            await self.stop()


async def main():
    """Main entry point for CLI"""
    import argparse

    parser = argparse.ArgumentParser(description='Claude-Loop WebSocket Server')
    parser.add_argument('--host', default='127.0.0.1', help='Host to bind to')
    parser.add_argument('--port', type=int, default=18790, help='Port to bind to')
    parser.add_argument('--debug', action='store_true', help='Enable debug logging')

    args = parser.parse_args()

    # Setup logging
    logging.basicConfig(
        level=logging.DEBUG if args.debug else logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # Create and run server
    server = ClaudeLoopWebSocketServer(host=args.host, port=args.port)
    await server.run_forever()


if __name__ == '__main__':
    asyncio.run(main())
