#!/usr/bin/env python3
"""
Session Locking for Claude-Loop

Provides file-based locking to prevent race conditions in parallel execution.
Supports timeout, automatic cleanup, and lock recovery.

Usage:
    from lib.session_lock import SessionLock, with_session_lock

    # Context manager
    with SessionLock('PRD-001') as lock:
        # Critical section - only one process at a time
        do_work()

    # Decorator
    @with_session_lock('PRD-001')
    def my_function():
        do_work()

    # Async support
    async with SessionLock('PRD-001') as lock:
        await do_async_work()
"""

import asyncio
import fcntl
import os
import time
from pathlib import Path
from typing import Optional
from contextlib import contextmanager, asynccontextmanager
from functools import wraps


class LockTimeout(Exception):
    """Raised when lock acquisition times out"""
    pass


class LockError(Exception):
    """Raised on lock-related errors"""
    pass


class SessionLock:
    """File-based session lock with timeout"""

    LOCKS_DIR = Path(".claude-loop/locks")
    DEFAULT_TIMEOUT = 300  # 5 minutes

    def __init__(
        self,
        lock_name: str,
        timeout: float = DEFAULT_TIMEOUT,
        auto_cleanup: bool = True
    ):
        """
        Initialize session lock

        Args:
            lock_name: Unique lock identifier (e.g., PRD ID, session ID)
            timeout: Lock acquisition timeout in seconds
            auto_cleanup: Automatically clean up stale locks
        """
        self.lock_name = lock_name
        self.timeout = timeout
        self.auto_cleanup = auto_cleanup

        # Create locks directory
        self.LOCKS_DIR.mkdir(parents=True, exist_ok=True)

        # Lock file path
        self.lock_file = self.LOCKS_DIR / f"{lock_name}.lock"
        self.lock_fd: Optional[int] = None
        self.acquired = False

    def acquire(self, blocking: bool = True) -> bool:
        """
        Acquire the lock

        Args:
            blocking: If True, block until lock is acquired or timeout

        Returns:
            True if lock acquired, False otherwise

        Raises:
            LockTimeout: If timeout exceeded
        """
        if self.acquired:
            return True

        # Open lock file
        self.lock_fd = os.open(
            self.lock_file,
            os.O_CREAT | os.O_RDWR | os.O_TRUNC
        )

        # Try to acquire lock
        start_time = time.time()

        while True:
            try:
                # Non-blocking lock attempt
                fcntl.flock(self.lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)

                # Lock acquired!
                self.acquired = True

                # Write metadata
                metadata = {
                    'pid': os.getpid(),
                    'acquired_at': time.time(),
                    'lock_name': self.lock_name
                }
                os.write(self.lock_fd, str(metadata).encode())
                os.fsync(self.lock_fd)

                return True

            except (IOError, OSError) as e:
                # Lock is held by another process
                if not blocking:
                    os.close(self.lock_fd)
                    self.lock_fd = None
                    return False

                # Check timeout
                elapsed = time.time() - start_time
                if elapsed >= self.timeout:
                    os.close(self.lock_fd)
                    self.lock_fd = None

                    # Try cleanup if stale
                    if self.auto_cleanup and self._is_stale():
                        self._force_cleanup()
                        # Retry once after cleanup
                        return self.acquire(blocking=False)

                    raise LockTimeout(
                        f"Failed to acquire lock '{self.lock_name}' within {self.timeout}s"
                    )

                # Wait a bit before retry
                time.sleep(0.1)

    def release(self):
        """Release the lock"""
        if not self.acquired:
            return

        try:
            if self.lock_fd is not None:
                fcntl.flock(self.lock_fd, fcntl.LOCK_UN)
                os.close(self.lock_fd)
                self.lock_fd = None

            # Remove lock file
            if self.lock_file.exists():
                self.lock_file.unlink()

        except Exception as e:
            raise LockError(f"Error releasing lock: {e}")
        finally:
            self.acquired = False

    def _is_stale(self) -> bool:
        """Check if lock is stale (holder process dead)"""
        if not self.lock_file.exists():
            return False

        try:
            # Read lock metadata
            with open(self.lock_file, 'r') as f:
                metadata = eval(f.read())

            # Check if process still exists
            pid = metadata.get('pid')
            if pid:
                try:
                    os.kill(pid, 0)  # Signal 0 checks existence
                    return False  # Process exists
                except OSError:
                    return True  # Process dead

        except Exception:
            pass

        return False

    def _force_cleanup(self):
        """Force cleanup of stale lock"""
        try:
            if self.lock_file.exists():
                self.lock_file.unlink()
        except Exception:
            pass

    def __enter__(self):
        """Context manager entry"""
        self.acquire()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.release()
        return False

    async def __aenter__(self):
        """Async context manager entry"""
        # Run acquire in executor to avoid blocking
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self.acquire)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self.release)
        return False


@contextmanager
def with_session_lock(lock_name: str, timeout: float = SessionLock.DEFAULT_TIMEOUT):
    """
    Context manager for session locking

    Usage:
        with with_session_lock('PRD-001'):
            do_work()
    """
    lock = SessionLock(lock_name, timeout=timeout)
    try:
        lock.acquire()
        yield lock
    finally:
        lock.release()


@asynccontextmanager
async def with_async_session_lock(lock_name: str, timeout: float = SessionLock.DEFAULT_TIMEOUT):
    """
    Async context manager for session locking

    Usage:
        async with with_async_session_lock('PRD-001'):
            await do_async_work()
    """
    lock = SessionLock(lock_name, timeout=timeout)
    try:
        await lock.__aenter__()
        yield lock
    finally:
        await lock.__aexit__(None, None, None)


def session_locked(lock_name: str, timeout: float = SessionLock.DEFAULT_TIMEOUT):
    """
    Decorator for automatic session locking

    Usage:
        @session_locked('PRD-001')
        def my_function():
            do_work()
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            with with_session_lock(lock_name, timeout):
                return func(*args, **kwargs)
        return wrapper
    return decorator


def cleanup_stale_locks(max_age_seconds: int = 3600):
    """
    Clean up stale lock files

    Args:
        max_age_seconds: Maximum age of lock file before considering stale
    """
    locks_dir = SessionLock.LOCKS_DIR
    if not locks_dir.exists():
        return

    now = time.time()
    cleaned = 0

    for lock_file in locks_dir.glob("*.lock"):
        try:
            # Check file age
            mtime = lock_file.stat().st_mtime
            age = now - mtime

            if age > max_age_seconds:
                # Check if process still exists
                try:
                    with open(lock_file, 'r') as f:
                        metadata = eval(f.read())
                    pid = metadata.get('pid')

                    if pid:
                        try:
                            os.kill(pid, 0)
                            continue  # Process exists, don't clean
                        except OSError:
                            pass  # Process dead, clean it

                except Exception:
                    pass

                # Remove stale lock
                lock_file.unlink()
                cleaned += 1

        except Exception:
            pass

    return cleaned


if __name__ == '__main__':
    # Example usage
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == 'cleanup':
        cleaned = cleanup_stale_locks()
        print(f"Cleaned up {cleaned} stale locks")
        sys.exit(0)

    # Demo
    print("Acquiring lock...")
    with SessionLock('test-lock', timeout=5) as lock:
        print("Lock acquired! Doing work...")
        time.sleep(2)
        print("Work done!")
    print("Lock released!")
