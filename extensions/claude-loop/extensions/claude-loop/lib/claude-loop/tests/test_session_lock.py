#!/usr/bin/env python3
"""Tests for session_lock.py"""

import pytest
import time
import os
import multiprocessing
from pathlib import Path
from lib.session_lock import SessionLock, with_session_lock, LockTimeout


@pytest.fixture
def lock_name():
    """Generate unique lock name for test"""
    return f"test-lock-{os.getpid()}-{time.time()}"


@pytest.fixture(autouse=True)
def cleanup_locks():
    """Clean up test locks after each test"""
    yield
    # Cleanup
    locks_dir = SessionLock.LOCKS_DIR
    if locks_dir.exists():
        for lock_file in locks_dir.glob("test-lock-*.lock"):
            try:
                lock_file.unlink()
            except:
                pass


def test_lock_acquire_and_release(lock_name):
    """Test basic lock acquisition and release"""
    lock = SessionLock(lock_name, timeout=5)

    # Acquire lock
    assert lock.acquire()
    assert lock.acquired

    # Release lock
    lock.release()
    assert not lock.acquired


def test_lock_context_manager(lock_name):
    """Test lock as context manager"""
    with SessionLock(lock_name, timeout=5) as lock:
        assert lock.acquired

    # Lock should be released after context
    assert not lock.acquired


def test_lock_blocks_concurrent_access(lock_name):
    """Test that lock blocks concurrent access"""
    def try_acquire(lock_name, result_queue):
        """Try to acquire lock in subprocess"""
        lock = SessionLock(lock_name, timeout=1)
        try:
            acquired = lock.acquire(blocking=True)
            result_queue.put(('success' if acquired else 'failed', time.time()))
            if acquired:
                time.sleep(0.5)
                lock.release()
        except LockTimeout:
            result_queue.put(('timeout', time.time()))

    # Acquire lock in main process
    lock = SessionLock(lock_name, timeout=5)
    lock.acquire()

    # Try to acquire in subprocess (should timeout)
    result_queue = multiprocessing.Queue()
    p = multiprocessing.Process(target=try_acquire, args=(lock_name, result_queue))
    p.start()

    # Wait for subprocess
    p.join(timeout=3)

    # Check result
    result, _ = result_queue.get(timeout=1)
    assert result == 'timeout'

    # Release main lock
    lock.release()


def test_lock_non_blocking(lock_name):
    """Test non-blocking lock acquisition"""
    lock1 = SessionLock(lock_name, timeout=5)
    lock1.acquire()

    # Try non-blocking acquire (should fail immediately)
    lock2 = SessionLock(lock_name, timeout=5)
    assert not lock2.acquire(blocking=False)

    lock1.release()


def test_lock_timeout(lock_name):
    """Test lock timeout"""
    def hold_lock(lock_name):
        """Hold lock for a while"""
        lock = SessionLock(lock_name, timeout=5)
        lock.acquire()
        time.sleep(3)
        lock.release()

    # Start process that holds lock
    p = multiprocessing.Process(target=hold_lock, args=(lock_name,))
    p.start()

    # Wait for lock to be acquired
    time.sleep(0.5)

    # Try to acquire with short timeout (should raise LockTimeout)
    lock = SessionLock(lock_name, timeout=1)

    with pytest.raises(LockTimeout):
        lock.acquire()

    # Cleanup
    p.join()


def test_lock_reacquire(lock_name):
    """Test acquiring same lock twice"""
    lock = SessionLock(lock_name, timeout=5)

    # First acquire
    assert lock.acquire()

    # Second acquire (should return True immediately)
    assert lock.acquire()
    assert lock.acquired

    lock.release()


def test_with_session_lock_context(lock_name):
    """Test with_session_lock context manager"""
    results = []

    with with_session_lock(lock_name):
        results.append('acquired')

    results.append('released')

    assert results == ['acquired', 'released']


def test_concurrent_locks_different_names():
    """Test that different locks don't interfere"""
    lock1 = SessionLock('lock-1', timeout=5)
    lock2 = SessionLock('lock-2', timeout=5)

    # Both should acquire successfully
    assert lock1.acquire()
    assert lock2.acquire()

    lock1.release()
    lock2.release()


def test_lock_file_created(lock_name):
    """Test that lock file is created"""
    lock = SessionLock(lock_name, timeout=5)
    lock.acquire()

    # Check file exists
    assert lock.lock_file.exists()

    lock.release()

    # File should be removed
    assert not lock.lock_file.exists()


def test_lock_metadata(lock_name):
    """Test lock file contains metadata"""
    lock = SessionLock(lock_name, timeout=5)
    lock.acquire()

    # Read metadata
    with open(lock.lock_file, 'r') as f:
        content = f.read()

    assert 'pid' in content
    assert 'acquired_at' in content
    assert lock_name in content

    lock.release()


@pytest.mark.asyncio
async def test_async_lock(lock_name):
    """Test async lock context manager"""
    import asyncio

    acquired = False
    released = False

    async with SessionLock(lock_name, timeout=5):
        acquired = True
        await asyncio.sleep(0.1)

    released = True

    assert acquired
    assert released


def test_lock_cleanup_after_exception(lock_name):
    """Test lock is released even if exception occurs"""
    lock = SessionLock(lock_name, timeout=5)

    try:
        with lock:
            raise ValueError("Test error")
    except ValueError:
        pass

    # Lock should be released
    assert not lock.acquired
    assert not lock.lock_file.exists()


def test_multiple_acquires_same_lock(lock_name):
    """Test that acquiring twice doesn't create issues"""
    lock = SessionLock(lock_name, timeout=5)

    lock.acquire()
    lock.acquire()  # Should be idempotent

    assert lock.acquired

    lock.release()
    assert not lock.acquired


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
