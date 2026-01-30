#!/usr/bin/env python3
"""
Example Python WebSocket client for claude-loop progress monitoring

Usage:
    # Monitor all events
    python examples/websocket_client.py

    # Monitor specific PRD
    python examples/websocket_client.py --prd PRD-001

    # Save events to file
    python examples/websocket_client.py --output events.jsonl

    # Quiet mode (only errors)
    python examples/websocket_client.py --quiet
"""

import asyncio
import argparse
import json
import sys
from datetime import datetime
from typing import Optional

try:
    import socketio
    HAS_DEPS = True
except ImportError:
    HAS_DEPS = False
    print("Error: python-socketio not installed. Install with: pip install python-socketio[asyncio_client]")
    sys.exit(1)


class ProgressMonitor:
    """Monitor claude-loop progress via WebSocket"""

    def __init__(self, host: str = '127.0.0.1', port: int = 18790, prd_id: Optional[str] = None,
                 output_file: Optional[str] = None, quiet: bool = False):
        self.host = host
        self.port = port
        self.prd_id = prd_id
        self.output_file = output_file
        self.quiet = quiet

        # Statistics
        self.stats = {
            'total_events': 0,
            'stories_started': 0,
            'stories_completed': 0,
            'tests_passed': 0,
            'tests_failed': 0,
            'commits': 0,
            'errors': 0
        }

        # Socket.IO client
        self.sio = socketio.AsyncClient()

        # Setup event handlers
        self.sio.on('connect', self.on_connect)
        self.sio.on('disconnect', self.on_disconnect)
        self.sio.on('event', self.on_event)
        self.sio.on('subscribed', self.on_subscribed)

    async def on_connect(self):
        """Handle connection"""
        self._print('info', f'Connected to claude-loop at {self.host}:{self.port}')

        # Subscribe to specific PRD if requested
        if self.prd_id:
            await self.sio.emit('subscribe_prd', {'prd_id': self.prd_id})

    async def on_disconnect(self):
        """Handle disconnection"""
        self._print('warning', 'Disconnected from claude-loop')

    async def on_subscribed(self, data):
        """Handle subscription confirmation"""
        prd_id = data.get('prd_id', 'unknown')
        self._print('info', f'Subscribed to PRD: {prd_id}')

    async def on_event(self, data):
        """Handle incoming event"""
        self.stats['total_events'] += 1

        event_type = data.get('type', 'unknown')
        event_data = data.get('data', {})
        prd_id = data.get('prd_id', '')
        timestamp = data.get('timestamp', '')

        # Update statistics
        self._update_stats(event_type, event_data)

        # Log event
        self._print_event(event_type, event_data, prd_id, timestamp)

        # Write to output file if specified
        if self.output_file:
            self._write_to_file(data)

    def _update_stats(self, event_type: str, data: dict):
        """Update statistics based on event"""
        if event_type == 'story.started':
            self.stats['stories_started'] += 1
        elif event_type == 'story.completed':
            self.stats['stories_completed'] += 1
        elif event_type == 'test.run':
            self.stats['tests_passed'] += data.get('passed', 0)
            self.stats['tests_failed'] += data.get('failed', 0)
        elif event_type == 'commit.created':
            self.stats['commits'] += 1
        elif event_type == 'error.occurred':
            self.stats['errors'] += 1

    def _print_event(self, event_type: str, data: dict, prd_id: str, timestamp: str):
        """Print event to console"""
        if self.quiet and event_type != 'error.occurred':
            return

        # Format message based on event type
        if event_type == 'story.started':
            message = f"📖 Story {data.get('story_id')} started"
            color = 'blue'
        elif event_type == 'story.completed':
            success = data.get('success', False)
            story_id = data.get('story_id')
            message = f"{'✓' if success else '✗'} Story {story_id} {'completed' if success else 'failed'}"
            color = 'green' if success else 'red'
        elif event_type == 'test.run':
            passed = data.get('passed', 0)
            failed = data.get('failed', 0)
            message = f"🧪 Tests: {passed} passed, {failed} failed"
            color = 'green' if failed == 0 else 'yellow'
        elif event_type == 'commit.created':
            commit_hash = data.get('commit_hash', '')[:7]
            message = f"📝 Commit created: {commit_hash}"
            color = 'green'
        elif event_type == 'error.occurred':
            error = data.get('error', 'Unknown error')
            message = f"❌ Error: {error}"
            color = 'red'
        else:
            message = f"Event: {event_type}"
            color = 'white'

        # Print with color
        prefix = f"[{prd_id}]" if prd_id else ""
        self._print(color, f"{prefix} {message}")

    def _print(self, level: str, message: str):
        """Print colored message"""
        colors = {
            'info': '\033[96m',      # Cyan
            'warning': '\033[93m',   # Yellow
            'error': '\033[91m',     # Red
            'green': '\033[92m',     # Green
            'blue': '\033[94m',      # Blue
            'red': '\033[91m',       # Red
            'yellow': '\033[93m',    # Yellow
            'white': '\033[97m',     # White
        }
        reset = '\033[0m'

        color = colors.get(level, '')
        timestamp = datetime.now().strftime('%H:%M:%S')
        print(f"{color}[{timestamp}] {message}{reset}")

    def _write_to_file(self, data: dict):
        """Write event to JSONL file"""
        try:
            with open(self.output_file, 'a') as f:
                f.write(json.dumps(data) + '\n')
        except Exception as e:
            self._print('error', f"Failed to write to file: {e}")

    def print_stats(self):
        """Print statistics"""
        print("\n" + "="*50)
        print("Statistics:")
        print(f"  Total Events: {self.stats['total_events']}")
        print(f"  Stories Started: {self.stats['stories_started']}")
        print(f"  Stories Completed: {self.stats['stories_completed']}")
        print(f"  Tests Passed: {self.stats['tests_passed']}")
        print(f"  Tests Failed: {self.stats['tests_failed']}")
        print(f"  Commits: {self.stats['commits']}")
        print(f"  Errors: {self.stats['errors']}")
        print("="*50 + "\n")

    async def connect(self):
        """Connect to WebSocket server"""
        url = f'http://{self.host}:{self.port}'
        await self.sio.connect(url)

    async def disconnect(self):
        """Disconnect from server"""
        await self.sio.disconnect()

    async def run(self):
        """Run the monitor"""
        try:
            await self.connect()
            self._print('info', 'Monitoring events (Ctrl+C to stop)...')

            # Keep running until interrupted
            while True:
                await asyncio.sleep(1)

        except KeyboardInterrupt:
            self._print('info', 'Stopping monitor...')
            self.print_stats()
        except Exception as e:
            self._print('error', f'Error: {e}')
        finally:
            await self.disconnect()


def main():
    parser = argparse.ArgumentParser(description='Monitor claude-loop progress via WebSocket')
    parser.add_argument('--host', default='127.0.0.1', help='WebSocket server host')
    parser.add_argument('--port', type=int, default=18790, help='WebSocket server port')
    parser.add_argument('--prd', dest='prd_id', help='Subscribe to specific PRD')
    parser.add_argument('--output', dest='output_file', help='Write events to JSONL file')
    parser.add_argument('--quiet', action='store_true', help='Only show errors')

    args = parser.parse_args()

    monitor = ProgressMonitor(
        host=args.host,
        port=args.port,
        prd_id=args.prd_id,
        output_file=args.output_file,
        quiet=args.quiet
    )

    asyncio.run(monitor.run())


if __name__ == '__main__':
    main()
